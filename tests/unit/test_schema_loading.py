"""Tests for schema loading (P1.11)."""

from pathlib import Path

from octave_mcp.core.schema_extractor import SchemaDefinition
from octave_mcp.schemas.loader import load_schema


class TestSchemaLoading:
    """Test schema file loading."""

    def test_loads_schema_from_file(self):
        """Should load schema from .oct.md file.

        Issue #93: load_schema now returns SchemaDefinition instead of dict
        for proper holographic pattern parsing support.
        """
        # Use builtin META schema
        schema_path = Path(__file__).parent.parent.parent / "src/octave_mcp/schemas/builtin/meta.oct.md"
        if schema_path.exists():
            schema = load_schema(schema_path)
            assert isinstance(schema, SchemaDefinition)
