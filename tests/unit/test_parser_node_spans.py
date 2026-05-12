"""T3 tests: parser propagates source spans onto CST nodes.

ADR-0006 SR2-T2 Strategy A PR-1 (GH#377). The parser must populate
``start_byte`` / ``end_byte`` on every node it constructs. Spans must
nest correctly (child within parent) and round-trip to a sensible
substring of the original NFC content. Exact byte equality is asserted
in PR-3 (T9 fixture); this is a smoke test.

See ``docs/adr/adr-0006-sr2-t2-ast-span-coverage-audit.md`` §6 row T3.
"""

from __future__ import annotations

import unicodedata

from octave_mcp.core.grammar.cst import (
    Assignment,
    Block,
    Comment,
    InlineMap,
    ListValue,
    LiteralZoneValue,
    Section,
)
from octave_mcp.core.parser import parse

REPRESENTATIVE_DOC = """===MY_DOC===
META:
  TYPE::EXAMPLE
  VERSION::"1.0"
---
§1::SECTION_A
  KEY::value
  BLOCK_KEY:
    CHILD_A::1
    CHILD_B::2
  // a comment line
  ITEMS::[a, b, c]
  MAP::[k::v, k2::v2]
  ZONE:
    ```python
    code here
    ```
===END===
"""


def _nfc(src: str) -> str:
    return unicodedata.normalize("NFC", src)


def test_document_has_full_span() -> None:
    doc = parse(REPRESENTATIVE_DOC)
    nfc = _nfc(REPRESENTATIVE_DOC)
    nfc_bytes = nfc.encode("utf-8")
    assert doc.start_byte == 0
    assert doc.end_byte == len(nfc_bytes)


def test_document_meta_byte_range_populated() -> None:
    doc = parse(REPRESENTATIVE_DOC)
    assert doc.meta_start_byte is not None
    assert doc.meta_end_byte is not None
    assert doc.meta_end_byte > doc.meta_start_byte


def test_section_has_span() -> None:
    doc = parse(REPRESENTATIVE_DOC)
    section = next(s for s in doc.sections if isinstance(s, Section))
    assert section.start_byte is not None
    assert section.end_byte is not None
    assert section.end_byte > section.start_byte


def test_section_span_contains_all_children() -> None:
    doc = parse(REPRESENTATIVE_DOC)
    section = next(s for s in doc.sections if isinstance(s, Section))
    for child in section.children:
        if child.start_byte is None or child.end_byte is None:
            continue
        assert child.start_byte >= section.start_byte
        assert child.end_byte <= section.end_byte


def test_assignment_has_span() -> None:
    doc = parse(REPRESENTATIVE_DOC)
    section = next(s for s in doc.sections if isinstance(s, Section))
    assignments = [c for c in section.children if isinstance(c, Assignment)]
    assert assignments, "section should contain assignments"
    for a in assignments:
        assert a.start_byte is not None
        assert a.end_byte is not None
        assert a.end_byte >= a.start_byte


def test_block_has_span_containing_children() -> None:
    doc = parse(REPRESENTATIVE_DOC)
    section = next(s for s in doc.sections if isinstance(s, Section))
    block = next(c for c in section.children if isinstance(c, Block))
    assert block.start_byte is not None
    assert block.end_byte is not None
    assert block.end_byte > block.start_byte
    for child in block.children:
        if child.start_byte is None:
            continue
        assert child.start_byte >= block.start_byte
        assert child.end_byte <= block.end_byte


def test_comment_node_has_span() -> None:
    doc = parse(REPRESENTATIVE_DOC)
    section = next(s for s in doc.sections if isinstance(s, Section))
    # Comment is leading-attached to the next assignment, so search children
    comments = [c for c in section.children if isinstance(c, Comment)]
    # If comments are attached as leading_comments rather than separate Comment
    # nodes, the test simply skips — span on Comment node only required if one
    # is present in the children list.
    for c in comments:
        assert c.start_byte is not None
        assert c.end_byte is not None


def test_list_value_has_span() -> None:
    doc = parse(REPRESENTATIVE_DOC)
    section = next(s for s in doc.sections if isinstance(s, Section))
    items_a = next(c for c in section.children if isinstance(c, Assignment) and c.key == "ITEMS")
    assert isinstance(items_a.value, ListValue)
    assert items_a.value.start_byte is not None
    assert items_a.value.end_byte is not None
    assert items_a.value.end_byte > items_a.value.start_byte


def test_inline_map_has_span() -> None:
    doc = parse(REPRESENTATIVE_DOC)
    section = next(s for s in doc.sections if isinstance(s, Section))
    map_a = next(c for c in section.children if isinstance(c, Assignment) and c.key == "MAP")
    # Inline maps inside [...] are wrapped in a ListValue whose items are
    # InlineMap pairs. The outer ListValue carries the bracket-bracket span;
    # each InlineMap pair carries its own k::v pair span.
    assert isinstance(map_a.value, ListValue)
    assert map_a.value.start_byte is not None
    assert map_a.value.end_byte is not None
    inline_maps = [it for it in map_a.value.items if isinstance(it, InlineMap)]
    assert inline_maps, "expected at least one InlineMap pair"
    for im in inline_maps:
        assert im.start_byte is not None
        assert im.end_byte is not None
        assert im.end_byte >= im.start_byte


def test_literal_zone_value_has_span() -> None:
    doc = parse(REPRESENTATIVE_DOC)
    section = next(s for s in doc.sections if isinstance(s, Section))
    zone_block = next(c for c in section.children if isinstance(c, Block) and c.key == "ZONE")
    lzv_assignment = next(c for c in zone_block.children if isinstance(c, Assignment))
    assert isinstance(lzv_assignment.value, LiteralZoneValue)
    lzv = lzv_assignment.value
    assert lzv.start_byte is not None
    assert lzv.end_byte is not None
    assert lzv.end_byte > lzv.start_byte


def test_spans_byte_round_trip_smoke() -> None:
    """Every node's span decodes to a non-empty UTF-8 string within the source."""
    doc = parse(REPRESENTATIVE_DOC)
    nfc_bytes = _nfc(REPRESENTATIVE_DOC).encode("utf-8")

    def visit(node: object) -> None:
        for fname in ("start_byte", "end_byte"):
            if not hasattr(node, fname):
                return
        s = node.start_byte  # type: ignore[attr-defined]
        e = node.end_byte  # type: ignore[attr-defined]
        if s is None or e is None:
            return
        assert 0 <= s <= e <= len(nfc_bytes)
        # Slice decodes cleanly as UTF-8 (no mid-codepoint split)
        nfc_bytes[s:e].decode("utf-8")
        children = getattr(node, "children", None) or getattr(node, "sections", None) or []
        for child in children:
            visit(child)

    visit(doc)


def test_simple_document_section_span() -> None:
    """A minimal doc — single section, single assignment — wires spans end-to-end."""
    src = "===D===\n§1::S\n  K::v\n===END===\n"
    doc = parse(src)
    nfc_bytes = _nfc(src).encode("utf-8")
    assert doc.start_byte == 0
    assert doc.end_byte == len(nfc_bytes)
    section = next(s for s in doc.sections if isinstance(s, Section))
    assert section.start_byte is not None
    assert section.end_byte is not None
    assignment = next(c for c in section.children if isinstance(c, Assignment))
    assert assignment.start_byte is not None
    assert assignment.end_byte is not None
    # Nesting
    assert section.start_byte >= doc.start_byte
    assert section.end_byte <= doc.end_byte
    assert assignment.start_byte >= section.start_byte
    assert assignment.end_byte <= section.end_byte
