"""Tests for enhanced schema loader (Issue #93).

Tests loading of schema definitions from OCTAVE files using
the new holographic pattern parsing infrastructure.

TDD RED phase: Write failing tests before implementation.
"""

import tempfile

import pytest


class TestSchemaLoaderImports:
    """Test schema loader imports."""

    def test_load_schema_importable(self):
        """load_schema should be importable from schemas.loader."""
        from octave_mcp.schemas.loader import load_schema

        assert load_schema is not None

    def test_load_schema_returns_schema_definition(self):
        """load_schema should return a SchemaDefinition."""
        from octave_mcp.core.schema_extractor import SchemaDefinition
        from octave_mcp.schemas.loader import load_schema

        # Create a temporary schema file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".oct.md", delete=False) as f:
            f.write(
                """
===TEST_SCHEMA===
META:
  TYPE::PROTOCOL_DEFINITION
  VERSION::"1.0"

FIELDS:
  NAME::["example"∧REQ→§SELF]
===END===
"""
            )
            f.flush()
            schema = load_schema(f.name)
            assert isinstance(schema, SchemaDefinition)


class TestSchemaLoaderFunctionality:
    """Test schema loader core functionality."""

    def test_load_schema_extracts_name(self):
        """load_schema should extract schema name from envelope."""
        from octave_mcp.schemas.loader import load_schema

        with tempfile.NamedTemporaryFile(mode="w", suffix=".oct.md", delete=False) as f:
            f.write(
                """
===MY_SCHEMA===
META:
  TYPE::PROTOCOL_DEFINITION
  VERSION::"1.0"

FIELDS:
  ID::["abc"∧REQ→§SELF]
===END===
"""
            )
            f.flush()
            schema = load_schema(f.name)
            assert schema.name == "MY_SCHEMA"

    def test_load_schema_extracts_version(self):
        """load_schema should extract version from META block."""
        from octave_mcp.schemas.loader import load_schema

        with tempfile.NamedTemporaryFile(mode="w", suffix=".oct.md", delete=False) as f:
            f.write(
                """
===TEST===
META:
  TYPE::PROTOCOL_DEFINITION
  VERSION::"2.5.0"

FIELDS:
  NAME::["test"∧REQ→§SELF]
===END===
"""
            )
            f.flush()
            schema = load_schema(f.name)
            assert schema.version == "2.5.0"

    def test_load_schema_extracts_fields(self):
        """load_schema should extract field definitions."""
        from octave_mcp.schemas.loader import load_schema

        with tempfile.NamedTemporaryFile(mode="w", suffix=".oct.md", delete=False) as f:
            f.write(
                """
===TEST===
META:
  TYPE::PROTOCOL_DEFINITION

FIELDS:
  AGENT::["impl-lead"∧REQ→§INDEXER]
  STATUS::["ACTIVE"∧REQ→§SELF]
===END===
"""
            )
            f.flush()
            schema = load_schema(f.name)
            assert len(schema.fields) == 2
            assert "AGENT" in schema.fields
            assert "STATUS" in schema.fields

    def test_load_schema_extracts_policy(self):
        """load_schema should extract POLICY block."""
        from octave_mcp.schemas.loader import load_schema

        with tempfile.NamedTemporaryFile(mode="w", suffix=".oct.md", delete=False) as f:
            f.write(
                """
===TEST===
META:
  TYPE::PROTOCOL_DEFINITION

POLICY:
  VERSION::"1.0"
  UNKNOWN_FIELDS::REJECT

FIELDS:
  NAME::["test"∧REQ→§SELF]
===END===
"""
            )
            f.flush()
            schema = load_schema(f.name)
            assert schema.policy.version == "1.0"
            assert schema.policy.unknown_fields == "REJECT"


class TestSchemaLoaderFromSpecsDir:
    """Test loading schemas from specs/ directory."""

    def test_load_schema_by_name(self):
        """load_schema_by_name should find schema in specs/schemas/ directory."""
        # This assumes there's at least one schema in specs/schemas/
        # If not, this test should be skipped
        pass  # Placeholder - implement when specs/schemas/ has content

    def test_get_schema_search_paths(self):
        """get_schema_search_paths should return valid paths."""
        from octave_mcp.schemas.loader import get_schema_search_paths

        paths = get_schema_search_paths()
        assert isinstance(paths, list)
        assert len(paths) > 0


class TestSchemaLoaderErrors:
    """Test schema loader error handling."""

    def test_load_schema_file_not_found(self):
        """load_schema should raise FileNotFoundError for missing files."""
        from octave_mcp.schemas.loader import load_schema

        with pytest.raises(FileNotFoundError):
            load_schema("/nonexistent/path/schema.oct.md")

    def test_load_schema_invalid_content(self):
        """load_schema should handle invalid OCTAVE content gracefully."""
        from octave_mcp.schemas.loader import load_schema

        with tempfile.NamedTemporaryFile(mode="w", suffix=".oct.md", delete=False) as f:
            f.write("This is not valid OCTAVE content\n")
            f.flush()
            # Should return a minimal schema or raise a specific error
            schema = load_schema(f.name)
            # At minimum, should return something
            assert schema is not None


class TestBuiltinSchemas:
    """Test builtin schema loading."""

    def test_get_builtin_schema_meta(self):
        """get_builtin_schema should return META schema."""
        from octave_mcp.schemas.loader import get_builtin_schema

        schema = get_builtin_schema("META")
        assert schema is not None

    def test_load_builtin_schemas(self):
        """load_builtin_schemas should load all available schemas."""
        from octave_mcp.schemas.loader import load_builtin_schemas

        schemas = load_builtin_schemas()
        assert isinstance(schemas, dict)


class TestSchemaLoaderIntegration:
    """Integration tests for schema loader with holographic patterns."""

    def test_load_schema_with_enum_constraint(self):
        """Should correctly load schema with ENUM constraint."""
        from octave_mcp.schemas.loader import load_schema

        with tempfile.NamedTemporaryFile(mode="w", suffix=".oct.md", delete=False) as f:
            f.write(
                """
===TEST===
META:
  TYPE::PROTOCOL_DEFINITION

FIELDS:
  STATUS::["ACTIVE"∧REQ∧ENUM[ACTIVE,INACTIVE,DRAFT]→§SELF]
===END===
"""
            )
            f.flush()
            schema = load_schema(f.name)
            field = schema.fields["STATUS"]
            assert field.pattern.example == "ACTIVE"
            assert len(field.pattern.constraints.constraints) == 2  # REQ and ENUM

    def test_load_schema_with_target(self):
        """Should correctly load schema with extraction target."""
        from octave_mcp.schemas.loader import load_schema

        with tempfile.NamedTemporaryFile(mode="w", suffix=".oct.md", delete=False) as f:
            f.write(
                """
===TEST===
META:
  TYPE::PROTOCOL_DEFINITION

FIELDS:
  AGENT::["impl-lead"∧REQ→§INDEXER]
===END===
"""
            )
            f.flush()
            schema = load_schema(f.name)
            field = schema.fields["AGENT"]
            assert field.pattern.target == "INDEXER"

    def test_load_schema_field_is_required(self):
        """Should correctly identify required vs optional fields."""
        from octave_mcp.schemas.loader import load_schema

        with tempfile.NamedTemporaryFile(mode="w", suffix=".oct.md", delete=False) as f:
            f.write(
                """
===TEST===
META:
  TYPE::PROTOCOL_DEFINITION

FIELDS:
  REQUIRED_FIELD::["value"∧REQ→§SELF]
  OPTIONAL_FIELD::["value"∧OPT→§SELF]
===END===
"""
            )
            f.flush()
            schema = load_schema(f.name)
            assert schema.fields["REQUIRED_FIELD"].is_required is True
            assert schema.fields["OPTIONAL_FIELD"].is_required is False
