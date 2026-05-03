"""Tests for format_style parameter on octave_write (GitHub Issue #376, PR-A).

TDD RED-then-GREEN: tests authored before implementation.

format_style modes:
- "preserve": Strategy C — if parse(new) == parse(baseline), write baseline bytes
  verbatim; else fall through to canonical emit().
- "expanded": AST pre-pass lifting InlineMap (and ListValue items that are
  InlineMap) into Block form before emit(). Output is canonical multi-line.
- "compact": AST pre-pass collapsing eligible Blocks (atom-only children, no
  Comments anywhere in subtree, arity-bounded) into Assignment(value=ListValue
  of InlineMap). Comment-bearing subtrees are vetoed and W_COMPACT_REFUSED
  surfaces in corrections (I3 Mirror Constraint + I4 Auditability).

All three modes are projections of one canonical AST→bytes function (I1
Single-Canon Discipline) — there is exactly one emit() in the pipeline.
"""

from __future__ import annotations

import os
import tempfile

import pytest

from octave_mcp.core.ast_nodes import (
    Assignment,
    Block,
    Comment,
    Document,
    InlineMap,
    ListValue,
    Section,
)
from octave_mcp.core.emitter import emit
from octave_mcp.core.parser import parse
from octave_mcp.mcp.write import (
    E_AST_CYCLE,
    E_INVALID_FORMAT_STYLE,
    FORMAT_STYLE_VALUES,
    W_COMPACT_REFUSED,
    OctaveASTCycleError,
    WriteTool,
    _apply_format_style,
    _compact_pass,
    _emit_with_style,
    _expand_pass,
    _subtree_has_comment,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _semantic_key(doc: Document) -> dict:
    """Flatten a Document to a structure that treats Block-form and
    InlineList-of-InlineMap as equivalent.

    Used by the single-canon-discipline test to compare across format_style
    modes. This embodies the I1 "bijective on semantic space" invariant: the
    three modes differ in syntactic form but encode the same semantic content.
    """

    def value_key(v):
        if isinstance(v, ListValue):
            # List of InlineMaps — flatten to dict (semantic equivalence to a Block).
            if v.items and all(isinstance(it, InlineMap) for it in v.items):
                merged: dict = {}
                for it in v.items:
                    for k, vv in it.pairs.items():
                        merged[k] = value_key(vv)
                return ("BLOCKLIKE", merged)
            return ("LIST", [value_key(it) for it in v.items])
        if isinstance(v, InlineMap):
            return ("BLOCKLIKE", {k: value_key(vv) for k, vv in v.pairs.items()})
        return ("ATOM", v)

    def child_key(node):
        if isinstance(node, Assignment):
            return ("KV", node.key, value_key(node.value))
        if isinstance(node, Block):
            # Treat a Block with only atom-valued Assignment children as the
            # semantic equivalent of an Assignment(KEY, BLOCKLIKE{...}) — this
            # is exactly the expanded↔compact pair that PR-A normalises.
            if node.children and all(
                isinstance(c, Assignment) and not isinstance(c.value, (ListValue, InlineMap)) for c in node.children
            ):
                merged = {c.key: value_key(c.value) for c in node.children if isinstance(c, Assignment)}
                return ("KV", node.key, ("BLOCKLIKE", merged))
            return ("B", node.key, [child_key(c) for c in node.children])
        if isinstance(node, Section):
            return ("S", node.section_id, node.key, [child_key(c) for c in node.children])
        if isinstance(node, Comment):
            return ("C", node.text)
        return ("X", repr(node))

    return {
        "name": doc.name,
        "meta": doc.meta,
        "sections": [child_key(s) for s in doc.sections],
    }


def _expanded_fixture_block_form() -> Document:
    """Document where compact-form (InlineList-of-InlineMap) is the source."""
    return parse("""===T===
§1::PROFILES
  ALICE::[
    NAME::Alice,
    AGE::30
  ]
  BOB::[
    NAME::Bob,
    AGE::25
  ]
===END===
""")


def _compact_eligible_block_doc() -> Document:
    """Block of atom-only children, no comments — eligible for compact."""
    return Document(
        name="T",
        sections=[
            Section(
                section_id="1",
                key="A",
                children=[
                    Block(
                        key="PROFILE",
                        children=[
                            Assignment(key="NAME", value="Alice"),
                            Assignment(key="AGE", value=30),
                        ],
                    )
                ],
            )
        ],
    )


def _compact_with_comment_block_doc() -> Document:
    """Block carrying a Comment — compact must veto."""
    return Document(
        name="T",
        sections=[
            Section(
                section_id="1",
                key="A",
                children=[
                    Block(
                        key="PROFILE",
                        children=[
                            Comment(text="canonical contact"),
                            Assignment(key="NAME", value="Alice"),
                            Assignment(key="AGE", value=30),
                        ],
                    )
                ],
            )
        ],
    )


# ---------------------------------------------------------------------------
# Schema acceptance / rejection (I5 Schema Sovereignty)
# ---------------------------------------------------------------------------


class TestFormatStyleSchema:
    def test_format_style_param_accepted(self):
        tool = WriteTool()
        schema = tool.get_input_schema()
        assert "format_style" in schema["properties"]
        prop = schema["properties"]["format_style"]
        assert prop["type"] == "string"
        # Enum lists exactly the three documented values
        assert set(prop["enum"]) == {"preserve", "expanded", "compact"}
        # Optional (not required)
        assert "format_style" not in schema.get("required", [])

    def test_format_style_constants_exposed(self):
        # Stable identifiers usable by callers / tests / repair logs (I4).
        assert FORMAT_STYLE_VALUES == ("preserve", "expanded", "compact")
        assert E_INVALID_FORMAT_STYLE == "E_INVALID_FORMAT_STYLE"
        assert W_COMPACT_REFUSED == "W_COMPACT_REFUSED"

    @pytest.mark.asyncio
    async def test_invalid_format_style_rejected(self):
        tool = WriteTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "doc.oct.md")
            result = await tool.execute(
                target_path=target,
                content="===T===\nKEY::value\n===END===\n",
                format_style="bogus",
            )
            assert result["status"] == "error"
            codes = [e["code"] for e in result["errors"]]
            assert E_INVALID_FORMAT_STYLE in codes


# ---------------------------------------------------------------------------
# Expanded mode (AST pre-pass)
# ---------------------------------------------------------------------------


class TestExpandedMode:
    def test_expanded_lifts_inline_map_list_to_block(self):
        """ListValue([InlineMap{...}]) value lifts into a Block of Assignments."""
        doc = _expanded_fixture_block_form()
        expanded_doc = _apply_format_style(doc, "expanded", corrections=[])
        # ALICE / BOB should now be Blocks, not Assignments with ListValue
        section = expanded_doc.sections[0]
        assert isinstance(section, Section)
        keys = {c.key for c in section.children}
        assert keys == {"ALICE", "BOB"}
        for child in section.children:
            assert isinstance(child, Block), f"expected Block for {child.key}, got {type(child).__name__}"
            child_keys = {a.key for a in child.children if isinstance(a, Assignment)}
            assert child_keys == {"NAME", "AGE"}

    def test_expanded_idempotent_on_already_expanded(self):
        """Expanded pre-pass is a no-op on a Document that already has Block form."""
        doc = parse("""===T===
§1::A
  PROFILE:
    NAME::Alice
    AGE::30
===END===
""")
        before = emit(doc)
        out = _emit_with_style(doc, baseline_bytes=None, new_bytes=None, format_style="expanded", corrections=[])
        # Re-emit through expanded should match plain emit (already canonical)
        assert out == before

    def test_expanded_matches_validate_canonical(self):
        """For 5 fixtures with InlineMap shapes, expanded output matches the
        canonical multi-line form produced by lifting + plain emit()."""
        fixtures = [
            "===A===\n§1::S\n  X::[K::1,L::2]\n===END===\n",
            "===B===\n§1::S\n  Y::[A::foo,B::bar]\n===END===\n",
            "===C===\n§1::S\n  Z::[NAME::Alice,AGE::30]\n===END===\n",
            "===D===\n§1::S\n  W::[K1::v1,K2::v2,K3::v3]\n===END===\n",
            "===E===\n§1::S\n  V::[ID::1,LABEL::root]\n===END===\n",
        ]
        for src in fixtures:
            doc = parse(src)
            corr: list = []
            out = _emit_with_style(doc, baseline_bytes=None, new_bytes=None, format_style="expanded", corrections=corr)
            # Output must round-trip
            reparsed = parse(out)
            # And re-emitting expanded on the reparsed doc must be byte-identical (idempotence)
            again = _emit_with_style(
                reparsed, baseline_bytes=None, new_bytes=None, format_style="expanded", corrections=[]
            )
            assert again == out, f"expanded not idempotent for fixture: {src!r}"
            # Block-form must have appeared
            assert ":" in out
            # Output must NOT contain the inline-list bracket form for the lifted key
            # (basic structural assertion — a `KEY::[` would mean inline form remained)
            for line in out.splitlines():
                stripped = line.strip()
                # Allow "===NAME===" envelope and section headers
                if stripped.startswith("===") or stripped.startswith("§"):
                    continue
                if "::" in stripped and stripped.endswith("["):
                    raise AssertionError(f"inline-list-form survived expanded pass: {line!r}")


# ---------------------------------------------------------------------------
# Compact mode (AST pre-pass + W_COMPACT_REFUSED veto)
# ---------------------------------------------------------------------------


class TestCompactMode:
    def test_compact_collapses_simple_inline_maps(self):
        doc = _compact_eligible_block_doc()
        corrections: list = []
        out = _emit_with_style(
            doc, baseline_bytes=None, new_bytes=None, format_style="compact", corrections=corrections
        )
        # Output should contain the inline-list-of-inlinemap form
        assert "PROFILE::[" in out
        assert "NAME::Alice" in out
        assert "AGE::30" in out
        # No W_COMPACT_REFUSED for this clean fixture
        assert all(c.get("code") != W_COMPACT_REFUSED for c in corrections)

    def test_compact_vetoes_subtrees_with_comments(self):
        doc = _compact_with_comment_block_doc()
        corrections: list = []
        out = _emit_with_style(
            doc, baseline_bytes=None, new_bytes=None, format_style="compact", corrections=corrections
        )
        # Block-form must survive (no collapse)
        assert "PROFILE:" in out
        assert "// canonical contact" in out
        # W_COMPACT_REFUSED must be logged (I4 Audit)
        veto_codes = [c.get("code") for c in corrections]
        assert W_COMPACT_REFUSED in veto_codes
        # Veto entry should reference the field
        veto = next(c for c in corrections if c.get("code") == W_COMPACT_REFUSED)
        assert veto.get("safe") is True
        assert veto.get("semantics_changed") is False
        # Has a message identifying the subtree
        assert "PROFILE" in (veto.get("message") or "") or "PROFILE" in (veto.get("field") or "")

    def test_compact_idempotent(self):
        doc = _compact_eligible_block_doc()
        once = _emit_with_style(doc, baseline_bytes=None, new_bytes=None, format_style="compact", corrections=[])
        twice_doc = parse(once)
        twice = _emit_with_style(twice_doc, baseline_bytes=None, new_bytes=None, format_style="compact", corrections=[])
        assert once == twice


# ---------------------------------------------------------------------------
# Preserve mode (Strategy C — parse-equality short-circuit)
# ---------------------------------------------------------------------------


class TestPreserveMode:
    @pytest.mark.asyncio
    async def test_preserve_no_op_on_parse_equality(self):
        """Whitespace-only difference from baseline writes baseline bytes verbatim."""
        baseline = "===T===\n§1::A\n  K::value\n===END===\n"
        # Add semantically-irrelevant whitespace difference (extra blank line)
        new_content = "===T===\n§1::A\n  K::value\n\n===END===\n"

        tool = WriteTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "doc.oct.md")
            with open(target, "w", encoding="utf-8") as f:
                f.write(baseline)

            result = await tool.execute(
                target_path=target,
                content=new_content,
                format_style="preserve",
            )
            assert result["status"] == "success"
            with open(target, encoding="utf-8") as f:
                on_disk = f.read()
            # Strategy C: baseline preserved byte-for-byte
            assert on_disk == baseline

    @pytest.mark.asyncio
    async def test_preserve_falls_through_on_ast_diff(self):
        """Semantic difference falls through to canonical emit()."""
        baseline = "===T===\n§1::A\n  K::value\n===END===\n"
        new_content = "===T===\n§1::A\n  K::different\n===END===\n"

        tool = WriteTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "doc.oct.md")
            with open(target, "w", encoding="utf-8") as f:
                f.write(baseline)

            result = await tool.execute(
                target_path=target,
                content=new_content,
                format_style="preserve",
            )
            assert result["status"] == "success"
            with open(target, encoding="utf-8") as f:
                on_disk = f.read()
            # Fell through to canonical emit — content reflects new value
            assert "K::different" in on_disk
            # And it's parse-equal to the new content
            assert _semantic_key(parse(on_disk)) == _semantic_key(parse(new_content))


# ---------------------------------------------------------------------------
# Single-canon discipline & idempotence (I1)
# ---------------------------------------------------------------------------


_CORPUS = [
    "===A===\n§1::S\n  K::value\n===END===\n",
    "===B===\n§1::S\n  PROFILE::[NAME::Alice,AGE::30]\n===END===\n",
    "===C===\nMETA:\n  TYPE::TEST\n§1::S\n  K::v\n===END===\n",
    "===D===\n§1::S\n  L::[a,b,c]\n===END===\n",
]


class TestSingleCanonDiscipline:
    @pytest.mark.parametrize("src", _CORPUS)
    def test_modes_agree_on_semantic_space(self, src):
        """parse(emit(doc, X)) ≈ parse(emit(doc, Y)) under semantic equivalence
        (Block↔InlineList-of-InlineMap normalised)."""
        doc = parse(src)
        outputs = {}
        for mode in ("preserve", "expanded", "compact"):
            outputs[mode] = _emit_with_style(
                doc, baseline_bytes=None, new_bytes=None, format_style=mode, corrections=[]
            )
        keys = {m: _semantic_key(parse(out)) for m, out in outputs.items()}
        # All three semantic keys must match — bijective on semantic space (I1)
        assert keys["preserve"] == keys["expanded"] == keys["compact"], (
            f"mode outputs diverge semantically:\n preserve={outputs['preserve']!r}\n"
            f" expanded={outputs['expanded']!r}\n compact={outputs['compact']!r}"
        )

    @pytest.mark.parametrize("src", _CORPUS)
    @pytest.mark.parametrize("mode", ["preserve", "expanded", "compact"])
    def test_idempotent_per_mode(self, src, mode):
        """emit(parse(emit(doc, M)), M) == emit(doc, M) for each mode M."""
        doc = parse(src)
        once = _emit_with_style(doc, baseline_bytes=None, new_bytes=None, format_style=mode, corrections=[])
        reparsed = parse(once)
        twice = _emit_with_style(reparsed, baseline_bytes=None, new_bytes=None, format_style=mode, corrections=[])
        assert once == twice, f"mode {mode} not idempotent for {src!r}: once={once!r} twice={twice!r}"


# ---------------------------------------------------------------------------
# CIV B1 — W_COMPACT_REFUSED audit-ID disambiguation (I4 attributability).
# ---------------------------------------------------------------------------


class TestSiblingPathDisambiguation:
    def test_two_sibling_blocks_same_key_get_unique_paths(self):
        """Two sibling Blocks sharing a key (both with comments) must produce
        TWO refusal records with DISTINCT field IDs (CIV B1)."""
        doc = parse(
            "===T===\n"
            "§1::A\n"
            "  PROFILE:\n"
            "    // c1\n"
            "    NAME::Alice\n"
            "  PROFILE:\n"
            "    // c2\n"
            "    NAME::Bob\n"
            "===END===\n"
        )
        corrections: list = []
        _compact_pass(doc.sections, corrections, "")
        veto = [c for c in corrections if c.get("code") == W_COMPACT_REFUSED]
        assert len(veto) == 2, f"expected 2 veto records, got {len(veto)}: {veto!r}"
        fields = {c["field"] for c in veto}
        assert len(fields) == 2, f"expected 2 distinct fields, got {fields!r}"
        # The two paths share a base prefix and differ in the ordinal suffix.
        assert all("PROFILE" in f for f in fields)
        assert any(f.endswith("#0") for f in fields)
        assert any(f.endswith("#1") for f in fields)

    def test_singleton_block_path_has_no_ordinal_suffix(self):
        """A Block whose key is unique among its siblings keeps an unsuffixed
        path so audit IDs stay readable in the common case."""
        doc = parse("===T===\n" "§1::A\n" "  PROFILE:\n" "    // c1\n" "    NAME::Alice\n" "===END===\n")
        corrections: list = []
        _compact_pass(doc.sections, corrections, "")
        veto = [c for c in corrections if c.get("code") == W_COMPACT_REFUSED]
        assert len(veto) == 1
        # Singleton — no '#' disambiguator.
        assert "#" not in veto[0]["field"]
        assert "PROFILE" in veto[0]["field"]


# ---------------------------------------------------------------------------
# CIV B2 — Cycle traversal raises structured error (E_AST_CYCLE).
# ---------------------------------------------------------------------------


class TestCycleGuard:
    def test_subtree_has_comment_raises_on_cycle(self):
        b = Block(key="X", children=[Assignment(key="K", value="v")])
        b.children.append(b)  # self-referential
        with pytest.raises(OctaveASTCycleError, match=E_AST_CYCLE):
            _subtree_has_comment(b)

    def test_compact_pass_raises_on_cycle(self):
        b = Block(key="X", children=[Assignment(key="K", value="v")])
        b.children.append(b)
        with pytest.raises(OctaveASTCycleError, match=E_AST_CYCLE):
            _compact_pass([b], corrections=[], field_path="")

    def test_expand_pass_raises_on_cycle(self):
        b = Block(key="X", children=[Assignment(key="K", value="v")])
        b.children.append(b)
        with pytest.raises(OctaveASTCycleError, match=E_AST_CYCLE):
            _expand_pass([b])

    def test_cycle_error_carries_stable_code(self):
        b = Block(key="X", children=[])
        b.children.append(b)
        try:
            _subtree_has_comment(b)
        except OctaveASTCycleError as exc:
            assert exc.code == E_AST_CYCLE
            assert E_AST_CYCLE in str(exc)
        else:  # pragma: no cover
            raise AssertionError("expected OctaveASTCycleError")

    def test_acyclic_ast_unaffected_by_guard(self):
        """The cycle guard must not regress normal traversal — sibling Blocks
        sharing a child reference are NOT cycles (no ancestor link)."""
        # Build two independent Blocks that share NO node identity.
        b1 = Block(key="A", children=[Assignment(key="K", value="v1")])
        b2 = Block(key="B", children=[Assignment(key="K", value="v2")])
        # Each must traverse cleanly.
        assert _subtree_has_comment(b1) is False
        assert _subtree_has_comment(b2) is False


# ---------------------------------------------------------------------------
# CIV B3 — Arity-exceeded W_COMPACT_REFUSED audit symmetry.
# ---------------------------------------------------------------------------


class TestArityRefusal:
    def _make_block_with_n_atom_children(self, n: int) -> Document:
        children = [Assignment(key=f"K{i}", value=i) for i in range(n)]
        return Document(
            name="T",
            sections=[
                Section(
                    section_id="1",
                    key="A",
                    children=[Block(key="WIDE", children=children)],
                )
            ],
        )

    def test_arity_exceeded_emits_refusal_with_reason(self):
        """A Block with 9 atom-only children (no comments) exceeds the arity
        bound and must produce exactly one W_COMPACT_REFUSED record carrying
        ``reason='arity_exceeded'`` (CIV B3)."""
        doc = self._make_block_with_n_atom_children(9)
        corrections: list = []
        _compact_pass(doc.sections, corrections, "")
        arity_records = [
            c for c in corrections if c.get("code") == W_COMPACT_REFUSED and c.get("reason") == "arity_exceeded"
        ]
        assert len(arity_records) == 1, f"expected 1 arity refusal, got {arity_records!r}"
        rec = arity_records[0]
        assert "WIDE" in rec["field"]
        assert "9" in rec["message"]
        assert rec["safe"] is True
        assert rec["semantics_changed"] is False

    def test_arity_at_bound_collapses_with_no_refusal(self):
        """A Block with exactly _COMPACT_MAX_PAIRS=8 children collapses cleanly
        with NO refusal record (boundary check)."""
        doc = self._make_block_with_n_atom_children(8)
        corrections: list = []
        _compact_pass(doc.sections, corrections, "")
        assert all(c.get("code") != W_COMPACT_REFUSED for c in corrections), corrections

    def test_comment_refusal_carries_reason_discriminant(self):
        """Existing comment-veto records must also carry the new ``reason``
        field (audit-symmetry)."""
        doc = parse("===T===\n" "§1::A\n" "  PROFILE:\n" "    // c\n" "    NAME::Alice\n" "===END===\n")
        corrections: list = []
        _compact_pass(doc.sections, corrections, "")
        veto = [c for c in corrections if c.get("code") == W_COMPACT_REFUSED]
        assert len(veto) == 1
        assert veto[0].get("reason") == "contains_comment"


# ---------------------------------------------------------------------------
# CIV B4 — explicit byte-identity guard for default (format_style=None).
# ---------------------------------------------------------------------------


class TestDefaultUnchanged:
    @pytest.mark.parametrize("src", _CORPUS)
    def test_format_style_none_byte_identical_to_emit(self, src):
        """When ``format_style`` is omitted, ``_emit_with_style`` MUST return
        the same bytes as plain ``emit(doc)`` — guards the documented
        "current" sentinel default against silent regression (TMG/CIV)."""
        doc = parse(src)
        out = _emit_with_style(doc, baseline_bytes=None, new_bytes=None, format_style=None, corrections=[])
        assert out == emit(doc)


# ---------------------------------------------------------------------------
# Cubic C1 — preserve-mode CLI degrades gracefully on invalid-UTF-8 baseline.
# ---------------------------------------------------------------------------


class TestPreserveInvalidUTF8Baseline:
    def test_cli_preserve_invalid_utf8_baseline_does_not_crash(self):
        """When the on-disk baseline contains invalid UTF-8, ``--format-style
        preserve`` must NOT crash; the preserve short-circuit simply cannot
        fire and the canonical write proceeds (cubic C1)."""
        from click.testing import CliRunner

        from octave_mcp.cli.main import cli

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "doc.oct.md")
            # Write invalid UTF-8 directly to bypass any encoder normalisation.
            with open(target, "wb") as f:
                f.write(b"\xff\xfe invalid utf-8 baseline bytes")

            new_content = "===T===\n§1::A\n  K::value\n===END===\n"
            result = runner.invoke(
                cli,
                [
                    "write",
                    target,
                    "--content",
                    new_content,
                    "--format-style",
                    "preserve",
                ],
            )
            assert result.exit_code == 0, (
                f"expected exit 0 (graceful degrade), got {result.exit_code}; "
                f"stdout={result.output!r}; exc={result.exception!r}"
            )
            # File must now hold the canonical form (preserve fell through).
            with open(target, encoding="utf-8") as f:
                on_disk = f.read()
            assert "K::value" in on_disk


# ---------------------------------------------------------------------------
# Cubic C2 — DFS path-stack: shared-acyclic refs do NOT raise E_AST_CYCLE.
# ---------------------------------------------------------------------------


class TestSharedAcyclicReferences:
    def _shared_child_doc(self) -> Document:
        """Build an acyclic AST where two distinct Block parents reference
        the SAME atom-valued Assignment instance (same id())."""
        shared_child = Assignment(key="K", value="v")
        b1 = Block(key="A", children=[shared_child])
        b2 = Block(key="B", children=[shared_child])  # same instance, different parent
        return Document(
            name="T",
            sections=[Section(section_id="1", key="S", children=[b1, b2])],
        )

    def test_subtree_has_comment_handles_shared_acyclic_node(self):
        """Two Blocks sharing an Assignment by reference is acyclic — the
        traversal must NOT raise (cubic C2)."""
        doc = self._shared_child_doc()
        # Each Block independently traverses the shared child; with the DFS
        # path-stack pattern, the id() is discarded on frame exit.
        for block in doc.sections[0].children:
            assert _subtree_has_comment(block) is False

    def test_compact_pass_handles_shared_acyclic_node(self):
        """_compact_pass must traverse a shared-acyclic AST without raising."""
        doc = self._shared_child_doc()
        corrections: list = []
        # Should not raise OctaveASTCycleError.
        out = _compact_pass(doc.sections, corrections, "")
        assert len(out) == 1  # one Section back

    def test_expand_pass_handles_shared_acyclic_node(self):
        """_expand_pass must traverse a shared-acyclic AST without raising."""
        doc = self._shared_child_doc()
        out = _expand_pass(doc.sections)
        assert len(out) == 1

    def test_true_cycles_still_raise(self):
        """Regression guard for cubic C2 fix: genuine self-reference is still
        caught even with the path-stack discard semantics."""
        b = Block(key="X", children=[])
        b.children.append(b)  # true cycle: b is its own descendant
        with pytest.raises(OctaveASTCycleError, match=E_AST_CYCLE):
            _subtree_has_comment(b)
        with pytest.raises(OctaveASTCycleError, match=E_AST_CYCLE):
            _compact_pass([b], corrections=[], field_path="")
        with pytest.raises(OctaveASTCycleError, match=E_AST_CYCLE):
            _expand_pass([b])


# ---------------------------------------------------------------------------
# Cubic C3 — OctaveASTCycleError surfaced as structured envelope/CLI error.
# ---------------------------------------------------------------------------


class TestCycleErrorStructuredSurface:
    @pytest.mark.asyncio
    async def test_execute_surfaces_e_ast_cycle_envelope(self, monkeypatch):
        """End-to-end MCP path: a cyclic AST inside the pre-pass MUST produce
        an error envelope with ``code='E_AST_CYCLE'``, NOT a generic
        ``E_EMIT`` (cubic C3)."""
        import octave_mcp.mcp.write as write_mod

        original_apply = write_mod._apply_format_style

        def cyclic_apply(doc, style, corrections):
            # Inject a cycle into the parsed doc, then exercise the real
            # _expand_pass via _apply_format_style — this raises
            # OctaveASTCycleError from inside _emit_with_style, which is
            # the integration boundary cubic C3 targets.
            if doc.sections:
                first = doc.sections[0]
                if isinstance(first, Section) and first.children:
                    first.children.append(first)  # cycle
            return original_apply(doc, style, corrections)

        monkeypatch.setattr(write_mod, "_apply_format_style", cyclic_apply)

        tool = WriteTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "doc.oct.md")
            result = await tool.execute(
                target_path=target,
                content="===T===\n§1::A\n  K::value\n===END===\n",
                format_style="expanded",
            )
            assert result["status"] == "error"
            codes = [e["code"] for e in result["errors"]]
            assert E_AST_CYCLE in codes, f"expected E_AST_CYCLE in error codes, got {codes!r}"
            assert "E_EMIT" not in codes, f"E_AST_CYCLE was swallowed into generic E_EMIT: {codes!r}"

    def test_cli_surfaces_e_ast_cycle_message(self, monkeypatch):
        """CLI path: a cyclic AST inside the pre-pass MUST produce a stderr
        message containing ``E_AST_CYCLE`` and exit non-zero (cubic C3)."""
        from click.testing import CliRunner

        import octave_mcp.mcp.write as write_mod
        from octave_mcp.cli.main import cli

        original_apply = write_mod._apply_format_style

        def cyclic_apply(doc, style, corrections):
            if doc.sections:
                first = doc.sections[0]
                if isinstance(first, Section) and first.children:
                    first.children.append(first)
            return original_apply(doc, style, corrections)

        monkeypatch.setattr(write_mod, "_apply_format_style", cyclic_apply)

        # click 8.3+ keeps stdout/stderr separate by default; ``result.stderr``
        # captures the OctaveASTCycleError surface.
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "doc.oct.md")
            result = runner.invoke(
                cli,
                [
                    "write",
                    target,
                    "--content",
                    "===T===\n§1::A\n  K::value\n===END===\n",
                    "--format-style",
                    "expanded",
                ],
            )
            assert result.exit_code == 1, f"expected exit 1, got {result.exit_code}"
            assert E_AST_CYCLE in (result.stderr or ""), f"expected E_AST_CYCLE in stderr, got stderr={result.stderr!r}"
