"""Write fidelity checks for ``octave_write`` (tool-fidelity slice 1, PR-2).

The write rule: a write reproduces the document exactly in MEANING. Every
change from input to output must be a logged, reversible, syntax-only
normalization (the closed equivalence list below), a change the caller
declared, or a logged TIER_REPAIR the caller opted into with ``lenient=True``.
Anything else drops or alters content, and the write is refused with
``E_FIDELITY`` and ``fidelity_violations[]``. North Star A2 (lenient parsing)
and the IS entry "lenient-to-canonical normalizer" are not amended.

Governing records: OCTAVE-MCP-DIRECTION-CONTAINER-RECEIPTS-PITH-20261110
(``write_rule``) and OCTAVE-MCP-DIRECTION-RULINGS-AMENDMENT-20261117
("meaning exact is right"). Build plan: phase-tool-fidelity/build-plan.md,
sections 3 and 4.

Checks
------
F1  lexical accounting: the reference text and the canonical emit are lexed
    with the same lexer and their token keys are aligned in order.
F2  fixed point: the output re-parses (strict) to the document handed to the
    emitter, raises no new loss-class or spec_violation warning, and a format
    style keeps every comment.
C1  changes mode: the baseline round-trips through the same emit path before
    it is edited, and each re-emitted node round-trips on its own.
C2  changes mode: only the declared changes changed (masked projections,
    resolved with the mutator's own route resolver).
F3  (unchanged-node bytes) lands with PR-3.

Closed equivalence list (each entry has a test in
``tests/unit/test_write_fidelity_lenient_allowed.py``):
E0  NFC normalization (logged as ``NFC_NORMALIZATION``).
E1  an ASCII operator alias and its Unicode form (one ``TokenType``).
E2  regrouping: a STRING or IDENTIFIER stands for a contiguous token run
    whose source text (aliases in their Unicode form) equals its value.
E3  a trailing comma before ``]``.
E4  constructor canonicalization ``NAME[a, b]`` -> ``NAME<a,b>`` (GH#276),
    refused when two words would be joined. Added from the R5 corpus run.
E5  envelope completion: ``===NAME===`` and ``===END===`` added by the
    emitter when the input omitted them. Added from the R4/R5 runs.
"""

from __future__ import annotations

import difflib
from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from octave_mcp.core.ast_nodes import (
    Absent,
    Assignment,
    Block,
    Comment,
    Document,
    HolographicValue,
    InlineMap,
    ListValue,
    LiteralZoneValue,
    Section,
)
from octave_mcp.core.emitter import emit, emit_assignment, emit_block, emit_meta, emit_section
from octave_mcp.core.lexer import Token, TokenType, normalize_content, tokenize
from octave_mcp.core.parser import _strip_yaml_frontmatter, parse, parse_with_warnings
from octave_mcp.mcp.document_mutator import resolve_change_route
from octave_mcp.mcp.write_mutation import (
    _extract_op_descriptor,
    _is_delete_sentinel,
    _is_op_descriptor,
    _normalize_value_for_ast,
    _normalize_value_for_ast_preserving,
)

if TYPE_CHECKING:
    from octave_mcp.mcp.write import WriteTool

E_FIDELITY = "E_FIDELITY"

CONTENT_LOSS = "content_loss"
CONTENT_ADDED = "content_added"
NOT_FIXED_POINT = "not_fixed_point"
DECLARED_CHANGE_MISMATCH = "declared_change_mismatch"

NFC_NORMALIZATION = "NFC_NORMALIZATION"

_MAX_VIOLATIONS = 20
_RESYNC_WINDOW = 300
_SNIPPET = 160

_HINTS = {
    CONTENT_LOSS: (
        "Writing would drop or change this input content (I1, I3). Quote the value, "
        "or fix the input so it parses without loss; nothing was written."
    ),
    CONTENT_ADDED: "Writing would add content that is not in the input (I3); nothing was written.",
    NOT_FIXED_POINT: (
        "The output does not re-parse to the document that was emitted, so a second "
        "read would change its meaning (I1); nothing was written."
    ),
    DECLARED_CHANGE_MISMATCH: "The output differs from the baseline outside the declared changes; nothing was written.",
}

_HINT_CREATED = (
    "created: changes cannot create a key at a path that does not exist (#517, I3). "
    "Use content= to add new structure, MERGE into an existing parent, or set META.<FIELD>."
)

# Token types keyed by type alone (their value is fixed, or an alias whose
# Unicode form is the same TokenType: E1).
_TYPE_ONLY = frozenset(
    {
        TokenType.ASSIGN,
        TokenType.BLOCK,
        TokenType.LIST_START,
        TokenType.LIST_END,
        TokenType.CONCAT,
        TokenType.AT,
        TokenType.SYNTHESIS,
        TokenType.TENSION,
        TokenType.CONSTRAINT,
        TokenType.ALTERNATIVE,
        TokenType.FLOW,
        TokenType.SECTION,
        TokenType.COMMA,
        TokenType.SEPARATOR,
        TokenType.ENVELOPE_END,
        TokenType.FENCE_CLOSE,
        TokenType.NULL,
    }
)
_SKIPPED = frozenset({TokenType.NEWLINE, TokenType.INDENT, TokenType.EOF})
_TYPED_LITERALS = frozenset({TokenType.NUMBER, TokenType.BOOLEAN, TokenType.NULL, TokenType.VERSION})
_REGROUP_TYPES = frozenset({TokenType.STRING, TokenType.IDENTIFIER})

# Parser warning classes whose appearance in the OUTPUT parse (beyond the
# reference parse) means the output is not a canonical fixed point (F2).
_F2_WARNING_TYPES = frozenset({"spec_violation", "lenient_parse"})


def violation(kind: str, line: int, expected: str, found: str, hint: str | None = None) -> dict[str, Any]:
    """One ``fidelity_violations[]`` entry."""
    return {
        "kind": kind,
        "line": line,
        "expected": _clip(expected),
        "found": _clip(found),
        "hint": hint or _HINTS[kind],
    }


def _clip(text: str) -> str:
    return text if len(text) <= _SNIPPET else text[: _SNIPPET - 3] + "..."


# ---------------------------------------------------------------------------
# F1: lexical keys
# ---------------------------------------------------------------------------


@dataclass
class _Item:
    key: tuple[Any, ...]
    tok: Token
    line_start: bool


class _Lexed:
    """One side of an F1 comparison: frontmatter segment plus body tokens."""

    def __init__(self, text: str) -> None:
        body, frontmatter = _strip_yaml_frontmatter(text)
        self.frontmatter = frontmatter if frontmatter is not None and frontmatter.strip() else None
        self.nfc = normalize_content(body).encode("utf-8")
        tokens, _ = tokenize(body)
        self.items: list[_Item] = []
        last_line = -1
        for tok in tokens:
            if tok.type in _SKIPPED:
                continue
            self.items.append(_Item(_key(tok), tok, tok.line != last_line))
            last_line = tok.line

    def source(self, i: int, k: int) -> str:
        """Exact source text of items[i:k]."""
        if i >= k or i >= len(self.items):
            return ""
        k = min(k, len(self.items))
        return self.nfc[self.items[i].tok.start_byte : self.items[k - 1].tok.end_byte].decode("utf-8", "replace")

    def run_text(self, i: int, k: int) -> str:
        """Source text of items[i:k] with each alias in its Unicode form (E1)."""
        parts: list[str] = []
        prev_end: int | None = None
        for item in self.items[i:k]:
            tok = item.tok
            if prev_end is not None:
                parts.append(self.nfc[prev_end : tok.start_byte].decode("utf-8", "replace"))
            parts.append(_canonical_text(tok, self.nfc))
            prev_end = tok.end_byte
        return "".join(parts)

    def line(self, i: int) -> int:
        if not self.items:
            return 0
        return self.items[min(i, len(self.items) - 1)].tok.line


def _key(tok: Token) -> tuple[Any, ...]:
    if tok.type in _TYPE_ONLY:
        return (tok.type.name,)
    if tok.type == TokenType.FENCE_OPEN:
        info = tok.value.get("info_tag") if isinstance(tok.value, dict) else None
        return ("FENCE_OPEN", info)
    if tok.type == TokenType.BOOLEAN:
        return ("BOOLEAN", bool(tok.value))
    return (tok.type.name, tok.value)


def _canonical_text(tok: Token, nfc: bytes) -> str:
    if tok.normalized_from is not None:
        return str(tok.value)
    return nfc[tok.start_byte : tok.end_byte].decode("utf-8", "replace")


@dataclass
class _Allowances:
    """Declared differences F1 may consume: TIER_REPAIR substitutions."""

    substitutions: Counter[tuple[str, str]] = field(default_factory=Counter)


def _regroup(side: _Lexed, i: int, other: _Lexed, j: int) -> int | None:
    """E2: other.items[j] (STRING or IDENTIFIER) stands for side.items[i:k]
    when its value equals that run's source text. Returns k, or None."""
    if j >= len(other.items) or i >= len(side.items):
        return None
    tok = other.items[j].tok
    if tok.type not in _REGROUP_TYPES or not isinstance(tok.value, str):
        return None
    value = tok.value
    for k in range(i + 1, len(side.items) + 1):
        if k == i + 1 and side.items[i].tok.type in _TYPED_LITERALS:
            # A typed literal never becomes (or comes from) a string.
            return None
        text = side.run_text(i, k)
        if text == value:
            if k == i + 1 and side.items[i].tok.type == tok.type:
                return None  # same type, different value: not a regroup
            return k
        if len(text) > len(value):
            return None
    return None


def _constructor(ref: _Lexed, i: int, out: _Lexed, j: int) -> int | None:
    """E4: ``NAME[a, b]`` (adjacent bracket) in the reference stands for the
    output STRING/IDENTIFIER ``NAME<a,b>``. Whitespace may be dropped only
    next to a comma or bracket; joining two words is refused."""
    if j >= len(out.items) or i + 1 >= len(ref.items):
        return None
    otok = out.items[j].tok
    if otok.type not in _REGROUP_TYPES or not isinstance(otok.value, str):
        return None
    name, bracket = ref.items[i].tok, ref.items[i + 1].tok
    if name.type != TokenType.IDENTIFIER or bracket.type != TokenType.LIST_START:
        return None
    if name.end_byte != bracket.start_byte:
        return None
    parts = [_canonical_text(name, ref.nfc), "<"]
    depth = 0
    prev: Token | None = None
    k = i + 1
    while k < len(ref.items):
        tok = ref.items[k].tok
        if tok.type == TokenType.LIST_START:
            depth += 1
            if depth > 1:
                parts.append("[")
        elif tok.type == TokenType.LIST_END:
            depth -= 1
            if depth == 0:
                parts.append(">")
                return k + 1 if "".join(parts) == otok.value else None
            parts.append("]")
        elif tok.type == TokenType.COMMENT:
            return None
        else:
            if (
                prev is not None
                and prev.type not in (TokenType.COMMA, TokenType.LIST_START)
                and tok.type != TokenType.COMMA
                and ref.nfc[prev.end_byte : tok.start_byte]
            ):
                return None  # whitespace between two words would be lost
            parts.append("," if tok.type == TokenType.COMMA else _canonical_text(tok, ref.nfc))
        prev = tok
        k += 1
    return None


def _is_trailing_comma(side: _Lexed, i: int, other: _Lexed, j: int) -> bool:
    """E3: side.items[i] is a comma directly before ``]`` and other is at ``]``."""
    if i + 1 >= len(side.items) or side.items[i].key != ("COMMA",):
        return False
    if side.items[i + 1].key != ("LIST_END",):
        return False
    return j < len(other.items) and other.items[j].key == ("LIST_END",)


def _substitution(ref: _Lexed, i: int, out: _Lexed, j: int, allow: _Allowances) -> bool:
    if i >= len(ref.items) or j >= len(out.items) or not allow.substitutions:
        return False
    before, after = ref.items[i].tok.value, out.items[j].tok.value
    pair = (str(before), str(after))
    if allow.substitutions[pair] > 0:
        allow.substitutions[pair] -= 1
        return True
    return False


def _align(ref: _Lexed, out: _Lexed, allow: _Allowances) -> list[dict[str, Any]]:
    """Walk both key sequences in order, consuming equivalences; each
    difference that no rule covers becomes a violation (deny by default)."""
    found: list[dict[str, Any]] = []
    i = j = 0
    n, m = len(ref.items), len(out.items)
    while i < n or j < m:
        if i < n and j < m and ref.items[i].key == out.items[j].key:
            i += 1
            j += 1
            continue
        if _is_trailing_comma(ref, i, out, j):
            i += 1
            continue
        if _is_trailing_comma(out, j, ref, i):
            j += 1
            continue
        if (
            j == 0
            and m
            and out.items[0].key[0] == "ENVELOPE_START"
            and (not n or ref.items[0].key[0] != "ENVELOPE_START")
        ):
            j += 1  # E5: inferred envelope name
            continue
        if i >= n and j == m - 1 and out.items[j].key == ("ENVELOPE_END",):
            j += 1  # E5: completed ===END===
            continue
        k = _regroup(ref, i, out, j)
        if k is not None:
            i, j = k, j + 1
            continue
        k = _regroup(out, j, ref, i)
        if k is not None:
            i, j = i + 1, k
            continue
        k = _constructor(ref, i, out, j)
        if k is not None:
            i, j = k, j + 1
            continue
        if _substitution(ref, i, out, j, allow):
            i += 1
            j += 1
            continue
        a_keys = [it.key for it in ref.items[i : i + _RESYNC_WINDOW]]
        b_keys = [it.key for it in out.items[j : j + _RESYNC_WINDOW]]
        opcodes = [
            op for op in difflib.SequenceMatcher(None, a_keys, b_keys, autojunk=False).get_opcodes() if op[0] != "equal"
        ]
        if not opcodes:
            # Windows agree but the walk stalled: consume one token each side.
            tag, a1, a2, b1, b2 = "replace", 0, min(1, n - i), 0, min(1, m - j)
        else:
            tag, a1, a2, b1, b2 = opcodes[0]
        kind = CONTENT_ADDED if tag == "insert" else CONTENT_LOSS
        found.append(
            violation(
                kind,
                ref.line(i + a1),
                ref.source(i + a1, i + a2),
                out.source(j + b1, j + b2),
            )
        )
        if len(found) >= _MAX_VIOLATIONS:
            break
        i, j = i + a2, j + b2
    return found


def _frontmatter_violations(ref_frontmatter: str | None, out_frontmatter: str | None) -> list[dict[str, Any]]:
    if ref_frontmatter == out_frontmatter:
        return []
    if out_frontmatter is None:
        return [violation(CONTENT_LOSS, 1, ref_frontmatter or "", "", "YAML frontmatter would be lost.")]
    return [violation(CONTENT_LOSS, 1, ref_frontmatter or "", out_frontmatter, "YAML frontmatter would change.")]


def lexical_violations(
    reference: str,
    output: str,
    *,
    substitutions: list[tuple[str, str]] | None = None,
    masked_meta_keys: set[str] | None = None,
    expected_frontmatter: str | None = None,
    use_expected_frontmatter: bool = False,
) -> list[dict[str, Any]]:
    """F1: compare the reference text with an output text, token by token.

    Raises nothing: text that cannot be lexed is itself a violation (fail
    closed, deny by default).
    """
    try:
        ref = _Lexed(reference)
    except Exception as exc:  # noqa: BLE001 -- any lexer failure fails closed
        return [violation(CONTENT_LOSS, 0, "input that lexes", f"{type(exc).__name__}: {exc}", _HINT_UNLEXABLE)]
    try:
        out = _Lexed(output)
    except Exception as exc:  # noqa: BLE001
        return [violation(NOT_FIXED_POINT, 0, "output that lexes", f"{type(exc).__name__}: {exc}")]
    if masked_meta_keys:
        _drop_meta_entries(ref, masked_meta_keys)
        _drop_meta_entries(out, masked_meta_keys)
    want_fm = expected_frontmatter if use_expected_frontmatter else ref.frontmatter
    if want_fm is not None and not want_fm.strip():
        want_fm = None
    found = _frontmatter_violations(want_fm, out.frontmatter)
    allow = _Allowances(Counter(substitutions or []))
    found.extend(_align(ref, out, allow))
    return found[:_MAX_VIOLATIONS]


_HINT_UNLEXABLE = (
    "The input could not be lexed for comparison, so its meaning cannot be shown to "
    "survive the write; nothing was written."
)


def _drop_meta_entries(side: _Lexed, keys: set[str]) -> None:
    """Remove the META entries for ``keys`` (declared ``mutations``) so F1
    leaves them out; their values are checked separately."""
    items = side.items
    start = None
    for idx in range(len(items) - 1):
        it = items[idx]
        if (
            it.line_start
            and it.tok.column == 1
            and it.key == ("IDENTIFIER", "META")
            and items[idx + 1].key == ("BLOCK",)
        ):
            start = idx + 2
            break
    if start is None:
        return
    end = start
    while end < len(items) and not (items[end].line_start and items[end].tok.column == 1):
        end += 1
    # Split [start, end) into entries at line starts outside brackets.
    keep: list[_Item] = []
    depth = 0
    drop = False
    for it in items[start:end]:
        if it.line_start and depth == 0:
            drop = it.tok.type == TokenType.IDENTIFIER and it.tok.value in keys
        if it.key == ("LIST_START",):
            depth += 1
        elif it.key == ("LIST_END",):
            depth = max(0, depth - 1)
        if not drop:
            keep.append(it)
    if not keep:
        # Only declared entries were in META: the header exists because of them.
        side.items = items[: start - 2] + items[end:]
        return
    side.items = items[:start] + keep + items[end:]


# ---------------------------------------------------------------------------
# Semantic projection (F2, C2)
# ---------------------------------------------------------------------------


@dataclass
class _Masks:
    node_ids: set[int] = field(default_factory=set)
    slots: set[tuple[int, str]] = field(default_factory=set)
    meta: set[str] = field(default_factory=set)


_NO_MASKS = _Masks()


def project_value(value: Any) -> Any:
    """Project a value to plain tuples. Spans, trivia, comments, ``was_quoted``,
    dirty flags and token witnesses are left out. Three mapping forms project
    equal: an InlineMap, a list made only of ``K::V`` pairs, and a Block."""
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, int | float):
        return ("num", value)
    if isinstance(value, str):
        return ("str", value)
    if value is None:
        return ("null",)
    if isinstance(value, Absent):
        return ("absent",)
    if isinstance(value, InlineMap):
        return ("map", tuple((k, project_value(v)) for k, v in value.pairs.items()))
    if isinstance(value, ListValue | list):
        items = value.items if isinstance(value, ListValue) else value
        if items and all(isinstance(x, InlineMap) for x in items):
            return ("map", tuple(pair for x in items for pair in project_value(x)[1]))
        return ("list", tuple(project_value(x) for x in items))
    if isinstance(value, dict):
        return ("map", tuple((k, project_value(v)) for k, v in value.items()))
    if isinstance(value, LiteralZoneValue):
        return ("literal", value.info_tag, value.content)
    if isinstance(value, HolographicValue):
        return ("holographic", value.raw_pattern)
    return ("other", repr(value))


def _node_label(node: Any) -> Any:
    if isinstance(node, Section):
        return ("§", node.section_id)
    return node.key


def _node_value(node: Any, masks: _Masks) -> Any:
    if isinstance(node, Assignment):
        return project_value(node.value)
    if isinstance(node, Block):
        return ("map", _children(node, node.children, masks))
    if isinstance(node, Section):
        return ("section", node.key, node.annotation, _children(node, node.children, masks))
    return ("other", repr(node))


def _children(container: Any, nodes: list[Any], masks: _Masks) -> tuple[Any, ...]:
    out: list[Any] = []
    for node in nodes:
        if isinstance(node, Comment):
            continue
        if id(node) in masks.node_ids:
            continue
        if not isinstance(node, Section) and (id(container), node.key) in masks.slots:
            continue
        out.append((_node_label(node), _node_value(node, masks)))
    return tuple(out)


def _view(doc: Any, masks: _Masks = _NO_MASKS) -> tuple[Any, ...]:
    meta = tuple((k, project_value(v)) for k, v in doc.meta.items() if k not in masks.meta)
    envelopes = tuple(_view(env) for env in getattr(doc, "additional_envelopes", []) or [])
    return (
        doc.name,
        getattr(doc, "grammar_version", None),
        meta,
        doc.has_separator,
        _children(doc, doc.sections, masks),
        envelopes,
    )


def semantic_projection(doc: Document) -> tuple[Any, ...]:
    """Map a parsed document to plain tuples for equality (F2, C2)."""
    return _view(doc)


def _first_difference(a: tuple[Any, ...], b: tuple[Any, ...]) -> tuple[str, str]:
    """Render the first differing element of two projections."""
    names = ("envelope", "grammar", "META", "separator", "body", "envelopes")
    for name, x, y in zip(names, a, b, strict=True):
        if x == y:
            continue
        if isinstance(x, tuple) and isinstance(y, tuple) and name in ("META", "body"):
            for ex, ey in zip(x, y, strict=False):
                if ex != ey:
                    return repr(ex), repr(ey)
            if len(x) > len(y):
                return repr(x[len(y)]), "(missing)"
            return "(missing)", repr(y[len(x)])
        return f"{name}: {x!r}", f"{name}: {y!r}"
    return repr(a), repr(b)


# ---------------------------------------------------------------------------
# F2: fixed point
# ---------------------------------------------------------------------------


def _warning_counts(warnings: list[dict[str, Any]]) -> Counter[tuple[str, str]]:
    return Counter(
        (str(w.get("type")), str(w.get("subtype")))
        for w in warnings
        if isinstance(w, dict) and w.get("type") in _F2_WARNING_TYPES
    )


def _reference_warnings(text: str | None, strict: bool) -> list[dict[str, Any]]:
    if text is None:
        return []
    try:
        _, warnings = parse_with_warnings(text, strict_structure=strict)
    except Exception:  # noqa: BLE001 -- an unparseable reference has no warning baseline
        return []
    return list(warnings)


def _comment_keys(text: str) -> Counter[str]:
    try:
        side = _Lexed(text)
    except Exception:  # noqa: BLE001
        return Counter()
    return Counter(str(it.tok.value) for it in side.items if it.tok.type == TokenType.COMMENT)


def fixed_point_violations(
    target_doc: Any,
    output: str,
    *,
    reference_warnings: list[dict[str, Any]],
    pre_style_text: str | None = None,
) -> list[dict[str, Any]]:
    """F2: the output re-parses to the document handed to the emitter."""
    try:
        out_doc, out_warnings = parse_with_warnings(output, strict_structure=True)
    except Exception as exc:  # noqa: BLE001
        return [violation(NOT_FIXED_POINT, 0, "output that re-parses", f"{type(exc).__name__}: {exc}")]
    found: list[dict[str, Any]] = []
    want, got = semantic_projection(target_doc), semantic_projection(out_doc)
    if want != got:
        expected, actual = _first_difference(want, got)
        found.append(violation(NOT_FIXED_POINT, 0, expected, actual))
    new = _warning_counts(out_warnings) - _warning_counts(reference_warnings)
    for (wtype, subtype), _count in sorted(new.items()):
        line = next(
            (
                int(w.get("line", 0))
                for w in out_warnings
                if w.get("type") == wtype and str(w.get("subtype")) == subtype
            ),
            0,
        )
        found.append(
            violation(
                NOT_FIXED_POINT,
                line,
                "output that re-parses without new warnings",
                f"{wtype}:{subtype}",
            )
        )
    if pre_style_text is not None:
        lost = _comment_keys(pre_style_text) - _comment_keys(output)
        for comment in sorted(lost):
            found.append(violation(CONTENT_LOSS, 0, f"// {comment}", "", "The format style would drop this comment."))
    return found


# ---------------------------------------------------------------------------
# C1: the baseline round-trips before it is edited
# ---------------------------------------------------------------------------


def split_node_gap(node_text: str) -> tuple[str, str]:
    """Split a node's baseline slice into (body, gap). The gap is the longest
    run of whole lines at the end that are blank or comment-only."""
    lines = node_text.splitlines(keepends=True)
    cut = len(lines)
    while cut > 1:
        stripped = lines[cut - 1].strip()
        if stripped == "" or stripped.startswith("//"):
            cut -= 1
            continue
        break
    return "".join(lines[:cut]), "".join(lines[cut:])


def _strip_gap_comments(emission: str, gap: str) -> str:
    """Remove trailing comment-only lines of an emission that the gap already
    holds (the same comments, attached to the node in the AST)."""
    gap_comments = Counter(line.strip() for line in gap.splitlines() if line.strip().startswith("//"))
    lines = emission.splitlines(keepends=True)
    while lines:
        last = lines[-1].strip()
        if last == "":
            lines.pop()
            continue
        if last.startswith("//") and gap_comments[last] > 0:
            gap_comments[last] -= 1
            lines.pop()
            continue
        break
    return "".join(lines)


def _emit_node(node: Any) -> str:
    if isinstance(node, Assignment):
        return emit_assignment(node, 0)
    if isinstance(node, Block):
        return emit_block(node, 0)
    if isinstance(node, Section):
        return emit_section(node, 0)
    return ""


def _reemitted(node: Any) -> bool:
    return bool(node.dirty or node.repaired or getattr(node, "body_dirty", False))


def baseline_roundtrip_violations(baseline: str, edited_doc: Any, format_style: str | None) -> list[dict[str, Any]]:
    """C1. (a) The unedited baseline goes through the same emit path the
    write uses (preserve, or canonical) and must keep every token. (b) Under
    preserve, each node the edit forces to re-emit must round-trip on its own
    (gap split, per-kind emission)."""
    from octave_mcp.mcp.write_format import _emit_with_style, _to_baseline_bytes

    try:
        fresh = parse(baseline)
    except Exception as exc:  # noqa: BLE001
        return [violation(CONTENT_LOSS, 0, "a baseline that parses", f"{type(exc).__name__}: {exc}", _HINT_UNLEXABLE)]
    preserve = format_style == "preserve"
    baseline_bytes = _to_baseline_bytes(baseline)
    if preserve and baseline_bytes is not None:
        unedited = _emit_with_style(
            fresh,
            baseline_bytes=baseline_bytes,
            format_style="preserve",
            corrections=[],
            spans_valid_for_baseline=True,
        )
    else:
        unedited = emit(fresh)
    found = lexical_violations(baseline, unedited)
    if not preserve or baseline_bytes is None:
        return found

    by_start = {n.start_byte: n for n in fresh.sections if n.start_byte is not None}
    for node in edited_doc.sections:
        if node.start_byte is None or not _reemitted(node):
            continue
        original = by_start.get(node.start_byte)
        if original is None or original.end_byte is None:
            continue
        body, gap = split_node_gap(baseline_bytes[original.start_byte : original.end_byte].decode("utf-8"))
        emission = _strip_gap_comments(_emit_node(original), gap)
        found.extend(lexical_violations(body, emission))
    meta_dirty = bool(getattr(edited_doc, "dirty", False)) or any(edited_doc.meta_dirty.values())
    if meta_dirty and fresh.meta_start_byte is not None and fresh.meta_end_byte is not None:
        body, gap = split_node_gap(baseline_bytes[fresh.meta_start_byte : fresh.meta_end_byte].decode("utf-8"))
        found.extend(lexical_violations(body, _strip_gap_comments(emit_meta(fresh.meta), gap)))
    return found[:_MAX_VIOLATIONS]


# ---------------------------------------------------------------------------
# C2: only the declared changes changed
# ---------------------------------------------------------------------------


@dataclass
class _Target:
    route: str
    masks: _Masks
    container: Any = None  # Block/Section/Document holding slot children
    child_keys: tuple[str, ...] = ()
    nodes: tuple[Any, ...] = ()
    meta_fields: tuple[str, ...] = ()


def _top_node(doc: Any, key: str) -> tuple[Any, ...]:
    """The first top-level Assignment or Block with ``key`` (either kind: a
    scalar can replace a Block, and a nested dict synthesizes a Block)."""
    return tuple(s for s in doc.sections if isinstance(s, Assignment | Block) and s.key == key)[:1]


def _resolve(tool: WriteTool, doc: Any, key: str, new_value: Any, route: Any, *, output_side: bool) -> _Target:
    """Collect the node identities, child slots and META slots a change
    touches in ``doc``. The route comes from the mutator's own resolver run
    once on the baseline, so both ASTs are read through the same branch.

    On the output side a DELETE target is never masked: if it survived, it
    shows up in the masked comparison."""
    masks = _Masks()
    target = _Target(route=route.kind, masks=masks)
    op, payload, _ = _extract_op_descriptor(new_value)
    deleting = op == "DELETE" or _is_delete_sentinel(new_value)
    kind = route.kind
    if output_side and deleting:
        return target
    if kind == "section_child":
        section = tool._find_section(doc, route.section_id or "", route.section_name)
        if section is not None:
            target.container, target.child_keys = section, (route.child_key or "",)
    elif kind == "block_child":
        block = tool._find_block(doc, route.parent_key or "")
        if block is not None:
            target.container, target.child_keys = block, (route.child_key or "",)
    elif kind == "meta_flat_atom":
        field_name = key[5:]
        target.nodes = tuple(s for s in doc.sections if isinstance(s, Assignment) and s.key == field_name)[:1]
    elif kind == "meta_field":
        target.meta_fields = (key[5:],)
    elif kind == "meta_whole":
        if deleting:
            target.meta_fields = tuple(doc.meta.keys())
        else:
            merge = payload if op == "MERGE" else new_value
            target.meta_fields = tuple(k for k, v in merge.items() if not (output_side and _is_delete_sentinel(v)))
    elif kind == "top_delete":
        target.nodes = tuple(s for s in doc.sections if isinstance(s, Assignment) and s.key == key)
    elif kind in ("block_full_replace", "top_block_to_scalar", "top_array_op", "top_assignment"):
        target.nodes = _top_node(doc, key)
    elif kind == "anchored":
        resolved = tool._resolve_anchored_change(doc, key)
        if resolved is not None:
            target.nodes = (resolved[0],)
    elif kind == "top_merge":
        container = tool._find_block(doc, key) or next(
            (s for s in doc.sections if isinstance(s, Section) and s.key == key), None
        )
        if container is not None:
            target.container = container
            target.child_keys = tuple(k for k, v in payload.items() if not (output_side and _is_delete_sentinel(v)))
    masks.node_ids.update(id(n) for n in target.nodes)
    if target.container is not None:
        masks.slots.update((id(target.container), ck) for ck in target.child_keys)
    masks.meta.update(target.meta_fields)
    return target


def _elements(doc: Any, target: _Target) -> list[tuple[str, Any, Any]]:
    """(label, ast_value_or_node, projection) for each element the target names."""
    out: list[tuple[str, Any, Any]] = []
    for node in target.nodes:
        out.append((str(_node_label(node)), node, _node_value(node, _NO_MASKS)))
    if target.container is not None:
        for child in target.container.children:
            if isinstance(child, Assignment | Block) and child.key in target.child_keys:
                out.append((child.key, child, _node_value(child, _NO_MASKS)))
    for name in target.meta_fields:
        if name in doc.meta:
            out.append((name, doc.meta[name], project_value(doc.meta[name])))
    return out


def _expected(new_value: Any, existing: Any) -> Any:
    """Projection of a declared value as the mutator would build it."""
    if isinstance(new_value, dict) and not _is_op_descriptor(new_value):
        return (
            "map",
            tuple((k, _expected(v, None)) for k, v in new_value.items() if not _is_delete_sentinel(v)),
        )
    existing_value = existing.value if isinstance(existing, Assignment) else existing
    if existing_value is not None and not isinstance(existing, Block | Section):
        return project_value(_normalize_value_for_ast_preserving(new_value, existing_value))
    return project_value(_normalize_value_for_ast(new_value))


def _mismatch(key: str, expected: Any, found: Any, line: int = 0, hint: str | None = None) -> dict[str, Any]:
    return violation(DECLARED_CHANGE_MISMATCH, line, f"{key}: {expected!r}", f"{key}: {found!r}", hint)


_CREATABLE_ROUTES = frozenset({"meta_field", "meta_whole", "top_merge"})


def _check_one(key: str, new_value: Any, t0: _Target, t1: _Target, doc0: Any, doc1: Any) -> list[dict[str, Any]]:
    op, payload, _ = _extract_op_descriptor(new_value)
    deleting = op == "DELETE" or _is_delete_sentinel(new_value)
    before = _elements(doc0, t0)
    after = _elements(doc1, t1)

    if t0.route in ("top_merge", "meta_whole") and not deleting:
        merge = payload if op == "MERGE" else new_value
        found: list[dict[str, Any]] = []
        base = {label: node for label, node, _ in before}
        got = {label: proj for label, _, proj in after}
        for mk, mv in merge.items():
            if _is_delete_sentinel(mv):
                continue  # unmasked on the output side: a survivor fails the masked comparison
            want = _expected(mv, base.get(mk))
            if got.get(mk) != want:
                found.append(_mismatch(f"{key}.{mk}", want, got.get(mk, "(missing)")))
        return found

    if before == [] and after != [] and not deleting and t0.route not in _CREATABLE_ROUTES:
        return [_mismatch(key, "(absent in baseline)", after[0][2], hint=_HINT_CREATED)]

    if deleting:
        # The output side does not mask a DELETE target, so a survivor is
        # reported by the masked comparison in declared_change_violations.
        return []

    got_proj = after[0][2] if after else "(missing)"
    existing = before[0][1] if before else None
    if op in ("APPEND", "PREPEND"):
        if not isinstance(existing, Assignment):
            return [_mismatch(key, "(an existing list)", got_proj)]
        current = existing.value
        items = list(current.items) if isinstance(current, ListValue) else list(current or [])
        raw = list(payload) if isinstance(payload, list) else [payload]
        added = [_normalize_value_for_ast(x) for x in raw]
        want = project_value(ListValue(items=items + added if op == "APPEND" else added + items))
    elif t0.route == "top_block_to_scalar":
        want = project_value(_normalize_value_for_ast(new_value))
    elif t0.route == "block_full_replace":
        want = _expected_full_replace(new_value, existing)
    else:
        want = _expected(new_value, existing)
    if got_proj != want:
        return [_mismatch(key, want, got_proj)]
    return []


def _expected_full_replace(payload: dict[str, Any], block: Any) -> Any:
    existing = {c.key: c for c in getattr(block, "children", []) if isinstance(c, Assignment | Block)}
    pairs = []
    for mk, mv in payload.items():
        if _is_delete_sentinel(mv):
            continue
        child = existing.get(mk)
        if isinstance(child, Block) and isinstance(mv, dict) and not _is_op_descriptor(mv):
            pairs.append((mk, _expected_full_replace(mv, child)))
        else:
            pairs.append((mk, _expected(mv, child)))
    return ("map", tuple(pairs))


def declared_change_violations(
    tool: WriteTool,
    baseline: str,
    output: str,
    changes: dict[str, Any],
    mutations: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """C2: P1 masked must equal P0 masked, and each declared target must hold
    the declared value (or be absent for DELETE)."""
    declared = list(changes.items()) + [(f"META.{k}", v) for k, v in (mutations or {}).items()]
    try:
        doc0 = parse(baseline)
    except Exception as exc:  # noqa: BLE001
        return [violation(CONTENT_LOSS, 0, "a baseline that parses", f"{type(exc).__name__}: {exc}", _HINT_UNLEXABLE)]
    try:
        doc1 = parse(output)
    except Exception as exc:  # noqa: BLE001
        return [violation(NOT_FIXED_POINT, 0, "output that re-parses", f"{type(exc).__name__}: {exc}")]
    masks0, masks1 = _Masks(), _Masks()
    targets: list[tuple[str, Any, _Target, _Target]] = []
    for key, value in declared:
        route = resolve_change_route(tool, doc0, key, value)
        t0 = _resolve(tool, doc0, key, value, route, output_side=False)
        t1 = _resolve(tool, doc1, key, value, route, output_side=True)
        for mine, other in ((masks0, t0.masks), (masks1, t1.masks)):
            mine.node_ids |= other.node_ids
            mine.slots |= other.slots
            mine.meta |= other.meta
        targets.append((key, value, t0, t1))
    found: list[dict[str, Any]] = []
    p0, p1 = _view(doc0, masks0), _view(doc1, masks1)
    if p0 != p1:
        expected, actual = _first_difference(p0, p1)
        found.append(violation(DECLARED_CHANGE_MISMATCH, 0, expected, actual))
    for key, value, t0, t1 in targets:
        found.extend(_check_one(key, value, t0, t1, doc0, doc1))
    return found[:_MAX_VIOLATIONS]


# ---------------------------------------------------------------------------
# Entry point shared by WriteTool and the CLI
# ---------------------------------------------------------------------------


@dataclass
class FidelityRequest:
    """Everything the checks need from one write call."""

    mode: str  # "content", "changes" or "normalize"
    doc: Any  # the document handed to the emitter
    output: str  # the bytes about to be written
    reference: str = ""  # content mode: the submitted content; else the baseline
    baseline: str = ""
    format_style: str | None = None
    lenient: bool = False
    changes: dict[str, Any] | None = None
    mutations: dict[str, Any] | None = None
    corrections: list[dict[str, Any]] = field(default_factory=list)
    tool: Any = None  # WriteTool, for the mutator's route resolver (C2)
    strict_structure: bool = True


@dataclass
class FidelityResult:
    violations: list[dict[str, Any]]
    corrections: list[dict[str, Any]]


def _codes(corrections: list[dict[str, Any]]) -> set[str]:
    return {str(c.get("code", "")) for c in corrections}


def _nfc_correction(raw: str) -> list[dict[str, Any]]:
    """E0: log NFC normalization when the raw input is not already NFC."""
    try:
        body, _ = _strip_yaml_frontmatter(raw)
        if normalize_content(body) == body:
            return []
    except Exception:  # noqa: BLE001 -- unlexable input is reported by F1
        return []
    return [
        {
            "code": NFC_NORMALIZATION,
            "tier": "NORMALIZATION",
            "message": "Unicode text normalized to NFC (canonical equivalence; meaning unchanged).",
            "safe": True,
            "semantics_changed": False,
        }
    ]


def _content_reference(tool: Any, content: str, lenient: bool) -> tuple[str, str]:
    """Return (reference, parse_input_equivalent) for content mode: the
    submitted content after markdown-fence unwrap (and the logged lenient
    curly-brace repair), before the § auto-quote rewrite."""
    import re

    from octave_mcp.mcp.write_detection import _auto_quote_section_refs_in_values

    reference = content
    if tool is not None:
        reference, _ = tool._unwrap_markdown_code_fence(reference)
    if lenient and tool is not None:
        structured = (
            re.search(r"(?m)^[ \t]*[A-Za-z_][A-Za-z0-9_.]*::", reference) is not None
            or re.search(r"(?m)^===.+===\s*$", reference) is not None
        )
        if structured:
            reference, _ = tool._repair_curly_brace_annotations(reference)
    if tool is None:
        # The CLI parses the submitted text as is (no fence unwrap, no § auto-quote).
        return reference, reference
    parse_input, _ = _auto_quote_section_refs_in_values(reference)
    return reference, parse_input


def _path_rule_violations(req: FidelityRequest, reference: str) -> list[dict[str, Any]] | None:
    """Paths that cannot be lexed get their own rules. Returns None when
    neither path applies."""
    codes = _codes(req.corrections)
    if "W_STRUCT_RAW_WRAP" in codes:
        try:
            out = parse(req.output)
            body = next(s for s in out.sections if isinstance(s, Block) and s.key == "BODY")
            raw = next(c.value for c in body.children if isinstance(c, Assignment) and c.key == "RAW")
        except Exception:  # noqa: BLE001
            raw = None
        if raw != reference:
            return [
                violation(CONTENT_LOSS, 0, reference, str(raw), "The plain-text wrap must keep the raw text exactly.")
            ]
        return []
    if "W_SALVAGE_LOCALIZED" in codes:
        try:
            out = parse(req.output)
        except Exception as exc:  # noqa: BLE001
            return [violation(NOT_FIXED_POINT, 0, "output that re-parses", str(exc))]
        found = []
        values = {s.key: s.value for s in out.sections if isinstance(s, Assignment)}
        for c in req.corrections:
            if c.get("code") != "W_SALVAGE_LINE":
                continue
            marker = f"_PARSE_ERROR_LINE_{c.get('line')}"
            if values.get(marker) != c.get("original"):
                found.append(
                    violation(
                        CONTENT_LOSS,
                        int(c.get("line") or 0),
                        str(c.get("original")),
                        str(values.get(marker)),
                        "A salvaged line must appear exactly under its _PARSE_ERROR_LINE_N marker.",
                    )
                )
        return found
    return None


def _repair_substitutions(corrections: list[dict[str, Any]]) -> list[tuple[str, str]]:
    return [
        (str(c["before"]), str(c["after"]))
        for c in corrections
        if c.get("tier") == "REPAIR" and isinstance(c.get("before"), str) and isinstance(c.get("after"), str)
    ]


def check_write_fidelity(req: FidelityRequest) -> FidelityResult:
    """Run F1, F2, C1 and C2 for one write. The caller refuses the write when
    ``violations`` is non-empty, and otherwise appends ``corrections``."""
    styled = req.format_style in ("expanded", "compact")
    pre_style = emit(req.doc) if styled else req.output
    found: list[dict[str, Any]] = []
    extra: list[dict[str, Any]] = []

    if req.mode in ("content", "normalize"):
        # Normalize mode runs octave_write's content path on the baseline
        # (fence unwrap, lenient curly repair, § auto-quote), so its reference
        # is built the same way.
        source = req.reference if req.mode == "content" else (req.reference or req.baseline)
        reference, parse_input = _content_reference(req.tool, source, req.lenient)
        extra.extend(_nfc_correction(reference))
        ref_warnings = _reference_warnings(parse_input, req.strict_structure)
        path_rule = _path_rule_violations(req, reference)
        if path_rule is not None:
            found.extend(path_rule)
        else:
            inherited = "W_FRONTMATTER_INHERITED" in _codes(req.corrections)
            found.extend(
                lexical_violations(
                    reference,
                    pre_style,
                    substitutions=_repair_substitutions(req.corrections) if req.lenient else None,
                    masked_meta_keys=set(req.mutations or {}),
                    expected_frontmatter=req.doc.raw_frontmatter if inherited else None,
                    use_expected_frontmatter=inherited,
                )
            )
            found.extend(_mutation_violations(req))
    else:
        extra.extend(_nfc_correction(req.baseline))
        ref_warnings = _reference_warnings(req.baseline, False)
        found.extend(baseline_roundtrip_violations(req.baseline, req.doc, req.format_style))
        if req.tool is not None and (req.changes or req.mutations):
            found.extend(
                declared_change_violations(req.tool, req.baseline, req.output, req.changes or {}, req.mutations)
            )

    found.extend(
        fixed_point_violations(
            req.doc,
            req.output,
            reference_warnings=ref_warnings,
            pre_style_text=pre_style if styled else None,
        )
    )
    return FidelityResult(violations=found[:_MAX_VIOLATIONS], corrections=extra)


def _mutation_violations(req: FidelityRequest) -> list[dict[str, Any]]:
    """Content mode ``mutations``: the output META at each mutated key must
    project equal to the mutation value (DELETE: absent)."""
    if not req.mutations:
        return []
    try:
        out_meta = parse(req.output).meta
    except Exception:  # noqa: BLE001 -- F2 reports an output that does not re-parse
        return []
    found = []
    for key, value in req.mutations.items():
        if _is_delete_sentinel(value):
            if key in out_meta:
                found.append(_mismatch(f"META.{key}", "(absent)", project_value(out_meta[key])))
            continue
        want = project_value(_normalize_value_for_ast(value))
        got = project_value(out_meta[key]) if key in out_meta else "(missing)"
        if got != want:
            found.append(_mismatch(f"META.{key}", want, got))
    return found


def refusal_envelope(base: dict[str, Any], violations: list[dict[str, Any]]) -> dict[str, Any]:
    """Turn an error envelope into the E_FIDELITY refusal."""
    kinds = sorted({v["kind"] for v in violations})
    base["errors"] = [
        {
            "code": E_FIDELITY,
            "message": (
                f"Write refused: {len(violations)} fidelity violation(s) ({', '.join(kinds)}). "
                "The output would not reproduce the input exactly in meaning; nothing was written. "
                "See fidelity_violations."
            ),
        }
    ]
    base["fidelity_violations"] = violations
    return base
