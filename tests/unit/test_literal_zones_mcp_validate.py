"""Tests for literal zone reporting in octave_validate (T13).

Issue #235 Phase 4: MCP Tool zone reporting.

TDD RED commit: These tests must FAIL before the implementation is added.

Blueprint: §8.1, §8.4
Build plan: §T13
"""

import pytest

from octave_mcp.mcp.validate import ValidateTool

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TOOL = ValidateTool()


async def _validate(content: str, schema: str = "META") -> dict:
    """Call the validate tool and return the result dict."""
    return await TOOL.execute(content=content, schema=schema)


# A minimal valid OCTAVE doc with no literal zones
DOC_NO_ZONES = """\
===PLAIN===
META:
  TYPE::"TEST"
  VERSION::"1.0"

GREETING::hello world
===END===
"""

# A doc with exactly one literal zone
# Note: OCTAVE syntax requires the fence on the line AFTER the key (VALUE:: then newline then ```)
DOC_ONE_ZONE = """\
===CODE_DOC===
META:
  TYPE::"TEST"
  VERSION::"1.0"

CODE::
```python
hello
```
===END===
"""

# A doc with YAML frontmatter (so container.status == "preserved")
DOC_WITH_FRONTMATTER = """\
---
title: Test
---
===FRONTMATTER_DOC===
META:
  TYPE::"TEST"
  VERSION::"1.0"

CODE::
```python
hello
```
===END===
"""

# A doc with two literal zones
DOC_TWO_ZONES = """\
===MULTI===
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

# ---------------------------------------------------------------------------
# T13.1: No literal zones — no zone-related keys in result
# ---------------------------------------------------------------------------


class TestNoLiteralZones:
    """Validate doc with no literal zones: zone keys absent from result."""

    @pytest.mark.asyncio
    async def test_no_contains_literal_zones_key(self) -> None:
        """result must NOT have 'contains_literal_zones' key for docs without zones."""
        result = await _validate(DOC_NO_ZONES)
        assert "contains_literal_zones" not in result

    @pytest.mark.asyncio
    async def test_no_literal_zone_count_key(self) -> None:
        """result must NOT have 'literal_zone_count' key for docs without zones."""
        result = await _validate(DOC_NO_ZONES)
        assert "literal_zone_count" not in result

    @pytest.mark.asyncio
    async def test_no_zone_report_key(self) -> None:
        """result must NOT have 'zone_report' key for docs without zones."""
        result = await _validate(DOC_NO_ZONES)
        assert "zone_report" not in result


# ---------------------------------------------------------------------------
# T13.2: One literal zone — top-level flags
# ---------------------------------------------------------------------------


class TestOneLiteralZoneFlags:
    """Validate doc with one literal zone: top-level flags present."""

    @pytest.mark.asyncio
    async def test_contains_literal_zones_is_true(self) -> None:
        """contains_literal_zones must be True when doc has a literal zone."""
        result = await _validate(DOC_ONE_ZONE)
        assert result.get("contains_literal_zones") is True

    @pytest.mark.asyncio
    async def test_literal_zone_count_is_one(self) -> None:
        """literal_zone_count must be 1 for a doc with one literal zone."""
        result = await _validate(DOC_ONE_ZONE)
        assert result.get("literal_zone_count") == 1

    @pytest.mark.asyncio
    async def test_literal_zones_validated_is_false(self) -> None:
        """literal_zones_validated must always be False (I5: honest reporting, D4: content opaque)."""
        result = await _validate(DOC_ONE_ZONE)
        assert result.get("literal_zones_validated") is False


# ---------------------------------------------------------------------------
# T13.3: zone_report structure
# ---------------------------------------------------------------------------


class TestZoneReportStructure:
    """zone_report format matches blueprint §8.4."""

    @pytest.mark.asyncio
    async def test_zone_report_present(self) -> None:
        """zone_report key must be present when literal zones exist."""
        result = await _validate(DOC_ONE_ZONE)
        assert "zone_report" in result

    @pytest.mark.asyncio
    async def test_zone_report_has_dsl_key(self) -> None:
        """zone_report must have 'dsl' sub-key."""
        result = await _validate(DOC_ONE_ZONE)
        zone_report = result["zone_report"]
        assert "dsl" in zone_report

    @pytest.mark.asyncio
    async def test_zone_report_has_container_key(self) -> None:
        """zone_report must have 'container' sub-key."""
        result = await _validate(DOC_ONE_ZONE)
        zone_report = result["zone_report"]
        assert "container" in zone_report

    @pytest.mark.asyncio
    async def test_zone_report_has_literal_key(self) -> None:
        """zone_report must have 'literal' sub-key."""
        result = await _validate(DOC_ONE_ZONE)
        zone_report = result["zone_report"]
        assert "literal" in zone_report

    @pytest.mark.asyncio
    async def test_zone_report_literal_status_is_preserved(self) -> None:
        """zone_report.literal.status must be 'preserved' (D6: preserve always)."""
        result = await _validate(DOC_ONE_ZONE)
        literal = result["zone_report"]["literal"]
        assert literal["status"] == "preserved"

    @pytest.mark.asyncio
    async def test_zone_report_literal_count_is_one(self) -> None:
        """zone_report.literal.count must match the number of literal zones."""
        result = await _validate(DOC_ONE_ZONE)
        literal = result["zone_report"]["literal"]
        assert literal["count"] == 1

    @pytest.mark.asyncio
    async def test_zone_report_literal_content_validated_is_false(self) -> None:
        """zone_report.literal.content_validated must always be False (D4 + I5)."""
        result = await _validate(DOC_ONE_ZONE)
        literal = result["zone_report"]["literal"]
        assert literal["content_validated"] is False

    @pytest.mark.asyncio
    async def test_zone_report_literal_zones_list_present(self) -> None:
        """zone_report.literal.zones must be a non-empty list."""
        result = await _validate(DOC_ONE_ZONE)
        literal = result["zone_report"]["literal"]
        assert "zones" in literal
        assert isinstance(literal["zones"], list)
        assert len(literal["zones"]) == 1

    @pytest.mark.asyncio
    async def test_zone_report_literal_zones_entry_has_key(self) -> None:
        """Each zone entry must have 'key' field."""
        result = await _validate(DOC_ONE_ZONE)
        zone = result["zone_report"]["literal"]["zones"][0]
        assert "key" in zone

    @pytest.mark.asyncio
    async def test_zone_report_literal_zones_entry_has_info_tag(self) -> None:
        """Each zone entry must have 'info_tag' field."""
        result = await _validate(DOC_ONE_ZONE)
        zone = result["zone_report"]["literal"]["zones"][0]
        assert "info_tag" in zone

    @pytest.mark.asyncio
    async def test_zone_report_literal_zones_entry_has_line(self) -> None:
        """Each zone entry must have 'line' field."""
        result = await _validate(DOC_ONE_ZONE)
        zone = result["zone_report"]["literal"]["zones"][0]
        assert "line" in zone

    @pytest.mark.asyncio
    async def test_zone_report_literal_zones_entry_key_is_code(self) -> None:
        """Zone entry key must be 'CODE' for our test doc."""
        result = await _validate(DOC_ONE_ZONE)
        zone = result["zone_report"]["literal"]["zones"][0]
        assert zone["key"] == "CODE"

    @pytest.mark.asyncio
    async def test_zone_report_literal_zones_entry_info_tag_is_python(self) -> None:
        """Zone entry info_tag must be 'python' for our test doc."""
        result = await _validate(DOC_ONE_ZONE)
        zone = result["zone_report"]["literal"]["zones"][0]
        assert zone["info_tag"] == "python"


# ---------------------------------------------------------------------------
# T13.4: container status
# ---------------------------------------------------------------------------


class TestContainerStatus:
    """zone_report.container.status reflects frontmatter presence."""

    @pytest.mark.asyncio
    async def test_container_status_absent_for_doc_without_frontmatter(self) -> None:
        """container.status is 'absent' when doc has no YAML frontmatter."""
        result = await _validate(DOC_ONE_ZONE)
        container = result["zone_report"]["container"]
        assert container["status"] == "absent"

    @pytest.mark.asyncio
    async def test_container_status_preserved_for_doc_with_frontmatter(self) -> None:
        """container.status is 'preserved' when doc has YAML frontmatter."""
        result = await _validate(DOC_WITH_FRONTMATTER)
        container = result["zone_report"]["container"]
        assert container["status"] == "preserved"


# ---------------------------------------------------------------------------
# T13.5: repair_log present when literal zones exist
# ---------------------------------------------------------------------------


class TestRepairLogPresent:
    """repair_log must include LiteralZoneRepairLog when literal zones present."""

    @pytest.mark.asyncio
    async def test_repair_log_present_in_result(self) -> None:
        """result must have 'literal_zone_repair_log' key when zones exist."""
        result = await _validate(DOC_ONE_ZONE)
        # repair_log for literal zones may be under a dedicated key
        assert "literal_zone_repair_log" in result

    @pytest.mark.asyncio
    async def test_repair_log_is_list(self) -> None:
        """literal_zone_repair_log must be a list."""
        result = await _validate(DOC_ONE_ZONE)
        assert isinstance(result["literal_zone_repair_log"], list)


# ---------------------------------------------------------------------------
# T13.6: Two literal zones
# ---------------------------------------------------------------------------


class TestTwoLiteralZones:
    """Two literal zones: counts and zones list both show 2."""

    @pytest.mark.asyncio
    async def test_two_zones_count(self) -> None:
        """literal_zone_count must be 2 for doc with two literal zones."""
        result = await _validate(DOC_TWO_ZONES)
        assert result.get("literal_zone_count") == 2

    @pytest.mark.asyncio
    async def test_two_zones_report_count(self) -> None:
        """zone_report.literal.count must be 2 for doc with two literal zones."""
        result = await _validate(DOC_TWO_ZONES)
        literal = result["zone_report"]["literal"]
        assert literal["count"] == 2

    @pytest.mark.asyncio
    async def test_two_zones_list_length(self) -> None:
        """zone_report.literal.zones must have 2 entries."""
        result = await _validate(DOC_TWO_ZONES)
        zones = result["zone_report"]["literal"]["zones"]
        assert len(zones) == 2


# ---------------------------------------------------------------------------
# T13.7: Acceptance criterion (blueprint §T13)
# ---------------------------------------------------------------------------


class TestAcceptanceCriterion:
    """Blueprint acceptance: zone_report.literal.status == 'preserved'."""

    @pytest.mark.asyncio
    async def test_acceptance_literal_status_preserved(self) -> None:
        """Acceptance: validate doc with literal zone returns zone_report.literal.status == 'preserved'."""
        doc = "===DOC===\nCODE::\n```python\nhello\n```\n===END===\n"
        result = await _validate(doc)
        assert result["zone_report"]["literal"]["status"] == "preserved"
