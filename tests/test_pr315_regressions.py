"""Regression tests for PR#315 CE review findings.

Fix 1: Multi-zone hash identity — each literal zone must get a distinct, correct hash
Fix 2: W_META warnings — must fire based on document content, not schema presence
"""

import hashlib

from octave_mcp.core.parser import parse
from octave_mcp.core.validator import Validator, _count_literal_zones

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Two literal zones with the SAME assignment key but different content
OCTAVE_SAME_KEY_TWO_ZONES = """\
===SAMPLE===
META:
  TYPE::"TEST"

§1::SECTION_A
CODE::
```python
print("hello")
```

§2::SECTION_B
CODE::
```python
print("world")
```

===END==="""

# Three literal zones: two share a key, one unique
OCTAVE_MIXED_KEYS_THREE_ZONES = """\
===SAMPLE===
META:
  TYPE::"TEST"

§1::FIRST
DATA::
```json
{"a": 1}
```

§2::SECOND
DATA::
```json
{"b": 2}
```

§3::THIRD
CONFIG::
```yaml
key: value
```

===END==="""

# META with COMPRESSION_TIER but no schema provided
OCTAVE_TIER_NO_SCHEMA = """\
===SAMPLE===
META:
  TYPE::"TEST"
  COMPRESSION_TIER::AGGRESSIVE

§1::SECTION
KEY::"value"

===END==="""

# META with LOSS_PROFILE 'none' and non-lossless tier, no schema provided
OCTAVE_NONE_PROFILE_NO_SCHEMA = """\
===SAMPLE===
META:
  TYPE::"TEST"
  COMPRESSION_TIER::CONSERVATIVE
  LOSS_PROFILE::"none"

§1::SECTION
KEY::"value"

===END==="""

# META with both tier and profile, no schema provided — should produce NO warnings
OCTAVE_TIER_WITH_PROFILE_NO_SCHEMA = """\
===SAMPLE===
META:
  TYPE::"TEST"
  COMPRESSION_TIER::AGGRESSIVE
  LOSS_PROFILE::"drop_narrative_preserve_protocol"

§1::SECTION
KEY::"value"

===END==="""


# ===========================================================================
# Fix 1: Multi-zone hash identity — distinct correct hashes per zone
# ===========================================================================


class TestMultiZoneHashIdentity:
    """Each literal zone must produce a distinct, correct SHA-256 hash.

    Regression for: _get_literal_zone_content() first-match bug where
    multiple zones under the same assignment key all received the same hash.
    """

    def test_same_key_zones_get_distinct_hashes(self):
        """Two zones with the same key ('CODE') must get different hashes."""
        from octave_mcp.core.literal_zone_audit import build_literal_zone_repair_log

        doc = parse(OCTAVE_SAME_KEY_TWO_ZONES)
        zones = _count_literal_zones(doc)

        assert len(zones) == 2, f"Expected 2 zones, got {len(zones)}"

        log = build_literal_zone_repair_log(zones, doc, "test_stage")

        assert len(log.entries) == 2, f"Expected 2 entries, got {len(log.entries)}"
        # The two hashes MUST be different (different content)
        assert log.entries[0].pre_hash != log.entries[1].pre_hash, (
            "Two zones with different content must produce different hashes. " f"Both got: {log.entries[0].pre_hash}"
        )

    def test_same_key_zones_hash_correctness(self):
        """Each zone hash must match independently computed SHA-256 of its content."""
        from octave_mcp.core.literal_zone_audit import build_literal_zone_repair_log

        doc = parse(OCTAVE_SAME_KEY_TWO_ZONES)
        zones = _count_literal_zones(doc)
        log = build_literal_zone_repair_log(zones, doc, "test_stage")

        expected_hello = hashlib.sha256(b'print("hello")').hexdigest()
        expected_world = hashlib.sha256(b'print("world")').hexdigest()

        # Entries must be in document order
        assert (
            log.entries[0].pre_hash == expected_hello
        ), f"First zone hash mismatch: expected {expected_hello}, got {log.entries[0].pre_hash}"
        assert (
            log.entries[1].pre_hash == expected_world
        ), f"Second zone hash mismatch: expected {expected_world}, got {log.entries[1].pre_hash}"

    def test_entry_count_equals_zone_count(self):
        """len(entries) must equal len(zones) — invariant check."""
        from octave_mcp.core.literal_zone_audit import build_literal_zone_repair_log

        doc = parse(OCTAVE_MIXED_KEYS_THREE_ZONES)
        zones = _count_literal_zones(doc)
        log = build_literal_zone_repair_log(zones, doc, "test_stage")

        assert len(log.entries) == len(
            zones
        ), f"Entry/zone count mismatch: {len(log.entries)} entries vs {len(zones)} zones"

    def test_three_zones_mixed_keys_all_distinct(self):
        """Three zones (two sharing a key) all produce distinct correct hashes."""
        from octave_mcp.core.literal_zone_audit import build_literal_zone_repair_log

        doc = parse(OCTAVE_MIXED_KEYS_THREE_ZONES)
        zones = _count_literal_zones(doc)
        log = build_literal_zone_repair_log(zones, doc, "test_stage")

        assert len(log.entries) == 3

        hashes = [e.pre_hash for e in log.entries]
        assert len(set(hashes)) == 3, f"Expected 3 distinct hashes, got {len(set(hashes))} unique from {hashes}"

        # Verify each hash matches expected content
        expected_a = hashlib.sha256(b'{"a": 1}').hexdigest()
        expected_b = hashlib.sha256(b'{"b": 2}').hexdigest()
        expected_yaml = hashlib.sha256(b"key: value").hexdigest()

        assert log.entries[0].pre_hash == expected_a
        assert log.entries[1].pre_hash == expected_b
        assert log.entries[2].pre_hash == expected_yaml


# ===========================================================================
# Fix 2: W_META warnings fire without schema
# ===========================================================================


class TestWMetaWarningsWithoutSchema:
    """W_META warnings must fire based on document content, not schema presence.

    Regression for: _validate_meta() only ran when 'META' in self.schema,
    silently suppressing warnings when schema=None.
    """

    def test_w_meta_001_fires_without_schema(self):
        """W_META_001 fires when COMPRESSION_TIER present but no LOSS_PROFILE, even with schema=None."""
        doc = parse(OCTAVE_TIER_NO_SCHEMA)
        validator = Validator(schema=None)
        validator.validate(doc)

        warnings = [e for e in validator.errors if e.code == "W_META_001"]
        assert len(warnings) == 1, f"Expected W_META_001 warning, got codes: {[e.code for e in validator.errors]}"
        assert warnings[0].severity == "warning"

    def test_w_meta_002_fires_without_schema(self):
        """W_META_002 fires when LOSS_PROFILE='none' with non-lossless tier, even with schema=None."""
        doc = parse(OCTAVE_NONE_PROFILE_NO_SCHEMA)
        validator = Validator(schema=None)
        validator.validate(doc)

        warnings = [e for e in validator.errors if e.code == "W_META_002"]
        assert len(warnings) == 1, f"Expected W_META_002 warning, got codes: {[e.code for e in validator.errors]}"
        assert warnings[0].severity == "warning"

    def test_no_false_warnings_without_schema(self):
        """No W_META warnings when COMPRESSION_TIER has proper LOSS_PROFILE, schema=None."""
        doc = parse(OCTAVE_TIER_WITH_PROFILE_NO_SCHEMA)
        validator = Validator(schema=None)
        validator.validate(doc)

        meta_warnings = [e for e in validator.errors if e.code.startswith("W_META")]
        assert len(meta_warnings) == 0, f"Expected no W_META warnings, got: {[w.code for w in meta_warnings]}"

    def test_w_meta_001_fires_with_empty_schema(self):
        """W_META_001 fires with empty schema dict (no META key in schema)."""
        doc = parse(OCTAVE_TIER_NO_SCHEMA)
        validator = Validator(schema={})
        validator.validate(doc)

        warnings = [e for e in validator.errors if e.code == "W_META_001"]
        assert (
            len(warnings) == 1
        ), f"Expected W_META_001 warning with empty schema, got codes: {[e.code for e in validator.errors]}"
