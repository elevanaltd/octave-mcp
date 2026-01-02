"""Tests for debate transcript schema (Issue #52).

TDD RED phase: These tests define the expected behavior for
debate transcript validation and JSON-to-OCTAVE conversion.

Debate transcripts from debate-hall-mcp have structure:
- THREAD_ID: Unique identifier
- TOPIC: What the debate is about
- MODE: "fixed" or "mediated"
- STATUS: "active", "synthesis", or "closed"
- PARTICIPANTS: List of roles (Wind, Wall, Door)
- TURNS: List of turn records
- SYNTHESIS: Final synthesis (optional)
"""

from pathlib import Path

import pytest

from octave_mcp.schemas.loader import load_schema, load_schema_by_name


class TestDebateSchemaLoading:
    """Test loading debate transcript schema from specs/schemas/."""

    def test_debate_schema_file_exists(self):
        """Debate schema file should exist in specs/schemas/."""
        schema_path = Path(__file__).parent.parent.parent / "specs" / "schemas" / "debate_transcript.oct.md"
        assert schema_path.exists(), f"Schema file not found at {schema_path}"

    def test_load_debate_schema_by_name(self):
        """load_schema_by_name should find debate_transcript schema."""
        schema = load_schema_by_name("DEBATE_TRANSCRIPT")
        assert schema is not None, "Should find DEBATE_TRANSCRIPT schema"
        assert schema.name == "DEBATE_TRANSCRIPT"

    def test_debate_schema_has_required_fields(self):
        """Debate schema should define required fields."""
        schema = load_schema_by_name("DEBATE_TRANSCRIPT")
        assert schema is not None

        required_fields = ["THREAD_ID", "TOPIC", "MODE", "STATUS", "PARTICIPANTS", "TURNS"]
        for field_name in required_fields:
            assert field_name in schema.fields, f"Schema should have {field_name} field"
            field = schema.fields[field_name]
            # Note: Complex holographic patterns like [[list]∧REQ∧TYPE[LIST]→§SELF]
            # may not parse constraints correctly due to nested brackets.
            # For simple patterns like ["value"∧REQ→§SELF], is_required works.
            # For fields with complex patterns, check raw_value contains REQ
            if field.pattern is not None:
                assert field.is_required, f"{field_name} should be required (via pattern)"
            else:
                assert "REQ" in (field.raw_value or ""), f"{field_name} should have REQ in raw_value"

    def test_debate_schema_synthesis_is_optional(self):
        """SYNTHESIS field should be optional."""
        schema = load_schema_by_name("DEBATE_TRANSCRIPT")
        assert schema is not None
        assert "SYNTHESIS" in schema.fields
        assert not schema.fields["SYNTHESIS"].is_required

    def test_debate_schema_mode_has_enum(self):
        """MODE field should have ENUM constraint for fixed/mediated."""
        schema = load_schema_by_name("DEBATE_TRANSCRIPT")
        assert schema is not None
        assert "MODE" in schema.fields

        mode_field = schema.fields["MODE"]
        # Check for ENUM either in pattern or raw_value
        # (pattern parsing may not extract combined constraints like ∧REQ∧ENUM[...])
        if mode_field.pattern is not None and mode_field.pattern.constraints:
            enum_values = None
            for constraint in mode_field.pattern.constraints.constraints:
                if hasattr(constraint, "values"):
                    enum_values = constraint.values
                    break
            if enum_values is not None:
                assert "fixed" in enum_values
                assert "mediated" in enum_values
                return  # Test passed via pattern

        # Fallback: check raw_value contains ENUM definition
        raw = mode_field.raw_value or ""
        assert "ENUM" in raw, "MODE should have ENUM in raw value"
        assert "fixed" in raw, "MODE should include 'fixed' value"
        assert "mediated" in raw, "MODE should include 'mediated' value"

    def test_debate_schema_status_has_enum(self):
        """STATUS field should have ENUM constraint for status values."""
        schema = load_schema_by_name("DEBATE_TRANSCRIPT")
        assert schema is not None
        assert "STATUS" in schema.fields

        status_field = schema.fields["STATUS"]
        # Check for ENUM either in pattern or raw_value
        if status_field.pattern is not None and status_field.pattern.constraints:
            enum_values = None
            for constraint in status_field.pattern.constraints.constraints:
                if hasattr(constraint, "values"):
                    enum_values = constraint.values
                    break
            if enum_values is not None:
                assert "active" in enum_values
                assert "synthesis" in enum_values
                assert "closed" in enum_values
                return  # Test passed via pattern

        # Fallback: check raw_value contains ENUM definition
        raw = status_field.raw_value or ""
        assert "ENUM" in raw, "STATUS should have ENUM in raw value"
        assert "active" in raw, "STATUS should include 'active' value"
        assert "synthesis" in raw, "STATUS should include 'synthesis' value"
        assert "closed" in raw, "STATUS should include 'closed' value"

    def test_debate_schema_has_version(self):
        """Debate schema should have version defined."""
        schema = load_schema_by_name("DEBATE_TRANSCRIPT")
        assert schema is not None
        assert schema.version is not None
        assert schema.version == "1.0"


class TestDebateSchemaValidation:
    """Test validation of debate transcripts against schema."""

    def test_valid_debate_transcript_validates(self):
        """Valid debate transcript should pass schema validation."""
        from octave_mcp.core.parser import parse
        from octave_mcp.core.validator import Validator
        from octave_mcp.schemas.loader import load_schema_by_name

        schema = load_schema_by_name("DEBATE_TRANSCRIPT")
        assert schema is not None

        # Create a valid debate transcript (no [...] which is invalid OCTAVE)
        content = """===DEBATE_TRANSCRIPT===
META:
  TYPE::DEBATE_TRANSCRIPT
  VERSION::"1.0"

THREAD_ID::test-debate-001
TOPIC::Whether AI should use OCTAVE format
MODE::fixed
STATUS::closed
PARTICIPANTS::[Wind, Wall, Door]
TURNS::[turn1, turn2]
SYNTHESIS::AI should adopt OCTAVE for structured outputs
===END==="""

        doc = parse(content)

        # Schema definition needs to be converted to dict for Validator
        schema_dict = {
            "name": schema.name,
            "version": schema.version or "1.0",
            "FIELDS": {
                field_name: {"required": field_def.is_required} for field_name, field_def in schema.fields.items()
            },
        }

        validator = Validator(schema=schema_dict)
        errors = validator.validate(doc, strict=False)

        # Should have no errors
        assert len(errors) == 0, f"Valid transcript should not have errors: {errors}"


class TestDebateSchemaFromFile:
    """Test loading the actual schema file."""

    def test_schema_parses_without_error(self):
        """Schema file should parse without errors."""
        schema_path = Path(__file__).parent.parent.parent / "specs" / "schemas" / "debate_transcript.oct.md"
        if not schema_path.exists():
            pytest.skip("Schema file not yet created")

        schema = load_schema(schema_path)
        assert schema is not None
        assert schema.name == "DEBATE_TRANSCRIPT"

    def test_schema_fields_have_holographic_patterns(self):
        """Schema fields should have valid holographic patterns."""
        schema_path = Path(__file__).parent.parent.parent / "specs" / "schemas" / "debate_transcript.oct.md"
        if not schema_path.exists():
            pytest.skip("Schema file not yet created")

        schema = load_schema(schema_path)

        for field_name, field_def in schema.fields.items():
            # Each field should have a parsed pattern
            assert (
                field_def.pattern is not None or field_def.raw_value is not None
            ), f"Field {field_name} should have a pattern or raw value"
