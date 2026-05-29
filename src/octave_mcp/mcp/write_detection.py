"""Pure-text detection helpers and W-code warning emitters.

Extracted from write.py as part of STRATEGY_S1 (#459/#463).

This module contains CLUSTER_A: pure-text detection helpers used by
``WriteTool`` for lenient-parsing auto-quoting, annotation-too-long
detection, snake-case blob detection, and literal-zone / holographic
line-set construction.

No behaviour change: functions and constants were moved verbatim from
``octave_mcp.mcp.write``.
"""

import re
from typing import Any

# Quoting guidance warning
W_UNQUOTED_SECTION_IN_VALUE = "W_UNQUOTED_SECTION_IN_VALUE"
# GH#403: Annotation content discipline warning.
# Fires (non-blocking) when annotation identifier content (the qualifier
# inside <>) exceeds the discipline threshold: len > 32 chars OR
# underscore-token count >= 5.  Content at this size is snake_case prose
# masquerading as an identifier qualifier — it belongs in a sibling
# RATIONALE field with quoted prose.  Routed to corrections (repair_log),
# NOT to errors — it is advisory, not a validation failure.
W_ANNOTATION_TOO_LONG = "W_ANNOTATION_TOO_LONG"

# Threshold constants (GH#403)
_ANNOTATION_TOO_LONG_CHAR_LIMIT = 32
_ANNOTATION_TOO_LONG_TOKEN_LIMIT = 5  # >= 5 underscore-delimited tokens

# GH#452: Snake-case prose blob discipline warning.
# Fires (non-blocking, advisory) when a value (or list-element) appearing in
# the position of a reasoning field carries a snake_case prose token that
# matches the bulk OR semantic trigger.  The canonical name for the pattern
# the validator is steering authors away from is ``TELEGRAPHIC_PHRASE``
# (primer landed in #453 / PR #455) — short prose belongs in a quoted
# RATIONALE/NOTE, not in an identifier-shaped snake_case blob.
#
# v1 severity: ADVISORY only (warnings[]). v2 blocking semantics ship ~30
# days later as a separate PR.
W_SNAKE_CASE_BLOB = "W_SNAKE_CASE_BLOB"

# 18 reasoning fields per refined contract (operator comment 4549996376):
# value (or list-element) in the position of one of these KEYs is checked.
_W_SNAKE_CASE_BLOB_REASONING_FIELDS: frozenset[str] = frozenset(
    {
        "DECISION",
        "BECAUSE",
        "RATIONALE",
        "RETAINS",
        "GUIDANCE",
        "WHY",
        "NOTE",
        "PRINCIPLE",
        "ESCAPE_HATCH",
        "CONTEXT",
        "EVIDENCE",
        "OBSERVATION",
        "FINDING",
        "CONSEQUENCES",
        "TRADEOFFS",
        "NEXT_STEPS",
        "CAVEAT",
        "ASSUMPTION",
    }
)

# Content triggers
_W_SNAKE_CASE_BLOB_BULK_CHAR_LIMIT = 40  # length > 40
_W_SNAKE_CASE_BLOB_BULK_UNDERSCORE_LIMIT = 4  # underscores >= 4
_W_SNAKE_CASE_BLOB_SEMANTIC_STOPWORD_LIMIT = 2  # stopword_count >= 2

# Semantic stopwords (lowercased, compared case-insensitively against
# underscore-delimited tokens of the candidate token).
_W_SNAKE_CASE_BLOB_STOPWORDS: frozenset[str] = frozenset(
    {
        "and",
        "or",
        "of",
        "to",
        "the",
        "with",
        "is",
        "are",
        "via",
        "for",
        "from",
        "at",
        "by",
        "on",
        "in",
        "into",
        "when",
        "if",
        "not",
        "no",
        "plus",
        "as",
        "then",
    }
)

# Exclusion regex: ALL-CAPS short idiom (first char A-Z, then up to 15 more
# A-Z/0-9/_). Matches SUPERSEDED_BY, NEXT_ACTIONS, etc.
_W_SNAKE_CASE_BLOB_ALLCAPS_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,15}$")

# A candidate token in value position is matched by this regex. We deliberately
# require at least one underscore in the token body so we never have to scan
# bare words — the zero-underscore exclusion would drop them anyway. The start
# character class permits digits so empirical offenders like
# ``5_to_10_active_projects`` are matched verbatim, not truncated to
# ``to_10_active_projects`` (CRS PR #456 finding 2, comment 4550471154).
# Tokens may contain letters, digits, underscores, hyphens, and dots; the
# hyphen/dot exclusions are applied after extraction.
_W_SNAKE_CASE_BLOB_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_./\-]*_[A-Za-z0-9_./\-]*")

# A reasoning-field assignment opener: ``  KEY::``  (with optional indent).
# Capture group 1 is the KEY. No ``re.MULTILINE``: the scanner walks lines
# explicitly and calls ``match(raw_line)`` per line (CRS PR #456 finding 3).
_W_SNAKE_CASE_BLOB_OPENER_RE = re.compile(r"^[ \t]*([A-Z][A-Z0-9_]*)\s*:\s*:")

# Standalone reasoning-field block header: ``KEY:[`` opening a children block.
# Capture group 1 is the KEY. The opening ``[`` is required (not optional)
# because the call site only acts when it is present; making it mandatory at
# the regex level eliminates the redundant group-check (CRS PR #456 finding 3).
# No ``re.MULTILINE`` for the same reason as the opener above.
_W_SNAKE_CASE_BLOB_BLOCK_OPEN_RE = re.compile(r"^[ \t]*([A-Z][A-Z0-9_]*)\s*:\s*\[")

# Regex to extract annotation qualifier content (inside angle brackets).
# Matches NAME<qualifier> at word boundaries within a line; captures the
# qualifier content only.  The outer name part is not restricted here
# because is_annotation_shape already enforces the identifier grammar;
# we need a broader scan that catches multi-annotation list values.
_ANNOTATION_QUALIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.\-]*<([A-Za-z_./][A-Za-z0-9_.\-/]*)>")
# Regex: line with KEY::  followed by § somewhere in the value portion.
# Matches lines like  KEY::§2_BEHAVIOR  and  KEY::["§2_BEHAVIOR"]
# but NOT lines where § starts the line (section declarations like §1::NAME).
# GH#329: Key pattern widened to cover unicode/hyphen/slash identifiers.
# GH#329r2: Removed fragile lookahead; quoting context checked post-match
#   by _all_section_marks_quoted() to handle arrays, nested quotes, etc.
# GH#329r2: Key pattern uses \w for unicode support (e.g. clé::§2).
_UNQUOTED_SECTION_RE = re.compile(
    r"^[ \t]*[\w./][\w.\-/]*::"  # KEY:: (unicode-aware identifier grammar)
    r"[^§\n]*"  # optional non-§ chars before the §
    r"§",  # a § in value position
    re.MULTILINE,
)

# Regex for detecting literal zone (fenced code block) boundaries.
_LITERAL_ZONE_FENCE_RE = re.compile(r"^[ \t]*```", re.MULTILINE)


def _build_literal_zone_line_set(content: str) -> set[int]:
    """Build a set of 1-based line numbers that fall inside literal zones.

    Literal zones are ``` fenced blocks. Lines between (and including) the
    opening and closing fences are considered inside the zone.
    """
    inside_lines: set[int] = set()
    in_zone = False
    for line_num, line in enumerate(content.split("\n"), start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            if not in_zone:
                in_zone = True
                inside_lines.add(line_num)
            else:
                inside_lines.add(line_num)
                in_zone = False
            continue
        if in_zone:
            inside_lines.add(line_num)
    return inside_lines


def _build_holographic_line_set(content: str) -> set[int]:
    """Build a set of 1-based line numbers whose value is a holographic pattern.

    Shape F lexical sanctuary (GH-420, debate thread
    ``2026-05-14-octave-mcp-octavewrite-meta-gr-01krjzag``).

    The lenient-parsing repair pass ``_auto_quote_section_refs_in_values``
    must NOT mutate lines whose bracketed value is a holographic pattern
    of the form::

        KEY::["example"∧CONSTRAINT→§TARGET]

    or its ASCII-arrow variant ``->§TARGET``. Quoting the trailing
    ``§TARGET`` fragments the operator chain semantics and violates
    PROD::I1::SYNTACTIC_FIDELITY and PROD::I3::MIRROR_CONSTRAINT.

    Authority direction (per debate verdict, operators declared OPEN):
    recognition defers to ``octave_mcp.core.holographic``'s existing
    operator-boundary detection (``_find_constraint_start`` /
    ``_find_target_start``). The repair pass is NOT permitted to maintain
    a parallel operator catalogue — that would silently re-introduce the
    same bug whenever a new operator joins the meta-grammar.

    A line is considered holographic when, after splitting on the first
    ``::``, the value portion (stripped of any trailing line-comment)
    contains at least one bracket-enclosed value whose contents have a
    parser-recognised constraint operator (``∧``) at top level OR a
    parser-recognised target operator (``→§`` / ``->§``) at top level.

    Args:
        content: Raw OCTAVE content to scan.

    Returns:
        Set of 1-based line numbers protected by the lexical sanctuary.
    """
    # Lazy import to avoid a module-load cycle: core.holographic imports
    # core.constraints which transitively reaches lexer-adjacent modules.
    # mcp.write_detection is loaded as part of the MCP tool surface, well after
    # core.holographic, so a function-local import is safe and explicit.
    from octave_mcp.core.holographic import _find_constraint_start, _find_target_start

    protected: set[int] = set()

    for line_num, raw_line in enumerate(content.split("\n"), start=1):
        line = raw_line

        # The value follows the first ``::``. Lines without ``::`` cannot
        # carry a key::value holographic pattern in this position.
        colon_idx = line.find("::")
        if colon_idx == -1:
            continue
        value_part = line[colon_idx + 2 :]

        # Walk the value portion looking for bracket-enclosed regions.
        # ``_find_constraint_start`` / ``_find_target_start`` operate on
        # the content *inside* the outer brackets, so we extract each
        # ``[...]`` span and ask the parser whether it contains a
        # top-level holographic operator. Any single matching span is
        # sufficient to mark the line as protected.
        depth = 0
        in_quotes = False
        span_start = -1
        i = 0
        length = len(value_part)
        while i < length:
            ch = value_part[i]
            if ch == '"':
                # Backslash-run parity (matches GH#361r2 convention used in
                # ``_all_section_marks_quoted``): count the run of trailing
                # backslashes immediately before this quote. Even count
                # (including zero) means the quote is UNESCAPED and must
                # toggle ``in_quotes``; odd count means the quote is
                # escaped and must NOT toggle. A naive single-character
                # lookback misclassifies ``\\"`` (two backslashes = escaped
                # backslash pair, quote IS unescaped) as escaped, which
                # leaves the parser walk stuck inside a string and lets
                # operators in the bracketed value escape recognition
                # (cubic-dev-ai P1 on PR #431).
                backslash_count = 0
                j = i - 1
                while j >= 0 and value_part[j] == "\\":
                    backslash_count += 1
                    j -= 1
                if backslash_count % 2 == 0:
                    in_quotes = not in_quotes
            elif not in_quotes:
                if ch == "[":
                    if depth == 0:
                        span_start = i + 1
                    depth += 1
                elif ch == "]":
                    depth -= 1
                    if depth == 0 and span_start != -1:
                        span = value_part[span_start:i]
                        if _find_constraint_start(span) != -1 or _find_target_start(span) != -1:
                            protected.add(line_num)
                            break
                        span_start = -1
                elif ch == "/" and i + 1 < length and value_part[i + 1] == "/" and depth == 0:
                    # OCTAVE line comment outside any bracket span: the
                    # rest of the line is commentary, stop scanning.
                    break
            i += 1

    return protected


def _all_section_marks_quoted(line: str) -> bool:
    """Return True if every § on *line* appears inside a double-quoted string.

    Scans *line* character-by-character, toggling an ``in_quote`` flag on
    each unescaped ``"``.  Any ``§`` encountered while ``in_quote`` is False
    means at least one section mark is unquoted, so we return False.

    GH#361r1: Escaped quotes (``\\"``) do NOT toggle the ``in_quote`` state.
    GH#361r2: Backslash parity is checked by counting consecutive backslashes
    before a quote. Even count (including 0) means the quote is unescaped;
    odd count means it is escaped. This handles cases like ``\\\\"`` where
    the backslashes are themselves escaped and the quote is actually unescaped.

    When ``//`` is encountered outside quotes, scanning stops because
    everything after is an OCTAVE comment (GH#329r3).

    This is a secondary filter applied after the regex match to eliminate
    false positives from array syntax like ``KEY::["§2_BEHAVIOR"]`` where
    the § is properly quoted inside brackets.
    """
    in_quote = False
    i = 0
    length = len(line)
    while i < length:
        ch = line[i]
        if ch == '"':
            # GH#361r2: Count consecutive backslashes before this quote
            # to determine parity.  Even count (including 0) means the
            # quote is NOT escaped; odd count means it IS escaped.
            backslash_count = 0
            j = i - 1
            while j >= 0 and line[j] == "\\":
                backslash_count += 1
                j -= 1
            if backslash_count % 2 == 0:
                in_quote = not in_quote
        elif ch == "/" and i > 0 and line[i - 1] == "/" and not in_quote:
            # GH#329r3: "//" outside quotes starts a comment; stop scanning.
            return True
        elif ch == "§" and not in_quote:
            return False
        i += 1
    return True


# GH#334: Regex matching a contiguous value token that contains at least one §.
# This captures the ENTIRE token (not just the §N::NAME part) so that compound
# values like §1_through_§4 are quoted as a single unit instead of being
# fragmented into "§1_through_""§4".
# A "value token" is a contiguous run of identifier chars, §, ::, brackets, etc.
# that ends at a comma, whitespace, or end of the value.
_SECTION_REF_TOKEN_RE = re.compile(
    r"§"
    r"\w+"  # section number/name (e.g., "5", "2_BEHAVIOR")
    r"(?:::\w[\w.\-]*)*"  # optional ::NAME suffix(es)
)

# GH#334: Match the full extent of a value token containing § marks.
# Used to find the boundaries of a compound token like "§1_through_§4"
# so the entire thing can be wrapped in one pair of quotes.
_SECTION_CONTAINING_TOKEN_RE = re.compile(
    r"(?:[\w.\-]|§|::|/(?!/))+"
)  # contiguous run of identifier chars, §, ::, and single /


def _auto_quote_section_refs_in_values(content: str) -> tuple[str, list[dict[str, Any]]]:
    """GH#334: Auto-quote unquoted § references in value positions.

    When a line has KEY::...§N::NAME... where the § is not inside double quotes,
    the lexer would fragment it (§ -> SECTION token, corrupting the value).
    This function wraps such references in double quotes BEFORE parsing.

    I1 (Syntactic Fidelity): normalization alters syntax, never semantics.
    The author intended §5::ANCHOR_KERNEL as a literal string value, not a
    section declaration.  Quoting preserves that intent.

    I4 (Transform Auditability): every auto-quote is logged as a correction.

    Args:
        content: Raw OCTAVE content that may contain unquoted § in values.

    Returns:
        Tuple of (transformed_content, list of correction records).
    """
    corrections: list[dict[str, Any]] = []
    literal_zone_lines = _build_literal_zone_line_set(content)
    # Shape F sanctuary (GH-420): lines whose bracketed value is a
    # holographic pattern (e.g. ``KEY::["x"∧REQ→§TARGET]``) must NOT be
    # quoted. The recognition defers to ``core.holographic``; see
    # ``_build_holographic_line_set`` for the authority chain.
    holographic_lines = _build_holographic_line_set(content)
    protected_lines = literal_zone_lines | holographic_lines

    lines = content.split("\n")
    result_lines: list[str] = []

    for line_num_0, line in enumerate(lines):
        line_num = line_num_0 + 1  # 1-based

        # Skip lines inside literal zones or holographic sanctuaries
        if line_num in protected_lines:
            result_lines.append(line)
            continue

        # Only process lines that match the unquoted-section-in-value pattern
        if not _UNQUOTED_SECTION_RE.match(line.lstrip()):
            # Also check: line might have leading whitespace that re.match misses
            # The regex is MULTILINE so it anchors to ^ but we're checking per-line
            if not _UNQUOTED_SECTION_RE.search(line):
                result_lines.append(line)
                continue

        # Extract value portion (after first ::)
        colon_idx = line.find("::")
        if colon_idx == -1:
            result_lines.append(line)
            continue

        key_part = line[: colon_idx + 2]  # includes the ::
        value_part = line[colon_idx + 2 :]

        # Check if all § marks are already quoted
        if _all_section_marks_quoted(value_part):
            result_lines.append(line)
            continue

        # Auto-quote unquoted § references in the value portion.
        # Walk character by character, tracking quote state.
        # GH#334: When a § is found, we quote the entire contiguous value
        # token containing it (e.g., §1_through_§4 becomes "§1_through_§4")
        # rather than quoting each § individually.
        new_value_chars: list[str] = []
        i = 0
        modified = False
        in_quote = False

        while i < len(value_part):
            ch = value_part[i]

            if ch == '"':
                # GH#361r2: Count consecutive backslashes before this quote
                # to determine parity.  Even count (including 0) means the
                # quote is NOT escaped; odd count means it IS escaped.
                backslash_count = 0
                j = i - 1
                while j >= 0 and value_part[j] == "\\":
                    backslash_count += 1
                    j -= 1
                if backslash_count % 2 == 0:
                    in_quote = not in_quote
                new_value_chars.append(ch)
                i += 1
            elif ch == "/" and i + 1 < len(value_part) and value_part[i + 1] == "/" and not in_quote:
                # Comment start: rest of line is comment, append as-is
                new_value_chars.append(value_part[i:])
                i = len(value_part)
            elif ch == "§" and not in_quote:
                # Found unquoted § — extract the full contiguous value token.
                # Use _SECTION_CONTAINING_TOKEN_RE to find the entire token
                # boundary (handles compound refs like §1_through_§4).
                token_match = _SECTION_CONTAINING_TOKEN_RE.match(value_part, i)
                if token_match:
                    ref_text = token_match.group(0)
                    new_value_chars.append('"')
                    new_value_chars.append(ref_text)
                    new_value_chars.append('"')
                    i = token_match.end()
                    modified = True
                else:
                    # Bare § without a following identifier — quote just §
                    new_value_chars.append('"§"')
                    i += 1
                    modified = True
            else:
                new_value_chars.append(ch)
                i += 1

        if modified:
            new_value = "".join(new_value_chars)
            new_line = key_part + new_value
            result_lines.append(new_line)
            corrections.append(
                {
                    "code": W_UNQUOTED_SECTION_IN_VALUE,
                    "tier": "LENIENT_PARSE",
                    "message": (
                        f"W_UNQUOTED_SECTION_IN_VALUE: Value at line {line_num} contains "
                        f"unquoted § which would be parsed as a section operator. "
                        f"Auto-quoted to preserve intended meaning (I1 fidelity)."
                    ),
                    "line": line_num,
                    "original": line.strip(),
                    "repaired": new_line.strip(),
                    "safe": True,
                    "semantics_changed": False,
                }
            )
        else:
            result_lines.append(line)

    return "\n".join(result_lines), corrections


def _detect_unquoted_section_in_values(content: str) -> list[dict[str, Any]]:
    """Detect unquoted § in value positions and emit guidance warnings.

    Scans input content for lines where § appears after :: without quoting.
    The lexer correctly tokenizes § as a SECTION operator, which can cause
    silent data loss when the user intended § as literal text in a value.

    This does NOT change parser behavior -- it only emits advisory warnings.

    GH#329: Excludes matches inside literal zones (``` fenced blocks) since
    the lexer preserves literal zone content verbatim.

    Returns:
        List of correction dicts with W_UNQUOTED_SECTION_IN_VALUE code.
    """
    warnings: list[dict[str, Any]] = []
    # GH#329: Build set of line numbers inside literal zones to skip
    literal_zone_lines = _build_literal_zone_line_set(content)
    # GH-420 Shape F sanctuary: lines whose bracketed value is a holographic
    # pattern are NOT advisory targets — the § is part of the operator chain.
    holographic_lines = _build_holographic_line_set(content)
    protected_lines = literal_zone_lines | holographic_lines

    for match in _UNQUOTED_SECTION_RE.finditer(content):
        # Calculate line number from match position
        line_num = content[: match.start()].count("\n") + 1

        # Skip matches inside literal zones or holographic sanctuaries
        if line_num in protected_lines:
            continue

        # Extract the full line for context
        line_start = content.rfind("\n", 0, match.start()) + 1
        line_end = content.find("\n", match.start())
        if line_end == -1:
            line_end = len(content)
        full_line = content[line_start:line_end].strip()

        # GH#329r2: Extract value portion (after ::) and check if all §
        # marks are inside quoted strings.  Handles arrays like ["§2"]
        # where the regex match alone cannot determine quoting context.
        colon_idx = full_line.find("::")
        value_part = full_line[colon_idx + 2 :] if colon_idx != -1 else full_line
        if _all_section_marks_quoted(value_part):
            continue

        warnings.append(
            {
                "code": W_UNQUOTED_SECTION_IN_VALUE,
                "tier": "LENIENT_PARSE",
                "message": (
                    f"W_UNQUOTED_SECTION_IN_VALUE: Value at line {line_num} contains "
                    f"unquoted § which is parsed as a section operator. "
                    f'Quote the value to use § as literal text: KEY::"value_with_§"'
                ),
                "line": line_num,
                "original": full_line,
                "safe": True,
                "semantics_changed": False,
            }
        )
    return warnings


def _build_annotation_protected_ranges(content: str) -> list[tuple[int, int]]:
    """Build character-offset protected ranges for W_ANNOTATION_TOO_LONG scanner.

    GH#403 rework: mirrors the protected-range approach used in
    _repair_curly_brace_annotations() to avoid false positives in:
      1. Literal zones (``` fenced blocks) — Zone 3, exempt from normalization
      2. Quoted strings ("...") — Zone 2, preserving containers
      3. Comment spans (// to end of line) — not OCTAVE DSL content

    Returns:
        Sorted list of (start, end) character-offset tuples that are protected.
    """
    protected: list[tuple[int, int]] = []

    # 1. Literal zones: ``` fenced blocks (including fence lines themselves)
    in_fence = False
    fence_start = 0
    offset = 0
    for line in content.split("\n"):
        line_start = offset
        offset += len(line) + 1  # +1 for newline separator
        stripped = line.strip()
        if stripped.startswith("```"):
            if not in_fence:
                in_fence = True
                fence_start = line_start
            else:
                in_fence = False
                fence_end = line_start + len(line)
                protected.append((fence_start, fence_end))
    # If fence was never closed, protect from fence_start to end of content
    if in_fence:
        protected.append((fence_start, len(content)))

    # 2. Quoted strings: text between "" anywhere in content
    quote_pattern = re.compile(r'"(?:[^"\\]|\\.)*"')
    for m in quote_pattern.finditer(content):
        protected.append((m.start(), m.end()))

    # 3. Comments: // to end of line
    comment_pattern = re.compile(r"//[^\n]*")
    for m in comment_pattern.finditer(content):
        protected.append((m.start(), m.end()))

    protected.sort()
    return protected


def _is_in_protected_range(pos: int, protected: list[tuple[int, int]]) -> bool:
    """Return True if character position falls within any protected range."""
    for start, end in protected:
        if start <= pos < end:
            return True
        if start > pos:
            break
    return False


def _count_brackets_outside_protected(line: str, line_offset: int, protected: list[tuple[int, int]]) -> int:
    """Return net bracket depth delta (``[`` minus ``]``) considering ONLY
    characters of ``line`` whose absolute offset falls OUTSIDE every
    protected range.

    Protected zones (literal fences, quoted strings, ``//`` comments) are
    opaque syntax-wise: brackets inside them are text, not list-open/close
    tokens. Used by ``_detect_snake_case_blob`` to keep multiline list
    state honest when a line begins in a protected zone but still contains
    a real ``[`` or ``]`` outside it (cubic P2 fix for PR #456 — see
    discussion_r3307813188).
    """
    delta = 0
    for col, ch in enumerate(line):
        if ch != "[" and ch != "]":
            continue
        if _is_in_protected_range(line_offset + col, protected):
            continue
        delta += 1 if ch == "[" else -1
    return delta


def _detect_annotation_too_long(content: str) -> list[dict[str, Any]]:
    """Detect annotation identifier content that violates discipline thresholds.

    GH#403: Annotations are SHORT qualifiers (1-3 words, identifier-only).
    Multi-word snake_case rationales stuffed into annotation content are a
    discipline violation.  This function emits a non-blocking advisory warning
    (W_ANNOTATION_TOO_LONG) for any annotation qualifier that exceeds EITHER:
      * len(qualifier) > 32 characters, OR
      * underscore-delimited token count >= 5 (i.e. >= 4 underscores in content)

    GH#403 rework: Uses character-offset protected ranges (same approach as
    _repair_curly_brace_annotations) to skip comment lines, quoted string
    values, and fenced literal zones.  Only Zone 1 (normalizing DSL) content
    is scanned for discipline violations.

    The warning is safe=True, semantics_changed=False — it is advisory only
    and does NOT block the write operation.  Frozen archives (docs/research/,
    examples/) receive the same treatment; the JIT policy (AGENTS.oct.md)
    governs when agents should refactor long annotations on amendment.

    Args:
        content: Raw OCTAVE document content string.

    Returns:
        List of correction dicts with W_ANNOTATION_TOO_LONG code, one per
        offending annotation found in the document.
    """
    warnings: list[dict[str, Any]] = []

    # Build protected ranges once for the whole document (I1: zone-aware scanning)
    protected = _build_annotation_protected_ranges(content)

    for match in _ANNOTATION_QUALIFIER_RE.finditer(content):
        # Skip matches whose start position falls inside a protected zone
        if _is_in_protected_range(match.start(), protected):
            continue

        qualifier = match.group(1)
        if not qualifier:
            continue

        qualifier_len = len(qualifier)
        underscore_token_count = qualifier.count("_") + 1  # tokens = underscores + 1

        if (
            qualifier_len > _ANNOTATION_TOO_LONG_CHAR_LIMIT
            or underscore_token_count >= _ANNOTATION_TOO_LONG_TOKEN_LIMIT
        ):
            # Compute 1-based line number from match position in full content
            line_num = content[: match.start()].count("\n") + 1
            annotation_value = match.group(0)
            warnings.append(
                {
                    "code": W_ANNOTATION_TOO_LONG,
                    "tier": "ANNOTATION_DISCIPLINE",
                    "message": (
                        f"W_ANNOTATION_TOO_LONG at line {line_num}: annotation qualifier "
                        f"'{qualifier}' exceeds discipline thresholds "
                        f"(len={qualifier_len}, tokens={underscore_token_count}). "
                        f"Annotations must be ≤32 chars and ≤4 underscore-tokens. "
                        f"Extract multi-word rationale to a sibling RATIONALE field with quoted prose."
                    ),
                    "line": line_num,
                    "annotation": annotation_value,
                    "qualifier": qualifier,
                    "qualifier_len": qualifier_len,
                    "underscore_token_count": underscore_token_count,
                    "safe": True,
                    "semantics_changed": False,
                }
            )
    return warnings


def _w_snake_case_blob_token_excluded(token: str) -> bool:
    """Return True if ``token`` is excluded from W_SNAKE_CASE_BLOB consideration.

    Exclusions (refined contract, operator comment 4549996376):
      * Token contains ``-`` or ``.`` (hyphen/dot identifiers are not snake-position)
      * Token matches ``^[A-Z][A-Z0-9_]{0,15}$`` (short ALL-CAPS idiom)
      * Token has zero underscores
    """
    if "-" in token or "." in token:
        return True
    if "_" not in token:
        return True
    if _W_SNAKE_CASE_BLOB_ALLCAPS_RE.match(token):
        return True
    return False


def _w_snake_case_blob_token_triggers(token: str) -> bool:
    """Apply bulk OR semantic content trigger to ``token``.

    Bulk:     ``len(token) > 40`` AND ``underscore_count >= 4``.
    Semantic: ``stopword_count >= 2`` where stopwords are matched
              case-insensitively against the underscore-delimited token parts.
    """
    underscore_count = token.count("_")

    # Bulk trigger
    if len(token) > _W_SNAKE_CASE_BLOB_BULK_CHAR_LIMIT and underscore_count >= _W_SNAKE_CASE_BLOB_BULK_UNDERSCORE_LIMIT:
        return True

    # Semantic trigger
    parts = token.lower().split("_")
    stopword_hits = sum(1 for p in parts if p in _W_SNAKE_CASE_BLOB_STOPWORDS)
    if stopword_hits >= _W_SNAKE_CASE_BLOB_SEMANTIC_STOPWORD_LIMIT:
        return True

    return False


def _w_snake_case_blob_build_warning(*, token: str, line_num: int, parent_field: str) -> dict[str, Any]:
    """Construct a W_SNAKE_CASE_BLOB warning dict (I4: stable provenance)."""
    return {
        "code": W_SNAKE_CASE_BLOB,
        # STRUCTURAL_CHECK tier: this is an informational diagnostic — no text
        # transformation is applied to the document. The HARD_SYMMETRY
        # invariant (ADR-0006 / I4) requires that "transformation tier"
        # corrections agree with the emitted diff; a no-op advisory belongs
        # in the STRUCTURAL_CHECK bucket so the diff-iff-corrections check
        # remains exact. See ``tests/unit/test_writer_reader_symmetry.py``.
        "tier": "STRUCTURAL_CHECK",
        "discipline": "REASONING_FIELD",
        "message": (
            f"W_SNAKE_CASE_BLOB at line {line_num}: snake-case prose blob "
            f"'{token}' in reasoning field '{parent_field}' — this is the "
            f"TELEGRAPHIC_PHRASE anti-pattern (snake_case prose masquerading "
            f"as an identifier). Extract to a quoted RATIONALE/NOTE string "
            f"value, or split into structured sub-fields. Advisory only."
        ),
        "line": line_num,
        "token": token,
        "parent_field": parent_field,
        "safe": True,
        "semantics_changed": False,
    }


def _detect_snake_case_blob(content: str) -> list[dict[str, Any]]:
    """Detect snake-case prose blobs in reasoning-field positions (GH#452).

    Refined contract (operator comment 4549996376):

    POSITION_TRIGGER ::
        * value-of-reasoning-field (``KEY::<value>`` where KEY is a reasoning field), OR
        * list-element-within-reasoning-field-list (each comma-separated element
          inside ``KEY::[...]`` or ``KEY:[...]`` where KEY is a reasoning field).

    CONTENT_TRIGGER (bulk OR semantic):
        * bulk: ``len(token) > 40`` AND ``underscore_count >= 4``
        * semantic: ``>=2`` stopword hits among underscore-delimited token parts

    EXCLUSIONS (any one suppresses the warning):
        * token contains ``-`` or ``.`` (path/hyphen identifiers are not snake-position)
        * token matches ``^[A-Z][A-Z0-9_]{0,15}$`` (short ALL-CAPS idiom)
        * token has zero underscores

    Protected zones (mirrors ``_detect_annotation_too_long``):
        * Fenced literal zones (Zone 3)
        * Quoted string values (Zone 2 preserving container)
        * ``//`` comment spans

    Severity v1: ADVISORY only — non-blocking, routed to corrections/warnings.
    Severity v2 (deferred): blocking enforcement ships in a separate PR ~30
    days later.

    Args:
        content: Raw OCTAVE document content string.

    Returns:
        List of correction dicts with code ``W_SNAKE_CASE_BLOB``, one per
        offending token (file:line provenance for I4 audit completeness).
    """
    warnings: list[dict[str, Any]] = []

    # Reuse the same zone-aware protected ranges as W_ANNOTATION_TOO_LONG so
    # comments, quoted strings, and literal fences are exempt by construction.
    protected = _build_annotation_protected_ranges(content)

    lines = content.split("\n")

    # Build cumulative line-start offsets so we can map (line_idx, col) -> offset
    # for protected-zone checks without re-walking the content each time.
    line_offsets: list[int] = [0]
    for ln in lines:
        line_offsets.append(line_offsets[-1] + len(ln) + 1)  # +1 for \n

    def _scan_value_span(value_text: str, base_offset: int, line_num: int, parent_field: str) -> None:
        """Scan a value-position span for snake-case prose blobs."""
        for tok_match in _W_SNAKE_CASE_BLOB_TOKEN_RE.finditer(value_text):
            tok = tok_match.group(0)
            # Strip trailing punctuation that the regex may have grabbed
            # (commas/closing brackets are not part of the regex char class,
            # but defensive trim in case of grammar drift).
            tok = tok.rstrip(",;]")
            if not tok:
                continue
            absolute_pos = base_offset + tok_match.start()
            if _is_in_protected_range(absolute_pos, protected):
                continue
            if _w_snake_case_blob_token_excluded(tok):
                continue
            if not _w_snake_case_blob_token_triggers(tok):
                continue
            warnings.append(_w_snake_case_blob_build_warning(token=tok, line_num=line_num, parent_field=parent_field))

    # Walk lines, tracking reasoning-field list context across line boundaries.
    in_reasoning_list = False
    list_parent_field = ""
    list_bracket_depth = 0

    i = 0
    while i < len(lines):
        raw_line = lines[i]
        line_num = i + 1
        line_offset = line_offsets[i]

        # Skip token scanning on lines that are wholly protected (e.g.
        # comment line, literal-fence line). A line is wholly protected if
        # its first non-whitespace character is inside a protected zone.
        # NOTE (cubic P2 / PR #456 discussion_r3307813188): bracket
        # accounting must STILL run on the non-protected substring of the
        # line, otherwise a real ``]`` sitting outside the protected range
        # (e.g. after a closing quote on the same line) would be missed
        # and ``in_reasoning_list`` would leak past the actual list close.
        first_nonws = len(raw_line) - len(raw_line.lstrip())
        line_start_pos = line_offset + first_nonws
        if first_nonws < len(raw_line) and _is_in_protected_range(line_start_pos, protected):
            if in_reasoning_list:
                list_bracket_depth += _count_brackets_outside_protected(raw_line, line_offset, protected)
                if list_bracket_depth <= 0:
                    in_reasoning_list = False
                    list_parent_field = ""
                    list_bracket_depth = 0
            i += 1
            continue

        if in_reasoning_list:
            # We're inside an open KEY::[ ... ] list opened on a prior line.
            # Each element on this line is candidate token territory.
            _scan_value_span(raw_line, line_offset, line_num, list_parent_field)
            # Track bracket balance to detect end of the list. Count only
            # brackets that sit outside protected ranges (cubic P2 fix):
            # ``]`` inside a comment or literal zone on this line is text,
            # not list syntax.
            list_bracket_depth += _count_brackets_outside_protected(raw_line, line_offset, protected)
            if list_bracket_depth <= 0:
                in_reasoning_list = False
                list_parent_field = ""
                list_bracket_depth = 0
            i += 1
            continue

        # Not currently in a list context — look for a reasoning-field opener.
        m = _W_SNAKE_CASE_BLOB_OPENER_RE.match(raw_line)
        if m:
            key = m.group(1)
            if key in _W_SNAKE_CASE_BLOB_REASONING_FIELDS:
                # The value portion begins right after the second colon.
                value_start_col = m.end()
                value_text = raw_line[value_start_col:]
                value_base_offset = line_offset + value_start_col

                # Detect whether the value opens a list across multiple lines.
                stripped_value = value_text.lstrip()
                opens_list = stripped_value.startswith("[")
                if opens_list:
                    # Inline-list-on-same-line OR multi-line list. Compute net
                    # bracket depth across this line, counting only brackets
                    # that sit outside protected ranges (cubic P2 fix —
                    # PR #456 discussion_r3307813188).
                    bracket_depth = _count_brackets_outside_protected(value_text, value_base_offset, protected)
                    if bracket_depth <= 0:
                        # Entire inline list on this single line — scan and done.
                        _scan_value_span(value_text, value_base_offset, line_num, key)
                    else:
                        # Multi-line list — scan this line as the opener and
                        # enter list context for subsequent lines.
                        _scan_value_span(value_text, value_base_offset, line_num, key)
                        in_reasoning_list = True
                        list_parent_field = key
                        list_bracket_depth = bracket_depth
                else:
                    # Plain scalar value on the same line.
                    _scan_value_span(value_text, value_base_offset, line_num, key)
                i += 1
                continue

        # Check for block-opener form ``DECISION:[`` (single colon followed by
        # ``[``) which the contract treats identically to ``KEY::[`` for the
        # purpose of list-element recursion. The opening ``[`` is required by
        # the regex itself (CRS PR #456 finding 3 — eliminating the optional
        # capture group + post-match check redundancy).
        bm = _W_SNAKE_CASE_BLOB_BLOCK_OPEN_RE.match(raw_line)
        if bm:
            key = bm.group(1)
            if key in _W_SNAKE_CASE_BLOB_REASONING_FIELDS:
                value_start_col = bm.end() - 1  # include the [
                value_text = raw_line[value_start_col:]
                value_base_offset = line_offset + value_start_col
                bracket_depth = _count_brackets_outside_protected(value_text, value_base_offset, protected)
                if bracket_depth <= 0:
                    _scan_value_span(value_text, value_base_offset, line_num, key)
                else:
                    _scan_value_span(value_text, value_base_offset, line_num, key)
                    in_reasoning_list = True
                    list_parent_field = key
                    list_bracket_depth = bracket_depth
                i += 1
                continue

        i += 1

    return warnings


# ---------------------------------------------------------------------------
# GH-structural-advisory: W_INLINE_ARRAY_ROOT
# ---------------------------------------------------------------------------

# Advisory code for map-as-inline-array structural pattern.
W_INLINE_ARRAY_ROOT = "W_INLINE_ARRAY_ROOT"

# Threshold: inline array with >= this many K::V elements triggers.
_W_INLINE_ARRAY_ROOT_ENTRY_THRESHOLD = 3

# Threshold: serialized array length > this triggers regardless of entry count.
_W_INLINE_ARRAY_ROOT_LENGTH_THRESHOLD = 80

# Regex: detects a K::V map-entry element within an inline array — the
# discriminator between map-as-inline-array and scalar/string lists.
# A map entry is: optional whitespace, an identifier token, `::`, then a value.
_W_INLINE_ARRAY_ROOT_ENTRY_RE = re.compile(r"(?:^|,)\s*[A-Za-z_][A-Za-z0-9_]*\s*::")

# Regex: detects an assignment opener with an inline array value on the same
# line: ``KEY::[...]`` (double-colon form).
_W_INLINE_ARRAY_ROOT_INLINE_RE = re.compile(r"^[ \t]*[A-Za-z_][A-Za-z0-9_]*\s*::\s*\[")

# Regex: detects a block-opener form ``KEY:[`` (single colon).
_W_INLINE_ARRAY_ROOT_BLOCK_RE = re.compile(r"^[ \t]*[A-Za-z_][A-Za-z0-9_]*\s*:\s*\[")


def _w_inline_array_root_array_is_map(array_content: str) -> bool:
    """Return True if *array_content* (the text between [ and ]) contains
    K::V map-entry elements.

    The discriminator: at least one element must contain ``::`` in an
    identifier-value position (not just a string value).
    """
    return bool(_W_INLINE_ARRAY_ROOT_ENTRY_RE.search(array_content))


def _w_inline_array_root_entry_count(array_content: str) -> int:
    """Count the number of top-level comma-separated elements in *array_content*."""
    # A simple heuristic: count commas at depth 0 plus 1.
    depth = 0
    commas = 0
    in_quote = False
    for ch in array_content:
        if ch == '"' and not in_quote:
            in_quote = True
        elif ch == '"' and in_quote:
            in_quote = False
        elif not in_quote:
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
            elif ch == "," and depth == 0:
                commas += 1
    stripped = array_content.strip()
    if not stripped:
        return 0
    return commas + 1


def _detect_inline_array_root(content: str) -> list[dict[str, Any]]:
    """Detect map-as-inline-array structural pattern (W_INLINE_ARRAY_ROOT).

    Fires when a key's value is an inline array ``[...]`` whose elements are
    themselves K::V map-entries (map-as-inline-array), AND EITHER:
      * entry count >= 3, OR
      * serialized length > ``_W_INLINE_ARRAY_ROOT_LENGTH_THRESHOLD``

    Does NOT fire on:
      * Legitimate scalar/string lists: IMMUTABLES::[a, b, c]
      * Content inside fenced literal zones (Zone 3)
      * Content inside // comments

    Discriminator: elements contain ``::`` map syntax.

    Severity: ADVISORY only (non-blocking, surfaced in warnings/corrections).

    Args:
        content: Raw OCTAVE document content string.

    Returns:
        List of warning dicts with code ``W_INLINE_ARRAY_ROOT``.
    """
    warnings_out: list[dict[str, Any]] = []

    literal_zone_lines = _build_literal_zone_line_set(content)
    lines = content.split("\n")

    # Build cumulative offsets for line-based tracking.
    line_offsets: list[int] = [0]
    for ln in lines:
        line_offsets.append(line_offsets[-1] + len(ln) + 1)

    i = 0
    while i < len(lines):
        raw_line = lines[i]
        line_num = i + 1

        # Skip literal zone lines.
        if line_num in literal_zone_lines:
            i += 1
            continue

        # Skip comment lines.
        stripped = raw_line.lstrip()
        if stripped.startswith("//"):
            i += 1
            continue

        # --- Case 1: inline form ``KEY::[...]`` on a single line ---
        m = _W_INLINE_ARRAY_ROOT_INLINE_RE.match(raw_line)
        # --- Case 2: block-open form ``KEY:[`` possibly spanning lines ---
        bm = _W_INLINE_ARRAY_ROOT_BLOCK_RE.match(raw_line) if not m else None

        opener_match = m or bm
        if not opener_match:
            i += 1
            continue

        # Locate the opening ``[`` position in the line.
        bracket_pos = raw_line.index("[", opener_match.start())
        # Collect the full array content by walking forward until balanced.
        full_array = ""
        depth = 0
        found_close = False
        scan_line_idx = i
        while scan_line_idx < len(lines):
            scan_line = lines[scan_line_idx]
            # Skip literal zone inside multi-line array collection.
            if scan_line_idx + 1 in literal_zone_lines and scan_line_idx != i:
                scan_line_idx += 1
                continue
            start_col = bracket_pos if scan_line_idx == i else 0
            for _col, ch in enumerate(scan_line[start_col:], start=start_col):
                if ch == "[":
                    depth += 1
                    if depth == 1:
                        continue  # skip the opening bracket itself
                elif ch == "]":
                    depth -= 1
                    if depth == 0:
                        found_close = True
                        break
                if depth > 0:
                    full_array += ch
            if found_close:
                break
            if depth > 0 and scan_line_idx < len(lines) - 1:
                full_array += "\n"
            scan_line_idx += 1

        if not found_close:
            i += 1
            continue

        # Discriminate: does the array content contain K::V map entries?
        if not _w_inline_array_root_array_is_map(full_array):
            i += 1
            continue

        entry_count = _w_inline_array_root_entry_count(full_array)
        array_length = len(full_array)

        if entry_count >= _W_INLINE_ARRAY_ROOT_ENTRY_THRESHOLD or array_length > _W_INLINE_ARRAY_ROOT_LENGTH_THRESHOLD:
            # Extract the key name from the line.
            key_match = re.match(r"^[ \t]*([A-Za-z_][A-Za-z0-9_]*)", raw_line)
            key_name = key_match.group(1) if key_match else "<unknown>"
            warnings_out.append(
                {
                    "code": W_INLINE_ARRAY_ROOT,
                    "tier": "STRUCTURAL_CHECK",
                    "discipline": "STRUCTURAL_ADVISORY",
                    "message": (
                        f"W_INLINE_ARRAY_ROOT at line {line_num}: key '{key_name}' "
                        f"has {entry_count} map-entry elements authored as an "
                        f"inline-array root; prefer BLOCK form (KEY: + indented "
                        f"children). Inline arrays are for scalar lists, not "
                        f"maps-of-maps."
                    ),
                    "line": line_num,
                    "key": key_name,
                    "entry_count": entry_count,
                    "safe": True,
                    "semantics_changed": False,
                }
            )

        i += 1

    return warnings_out


# ---------------------------------------------------------------------------
# GH-structural-advisory: W_FLAT_PREFIX_SCALAR
# ---------------------------------------------------------------------------

# Advisory code for flat sibling keys that share a redundant prefix.
W_FLAT_PREFIX_SCALAR = "W_FLAT_PREFIX_SCALAR"

# Minimum number of sibling keys sharing a prefix to trigger the warning.
_W_FLAT_PREFIX_SCALAR_GROUP_THRESHOLD = 3

# Regex matching a top-level (zero-indent or consistent-indent) KEY assignment.
# Captures the full key name. We restrict to uppercase/underscore keys as those
# are the primary OCTAVE structural pattern subject to flat-prefix sprawl.
_W_FLAT_PREFIX_SCALAR_KEY_RE = re.compile(r"^([ \t]*)([A-Z][A-Z0-9_]+)\s*:[:s]")


def _w_flat_prefix_scalar_all_prefixes(key: str) -> list[str]:
    """Return all valid underscore-delimited prefix segments for *key*.

    For ``NODE_RUNTIME_FLOOR`` → [``NODE``, ``NODE_RUNTIME``].
    For ``DB_HOST`` → [``DB``].
    For ``FOO`` (no underscore) → [] (single-segment keys have no prefix).

    We generate ALL candidate prefixes (not just "all except last") so that
    siblings like ``NODE_RUNTIME_FLOOR``, ``NODE_RUNTIME_PIN_SITES``,
    ``NODE_RUNTIME_WHY`` all map to the shared prefix ``NODE_RUNTIME`` even
    though their "all except last" prefixes differ (``NODE_RUNTIME`` vs
    ``NODE_RUNTIME_PIN``).
    """
    parts = key.split("_")
    if len(parts) < 2:
        return []
    # All prefixes: from the first segment up to (but not including) the last.
    return ["_".join(parts[:n]) for n in range(1, len(parts))]


def _detect_flat_prefix_scalar(content: str) -> list[dict[str, Any]]:
    """Detect sibling keys that share a redundant underscore prefix (W_FLAT_PREFIX_SCALAR).

    Heuristic:
      1. Extract all key assignment lines at the same indentation level
         (excluding literal zones and comment lines).
      2. For each candidate prefix (all underscore-delimited prefixes of each
         key), count how many sibling keys share that prefix.
      3. For groups with >= 3 members at the same indentation level, emit an
         advisory warning suggesting nesting under a ``{PREFIX}:`` block parent.
      4. Report the longest qualifying prefix to give the most actionable advice.

    Severity: ADVISORY only (non-blocking).

    Args:
        content: Raw OCTAVE document content string.

    Returns:
        List of warning dicts with code ``W_FLAT_PREFIX_SCALAR``.
    """
    warnings_out: list[dict[str, Any]] = []
    literal_zone_lines = _build_literal_zone_line_set(content)

    lines = content.split("\n")

    # Collect (indent_level, key_name, line_num) tuples.
    entries: list[tuple[str, str, int]] = []

    for line_idx, raw_line in enumerate(lines):
        line_num = line_idx + 1

        # Skip literal zone lines.
        if line_num in literal_zone_lines:
            continue

        # Skip comment lines.
        stripped = raw_line.lstrip()
        if stripped.startswith("//"):
            continue

        m = _W_FLAT_PREFIX_SCALAR_KEY_RE.match(raw_line)
        if not m:
            continue

        indent = m.group(1)
        key_name = m.group(2)
        entries.append((indent, key_name, line_num))

    if not entries:
        return warnings_out

    from collections import defaultdict

    # Build a mapping: (indent, prefix) -> list of (key_name, line_num)
    # A key contributes to every prefix group it belongs to.
    prefix_groups: dict[tuple[str, str], list[tuple[str, int]]] = defaultdict(list)

    for indent, key_name, line_num in entries:
        for prefix in _w_flat_prefix_scalar_all_prefixes(key_name):
            prefix_groups[(indent, prefix)].append((key_name, line_num))

    # Among qualifying groups (size >= threshold), report the LONGEST prefix
    # for each key set — this gives the most actionable suggestion.
    # To avoid double-reporting a set of keys under both "DB" and "DB_HOST"
    # when the intent is to flag "DB", we deduplicate by the key-set fingerprint
    # and keep only the longest prefix per unique key set.
    best_prefix_for_keyset: dict[tuple[str, frozenset[str]], str] = {}

    for (indent, prefix), members in prefix_groups.items():
        if len(members) < _W_FLAT_PREFIX_SCALAR_GROUP_THRESHOLD:
            continue
        key_set = frozenset(k for k, _ in members)
        group_id = (indent, key_set)
        existing = best_prefix_for_keyset.get(group_id)
        if existing is None or len(prefix) > len(existing):
            best_prefix_for_keyset[group_id] = prefix

    # Emit one warning per unique (indent, key_set) using the best (longest) prefix.
    for (indent, _key_set), best_prefix in best_prefix_for_keyset.items():
        # Retrieve the members for this (indent, best_prefix) group.
        members = prefix_groups[(indent, best_prefix)]
        # De-duplicate member list (a key may appear multiple times if it
        # contributes to both shorter and longer prefix groups).
        seen_keys: set[str] = set()
        unique_members: list[tuple[str, int]] = []
        for k, ln in members:
            if k not in seen_keys:
                seen_keys.add(k)
                unique_members.append((k, ln))

        if len(unique_members) < _W_FLAT_PREFIX_SCALAR_GROUP_THRESHOLD:
            continue

        first_line = unique_members[0][1]
        key_names = [k for k, _ in unique_members]
        warnings_out.append(
            {
                "code": W_FLAT_PREFIX_SCALAR,
                "tier": "STRUCTURAL_CHECK",
                "discipline": "STRUCTURAL_ADVISORY",
                "message": (
                    f"W_FLAT_PREFIX_SCALAR at line {first_line}: sibling keys "
                    f"share prefix '{best_prefix}_'; nest under '{best_prefix}:' "
                    f"block to drop the redundant prefix (key-token saving + "
                    f"better attention inheritance). Keys: {', '.join(key_names)}"
                ),
                "line": first_line,
                "prefix": best_prefix,
                "keys": key_names,
                "safe": True,
                "semantics_changed": False,
            }
        )

    return warnings_out
