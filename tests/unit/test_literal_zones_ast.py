"""Tests for LiteralZoneValue AST node.

Issue #235: Literal zones (fenced code blocks) need a dedicated value type
to prevent silent normalization through string paths.

T01: Verifies dataclass construction, field access, equality, and the D1
constraint that LiteralZoneValue is NOT an ASTNode subclass.
"""

from octave_mcp.core.ast_nodes import ASTNode, LiteralZoneValue


class TestLiteralZoneValueConstruction:
    """Test LiteralZoneValue default and explicit construction."""

    def test_default_construction(self) -> None:
        """LiteralZoneValue() creates instance with correct defaults."""
        lzv = LiteralZoneValue()
        assert lzv.content == ""
        assert lzv.info_tag is None
        assert lzv.fence_marker == "```"

    def test_explicit_construction(self) -> None:
        """LiteralZoneValue with all fields set allows field access."""
        lzv = LiteralZoneValue(content="hello", info_tag="python", fence_marker="```")
        assert lzv.content == "hello"
        assert lzv.info_tag == "python"
        assert lzv.fence_marker == "```"

    def test_longer_fence_marker(self) -> None:
        """Fence marker can be longer than triple backtick."""
        lzv = LiteralZoneValue(content="nested ```", fence_marker="````")
        assert lzv.fence_marker == "````"


class TestLiteralZoneValueEquality:
    """Test dataclass equality semantics."""

    def test_identical_instances_are_equal(self) -> None:
        """Two LiteralZoneValue with same fields are equal."""
        a = LiteralZoneValue(content="x", info_tag="json", fence_marker="```")
        b = LiteralZoneValue(content="x", info_tag="json", fence_marker="```")
        assert a == b

    def test_different_content_not_equal(self) -> None:
        """Different content means not equal."""
        a = LiteralZoneValue(content="x")
        b = LiteralZoneValue(content="y")
        assert a != b


class TestLiteralZoneValueNotASTNode:
    """D1: LiteralZoneValue is a value type, NOT an ASTNode subclass."""

    def test_not_instance_of_astnode(self) -> None:
        """LiteralZoneValue must NOT be an ASTNode instance."""
        lzv = LiteralZoneValue()
        assert not isinstance(lzv, ASTNode)

    def test_not_subclass_of_astnode(self) -> None:
        """LiteralZoneValue class must NOT be a subclass of ASTNode."""
        assert not issubclass(LiteralZoneValue, ASTNode)


class TestLiteralZoneValueEmptyContent:
    """I2: Empty content is a valid, distinct state."""

    def test_empty_content_is_valid(self) -> None:
        """Empty string content is valid (I2: distinct from absent)."""
        lzv = LiteralZoneValue(content="")
        assert lzv.content == ""
        # Empty content is still a real LiteralZoneValue
        assert isinstance(lzv, LiteralZoneValue)

    def test_empty_content_not_none(self) -> None:
        """Empty content is the empty string, not None."""
        lzv = LiteralZoneValue()
        assert lzv.content is not None
        assert lzv.content == ""
