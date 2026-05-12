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


# ---------------------------------------------------------------------------
# PR-2 T5 (ADR-0006 SR2-T2 Strategy A): body_dirty + Document.meta_dirty +
# Document.trailing_comments byte range.
#
# PR-2 introduces refined dirty-bit infrastructure so that Block/Section
# bodies can be marked re-emittable while keeping their headers spliced,
# and so that Document META can mark individual keys dirty without
# blowing the whole META region's diff footprint. The trailing-comments
# byte range supports the ADR §3 subsection policy (slice unchanged when
# clean, re-emit when dirty).
#
# These fields are infrastructure-only in PR-2 — the emitter consumes
# them in PR-3 (T8). PR-2 tests only assert presence + default state +
# kwarg acceptance.
# ---------------------------------------------------------------------------


class TestBlockBodyDirty:
    """Block.body_dirty is False by default and accepted as a kwarg."""

    def test_body_dirty_default_false(self) -> None:
        block = Block()
        assert hasattr(block, "body_dirty")
        assert block.body_dirty is False

    def test_body_dirty_independent_of_dirty(self) -> None:
        block = Block()
        block.body_dirty = True
        assert block.body_dirty is True
        # body_dirty is distinct from whole-node dirty
        assert block.dirty is False

    def test_body_dirty_accepted_as_kwarg(self) -> None:
        block = Block(key="K", body_dirty=True)
        assert block.body_dirty is True


class TestSectionBodyDirty:
    """Section.body_dirty mirrors Block — bodies can re-emit while header splices."""

    def test_body_dirty_default_false(self) -> None:
        section = Section()
        assert hasattr(section, "body_dirty")
        assert section.body_dirty is False

    def test_body_dirty_independent_of_dirty(self) -> None:
        section = Section()
        section.body_dirty = True
        assert section.body_dirty is True
        assert section.dirty is False

    def test_body_dirty_accepted_as_kwarg(self) -> None:
        section = Section(section_id="1", key="S", body_dirty=True)
        assert section.body_dirty is True


class TestDocumentMetaDirty:
    """Document.meta_dirty is a per-key dict marking META fields touched."""

    def test_meta_dirty_default_empty_dict(self) -> None:
        doc = Document()
        assert hasattr(doc, "meta_dirty")
        assert doc.meta_dirty == {}
        assert isinstance(doc.meta_dirty, dict)

    def test_meta_dirty_independent_per_document_instance(self) -> None:
        """Defaults must not share a mutable dict across instances (default_factory)."""
        doc_a = Document()
        doc_b = Document()
        doc_a.meta_dirty["STATUS"] = True
        # doc_b's dict must remain empty — no shared mutable default
        assert doc_b.meta_dirty == {}

    def test_meta_dirty_per_key_set_get(self) -> None:
        doc = Document()
        doc.meta_dirty["STATUS"] = True
        doc.meta_dirty["VERSION"] = True
        assert doc.meta_dirty["STATUS"] is True
        assert doc.meta_dirty["VERSION"] is True
        assert "UPDATED" not in doc.meta_dirty


class TestDocumentTrailingCommentsByteRange:
    """Document.trailing_comments_start_byte/end_byte mark the trailing band."""

    def test_trailing_comments_byte_range_defaults_none(self) -> None:
        doc = Document()
        assert hasattr(doc, "trailing_comments_start_byte")
        assert hasattr(doc, "trailing_comments_end_byte")
        assert doc.trailing_comments_start_byte is None
        assert doc.trailing_comments_end_byte is None

    def test_trailing_comments_byte_range_accepts_kwargs(self) -> None:
        doc = Document(trailing_comments_start_byte=100, trailing_comments_end_byte=120)
        assert doc.trailing_comments_start_byte == 100
        assert doc.trailing_comments_end_byte == 120
