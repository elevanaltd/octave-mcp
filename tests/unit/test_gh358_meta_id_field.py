"""Tests for GitHub issue #358: META.ID as optional first-class field.

META.ID is canonical identity metadata that any document should be able to carry.
Removing ID for STRICT compliance is compliance theater, not genuine improvement.

Tests verify:
- META.ID passes STRICT validation (no E007)
- META.ID is optional (documents without it still validate)
- META.ID appears correctly in canonical output
- META.ID round-trips through parse -> emit cycle
"""

import pytest

from octave_mcp.core.parser import parse
from octave_mcp.core.validator import validate
from octave_mcp.schemas.loader import BUILTIN_SCHEMA_DEFINITIONS


class TestMetaIdStrictValidation:
    """META.ID must pass STRICT profile validation without E007."""

    def test_meta_id_passes_strict_validation(self):
        """META.ID should be accepted in STRICT mode without E007 errors.

        This is the core fix for #358: documents with META.ID should not
        fail STRICT validation with 'Unknown field ID not allowed'.
        """
        doc = """===TEST===
META:
  TYPE::"AGENT_DEFINITION"
  VERSION::"1.0"
  ID::"agent-001"

CONTENT::value
===END==="""

        ast = parse(doc)
        schema = BUILTIN_SCHEMA_DEFINITIONS.get("META")

        errors = validate(ast, schema=schema, strict=True)

        # Filter to only E007 errors about ID
        id_errors = [e for e in errors if e.code == "E007" and "ID" in e.field_path]
        assert len(id_errors) == 0, (
            f"META.ID should not trigger E007 in STRICT mode. "
            f"Got errors: {[(e.code, e.message) for e in id_errors]}"
        )

    def test_meta_id_with_all_fields_passes_strict(self):
        """META block with TYPE, VERSION, STATUS, and ID should all pass STRICT."""
        doc = """===TEST===
META:
  TYPE::"WORKFLOW"
  VERSION::"2.0"
  STATUS::ACTIVE
  ID::"workflow-xyz-123"

BODY::content
===END==="""

        ast = parse(doc)
        schema = BUILTIN_SCHEMA_DEFINITIONS.get("META")

        errors = validate(ast, schema=schema, strict=True)

        # No E007 errors at all (all fields are known)
        e007_errors = [e for e in errors if e.code == "E007"]
        assert len(e007_errors) == 0, (
            f"All META fields (TYPE, VERSION, STATUS, ID) should be recognized. "
            f"Got E007 errors: {[(e.code, e.message) for e in e007_errors]}"
        )


class TestMetaIdOptional:
    """META.ID must be optional -- documents without it still validate."""

    def test_document_without_id_still_validates(self):
        """Documents without META.ID should validate normally (no E003)."""
        doc = """===TEST===
META:
  TYPE::"TEST_DOC"
  VERSION::"1.0"

CONTENT::value
===END==="""

        ast = parse(doc)
        schema = BUILTIN_SCHEMA_DEFINITIONS.get("META")

        errors = validate(ast, schema=schema, strict=True)

        # No required-field errors for ID
        id_required_errors = [e for e in errors if e.code == "E003" and "ID" in e.message]
        assert len(id_required_errors) == 0, "META.ID should be optional -- missing ID must not trigger E003."

    def test_document_with_only_required_fields_validates(self):
        """Documents with only TYPE and VERSION should validate (ID not required)."""
        doc = """===TEST===
META:
  TYPE::"MINIMAL"
  VERSION::"1.0"
===END==="""

        ast = parse(doc)
        schema = BUILTIN_SCHEMA_DEFINITIONS.get("META")

        errors = validate(ast, schema=schema, strict=True)

        # Should have zero errors
        assert len(errors) == 0, (
            f"Document with only required META fields should validate. "
            f"Got errors: {[(e.code, e.message) for e in errors]}"
        )


class TestMetaIdCanonicalOutput:
    """META.ID should appear correctly in canonical (emitted) output."""

    def test_meta_id_preserved_in_parse(self):
        """META.ID should be present in parsed document meta dict."""
        doc = """===TEST===
META:
  TYPE::"AGENT_DEFINITION"
  VERSION::"7.0.0"
  ID::"implementation-lead"

§1::IDENTITY
  ROLE::IMPLEMENTATION_LEAD
===END==="""

        ast = parse(doc)

        assert "ID" in ast.meta, "META.ID should be present in parsed meta dict"
        assert (
            ast.meta["ID"] == '"implementation-lead"' or ast.meta["ID"] == "implementation-lead"
        ), f"META.ID value should be preserved. Got: {ast.meta['ID']}"

    def test_meta_id_round_trips_through_emit(self):
        """META.ID should survive parse -> emit -> parse cycle."""
        from octave_mcp.core.emitter import emit

        doc = """===TEST===
META:
  TYPE::"DOCUMENT"
  VERSION::"1.0"
  ID::"doc-round-trip"

CONTENT::value
===END==="""

        ast = parse(doc)
        emitted = emit(ast)
        re_parsed = parse(emitted)

        assert "ID" in re_parsed.meta, "META.ID should survive round-trip through emit"


class TestMetaIdInBuiltinSchema:
    """META.ID should be declared in the builtin schema definitions."""

    def test_id_in_builtin_schema_definitions(self):
        """BUILTIN_SCHEMA_DEFINITIONS META should include ID field."""
        meta_schema = BUILTIN_SCHEMA_DEFINITIONS.get("META")
        assert meta_schema is not None, "META schema should exist in BUILTIN_SCHEMA_DEFINITIONS"

        fields = meta_schema.get("META", {}).get("fields", {})
        assert "ID" in fields, f"META schema fields should include 'ID'. " f"Current fields: {list(fields.keys())}"
        assert fields["ID"]["type"] == "STRING", "META.ID should be typed as STRING"

    def test_id_not_in_required_fields(self):
        """META.ID should not be in the required fields list."""
        meta_schema = BUILTIN_SCHEMA_DEFINITIONS.get("META")
        assert meta_schema is not None

        required = meta_schema.get("META", {}).get("required", [])
        assert "ID" not in required, "META.ID should be optional (not in required list)"

    def test_id_in_file_based_schema(self):
        """File-based META schema (meta.oct.md) should declare ID field.

        Note: The META_SCHEMA file is a meta-schema that defines META block
        structure. The schema extractor does not extract its nested FIELDS
        block into SchemaDefinition.fields (by design). Instead, we verify
        the parsed document AST contains the ID field definition.
        """
        from pathlib import Path

        from octave_mcp.core.parser import parse as octave_parse

        meta_schema_path = (
            Path(__file__).parent.parent.parent / "src" / "octave_mcp" / "schemas" / "builtin" / "meta.oct.md"
        )
        if not meta_schema_path.exists():
            # Try package-relative path
            import octave_mcp.schemas.builtin

            meta_schema_path = Path(octave_mcp.schemas.builtin.__file__).parent / "meta.oct.md"

        assert meta_schema_path.exists(), f"meta.oct.md not found at {meta_schema_path}"

        content = meta_schema_path.read_text()
        doc = octave_parse(content)

        # The FIELDS section should contain an ID field definition
        # Walk the AST to find the FIELDS block and its ID child
        found_id = False
        for section in doc.sections:
            if getattr(section, "key", None) == "FIELDS":
                for child in getattr(section, "children", []):
                    if getattr(child, "key", None) == "ID":
                        found_id = True
                        break
        assert found_id, "meta.oct.md FIELDS block should contain an ID field definition"


class TestMetaIdMcpValidation:
    """META.ID should pass through MCP validate tool in STRICT profile."""

    @pytest.mark.asyncio
    async def test_validate_tool_strict_accepts_meta_id(self):
        """MCP validate tool with profile=STRICT should accept META.ID."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        content = """===TEST===
META:
  TYPE::"META"
  VERSION::"1.0"
  ID::"test-document-001"
===END==="""

        result = await tool.execute(content=content, schema="META", profile="STRICT")

        assert result["profile"] == "STRICT"
        # META.ID should not cause INVALID status
        validation_errors = result.get("validation_errors", [])
        id_errors = [e for e in validation_errors if "ID" in str(e.get("field", ""))]
        assert len(id_errors) == 0, f"META.ID should not trigger validation errors in STRICT mode. " f"Got: {id_errors}"
