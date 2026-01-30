"""Tests for deep nesting warning and error (Issue #192).

TDD RED phase: These tests define the expected behavior for deep nesting detection.

Requirements from Issue #192:
1. Warning at 5+ levels: Emit W_DEEP_NESTING::depth N at line L, consider flattening
2. Error at 100 levels: Hard error per spec (implementation cap)
3. Configurable threshold: Default 5, allow override

Tests:
- Warning emitted at depth 5
- Warning includes depth and line number
- Error at depth 100
- Threshold is configurable (custom threshold)
- No warning at depth 4 (boundary test)
"""

import pytest

from octave_mcp.core.lexer import tokenize
from octave_mcp.core.parser import Parser, ParserError, parse_with_warnings


class TestDeepNestingWarning:
    """Test deep nesting warning emission at configurable threshold."""

    def test_no_warning_at_depth_4(self):
        """Should NOT emit warning at depth 4 (below default threshold).

        Given content with 4 levels of bracket nesting,
        when parsed with default threshold (5),
        then no W_DEEP_NESTING warning should be emitted.
        """
        # Depth 4: [[[[value]]]]
        content = """===TEST===
META:
  TYPE::TEST
DATA:
  NESTED::[[[[value]]]]
===END==="""

        doc, warnings = parse_with_warnings(content)

        # No deep nesting warnings at depth 4
        deep_nesting_warnings = [
            w for w in warnings if w.get("subtype") == "deep_nesting" or "W_DEEP_NESTING" in w.get("message", "")
        ]
        assert (
            len(deep_nesting_warnings) == 0
        ), f"Expected no deep nesting warnings at depth 4, got: {deep_nesting_warnings}"

    def test_warning_at_depth_5(self):
        """Should emit W_DEEP_NESTING warning at depth 5 (default threshold).

        Given content with 5 levels of bracket nesting,
        when parsed with default threshold (5),
        then W_DEEP_NESTING warning should be emitted.
        """
        # Depth 5: [[[[[value]]]]]
        content = """===TEST===
META:
  TYPE::TEST
DATA:
  NESTED::[[[[[value]]]]]
===END==="""

        doc, warnings = parse_with_warnings(content)

        # Should have deep nesting warning at depth 5
        deep_nesting_warnings = [
            w for w in warnings if w.get("subtype") == "deep_nesting" or "W_DEEP_NESTING" in w.get("message", "")
        ]
        assert len(deep_nesting_warnings) >= 1, f"Expected W_DEEP_NESTING warning at depth 5. Warnings: {warnings}"

    def test_warning_includes_depth(self):
        """Warning message should include the actual nesting depth.

        Given content with 6 levels of nesting,
        when parsed,
        then the warning message should include the depth where warning was triggered.
        Note: Warning is emitted when first reaching depth >= threshold (5),
        so "depth 5" is expected even with 6 levels of nesting.
        """
        # Depth 6: [[[[[[value]]]]]]
        content = """===TEST===
META:
  TYPE::TEST
DATA:
  NESTED::[[[[[[value]]]]]]
===END==="""

        doc, warnings = parse_with_warnings(content)

        # Find deep nesting warning
        deep_nesting_warnings = [
            w for w in warnings if w.get("subtype") == "deep_nesting" or "W_DEEP_NESTING" in w.get("message", "")
        ]
        assert len(deep_nesting_warnings) >= 1, f"Expected deep nesting warning. Warnings: {warnings}"

        # Warning should include depth (warns at threshold, which is 5)
        warning = deep_nesting_warnings[0]
        message = warning.get("message", "")
        assert "depth" in message.lower() and (
            "5" in message or "6" in message
        ), f"Warning should mention depth (5 or 6), got: {message}"

    def test_warning_includes_line_number(self):
        """Warning should include the line number where deep nesting occurred.

        Given content with deep nesting,
        when parsed,
        then the warning should include line number information.
        """
        # Depth 5 on line 5
        content = """===TEST===
META:
  TYPE::TEST
DATA:
  NESTED::[[[[[value]]]]]
===END==="""

        doc, warnings = parse_with_warnings(content)

        # Find deep nesting warning
        deep_nesting_warnings = [
            w for w in warnings if w.get("subtype") == "deep_nesting" or "W_DEEP_NESTING" in w.get("message", "")
        ]
        assert len(deep_nesting_warnings) >= 1, f"Expected deep nesting warning. Warnings: {warnings}"

        # Warning should have line number
        warning = deep_nesting_warnings[0]
        assert (
            "line" in warning or "line" in warning.get("message", "").lower()
        ), f"Warning should include line number. Warning: {warning}"

    def test_warning_at_depth_7(self):
        """Should emit W_DEEP_NESTING warning at depth 7.

        Given content with 7 levels of bracket nesting,
        when parsed,
        then W_DEEP_NESTING warning should be emitted with correct depth.
        """
        # Depth 7: [[[[[[[value]]]]]]]
        content = """===TEST===
META:
  TYPE::TEST
DATA:
  NESTED::[[[[[[[ value ]]]]]]]
===END==="""

        doc, warnings = parse_with_warnings(content)

        # Should have deep nesting warning
        deep_nesting_warnings = [
            w for w in warnings if w.get("subtype") == "deep_nesting" or "W_DEEP_NESTING" in w.get("message", "")
        ]
        assert len(deep_nesting_warnings) >= 1, f"Expected W_DEEP_NESTING warning at depth 7. Warnings: {warnings}"


class TestDeepNestingError:
    """Test hard error at maximum nesting depth (100)."""

    def test_error_at_depth_100(self):
        """Should raise ParserError at depth 100 (hard implementation cap).

        Given content with 100 levels of bracket nesting,
        when parsed,
        then ParserError should be raised with E_MAX_NESTING_EXCEEDED.
        """
        # Build deeply nested content: 100 levels of [
        opening_brackets = "[" * 100
        closing_brackets = "]" * 100
        content = f"""===TEST===
META:
  TYPE::TEST
DATA:
  NESTED::{opening_brackets}value{closing_brackets}
===END==="""

        # Should raise error at depth 100
        with pytest.raises(ParserError) as exc_info:
            parse_with_warnings(content)

        # Error should have correct code
        assert (
            "E_MAX_NESTING_EXCEEDED" in str(exc_info.value) or exc_info.value.code == "E_MAX_NESTING_EXCEEDED"
        ), f"Expected E_MAX_NESTING_EXCEEDED error, got: {exc_info.value}"

    def test_no_error_at_depth_99(self):
        """Should NOT raise error at depth 99 (just under implementation cap).

        Given content with 99 levels of bracket nesting,
        when parsed,
        then parsing should succeed (with warnings, but no error).
        """
        # Build deeply nested content: 99 levels of [
        opening_brackets = "[" * 99
        closing_brackets = "]" * 99
        content = f"""===TEST===
META:
  TYPE::TEST
DATA:
  NESTED::{opening_brackets}value{closing_brackets}
===END==="""

        # Should parse without error (may have warnings)
        doc, warnings = parse_with_warnings(content)

        # Should have parsed successfully
        assert doc is not None


class TestConfigurableThreshold:
    """Test configurable nesting threshold."""

    def test_custom_threshold_3_warns_at_depth_3(self):
        """Should emit warning at depth 3 when threshold is set to 3.

        Given content with 3 levels of nesting,
        and parser configured with deep_nesting_threshold=3,
        then W_DEEP_NESTING warning should be emitted.
        """
        # Depth 3: [[[value]]]
        content = """===TEST===
META:
  TYPE::TEST
DATA:
  NESTED::[[[value]]]
===END==="""

        tokens, _ = tokenize(content)  # tokenize returns (tokens, repairs)
        parser = Parser(tokens, strict_structure=False, deep_nesting_threshold=3)
        parser.parse_document()  # Only need to parse to trigger warnings

        # Should have deep nesting warning at depth 3
        deep_nesting_warnings = [
            w for w in parser.warnings if w.get("subtype") == "deep_nesting" or "W_DEEP_NESTING" in w.get("message", "")
        ]
        assert (
            len(deep_nesting_warnings) >= 1
        ), f"Expected W_DEEP_NESTING warning at depth 3 with threshold=3. Warnings: {parser.warnings}"

    def test_custom_threshold_3_no_warning_at_depth_2(self):
        """Should NOT emit warning at depth 2 when threshold is set to 3.

        Given content with 2 levels of nesting,
        and parser configured with deep_nesting_threshold=3,
        then no W_DEEP_NESTING warning should be emitted.
        """
        # Depth 2: [[value]]
        content = """===TEST===
META:
  TYPE::TEST
DATA:
  NESTED::[[value]]
===END==="""

        tokens, _ = tokenize(content)  # tokenize returns (tokens, repairs)
        parser = Parser(tokens, strict_structure=False, deep_nesting_threshold=3)
        parser.parse_document()  # Only need to parse to trigger warnings

        # Should NOT have deep nesting warning at depth 2
        deep_nesting_warnings = [
            w for w in parser.warnings if w.get("subtype") == "deep_nesting" or "W_DEEP_NESTING" in w.get("message", "")
        ]
        assert (
            len(deep_nesting_warnings) == 0
        ), f"Expected no deep nesting warnings at depth 2 with threshold=3, got: {deep_nesting_warnings}"

    def test_custom_threshold_10_no_warning_at_depth_9(self):
        """Should NOT emit warning at depth 9 when threshold is set to 10.

        Given content with 9 levels of nesting,
        and parser configured with deep_nesting_threshold=10,
        then no W_DEEP_NESTING warning should be emitted.
        """
        # Depth 9: [[[[[[[[[value]]]]]]]]]
        opening_brackets = "[" * 9
        closing_brackets = "]" * 9
        content = f"""===TEST===
META:
  TYPE::TEST
DATA:
  NESTED::{opening_brackets}value{closing_brackets}
===END==="""

        tokens, _ = tokenize(content)  # tokenize returns (tokens, repairs)
        parser = Parser(tokens, strict_structure=False, deep_nesting_threshold=10)
        parser.parse_document()  # Only need to parse to trigger warnings

        # Should NOT have deep nesting warning at depth 9
        deep_nesting_warnings = [
            w for w in parser.warnings if w.get("subtype") == "deep_nesting" or "W_DEEP_NESTING" in w.get("message", "")
        ]
        assert (
            len(deep_nesting_warnings) == 0
        ), f"Expected no deep nesting warnings at depth 9 with threshold=10, got: {deep_nesting_warnings}"

    def test_custom_threshold_10_warns_at_depth_10(self):
        """Should emit warning at depth 10 when threshold is set to 10.

        Given content with 10 levels of nesting,
        and parser configured with deep_nesting_threshold=10,
        then W_DEEP_NESTING warning should be emitted.
        """
        # Depth 10: [[[[[[[[[[value]]]]]]]]]]
        opening_brackets = "[" * 10
        closing_brackets = "]" * 10
        content = f"""===TEST===
META:
  TYPE::TEST
DATA:
  NESTED::{opening_brackets}value{closing_brackets}
===END==="""

        tokens, _ = tokenize(content)  # tokenize returns (tokens, repairs)
        parser = Parser(tokens, strict_structure=False, deep_nesting_threshold=10)
        parser.parse_document()  # Only need to parse to trigger warnings

        # Should have deep nesting warning at depth 10
        deep_nesting_warnings = [
            w for w in parser.warnings if w.get("subtype") == "deep_nesting" or "W_DEEP_NESTING" in w.get("message", "")
        ]
        assert (
            len(deep_nesting_warnings) >= 1
        ), f"Expected W_DEEP_NESTING warning at depth 10 with threshold=10. Warnings: {parser.warnings}"


class TestNestingWarningSubtype:
    """Test that warning has correct structure and subtype."""

    def test_warning_has_subtype_deep_nesting(self):
        """Warning should have subtype='deep_nesting' for filtering.

        Given content with deep nesting,
        when parsed,
        then the warning dict should have subtype='deep_nesting'.
        """
        # Depth 5
        content = """===TEST===
META:
  TYPE::TEST
DATA:
  NESTED::[[[[[value]]]]]
===END==="""

        doc, warnings = parse_with_warnings(content)

        # Find deep nesting warning
        deep_nesting_warnings = [w for w in warnings if w.get("subtype") == "deep_nesting"]
        assert len(deep_nesting_warnings) >= 1, f"Expected warning with subtype='deep_nesting'. Warnings: {warnings}"

    def test_warning_has_type_lenient_parse(self):
        """Warning should have type='lenient_parse' consistent with other warnings.

        Given content with deep nesting,
        when parsed,
        then the warning dict should have type='lenient_parse'.
        """
        # Depth 5
        content = """===TEST===
META:
  TYPE::TEST
DATA:
  NESTED::[[[[[value]]]]]
===END==="""

        doc, warnings = parse_with_warnings(content)

        # Find deep nesting warning
        deep_nesting_warnings = [w for w in warnings if w.get("subtype") == "deep_nesting"]
        assert len(deep_nesting_warnings) >= 1

        warning = deep_nesting_warnings[0]
        assert warning.get("type") == "lenient_parse", f"Expected type='lenient_parse', got: {warning.get('type')}"
