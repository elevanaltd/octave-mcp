"""Tests for GH#272: // comments inside array brackets must be stripped.

When inline comments appear inside array bracket context [a, // comment, b],
the comment text must NOT be included as data values. This is an I3 (Mirror
Constraint) violation: "reflect only present, create nothing" -- comment text
is not data and must not be reflected as data.

Reproduction:
    SKILLS::[
        ho-mode,  // Critical lane discipline
        ho-orchestrate,  // Essential for orchestration
    ]

Expected: ["ho-mode", "ho-orchestrate"]
Wrong:    ["ho-mode", "Critical lane discipline", "ho-orchestrate", "Essential for orchestration"]
"""

from octave_mcp.core.emitter import emit
from octave_mcp.core.parser import parse


class TestCommentStrippingInArrayBrackets:
    """GH#272: Comments inside array brackets must be stripped, not treated as data."""

    def test_inline_comment_after_comma_stripped(self):
        """Comments after comma inside array must not appear as list items."""
        content = "SKILLS::[\n    ho-mode,  // Critical lane discipline\n    ho-orchestrate,  // Essential for orchestration\n]"
        doc = parse(content)
        assignment = doc.sections[0]
        assert assignment.key == "SKILLS"
        items = assignment.value.items
        assert items == ["ho-mode", "ho-orchestrate"], f"Comment text leaked into array data: {items}"

    def test_comment_at_end_of_single_line_array(self):
        """Comment at the end of a single-line array element."""
        content = "LIST::[a, b, c  // trailing comment\n]"
        doc = parse(content)
        assignment = doc.sections[0]
        items = assignment.value.items
        assert "trailing comment" not in str(items), f"Comment text leaked into array data: {items}"
        assert "c" in items

    def test_comment_only_line_inside_array(self):
        """A line containing only a comment inside an array should produce no item."""
        content = "LIST::[\n    // just a comment\n    a,\n    b\n]"
        doc = parse(content)
        assignment = doc.sections[0]
        items = assignment.value.items
        assert items == ["a", "b"], f"Comment-only line produced spurious items: {items}"

    def test_nested_array_comments_stripped(self):
        """Comments inside nested arrays must also be stripped."""
        content = "DATA::[\n    [x, // inner comment\n     y],\n    [z]\n]"
        doc = parse(content)
        assignment = doc.sections[0]
        outer_items = assignment.value.items
        # Inner list items should not include comment text
        inner_items = outer_items[0].items
        assert "inner comment" not in str(inner_items), f"Comment text leaked into nested array: {inner_items}"

    def test_string_containing_double_slash_not_stripped(self):
        """String literals containing // must NOT be treated as comments.

        This is the key safety constraint: URLs and other strings with //
        must be preserved as data.
        """
        content = 'URL::"https://example.com"'
        doc = parse(content)
        assignment = doc.sections[0]
        assert assignment.value == "https://example.com"

    def test_string_with_double_slash_inside_array(self):
        """String literals with // inside arrays must be preserved."""
        content = 'URLS::["https://a.com", "https://b.com"]'
        doc = parse(content)
        assignment = doc.sections[0]
        items = assignment.value.items
        assert items == ["https://a.com", "https://b.com"]

    def test_roundtrip_comment_stripped(self):
        """Parse-emit round trip should strip comments from arrays."""
        content = "SKILLS::[\n    ho-mode,  // Critical lane discipline\n    ho-orchestrate,  // Essential for orchestration\n]"
        doc = parse(content)
        output = emit(doc)
        # Comments should not appear in the output as data values
        assert "Critical lane discipline" not in output, f"Comment text survived round-trip as data: {output}"
        assert "Essential for orchestration" not in output, f"Comment text survived round-trip as data: {output}"
        assert "ho-mode" in output
        assert "ho-orchestrate" in output

    def test_multiple_comments_between_items(self):
        """Multiple comment lines between items should all be stripped."""
        content = "LIST::[\n    a,\n    // comment 1\n    // comment 2\n    b\n]"
        doc = parse(content)
        assignment = doc.sections[0]
        items = assignment.value.items
        assert items == ["a", "b"], f"Comment text leaked into array data: {items}"
