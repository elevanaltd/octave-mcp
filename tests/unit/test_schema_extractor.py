"""Tests for schema extraction from OCTAVE documents (Issue #93).

Tests extraction of schema definitions (POLICY, FIELDS blocks) from parsed
OCTAVE documents using holographic pattern parsing.

TDD RED phase: Write failing tests before implementation.
"""

from octave_mcp.core.parser import parse


class TestSchemaExtractorImport:
    """Test schema extractor imports."""

    def test_extract_schema_from_document_import(self):
        """extract_schema_from_document should be importable."""
        from octave_mcp.core.schema_extractor import extract_schema_from_document

        assert extract_schema_from_document is not None

    def test_schema_definition_import(self):
        """SchemaDefinition should be importable."""
        from octave_mcp.core.schema_extractor import SchemaDefinition

        assert SchemaDefinition is not None

    def test_field_definition_import(self):
        """FieldDefinition should be importable."""
        from octave_mcp.core.schema_extractor import FieldDefinition

        assert FieldDefinition is not None


class TestSchemaExtractorBasic:
    """Test basic schema extraction functionality."""

    def test_extract_empty_document_returns_empty_schema(self):
        """Extracting from empty document returns empty schema."""
        from octave_mcp.core.schema_extractor import extract_schema_from_document

        doc = parse(
            """
===TEST===
META:
  TYPE::PROTOCOL_DEFINITION
===END===
"""
        )
        schema = extract_schema_from_document(doc)
        assert schema is not None
        assert len(schema.fields) == 0

    def test_extract_schema_with_single_field(self):
        """Should extract single field definition."""
        from octave_mcp.core.schema_extractor import extract_schema_from_document

        doc = parse(
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
        schema = extract_schema_from_document(doc)
        assert len(schema.fields) == 1
        assert "NAME" in schema.fields
        assert schema.fields["NAME"].pattern.example == "example"

    def test_extract_schema_with_multiple_fields(self):
        """Should extract multiple field definitions."""
        from octave_mcp.core.schema_extractor import extract_schema_from_document

        doc = parse(
            """
===SESSION_LOG===
META:
  TYPE::PROTOCOL_DEFINITION
  VERSION::"1.0"

FIELDS:
  AGENT::["implementation-lead"∧REQ→§INDEXER]
  PHASE::["B2"∧REQ∧ENUM[D0,D1,D2,D3,B0,B1,B2,B3]→§INDEXER]
  STATUS::["ACTIVE"∧REQ∧ENUM[ACTIVE,DRAFT]→§SELF]
===END===
"""
        )
        schema = extract_schema_from_document(doc)
        assert len(schema.fields) == 3
        assert "AGENT" in schema.fields
        assert "PHASE" in schema.fields
        assert "STATUS" in schema.fields

    def test_extract_field_preserves_constraints(self):
        """Extracted field should preserve constraint chain."""
        from octave_mcp.core.schema_extractor import extract_schema_from_document

        # Using ENUM constraint which the lexer understands (brackets not parens)
        doc = parse(
            """
===TEST===
META:
  TYPE::PROTOCOL_DEFINITION

FIELDS:
  STATUS::["ACTIVE"∧REQ∧ENUM[ACTIVE,INACTIVE]→§SELF]
===END===
"""
        )
        schema = extract_schema_from_document(doc)
        field = schema.fields["STATUS"]
        assert len(field.pattern.constraints.constraints) == 2

    def test_extract_field_preserves_target(self):
        """Extracted field should preserve target."""
        from octave_mcp.core.schema_extractor import extract_schema_from_document

        doc = parse(
            """
===TEST===
META:
  TYPE::PROTOCOL_DEFINITION

FIELDS:
  ID::["abc123"∧REQ→§INDEXER]
===END===
"""
        )
        schema = extract_schema_from_document(doc)
        field = schema.fields["ID"]
        assert field.pattern.target == "INDEXER"


class TestSchemaExtractorPolicy:
    """Test POLICY block extraction."""

    def test_extract_policy_version(self):
        """Should extract POLICY VERSION."""
        from octave_mcp.core.schema_extractor import extract_schema_from_document

        doc = parse(
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
        schema = extract_schema_from_document(doc)
        assert schema.policy.version == "1.0"

    def test_extract_policy_unknown_fields(self):
        """Should extract POLICY UNKNOWN_FIELDS setting."""
        from octave_mcp.core.schema_extractor import extract_schema_from_document

        doc = parse(
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
        schema = extract_schema_from_document(doc)
        assert schema.policy.unknown_fields == "REJECT"

    def test_extract_policy_targets(self):
        """Should extract POLICY TARGETS list."""
        from octave_mcp.core.schema_extractor import extract_schema_from_document

        doc = parse(
            """
===TEST===
META:
  TYPE::PROTOCOL_DEFINITION

POLICY:
  VERSION::"1.0"
  UNKNOWN_FIELDS::REJECT
  TARGETS::[§INDEXER,§DECISION_LOG]

FIELDS:
  NAME::["test"∧REQ→§INDEXER]
===END===
"""
        )
        schema = extract_schema_from_document(doc)
        assert "INDEXER" in schema.policy.targets
        assert "DECISION_LOG" in schema.policy.targets


class TestSchemaExtractorErrors:
    """Test schema extraction error handling."""

    def test_extract_handles_invalid_holographic_pattern(self):
        """Should handle fields with invalid holographic patterns gracefully."""
        from octave_mcp.core.schema_extractor import extract_schema_from_document

        doc = parse(
            """
===TEST===
META:
  TYPE::PROTOCOL_DEFINITION

FIELDS:
  INVALID::not_a_holographic_pattern
===END===
"""
        )
        schema = extract_schema_from_document(doc)
        # Should either skip invalid fields or raise a clear error
        # For robustness, we prefer skipping with a warning
        assert "INVALID" not in schema.fields or schema.fields["INVALID"].pattern is None

    def test_extract_no_fields_block(self):
        """Should return empty fields when no FIELDS block exists."""
        from octave_mcp.core.schema_extractor import extract_schema_from_document

        doc = parse(
            """
===TEST===
META:
  TYPE::PROTOCOL_DEFINITION

POLICY:
  VERSION::"1.0"
===END===
"""
        )
        schema = extract_schema_from_document(doc)
        assert len(schema.fields) == 0


class TestSchemaDefinitionStructure:
    """Test SchemaDefinition dataclass structure."""

    def test_schema_definition_has_name(self):
        """SchemaDefinition should have name attribute."""
        from octave_mcp.core.schema_extractor import extract_schema_from_document

        doc = parse(
            """
===MY_SCHEMA===
META:
  TYPE::PROTOCOL_DEFINITION

FIELDS:
  NAME::["test"∧REQ→§SELF]
===END===
"""
        )
        schema = extract_schema_from_document(doc)
        assert schema.name == "MY_SCHEMA"

    def test_schema_definition_has_version_from_meta(self):
        """SchemaDefinition should extract version from META block."""
        from octave_mcp.core.schema_extractor import extract_schema_from_document

        doc = parse(
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
        schema = extract_schema_from_document(doc)
        assert schema.version == "2.5.0"

    def test_schema_definition_has_fields_dict(self):
        """SchemaDefinition.fields should be a dict."""
        from octave_mcp.core.schema_extractor import extract_schema_from_document

        doc = parse(
            """
===TEST===
META:
  TYPE::PROTOCOL_DEFINITION

FIELDS:
  A::["a"∧REQ→§SELF]
  B::["b"∧REQ→§SELF]
===END===
"""
        )
        schema = extract_schema_from_document(doc)
        assert isinstance(schema.fields, dict)
        assert len(schema.fields) == 2


class TestFieldDefinitionStructure:
    """Test FieldDefinition dataclass structure."""

    def test_field_definition_has_name(self):
        """FieldDefinition should have name attribute."""
        from octave_mcp.core.schema_extractor import extract_schema_from_document

        doc = parse(
            """
===TEST===
META:
  TYPE::PROTOCOL_DEFINITION

FIELDS:
  AGENT::["impl-lead"∧REQ→§SELF]
===END===
"""
        )
        schema = extract_schema_from_document(doc)
        assert schema.fields["AGENT"].name == "AGENT"

    def test_field_definition_has_pattern(self):
        """FieldDefinition should have HolographicPattern."""
        from octave_mcp.core.holographic import HolographicPattern
        from octave_mcp.core.schema_extractor import extract_schema_from_document

        doc = parse(
            """
===TEST===
META:
  TYPE::PROTOCOL_DEFINITION

FIELDS:
  NAME::["test"∧REQ→§SELF]
===END===
"""
        )
        schema = extract_schema_from_document(doc)
        assert isinstance(schema.fields["NAME"].pattern, HolographicPattern)

    def test_field_definition_exposes_is_required(self):
        """FieldDefinition should expose is_required property."""
        from octave_mcp.core.schema_extractor import extract_schema_from_document

        doc = parse(
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
        schema = extract_schema_from_document(doc)
        assert schema.fields["REQUIRED_FIELD"].is_required is True
        assert schema.fields["OPTIONAL_FIELD"].is_required is False


class TestRealWorldSchemaExtraction:
    """Test extraction of realistic schema documents."""

    def test_extract_session_log_schema(self):
        """Should extract SESSION_LOG schema as defined in ADR-002."""
        from octave_mcp.core.schema_extractor import extract_schema_from_document

        # Note: TYPE(X) constraints use parentheses which the lexer doesn't support
        # Using simpler constraints that the lexer understands
        doc = parse(
            """
===SESSION_LOG===
META:
  TYPE::PROTOCOL_DEFINITION
  VERSION::"1.0"
  STATUS::DRAFT

POLICY:
  VERSION::"1.0"
  UNKNOWN_FIELDS::REJECT
  TARGETS::[§INDEXER,§DECISION_LOG]

FIELDS:
  AGENT::["implementation-lead"∧REQ→§INDEXER]
  PHASE::["B2"∧REQ∧ENUM[D0,D1,D2,D3,B0,B1,B2,B3]→§INDEXER]
  OUTCOMES::["5 tests passing"∧REQ→§SELF]
===END===
"""
        )
        schema = extract_schema_from_document(doc)

        # Verify structure
        assert schema.name == "SESSION_LOG"
        assert schema.version == "1.0"
        assert len(schema.fields) == 3  # Updated: AGENT, PHASE, OUTCOMES

        # Verify AGENT field (only REQ constraint now)
        agent = schema.fields["AGENT"]
        assert agent.pattern.example == "implementation-lead"
        assert agent.pattern.target == "INDEXER"
        assert len(agent.pattern.constraints.constraints) == 1

        # Verify PHASE field
        phase = schema.fields["PHASE"]
        assert phase.pattern.example == "B2"
        assert len(phase.pattern.constraints.constraints) == 2

        # Verify policy
        assert schema.policy.version == "1.0"
        assert schema.policy.unknown_fields == "REJECT"


class TestSchemaExtractorDefaultTarget:
    """Test POLICY.DEFAULT_TARGET extraction for feudal inheritance (Issue #103)."""

    def test_extract_policy_default_target(self):
        """Should extract POLICY DEFAULT_TARGET for block-level inheritance.

        Issue #103: Block-level routing inheritance requires DEFAULT_TARGET
        to be extracted from POLICY block and set on SchemaDefinition.

        POLICY:
          DEFAULT_TARGET::INDEXER

        -> schema.default_target == "INDEXER"
        """
        from octave_mcp.core.schema_extractor import extract_schema_from_document

        doc = parse(
            """
===TEST_SCHEMA===
META:
  TYPE::PROTOCOL_DEFINITION
  VERSION::"1.0"

POLICY:
  VERSION::"1.0"
  UNKNOWN_FIELDS::REJECT
  DEFAULT_TARGET::INDEXER

FIELDS:
  NAME::["example"∧REQ]
===END===
"""
        )
        schema = extract_schema_from_document(doc)

        # DEFAULT_TARGET should be extracted from POLICY and set on schema
        assert schema.default_target == "INDEXER"

    def test_extract_policy_default_target_with_quoted_section_marker(self):
        """Should handle DEFAULT_TARGET with quoted section marker prefix.

        When authors quote the target, section marker is preserved in the string
        and should be stripped: DEFAULT_TARGET::"RISK_LOG" -> "RISK_LOG".

        Note: Unquoted section markers are tokenized separately by the lexer.
        The recommended syntax is DEFAULT_TARGET::RISK_LOG (no marker).
        """
        from octave_mcp.core.schema_extractor import extract_schema_from_document

        # Using quoted string to preserve the section marker in value
        doc = parse(
            """
===TEST_SCHEMA===
META:
  TYPE::PROTOCOL_DEFINITION

POLICY:
  DEFAULT_TARGET::"RISK_LOG"

FIELDS:
  RISK::["auth_bypass"∧REQ]
===END===
"""
        )
        schema = extract_schema_from_document(doc)

        # Value should be extracted (quotes stripped by parser)
        assert schema.default_target == "RISK_LOG"

    def test_default_target_enables_field_inheritance(self):
        """Fields without explicit target should inherit from schema.default_target.

        This is an integration test verifying the full feudal inheritance chain:
        1. POLICY.DEFAULT_TARGET extracted during schema extraction
        2. SchemaDefinition.default_target set
        3. Validator uses default_target for fields without explicit target
        """
        from octave_mcp.core.ast_nodes import Assignment, Block, Document
        from octave_mcp.core.schema_extractor import extract_schema_from_document
        from octave_mcp.core.validator import Validator

        # Parse schema with DEFAULT_TARGET
        schema_doc = parse(
            """
===TEST_SCHEMA===
META:
  TYPE::PROTOCOL_DEFINITION

POLICY:
  DEFAULT_TARGET::INDEXER

FIELDS:
  AGENT::["impl-lead"∧REQ]
===END===
"""
        )
        schema = extract_schema_from_document(schema_doc)

        # Verify schema has default_target set
        assert schema.default_target == "INDEXER"

        # Create document with field that has no explicit target
        section = Block(
            key="TEST_SCHEMA",
            children=[Assignment(key="AGENT", value="implementation-lead")],
        )
        document = Document(meta={}, sections=[section])

        # Validate with schema - should inherit default_target
        validator = Validator()
        validator.validate(document, strict=False, section_schemas={"TEST_SCHEMA": schema})

        # Assert: Routing entry created using inherited target
        assert validator.routing_log.has_routes()
        entry = validator.routing_log.entries[0]
        assert entry.target_name == "INDEXER"
        assert entry.source_path == "TEST_SCHEMA.AGENT"

    def test_no_default_target_when_not_specified(self):
        """Schema without POLICY.DEFAULT_TARGET should have None."""
        from octave_mcp.core.schema_extractor import extract_schema_from_document

        doc = parse(
            """
===TEST_SCHEMA===
META:
  TYPE::PROTOCOL_DEFINITION

POLICY:
  VERSION::"1.0"

FIELDS:
  NAME::["example"∧REQ→§SELF]
===END===
"""
        )
        schema = extract_schema_from_document(doc)

        # No DEFAULT_TARGET specified, should be None
        assert schema.default_target is None
