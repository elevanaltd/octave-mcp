"""Tests for literal zone write guards and zone reporting (T10 + T14).

Issue #235: Verifies that LiteralZoneValue is handled correctly in:
- emitter.py: is_absent() returns False for LiteralZoneValue
- emitter.py: needs_quotes() returns False for LiteralZoneValue
- write.py: _normalize_value_for_ast() returns LiteralZoneValue unchanged
- write.py: zone_report and repair_log added to response when literal zones present
- write.py: literal zone content preserved byte-for-byte (T14)
"""

import os
import tempfile

import pytest

from octave_mcp.core.ast_nodes import LiteralZoneValue
from octave_mcp.core.emitter import is_absent, needs_quotes
from octave_mcp.mcp.write import WriteTool, _normalize_value_for_ast

_TOOL = WriteTool()

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


# ===========================================================================
# T14: octave_write — Zone Reporting + Preservation
# ===========================================================================

# Note: OCTAVE syntax requires the fence on the line AFTER the key
_DOC_ONE_ZONE = """\
===DOC===
META:
  TYPE::"TEST"
  VERSION::"1.0"

CODE::
```python
print("hello")
```
===END===
"""

_DOC_WITH_TABS = """\
===DOC===
META:
  TYPE::"TEST"
  VERSION::"1.0"

CODE::
```
\tindented with tabs
\t\tdouble indent
```
===END===
"""

_DOC_NO_ZONES = """\
===DOC===
META:
  TYPE::"TEST"
  VERSION::"1.0"

PLAIN::just a value
===END===
"""

_DOC_TWO_ZONES = """\
===DOC===
META:
  TYPE::"TEST"
  VERSION::"1.0"

CODE::
```python
print("hello")
```

CONFIG::
```json
{"key": "value"}
```
===END===
"""


async def _write_content_result(content: str) -> dict:
    """Helper: write content to a temp file and return result dict."""
    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "test.oct.md")
        return await _TOOL.execute(target_path=target, content=content)


class TestWriteZoneReportPresence:
    """zone_report must appear in response when literal zones are present."""

    @pytest.mark.asyncio
    async def test_zone_report_present_when_zones_exist(self) -> None:
        """zone_report key must be in result when doc has literal zones."""
        result = await _write_content_result(_DOC_ONE_ZONE)
        assert result["status"] == "success"
        assert "zone_report" in result

    @pytest.mark.asyncio
    async def test_zone_report_absent_when_no_zones(self) -> None:
        """zone_report key must NOT be in result when doc has no literal zones."""
        result = await _write_content_result(_DOC_NO_ZONES)
        assert result["status"] == "success"
        assert "zone_report" not in result

    @pytest.mark.asyncio
    async def test_contains_literal_zones_flag_true(self) -> None:
        """contains_literal_zones must be True when zones present."""
        result = await _write_content_result(_DOC_ONE_ZONE)
        assert result.get("contains_literal_zones") is True

    @pytest.mark.asyncio
    async def test_literal_zones_validated_is_false(self) -> None:
        """literal_zones_validated must always be False (I5: honest, D4: opaque)."""
        result = await _write_content_result(_DOC_ONE_ZONE)
        assert result.get("literal_zones_validated") is False

    @pytest.mark.asyncio
    async def test_literal_zone_count_is_one(self) -> None:
        """literal_zone_count must be 1 for single-zone doc."""
        result = await _write_content_result(_DOC_ONE_ZONE)
        assert result.get("literal_zone_count") == 1

    @pytest.mark.asyncio
    async def test_zone_report_literal_status_preserved(self) -> None:
        """zone_report.literal.status must be 'preserved'."""
        result = await _write_content_result(_DOC_ONE_ZONE)
        assert result["zone_report"]["literal"]["status"] == "preserved"

    @pytest.mark.asyncio
    async def test_zone_report_literal_count_one(self) -> None:
        """zone_report.literal.count must be 1."""
        result = await _write_content_result(_DOC_ONE_ZONE)
        assert result["zone_report"]["literal"]["count"] == 1

    @pytest.mark.asyncio
    async def test_zone_report_literal_content_validated_false(self) -> None:
        """zone_report.literal.content_validated must be False."""
        result = await _write_content_result(_DOC_ONE_ZONE)
        assert result["zone_report"]["literal"]["content_validated"] is False

    @pytest.mark.asyncio
    async def test_zone_report_literal_zones_list(self) -> None:
        """zone_report.literal.zones must be a list with one entry."""
        result = await _write_content_result(_DOC_ONE_ZONE)
        zones = result["zone_report"]["literal"]["zones"]
        assert isinstance(zones, list)
        assert len(zones) == 1

    @pytest.mark.asyncio
    async def test_zone_report_zones_entry_has_required_keys(self) -> None:
        """Each zone entry must have key, info_tag, and line."""
        result = await _write_content_result(_DOC_ONE_ZONE)
        zone = result["zone_report"]["literal"]["zones"][0]
        assert "key" in zone
        assert "info_tag" in zone
        assert "line" in zone

    @pytest.mark.asyncio
    async def test_two_zones_count(self) -> None:
        """literal_zone_count must be 2 for two-zone doc."""
        result = await _write_content_result(_DOC_TWO_ZONES)
        assert result.get("literal_zone_count") == 2


class TestWriteRepairLog:
    """repair_log for literal zones must appear in response when zones present."""

    @pytest.mark.asyncio
    async def test_literal_zone_repair_log_present(self) -> None:
        """literal_zone_repair_log must be in result when zones present."""
        result = await _write_content_result(_DOC_ONE_ZONE)
        assert "literal_zone_repair_log" in result

    @pytest.mark.asyncio
    async def test_literal_zone_repair_log_is_list(self) -> None:
        """literal_zone_repair_log must be a list."""
        result = await _write_content_result(_DOC_ONE_ZONE)
        assert isinstance(result["literal_zone_repair_log"], list)

    @pytest.mark.asyncio
    async def test_repair_log_absent_when_no_zones(self) -> None:
        """literal_zone_repair_log must NOT be in result when no literal zones."""
        result = await _write_content_result(_DOC_NO_ZONES)
        assert "literal_zone_repair_log" not in result


class TestWriteContentPreservation:
    """Literal zone content must be preserved byte-for-byte through write."""

    @pytest.mark.asyncio
    async def test_literal_zone_content_preserved_in_output(self) -> None:
        """Zone content must survive the write pipeline byte-for-byte."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "test.oct.md")
            result = await _TOOL.execute(target_path=target, content=_DOC_ONE_ZONE)
            assert result["status"] == "success"
            # Read back written file
            with open(target, encoding="utf-8") as f:
                written = f.read()
            # The literal content 'print("hello")' must appear verbatim
            assert 'print("hello")' in written

    @pytest.mark.asyncio
    async def test_tabs_preserved_in_literal_zone(self) -> None:
        """Tabs inside a literal zone must be preserved (not converted to spaces)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "test.oct.md")
            result = await _TOOL.execute(target_path=target, content=_DOC_WITH_TABS)
            assert result["status"] == "success"
            with open(target, encoding="utf-8") as f:
                written = f.read()
            assert "\tindented with tabs" in written
            assert "\t\tdouble indent" in written

    @pytest.mark.asyncio
    async def test_unwrap_markdown_fence_does_not_strip_inner_fence(self) -> None:
        """_unwrap_markdown_code_fence strips only the outer transport fence, not inner literal zones."""
        # A document wrapped in outer markdown fence containing a literal zone inside
        outer_wrapped = "```octave\n" + _DOC_ONE_ZONE + "```"
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "test.oct.md")
            result = await _TOOL.execute(target_path=target, content=outer_wrapped)
            assert result["status"] == "success"
            # Should have unwrapped outer fence (W_MARKDOWN_UNWRAP correction)
            assert any(c.get("code") == "W_MARKDOWN_UNWRAP" for c in result.get("corrections", []))
            # Inner literal zone must still be in the written file
            with open(target, encoding="utf-8") as f:
                written = f.read()
            assert "```python" in written or "```" in written

    @pytest.mark.asyncio
    async def test_write_without_literal_zones_no_zone_keys(self) -> None:
        """Write doc without literal zones: result has no zone-related keys."""
        result = await _write_content_result(_DOC_NO_ZONES)
        assert "contains_literal_zones" not in result
        assert "literal_zone_count" not in result
        assert "literal_zones_validated" not in result
