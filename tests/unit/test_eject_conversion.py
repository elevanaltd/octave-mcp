"""Tests for eject tool conversion functions.

Tests the internal _ast_to_dict, _convert_value, _convert_block,
_ast_to_markdown, and _block_to_markdown functions.
Targets coverage of eject.py lines 40-41, 58, 72-80, 111-114, 127-133.
"""

from octave_mcp.core.ast_nodes import Assignment, Block, Document, InlineMap, ListValue
from octave_mcp.mcp.eject import (
    _ast_to_dict,
    _ast_to_markdown,
    _block_to_markdown,
    _convert_block,
    _convert_value,
)


class TestConvertValue:
    """Tests for _convert_value function."""

    def test_convert_string_value(self):
        """String values are passed through unchanged."""
        result = _convert_value("test string")
        assert result == "test string"

    def test_convert_integer_value(self):
        """Integer values are passed through unchanged."""
        result = _convert_value(42)
        assert result == 42

    def test_convert_list_value(self):
        """ListValue is converted to Python list."""
        list_val = ListValue(items=["a", "b", "c"])
        result = _convert_value(list_val)
        assert result == ["a", "b", "c"]

    def test_convert_list_value_nested(self):
        """Nested ListValue is recursively converted."""
        inner_list = ListValue(items=["x", "y"])
        outer_list = ListValue(items=["a", inner_list, "b"])
        result = _convert_value(outer_list)
        assert result == ["a", ["x", "y"], "b"]

    def test_convert_inline_map(self):
        """InlineMap is converted to Python dict."""
        inline_map = InlineMap(pairs={"key1": "value1", "key2": "value2"})
        result = _convert_value(inline_map)
        assert result == {"key1": "value1", "key2": "value2"}

    def test_convert_inline_map_with_list(self):
        """InlineMap with ListValue values is recursively converted."""
        list_val = ListValue(items=["a", "b"])
        inline_map = InlineMap(pairs={"items": list_val, "name": "test"})
        result = _convert_value(inline_map)
        assert result == {"items": ["a", "b"], "name": "test"}

    def test_convert_boolean_value(self):
        """Boolean values are passed through unchanged."""
        assert _convert_value(True) is True
        assert _convert_value(False) is False

    def test_convert_none_value(self):
        """None values are passed through unchanged."""
        assert _convert_value(None) is None


class TestConvertBlock:
    """Tests for _convert_block function."""

    def test_convert_block_with_assignments(self):
        """Block with Assignment children is converted to dict."""
        block = Block(
            key="TEST",
            children=[
                Assignment(key="FIELD1", value="value1"),
                Assignment(key="FIELD2", value=42),
            ],
        )
        result = _convert_block(block)
        assert result == {"FIELD1": "value1", "FIELD2": 42}

    def test_convert_block_with_nested_blocks(self):
        """Nested Block children are recursively converted."""
        inner_block = Block(
            key="INNER",
            children=[Assignment(key="NESTED", value="nested_value")],
        )
        outer_block = Block(
            key="OUTER",
            children=[
                Assignment(key="TOP", value="top_value"),
                inner_block,
            ],
        )
        result = _convert_block(outer_block)
        assert result == {
            "TOP": "top_value",
            "INNER": {"NESTED": "nested_value"},
        }

    def test_convert_block_with_list_values(self):
        """Block with ListValue assignments is properly converted."""
        block = Block(
            key="TEST",
            children=[
                Assignment(key="ITEMS", value=ListValue(items=["a", "b", "c"])),
            ],
        )
        result = _convert_block(block)
        assert result == {"ITEMS": ["a", "b", "c"]}

    def test_convert_block_with_inline_map(self):
        """Block with InlineMap assignments is properly converted."""
        inline_map = InlineMap(pairs={"x": 1, "y": 2})
        block = Block(
            key="TEST",
            children=[
                Assignment(key="COORDS", value=inline_map),
            ],
        )
        result = _convert_block(block)
        assert result == {"COORDS": {"x": 1, "y": 2}}

    def test_convert_empty_block(self):
        """Empty block is converted to empty dict."""
        block = Block(key="EMPTY", children=[])
        result = _convert_block(block)
        assert result == {}


class TestAstToDict:
    """Tests for _ast_to_dict function."""

    def test_ast_to_dict_with_meta(self):
        """Document with META is converted with META preserved."""
        doc = Document(
            name="TEST",
            meta={"TYPE": "TEST", "VERSION": "1.0"},
            sections=[Assignment(key="STATUS", value="active")],
        )
        result = _ast_to_dict(doc)
        assert result["META"] == {"TYPE": "TEST", "VERSION": "1.0"}
        assert result["STATUS"] == "active"

    def test_ast_to_dict_with_meta_list_values(self):
        """Document with META containing ListValue objects is properly converted.

        BUG REPRODUCTION: When _apply_changes stores ListValue in doc.meta,
        _ast_to_dict must convert it to a native Python list for JSON serialization.
        Without the fix, json.dumps fails with:
            TypeError: Object of type ListValue is not JSON serializable
        """
        import json

        # Simulate what _apply_changes does when processing META.TAGS changes
        list_value = ListValue(items=["alpha", "beta", "gamma"])
        doc = Document(
            name="TEST",
            meta={"TYPE": "TEST", "VERSION": "1.0", "TAGS": list_value},
            sections=[Assignment(key="STATUS", value="active")],
        )
        result = _ast_to_dict(doc)

        # META values must be native Python types (list, not ListValue)
        assert result["META"]["TAGS"] == ["alpha", "beta", "gamma"]

        # Critical: must be JSON serializable without TypeError
        json_output = json.dumps(result)
        assert "alpha" in json_output
        assert "beta" in json_output
        assert "gamma" in json_output

    def test_ast_to_dict_without_meta(self):
        """Document without META is converted without META key."""
        doc = Document(
            name="TEST",
            meta=None,
            sections=[Assignment(key="FIELD", value="value")],
        )
        result = _ast_to_dict(doc)
        assert "META" not in result
        assert result["FIELD"] == "value"

    def test_ast_to_dict_with_block_sections(self):
        """Document with Block sections is properly converted."""
        doc = Document(
            name="TEST",
            meta=None,
            sections=[
                Block(
                    key="SECTION",
                    children=[
                        Assignment(key="CHILD", value="child_value"),
                    ],
                ),
            ],
        )
        result = _ast_to_dict(doc)
        assert result["SECTION"] == {"CHILD": "child_value"}

    def test_ast_to_dict_mixed_sections(self):
        """Document with mixed Assignment and Block sections."""
        doc = Document(
            name="TEST",
            meta={"VERSION": "1.0"},
            sections=[
                Assignment(key="TOP_FIELD", value="top_value"),
                Block(
                    key="NESTED",
                    children=[Assignment(key="INNER", value="inner_value")],
                ),
            ],
        )
        result = _ast_to_dict(doc)
        assert result["META"] == {"VERSION": "1.0"}
        assert result["TOP_FIELD"] == "top_value"
        assert result["NESTED"] == {"INNER": "inner_value"}


class TestBlockToMarkdown:
    """Tests for _block_to_markdown function."""

    def test_block_to_markdown_with_assignments(self):
        """Block with assignments generates markdown list items."""
        block = Block(
            key="TEST",
            children=[
                Assignment(key="FIELD1", value="value1"),
                Assignment(key="FIELD2", value="value2"),
            ],
        )
        lines: list[str] = []
        _block_to_markdown(block, lines, level=3)
        assert "- **FIELD1**: value1" in lines
        assert "- **FIELD2**: value2" in lines

    def test_block_to_markdown_with_nested_block(self):
        """Nested block generates heading with increased level."""
        inner_block = Block(
            key="INNER",
            children=[Assignment(key="NESTED", value="nested_value")],
        )
        outer_block = Block(
            key="OUTER",
            children=[inner_block],
        )
        lines: list[str] = []
        _block_to_markdown(outer_block, lines, level=3)
        assert "### INNER" in lines
        assert "- **NESTED**: nested_value" in lines

    def test_block_to_markdown_level_increment(self):
        """Heading level increments for deeper nesting."""
        block = Block(key="LEVEL", children=[])
        lines: list[str] = []
        # Add a nested block at level 4
        nested = Block(
            key="NESTED",
            children=[Assignment(key="FIELD", value="value")],
        )
        block.children.append(nested)
        _block_to_markdown(block, lines, level=4)
        assert "#### NESTED" in lines


class TestAstToMarkdown:
    """Tests for _ast_to_markdown function."""

    def test_ast_to_markdown_has_title(self):
        """Markdown output includes document name as title."""
        doc = Document(
            name="TESTDOC",
            meta=None,
            sections=[],
        )
        result = _ast_to_markdown(doc)
        assert "# TESTDOC" in result

    def test_ast_to_markdown_includes_meta(self):
        """Markdown output includes META section if present."""
        doc = Document(
            name="TEST",
            meta={"TYPE": "TEST", "VERSION": "1.0"},
            sections=[],
        )
        result = _ast_to_markdown(doc)
        assert "## META" in result
        assert "**TYPE**" in result
        assert "**VERSION**" in result

    def test_ast_to_markdown_no_meta(self):
        """Markdown output omits META section if not present."""
        doc = Document(
            name="TEST",
            meta=None,
            sections=[Assignment(key="FIELD", value="value")],
        )
        result = _ast_to_markdown(doc)
        assert "## META" not in result
        assert "**FIELD**" in result

    def test_ast_to_markdown_with_assignment_section(self):
        """Assignment sections appear as bold key-value pairs."""
        doc = Document(
            name="TEST",
            meta=None,
            sections=[Assignment(key="STATUS", value="active")],
        )
        result = _ast_to_markdown(doc)
        assert "**STATUS**: active" in result

    def test_ast_to_markdown_with_block_section(self):
        """Block sections appear as headings with content."""
        doc = Document(
            name="TEST",
            meta=None,
            sections=[
                Block(
                    key="SECTION",
                    children=[Assignment(key="FIELD", value="value")],
                ),
            ],
        )
        result = _ast_to_markdown(doc)
        assert "## SECTION" in result
        assert "**FIELD**" in result
