"""MCP tool for OCTAVE write (GH#51 Tool Consolidation).

Implements octave_write tool - replaces octave_create + octave_amend with:
- Unified write with content XOR changes parameter model (or neither for normalize)
- Normalize mode: omit both content and changes to re-emit existing file in canonical form
- Tri-state semantics for changes: absent=no-op, {"$op":"DELETE"}=remove, null=empty
- base_hash CAS guard in BOTH modes when file exists
- Unified envelope: status, path, canonical_hash, corrections, diff, errors, validation_status
- I1 (Syntactic Fidelity): Normalizes to canonical form
- I2 (Deterministic Absence): Tri-state semantics
- I4 (Auditability): Returns corrections and diff
- I5 (Schema Sovereignty): Always returns validation_status
"""

import copy
import hashlib
import os
import re
import tempfile
from dataclasses import dataclass, field
from difflib import unified_diff
from pathlib import Path
from typing import Any

from octave_mcp.core.ast_nodes import (
    Assignment,
    ASTNode,
    Block,
    Comment,
    Document,
    InlineMap,
    ListValue,
    LiteralZoneValue,
    Section,
)
from octave_mcp.core.emitter import emit
from octave_mcp.core.gbnf_compiler import GBNFCompiler
from octave_mcp.core.hydrator import resolve_hermetic_standard
from octave_mcp.core.lexer import ENVELOPE_ID_PATTERN, LexerError, tokenize
from octave_mcp.core.literal_zone_audit import build_literal_zone_repair_log
from octave_mcp.core.parser import ParserError, parse, parse_with_warnings
from octave_mcp.core.repair import repair
from octave_mcp.core.schema_extractor import SchemaDefinition
from octave_mcp.core.validator import Validator, _count_literal_zones
from octave_mcp.mcp.base_tool import BaseTool, SchemaBuilder
from octave_mcp.mcp.compile_grammar import USAGE_HINTS
from octave_mcp.schemas.loader import (
    BUILTIN_SCHEMA_DEFINITIONS,
    get_builtin_schema,
    get_schema_search_paths,
    load_schema,
    load_schema_by_name,
)

# Sentinel for DELETE operation in tri-state changes
DELETE_SENTINEL = {"$op": "DELETE"}

# Structural warning codes (Issue #92)
W_STRUCT_001 = "W_STRUCT_001"  # Section marker loss
W_STRUCT_002 = "W_STRUCT_002"  # Block count reduction
W_STRUCT_003 = "W_STRUCT_003"  # Assignment count reduction

# Quoting guidance warning
W_UNQUOTED_SECTION_IN_VALUE = "W_UNQUOTED_SECTION_IN_VALUE"

# GH#349: Data loss warning for bare lines dropped during lenient parsing (I4)
W_BARE_LINE_DROPPED = "W_BARE_LINE_DROPPED"

# GH#376 PR-A: format_style parameter constants.
# Three modes are projections of one canonical AST→bytes function (I1
# Single-Canon Discipline). They are NOT parallel emitters.
#
# - "preserve": Strategy C — if parse(new_content) == parse(baseline_content)
#   (AST-equality, ignoring whitespace) write baseline bytes verbatim and
#   short-circuit; otherwise fall through to canonical emit().
# - "expanded": AST normalisation pre-pass that lifts InlineMap (and ListValue
#   items that are InlineMap) into Block form before emit(). Output is the
#   canonical multi-line form.
# - "compact": AST normalisation pre-pass that collapses eligible Blocks
#   (atom-only children, no Comments anywhere in subtree, arity-bounded) into
#   Assignment(value=ListValue([InlineMap{...}, ...])). Subtrees containing a
#   Comment are vetoed (left untouched) and a W_COMPACT_REFUSED entry surfaces
#   in the repair log (I3 Mirror Constraint + I4 Auditability).
#
# When format_style is omitted (None), today's behaviour is preserved exactly:
# emit(doc) with no pre-pass and no short-circuit (the "current" sentinel
# documented in the PR description). This guarantees the 2788 baseline tests
# remain byte-identical.
FORMAT_STYLE_VALUES: tuple[str, str, str] = ("preserve", "expanded", "compact")
E_INVALID_FORMAT_STYLE = "E_INVALID_FORMAT_STYLE"
W_COMPACT_REFUSED = "W_COMPACT_REFUSED"

# CIV B2 (#376 PR-A rework): structured error code raised when an AST cycle is
# detected by the format_style traversals. AST nodes are mutable dataclasses
# that can be programmatically constructed into self-referential graphs; the
# traversals MUST surface this as a stable code rather than letting a
# RecursionError escape unwrapped.
E_AST_CYCLE = "E_AST_CYCLE"


class OctaveASTCycleError(ValueError):
    """Raised when a format_style AST traversal detects a cycle.

    Carries a stable ``code`` attribute (``E_AST_CYCLE``) so downstream
    error envelopes can surface a structured identifier rather than a bare
    RecursionError.
    """

    code: str = E_AST_CYCLE

    def __init__(self, node: Any, where: str) -> None:
        msg = (
            f"{E_AST_CYCLE}: AST cycle detected during format_style traversal "
            f"at {where} (node id={id(node)}, type={type(node).__name__}). "
            "Format_style traversals require an acyclic AST."
        )
        super().__init__(msg)


# Compact mode arity bound — collapse only "small" Blocks to keep output
# readable. Values above this stay in Block form.
_COMPACT_MAX_PAIRS = 8

# CIV B3 (#376 PR-A rework): W_COMPACT_REFUSED record carries a ``reason``
# discriminant so callers can distinguish why a subtree was not collapsed.
# This closes the I4 audit-symmetry gap where arity-exceeded blocks were
# previously skipped silently.
_REFUSE_REASON_COMMENT = "contains_comment"
_REFUSE_REASON_ARITY = "arity_exceeded"

# GH#352: Guidance hint for UNVALIDATED status (I5)
# GH#361r3: Base hint text; available schemas appended dynamically at runtime.
_VALIDATION_HINT_BASE = "Pass schema='META' (or another schema name) to enable I5 schema validation."

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

    lines = content.split("\n")
    result_lines: list[str] = []

    for line_num_0, line in enumerate(lines):
        line_num = line_num_0 + 1  # 1-based

        # Skip lines inside literal zones
        if line_num in literal_zone_lines:
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

    for match in _UNQUOTED_SECTION_RE.finditer(content):
        # Calculate line number from match position
        line_num = content[: match.start()].count("\n") + 1

        # GH#329: Skip matches inside literal zones
        if line_num in literal_zone_lines:
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


@dataclass
class StructuralMetrics:
    """Metrics for structural comparison of OCTAVE documents.

    Tracks counts of structural elements to detect potential data loss
    during normalization or transformation.
    """

    sections: int = 0  # Count of Section nodes
    section_markers: set[str] = field(default_factory=set)  # Section IDs found
    blocks: int = 0  # Count of Block nodes
    assignments: int = 0  # Count of Assignment nodes


def extract_structural_metrics(doc: Document) -> StructuralMetrics:
    """Extract structural metrics from a parsed OCTAVE document.

    Recursively traverses the AST to count structural elements.

    Args:
        doc: Parsed Document AST

    Returns:
        StructuralMetrics with counts of structural elements
    """
    metrics = StructuralMetrics()

    def traverse(nodes: list[ASTNode]) -> None:
        """Recursively count structural elements."""
        for node in nodes:
            if isinstance(node, Section):
                metrics.sections += 1
                metrics.section_markers.add(node.section_id)
                traverse(node.children)
            elif isinstance(node, Block):
                metrics.blocks += 1
                traverse(node.children)
            elif isinstance(node, Assignment):
                metrics.assignments += 1

    traverse(doc.sections)
    return metrics


def _is_delete_sentinel(value: Any) -> bool:
    """Check if value is the DELETE sentinel.

    Args:
        value: Value to check

    Returns:
        True if value is the DELETE sentinel
    """
    return isinstance(value, dict) and value.get("$op") == "DELETE"


# GH#373: Recognised op descriptors for op-aware nested mutation.
# Bare values (no $op) preserve PR #370 full-replacement semantics.
_KNOWN_OPS = frozenset({"APPEND", "PREPEND", "MERGE", "DELETE"})


def _is_op_descriptor(value: Any) -> bool:
    """GH#373: True iff value is a dict carrying a recognised "$op" key.

    Discriminates op descriptors from bare dict values (which are valid full
    replacements emitted as InlineMap). A dict without "$op" is bare data;
    a dict with "$op" is interpreted as an instruction and validated.
    """
    return isinstance(value, dict) and "$op" in value


def _extract_op_descriptor(value: Any) -> tuple[str | None, Any, dict[str, Any] | None]:
    """GH#373: Parse a changes-mode value into (op, payload, error).

    Returns:
        (op, payload, error) tuple where:
          - op: one of "APPEND" | "PREPEND" | "MERGE" | "DELETE" if the value
            is a recognised op descriptor; None for bare values (legacy
            full-replacement semantics).
          - payload: the descriptor's "value" field (for APPEND/PREPEND/MERGE),
            None for DELETE, or the bare value verbatim when op is None.
          - error: None on success; otherwise an error dict with code
            "E_INVALID_OP_DESCRIPTOR" describing the malformation.

    Validation rules:
      - Unknown $op string -> E_INVALID_OP_DESCRIPTOR.
      - APPEND / PREPEND / MERGE without "value" key -> E_INVALID_OP_DESCRIPTOR.
        (DELETE has no "value" by design.)
      - MERGE with non-dict "value" -> E_INVALID_OP_DESCRIPTOR.
    """
    if not _is_op_descriptor(value):
        return (None, value, None)

    op = value.get("$op")
    if not isinstance(op, str) or op not in _KNOWN_OPS:
        return (
            None,
            None,
            {
                "code": "E_INVALID_OP_DESCRIPTOR",
                "message": (
                    f"Invalid $op value {op!r}: expected one of "
                    f"{sorted(_KNOWN_OPS)}. Bare values (no $op) are "
                    f"interpreted as full replacement."
                ),
            },
        )

    if op == "DELETE":
        # DELETE has no payload; ignore any extra keys for forward-compat.
        return ("DELETE", None, None)

    if "value" not in value:
        return (
            None,
            None,
            {
                "code": "E_INVALID_OP_DESCRIPTOR",
                "message": (f"$op {op!r} descriptor is missing required 'value' field."),
            },
        )

    payload = value["value"]
    if op == "MERGE" and not isinstance(payload, dict):
        return (
            None,
            None,
            {
                "code": "E_INVALID_OP_DESCRIPTOR",
                "message": (
                    f"$op MERGE requires 'value' to be a dict (block contents); " f"got {type(payload).__name__}."
                ),
            },
        )

    return (op, payload, None)


def _apply_array_op_inplace(assignment: Assignment, op: str, payload: Any) -> None:
    """GH#373: Apply APPEND or PREPEND to a list-valued Assignment in place.

    Caller is responsible for verifying target type via _resolve_target_type
    (validator already does this and rejects mismatches with E_OP_TARGET_MISMATCH).

    Semantics:
      - payload as a single element: push/unshift one element.
      - payload as a list: bulk push/unshift in caller order.
    Existing items keep their original tokens (where present); new items are
    appended as Python values, mirroring how _normalize_value_for_ast produces
    list contents.

    Args:
        assignment: The Assignment node holding a ListValue or list.
        op: "APPEND" or "PREPEND".
        payload: Element or list of elements to push.
    """
    new_items = list(payload) if isinstance(payload, list) else [payload]

    current = assignment.value
    if isinstance(current, ListValue):
        existing = list(current.items)
        # Drop tokens: bulk-edit invalidates the verbatim token slice. Re-emission
        # will use canonical form for the modified array's bytes (diff-locality
        # gap is documented in GH#371).
        if op == "APPEND":
            assignment.value = ListValue(items=existing + new_items)
        else:  # PREPEND
            assignment.value = ListValue(items=new_items + existing)
    elif isinstance(current, list):
        if op == "APPEND":
            assignment.value = ListValue(items=current + new_items)
        else:  # PREPEND
            assignment.value = ListValue(items=new_items + current)
    else:
        # Validator should prevent this; defensive raise for direct callers.
        raise ValueError(
            [
                {
                    "code": "E_OP_TARGET_MISMATCH",
                    "message": (f"$op {op} requires list-valued target; got " f"{type(current).__name__}."),
                }
            ]
        )


def _target_type_for_assignment(value: Any) -> str:
    """GH#373: Classify an Assignment's value for op/target-type validation.

    Returns one of: "array" | "scalar" | "map".
      - "array": ListValue or Python list.
      - "map":   InlineMap or Python dict (non-op-descriptor).
      - "scalar": everything else (str, int, bool, None, LiteralZoneValue, etc.).
    """
    if isinstance(value, ListValue | list):
        return "array"
    if isinstance(value, InlineMap) or (isinstance(value, dict) and not _is_op_descriptor(value)):
        return "map"
    return "scalar"


def _normalize_value_for_ast(value: Any) -> Any:
    """Normalize a Python value to an AST-compatible type.

    I1 (Syntactic Fidelity): Ensures values are properly typed for emission.

    Python lists must be wrapped in ListValue to emit correct OCTAVE syntax.
    Without this, str(list) produces "['a', 'b']" which is invalid OCTAVE.

    Python dicts must be wrapped in InlineMap to emit correct OCTAVE syntax.
    Without this, str(dict) produces "{'key': 'value'}" which is invalid OCTAVE.
    Issue #176: Nested dicts should produce valid OCTAVE like [key::value], not Python repr.

    Args:
        value: Python value from changes dict

    Returns:
        AST-compatible value (ListValue for lists, InlineMap for dicts, original for others)
    """
    # Issue #235 MP8: Literal zones must NOT be normalized (D3: zero processing).
    # Return unchanged to prevent content being wrapped or coerced.
    if isinstance(value, LiteralZoneValue):
        return value

    if isinstance(value, list):
        # Recursively normalize list items
        normalized_items = [_normalize_value_for_ast(item) for item in value]
        return ListValue(items=normalized_items)
    elif isinstance(value, dict):
        # Issue #176: Convert dicts to InlineMap to produce valid OCTAVE syntax
        # InlineMap emits as [key::value,key2::value2] which is valid OCTAVE
        # Without this, str(dict) produces "{'key': 'value'}" which is INVALID OCTAVE
        # Recursively normalize all values in the dict
        normalized_pairs = {k: _normalize_value_for_ast(v) for k, v in value.items()}
        return InlineMap(pairs=normalized_pairs)
    # Other types (str, int, bool, None, etc.) are handled by emit_value directly
    return value


# ---------------------------------------------------------------------------
# GH#376 PR-A: format_style AST projections (I1 Single-Canon Discipline).
#
# These helpers form AST normalisation pre-passes feeding the SAME emit()
# function used by today's canonical pipeline. They never fork the emitter.
# ---------------------------------------------------------------------------


def _is_atom_value(v: Any) -> bool:
    """Return True for primitive values safe to put inside an InlineMap pair.

    Excludes structured nodes (ListValue, InlineMap, HolographicValue,
    LiteralZoneValue) since collapsing those into an inline pair would change
    semantics.
    """
    return v is None or isinstance(v, (bool, int, float, str))


def _subtree_has_comment(node: Any, _seen: set[int] | None = None) -> bool:
    """Recursively check whether a subtree contains any Comment node.

    Compact mode MUST NOT collapse any subtree containing a Comment — doing so
    would erase the comment, violating I3 Mirror Constraint. Comments may live
    as Comment children, leading_comments, or trailing_comment annotations on
    any ASTNode.

    CIV B2 (#376 PR-A rework): traversal carries an id-keyed visited-set so
    that programmatically-constructed cyclic ASTs surface a structured
    ``OctaveASTCycleError`` (``code = E_AST_CYCLE``) instead of escaping as a
    bare ``RecursionError``. Keys on ``id(node)`` because AST nodes are
    mutable dataclasses and therefore unhashable.

    Cubic C2 (#376 PR-A rework): the visited-set is a DFS *path stack*, not a
    permanent visited record — entries are discarded on frame exit via the
    ``finally`` block. This distinguishes a true cycle (same node reachable
    from itself along the current ancestry) from a shared-acyclic reference
    (same node reached via two distinct paths under different parents).
    """
    if _seen is None:
        _seen = set()
    nid = id(node)
    if nid in _seen:
        raise OctaveASTCycleError(node, where="_subtree_has_comment")
    _seen.add(nid)
    try:
        if isinstance(node, Comment):
            return True
        if isinstance(node, ASTNode):
            if getattr(node, "leading_comments", None):
                return True
            if getattr(node, "trailing_comment", None):
                return True
        if isinstance(node, (Block, Section)):
            return any(_subtree_has_comment(c, _seen) for c in node.children)
        if isinstance(node, Document):
            if node.trailing_comments:
                return True
            return any(_subtree_has_comment(c, _seen) for c in node.sections)
        return False
    finally:
        _seen.discard(nid)


def _block_compact_eligible(block: Block) -> bool:
    """Return True if a Block can safely collapse into an inline-list-of-InlineMap.

    Eligibility requires:
    - Every child is an Assignment (no nested Blocks/Sections/Comments)
    - Every Assignment's value is an atom (str/int/float/bool/None)
    - The Block carries no comments (leading_comments/trailing_comment)
    - No Assignment child carries comments
    - The Block has at least one and at most _COMPACT_MAX_PAIRS children
    - The Block has no target annotation (collapsing would lose it)
    """
    if block.target:
        return False
    if block.leading_comments or block.trailing_comment:
        return False
    if not block.children or len(block.children) > _COMPACT_MAX_PAIRS:
        return False
    for child in block.children:
        if not isinstance(child, Assignment):
            return False
        if child.leading_comments or child.trailing_comment:
            return False
        if not _is_atom_value(child.value):
            return False
    return True


def _block_would_collapse_but_for_arity(block: Block) -> bool:
    """Return True if ``block`` is collapse-eligible apart from arity.

    Used by the compact pre-pass to surface a W_COMPACT_REFUSED record with
    ``reason="arity_exceeded"`` when an otherwise-collapsible Block has more
    than ``_COMPACT_MAX_PAIRS`` children. This closes the I4 audit-symmetry
    gap (CIV B3): the contract is "compact tells you what it refused", so an
    eligible-but-too-large Block must produce an audit record rather than
    pass through silently.
    """
    if len(block.children) <= _COMPACT_MAX_PAIRS:
        return False
    if block.target:
        return False
    if block.leading_comments or block.trailing_comment:
        return False
    for child in block.children:
        if not isinstance(child, Assignment):
            return False
        if child.leading_comments or child.trailing_comment:
            return False
        if not _is_atom_value(child.value):
            return False
    return True


def _block_to_compact_assignment(block: Block) -> Assignment:
    """Convert an eligible Block into Assignment(KEY, ListValue([InlineMap, ...])).

    Each child Assignment becomes a single-pair InlineMap inside the ListValue.
    This mirrors the parsed shape of bracket-notation inline lists (verified by
    parser experiment: ``[K::V,L::W]`` parses as ListValue of two InlineMaps,
    each with one pair) so that re-parsing the emitted form is structurally
    stable.
    """
    items: list[Any] = []
    for child in block.children:
        assert isinstance(child, Assignment)  # noqa: S101 -- _block_compact_eligible guarantees
        items.append(InlineMap(pairs={child.key: child.value}))
    return Assignment(
        key=block.key,
        value=ListValue(items=items),
        line=block.line,
        column=block.column,
    )


def _compact_pass(
    children: list[Any],
    corrections: list[dict[str, Any]],
    field_path: str,
    _seen: set[int] | None = None,
) -> list[Any]:
    """Walk a list of AST children, collapsing eligible Blocks in place.

    Ineligible Blocks have their children recursively visited (so a Block that
    can't collapse may still contain a Block deeper down that can). Subtrees
    containing Comments are vetoed and a W_COMPACT_REFUSED record with
    ``reason="contains_comment"`` is appended to ``corrections`` (I3 Mirror
    Constraint + I4 Audit). Blocks that would otherwise be eligible but exceed
    ``_COMPACT_MAX_PAIRS`` produce a W_COMPACT_REFUSED with
    ``reason="arity_exceeded"`` (CIV B3 audit-symmetry). Other node types
    pass through unchanged.

    CIV B1: when sibling Blocks/Sections share a key, audit IDs are
    disambiguated with a ``#N`` suffix so refusal records remain uniquely
    attributable.

    CIV B2: traversal carries an id-keyed visited-set; a self-referential AST
    raises ``OctaveASTCycleError`` (``E_AST_CYCLE``) instead of escaping as a
    ``RecursionError``.

    Cubic C2 (#376 PR-A rework): the visited-set is a DFS *path stack*. Each
    frame discards its own id() on exit via ``finally``, so two distinct
    parents may legally share an acyclic child by reference without the guard
    misfiring. A genuine cycle is still caught — the offending node remains on
    the stack along its own ancestry.
    """
    if _seen is None:
        _seen = set()

    # Per-call ordinal tracker for this children-list (CIV B1 sibling ID).
    ordinals: dict[str, int] = {}

    # First pass: count collision occurrences so singletons stay un-suffixed
    # (``KEY``) while genuine collisions surface as ``KEY#0``, ``KEY#1``, etc.
    key_counts: dict[str, int] = {}
    for child in children:
        if isinstance(child, Block):
            key_counts[child.key] = key_counts.get(child.key, 0) + 1
        elif isinstance(child, Section):
            sk = f"§{child.section_id}"
            key_counts[sk] = key_counts.get(sk, 0) + 1

    out: list[Any] = []
    for child in children:
        nid = id(child)
        if nid in _seen:
            raise OctaveASTCycleError(child, where="_compact_pass")
        _seen.add(nid)
        try:
            if isinstance(child, Block):
                key: str = child.key
                n = ordinals.get(key, 0)
                ordinals[key] = n + 1
                suffix = f"#{n}" if key_counts[key] > 1 else ""
                base = f"{field_path}.{key}" if field_path else key
                child_path = base + suffix

                if _subtree_has_comment(child):
                    # I3 veto — leave Block untouched so comments survive (I4 audit).
                    corrections.append(
                        {
                            "code": W_COMPACT_REFUSED,
                            "tier": "FORMAT_STYLE",
                            "field": child_path,
                            "reason": _REFUSE_REASON_COMMENT,
                            "message": (
                                f"Compact mode refused to collapse subtree '{child_path}': "
                                "contains comment(s) (I3 Mirror Constraint)."
                            ),
                            "safe": True,
                            "semantics_changed": False,
                        }
                    )
                    # Still recurse into children — deeper Blocks without comments
                    # can still collapse where safe.
                    child.children = _compact_pass(child.children, corrections, child_path, _seen)
                    out.append(child)
                elif _block_compact_eligible(child):
                    out.append(_block_to_compact_assignment(child))
                elif _block_would_collapse_but_for_arity(child):
                    # CIV B3 — eligible-but-too-large block, surface receipt.
                    corrections.append(
                        {
                            "code": W_COMPACT_REFUSED,
                            "tier": "FORMAT_STYLE",
                            "field": child_path,
                            "reason": _REFUSE_REASON_ARITY,
                            "message": (
                                f"Compact mode refused to collapse subtree '{child_path}': "
                                f"{len(child.children)} children exceed _COMPACT_MAX_PAIRS="
                                f"{_COMPACT_MAX_PAIRS}."
                            ),
                            "safe": True,
                            "semantics_changed": False,
                        }
                    )
                    # Even though we won't collapse, recurse to honour deeper opportunities.
                    child.children = _compact_pass(child.children, corrections, child_path, _seen)
                    out.append(child)
                else:
                    # Not eligible (e.g. mixed children) but no comments — recurse.
                    child.children = _compact_pass(child.children, corrections, child_path, _seen)
                    out.append(child)
            elif isinstance(child, Section):
                sk = f"§{child.section_id}"
                n = ordinals.get(sk, 0)
                ordinals[sk] = n + 1
                suffix = f"#{n}" if key_counts[sk] > 1 else ""
                base = f"{field_path}.{sk}" if field_path else sk
                child_path = base + suffix
                child.children = _compact_pass(child.children, corrections, child_path, _seen)
                out.append(child)
            else:
                out.append(child)
        finally:
            _seen.discard(nid)
    return out


def _expand_pass(children: list[Any], _seen: set[int] | None = None) -> list[Any]:
    """Walk a list of AST children, lifting InlineMap shapes into Blocks.

    Two patterns are lifted:
    - ``Assignment(KEY, InlineMap{k1:v1,...})`` → ``Block(KEY, [Assignment(k1,v1),...])``
    - ``Assignment(KEY, ListValue([InlineMap{k1:v1}, InlineMap{k2:v2}, ...]))``
      where every list item is an atom-valued InlineMap → ``Block(KEY, [...])``

    Only atom-valued InlineMaps are lifted; structured values stay inline so we
    do not fabricate semantic content (I3 Mirror Constraint).

    CIV B2 (#376 PR-A rework): traversal carries an id-keyed visited-set so a
    self-referential AST raises ``OctaveASTCycleError`` (``E_AST_CYCLE``)
    instead of escaping as a bare ``RecursionError``.

    Cubic C2 (#376 PR-A rework): the visited-set is a DFS *path stack*; each
    frame discards its id() on exit so shared-acyclic references (the same
    child instance under two parents) traverse cleanly. True cycles still
    raise because the offending node remains on its own ancestry path.
    """
    if _seen is None:
        _seen = set()
    out: list[Any] = []
    for child in children:
        nid = id(child)
        if nid in _seen:
            raise OctaveASTCycleError(child, where="_expand_pass")
        _seen.add(nid)
        try:
            if isinstance(child, Assignment):
                lifted = _maybe_lift_assignment_to_block(child)
                if lifted is not None:
                    out.append(lifted)
                else:
                    out.append(child)
            elif isinstance(child, Block):
                child.children = _expand_pass(child.children, _seen)
                out.append(child)
            elif isinstance(child, Section):
                child.children = _expand_pass(child.children, _seen)
                out.append(child)
            else:
                out.append(child)
        finally:
            _seen.discard(nid)
    return out


def _maybe_lift_assignment_to_block(assignment: Assignment) -> Block | None:
    """Return a Block lifted from an InlineMap-shaped Assignment, or None.

    Returns None when the value is not an InlineMap shape eligible for lifting.
    """
    value = assignment.value
    pairs: list[tuple[str, Any]] = []

    if isinstance(value, InlineMap):
        for k, v in value.pairs.items():
            if not _is_atom_value(v):
                return None
            pairs.append((k, v))
    elif isinstance(value, ListValue):
        if not value.items or not all(isinstance(it, InlineMap) for it in value.items):
            return None
        for item in value.items:
            assert isinstance(item, InlineMap)  # noqa: S101
            for k, v in item.pairs.items():
                if not _is_atom_value(v):
                    return None
                pairs.append((k, v))
    else:
        return None

    if not pairs:
        return None

    block_children: list[Any] = [
        Assignment(key=k, value=v, line=assignment.line, column=assignment.column) for k, v in pairs
    ]
    return Block(
        key=assignment.key,
        children=block_children,
        line=assignment.line,
        column=assignment.column,
        leading_comments=list(assignment.leading_comments),
        trailing_comment=assignment.trailing_comment,
    )


def _apply_format_style(doc: Document, format_style: str | None, corrections: list[dict[str, Any]]) -> Document:
    """Return a Document transformed for the given format_style mode.

    Operates on a deep copy so the caller's AST is never mutated. For
    'expanded' / 'compact' applies the corresponding pre-pass; for any other
    value (including None and 'preserve') returns the deep copy unchanged.
    """
    new_doc = copy.deepcopy(doc)
    if format_style == "expanded":
        new_doc.sections = _expand_pass(new_doc.sections)
    elif format_style == "compact":
        new_doc.sections = _compact_pass(new_doc.sections, corrections, field_path="")
    return new_doc


def _emit_with_style(
    doc: Document,
    *,
    baseline_bytes: str | None = None,
    new_bytes: str | None = None,  # noqa: ARG001 -- reserved for future preserve variants (#377)
    format_style: str | None,
    corrections: list[dict[str, Any]],
) -> str:
    """Single canon orchestrator: produce canonical bytes for ``doc`` under
    ``format_style``.

    Strategy:
    - 'expanded' / 'compact' → apply AST pre-pass and emit().
    - 'preserve' (Strategy C short-circuit): emit canonically; if
      ``baseline_bytes`` is provided AND its canonical form equals the new
      canonical form, return ``baseline_bytes`` verbatim (zero diff for
      whitespace-only edits). Otherwise return the canonical bytes.
    - Anything else (including None) → emit(doc) (today's behaviour preserved
      byte-for-byte; this is the documented "current" sentinel).

    All non-shortcut paths route through one and only one ``emit()`` call on
    the doc (or its pre-pass projection), satisfying I1 Single-Canon Discipline.

    The ``new_bytes`` parameter is reserved for future preserve-mode variants
    (full Strategy A in #377) where source-span infrastructure may need access
    to the original input bytes; PR-A uses canonical-form comparison only.
    """
    if format_style in ("expanded", "compact"):
        projected = _apply_format_style(doc, format_style, corrections)
        canonical = emit(projected)
    else:
        canonical = emit(doc)

    if format_style == "preserve" and baseline_bytes is not None:
        try:
            # TODO(#377): pass the already-parsed baseline_doc through and
            # skip this reparse — Strategy A reworks preserve mode entirely
            # (CRS P3-01 / TMG advisory).
            baseline_canonical = emit(parse(baseline_bytes))
        except (LexerError, ParserError):
            return canonical
        if baseline_canonical == canonical:
            return baseline_bytes

    return canonical


# GH#263: Regex pattern for detecting NAME{qualifier} curly-brace annotations
# Matches: identifier characters followed by {qualifier_chars}
# The identifier pattern mirrors _is_valid_identifier_start/char from lexer.py
_CURLY_BRACE_ANNOTATION_PATTERN = re.compile(r"([A-Za-z_][A-Za-z0-9_./\-]*)\{([A-Za-z_][A-Za-z0-9_./\-]*)\}")

# GH#335: Regex pattern for detecting array-index notation in change paths.
# Matches keys containing bracket-enclosed integers like KEY[0], ITEMS[42], etc.
# Used to reject unresolvable paths instead of silently appending them.
_ARRAY_INDEX_RE = re.compile(r"\[\d+\]")

# GH#353: Regex pattern for parsing section-prefixed change paths.
# Matches: §<id>.<key>  or  §<id>::<name>.<key>
# Where <id> is a section number with optional suffix (e.g., "1", "2b", "3.5"),
# <name> is the section name (identifiers), and <key> is the child key to target.
# Only single-level child keys are supported (no deep nesting like §1.BLOCK.NESTED).
# Group layout: (1) section_id, (2) optional ::name, (3) child_key
# NOTE: The child key pattern excludes dots to prevent matching deep paths like §1.A.B.C.
# The section name in ::NAME allows dots (for names like v2.0) but the child key does NOT,
# since dots in the child position indicate hierarchical path traversal which is unsupported.
_SECTION_PATH_RE = re.compile(
    r"^§([0-9]+[a-zA-Z]?(?:\.[0-9]+)?)"  # §<id>: digits + optional letter suffix + optional .N
    r"(?:::([A-Za-z_][A-Za-z0-9_/\-]*))?"  # optional ::NAME (no dots in name)
    r"\.([A-Za-z_][A-Za-z0-9_/\-]*)$"  # .KEY (required child key, no dots)
)


class WriteTool(BaseTool):
    """MCP tool for octave_write - unified write operation for OCTAVE files."""

    # Security: allowed file extensions
    ALLOWED_EXTENSIONS = {".oct.md", ".octave", ".md"}

    def _repair_curly_brace_annotations(self, content: str) -> tuple[str, list[dict[str, Any]]]:
        """GH#263: Pre-process content to repair NAME{qualifier} -> NAME<qualifier>.

        I1 (Syntactic Fidelity): Only applies to Zone 1 (normalizing DSL) content.
        Quoted strings, literal zones (fenced blocks), and comments are protected.

        I4 (Transform Auditability): Every repair is logged with original and repaired
        syntax for full auditability.

        Args:
            content: Raw content that may contain curly-brace annotations

        Returns:
            Tuple of (repaired_content, list of correction records)
        """
        corrections: list[dict[str, Any]] = []

        # Build a set of character ranges that are protected from repair:
        # 1. Literal zones (``` fenced blocks) - Zone 3
        # 2. Quoted strings (text between "" after ::) - Zone 2
        # 3. Comments (// to end of line)
        protected: list[tuple[int, int]] = []

        # Find literal zone boundaries (``` fences)
        in_fence = False
        fence_start = 0
        offset = 0
        for line in content.split("\n"):
            line_start = offset
            offset += len(line) + 1  # +1 for the newline separator
            stripped = line.strip()
            if stripped.startswith("```"):
                if not in_fence:
                    in_fence = True
                    fence_start = line_start
                else:
                    in_fence = False
                    fence_end = line_start + len(line)
                    protected.append((fence_start, fence_end))

        # If fence was never closed, protect from fence_start to end
        if in_fence:
            protected.append((fence_start, len(content)))

        # Find quoted strings: text between "" on a line (after ::)
        quote_pattern = re.compile(r'"(?:[^"\\]|\\.)*"')
        for m in quote_pattern.finditer(content):
            protected.append((m.start(), m.end()))

        # Find comments: // to end of line
        comment_pattern = re.compile(r"//[^\n]*")
        for m in comment_pattern.finditer(content):
            protected.append((m.start(), m.end()))

        # Sort protected ranges for efficient lookup
        protected.sort()

        def _is_protected(pos: int) -> bool:
            """Check if a position falls within any protected range."""
            for start, end in protected:
                if start <= pos < end:
                    return True
                if start > pos:
                    break
            return False

        # Apply regex only to unprotected regions
        repaired = content
        # Collect matches that are in Zone 1 (unprotected)
        zone1_matches = []
        for match in _CURLY_BRACE_ANNOTATION_PATTERN.finditer(content):
            if not _is_protected(match.start()):
                zone1_matches.append(match)

        for match in zone1_matches:
            original = match.group(0)
            name = match.group(1)
            qualifier = match.group(2)
            suggested = f"{name}<{qualifier}>"

            corrections.append(
                {
                    "code": "W_REPAIR_CANDIDATE",
                    "tier": "LENIENT_PARSE",
                    "message": (
                        f"W_REPAIR_CANDIDATE::{original} repaired to {suggested}. "
                        f"Use angle brackets <> for annotation qualifiers, not curly braces {{}}."
                    ),
                    "before": original,
                    "after": suggested,
                    "safe": True,
                    "semantics_changed": False,
                }
            )

        # Replace only unprotected matches (process in reverse to preserve offsets)
        if corrections:
            for match in reversed(zone1_matches):
                name = match.group(1)
                qualifier = match.group(2)
                repaired = repaired[: match.start()] + f"{name}<{qualifier}>" + repaired[match.end() :]

        return repaired, corrections

    def _unwrap_markdown_code_fence(self, content: str) -> tuple[str, bool]:
        """Extract OCTAVE payload from a single outer markdown code fence.

        Accepts common fenced forms such as ```octave and ```markdown.
        Returns the original content when no full-document fence is present.
        """
        fence_match = re.match(r"^\s*```[^\n]*\n([\s\S]*?)\n```\s*$", content)
        if not fence_match:
            return content, False
        return fence_match.group(1), True

    def _build_unified_diff(self, before: str, after: str) -> str:
        """Build a compact unified diff string for diff-first responses."""
        before_lines = before.splitlines(keepends=True)
        after_lines = after.splitlines(keepends=True)
        diff_iter = unified_diff(before_lines, after_lines, fromfile="original", tofile="canonical", n=3)

        max_chars = 200_000
        out: list[str] = []
        total = 0
        for line in diff_iter:
            # Stop once we exceed the cap (streaming to avoid allocating huge diffs)
            if total + len(line) > max_chars:
                out.append("\n... (diff truncated)\n")
                break
            out.append(line)
            total += len(line)

        return "".join(out)

    def _wrap_plain_text_as_doc(self, raw_text: str, schema_name: str | None) -> tuple[str, list[dict[str, Any]]]:
        """Deterministically wrap plain text into a canonical OCTAVE carrier doc."""
        doc = Document(name="DOC")
        doc.meta = {"TYPE": schema_name or "UNKNOWN", "VERSION": "1.0"}
        doc.sections = [Block(key="BODY", children=[Assignment(key="RAW", value=raw_text)])]

        corrections: list[dict[str, Any]] = [
            {
                "code": "W_STRUCT_RAW_WRAP",
                "tier": "LENIENT_PARSE",
                "message": "Wrapped plain text into BODY: RAW carrier to produce parseable canonical OCTAVE",
                "safe": True,
                "semantics_changed": False,
            }
        ]
        return emit(doc), corrections

    def _localized_salvage(
        self, content: str, parse_error: str, schema_name: str | None
    ) -> tuple[Document, list[dict[str, Any]]]:
        """Issue #177: Attempt localized salvaging that preserves document structure.

        Instead of wrapping the entire file into a generic DOC with BODY::RAW,
        this method:
        1. Extracts and preserves the document envelope name (===NAME===)
        2. Parses line-by-line to identify which specific lines fail
        3. Preserves valid sections/fields
        4. Wraps only failing lines with _PARSE_ERROR_LINE_N markers

        Args:
            content: The original content that failed to parse
            parse_error: The error message from the failed parse attempt
            schema_name: Optional schema name for META.TYPE

        Returns:
            Tuple of (Document, corrections list)
        """
        corrections: list[dict[str, Any]] = []

        # Extract document envelope name from content
        envelope_match = re.search(rf"^===({ENVELOPE_ID_PATTERN})===\s*$", content, re.MULTILINE)
        doc_name = envelope_match.group(1) if envelope_match else "DOC"

        # Create document with extracted name
        doc = Document(name=doc_name)

        # Try to extract and preserve META block if present
        meta_match = re.search(
            r"^META:\s*\n((?:[ \t]+[^\n]+\n)*)",
            content,
            re.MULTILINE,
        )
        if meta_match:
            meta_content = meta_match.group(1)
            # Try to parse META fields
            meta_dict: dict[str, Any] = {}
            for line in meta_content.split("\n"):
                line = line.strip()
                if "::" in line:
                    key_value = line.split("::", 1)
                    if len(key_value) == 2:
                        key = key_value[0].strip()
                        value = key_value[1].strip().strip('"')
                        meta_dict[key] = value
            if meta_dict:
                doc.meta = meta_dict
            else:
                doc.meta = {"TYPE": schema_name or "UNKNOWN", "VERSION": "1.0"}
        else:
            doc.meta = {"TYPE": schema_name or "UNKNOWN", "VERSION": "1.0"}

        # Parse content line-by-line to identify valid vs failing lines
        # Issue #248: Track bracket depth so multi-line [...] blocks are tested
        # as complete units rather than line-by-line (which falsely rejects ] and ],)
        lines = content.split("\n")
        salvaged_sections: list[ASTNode] = []
        error_lines: list[tuple[int, str]] = []
        current_valid_lines: list[str] = []
        bracket_depth = 0
        bracket_block_lines: list[str] = []
        bracket_block_start_indices: list[int] = []

        # Skip envelope and end markers for line-by-line processing
        in_content = False
        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Track envelope markers
            if re.match(r"^===.+===\s*$", stripped):
                in_content = not in_content
                continue

            # Skip META block lines (already processed)
            if stripped.startswith("META:") or (meta_match and line in meta_match.group(0)):
                continue
            if stripped == "---":  # META separator
                continue

            if not in_content:
                continue

            # Issue #248: Track bracket depth for multi-line bracket blocks.
            # Lines like `],` and `]` are only valid inside an open bracket context.
            # When inside brackets (depth > 0), accumulate lines and test the
            # complete block once all brackets are balanced.
            if stripped:
                # Count bracket transitions on this line, skipping brackets
                # inside quoted strings to avoid false depth changes.
                line_opens = 0
                line_closes = 0
                in_quote = False
                escape_next = False
                for ch in stripped:
                    if escape_next:
                        escape_next = False
                        continue
                    if ch == "\\":
                        escape_next = True
                        continue
                    if ch == '"':
                        in_quote = not in_quote
                        continue
                    if not in_quote:
                        if ch == "[":
                            line_opens += 1
                        elif ch == "]":
                            line_closes += 1

                if bracket_depth > 0:
                    # Inside a bracket block - accumulate unconditionally
                    bracket_block_lines.append(line)
                    bracket_block_start_indices.append(i)
                    bracket_depth += line_opens - line_closes

                    if bracket_depth <= 0:
                        # Brackets balanced - flush accumulated valid lines then
                        # test the complete bracket block
                        bracket_depth = 0

                        # First, flush any pre-bracket valid lines
                        if current_valid_lines:
                            try:
                                vbc = "===TEST===\n" + "\n".join(current_valid_lines) + "\n===END==="
                                vd = parse(vbc)
                                salvaged_sections.extend(vd.sections)
                            except Exception:
                                for vl in current_valid_lines:
                                    if vl.strip():
                                        salvaged_sections.append(Assignment(key="_SALVAGED_LINE", value=vl))

                        # Now test the bracket block as a complete unit
                        # (opening line was stored as first bracket_block_lines entry)
                        try:
                            block_content = "===TEST===\n" + "\n".join(bracket_block_lines) + "\n===END==="
                            valid_doc = parse(block_content)
                            salvaged_sections.extend(valid_doc.sections)
                        except Exception:
                            # Bracket block failed as a unit - wrap as a single
                            # salvaged assignment preserving the full block text
                            block_text = "\n".join(bracket_block_lines)
                            salvaged_sections.append(Assignment(key="_SALVAGED_BLOCK", value=block_text))

                        current_valid_lines = []
                        bracket_block_lines = []
                        bracket_block_start_indices = []
                    continue

                if line_opens > line_closes:
                    # Opening a new multi-line bracket block
                    bracket_depth = line_opens - line_closes
                    bracket_block_lines = [line]
                    bracket_block_start_indices = [i]
                    continue

                # Normal line (no open bracket context) - test in isolation
                test_content = f"===TEST===\n{line}\n===END==="
                try:
                    parse(test_content)
                    current_valid_lines.append(line)
                except Exception:
                    # This line has an error - record it
                    error_lines.append((i, line))
                    # Flush any accumulated valid lines before the error
                    if current_valid_lines:
                        # Try to parse accumulated valid lines as a block
                        try:
                            valid_block_content = "===TEST===\n" + "\n".join(current_valid_lines) + "\n===END==="
                            valid_doc = parse(valid_block_content)
                            salvaged_sections.extend(valid_doc.sections)
                        except Exception:
                            # Even accumulated lines failed together - wrap as error
                            for vl in current_valid_lines:
                                salvaged_sections.append(Assignment(key="_SALVAGED_LINE", value=vl))
                        current_valid_lines = []
            else:
                # Empty line - keep in current valid block
                if current_valid_lines:
                    current_valid_lines.append(line)

        # Flush any remaining bracket block (unbalanced brackets at end of doc)
        if bracket_block_lines:
            # First flush pre-bracket valid lines
            if current_valid_lines:
                try:
                    vbc = "===TEST===\n" + "\n".join(current_valid_lines) + "\n===END==="
                    vd = parse(vbc)
                    salvaged_sections.extend(vd.sections)
                except Exception:
                    for vl in current_valid_lines:
                        if vl.strip():
                            salvaged_sections.append(Assignment(key="_SALVAGED_LINE", value=vl))
            # Try bracket block as unit; if it fails, wrap as single error
            try:
                block_content = "===TEST===\n" + "\n".join(bracket_block_lines) + "\n===END==="
                valid_doc = parse(block_content)
                salvaged_sections.extend(valid_doc.sections)
            except Exception:
                block_text = "\n".join(bracket_block_lines)
                salvaged_sections.append(Assignment(key="_SALVAGED_BLOCK", value=block_text))
            current_valid_lines = []

        # Flush remaining valid lines
        if current_valid_lines:
            try:
                valid_block_content = "===TEST===\n" + "\n".join(current_valid_lines) + "\n===END==="
                valid_doc = parse(valid_block_content)
                salvaged_sections.extend(valid_doc.sections)
            except Exception:
                for vl in current_valid_lines:
                    if vl.strip():
                        salvaged_sections.append(Assignment(key="_SALVAGED_LINE", value=vl))

        # Add error markers for each failing line
        for line_num, line_content in error_lines:
            # I1 (Syntactic Fidelity): emit_value handles escaping, don't pre-escape
            # Pre-escaping would cause double-escaping of backslashes and quotes
            salvaged_sections.append(Assignment(key=f"_PARSE_ERROR_LINE_{line_num}", value=line_content))
            corrections.append(
                {
                    "code": "W_SALVAGE_LINE",
                    "tier": "LENIENT_PARSE",
                    "message": f"Line {line_num} failed to parse: wrapped as _PARSE_ERROR_LINE_{line_num}",
                    "line": line_num,
                    "original": line_content,
                    "safe": True,
                    "semantics_changed": False,
                }
            )

        doc.sections = salvaged_sections if salvaged_sections else []

        # Add overall salvage correction
        corrections.insert(
            0,
            {
                "code": "W_SALVAGE_LOCALIZED",
                "tier": "LENIENT_PARSE",
                "message": f"Localized salvage: preserved document envelope '{doc_name}', "
                f"salvaged {len(salvaged_sections) - len(error_lines)} valid elements, "
                f"wrapped {len(error_lines)} failing line(s)",
                "safe": True,
                "semantics_changed": False,
                "parse_error": parse_error,
            },
        )

        return doc, corrections

    def _map_parse_warnings_to_corrections(self, warnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert parser/lexer warnings (I4) into octave_write corrections entries."""
        corrections: list[dict[str, Any]] = []
        for w in warnings:
            w_type = w.get("type", "")
            if w_type == "normalization":
                corrections.append(
                    {
                        "code": "W002",
                        "tier": "NORMALIZATION",
                        "message": f"ASCII operator -> Unicode: {w.get('original', '')} -> {w.get('normalized', '')}",
                        "line": w.get("line", 0),
                        "column": w.get("column", 0),
                        "before": w.get("original", ""),
                        "after": w.get("normalized", ""),
                        "safe": True,
                        "semantics_changed": False,
                    }
                )
                continue

            if w_type == "lenient_parse":
                subtype = w.get("subtype", "unknown")

                # GH#305: Constructor misuse warnings are advisory
                # No data loss, no auto-fix — just advisory per I1
                if subtype == "constructor_misuse":
                    corrections.append(
                        {
                            "code": "W_CONSTRUCTOR_MISUSE",
                            "tier": "LENIENT_PARSE",
                            "message": w.get("message", f"Constructor misuse: {w.get('key', '?')}"),
                            "line": w.get("line", 0),
                            "column": w.get("column", 0),
                            "key": w.get("key", ""),
                            "value": w.get("value", ""),
                            "safe": True,
                            "semantics_changed": False,
                        }
                    )
                # GH#310: PATTERN/REGEX auto-quoting is advisory + safe
                # Value was bare, emitter will auto-quote for I1 fidelity
                elif subtype == "pattern_autoquote":
                    corrections.append(
                        {
                            "code": "W_PATTERN_AUTOQUOTE",
                            "tier": "LENIENT_PARSE",
                            "message": w.get(
                                "message",
                                f"PATTERN/REGEX value auto-quoted: {w.get('key', '?')}",
                            ),
                            "line": w.get("line", 0),
                            "column": w.get("column", 0),
                            "key": w.get("key", ""),
                            "value": w.get("value", ""),
                            "safe": True,
                            "semantics_changed": False,
                        }
                    )
                # GH#294: Duplicate key warnings get special treatment
                # Data loss = safe:false, semantics_changed:true
                elif subtype == "duplicate_key":
                    corrections.append(
                        {
                            "code": "W_DUPLICATE_KEY",
                            "tier": "LENIENT_PARSE",
                            "message": w.get("message", f"Duplicate key: {w.get('key', '?')}"),
                            "line": w.get("duplicate_line", w.get("line", 0)),
                            "column": w.get("column", 0),
                            "key": w.get("key", ""),
                            "all_lines": w.get("all_lines", []),
                            "safe": False,
                            "semantics_changed": True,
                        }
                    )
                # GH#348: Numeric key dropped = silent data loss (I4 violation)
                # Numeric keys are not valid OCTAVE identifiers; content is
                # dropped from canonical output. Must be safe:false,
                # semantics_changed:true so agents detect the loss.
                elif subtype == "numeric_key_dropped":
                    corrections.append(
                        {
                            "code": "W_NUMERIC_KEY_DROPPED",
                            "tier": "LENIENT_PARSE",
                            "message": w.get(
                                "message",
                                f"Numeric key dropped: {w.get('key', '?')}",
                            ),
                            "line": w.get("line", 0),
                            "column": w.get("column", 0),
                            "key": w.get("key", ""),
                            "value": w.get("value", ""),
                            "safe": False,
                            "semantics_changed": True,
                        }
                    )
                # GH#349: Bare line dropped = silent data loss (I4 violation)
                # Must be safe:false, semantics_changed:true so agents detect loss
                elif subtype == "bare_line_dropped":
                    original = w.get("original", "?")
                    corrections.append(
                        {
                            "code": W_BARE_LINE_DROPPED,
                            "tier": "LENIENT_PARSE",
                            "message": f"Bare line dropped: '{original}' has no :: or : operator and was silently removed",
                            "line": w.get("line", 0),
                            "column": w.get("column", 0),
                            "before": original,
                            "after": "",
                            "safe": False,
                            "semantics_changed": True,
                        }
                    )
                else:
                    corrections.append(
                        {
                            "code": f"W_LENIENT_{subtype}".upper(),
                            "tier": "LENIENT_PARSE",
                            "message": f"Lenient parse: {subtype}",
                            "line": w.get("line", 0),
                            "column": w.get("column", 0),
                            "before": w.get("original", ""),
                            "after": w.get("result", ""),
                            "safe": True,
                            "semantics_changed": False,
                        }
                    )
        return corrections

    def _error_envelope(
        self,
        target_path: str,
        errors: list[dict[str, Any]],
        corrections: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Build consistent error envelope with all required fields.

        Args:
            target_path: The target file path
            errors: List of error records
            corrections: Optional list of corrections (defaults to empty list)

        Returns:
            Complete error envelope with all required fields per D2 design
        """
        # I5 (Schema Sovereignty): validation_status must be UNVALIDATED to make bypass visible
        # "Schema bypass shall be visible, never silent" - North Star I5
        return {
            "status": "error",
            "path": target_path,
            "canonical_hash": "",
            "corrections": corrections if corrections is not None else [],
            "diff": "",
            "diff_unified": "",
            "errors": errors,
            "validation_status": "UNVALIDATED",  # I5: Explicit bypass - no schema validator yet
            "validation_hint": self._build_validation_hint(),  # GH#352+361r3: guidance with available schemas
        }

    def get_name(self) -> str:
        """Get tool name."""
        return "octave_write"

    def get_description(self) -> str:
        """Get tool description."""
        return (
            "Unified entry point for writing OCTAVE files. "
            "Handles creation (new files) and modification (existing files). "
            "Use content for full payload, changes for delta updates. "
            "Omit both content and changes to normalize an existing file in-place. "
            "Replaces octave_create and octave_amend."
        )

    def get_input_schema(self) -> dict[str, Any]:
        """Get input schema."""
        schema = SchemaBuilder()

        schema.add_parameter("target_path", "string", required=True, description="File path to write to")

        schema.add_parameter(
            "content",
            "string",
            required=False,
            description="Full content for new files or overwrites. Accepts raw OCTAVE or a single markdown fenced code block. Mutually exclusive with changes.",
        )

        schema.add_parameter(
            "changes",
            "object",
            required=False,
            description=(
                "Dictionary of field updates for existing files. "
                "Each value is either a bare value (full replacement, default) "
                "or a $op descriptor: "
                '{"$op":"DELETE"} removes the target; '
                '{"$op":"APPEND","value":x} pushes x (or each item of list x) '
                "onto the end of an array target; "
                '{"$op":"PREPEND","value":x} unshifts onto the front of an array; '
                '{"$op":"MERGE","value":{...}} deep-merges into a block target, '
                "preserving unmentioned children (use inner $op:DELETE to remove). "
                "Op/target-type mismatches return E_OP_TARGET_MISMATCH; "
                "missing paths return E_UNRESOLVABLE_PATH (no auto-create, I3); "
                "malformed descriptors return E_INVALID_OP_DESCRIPTOR. "
                "Paths support: top-level KEY, META.FIELD, PARENT.CHILD into a "
                "top-level Block, and §N.KEY / §N::NAME.KEY into Sections. "
                "(GH#373)"
            ),
        )

        schema.add_parameter(
            "mutations",
            "object",
            required=False,
            description="META field overrides (applies to both modes).",
        )

        schema.add_parameter(
            "base_hash",
            "string",
            required=False,
            description="Expected SHA-256 hash of existing file for consistency check (CAS).",
        )

        # GH#355: List common schemas in description so agents know what's available
        schema.add_parameter(
            "schema",
            "string",
            required=False,
            description=(
                "Schema name for validation (I5). "
                "Common schemas: META, SKILL, CRS_REVIEW, COGNITION_DEFINITION, DEBATE_TRANSCRIPT. "
                "Use 'frozen@<hash>' or 'latest' for hermetic resolution. "
                "If an unknown schema is provided, the response includes available_schemas."
            ),
        )

        schema.add_parameter(
            "debug_grammar",
            "boolean",
            required=False,
            description="If True, include compiled regex/grammar in output for debugging constraint evaluation.",
        )

        schema.add_parameter(
            "grammar_hint",
            "boolean",
            required=False,
            description="If True and validation returns INVALID, include compiled GBNF grammar in response to guide correction.",
        )

        schema.add_parameter(
            "lenient",
            "boolean",
            required=False,
            # GH#359: Explicitly state default value so agents know lenient is opt-in
            description="If True, enable deterministic lenient parsing + optional schema repairs. Default: false (strict parsing).",
        )

        schema.add_parameter(
            "corrections_only",
            "boolean",
            required=False,
            description="If True, return corrections/diff without writing to disk (dry run).",
        )

        # GH#354: Accept dry_run as alias for corrections_only
        schema.add_parameter(
            "dry_run",
            "boolean",
            required=False,
            description="Alias for corrections_only. If True, return corrections/diff without writing to disk (default: false).",
        )

        schema.add_parameter(
            "parse_error_policy",
            "string",
            required=False,
            description='Policy when tokenization/parsing fails in lenient mode: "error" (default) or "salvage".',
            enum=["error", "salvage"],
        )

        # GH#376 PR-A: format_style toggle. Three modes are AST projections
        # of one canonical emit() (I1 Single-Canon Discipline).
        schema.add_parameter(
            "format_style",
            "string",
            required=False,
            description=(
                "Output formatting style for canonical emission. "
                "'preserve' (Strategy C): if new content is AST-equal to the existing file, "
                "write the baseline bytes verbatim — zero diff for whitespace-only edits. "
                "'expanded': lift inline-map shapes (KEY::[K::V,...]) into Block form before emit. "
                "'compact': collapse atom-only Blocks (no comments, arity-bounded) into "
                "inline-list-of-InlineMap form. Comment-bearing subtrees are vetoed and a "
                f"{W_COMPACT_REFUSED} record surfaces in corrections (I3 Mirror Constraint, "
                "I4 Auditability). When omitted, today's canonical behaviour is preserved exactly. "
                "(GH#376 PR-A — full preserve-mode strategy A is tracked separately as #377.)"
            ),
            enum=list(FORMAT_STYLE_VALUES),
        )

        return schema.build()

    def _validate_path(self, target_path: str) -> tuple[bool, str | None]:
        """Validate target path for security.

        Args:
            target_path: Path to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        path = Path(target_path)

        # Reject path traversal early (before any filesystem resolution)
        try:
            if any(part == ".." for part in path.parts):
                return False, "Path traversal not allowed (..)"
        except Exception as e:
            return False, f"Invalid path: {str(e)}"

        # Check for symlinks anywhere in path (security: prevent symlink-based exfiltration)
        # This includes both the final component AND any parent directories
        # Example attack: /tmp/link/secret.oct.md where 'link' is a symlink
        #
        # Strategy: Use resolve() to follow all symlinks and compare to original
        # If they differ, a symlink was traversed. However, we need to handle
        # system-level symlinks (like /var -> /private/var on macOS).
        #
        # Safe approach: Resolve both paths and compare. If they're different,
        # check if the resolved path is still within an acceptable system location.
        try:
            # Get absolute path (does not follow symlinks)
            absolute = path.absolute()

            # Resolve to canonical path (follows all symlinks)
            resolved = absolute.resolve(strict=False)

            # If paths differ after normalization, symlinks were involved
            # Now check each component to see if it's a user-controlled symlink
            if absolute != resolved:
                # Walk the path to find which component is the symlink
                current = Path("/")
                for part in absolute.parts[1:]:  # Skip root
                    current = current / part
                    if current.exists() and current.is_symlink():
                        # Found a symlink - check if it's a system symlink
                        # System symlinks are typically in the first 2-3 components
                        # and resolve to /private/* or other system paths
                        symlink_depth = len(Path(current).parts)
                        resolved_target = current.resolve()

                        # Allow common system symlinks:
                        # - /var -> /private/var (depth 1)
                        # - /tmp -> /private/tmp (depth 1)
                        # - /etc -> /private/etc (depth 1)
                        if symlink_depth <= 2 and str(resolved_target).startswith("/private/"):
                            # Likely system symlink, allow it
                            continue

                        # User-controlled symlink - reject
                        return (
                            False,
                            f"Symlinks in path are not allowed for security reasons: '{target_path}'. Use corrections_only=true to preview normalization without writing.",
                        )

        except Exception as e:
            return False, f"Path resolution failed: {str(e)}"

        # Check file extension
        if path.suffix not in self.ALLOWED_EXTENSIONS:
            compound_suffix = "".join(path.suffixes[-2:]) if len(path.suffixes) >= 2 else path.suffix
            if compound_suffix not in self.ALLOWED_EXTENSIONS:
                allowed = ", ".join(sorted(self.ALLOWED_EXTENSIONS))
                return False, f"Invalid file extension. Allowed: {allowed}"

        return True, None

    def _compute_hash(self, content: str) -> str:
        """Compute SHA-256 hash of content.

        Args:
            content: Content to hash

        Returns:
            Hex digest of SHA-256 hash
        """
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _list_available_schemas(self) -> list[str]:
        """Enumerate all available schema names from builtins and search paths.

        GH#355: Returns a sorted list of schema names that agents can use
        with the schema parameter. Combines builtin dict schemas and
        file-based schemas from search paths.

        Returns:
            Sorted list of available schema name strings.
        """
        names: set[str] = set()

        # Builtin dict schemas (e.g. META)
        names.update(BUILTIN_SCHEMA_DEFINITIONS.keys())

        # File-based schemas from search paths
        for search_path in get_schema_search_paths():
            for schema_file in search_path.glob("*.oct.md"):
                # Schema name is derived from filename: meta.oct.md -> META
                name = schema_file.stem  # e.g. "meta" from "meta.oct.md"
                # Remove .oct suffix if present (stem of .oct.md is "meta.oct" not "meta")
                if name.endswith(".oct"):
                    name = name[:-4]
                names.add(name.upper())

        return sorted(names)

    def _build_validation_hint(self) -> str:
        """Build UNVALIDATED hint including available schema names.

        GH#361r3: Agents receiving UNVALIDATED status need to know which
        schema names are valid so they can self-correct. Appends the
        available schemas list to the base hint text.

        Returns:
            Hint string with available schemas enumerated.
        """
        schemas = self._list_available_schemas()
        if schemas:
            return f"{_VALIDATION_HINT_BASE} Available schemas: {', '.join(schemas)}"
        return _VALIDATION_HINT_BASE

    def _track_corrections(
        self, original: str, canonical: str, tokenize_repairs: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Track normalization corrections.

        Args:
            original: Original content
            canonical: Canonical content
            tokenize_repairs: Repairs from tokenization

        Returns:
            List of correction records with W001-W005 codes
        """
        corrections = []

        # Map tokenize repairs to W002 (ASCII operator -> Unicode)
        for token_repair in tokenize_repairs:
            corrections.append(
                {
                    "code": "W002",
                    "message": f"ASCII operator -> Unicode: {token_repair.get('original', '')} -> {token_repair.get('normalized', '')}",
                    "line": token_repair.get("line", 0),
                    "column": token_repair.get("column", 0),
                    "before": token_repair.get("original", ""),
                    "after": token_repair.get("normalized", ""),
                }
            )

        return corrections

    def _validate_change_paths(self, changes: dict[str, Any], doc: Any | None = None) -> list[dict[str, Any]]:
        """GH#335/GH#353: Validate change paths are resolvable before applying.

        Detects paths that _apply_changes cannot resolve to AST nodes and
        returns error records instead of silently appending literal dot-path
        lines to the document.

        GH#353: Section-prefixed paths (§N.KEY or §N::NAME.KEY) are now valid
        when they match a single child key within an existing section. When
        ``doc`` is provided, section existence and name matching are verified.

        I3 (Mirror Constraint): reflect only present, create nothing.
        Silent append of unresolvable paths fabricates content, violating I3.

        Unresolvable path patterns:
        1. Array-index notation: KEY[N] -- _apply_changes has no array element
           resolution; would silently append 'KEY[N]::"value"' as a literal key.
        2. Invalid section paths: §N without child key, or deep nested §N.A.B.C
           -- only §N.KEY and §N::NAME.KEY are supported (GH#353).
        3. Non-META dot-paths: X.Y.Z (where X != "META") -- _apply_changes only
           resolves META.FIELD; other dot-paths would be treated as literal keys
           containing dots, which is almost certainly not what the caller intended.

        Args:
            changes: Dictionary of change paths to validate
            doc: Optional parsed AST document for section existence validation.
                When provided, section paths are verified against actual sections.

        Returns:
            List of error dicts for unresolvable paths (empty if all paths are valid)
        """
        errors: list[dict[str, Any]] = []

        # GH#373: Pre-pass for op-descriptor shape validation. Catches malformed
        # descriptors (unknown $op, missing 'value', MERGE-with-non-dict) before
        # path resolution so the caller sees descriptor errors even when the path
        # itself is fine. Op/target-type mismatch is checked further below
        # (requires AST lookup of the resolved target).
        op_descriptors: dict[str, tuple[str | None, Any]] = {}
        for key, raw_value in changes.items():
            op, payload, op_err = _extract_op_descriptor(raw_value)
            if op_err is not None:
                err = {**op_err, "message": f"Invalid descriptor for '{key}': {op_err['message']}"}
                errors.append(err)
                continue
            op_descriptors[key] = (op, payload)

        for key in changes:
            # Skip keys that already failed descriptor validation; their target
            # type cannot be safely inspected in op/target-mismatch checks.
            if key not in op_descriptors:
                continue

            # Pattern 1: Array-index notation (e.g., KEY[4], §2.X.Y[0])
            if _ARRAY_INDEX_RE.search(key):
                errors.append(
                    {
                        "code": "E_UNRESOLVABLE_PATH",
                        "message": (
                            f"Unresolvable change path '{key}': array-index notation "
                            f"(e.g., KEY[N]) is not supported by the changes parameter. "
                            f"The changes parameter can only update top-level keys and "
                            f"META fields (via META.FIELD dot-notation). To modify array "
                            f"elements, use the content parameter with the full document."
                        ),
                    }
                )
                continue

            # Pattern 2: Section-prefixed paths
            # GH#353: Valid section paths (§N.KEY or §N::NAME.KEY) are now resolvable.
            # Only reject invalid section path patterns.
            if key.startswith("§"):
                match = _SECTION_PATH_RE.match(key)
                if not match:
                    # Invalid section path: either bare §N, or deep nested §N.A.B.C,
                    # or malformed syntax.
                    errors.append(
                        {
                            "code": "E_UNRESOLVABLE_PATH",
                            "message": (
                                f"Unresolvable change path '{key}': invalid section path. "
                                f"Section paths must use §N.KEY or §N::NAME.KEY format "
                                f"(single child key only). Deep nested paths like "
                                f"§N.BLOCK.NESTED are not supported. To modify deeply "
                                f"nested fields, use the content parameter with the full document."
                            ),
                        }
                    )
                elif doc is not None:
                    # GH#353: Verify the section actually exists in the document.
                    section_id, section_name, _child_key = match.groups()
                    section = self._find_section(doc, section_id, section_name)
                    if section is None:
                        name_detail = f" with name '{section_name}'" if section_name else ""
                        errors.append(
                            {
                                "code": "E_UNRESOLVABLE_PATH",
                                "message": (
                                    f"Unresolvable change path '{key}': section "
                                    f"§{section_id}{name_detail} not found in document."
                                ),
                            }
                        )
                continue

            # Pattern 3: Non-META hierarchical dot-paths.
            # META.FIELD is handled by _apply_changes.
            #
            # GH#347 carve-out: Single-dot keys like P1.1 or v2.0 are valid OCTAVE
            # identifiers (the lexer allows dots in identifiers).
            # GH#369: AST-aware resolution distinguishes "identifier with dots"
            # from "PARENT.CHILD path expression":
            #   - 2+ dots, non-META: always reject (deep nested paths unsupported).
            #   - exactly 1 dot, non-META:
            #       * If PARENT is a top-level Block in the AST -> treat dot as
            #         path separator. CHILD must resolve inside that Block,
            #         otherwise reject with E_UNRESOLVABLE_PATH.
            #       * Else if the literal dotted key already exists as a flat
            #         top-level Assignment -> accept (modify in place).
            #       * Else if doc is None (no AST available for resolution) ->
            #         accept (defer; legacy behaviour relied on this for the
            #         GH#347 carve-out without parsing).
            #       * Else -> reject (no resolvable target).
            if "." in key and not key.startswith("META."):
                if key.count(".") >= 2:
                    errors.append(
                        {
                            "code": "E_UNRESOLVABLE_PATH",
                            "message": (
                                f"Unresolvable change path '{key}': nested dot-path notation "
                                f"is only supported for META fields (e.g., META.STATUS). "
                                f"Other dot-paths cannot be resolved to AST nodes. To modify "
                                f"nested fields, use the content parameter with the full document."
                            ),
                        }
                    )
                    continue

                # Exactly one dot, non-META. AST-aware resolution.
                if doc is not None:
                    parent_key, _, child_key = key.partition(".")
                    parent_block = self._find_block(doc, parent_key)
                    if parent_block is not None:
                        # PARENT exists as a top-level Block. Treat dot as path
                        # separator; CHILD must resolve inside the Block.
                        if not any(isinstance(c, Assignment) and c.key == child_key for c in parent_block.children):
                            # GH#370: Before rejecting, check if the literal dotted key
                            # exists as a flat assignment (conflict scenario from GH#369).
                            # If the flat key exists, applier will handle it; validator
                            # must not reject to maintain contract with applier.
                            flat_match = any(isinstance(s, Assignment) and s.key == key for s in doc.sections)
                            if flat_match:
                                # Conflicted document: Block + flat dotted assignment coexist.
                                # Applier will route to flat assignment (GH#347 carve-out).
                                # Tolerate here for consistency; validator will emit W_DUPLICATE_TARGET.
                                continue
                            # No flat fallback; reject the unresolvable path.
                            errors.append(
                                {
                                    "code": "E_UNRESOLVABLE_PATH",
                                    "message": (
                                        f"Unresolvable change path '{key}': '{parent_key}' is a "
                                        f"top-level block but does not contain a child assignment "
                                        f"named '{child_key}'. To add a new child field to a block, "
                                        f"use the content parameter with the full document."
                                    ),
                                }
                            )
                            continue
                        # PARENT.CHILD resolves inside the block. _apply_changes
                        # will route to _apply_block_change.
                        continue
                    # PARENT is not a top-level Block. The key is acceptable
                    # only if it already exists as a flat top-level Assignment
                    # (preserves the GH#347 single-identifier carve-out for
                    # legitimate dotted identifiers like P1.1).
                    flat_match = any(isinstance(s, Assignment) and s.key == key for s in doc.sections)
                    if flat_match:
                        continue
                    errors.append(
                        {
                            "code": "E_UNRESOLVABLE_PATH",
                            "message": (
                                f"Unresolvable change path '{key}': '{parent_key}' is not a "
                                f"top-level block and the literal key '{key}' does not exist "
                                f"as a flat top-level assignment. If you intended a nested "
                                f"field, use the content parameter with the full document. "
                                f"If you intended a flat top-level key, ensure it exists "
                                f"or pass content= to create it."
                            ),
                        }
                    )
                    continue
                # doc is None: cannot do AST-aware resolution. Fall through and
                # accept (legacy behaviour). _apply_changes will resolve.

        # GH#373: Op/target-type compatibility post-pass.
        # For each key with a recognised $op, look up the resolved target in the
        # AST and verify the op is compatible with the target type.
        # I5 (Schema Sovereignty): mismatches surface as visible E_OP_TARGET_MISMATCH
        # errors, never silent coercion.
        # I3 (Mirror Constraint): MERGE/APPEND/PREPEND on a missing path is
        # rejected (no auto-create) via E_UNRESOLVABLE_PATH.
        # Already-errored keys are skipped to keep error reports focused.
        already_errored_keys = {
            k
            for k in changes
            if any(
                # Heuristic: any error message that quotes this key counts.
                # Keeps the post-pass from double-reporting.
                f"'{k}'" in (e.get("message") or "")
                for e in errors
            )
        }
        if doc is not None:
            for key, (op, _payload) in op_descriptors.items():
                if op is None or op == "DELETE":
                    # Bare values: no target-type constraint.
                    # DELETE is permitted on any target (idempotent for missing).
                    continue
                if key in already_errored_keys:
                    continue

                target_kind, target_node = self._resolve_target_type(doc, key)
                if target_kind == "missing":
                    errors.append(
                        {
                            "code": "E_UNRESOLVABLE_PATH",
                            "message": (
                                f"Unresolvable change path '{key}': $op {op} "
                                f"requires an existing target, but no node "
                                f"resolves at this path. Auto-create is forbidden "
                                f"by I3 (Mirror Constraint); use content= to add "
                                f"new structure."
                            ),
                        }
                    )
                    continue

                if op in ("APPEND", "PREPEND"):
                    if target_kind != "array":
                        errors.append(
                            {
                                "code": "E_OP_TARGET_MISMATCH",
                                "message": (
                                    f"$op {op} requires an array target at '{key}', "
                                    f"but found {target_kind}. APPEND/PREPEND only "
                                    f"apply to list-valued assignments."
                                ),
                            }
                        )
                elif op == "MERGE":
                    if target_kind not in ("block", "section", "meta"):
                        errors.append(
                            {
                                "code": "E_OP_TARGET_MISMATCH",
                                "message": (
                                    f"$op MERGE requires a block (dict) target at "
                                    f"'{key}', but found {target_kind}. MERGE only "
                                    f"applies to top-level Blocks, Sections, or META."
                                ),
                            }
                        )

        return errors

    def _resolve_target_type(self, doc: Any, key: str) -> tuple[str, Any]:
        """GH#373: Classify the AST target a change-path resolves to.

        Returns:
            (kind, node) where kind is one of:
              - "missing": no target node exists at this path.
              - "array":   target is a list-valued Assignment (ListValue / list).
              - "scalar":  target is a non-list, non-map Assignment value.
              - "map":     target is an InlineMap or dict Assignment value.
              - "block":   target is a top-level Block.
              - "section": target is a Section node.
              - "meta":    target is the document's META block as a whole.
            node is the resolved AST node (or value), or None when missing.

        Used by _validate_change_paths to enforce op/target-type compatibility.
        Path patterns mirror the resolution logic in _apply_changes.
        """
        # META.FIELD -> doc.meta[field]
        if key.startswith("META.") and len(key) > 5:
            field_name = key[5:]
            if field_name in doc.meta:
                value = doc.meta[field_name]
                if isinstance(value, ListValue | list):
                    return ("array", value)
                if isinstance(value, InlineMap) or (isinstance(value, dict) and not _is_op_descriptor(value)):
                    return ("map", value)
                return ("scalar", value)
            return ("missing", None)

        # Top-level META as a whole -> meta block.
        if key == "META":
            return ("meta", doc.meta)

        # §N.KEY or §N::NAME.KEY -> child Assignment within Section.
        if key.startswith("§"):
            match = _SECTION_PATH_RE.match(key)
            if match is not None:
                section_id, section_name, child_key = match.groups()
                section = self._find_section(doc, section_id, section_name)
                if section is None:
                    return ("missing", None)
                for child in section.children:
                    if isinstance(child, Assignment) and child.key == child_key:
                        kind = _target_type_for_assignment(child.value)
                        return (kind, child)
                    if isinstance(child, Block) and child.key == child_key:
                        return ("block", child)
                return ("missing", None)
            return ("missing", None)

        # PARENT.CHILD where PARENT is a top-level Block -> nested Assignment.
        if "." in key and key.count(".") == 1:
            parent_key, _, child_key = key.partition(".")
            parent_block = self._find_block(doc, parent_key)
            if parent_block is not None:
                for child in parent_block.children:
                    if isinstance(child, Assignment) and child.key == child_key:
                        kind = _target_type_for_assignment(child.value)
                        return (kind, child)
                    if isinstance(child, Block) and child.key == child_key:
                        return ("block", child)
                # PARENT is a Block but CHILD missing inside it.
                # Fall through to flat-key lookup (GH#370 conflicted-doc carve-out).
            # Either PARENT is not a Block, or CHILD missing inside PARENT block.
            # Try literal flat top-level Assignment (GH#347 dotted identifiers).
            for node in doc.sections:
                if isinstance(node, Assignment) and node.key == key:
                    kind = _target_type_for_assignment(node.value)
                    return (kind, node)
            return ("missing", None)

        # Bare top-level KEY.
        for node in doc.sections:
            if isinstance(node, Assignment) and node.key == key:
                kind = _target_type_for_assignment(node.value)
                return (kind, node)
            if isinstance(node, Block) and node.key == key:
                return ("block", node)
            if isinstance(node, Section) and node.key == key:
                return ("section", node)
        return ("missing", None)

    def _find_block(self, doc: Any, block_key: str) -> Block | None:
        """Find a top-level Block node in doc.sections by key.

        GH#369: Companion to _find_section for nested Block path resolution.
        Walks doc.sections looking for a Block whose .key matches block_key.
        Only inspects direct children of the document (top-level blocks);
        deeper nesting is intentionally not searched, mirroring the single-
        level child-key constraint of _find_section.

        Args:
            doc: Parsed AST document
            block_key: Block key name to match (e.g., "NAV")

        Returns:
            Matching Block node, or None if not found.
        """
        for node in doc.sections:
            if isinstance(node, Block) and node.key == block_key:
                return node
        return None

    def _apply_block_change(
        self,
        doc: Any,
        original_key: str,
        block_key: str,
        child_key: str,
        new_value: Any,
    ) -> None:
        """Apply a change to a child Assignment within a top-level Block node.

        GH#369: Mirrors _apply_section_change for top-level Block nodes.
        Used when the change key is PARENT.CHILD and PARENT is a top-level
        Block. Supports set/replace and DELETE sentinel for the child
        Assignment. Modifying nested Block-within-Block targets and array
        merge ops are explicitly out of scope.

        Args:
            doc: Parsed AST document
            original_key: The original changes key (for error messages)
            block_key: Top-level block key to navigate into
            child_key: Child key within the block to modify
            new_value: New value (with tri-state semantics)

        Raises:
            ValueError: If the block cannot be found, or if child_key resolves
                to a Block (nested block-in-block modification not supported).
                _validate_change_paths runs first so these are safety nets.
        """
        block = self._find_block(doc, block_key)
        if block is None:
            raise ValueError(
                [
                    {
                        "code": "E_UNRESOLVABLE_PATH",
                        "message": (f"Block '{block_key}' not found in document for " f"change path '{original_key}'."),
                    }
                ]
            )

        # Reject Block-in-Block targets (mirrors _apply_section_change I3 guard).
        for child in block.children:
            if isinstance(child, Block) and child.key == child_key:
                raise ValueError(
                    [
                        {
                            "code": "E_BLOCK_TARGET",
                            "message": (
                                f"Cannot modify '{child_key}' in block '{block_key}' via "
                                f"changes-mode: it is a Block (nested structure), not an "
                                f"Assignment. Use content= to rewrite the block, or target "
                                f"individual keys within the inner block."
                            ),
                        }
                    ]
                )

        # GH#373: Op-aware dispatch. Bare values fall through to legacy
        # full-replacement; descriptors (DELETE/APPEND/PREPEND) take their op
        # branch. MERGE on a nested Assignment is unreachable here because
        # _validate_change_paths rejects it via E_OP_TARGET_MISMATCH.
        op, payload, _ = _extract_op_descriptor(new_value)

        if op == "DELETE" or _is_delete_sentinel(new_value):
            block.children = [c for c in block.children if not (isinstance(c, Assignment) and c.key == child_key)]
            return

        if op in ("APPEND", "PREPEND"):
            for child in block.children:
                if isinstance(child, Assignment) and child.key == child_key:
                    _apply_array_op_inplace(child, op, payload)
                    return
            # Validator should have caught missing target; safety net.
            raise ValueError(
                [
                    {
                        "code": "E_UNRESOLVABLE_PATH",
                        "message": (
                            f"$op {op} target '{child_key}' not found in block "
                            f"'{block_key}' (path '{original_key}')."
                        ),
                    }
                ]
            )

        # Legacy full-value replacement (or new Assignment if missing).
        normalized_value = _normalize_value_for_ast(new_value)
        for child in block.children:
            if isinstance(child, Assignment) and child.key == child_key:
                child.value = normalized_value
                return

        # If we reach here, _validate_change_paths missed the case. Add as new
        # child Assignment to keep behaviour consistent with _apply_section_change.
        block.children.append(Assignment(key=child_key, value=normalized_value))

    def _find_section(
        self,
        doc: Any,
        section_id: str,
        section_name: str | None,
    ) -> Section | None:
        """Find a Section node in doc.sections by ID and optional name.

        GH#353: Navigates doc.sections to locate a Section matching the given
        section_id. If section_name is provided, also verifies the name matches.

        Args:
            doc: Parsed AST document
            section_id: Section number to match (e.g., "1", "2b", "3.5")
            section_name: Optional section name to verify (e.g., "IDENTITY")

        Returns:
            Matching Section node, or None if not found / name mismatch.
        """
        for node in doc.sections:
            if isinstance(node, Section) and node.section_id == section_id:
                if section_name is not None and node.key != section_name:
                    return None  # Name mismatch
                return node
        return None

    def _apply_section_change(
        self,
        doc: Any,
        original_key: str,
        section_id: str,
        section_name: str | None,
        child_key: str,
        new_value: Any,
    ) -> None:
        """Apply a change to a child key within a section node.

        GH#353: Navigates into a Section's children to update, add, or delete
        a child Assignment by key name.

        Args:
            doc: Parsed AST document
            original_key: The original changes key (for error messages)
            section_id: Section number (e.g., "1", "2b")
            section_name: Optional section name for verification (e.g., "IDENTITY")
            child_key: The child key to modify within the section
            new_value: The new value (with tri-state semantics)

        Raises:
            ValueError: If the section cannot be found (section_id not present
                or section_name mismatch). This should not happen because
                _validate_change_paths runs first, but provides a safety net
                for direct callers.
        """
        section = self._find_section(doc, section_id, section_name)
        if section is None:
            # Safety net: _validate_change_paths should catch this first.
            raise ValueError(
                [
                    {
                        "code": "E_UNRESOLVABLE_PATH",
                        "message": (
                            f"Section §{section_id} not found in document"
                            + (f" (expected name '{section_name}')" if section_name else "")
                            + f" for change path '{original_key}'."
                        ),
                    }
                ]
            )

        # GH#361r3: Reject changes targeting Block children (I3 - Mirror Constraint).
        # Section-path changes only support Assignment children. If the child_key
        # resolves to a Block node, reject with an error rather than silently
        # no-opping (delete) or appending a sibling Assignment (set).
        for child in section.children:
            if isinstance(child, Block) and child.key == child_key:
                raise ValueError(
                    [
                        {
                            "code": "E_BLOCK_TARGET",
                            "message": (
                                f"Cannot modify '{child_key}' in §{section_id} via section-path: "
                                f"it is a Block (nested structure), not an Assignment. "
                                f"Use content= to rewrite the section, or target individual "
                                f"keys within the block."
                            ),
                        }
                    ]
                )

        # GH#373: Op-aware dispatch parallel to _apply_block_change.
        op, payload, _ = _extract_op_descriptor(new_value)

        if op == "DELETE" or _is_delete_sentinel(new_value):
            # I2: DELETE sentinel - remove child from section
            section.children = [c for c in section.children if not (isinstance(c, Assignment) and c.key == child_key)]
            return

        if op in ("APPEND", "PREPEND"):
            for child in section.children:
                if isinstance(child, Assignment) and child.key == child_key:
                    _apply_array_op_inplace(child, op, payload)
                    return
            raise ValueError(
                [
                    {
                        "code": "E_UNRESOLVABLE_PATH",
                        "message": (
                            f"$op {op} target '{child_key}' not found in §{section_id} " f"(path '{original_key}')."
                        ),
                    }
                ]
            )

        # Update or add child assignment
        # I1 (Syntactic Fidelity): Normalize Python values to AST types
        normalized_value = _normalize_value_for_ast(new_value)
        found = False
        for child in section.children:
            if isinstance(child, Assignment) and child.key == child_key:
                child.value = normalized_value
                found = True
                break

        if not found:
            # Add new assignment to section children
            new_assignment = Assignment(key=child_key, value=normalized_value)
            section.children.append(new_assignment)

    def _apply_changes(self, doc: Any, changes: dict[str, Any]) -> Any:
        """Apply changes to AST document with tri-state and dot-notation semantics.

        Args:
            doc: Parsed AST document
            changes: Dictionary of field updates with tri-state semantics:
                - Key absent: No change to field
                - Key present with {"$op": "DELETE"}: Delete the field
                - Key present with None: Set field to null/empty
                - Key present with value: Update field to new value

                Dot-notation support for nested updates:
                - "META.STATUS": "ACTIVE" -> updates doc.meta["STATUS"]
                - "META.NEW_FIELD": "value" -> adds field to doc.meta
                - "META.FIELD": {"$op": "DELETE"} -> removes field from doc.meta
                - "META": {...} -> merges into existing doc.meta (unmentioned fields preserved)
                  Use {"$op": "DELETE"} on individual keys within the dict to remove them.

        Returns:
            Modified document

        Raises:
            ValueError: If any change paths are unresolvable (GH#335)
        """
        # GH#335: Validate all paths before applying any changes.
        # Fail-fast: if ANY path is unresolvable, reject the entire batch
        # to prevent partial application with silent corruption.
        path_errors = self._validate_change_paths(changes, doc)
        if path_errors:
            raise ValueError(path_errors)

        for key, new_value in changes.items():
            # GH#353: Section-prefixed paths (§N.KEY or §N::NAME.KEY)
            if key.startswith("§"):
                match = _SECTION_PATH_RE.match(key)
                if match:
                    section_id, section_name, child_key = match.groups()
                    self._apply_section_change(doc, key, section_id, section_name, child_key, new_value)
                # Invalid section paths already rejected by _validate_change_paths
                continue

            # Check for dot-notation: META.FIELD
            if key.startswith("META."):
                # Extract the field name after "META."
                field_name = key[5:]  # Remove "META." prefix
                if _is_delete_sentinel(new_value):
                    # Delete field from doc.meta
                    if field_name in doc.meta:
                        del doc.meta[field_name]
                else:
                    # Update or add field in doc.meta
                    # I1 (Syntactic Fidelity): Normalize Python values to AST types
                    # Without this, Python lists emit as "['a', 'b']" instead of "[a,b]"
                    doc.meta[field_name] = _normalize_value_for_ast(new_value)
            elif key == "META" and isinstance(new_value, dict):
                if _is_delete_sentinel(new_value):
                    # DELETE sentinel on META clears the entire block
                    doc.meta = {}
                else:
                    # GH#302: MERGE into existing META, not replace.
                    # Previous behavior replaced the entire META dict, silently
                    # dropping fields like CONTRACT::HOLOGRAPHIC that were not
                    # included in the changes dict.  Merge preserves unmentioned
                    # fields (I3 Mirror Constraint: reflect only present, create
                    # nothing -- and do not destroy what is already present).
                    #
                    # GH#373: An explicit {"$op": "MERGE", "value": {...}} descriptor
                    # has the same semantics as the bare-dict legacy form; payload
                    # is the inner dict.
                    op_meta, payload_meta, _ = _extract_op_descriptor(new_value)
                    merge_dict = payload_meta if op_meta == "MERGE" else new_value
                    for mk, mv in merge_dict.items():
                        if _is_delete_sentinel(mv):
                            doc.meta.pop(mk, None)
                        else:
                            # I1 (Syntactic Fidelity): Normalize values for AST
                            doc.meta[mk] = _normalize_value_for_ast(mv)
            elif (
                "." in key
                and key.count(".") == 1
                and self._find_block(doc, key.split(".", 1)[0]) is not None
                and not any(isinstance(s, Assignment) and s.key == key for s in doc.sections)
            ):
                # GH#369: PARENT.CHILD where PARENT is a top-level Block and the
                # literal dotted key does NOT already exist as a flat top-level
                # Assignment. Route into the Block instead of falling through to
                # the flat-assignment branch (which would silently append a
                # duplicate assignment with a dotted key, violating I3).
                #
                # The "literal dotted key already exists at top level" check
                # preserves the GH#347 edge case where a block named e.g. "P1"
                # coexists with a flat assignment "P1.1::value": we still
                # modify the flat assignment in that scenario.
                parent_key, _, child_key = key.partition(".")
                self._apply_block_change(doc, key, parent_key, child_key, new_value)
            elif _is_delete_sentinel(new_value):
                # I2: DELETE sentinel - remove field entirely from sections
                doc.sections = [s for s in doc.sections if not (isinstance(s, Assignment) and s.key == key)]
            else:
                # GH#373: Op-aware dispatch on top-level keys.
                # MERGE on a top-level Block; APPEND/PREPEND on a top-level
                # array Assignment. Bare values fall through to legacy
                # full-replacement.
                op, payload, _ = _extract_op_descriptor(new_value)

                if op == "MERGE":
                    # Validator restricts MERGE to block/section/meta targets.
                    target_block: Block | None = self._find_block(doc, key)
                    if target_block is not None:
                        for mk, mv in payload.items():
                            if _is_delete_sentinel(mv):
                                target_block.children = [
                                    c for c in target_block.children if not (isinstance(c, Assignment) and c.key == mk)
                                ]
                                continue
                            normalized_mv = _normalize_value_for_ast(mv)
                            found_child = False
                            for child in target_block.children:
                                if isinstance(child, Assignment) and child.key == mk:
                                    child.value = normalized_mv
                                    found_child = True
                                    break
                            if not found_child:
                                target_block.children.append(Assignment(key=mk, value=normalized_mv))
                        continue

                    # MERGE on a Section -- search and merge children.
                    target_section: Section | None = None
                    for node in doc.sections:
                        if isinstance(node, Section) and node.key == key:
                            target_section = node
                            break
                    if target_section is not None:
                        for mk, mv in payload.items():
                            if _is_delete_sentinel(mv):
                                target_section.children = [
                                    c
                                    for c in target_section.children
                                    if not (isinstance(c, Assignment) and c.key == mk)
                                ]
                                continue
                            normalized_mv = _normalize_value_for_ast(mv)
                            found_child = False
                            for child in target_section.children:
                                if isinstance(child, Assignment) and child.key == mk:
                                    child.value = normalized_mv
                                    found_child = True
                                    break
                            if not found_child:
                                target_section.children.append(Assignment(key=mk, value=normalized_mv))
                        continue
                    # Validator should have caught missing target; safety net.
                    raise ValueError(
                        [
                            {
                                "code": "E_UNRESOLVABLE_PATH",
                                "message": (f"$op MERGE target '{key}' not found as a Block " f"or Section."),
                            }
                        ]
                    )

                if op in ("APPEND", "PREPEND"):
                    for section in doc.sections:
                        if isinstance(section, Assignment) and section.key == key:
                            _apply_array_op_inplace(section, op, payload)
                            break
                    else:
                        raise ValueError(
                            [
                                {
                                    "code": "E_UNRESOLVABLE_PATH",
                                    "message": (f"$op {op} target '{key}' not found as a " f"top-level Assignment."),
                                }
                            ]
                        )
                    continue

                # Legacy full-value replacement (or new Assignment if missing).
                # I1 (Syntactic Fidelity): Normalize Python values to AST types
                normalized_value = _normalize_value_for_ast(new_value)
                found = False
                for section in doc.sections:
                    if isinstance(section, Assignment) and section.key == key:
                        section.value = normalized_value
                        found = True
                        break

                # If not found and not deleting, add new field
                if not found:
                    # Create new assignment node with normalized value
                    new_assignment = Assignment(key=key, value=normalized_value)
                    doc.sections.append(new_assignment)

        return doc

    def _apply_mutations(self, doc: Document, mutations: dict[str, Any] | None) -> None:
        """Apply META field mutations to document AST.

        Args:
            doc: Parsed document to mutate
            mutations: Dictionary of META fields to inject/override

        Mutations support:
        - Set/override fields (including None/null)
        - DELETE sentinel removes field
        - Python lists normalized to ListValue for canonical emission
        """
        if not mutations:
            return

        for key, value in mutations.items():
            if _is_delete_sentinel(value):
                doc.meta.pop(key, None)
                continue
            doc.meta[key] = _normalize_value_for_ast(value)

    def _generate_diff(
        self,
        original_bytes: int,
        canonical_bytes: int,
        original_metrics: StructuralMetrics | None,
        canonical_metrics: StructuralMetrics | None,
        content_changed: bool = False,
    ) -> str:
        """Generate structural diff from pre-computed metrics.

        Compares structural metrics to detect potential data loss during
        normalization. Returns warnings for significant structural changes.

        Args:
            original_bytes: Byte length of original content
            canonical_bytes: Byte length of canonical content
            original_metrics: Pre-computed metrics from original document (or None)
            canonical_metrics: Pre-computed metrics from canonical document (or None)
            content_changed: Whether content differs (for I4 auditability when
                byte count and structure are identical but values differ)

        Returns:
            Structural diff summary with warning codes for significant changes
        """
        # I4 Auditability: Must report changes even when byte count and structure
        # are identical but content values differ (e.g., KEY::foo -> KEY::bar)
        if not content_changed and original_bytes == canonical_bytes and original_metrics == canonical_metrics:
            return "No changes"

        # Build structural summary with warnings
        summary_parts = []
        warnings = []

        # Byte count change
        summary_parts.append(f"{original_bytes} -> {canonical_bytes} bytes")

        # If we have metrics, check for structural changes
        if original_metrics is not None and canonical_metrics is not None:
            # Section marker loss (W_STRUCT_001)
            lost_sections = original_metrics.section_markers - canonical_metrics.section_markers
            if lost_sections:
                warnings.append(f"{W_STRUCT_001}: section markers removed ({', '.join(sorted(lost_sections))})")

            # Block count reduction (W_STRUCT_002)
            if canonical_metrics.blocks < original_metrics.blocks:
                block_diff = original_metrics.blocks - canonical_metrics.blocks
                warnings.append(f"{W_STRUCT_002}: {block_diff} block(s) removed")

            # Assignment count reduction (W_STRUCT_003)
            if canonical_metrics.assignments < original_metrics.assignments:
                assign_diff = original_metrics.assignments - canonical_metrics.assignments
                warnings.append(f"{W_STRUCT_003}: {assign_diff} assignment(s) removed")

        # Build final summary
        result = " | ".join(summary_parts)
        if warnings:
            result += " | WARNINGS: " + "; ".join(warnings)

        return result

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute write pipeline.

        Args:
            target_path: File path to write to
            content: Full content for new files/overwrites (XOR with changes)
            changes: Field updates for existing files (XOR with content)
            mutations: Optional META field overrides
            base_hash: Optional CAS consistency check hash
            schema: Optional schema name for validation
            debug_grammar: Whether to include compiled grammar in output (default: False)

        Returns:
            Dictionary with:
            - status: "success" or "error"
            - path: Written file path (on success)
            - canonical_hash: SHA-256 hash of canonical content (on success)
            - corrections: List of corrections applied
            - diff: Compact diff of changes
            - errors: List of errors (on failure)
            - validation_status: VALIDATED | UNVALIDATED | INVALID
            - schema_name: Schema name used (when VALIDATED or INVALID)
            - schema_version: Schema version used (when VALIDATED or INVALID)
            - validation_errors: List of schema validation errors (when INVALID)
            - debug_info: Constraint grammar debug information (when debug_grammar=True)
        """
        # Validate and extract parameters
        params = self.validate_parameters(kwargs)
        target_path = params["target_path"]
        content = params.get("content")
        changes = params.get("changes")
        mutations = params.get("mutations")
        base_hash = params.get("base_hash")
        schema_name = params.get("schema")
        debug_grammar = params.get("debug_grammar", False)
        grammar_hint = params.get("grammar_hint", False)
        lenient = params.get("lenient", False)
        # GH#354: Accept dry_run as alias for corrections_only (either triggers dry-run)
        corrections_only = params.get("corrections_only", False) or params.get("dry_run", False)
        parse_error_policy = params.get("parse_error_policy", "error")
        # GH#376 PR-A: format_style is optional; None preserves today's behaviour.
        format_style = params.get("format_style")

        if parse_error_policy not in ("error", "salvage"):
            return self._error_envelope(
                target_path,
                [{"code": "E_INPUT", "message": f"Invalid parse_error_policy: {parse_error_policy}"}],
            )

        if format_style is not None and format_style not in FORMAT_STYLE_VALUES:
            return self._error_envelope(
                target_path,
                [
                    {
                        "code": E_INVALID_FORMAT_STYLE,
                        "message": (
                            f"Invalid format_style: {format_style!r}. " f"Expected one of {list(FORMAT_STYLE_VALUES)}."
                        ),
                    }
                ],
            )

        # Initialize result with unified envelope per D2 design
        # I5 (Schema Sovereignty): validation_status must be UNVALIDATED to make bypass visible
        # "Schema bypass shall be visible, never silent" - North Star I5
        result: dict[str, Any] = {
            "status": "success",
            "path": target_path,
            "canonical_hash": "",
            "corrections": [],
            "warnings": [],  # GH#349: Top-level warnings for data loss (I4)
            "diff": "",
            "diff_unified": "",
            "errors": [],
            "validation_status": "UNVALIDATED",  # I5: Explicit bypass until validated
            "validation_hint": self._build_validation_hint(),  # GH#352+361r3: guidance with available schemas
        }

        # STEP 1: Validate path
        path_valid, path_error = self._validate_path(target_path)
        if not path_valid:
            return self._error_envelope(
                target_path,
                [{"code": "E_PATH", "message": path_error}],
            )

        # STEP 2: Validate content XOR changes
        if content is not None and changes is not None:
            return self._error_envelope(
                target_path,
                [
                    {
                        "code": "E_INPUT",
                        "message": "Cannot provide both content and changes - they are mutually exclusive",
                    }
                ],
            )

        path_obj = Path(target_path)
        file_exists = path_obj.exists()

        # Handle modes based on content vs changes
        baseline_content_for_diff = ""
        original_metrics: StructuralMetrics | None = None
        canonical_metrics: StructuralMetrics | None = None
        canonical_content = ""
        corrections: list[dict[str, Any]] = []

        # Determine mode
        normalize_mode = content is None and changes is None

        if normalize_mode:
            # NORMALIZE MODE: read existing file, parse, emit canonical form, write back
            # Pure I1 (Syntactic Fidelity) enforcement: normalization alters syntax never semantics
            if not file_exists:
                return self._error_envelope(
                    target_path,
                    [{"code": "E_FILE", "message": "File does not exist - normalize mode requires existing file"}],
                )

            # Read existing file
            try:
                with open(target_path, encoding="utf-8") as f:
                    baseline_content_for_diff = f.read()
            except Exception as e:
                return self._error_envelope(
                    target_path,
                    [{"code": "E_READ", "message": f"Read error: {str(e)}"}],
                )

            # Check base_hash if provided (CAS guard)
            if base_hash:
                current_hash = self._compute_hash(baseline_content_for_diff)
                if current_hash != base_hash:
                    return self._error_envelope(
                        target_path,
                        [
                            {
                                "code": "E_HASH",
                                "message": f"Hash mismatch - file has been modified (expected {base_hash[:8]}..., got {current_hash[:8]}...)",
                            }
                        ],
                    )

            # Feed through parse -> emit pipeline (reuse content-mode logic)
            # I3 (Mirror Constraint): reflect only what is present, create nothing
            content = baseline_content_for_diff

        if changes is not None:
            # CHANGES MODE (Amend) - file must exist
            if not file_exists:
                return self._error_envelope(
                    target_path,
                    [{"code": "E_FILE", "message": "File does not exist - changes mode requires existing file"}],
                )

            # Read existing file
            try:
                with open(target_path, encoding="utf-8") as f:
                    baseline_content_for_diff = f.read()
            except Exception as e:
                return self._error_envelope(
                    target_path,
                    [{"code": "E_READ", "message": f"Read error: {str(e)}"}],
                )

            # Check base_hash if provided
            if base_hash:
                current_hash = self._compute_hash(baseline_content_for_diff)
                if current_hash != base_hash:
                    return self._error_envelope(
                        target_path,
                        [
                            {
                                "code": "E_HASH",
                                "message": f"Hash mismatch - file has been modified (expected {base_hash[:8]}..., got {current_hash[:8]}...)",
                            }
                        ],
                    )

            # Parse existing content (strict)
            try:
                doc = parse(baseline_content_for_diff)
                original_metrics = extract_structural_metrics(doc)
            except Exception as e:
                return self._error_envelope(
                    target_path,
                    [{"code": "E_PARSE", "message": f"Parse error: {str(e)}"}],
                )

            # Apply changes with tri-state semantics
            try:
                doc = self._apply_changes(doc, changes)
            except ValueError as e:
                # GH#335: _validate_change_paths raises ValueError with
                # structured error list for unresolvable paths.
                error_list = e.args[0] if e.args and isinstance(e.args[0], list) else []
                if error_list:
                    return self._error_envelope(target_path, error_list)
                return self._error_envelope(
                    target_path,
                    [{"code": "E_APPLY", "message": f"Apply changes error: {str(e)}"}],
                )
            except Exception as e:
                return self._error_envelope(
                    target_path,
                    [{"code": "E_APPLY", "message": f"Apply changes error: {str(e)}"}],
                )

            # Apply META mutations (if any)
            self._apply_mutations(doc, mutations)

        else:
            # CONTENT MODE (Create/Overwrite)
            assert content is not None

            # baseline for diff: existing file content if overwriting
            if file_exists:
                try:
                    with open(target_path, encoding="utf-8") as f:
                        baseline_content_for_diff = f.read()
                except Exception:
                    baseline_content_for_diff = ""
                if baseline_content_for_diff:
                    try:
                        try:
                            baseline_doc = parse(baseline_content_for_diff)
                        except (LexerError, ParserError):
                            baseline_doc, _ = parse_with_warnings(baseline_content_for_diff)
                        original_metrics = extract_structural_metrics(baseline_doc)
                    except (LexerError, ParserError) as e:
                        # GH#266: parse may fail on pre-repair content (e.g. NAME{qualifier}).
                        # Narrow to parse exceptions; let unexpected errors (IOError,
                        # MemoryError, etc.) propagate naturally.
                        original_metrics = None
                        corrections.append(
                            {
                                "code": "W_BASELINE_METRICS_SKIPPED",
                                "message": f"Baseline metrics skipped: {type(e).__name__}: {e}",
                                "safe": True,
                                "semantics_changed": False,
                            }
                        )

            # Check base_hash if provided AND file exists (CAS guard)
            if base_hash and file_exists:
                current_hash = self._compute_hash(baseline_content_for_diff)
                if current_hash != base_hash:
                    return self._error_envelope(
                        target_path,
                        [
                            {
                                "code": "E_HASH",
                                "message": f"Hash mismatch - file has been modified (expected {base_hash[:8]}..., got {current_hash[:8]}...)",
                            }
                        ],
                    )

            parse_input = content
            parse_input, unwrapped = self._unwrap_markdown_code_fence(parse_input)
            if unwrapped:
                corrections.append(
                    {
                        "code": "W_MARKDOWN_UNWRAP",
                        "message": "Unwrapped markdown code fence before OCTAVE parsing.",
                        "safe": True,
                        "semantics_changed": False,
                    }
                )

            # GH#334: Auto-quote unquoted § references in value positions BEFORE
            # parsing. The lexer is context-free and always produces SECTION tokens
            # for §, which fragments intended string values. Auto-quoting preserves
            # author intent (I1) and logs corrections (I4).
            parse_input, section_quote_corrections = _auto_quote_section_refs_in_values(parse_input)
            corrections.extend(section_quote_corrections)

            if lenient:
                # Detect likely OCTAVE structure using line-anchored patterns to avoid false positives in prose.
                # GH#263 rework round 4: Only strong, unambiguous OCTAVE signals trigger structured mode.
                # - assignment_line (KEY::value): The :: operator is definitively OCTAVE syntax.
                # - envelope_line (===NAME===): Definitively OCTAVE envelope markers.
                # Weak signals like block_line (KEY:\s*$) and meta_block (META:) are excluded
                # because they match prose headers like "Title:", "Note:", "Summary:", "META:".
                # Real OCTAVE files with META: blocks always contain :: assignments inside,
                # so they are still detected via assignment_line.
                assignment_line = re.search(r"(?m)^[ \t]*[A-Za-z_][A-Za-z0-9_.]*::", parse_input) is not None
                envelope_line = re.search(r"(?m)^===.+===\s*$", parse_input) is not None
                looks_structured = assignment_line or envelope_line

                if looks_structured:
                    # GH#263: Pre-process curly-brace annotations ONLY for confirmed OCTAVE content.
                    # Plain text with FOO{bar} must not be mutated (I1 syntactic fidelity).
                    # I4 (Transform Auditability): repairs logged in corrections.
                    parse_input, curly_corrections = self._repair_curly_brace_annotations(parse_input)
                    corrections.extend(curly_corrections)

                if not looks_structured and parse_input.strip():
                    parse_input, wrap_corrections = self._wrap_plain_text_as_doc(parse_input, schema_name)
                    corrections.extend(wrap_corrections)

                try:
                    doc, parse_warnings = parse_with_warnings(parse_input)
                    corrections.extend(self._map_parse_warnings_to_corrections(parse_warnings))
                except Exception as e:
                    if parse_error_policy == "salvage":
                        # Issue #177: Use localized salvaging to preserve document structure
                        doc, salvage_corrections = self._localized_salvage(content, str(e), schema_name)
                        corrections.extend(salvage_corrections)
                    else:
                        return self._error_envelope(
                            target_path,
                            [{"code": "E_PARSE", "message": f"Parse error: {str(e)}"}],
                            corrections,
                        )

            else:
                # Strict tokenization + strict parse
                try:
                    _, tokenize_repairs = tokenize(parse_input)
                except Exception as e:
                    # GH#329: Emit § quoting warnings even on strict tokenize failure path.
                    # GH#334: Include auto-quoting corrections already accumulated in
                    # `corrections` (from the pre-parse auto-quoting step).
                    error_corrections = list(corrections)
                    error_corrections.extend(_detect_unquoted_section_in_values(parse_input))
                    return self._error_envelope(
                        target_path,
                        [
                            {
                                "code": "E_TOKENIZE",
                                "message": f"Tokenization error: {str(e)}",
                            }
                        ],
                        error_corrections,
                    )

                try:
                    # GH#348: Use parse_with_warnings even in strict mode to
                    # capture I4 audit warnings (e.g., W_NUMERIC_KEY_DROPPED).
                    # Silent data loss must be reported regardless of mode.
                    # GH#361r3: Pass strict_structure=True so structural issues
                    # (unclosed lists, nested inline maps) raise ParserError
                    # instead of being silently recovered.
                    doc, strict_parse_warnings = parse_with_warnings(parse_input, strict_structure=True)
                    corrections.extend(self._map_parse_warnings_to_corrections(strict_parse_warnings))
                except Exception as e:
                    # GH#334: Start from existing corrections (includes auto-quoting).
                    strict_corrections = list(corrections)
                    strict_corrections.extend(self._track_corrections(parse_input, parse_input, tokenize_repairs))
                    # GH#329: Emit § quoting warnings even on strict parse failure.
                    strict_corrections.extend(_detect_unquoted_section_in_values(parse_input))
                    return self._error_envelope(
                        target_path,
                        [
                            {
                                "code": "E_PARSE",
                                "message": f"Parse error: {str(e)}",
                            }
                        ],
                        strict_corrections,
                    )

                corrections.extend(self._track_corrections(parse_input, parse_input, tokenize_repairs))

            # Detect unquoted § in value positions and emit guidance warnings.
            # This runs on parse_input (after markdown fence unwrapping) so that
            # outer ``` fences don't suppress the warning via literal zone detection.
            # The lexer/parser behavior is correct; this is purely user-facing guidance.
            section_warnings = _detect_unquoted_section_in_values(parse_input)
            corrections.extend(section_warnings)

            # Apply META mutations (if any)
            self._apply_mutations(doc, mutations)

            # GH#302: Inherit frontmatter from existing file when new content lacks it.
            # When an agent rewrites a file via content mode but omits YAML frontmatter,
            # the original frontmatter (required for skill/agent discovery) would be lost.
            # I3 (Mirror Constraint): preserve what exists; do not silently destroy.
            if not normalize_mode and doc.raw_frontmatter is None and file_exists and baseline_content_for_diff:
                try:
                    baseline_doc = parse(baseline_content_for_diff)
                    if baseline_doc.raw_frontmatter is not None:
                        doc.raw_frontmatter = baseline_doc.raw_frontmatter
                        corrections.append(
                            {
                                "code": "W_FRONTMATTER_INHERITED",
                                "message": "YAML frontmatter inherited from existing file (new content lacked frontmatter).",
                                "safe": True,
                                "semantics_changed": False,
                            }
                        )
                except (LexerError, ParserError) as exc:
                    corrections.append(
                        {
                            "code": "W_FRONTMATTER_INHERITANCE_SKIPPED",
                            "message": (
                                f"Frontmatter inheritance skipped: baseline file could not be parsed ({type(exc).__name__}: {exc})"
                            ),
                            "safe": True,
                            "semantics_changed": False,
                        }
                    )

        # Emit canonical form (may be re-emitted after schema repair).
        # GH#376 PR-A: format_style routes through _emit_with_style — a single
        # canonical AST→bytes orchestrator that applies expanded/compact AST
        # pre-passes or the preserve Strategy C short-circuit, all via the
        # SAME emit() call (I1 Single-Canon Discipline).
        try:
            canonical_content = _emit_with_style(
                doc,
                baseline_bytes=baseline_content_for_diff or None,
                new_bytes=content,
                format_style=format_style,
                corrections=corrections,
            )
            canonical_metrics = extract_structural_metrics(doc)
        except OctaveASTCycleError as cyc:
            # Cubic C3 (#376 PR-A): preserve the structured E_AST_CYCLE code
            # so clients can discriminate cycle errors from generic emit
            # failures. MUST appear BEFORE the broad ``except Exception``
            # below — OctaveASTCycleError is a ValueError subclass and would
            # otherwise be swallowed into the generic E_EMIT envelope.
            return self._error_envelope(
                target_path,
                [{"code": OctaveASTCycleError.code, "message": str(cyc)}],
                corrections,
            )
        except Exception as e:
            return self._error_envelope(
                target_path,
                [{"code": "E_EMIT", "message": f"Emit error: {str(e)}"}],
                corrections,
            )

        result["corrections"] = corrections

        # GH#361r5: warnings generation moved AFTER schema repair logic below.
        # Previously built here, but schema repairs can append safe=False
        # corrections that would be excluded from the warnings array.

        # GH#287 Decision 6: Confirmation echo — show SOURCE→STRICT compilations
        # When lenient parsing produces corrections, build a compilations list
        # showing the delta in structured format. Cap at 5 entries + summary.
        if lenient:
            compilations: list[dict[str, str] | str] = []
            _compilation_rule_map = {
                "W002": "ascii_to_unicode",
                "W_LENIENT_MULTI_WORD_COALESCE": "multi_word_coalesce",
                "W_LENIENT_SOURCE_COMPILE_VALUE": "operator_rich_value",
                "W_LENIENT_DUPLICATE_KEY": "duplicate_key",
                "W_MARKDOWN_UNWRAP": "markdown_unwrap",
                "W_SALVAGE_LOCALIZED": "salvage",
            }
            for c in corrections:
                code = c.get("code", "")
                before = c.get("before", "")
                after = c.get("after", "")
                if not before and not after:
                    continue
                rule = _compilation_rule_map.get(code, "normalization")
                # Format source and strict in KEY::value style where applicable
                source_str = str(before) if before else ""
                strict_str = str(after) if after else source_str
                if source_str or strict_str:
                    compilations.append(
                        {
                            "source": source_str,
                            "strict": strict_str,
                            "rule": rule,
                        }
                    )

            # Cap at 5 entries + summary per ADR-0005
            if len(compilations) > 5:
                total = len(compilations)
                compilations = compilations[:5]
                compilations.append(f"...and {total - 5} other normalizations applied.")

            result["compilations"] = compilations
        else:
            result["compilations"] = []

        # Issue #235 T14: Literal zone reporting (§8.2, §8.4)
        # After emit, populate zone_report when literal zones are present.
        zones = _count_literal_zones(doc)
        if zones:
            result["contains_literal_zones"] = True
            result["literal_zone_count"] = len(zones)
            result["literal_zones_validated"] = False  # I5: always False (D4: content opaque)
            result["zone_report"] = {
                "dsl": {"status": "valid", "errors": []},
                "container": {
                    "status": "preserved" if doc.raw_frontmatter else "absent",
                    "validation_status": "UNVALIDATED",  # I5: default before schema validation runs
                },
                "literal": {
                    "status": "preserved",
                    "count": len(zones),
                    "content_validated": False,  # D4: content opaque; I5: honest
                    "zones": zones,
                },
            }
            result["literal_zone_repair_log"] = build_literal_zone_repair_log(zones, doc, "octave_write").to_dict()

        # GH#370: Structural validation (runs regardless of schema).
        # Detects W_DUPLICATE_TARGET warnings that must surface in default flow.
        # This is a lightweight check that doesn't require schema binding.

        structural_validator = Validator(schema=None)
        structural_warnings = structural_validator.validate(doc, strict=False, section_schemas=None)

        # Filter to only warnings (severity='warning') and add them as corrections
        # so they surface in the result.
        for warning in structural_warnings:
            if warning.severity == "warning":
                result["corrections"].append(
                    {
                        "code": warning.code,
                        "tier": "STRUCTURAL_CHECK",
                        "message": warning.message,
                        "field": warning.field_path,
                        "safe": True,  # W_DUPLICATE_TARGET is a safety net, not data loss
                        "semantics_changed": False,
                    }
                )

        # Schema Validation (I5 Schema Sovereignty)
        if schema_name:
            # Old-style dict schemas (META-only, backwards compatibility)
            schema_def = get_builtin_schema(schema_name)

            # New-style SchemaDefinition schemas (constraint validation via section_schemas)
            schema_definition: SchemaDefinition | None = None
            section_schemas: dict[str, SchemaDefinition] | None = None

            # Issue #150: Hermetic resolution for frozen@ and latest schema references
            if schema_name.startswith("frozen@") or schema_name == "latest":
                try:
                    schema_path = resolve_hermetic_standard(schema_name)
                    schema_definition = load_schema(schema_path)
                except Exception:
                    schema_definition = None
            else:
                try:
                    schema_definition = load_schema_by_name(schema_name)
                except Exception:
                    schema_definition = None

            if schema_definition is not None and schema_definition.fields:
                # Map only the schema's name to its definition (validate.py Gap_1 pattern)
                section_schemas = {schema_definition.name: schema_definition}

            has_schema = schema_def is not None or (schema_definition is not None and bool(schema_definition.fields))

            # Add debug grammar information if requested
            if debug_grammar and schema_definition is not None:
                debug_info: dict[str, Any] = {
                    "schema_name": schema_definition.name,
                    "schema_version": schema_definition.version or "unknown",
                    "field_constraints": {},
                }
                for field_name, field_def in schema_definition.fields.items():
                    if hasattr(field_def, "pattern") and field_def.pattern and field_def.pattern.constraints:
                        chain = field_def.pattern.constraints
                        debug_info["field_constraints"][field_name] = {
                            "chain": chain.to_string(),
                            "compiled_regex": chain.compile(),
                        }
                result["debug_info"] = debug_info

            if has_schema:
                # I5: Schema-validated documents shall record schema name and version used
                if schema_def is not None:
                    result["schema_name"] = schema_def.get("name", schema_name)
                    result["schema_version"] = schema_def.get("version", "unknown")
                elif schema_definition is not None:
                    result["schema_name"] = schema_definition.name
                    result["schema_version"] = schema_definition.version or "unknown"

                validator = Validator(schema=schema_def)
                validation_errors = validator.validate(doc, strict=False, section_schemas=section_schemas)

                # Lenient mode: apply minimal safe repairs for builtin dict schemas (META-only)
                if lenient and schema_def is not None and validation_errors:
                    meta_schema = schema_def.get("META", {})
                    fields = meta_schema.get("fields", {})
                    did_repair = False

                    for field_name, field_spec in fields.items():
                        if field_spec.get("type") != "ENUM":
                            continue
                        allowed_values = field_spec.get("values", [])
                        current = doc.meta.get(field_name)
                        if not isinstance(current, str):
                            continue

                        if current in allowed_values:
                            continue

                        matches = [v for v in allowed_values if isinstance(v, str) and v.lower() == current.lower()]
                        if len(matches) != 1:
                            continue

                        canonical_value = matches[0]
                        doc.meta[field_name] = canonical_value
                        did_repair = True
                        result["corrections"].append(
                            {
                                "code": "ENUM_CASEFOLD",
                                "tier": "REPAIR",
                                "before": current,
                                "after": canonical_value,
                                "safe": True,
                                "semantics_changed": False,
                                "message": f"Schema repair: enum casefold {field_name}",
                            }
                        )

                    if did_repair:
                        # GH#376 PR-A: re-emit through the single-canon orchestrator
                        # so format_style applies to schema-repaired output too.
                        canonical_content = _emit_with_style(
                            doc,
                            baseline_bytes=baseline_content_for_diff or None,
                            new_bytes=content,
                            format_style=format_style,
                            corrections=result["corrections"],
                        )
                        canonical_metrics = extract_structural_metrics(doc)
                        validation_errors = validator.validate(doc, strict=False, section_schemas=section_schemas)

                # Lenient mode may apply safe schema repairs (enum casefold, type coercion)
                if lenient and schema_definition is not None and validation_errors:
                    try:
                        doc, repair_log = repair(doc, validation_errors, fix=True, schema=schema_definition)
                        for entry in repair_log.repairs:
                            result["corrections"].append(
                                {
                                    "code": entry.rule_id,
                                    "tier": entry.tier.value,
                                    "before": entry.before,
                                    "after": entry.after,
                                    "safe": entry.safe,
                                    "semantics_changed": entry.semantics_changed,
                                    "message": f"Schema repair: {entry.rule_id}",
                                }
                            )
                        # Re-emit canonical after repairs (GH#376 PR-A: single-canon
                        # orchestrator so format_style applies to repaired output).
                        canonical_content = _emit_with_style(
                            doc,
                            baseline_bytes=baseline_content_for_diff or None,
                            new_bytes=content,
                            format_style=format_style,
                            corrections=result["corrections"],
                        )
                        canonical_metrics = extract_structural_metrics(doc)
                        # Revalidate
                        validation_errors = validator.validate(doc, strict=False, section_schemas=section_schemas)
                    except Exception:
                        # Best-effort: if repair fails, preserve original validation_errors
                        pass

                if validation_errors:
                    result["validation_status"] = "INVALID"
                    result.pop("validation_hint", None)  # GH#352: remove hint when validated
                    result["validation_errors"] = [
                        {"code": err.code, "message": err.message, "field": err.field_path} for err in validation_errors
                    ]

                    # GH#278: Include compiled grammar hint on INVALID when requested
                    if grammar_hint and schema_definition is not None:
                        try:
                            compiled = GBNFCompiler().compile_schema(schema_definition, include_envelope=True)
                            result["grammar_hint"] = {
                                "format": "gbnf",
                                "grammar": compiled,
                                "usage_hints": USAGE_HINTS,
                            }
                        except Exception:
                            result["grammar_hint"] = {
                                "error": "E_GRAMMAR_COMPILE",
                                "message": "Grammar compilation failed for this schema",
                            }
                else:
                    result["validation_status"] = "VALIDATED"
                    result.pop("validation_hint", None)  # GH#352: remove hint when validated
            else:
                # GH#355: Schema not found - remain UNVALIDATED but list available schemas
                # I5 (Schema Sovereignty): make available options visible so agents can self-correct
                result["available_schemas"] = self._list_available_schemas()

        # GH#349 + GH#361r5: Surface data-loss corrections as top-level warnings (I4).
        # Agents can detect data loss by checking result["warnings"] without
        # parsing corrections internals. Any correction with safe=False
        # indicates data loss and is promoted to the warnings array.
        # IMPORTANT: This MUST run AFTER schema repair logic above, which may
        # append additional safe=False corrections to result["corrections"].
        result["warnings"] = [
            {"code": c["code"], "message": c["message"], "line": c.get("line", 0)}
            for c in result["corrections"]
            if c.get("safe") is False
        ]

        # I4 (Transform Auditability): record the mode in the response envelope
        if normalize_mode:
            result["mode"] = "normalize"

        # Diff-first output + hashes (works for dry-run)
        result["diff_unified"] = self._build_unified_diff(baseline_content_for_diff, canonical_content)
        result["canonical_hash"] = self._compute_hash(canonical_content)

        content_changed = baseline_content_for_diff != canonical_content
        result["diff"] = self._generate_diff(
            len(baseline_content_for_diff),
            len(canonical_content),
            original_metrics,
            canonical_metrics,
            content_changed=content_changed,
        )

        if corrections_only:
            # Explicit dry-run: no filesystem writes, no mkdir side effects
            return result

        # WRITE FILE (atomic + symlink-safe)
        try:
            # Ensure parent directory exists
            path_obj.parent.mkdir(parents=True, exist_ok=True)

            # Reject symlink targets (security)
            if path_obj.exists() and path_obj.is_symlink():
                return self._error_envelope(
                    target_path,
                    [
                        {
                            "code": "E_WRITE",
                            "message": f"Cannot write to symlink target '{target_path}'. Use corrections_only=true to preview normalization without writing.",
                        }
                    ],
                    result["corrections"],
                )

            # Preserve permissions if file exists
            original_mode = None
            if path_obj.exists():
                original_stat = os.stat(target_path)
                original_mode = original_stat.st_mode & 0o777

            # Atomic write: tempfile -> fsync -> os.replace
            fd, temp_path = tempfile.mkstemp(dir=path_obj.parent, suffix=".tmp", text=True)
            try:
                if original_mode is not None:
                    os.fchmod(fd, original_mode)

                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(canonical_content)
                    f.flush()
                    os.fsync(f.fileno())

                # TOCTOU protection: recheck base_hash before replace
                if base_hash and file_exists:
                    with open(target_path, encoding="utf-8") as verify_f:
                        verify_content = verify_f.read()
                    verify_hash = self._compute_hash(verify_content)
                    if verify_hash != base_hash:
                        os.unlink(temp_path)
                        return self._error_envelope(
                            target_path,
                            [
                                {
                                    "code": "E_HASH",
                                    "message": f"Hash mismatch before write - file was modified during operation (expected {base_hash[:8]}..., got {verify_hash[:8]}...)",
                                }
                            ],
                            result["corrections"],
                        )

                # Atomic replace
                os.replace(temp_path, target_path)

            except Exception:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise

        except PermissionError:
            return self._error_envelope(
                target_path,
                [
                    {
                        "code": "E_WRITE",
                        "message": f"Permission denied writing '{target_path}'. Use corrections_only=true to preview normalization without writing.",
                    }
                ],
                result["corrections"],
            )
        except Exception as e:
            return self._error_envelope(
                target_path,
                [
                    {
                        "code": "E_WRITE",
                        "message": f"Write error: {str(e)}. Use corrections_only=true to preview normalization without writing.",
                    }
                ],
                result["corrections"],
            )

        return result
