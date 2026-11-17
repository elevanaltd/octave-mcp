"""R4 -- the A2 guard: lenient input still succeeds under E_FIDELITY (PR-2).

Governing records: OCTAVE-MCP-DIRECTION-CONTAINER-RECEIPTS-PITH-20261110 and
OCTAVE-MCP-DIRECTION-RULINGS-AMENDMENT-20261117 ("meaning exact is right").
Build plan: tool-fidelity slice 1, sections 1 (A2 boundary), 3 (the closed
equivalence list) and 5 R4.

The write rule is exact in meaning, not byte-exact. North Star A2 (lenient
parsing) and the IS entry "lenient-to-canonical normalizer" are not amended:
every case below is a logged, reversible, syntax-only normalization or a
declared change, and each must still succeed.

Equivalences exercised (closed list; each entry has a test here):
  E0  NFC normalization (logged)
  E1  ASCII operator alias -> Unicode form
  E2  regrouping (quoting / dequoting / multi-word coalesce / § auto-quote)
  E3  trailing comma before ``]``
  E4  constructor canonicalization ``NAME[a,b]`` -> ``NAME<a,b>`` (GH#276),
      added from the R5 corpus run; refused when it would join words
  E5  envelope completion (``===INFERRED===`` / ``===END===`` added)
"""

from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Any

import pytest

from octave_mcp.mcp.write import WriteTool

_TOOL = WriteTool()


async def _ok(path: Path, **kwargs: Any) -> dict[str, Any]:
    result = await _TOOL.execute(target_path=str(path), **kwargs)
    assert result["status"] == "success", result
    assert "fidelity_violations" not in result
    return result


def _codes(result: dict[str, Any]) -> list[str]:
    return [c.get("code", "") for c in result["corrections"]]


class TestContentModeEquivalences:
    async def test_e1_ascii_operators(self, tmp_path: Path) -> None:
        content = '===D===\nMETA:\n  TYPE::T\n  VERSION::"1"\nK::[a->b, c + d, x vs y]\n===END===\n'
        result = await _ok(tmp_path / "e1.oct.md", content=content)
        assert result["corrections"], "the alias rewrite must be logged"
        assert "a→b" in (tmp_path / "e1.oct.md").read_text(encoding="utf-8")

    async def test_e2_multi_word_coalesce(self, tmp_path: Path) -> None:
        result = await _ok(tmp_path / "e2.oct.md", content="===D===\nK::hello wide world\n===END===\n")
        assert "W_LENIENT_MULTI_WORD_COALESCE" in _codes(result)

    async def test_e2_section_reference_auto_quote(self, tmp_path: Path) -> None:
        path = tmp_path / "e2s.oct.md"
        await _ok(path, content="===D===\nX::§A\n===END===\n")
        assert 'X::"§A"' in path.read_text(encoding="utf-8")

    async def test_e2_identifier_dequote(self, tmp_path: Path) -> None:
        result = await _ok(tmp_path / "e2d.oct.md", content='===D===\nW::"abc"\nV::"5"\n===END===\n')
        assert "TN_IDENTIFIER_DEQUOTE" in _codes(result)

    async def test_e2_dequote_with_ascii_alias_inside_the_run(self, tmp_path: Path) -> None:
        """``#1`` lexes as SECTION(#→§) + NUMBER; the output quotes it as "§1"."""
        await _ok(tmp_path / "e2a.oct.md", content="===D===\nREF::#1\n===END===\n")

    async def test_e3_trailing_comma(self, tmp_path: Path) -> None:
        await _ok(tmp_path / "e3.oct.md", content="===D===\nL::[a,b,]\n===END===\n")

    async def test_e4_constructor_canonicalization(self, tmp_path: Path) -> None:
        path = tmp_path / "e4.oct.md"
        await _ok(path, content="===D===\nC::[REQ[mandatory], OPT[a, b]]\n===END===\n")
        written = path.read_text(encoding="utf-8")
        assert "REQ<mandatory>" in written and "OPT<a,b>" in written

    @pytest.mark.parametrize(
        "content",
        [
            pytest.param("A::1\nB::two\n", id="no_envelope"),
            pytest.param("===X===\nA::1\n", id="no_end_marker"),
        ],
    )
    async def test_e5_envelope_completion(self, tmp_path: Path, content: str) -> None:
        await _ok(tmp_path / "e5.oct.md", content=content)

    async def test_e0_decomposed_unicode_is_logged(self, tmp_path: Path) -> None:
        decomposed = '===D===\nK::"cafe\u0301"\n===END===\n'
        assert unicodedata.normalize("NFC", decomposed) != decomposed
        path = tmp_path / "e0.oct.md"
        result = await _ok(path, content=decomposed)
        assert "NFC_NORMALIZATION" in _codes(result)
        assert "caf\u00e9" in path.read_text(encoding="utf-8")

    async def test_markdown_fence_unwrap(self, tmp_path: Path) -> None:
        result = await _ok(tmp_path / "md.oct.md", content="```octave\n===D===\nK::v\n===END===\n```")
        assert "W_MARKDOWN_UNWRAP" in _codes(result)

    async def test_plain_text_wrap_keeps_the_raw_text(self, tmp_path: Path) -> None:
        path = tmp_path / "raw.oct.md"
        await _ok(path, content="Hello, world!", lenient=True)
        assert 'RAW::"Hello, world!"' in path.read_text(encoding="utf-8")

    async def test_yaml_frontmatter_segment(self, tmp_path: Path) -> None:
        path = tmp_path / "fm.oct.md"
        await _ok(path, content="---\nname: agent\ndescription: plain\n---\n\n===D===\nK::v\n===END===\n")
        assert path.read_text(encoding="utf-8").startswith("---\nname: agent\n")

    async def test_lenient_enum_casefold_tier_repair(self, tmp_path: Path) -> None:
        content = '===META_SCHEMA===\nMETA:\n  TYPE::META\n  VERSION::"1.0.0"\n  STATUS::draft\n===END==='
        path = tmp_path / "enum.oct.md"
        result = await _ok(path, content=content, schema="META", lenient=True)
        assert "ENUM_CASEFOLD" in _codes(result)
        assert "STATUS::DRAFT" in path.read_text(encoding="utf-8")

    async def test_salvage_keeps_the_raw_text(self, tmp_path: Path) -> None:
        path = tmp_path / "salvage.oct.md"
        await _ok(path, content="===DOC===\nKEY::a\tb\n===END===", lenient=True, parse_error_policy="salvage")
        assert "_PARSE_ERROR_LINE_2" in path.read_text(encoding="utf-8")

    async def test_mutations_in_content_mode(self, tmp_path: Path) -> None:
        path = tmp_path / "mut.oct.md"
        content = '===D===\nMETA:\n  TYPE::T\n  VERSION::"1"\nK::v\n===END===\n'
        await _ok(path, content=content, mutations={"VERSION": "2", "STATUS": "ACTIVE"})
        written = path.read_text(encoding="utf-8")
        assert 'VERSION::"2"' in written or "VERSION::2" in written
        assert "STATUS::ACTIVE" in written


class TestFormatStyles:
    async def test_expanded_lifts_inline_map_list_to_block(self, tmp_path: Path) -> None:
        path = tmp_path / "exp.oct.md"
        await _ok(path, content="===D===\nA::[K::V,L::W]\n===END===\n", format_style="expanded")
        assert "A:\n  K::V\n  L::W" in path.read_text(encoding="utf-8")

    async def test_compact_returns_block_to_brackets(self, tmp_path: Path) -> None:
        path = tmp_path / "cmp.oct.md"
        from octave_mcp.core.ast_nodes import ListValue
        from octave_mcp.core.parser import parse

        await _ok(path, content="===D===\nA:\n  K::V\n  L::W\n===END===\n", format_style="compact")
        node = parse(path.read_text(encoding="utf-8")).sections[0]
        assert isinstance(node.value, ListValue), "compact must return the block to bracket form"

    async def test_compact_refuses_comment_bearing_block_and_keeps_comments(self, tmp_path: Path) -> None:
        content = "===D===\nOUTER:\n  // keep this note\n  INNER:\n    K::V\n    L::W\n  X::y\n===END===\n"
        path = tmp_path / "cmpc.oct.md"
        result = await _ok(path, content=content, format_style="compact")
        assert "W_COMPACT_REFUSED" in _codes(result)
        assert "// keep this note" in path.read_text(encoding="utf-8")

    async def test_direct_inline_map_value_under_expanded(self, tmp_path: Path) -> None:
        path = tmp_path / "direct.oct.md"
        path.write_text('===D===\nMETA:\n  TYPE::T\n  VERSION::"1"\nX::old\n===END===\n', encoding="utf-8")
        await _ok(path, changes={"X": {"a": "one", "b": "two"}}, format_style="expanded")
        assert "X:\n  a::one\n  b::two" in path.read_text(encoding="utf-8")


class TestChangesModePathForms:
    """Each path form masks exactly its resolved target (C2, round 3)."""

    async def test_literal_dotted_key_alongside_block_child(self, tmp_path: Path) -> None:
        path = tmp_path / "dotted.oct.md"
        path.write_text("===D===\nP1:\n  X::block_child\nP1.1::flat\nZ::z\n===END===\n", encoding="utf-8")
        await _ok(path, changes={"P1.1": "changed"})
        written = path.read_text(encoding="utf-8")
        assert "P1.1::changed" in written and "X::block_child" in written

    async def test_meta_field_in_meta_envelope(self, tmp_path: Path) -> None:
        path = tmp_path / "metaenv.oct.md"
        path.write_text('===META===\nTYPE::T\nVERSION::"1"\nSTATUS::DRAFT\n===END===\n', encoding="utf-8")
        await _ok(path, changes={"META.STATUS": "ACTIVE"})
        written = path.read_text(encoding="utf-8")
        assert "STATUS::ACTIVE" in written and "TYPE::T" in written

    async def test_anchored_path(self, tmp_path: Path) -> None:
        path = tmp_path / "anchored.oct.md"
        path.write_text(
            "===D===\nITEMS:\n  NAME::a\n  STATE::old\n  NAME::b\n  STATE::other\n===END===\n", encoding="utf-8"
        )
        await _ok(path, changes={"NAME/STATE": "new"})
        assert "STATE::new" in path.read_text(encoding="utf-8")

    async def test_named_section_path(self, tmp_path: Path) -> None:
        path = tmp_path / "secname.oct.md"
        path.write_text("===D===\n§1::ONE\n  K::v\n  L::w\n§2::TWO\n  M::x\n===END===\n", encoding="utf-8")
        await _ok(path, changes={"§1::ONE.K": "changed"})
        written = path.read_text(encoding="utf-8")
        assert "K::changed" in written and "L::w" in written and "M::x" in written


class TestC1GapAccounting:
    """C1 (round 3): the dirty node's baseline slice is split at its trailing
    gap of blank or comment-only lines; only the body is compared."""

    @pytest.mark.parametrize(
        ("node_text", "body", "gap"),
        [
            pytest.param("§1::ONE\n  A::x\n\n", "§1::ONE\n  A::x\n", "\n", id="trailing_blank"),
            pytest.param(
                "§1::ONE\n  A::x\n  // trailing note\n\n",
                "§1::ONE\n  A::x\n",
                "  // trailing note\n\n",
                id="trailing_comment_line",
            ),
            pytest.param("§1::ONE\n  A::x\n", "§1::ONE\n  A::x\n", "", id="no_gap"),
        ],
    )
    def test_split_node_gap(self, node_text: str, body: str, gap: str) -> None:
        from octave_mcp.mcp.write_fidelity import split_node_gap

        assert split_node_gap(node_text) == (body, gap)

    @pytest.mark.parametrize(
        "baseline",
        [
            pytest.param("===D===\n§1::ONE\n  A::x\n\n§2::TWO\n  B::y\n===END===\n", id="trailing_blank"),
            pytest.param(
                "===D===\n§1::ONE\n  A::x\n  // trailing note\n\n§2::TWO\n  B::y\n===END===\n",
                id="trailing_comment_line",
            ),
        ],
    )
    async def test_dirty_node_with_gap_is_not_a_false_refusal(self, tmp_path: Path, baseline: str) -> None:
        path = tmp_path / "gap.oct.md"
        path.write_text(baseline, encoding="utf-8")
        await _ok(path, changes={"§1.A": "changed"}, format_style="preserve")
        assert "A::changed" in path.read_text(encoding="utf-8")


class TestSemanticProjection:
    """Unit tests for semantic_projection() (CE finding 5)."""

    _TEXT = (
        '===D===\nMETA:\n  TYPE::T\n  VERSION::"1"\n'
        "// lead\nK::v\nL::[a,b]\nB:\n  X::1\n§1::S\n  Y::true\n===END===\n"
    )

    def _proj(self, text: str) -> Any:
        from octave_mcp.mcp.write_fidelity import semantic_projection

        from octave_mcp.core.parser import parse

        return semantic_projection(parse(text))

    def test_two_parses_project_equal(self) -> None:
        assert self._proj(self._TEXT) == self._proj(self._TEXT)

    @pytest.mark.parametrize(
        ("old", "new"),
        [
            pytest.param("K::v", "K::w", id="scalar"),
            pytest.param("L::[a,b]", "L::[a,c]", id="list_item"),
            pytest.param("  X::1", "  X::2", id="child"),
            pytest.param("  Y::true", "  Y::false", id="bool"),
            pytest.param('VERSION::"1"', 'VERSION::"2"', id="meta"),
        ],
    )
    def test_changes_project_unequal(self, old: str, new: str) -> None:
        assert self._TEXT.count(old) == 1
        assert self._proj(self._TEXT) != self._proj(self._TEXT.replace(old, new))

    def test_spans_trivia_and_comments_do_not_affect_equality(self) -> None:
        spaced = self._TEXT.replace("// lead\n", "").replace("K::v\n", "\n\nK::v\n")
        assert self._proj(self._TEXT) == self._proj(spaced)

    def test_mapping_equivalence(self) -> None:
        inline_list = self._proj("===D===\nA::[K::V,L::W]\n===END===\n")
        block = self._proj("===D===\nA:\n  K::V\n  L::W\n===END===\n")
        assert inline_list == block
