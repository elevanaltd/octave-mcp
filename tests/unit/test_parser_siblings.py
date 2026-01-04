"""Tests for Issue #81: Parser sibling block detection with implicit dedent.

This test file validates that the parser correctly identifies sibling blocks
when there is no explicit INDENT token (implicit dedent to column 0).

Bug: When parser consumes NEWLINE and encounters IDENTIFIER at column 0 without
preceding INDENT token, it should infer dedent to level 0 and break out of
nested block parsing. Instead, it was treating the identifier as a child of
the innermost block.

TDD: RED phase - these tests must FAIL before implementation.
"""

from octave_mcp.core.ast_nodes import Assignment, Block
from octave_mcp.core.emitter import emit
from octave_mcp.core.parser import parse


class TestSiblingBlocksWithImplicitDedent:
    """Test that blocks at same level are parsed as siblings, not parent-child."""

    def test_parses_sibling_blocks_after_nested_block(self):
        """Test that blocks at same level are siblings, not parent-child after nested content.

        Structure:
        - TEST section
          - BLOCK_A (child of TEST)
            - STATUS (child of BLOCK_A)
            - TASKS (child of BLOCK_A)
              - task_1 (child of TASKS)
              - task_2 (child of TASKS)
          - BLOCK_B (child of TEST, sibling of BLOCK_A)  <-- BUG: was becoming child of TASKS
            - STATUS (child of BLOCK_B)
        """
        source = """===TEST===
BLOCK_A:
  STATUS::COMPLETE
  TASKS:
    task_1::DONE
    task_2::DONE
BLOCK_B:
  STATUS::PENDING
===END==="""
        doc = parse(source)

        # Should have one section named "TEST"
        assert doc.name == "TEST"

        # TEST section should have 2 top-level children: BLOCK_A and BLOCK_B
        assert len(doc.sections) == 2, (
            f"Expected 2 top-level blocks (BLOCK_A, BLOCK_B), got {len(doc.sections)}: "
            f"{[getattr(s, 'key', getattr(s, 'name', str(s))) for s in doc.sections]}"
        )

        block_a = doc.sections[0]
        block_b = doc.sections[1]

        # Verify BLOCK_A structure
        assert isinstance(block_a, Block), f"Expected Block, got {type(block_a)}"
        assert block_a.key == "BLOCK_A"

        # Verify BLOCK_B structure (this is the bug - pre-fix BLOCK_B is nested wrong)
        assert isinstance(block_b, Block), f"Expected Block, got {type(block_b)}"
        assert block_b.key == "BLOCK_B", f"Expected BLOCK_B as second top-level block, got {block_b.key}"

    def test_parses_simple_sibling_blocks_no_deep_nesting(self):
        """Test basic sibling detection without deep nesting."""
        source = """===TEST===
FIRST:
  VALUE::one
SECOND:
  VALUE::two
===END==="""
        doc = parse(source)

        assert (
            len(doc.sections) == 2
        ), f"Expected 2 blocks, got {len(doc.sections)}: {[getattr(s, 'key', str(s)) for s in doc.sections]}"
        assert doc.sections[0].key == "FIRST"
        assert doc.sections[1].key == "SECOND"

    def test_parses_three_sibling_blocks(self):
        """Test three sibling blocks at same level."""
        source = """===TEST===
ALPHA:
  STATUS::A
BETA:
  STATUS::B
GAMMA:
  STATUS::C
===END==="""
        doc = parse(source)

        assert len(doc.sections) == 3, f"Expected 3 blocks, got {len(doc.sections)}"
        assert doc.sections[0].key == "ALPHA"
        assert doc.sections[1].key == "BETA"
        assert doc.sections[2].key == "GAMMA"

    def test_mixed_assignments_and_blocks_as_siblings(self):
        """Test mixed content types at same level."""
        source = """===TEST===
SETTING::value
CONFIG:
  NESTED::data
ANOTHER_SETTING::value2
===END==="""
        doc = parse(source)

        # Should have 3 sections: Assignment, Block, Assignment
        assert len(doc.sections) == 3, f"Expected 3 sections, got {len(doc.sections)}"
        assert isinstance(doc.sections[0], Assignment)
        assert isinstance(doc.sections[1], Block)
        assert isinstance(doc.sections[2], Assignment)


class TestIdempotenceWithSiblingBlocks:
    """Test that emit->parse->emit produces identical output (idempotence)."""

    def test_emits_parses_idempotent_with_nested_siblings(self):
        """Verify emit->parse->emit cycle preserves structure with nested siblings."""
        source = """===TEST===
BLOCK_A:
  TASKS:
    task::DONE
BLOCK_B:
  STATUS::OK
===END==="""

        # First cycle
        doc1 = parse(source)
        emitted1 = emit(doc1)

        # Second cycle
        doc2 = parse(emitted1)
        emitted2 = emit(doc2)

        # Idempotence: second emit should equal first emit
        assert emitted1 == emitted2, f"Idempotence violated!\nFirst emit:\n{emitted1}\nSecond emit:\n{emitted2}"

    def test_round_trip_preserves_sibling_structure(self):
        """Verify structure is preserved through round-trip."""
        source = """===TEST===
A:
  DEEP:
    DEEPER::value
B:
  SHALLOW::value
===END==="""

        doc1 = parse(source)

        # Verify initial structure
        assert len(doc1.sections) == 2, "Pre-roundtrip: Expected 2 sibling blocks"
        assert doc1.sections[0].key == "A"
        assert doc1.sections[1].key == "B"

        # Round-trip
        emitted = emit(doc1)
        doc2 = parse(emitted)

        # Verify preserved structure
        assert len(doc2.sections) == 2, "Post-roundtrip: Expected 2 sibling blocks"
        assert doc2.sections[0].key == "A"
        assert doc2.sections[1].key == "B"

    def test_complex_nesting_idempotence(self):
        """Test complex nested structure maintains idempotence."""
        source = """===COMPLEX===
LEVEL1_A:
  LEVEL2_A:
    LEVEL3::value_a
  LEVEL2_B:
    LEVEL3::value_b
LEVEL1_B:
  LEVEL2::value_c
===END==="""

        doc1 = parse(source)
        emitted1 = emit(doc1)
        doc2 = parse(emitted1)
        emitted2 = emit(doc2)

        # Idempotence check
        assert emitted1 == emitted2, f"Complex nesting idempotence violated!\nFirst:\n{emitted1}\nSecond:\n{emitted2}"


class TestEdgeCases:
    """Edge cases for sibling detection."""

    def test_empty_nested_block_followed_by_sibling(self):
        """Test empty block followed by sibling at same level."""
        source = """===TEST===
EMPTY:
SIBLING:
  VALUE::present
===END==="""
        doc = parse(source)

        # Note: Empty blocks may or may not be preserved depending on implementation
        # At minimum, SIBLING should be parsed as top-level, not child of EMPTY
        sibling_found = any(getattr(s, "key", None) == "SIBLING" for s in doc.sections)
        assert sibling_found, "SIBLING block should be at top level"

    def test_assignment_after_deeply_nested_block(self):
        """Test assignment at root level after deep nesting."""
        source = """===TEST===
DEEP:
  DEEPER:
    DEEPEST::value
ROOT_ASSIGNMENT::back_at_root
===END==="""
        doc = parse(source)

        # Should have 2 sections: DEEP block and ROOT_ASSIGNMENT assignment
        assert len(doc.sections) == 2, f"Expected 2 sections, got {len(doc.sections)}"
        assert doc.sections[0].key == "DEEP"
        assert doc.sections[1].key == "ROOT_ASSIGNMENT"
        assert isinstance(doc.sections[1], Assignment)


class TestSectionMarkerSiblings:
    """Test that section markers with children do not absorb column-0 siblings.

    GH#81 rework: The same implicit dedent bug exists in parse_section_marker
    as was fixed in the block parsing loop. Section markers with indented children
    should not swallow sibling blocks or assignments at column 0.
    """

    def test_section_marker_does_not_absorb_column0_block_sibling(self):
        """Section marker with children should not swallow sibling block at column 0.

        Bug: parse_section_marker resets current_line_indent=0 on NEWLINE (line 351)
        but does NOT check current_line_indent < child_indent before parsing child.
        This causes SIBLING_BLOCK to be incorrectly absorbed as child of CONTEXT.
        """
        source = """===TEST===
\u00a7CONTEXT::info
  NESTED::child
SIBLING_BLOCK:
  VALUE::data
===END==="""
        doc = parse(source)

        # Should have 2 top-level sections: Section(CONTEXT) and Block(SIBLING_BLOCK)
        assert len(doc.sections) == 2, (
            f"Expected 2 top-level sections (CONTEXT, SIBLING_BLOCK), got {len(doc.sections)}: "
            f"{[getattr(s, 'key', getattr(s, 'section_id', str(s))) for s in doc.sections]}"
        )

        # First should be Section marker
        from octave_mcp.core.ast_nodes import Section

        assert isinstance(doc.sections[0], Section), f"Expected Section, got {type(doc.sections[0])}"
        assert doc.sections[0].key == "info" or doc.sections[0].section_id == "CONTEXT"

        # Second should be Block
        assert isinstance(doc.sections[1], Block), f"Expected Block, got {type(doc.sections[1])}"
        assert doc.sections[1].key == "SIBLING_BLOCK"

    def test_section_marker_does_not_absorb_column0_assignment_sibling(self):
        """Section marker with children should not swallow sibling assignment at column 0."""
        source = """===TEST===
\u00a71::FIRST_SECTION
  CHILD::value
SIBLING_ASSIGNMENT::at_root
===END==="""
        doc = parse(source)

        # Should have 2 top-level sections
        assert (
            len(doc.sections) == 2
        ), f"Expected 2 sections, got {len(doc.sections)}: {[getattr(s, 'key', str(s)) for s in doc.sections]}"

        # First is Section marker
        from octave_mcp.core.ast_nodes import Section

        assert isinstance(doc.sections[0], Section)
        assert doc.sections[0].section_id == "1"

        # Second is Assignment
        assert isinstance(doc.sections[1], Assignment)
        assert doc.sections[1].key == "SIBLING_ASSIGNMENT"

    def test_section_marker_with_deep_nesting_and_block_sibling(self):
        """Section marker with deeply nested children should not absorb column-0 block."""
        source = """===TEST===
\u00a7MAIN::SECTION
  LEVEL1:
    LEVEL2::deep_value
SIBLING_BLOCK:
  STATUS::ok
===END==="""
        doc = parse(source)

        # Should have 2 top-level sections
        assert len(doc.sections) == 2, f"Expected 2 sections, got {len(doc.sections)}"

        from octave_mcp.core.ast_nodes import Section

        assert isinstance(doc.sections[0], Section)
        assert isinstance(doc.sections[1], Block)
        assert doc.sections[1].key == "SIBLING_BLOCK"

    def test_multiple_section_markers_as_siblings(self):
        """Multiple section markers at same level should all be siblings."""
        source = """===TEST===
\u00a71::FIRST
  A::value_a
\u00a72::SECOND
  B::value_b
\u00a73::THIRD
  C::value_c
===END==="""
        doc = parse(source)

        # Should have 3 top-level section markers
        assert len(doc.sections) == 3, f"Expected 3 sections, got {len(doc.sections)}"

        from octave_mcp.core.ast_nodes import Section

        for i, section in enumerate(doc.sections, start=1):
            assert isinstance(section, Section), f"Section {i} should be Section, got {type(section)}"
            assert section.section_id == str(i)
