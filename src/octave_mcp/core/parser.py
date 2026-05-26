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

from octave_mcp.core.grammar.cst import (
    Assignment,
    ASTNode,
    Block,
    Comment,
    Document,
    Envelope,
    HolographicValue,
    InlineMap,
    ListValue,
    LiteralZoneValue,
    Section,
)
from octave_mcp.core.lexer import Token, TokenType, tokenize  # noqa: F401 - TokenType members used via attribute access

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

# Issue #305: Known constructor names from §2c::BRACKET_FORMS
# These names should use constructor form NAME[args] not assignment form NAME::"value"
# When used as inline map keys with string values, emit W_CONSTRUCTOR_MISUSE warning
KNOWN_CONSTRUCTORS: frozenset[str] = frozenset({"REGEX", "ENUM", "TYPE", "PATTERN", "NEVER", "ALWAYS"})

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


def _has_annotation(value: str) -> bool:
    """Check if a token value contains an angle-bracket annotation like NAME<qualifier>.

    GH#269: Annotated identifiers like NEVER<X> are structured tokens that must
    NOT be coalesced with adjacent tokens during multi-word capture. This helper
    detects the NAME<qualifier> pattern so the parser can split them into separate
    ListValue items instead of joining them into a single string.
    """
    return "<" in value and value.endswith(">")


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

    def _emit_duplicate_key_warning(self, key: str, key_line: int, key_positions: dict[str, list[int]]) -> None:
        """Emit W_DUPLICATE_KEY warning with all occurrence line numbers.

        GH#294: When a duplicate key is detected at the same level, emit a warning
        that includes ALL line numbers where the key appears, not just the first
        and current occurrence.

        Args:
            key: The duplicate key name
            key_line: Line number of the current (duplicate) occurrence
            key_positions: Dict mapping key names to lists of ALL line numbers
        """
        all_lines = key_positions[key]
        count = len(all_lines)
        lines_str = ", ".join(str(ln) for ln in all_lines)
        self.warnings.append(
            {
                "type": "lenient_parse",
                "subtype": "duplicate_key",
                "key": key,
                "first_line": all_lines[0],
                "duplicate_line": key_line,
                "all_lines": list(all_lines),
                "message": (f"Key '{key}' appears {count} times at lines " f"{lines_str} \u2014 only last value kept"),
            }
        )

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

    def _peek_past_brackets_at(self, bracket_start: int) -> TokenType:
        """Return the token type immediately after the bracket group starting at bracket_start.

        Used to perform look-ahead past a LIST_START...LIST_END group. Handles nested
        brackets correctly.

        GH#261: Enables parse_value() to detect IDENTIFIER[bracket]OPERATOR patterns
        and dispatch them to parse_flow_expression() rather than the multi-word path.

        Args:
            bracket_start: Token index where the LIST_START token is located.

        Returns:
            TokenType of the first token after the matching LIST_END, or TokenType.EOF
            if no match found.
        """
        if bracket_start >= len(self.tokens) or self.tokens[bracket_start].type != TokenType.LIST_START:
            if bracket_start < len(self.tokens):
                return self.tokens[bracket_start].type
            return TokenType.EOF

        depth = 1
        i = bracket_start + 1
        while i < len(self.tokens) and depth > 0:
            t = self.tokens[i]
            if t.type == TokenType.LIST_START:
                depth += 1
            elif t.type == TokenType.LIST_END:
                depth -= 1
            i += 1

        if i < len(self.tokens):
            return self.tokens[i].type
        return TokenType.EOF

    def _is_adjacent_bracket(self) -> bool:
        """Check if current LIST_START token is immediately adjacent to the previous token.

        GH#276 rework: Per OCTAVE spec, constructor syntax requires `[` immediately
        adjacent to NAME (no whitespace). `NAME[args]` is a constructor, but
        `NAME [args]` (with space) is NAME followed by a separate list.

        Returns:
            True if the bracket is adjacent (constructor syntax), False if there's
            a whitespace gap (separate list).
        """
        if self.pos < 1:
            return False
        prev = self.tokens[self.pos - 1]
        bracket = self.current()
        if prev.line != bracket.line:
            return False
        # Compute the raw text length of the previous token
        if prev.type == TokenType.NUMBER and prev.raw is not None:
            prev_len = len(prev.raw)
        elif prev.type == TokenType.BOOLEAN:
            prev_len = 4 if prev.value else 5  # "true" or "false"
        elif prev.type == TokenType.NULL:
            prev_len = 4  # "null"
        elif prev.type == TokenType.STRING:
            prev_len = len(prev.value) + 2  # Surrounding quotes
        else:
            prev_len = len(str(prev.value))
        return prev.column + prev_len == bracket.column

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
        # GH#276 round 2: Use blacklist approach — capture ALL tokens inside
        # brackets except LIST_END (which terminates). This is future-proof:
        # any new token type will automatically be preserved instead of silently
        # dropped, satisfying I1 (syntactic fidelity).
        #
        # GH#276 round 3: Also skip COMMENT, NEWLINE, and INDENT tokens.
        # These are non-semantic tokens that should not become constructor
        # payload data, just as they are filtered in list parsing (I1/I4).
        _SKIP_TYPES = {TokenType.COMMENT, TokenType.NEWLINE, TokenType.INDENT}

        annotation_tokens: list[str] = []

        while bracket_depth > 0 and self.current().type != TokenType.EOF:
            tok = self.current()
            if tok.type == TokenType.LIST_START:
                bracket_depth += 1
                annotation_tokens.append("[")
            elif tok.type == TokenType.LIST_END:
                bracket_depth -= 1
                if bracket_depth > 0:  # Don't include the final ]
                    annotation_tokens.append("]")
            elif tok.type == TokenType.COMMA:
                annotation_tokens.append(",")
            elif tok.type in _SKIP_TYPES:
                pass  # Non-semantic tokens: skip silently
            else:
                # Blacklist approach: capture any token between [ and ].
                # Use _token_to_str for consistent stringification of all
                # value types (NUMBER with raw, BOOLEAN, NULL, VERSION,
                # VARIABLE, STRING with quotes, IDENTIFIER, operators, etc.)
                annotation_tokens.append(_token_to_str(tok))
            self.advance()

        # GH#276 rework: Return empty string for empty brackets FOO[]
        # instead of None, so FOO<> is emitted (I4 auditability).
        return "".join(annotation_tokens) if annotation_tokens else ""

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
        """Parse a complete OCTAVE document.

        ADR-0006 SR2-T2 (GH#377): populates ``start_byte`` / ``end_byte``
        on the Document (covering the full NFC byte stream) and on the
        META region when present (``meta_start_byte`` / ``meta_end_byte``).
        """
        doc = Document()
        # Document start_byte is always 0 (NFC content base offset).
        doc.start_byte = 0
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

        # Parse META block first if present.
        # ADR-0006 SR2-T2 (GH#377): record byte range of the META region for
        # downstream consumers (PR-3 emitter). Captured BEFORE the call so the
        # start_byte reflects the META identifier token; the end_byte reflects
        # whichever token sits one past the last META child.
        if self.current().type == TokenType.IDENTIFIER and self.current().value == "META":
            meta_start_tok = self.current()
            meta_block = self.parse_meta_block()
            doc.meta = meta_block
            doc.meta_start_byte = meta_start_tok.start_byte
            # The current token (post parse_meta_block) is one past the META
            # region; use the previously consumed token's end_byte.
            prev_idx = max(0, self.pos - 1)
            doc.meta_end_byte = self.tokens[prev_idx].end_byte
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
        # ADR-0006 SR2-T2 PR-2 (GH#377): track the start_byte of the first
        # comment in the pending band, so the eventual parse_section()
        # call can populate ``node.comment_block_start_byte``. Reset to
        # None whenever pending_comments is reset to [].
        pending_comments_start_byte: int | None = None
        # GH#294: Track key positions for duplicate detection at document level
        doc_key_positions: dict[str, list[int]] = {}

        while self.current().type != TokenType.ENVELOPE_END and self.current().type != TokenType.EOF:
            # Skip indentation at document level
            if self.current().type == TokenType.INDENT:
                self.advance()
                continue

            # Issue #182: Collect comments as pending for next section
            if self.current().type == TokenType.COMMENT:
                if not pending_comments:
                    pending_comments_start_byte = self.current().start_byte
                pending_comments.append(self.current().value)
                self.advance()
                continue

            # Skip newlines
            if self.current().type == TokenType.NEWLINE:
                self.advance()
                continue

            # Parse section (assignment or block) with pending comments
            section = self.parse_section(0, pending_comments, leading_comments_start_byte=pending_comments_start_byte)
            pending_comments = []  # Reset after passing to section
            pending_comments_start_byte = None
            if section:
                # GH#294: Track duplicate keys at document level
                if isinstance(section, Assignment):
                    sec_key = section.key
                    sec_line = section.line
                    if sec_key in doc_key_positions:
                        doc_key_positions[sec_key].append(sec_line)
                        self._emit_duplicate_key_warning(sec_key, sec_line, doc_key_positions)
                    else:
                        doc_key_positions[sec_key] = [sec_line]
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
            # ADR-0006 SR2-T2 PR-2 (GH#377): trailing-comments byte band
            # = first comment's start_byte ... last comment's end_byte.
            doc.trailing_comments_start_byte = pending_comments_start_byte
            # End byte = position of the token immediately preceding
            # ENVELOPE_END / EOF. self.pos points at ENVELOPE_END (or
            # EOF) when we exit the loop; the trailing band ends at the
            # previous token's end_byte.
            _band_end_idx = max(0, self.pos - 1)
            doc.trailing_comments_end_byte = self.tokens[_band_end_idx].end_byte

        # Expect END envelope (lenient - allow missing)
        if self.current().type == TokenType.ENVELOPE_END:
            self.advance()

        # ADR-0006 SR2-T2 (GH#377): Document.end_byte = last token's end_byte.
        # The lexer emits EOF with end_byte == len(content_nfc.encode()), so
        # this transitively covers the whole NFC byte stream.
        if self.tokens:
            doc.end_byte = self.tokens[-1].end_byte

        # ADR-0006 SR2-T2 PR-2 (GH#377): trail-anchored whitespace policy.
        # A node's end_byte extends through its trailing blank lines up to
        # (but not including) the next sibling's start_byte. Implemented as
        # a post-pass walking doc.sections (and children) in order.
        # See ADR §3 whitespace subsection.
        self._extend_trail_anchored_spans(doc)

        # CE BLOCKER (PR #418): propagate descendant ``repaired=True`` to
        # ancestor ``body_dirty=True`` so the Strategy A T8 slice path in
        # emit() cannot splice the OLD baseline bytes for a parent whose
        # child Assignment was lenient-repaired (e.g. multi_word_coalesce,
        # pattern_autoquote) during parse construction. Same propagation
        # contract that ``core/repair.py:_repair_ast_node`` enforces for
        # the post-parse schema-repair surface, applied here at a single
        # post-pass chokepoint.
        _propagate_repaired_to_body_dirty(doc)

        # GH #420 Option D: consume any additional top-level envelopes that
        # follow the first ===END===.  Each becomes an ``Envelope`` node on
        # ``doc.additional_envelopes``.  Single-envelope documents are
        # unaffected: the loop body only runs when another ``ENVELOPE_START``
        # is present.  See ``parse_additional_envelope`` for the body
        # contract (which mirrors envelope-#1 parsing minus document-level
        # surface — no grammar sentinel, no YAML frontmatter).
        while True:
            self.skip_whitespace(skip_comments=False)
            if self.current().type != TokenType.ENVELOPE_START:
                break
            envelope = self.parse_additional_envelope()
            doc.additional_envelopes.append(envelope)

        return doc

    def parse_additional_envelope(self) -> Envelope:
        """Parse a sibling top-level envelope into an ``Envelope`` node.

        GH #420 Option D (additive multi-envelope support).  Called by
        ``parse_document`` for each envelope #2..N after the first
        ``===END===`` is consumed.  The body logic mirrors the
        single-envelope parsing in ``parse_document`` (META block,
        optional separator, section/comment/newline loop, trailing
        comments, ``===END===``) and populates the same per-envelope
        audit/preserve fields (``meta_start_byte`` / ``meta_end_byte`` /
        ``trailing_comments_start_byte`` / ``trailing_comments_end_byte``
        and ``start_byte`` / ``end_byte`` on the envelope itself) so that
        Strategy A preserve mode can slice unchanged sibling envelopes
        verbatim from baseline (#420 AC1) on emission.

        Document-level surface (YAML frontmatter, grammar sentinel) is
        intentionally NOT recognised here — those belong on envelope #1
        only, before the first ``===NAME===``.
        """
        envelope = Envelope()

        # Capture the envelope's start_byte at the ENVELOPE_START token.
        envelope_start_tok = self.current()
        envelope.start_byte = envelope_start_tok.start_byte

        # Consume ===NAME=== and record the envelope name.
        token = self.advance()
        envelope.name = token.value
        envelope.line = token.line
        envelope.column = token.column
        self.skip_whitespace(skip_comments=False)

        # Parse META block if present (parallel to parse_document META
        # handling — see lines ~546-556 there for the source).
        if self.current().type == TokenType.IDENTIFIER and self.current().value == "META":
            meta_start_tok = self.current()
            meta_block = self.parse_meta_block()
            envelope.meta = meta_block
            envelope.meta_start_byte = meta_start_tok.start_byte
            prev_idx = max(0, self.pos - 1)
            envelope.meta_end_byte = self.tokens[prev_idx].end_byte
            self.skip_whitespace(skip_comments=False)

        # Optional separator.
        if self.current().type == TokenType.SEPARATOR:
            envelope.has_separator = True
            self.advance()
            self.skip_whitespace(skip_comments=False)

        # Body parse — same comment/section/newline pattern as
        # parse_document, scoped to this envelope.
        pending_comments: list[str] = []
        pending_comments_start_byte: int | None = None
        env_key_positions: dict[str, list[int]] = {}

        while self.current().type != TokenType.ENVELOPE_END and self.current().type != TokenType.EOF:
            if self.current().type == TokenType.INDENT:
                self.advance()
                continue

            if self.current().type == TokenType.COMMENT:
                if not pending_comments:
                    pending_comments_start_byte = self.current().start_byte
                pending_comments.append(self.current().value)
                self.advance()
                continue

            if self.current().type == TokenType.NEWLINE:
                self.advance()
                continue

            section = self.parse_section(
                0,
                pending_comments,
                leading_comments_start_byte=pending_comments_start_byte,
            )
            pending_comments = []
            pending_comments_start_byte = None
            if section:
                if isinstance(section, Assignment):
                    sec_key = section.key
                    sec_line = section.line
                    if sec_key in env_key_positions:
                        env_key_positions[sec_key].append(sec_line)
                        self._emit_duplicate_key_warning(sec_key, sec_line, env_key_positions)
                    else:
                        env_key_positions[sec_key] = [sec_line]
                envelope.sections.append(section)
            elif self.current().type not in (TokenType.ENVELOPE_END, TokenType.EOF):
                self.advance()

        # Trailing comments band (band that lives between the last
        # section's end_byte and the ===END=== marker).
        if pending_comments:
            envelope.trailing_comments = pending_comments
            envelope.trailing_comments_start_byte = pending_comments_start_byte
            _band_end_idx = max(0, self.pos - 1)
            envelope.trailing_comments_end_byte = self.tokens[_band_end_idx].end_byte

        # Consume ===END=== (lenient — allow missing for symmetry with
        # parse_document's tolerance).
        if self.current().type == TokenType.ENVELOPE_END:
            end_tok = self.current()
            envelope.end_byte = end_tok.end_byte
            self.advance()
        else:
            # Lenient: stamp end_byte from the last token seen so the
            # slice path still has a usable bound.  Strategy A preserve
            # mode then conservatively re-emits this envelope canonically
            # (no baseline slice) until structural invariants are
            # restored.
            prev_idx = max(0, self.pos - 1)
            envelope.end_byte = self.tokens[prev_idx].end_byte

        # Extend trail-anchored spans inside this envelope's sections,
        # parallel to the post-pass on doc.sections in parse_document.
        self._extend_trail_anchored_spans_sections(envelope.sections)

        # Propagate any descendant repaired=True up to body_dirty signals
        # on this envelope's sections, mirroring the Document post-pass.
        # The helper recurses ``sections`` (which Envelope shares with
        # Document) so a single call covers the whole envelope subtree.
        _propagate_repaired_to_body_dirty(envelope)

        return envelope

    def _extend_trail_anchored_spans_sections(self, sections: list[ASTNode]) -> None:
        """Trail-anchored span extension scoped to a sibling list.

        Mirrors ``_extend_trail_anchored_spans`` but operates directly on
        a ``sections`` list (used by ``parse_additional_envelope`` since
        that path does not own a full ``Document``).
        """

        def _adjust(siblings: list[Any]) -> None:
            for i, node in enumerate(siblings):
                if isinstance(node, (Block, Section)):
                    _adjust(node.children)
                if i + 1 >= len(siblings):
                    continue
                next_start = getattr(siblings[i + 1], "start_byte", None)
                cur_end = getattr(node, "end_byte", None)
                if next_start is not None and cur_end is not None and cur_end <= next_start:
                    node.end_byte = next_start

        _adjust(sections)

    def _extend_trail_anchored_spans(self, doc: Document) -> None:
        """Extend each node's ``end_byte`` to its successor's ``start_byte``.

        ADR-0006 SR2-T2 PR-2 (GH#377). For each ordered sibling list
        (doc.sections, Block.children, Section.children), set
        ``sibling[i].end_byte = sibling[i+1].start_byte`` when both are
        non-None and the existing end_byte is <= the successor's start.
        For the last sibling, leave its end_byte unchanged — the parent
        owns the gap up to its own end_byte (or to ===END=== for
        doc.sections; the trailing-comments band lives there).

        Containers (Block, Section) are recursed BEFORE their own
        end_byte is adjusted, so child extension does not race with
        parent extension on the same byte position.
        """

        def _adjust(siblings: list[Any]) -> None:
            for i, node in enumerate(siblings):
                # Recurse first so children's end_bytes reach their own
                # next-sibling boundaries before parent re-adjusts.
                if isinstance(node, (Block, Section)):
                    _adjust(node.children)
                if i + 1 >= len(siblings):
                    continue
                next_start = getattr(siblings[i + 1], "start_byte", None)
                cur_end = getattr(node, "end_byte", None)
                if next_start is not None and cur_end is not None and cur_end <= next_start:
                    node.end_byte = next_start

        _adjust(doc.sections)

    def parse_meta_block(self) -> dict[str, Any]:
        """Parse META block into dictionary.

        Issue #179: Detects duplicate keys and emits warnings per I4 auditability.
        GH#294: Enhanced to track all occurrence lines and use consolidated warning format.
        Per spec: DUPLICATES::keys_must_be_unique_per_block
        """
        meta: dict[str, Any] = {}
        # GH#294: Track ALL key positions for duplicate detection (key -> list of line numbers)
        key_positions: dict[str, list[int]] = {}

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

            # GH#297: Handle comments inside META block.
            # Comments (inline after value or standalone lines) must be
            # consumed without breaking out of the META parsing loop.
            # Without this, a COMMENT token causes the else-break below
            # to fire, ejecting all subsequent keys to document root.
            # Only consume comments that are indented (part of META block),
            # not root-level comments that signal META block has ended.
            if self.current().type == TokenType.COMMENT:
                if indent_level > 0 and not has_indented:
                    break  # Root-level comment — META block is done
                self.advance()
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

                    # GH#294: Track ALL occurrences and emit warning on duplicates
                    if key in key_positions:
                        key_positions[key].append(key_line)
                        self._emit_duplicate_key_warning(key, key_line, key_positions)
                    else:
                        key_positions[key] = [key_line]

                    meta[key] = value
                elif self.current().type == TokenType.BLOCK:
                    # GH#287 P3: Handle nested block key (e.g., LOSS_PROFILE:)
                    # Parse children as a nested dict to preserve parent-child association
                    self.advance()  # Consume BLOCK (:)
                    self.skip_whitespace()

                    nested_meta: dict[str, Any] = {}
                    # PR#307 Finding 1: Track duplicate keys within nested blocks
                    nested_key_positions: dict[str, list[int]] = {}
                    if self.current().type == TokenType.INDENT:
                        nested_indent = self.current().value
                        self.advance()
                        nested_has_indented = True

                        while True:
                            if self.current().type in (TokenType.EOF, TokenType.ENVELOPE_END):
                                break

                            if self.current().type == TokenType.INDENT:
                                if self.current().value < nested_indent:
                                    break  # Dedent, end of nested block
                                self.advance()
                                nested_has_indented = True
                                continue

                            if self.current().type == TokenType.NEWLINE:
                                self.advance()
                                nested_has_indented = False
                                continue

                            # PR#307 Finding 3: Guard nested comment handler
                            # against consuming root-level comments
                            if self.current().type == TokenType.COMMENT:
                                if nested_indent > 0 and not nested_has_indented:
                                    break  # Root-level comment — nested block is done
                                self.advance()
                                continue

                            if self.current().type == TokenType.IDENTIFIER:
                                if nested_indent > 0 and not nested_has_indented:
                                    break

                                nested_key = self.current().value
                                nested_key_line = self.current().line
                                self.advance()
                                if self.current().type == TokenType.ASSIGN:
                                    self.advance()
                                    nested_value = self.parse_value()

                                    # PR#307 Finding 1: Emit W_DUPLICATE_KEY
                                    # for duplicate keys in nested blocks
                                    if nested_key in nested_key_positions:
                                        nested_key_positions[nested_key].append(nested_key_line)
                                        self._emit_duplicate_key_warning(
                                            nested_key, nested_key_line, nested_key_positions
                                        )
                                    else:
                                        nested_key_positions[nested_key] = [nested_key_line]

                                    nested_meta[nested_key] = nested_value
                                else:
                                    continue
                            else:
                                break

                    # PR#307 Finding 2: Check for duplicate block-form keys
                    if key in key_positions:
                        key_positions[key].append(key_line)
                        self._emit_duplicate_key_warning(key, key_line, key_positions)
                    else:
                        key_positions[key] = [key_line]
                    meta[key] = nested_meta
                    # GH#287: Reset indentation tracking after nested block.
                    # The nested block consumed tokens across lines; the next
                    # token may sit at column 0 (no INDENT emitted).  Without
                    # this reset has_indented would remain True from the
                    # parent key's indent, causing the outer loop to absorb
                    # root-level identifiers into META.
                    has_indented = False
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

        # Issue #217: Don't skip comments here - preserve them for section children
        self.skip_whitespace(skip_comments=False)

        # Parse section children (similar to block parsing)
        children: list[ASTNode] = []
        # GH#294: Track key positions for duplicate detection in section children
        section_key_positions: dict[str, list[int]] = {}

        # Issue #217: Collect any comments at column 0 before first indented child
        # These are orphan comments that appear between section header and children
        pre_indent_comments: list[str] = []
        while self.current().type in (TokenType.COMMENT, TokenType.NEWLINE):
            if self.current().type == TokenType.COMMENT:
                pre_indent_comments.append(self.current().value)
            self.advance()

        # Expect indentation for children
        if self.current().type == TokenType.INDENT:
            child_indent = self.current().value
            self.advance()

            # Track current line's indentation to determine if SECTION is child or sibling
            current_line_indent = child_indent

            # Issue #182: Track pending comments for next child
            # Issue #217: Include any pre-indent comments collected before first INDENT
            pending_comments: list[str] = pre_indent_comments.copy()
            # PR-2 T4 (GH#377): track first-comment start_byte for the
            # leading-comment band span. pre_indent_comments at this
            # point have already been consumed by the earlier loop so
            # their start byte is lost; we approximate by using the next
            # COMMENT token's start_byte if pending was repopulated by
            # pre_indent_comments. For pre_indent_comments-only cases,
            # set to None so the slice path falls back to canonical
            # re-emission of the parent (safe default).
            pending_comments_start_byte: int | None = None

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
                    if not pending_comments:
                        pending_comments_start_byte = self.current().start_byte
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

                # GH#348: Detect numeric keys before parse_section to avoid
                # silent data loss (I4 violation). Numeric keys are consumed
                # and warnings emitted for recovery.
                if self._try_consume_numeric_key():
                    # GH#361r4: Flush pending comments as children before
                    # resetting. Silently discarding comments violates I4
                    # (Transform Auditability).
                    for comment_text in pending_comments:
                        children.append(Comment(text=comment_text))
                    pending_comments = []
                    pending_comments_start_byte = None
                    current_line_indent = 0
                    continue

                # Parse child with any pending comments
                child = self.parse_section(
                    child_indent,
                    pending_comments,
                    leading_comments_start_byte=pending_comments_start_byte,
                )
                pending_comments = []  # Reset after passing to child
                pending_comments_start_byte = None
                if child:
                    # GH#294: Track duplicate keys in section children
                    if isinstance(child, Assignment):
                        child_key = child.key
                        child_line = child.line
                        if child_key in section_key_positions:
                            section_key_positions[child_key].append(child_line)
                            self._emit_duplicate_key_warning(child_key, child_line, section_key_positions)
                        else:
                            section_key_positions[child_key] = [child_line]
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
        else:
            # Issue #217: No indented children, but may have pre-indent comments
            # Add them as orphan comments in the section
            if pre_indent_comments:
                for comment_text in pre_indent_comments:
                    children.append(Comment(text=comment_text))

        # ADR-0006 SR2-T2 (GH#377): span = §-marker token start ... last
        # child's end (or section_token's end_byte if no children).
        section_end_byte: int | None = section_token.end_byte
        if children:
            for _span_child in reversed(children):
                _child_end = getattr(_span_child, "end_byte", None)
                if _child_end is not None:
                    section_end_byte = _child_end
                    break
        return Section(
            section_id=section_id,
            key=section_name,
            annotation=annotation,
            children=children,
            line=section_token.line,
            column=section_token.column,
            start_byte=section_token.start_byte,
            end_byte=section_end_byte,
        )

    def _try_consume_numeric_key(self) -> bool:
        """Detect and consume numeric key assignments, emitting I4 warning.

        GH#348: Numeric keys (e.g., 1::"value") are not valid OCTAVE identifiers.
        When encountered as block/section children, the parser previously returned
        None from parse_section(), causing the child loop to break and silently
        drop all remaining content (I4 violation: silent data loss).

        This method detects NUMBER::value patterns, consumes the tokens to avoid
        infinite loops, and emits a W_NUMERIC_KEY_DROPPED warning with the
        dropped key and value for recovery (I4: "if bits lost must have receipt").

        Returns:
            True if a numeric key was consumed (caller should continue), False otherwise.
        """
        if self.current().type == TokenType.NUMBER and self.peek().type == TokenType.ASSIGN:
            key_token = self.current()
            key_str = str(key_token.value)
            self.advance()  # consume NUMBER
            self.advance()  # consume ASSIGN (::)
            # Parse the value so it's fully consumed from the token stream
            value = self.parse_value()
            # Convert value to string for the warning message
            value_str = str(value) if value is not None else ""
            self.warnings.append(
                {
                    "type": "lenient_parse",
                    "subtype": "numeric_key_dropped",
                    "key": key_str,
                    "value": value_str,
                    "line": key_token.line,
                    "column": key_token.column,
                    "message": (
                        f"W_NUMERIC_KEY_DROPPED at line {key_token.line}: "
                        f"Numeric key '{key_str}' is not a valid OCTAVE identifier. "
                        f"Assignment {key_str}::{value_str!r} was dropped from "
                        f"canonical output. Use a string identifier instead "
                        f"(e.g., ITEM_{key_str}::{value_str!r})."
                    ),
                }
            )
            return True
        return False

    def parse_section(
        self,
        base_indent: int,
        leading_comments: list[str] | None = None,
        leading_comments_start_byte: int | None = None,
    ) -> Assignment | Block | Section | None:
        """Parse a top-level section (assignment, block, or section).

        Args:
            base_indent: The base indentation level for this section
            leading_comments: Comments collected before this section (Issue #182)
            leading_comments_start_byte: ADR-0006 SR2-T2 PR-2 (GH#377).
                Start byte of the first comment in ``leading_comments``;
                populates ``node.comment_block_start_byte`` so Strategy
                A can decide whether to splice the leading-comment band
                (parent clean) or re-emit it (parent dirty).
        """
        # Check for section marker first
        if self.current().type == TokenType.SECTION:
            section = self.parse_section_marker()
            if section and leading_comments:
                section.leading_comments = leading_comments
                # PR-2 T4: comment-block span on the wrapping Section.
                section.comment_block_start_byte = leading_comments_start_byte
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
            # GH#310: Capture whether value is quoted BEFORE parse_value() strips quotes.
            # Used to emit W_PATTERN_AUTOQUOTE when PATTERN/REGEX values are bare.
            value_is_quoted = self.current().type == TokenType.STRING
            # ADR-0006 SR2-T2 PR-2 (GH#377): track lenient_parse warnings
            # emitted during this Assignment's value parse. If any
            # lenient repair fires (multi_word_coalesce, etc.) the
            # source bytes diverge from the AST value semantically;
            # splicing them back would re-introduce the unrepaired
            # form. The Assignment must be marked ``repaired=True`` so
            # Strategy A's emitter (PR-3 / T8) re-emits canonically.
            _warnings_before_value = len(self.warnings)
            value = self.parse_value()

            # GH#310: PATTERN/REGEX keys with bare (unquoted) values get auto-quoted
            # by the emitter. Emit I4 audit warning so the correction is traceable.
            if (
                key in KNOWN_CONSTRUCTORS
                and key in ("PATTERN", "REGEX")
                and not value_is_quoted
                and isinstance(value, str)
            ):
                self.warnings.append(
                    {
                        "type": "lenient_parse",
                        "subtype": "pattern_autoquote",
                        "key": key,
                        "value": value,
                        "line": identifier_token.line,
                        "column": identifier_token.column,
                        "message": (
                            f"W_PATTERN_AUTOQUOTE at line {identifier_token.line}: "
                            f"'{key}' value '{value}' was bare (unquoted). "
                            f"Auto-quoted for lexical matching fidelity (I1)."
                        ),
                    }
                )

            # Issue #182: Collect trailing comment after value
            trailing_comment = self.collect_trailing_comment()
            # ADR-0006 SR2-T2 (GH#377): span = identifier ... last consumed token.
            assign_end_byte = self.tokens[max(0, self.pos - 1)].end_byte
            assignment = Assignment(
                key=key,
                value=value,
                line=identifier_token.line,
                column=identifier_token.column,
                leading_comments=leading_comments or [],
                trailing_comment=trailing_comment,
                start_byte=identifier_token.start_byte,
                end_byte=assign_end_byte,
                comment_block_start_byte=(leading_comments_start_byte if leading_comments else None),
            )
            # ADR-0006 SR1-T1 Step 5 §4.5 G2: record source-quoting provenance.
            # value_is_quoted is True iff the consumed value token was a STRING
            # (i.e. the user wrote KEY::"..."). False otherwise (bare IDENTIFIER,
            # NUMBER, BOOLEAN, NULL, list, inline-map, etc.). Step 3 will read
            # this to log identifier-dequoting decisions via tier_normalize.
            assignment.was_quoted = value_is_quoted
            # ADR-0006 SR2-T2 PR-2 (GH#377): mark Assignment repaired when
            # a lenient_parse warning fired during value parsing OR auto-quoting
            # (multi_word_coalesce, pattern_autoquote, etc.). Computed AFTER
            # pattern_autoquote since that warning fires after parse_value()
            # returns (CRS P1-1 fix on PR-2: re-checked here so the boolean
            # reflects the full warning window for this Assignment).
            _lenient_warning_fired = any(
                w.get("type") == "lenient_parse" for w in self.warnings[_warnings_before_value:]
            )
            if _lenient_warning_fired:
                assignment.repaired = True
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
            # GH#294: Track key positions for duplicate detection in block children
            block_key_positions: dict[str, list[int]] = {}

            # Issue #259: Literal zone directly after block colon (no indented children).
            # Token stream: IDENTIFIER -> BLOCK ':' -> NEWLINE -> FENCE_OPEN ...
            # After skip_whitespace() the NEWLINE is consumed and current() is FENCE_OPEN.
            # The normal INDENT-gated path would leave children empty, silently dropping
            # the literal zone (I1 violation). Parse it here into a bare-key Assignment.
            if self.current().type == TokenType.FENCE_OPEN:
                fence_open_tok = self.current()
                lzv = self.parse_literal_zone()
                lz_end_byte = self.tokens[max(0, self.pos - 1)].end_byte
                children.append(
                    Assignment(
                        key="",
                        value=lzv,
                        line=fence_open_tok.line,
                        column=fence_open_tok.column,
                        start_byte=fence_open_tok.start_byte,
                        end_byte=lz_end_byte,
                    )
                )

            # Expect indentation for children
            elif self.current().type == TokenType.INDENT:
                child_indent = self.current().value
                self.advance()

                # GH#81: Track current line's indentation to detect implicit dedent
                # When NEWLINE is consumed without subsequent INDENT, the next token
                # is at column 0 (implicit dedent). We must detect this and break.
                current_line_indent = child_indent

                # Issue #182: Track pending comments for next child
                pending_comments: list[str] = []
                # PR-2 T4 (GH#377): track first-comment start_byte for the
                # block child's leading-comment band span.
                pending_comments_start_byte: int | None = None

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
                        if not pending_comments:
                            pending_comments_start_byte = self.current().start_byte
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

                    # Issue #259: Literal zone as a child inside an indented block body.
                    # FENCE_OPEN is not an IDENTIFIER so parse_section() returns None,
                    # causing the loop to break and silently drop the literal zone (I1).
                    # Parse it here directly as a bare-key Assignment child.
                    if self.current().type == TokenType.FENCE_OPEN:
                        fence_open_tok = self.current()
                        lzv = self.parse_literal_zone()
                        lz_end_byte = self.tokens[max(0, self.pos - 1)].end_byte
                        children.append(
                            Assignment(
                                key="",
                                value=lzv,
                                line=fence_open_tok.line,
                                column=fence_open_tok.column,
                                leading_comments=pending_comments or [],
                                start_byte=fence_open_tok.start_byte,
                                end_byte=lz_end_byte,
                                comment_block_start_byte=(pending_comments_start_byte if pending_comments else None),
                            )
                        )
                        pending_comments = []
                        pending_comments_start_byte = None
                        current_line_indent = 0
                        continue

                    # GH#348: Detect numeric keys before parse_section to avoid
                    # silent data loss (I4 violation). Numeric keys are consumed
                    # and warnings emitted for recovery.
                    if self._try_consume_numeric_key():
                        # GH#361r4: Flush pending comments as children before
                        # resetting. Silently discarding comments violates I4
                        # (Transform Auditability).
                        for comment_text in pending_comments:
                            children.append(Comment(text=comment_text))
                        pending_comments = []
                        pending_comments_start_byte = None
                        current_line_indent = 0
                        continue

                    # Parse child with any pending comments
                    child = self.parse_section(
                        child_indent,
                        pending_comments,
                        leading_comments_start_byte=pending_comments_start_byte,
                    )
                    pending_comments = []  # Reset after passing to child
                    pending_comments_start_byte = None
                    if child:
                        # GH#294: Track duplicate keys in block children
                        if isinstance(child, Assignment):
                            child_key = child.key
                            child_line = child.line
                            if child_key in block_key_positions:
                                block_key_positions[child_key].append(child_line)
                                self._emit_duplicate_key_warning(child_key, child_line, block_key_positions)
                            else:
                                block_key_positions[child_key] = [child_line]
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

            # ADR-0006 SR2-T2 (GH#377): span = identifier_token.start ...
            # last child's end_byte (or block_token.end_byte if no children).
            block_end_byte: int | None = block_token.end_byte
            if children:
                for _span_child in reversed(children):
                    _child_end = getattr(_span_child, "end_byte", None)
                    if _child_end is not None:
                        block_end_byte = _child_end
                        break
            return Block(
                key=key,
                children=children,
                line=identifier_token.line,
                column=identifier_token.column,
                leading_comments=leading_comments or [],
                target=block_target,  # Issue #189: Block inheritance target
                start_byte=identifier_token.start_byte,
                end_byte=block_end_byte,
                comment_block_start_byte=(leading_comments_start_byte if leading_comments else None),
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

    def parse_literal_zone(self) -> LiteralZoneValue:
        """Parse a literal zone from FENCE_OPEN, LITERAL_CONTENT, FENCE_CLOSE tokens.

        Issue #235: Called when parse_value() encounters a FENCE_OPEN token.

        Returns:
            LiteralZoneValue with content, info_tag, and fence_marker.

        Raises:
            ParserError (E006): If FENCE_CLOSE is missing (unterminated zone).
        """
        fence_token = self.expect(TokenType.FENCE_OPEN)
        fence_data = fence_token.value  # dict with fence_marker and info_tag
        if not isinstance(fence_data, dict) or "fence_marker" not in fence_data:
            raise ParserError(
                f"Malformed FENCE_OPEN token at line {fence_token.line}.",
                fence_token,
                "E006",
            )
        marker = fence_data["fence_marker"]
        info_tag = fence_data.get("info_tag")

        # Clean info_tag: strip whitespace, normalize to None if empty
        if info_tag is not None:
            info_tag = info_tag.strip()
            if not info_tag:
                info_tag = None

        # Expect literal content
        if self.current().type == TokenType.LITERAL_CONTENT:
            content = self.current().value
            self.advance()
        else:
            content = ""  # Empty literal zone (I2: distinct from absent)

        # Expect closing fence
        if self.current().type == TokenType.FENCE_CLOSE:
            self.advance()
        else:
            raise ParserError(
                f"Unterminated literal zone starting at line {fence_token.line}. "
                f"Expected closing fence '{marker}' but reached "
                f"{self.current().type.name}.",
                fence_token,
                "E006",
            )

        # ADR-0006 SR2-T2 (GH#377): span = fence_open.start ...
        # last consumed token's end (FENCE_CLOSE or recovery point).
        lzv_end_byte = self.tokens[max(0, self.pos - 1)].end_byte
        return LiteralZoneValue(
            content=content,
            info_tag=info_tag,
            fence_marker=marker,
            start_byte=fence_token.start_byte,
            end_byte=lzv_end_byte,
        )

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
                # GH#276 round 2: Handle trailing bracket annotations.
                if self.current().type == TokenType.LIST_START:
                    if self._is_adjacent_bracket():
                        self._consume_bracket_annotation(capture=False)
                    else:
                        # Non-adjacent bracket: capture to prevent data loss (I4).
                        annotation = self._consume_bracket_annotation(capture=True)
                        if annotation is not None:
                            result = f"{result} [{annotation}]"
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
                # GH#276 round 2: Handle trailing bracket annotations.
                if self.current().type == TokenType.LIST_START:
                    if self._is_adjacent_bracket():
                        self._consume_bracket_annotation(capture=False)
                    else:
                        annotation = self._consume_bracket_annotation(capture=True)
                        if annotation is not None:
                            result = f"{result} [{annotation}]"

                return result

            # GH#287 P2: Check for NUMBER[bracket]OPERATOR pattern (e.g., 2024[x] → 2026[y]).
            # When a number is followed by brackets and then an operator, capture the
            # entire expression as a string to prevent data loss in operator-rich values.
            if next_token.type == TokenType.LIST_START:
                token_after_bracket = self._peek_past_brackets_at(self.pos + 1)
                if token_after_bracket in EXPRESSION_OPERATORS:
                    # Capture as operator-rich expression string
                    start_line = token.line
                    start_column = token.column
                    num_str = _token_to_str(token)
                    self.advance()  # Consume NUMBER

                    # Consume all remaining tokens on this value line:
                    # brackets, operators, identifiers, numbers
                    expr_parts = [num_str]
                    while self.current().type not in (
                        TokenType.NEWLINE,
                        TokenType.EOF,
                        TokenType.ENVELOPE_END,
                    ):
                        cur = self.current()
                        if cur.type == TokenType.LIST_START:
                            expr_parts.append("[")
                            self.advance()
                        elif cur.type == TokenType.LIST_END:
                            expr_parts.append("]")
                            self.advance()
                        elif cur.type in EXPRESSION_OPERATORS:
                            expr_parts.append(f" {cur.value} ")
                            self.advance()
                        elif cur.type in VALUE_TOKENS:
                            expr_parts.append(_token_to_str(cur))
                            self.advance()
                        elif cur.type == TokenType.COMMA:
                            expr_parts.append(",")
                            self.advance()
                        else:
                            break

                    result = "".join(expr_parts)
                    # I4 Audit: Emit W_SOURCE_COMPILE warning for operator-rich value capture
                    self.warnings.append(
                        {
                            "type": "lenient_parse",
                            "subtype": "source_compile_value",
                            "original": result,
                            "result": result,
                            "context": "operator_rich_value",
                            "line": start_line,
                            "column": start_column,
                        }
                    )
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
                # GH#276 round 2: Handle trailing bracket annotations.
                if self.current().type == TokenType.LIST_START:
                    if self._is_adjacent_bracket():
                        self._consume_bracket_annotation(capture=False)
                    else:
                        # Non-adjacent bracket: capture to prevent data loss (I4).
                        annotation = self._consume_bracket_annotation(capture=True)
                        if annotation is not None:
                            result = f"{result} [{annotation}]"
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
                # GH#276 round 2: Handle trailing bracket annotations.
                if self.current().type == TokenType.LIST_START:
                    if self._is_adjacent_bracket():
                        self._consume_bracket_annotation(capture=False)
                    else:
                        # Non-adjacent bracket: capture to prevent data loss (I4).
                        annotation = self._consume_bracket_annotation(capture=True)
                        if annotation is not None:
                            result = f"{result} [{annotation}]"
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
                # GH#276 round 2: Handle trailing bracket annotations.
                if self.current().type == TokenType.LIST_START:
                    if self._is_adjacent_bracket():
                        self._consume_bracket_annotation(capture=False)
                    else:
                        # Non-adjacent bracket: capture to prevent data loss (I4).
                        annotation = self._consume_bracket_annotation(capture=True)
                        if annotation is not None:
                            result = f"{result} [{annotation}]"
                return result

            # Standalone VERSION
            self.advance()
            return str(token.value)

        elif token.type == TokenType.LIST_START:
            return self.parse_list()

        # Issue #235: Literal zone detection
        # FENCE_OPEN token indicates start of a literal zone (fenced code block).
        # When a literal zone is the value of an assignment (KEY::\n```...```),
        # a NEWLINE token sits between ASSIGN and FENCE_OPEN. We handle that
        # case here: if current is NEWLINE and next is FENCE_OPEN, skip the
        # NEWLINE so the literal zone is consumed as the assignment value.
        elif token.type == TokenType.FENCE_OPEN:
            return self.parse_literal_zone()

        elif token.type == TokenType.NEWLINE and self.peek().type == TokenType.FENCE_OPEN:
            self.advance()  # Skip NEWLINE before fence
            return self.parse_literal_zone()

        elif token.type == TokenType.IDENTIFIER:
            # Check if this starts an expression with operators (GH#62, GH#65)
            next_token = self.peek()
            if next_token.type in EXPRESSION_OPERATORS:
                # Expression with operators like A->B->C, X+Y, A@B, A~B, Speed vs Quality, etc.
                return self.parse_flow_expression()

            # GH#261: Detect IDENTIFIER[bracket]OPERATOR pattern (e.g., CONST[X]∧CONST[Y]).
            # When next token is LIST_START, scan past the bracket group to check if an
            # expression operator follows. If so, dispatch to parse_flow_expression() which
            # will handle the embedded brackets and trailing annotations correctly.
            if next_token.type == TokenType.LIST_START:
                token_after_bracket = self._peek_past_brackets_at(self.pos + 1)
                if token_after_bracket in EXPRESSION_OPERATORS:
                    return self.parse_flow_expression()

            # GH#66: Capture multi-word bare values
            # Examples: "Main content", "Hello World Again"
            # Stops at: NEWLINE, COMMA, LIST_END, ENVELOPE markers, operators
            parts = [token.value]
            self.advance()

            # GH#276: Capture constructor bracket annotation NAME[args] -> NAME<args>
            # Per OCTAVE spec §1b: NAME immediately followed by [args] is constructor
            # syntax. The bracket contents are semantic arguments that must be preserved.
            # Convert to canonical angle-bracket form NAME<args> for I1 syntactic fidelity.
            # GH#276 rework: Adjacency check — only treat as constructor if [ is
            # immediately adjacent to NAME (no whitespace gap).
            if self.current().type == TokenType.LIST_START and self._is_adjacent_bracket():
                annotation = self._consume_bracket_annotation(capture=True)
                if annotation is not None:
                    parts[0] = f"{parts[0]}<{annotation}>"

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
                # GH#276: Capture bracket annotation if present after colon-path value
                # Examples: HERMES:API_TIMEOUT[note], MODULE:SUB[annotation]
                # Preserves constructor args as angle-bracket form for I1 fidelity.
                # GH#276 rework: Adjacency check — [ must be immediately adjacent.
                result_path = ":".join(parts)
                if self.current().type == TokenType.LIST_START and self._is_adjacent_bracket():
                    annotation = self._consume_bracket_annotation(capture=True)
                    if annotation is not None:
                        result_path = f"{result_path}<{annotation}>"
                return result_path

            # GH#66: Continue capturing consecutive identifiers as multi-word value
            # GH#63: Include NUMBER tokens in multi-word capture (convert to string)
            # Issue #140/#141: Include VALUE_TOKENS to prevent data loss
            # Stop at delimiters, operators, or non-value tokens

            # Track start position for I4 audit
            start_line = token.line
            start_column = token.column

            # GH#269 rework: Unified accumulator pattern for annotated identifiers.
            # CRS+CE review identified two problems with the previous two-path approach:
            # 1. Bare words after annotated tokens weren't coalesced with each other
            # 2. Early return for annotated-first tokens skipped expression operator checks
            # 3. Order-dependent behavior (A<X> B C vs A B C<X> gave different results)
            #
            # Solution: Lookahead scan to detect if ANY token in the sequence is annotated.
            # If so, use a unified accumulator loop that:
            #   - Buffers bare words and coalesces them on flush
            #   - Emits annotated tokens as separate items
            #   - Handles expression operators correctly
            # If not, fall through to existing bare-word coalescing + expression logic.

            has_any_annotation = _has_annotation(parts[0])
            if not has_any_annotation:
                # Lookahead: scan upcoming value tokens for annotations
                scan_pos = self.pos
                while scan_pos < len(self.tokens) and self.tokens[scan_pos].type in VALUE_TOKENS:
                    scan_val = _token_to_str(self.tokens[scan_pos])
                    if _has_annotation(scan_val):
                        has_any_annotation = True
                        break
                    scan_pos += 1

            if has_any_annotation:
                # GH#269 unified accumulator: bare_words buffer + items list
                bare_words: list[str] = []
                items: list[str] = []

                # Process the first token (already consumed)
                if _has_annotation(parts[0]):
                    items.append(parts[0])
                else:
                    bare_words.append(parts[0])

                # Process remaining value tokens and expression operators
                while self.current().type in VALUE_TOKENS or self.current().type in EXPRESSION_OPERATORS:
                    if self.current().type in EXPRESSION_OPERATORS:
                        # Flush bare_words before operator
                        if bare_words:
                            items.append(" ".join(bare_words))
                            bare_words = []
                        # Handle expression: collect operator and remaining tokens
                        expr_parts = list(items) if items else []
                        # If items is non-empty, the last item starts the expression LHS
                        # Build expression string from all collected items + operator + rest
                        op_parts: list[str] = []
                        while self.current().type in VALUE_TOKENS or self.current().type in EXPRESSION_OPERATORS:
                            if self.current().type in EXPRESSION_OPERATORS:
                                op_parts.append(self.current().value)
                                self.advance()
                            elif self.current().type in VALUE_TOKENS:
                                op_parts.append(_token_to_str(self.current()))
                                self.advance()
                            else:
                                break
                        # Merge: items collected so far become space-joined prefix,
                        # then operator expression appended
                        if expr_parts:
                            full_expr = " ".join(str(p) for p in expr_parts) + "".join(str(p) for p in op_parts)
                        else:
                            full_expr = "".join(str(p) for p in op_parts)
                        # GH#276 round 2: Handle trailing bracket annotations.
                        if self.current().type == TokenType.LIST_START:
                            if self._is_adjacent_bracket():
                                self._consume_bracket_annotation(capture=False)
                            else:
                                annotation = self._consume_bracket_annotation(capture=True)
                                if annotation is not None:
                                    full_expr = f"{full_expr} [{annotation}]"
                        return full_expr

                    cur_val = _token_to_str(self.current())
                    self.advance()
                    # GH#276: Check for constructor bracket annotation after this token
                    # e.g., ALWAYS[SYSTEM_COHERENCE] -> ALWAYS<SYSTEM_COHERENCE>
                    # GH#276 rework: Adjacency check — [ must be immediately adjacent.
                    if self.current().type == TokenType.LIST_START and self._is_adjacent_bracket():
                        annotation = self._consume_bracket_annotation(capture=True)
                        if annotation is not None:
                            cur_val = f"{cur_val}<{annotation}>"
                    if _has_annotation(cur_val):
                        # Flush accumulated bare words before annotated token
                        if bare_words:
                            items.append(" ".join(bare_words))
                            bare_words = []
                        items.append(cur_val)
                    else:
                        bare_words.append(cur_val)

                # Flush any remaining bare words
                if bare_words:
                    items.append(" ".join(bare_words))

                # GH#276 round 2: Handle trailing bracket annotations.
                if self.current().type == TokenType.LIST_START:
                    if self._is_adjacent_bracket():
                        self._consume_bracket_annotation(capture=False)
                    else:
                        # Non-adjacent bracket: capture into value to prevent data loss (I4).
                        annotation = self._consume_bracket_annotation(capture=True)
                        if annotation is not None:
                            last = items[-1] if items else ""
                            items[-1] = f"{last} [{annotation}]"

                # Return as ListValue if multiple items, scalar if single
                if len(items) == 1:
                    return items[0]
                return ListValue(items=items)

            # No annotations detected: original bare-word coalescing + expression logic
            word_parts = [parts[0]]

            while self.current().type in VALUE_TOKENS:
                # Check if next token after this identifier is an operator
                # If so, we're starting an expression, not a multi-word value
                if self.peek().type in EXPRESSION_OPERATORS:
                    # Include this word and then parse the rest as expression
                    # GH#66: Use _token_to_str to preserve NUMBER lexemes
                    word_parts.append(_token_to_str(self.current()))
                    self.advance()
                    # Now we need to continue with flow expression parsing
                    expr_parts_plain = [" ".join(word_parts)]
                    while self.current().type in VALUE_TOKENS or self.current().type in EXPRESSION_OPERATORS:
                        if self.current().type in EXPRESSION_OPERATORS:
                            expr_parts_plain.append(self.current().value)
                            self.advance()
                        elif self.current().type in VALUE_TOKENS:
                            # GH#66/#140/#141: Use _token_to_str to preserve all value token lexemes
                            expr_parts_plain.append(_token_to_str(self.current()))
                            self.advance()
                        else:
                            break
                    # I4 Audit: Emit warning when multi-word coalescing occurs in expression path
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
                    return "".join(str(p) for p in expr_parts_plain)

                # Just another word/number in the multi-word value
                # GH#66: Use _token_to_str to preserve NUMBER lexemes (e.g., 1e10)
                cur_word = _token_to_str(self.current())
                self.advance()
                # GH#276: Check for constructor bracket annotation after this word
                # GH#276 rework: Adjacency check — [ must be immediately adjacent.
                if self.current().type == TokenType.LIST_START and self._is_adjacent_bracket():
                    annotation = self._consume_bracket_annotation(capture=True)
                    if annotation is not None:
                        cur_word = f"{cur_word}<{annotation}>"
                word_parts.append(cur_word)

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
            if self.current().type == TokenType.LIST_START:
                if self._is_adjacent_bracket():
                    # Adjacent bracket: constructor annotation, consume without capture
                    # (already captured in the loop above at line ~1530)
                    self._consume_bracket_annotation(capture=False)
                else:
                    # GH#276 round 2: Non-adjacent bracket `A [B,C]` — the bracket
                    # content is NOT a constructor annotation but separate list data.
                    # Capture it into the value to prevent silent data loss (I4).
                    annotation = self._consume_bracket_annotation(capture=True)
                    if annotation is not None:
                        result = f"{result} [{annotation}]"

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
            # GH#276 round 2: Handle trailing bracket annotations.
            if self.current().type == TokenType.LIST_START:
                if self._is_adjacent_bracket():
                    self._consume_bracket_annotation(capture=False)
                else:
                    annotation = self._consume_bracket_annotation(capture=True)
                    if annotation is not None:
                        section_marker = f"{section_marker} [{annotation}]"

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
        # ADR-0006 SR2-T2 (GH#377): span = LIST_START.start ... LIST_END.end.
        list_start_byte = bracket_token.start_byte
        self.expect(TokenType.LIST_START)
        self.bracket_depth += 1  # GH#184: Track bracket nesting for NEVER rule validation

        # Issue #192: Check for deep nesting
        self._check_deep_nesting(bracket_token)

        items: list[Any] = []

        # Parse list items
        # GH#270: Removed cross-item inline map key duplicate tracking.
        # Each InlineMap item in a list is a separate array entry, so repeated
        # keys across items (e.g., [REGEX::"a", REGEX::"b"]) are intentional
        # and must not trigger W_DUPLICATE_KEY warnings. The previous tracking
        # (Issue #179) incorrectly treated list items as map entries.
        while True:
            # Skip whitespace/newlines/indents/comments (valid anywhere between items)
            # GH#272: COMMENT tokens inside bracket context must be stripped to prevent
            # comment text from being promoted to data values (I3 Mirror Constraint).
            while self.current().type in (TokenType.NEWLINE, TokenType.INDENT, TokenType.COMMENT):
                self.advance()

            # Check for end of list
            # Issue #162 Fix: Check for EOF to prevent infinite loop
            if self.current().type in (TokenType.LIST_END, TokenType.EOF, TokenType.ENVELOPE_END):
                break

            # Parse item value
            item = self.parse_list_item()
            items.append(item)

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

        # ADR-0006 SR2-T2 (GH#377): list_end_byte = previously consumed
        # token's end_byte (LIST_END or recovery point).
        list_end_byte = self.tokens[max(0, self.pos - 1)].end_byte

        # Issue #187: Check if this is a holographic pattern
        # Holographic patterns have the form: ["example"∧CONSTRAINT→§TARGET]
        # Detection: Look for CONSTRAINT (∧) token in the token slice
        holographic_result = self._try_parse_holographic(token_slice)
        if holographic_result is not None:
            holographic_result.start_byte = list_start_byte
            holographic_result.end_byte = list_end_byte
            return holographic_result

        return ListValue(
            items=items,
            tokens=token_slice,
            start_byte=list_start_byte,
            end_byte=list_end_byte,
        )

    def parse_list_item(self) -> Any:
        """Parse a single list item.

        Issue #185: Validates INLINE_MAP_NESTING::forbidden[values_must_be_atoms]
        from octave-core-spec.oct.md section 5::MODES.
        Inline map values must be atoms - nested inline maps are forbidden.
        Only enforced in strict mode; lenient mode emits warning.

        Issue #246: Also recognizes NUMBER::value as inline map syntax.
        Numbered-key syntax (e.g., 1::"string") inside list literals must be
        parsed as InlineMap items, not flattened into separate tokens.
        """
        # Check for inline map [k::v, k2::v2]
        # Issue #246: Also handle NUMBER::value (numbered-key syntax in lists)
        is_identifier_key = self.current().type == TokenType.IDENTIFIER and self.peek().type == TokenType.ASSIGN
        is_number_key = self.current().type == TokenType.NUMBER and self.peek().type == TokenType.ASSIGN
        if is_identifier_key or is_number_key:
            # Inline map item
            pairs: dict[str, Any] = {}
            key_token = self.current()  # Capture for error reporting
            # Issue #246: Convert NUMBER key to string for consistent InlineMap handling
            key = str(self.current().value) if is_number_key else self.current().value
            self.advance()
            self.expect(TokenType.ASSIGN)
            # Issue #305: Capture whether the value token is a quoted string
            # before parse_value() consumes it. Bare identifiers are also str
            # after parsing, so we need the token type to distinguish.
            value_is_quoted_string = self.current().type == TokenType.STRING
            value = self.parse_value()

            # Issue #185: Validate inline map values are atoms (no nested inline maps)
            # Per spec: INLINE_MAP_NESTING::forbidden[values_must_be_atoms]
            # Only error in strict mode; lenient mode emits warning per I4
            self._validate_inline_map_value_is_atom(key, value, key_token)

            # GH#310: PATTERN/REGEX keys with bare (unquoted) values in inline-map
            # get auto-quoted by the emitter. Emit I4 audit warning so the
            # correction is traceable (mirrors assignment path logic).
            if (
                is_identifier_key
                and key in KNOWN_CONSTRUCTORS
                and key in ("PATTERN", "REGEX")
                and not value_is_quoted_string
                and isinstance(value, str)
            ):
                self.warnings.append(
                    {
                        "type": "lenient_parse",
                        "subtype": "pattern_autoquote",
                        "key": key,
                        "value": value,
                        "line": key_token.line,
                        "column": key_token.column,
                        "message": (
                            f"W_PATTERN_AUTOQUOTE at line {key_token.line}: "
                            f"'{key}' value '{value}' was bare (unquoted) in inline-map. "
                            f"Auto-quoted for lexical matching fidelity (I1)."
                        ),
                    }
                )

            # Issue #305: Detect known constructor names used as assignment keys
            # Per §2c::BRACKET_FORMS, names like REGEX, ENUM, TYPE should use
            # constructor form REGEX["pattern"] not assignment form REGEX::"pattern"
            # Only warn when value is a quoted string (strongly suggests constructor intent)
            if is_identifier_key and key in KNOWN_CONSTRUCTORS and value_is_quoted_string:
                suggested = f'{key}["{value}"]'
                self.warnings.append(
                    {
                        "type": "lenient_parse",
                        "subtype": "constructor_misuse",
                        "key": key,
                        "value": value,
                        "line": key_token.line,
                        "column": key_token.column,
                        "message": (
                            f"W_CONSTRUCTOR_MISUSE at line {key_token.line}: "
                            f"'{key}' is a known constructor name (§2c) but used "
                            f"as an assignment key. Did you mean {suggested} "
                            f"(constructor form)?"
                        ),
                    }
                )

            pairs[key] = value
            # ADR-0006 SR2-T2 (GH#377): span = key_token.start ... last consumed
            # token's end (covers k::v pair extent).
            im_end_byte = self.tokens[max(0, self.pos - 1)].end_byte
            return InlineMap(
                pairs=pairs,
                start_byte=key_token.start_byte,
                end_byte=im_end_byte,
            )

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
                # GH#261: After consuming an identifier, check for an embedded bracket group
                # (e.g., CONST[X] in CONST[X]∧CONST[Y], or ENUM[A,B] in ENUM[A,B]∧CONST[C]).
                # A bracket group is "embedded" (part of the expression) when the token
                # after it is NOT a list-terminating token (COMMA, LIST_END, NEWLINE, EOF,
                # ENVELOPE markers). In that case consume and include it as part of the
                # expression string. The actual trailing annotation (followed by list
                # delimiter) is handled after the loop by _consume_bracket_annotation().
                if self.current().type == TokenType.LIST_START:
                    token_after = self._peek_past_brackets_at(self.pos)
                    if token_after not in (
                        TokenType.COMMA,
                        TokenType.LIST_END,
                        TokenType.NEWLINE,
                        TokenType.EOF,
                        TokenType.ENVELOPE_END,
                        TokenType.ENVELOPE_START,
                    ):
                        # Embedded bracket group: consume and include in expression string
                        # GH#276 round 4: Use blacklist approach (matching
                        # _consume_bracket_annotation) — capture ALL tokens
                        # except LIST_END, COMMENT, NEWLINE, INDENT.  This
                        # prevents silent data loss for BOOLEAN, VARIABLE,
                        # VERSION and any future token types (I1).
                        _EXPR_SKIP = {TokenType.COMMENT, TokenType.NEWLINE, TokenType.INDENT}
                        bracket_parts = ["["]
                        self.advance()  # Consume [
                        depth = 1
                        while depth > 0 and self.current().type != TokenType.EOF:
                            tok = self.current()
                            if tok.type == TokenType.LIST_START:
                                depth += 1
                                bracket_parts.append("[")
                            elif tok.type == TokenType.LIST_END:
                                depth -= 1
                                if depth > 0:
                                    bracket_parts.append("]")
                            elif tok.type == TokenType.COMMA:
                                bracket_parts.append(",")
                            elif tok.type in _EXPR_SKIP:
                                pass  # Non-semantic tokens: skip silently
                            else:
                                bracket_parts.append(_token_to_str(tok))
                            self.advance()
                        bracket_parts.append("]")
                        parts.append("".join(bracket_parts))
            else:
                break

        # GH#261: Consume trailing bracket annotation if present (e.g., [mutually_exclusive]
        # after REQ∧OPT). This is consistent with all other parse_value() paths which call
        # _consume_bracket_annotation(capture=False) before returning.
        # GH#276 round 2: Handle trailing bracket annotations.
        if self.current().type == TokenType.LIST_START:
            if self._is_adjacent_bracket():
                self._consume_bracket_annotation(capture=False)
            else:
                # Non-adjacent: capture to prevent data loss
                annotation = self._consume_bracket_annotation(capture=True)
                if annotation is not None:
                    parts.append(f"[{annotation}]")

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


def _propagate_repaired_to_body_dirty(node: Any) -> bool:
    """Propagate descendant ``repaired=True`` to ancestor ``body_dirty=True``.

    Walks the AST subtree rooted at ``node`` and returns True iff ``node``
    OR any descendant has ``repaired=True``. On the way out, every
    Block/Section whose descendant tree contains a repaired Assignment is
    marked ``body_dirty=True`` so the Strategy A T8 slice path in
    ``emit()`` falls through to the canonical re-emit path for that
    subtree.

    CE BLOCKER (PR #418, rework cycle 5): the parser sets
    ``assignment.repaired=True`` on a child Assignment whenever a lenient
    value-parse repair fires (e.g. multi_word_coalesce, pattern_autoquote)
    but the enclosing Block/Section is left with ``body_dirty=False``.
    Without this post-pass, preserve-mode emit would slice the parent's
    whole subtree from baseline — including the un-canonicalised child
    bytes — silently dropping the repair.

    This is the parser-side analogue of ``core/repair.py:_repair_ast_node``,
    which performs the same propagation for the post-parse schema-repair
    surface. The parser builds bottom-up so a single post-pass over the
    constructed Document is sufficient and cheap (one O(n) walk where n
    is the total node count, after which preserve-mode emit can dispatch
    in O(1) per top-level section).

    Args:
        node: AST node to scan (Document, Block, Section, Assignment, …).

    Returns:
        True iff this node OR any descendant has ``repaired=True``;
        False otherwise.
    """
    self_repaired = bool(getattr(node, "repaired", False))
    children = getattr(node, "children", None)
    sections = getattr(node, "sections", None)  # only Document has this

    descendant_repaired = False
    if children:
        for child in children:
            if _propagate_repaired_to_body_dirty(child):
                descendant_repaired = True
    if sections:
        for section in sections:
            if _propagate_repaired_to_body_dirty(section):
                descendant_repaired = True

    if descendant_repaired and hasattr(node, "body_dirty"):
        # Paired-write: any ancestor whose descendant subtree was
        # repaired MUST be marked body_dirty so emit() takes the
        # canonical re-emit path instead of slicing stale baseline
        # bytes for the now-mutated subtree.
        node.body_dirty = True

    return self_repaired or descendant_repaired


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


def parse_with_warnings(
    content: str | list[Token],
    *,
    strict_structure: bool = False,
) -> tuple[Document, list[dict]]:
    """Parse OCTAVE content into AST with I4 audit trail.

    Returns both the parsed document and any warnings generated during
    lenient parsing (e.g., multi-word value coalescing).

    I4 Immutable: "If not written and addressable, didn't happen"
    - Lenient parsing transforms must be auditable
    - Multi-word bare values coalesced into single string emit warnings

    Args:
        content: Raw OCTAVE text (lenient or canonical) or list of tokens
        strict_structure: If True, raise ParserError on structural issues
            (e.g., unclosed lists, nested inline maps) instead of leniently
            recovering. Use True when lenient=False in write mode (GH#361r3).

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
        ParserError: On syntax errors (always), or structural issues
            when strict_structure=True
    """
    raw_frontmatter: str | None = None

    if isinstance(content, str):
        # Issue #91: Strip YAML frontmatter before tokenization
        stripped_content, raw_frontmatter = _strip_yaml_frontmatter(content)
        tokens, lexer_repairs = tokenize(stripped_content)
    else:
        tokens = content
        lexer_repairs = []

    parser = Parser(tokens, strict_structure=strict_structure)
    doc = parser.parse_document()

    # Preserve frontmatter in Document AST for I4 auditability
    doc.raw_frontmatter = raw_frontmatter

    # Combine lexer repairs and parser warnings
    # Lexer repairs are about ASCII normalization
    # Parser warnings are about lenient parsing (multi-word coalescing)
    all_warnings = list(lexer_repairs) + parser.warnings

    return doc, all_warnings
