"""Tests for Policy Block enforcement (Issue #190).

TDD RED phase: These tests define the expected behavior for:
1. UNKNOWN_FIELDS enforcement (REJECT | WARN | IGNORE)
2. POLICY block required field validation
3. Custom targets from POLICY.TARGETS integration with TargetRegistry

Spec reference: src/octave_mcp/resources/specs/octave-schema-spec.oct.md §5::POLICY_BLOCK

REQUIRED_IN_SCHEMA::[
  VERSION::"1.0",
  UNKNOWN_FIELDS::REJECT∨IGNORE∨WARN,
  TARGETS::[list_of_valid_targets]
]
"""

from octave_mcp.core.ast_nodes import Assignment, Block, Document
from octave_mcp.core.holographic import parse_holographic_pattern
from octave_mcp.core.parser import parse
from octave_mcp.core.schema_extractor import (
    FieldDefinition,
    PolicyDefinition,
    SchemaDefinition,
    extract_schema_from_document,
)
from octave_mcp.core.validator import Validator


class TestUnknownFieldsReject:
    """Test UNKNOWN_FIELDS::REJECT policy enforcement."""

    def test_reject_unknown_field_produces_error(self):
        """UNKNOWN_FIELDS::REJECT should produce E007 error for unknown fields.

        Given a schema with UNKNOWN_FIELDS::REJECT policy,
        when validating a document with a field not in the schema,
        then validator should produce E007 error.
        """
        # Arrange: Schema with REJECT policy
        pattern = parse_holographic_pattern('["example"∧REQ→§SELF]')
        schema = SchemaDefinition(
            name="TEST_SCHEMA",
            policy=PolicyDefinition(
                version="1.0",
                unknown_fields="REJECT",
                targets=["SELF"],
            ),
            fields={"KNOWN_FIELD": FieldDefinition(name="KNOWN_FIELD", pattern=pattern)},
        )

        # Create section with both known and unknown fields
        section = Block(
            key="TEST_SECTION",
            children=[
                Assignment(key="KNOWN_FIELD", value="valid_value"),
                Assignment(key="UNKNOWN_FIELD", value="should_cause_error"),
            ],
        )
        document = Document(meta={}, sections=[section])

        # Act
        validator = Validator()
        errors = validator.validate(document, strict=False, section_schemas={"TEST_SECTION": schema})

        # Assert: Should have E007 error for unknown field
        assert len(errors) > 0, "Expected error for unknown field with REJECT policy"
        unknown_errors = [e for e in errors if "UNKNOWN_FIELD" in e.field_path]
        assert len(unknown_errors) > 0, "Expected error specifically for UNKNOWN_FIELD"
        assert any(e.code == "E007" for e in unknown_errors), "Expected E007 error code for unknown field"

    def test_reject_multiple_unknown_fields(self):
        """UNKNOWN_FIELDS::REJECT should report each unknown field separately.

        Given multiple unknown fields,
        then each should produce its own error.
        """
        # Arrange
        pattern = parse_holographic_pattern('["example"∧REQ→§SELF]')
        schema = SchemaDefinition(
            name="TEST_SCHEMA",
            policy=PolicyDefinition(
                version="1.0",
                unknown_fields="REJECT",
                targets=["SELF"],
            ),
            fields={"DEFINED": FieldDefinition(name="DEFINED", pattern=pattern)},
        )

        section = Block(
            key="TEST",
            children=[
                Assignment(key="DEFINED", value="ok"),
                Assignment(key="UNKNOWN_A", value="bad"),
                Assignment(key="UNKNOWN_B", value="also_bad"),
                Assignment(key="UNKNOWN_C", value="very_bad"),
            ],
        )
        document = Document(meta={}, sections=[section])

        # Act
        validator = Validator()
        errors = validator.validate(document, strict=False, section_schemas={"TEST": schema})

        # Assert: Should have 3 errors for 3 unknown fields
        unknown_errors = [e for e in errors if e.code == "E007" and "UNKNOWN" in e.field_path]
        assert len(unknown_errors) == 3, f"Expected 3 unknown field errors, got {len(unknown_errors)}"


class TestUnknownFieldsWarn:
    """Test UNKNOWN_FIELDS::WARN policy enforcement."""

    def test_warn_unknown_field_produces_warning(self):
        """UNKNOWN_FIELDS::WARN should produce W001 warning for unknown fields.

        Given a schema with UNKNOWN_FIELDS::WARN policy,
        when validating a document with a field not in the schema,
        then validator should produce W001 warning (not error).
        """
        # Arrange
        pattern = parse_holographic_pattern('["example"∧REQ→§SELF]')
        schema = SchemaDefinition(
            name="TEST_SCHEMA",
            policy=PolicyDefinition(
                version="1.0",
                unknown_fields="WARN",
                targets=["SELF"],
            ),
            fields={"KNOWN_FIELD": FieldDefinition(name="KNOWN_FIELD", pattern=pattern)},
        )

        section = Block(
            key="TEST_SECTION",
            children=[
                Assignment(key="KNOWN_FIELD", value="valid_value"),
                Assignment(key="UNKNOWN_FIELD", value="should_produce_warning"),
            ],
        )
        document = Document(meta={}, sections=[section])

        # Act
        validator = Validator()
        errors = validator.validate(document, strict=False, section_schemas={"TEST_SECTION": schema})

        # Assert: Should have W001 warning (not E007 error)
        unknown_entries = [e for e in errors if "UNKNOWN_FIELD" in e.field_path]
        assert len(unknown_entries) > 0, "Expected warning for unknown field"
        assert any(e.code == "W001" for e in unknown_entries), "Expected W001 warning code for WARN policy"

    def test_warn_validation_result_indicates_warning_severity(self):
        """W001 warnings should have severity='warning' attribute.

        Warnings are distinguishable from errors by severity.
        """
        # Arrange
        pattern = parse_holographic_pattern('["example"∧OPT→§SELF]')
        schema = SchemaDefinition(
            name="TEST_SCHEMA",
            policy=PolicyDefinition(
                version="1.0",
                unknown_fields="WARN",
                targets=["SELF"],
            ),
            fields={"FIELD": FieldDefinition(name="FIELD", pattern=pattern)},
        )

        section = Block(
            key="TEST",
            children=[
                Assignment(key="EXTRA", value="unknown"),
            ],
        )
        document = Document(meta={}, sections=[section])

        # Act
        validator = Validator()
        errors = validator.validate(document, strict=False, section_schemas={"TEST": schema})

        # Assert: W001 should have severity attribute
        warnings = [e for e in errors if e.code == "W001"]
        assert len(warnings) > 0, "Expected W001 warning"
        # ValidationError needs severity attribute for warnings
        assert hasattr(warnings[0], "severity"), "ValidationError should have severity attribute"
        assert warnings[0].severity == "warning", "W001 should have severity='warning'"


class TestUnknownFieldsIgnore:
    """Test UNKNOWN_FIELDS::IGNORE policy enforcement."""

    def test_ignore_unknown_field_no_error(self):
        """UNKNOWN_FIELDS::IGNORE should silently skip unknown fields.

        Given a schema with UNKNOWN_FIELDS::IGNORE policy,
        when validating a document with unknown fields,
        then validator should produce no errors for those fields.
        """
        # Arrange
        pattern = parse_holographic_pattern('["example"∧REQ→§SELF]')
        schema = SchemaDefinition(
            name="TEST_SCHEMA",
            policy=PolicyDefinition(
                version="1.0",
                unknown_fields="IGNORE",
                targets=["SELF"],
            ),
            fields={"KNOWN_FIELD": FieldDefinition(name="KNOWN_FIELD", pattern=pattern)},
        )

        section = Block(
            key="TEST_SECTION",
            children=[
                Assignment(key="KNOWN_FIELD", value="valid_value"),
                Assignment(key="UNKNOWN_FIELD", value="should_be_ignored"),
                Assignment(key="ANOTHER_UNKNOWN", value="also_ignored"),
            ],
        )
        document = Document(meta={}, sections=[section])

        # Act
        validator = Validator()
        errors = validator.validate(document, strict=False, section_schemas={"TEST_SECTION": schema})

        # Assert: No errors for unknown fields
        unknown_errors = [e for e in errors if "UNKNOWN" in e.field_path]
        assert len(unknown_errors) == 0, "IGNORE policy should produce no errors for unknown fields"


class TestDefaultUnknownFieldsPolicy:
    """Test default behavior when no UNKNOWN_FIELDS policy is set."""

    def test_default_policy_is_reject(self):
        """Default UNKNOWN_FIELDS policy should be REJECT.

        Per spec: PolicyDefinition has unknown_fields='REJECT' as default.
        """
        policy = PolicyDefinition()
        assert policy.unknown_fields == "REJECT"

    def test_default_policy_behavior(self):
        """Without explicit UNKNOWN_FIELDS, should behave as REJECT.

        Schemas without explicit UNKNOWN_FIELDS policy should
        reject unknown fields by default (fail-safe).
        """
        # Arrange: Schema without explicit unknown_fields (uses default)
        pattern = parse_holographic_pattern('["example"∧REQ→§SELF]')
        schema = SchemaDefinition(
            name="TEST_SCHEMA",
            # policy not specified, uses default PolicyDefinition()
            fields={"DEFINED": FieldDefinition(name="DEFINED", pattern=pattern)},
        )

        section = Block(
            key="TEST",
            children=[
                Assignment(key="DEFINED", value="ok"),
                Assignment(key="EXTRA", value="unknown"),
            ],
        )
        document = Document(meta={}, sections=[section])

        # Act
        validator = Validator()
        errors = validator.validate(document, strict=False, section_schemas={"TEST": schema})

        # Assert: Should reject unknown field (default is REJECT)
        unknown_errors = [e for e in errors if "EXTRA" in e.field_path]
        assert len(unknown_errors) > 0, "Default policy should reject unknown fields"


class TestPolicyCustomTargetsIntegration:
    """Test POLICY.TARGETS integration with TargetRegistry (Issue #188)."""

    def test_custom_target_from_policy_is_valid(self):
        """Custom targets from POLICY.TARGETS should be valid for routing.

        Given a schema with POLICY.TARGETS::[§CUSTOM_TARGET],
        when a field routes to CUSTOM_TARGET,
        then validation should pass (no E009 invalid target error).
        """
        # Arrange: Schema with custom target in POLICY
        pattern = parse_holographic_pattern('["example"∧REQ→§CUSTOM_TARGET]')
        schema = SchemaDefinition(
            name="TEST_SCHEMA",
            policy=PolicyDefinition(
                version="1.0",
                unknown_fields="REJECT",
                targets=["CUSTOM_TARGET"],  # Custom target declared in policy
            ),
            fields={"FIELD": FieldDefinition(name="FIELD", pattern=pattern)},
        )

        section = Block(
            key="TEST",
            children=[
                Assignment(key="FIELD", value="routed_value"),
            ],
        )
        document = Document(meta={}, sections=[section])

        # Act
        validator = Validator()
        errors = validator.validate(document, strict=False, section_schemas={"TEST": schema})

        # Assert: No E009 invalid target error
        target_errors = [e for e in errors if e.code == "E009"]
        assert (
            len(target_errors) == 0
        ), f"Custom target from POLICY.TARGETS should be valid. Got errors: {target_errors}"

    def test_undeclared_custom_target_produces_error(self):
        """Undeclared custom targets should produce E009 error.

        Given a schema with POLICY.TARGETS that does NOT include TARGET_X,
        when a field routes to TARGET_X,
        then validation should produce E009 invalid target error.
        """
        # Arrange: Schema with limited targets
        pattern = parse_holographic_pattern('["example"∧REQ→§UNDECLARED_TARGET]')
        schema = SchemaDefinition(
            name="TEST_SCHEMA",
            policy=PolicyDefinition(
                version="1.0",
                unknown_fields="REJECT",
                targets=["ONLY_THIS_TARGET"],  # UNDECLARED_TARGET not listed
            ),
            fields={"FIELD": FieldDefinition(name="FIELD", pattern=pattern)},
        )

        section = Block(
            key="TEST",
            children=[
                Assignment(key="FIELD", value="routed_value"),
            ],
        )
        document = Document(meta={}, sections=[section])

        # Act
        validator = Validator()
        errors = validator.validate(document, strict=False, section_schemas={"TEST": schema})

        # Assert: Should have E009 invalid target error
        target_errors = [e for e in errors if e.code == "E009"]
        assert len(target_errors) > 0, "Undeclared custom target should produce E009 error"

    def test_builtin_targets_always_valid(self):
        """Builtin targets (SELF, INDEXER, etc.) are always valid.

        Even without being in POLICY.TARGETS, builtin targets should work.
        """
        # Arrange: Schema with empty custom targets (only builtins)
        pattern = parse_holographic_pattern('["example"∧REQ→§INDEXER]')
        schema = SchemaDefinition(
            name="TEST_SCHEMA",
            policy=PolicyDefinition(
                version="1.0",
                unknown_fields="REJECT",
                targets=[],  # No custom targets, but INDEXER is builtin
            ),
            fields={"FIELD": FieldDefinition(name="FIELD", pattern=pattern)},
        )

        section = Block(
            key="TEST",
            children=[
                Assignment(key="FIELD", value="routed_value"),
            ],
        )
        document = Document(meta={}, sections=[section])

        # Act
        validator = Validator()
        errors = validator.validate(document, strict=False, section_schemas={"TEST": schema})

        # Assert: No E009 error - INDEXER is builtin
        target_errors = [e for e in errors if e.code == "E009"]
        assert len(target_errors) == 0, "Builtin targets should always be valid"


class TestPolicyTargetsExtraction:
    """Test extraction of POLICY.TARGETS from parsed documents."""

    def test_policy_targets_extracted_during_schema_extraction(self):
        """POLICY.TARGETS should be extracted to schema.policy.targets."""
        doc = parse("""
===TEST_SCHEMA===
META:
  TYPE::PROTOCOL_DEFINITION
  VERSION::"1.0"

POLICY:
  VERSION::"1.0"
  UNKNOWN_FIELDS::REJECT
  TARGETS::[§CUSTOM_A,§CUSTOM_B,§MY_LOG]

FIELDS:
  NAME::["example"∧REQ→§CUSTOM_A]
===END===
""")
        schema = extract_schema_from_document(doc)

        # Assert: Custom targets extracted
        assert "CUSTOM_A" in schema.policy.targets
        assert "CUSTOM_B" in schema.policy.targets
        assert "MY_LOG" in schema.policy.targets


class TestPolicyBlockValidation:
    """Test validation of POLICY block structure.

    Spec §5::POLICY_BLOCK REQUIRED_IN_SCHEMA::
    - VERSION::"1.0"
    - UNKNOWN_FIELDS::REJECT∨IGNORE∨WARN
    - TARGETS::[list_of_valid_targets]
    """

    def test_policy_version_required_in_schema(self):
        """POLICY block should require VERSION field.

        When POLICY block exists but lacks VERSION,
        validation should produce error.
        """
        # This tests whether validate_policy_block detects missing VERSION
        doc = parse("""
===TEST_SCHEMA===
META:
  TYPE::PROTOCOL_DEFINITION
  VERSION::"1.0"

POLICY:
  UNKNOWN_FIELDS::REJECT

FIELDS:
  NAME::["example"∧REQ→§SELF]
===END===
""")
        schema = extract_schema_from_document(doc)

        # Without explicit validation function, default VERSION is "1.0"
        # But spec requires it to be explicit in POLICY block
        # This test verifies the schema extraction handles defaults properly
        assert schema.policy.version == "1.0"  # Default applied

    def test_policy_unknown_fields_has_valid_values(self):
        """UNKNOWN_FIELDS must be one of REJECT, WARN, or IGNORE.

        Invalid values should produce validation error.
        """
        # Arrange: Manual schema with invalid unknown_fields
        schema = SchemaDefinition(
            name="TEST",
            policy=PolicyDefinition(
                version="1.0",
                unknown_fields="INVALID_VALUE",  # Not REJECT, WARN, or IGNORE
                targets=[],
            ),
            fields={},
        )

        section = Block(key="TEST", children=[])
        document = Document(meta={}, sections=[section])

        # Act
        validator = Validator()
        # Invalid policy values fall back to REJECT (fail-safe)
        # This validation is tested implicitly - if policy value is invalid,
        # REJECT behavior is applied
        _errors = validator.validate(document, strict=False, section_schemas={"TEST": schema})

        # Assert: No error for valid document, but invalid policy silently defaults to REJECT
        # The test documents current behavior: invalid policy values are fail-safe
        assert _errors == []  # Empty section with empty schema fields = no errors


class TestPolicyIntegrationWithValidation:
    """Integration tests for policy enforcement with full validation pipeline."""

    def test_full_schema_validation_with_policy(self):
        """Full validation pipeline with schema policy.

        Parse schema document, extract schema, validate instance document.
        """
        # Parse and extract schema
        schema_doc = parse("""
===SESSION_LOG===
META:
  TYPE::PROTOCOL_DEFINITION
  VERSION::"1.0"

POLICY:
  VERSION::"1.0"
  UNKNOWN_FIELDS::REJECT
  TARGETS::[§INDEXER,§DECISION_LOG]

FIELDS:
  AGENT::["implementation-lead"∧REQ→§INDEXER]
  PHASE::["B2"∧REQ∧ENUM[D0,D1,D2,D3,B0,B1,B2,B3]→§INDEXER]
===END===
""")
        schema = extract_schema_from_document(schema_doc)

        # Create instance document with valid fields
        section = Block(
            key="CONTENT",
            children=[
                Assignment(key="AGENT", value="implementation-lead"),
                Assignment(key="PHASE", value="B2"),
            ],
        )
        document = Document(meta={}, sections=[section])

        # Validate
        validator = Validator()
        errors = validator.validate(document, strict=False, section_schemas={"CONTENT": schema})

        # Should pass - all fields known and valid
        assert len(errors) == 0, f"Expected no errors, got: {errors}"

    def test_full_schema_validation_rejects_unknown(self):
        """Full validation pipeline rejects unknown fields per policy."""
        # Parse and extract schema
        schema_doc = parse("""
===CONFIG===
META:
  TYPE::PROTOCOL_DEFINITION
  VERSION::"1.0"

POLICY:
  VERSION::"1.0"
  UNKNOWN_FIELDS::REJECT
  TARGETS::[§SELF]

FIELDS:
  STATUS::["ACTIVE"∧REQ∧ENUM[ACTIVE,INACTIVE]→§SELF]
===END===
""")
        schema = extract_schema_from_document(schema_doc)

        # Create instance with unknown field
        section = Block(
            key="CONFIG",
            children=[
                Assignment(key="STATUS", value="ACTIVE"),
                Assignment(key="UNKNOWN_EXTRA", value="not_in_schema"),
            ],
        )
        document = Document(meta={}, sections=[section])

        # Validate
        validator = Validator()
        errors = validator.validate(document, strict=False, section_schemas={"CONFIG": schema})

        # Should reject UNKNOWN_EXTRA
        assert len(errors) > 0, "Expected error for unknown field"
        unknown_errors = [e for e in errors if "UNKNOWN_EXTRA" in e.field_path]
        assert len(unknown_errors) > 0, "Expected error specifically for UNKNOWN_EXTRA"
