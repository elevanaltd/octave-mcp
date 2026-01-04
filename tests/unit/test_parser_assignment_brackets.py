"""Tests for assignment values with bracket annotations (Issue #85).

Problem: Bracket annotations after assignment values like `STATUS::DONE[annotation]`
break indentation tracking because parse_value() ends at LIST_START instead of
consuming the bracket and ending at NEWLINE.

This causes GH#81's indentation tracking to fail, making siblings appear as
nested children.
"""

from octave_mcp.core.parser import parse


class TestAssignmentValueBracketAnnotations:
    """Test that bracket annotations after values are consumed correctly."""

    def test_assignment_value_with_bracket_annotation_preserves_indentation(self):
        """Bracket annotations after values should not break indentation tracking."""
        content = """===TEST===
BLOCK:
  TASKS:
    task_1::DONE[annotation]
    task_2::DONE[another]
===END===
"""
        doc = parse(content)

        # Should have one top-level BLOCK
        assert len(doc.sections) == 1
        block = doc.sections[0]
        assert block.key == "BLOCK"

        # BLOCK should have one child TASKS
        assert len(block.children) == 1
        tasks = block.children[0]
        assert tasks.key == "TASKS"

        # TASKS should have TWO children (not one!)
        assert (
            len(tasks.children) == 2
        ), f"Expected 2 children (task_1 and task_2), got {len(tasks.children)}: {[c.key for c in tasks.children]}"
        assert tasks.children[0].key == "task_1"
        assert tasks.children[1].key == "task_2"

    def test_nested_bracket_annotation_consumed(self):
        """Nested brackets should be fully consumed."""
        content = """===TEST===
ITEM:
  STATUS::PENDING[[complex,annotation]]
  NEXT::TODO
===END===
"""
        doc = parse(content)
        item = doc.sections[0]

        # Both STATUS and NEXT should be children of ITEM
        assert (
            len(item.children) == 2
        ), f"Expected 2 children (STATUS and NEXT), got {len(item.children)}: {[c.key for c in item.children]}"
        assert item.children[0].key == "STATUS"
        assert item.children[1].key == "NEXT"

    def test_bracket_at_deeper_nesting(self):
        """Bracket annotations at multiple nesting levels."""
        content = """===TEST===
L1:
  L2:
    L3:
      A::X[note]
      B::Y
    L3B:
      C::Z
===END===
"""
        doc = parse(content)
        l1 = doc.sections[0]
        l2 = l1.children[0]

        # L2 should have TWO L3 blocks
        assert (
            len(l2.children) == 2
        ), f"Expected 2 children (L3 and L3B), got {len(l2.children)}: {[c.key for c in l2.children]}"
        assert l2.children[0].key == "L3"
        assert l2.children[1].key == "L3B"

        # L3 should have TWO children A and B
        l3 = l2.children[0]
        assert (
            len(l3.children) == 2
        ), f"Expected 2 children (A and B), got {len(l3.children)}: {[c.key for c in l3.children]}"
        assert l3.children[0].key == "A"
        assert l3.children[1].key == "B"

    def test_empty_bracket_annotation(self):
        """Empty bracket annotations should be consumed."""
        content = """===TEST===
ITEM:
  A::value[]
  B::other
===END===
"""
        doc = parse(content)
        item = doc.sections[0]

        assert len(item.children) == 2
        assert item.children[0].key == "A"
        assert item.children[1].key == "B"

    def test_bracket_with_complex_content(self):
        """Bracket annotations with complex content (commas, nested brackets)."""
        content = """===TEST===
TASK:
  PHASE::B2[implementation,testing,[nested,content]]
  STATUS::active
===END===
"""
        doc = parse(content)
        task = doc.sections[0]

        assert len(task.children) == 2
        assert task.children[0].key == "PHASE"
        assert task.children[1].key == "STATUS"


class TestColonPathBracketAnnotations:
    """Test bracket annotations after colon-path values (GH#85 PR review fix)."""

    def test_colon_path_value_with_bracket_annotation(self):
        """Bracket annotations after colon-path values should not break indentation.

        GH#85: The bracket consumption logic was placed AFTER the colon-path early return,
        making it unreachable for values like PHASE:SUB[note].
        """
        content = """===TEST===
BLOCK:
  TASKS:
    task_1::PHASE:SUB[note]
    task_2::DONE
===END===
"""
        doc = parse(content)

        block = doc.sections[0]
        assert block.key == "BLOCK"

        tasks = block.children[0]
        assert tasks.key == "TASKS"

        # CRITICAL: Both tasks must be children of TASKS
        assert (
            len(tasks.children) == 2
        ), f"Expected 2 children (task_1 and task_2), got {len(tasks.children)}: {[c.key for c in tasks.children]}"
        assert tasks.children[0].key == "task_1"
        assert tasks.children[1].key == "task_2"

    def test_nested_colon_path_with_bracket(self):
        """Multi-level colon paths with brackets."""
        content = """===TEST===
CONFIG:
  SETTING::MODULE:SUB:COMPONENT[v2]
  NEXT::VALUE
===END===
"""
        doc = parse(content)

        config = doc.sections[0]
        assert (
            len(config.children) == 2
        ), f"Expected 2 children (SETTING and NEXT), got {len(config.children)}: {[c.key for c in config.children]}"
        assert config.children[0].key == "SETTING"
        assert config.children[1].key == "NEXT"

    def test_colon_path_with_nested_brackets(self):
        """Colon paths with nested bracket content."""
        content = """===TEST===
WORKFLOW:
  PHASE::D0:DISCOVERY[[exploration,analysis]]
  STATUS::active
===END===
"""
        doc = parse(content)

        workflow = doc.sections[0]
        assert len(workflow.children) == 2, (
            f"Expected 2 children (PHASE and STATUS), got {len(workflow.children)}: "
            f"{[c.key for c in workflow.children]}"
        )
        assert workflow.children[0].key == "PHASE"
        assert workflow.children[1].key == "STATUS"

    def test_colon_path_empty_bracket(self):
        """Colon paths with empty bracket annotation."""
        content = """===TEST===
DATA:
  REF::NAMESPACE:KEY[]
  OTHER::value
===END===
"""
        doc = parse(content)

        data = doc.sections[0]
        assert len(data.children) == 2
        assert data.children[0].key == "REF"
        assert data.children[1].key == "OTHER"
