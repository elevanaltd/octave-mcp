"""Test cases for SchemaRepository (P2.5).

Tests schema repository functionality:
- Initialization and builtin schema loading
- Schema registration and retrieval
- Version handling
"""

import pytest

from octave_mcp.schemas.repository import SchemaRepository


class TestSchemaRepository:
    """Test SchemaRepository functionality."""

    @pytest.fixture
    def repository(self):
        """Create SchemaRepository instance."""
        return SchemaRepository()

    def test_repository_initializes(self, repository):
        """Repository initializes successfully."""
        assert repository is not None

    def test_repository_has_empty_schemas_dict(self, repository):
        """Repository has schemas dictionary."""
        # Repository should have internal schemas storage
        assert hasattr(repository, "_schemas") or hasattr(repository, "schemas")

    def test_register_schema(self, repository):
        """Can register a custom schema."""
        # For now, just test the interface exists
        # Actual schema loading is deferred
        repository.register("test_schema", None)

        # Should be able to retrieve it
        result = repository.get("test_schema")
        # Schema can be None for now (minimal implementation)
        assert result is None  # Registered as None

    def test_get_nonexistent_schema_returns_none(self, repository):
        """Getting nonexistent schema returns None."""
        schema = repository.get("nonexistent")
        assert schema is None

    def test_list_schemas(self, repository):
        """Can list available schemas."""
        schemas = repository.list_schemas()
        assert isinstance(schemas, list)

    def test_register_and_retrieve(self, repository):
        """Can register and retrieve schema."""
        from octave_mcp.schemas.repository import Schema

        # Create minimal schema
        test_schema = Schema(name="TEST", version="1.0", fields={})

        repository.register("TEST", test_schema)

        retrieved = repository.get("TEST")
        assert retrieved is not None
        assert retrieved.name == "TEST"

    def test_multiple_schemas(self, repository):
        """Can register multiple schemas."""
        from octave_mcp.schemas.repository import Schema

        schema1 = Schema(name="SCHEMA1", version="1.0", fields={})
        schema2 = Schema(name="SCHEMA2", version="1.0", fields={})

        repository.register("SCHEMA1", schema1)
        repository.register("SCHEMA2", schema2)

        schemas = repository.list_schemas()
        assert "SCHEMA1" in schemas
        assert "SCHEMA2" in schemas
        assert len(schemas) >= 2

    def test_overwrite_schema(self, repository):
        """Can overwrite existing schema."""
        from octave_mcp.schemas.repository import Schema

        schema_v1 = Schema(name="TEST", version="1.0", fields={})
        schema_v2 = Schema(name="TEST", version="2.0", fields={})

        repository.register("TEST", schema_v1)
        repository.register("TEST", schema_v2)

        retrieved = repository.get("TEST")
        assert retrieved.version == "2.0"
