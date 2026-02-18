"""Tests for LiteralZoneValue export in octave_eject (T15).

Issue #235 Phase 4: MCP Tool zone reporting.

TDD RED commit: These tests must FAIL before the implementation is added.

Blueprint: §8.3, §3.2 match points 5-6
Build plan: §T15

BLOCKING GAPS (without fixes these cause runtime failures):
- _convert_value() has no LiteralZoneValue guard -> TypeError on JSON/YAML export
- _format_markdown_value() has no guard -> Python repr leaks into output
"""

import json

import pytest

from octave_mcp.mcp.eject import EjectTool

_TOOL = EjectTool()

# ---------------------------------------------------------------------------
# Test documents
# Note: OCTAVE syntax requires fence on the line AFTER the key
# ---------------------------------------------------------------------------

_DOC_ONE_ZONE = """\
===CODE_DOC===
META:
  TYPE::"TEST"
  VERSION::"1.0"

CODE::
```python
print("hello")
```
===END===
"""

_DOC_ZONE_NO_TAG = """\
===DOC===
META:
  TYPE::"TEST"
  VERSION::"1.0"

SCRIPT::
```
#!/bin/bash
echo hello
```
===END===
"""

_DOC_FOUR_BACKTICK = """\
===DOC===
META:
  TYPE::"TEST"
  VERSION::"1.0"

CODE::
````python
print("hello")
````
===END===
"""

_DOC_NO_ZONES = """\
===DOC===
META:
  TYPE::"TEST"
  VERSION::"1.0"

GREETING::hello world
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


async def _eject(content: str, schema: str = "META", fmt: str = "json") -> dict:
    """Call the eject tool and return the result dict."""
    return await _TOOL.execute(content=content, schema=schema, format=fmt)


# ---------------------------------------------------------------------------
# T15.1: JSON export — no TypeError and correct structure
# ---------------------------------------------------------------------------


class TestEjectJsonLiteralZone:
    """Eject to JSON: LiteralZoneValue must serialize to __literal_zone__ dict."""

    @pytest.mark.asyncio
    async def test_json_no_typeerror(self) -> None:
        """Eject doc with literal zone to JSON must not raise TypeError."""
        # Before fix, _convert_value falls through to 'return value'
        # which puts a LiteralZoneValue object into json.dumps and raises TypeError.
        result = await _eject(_DOC_ONE_ZONE, fmt="json")
        # If we get here without exception, the guard is working
        assert result["output"] is not None

    @pytest.mark.asyncio
    async def test_json_output_is_valid_json(self) -> None:
        """JSON output must be parseable JSON (not a Python repr of LiteralZoneValue)."""
        result = await _eject(_DOC_ONE_ZONE, fmt="json")
        data = json.loads(result["output"])  # Must not raise
        assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_json_field_has_literal_zone_marker(self) -> None:
        """The CODE field in JSON output must have __literal_zone__: True."""
        result = await _eject(_DOC_ONE_ZONE, fmt="json")
        data = json.loads(result["output"])
        assert data["CODE"]["__literal_zone__"] is True

    @pytest.mark.asyncio
    async def test_json_field_has_content(self) -> None:
        """The CODE field in JSON output must have 'content' key with verbatim content."""
        result = await _eject(_DOC_ONE_ZONE, fmt="json")
        data = json.loads(result["output"])
        assert "content" in data["CODE"]
        assert 'print("hello")' in data["CODE"]["content"]

    @pytest.mark.asyncio
    async def test_json_field_has_info_tag(self) -> None:
        """The CODE field in JSON output must have 'info_tag' key."""
        result = await _eject(_DOC_ONE_ZONE, fmt="json")
        data = json.loads(result["output"])
        assert "info_tag" in data["CODE"]
        assert data["CODE"]["info_tag"] == "python"

    @pytest.mark.asyncio
    async def test_json_field_has_fence_marker(self) -> None:
        """The CODE field in JSON output must have 'fence_marker' key."""
        result = await _eject(_DOC_ONE_ZONE, fmt="json")
        data = json.loads(result["output"])
        assert "fence_marker" in data["CODE"]
        assert data["CODE"]["fence_marker"] == "```"

    @pytest.mark.asyncio
    async def test_json_info_tag_none_when_absent(self) -> None:
        """info_tag must be None (JSON null) when no info tag in fence."""
        result = await _eject(_DOC_ZONE_NO_TAG, fmt="json")
        data = json.loads(result["output"])
        assert data["SCRIPT"]["info_tag"] is None

    @pytest.mark.asyncio
    async def test_json_four_backtick_fence_marker(self) -> None:
        """fence_marker must be '````' for four-backtick fences."""
        result = await _eject(_DOC_FOUR_BACKTICK, fmt="json")
        data = json.loads(result["output"])
        assert data["CODE"]["fence_marker"] == "````"

    @pytest.mark.asyncio
    async def test_json_no_literal_zone_key_for_plain_doc(self) -> None:
        """Docs without literal zones must NOT have __literal_zone__ in output."""
        result = await _eject(_DOC_NO_ZONES, fmt="json")
        data = json.loads(result["output"])
        # GREETING should be a plain string, not a zone dict
        greeting = data.get("GREETING")
        assert not isinstance(greeting, dict) or "__literal_zone__" not in greeting


# ---------------------------------------------------------------------------
# T15.2: Markdown export — fence block emitted correctly
# ---------------------------------------------------------------------------


class TestEjectMarkdownLiteralZone:
    """Eject to markdown: LiteralZoneValue must emit as fenced code block."""

    @pytest.mark.asyncio
    async def test_markdown_no_python_repr_leakage(self) -> None:
        """Markdown output must not contain Python repr of LiteralZoneValue."""
        result = await _eject(_DOC_ONE_ZONE, fmt="markdown")
        output = result["output"]
        # Python repr would look like: LiteralZoneValue(content=..., ...)
        assert "LiteralZoneValue" not in output

    @pytest.mark.asyncio
    async def test_markdown_contains_fence_markers(self) -> None:
        """Markdown output must contain triple-backtick fence markers."""
        result = await _eject(_DOC_ONE_ZONE, fmt="markdown")
        output = result["output"]
        assert "```" in output

    @pytest.mark.asyncio
    async def test_markdown_contains_info_tag(self) -> None:
        """Markdown output must contain the info tag (e.g., 'python')."""
        result = await _eject(_DOC_ONE_ZONE, fmt="markdown")
        output = result["output"]
        assert "python" in output

    @pytest.mark.asyncio
    async def test_markdown_content_verbatim(self) -> None:
        """Markdown output must contain the literal zone content verbatim."""
        result = await _eject(_DOC_ONE_ZONE, fmt="markdown")
        output = result["output"]
        assert 'print("hello")' in output

    @pytest.mark.asyncio
    async def test_markdown_fence_block_structure(self) -> None:
        """Markdown output must have opening and closing fence markers."""
        result = await _eject(_DOC_ONE_ZONE, fmt="markdown")
        output = result["output"]
        # Opening fence: ```python (may be prefixed with markdown bold **KEY**: )
        # Closing fence: ``` on its own line
        lines = output.split("\n")
        # Count lines that contain ``` (opening may be on same line as key label)
        fence_lines = [line for line in lines if "```" in line]
        # Must have at least 2 occurrences (opening and closing fence)
        assert len(fence_lines) >= 2

    @pytest.mark.asyncio
    async def test_markdown_no_tag_produces_plain_fence(self) -> None:
        """When info_tag is None, markdown output has plain fence with no tag."""
        result = await _eject(_DOC_ZONE_NO_TAG, fmt="markdown")
        output = result["output"]
        # Should contain ``` without a language tag
        assert "```" in output


# ---------------------------------------------------------------------------
# T15.3: YAML export — no TypeError
# ---------------------------------------------------------------------------


class TestEjectYamlLiteralZone:
    """Eject to YAML: LiteralZoneValue must serialize to __literal_zone__ mapping."""

    @pytest.mark.asyncio
    async def test_yaml_no_typeerror(self) -> None:
        """Eject doc with literal zone to YAML must not raise TypeError."""
        result = await _eject(_DOC_ONE_ZONE, fmt="yaml")
        assert result["output"] is not None

    @pytest.mark.asyncio
    async def test_yaml_contains_literal_zone_marker(self) -> None:
        """YAML output must contain '__literal_zone__' key."""
        result = await _eject(_DOC_ONE_ZONE, fmt="yaml")
        import yaml

        data = yaml.safe_load(result["output"])
        assert data["CODE"]["__literal_zone__"] is True


# ---------------------------------------------------------------------------
# T15.4: zone_report in eject response
# ---------------------------------------------------------------------------


class TestEjectZoneReport:
    """zone_report must be present in eject response when literal zones exist."""

    @pytest.mark.asyncio
    async def test_zone_report_present_for_json(self) -> None:
        """zone_report must be in eject JSON result when zones present."""
        result = await _eject(_DOC_ONE_ZONE, fmt="json")
        assert "zone_report" in result

    @pytest.mark.asyncio
    async def test_zone_report_present_for_markdown(self) -> None:
        """zone_report must be in eject markdown result when zones present."""
        result = await _eject(_DOC_ONE_ZONE, fmt="markdown")
        assert "zone_report" in result

    @pytest.mark.asyncio
    async def test_zone_report_literal_count(self) -> None:
        """zone_report.literal.count must match number of literal zones."""
        result = await _eject(_DOC_ONE_ZONE, fmt="json")
        assert result["zone_report"]["literal"]["count"] == 1

    @pytest.mark.asyncio
    async def test_zone_report_absent_for_no_zones(self) -> None:
        """zone_report must NOT be in eject result when no literal zones."""
        result = await _eject(_DOC_NO_ZONES, fmt="json")
        assert "zone_report" not in result

    @pytest.mark.asyncio
    async def test_two_zones_zone_report_count(self) -> None:
        """zone_report.literal.count must be 2 for two-zone doc."""
        result = await _eject(_DOC_TWO_ZONES, fmt="json")
        assert result["zone_report"]["literal"]["count"] == 2


# ---------------------------------------------------------------------------
# T15.5: Acceptance criterion (blueprint §T15)
# ---------------------------------------------------------------------------


class TestEjectAcceptanceCriterion:
    """Blueprint acceptance: eject JSON result has __literal_zone__: True for CODE field."""

    @pytest.mark.asyncio
    async def test_acceptance_json_literal_zone_marker(self) -> None:
        """Acceptance: eject(doc_with_literal_zone, 'json')['CODE']['__literal_zone__'] == True."""
        result = await _eject(_DOC_ONE_ZONE, fmt="json")
        data = json.loads(result["output"])
        assert data["CODE"]["__literal_zone__"] is True
