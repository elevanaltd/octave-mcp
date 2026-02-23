"""Tests for GH#261: bracket annotation after flow expression becomes spurious list element.

ROOT CAUSE:
  parse_flow_expression() does NOT call _consume_bracket_annotation(capture=False) after
  returning. Every other path in parse_value() does. This leaves trailing bracket
  annotations (e.g., [mutually_exclusive]) as unconsumed tokens in the list context,
  where they get parsed as nested list elements — spurious new items.

TDD: RED phase — tests define expected behavior before the fix is applied.
"""

from octave_mcp.core.ast_nodes import Assignment, ListValue
from octave_mcp.core.parser import parse


class TestIssue261BracketAnnotationAfterFlowExpression:
    """GH#261: bracket annotations after flow expressions must be consumed, not treated
    as separate list elements."""

    def test_simple_flow_with_trailing_bracket_annotation(self):
        """REQ∧OPT[mutually_exclusive] must parse as a single list item 'REQ∧OPT'.

        The trailing bracket annotation [mutually_exclusive] must be consumed
        (discarded) rather than parsed as a second list element.
        """
        content = """===TEST===
ERRORS::[
  REQ∧OPT[mutually_exclusive]
]
===END==="""
        doc = parse(content)
        assignment = doc.sections[0]
        assert isinstance(assignment, Assignment), f"Expected Assignment, got {type(assignment).__name__}"
        assert isinstance(assignment.value, ListValue), f"Expected ListValue, got {type(assignment.value).__name__}"
        items = assignment.value.items
        assert len(items) == 1, (
            f"Expected 1 list item, got {len(items)}. Items: {items!r}\n"
            f"Bug: [mutually_exclusive] parsed as a spurious second list element."
        )
        assert items[0] == "REQ∧OPT", f"Expected 'REQ∧OPT', got {items[0]!r}"

    def test_conflict_errors_three_items(self):
        """CONFLICT_ERRORS list must have exactly 3 items, not 9 (or more).

        Reproduction case from issue #261. After normalization the buggy parser
        produces spurious elements like [mutually_exclusive], ENUM, ∧, CONST,
        [empty_intersection] as separate list items.

        Expected items:
          - "REQ∧OPT"
          - "ENUM[A,B]∧CONST[C]"
          - "CONST[X]∧CONST[Y]"
        """
        content = """===TEST===
CONFLICT_ERRORS::[
  REQ∧OPT[mutually_exclusive],
  ENUM[A,B]∧CONST[C][empty_intersection],
  CONST[X]∧CONST[Y][contradictory]
]
===END==="""
        doc = parse(content)
        assignment = doc.sections[0]
        assert isinstance(assignment, Assignment), f"Expected Assignment, got {type(assignment).__name__}"
        assert isinstance(assignment.value, ListValue), f"Expected ListValue, got {type(assignment.value).__name__}"
        items = assignment.value.items
        assert len(items) == 3, (
            f"Expected 3 list items, got {len(items)}. Items: {items!r}\n"
            f"Bug: trailing bracket annotations after flow expressions are parsed "
            f"as spurious separate list elements."
        )
        assert items[0] == "REQ∧OPT", f"Item 0: expected 'REQ∧OPT', got {items[0]!r}"
        assert items[1] == "ENUM[A,B]∧CONST[C]", f"Item 1: expected 'ENUM[A,B]∧CONST[C]', got {items[1]!r}"
        assert items[2] == "CONST[X]∧CONST[Y]", f"Item 2: expected 'CONST[X]∧CONST[Y]', got {items[2]!r}"

    def test_flow_expression_trailing_annotation_discarded_not_nested_list(self):
        """Trailing [annotation] after a flow expression must not create a nested list.

        The [annotation] following A∧B should be silently consumed (discarded),
        consistent with how annotations are handled after all other parse_value paths.
        """
        content = """===TEST===
RULES::[A∧B[note], C→D[another_note]]
===END==="""
        doc = parse(content)
        assignment = doc.sections[0]
        assert isinstance(assignment.value, ListValue)
        items = assignment.value.items
        assert len(items) == 2, f"Expected 2 items, got {len(items)}. Items: {items!r}"
        assert items[0] == "A∧B", f"Expected 'A∧B', got {items[0]!r}"
        assert items[1] == "C→D", f"Expected 'C→D', got {items[1]!r}"

    def test_flow_without_annotation_unaffected(self):
        """Flow expressions without trailing bracket annotations must be unchanged.

        This is a regression guard: simple flow expressions that currently work
        correctly must continue to work after the fix.
        """
        content = """===TEST===
FLOW::[A→B, X∧Y, P⊕Q]
===END==="""
        doc = parse(content)
        assignment = doc.sections[0]
        assert isinstance(assignment.value, ListValue)
        items = assignment.value.items
        assert len(items) == 3, f"Expected 3 items, got {len(items)}. Items: {items!r}"
        assert items[0] == "A→B"
        assert items[1] == "X∧Y"
        assert items[2] == "P⊕Q"

    def test_constraint_flow_trailing_bracket_in_multi_item_list(self):
        """CONST[X]∧CONST[Y][contradictory] as one of multiple list items parses correctly.

        In a multi-item list, CONST[X]∧CONST[Y][contradictory] must produce the
        string 'CONST[X]∧CONST[Y]' as a single list element. The trailing
        [contradictory] annotation is consumed and discarded.

        Note: A single-item list like [CONST[X]∧CONST[Y][note]] activates holographic
        pattern detection (separate behavior), so this test uses a two-item list to
        isolate the GH#261 fix.
        """
        content = """===TEST===
ERRORS::[CONST[X]∧CONST[Y][contradictory], DONE]
===END==="""
        doc = parse(content)
        assignment = doc.sections[0]
        assert isinstance(assignment, Assignment), f"Expected Assignment, got {type(assignment).__name__}"
        assert isinstance(assignment.value, ListValue), f"Expected ListValue, got {type(assignment.value).__name__}"
        items = assignment.value.items
        assert len(items) == 2, f"Expected 2 items, got {len(items)}. Items: {items!r}"
        assert items[0] == "CONST[X]∧CONST[Y]", f"Expected 'CONST[X]∧CONST[Y]', got {items[0]!r}"
        assert items[1] == "DONE", f"Expected 'DONE', got {items[1]!r}"
