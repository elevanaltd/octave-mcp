"""Tests for block inheritance integration in validation (M3 CE violations).

CE Violation #1: BLOCK_TARGETS_PARSED_BUT_VALIDATOR_IGNORES_BLOCK_INHERITANCE
CE Violation #2: INHERITANCE_RESOLVER_UNWIRED

These tests verify that block target annotations parsed from the AST
are used during validation to route fields without explicit targets.

TDD RED phase: Tests should FAIL until fixes are implemented.
"""

from octave_mcp.core.ast_nodes import Block
from octave_mcp.core.holographic import parse_holographic_pattern
from octave_mcp.core.parser import parse
from octave_mcp.core.schema_extractor import (
    FieldDefinition,
    SchemaDefinition,
    extract_block_targets,
)
from octave_mcp.core.validator import Validator


class TestValidatorBlockInheritanceIntegration:
    """Test that validator uses block inheritance for target routing."""

    def test_field_inherits_target_from_parent_block(self):
        """Field without explicit target should inherit from parent block.

        CE Violation #1 & #2: Block targets are parsed but validator
        only uses POLICY.DEFAULT_TARGET, not block hierarchy.

        Given:
        - RISKS[->RISK_LOG]:
            CRITICAL::"auth_bypass"  # No explicit target in field
        - Schema with CRITICAL field having no explicit target

        Expected: CRITICAL routes to RISK_LOG via block inheritance.
        """
        # Parse document with block-level target annotation
        doc = parse("""
===TEST===
META:
  TYPE::TEST

RISKS[->RISK_LOG]:
  CRITICAL::"auth_bypass"
===END===
""")
        # Create a schema for RISKS section
        # Field has no explicit target - should inherit from block
        pattern = parse_holographic_pattern('["auth_bypass"∧REQ]')  # No target
        schema = SchemaDefinition(
            name="RISKS",
            fields={
                "CRITICAL": FieldDefinition(
                    name="CRITICAL",
                    pattern=pattern,
                )
            },
        )

        # Find the RISKS block
        risks_block = None
        for section in doc.sections:
            if isinstance(section, Block) and section.key == "RISKS":
                risks_block = section
                break

        assert risks_block is not None
        assert risks_block.target == "RISK_LOG"  # Parser captured block target

        # Validate with the document (so block targets can be extracted)
        validator = Validator()
        validator.validate(doc, strict=False, section_schemas={"RISKS": schema})

        # Assert: Field should route to inherited target
        assert validator.routing_log.has_routes(), "Expected routing to inherited target"
        entry = validator.routing_log.entries[0]
        assert (
            entry.target_name == "RISK_LOG"
        ), f"Expected field to inherit RISK_LOG from block, got {entry.target_name}"
        assert entry.source_path == "RISKS.CRITICAL"

    def test_field_explicit_target_overrides_block_inheritance(self):
        """Field with explicit target should override inherited block target.

        Given:
        - RISKS[->RISK_LOG]:
            WARNING::["rate_limit"∧OPT→§SELF]  # Explicit target in field

        Expected: WARNING routes to SELF (explicit), not RISK_LOG (inherited).
        """
        doc = parse("""
===TEST===
META:
  TYPE::TEST

RISKS[->RISK_LOG]:
  WARNING::"rate_limit"
===END===
""")
        # Field has explicit target SELF (using proper OCTAVE syntax with → and §)
        pattern = parse_holographic_pattern('["rate_limit"∧OPT→§SELF]')
        schema = SchemaDefinition(
            name="RISKS",
            fields={
                "WARNING": FieldDefinition(
                    name="WARNING",
                    pattern=pattern,
                )
            },
        )

        validator = Validator()
        validator.validate(doc, strict=False, section_schemas={"RISKS": schema})

        # Assert: Field should use explicit target, not inherited
        assert validator.routing_log.has_routes()
        entry = validator.routing_log.entries[0]
        assert entry.target_name == "SELF", f"Expected explicit target SELF, got {entry.target_name}"

    def test_deeply_nested_block_targets_are_extracted(self):
        """Deeply nested blocks should have targets extracted correctly.

        Given:
        - OUTER[->OUTER_TARGET]:
            MIDDLE[->MIDDLE_TARGET]:
              INNER:
                FIELD::"value"

        Verifies: Block targets are correctly extracted from nested structure.
        NOTE: Actual validation of deeply nested fields (inside OUTER.MIDDLE.INNER)
        requires recursive block validation which is beyond current scope.
        Current implementation only validates direct children of top-level sections.
        """
        doc = parse("""
===TEST===
META:
  TYPE::TEST

OUTER[->OUTER_TARGET]:
  MIDDLE[->MIDDLE_TARGET]:
    INNER:
      FIELD::"value"
===END===
""")
        # Verify block targets are extracted correctly
        block_targets = extract_block_targets(doc)
        assert block_targets.get("OUTER") == "OUTER_TARGET"
        assert block_targets.get("OUTER.MIDDLE") == "MIDDLE_TARGET"

        # Verify InheritanceResolver can resolve from this structure
        from octave_mcp.core.schema_extractor import InheritanceResolver

        resolver = InheritanceResolver()

        # Path: OUTER.MIDDLE.INNER.FIELD -> should resolve to MIDDLE_TARGET
        target = resolver.resolve_target(["OUTER", "MIDDLE", "INNER", "FIELD"], block_targets)
        assert target == "MIDDLE_TARGET", f"Expected MIDDLE_TARGET from nearest ancestor, got {target}"

    def test_block_target_inheritance_with_no_policy_default(self):
        """Block inheritance should work even without POLICY.DEFAULT_TARGET.

        CE Violation #2: Validator only checks POLICY.DEFAULT_TARGET,
        ignoring block-level targets entirely.

        Given:
        - No POLICY.DEFAULT_TARGET
        - DATA[->INDEXER]:
            ID::"123"  # No explicit target

        Expected: ID routes to INDEXER via block target (not None).
        """
        doc = parse("""
===TEST===
META:
  TYPE::TEST

DATA[->INDEXER]:
  ID::"123"
===END===
""")
        # Schema has no default_target
        pattern = parse_holographic_pattern('["123"∧REQ]')
        schema = SchemaDefinition(
            name="DATA",
            fields={
                "ID": FieldDefinition(
                    name="ID",
                    pattern=pattern,
                )
            },
            default_target=None,  # No policy default
        )

        validator = Validator()
        validator.validate(doc, strict=False, section_schemas={"DATA": schema})

        # Assert: Should still route to INDEXER via block inheritance
        assert validator.routing_log.has_routes(), "Expected block target inheritance to route field"
        entry = validator.routing_log.entries[0]
        assert entry.target_name == "INDEXER", f"Expected block target INDEXER, got {entry.target_name}"


class TestValidatorExtractsBlockTargets:
    """Test that validator correctly extracts block targets from document."""

    def test_validator_extracts_block_targets_during_validation(self):
        """Validator should extract block targets from parsed document.

        Block targets should be extracted once at the start of validation
        and used for inheritance resolution throughout.
        """
        doc = parse("""
===TEST===
META:
  TYPE::TEST

RISKS[->RISK_LOG]:
  CRITICAL::"auth_bypass"

DATA[->INDEXER]:
  ID::"abc"
===END===
""")
        # Verify block targets are extractable
        block_targets = extract_block_targets(doc)
        assert block_targets.get("RISKS") == "RISK_LOG"
        assert block_targets.get("DATA") == "INDEXER"

        # Schema for RISKS section
        pattern = parse_holographic_pattern('["auth_bypass"∧REQ]')
        schema = SchemaDefinition(
            name="RISKS",
            fields={
                "CRITICAL": FieldDefinition(
                    name="CRITICAL",
                    pattern=pattern,
                )
            },
        )

        # Validate - block targets should be used
        validator = Validator()
        validator.validate(doc, strict=False, section_schemas={"RISKS": schema})

        # This test verifies the mechanism works - if block targets
        # were not extracted/used, routing would fail or use wrong target
        assert validator.routing_log.has_routes()


class TestInheritanceResolverIntegration:
    """Test InheritanceResolver is actually called during validation."""

    def test_inheritance_resolver_resolve_called(self):
        """InheritanceResolver.resolve_target should be invoked for fields.

        CE Violation #2: InheritanceResolver exists but is never called
        during validation.

        This test verifies the resolver is wired into the validation flow.
        """

        doc = parse("""
===TEST===
META:
  TYPE::TEST

RISKS[->RISK_LOG]:
  CRITICAL::"auth_bypass"
===END===
""")
        # Schema field without explicit target
        pattern = parse_holographic_pattern('["auth_bypass"∧REQ]')
        schema = SchemaDefinition(
            name="RISKS",
            fields={
                "CRITICAL": FieldDefinition(
                    name="CRITICAL",
                    pattern=pattern,
                )
            },
        )

        validator = Validator()
        validator.validate(doc, strict=False, section_schemas={"RISKS": schema})

        # If inheritance resolver was called, routing should show inherited target
        assert validator.routing_log.has_routes()
        entry = validator.routing_log.entries[0]
        assert entry.target_name == "RISK_LOG", "InheritanceResolver was not used - field did not inherit block target"


class TestBlockInheritanceWithPolicy:
    """Test interaction between block inheritance and POLICY.DEFAULT_TARGET."""

    def test_block_target_takes_precedence_over_policy_default(self):
        """Block-level target should take precedence over POLICY.DEFAULT_TARGET.

        Feudal inheritance hierarchy (closest wins):
        1. Field explicit target (highest)
        2. Block-level target [->TARGET]
        3. POLICY.DEFAULT_TARGET (lowest)

        Given:
        - POLICY.DEFAULT_TARGET::BACKUP_LOG
        - RISKS[->RISK_LOG]:
            CRITICAL::"value"  # No explicit target

        Expected: CRITICAL routes to RISK_LOG (block), not BACKUP_LOG (policy).
        """
        doc = parse("""
===TEST===
META:
  TYPE::TEST

RISKS[->RISK_LOG]:
  CRITICAL::"auth_bypass"
===END===
""")
        # Schema has policy default_target, but block has its own target
        pattern = parse_holographic_pattern('["auth_bypass"∧REQ]')
        schema = SchemaDefinition(
            name="RISKS",
            fields={
                "CRITICAL": FieldDefinition(
                    name="CRITICAL",
                    pattern=pattern,
                )
            },
            default_target="BACKUP_LOG",  # Policy default
        )

        validator = Validator()
        validator.validate(doc, strict=False, section_schemas={"RISKS": schema})

        # Assert: Block target wins over policy default
        assert validator.routing_log.has_routes()
        entry = validator.routing_log.entries[0]
        assert (
            entry.target_name == "RISK_LOG"
        ), f"Expected block target RISK_LOG to win over policy default, got {entry.target_name}"

    def test_policy_default_used_when_no_block_target(self):
        """POLICY.DEFAULT_TARGET should be used when no block has a target.

        Given:
        - POLICY.DEFAULT_TARGET::BACKUP_LOG
        - SIMPLE: (no block target)
            FIELD::"value"

        Expected: FIELD routes to BACKUP_LOG (policy default).
        """
        doc = parse("""
===TEST===
META:
  TYPE::TEST

SIMPLE:
  FIELD::"value"
===END===
""")
        # Block has no target, policy has default
        pattern = parse_holographic_pattern('["value"∧REQ]')
        schema = SchemaDefinition(
            name="SIMPLE",
            fields={
                "FIELD": FieldDefinition(
                    name="FIELD",
                    pattern=pattern,
                )
            },
            default_target="BACKUP_LOG",  # Policy default
        )

        validator = Validator()
        validator.validate(doc, strict=False, section_schemas={"SIMPLE": schema})

        # Assert: Policy default is used
        assert validator.routing_log.has_routes()
        entry = validator.routing_log.entries[0]
        assert entry.target_name == "BACKUP_LOG", f"Expected policy default BACKUP_LOG, got {entry.target_name}"
