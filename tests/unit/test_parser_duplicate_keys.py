"""Tests for duplicate key detection in OCTAVE parser (GitHub Issues #179 and #294).

Per octave-core-spec.oct.md §1::ENVELOPE:
  DUPLICATES::keys_must_be_unique_per_block

When duplicate keys are encountered, the parser should:
1. Detect the duplicate during parsing
2. Emit a warning with key name and line numbers of ALL occurrences
3. Keep the last value (current behavior, but now auditable)
4. Mark as safe=false, semantics_changed=true (data loss)

I4 Immutable: "If bits lost must have receipt"
Duplicate key overwrites are data loss - must be auditable.

GH#294: Extended to blocks, sections, and document-level assignments.
The correction code must be W_DUPLICATE_KEY (not W_LENIENT_DUPLICATE_KEY).
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
    """Test duplicate key detection in inline maps [k::v, k::v2].

    GH#270: Separate InlineMap entries in a list are array items, not map entries.
    Repeated keys across separate InlineMap items should NOT trigger warnings
    because lists semantically allow repeated keys (e.g., REGEX::"a", REGEX::"b").
    """

    def test_no_warning_for_repeated_keys_across_inline_map_items(self):
        """Repeated keys across separate InlineMap items in a list should NOT warn.

        GH#270: [REGEX::"a", REGEX::"b"] is an array of InlineMap entries.
        Each REGEX is a separate list item -- not a map collision.
        """
        content = """===TEST===
MUST_USE::[REGEX::"^pattern_a", REGEX::"^pattern_b", REGEX::"^pattern_c"]
===END==="""
        doc, warnings = parse_with_warnings(content)

        # Document should parse successfully
        assert doc is not None

        # Find the MUST_USE assignment
        must_use = None
        for node in doc.sections:
            if hasattr(node, "key") and node.key == "MUST_USE":
                must_use = node
                break
        assert must_use is not None, "MUST_USE field not found"
        assert hasattr(must_use.value, "items"), "Expected ListValue"
        assert len(must_use.value.items) == 3, f"Expected 3 items, got {len(must_use.value.items)}"

        # No duplicate key warnings should be emitted for cross-item keys
        duplicate_warnings = [w for w in warnings if w.get("subtype") == "duplicate_key"]
        assert (
            len(duplicate_warnings) == 0
        ), f"Should not warn for repeated keys across list items: {duplicate_warnings}"

    def test_no_warning_for_unique_keys_in_inline_map(self):
        """Should not emit warning when all inline map keys are unique."""
        content = """===TEST===
DATA::[name::Alice, age::30, city::NYC]
===END==="""
        doc, warnings = parse_with_warnings(content)

        # No duplicate key warnings should be emitted
        duplicate_warnings = [w for w in warnings if w.get("subtype") == "duplicate_key"]
        assert len(duplicate_warnings) == 0

    def test_preserves_all_entries_with_repeated_keys_in_list(self):
        """All InlineMap entries with same key must be preserved in list items.

        GH#270: This is the core I1 (syntactic fidelity) test -- the parser
        must not merge or drop entries just because they share a key name.
        """
        content = """===TEST===
PATTERNS::[PATTERN::"first", PATTERN::"second"]
===END==="""
        doc, warnings = parse_with_warnings(content)

        assert doc is not None
        patterns = None
        for node in doc.sections:
            if hasattr(node, "key") and node.key == "PATTERNS":
                patterns = node
                break
        assert patterns is not None
        items = patterns.value.items
        assert len(items) == 2, f"Both items must be preserved, got {len(items)}"

        # Verify each item has the correct value
        from octave_mcp.core.ast_nodes import InlineMap

        assert isinstance(items[0], InlineMap)
        assert isinstance(items[1], InlineMap)
        assert items[0].pairs.get("PATTERN") == "first"
        assert items[1].pairs.get("PATTERN") == "second"

        # No spurious warnings
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

        # GH#294: Message should follow enhanced spec format
        message = dup_warning.get("message", "")
        assert "KEY" in message
        assert "appears" in message and "only last value kept" in message


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
        """GH#294: Duplicate key within same block SHOULD trigger warning."""
        content = """===TEST===
CONFIG:
  SETTING::first
  OTHER::value
  SETTING::second
===END==="""
        doc, warnings = parse_with_warnings(content)

        # Should detect duplicate within CONFIG block
        duplicate_warnings = [w for w in warnings if w.get("subtype") == "duplicate_key"]
        assert len(duplicate_warnings) >= 1, f"Expected duplicate key warning in block, got {warnings}"

        dup_warning = duplicate_warnings[0]
        assert dup_warning.get("key") == "SETTING"
        assert "all_lines" in dup_warning, "Warning must include all_lines for GH#294"

    def test_duplicate_key_within_section(self):
        """GH#294: Duplicate key within a section SHOULD trigger warning."""
        content = """===TEST===
\u00a71::IDENTITY
  ROLE::first
  NAME::test
  ROLE::second
===END==="""
        doc, warnings = parse_with_warnings(content)

        duplicate_warnings = [w for w in warnings if w.get("subtype") == "duplicate_key"]
        assert len(duplicate_warnings) >= 1, f"Expected duplicate key warning in section, got {warnings}"

        dup_warning = duplicate_warnings[0]
        assert dup_warning.get("key") == "ROLE"


class TestDuplicateKeyAtDocumentLevel:
    """GH#294: Test duplicate key detection at document top level."""

    def test_duplicate_top_level_assignment(self):
        """Duplicate assignment keys at document level should trigger warning."""
        content = """===TEST===
MEANING::first
OTHER::value
MEANING::second
===END==="""
        doc, warnings = parse_with_warnings(content)

        duplicate_warnings = [w for w in warnings if w.get("subtype") == "duplicate_key"]
        assert len(duplicate_warnings) >= 1, f"Expected duplicate key warning at document level, got {warnings}"

        dup_warning = duplicate_warnings[0]
        assert dup_warning.get("key") == "MEANING"

    def test_six_duplicates_at_same_level(self):
        """GH#294 evidence case: 6 occurrences of same key should report all lines.

        Reproduces the actual incident where MEANING appeared 6 times.
        """
        content = """===TEST===
OPERATORS:
  MEANING::synthesis
  MEANING::tension
  MEANING::constraint
  MEANING::flow
  MEANING::alternative
  MEANING::concatenation
===END==="""
        doc, warnings = parse_with_warnings(content)

        duplicate_warnings = [w for w in warnings if w.get("subtype") == "duplicate_key"]
        assert len(duplicate_warnings) >= 1, f"Expected duplicate key warnings, got {warnings}"

        # GH#294: Warning must include all_lines with ALL occurrences
        # Find the consolidated warning for MEANING
        meaning_warnings = [w for w in duplicate_warnings if w.get("key") == "MEANING"]
        assert len(meaning_warnings) >= 1

        # Check that all_lines captures all 6 occurrences
        warning = meaning_warnings[-1]  # Last warning should have cumulative info
        all_lines = warning.get("all_lines", [])
        assert len(all_lines) == 6, f"Expected 6 line entries in all_lines, got {len(all_lines)}: {all_lines}"


class TestDuplicateKeyWarningFormatGH294:
    """GH#294: Test the enhanced warning format per issue spec."""

    def test_warning_has_all_lines_field(self):
        """GH#294: Warning must include all_lines with line numbers of all occurrences."""
        content = """===TEST===
META:
  KEY::first
  KEY::second
  KEY::third
===END==="""
        doc, warnings = parse_with_warnings(content)

        duplicate_warnings = [w for w in warnings if w.get("subtype") == "duplicate_key"]
        assert len(duplicate_warnings) >= 1

        # The last warning for KEY should have all_lines covering all 3 occurrences
        key_warnings = [w for w in duplicate_warnings if w.get("key") == "KEY"]
        last_warning = key_warnings[-1]
        all_lines = last_warning.get("all_lines", [])
        assert len(all_lines) == 3, f"Expected 3 lines in all_lines, got {all_lines}"

    def test_warning_message_format_gh294(self):
        """GH#294: Message must match spec format with count and line list."""
        content = """===TEST===
META:
  ITEM::alpha
  ITEM::beta
  ITEM::gamma
===END==="""
        doc, warnings = parse_with_warnings(content)

        duplicate_warnings = [w for w in warnings if w.get("subtype") == "duplicate_key"]
        last_warning = [w for w in duplicate_warnings if w.get("key") == "ITEM"][-1]

        message = last_warning.get("message", "")
        # GH#294 format: "Key 'ITEM' appears N times at lines X, Y, Z -- only last value kept"
        assert "ITEM" in message
        assert "appears" in message
        assert "3 times" in message
        assert "only last value kept" in message


class TestDuplicateKeyCorrectionMapping:
    """GH#294: Test that corrections array uses correct format."""

    def test_correction_code_is_w_duplicate_key(self):
        """GH#294: Correction code must be W_DUPLICATE_KEY, not W_LENIENT_DUPLICATE_KEY."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()
        warnings = [
            {
                "type": "lenient_parse",
                "subtype": "duplicate_key",
                "key": "MEANING",
                "first_line": 10,
                "duplicate_line": 15,
                "all_lines": [10, 12, 15],
                "message": "Key 'MEANING' appears 3 times at lines 10, 12, 15 -- only last value kept",
            }
        ]

        corrections = tool._map_parse_warnings_to_corrections(warnings)

        dup_corrections = [c for c in corrections if c.get("code") == "W_DUPLICATE_KEY"]
        assert len(dup_corrections) == 1, (
            f"Expected correction with code W_DUPLICATE_KEY, got codes: " f"{[c.get('code') for c in corrections]}"
        )

    def test_correction_safe_false_semantics_changed_true(self):
        """GH#294: Correction must have safe=false, semantics_changed=true."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()
        warnings = [
            {
                "type": "lenient_parse",
                "subtype": "duplicate_key",
                "key": "TEST",
                "first_line": 5,
                "duplicate_line": 8,
                "all_lines": [5, 8],
                "message": "Key 'TEST' appears 2 times at lines 5, 8 -- only last value kept",
            }
        ]

        corrections = tool._map_parse_warnings_to_corrections(warnings)
        dup_corrections = [c for c in corrections if c.get("code") == "W_DUPLICATE_KEY"]
        assert len(dup_corrections) == 1

        correction = dup_corrections[0]
        assert correction.get("safe") is False, f"Expected safe=false, got {correction.get('safe')}"
        assert (
            correction.get("semantics_changed") is True
        ), f"Expected semantics_changed=true, got {correction.get('semantics_changed')}"


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
        """Three occurrences of same key should report warnings with all_lines."""
        content = """===TEST===
META:
  KEY::first
  KEY::second
  KEY::third
===END==="""
        doc, warnings = parse_with_warnings(content)

        duplicate_warnings = [w for w in warnings if w.get("subtype") == "duplicate_key"]
        # Should emit warnings for duplicate occurrences
        assert len(duplicate_warnings) >= 2, f"Expected 2 duplicate warnings, got {len(duplicate_warnings)}"

        # GH#294: Last warning should have all 3 lines in all_lines
        key_warnings = [w for w in duplicate_warnings if w.get("key") == "KEY"]
        last_warning = key_warnings[-1]
        assert len(last_warning.get("all_lines", [])) == 3

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
