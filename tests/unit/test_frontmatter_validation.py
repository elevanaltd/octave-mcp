"""Tests for Zone 2 (YAML frontmatter) validation — Issue #244.

Extends I5 Schema Sovereignty to Zone 2 so that schemas with FRONTMATTER
definitions validate Document.raw_frontmatter fields.

TDD RED phase: These tests define the expected behavior before implementation.
"""


class TestFrontmatterFieldDefDataclass:
    """Test the FrontmatterFieldDef dataclass."""

    def test_frontmatter_field_def_importable(self):
        """FrontmatterFieldDef should be importable from schema_extractor."""
        from octave_mcp.core.schema_extractor import FrontmatterFieldDef

        assert FrontmatterFieldDef is not None

    def test_frontmatter_field_def_defaults(self):
        """FrontmatterFieldDef should have sensible defaults."""
        from octave_mcp.core.schema_extractor import FrontmatterFieldDef

        field_def = FrontmatterFieldDef(name="test")
        assert field_def.name == "test"
        assert field_def.required is False
        assert field_def.field_type == "STRING"

    def test_frontmatter_field_def_required(self):
        """FrontmatterFieldDef should support required=True."""
        from octave_mcp.core.schema_extractor import FrontmatterFieldDef

        field_def = FrontmatterFieldDef(name="name", required=True, field_type="STRING")
        assert field_def.required is True
        assert field_def.field_type == "STRING"

    def test_frontmatter_field_def_list_type(self):
        """FrontmatterFieldDef should support LIST type."""
        from octave_mcp.core.schema_extractor import FrontmatterFieldDef

        field_def = FrontmatterFieldDef(name="allowed-tools", required=True, field_type="LIST")
        assert field_def.field_type == "LIST"


class TestSchemaDefinitionFrontmatter:
    """Test that SchemaDefinition supports frontmatter field definitions."""

    def test_schema_definition_has_frontmatter_field(self):
        """SchemaDefinition should have a frontmatter dict attribute."""
        from octave_mcp.core.schema_extractor import SchemaDefinition

        schema = SchemaDefinition(name="TEST")
        assert hasattr(schema, "frontmatter")
        assert isinstance(schema.frontmatter, dict)
        assert len(schema.frontmatter) == 0

    def test_schema_definition_with_frontmatter_fields(self):
        """SchemaDefinition should accept frontmatter field definitions."""
        from octave_mcp.core.schema_extractor import FrontmatterFieldDef, SchemaDefinition

        schema = SchemaDefinition(
            name="SKILL",
            frontmatter={
                "name": FrontmatterFieldDef(name="name", required=True, field_type="STRING"),
                "description": FrontmatterFieldDef(name="description", required=True, field_type="STRING"),
                "allowed-tools": FrontmatterFieldDef(name="allowed-tools", required=True, field_type="LIST"),
            },
        )
        assert len(schema.frontmatter) == 3
        assert schema.frontmatter["name"].required is True

    def test_schema_without_frontmatter_backward_compat(self):
        """Schemas without frontmatter should work exactly as before."""
        from octave_mcp.core.schema_extractor import SchemaDefinition

        schema = SchemaDefinition(name="META", version="1.0.0")
        assert schema.frontmatter == {}


class TestFrontmatterExtraction:
    """Test extraction of FRONTMATTER block from schema documents."""

    def test_extract_frontmatter_from_schema_document(self):
        """extract_schema_from_document should parse FRONTMATTER block."""
        from octave_mcp.core.parser import parse
        from octave_mcp.core.schema_extractor import extract_schema_from_document

        content = """===SKILL_SCHEMA===
META:
  TYPE::SCHEMA
  VERSION::"1.0.0"
  STATUS::ACTIVE
---
FRONTMATTER:
  name:
    REQUIRED::true
    TYPE::STRING
  description:
    REQUIRED::true
    TYPE::STRING
  allowed-tools:
    REQUIRED::true
    TYPE::LIST
  version:
    REQUIRED::false
    TYPE::STRING
===END==="""
        doc = parse(content)
        schema = extract_schema_from_document(doc)

        assert len(schema.frontmatter) == 4
        assert schema.frontmatter["name"].required is True
        assert schema.frontmatter["name"].field_type == "STRING"
        assert schema.frontmatter["description"].required is True
        assert schema.frontmatter["allowed-tools"].required is True
        assert schema.frontmatter["allowed-tools"].field_type == "LIST"
        assert schema.frontmatter["version"].required is False

    def test_extract_no_frontmatter_block(self):
        """Schemas without FRONTMATTER block should have empty frontmatter dict."""
        from octave_mcp.core.parser import parse
        from octave_mcp.core.schema_extractor import extract_schema_from_document

        content = """===META_SCHEMA===
META:
  TYPE::SCHEMA
  VERSION::"1.0.0"
---
FIELDS:
  NAME::["example"∧REQ]
===END==="""
        doc = parse(content)
        schema = extract_schema_from_document(doc)

        assert schema.frontmatter == {}


class TestValidatorFrontmatter:
    """Test the Validator's frontmatter validation capability."""

    def test_validate_frontmatter_valid(self):
        """Valid frontmatter should produce no errors."""
        from octave_mcp.core.schema_extractor import FrontmatterFieldDef, SchemaDefinition
        from octave_mcp.core.validator import validate_frontmatter

        schema = SchemaDefinition(
            name="SKILL",
            frontmatter={
                "name": FrontmatterFieldDef(name="name", required=True, field_type="STRING"),
                "description": FrontmatterFieldDef(name="description", required=True, field_type="STRING"),
                "allowed-tools": FrontmatterFieldDef(name="allowed-tools", required=True, field_type="LIST"),
            },
        )

        raw_frontmatter = 'name: my-skill\ndescription: "A test skill"\nallowed-tools: ["*"]'

        errors = validate_frontmatter(raw_frontmatter, schema)
        assert len(errors) == 0

    def test_validate_frontmatter_missing_required_field(self):
        """Missing required frontmatter field should produce E_FM_REQUIRED error."""
        from octave_mcp.core.schema_extractor import FrontmatterFieldDef, SchemaDefinition
        from octave_mcp.core.validator import validate_frontmatter

        schema = SchemaDefinition(
            name="SKILL",
            frontmatter={
                "name": FrontmatterFieldDef(name="name", required=True, field_type="STRING"),
                "description": FrontmatterFieldDef(name="description", required=True, field_type="STRING"),
                "allowed-tools": FrontmatterFieldDef(name="allowed-tools", required=True, field_type="LIST"),
            },
        )

        # Missing 'name' field
        raw_frontmatter = 'description: "A test skill"\nallowed-tools: ["*"]'

        errors = validate_frontmatter(raw_frontmatter, schema)
        assert len(errors) == 1
        assert errors[0].code == "E_FM_REQUIRED"
        assert "name" in errors[0].message

    def test_validate_frontmatter_multiple_missing_fields(self):
        """Multiple missing required fields should produce multiple errors."""
        from octave_mcp.core.schema_extractor import FrontmatterFieldDef, SchemaDefinition
        from octave_mcp.core.validator import validate_frontmatter

        schema = SchemaDefinition(
            name="SKILL",
            frontmatter={
                "name": FrontmatterFieldDef(name="name", required=True, field_type="STRING"),
                "description": FrontmatterFieldDef(name="description", required=True, field_type="STRING"),
                "allowed-tools": FrontmatterFieldDef(name="allowed-tools", required=True, field_type="LIST"),
            },
        )

        # Missing all required fields
        raw_frontmatter = "version: 1.0"

        errors = validate_frontmatter(raw_frontmatter, schema)
        assert len(errors) == 3
        error_fields = {e.field_path for e in errors}
        assert "frontmatter.name" in error_fields
        assert "frontmatter.description" in error_fields
        assert "frontmatter.allowed-tools" in error_fields

    def test_validate_frontmatter_wrong_type_expects_list(self):
        """Frontmatter field with wrong type should produce E_FM_TYPE error."""
        from octave_mcp.core.schema_extractor import FrontmatterFieldDef, SchemaDefinition
        from octave_mcp.core.validator import validate_frontmatter

        schema = SchemaDefinition(
            name="SKILL",
            frontmatter={
                "name": FrontmatterFieldDef(name="name", required=True, field_type="STRING"),
                "allowed-tools": FrontmatterFieldDef(name="allowed-tools", required=True, field_type="LIST"),
            },
        )

        # allowed-tools is a string instead of list
        raw_frontmatter = 'name: my-skill\nallowed-tools: "not-a-list"'

        errors = validate_frontmatter(raw_frontmatter, schema)
        assert len(errors) == 1
        assert errors[0].code == "E_FM_TYPE"
        assert "allowed-tools" in errors[0].message

    def test_validate_frontmatter_wrong_type_expects_string(self):
        """Frontmatter field expecting STRING but got list should produce E_FM_TYPE."""
        from octave_mcp.core.schema_extractor import FrontmatterFieldDef, SchemaDefinition
        from octave_mcp.core.validator import validate_frontmatter

        schema = SchemaDefinition(
            name="SKILL",
            frontmatter={
                "name": FrontmatterFieldDef(name="name", required=True, field_type="STRING"),
            },
        )

        raw_frontmatter = "name:\n  - item1\n  - item2"

        errors = validate_frontmatter(raw_frontmatter, schema)
        assert len(errors) == 1
        assert errors[0].code == "E_FM_TYPE"

    def test_validate_frontmatter_none_raw(self):
        """None raw_frontmatter with required fields should produce errors."""
        from octave_mcp.core.schema_extractor import FrontmatterFieldDef, SchemaDefinition
        from octave_mcp.core.validator import validate_frontmatter

        schema = SchemaDefinition(
            name="SKILL",
            frontmatter={
                "name": FrontmatterFieldDef(name="name", required=True, field_type="STRING"),
            },
        )

        errors = validate_frontmatter(None, schema)
        assert len(errors) >= 1
        assert errors[0].code == "E_FM_REQUIRED"

    def test_validate_frontmatter_no_schema_frontmatter(self):
        """Schema without frontmatter defs should return empty errors."""
        from octave_mcp.core.schema_extractor import SchemaDefinition
        from octave_mcp.core.validator import validate_frontmatter

        schema = SchemaDefinition(name="META")

        errors = validate_frontmatter("name: test", schema)
        assert len(errors) == 0

    def test_validate_frontmatter_optional_field_absent(self):
        """Optional frontmatter field being absent should not produce errors."""
        from octave_mcp.core.schema_extractor import FrontmatterFieldDef, SchemaDefinition
        from octave_mcp.core.validator import validate_frontmatter

        schema = SchemaDefinition(
            name="SKILL",
            frontmatter={
                "name": FrontmatterFieldDef(name="name", required=True, field_type="STRING"),
                "version": FrontmatterFieldDef(name="version", required=False, field_type="STRING"),
            },
        )

        raw_frontmatter = "name: my-skill"

        errors = validate_frontmatter(raw_frontmatter, schema)
        assert len(errors) == 0

    def test_validate_frontmatter_yaml_parse_error(self):
        """Invalid YAML in frontmatter should produce E_FM_PARSE error."""
        from octave_mcp.core.schema_extractor import FrontmatterFieldDef, SchemaDefinition
        from octave_mcp.core.validator import validate_frontmatter

        schema = SchemaDefinition(
            name="SKILL",
            frontmatter={
                "name": FrontmatterFieldDef(name="name", required=True, field_type="STRING"),
            },
        )

        raw_frontmatter = "name: [invalid yaml\n  : bad"

        errors = validate_frontmatter(raw_frontmatter, schema)
        assert len(errors) >= 1
        assert errors[0].code == "E_FM_PARSE"


class TestSkillSchemaBuiltin:
    """Test that the SKILL schema is available as a builtin."""

    def test_skill_schema_loadable(self):
        """SKILL schema should be loadable by name."""
        from octave_mcp.schemas.loader import load_schema_by_name

        schema = load_schema_by_name("SKILL")
        assert schema is not None
        assert schema.name == "SKILL_SCHEMA"

    def test_skill_schema_has_frontmatter(self):
        """SKILL schema should define frontmatter requirements."""
        from octave_mcp.schemas.loader import load_schema_by_name

        schema = load_schema_by_name("SKILL")
        assert schema is not None
        assert len(schema.frontmatter) >= 3
        assert "name" in schema.frontmatter
        assert "description" in schema.frontmatter
        assert "allowed-tools" in schema.frontmatter
        assert schema.frontmatter["name"].required is True
        assert schema.frontmatter["description"].required is True
        assert schema.frontmatter["allowed-tools"].required is True
        assert schema.frontmatter["allowed-tools"].field_type == "LIST"

    def test_skill_schema_has_body_fields(self):
        """SKILL schema should define OCTAVE body fields."""
        from octave_mcp.schemas.loader import load_schema_by_name

        schema = load_schema_by_name("SKILL")
        assert schema is not None
        # At minimum, TYPE should be required
        assert "TYPE" in schema.fields


class TestValidatorIntegrationWithFrontmatter:
    """Integration tests for the Validator with frontmatter validation."""

    def test_validator_validate_with_frontmatter(self):
        """Validator.validate should validate frontmatter when schema has frontmatter defs."""
        from octave_mcp.core.parser import parse
        from octave_mcp.core.schema_extractor import FrontmatterFieldDef, SchemaDefinition
        from octave_mcp.core.validator import Validator

        content = """---
name: my-skill
description: A test skill
allowed-tools: ["*"]
---
===SKILL===
META:
  TYPE::SKILL
  VERSION::"1.0"
===END==="""
        doc = parse(content)

        schema_def = SchemaDefinition(
            name="SKILL",
            frontmatter={
                "name": FrontmatterFieldDef(name="name", required=True, field_type="STRING"),
                "description": FrontmatterFieldDef(name="description", required=True, field_type="STRING"),
                "allowed-tools": FrontmatterFieldDef(name="allowed-tools", required=True, field_type="LIST"),
            },
        )

        validator = Validator()
        errors = validator.validate(doc, section_schemas={"SKILL": schema_def})
        # Should pass - all required frontmatter fields present
        fm_errors = [e for e in errors if e.code.startswith("E_FM")]
        assert len(fm_errors) == 0

    def test_validator_validate_missing_frontmatter_field(self):
        """Validator.validate should report missing frontmatter fields."""
        from octave_mcp.core.parser import parse
        from octave_mcp.core.schema_extractor import FrontmatterFieldDef, SchemaDefinition
        from octave_mcp.core.validator import Validator

        content = """---
description: A test skill
---
===SKILL===
META:
  TYPE::SKILL
  VERSION::"1.0"
===END==="""
        doc = parse(content)

        schema_def = SchemaDefinition(
            name="SKILL",
            frontmatter={
                "name": FrontmatterFieldDef(name="name", required=True, field_type="STRING"),
                "description": FrontmatterFieldDef(name="description", required=True, field_type="STRING"),
                "allowed-tools": FrontmatterFieldDef(name="allowed-tools", required=True, field_type="LIST"),
            },
        )

        validator = Validator()
        errors = validator.validate(doc, section_schemas={"SKILL": schema_def})
        fm_errors = [e for e in errors if e.code.startswith("E_FM")]
        assert len(fm_errors) == 2  # name and allowed-tools missing
        error_fields = {e.field_path for e in fm_errors}
        assert "frontmatter.name" in error_fields
        assert "frontmatter.allowed-tools" in error_fields
