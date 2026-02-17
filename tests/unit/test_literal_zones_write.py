"""Tests for literal zone write guards (T10 -- match points 2, 3, 8).

Issue #235: Verifies that LiteralZoneValue is handled correctly in:
- emitter.py: is_absent() returns False for LiteralZoneValue
- emitter.py: needs_quotes() returns False for LiteralZoneValue
- write.py: _normalize_value_for_ast() returns LiteralZoneValue unchanged
"""

from octave_mcp.core.ast_nodes import LiteralZoneValue
from octave_mcp.core.emitter import is_absent, needs_quotes
from octave_mcp.mcp.write import _normalize_value_for_ast

# --- Match Point 2: is_absent() ---


class TestIsAbsentLiteralZone:
    """MP2: is_absent returns False for LiteralZoneValue."""

    def test_is_absent_literal_zone_returns_false(self) -> None:
        """LiteralZoneValue is NOT absent."""
        lzv = LiteralZoneValue(content="hello", info_tag="python")
        assert is_absent(lzv) is False

    def test_is_absent_empty_literal_zone_returns_false(self) -> None:
        """Empty LiteralZoneValue is NOT absent (I2: empty != absent)."""
        lzv = LiteralZoneValue(content="")
        assert is_absent(lzv) is False

    def test_is_absent_default_literal_zone_returns_false(self) -> None:
        """Default-constructed LiteralZoneValue is NOT absent."""
        lzv = LiteralZoneValue()
        assert is_absent(lzv) is False


# --- Match Point 3: needs_quotes() ---


class TestNeedsQuotesLiteralZone:
    """MP3: needs_quotes returns False for LiteralZoneValue."""

    def test_needs_quotes_literal_zone_returns_false(self) -> None:
        """LiteralZoneValue does not need quotes."""
        lzv = LiteralZoneValue(content="hello world", info_tag="python")
        assert needs_quotes(lzv) is False

    def test_needs_quotes_empty_literal_zone_returns_false(self) -> None:
        """Empty LiteralZoneValue does not need quotes."""
        lzv = LiteralZoneValue(content="")
        assert needs_quotes(lzv) is False

    def test_needs_quotes_literal_zone_with_special_chars_returns_false(self) -> None:
        """LiteralZoneValue with special chars still returns False (not a string)."""
        lzv = LiteralZoneValue(content='key::"value" with spaces\n')
        assert needs_quotes(lzv) is False


# --- Match Point 8: _normalize_value_for_ast() ---


class TestNormalizeValueForAstLiteralZone:
    """MP8: _normalize_value_for_ast returns LiteralZoneValue unchanged."""

    def test_literal_zone_returned_unchanged(self) -> None:
        """LiteralZoneValue passes through normalization unchanged."""
        lzv = LiteralZoneValue(content="hello\n", info_tag="python", fence_marker="```")
        result = _normalize_value_for_ast(lzv)
        assert result is lzv  # Identity check -- same object

    def test_literal_zone_content_not_normalized(self) -> None:
        """LiteralZoneValue content is NOT NFC-normalized."""
        # Content with tabs and special chars must survive unchanged
        lzv = LiteralZoneValue(content="raw\tcontent\nwith\ttabs")
        result = _normalize_value_for_ast(lzv)
        assert result.content == "raw\tcontent\nwith\ttabs"

    def test_literal_zone_not_wrapped_in_list_value(self) -> None:
        """LiteralZoneValue is NOT wrapped in ListValue (not a list)."""
        lzv = LiteralZoneValue(content="[a, b, c]")
        result = _normalize_value_for_ast(lzv)
        assert isinstance(result, LiteralZoneValue)
        assert result is lzv

    def test_literal_zone_not_wrapped_in_inline_map(self) -> None:
        """LiteralZoneValue is NOT wrapped in InlineMap (not a dict)."""
        lzv = LiteralZoneValue(content='{"key": "value"}')
        result = _normalize_value_for_ast(lzv)
        assert isinstance(result, LiteralZoneValue)
        assert result is lzv

    def test_literal_zone_preserves_all_fields(self) -> None:
        """All LiteralZoneValue fields preserved through normalization."""
        lzv = LiteralZoneValue(content="code\n", info_tag="rust", fence_marker="````")
        result = _normalize_value_for_ast(lzv)
        assert result.content == "code\n"
        assert result.info_tag == "rust"
        assert result.fence_marker == "````"
