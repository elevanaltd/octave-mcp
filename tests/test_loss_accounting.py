"""Tests for loss accounting hardening (I4 audit receipts + LOSS_PROFILE warnings).

TDD RED phase: These tests define the expected behavior for:
1. LiteralZoneRepairLog population with SHA-256 receipts
2. W_META_001 and W_META_002 validation warnings
"""

import hashlib
import re

from octave_mcp.core.parser import parse
from octave_mcp.core.repair_log import LiteralZoneRepairLog
from octave_mcp.core.validator import Validator

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

OCTAVE_WITH_ONE_ZONE = """\
===SAMPLE===
META:
  TYPE::"TEST"

CODE::
```python
print("hello")
```

===END==="""

OCTAVE_WITH_THREE_ZONES = """\
===SAMPLE===
META:
  TYPE::"TEST"

CODE::
```python
print("hello")
```
CONFIG::
```json
{"key": "value"}
```
SCRIPT::
```bash
echo "test"
```

===END==="""

OCTAVE_NO_ZONES = """\
===SAMPLE===
META:
  TYPE::"TEST"

§1::SECTION
KEY::"value"

===END==="""

# --- META fixtures for LOSS_PROFILE warnings ---

OCTAVE_TIER_NO_PROFILE = """\
===SAMPLE===
META:
  TYPE::"TEST"
  COMPRESSION_TIER::AGGRESSIVE

§1::SECTION
KEY::"value"

===END==="""

OCTAVE_NONE_PROFILE_NON_LOSSLESS = """\
===SAMPLE===
META:
  TYPE::"TEST"
  COMPRESSION_TIER::CONSERVATIVE
  LOSS_PROFILE::"none"

§1::SECTION
KEY::"value"

===END==="""

OCTAVE_LOSSLESS_WITH_NONE = """\
===SAMPLE===
META:
  TYPE::"TEST"
  COMPRESSION_TIER::LOSSLESS
  LOSS_PROFILE::"none"

§1::SECTION
KEY::"value"

===END==="""

OCTAVE_TIER_WITH_PROFILE = """\
===SAMPLE===
META:
  TYPE::"TEST"
  COMPRESSION_TIER::AGGRESSIVE
  LOSS_PROFILE::"drop_narrative_preserve_protocol"

§1::SECTION
KEY::"value"

===END==="""

OCTAVE_NO_TIER = """\
===SAMPLE===
META:
  TYPE::"TEST"

§1::SECTION
KEY::"value"

===END==="""


# ===========================================================================
# Task 1: LiteralZoneRepairLog SHA-256 population
# ===========================================================================


class TestLiteralZoneRepairLogPopulation:
    """Tests for _build_literal_zone_repair_log helper."""

    def test_populated_entries_when_zones_exist(self):
        """Populated entries when literal zones exist, empty when no zones."""
        from octave_mcp.core.literal_zone_audit import build_literal_zone_repair_log
        from octave_mcp.core.validator import _count_literal_zones

        doc = parse(OCTAVE_WITH_ONE_ZONE)
        zones = _count_literal_zones(doc)
        log = build_literal_zone_repair_log(zones, doc, "test_stage")

        assert isinstance(log, LiteralZoneRepairLog)
        assert len(log.entries) == 1
        assert log.entries[0].zone_key == "CODE"
        assert log.entries[0].action == "preserved"
        assert log.entries[0].source_stage == "test_stage"

    def test_empty_entries_when_no_zones(self):
        """Empty entries when no literal zones exist."""
        from octave_mcp.core.literal_zone_audit import build_literal_zone_repair_log
        from octave_mcp.core.validator import _count_literal_zones

        doc = parse(OCTAVE_NO_ZONES)
        zones = _count_literal_zones(doc)
        log = build_literal_zone_repair_log(zones, doc, "test_stage")

        assert isinstance(log, LiteralZoneRepairLog)
        assert len(log.entries) == 0

    def test_sha256_hash_correctness(self):
        """SHA-256 hash is 64-char hex and pre_hash equals post_hash."""
        from octave_mcp.core.literal_zone_audit import build_literal_zone_repair_log
        from octave_mcp.core.validator import _count_literal_zones

        doc = parse(OCTAVE_WITH_ONE_ZONE)
        zones = _count_literal_zones(doc)
        log = build_literal_zone_repair_log(zones, doc, "test_stage")

        entry = log.entries[0]
        # 64-char hex string
        assert len(entry.pre_hash) == 64
        assert re.fullmatch(r"[0-9a-f]{64}", entry.pre_hash)
        # D3: zero processing means pre == post
        assert entry.pre_hash == entry.post_hash

    def test_sha256_matches_expected_content(self):
        """SHA-256 hash matches independently computed hash of zone content."""
        from octave_mcp.core.literal_zone_audit import build_literal_zone_repair_log
        from octave_mcp.core.validator import _count_literal_zones

        doc = parse(OCTAVE_WITH_ONE_ZONE)
        zones = _count_literal_zones(doc)
        log = build_literal_zone_repair_log(zones, doc, "test_stage")

        expected_hash = hashlib.sha256(b'print("hello")').hexdigest()
        assert log.entries[0].pre_hash == expected_hash

    def test_multiple_zones_all_logged(self):
        """Multiple zones all produce entries."""
        from octave_mcp.core.literal_zone_audit import build_literal_zone_repair_log
        from octave_mcp.core.validator import _count_literal_zones

        doc = parse(OCTAVE_WITH_THREE_ZONES)
        zones = _count_literal_zones(doc)
        log = build_literal_zone_repair_log(zones, doc, "test_stage")

        assert len(log.entries) == 3
        keys = {e.zone_key for e in log.entries}
        assert keys == {"CODE", "CONFIG", "SCRIPT"}

    def test_zone_key_and_line_correct(self):
        """Zone key and line match the source document."""
        from octave_mcp.core.literal_zone_audit import build_literal_zone_repair_log
        from octave_mcp.core.validator import _count_literal_zones

        doc = parse(OCTAVE_WITH_ONE_ZONE)
        zones = _count_literal_zones(doc)
        log = build_literal_zone_repair_log(zones, doc, "test_stage")

        entry = log.entries[0]
        assert entry.zone_key == "CODE"
        # Line should match the zone metadata from _count_literal_zones
        assert entry.line == zones[0]["line"]

    def test_timestamp_is_iso8601(self):
        """Timestamp is valid ISO 8601 format."""
        from octave_mcp.core.literal_zone_audit import build_literal_zone_repair_log
        from octave_mcp.core.validator import _count_literal_zones

        doc = parse(OCTAVE_WITH_ONE_ZONE)
        zones = _count_literal_zones(doc)
        log = build_literal_zone_repair_log(zones, doc, "test_stage")

        # ISO 8601 format check (basic: contains T and timezone info)
        ts = log.entries[0].timestamp
        assert "T" in ts
        assert ts.endswith("+00:00") or ts.endswith("Z")

    def test_all_preserved_property(self):
        """LiteralZoneRepairLog.all_preserved returns True when all zones preserved."""
        from octave_mcp.core.literal_zone_audit import build_literal_zone_repair_log
        from octave_mcp.core.validator import _count_literal_zones

        doc = parse(OCTAVE_WITH_THREE_ZONES)
        zones = _count_literal_zones(doc)
        log = build_literal_zone_repair_log(zones, doc, "test_stage")

        assert log.all_preserved is True


# ===========================================================================
# Task 2: LOSS_PROFILE consistency warnings
# ===========================================================================


class TestLossProfileWarnings:
    """Tests for W_META_001 and W_META_002 validation warnings."""

    def test_w_meta_001_tier_without_profile(self):
        """W_META_001: COMPRESSION_TIER declared but LOSS_PROFILE absent."""
        doc = parse(OCTAVE_TIER_NO_PROFILE)
        validator = Validator()
        validator.validate(doc)

        warnings = [e for e in validator.errors if e.severity == "warning"]
        codes = [w.code for w in warnings]
        assert "W_META_001" in codes
        w = next(w for w in warnings if w.code == "W_META_001")
        assert "COMPRESSION_TIER" in w.message
        assert "LOSS_PROFILE" in w.message

    def test_w_meta_002_none_profile_non_lossless(self):
        """W_META_002: LOSS_PROFILE is 'none' but COMPRESSION_TIER is not LOSSLESS."""
        doc = parse(OCTAVE_NONE_PROFILE_NON_LOSSLESS)
        validator = Validator()
        validator.validate(doc)

        warnings = [e for e in validator.errors if e.severity == "warning"]
        codes = [w.code for w in warnings]
        assert "W_META_002" in codes
        w = next(w for w in warnings if w.code == "W_META_002")
        assert "none" in w.message.lower() or "LOSS_PROFILE" in w.message

    def test_no_warning_lossless_with_none(self):
        """No warning when COMPRESSION_TIER is LOSSLESS and LOSS_PROFILE is 'none'."""
        doc = parse(OCTAVE_LOSSLESS_WITH_NONE)
        validator = Validator()
        validator.validate(doc)

        warnings = [e for e in validator.errors if e.severity == "warning"]
        meta_warnings = [w for w in warnings if w.code.startswith("W_META")]
        assert len(meta_warnings) == 0

    def test_no_warning_tier_with_profile(self):
        """No warning when both COMPRESSION_TIER and non-none LOSS_PROFILE present."""
        doc = parse(OCTAVE_TIER_WITH_PROFILE)
        validator = Validator()
        validator.validate(doc)

        warnings = [e for e in validator.errors if e.severity == "warning"]
        meta_warnings = [w for w in warnings if w.code.startswith("W_META")]
        assert len(meta_warnings) == 0

    def test_no_warning_no_tier(self):
        """No warning when no COMPRESSION_TIER in META."""
        doc = parse(OCTAVE_NO_TIER)
        validator = Validator()
        validator.validate(doc)

        warnings = [e for e in validator.errors if e.severity == "warning"]
        meta_warnings = [w for w in warnings if w.code.startswith("W_META")]
        assert len(meta_warnings) == 0

    def test_warnings_are_not_errors(self):
        """W_META warnings have severity='warning', not 'error'."""
        doc = parse(OCTAVE_TIER_NO_PROFILE)
        validator = Validator()
        validator.validate(doc)

        meta_items = [e for e in validator.errors if e.code.startswith("W_META")]
        for item in meta_items:
            assert item.severity == "warning"
