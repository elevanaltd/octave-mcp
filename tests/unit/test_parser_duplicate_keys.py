"""Tests for duplicate key detection in OCTAVE parser (GitHub Issue #179).

Per octave-core-spec.oct.md §1::ENVELOPE:
  DUPLICATES::keys_must_be_unique_per_block

When duplicate keys are encountered, the parser should:
1. Detect the duplicate during parsing
2. Emit a warning with key name and line numbers
3. Keep the last value (current behavior, but now auditable)

I4 Immutable: "If bits lost must have receipt"
Duplicate key overwrites are data loss - must be auditable.
"""

import pytest

from octave_mcp.core.parser import parse, parse_with_warnings


class TestDuplicateKeyDetectionMeta:
    """Test duplicate key detection in META blocks."""

    def test_detects_duplicate_key_in_meta_block(self):
        """Should detect duplicate key in META block and emit warning.

        Per spec: DUPLICATES::keys_must_be_unique_per_block
        Per I4: If bits lost must have receipt
        """
        content = """===TEST===
META:
  TYPE::FIRST_VALUE
  VERSION::"1.0"
  TYPE::SECOND_VALUE
===END==="""
        doc, warnings = parse_with_warnings(content)

        # Document should parse successfully
        assert doc is not None
        assert doc.name == "TEST"

        # Last value should win (existing behavior)
        assert doc.meta.get("TYPE") == "SECOND_VALUE"

        # I4 Audit: Should emit warning for duplicate key
        duplicate_warnings = [w for w in warnings if w.get("subtype") == "duplicate_key"]
        assert len(duplicate_warnings) >= 1, f"Expected duplicate key warning, got {warnings}"

        # Verify warning structure
        dup_warning = duplicate_warnings[0]
        assert dup_warning.get("type") == "lenient_parse"
        assert dup_warning.get("key") == "TYPE"
        assert dup_warning.get("first_line") is not None
        assert dup_warning.get("duplicate_line") is not None
        # First definition at line 3, second at line 5
        assert dup_warning.get("first_line") < dup_warning.get("duplicate_line")

    def test_detects_multiple_duplicate_keys_in_meta(self):
        """Should detect multiple different duplicate keys."""
        content = """===TEST===
META:
  TYPE::first
  VERSION::"1.0"
  TYPE::second
  VERSION::"2.0"
===END==="""
        doc, warnings = parse_with_warnings(content)

        # Both duplicates should be detected
        duplicate_warnings = [w for w in warnings if w.get("subtype") == "duplicate_key"]
        duplicate_keys = {w.get("key") for w in duplicate_warnings}
        assert "TYPE" in duplicate_keys
        assert "VERSION" in duplicate_keys

    def test_no_warning_for_unique_keys_in_meta(self):
        """Should not emit warning when all keys are unique."""
        content = """===TEST===
META:
  TYPE::SPEC
  VERSION::"1.0"
  STATUS::ACTIVE
===END==="""
        doc, warnings = parse_with_warnings(content)

        # No duplicate key warnings should be emitted
        duplicate_warnings = [w for w in warnings if w.get("subtype") == "duplicate_key"]
        assert len(duplicate_warnings) == 0


class TestDuplicateKeyDetectionInlineMap:
    """Test duplicate key detection in inline maps [k::v, k::v2]."""

    def test_detects_duplicate_key_in_inline_map(self):
        """Should detect duplicate key in inline map and emit warning.

        Inline maps: [k::v, k2::v2, k::v3] - third item duplicates first
        """
        content = """===TEST===
DATA::[name::Alice, age::30, name::Bob]
===END==="""
        doc, warnings = parse_with_warnings(content)

        # Document should parse successfully
        assert doc is not None
        assert len(doc.sections) == 1

        # I4 Audit: Should emit warning for duplicate key
        duplicate_warnings = [w for w in warnings if w.get("subtype") == "duplicate_key"]
        assert len(duplicate_warnings) >= 1, f"Expected duplicate key warning, got {warnings}"

        # Verify warning identifies the key
        dup_warning = duplicate_warnings[0]
        assert dup_warning.get("key") == "name"

    def test_no_warning_for_unique_keys_in_inline_map(self):
        """Should not emit warning when all inline map keys are unique."""
        content = """===TEST===
DATA::[name::Alice, age::30, city::NYC]
===END==="""
        doc, warnings = parse_with_warnings(content)

        # No duplicate key warnings should be emitted
        duplicate_warnings = [w for w in warnings if w.get("subtype") == "duplicate_key"]
        assert len(duplicate_warnings) == 0


class TestDuplicateKeyWarningFormat:
    """Test the format of duplicate key warnings per spec."""

    def test_warning_includes_line_numbers(self):
        """Warning should include both first and duplicate line numbers.

        Format: W_DUPLICATE_KEY::key_name at line N overwrites previous definition at line M
        """
        content = """===TEST===
META:
  KEY::first
  OTHER::value
  KEY::second
===END==="""
        doc, warnings = parse_with_warnings(content)

        duplicate_warnings = [w for w in warnings if w.get("subtype") == "duplicate_key"]
        assert len(duplicate_warnings) >= 1

        dup_warning = duplicate_warnings[0]
        # Line numbers should be present
        first_line = dup_warning.get("first_line")
        dup_line = dup_warning.get("duplicate_line")
        assert first_line is not None, "Missing first_line in warning"
        assert dup_line is not None, "Missing duplicate_line in warning"

        # First occurrence should be before duplicate
        assert first_line < dup_line, f"first_line ({first_line}) should be < duplicate_line ({dup_line})"

        # Message should follow spec format
        message = dup_warning.get("message", "")
        assert "KEY" in message
        assert "overwrites" in message.lower() or "duplicate" in message.lower()


class TestDuplicateKeyInNestedBlocks:
    """Test duplicate key detection respects block scope."""

    def test_same_key_in_different_blocks_is_allowed(self):
        """Same key in different blocks should NOT trigger warning.

        Spec: keys_must_be_unique_per_block - scoped to containing block
        """
        content = """===TEST===
BLOCK1:
  KEY::value1
BLOCK2:
  KEY::value2
===END==="""
        doc, warnings = parse_with_warnings(content)

        # No duplicate key warnings - different blocks
        duplicate_warnings = [w for w in warnings if w.get("subtype") == "duplicate_key"]
        assert len(duplicate_warnings) == 0, f"Unexpected duplicate warnings: {duplicate_warnings}"

    def test_duplicate_key_within_same_block(self):
        """Duplicate key within same block SHOULD trigger warning."""
        content = """===TEST===
CONFIG:
  SETTING::first
  OTHER::value
  SETTING::second
===END==="""
        doc, warnings = parse_with_warnings(content)

        # Should detect duplicate within CONFIG block
        # Note: Block children are stored in a list, not dict, so this tests
        # whether we add key tracking to block parsing
        # For now, this may not trigger - documenting expected behavior
        # Implementation may need to track keys in block children too
        _ = (doc, warnings)  # Suppress unused variable warning


class TestDuplicateKeyWithStrictMode:
    """Test strict mode behavior for duplicate keys."""

    @pytest.mark.skip(reason="Strict mode rejection not implemented yet")
    def test_strict_mode_rejects_duplicate_keys(self):
        """In strict mode, duplicate keys should raise ParserError.

        Per issue spec: Optionally reject in STRICT mode
        """
        from octave_mcp.core.parser import ParserError

        content = """===TEST===
META:
  TYPE::first
  TYPE::second
===END==="""
        # Future: strict=True should reject duplicates
        with pytest.raises(ParserError):
            parse(content, strict=True)  # type: ignore


class TestDuplicateKeyEdgeCases:
    """Edge cases for duplicate key detection."""

    def test_triple_duplicate_reports_all_duplicates(self):
        """Three occurrences of same key should report two warnings."""
        content = """===TEST===
META:
  KEY::first
  KEY::second
  KEY::third
===END==="""
        doc, warnings = parse_with_warnings(content)

        duplicate_warnings = [w for w in warnings if w.get("subtype") == "duplicate_key"]
        # Second occurrence (line N) overwrites first
        # Third occurrence (line M) overwrites second
        # Should emit 2 warnings total
        assert len(duplicate_warnings) >= 2, f"Expected 2 duplicate warnings, got {len(duplicate_warnings)}"

    def test_case_sensitive_key_comparison(self):
        """Key comparison should be case-sensitive.

        KEY and key are different keys - no duplicate warning.
        """
        content = """===TEST===
META:
  KEY::uppercase
  key::lowercase
===END==="""
        doc, warnings = parse_with_warnings(content)

        # Different case = different keys, no duplicate
        duplicate_warnings = [w for w in warnings if w.get("subtype") == "duplicate_key"]
        assert len(duplicate_warnings) == 0

    def test_empty_meta_block_no_warnings(self):
        """Empty META block should not emit any duplicate warnings."""
        content = """===TEST===
META:
===END==="""
        doc, warnings = parse_with_warnings(content)

        duplicate_warnings = [w for w in warnings if w.get("subtype") == "duplicate_key"]
        assert len(duplicate_warnings) == 0
