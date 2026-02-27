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

    # Grammar sentinel (Issue #48 Phase 2)
    GRAMMAR_SENTINEL = auto()  # OCTAVE::VERSION at document start

    # Version field (Issues #140 #141)
    VERSION = auto()  # VERSION::1.0.0 semantic version strings

    # Variable reference (Issue #181)
    VARIABLE = auto()  # $VAR, $1:name placeholders

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

    # Literal zone tokens (Issue #235)
    FENCE_OPEN = auto()  # Opening ``` with optional info tag
    FENCE_CLOSE = auto()  # Closing ```
    LITERAL_CONTENT = auto()  # Raw content between fences


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


# Critical-Engineer: consulted for Parser contract integrity (VERSION field + sentinel scoping)

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

# GH#184: Wrong case patterns for boolean/null (spec §6::NEVER)
# These match case-insensitive versions that are NOT the correct lowercase form
WRONG_CASE_PATTERNS = {
    "True": "true",
    "TRUE": "true",
    "False": "false",
    "FALSE": "false",
    "Null": "null",
    "NULL": "null",
}

# GH#186: Unicode characters that are OCTAVE operators (must NOT be identifiers)
# These are matched by their own patterns before identifier pattern
OPERATOR_CHARS = frozenset(
    {
        "→",  # FLOW (U+2192)
        "⊕",  # SYNTHESIS (U+2295)
        "⧺",  # CONCAT (U+29FA)
        "⇌",  # TENSION (U+21CC)
        "∧",  # CONSTRAINT (U+2227)
        "∨",  # ALTERNATIVE (U+2228)
        "§",  # SECTION (U+00A7)
    }
)

# Matches 3+ backticks at line start (with optional 0-3 spaces indent)
# Captures: (1) indent, (2) full fence+info, (3) the backtick sequence, (4) info tag
FENCE_PATTERN = re.compile(r"^( {0,3})((`{3,})([^\n`]*)?)$")

# Detects inline fence syntax: KEY::```info_tag (fence on same line as key)
# This is invalid OCTAVE -- the fence must start on the line AFTER the key
_INLINE_FENCE_PATTERN = re.compile(r"^.*::(`{3,})")


def _evaluate_fence_line(
    backtick_seq: str,
    open_fence_marker: str,
    trailing_content: str,
    line: int,
    column: int,
    open_line: int,
) -> str:
    """Evaluate a backtick sequence found at line start inside an open fence.

    Returns: "close" or "content", or raises LexerError for E007.

    PRECEDENCE ORDER (B0-B1 amendment):
      1. Closing fence (exact match, no trailing content) -- checked FIRST
      2. Nested fence error (equal-or-greater length)     -- checked SECOND
      3. Content (shorter length)                         -- fallthrough
    """
    seq_len = len(backtick_seq)
    open_len = len(open_fence_marker)

    # CASE 1: Exact match with clean line -> CLOSE
    if seq_len == open_len and not trailing_content.strip():
        return "close"

    # CASE 2: Equal length with trailing content -> ERROR (ambiguous)
    # CASE 3: Greater length -> ERROR (nested fence)
    if seq_len >= open_len:
        raise LexerError(
            f"E007_NESTED_FENCE: Nested literal zone detected at line {line}. "
            f"Found fence '{backtick_seq}' (length {seq_len}) "
            f"inside literal zone opened with '{open_fence_marker}' "
            f"(length {open_len}) at line {open_line}. "
            f"Use a longer fence to wrap content containing shorter fences, "
            f"e.g., {'`' * (open_len + 1)} to wrap content with {open_fence_marker}.",
            line,
            column,
            "E007",
        )

    # CASE 4: Shorter fence -> treat as content
    return "content"


def _normalize_with_fence_detection(
    content: str,
) -> tuple[str, list[tuple[int, int, str, str | None]]]:
    """Single-pass fence detection with selective NFC normalization.

    Processes content line-by-line. When outside a fence, each line is
    NFC-normalized before appending to the output buffer. When inside a
    fence, lines are appended verbatim (no NFC). Fence span offsets are
    recorded against the OUTPUT buffer, so they are always valid for the
    returned string.

    Args:
        content: Raw (non-NFC-normalized) content string.

    Returns:
        Tuple of:
        - normalized_content: String with NFC applied outside fences,
          literal zone content preserved exactly.
        - fence_spans: List of (start_offset, end_offset, fence_marker,
          info_tag) tuples. Offsets are valid for normalized_content.

    Raises:
        LexerError: E006 if a fence is opened but never closed.
        LexerError: E007 (subtype E007_NESTED_FENCE) if a fence of
                    equal or greater length appears inside an open fence.
    """
    lines = content.split("\n")
    output_parts: list[str] = []
    fence_spans: list[tuple[int, int, str, str | None]] = []
    output_offset = 0
    in_fence = False
    current_fence_marker: str | None = None
    current_info_tag: str | None = None
    open_line = -1
    span_start = -1

    for line_num, line in enumerate(lines, start=1):
        match = FENCE_PATTERN.match(line)

        if match and not in_fence:
            # Opening fence: start literal zone
            backtick_seq = match.group(3)
            raw_tag = match.group(4).strip()
            current_info_tag = raw_tag if raw_tag else None
            in_fence = True
            current_fence_marker = backtick_seq
            open_line = line_num
            # NFC-normalize the fence line itself (it's structural, not content)
            normalized_line = unicodedata.normalize("NFC", line)
            output_parts.append(normalized_line)
            span_start = output_offset
            output_offset += len(normalized_line) + 1  # +1 for newline

        elif match and in_fence:
            backtick_seq = match.group(3)
            trailing = match.group(4)
            # Use precedence table from section 5.3.1
            if current_fence_marker is None:
                raise LexerError(
                    "E006: Internal error: fence marker is None inside open fence.",
                    line_num,
                    1,
                    "E006",
                )
            result = _evaluate_fence_line(
                backtick_seq,
                current_fence_marker,
                trailing,
                line_num,
                1,
                open_line,
            )
            if result == "close":
                # NFC-normalize the closing fence line (structural)
                normalized_line = unicodedata.normalize("NFC", line)
                output_parts.append(normalized_line)
                output_offset += len(normalized_line) + 1
                fence_spans.append(
                    (
                        span_start,
                        output_offset - 1,
                        current_fence_marker,
                        current_info_tag,
                    )
                )
                in_fence = False
                current_fence_marker = None
                current_info_tag = None
            else:  # "content"
                # Shorter fence inside literal zone: preserve verbatim
                output_parts.append(line)
                output_offset += len(line) + 1

        elif in_fence:
            # Inside literal zone: preserve verbatim (NO NFC)
            output_parts.append(line)
            output_offset += len(line) + 1

        else:
            # Outside literal zone: apply NFC normalization
            normalized_line = unicodedata.normalize("NFC", line)
            output_parts.append(normalized_line)
            output_offset += len(normalized_line) + 1

    if in_fence:
        # Check if any line before the detected fence opening has an inline fence
        # (KEY::``` on same line) -- a common mistake that produces a misleading E006
        inline_hint = ""
        for check_line_num, check_line in enumerate(lines, start=1):
            if check_line_num >= open_line:
                break
            if _INLINE_FENCE_PATTERN.match(check_line):
                inline_hint = (
                    f" Hint: line {check_line_num} appears to use inline fence syntax "
                    f"({check_line.strip()!r}). Literal zones must start on the line "
                    f"AFTER the key: write 'KEY::' on one line, then '{current_fence_marker}' "
                    f"on the next."
                )
                break
        raise LexerError(
            f"E006: Unterminated literal zone. Fence '{current_fence_marker}' "
            f"opened at line {open_line} was never closed. "
            f"Add a matching closing fence: {current_fence_marker}.{inline_hint}",
            open_line,
            1,
            "E006",
        )

    return "\n".join(output_parts), fence_spans


def _is_valid_identifier_start(char: str) -> bool:
    """Check if character can start an identifier (GH#186).

    Valid identifier start characters:
    - ASCII letters (A-Za-z)
    - Underscore (_)
    - Dot (.) and slash (/) for paths
    - Unicode letters (category L*)
    - Emoji and symbols (category So - Symbol, Other)
    - Some math symbols (category Sm - Symbol, Math) that aren't operators

    Args:
        char: Single character to check

    Returns:
        True if character can start an identifier
    """
    if not char:
        return False

    # Fast path for ASCII
    if char.isascii():
        return char.isalpha() or char in "_./"

    # Exclude OCTAVE operator characters
    if char in OPERATOR_CHARS:
        return False

    # Check unicode category
    category = unicodedata.category(char)

    # Allow letters (L*), Symbol Other (So), some Math Symbols (Sm)
    # So includes: emoji, dingbats, box drawing, misc symbols
    # Sm includes: mathematical operators (we exclude OCTAVE operators above)
    # Po includes: bullet points, other punctuation used as markers
    if category.startswith("L"):  # Letter
        return True
    if category == "So":  # Symbol, Other (emoji, misc symbols)
        return True
    if category == "Sm":  # Symbol, Math (if not an operator)
        return True
    if category == "No":  # Number, Other (circled numbers, etc.)
        return True
    if category == "Sk":  # Symbol, Modifier (variation selectors, etc.)
        return True
    if category == "Po":  # Punctuation, Other (bullets, etc.)
        return True

    return False


def _is_valid_identifier_char(char: str) -> bool:
    """Check if character can appear in identifier body (GH#186).

    Valid identifier body characters include all start characters plus:
    - Digits (0-9)
    - Hyphen (-) but not at end
    - Unicode Number characters (category N*)

    Args:
        char: Single character to check

    Returns:
        True if character can appear in identifier body
    """
    if not char:
        return False

    # Fast path for ASCII
    if char.isascii():
        return char.isalnum() or char in "_./-"

    # Everything valid for start is valid for body
    if _is_valid_identifier_start(char):
        return True

    # Additionally allow unicode number categories
    category = unicodedata.category(char)
    if category.startswith("N"):  # Number (Nd, Nl, No)
        return True

    # Allow combining marks for emoji with modifiers
    if category.startswith("M"):  # Mark (Mn, Mc, Me)
        return True

    return False


def _match_curly_brace_annotation(content: str, end: int) -> tuple[int, int, int] | None:
    """Check for a curly-brace annotation pattern NAME{qualifier} at position.

    GH#263: Detects curly-brace annotation syntax that should use angle brackets.
    Called after the base identifier has been consumed up to `end`.

    Args:
        content: Full content string
        end: Position immediately after the base identifier (should point to '{')

    Returns:
        Tuple of (qualifier_start, qualifier_end, close_brace_pos) if pattern found,
        None otherwise.
    """
    if end >= len(content) or content[end] != "{":
        return None

    qualifier_start = end + 1
    # Qualifier must start with a valid identifier start char
    if qualifier_start >= len(content) or not _is_valid_identifier_start(content[qualifier_start]):
        return None

    qualifier_end = qualifier_start + 1
    # Consume remaining qualifier characters (identifier body chars)
    while qualifier_end < len(content) and _is_valid_identifier_char(content[qualifier_end]):
        qualifier_end += 1
    # Strip trailing hyphens from qualifier (same as identifier rule)
    while qualifier_end > qualifier_start + 1 and content[qualifier_end - 1] == "-":
        qualifier_end -= 1
    # Must have closing '}'
    if qualifier_end < len(content) and content[qualifier_end] == "}":
        return qualifier_start, qualifier_end, qualifier_end

    return None


def _match_unicode_identifier(
    content: str, pos: int, lenient: bool = False, repairs: list[Any] | None = None
) -> str | None:
    """Match a unicode-aware identifier starting at position (GH#186).

    Handles emoji and unicode symbols as valid identifier characters.
    Multi-codepoint emoji (ZWJ sequences, skin tones) are supported by
    consuming all valid identifier characters including combining marks.

    Issue #248: Also matches NAME<qualifier> annotation syntax (§2c).
    When a valid identifier is followed by '<', we look ahead for a
    valid qualifier (identifier chars) and closing '>'. This produces
    a single identifier token like "ATHENA<strategic_wisdom>".
    Standalone '<' or '>' outside this pattern still errors per §3b.

    GH#263: Also detects NAME{qualifier} curly-brace annotation patterns.
    In lenient mode, auto-repairs {} -> <> and logs a W_REPAIR_CANDIDATE.
    In strict mode, returns only the base identifier (caller handles E005).

    Args:
        content: Full content string
        pos: Starting position
        lenient: If True, auto-repair curly-brace annotations to angle brackets
        repairs: Mutable list to append repair records to (used in lenient mode)

    Returns:
        Matched identifier string, or None if no match
    """
    if pos >= len(content):
        return None

    # Check first character
    if not _is_valid_identifier_start(content[pos]):
        return None

    # Build identifier by consuming valid characters
    end = pos + 1
    while end < len(content) and _is_valid_identifier_char(content[end]):
        end += 1

    # Don't end with hyphen (per existing lexer behavior)
    while end > pos + 1 and content[end - 1] == "-":
        end -= 1

    if end == pos:
        return None

    # Issue #248: Check for angle bracket annotation NAME<qualifier>
    # Only match if we consumed a valid identifier AND next char is '<'
    # The qualifier must start with a valid identifier start char (not '-')
    # and be followed by valid identifier body chars, then '>'.
    # This prevents '<->' (tension operator alias) from being consumed.
    if end < len(content) and content[end] == "<":
        qualifier_start = end + 1
        # Qualifier must start with a valid identifier start char
        if qualifier_start < len(content) and _is_valid_identifier_start(content[qualifier_start]):
            qualifier_end = qualifier_start + 1
            # Consume remaining qualifier characters (identifier body chars)
            while qualifier_end < len(content) and _is_valid_identifier_char(content[qualifier_end]):
                qualifier_end += 1
            # Strip trailing hyphens from qualifier (same as identifier rule)
            while qualifier_end > qualifier_start + 1 and content[qualifier_end - 1] == "-":
                qualifier_end -= 1
            # Must have closing '>'
            if qualifier_end < len(content) and content[qualifier_end] == ">":
                # Valid NAME<qualifier> -- extend end past '>'
                end = qualifier_end + 1

    # GH#263: Check for curly-brace annotation NAME{qualifier}
    # This is a common mistake — users write {} instead of <>
    curly_match = _match_curly_brace_annotation(content, end)
    if curly_match is not None:
        qualifier_start, qualifier_end, close_brace_pos = curly_match
        base_name = content[pos:end]
        qualifier = content[qualifier_start:qualifier_end]
        original = f"{base_name}{{{qualifier}}}"
        repaired = f"{base_name}<{qualifier}>"

        if lenient and repairs is not None:
            # Auto-repair: return the identifier with angle brackets
            # and log the repair for I4 auditability
            repairs.append(
                {
                    "type": "repair_candidate",
                    "subtype": "curly_brace_annotation",
                    "original": original,
                    "repaired": repaired,
                    "line": 0,  # Will be updated by caller with actual line
                    "column": 0,  # Will be updated by caller with actual column
                    "message": (
                        f"W_REPAIR_CANDIDATE::{original} repaired to {repaired}. "
                        f"Use angle brackets <> for annotation qualifiers, not curly braces {{}}."
                    ),
                }
            )
            # Consume past the closing '}'
            end = close_brace_pos + 1
            return repaired
        # In strict mode: return only the base identifier
        # The caller will hit E005 on '{' with enhanced error message

    return content[pos:end]


# Token patterns (order matters for longest match)
TOKEN_PATTERNS = [
    # Grammar sentinel (Issue #48 Phase 2) - must come first
    # Pattern: OCTAVE::VERSION where VERSION is semver-like (e.g., 5, 5.1, 5.1.0, 5.1.0-beta.1)
    # Version regex: major(.minor(.patch)?)?(-prerelease)?
    (r"OCTAVE::(\d+(?:\.\d+)*(?:-[A-Za-z0-9.-]+)?)", TokenType.GRAMMAR_SENTINEL),
    # VERSION token patterns (Issues #140, #141)
    # Pattern ordering is critical for performance:
    # 1. VERSION patterns come BEFORE NUMBER to prevent greedy NUMBER matching
    # 2. VERSION regex uses specific anchors (\d+\.\d+) that fail fast on non-versions
    # 3. Most numeric inputs match NUMBER directly, so VERSION overhead is minimal
    # 4. Performance impact: <2% on typical documents (VERSION patterns fail quickly)
    # Semantic version pattern (must come before NUMBER to prevent partial match)
    # Matches version strings with 3+ parts OR 2 parts + suffix
    # Examples: 0.1.0, 1.2.3, 1.0-beta, 1.0-beta-1, 1.0+build
    # Excludes simple floats like 3.14 (handled by NUMBER)
    # Note: Hyphens allowed in prerelease identifiers (e.g., beta-1, rc-2)
    (r"(\d+\.\d+\.\d+(?:\.\d+)*(?:-[A-Za-z0-9.-]+)?(?:\+[A-Za-z0-9.]+)?)", TokenType.VERSION),  # 3+ parts
    (r"(\d+\.\d+(?:-[A-Za-z0-9.-]+)(?:\+[A-Za-z0-9.]+)?)", TokenType.VERSION),  # 2 parts + prerelease
    (r"(\d+\.\d+(?:\+[A-Za-z0-9.]+))", TokenType.VERSION),  # 2 parts + build
    # Envelope markers (must come before SEPARATOR)
    # ENVELOPE_END must come before ENVELOPE_START to match first
    (r"===END===", TokenType.ENVELOPE_END),
    # GH#145: Accept both upper and lowercase letters in envelope identifiers
    # Per spec §4::STRUCTURE: KEYS::[A-Z,a-z,0-9,_][start_with_letter_or_underscore]
    (r"===([A-Za-z_][A-Za-z0-9_]*)===", TokenType.ENVELOPE_START),
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
    # Variable reference (Issue #181): $VAR, $1:name, $MY_VAR123
    # Pattern: $ followed by alphanumeric, underscore, or colon
    # Colon is allowed for type hints like $1:role but stops at whitespace
    (r"\$[A-Za-z0-9_:]+", TokenType.VARIABLE),
    # GH#186: IDENTIFIER pattern removed - now handled by _match_unicode_identifier()
    # to support emoji and unicode symbols in identifiers
    # Newlines
    (r"\n", TokenType.NEWLINE),
]


# GH#145: Pattern to detect malformed envelope markers
# Matches ===...=== with any content between
_INVALID_ENVELOPE_PATTERN = re.compile(r"===([^=\n]*)===")

# Valid envelope identifier pattern (for error detection)
_VALID_ENVELOPE_ID_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _check_invalid_envelope(content: str, pos: int, line: int, column: int) -> LexerError | None:
    """Check if we're looking at an invalid envelope pattern.

    GH#145: Provides specific error messages for invalid envelope identifiers.

    Args:
        content: Full content string
        pos: Current position in content
        line: Current line number
        column: Current column number

    Returns:
        LexerError if invalid envelope detected, None otherwise
    """
    match = _INVALID_ENVELOPE_PATTERN.match(content, pos)
    if not match:
        # Not a complete ===...=== pattern
        return None

    identifier = match.group(1)

    # Check for empty identifier
    if not identifier:
        return LexerError(
            "Envelope identifier is empty. Use a valid name like ===MY_DOC=== or ===MyDoc===.",
            line,
            column,
            "E_INVALID_ENVELOPE_ID",
        )

    # Check if it's already valid (shouldn't reach here, but safety check)
    if _VALID_ENVELOPE_ID_PATTERN.match(identifier):
        return None

    # Find the first invalid character
    first_invalid_char = None
    first_invalid_pos = 0

    for i, char in enumerate(identifier):
        if i == 0:
            # First character must be letter or underscore
            if not (char.isalpha() or char == "_"):
                first_invalid_char = char
                first_invalid_pos = i
                break
        else:
            # Subsequent characters must be alphanumeric or underscore
            if not (char.isalnum() or char == "_"):
                first_invalid_char = char
                first_invalid_pos = i
                break

    if first_invalid_char is None:
        # Shouldn't happen, but safety
        return None

    # Build helpful error message based on the character
    char_desc = first_invalid_char
    if first_invalid_char == "-":
        char_desc = "hyphen '-'"
    elif first_invalid_char == " ":
        char_desc = "space"
    elif first_invalid_char.isdigit() and first_invalid_pos == 0:
        return LexerError(
            f"Envelope identifier '{identifier}' cannot start with a digit. "
            "Use a letter or underscore as the first character.",
            line,
            column,
            "E_INVALID_ENVELOPE_ID",
        )

    return LexerError(
        f"Envelope identifier '{identifier}' contains invalid character {char_desc}. "
        "Use underscores or CamelCase instead (e.g., my_document or MyDocument).",
        line,
        column,
        "E_INVALID_ENVELOPE_ID",
    )


def tokenize(content: str, lenient: bool = False) -> tuple[list[Token], list[Any]]:
    """Tokenize OCTAVE content with ASCII alias normalization.

    Args:
        content: Raw OCTAVE text
        lenient: If True, auto-repair curly-brace annotations (GH#263)

    Returns:
        Tuple of (tokens, repairs)

    Raises:
        LexerError: On invalid syntax (tabs, malformed operators, unbalanced brackets)
    """
    # Apply NFC unicode normalization with fence detection (Issue #235)
    # Replaces blanket NFC: literal zone content is preserved verbatim (D3: zero processing)
    content, fence_spans = _normalize_with_fence_detection(content)

    # Check for tabs OUTSIDE literal zones only (Issue #235: tab bypass)
    for i, char in enumerate(content):
        if char == "\t":
            # Check if this position falls within any fence span
            in_literal = any(start <= i < end for start, end, _, _ in fence_spans)
            if not in_literal:
                tab_line = content[:i].count("\n") + 1
                tab_column = len(content[:i].split("\n")[-1]) + 1
                raise LexerError(
                    "Tabs are not allowed. Use 2 spaces for indentation.",
                    tab_line,
                    tab_column,
                    "E005",
                )

    tokens: list[Token] = []
    repairs: list[Any] = []
    line = 1
    column = 1
    pos = 0

    # Issue #235: Track which fence span we are expecting next
    fence_span_idx = 0

    # Track bracket depth for unbalanced bracket detection (GH#180)
    # Stack of (bracket_char, line, column) for each opening bracket
    bracket_stack: list[tuple[str, int, int]] = []

    # Compile all patterns
    compiled_patterns = [(re.compile(pattern), token_type) for pattern, token_type in TOKEN_PATTERNS]

    while pos < len(content):
        # Issue #235: Check if current position is the start of a fence span
        # Emit FENCE_OPEN, LITERAL_CONTENT, FENCE_CLOSE tokens and skip past span
        if fence_span_idx < len(fence_spans) and pos == fence_spans[fence_span_idx][0]:
            span_start, span_end, marker, tag = fence_spans[fence_span_idx]

            # Emit FENCE_OPEN token
            tokens.append(
                Token(
                    TokenType.FENCE_OPEN,
                    {"fence_marker": marker, "info_tag": tag},
                    line,
                    column,
                )
            )

            # Find content boundaries within the span
            # content_start: position after the first newline (end of opening fence line)
            # content_end: position of the last newline before closing fence line
            first_newline = content.index("\n", span_start)
            content_start = first_newline + 1

            # Find the start of the closing fence line
            # The closing fence is the last line of the span
            last_newline = content.rindex("\n", span_start, span_end)
            content_end = last_newline

            # Advance line past opening fence line's newline
            line += 1  # Move past opening fence line's newline
            column = 1

            # Extract literal content
            if content_start <= content_end:
                literal_text = content[content_start:content_end]
            else:
                # Empty literal zone (opening fence immediately followed by closing fence)
                literal_text = ""

            # Emit LITERAL_CONTENT token (line is the first content line)
            content_line = line
            tokens.append(Token(TokenType.LITERAL_CONTENT, literal_text, content_line, 1))

            # Advance line tracking past content lines.
            # Count newlines in the span to determine how many content lines exist.
            # lines_in_span includes the opening fence newline + content newlines.
            # content_line_count = lines_in_span - 1 (subtract opening fence line).
            lines_in_span = content[span_start:span_end].count("\n")
            content_line_count = lines_in_span - 1
            line += content_line_count

            # Emit FENCE_CLOSE token
            close_line = line
            # Find the indent of the closing fence line
            close_fence_start = last_newline + 1
            close_column = 1
            tokens.append(Token(TokenType.FENCE_CLOSE, marker, close_line, close_column))

            # Advance past the span
            # Count the closing fence line's newline in line tracking
            closing_fence_text = content[close_fence_start:span_end]
            # Move pos past the entire span
            pos = span_end
            # Update line to be past the closing fence
            line = close_line + 1
            column = 1

            # Handle the case where the span ends at the boundary
            # pos should be at span_end, which is after closing fence line content
            # but before the newline that follows
            if pos < len(content) and content[pos] == "\n":
                # Emit NEWLINE token for the line break after closing fence
                tokens.append(Token(TokenType.NEWLINE, "\n", close_line, len(closing_fence_text) + 1))
                pos += 1

            fence_span_idx += 1
            continue

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
            # GRAMMAR_SENTINEL must only match at document start (position 0)
            # to prevent silent data loss in nested assignments like NOTE::OCTAVE::5.1.0
            if token_type == TokenType.GRAMMAR_SENTINEL and pos != 0:
                continue  # Skip GRAMMAR_SENTINEL pattern if not at position 0

            match = pattern.match(content, pos)
            if match:
                matched_text = match.group()
                normalized_from = None
                raw_lexeme = None  # GH#66: Preserve raw lexeme for NUMBER tokens

                # ... (value extraction logic)
                # Handle special tokens
                if token_type == TokenType.GRAMMAR_SENTINEL:
                    # Issue #48 Phase 2: Extract version string from OCTAVE::VERSION
                    value = match.group(1)  # Extract VERSION from OCTAVE::VERSION
                elif token_type == TokenType.VERSION:
                    # Issues #140 #141: Extract version string from VERSION::1.0.0
                    value = match.group(1)  # Extract version value (quoted or bare)
                elif token_type == TokenType.ENVELOPE_START:
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

                # GH#184: Check for wrong-case boolean/null patterns (spec §6::NEVER)
                # Emit spec_violation warning for True, False, TRUE, FALSE, Null, NULL
                if token_type == TokenType.IDENTIFIER and matched_text in WRONG_CASE_PATTERNS:
                    correct_form = WRONG_CASE_PATTERNS[matched_text]
                    repairs.append(
                        {
                            "type": "spec_violation",
                            "subtype": "wrong_case",
                            "original": matched_text,
                            "correct": correct_form,
                            "line": line,
                            "column": column,
                            "message": (
                                f"W_WRONG_CASE::{matched_text} should be {correct_form}. "
                                f"OCTAVE spec requires lowercase for boolean and null literals."
                            ),
                        }
                    )

                # GH#184: Check for 'vs' without word boundaries (spec §6::NEVER)
                # Detect patterns like "SpeedvsQuality" where 'vs' lacks boundaries
                if token_type == TokenType.IDENTIFIER and "vs" in matched_text.lower():
                    # Find 'vs' (case-insensitive) and check if it has proper boundaries
                    lower_text = matched_text.lower()
                    vs_pos = lower_text.find("vs")
                    if vs_pos != -1:
                        # Check if 'vs' is at boundaries or has non-alphanumeric neighbors
                        has_left_boundary = vs_pos == 0
                        has_right_boundary = vs_pos + 2 >= len(matched_text)
                        if not has_left_boundary and not has_right_boundary:
                            # 'vs' is embedded within identifier without boundaries
                            repairs.append(
                                {
                                    "type": "spec_violation",
                                    "subtype": "boundary_missing",
                                    "original": matched_text,
                                    "line": line,
                                    "column": column,
                                    "message": (
                                        f"W_BOUNDARY_MISSING::'{matched_text}' contains 'vs' without "
                                        f"word boundaries. Use 'Speed vs Quality' (with spaces) or "
                                        f"bracket syntax [Speed vs Quality]."
                                    ),
                                }
                            )

                # Track bracket balance (GH#180)
                if token_type == TokenType.LIST_START:
                    bracket_stack.append(("[", line, column))
                elif token_type == TokenType.LIST_END:
                    if not bracket_stack:
                        raise LexerError(
                            f"closing ']' at line {line}, column {column} has no matching '['",
                            line,
                            column,
                            "E_UNBALANCED_BRACKET",
                        )
                    bracket_stack.pop()

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
            # GH#145: Check for invalid envelope identifier patterns
            # Detect ===...=== that didn't match the valid envelope pattern
            if content[pos : pos + 3] == "===":
                error = _check_invalid_envelope(content, pos, line, column)
                if error:
                    raise error

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

            # GH#186: Try unicode identifier matching for emoji and symbols
            # GH#263: Pass lenient flag for curly-brace annotation auto-repair
            unicode_id = _match_unicode_identifier(content, pos, lenient=lenient, repairs=repairs)
            if unicode_id:
                # GH#263: Update line/column on any repair_candidate entries
                # that were just appended by _match_unicode_identifier
                for r in repairs:
                    if r.get("type") == "repair_candidate" and r.get("line") == 0 and r.get("column") == 0:
                        r["line"] = line
                        r["column"] = column

                token = Token(TokenType.IDENTIFIER, unicode_id, line, column)
                tokens.append(token)

                # GH#184: Check for wrong-case boolean/null patterns
                if unicode_id in WRONG_CASE_PATTERNS:
                    correct_form = WRONG_CASE_PATTERNS[unicode_id]
                    repairs.append(
                        {
                            "type": "spec_violation",
                            "subtype": "wrong_case",
                            "original": unicode_id,
                            "correct": correct_form,
                            "line": line,
                            "column": column,
                            "message": (
                                f"W_WRONG_CASE::{unicode_id} should be {correct_form}. "
                                f"OCTAVE spec requires lowercase for boolean and null literals."
                            ),
                        }
                    )

                # GH#184: Check for 'vs' without word boundaries (spec NEVER)
                if "vs" in unicode_id.lower():
                    lower_text = unicode_id.lower()
                    vs_pos = lower_text.find("vs")
                    if vs_pos != -1:
                        has_left_boundary = vs_pos == 0
                        has_right_boundary = vs_pos + 2 >= len(unicode_id)
                        if not has_left_boundary and not has_right_boundary:
                            repairs.append(
                                {
                                    "type": "spec_violation",
                                    "subtype": "boundary_missing",
                                    "original": unicode_id,
                                    "line": line,
                                    "column": column,
                                    "message": (
                                        f"W_BOUNDARY_MISSING::'{unicode_id}' contains 'vs' without "
                                        f"word boundaries. Use 'Speed vs Quality' (with spaces) or "
                                        f"bracket syntax [Speed vs Quality]."
                                    ),
                                }
                            )

                # Update position - count characters, not bytes
                column += len(unicode_id)
                pos += len(unicode_id)
                continue

            # GH#263: Enhanced error for curly-brace annotation pattern
            # Detect '{' after an identifier and provide W_REPAIR_CANDIDATE hint
            if content[pos] == "{" and tokens and tokens[-1].type == TokenType.IDENTIFIER:
                prev_name = tokens[-1].value
                # Try to match the curly-brace annotation pattern
                curly_match = _match_curly_brace_annotation(content, pos)
                if curly_match is not None:
                    qualifier_start, qualifier_end, close_brace_pos = curly_match
                    qualifier = content[qualifier_start:qualifier_end]
                    original = f"{prev_name}{{{qualifier}}}"
                    suggested = f"{prev_name}<{qualifier}>"
                    raise LexerError(
                        f"Unexpected character: '{{'. "
                        f"W_REPAIR_CANDIDATE::{original} should be {suggested}. "
                        f"Use angle brackets <> for annotation qualifiers, not curly braces {{}}.",
                        line,
                        column,
                        "E005",
                    )

            # GH#287 P1: Accept % in values when immediately preceded by alphanumeric
            # e.g. 60%, 100%_complete — but standalone % or prefix %foo still E005
            # ADR-0005 Decision 3: % is only valid in VALUE contexts, not in keys.
            # If % is immediately followed by :: the previous token is a key and
            # merging would produce a grammar-boundary bypass (CE #292 Finding 2).
            if (
                content[pos] == "%"
                and tokens
                and tokens[-1].type
                in (
                    TokenType.NUMBER,
                    TokenType.IDENTIFIER,
                )
                and not content[pos + 1 : pos + 3] == "::"
            ):
                prev_val = str(tokens[-1].value if tokens[-1].raw is None else tokens[-1].raw)
                if prev_val and prev_val[-1:].isalnum():
                    # Merge % into previous token, consuming any trailing identifier chars
                    suffix = "%"
                    suffix_pos = pos + 1
                    while suffix_pos < len(content) and _is_valid_identifier_char(content[suffix_pos]):
                        # Terminate on operator chars (GH#287: 60%→ = two tokens)
                        if content[suffix_pos] in OPERATOR_CHARS:
                            break
                        suffix += content[suffix_pos]
                        suffix_pos += 1
                    # Strip trailing hyphens (per identifier rule)
                    while len(suffix) > 1 and suffix[-1] == "-":
                        suffix = suffix[:-1]
                        suffix_pos -= 1
                    # Merge into previous token as IDENTIFIER
                    merged_value = prev_val + suffix
                    prev_token = tokens[-1]
                    tokens[-1] = Token(
                        TokenType.IDENTIFIER,
                        merged_value,
                        prev_token.line,
                        prev_token.column,
                        prev_token.normalized_from,
                        None,
                    )
                    advance = suffix_pos - pos
                    column += advance
                    pos = suffix_pos
                    continue

            # Unrecognized character
            raise LexerError(f"Unexpected character: '{content[pos]}'", line, column, "E005")

    # Check for unclosed brackets at end of input (GH#180)
    if bracket_stack:
        # Report the first unclosed bracket
        bracket_char, bracket_line, bracket_column = bracket_stack[0]
        raise LexerError(
            f"opening '{bracket_char}' at line {bracket_line}, column {bracket_column} has no matching ']'",
            bracket_line,
            bracket_column,
            "E_UNBALANCED_BRACKET",
        )

    # Add EOF token
    tokens.append(Token(TokenType.EOF, None, line, column))

    return tokens, repairs
