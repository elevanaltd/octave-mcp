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
        # Arrange - use builtin target INDEXER (Issue #188: target validation)
        pattern = parse_holographic_pattern('["example"∧REQ→§INDEXER]')
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
        - Parent block has default target ->DECISION_LOG (builtin)
        - Child field has explicit target ->INDEXER (builtin)

        Then the child's target (INDEXER) should be used.

        Note: Issue #188 requires targets to be valid (builtin/custom/file path).
        """
        # Arrange: Schema with block-level default target and field override
        # Using builtins: INDEXER overrides DECISION_LOG
        child_pattern = parse_holographic_pattern('["value"∧REQ→§INDEXER]')
        schema = SchemaDefinition(
            name="TEST",
            fields={"FIELD": FieldDefinition(name="FIELD", pattern=child_pattern)},
        )
        # Add block-level default target (builtin)
        schema.default_target = "DECISION_LOG"
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
        assert entry.target_name == "INDEXER"

    def test_field_inherits_parent_target_when_no_explicit(self):
        """Field without explicit target should inherit parent block target.

        Given:
        - Parent block has default target ->DECISION_LOG (builtin)
        - Child field has NO explicit target

        Then the parent's target (DECISION_LOG) should be used.

        Note: Issue #188 requires targets to be valid (builtin/custom/file path).
        """
        # Arrange: Pattern WITHOUT target, but schema has default (builtin)
        pattern = parse_holographic_pattern('["value"∧REQ]')  # No target
        schema = SchemaDefinition(
            name="TEST",
            fields={"FIELD": FieldDefinition(name="FIELD", pattern=pattern)},
        )
        # Set block-level default target (builtin)
        schema.default_target = "DECISION_LOG"
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
        assert entry.target_name == "DECISION_LOG"

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


# ============================================================================
# Issue #188: Target Routing System
# ============================================================================


class TestTargetDataclass:
    """Test Target dataclass representing a routing destination."""

    def test_target_has_required_fields(self):
        """Target should have name, target_type, and optional path.

        From spec §3::TARGETS:
        - BUILTIN::[§SELF,§META,§INDEXER,§DECISION_LOG,§RISK_LOG,§KNOWLEDGE_BASE]
        - FILE::§./relative/path[resolved_from_document_directory]
        """
        from octave_mcp.core.routing import Target

        target = Target(name="INDEXER", target_type="builtin")

        assert target.name == "INDEXER"
        assert target.target_type == "builtin"
        assert target.path is None

    def test_target_file_type_with_path(self):
        """File targets should have relative path resolved from document directory."""
        from octave_mcp.core.routing import Target

        target = Target(name="output", target_type="file", path="./output/data.oct")

        assert target.name == "output"
        assert target.target_type == "file"
        assert target.path == "./output/data.oct"

    def test_target_custom_type(self):
        """Custom targets are declared in POLICY.TARGETS."""
        from octave_mcp.core.routing import Target

        target = Target(name="MY_CUSTOM_TARGET", target_type="custom")

        assert target.name == "MY_CUSTOM_TARGET"
        assert target.target_type == "custom"

    def test_target_is_frozen(self):
        """Target should be immutable (frozen dataclass)."""
        from dataclasses import FrozenInstanceError

        from octave_mcp.core.routing import Target

        target = Target(name="SELF", target_type="builtin")

        # Should raise FrozenInstanceError
        import pytest

        with pytest.raises(FrozenInstanceError):
            target.name = "OTHER"


class TestTargetRegistry:
    """Test TargetRegistry for managing builtin and custom targets."""

    def test_registry_has_builtins(self):
        """Registry should recognize all builtin targets from spec.

        Spec §3::TARGETS BUILTIN::[§SELF,§META,§INDEXER,§DECISION_LOG,§RISK_LOG,§KNOWLEDGE_BASE]
        """
        from octave_mcp.core.routing import TargetRegistry

        registry = TargetRegistry()

        assert registry.is_builtin("SELF")
        assert registry.is_builtin("META")
        assert registry.is_builtin("INDEXER")
        assert registry.is_builtin("DECISION_LOG")
        assert registry.is_builtin("RISK_LOG")
        assert registry.is_builtin("KNOWLEDGE_BASE")

    def test_registry_custom_targets_initially_empty(self):
        """Registry should have no custom targets initially."""
        from octave_mcp.core.routing import TargetRegistry

        registry = TargetRegistry()

        assert len(registry.custom_targets) == 0

    def test_registry_register_custom_target(self):
        """Registry should allow registering custom targets."""
        from octave_mcp.core.routing import TargetRegistry

        registry = TargetRegistry()
        registry.register_custom("MY_TARGET")

        assert "MY_TARGET" in registry.custom_targets
        assert registry.is_valid("MY_TARGET")

    def test_registry_is_valid_builtin(self):
        """Builtin targets should be valid."""
        from octave_mcp.core.routing import TargetRegistry

        registry = TargetRegistry()

        assert registry.is_valid("INDEXER")
        assert registry.is_valid("DECISION_LOG")

    def test_registry_is_valid_custom(self):
        """Registered custom targets should be valid."""
        from octave_mcp.core.routing import TargetRegistry

        registry = TargetRegistry()
        registry.register_custom("CUSTOM")

        assert registry.is_valid("CUSTOM")

    def test_registry_is_valid_file_path(self):
        """File paths (starting with ./) should be valid."""
        from octave_mcp.core.routing import TargetRegistry

        registry = TargetRegistry()

        assert registry.is_valid("./output/data.oct")
        assert registry.is_valid("./relative/path")

    def test_registry_unknown_target_invalid(self):
        """Unknown targets should be invalid."""
        from octave_mcp.core.routing import TargetRegistry

        registry = TargetRegistry()

        assert not registry.is_valid("UNKNOWN_TARGET")
        assert not registry.is_valid("NOT_REGISTERED")

    def test_registry_resolve_builtin(self):
        """Resolve should return Target for builtin."""
        from octave_mcp.core.routing import Target, TargetRegistry

        registry = TargetRegistry()
        target = registry.resolve("INDEXER")

        assert target == Target(name="INDEXER", target_type="builtin")

    def test_registry_resolve_custom(self):
        """Resolve should return Target for custom."""
        from octave_mcp.core.routing import Target, TargetRegistry

        registry = TargetRegistry()
        registry.register_custom("MY_TARGET")
        target = registry.resolve("MY_TARGET")

        assert target == Target(name="MY_TARGET", target_type="custom")

    def test_registry_resolve_file_path(self):
        """Resolve should return Target for file path."""
        from octave_mcp.core.routing import Target, TargetRegistry

        registry = TargetRegistry()
        target = registry.resolve("./output/data.oct")

        assert target == Target(name="./output/data.oct", target_type="file", path="./output/data.oct")

    def test_registry_resolve_unknown_returns_none(self):
        """Resolve should return None for unknown targets."""
        from octave_mcp.core.routing import TargetRegistry

        registry = TargetRegistry()
        target = registry.resolve("UNKNOWN")

        assert target is None


class TestTargetRouter:
    """Test TargetRouter for routing logic and multi-target broadcast."""

    def test_router_requires_registry_and_log(self):
        """Router should be initialized with registry and routing log."""
        from octave_mcp.core.routing import RoutingLog, TargetRegistry, TargetRouter

        registry = TargetRegistry()
        log = RoutingLog()
        router = TargetRouter(registry=registry, routing_log=log)

        assert router.registry is registry
        assert router.log is log

    def test_router_parse_single_target(self):
        """Parser should handle single target specification."""
        from octave_mcp.core.routing import RoutingLog, TargetRegistry, TargetRouter

        router = TargetRouter(TargetRegistry(), RoutingLog())

        targets = router.parse_target_spec("INDEXER")
        assert targets == ["INDEXER"]

    def test_router_parse_multi_target_unicode(self):
        """Parser should handle multi-target with unicode disjunction (∨).

        Spec §3::TARGETS MULTI::"§A∨§B∨§C"[broadcast_to_all]
        """
        from octave_mcp.core.routing import RoutingLog, TargetRegistry, TargetRouter

        router = TargetRouter(TargetRegistry(), RoutingLog())

        targets = router.parse_target_spec("INDEXER∨DECISION_LOG∨RISK_LOG")
        assert targets == ["INDEXER", "DECISION_LOG", "RISK_LOG"]

    def test_router_parse_multi_target_strips_section_marker(self):
        """Parser should strip § section markers from target names."""
        from octave_mcp.core.routing import RoutingLog, TargetRegistry, TargetRouter

        router = TargetRouter(TargetRegistry(), RoutingLog())

        # With section markers
        targets = router.parse_target_spec("§INDEXER∨§DECISION_LOG")
        assert targets == ["INDEXER", "DECISION_LOG"]

    def test_router_route_single_valid_target(self):
        """Route should create routing entry for valid single target."""
        from octave_mcp.core.routing import RoutingLog, TargetRegistry, TargetRouter

        registry = TargetRegistry()
        log = RoutingLog()
        router = TargetRouter(registry, log)

        entries = router.route(
            source_path="CONFIG.STATUS",
            target_spec="INDEXER",
            value="ACTIVE",
            constraint_passed=True,
        )

        assert len(entries) == 1
        assert entries[0].target_name == "INDEXER"
        assert entries[0].source_path == "CONFIG.STATUS"
        assert entries[0].constraint_passed is True
        assert log.has_routes()

    def test_router_route_multi_target_broadcast(self):
        """Route should broadcast to all targets in multi-target spec.

        Spec: MULTI::"§A∨§B∨§C"[broadcast_to_all]
        """
        from octave_mcp.core.routing import RoutingLog, TargetRegistry, TargetRouter

        registry = TargetRegistry()
        log = RoutingLog()
        router = TargetRouter(registry, log)

        entries = router.route(
            source_path="DATA.ITEM",
            target_spec="INDEXER∨DECISION_LOG",
            value="test_value",
            constraint_passed=True,
        )

        assert len(entries) == 2
        target_names = {e.target_name for e in entries}
        assert target_names == {"INDEXER", "DECISION_LOG"}
        assert len(log.entries) == 2

    def test_router_route_invalid_target_error(self):
        """Route should raise error for invalid target.

        Spec: VALIDATION::target_must_exist[declared_in_POLICY.TARGETS∨builtin]
        """
        from octave_mcp.core.routing import (
            InvalidTargetError,
            RoutingLog,
            TargetRegistry,
            TargetRouter,
        )

        registry = TargetRegistry()
        log = RoutingLog()
        router = TargetRouter(registry, log)

        import pytest

        with pytest.raises(InvalidTargetError) as exc_info:
            router.route(
                source_path="DATA.FIELD",
                target_spec="UNKNOWN_TARGET",
                value="value",
                constraint_passed=True,
            )

        assert "UNKNOWN_TARGET" in str(exc_info.value)

    def test_router_route_multi_target_partial_failure(self):
        """Route should handle partial failure in multi-target.

        Spec: MULTI_FAILURE::non_transactional[partial_success_possible,handler_responsibility]
        """
        from octave_mcp.core.routing import (
            InvalidTargetError,
            RoutingLog,
            TargetRegistry,
            TargetRouter,
        )

        registry = TargetRegistry()
        log = RoutingLog()
        router = TargetRouter(registry, log)

        # First target valid, second invalid
        import pytest

        with pytest.raises(InvalidTargetError) as exc_info:
            router.route(
                source_path="DATA.FIELD",
                target_spec="INDEXER∨INVALID_TARGET",
                value="value",
                constraint_passed=True,
            )

        # Partial success: first target should have been routed
        assert "INVALID_TARGET" in str(exc_info.value)
        # Non-transactional: valid target was logged before error
        assert any(e.target_name == "INDEXER" for e in log.entries)

    def test_router_route_file_path_target(self):
        """Route should handle file path targets."""
        from octave_mcp.core.routing import RoutingLog, TargetRegistry, TargetRouter

        registry = TargetRegistry()
        log = RoutingLog()
        router = TargetRouter(registry, log)

        entries = router.route(
            source_path="DATA.OUTPUT",
            target_spec="./output/data.oct",
            value={"key": "value"},
            constraint_passed=True,
        )

        assert len(entries) == 1
        assert entries[0].target_name == "./output/data.oct"

    def test_router_route_with_custom_target(self):
        """Route should work with registered custom targets."""
        from octave_mcp.core.routing import RoutingLog, TargetRegistry, TargetRouter

        registry = TargetRegistry()
        registry.register_custom("MY_CUSTOM")
        log = RoutingLog()
        router = TargetRouter(registry, log)

        entries = router.route(
            source_path="DATA.FIELD",
            target_spec="MY_CUSTOM",
            value="data",
            constraint_passed=True,
        )

        assert len(entries) == 1
        assert entries[0].target_name == "MY_CUSTOM"


class TestValidatorTargetIntegration:
    """Test validator integration with TargetRouter for target validation."""

    def test_validator_accepts_builtin_target(self):
        """Validator should accept builtin targets without error."""
        pattern = parse_holographic_pattern('["value"∧REQ→§INDEXER]')
        schema = SchemaDefinition(
            name="TEST",
            fields={"FIELD": FieldDefinition(name="FIELD", pattern=pattern)},
        )
        section_schemas = {"BLOCK": schema}

        section = Block(
            key="BLOCK",
            children=[Assignment(key="FIELD", value="test")],
        )
        document = Document(meta={}, sections=[section])

        validator = Validator()
        errors = validator.validate(document, strict=False, section_schemas=section_schemas)

        # No errors for builtin target
        assert not any(e.code == "E009" for e in errors)
        # Routing should be logged
        assert validator.routing_log.has_routes()
        assert validator.routing_log.entries[0].target_name == "INDEXER"

    def test_validator_rejects_unknown_target(self):
        """Validator should reject unknown targets with E009 error.

        Spec: VALIDATION::target_must_exist[declared_in_POLICY.TARGETS∨builtin]
        """
        pattern = parse_holographic_pattern('["value"∧REQ→§UNKNOWN_TARGET]')
        schema = SchemaDefinition(
            name="TEST",
            fields={"FIELD": FieldDefinition(name="FIELD", pattern=pattern)},
        )
        section_schemas = {"BLOCK": schema}

        section = Block(
            key="BLOCK",
            children=[Assignment(key="FIELD", value="test")],
        )
        document = Document(meta={}, sections=[section])

        validator = Validator()
        errors = validator.validate(document, strict=False, section_schemas=section_schemas)

        # Should have E009 error for invalid target
        target_errors = [e for e in errors if e.code == "E009"]
        assert len(target_errors) == 1
        assert "UNKNOWN_TARGET" in target_errors[0].message

    def test_validator_accepts_file_path_target(self):
        """Validator should accept file path targets (starting with ./)."""
        pattern = parse_holographic_pattern('["value"∧REQ→§./output/data.oct]')
        schema = SchemaDefinition(
            name="TEST",
            fields={"FIELD": FieldDefinition(name="FIELD", pattern=pattern)},
        )
        section_schemas = {"BLOCK": schema}

        section = Block(
            key="BLOCK",
            children=[Assignment(key="FIELD", value="test")],
        )
        document = Document(meta={}, sections=[section])

        validator = Validator()
        errors = validator.validate(document, strict=False, section_schemas=section_schemas)

        # No errors for file path target
        assert not any(e.code == "E009" for e in errors)
        assert validator.routing_log.has_routes()
        assert validator.routing_log.entries[0].target_name == "./output/data.oct"

    def test_validator_accepts_custom_target_from_policy(self):
        """Validator should accept custom targets declared in POLICY.TARGETS."""
        from octave_mcp.core.schema_extractor import PolicyDefinition

        pattern = parse_holographic_pattern('["value"∧REQ→§MY_CUSTOM_TARGET]')
        schema = SchemaDefinition(
            name="TEST",
            fields={"FIELD": FieldDefinition(name="FIELD", pattern=pattern)},
            # Issue #190: Custom targets declared via policy.targets
            policy=PolicyDefinition(
                version="1.0",
                unknown_fields="REJECT",
                targets=["MY_CUSTOM_TARGET"],
            ),
        )
        section_schemas = {"BLOCK": schema}

        section = Block(
            key="BLOCK",
            children=[Assignment(key="FIELD", value="test")],
        )
        document = Document(meta={}, sections=[section])

        validator = Validator()
        errors = validator.validate(document, strict=False, section_schemas=section_schemas)

        # No errors for registered custom target
        assert not any(e.code == "E009" for e in errors)
        assert validator.routing_log.has_routes()
        assert validator.routing_log.entries[0].target_name == "MY_CUSTOM_TARGET"

    def test_validator_handles_multi_target_broadcast(self):
        """Validator should handle multi-target broadcast (§A∨§B)."""
        pattern = parse_holographic_pattern('["value"∧REQ→§INDEXER∨§DECISION_LOG]')
        schema = SchemaDefinition(
            name="TEST",
            fields={"FIELD": FieldDefinition(name="FIELD", pattern=pattern)},
        )
        section_schemas = {"BLOCK": schema}

        section = Block(
            key="BLOCK",
            children=[Assignment(key="FIELD", value="test")],
        )
        document = Document(meta={}, sections=[section])

        validator = Validator()
        errors = validator.validate(document, strict=False, section_schemas=section_schemas)

        # No errors for builtin targets
        assert not any(e.code == "E009" for e in errors)
        # Both targets should be routed
        assert len(validator.routing_log.entries) == 2
        target_names = {e.target_name for e in validator.routing_log.entries}
        assert target_names == {"INDEXER", "DECISION_LOG"}

    def test_validator_multi_target_partial_invalid(self):
        """Validator should report error for invalid target in multi-target spec.

        Spec: MULTI_FAILURE::non_transactional[partial_success_possible]
        """
        pattern = parse_holographic_pattern('["value"∧REQ→§INDEXER∨§UNKNOWN_TARGET]')
        schema = SchemaDefinition(
            name="TEST",
            fields={"FIELD": FieldDefinition(name="FIELD", pattern=pattern)},
        )
        section_schemas = {"BLOCK": schema}

        section = Block(
            key="BLOCK",
            children=[Assignment(key="FIELD", value="test")],
        )
        document = Document(meta={}, sections=[section])

        validator = Validator()
        errors = validator.validate(document, strict=False, section_schemas=section_schemas)

        # Should have E009 error for the invalid target
        target_errors = [e for e in errors if e.code == "E009"]
        assert len(target_errors) == 1
        assert "UNKNOWN_TARGET" in target_errors[0].message

        # Valid target should still be routed (non-transactional)
        assert any(e.target_name == "INDEXER" for e in validator.routing_log.entries)
