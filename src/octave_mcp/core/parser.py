"""OCTAVE parser with lenient input support.

Implements P1.3: lenient_parser_with_envelope_completion

Parses lexer tokens into AST with:
- Envelope inference for single documents
- Whitespace normalization around ::
- Nested block structure with indentation
- META block extraction
- YAML frontmatter stripping (Issue #91)
- Deep nesting warning and error detection (Issue #192)
"""

from typing import Any

from octave_mcp.core.ast_nodes import (
    Assignment,
    ASTNode,
    Block,
    Comment,
    Document,
    HolographicValue,
    InlineMap,
    ListValue,
    Section,
)
from octave_mcp.core.lexer import Token, TokenType, tokenize

# Issue #192: Deep nesting detection constants
# Warning threshold: emit W_DEEP_NESTING at this depth (configurable, default 5)
DEFAULT_DEEP_NESTING_THRESHOLD = 5
# Maximum nesting: hard error at this depth (implementation cap per spec)
MAX_NESTING_DEPTH = 100


def _strip_yaml_frontmatter(content: str) -> tuple[str, str | None]:
    """Strip YAML frontmatter from document content.

    YAML frontmatter is a block at the start of a document delimited by --- markers.
    This is commonly used in HestAI agent definitions and other markdown-like files.

    Issue #91: The OCTAVE lexer does not recognize YAML syntax (parentheses, etc.)
    so frontmatter must be stripped before tokenization.

    Issue #91 Rework: Performance and line number preservation fixes:
    - Fast path: Check content.startswith("---") BEFORE splitting (O(1) vs O(N))
    - Line offset: Replace frontmatter with equivalent newlines to preserve line numbers

    Args:
        content: Raw document content

    Returns:
        Tuple of (content_without_frontmatter, raw_frontmatter_or_none)
        When frontmatter is stripped, the returned content has the frontmatter
        replaced with newlines to preserve line number mapping.

    Example:
        >>> content = '''---
        ... name: Agent (Specialist)
        ... ---
        ...
        ... ===DOC===
        ... META::value
        ... ===END==='''
        >>> stripped, frontmatter = _strip_yaml_frontmatter(content)
        >>> '(' in stripped
        False
        >>> 'Agent (Specialist)' in frontmatter
        True
    """
    # Fast path: check first chars before splitting (true O(1) for non-frontmatter files)
    # This avoids O(N) split operation for the majority of files without frontmatter
    # Issue #91 Rework: Standard YAML frontmatter MUST start at column 0, line 1.
    # No lstrip() fallback - that creates O(N) string copy even for non-frontmatter.
    if not content.startswith("---"):
        return content, None

    lines = content.split("\n")

    # Check if document starts with YAML frontmatter marker
    if not lines or lines[0].strip() != "---":
        return content, None

    # Find the closing --- marker
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            # Found closing marker
            # Extract frontmatter (excluding the --- markers themselves)
            frontmatter_lines = lines[1:i]
            raw_frontmatter = "\n".join(frontmatter_lines)

            # Issue #91 Rework: Replace frontmatter with newlines to preserve line numbers
            # Frontmatter occupies lines 0 through i (inclusive of closing marker)
            # We need (i + 1) newlines to keep remaining content at correct line numbers
            frontmatter_line_count = i + 1
            padding = "\n" * frontmatter_line_count
            remaining_lines = lines[i + 1 :]
            stripped_content = padding + "\n".join(remaining_lines)

            return stripped_content, raw_frontmatter

    # No closing marker found - treat entire content as non-frontmatter
    return content, None


# Unified set of operators valid in expression contexts (GH#62, GH#65)
# This replaces ad-hoc inline operator checks in parse_flow_expression.
# By centralizing expression operators, we ensure consistent handling
# across the parser and make it easy to add new operators.
EXPRESSION_OPERATORS: frozenset[TokenType] = frozenset(
    {
        TokenType.FLOW,  # → or ->
        TokenType.SYNTHESIS,  # ⊕ or +
        TokenType.AT,  # @
        TokenType.CONCAT,  # ⧺ or ~
        TokenType.TENSION,  # ⇌ or vs or <->
        TokenType.CONSTRAINT,  # ∧ or &
        TokenType.ALTERNATIVE,  # ∨ or |
    }
)

# Semantic classification of tokens that can appear in values (#140/#141)
# This prevents data loss when VERSION, BOOLEAN, NULL, or STRING tokens
# appear in multi-word values like "Release 1.2.3 is ready"
# Issue #181: Added VARIABLE for $VAR placeholders
VALUE_TOKENS: frozenset[TokenType] = frozenset(
    {
        TokenType.IDENTIFIER,
        TokenType.NUMBER,
        TokenType.VERSION,
        TokenType.BOOLEAN,
        TokenType.NULL,
        TokenType.STRING,
        TokenType.VARIABLE,
    }
)


def _token_to_str(token: Token) -> str:
    """Convert token to string, preserving raw lexeme for NUMBER tokens (GH#66).

    For NUMBER tokens, uses the raw lexeme to preserve scientific notation format
    (e.g., '1e10' instead of '10000000000.0'). For other tokens, uses str(value).

    Issue #140/#141: Added support for VERSION, BOOLEAN, NULL, and STRING tokens
    to prevent data loss in multi-word values.
    Issue #181: Added support for VARIABLE tokens ($VAR placeholders).
    """
    if token.type == TokenType.NUMBER and token.raw is not None:
        return token.raw
    elif token.type == TokenType.BOOLEAN:
        return "true" if token.value else "false"
    elif token.type == TokenType.NULL:
        return "null"
    elif token.type == TokenType.VERSION:
        return str(token.value)
    elif token.type == TokenType.STRING:
        # Preserve quotes for strings in multi-word values
        return f'"{token.value}"'
    elif token.type == TokenType.VARIABLE:
        # Issue #181: Preserve variable as-is (e.g., $VAR, $1:name)
        return str(token.value)
    return str(token.value)


class ParserError(Exception):
    """Parser error with position information."""

    def __init__(self, message: str, token: Token | None = None, error_code: str = "E001"):
        self.message = message
        self.token = token
        self.error_code = error_code
        self.code = error_code  # Alias for consistent access
        if token:
            super().__init__(f"{error_code} at line {token.line}, column {token.column}: {message}")
        else:
            super().__init__(f"{error_code}: {message}")


class Parser:
    """OCTAVE parser with lenient input support."""

    def __init__(
        self,
        tokens: list[Token],
        strict_structure: bool = False,
        deep_nesting_threshold: int = DEFAULT_DEEP_NESTING_THRESHOLD,
    ):
        """Initialize parser with token stream.

        Args:
            tokens: List of tokens to parse
            strict_structure: If True, raise ParserError on structural issues (e.g. unclosed lists)
                            instead of leniently recovering.
            deep_nesting_threshold: Emit W_DEEP_NESTING warning at this nesting depth.
                                   Default is 5. Set to 0 to disable warnings.
        """
        self.tokens = tokens
        self.strict_structure = strict_structure
        self.deep_nesting_threshold = deep_nesting_threshold
        self.pos = 0
        self.current_indent = 0
        self.warnings: list[dict] = []  # I4 audit trail for lenient parsing events
        self.bracket_depth = 0  # GH#184: Track bracket nesting for NEVER rule validation
        self._deep_nesting_warned_at: set[int] = set()  # Track lines where warning was emitted

    def current(self) -> Token:
        """Get current token."""
        if self.pos >= len(self.tokens):
            return self.tokens[-1]  # Return EOF
        return self.tokens[self.pos]

    def peek(self, offset: int = 1) -> Token:
        """Peek ahead at token."""
        pos = self.pos + offset
        if pos >= len(self.tokens):
            return self.tokens[-1]  # Return EOF
        return self.tokens[pos]

    def advance(self) -> Token:
        """Consume and return current token."""
        token = self.current()
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return token

    def expect(self, token_type: TokenType) -> Token:
        """Expect specific token type and consume it."""
        token = self.current()
        if token.type != token_type:
            raise ParserError(f"Expected {token_type}, got {token.type}", token)
        return self.advance()

    def skip_whitespace(self, skip_comments: bool = True) -> None:
        """Skip newlines and optionally comments.

        Args:
            skip_comments: If True (default), also skip COMMENT tokens.
                          Set to False for Issue #182 comment preservation.
        """
        skip_types = {TokenType.NEWLINE}
        if skip_comments:
            skip_types.add(TokenType.COMMENT)
        while self.current().type in skip_types:
            self.advance()

    def collect_leading_comments(self) -> list[str]:
        """Collect leading comment lines before a node.

        Issue #182: Comment preservation.
        Collects all COMMENT tokens appearing before the next non-whitespace token.
        Called before parsing a node to capture its leading comments.

        Returns:
            List of comment text strings (without // prefix)
        """
        comments: list[str] = []
        while self.current().type in (TokenType.NEWLINE, TokenType.COMMENT, TokenType.INDENT):
            if self.current().type == TokenType.COMMENT:
                comments.append(self.current().value)
            self.advance()
        return comments

    def collect_trailing_comment(self) -> str | None:
        """Collect end-of-line comment after a value.

        Issue #182: Comment preservation.
        Checks for a COMMENT token on the same line after a value.
        Must be called immediately after parsing a value, before newline is consumed.

        Returns:
            Comment text string (without // prefix) or None
        """
        if self.current().type == TokenType.COMMENT:
            comment: str = str(self.current().value)
            self.advance()
            return comment
        return None

    def _consume_bracket_annotation(self, capture: bool = False) -> str | None:
        """Consume bracket annotation [content] if present.

        Handles nested brackets properly. Used for:
        - Section annotations: §0::META[schema_hints,versioning]
        - Colon-path annotations: HERMES:API_TIMEOUT[note]
        - Value annotations: DONE[annotation], PENDING[[nested,content]]

        Args:
            capture: If True, capture and return the annotation content.
                    If False, just skip the bracket block.

        Returns:
            Captured annotation string if capture=True and brackets present,
            None otherwise.
        """
        if self.current().type != TokenType.LIST_START:
            return None

        bracket_depth = 1
        self.advance()  # Consume [

        if not capture:
            # Fast path: just skip without capturing
            while bracket_depth > 0 and self.current().type != TokenType.EOF:
                if self.current().type == TokenType.LIST_START:
                    bracket_depth += 1
                elif self.current().type == TokenType.LIST_END:
                    bracket_depth -= 1
                self.advance()
            return None

        # Capture mode: collect tokens for annotation string
        annotation_tokens: list[str] = []

        while bracket_depth > 0 and self.current().type != TokenType.EOF:
            if self.current().type == TokenType.LIST_START:
                bracket_depth += 1
                annotation_tokens.append("[")
            elif self.current().type == TokenType.LIST_END:
                bracket_depth -= 1
                if bracket_depth > 0:  # Don't include the final ]
                    annotation_tokens.append("]")
            elif self.current().type == TokenType.IDENTIFIER:
                annotation_tokens.append(self.current().value)
            elif self.current().type == TokenType.COMMA:
                annotation_tokens.append(",")
            elif self.current().type == TokenType.STRING:
                annotation_tokens.append(f'"{self.current().value}"')
            self.advance()

        return "".join(annotation_tokens) if annotation_tokens else None

    def _parse_block_target_annotation(self) -> str | None:
        """Parse block target annotation [->TARGET] syntax.

        Issue #189: Block inheritance per spec section 4::BLOCK_INHERITANCE.
        Syntax: BLOCK[->TARGET]: where children inherit TARGET.

        Expected token sequence: [ -> IDENTIFIER ] or [ -> SECTION IDENTIFIER ]
        The FLOW token (->) is required. SECTION token (section marker) is optional.

        Returns:
            Target name (without section marker) if valid annotation,
            None if annotation is not a target (e.g., [note] annotation).
        """
        if self.current().type != TokenType.LIST_START:
            return None

        self.advance()  # Consume [

        # Check for FLOW token (->) to identify target annotation
        # Regular annotations like [note] don't start with ->
        if self.current().type != TokenType.FLOW:
            # Not a target annotation, rewind is not possible so skip bracket
            # This is a regular annotation [something], consume until ]
            bracket_depth = 1
            while bracket_depth > 0 and self.current().type != TokenType.EOF:
                if self.current().type == TokenType.LIST_START:
                    bracket_depth += 1
                elif self.current().type == TokenType.LIST_END:
                    bracket_depth -= 1
                self.advance()
            return None

        self.advance()  # Consume ->

        # Expect SECTION (section marker) or IDENTIFIER (target name)
        target: str | None = None

        if self.current().type == TokenType.SECTION:
            # Skip section marker, get following identifier
            self.advance()
            if self.current().type == TokenType.IDENTIFIER:
                target = self.current().value
                self.advance()
        elif self.current().type == TokenType.IDENTIFIER:
            target = self.current().value
            self.advance()

        # Consume closing ]
        if self.current().type == TokenType.LIST_END:
            self.advance()

        return target

    def parse_document(self) -> Document:
        """Parse a complete OCTAVE document."""
        doc = Document()
        self.skip_whitespace()

        # Issue #48 Phase 2: Check for grammar sentinel OCTAVE::VERSION
        # The lexer now produces a GRAMMAR_SENTINEL token for this pattern
        if self.current().type == TokenType.GRAMMAR_SENTINEL:
            doc.grammar_version = self.current().value  # Version string from lexer
            self.advance()
            self.skip_whitespace()

        # Check for explicit envelope
        if self.current().type == TokenType.ENVELOPE_START:
            token = self.advance()
            doc.name = token.value
            # Issue #182: Don't skip comments after envelope start
            self.skip_whitespace(skip_comments=False)
        else:
            # Infer envelope for single doc
            doc.name = "INFERRED"

        # Parse META block first if present
        if self.current().type == TokenType.IDENTIFIER and self.current().value == "META":
            meta_block = self.parse_meta_block()
            doc.meta = meta_block
            # Issue #182: Don't skip comments after META
            self.skip_whitespace(skip_comments=False)

        # Check for separator
        if self.current().type == TokenType.SEPARATOR:
            doc.has_separator = True
            self.advance()
            # Issue #182: Don't skip comments after separator
            self.skip_whitespace(skip_comments=False)

        # Parse document body
        # Issue #182: Track pending comments for next section
        pending_comments: list[str] = []

        while self.current().type != TokenType.ENVELOPE_END and self.current().type != TokenType.EOF:
            # Skip indentation at document level
            if self.current().type == TokenType.INDENT:
                self.advance()
                continue

            # Issue #182: Collect comments as pending for next section
            if self.current().type == TokenType.COMMENT:
                pending_comments.append(self.current().value)
                self.advance()
                continue

            # Skip newlines
            if self.current().type == TokenType.NEWLINE:
                self.advance()
                continue

            # Parse section (assignment or block) with pending comments
            section = self.parse_section(0, pending_comments)
            pending_comments = []  # Reset after passing to section
            if section:
                doc.sections.append(section)
            elif self.current().type not in (TokenType.ENVELOPE_END, TokenType.EOF):
                # Consume unexpected token to prevent infinite loop
                # GH#64: Warning is already emitted by parse_section for bare identifiers
                self.advance()

            # Issue #182: Don't skip comments - the loop will collect them
            # as pending_comments for the next section
            # (removed self.skip_whitespace() call that was consuming comments)

        # Issue #182: Any remaining pending_comments have no following section
        # (they appear before ===END===), so store them as document trailing comments
        if pending_comments:
            doc.trailing_comments = pending_comments

        # Expect END envelope (lenient - allow missing)
        if self.current().type == TokenType.ENVELOPE_END:
            self.advance()

        return doc

    def parse_meta_block(self) -> dict[str, Any]:
        """Parse META block into dictionary.

        Issue #179: Detects duplicate keys and emits warnings per I4 auditability.
        Per spec: DUPLICATES::keys_must_be_unique_per_block
        """
        meta: dict[str, Any] = {}
        # Issue #179: Track key positions for duplicate detection
        key_positions: dict[str, int] = {}  # key -> first occurrence line number

        # Consume META identifier
        self.expect(TokenType.IDENTIFIER)
        self.expect(TokenType.BLOCK)
        self.skip_whitespace()

        # Expect indentation for META children
        if self.current().type != TokenType.INDENT:
            return meta

        indent_level = self.current().value
        self.advance()
        has_indented = True  # We just consumed the first indent

        # Parse META fields
        while True:
            # End conditions
            if self.current().type == TokenType.EOF:
                break
            if self.current().type == TokenType.ENVELOPE_END:
                break

            # Handle indentation
            if self.current().type == TokenType.INDENT:
                if self.current().value < indent_level:
                    break  # Dedent, end of META block
                self.advance()
                has_indented = True
                continue

            # Handle newlines
            if self.current().type == TokenType.NEWLINE:
                self.advance()
                has_indented = False
                continue

            # Parse META field (must be assignment)
            if self.current().type == TokenType.IDENTIFIER:
                # Check if we have valid indentation for this field
                if indent_level > 0 and not has_indented:
                    break  # Dedent to 0 (implicit)

                key = self.current().value
                key_line = self.current().line
                self.advance()

                if self.current().type == TokenType.ASSIGN:
                    self.advance()
                    value = self.parse_value()

                    # Issue #179: Check for duplicate key
                    if key in key_positions:
                        # I4 Audit: Emit warning for duplicate key
                        # Per I4: "If bits lost must have receipt"
                        self.warnings.append(
                            {
                                "type": "lenient_parse",
                                "subtype": "duplicate_key",
                                "key": key,
                                "first_line": key_positions[key],
                                "duplicate_line": key_line,
                                "message": (
                                    f"W_DUPLICATE_KEY::{key} at line {key_line} "
                                    f"overwrites previous definition at line {key_positions[key]}"
                                ),
                            }
                        )
                    else:
                        # Track first occurrence
                        key_positions[key] = key_line

                    meta[key] = value
                else:
                    # Skip malformed field
                    continue
            else:
                # Unknown token type, stop parsing META
                break

        return meta

    def parse_section_marker(self) -> Section | None:
        """Parse §NUMBER::NAME or §IDENTIFIER::NAME section marker with nested children.

        Pattern: §NUMBER[SUFFIX]::NAME[bracket_tail] or §IDENTIFIER::[NAME] followed by indented children.
        Examples:
            §1::GOLDEN_RULE
              LITMUS::"value"
            §2b::LEXER_RULES
              RULE::"pattern"
            §0::META[schema_hints,versioning]
              TYPE::"SPEC"
            §CONTEXT::
              VAR::"value"
            §CONTEXT::LOCAL
              VAR::"local_value"
        """
        section_token = self.current()
        self.expect(TokenType.SECTION)  # Consume §

        # Accept either NUMBER or IDENTIFIER after §
        section_id: str
        if self.current().type == TokenType.NUMBER:
            # Traditional numbered section: §1, §2, etc.
            section_id = str(self.current().value)
            self.advance()

            # Check for optional suffix (IDENTIFIER like 'b', 'c')
            if self.current().type == TokenType.IDENTIFIER:
                # Only consume single-letter suffixes to avoid consuming the section name
                suffix_candidate = self.current().value
                if len(suffix_candidate) == 1 and suffix_candidate.isalpha():
                    section_id += suffix_candidate
                    self.advance()

        elif self.current().type == TokenType.IDENTIFIER:
            # Named section: §CONTEXT, §DEFINITIONS, etc.
            section_id = self.current().value
            self.advance()

        else:
            raise ParserError(
                f"Expected number or identifier after § section marker, got {self.current().type}",
                self.current(),
                "E006",
            )

        # Expect ::
        if self.current().type != TokenType.ASSIGN:
            raise ParserError(
                f"Expected :: after §{section_id}, got {self.current().type}",
                self.current(),
                "E006",
            )
        self.advance()

        # Section name is optional (for patterns like §CONTEXT::)
        # If present, it's an IDENTIFIER; if absent (newline/indent follows), use section_id as name
        section_name: str
        if self.current().type == TokenType.IDENTIFIER:
            section_name = self.current().value
            self.advance()
        elif self.current().type in (TokenType.NEWLINE, TokenType.INDENT, TokenType.LIST_START):
            # No explicit name, use section_id as the name (e.g., §CONTEXT:: → name is "CONTEXT")
            section_name = section_id
        else:
            raise ParserError(
                f"Expected section name or newline after §{section_id}::, got {self.current().type}",
                self.current(),
                "E006",
            )

        # Capture optional bracket annotation tail [...]
        # Example: §0::META[schema_hints,versioning]
        annotation = self._consume_bracket_annotation(capture=True)

        self.skip_whitespace()

        # Parse section children (similar to block parsing)
        children: list[ASTNode] = []

        # Expect indentation for children
        if self.current().type == TokenType.INDENT:
            child_indent = self.current().value
            self.advance()

            # Track current line's indentation to determine if SECTION is child or sibling
            current_line_indent = child_indent

            # Issue #182: Track pending comments for next child
            pending_comments: list[str] = []

            while True:
                # End conditions
                if self.current().type in (TokenType.EOF, TokenType.ENVELOPE_END):
                    break

                # Check indentation first to track current line's indent level
                if self.current().type == TokenType.INDENT:
                    current_line_indent = self.current().value
                    if current_line_indent < child_indent:
                        break  # Dedent, end of section
                    # Same or deeper level - consume and continue to parse
                    self.advance()
                    continue

                # Issue #182: Collect comments as pending for next child
                if self.current().type == TokenType.COMMENT:
                    pending_comments.append(self.current().value)
                    self.advance()
                    continue

                # Check for section marker - only break if at shallower indent than children
                # Nested child sections are at same or deeper indent as other children
                if self.current().type == TokenType.SECTION:
                    # If section is at shallower indent than current section's children, it's a sibling
                    if current_line_indent < child_indent:
                        break  # Sibling or parent section, end current section
                    # Otherwise (current_line_indent >= child_indent), it's a nested child section
                    # Let parse_section handle it by falling through to the parse_section call

                # Skip newlines
                if self.current().type == TokenType.NEWLINE:
                    self.advance()
                    # GH#81: After newline, reset indent tracking to 0
                    # Next INDENT token will update it, or absence means column 0
                    current_line_indent = 0
                    continue

                # GH#81: Check for implicit dedent before parsing child
                # If current line has less indentation than section children expect,
                # the next token is a sibling/ancestor, not a child
                if current_line_indent < child_indent:
                    break

                # Parse child with any pending comments
                child = self.parse_section(child_indent, pending_comments)
                pending_comments = []  # Reset after passing to child
                if child:
                    children.append(child)
                    # GH#81: After parsing a child (especially nested blocks),
                    # the recursive call may have consumed NEWLINEs. Reset indent
                    # tracking so next iteration properly detects the current
                    # line's indentation via INDENT token or implicit dedent.
                    current_line_indent = 0
                else:
                    # No valid child parsed, might be end of section
                    break

            # Issue #182: Handle orphan comments at end of section
            # If pending_comments exist but loop broke (dedent/EOF), they are inner comments
            if pending_comments:
                for comment_text in pending_comments:
                    children.append(Comment(text=comment_text))

        return Section(
            section_id=section_id,
            key=section_name,
            annotation=annotation,
            children=children,
            line=section_token.line,
            column=section_token.column,
        )

    def parse_section(
        self, base_indent: int, leading_comments: list[str] | None = None
    ) -> Assignment | Block | Section | None:
        """Parse a top-level section (assignment, block, or section).

        Args:
            base_indent: The base indentation level for this section
            leading_comments: Comments collected before this section (Issue #182)
        """
        # Check for section marker first
        if self.current().type == TokenType.SECTION:
            section = self.parse_section_marker()
            if section and leading_comments:
                section.leading_comments = leading_comments
            return section

        if self.current().type != TokenType.IDENTIFIER:
            return None

        # Capture token info before consuming for potential I4 audit warning
        identifier_token = self.current()
        key = identifier_token.value
        self.advance()

        # Issue #189: Check for block target annotation syntax: BLOCK[->TARGET]:
        # This must be checked BEFORE the ASSIGN/BLOCK check below.
        block_target: str | None = None
        if self.current().type == TokenType.LIST_START:
            block_target = self._parse_block_target_annotation()

        # Check for assignment or block
        # Lenient: allow FLOW (->) as assignment
        if self.current().type in (TokenType.ASSIGN, TokenType.FLOW):
            operator_token = self.current()
            # GH#184: Emit W_BARE_FLOW warning when flow arrow used as assignment
            if operator_token.type == TokenType.FLOW:
                self.warnings.append(
                    {
                        "type": "spec_violation",
                        "subtype": "bare_flow",
                        "line": operator_token.line,
                        "column": operator_token.column,
                        "message": (
                            f"W_BARE_FLOW::Flow operator '{operator_token.value}' "
                            f"at line {operator_token.line} used as assignment. "
                            f"Use '::' for assignment and brackets for flow: KEY::[A{operator_token.value}B]"
                        ),
                    }
                )
            self.advance()
            value = self.parse_value()
            # Issue #182: Collect trailing comment after value
            trailing_comment = self.collect_trailing_comment()
            assignment = Assignment(
                key=key,
                value=value,
                line=identifier_token.line,
                column=identifier_token.column,
                leading_comments=leading_comments or [],
                trailing_comment=trailing_comment,
            )
            return assignment

        elif self.current().type == TokenType.BLOCK:
            block_token = self.current()
            self.advance()

            # E001: Check if there's a value on the same line as the block operator
            # This catches "KEY: value" which should be "KEY::value"
            next_token = self.current()
            if next_token.type == TokenType.IDENTIFIER and next_token.line == block_token.line:
                raise ParserError(
                    f"Single colon assignment detected: '{key}: {next_token.value}'. "
                    f"OCTAVE REQUIREMENT: Use '{key}::{next_token.value}' (double colon) for assignments. "
                    "Single colon ':' is reserved for block definitions only.",
                    block_token,
                    "E001",
                )

            self.skip_whitespace()

            # Parse block children
            children: list[ASTNode] = []

            # Expect indentation for children
            if self.current().type == TokenType.INDENT:
                child_indent = self.current().value
                self.advance()

                # GH#81: Track current line's indentation to detect implicit dedent
                # When NEWLINE is consumed without subsequent INDENT, the next token
                # is at column 0 (implicit dedent). We must detect this and break.
                current_line_indent = child_indent

                # Issue #182: Track pending comments for next child
                pending_comments: list[str] = []

                while True:
                    # End conditions
                    if self.current().type in (TokenType.EOF, TokenType.ENVELOPE_END):
                        break

                    # Check indentation
                    if self.current().type == TokenType.INDENT:
                        current_line_indent = self.current().value
                        if current_line_indent < child_indent:
                            break  # Dedent, end of block
                        # Same or deeper level - consume and continue to parse
                        self.advance()
                        continue

                    # Issue #182: Collect comments as pending for next child
                    if self.current().type == TokenType.COMMENT:
                        pending_comments.append(self.current().value)
                        self.advance()
                        continue

                    # Skip newlines
                    if self.current().type == TokenType.NEWLINE:
                        self.advance()
                        # GH#81: After newline, reset indent tracking to 0
                        # Next INDENT token will update it, or absence means column 0
                        current_line_indent = 0
                        continue

                    # GH#81: Check for implicit dedent before parsing child
                    # If current line has less indentation than block children expect,
                    # the next token is a sibling/ancestor, not a child
                    if current_line_indent < child_indent:
                        break

                    # Parse child with any pending comments
                    child = self.parse_section(child_indent, pending_comments)
                    pending_comments = []  # Reset after passing to child
                    if child:
                        children.append(child)
                        # GH#81: After parsing a child (especially nested blocks),
                        # the recursive call may have consumed NEWLINEs. Reset indent
                        # tracking so next iteration properly detects the current
                        # line's indentation via INDENT token or implicit dedent.
                        current_line_indent = 0
                    elif self.current().type in (TokenType.NEWLINE, TokenType.INDENT, TokenType.COMMENT):
                        # GH#64: parse_section consumed and warned about bare identifier,
                        # leaving us at NEWLINE/INDENT. Continue parsing remaining children.
                        continue
                    else:
                        # No valid child parsed, might be end of block
                        break

                # Issue #182: Handle orphan comments at end of block
                # If pending_comments exist but loop broke (dedent/EOF), they are inner comments
                if pending_comments:
                    for comment_text in pending_comments:
                        children.append(Comment(text=comment_text))

            return Block(
                key=key,
                children=children,
                line=identifier_token.line,
                column=identifier_token.column,
                leading_comments=leading_comments or [],
                target=block_target,  # Issue #189: Block inheritance target
            )

        # GH#64: Bare identifier without :: or : operator - emit I4 audit warning
        # Per I4 (Transform Auditability): "If bits lost must have receipt"
        # The identifier was already consumed above, so use captured token info
        self.warnings.append(
            {
                "type": "lenient_parse",
                "subtype": "bare_line_dropped",
                "original": str(identifier_token.value),
                "line": identifier_token.line,
                "column": identifier_token.column,
                "reason": "Bare identifier without :: or : operator",
            }
        )
        return None

    def parse_value(self) -> Any:
        """Parse a value (string, number, boolean, null, list)."""
        token = self.current()

        if token.type == TokenType.STRING:
            # Issue #140/#141: Check if STRING is followed by more tokens for multi-word value
            next_token = self.peek()
            if next_token.type in VALUE_TOKENS:
                # STRING followed by more tokens - coalesce as multi-word value
                start_line = token.line
                start_column = token.column
                word_parts = [_token_to_str(token)]
                self.advance()  # Consume STRING

                # Accumulate following VALUE_TOKENS
                while self.current().type in VALUE_TOKENS:
                    word_parts.append(_token_to_str(self.current()))
                    self.advance()

                result = " ".join(word_parts)
                self.warnings.append(
                    {
                        "type": "lenient_parse",
                        "subtype": "multi_word_coalesce",
                        "original": word_parts,
                        "result": result,
                        "context": "string_multiword",
                        "line": start_line,
                        "column": start_column,
                    }
                )
                self._consume_bracket_annotation(capture=False)
                return result

            # Standalone STRING
            self.advance()
            return token.value

        elif token.type == TokenType.NUMBER:
            # GH#87: Check if NUMBER is followed by VALUE_TOKENS (e.g., 123_suffix, 123 1.0.0)
            # If so, coalesce into multi-word string value (same pattern as IDENTIFIER path)
            next_token = self.peek()
            if next_token.type in VALUE_TOKENS:
                # NUMBER followed by VALUE_TOKENS - coalesce as multi-word value
                # Track start position for I4 audit
                start_line = token.line
                start_column = token.column

                # Use raw lexeme for NUMBER to preserve format (e.g., 1e10)
                word_parts = [_token_to_str(token)]
                self.advance()  # Consume NUMBER

                # Accumulate following VALUE_TOKENS (like IDENTIFIER path) - Issue #140/#141
                while self.current().type in VALUE_TOKENS:
                    # Check if next token after this is an operator
                    if self.peek().type in EXPRESSION_OPERATORS:
                        # Include this token and parse rest as expression
                        word_parts.append(_token_to_str(self.current()))
                        self.advance()
                        # Continue with flow expression parsing
                        expr_parts = [" ".join(word_parts)]
                        while self.current().type in VALUE_TOKENS or self.current().type in EXPRESSION_OPERATORS:
                            if self.current().type in EXPRESSION_OPERATORS:
                                expr_parts.append(self.current().value)
                                self.advance()
                            elif self.current().type in VALUE_TOKENS:
                                expr_parts.append(_token_to_str(self.current()))
                                self.advance()
                            else:
                                break
                        # I4 Audit: Emit warning for NUMBER+IDENTIFIER coalescing in expression
                        self.warnings.append(
                            {
                                "type": "lenient_parse",
                                "subtype": "multi_word_coalesce",
                                "original": word_parts,
                                "result": " ".join(word_parts),
                                "context": "number_identifier_expression",
                                "line": start_line,
                                "column": start_column,
                            }
                        )
                        return "".join(str(p) for p in expr_parts)

                    # Just another word/number in the multi-word value
                    word_parts.append(_token_to_str(self.current()))
                    self.advance()

                # Join words with spaces
                result = " ".join(word_parts)

                # GH#87 I4 Audit: Emit warning for NUMBER+IDENTIFIER coalescing
                # Per I4: "If bits lost must have receipt" - this is lenient parsing
                self.warnings.append(
                    {
                        "type": "lenient_parse",
                        "subtype": "multi_word_coalesce",
                        "original": word_parts,
                        "result": result,
                        "context": "number_identifier",
                        "line": start_line,
                        "column": start_column,
                    }
                )

                # Consume bracket annotation if present (like IDENTIFIER path)
                self._consume_bracket_annotation(capture=False)

                return result

            # Standalone NUMBER - return numeric value as before
            self.advance()
            return token.value

        elif token.type == TokenType.BOOLEAN:
            # Issue #140/#141: Check if BOOLEAN is followed by more tokens for multi-word value
            next_token = self.peek()
            if next_token.type in VALUE_TOKENS:
                # BOOLEAN followed by more tokens - coalesce as multi-word value
                start_line = token.line
                start_column = token.column
                word_parts = [_token_to_str(token)]
                self.advance()  # Consume BOOLEAN

                # Accumulate following VALUE_TOKENS
                while self.current().type in VALUE_TOKENS:
                    word_parts.append(_token_to_str(self.current()))
                    self.advance()

                result = " ".join(word_parts)
                self.warnings.append(
                    {
                        "type": "lenient_parse",
                        "subtype": "multi_word_coalesce",
                        "original": word_parts,
                        "result": result,
                        "context": "boolean_multiword",
                        "line": start_line,
                        "column": start_column,
                    }
                )
                self._consume_bracket_annotation(capture=False)
                return result

            # Standalone BOOLEAN
            self.advance()
            return token.value

        elif token.type == TokenType.NULL:
            # Issue #140/#141: Check if NULL is followed by more tokens for multi-word value
            next_token = self.peek()
            if next_token.type in VALUE_TOKENS:
                # NULL followed by more tokens - coalesce as multi-word value
                start_line = token.line
                start_column = token.column
                word_parts = [_token_to_str(token)]
                self.advance()  # Consume NULL

                # Accumulate following VALUE_TOKENS
                while self.current().type in VALUE_TOKENS:
                    word_parts.append(_token_to_str(self.current()))
                    self.advance()

                result = " ".join(word_parts)
                self.warnings.append(
                    {
                        "type": "lenient_parse",
                        "subtype": "multi_word_coalesce",
                        "original": word_parts,
                        "result": result,
                        "context": "null_multiword",
                        "line": start_line,
                        "column": start_column,
                    }
                )
                self._consume_bracket_annotation(capture=False)
                return result

            # Standalone NULL
            self.advance()
            return None

        elif token.type == TokenType.VERSION:
            # Issue #140/#141: Check if VERSION is followed by more tokens for multi-word value
            next_token = self.peek()
            if next_token.type in VALUE_TOKENS:
                # VERSION followed by more tokens - coalesce as multi-word value
                start_line = token.line
                start_column = token.column
                word_parts = [_token_to_str(token)]
                self.advance()  # Consume VERSION

                # Accumulate following VALUE_TOKENS
                while self.current().type in VALUE_TOKENS:
                    word_parts.append(_token_to_str(self.current()))
                    self.advance()

                result = " ".join(word_parts)
                self.warnings.append(
                    {
                        "type": "lenient_parse",
                        "subtype": "multi_word_coalesce",
                        "original": word_parts,
                        "result": result,
                        "context": "version_multiword",
                        "line": start_line,
                        "column": start_column,
                    }
                )
                self._consume_bracket_annotation(capture=False)
                return result

            # Standalone VERSION
            self.advance()
            return str(token.value)

        elif token.type == TokenType.LIST_START:
            return self.parse_list()

        elif token.type == TokenType.IDENTIFIER:
            # Check if this starts an expression with operators (GH#62, GH#65)
            next_token = self.peek()
            if next_token.type in EXPRESSION_OPERATORS:
                # Expression with operators like A->B->C, X+Y, A@B, A~B, Speed vs Quality, etc.
                return self.parse_flow_expression()

            # GH#66: Capture multi-word bare values
            # Examples: "Main content", "Hello World Again"
            # Stops at: NEWLINE, COMMA, LIST_END, ENVELOPE markers, operators
            parts = [token.value]
            self.advance()

            # Collect colon-separated path components (Issue #41 Phase 2)
            # Examples: HERMES:API_TIMEOUT, MODULE:SUBMODULE:COMPONENT
            while self.current().type == TokenType.BLOCK and self.peek().type == TokenType.IDENTIFIER:
                # Consume BLOCK token (:)
                self.advance()
                # Consume IDENTIFIER token
                parts.append(self.current().value)
                self.advance()

            # If we consumed colons, return as colon-joined path
            if len(parts) > 1:
                # GH#85: Consume bracket annotation if present after colon-path value
                # Examples: HERMES:API_TIMEOUT[note], MODULE:SUB[annotation]
                # Must consume before returning so indentation tracking sees NEWLINE
                self._consume_bracket_annotation(capture=False)
                return ":".join(parts)

            # GH#66: Continue capturing consecutive identifiers as multi-word value
            # GH#63: Include NUMBER tokens in multi-word capture (convert to string)
            # Issue #140/#141: Include VALUE_TOKENS to prevent data loss
            # Stop at delimiters, operators, or non-value tokens
            word_parts = [parts[0]]
            # Track start position for I4 audit
            start_line = token.line
            start_column = token.column

            while self.current().type in VALUE_TOKENS:
                # Check if next token after this identifier is an operator
                # If so, we're starting an expression, not a multi-word value
                if self.peek().type in EXPRESSION_OPERATORS:
                    # Include this word and then parse the rest as expression
                    # GH#66: Use _token_to_str to preserve NUMBER lexemes
                    word_parts.append(_token_to_str(self.current()))
                    self.advance()
                    # Now we need to continue with flow expression parsing
                    expr_parts = [" ".join(word_parts)]
                    while self.current().type in VALUE_TOKENS or self.current().type in EXPRESSION_OPERATORS:
                        if self.current().type in EXPRESSION_OPERATORS:
                            expr_parts.append(self.current().value)
                            self.advance()
                        elif self.current().type in VALUE_TOKENS:
                            # GH#66/#140/#141: Use _token_to_str to preserve all value token lexemes
                            expr_parts.append(_token_to_str(self.current()))
                            self.advance()
                        else:
                            break
                    # I4 Audit: Emit warning when multi-word coalescing occurs in expression path
                    # Same pattern as terminal multi-word at line 557-567
                    if len(word_parts) > 1:
                        self.warnings.append(
                            {
                                "type": "lenient_parse",
                                "subtype": "multi_word_coalesce",
                                "original": word_parts,
                                "result": " ".join(word_parts),
                                "context": "expression_path",
                                "line": start_line,
                                "column": start_column,
                            }
                        )
                    return "".join(str(p) for p in expr_parts)

                # Just another word/number in the multi-word value
                # GH#66: Use _token_to_str to preserve NUMBER lexemes (e.g., 1e10)
                word_parts.append(_token_to_str(self.current()))
                self.advance()

            # Join words with spaces
            result = " ".join(word_parts)

            # GH#66 I4 Audit: Emit warning when multiple tokens coalesced into single value
            # "If bits lost must have receipt" - multi-word coalescing is lenient parsing
            if len(word_parts) > 1:
                self.warnings.append(
                    {
                        "type": "lenient_parse",
                        "subtype": "multi_word_coalesce",
                        "original": word_parts,
                        "result": result,
                        "line": start_line,
                        "column": start_column,
                    }
                )

            # GH#85: Consume bracket annotation if present after value
            # Examples: DONE[annotation], PENDING[[nested,content]]
            # Must consume before returning so indentation tracking sees NEWLINE
            self._consume_bracket_annotation(capture=False)

            return result

        elif token.type == TokenType.FLOW:
            # Flow expression starting with operator like →B→C
            return self.parse_flow_expression()

        elif token.type == TokenType.SECTION:
            # Gap 9 fix: Handle § section marker in value position
            # Examples: TARGET::§INDEXER, TARGETS::[§A, §B], REF::§1
            # The SECTION token contains '§' (canonical form, even if # was typed)
            section_marker = str(token.value)  # Always '§'
            self.advance()

            # Check for following IDENTIFIER or NUMBER
            next_token = self.current()
            if next_token.type == TokenType.IDENTIFIER:
                # §IDENTIFIER pattern (e.g., §INDEXER)
                section_marker += next_token.value
                self.advance()
            elif next_token.type == TokenType.NUMBER:
                # §NUMBER pattern (e.g., §1, §2)
                section_marker += _token_to_str(next_token)
                self.advance()
            # else: bare § marker, return as-is

            # Gap 9 regression fix: Consume bracket annotation if present
            # Examples: §X[note], §TARGET[[nested,content]]
            # Must consume before returning so indentation tracking sees NEWLINE
            self._consume_bracket_annotation(capture=False)

            return section_marker

        elif token.type == TokenType.VARIABLE:
            # Issue #181: Handle $VAR, $1:name variable placeholders
            # Variables are atomic values - treated like strings without expansion
            # Check if this starts an expression with operators (like $VAR->$OTHER)
            next_token = self.peek()
            if next_token.type in EXPRESSION_OPERATORS:
                return self.parse_flow_expression()

            # Simple variable - return as-is
            value = str(token.value)
            self.advance()
            return value

        else:
            # Try to consume as bare word
            value = str(token.value)
            self.advance()
            return value

    def parse_list(self) -> ListValue | HolographicValue:
        """Parse list [a, b, c] or holographic pattern ["example"∧REQ→§TARGET].

        Gap_2 ADR-0012: Captures token slice for token-witnessed reconstruction.
        This enables correct reconstruction of holographic patterns containing
        quoted operator symbols (e.g., ["∧"∧REQ→§SELF]).

        Issue #187: After parsing, checks if tokens indicate holographic pattern
        and returns HolographicValue instead of ListValue when appropriate.

        Issue #179: Detects duplicate keys in inline maps [k::v, k::v2].
        Issue #192: Detects deep nesting and emits warnings/errors.
        """
        # Gap_2: Record token position BEFORE consuming LIST_START
        # We want tokens from [ to ] inclusive for reconstruction
        start_pos = self.pos
        bracket_token = self.current()  # Capture for line number in warnings
        self.expect(TokenType.LIST_START)
        self.bracket_depth += 1  # GH#184: Track bracket nesting for NEVER rule validation

        # Issue #192: Check for deep nesting
        self._check_deep_nesting(bracket_token)

        items: list[Any] = []

        # Issue #179: Track inline map keys for duplicate detection
        inline_map_keys: dict[str, int] = {}  # key -> first occurrence line

        # Parse list items
        while True:
            # Skip whitespace/newlines/indents (valid anywhere between items)
            while self.current().type in (TokenType.NEWLINE, TokenType.INDENT):
                self.advance()

            # Check for end of list
            # Issue #162 Fix: Check for EOF to prevent infinite loop
            if self.current().type in (TokenType.LIST_END, TokenType.EOF, TokenType.ENVELOPE_END):
                break

            # Issue #179: Capture line before parsing item for accurate duplicate reporting
            item_line = self.current().line

            # Parse item value
            item = self.parse_list_item()
            items.append(item)

            # Issue #179: Check for duplicate keys in inline maps
            if isinstance(item, InlineMap):
                for key in item.pairs.keys():
                    if key in inline_map_keys:
                        # I4 Audit: Emit warning for duplicate key in inline map
                        self.warnings.append(
                            {
                                "type": "lenient_parse",
                                "subtype": "duplicate_key",
                                "key": key,
                                "first_line": inline_map_keys[key],
                                "duplicate_line": item_line,
                                "message": (
                                    f"W_DUPLICATE_KEY::{key} at line {item_line} "
                                    f"overwrites previous definition at line {inline_map_keys[key]}"
                                ),
                            }
                        )
                    else:
                        inline_map_keys[key] = item_line

            # Check for comma
            if self.current().type == TokenType.COMMA:
                self.advance()
                # Loop will handle whitespace skipping at start of next iteration
            elif self.current().type == TokenType.LIST_END:
                break
            else:
                # No comma, check if we have whitespace that acted as separator
                # If next is LIST_END, loop will handle it
                # If next is another item, strict syntax requires comma.
                # But lenient parser might allow space-separated?
                # For now, if not comma and not list end, we loop back.
                # If next token is start of value, we might parse it as next item (lenient)
                # or fail if parser expects comma.
                # The loop structure handles it: it tries to parse item.
                # If it's not a valid value start, parse_value might consume it as bare word.
                # So we rely on LIST_END check.

                # Issue #162: If we are stuck at EOF, break
                if self.current().type == TokenType.EOF:
                    break

                pass

        # Expect LIST_END only if we didn't hit EOF/ENVELOPE_END prematurely
        # This makes it lenient for unclosed lists at end of file
        if self.current().type == TokenType.LIST_END:
            self.advance()
            self.bracket_depth -= 1  # GH#184: Track bracket nesting for NEVER rule validation
        elif self.current().type in (TokenType.EOF, TokenType.ENVELOPE_END):
            self.bracket_depth -= 1  # GH#184: Decrement even on unclosed list
            if self.strict_structure:
                raise ParserError(
                    f"Unclosed list at end of content. Expected ']' before {self.current().type.name}",
                    self.current(),
                    "E007",
                )

            # I4 Audit: Emit warning for unclosed list at EOF/ENVELOPE_END
            # Per I4 (Transform Auditability): lenient parsing must emit receipt
            # This prevents silent corruption - callers know AST is incomplete
            current_token = self.current()
            self.warnings.append(
                {
                    "type": "lenient_parse",
                    "subtype": "unclosed_list",
                    "message": f"List not closed before {current_token.type.name}",
                    "line": current_token.line,
                    "column": current_token.column,
                }
            )
        else:
            self.expect(TokenType.LIST_END)
            self.bracket_depth -= 1  # GH#184: Track bracket nesting for NEVER rule validation

        # Gap_2: Capture token slice for token-witnessed reconstruction (ADR-0012)
        # Slice includes LIST_START through LIST_END (exclusive end, so pos is after ])
        end_pos = self.pos
        token_slice = self.tokens[start_pos:end_pos]

        # Issue #187: Check if this is a holographic pattern
        # Holographic patterns have the form: ["example"∧CONSTRAINT→§TARGET]
        # Detection: Look for CONSTRAINT (∧) token in the token slice
        holographic_result = self._try_parse_holographic(token_slice)
        if holographic_result is not None:
            return holographic_result

        return ListValue(items=items, tokens=token_slice)

    def parse_list_item(self) -> Any:
        """Parse a single list item.

        Issue #185: Validates INLINE_MAP_NESTING::forbidden[values_must_be_atoms]
        from octave-core-spec.oct.md section 5::MODES.
        Inline map values must be atoms - nested inline maps are forbidden.
        Only enforced in strict mode; lenient mode emits warning.
        """
        # Check for inline map [k::v, k2::v2]
        if self.current().type == TokenType.IDENTIFIER and self.peek().type == TokenType.ASSIGN:
            # Inline map item
            pairs: dict[str, Any] = {}
            key = self.current().value
            key_token = self.current()  # Capture for error reporting
            self.advance()
            self.expect(TokenType.ASSIGN)
            value = self.parse_value()

            # Issue #185: Validate inline map values are atoms (no nested inline maps)
            # Per spec: INLINE_MAP_NESTING::forbidden[values_must_be_atoms]
            # Only error in strict mode; lenient mode emits warning per I4
            self._validate_inline_map_value_is_atom(key, value, key_token)

            pairs[key] = value
            return InlineMap(pairs=pairs)

        # Regular value
        return self.parse_value()

    def _check_deep_nesting(self, token: Token) -> None:
        """Check for deep nesting and emit warning or raise error.

        Issue #192: Implements deep nesting detection per spec requirements:
        - Warning at configurable threshold (default 5): W_DEEP_NESTING
        - Hard error at 100 levels: E_MAX_NESTING_EXCEEDED

        Args:
            token: The bracket token for line number reporting

        Raises:
            ParserError: If nesting depth reaches MAX_NESTING_DEPTH (100)
        """
        depth = self.bracket_depth

        # Check for max nesting (hard error)
        if depth >= MAX_NESTING_DEPTH:
            raise ParserError(
                f"E_MAX_NESTING_EXCEEDED::Maximum nesting depth of {MAX_NESTING_DEPTH} exceeded. "
                f"Flatten your structure or use block syntax.",
                token,
                "E_MAX_NESTING_EXCEEDED",
            )

        # Check for deep nesting warning (if threshold is configured)
        if self.deep_nesting_threshold > 0 and depth >= self.deep_nesting_threshold:
            # Only warn once per line to avoid spam for [[[...]]]
            if token.line not in self._deep_nesting_warned_at:
                self._deep_nesting_warned_at.add(token.line)
                self.warnings.append(
                    {
                        "type": "lenient_parse",
                        "subtype": "deep_nesting",
                        "depth": depth,
                        "threshold": self.deep_nesting_threshold,
                        "line": token.line,
                        "column": token.column,
                        "message": (f"W_DEEP_NESTING::depth {depth} at line {token.line}, " f"consider flattening"),
                    }
                )

    def _validate_inline_map_value_is_atom(self, key: str, value: Any, token: Token) -> None:
        """Validate that an inline map value is atomic (not a nested inline map).

        Issue #185: Enforces INLINE_MAP_NESTING::forbidden[values_must_be_atoms]
        from octave-core-spec.oct.md section 5::MODES.

        In strict mode: raises ParserError for nested inline maps
        In lenient mode: emits I4 warning but allows parsing to continue

        Args:
            key: The inline map key (for error context)
            value: The parsed value to validate
            token: Token for error location reporting

        Raises:
            ParserError: If value contains nested inline maps (strict mode only)
        """
        # Direct nesting: value is an InlineMap
        if isinstance(value, InlineMap):
            if self.strict_structure:
                raise ParserError(
                    f"E_NESTED_INLINE_MAP::inline maps cannot contain inline maps. "
                    f"Key '{key}' has an inline map as value. "
                    f"Use block structure instead:\n"
                    f"  {key.upper()}:\n"
                    f"    NESTED_KEY::value",
                    token,
                    "E_NESTED_INLINE_MAP",
                )
            else:
                # I4 Audit: Emit warning for nested inline map in lenient mode
                self.warnings.append(
                    {
                        "type": "lenient_parse",
                        "subtype": "nested_inline_map",
                        "key": key,
                        "line": token.line,
                        "column": token.column,
                        "message": (
                            f"W_NESTED_INLINE_MAP::{key} at line {token.line} "
                            f"has inline map as value. Consider using block structure."
                        ),
                    }
                )
            return

        # Recursive check: value is a ListValue - check all items recursively
        if isinstance(value, ListValue):
            self._check_list_for_nested_inline_maps(key, value, token)

    def _check_list_for_nested_inline_maps(self, key: str, list_value: ListValue, token: Token) -> None:
        """Recursively check a list for inline maps at any depth.

        Issue #185: Ensures inline map values don't contain inline maps
        even when nested inside lists.

        In strict mode: raises ParserError
        In lenient mode: emits I4 warning

        Args:
            key: The inline map key (for error context)
            list_value: The list to check
            token: Token for error location reporting

        Raises:
            ParserError: If any item in the list (at any depth) is an InlineMap (strict mode only)
        """
        for item in list_value.items:
            if isinstance(item, InlineMap):
                if self.strict_structure:
                    raise ParserError(
                        f"E_NESTED_INLINE_MAP::inline maps cannot contain inline maps. "
                        f"Key '{key}' has a list containing inline maps. "
                        f"Use block structure instead:\n"
                        f"  {key.upper()}:\n"
                        f"    - NESTED_KEY::value",
                        token,
                        "E_NESTED_INLINE_MAP",
                    )
                else:
                    # I4 Audit: Emit warning for nested inline map in lenient mode
                    self.warnings.append(
                        {
                            "type": "lenient_parse",
                            "subtype": "nested_inline_map",
                            "key": key,
                            "line": token.line,
                            "column": token.column,
                            "message": (
                                f"W_NESTED_INLINE_MAP::{key} at line {token.line} "
                                f"has list containing inline maps. Consider using block structure."
                            ),
                        }
                    )
                    # In lenient mode, continue to allow but don't recurse further
                    # (one warning per key is enough)
                    return
            # Recursive check for nested lists
            if isinstance(item, ListValue):
                self._check_list_for_nested_inline_maps(key, item, token)

    def _try_parse_holographic(self, token_slice: list[Token]) -> HolographicValue | None:
        """Try to parse token slice as holographic pattern.

        Issue #187: Integrates holographic pattern parsing into L4 context.

        Holographic patterns have the form: ["example"∧CONSTRAINT→§TARGET]
        Detection criteria:
        - Must contain a CONSTRAINT (∧) token outside nested brackets
        - First substantive token after LIST_START should be the example value

        Args:
            token_slice: Token list from LIST_START to LIST_END inclusive

        Returns:
            HolographicValue if this is a holographic pattern, None otherwise
        """
        # Quick check: must have CONSTRAINT token to be holographic
        has_constraint = any(t.type == TokenType.CONSTRAINT for t in token_slice)
        if not has_constraint:
            return None

        # Additional heuristic: holographic patterns don't have commas at depth=0
        # This distinguishes [a, b∧c] (list with expression) from ["x"∧REQ] (holographic)
        # Check for commas outside nested brackets
        depth = 0
        for token in token_slice:
            if token.type == TokenType.LIST_START:
                depth += 1
            elif token.type == TokenType.LIST_END:
                depth -= 1
            elif token.type == TokenType.COMMA and depth == 1:
                # Comma at depth 1 means inside outer [], outside nested []
                # This is a regular list, not holographic
                return None

        # Reconstruct raw pattern string from tokens for parse_holographic_pattern()
        raw_pattern = self._reconstruct_pattern_from_tokens(token_slice)

        try:
            # Import here to avoid circular import
            from octave_mcp.core.holographic import HolographicPatternError, parse_holographic_pattern

            pattern = parse_holographic_pattern(raw_pattern)

            return HolographicValue(
                example=pattern.example,
                constraints=pattern.constraints,
                target=pattern.target,
                raw_pattern=raw_pattern,
                tokens=token_slice,
            )
        except HolographicPatternError:
            # Not a valid holographic pattern, fall back to ListValue
            return None

    def _reconstruct_pattern_from_tokens(self, token_slice: list[Token]) -> str:
        """Reconstruct pattern string from tokens for holographic parsing.

        Issue #187: Converts token slice back to string for parse_holographic_pattern().

        This preserves I1 syntactic fidelity by using token values directly.
        Handles nested brackets (for ENUM[a,b], REGEX[pattern], etc.) correctly.

        Args:
            token_slice: Token list from LIST_START to LIST_END inclusive

        Returns:
            Reconstructed pattern string like '["example"∧REQ→§TARGET]'
        """
        parts: list[str] = []

        for token in token_slice:
            if token.type == TokenType.LIST_START:
                parts.append("[")
            elif token.type == TokenType.LIST_END:
                parts.append("]")
            elif token.type == TokenType.STRING:
                parts.append(f'"{token.value}"')
            elif token.type == TokenType.NUMBER:
                # Use raw lexeme if available to preserve format (e.g., 1e10)
                if token.raw is not None:
                    parts.append(token.raw)
                else:
                    parts.append(str(token.value))
            elif token.type == TokenType.BOOLEAN:
                parts.append("true" if token.value else "false")
            elif token.type == TokenType.NULL:
                parts.append("null")
            elif token.type == TokenType.CONSTRAINT:
                parts.append("∧")
            elif token.type == TokenType.FLOW:
                parts.append("→")
            elif token.type == TokenType.SECTION:
                parts.append("§")
            elif token.type == TokenType.COMMA:
                parts.append(",")
            elif token.type == TokenType.IDENTIFIER:
                parts.append(str(token.value))
            # Note: LPAREN/RPAREN are not supported by the lexer,
            # so TYPE(X) patterns will fail at tokenization level.
            # Skip whitespace tokens

        return "".join(parts)

    def parse_flow_expression(self) -> str:
        """Parse expression with operators like A→B→C, X⊕Y, A@B, A⧺B, or Speed⇌Quality.

        Uses EXPRESSION_OPERATORS set for unified operator handling (GH#62, GH#65).
        This ensures all expression operators (FLOW, SYNTHESIS, AT, CONCAT, TENSION,
        CONSTRAINT, ALTERNATIVE) are properly captured in expressions.

        Gap 9 fix: Also handles SECTION tokens (§) in flow expressions.
        Example: START->§DESTINATION should capture '§DESTINATION' as single unit.

        GH#184: Emits spec violation warnings for NEVER rules:
        - W_BARE_FLOW: Flow arrow outside brackets
        - W_CONSTRAINT_OUTSIDE_BRACKETS: Constraint operator outside brackets
        - W_CHAINED_TENSION: Multiple tension operators in same expression
        """
        parts = []
        tension_count = 0  # GH#184: Track tension operators for chained tension detection
        first_tension_token: Token | None = None  # For error location

        # Collect all parts of expression using unified EXPRESSION_OPERATORS set
        # Gap 9: Include SECTION token type in valid expression components
        # Issue #181: Include VARIABLE token type for $VAR placeholders in expressions
        while (
            self.current().type in (TokenType.IDENTIFIER, TokenType.STRING, TokenType.SECTION, TokenType.VARIABLE)
            or self.current().type in EXPRESSION_OPERATORS
        ):
            if self.current().type in EXPRESSION_OPERATORS:
                operator_token = self.current()

                # GH#184: Detect NEVER rule violations
                if operator_token.type == TokenType.FLOW and self.bracket_depth == 0:
                    # W_BARE_FLOW: Flow arrow outside brackets
                    self.warnings.append(
                        {
                            "type": "spec_violation",
                            "subtype": "bare_flow",
                            "line": operator_token.line,
                            "column": operator_token.column,
                            "message": (
                                f"W_BARE_FLOW::Flow operator '{operator_token.value}' "
                                f"at line {operator_token.line} is outside brackets. "
                                f"Use list syntax: KEY::[A{operator_token.value}B]"
                            ),
                        }
                    )

                if operator_token.type == TokenType.CONSTRAINT and self.bracket_depth == 0:
                    # W_CONSTRAINT_OUTSIDE_BRACKETS: Constraint outside brackets
                    self.warnings.append(
                        {
                            "type": "spec_violation",
                            "subtype": "constraint_outside_brackets",
                            "line": operator_token.line,
                            "column": operator_token.column,
                            "message": (
                                f"W_CONSTRAINT_OUTSIDE_BRACKETS::Constraint operator "
                                f"'{operator_token.value}' at line {operator_token.line} "
                                f"is only valid inside brackets. Use: [A{operator_token.value}B]"
                            ),
                        }
                    )

                if operator_token.type == TokenType.TENSION:
                    tension_count += 1
                    if first_tension_token is None:
                        first_tension_token = operator_token

                parts.append(self.current().value)
                self.advance()
            elif self.current().type == TokenType.SECTION:
                # Gap 9 fix: Handle § section marker in flow expression
                # Concatenate § with following IDENTIFIER/NUMBER
                section_marker = self.current().value  # '§'
                self.advance()
                if self.current().type == TokenType.IDENTIFIER:
                    section_marker += self.current().value
                    self.advance()
                elif self.current().type == TokenType.NUMBER:
                    section_marker += _token_to_str(self.current())
                    self.advance()
                parts.append(section_marker)
            elif self.current().type in (TokenType.IDENTIFIER, TokenType.STRING, TokenType.VARIABLE):
                # Issue #181: Handle VARIABLE tokens in flow expressions
                parts.append(self.current().value)
                self.advance()
            else:
                break

        # GH#184: Check for chained tension (more than one tension operator)
        if tension_count > 1 and first_tension_token is not None:
            self.warnings.append(
                {
                    "type": "spec_violation",
                    "subtype": "chained_tension",
                    "line": first_tension_token.line,
                    "column": first_tension_token.column,
                    "message": (
                        f"W_CHAINED_TENSION::Expression at line {first_tension_token.line} "
                        f"contains {tension_count} tension operators. "
                        f"Tension is binary only (A vs B). Use separate expressions or list syntax."
                    ),
                }
            )

        return "".join(str(p) for p in parts)


def parse(content: str | list[Token]) -> Document:
    """Parse OCTAVE content into AST with strict structural validation.

    Ensures no silent data loss by enforcing closure of structural elements
    (e.g., lists, blocks). Use parse_with_warnings() for lenient parsing recovery.

    **Operational Note**: The CLI (`octave-mcp` command) uses strict mode by
    default to prevent malformed documents from silently corrupting data.
    For recovery workflows on slightly malformed inputs, use the Python API:
    `parse_with_warnings()` which returns warnings instead of raising errors.

    Args:
        content: Raw OCTAVE text (lenient or canonical) or list of tokens

    Returns:
        Document AST

    Raises:
        ParserError: On syntax errors or unclosed structural elements (e.g., E007)
    """
    raw_frontmatter: str | None = None

    if isinstance(content, str):
        # Issue #91: Strip YAML frontmatter before tokenization
        # YAML frontmatter contains characters (parentheses, etc.) that the lexer rejects
        stripped_content, raw_frontmatter = _strip_yaml_frontmatter(content)
        tokens, _ = tokenize(stripped_content)
    else:
        tokens = content

    # Use strict_structure=True to prevent silent data loss (Issue #162)
    parser = Parser(tokens, strict_structure=True)
    doc = parser.parse_document()

    # Preserve frontmatter in Document AST for I4 auditability
    doc.raw_frontmatter = raw_frontmatter

    return doc


def parse_meta_only(content: str) -> dict[str, Any]:
    """Fast META-only extraction without parsing full document.

    Performs minimal parsing to extract just the META section.
    Significantly faster than full parse() for large documents.
    Use when only metadata is needed (e.g., schema detection, routing).

    Args:
        content: Raw OCTAVE text

    Returns:
        Dictionary of META fields, empty dict if no META present
    """
    # Strip YAML frontmatter like full parser
    stripped_content, _ = _strip_yaml_frontmatter(content)
    tokens, _ = tokenize(stripped_content)

    parser = Parser(tokens)
    parser.skip_whitespace()

    # Skip grammar sentinel if present
    if parser.current().type == TokenType.GRAMMAR_SENTINEL:
        parser.advance()
        parser.skip_whitespace()

    # Skip envelope start if present
    if parser.current().type == TokenType.ENVELOPE_START:
        parser.advance()
        parser.skip_whitespace()

    # Check if META block exists
    if parser.current().type == TokenType.IDENTIFIER and parser.current().value == "META":
        return parser.parse_meta_block()

    # No META block found
    return {}


def parse_with_warnings(content: str | list[Token]) -> tuple[Document, list[dict]]:
    """Parse OCTAVE content into AST with I4 audit trail.

    Returns both the parsed document and any warnings generated during
    lenient parsing (e.g., multi-word value coalescing).

    I4 Immutable: "If not written and addressable, didn't happen"
    - Lenient parsing transforms must be auditable
    - Multi-word bare values coalesced into single string emit warnings

    Args:
        content: Raw OCTAVE text (lenient or canonical) or list of tokens

    Returns:
        Tuple of (Document AST, list of warning dicts)
        Warning dict structure:
        {
            "type": "lenient_parse",
            "subtype": "multi_word_coalesce",
            "original": ["word1", "word2", ...],
            "result": "word1 word2 ...",
            "line": int,
            "column": int
        }

    Raises:
        ParserError: On syntax errors
    """
    raw_frontmatter: str | None = None

    if isinstance(content, str):
        # Issue #91: Strip YAML frontmatter before tokenization
        stripped_content, raw_frontmatter = _strip_yaml_frontmatter(content)
        tokens, lexer_repairs = tokenize(stripped_content)
    else:
        tokens = content
        lexer_repairs = []

    parser = Parser(tokens)
    doc = parser.parse_document()

    # Preserve frontmatter in Document AST for I4 auditability
    doc.raw_frontmatter = raw_frontmatter

    # Combine lexer repairs and parser warnings
    # Lexer repairs are about ASCII normalization
    # Parser warnings are about lenient parsing (multi-word coalescing)
    all_warnings = list(lexer_repairs) + parser.warnings

    return doc, all_warnings
