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
        return asyncio.get_event_loop().run_until_complete(tool.execute(content=content, schema="COGNITION_DEFINITION"))

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
