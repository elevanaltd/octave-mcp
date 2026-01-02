"""Tests for target routing (Issue #103).

TDD RED phase: These tests define the expected behavior for target routing
with audit trail and feudal inheritance.

Design decisions from debate-hall synthesis:
1. RoutingEntry dataclass at src/octave_mcp/core/routing.py
   - Fields: source_path, target_name, value_hash, constraint_passed, timestamp
2. Feudal override: child explicit target completely overrides parent block target
3. routing_log added to validate output alongside repair_log
4. I4 compliant: every route operation logged
"""

import hashlib
from datetime import datetime

from octave_mcp.core.ast_nodes import Assignment, Block, Document
from octave_mcp.core.holographic import parse_holographic_pattern
from octave_mcp.core.routing import RoutingEntry, RoutingLog
from octave_mcp.core.schema_extractor import FieldDefinition, SchemaDefinition
from octave_mcp.core.validator import Validator


class TestRoutingEntryDataclass:
    """Test RoutingEntry dataclass structure and behavior."""

    def test_routing_entry_has_required_fields(self):
        """RoutingEntry should have source_path, target_name, value_hash, constraint_passed, timestamp.

        Given the design decision for audit trail,
        RoutingEntry must capture all information for I4 compliance.
        """
        entry = RoutingEntry(
            source_path="CONFIG.STATUS",
            target_name="SELF",
            value_hash="abc123",
            constraint_passed=True,
            timestamp="2024-01-01T00:00:00Z",
        )

        assert entry.source_path == "CONFIG.STATUS"
        assert entry.target_name == "SELF"
        assert entry.value_hash == "abc123"
        assert entry.constraint_passed is True
        assert entry.timestamp == "2024-01-01T00:00:00Z"

    def test_routing_entry_constraint_passed_false(self):
        """RoutingEntry should record when constraint validation fails.

        Even failed constraint evaluations should be logged for audit trail.
        """
        entry = RoutingEntry(
            source_path="META.TYPE",
            target_name="REGISTRY",
            value_hash="def456",
            constraint_passed=False,
            timestamp="2024-01-01T00:00:00Z",
        )

        assert entry.constraint_passed is False


class TestRoutingLog:
    """Test RoutingLog collection behavior."""

    def test_routing_log_empty_initially(self):
        """RoutingLog should be empty when created."""
        log = RoutingLog()
        assert len(log.entries) == 0
        assert log.has_routes() is False

    def test_routing_log_add_entry(self):
        """RoutingLog.add() should append RoutingEntry."""
        log = RoutingLog()
        log.add(
            source_path="SECTION.FIELD",
            target_name="TARGET",
            value_hash="hash",
            constraint_passed=True,
        )

        assert len(log.entries) == 1
        assert log.has_routes() is True
        assert log.entries[0].source_path == "SECTION.FIELD"

    def test_routing_log_add_generates_timestamp(self):
        """RoutingLog.add() should auto-generate ISO8601 timestamp."""
        log = RoutingLog()
        log.add(
            source_path="S.F",
            target_name="T",
            value_hash="h",
            constraint_passed=True,
        )

        # Timestamp should be valid ISO8601
        timestamp = log.entries[0].timestamp
        assert timestamp is not None
        # Should parse as datetime (will raise if invalid)
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


class TestValidatorRoutingCollection:
    """Test routing collection during validation."""

    def test_validator_has_routing_log_attribute(self):
        """Validator should have routing_log attribute."""
        validator = Validator()
        assert hasattr(validator, "routing_log")
        assert isinstance(validator.routing_log, RoutingLog)

    def test_validate_returns_routing_log(self):
        """Validator.validate() should populate routing_log when targets exist.

        Given a schema with target routing (->TARGET),
        when validation runs,
        then routing_log should contain entries for each routed field.
        """
        # Arrange: Create a schema with target routing
        # Note: Must use unicode operators (∧ and →§) for holographic pattern parsing
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
        section_schemas = {"CONFIG": schema}

        # Create document with valid value
        section = Block(
            key="CONFIG",
            children=[
                Assignment(key="STATUS", value="ACTIVE"),
            ],
        )
        document = Document(meta={}, sections=[section])

        # Act
        validator = Validator()
        validator.validate(document, strict=False, section_schemas=section_schemas)

        # Assert: routing_log should have entry for STATUS field
        assert validator.routing_log.has_routes()
        assert len(validator.routing_log.entries) == 1

        entry = validator.routing_log.entries[0]
        assert entry.source_path == "CONFIG.STATUS"
        assert entry.target_name == "SELF"
        assert entry.constraint_passed is True

    def test_validate_routing_records_value_hash(self):
        """Routing entry should include SHA-256 hash of the value.

        The value_hash enables audit trail verification.
        """
        # Arrange
        pattern = parse_holographic_pattern('["example"∧REQ→§TARGET]')
        schema = SchemaDefinition(
            name="TEST",
            fields={"FIELD": FieldDefinition(name="FIELD", pattern=pattern)},
        )
        section_schemas = {"SEC": schema}

        section = Block(
            key="SEC",
            children=[Assignment(key="FIELD", value="test_value")],
        )
        document = Document(meta={}, sections=[section])

        # Act
        validator = Validator()
        validator.validate(document, strict=False, section_schemas=section_schemas)

        # Assert: value_hash should be SHA-256 of "test_value"
        expected_hash = hashlib.sha256(b"test_value").hexdigest()
        assert validator.routing_log.entries[0].value_hash == expected_hash

    def test_validate_routing_constraint_failed(self):
        """Routing should record constraint_passed=False when validation fails.

        Even when constraints fail, the routing entry is logged for audit.
        """
        # Arrange: ENUM constraint that will fail
        pattern = parse_holographic_pattern('["ACTIVE"∧ENUM[ACTIVE,INACTIVE]→§SELF]')
        schema = SchemaDefinition(
            name="TEST",
            fields={"STATUS": FieldDefinition(name="STATUS", pattern=pattern)},
        )
        section_schemas = {"CFG": schema}

        # Invalid value that will fail ENUM
        section = Block(
            key="CFG",
            children=[Assignment(key="STATUS", value="INVALID")],
        )
        document = Document(meta={}, sections=[section])

        # Act
        validator = Validator()
        validator.validate(document, strict=False, section_schemas=section_schemas)

        # Assert: routing entry exists with constraint_passed=False
        assert validator.routing_log.has_routes()
        entry = validator.routing_log.entries[0]
        assert entry.target_name == "SELF"
        assert entry.constraint_passed is False

    def test_validate_no_routing_for_fields_without_target(self):
        """Fields without target should not create routing entries.

        Only fields with ->TARGET in their holographic pattern should be routed.
        """
        # Arrange: Pattern WITHOUT target
        pattern = parse_holographic_pattern('["ACTIVE"∧ENUM[ACTIVE,INACTIVE]]')
        schema = SchemaDefinition(
            name="TEST",
            fields={"STATUS": FieldDefinition(name="STATUS", pattern=pattern)},
        )
        section_schemas = {"CFG": schema}

        section = Block(
            key="CFG",
            children=[Assignment(key="STATUS", value="ACTIVE")],
        )
        document = Document(meta={}, sections=[section])

        # Act
        validator = Validator()
        validator.validate(document, strict=False, section_schemas=section_schemas)

        # Assert: No routing entries (pattern has no target)
        assert not validator.routing_log.has_routes()


class TestFeudalInheritance:
    """Test block-level target inheritance with feudal override.

    Design decision: Child explicit target completely overrides parent block target.
    """

    def test_child_explicit_target_overrides_parent(self):
        """Child field with explicit target should override any parent target.

        Given:
        - Parent block has default target ->PARENT_TARGET
        - Child field has explicit target ->CHILD_TARGET

        Then the child's target (CHILD_TARGET) should be used.
        """
        # Arrange: Schema with block-level default target and field override
        # The block target would be specified at schema level
        child_pattern = parse_holographic_pattern('["value"∧REQ→§CHILD_TARGET]')
        schema = SchemaDefinition(
            name="TEST",
            fields={"FIELD": FieldDefinition(name="FIELD", pattern=child_pattern)},
        )
        # Add block-level default target
        schema.default_target = "PARENT_TARGET"
        section_schemas = {"BLOCK": schema}

        section = Block(
            key="BLOCK",
            children=[Assignment(key="FIELD", value="test")],
        )
        document = Document(meta={}, sections=[section])

        # Act
        validator = Validator()
        validator.validate(document, strict=False, section_schemas=section_schemas)

        # Assert: Child's explicit target used, not parent's
        assert validator.routing_log.has_routes()
        entry = validator.routing_log.entries[0]
        assert entry.target_name == "CHILD_TARGET"

    def test_field_inherits_parent_target_when_no_explicit(self):
        """Field without explicit target should inherit parent block target.

        Given:
        - Parent block has default target ->PARENT_TARGET
        - Child field has NO explicit target

        Then the parent's target (PARENT_TARGET) should be used.
        """
        # Arrange: Pattern WITHOUT target, but schema has default
        pattern = parse_holographic_pattern('["value"∧REQ]')  # No target
        schema = SchemaDefinition(
            name="TEST",
            fields={"FIELD": FieldDefinition(name="FIELD", pattern=pattern)},
        )
        # Set block-level default target
        schema.default_target = "PARENT_TARGET"
        section_schemas = {"BLOCK": schema}

        section = Block(
            key="BLOCK",
            children=[Assignment(key="FIELD", value="test")],
        )
        document = Document(meta={}, sections=[section])

        # Act
        validator = Validator()
        validator.validate(document, strict=False, section_schemas=section_schemas)

        # Assert: Parent's target inherited
        assert validator.routing_log.has_routes()
        entry = validator.routing_log.entries[0]
        assert entry.target_name == "PARENT_TARGET"

    def test_no_routing_when_no_target_at_any_level(self):
        """No routing when neither field nor block has target.

        Given:
        - Parent block has NO default target
        - Child field has NO explicit target

        Then no routing entry should be created.
        """
        # Arrange: Pattern without target, schema without default
        pattern = parse_holographic_pattern('["value"∧REQ]')
        schema = SchemaDefinition(
            name="TEST",
            fields={"FIELD": FieldDefinition(name="FIELD", pattern=pattern)},
        )
        # NO default_target set
        section_schemas = {"BLOCK": schema}

        section = Block(
            key="BLOCK",
            children=[Assignment(key="FIELD", value="test")],
        )
        document = Document(meta={}, sections=[section])

        # Act
        validator = Validator()
        validator.validate(document, strict=False, section_schemas=section_schemas)

        # Assert: No routing (no targets at any level)
        assert not validator.routing_log.has_routes()


class TestRoutingLogSerialization:
    """Test RoutingLog serialization for MCP output."""

    def test_routing_log_to_dict(self):
        """RoutingLog should serialize to dict for JSON output.

        The octave_validate tool output needs routing_log as serializable data.
        """
        log = RoutingLog()
        log.add(
            source_path="S.F",
            target_name="T",
            value_hash="hash123",
            constraint_passed=True,
        )

        result = log.to_dict()

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["source_path"] == "S.F"
        assert result[0]["target_name"] == "T"
        assert result[0]["value_hash"] == "hash123"
        assert result[0]["constraint_passed"] is True
        assert "timestamp" in result[0]

    def test_routing_log_empty_serializes_to_empty_list(self):
        """Empty RoutingLog should serialize to empty list."""
        log = RoutingLog()
        result = log.to_dict()

        assert result == []
