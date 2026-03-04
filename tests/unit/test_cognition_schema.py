"""Tests for COGNITION_DEFINITION schema validation (Issue #325).

TDD RED phase: These tests define expected behavior for
cognition master file validation via octave_validate --schema COGNITION_DEFINITION.

Cognition files (logos.oct.md, ethos.oct.md, pathos.oct.md) have structure:
- §1::COGNITIVE_IDENTITY with NATURE block (FORCE, ESSENCE, ELEMENT)
- §2::COGNITIVE_RULES with MODE, PRIME_DIRECTIVE, THINK, THINK_NEVER
"""

from pathlib import Path

from octave_mcp.schemas.loader import load_schema_by_name


class TestCognitionSchemaLoading:
    """Test loading COGNITION_DEFINITION schema from specs/schemas/."""

    def test_cognition_schema_file_exists(self):
        """Cognition schema file should exist in resources."""
        schema_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "octave_mcp"
            / "resources"
            / "specs"
            / "schemas"
            / "cognition_definition.oct.md"
        )
        assert schema_path.exists(), f"Schema file not found at {schema_path}"

    def test_load_cognition_schema_by_name(self):
        """load_schema_by_name should find COGNITION_DEFINITION schema."""
        schema = load_schema_by_name("COGNITION_DEFINITION")
        assert schema is not None, "Should find COGNITION_DEFINITION schema"
        assert schema.name == "COGNITION_DEFINITION"

    def test_cognition_schema_has_version(self):
        """Cognition schema should have version defined."""
        schema = load_schema_by_name("COGNITION_DEFINITION")
        assert schema is not None
        assert schema.version is not None
        assert schema.version == "1.0"


class TestCognitionSchemaValidation:
    """Test validation of cognition files against COGNITION_DEFINITION schema."""

    def _validate_content(self, content: str) -> dict:
        """Helper to validate content through the MCP validate tool."""
        import asyncio

        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        return asyncio.run(tool.execute(content=content, schema="COGNITION_DEFINITION"))

    def test_valid_logos_file_validates(self):
        """LOGOS cognition file should pass COGNITION_DEFINITION validation."""
        logos_path = (
            Path(__file__).parent.parent.parent / "src" / "octave_mcp" / "resources" / "cognitions" / "logos.oct.md"
        )
        content = logos_path.read_text()
        result = self._validate_content(content)

        assert result["validation_status"] == "VALIDATED", (
            f"LOGOS should validate. Got: {result.get('validation_status')}. "
            f"Errors: {result.get('validation_errors', [])}"
        )
        assert result["valid"] is True

    def test_valid_ethos_file_validates(self):
        """ETHOS cognition file should pass COGNITION_DEFINITION validation."""
        ethos_path = (
            Path(__file__).parent.parent.parent / "src" / "octave_mcp" / "resources" / "cognitions" / "ethos.oct.md"
        )
        content = ethos_path.read_text()
        result = self._validate_content(content)

        assert result["validation_status"] == "VALIDATED", (
            f"ETHOS should validate. Got: {result.get('validation_status')}. "
            f"Errors: {result.get('validation_errors', [])}"
        )
        assert result["valid"] is True

    def test_valid_pathos_file_validates(self):
        """PATHOS cognition file should pass COGNITION_DEFINITION validation."""
        pathos_path = (
            Path(__file__).parent.parent.parent / "src" / "octave_mcp" / "resources" / "cognitions" / "pathos.oct.md"
        )
        content = pathos_path.read_text()
        result = self._validate_content(content)

        assert result["validation_status"] == "VALIDATED", (
            f"PATHOS should validate. Got: {result.get('validation_status')}. "
            f"Errors: {result.get('validation_errors', [])}"
        )
        assert result["valid"] is True

    def test_missing_prime_directive_is_invalid(self):
        """Cognition file missing PRIME_DIRECTIVE should fail validation."""
        content = """===COGNITION_TEST===
META:
  TYPE::COGNITION_DEFINITION
  VERSION::"1.0.0"
§1::COGNITIVE_IDENTITY
  NATURE:
    FORCE::STRUCTURE
    ESSENCE::ARCHITECT
    ELEMENT::DOOR
§2::COGNITIVE_RULES
  MODE::CONVERGENT
  THINK::["Rule one","Rule two"]
  THINK_NEVER::["Anti-pattern one"]
===END==="""

        result = self._validate_content(content)

        assert (
            result["validation_status"] == "INVALID"
        ), f"Missing PRIME_DIRECTIVE should be INVALID. Got: {result.get('validation_status')}"
        assert result["valid"] is False
        # Check that the error mentions PRIME_DIRECTIVE
        error_messages = [e.get("message", "") for e in result.get("validation_errors", [])]
        assert any(
            "PRIME_DIRECTIVE" in msg for msg in error_messages
        ), f"Error should mention PRIME_DIRECTIVE. Got: {error_messages}"

    def test_invalid_force_enum_is_invalid(self):
        """Cognition file with invalid FORCE enum value should fail validation."""
        content = """===COGNITION_TEST===
META:
  TYPE::COGNITION_DEFINITION
  VERSION::"1.0.0"
§1::COGNITIVE_IDENTITY
  NATURE:
    FORCE::CHAOS
    ESSENCE::ARCHITECT
    ELEMENT::DOOR
§2::COGNITIVE_RULES
  MODE::CONVERGENT
  PRIME_DIRECTIVE::"Test directive"
  THINK::["Rule one"]
  THINK_NEVER::["Anti-pattern one"]
===END==="""

        result = self._validate_content(content)

        assert (
            result["validation_status"] == "INVALID"
        ), f"Invalid FORCE enum should be INVALID. Got: {result.get('validation_status')}"
        assert result["valid"] is False
        # Check that the error mentions the invalid value
        error_messages = [e.get("message", "") for e in result.get("validation_errors", [])]
        assert any(
            "FORCE" in msg or "CHAOS" in msg for msg in error_messages
        ), f"Error should mention FORCE or CHAOS. Got: {error_messages}"

    def test_invalid_mode_enum_is_invalid(self):
        """Cognition file with invalid MODE enum value should fail validation."""
        content = """===COGNITION_TEST===
META:
  TYPE::COGNITION_DEFINITION
  VERSION::"1.0.0"
§1::COGNITIVE_IDENTITY
  NATURE:
    FORCE::STRUCTURE
    ESSENCE::ARCHITECT
    ELEMENT::DOOR
§2::COGNITIVE_RULES
  MODE::CREATIVE
  PRIME_DIRECTIVE::"Test directive"
  THINK::["Rule one"]
  THINK_NEVER::["Anti-pattern one"]
===END==="""

        result = self._validate_content(content)

        assert (
            result["validation_status"] == "INVALID"
        ), f"Invalid MODE enum should be INVALID. Got: {result.get('validation_status')}"
        assert result["valid"] is False

    def test_missing_nature_block_is_invalid(self):
        """Cognition file missing NATURE block should fail validation."""
        content = """===COGNITION_TEST===
META:
  TYPE::COGNITION_DEFINITION
  VERSION::"1.0.0"
§1::COGNITIVE_IDENTITY
§2::COGNITIVE_RULES
  MODE::CONVERGENT
  PRIME_DIRECTIVE::"Test directive"
  THINK::["Rule one"]
  THINK_NEVER::["Anti-pattern one"]
===END==="""

        result = self._validate_content(content)

        assert (
            result["validation_status"] == "INVALID"
        ), f"Missing NATURE block should be INVALID. Got: {result.get('validation_status')}"
        assert result["valid"] is False

    def test_missing_cognitive_rules_section_is_invalid(self):
        """Cognition file missing §2::COGNITIVE_RULES should fail validation."""
        content = """===COGNITION_TEST===
META:
  TYPE::COGNITION_DEFINITION
  VERSION::"1.0.0"
§1::COGNITIVE_IDENTITY
  NATURE:
    FORCE::STRUCTURE
    ESSENCE::ARCHITECT
    ELEMENT::DOOR
===END==="""

        result = self._validate_content(content)

        assert (
            result["validation_status"] == "INVALID"
        ), f"Missing COGNITIVE_RULES should be INVALID. Got: {result.get('validation_status')}"
        assert result["valid"] is False


class TestDebateTranscriptEnvelopeValidation:
    """Regression tests for DEBATE_TRANSCRIPT envelope-level validation (Issue #326).

    DEBATE_TRANSCRIPT documents have fields at the envelope level (document root),
    not nested inside blocks or sections. Prior to the fix, _build_deep_section_schemas
    only mapped nodes with child assignments, causing envelope-level fields to be
    missed. This produced false E003 errors for all required fields.
    """

    def _validate_content(self, content: str, schema: str = "DEBATE_TRANSCRIPT") -> dict:
        """Helper to validate content through the MCP validate tool."""
        import asyncio

        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        return asyncio.run(tool.execute(content=content, schema=schema))

    def test_valid_debate_transcript_validates(self):
        """Valid DEBATE_TRANSCRIPT with envelope-level fields should pass validation.

        Regression test for Issue #326: When META.TYPE == schema_name triggers deep
        section schema path, envelope-level assignments (THREAD_ID, TOPIC, etc.) must
        be captured by _build_deep_section_schemas to avoid false E003 errors.
        """
        content = """===MY_DEBATE===
META:
  TYPE::DEBATE_TRANSCRIPT
  VERSION::"1.0"
THREAD_ID::"test-debate-001"
TOPIC::"Should we use envelope-level fields?"
MODE::fixed
STATUS::active
PARTICIPANTS::[Wind,Wall,Door]
TURNS::[turn1,turn2]
===END==="""

        result = self._validate_content(content)

        assert result["validation_status"] == "VALIDATED", (
            f"Valid DEBATE_TRANSCRIPT should validate. Got: {result.get('validation_status')}. "
            f"Errors: {result.get('validation_errors', [])}"
        )
        assert result["valid"] is True

    def test_debate_transcript_missing_required_field_is_invalid(self):
        """DEBATE_TRANSCRIPT missing a required field should fail validation."""
        content = """===MY_DEBATE===
META:
  TYPE::DEBATE_TRANSCRIPT
  VERSION::"1.0"
THREAD_ID::"test-debate-002"
TOPIC::"Missing required fields"
MODE::fixed
STATUS::active
===END==="""
        # Missing PARTICIPANTS and TURNS (both REQ)

        result = self._validate_content(content)

        assert (
            result["validation_status"] == "INVALID"
        ), f"Missing required fields should be INVALID. Got: {result.get('validation_status')}"
        assert result["valid"] is False

    def test_debate_transcript_with_optional_fields_validates(self):
        """DEBATE_TRANSCRIPT with optional fields should also pass validation."""
        content = """===MY_DEBATE===
META:
  TYPE::DEBATE_TRANSCRIPT
  VERSION::"1.0"
THREAD_ID::"test-debate-003"
TOPIC::"Testing optional fields"
MODE::mediated
STATUS::closed
PARTICIPANTS::[Wind,Wall,Door]
TURNS::[turn1]
SYNTHESIS::"Final resolution reached"
MAX_ROUNDS::4
MAX_TURNS::12
===END==="""

        result = self._validate_content(content)

        assert result["validation_status"] == "VALIDATED", (
            f"DEBATE_TRANSCRIPT with optional fields should validate. "
            f"Got: {result.get('validation_status')}. "
            f"Errors: {result.get('validation_errors', [])}"
        )
        assert result["valid"] is True
