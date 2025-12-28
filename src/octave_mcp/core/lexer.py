"""OCTAVE lexer with ASCII normalization.

Implements P1.2: lenient_lexer_with_ascii_normalization

Token types and normalization logic for OCTAVE syntax.
Handles ASCII aliases (→/->, ⊕/+, etc.) with deterministic normalization.
"""

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any


class TokenType(Enum):
    """OCTAVE token types."""

    # Structural operators
    ASSIGN = auto()  # ::
    BLOCK = auto()  # :

    # Expression operators (by precedence)
    LIST_START = auto()  # [
    LIST_END = auto()  # ]
    CONCAT = auto()  # ⧺ or ~
    AT = auto()  # @ (location/context)
    SYNTHESIS = auto()  # ⊕ or +
    TENSION = auto()  # ⇌ or vs
    CONSTRAINT = auto()  # ∧ or &
    ALTERNATIVE = auto()  # ∨ or |
    FLOW = auto()  # → or ->

    # Special
    SECTION = auto()  # § or #
    COMMENT = auto()  # //

    # Envelope
    ENVELOPE_START = auto()  # ===NAME===
    ENVELOPE_END = auto()  # ===END===

    # Literals
    STRING = auto()  # "quoted" or bare_word
    NUMBER = auto()  # 42, 3.14, -1e10
    BOOLEAN = auto()  # true, false
    NULL = auto()  # null
    IDENTIFIER = auto()  # bare words

    # Structural
    COMMA = auto()  # ,
    NEWLINE = auto()  # \n
    INDENT = auto()  # leading spaces
    SEPARATOR = auto()  # ---
    EOF = auto()  # end of input


@dataclass
class Token:
    """OCTAVE token with position and normalization info."""

    type: TokenType
    value: Any
    line: int
    column: int
    normalized_from: str | None = None  # Original ASCII alias if normalized
    raw: str | None = None  # Original lexeme text (for NUMBER tokens)


class LexerError(Exception):
    """Lexer error with position information."""

    def __init__(self, message: str, line: int, column: int, error_code: str = "E005"):
        self.message = message
        self.line = line
        self.column = column
        self.error_code = error_code
        super().__init__(f"{error_code} at line {line}, column {column}: {message}")


# ASCII to Unicode normalization table
ASCII_ALIASES = {
    "->": "→",
    "<->": "⇌",  # GH#65: ASCII tension operator
    "+": "⊕",
    "~": "⧺",
    "vs": "⇌",
    "|": "∨",
    "&": "∧",
    "#": "§",
}

# Token patterns (order matters for longest match)
TOKEN_PATTERNS = [
    # Envelope markers (must come before SEPARATOR)
    # ENVELOPE_END must come before ENVELOPE_START to match first
    (r"===END===", TokenType.ENVELOPE_END),
    (r"===([A-Z_][A-Z0-9_]*)===", TokenType.ENVELOPE_START),
    # Separator
    (r"---", TokenType.SEPARATOR),
    # Comments (must come before operators)
    (r"//[^\n]*", TokenType.COMMENT),
    # Operators (longest match first)
    (r"::", TokenType.ASSIGN),
    (r":", TokenType.BLOCK),
    (r"→", TokenType.FLOW),
    (r"<->", TokenType.TENSION),  # GH#65: ASCII tension (must come before ->)
    (r"->", TokenType.FLOW),
    (r"⊕", TokenType.SYNTHESIS),
    # Note: + handled specially to distinguish from numbers
    (r"⧺", TokenType.CONCAT),
    (r"~", TokenType.CONCAT),
    (r"@", TokenType.AT),
    (r"⇌", TokenType.TENSION),
    (r"\bvs\b", TokenType.TENSION),  # Word boundaries required
    (r"∨", TokenType.ALTERNATIVE),
    (r"\|", TokenType.ALTERNATIVE),
    (r"∧", TokenType.CONSTRAINT),
    (r"&", TokenType.CONSTRAINT),
    (r"§", TokenType.SECTION),
    # Brackets
    (r"\[", TokenType.LIST_START),
    (r"\]", TokenType.LIST_END),
    (r",", TokenType.COMMA),
    # Quoted strings (with escape handling)
    # GH#63: Triple quotes MUST come before single quotes (longest match first)
    # Triple-quoted strings can contain newlines and internal quotes
    (r'"""(?:[^"\\]|\\.|"(?!""))*"""', TokenType.STRING),
    (r'"(?:[^"\\]|\\.)*"', TokenType.STRING),
    # Numbers (including negative and scientific notation)
    (r"-?\d+\.?\d*(?:[eE][+-]?\d+)?", TokenType.NUMBER),
    # Boolean and null literals
    (r"\btrue\b", TokenType.BOOLEAN),
    (r"\bfalse\b", TokenType.BOOLEAN),
    (r"\bnull\b", TokenType.NULL),
    # Section marker (ASCII alias)
    (r"#", TokenType.SECTION),
    # Identifiers (bare words, allows dots and hyphens for property paths and kebab-case)
    # Hyphen allowed in identifier body, but not at start (Issue #53)
    # Pattern uses negative lookbehind to avoid consuming -> (flow operator)
    (r"[A-Za-z_][A-Za-z0-9_.-]*(?<!-)", TokenType.IDENTIFIER),
    # Newlines
    (r"\n", TokenType.NEWLINE),
]


def tokenize(content: str) -> tuple[list[Token], list[Any]]:
    """Tokenize OCTAVE content with ASCII alias normalization.

    Args:
        content: Raw OCTAVE text

    Returns:
        Tuple of (tokens, repairs)

    Raises:
        LexerError: On invalid syntax (tabs, malformed operators)
    """
    # Apply NFC unicode normalization
    content = unicodedata.normalize("NFC", content)

    # ... (existing checks)

    # Check for tabs
    if "\t" in content:
        line = content[: content.index("\t")].count("\n") + 1
        column = len(content[: content.index("\t")].split("\n")[-1]) + 1
        raise LexerError("Tabs are not allowed. Use 2 spaces for indentation.", line, column, "E005")

    tokens: list[Token] = []
    repairs: list[Any] = []
    line = 1
    column = 1
    pos = 0

    # Compile all patterns
    compiled_patterns = [(re.compile(pattern), token_type) for pattern, token_type in TOKEN_PATTERNS]

    while pos < len(content):
        # ... (whitespace handling)
        # Track whitespace (spaces only, not newlines)
        if content[pos] == " ":
            # Count leading spaces for indentation
            if column == 1:  # Start of line
                space_count = 0
                while pos < len(content) and content[pos] == " ":
                    space_count += 1
                    pos += 1
                if space_count > 0 and pos < len(content) and content[pos] != "\n":
                    # Only emit INDENT if followed by non-newline
                    tokens.append(Token(TokenType.INDENT, space_count, line, column))
                    column += space_count
                continue
            else:
                # Skip inline spaces
                pos += 1
                column += 1
                continue

        # Try to match token patterns
        matched = False
        for pattern, token_type in compiled_patterns:
            match = pattern.match(content, pos)
            if match:
                matched_text = match.group()
                normalized_from = None
                raw_lexeme = None  # GH#66: Preserve raw lexeme for NUMBER tokens

                # ... (value extraction logic)
                # Handle special tokens
                if token_type == TokenType.ENVELOPE_START:
                    value = match.group(1)  # Extract NAME from ===NAME===
                elif token_type == TokenType.ENVELOPE_END:
                    value = "END"
                elif token_type == TokenType.STRING:
                    # GH#63: Handle triple quotes vs single quotes
                    # I4 Audit Trail: Record triple quote normalization
                    if matched_text.startswith('"""'):
                        # Triple-quoted string: remove """ from both ends
                        value = matched_text[3:-3]
                        # I4: Record triple quote to single quote normalization
                        normalized_from = '"""'
                    else:
                        # Single-quoted string: remove " from both ends
                        value = matched_text[1:-1]
                    # Process escape sequences
                    value = value.replace(r"\"", '"')
                    value = value.replace(r"\\", "\\")
                    value = value.replace(r"\n", "\n")
                    value = value.replace(r"\t", "\t")
                elif token_type == TokenType.NUMBER:
                    # Convert to int or float, but preserve raw lexeme for fidelity (GH#66)
                    if "." in matched_text or "e" in matched_text.lower():
                        value = float(matched_text)
                    else:
                        value = int(matched_text)
                    # Store raw lexeme for multi-word value reconstruction
                    raw_lexeme = matched_text
                elif token_type == TokenType.BOOLEAN:
                    value = matched_text == "true"
                elif token_type == TokenType.NULL:
                    value = None
                elif token_type == TokenType.COMMENT:
                    value = matched_text[2:].strip()  # Remove // and strip
                elif token_type == TokenType.NEWLINE:
                    value = "\n"
                else:
                    value = matched_text

                # Check for ASCII alias normalization
                if matched_text in ASCII_ALIASES:
                    normalized_from = matched_text
                    value = ASCII_ALIASES[matched_text]

                # Special handling for operators that need normalization
                if token_type in (
                    TokenType.FLOW,
                    TokenType.SYNTHESIS,
                    TokenType.CONCAT,
                    TokenType.TENSION,
                    TokenType.ALTERNATIVE,
                    TokenType.CONSTRAINT,
                    TokenType.SECTION,
                ):
                    if matched_text in ASCII_ALIASES:
                        normalized_from = matched_text
                        value = ASCII_ALIASES[matched_text]

                token = Token(token_type, value, line, column, normalized_from, raw_lexeme)
                tokens.append(token)

                if normalized_from:
                    repairs.append(
                        {
                            "type": "normalization",
                            "original": normalized_from,
                            "normalized": value,
                            "line": line,
                            "column": column,
                        }
                    )

                # Update position - count embedded newlines in matched text
                newline_count = matched_text.count("\n")
                if newline_count > 0:
                    # Token contains newlines (e.g., triple-quoted strings)
                    line += newline_count
                    # Column is position after last newline
                    last_newline_pos = matched_text.rfind("\n")
                    column = len(matched_text) - last_newline_pos
                else:
                    column += len(matched_text)
                pos = match.end()
                matched = True
                break

        if not matched:
            # Handle special case: + operator (need to distinguish from number)
            if content[pos] == "+":
                # Look ahead - is this part of a number or an operator?
                if pos + 1 < len(content) and content[pos + 1].isdigit():
                    # Part of number - this will be caught by number pattern
                    # But we're here, so it wasn't matched - treat as synthesis
                    pass
                # Treat as synthesis operator
                tokens.append(Token(TokenType.SYNTHESIS, "⊕", line, column, "+"))
                repairs.append(
                    {"type": "normalization", "original": "+", "normalized": "⊕", "line": line, "column": column}
                )
                column += 1
                pos += 1
                continue

            # Unrecognized character
            raise LexerError(f"Unexpected character: '{content[pos]}'", line, column, "E005")

    # Add EOF token
    tokens.append(Token(TokenType.EOF, None, line, column))

    return tokens, repairs
