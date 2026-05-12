"""T2 tests: CST node span / dirty / repaired field infrastructure.

ADR-0006 SR2-T2 Strategy A PR-1 (GH#377). Adds infrastructure fields to
``ASTNode`` (and minimal span pair to value types). PR-1 only verifies
that the fields exist and have correct defaults — population on the
parser side is exercised by ``test_parser_node_spans.py``.

See ``docs/adr/adr-0006-sr2-t2-ast-span-coverage-audit.md`` §6 row T2.
"""

from __future__ import annotations

from octave_mcp.core.grammar.cst import (
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


class TestASTNodeBaseFields:
    """ASTNode base must carry span + dirty/repaired infra fields."""

    def test_assignment_has_span_fields(self) -> None:
        node = Assignment()
        assert hasattr(node, "start_byte")
        assert hasattr(node, "end_byte")
        assert node.start_byte is None
        assert node.end_byte is None

    def test_assignment_has_dirty_repaired_defaults(self) -> None:
        node = Assignment()
        assert hasattr(node, "dirty")
        assert hasattr(node, "repaired")
        assert node.dirty is False
        assert node.repaired is False

    def test_assignment_has_comment_block_start_byte(self) -> None:
        node = Assignment()
        assert hasattr(node, "comment_block_start_byte")
        assert node.comment_block_start_byte is None

    def test_block_has_all_infrastructure_fields(self) -> None:
        node = Block()
        for fname in ("start_byte", "end_byte", "dirty", "repaired", "comment_block_start_byte"):
            assert hasattr(node, fname)

    def test_section_has_all_infrastructure_fields(self) -> None:
        node = Section()
        for fname in ("start_byte", "end_byte", "dirty", "repaired", "comment_block_start_byte"):
            assert hasattr(node, fname)

    def test_comment_has_all_infrastructure_fields(self) -> None:
        node = Comment()
        for fname in ("start_byte", "end_byte", "dirty", "repaired", "comment_block_start_byte"):
            assert hasattr(node, fname)


class TestDocumentSpanFields:
    """Document gets full span infra plus meta_start_byte / meta_end_byte."""

    def test_document_has_span_fields(self) -> None:
        doc = Document()
        assert doc.start_byte is None
        assert doc.end_byte is None
        assert doc.dirty is False
        assert doc.repaired is False

    def test_document_has_meta_byte_range(self) -> None:
        doc = Document()
        assert hasattr(doc, "meta_start_byte")
        assert hasattr(doc, "meta_end_byte")
        assert doc.meta_start_byte is None
        assert doc.meta_end_byte is None


class TestValueTypeSpanFields:
    """Value types get span pair only — NOT dirty/repaired (parent owns dirtiness)."""

    def test_list_value_has_span_pair_only(self) -> None:
        lv = ListValue()
        assert hasattr(lv, "start_byte")
        assert hasattr(lv, "end_byte")
        assert lv.start_byte is None
        assert lv.end_byte is None
        # Value types do NOT carry dirty/repaired (parent owns dirtiness)
        assert not hasattr(lv, "dirty")
        assert not hasattr(lv, "repaired")

    def test_inline_map_has_span_pair_only(self) -> None:
        m = InlineMap()
        assert m.start_byte is None
        assert m.end_byte is None
        assert not hasattr(m, "dirty")

    def test_holographic_value_has_span_pair_only(self) -> None:
        hv = HolographicValue(example="x", constraints=None, target=None)
        assert hv.start_byte is None
        assert hv.end_byte is None
        assert not hasattr(hv, "dirty")

    def test_literal_zone_value_has_span_pair_only(self) -> None:
        lzv = LiteralZoneValue()
        assert lzv.start_byte is None
        assert lzv.end_byte is None
        assert not hasattr(lzv, "dirty")


class TestFieldAcceptance:
    """Constructors must accept the new fields as keyword arguments."""

    def test_assignment_accepts_span_kwargs(self) -> None:
        a = Assignment(key="K", value="v", start_byte=10, end_byte=15, dirty=True, repaired=True)
        assert a.start_byte == 10
        assert a.end_byte == 15
        assert a.dirty is True
        assert a.repaired is True

    def test_document_accepts_meta_range_kwargs(self) -> None:
        d = Document(meta_start_byte=5, meta_end_byte=50)
        assert d.meta_start_byte == 5
        assert d.meta_end_byte == 50

    def test_list_value_accepts_span_kwargs(self) -> None:
        lv = ListValue(items=[1, 2], start_byte=0, end_byte=10)
        assert lv.start_byte == 0
        assert lv.end_byte == 10
