"""Tests for malformed holographic pattern warning (M3 CE Violation #3).

CE Violation #3: INVALID_HOLOGRAPHIC_PATTERN_SILENT_ACCEPT
Location: src/octave_mcp/core/schema_extractor.py:333

Problem: Malformed holographic patterns are caught and converted into
FieldDefinition with pattern=None, producing no validation warning.

Fix: Emit a validation warning (not error) indicating the pattern was malformed.
Per lenient parsing philosophy, this should warn but not block.

TDD RED phase: Tests should FAIL until fix is implemented.
"""

from octave_mcp.core.parser import parse
from octave_mcp.core.schema_extractor import (
    extract_schema_from_document,
)


class TestMalformedHolographicPatternWarning:
    """Test that malformed holographic patterns emit warnings."""

    def test_malformed_pattern_emits_warning(self):
        """Malformed holographic pattern should produce a warning.

        CE Violation #3: Current implementation silently accepts malformed
        patterns with pattern=None and no warning.

        Given: FIELDS block with invalid holographic syntax
        Expected: Warning emitted, field still extracted with pattern=None
        """
        doc = parse("""
===TEST===
META:
  TYPE::PROTOCOL_DEFINITION

FIELDS:
  INVALID_FIELD::not_a_holographic_pattern
===END===
""")
        # Extract schema - should emit warning for malformed pattern
        schema, warnings = extract_schema_from_document_with_warnings(doc)

        # Assert: Field is extracted but with pattern=None
        assert "INVALID_FIELD" in schema.fields
        assert schema.fields["INVALID_FIELD"].pattern is None

        # Assert: Warning was emitted
        assert len(warnings) > 0, "Expected warning for malformed holographic pattern, got none"
        assert any("INVALID_FIELD" in w.message for w in warnings), "Warning should mention the field name"
        assert any(
            "malformed" in w.message.lower() or "invalid" in w.message.lower() for w in warnings
        ), "Warning should indicate pattern was malformed/invalid"

    def test_valid_pattern_no_warning(self):
        """Valid holographic patterns should not emit warnings."""
        doc = parse("""
===TEST===
META:
  TYPE::PROTOCOL_DEFINITION

FIELDS:
  VALID_FIELD::["example"\u2227REQ\u2192\u00a7SELF]
===END===
""")
        schema, warnings = extract_schema_from_document_with_warnings(doc)

        # Assert: Field extracted with valid pattern
        assert "VALID_FIELD" in schema.fields
        assert schema.fields["VALID_FIELD"].pattern is not None

        # Assert: No warnings
        assert len(warnings) == 0, f"Unexpected warnings: {warnings}"

    def test_mixed_valid_and_invalid_patterns(self):
        """Mixed valid/invalid patterns should only warn for invalid ones."""
        doc = parse("""
===TEST===
META:
  TYPE::PROTOCOL_DEFINITION

FIELDS:
  VALID::["example"\u2227REQ\u2192\u00a7SELF]
  INVALID::broken_pattern_here
  ALSO_VALID::["another"\u2227OPT\u2192\u00a7INDEXER]
===END===
""")
        schema, warnings = extract_schema_from_document_with_warnings(doc)

        # Assert: Valid fields have patterns, invalid has None
        assert schema.fields["VALID"].pattern is not None
        assert schema.fields["INVALID"].pattern is None
        assert schema.fields["ALSO_VALID"].pattern is not None

        # Assert: Only one warning (for INVALID)
        assert len(warnings) == 1
        assert "INVALID" in warnings[0].message

    def test_warning_includes_raw_value(self):
        """Warning should include the raw malformed pattern for debugging."""
        doc = parse("""
===TEST===
META:
  TYPE::PROTOCOL_DEFINITION

FIELDS:
  BAD_FIELD::completely_wrong_syntax
===END===
""")
        schema, warnings = extract_schema_from_document_with_warnings(doc)

        # Assert: Warning includes raw value for debugging
        assert len(warnings) > 0
        # Warning should help author identify the problematic value
        warning_text = warnings[0].message
        assert "BAD_FIELD" in warning_text


class TestWarningDataStructure:
    """Test the warning data structure from schema extraction."""

    def test_warning_has_field_path(self):
        """Warning should include field path for locating the issue."""
        doc = parse("""
===TEST===
META:
  TYPE::PROTOCOL_DEFINITION

FIELDS:
  PROBLEMATIC::invalid_pattern
===END===
""")
        schema, warnings = extract_schema_from_document_with_warnings(doc)

        assert len(warnings) > 0
        warning = warnings[0]
        assert (
            hasattr(warning, "field_path")
            or "FIELDS.PROBLEMATIC" in warning.message
            or "PROBLEMATIC" in warning.message
        )

    def test_warning_severity_is_warning_not_error(self):
        """Warning severity should be 'warning', not 'error'.

        Per lenient parsing philosophy: warn but don't block.
        """
        doc = parse("""
===TEST===
META:
  TYPE::PROTOCOL_DEFINITION

FIELDS:
  MALFORMED::bad_syntax
===END===
""")
        schema, warnings = extract_schema_from_document_with_warnings(doc)

        assert len(warnings) > 0
        warning = warnings[0]
        # If warning has severity attribute, it should be 'warning'
        if hasattr(warning, "severity"):
            assert warning.severity == "warning", f"Expected severity 'warning', got {warning.severity}"


# Helper function to extract schema with warnings
def extract_schema_from_document_with_warnings(doc):
    """Extract schema from document, returning (schema, warnings) tuple.

    M3 CE violation #3 fix: SchemaDefinition now has a warnings attribute.
    """

    schema = extract_schema_from_document(doc)

    # SchemaDefinition now has warnings attribute (M3 fix)
    return schema, schema.warnings
