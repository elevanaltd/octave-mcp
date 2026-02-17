"""Tests for RepairLogEntry and LiteralZoneRepairLog.

Issue #235: Per-zone I4 audit receipts for literal zone content preservation.

T02: Verifies RepairLogEntry construction, LiteralZoneRepairLog.all_preserved
property logic, and to_dict() serialization for MCP tool responses.
"""

from octave_mcp.core.repair_log import LiteralZoneRepairLog, RepairLogEntry


class TestRepairLogEntryConstruction:
    """Test RepairLogEntry construction with all required fields."""

    def test_construction_with_all_fields(self) -> None:
        """RepairLogEntry accepts all required fields."""
        entry = RepairLogEntry(
            zone_key="DOC.CODE",
            line=5,
            action="preserved",
            pre_hash="abc123",
            post_hash="abc123",
            timestamp="2026-02-17T00:00:00Z",
            source_stage="repair",
        )
        assert entry.zone_key == "DOC.CODE"
        assert entry.line == 5
        assert entry.action == "preserved"
        assert entry.pre_hash == "abc123"
        assert entry.post_hash == "abc123"
        assert entry.timestamp == "2026-02-17T00:00:00Z"
        assert entry.source_stage == "repair"

    def test_construction_with_stripped_action(self) -> None:
        """RepairLogEntry accepts action='stripped'."""
        entry = RepairLogEntry(
            zone_key="DOC.SECTION.CONFIG",
            line=10,
            action="stripped",
            pre_hash="aaa",
            post_hash="bbb",
            timestamp="2026-02-17T01:00:00Z",
            source_stage="emitter",
        )
        assert entry.action == "stripped"
        assert entry.pre_hash != entry.post_hash

    def test_nested_key_path(self) -> None:
        """zone_key supports dotted OCTAVE key paths."""
        entry = RepairLogEntry(
            zone_key="DOC.SECTION.SUBSECTION.CODE",
            line=42,
            action="preserved",
            pre_hash="hash1",
            post_hash="hash1",
            timestamp="2026-02-17T02:00:00Z",
            source_stage="validator",
        )
        assert entry.zone_key == "DOC.SECTION.SUBSECTION.CODE"


class TestLiteralZoneRepairLogAllPreserved:
    """Test the all_preserved property for correctness."""

    def test_all_preserved_true_when_all_hashes_match(self) -> None:
        """all_preserved is True when every entry has matching hashes and action='preserved'."""
        entries = [
            RepairLogEntry(
                zone_key="DOC.A",
                line=1,
                action="preserved",
                pre_hash="hash1",
                post_hash="hash1",
                timestamp="2026-02-17T00:00:00Z",
                source_stage="repair",
            ),
            RepairLogEntry(
                zone_key="DOC.B",
                line=10,
                action="preserved",
                pre_hash="hash2",
                post_hash="hash2",
                timestamp="2026-02-17T00:00:01Z",
                source_stage="repair",
            ),
        ]
        log = LiteralZoneRepairLog(entries=entries)
        assert log.all_preserved is True

    def test_all_preserved_false_when_hash_mismatch(self) -> None:
        """all_preserved is False when pre_hash != post_hash."""
        entries = [
            RepairLogEntry(
                zone_key="DOC.A",
                line=1,
                action="preserved",
                pre_hash="hash1",
                post_hash="hash1",
                timestamp="2026-02-17T00:00:00Z",
                source_stage="repair",
            ),
            RepairLogEntry(
                zone_key="DOC.B",
                line=10,
                action="preserved",
                pre_hash="hash_before",
                post_hash="hash_after",
                timestamp="2026-02-17T00:00:01Z",
                source_stage="repair",
            ),
        ]
        log = LiteralZoneRepairLog(entries=entries)
        assert log.all_preserved is False

    def test_all_preserved_false_when_action_stripped(self) -> None:
        """all_preserved is False when any entry has action='stripped'."""
        entries = [
            RepairLogEntry(
                zone_key="DOC.A",
                line=1,
                action="stripped",
                pre_hash="hash1",
                post_hash="",
                timestamp="2026-02-17T00:00:00Z",
                source_stage="repair",
            ),
        ]
        log = LiteralZoneRepairLog(entries=entries)
        assert log.all_preserved is False

    def test_all_preserved_false_stripped_even_with_matching_hashes(self) -> None:
        """all_preserved is False when action='stripped' even if hashes happen to match."""
        entries = [
            RepairLogEntry(
                zone_key="DOC.A",
                line=1,
                action="stripped",
                pre_hash="same",
                post_hash="same",
                timestamp="2026-02-17T00:00:00Z",
                source_stage="repair",
            ),
        ]
        log = LiteralZoneRepairLog(entries=entries)
        assert log.all_preserved is False

    def test_empty_log_is_vacuously_true(self) -> None:
        """Empty LiteralZoneRepairLog(entries=[]) has all_preserved=True (vacuously true)."""
        log = LiteralZoneRepairLog(entries=[])
        assert log.all_preserved is True


class TestLiteralZoneRepairLogToDict:
    """Test to_dict() serialization for MCP tool responses."""

    def test_to_dict_returns_list_of_dicts(self) -> None:
        """to_dict() returns a list of dictionaries."""
        entries = [
            RepairLogEntry(
                zone_key="DOC.CODE",
                line=5,
                action="preserved",
                pre_hash="abc",
                post_hash="abc",
                timestamp="2026-02-17T00:00:00Z",
                source_stage="repair",
            ),
        ]
        log = LiteralZoneRepairLog(entries=entries)
        result = log.to_dict()
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], dict)

    def test_to_dict_contains_all_required_keys(self) -> None:
        """Each dict in to_dict() has all required keys."""
        entry = RepairLogEntry(
            zone_key="DOC.CODE",
            line=5,
            action="preserved",
            pre_hash="abc",
            post_hash="abc",
            timestamp="2026-02-17T00:00:00Z",
            source_stage="repair",
        )
        log = LiteralZoneRepairLog(entries=[entry])
        result = log.to_dict()
        expected_keys = {
            "zone_key",
            "line",
            "action",
            "pre_hash",
            "post_hash",
            "timestamp",
            "source_stage",
        }
        assert set(result[0].keys()) == expected_keys

    def test_to_dict_values_match_entry(self) -> None:
        """to_dict() values match the original RepairLogEntry fields."""
        entry = RepairLogEntry(
            zone_key="DOC.SECTION.CONFIG",
            line=42,
            action="stripped",
            pre_hash="before_hash",
            post_hash="after_hash",
            timestamp="2026-02-17T03:00:00Z",
            source_stage="emitter",
        )
        log = LiteralZoneRepairLog(entries=[entry])
        result = log.to_dict()
        d = result[0]
        assert d["zone_key"] == "DOC.SECTION.CONFIG"
        assert d["line"] == 42
        assert d["action"] == "stripped"
        assert d["pre_hash"] == "before_hash"
        assert d["post_hash"] == "after_hash"
        assert d["timestamp"] == "2026-02-17T03:00:00Z"
        assert d["source_stage"] == "emitter"

    def test_to_dict_multiple_entries(self) -> None:
        """to_dict() serializes multiple entries in order."""
        entries = [
            RepairLogEntry(
                zone_key="DOC.A",
                line=1,
                action="preserved",
                pre_hash="h1",
                post_hash="h1",
                timestamp="2026-02-17T00:00:00Z",
                source_stage="repair",
            ),
            RepairLogEntry(
                zone_key="DOC.B",
                line=20,
                action="stripped",
                pre_hash="h2",
                post_hash="h3",
                timestamp="2026-02-17T00:00:01Z",
                source_stage="emitter",
            ),
        ]
        log = LiteralZoneRepairLog(entries=entries)
        result = log.to_dict()
        assert len(result) == 2
        assert result[0]["zone_key"] == "DOC.A"
        assert result[1]["zone_key"] == "DOC.B"

    def test_to_dict_empty_log(self) -> None:
        """to_dict() returns empty list for empty log."""
        log = LiteralZoneRepairLog(entries=[])
        result = log.to_dict()
        assert result == []
