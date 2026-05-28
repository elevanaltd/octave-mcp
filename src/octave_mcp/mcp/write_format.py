"""Format-style pipeline (compact/expand/emit) extracted from write.py as part of STRATEGY_S1 (#459/#465). Threads NFC bytes and baseline spans for Strategy A preserve mode."""

import copy
from typing import Any

from octave_mcp.core.emitter import emit
from octave_mcp.core.grammar.cst import (
    Assignment,
    ASTNode,
    Block,
    Comment,
    Document,
    InlineMap,
    ListValue,
    Section,
)
from octave_mcp.core.lexer import LexerError, normalize_content

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
# documented in the PR description). This guarantees the historical baseline
# test suite remains byte-identical (no behavioural drift on the default path).
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


def _to_baseline_bytes(raw_str: str) -> bytes | None:
    """Convert a raw file-content string to post-NFC baseline bytes.

    HC-1 (GH#377 Strategy A): ``baseline_content_for_diff`` is the raw
    str from ``f.read()`` and must NOT be passed directly as
    ``baseline_bytes`` to the slice path.  Instead callers use this helper
    which applies the same fence-aware NFC normalization that ``tokenize()``
    performs, then encodes the result as UTF-8.  The resulting bytes are
    byte-index-compatible with all Token ``start_byte``/``end_byte`` values
    in the parsed document.

    Returns None if ``raw_str`` is empty or if normalization fails (e.g.
    due to an unterminated fence in the baseline — the slice path will
    simply not activate for malformed baselines).
    """
    if not raw_str:
        return None
    try:
        return normalize_content(raw_str).encode("utf-8")
    except (LexerError, Exception):
        # Malformed baseline: fall back to None so _emit_with_style
        # does not attempt the slice path.
        return None


def _emit_with_style(
    doc: Document,
    *,
    baseline_bytes: bytes | None = None,
    new_bytes: str | None = None,  # noqa: ARG001 -- reserved for future preserve variants (#377)
    format_style: str | None,
    corrections: list[dict[str, Any]],
    spans_valid_for_baseline: bool = False,
) -> str:
    """Single canon orchestrator: produce canonical bytes for ``doc`` under
    ``format_style``.

    Strategy (GH#377 Strategy A, T8 — Strategy-C short-circuit deleted):
    - 'expanded' / 'compact' → apply AST pre-pass and emit().
    - 'preserve' with spans_valid_for_baseline=True → Strategy A span-aware
      emit via FormatOptions.  ``baseline_bytes`` (post-NFC encoded, HC-2:
      bytes not str) is passed through FormatOptions to emit(), which
      dispatches per-node via dirty/repaired flags.  Unchanged nodes are
      sliced verbatim from baseline_bytes; changed nodes fall through to the
      canonical re-emit path.
    - 'preserve' with spans_valid_for_baseline=False (content mode) →
      emit(doc) canonical form.  This is correct because the doc's
      start_byte/end_byte values were computed from the NEW content, not from
      the baseline file, so the slice path would produce wrong output.
    - Anything else (including None) → emit(doc) (current behaviour preserved
      byte-for-byte; this is the documented "current" sentinel).

    All paths route through one and only one ``emit()`` call on the doc (or
    its pre-pass projection), satisfying I1 Single-Canon Discipline.

    HC-1: ``baseline_bytes`` is post-NFC encoded bytes (not the raw str from
    f.read()). The caller must pass normalize_content(raw).encode('utf-8').
    HC-2: Parameter type is ``bytes | None`` (not str | None).

    spans_valid_for_baseline: True only when ``doc`` was parsed from the same
    content that ``baseline_bytes`` represents (changes mode / normalize mode).
    False in content mode where the user supplies entirely new content.

    The ``new_bytes`` parameter is reserved for future preserve-mode variants.
    """
    if format_style == "preserve" and baseline_bytes is not None and spans_valid_for_baseline:
        # Strategy A: span-aware emit. FormatOptions threads baseline_bytes
        # and enable_preserve=True into emit(), which dispatches per-node via
        # dirty/repaired flags. EC-1b: no parse(emit) or emit(parse) calls.
        #
        # GH #420 CE rework (PR #451): preserve mode is now byte-stable on
        # inter-envelope trivia, including lines containing only trailing
        # whitespace (e.g. ``  \n``).  The default ``trailing_whitespace=
        # "strip"`` on FormatOptions would rstrip those lines and violate
        # PROD::I1 SYNTACTIC_FIDELITY.  When the caller explicitly opts
        # into preserve mode, opt into trailing-whitespace preservation
        # too — the semantic intent of "preserve" is to thread the
        # original bytes through emit, and trailing whitespace is part of
        # the original bytes.
        from octave_mcp.core.emitter import FormatOptions

        fmt = FormatOptions(
            baseline_bytes=baseline_bytes,
            enable_preserve=True,
            trailing_whitespace="preserve",
        )
        return emit(doc, fmt)
    if format_style in ("expanded", "compact"):
        projected = _apply_format_style(doc, format_style, corrections)
        return emit(projected)
    return emit(doc)
