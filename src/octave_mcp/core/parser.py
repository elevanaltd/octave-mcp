"""OCTAVE parser with lenient input support.

Implements P1.3: lenient_parser_with_envelope_completion

Parses lexer tokens into AST with:
- Envelope inference for single documents
- Whitespace normalization around ::
- Nested block structure with indentation
- META block extraction
"""

from typing import Any

from octave_mcp.core.ast_nodes import Assignment, ASTNode, Block, Document, InlineMap, ListValue, Section
from octave_mcp.core.lexer import Token, TokenType, tokenize


class ParserError(Exception):
    """Parser error with position information."""

    def __init__(self, message: str, token: Token | None = None, error_code: str = "E001"):
        self.message = message
        self.token = token
        self.error_code = error_code
        if token:
            super().__init__(f"{error_code} at line {token.line}, column {token.column}: {message}")
        else:
            super().__init__(f"{error_code}: {message}")


class Parser:
    """OCTAVE parser with lenient input support."""

    def __init__(self, tokens: list[Token]):
        """Initialize parser with token stream."""
        self.tokens = tokens
        self.pos = 0
        self.current_indent = 0
        self.warnings: list[dict[str, Any]] = []  # Issue #64: track dropped lines

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

    def skip_whitespace(self) -> None:
        """Skip newlines and comments."""
        while self.current().type in (TokenType.NEWLINE, TokenType.COMMENT):
            self.advance()

    def parse_document(self) -> Document:
        """Parse a complete OCTAVE document."""
        doc = Document()
        self.skip_whitespace()

        # Check for explicit envelope
        if self.current().type == TokenType.ENVELOPE_START:
            token = self.advance()
            doc.name = token.value
            self.skip_whitespace()
        else:
            # Infer envelope for single doc
            doc.name = "INFERRED"

        # Parse META block first if present
        if self.current().type == TokenType.IDENTIFIER and self.current().value == "META":
            meta_block = self.parse_meta_block()
            doc.meta = meta_block
            self.skip_whitespace()

        # Check for separator
        if self.current().type == TokenType.SEPARATOR:
            doc.has_separator = True
            self.advance()
            self.skip_whitespace()

        # Parse document body
        while self.current().type != TokenType.ENVELOPE_END and self.current().type != TokenType.EOF:
            # Skip indentation at document level
            if self.current().type == TokenType.INDENT:
                self.advance()
                continue

            # Issue #64: Capture potential bare identifier info before parsing
            # because parse_section advances past the identifier if it's not a valid section
            potential_bare_token = self.current()
            initial_pos = self.pos

            # Parse section (assignment or block)
            section = self.parse_section(0)
            if section:
                doc.sections.append(section)
            elif self.current().type not in (TokenType.ENVELOPE_END, TokenType.EOF):
                # Issue #64: Log warning for dropped bare line instead of silent discard
                # Use the token we captured before parse_section modified position
                if potential_bare_token.type == TokenType.IDENTIFIER:
                    self.warnings.append(
                        {
                            "type": "bare_line_dropped",
                            "message": f"Line without operator dropped: '{potential_bare_token.value}'",
                            "line": potential_bare_token.line,
                            "column": potential_bare_token.column,
                            "value": str(potential_bare_token.value),
                        }
                    )
                # Consume any remaining unexpected token to prevent infinite loop
                if self.pos == initial_pos:
                    self.advance()

            self.skip_whitespace()

        # Expect END envelope (lenient - allow missing)
        if self.current().type == TokenType.ENVELOPE_END:
            self.advance()

        # Issue #64: Attach collected warnings to document
        doc.warnings = self.warnings

        return doc

    def parse_meta_block(self) -> dict[str, Any]:
        """Parse META block into dictionary."""
        meta: dict[str, Any] = {}

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
                self.advance()

                if self.current().type == TokenType.ASSIGN:
                    self.advance()
                    value = self.parse_value()
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
        annotation = None
        if self.current().type == TokenType.LIST_START:
            # Consume [ and capture content until matching ]
            bracket_depth = 1
            annotation_tokens = []
            self.advance()  # Consume [

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

            # Join tokens to create annotation string
            if annotation_tokens:
                annotation = "".join(annotation_tokens)

        self.skip_whitespace()

        # Parse section children (similar to block parsing)
        children: list[ASTNode] = []

        # Expect indentation for children
        if self.current().type == TokenType.INDENT:
            child_indent = self.current().value
            self.advance()

            # Track current line's indentation to determine if SECTION is child or sibling
            current_line_indent = child_indent

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
                    # Reset indent tracking after newline
                    current_line_indent = 0
                    continue

                # Parse child
                child = self.parse_section(child_indent)
                if child:
                    children.append(child)
                else:
                    # No valid child parsed, might be end of section
                    break

        return Section(
            section_id=section_id,
            key=section_name,
            annotation=annotation,
            children=children,
            line=section_token.line,
            column=section_token.column,
        )

    def parse_section(self, base_indent: int) -> Assignment | Block | Section | None:
        """Parse a top-level section (assignment, block, or § section)."""
        # Check for § section marker first
        if self.current().type == TokenType.SECTION:
            return self.parse_section_marker()

        if self.current().type != TokenType.IDENTIFIER:
            return None

        key = self.current().value
        self.advance()

        # Check for assignment or block
        # Lenient: allow FLOW (->) as assignment
        if self.current().type in (TokenType.ASSIGN, TokenType.FLOW):
            self.advance()
            value = self.parse_value()
            return Assignment(key=key, value=value, line=self.current().line, column=self.current().column)

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

                while True:
                    # End conditions
                    if self.current().type in (TokenType.EOF, TokenType.ENVELOPE_END):
                        break

                    # Check indentation
                    if self.current().type == TokenType.INDENT:
                        if self.current().value < child_indent:
                            break  # Dedent, end of block
                        # Same or deeper level - consume and continue to parse
                        self.advance()
                        continue

                    # Skip newlines
                    if self.current().type == TokenType.NEWLINE:
                        self.advance()
                        continue

                    # Parse child
                    child = self.parse_section(child_indent)
                    if child:
                        children.append(child)
                    else:
                        # No valid child parsed, might be end of block
                        break

            return Block(key=key, children=children, line=self.current().line, column=self.current().column)

        return None

    def parse_value(self) -> Any:
        """Parse a value (string, number, boolean, null, list)."""
        token = self.current()

        if token.type == TokenType.STRING:
            self.advance()
            return token.value

        elif token.type == TokenType.NUMBER:
            self.advance()
            return token.value

        elif token.type == TokenType.BOOLEAN:
            self.advance()
            return token.value

        elif token.type == TokenType.NULL:
            self.advance()
            return None

        elif token.type == TokenType.LIST_START:
            return self.parse_list()

        elif token.type == TokenType.IDENTIFIER:
            # Check if this starts a flow/synthesis/at/concat/tension expression
            next_token = self.peek()
            if next_token.type in (
                TokenType.FLOW,
                TokenType.SYNTHESIS,
                TokenType.AT,
                TokenType.CONCAT,
                TokenType.TENSION,  # Issue #62: Include tension operator
            ):
                # Flow expression like A→B→C, synthesis like X⊕Y, location like A@B, concat like A⧺B, or tension like A⇌B
                return self.parse_flow_expression()

            # Consume compound identifier with colons (Issue #41 Phase 2)
            # Examples: HERMES:API_TIMEOUT, MODULE:SUBMODULE:COMPONENT
            # This preserves single colons WITHIN values
            parts = [token.value]
            self.advance()

            # Collect colon-separated path components
            while self.current().type == TokenType.BLOCK and self.peek().type == TokenType.IDENTIFIER:
                # Consume BLOCK token (:)
                self.advance()
                # Consume IDENTIFIER token
                parts.append(self.current().value)
                self.advance()

            # Return compound path if multiple parts, else single value
            if len(parts) > 1:
                return ":".join(parts)
            return parts[0]

        elif token.type == TokenType.FLOW:
            # Flow expression starting with operator like →B→C
            return self.parse_flow_expression()

        else:
            # Try to consume as bare word
            value = str(token.value)
            self.advance()
            return value

    def parse_list(self) -> ListValue:
        """Parse list [a, b, c]."""
        self.expect(TokenType.LIST_START)
        items: list[Any] = []

        # Parse list items
        while True:
            # Skip whitespace/newlines/indents (valid anywhere between items)
            while self.current().type in (TokenType.NEWLINE, TokenType.INDENT):
                self.advance()

            # Check for end of list
            if self.current().type == TokenType.LIST_END:
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
                pass

        self.expect(TokenType.LIST_END)
        return ListValue(items=items)

    def parse_list_item(self) -> Any:
        """Parse a single list item."""
        # Check for inline map [k::v, k2::v2]
        if self.current().type == TokenType.IDENTIFIER and self.peek().type == TokenType.ASSIGN:
            # Inline map item
            pairs: dict[str, Any] = {}
            key = self.current().value
            self.advance()
            self.expect(TokenType.ASSIGN)
            value = self.parse_value()
            pairs[key] = value
            return InlineMap(pairs=pairs)

        # Regular value
        return self.parse_value()

    def parse_flow_expression(self) -> str:
        """Parse flow/synthesis/at/concat/tension expression like A→B→C, X⊕Y, A@B, A⧺B, or A⇌B.

        Issue #62: Added TENSION to expression operators to prevent truncation.
        """
        parts = []

        # Collect all parts of flow/synthesis/at/concat/tension expression
        while self.current().type in (
            TokenType.IDENTIFIER,
            TokenType.FLOW,
            TokenType.SYNTHESIS,
            TokenType.AT,
            TokenType.CONCAT,
            TokenType.TENSION,  # Issue #62: Include tension operator
            TokenType.STRING,
        ):
            if self.current().type in (
                TokenType.FLOW,
                TokenType.SYNTHESIS,
                TokenType.AT,
                TokenType.CONCAT,
                TokenType.TENSION,  # Issue #62: Include tension operator
            ):
                parts.append(self.current().value)
                self.advance()
            elif self.current().type in (TokenType.IDENTIFIER, TokenType.STRING):
                parts.append(self.current().value)
                self.advance()
            else:
                break

        return "".join(str(p) for p in parts)


def parse(content: str | list[Token]) -> Document:
    """Parse OCTAVE content into AST.

    Args:
        content: Raw OCTAVE text (lenient or canonical) or list of tokens

    Returns:
        Document AST

    Raises:
        ParserError: On syntax errors
    """
    if isinstance(content, str):
        tokens, _ = tokenize(content)
    else:
        tokens = content

    parser = Parser(tokens)
    return parser.parse_document()
