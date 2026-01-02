"""Tests for _validate_section with SchemaDefinition (Issue #102).

TDD RED phase: These tests define the expected behavior for wiring
_validate_section to ConstraintChain evaluation via SchemaDefinition.

Design decisions from debate-hall synthesis:
1. Add optional section_schema: SchemaDefinition | None to _validate_section
2. Schema-less sections: skip content validation, no errors
3. Wire ConstraintChain.evaluate() for fields with holographic patterns
4. DO NOT validate targets (defer to #103)

PHASE 2 (Bug fix): Wire section_schemas through Validator.validate()
- Add section_schemas: dict[str, SchemaDefinition] | None to validate()
- Look up schema for each section by section.key
- Pass to _validate_section
"""

from octave_mcp.core.ast_nodes import Assignment, Block, Document
from octave_mcp.core.holographic import parse_holographic_pattern
from octave_mcp.core.schema_extractor import FieldDefinition, SchemaDefinition
from octave_mcp.core.validator import Validator


class TestValidateSectionWithSchema:
    """Test _validate_section with SchemaDefinition."""

    def test_validate_section_with_req_constraint_missing_field(self):
        """Should return E003 when required field is missing.

        Given a section with a SchemaDefinition that has a REQ constraint,
        when a required field is missing from the section,
        then _validate_section should add an E003 error.
        """
        # Arrange: Create a schema with REQ constraint
        pattern = parse_holographic_pattern('["example"∧REQ→§SELF]')
        schema = SchemaDefinition(
            name="TEST_SCHEMA",
            fields={
                "REQUIRED_FIELD": FieldDefinition(
                    name="REQUIRED_FIELD",
                    pattern=pattern,
                )
            },
        )

        # Create a Block section with NO children (missing required field)
        section = Block(key="TEST_SECTION", children=[])

        # Act
        validator = Validator()
        validator._validate_section(section, strict=False, section_schema=schema)

        # Assert: Should have E003 error for missing required field
        assert len(validator.errors) > 0
        assert any(e.code == "E003" for e in validator.errors)
        assert any("REQUIRED_FIELD" in e.message for e in validator.errors)

    def test_validate_section_with_enum_constraint_invalid_value(self):
        """Should return error when ENUM constraint is violated.

        Given a section with a SchemaDefinition that has an ENUM constraint,
        when a field value is not in the allowed enum values,
        then _validate_section should add an E005 error.
        """
        # Arrange: Create a schema with ENUM constraint
        pattern = parse_holographic_pattern('["ACTIVE"∧ENUM[ACTIVE,INACTIVE,ARCHIVED]→§SELF]')
        schema = SchemaDefinition(
            name="TEST_SCHEMA",
            fields={
                "STATUS": FieldDefinition(
                    name="STATUS",
                    pattern=pattern,
                )
            },
        )

        # Create a Block section with invalid STATUS value
        section = Block(
            key="TEST_SECTION",
            children=[
                Assignment(key="STATUS", value="INVALID_STATUS"),
            ],
        )

        # Act
        validator = Validator()
        validator._validate_section(section, strict=False, section_schema=schema)

        # Assert: Should have error for invalid enum value
        assert len(validator.errors) > 0
        # ENUM validation error code is E005
        assert any(e.code == "E005" for e in validator.errors)

    def test_validate_section_with_schema_none_no_errors(self):
        """Should skip content validation when section_schema is None.

        Given a section with no SchemaDefinition (section_schema=None),
        then _validate_section should not produce any content validation errors.
        This is the I5 schema sovereignty: schema-less sections are UNVALIDATED.
        """
        # Arrange: Create a Block section with arbitrary content
        section = Block(
            key="ARBITRARY_SECTION",
            children=[
                Assignment(key="ANY_FIELD", value="any_value"),
                Assignment(key="ANOTHER", value=12345),
            ],
        )

        # Act: Validate without schema
        validator = Validator()
        validator._validate_section(section, strict=False, section_schema=None)

        # Assert: No errors (structural pass-through)
        assert len(validator.errors) == 0

    def test_validate_section_with_valid_values_no_errors(self):
        """Should produce no errors when all field values satisfy constraints.

        Given a section with a SchemaDefinition containing constraints,
        when all field values satisfy their constraints,
        then _validate_section should produce no errors.
        """
        # Arrange: Create a schema with ENUM constraint
        pattern = parse_holographic_pattern('["ACTIVE"∧ENUM[ACTIVE,INACTIVE,ARCHIVED]→§SELF]')
        schema = SchemaDefinition(
            name="TEST_SCHEMA",
            fields={
                "STATUS": FieldDefinition(
                    name="STATUS",
                    pattern=pattern,
                )
            },
        )

        # Create a Block section with valid STATUS value
        section = Block(
            key="TEST_SECTION",
            children=[
                Assignment(key="STATUS", value="ACTIVE"),
            ],
        )

        # Act
        validator = Validator()
        validator._validate_section(section, strict=False, section_schema=schema)

        # Assert: No errors
        assert len(validator.errors) == 0

    def test_validate_section_with_type_constraint(self):
        """Should validate TYPE constraint on field values.

        Given a section with a SchemaDefinition containing TYPE[STRING] constraint,
        when a field has an integer value,
        then _validate_section should add a type error.
        """
        # Arrange: Create a schema with TYPE[STRING] constraint
        pattern = parse_holographic_pattern('["example"∧TYPE[STRING]→§SELF]')
        schema = SchemaDefinition(
            name="TEST_SCHEMA",
            fields={
                "NAME": FieldDefinition(
                    name="NAME",
                    pattern=pattern,
                )
            },
        )

        # Create a Block section with integer value (not string)
        section = Block(
            key="TEST_SECTION",
            children=[
                Assignment(key="NAME", value=12345),  # Should be string
            ],
        )

        # Act
        validator = Validator()
        validator._validate_section(section, strict=False, section_schema=schema)

        # Assert: Should have type error
        assert len(validator.errors) > 0
        assert any(e.code == "E007" for e in validator.errors)  # Type error code


class TestValidateSectionErrorConversion:
    """Test that constraint ValidationErrors are converted to validator ValidationErrors."""

    def test_constraint_error_includes_field_path(self):
        """Constraint errors should include proper field path.

        The field_path should be in format "SECTION_NAME.FIELD_NAME".
        """
        # Arrange: Create a schema with ENUM constraint
        pattern = parse_holographic_pattern('["ACTIVE"∧ENUM[ACTIVE,INACTIVE]→§SELF]')
        schema = SchemaDefinition(
            name="TEST_SCHEMA",
            fields={
                "STATUS": FieldDefinition(
                    name="STATUS",
                    pattern=pattern,
                )
            },
        )

        # Create a Block section with invalid value
        section = Block(
            key="CONFIG",
            children=[
                Assignment(key="STATUS", value="INVALID"),
            ],
        )

        # Act
        validator = Validator()
        validator._validate_section(section, strict=False, section_schema=schema)

        # Assert: Error field_path should include section and field
        assert len(validator.errors) > 0
        assert any("CONFIG.STATUS" in e.field_path for e in validator.errors)


class TestValidateSectionWithAssignment:
    """Test _validate_section with Assignment nodes (not Block)."""

    def test_validate_section_handles_assignment_node(self):
        """Should handle Assignment nodes passed as sections.

        While sections are typically Blocks, Assignment nodes should not cause errors.
        Schema validation only applies to Block children.
        """
        # Arrange: Create an Assignment (not a Block)
        section = Assignment(key="SIMPLE_KEY", value="simple_value")

        pattern = parse_holographic_pattern('["example"∧REQ→§SELF]')
        schema = SchemaDefinition(
            name="TEST_SCHEMA",
            fields={
                "SOME_FIELD": FieldDefinition(
                    name="SOME_FIELD",
                    pattern=pattern,
                )
            },
        )

        # Act: Should not crash
        validator = Validator()
        validator._validate_section(section, strict=False, section_schema=schema)

        # Assert: No errors for Assignment nodes (no children to validate)
        # An Assignment has no children, so field constraints don't apply
        assert len(validator.errors) == 0


class TestValidatePublicAPIWithSectionSchemas:
    """Test Validator.validate() with section_schemas parameter (Bug fix #102).

    BUG: Validator.validate() never passes section_schema to _validate_section.
    FIX: Add section_schemas parameter to validate() and wire through.
    """

    def test_validate_with_section_schemas_detects_invalid_enum(self):
        """PUBLIC API: validate() with section_schemas should detect invalid ENUM values.

        This is the core bug: _validate_section works but validate() never calls it
        with a schema. This test FAILS until the fix is applied.
        """
        # Arrange: Create a document with a section containing invalid enum value
        section = Block(
            key="CONFIG",
            children=[
                Assignment(key="STATUS", value="INVALID_VALUE"),
            ],
        )
        document = Document(meta={}, sections=[section])

        # Create section schema with ENUM constraint
        pattern = parse_holographic_pattern('["ACTIVE"∧ENUM[ACTIVE,INACTIVE,ARCHIVED]→§SELF]')
        section_schema = SchemaDefinition(
            name="CONFIG",
            fields={
                "STATUS": FieldDefinition(
                    name="STATUS",
                    pattern=pattern,
                )
            },
        )
        section_schemas = {"CONFIG": section_schema}

        # Act: Call PUBLIC validate() with section_schemas
        validator = Validator()
        errors = validator.validate(document, strict=False, section_schemas=section_schemas)

        # Assert: Should detect the invalid enum value through public API
        assert len(errors) > 0, "Expected validation error but got none (bug: section_schemas not wired)"
        assert any(e.code == "E005" for e in errors), "Expected E005 enum error"
        assert any("CONFIG.STATUS" in e.field_path for e in errors)

    def test_validate_with_section_schemas_detects_missing_required(self):
        """PUBLIC API: validate() with section_schemas should detect missing REQ fields.

        Given a section_schemas dict with a REQ constraint,
        when a required field is missing,
        then validate() should return E003 error.
        """
        # Arrange: Create document with empty section (missing required field)
        section = Block(key="SETTINGS", children=[])
        document = Document(meta={}, sections=[section])

        # Create section schema with REQ constraint
        pattern = parse_holographic_pattern('["value"∧REQ→§SELF]')
        section_schema = SchemaDefinition(
            name="SETTINGS",
            fields={
                "REQUIRED_FIELD": FieldDefinition(
                    name="REQUIRED_FIELD",
                    pattern=pattern,
                )
            },
        )
        section_schemas = {"SETTINGS": section_schema}

        # Act: Call PUBLIC validate()
        validator = Validator()
        errors = validator.validate(document, strict=False, section_schemas=section_schemas)

        # Assert: Should detect missing required field
        assert len(errors) > 0, "Expected E003 error for missing required field"
        assert any(e.code == "E003" for e in errors)
        assert any("REQUIRED_FIELD" in e.message for e in errors)

    def test_validate_with_section_schemas_none_preserves_behavior(self):
        """PUBLIC API: validate() without section_schemas preserves existing behavior.

        When section_schemas is None (default), validation should NOT produce
        section content errors - this is the I5 schema sovereignty behavior.
        """
        # Arrange: Create document with arbitrary section content
        section = Block(
            key="ANYTHING",
            children=[
                Assignment(key="RANDOM_FIELD", value="random_value"),
            ],
        )
        document = Document(meta={}, sections=[section])

        # Act: Call validate() without section_schemas (default behavior)
        validator = Validator()
        errors = validator.validate(document, strict=False)

        # Assert: No errors (backward compatible, schema-less sections unvalidated)
        assert len(errors) == 0

    def test_validate_with_section_schemas_unmatched_section_no_error(self):
        """Sections without matching schema entry should pass without validation.

        If a section's key is not in section_schemas, that section should
        be skipped (not cause an error).
        """
        # Arrange: Create document with section not in schemas dict
        section = Block(
            key="UNLISTED_SECTION",
            children=[
                Assignment(key="SOME_FIELD", value="some_value"),
            ],
        )
        document = Document(meta={}, sections=[section])

        # Create schemas for a DIFFERENT section
        pattern = parse_holographic_pattern('["value"∧REQ→§SELF]')
        section_schema = SchemaDefinition(
            name="OTHER_SECTION",
            fields={
                "OTHER_FIELD": FieldDefinition(
                    name="OTHER_FIELD",
                    pattern=pattern,
                )
            },
        )
        section_schemas = {"OTHER_SECTION": section_schema}

        # Act: Call validate() - section "UNLISTED_SECTION" has no schema
        validator = Validator()
        errors = validator.validate(document, strict=False, section_schemas=section_schemas)

        # Assert: No errors (unlisted sections skip validation)
        assert len(errors) == 0

    def test_validate_with_valid_section_values_no_errors(self):
        """PUBLIC API: Valid section values produce no errors.

        When all section values satisfy their constraints, validate() should
        return an empty error list.
        """
        # Arrange: Create document with valid section content
        section = Block(
            key="CONFIG",
            children=[
                Assignment(key="STATUS", value="ACTIVE"),  # Valid enum value
            ],
        )
        document = Document(meta={}, sections=[section])

        # Create section schema with ENUM constraint
        pattern = parse_holographic_pattern('["ACTIVE"∧ENUM[ACTIVE,INACTIVE,ARCHIVED]→§SELF]')
        section_schema = SchemaDefinition(
            name="CONFIG",
            fields={
                "STATUS": FieldDefinition(
                    name="STATUS",
                    pattern=pattern,
                )
            },
        )
        section_schemas = {"CONFIG": section_schema}

        # Act
        validator = Validator()
        errors = validator.validate(document, strict=False, section_schemas=section_schemas)

        # Assert: No errors for valid values
        assert len(errors) == 0
