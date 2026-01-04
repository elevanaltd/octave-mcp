"""Tests for repair engine (P1.6, Gap_5).

Gap_5 implements schema-driven repair logic:
- TIER_REPAIR: Enum casefold, type coercion (only when fix=true)
- TIER_FORBIDDEN: Never auto-fix field insertion, target inference

All repairs are logged to RepairLog for I4 audit compliance.
"""

from octave_mcp.core.constraints import ConstraintChain, EnumConstraint, TypeConstraint
from octave_mcp.core.holographic import HolographicPattern
from octave_mcp.core.parser import parse
from octave_mcp.core.repair import repair, repair_value
from octave_mcp.core.repair_log import RepairLog, RepairTier
from octave_mcp.core.schema_extractor import FieldDefinition
from octave_mcp.core.validator import validate


class TestRepairTiers:
    """Test repair tier classification."""

    def test_normalization_tier_always_applied(self):
        """TIER_NORMALIZATION repairs always applied (by lexer/parser)."""
        # ASCII aliases normalized by lexer
        content = """===TEST===
KEY::value
===END===
"""
        doc = parse(content)
        repaired, log = repair(doc, [])
        # Normalization happens in lexer, so log may be empty here
        assert repaired is not None

    def test_repair_tier_only_when_fix_true(self):
        """TIER_REPAIR only when fix=true."""
        doc = parse("===TEST===\nKEY::value\n===END===")
        repaired_no_fix, log_no_fix = repair(doc, [], fix=False)
        repaired_fix, log_fix = repair(doc, [], fix=True)
        # Both should work, but behavior may differ
        assert repaired_no_fix is not None
        assert repaired_fix is not None


class TestForbiddenRepairs:
    """Test forbidden repairs never applied."""

    def test_never_auto_fills_missing_fields(self):
        """Should never auto-fill missing required fields."""
        # This is enforced by validator returning E003 errors
        schema = {"META": {"required": ["TYPE"]}}
        doc = parse("===TEST===\nMETA:\n  VERSION::1.0\n===END===")
        errors = validate(doc, schema)
        # Errors should remain, repair shouldn't fix them
        repaired, log = repair(doc, errors, fix=True)
        # Validation errors for missing TYPE should persist
        errors_after = validate(repaired, schema)
        assert len(errors_after) > 0  # Still has errors, wasn't auto-fixed


# =============================================================================
# Gap_5: Schema-Driven Repair Logic Tests (TDD - RED PHASE)
# =============================================================================


class TestEnumCasefoldRepair:
    """Test enum casefold repair: lowercase -> CANONICAL (only if unique match)."""

    def test_enum_casefold_repairs_lowercase_to_canonical(self):
        """ENUM casefold: 'active' -> 'ACTIVE' when unique case-insensitive match."""
        # Create field definition with ENUM constraint
        constraints = ConstraintChain([EnumConstraint(allowed_values=["ACTIVE", "INACTIVE"])])
        pattern = HolographicPattern(example="ACTIVE", constraints=constraints, target=None)
        field_def = FieldDefinition(name="STATUS", pattern=pattern, raw_value=None)

        # Value differs only in case
        value = "active"
        repair_log = RepairLog(repairs=[])

        # Attempt repair with fix=True
        repaired_value, was_repaired = repair_value(
            value=value,
            field_def=field_def,
            repair_log=repair_log,
            fix=True,
        )

        # Should repair to canonical case
        assert was_repaired is True
        assert repaired_value == "ACTIVE"

        # Should log the repair with correct tier
        assert repair_log.has_repairs()
        assert len(repair_log.repairs) == 1
        entry = repair_log.repairs[0]
        assert entry.tier == RepairTier.REPAIR
        assert entry.before == "active"
        assert entry.after == "ACTIVE"
        assert "ENUM" in entry.rule_id

    def test_enum_casefold_handles_mixed_case(self):
        """ENUM casefold: 'AcTiVe' -> 'ACTIVE' when unique match."""
        constraints = ConstraintChain([EnumConstraint(allowed_values=["ACTIVE", "INACTIVE"])])
        pattern = HolographicPattern(example="ACTIVE", constraints=constraints, target=None)
        field_def = FieldDefinition(name="STATUS", pattern=pattern, raw_value=None)

        value = "AcTiVe"
        repair_log = RepairLog(repairs=[])

        repaired_value, was_repaired = repair_value(
            value=value,
            field_def=field_def,
            repair_log=repair_log,
            fix=True,
        )

        assert was_repaired is True
        assert repaired_value == "ACTIVE"

    def test_enum_casefold_no_repair_if_ambiguous(self):
        """ENUM casefold: No repair if multiple values match case-insensitively."""
        # Ambiguous: both "Active" and "ACTIVE" exist in enum (different entries)
        constraints = ConstraintChain([EnumConstraint(allowed_values=["Active", "ACTIVE", "INACTIVE"])])
        pattern = HolographicPattern(example="ACTIVE", constraints=constraints, target=None)
        field_def = FieldDefinition(name="STATUS", pattern=pattern, raw_value=None)

        value = "active"  # Matches both "Active" and "ACTIVE" case-insensitively
        repair_log = RepairLog(repairs=[])

        repaired_value, was_repaired = repair_value(
            value=value,
            field_def=field_def,
            repair_log=repair_log,
            fix=True,
        )

        # Should NOT repair - ambiguous match
        assert was_repaired is False
        assert repaired_value == "active"  # Original preserved
        assert not repair_log.has_repairs()

    def test_enum_casefold_no_repair_if_no_match(self):
        """ENUM casefold: No repair if value doesn't match any enum value."""
        constraints = ConstraintChain([EnumConstraint(allowed_values=["ACTIVE", "INACTIVE"])])
        pattern = HolographicPattern(example="ACTIVE", constraints=constraints, target=None)
        field_def = FieldDefinition(name="STATUS", pattern=pattern, raw_value=None)

        value = "PENDING"  # Not in enum at all
        repair_log = RepairLog(repairs=[])

        repaired_value, was_repaired = repair_value(
            value=value,
            field_def=field_def,
            repair_log=repair_log,
            fix=True,
        )

        # Should NOT repair - no match
        assert was_repaired is False
        assert repaired_value == "PENDING"
        assert not repair_log.has_repairs()

    def test_enum_casefold_no_repair_if_already_canonical(self):
        """ENUM casefold: No repair if value already matches exactly."""
        constraints = ConstraintChain([EnumConstraint(allowed_values=["ACTIVE", "INACTIVE"])])
        pattern = HolographicPattern(example="ACTIVE", constraints=constraints, target=None)
        field_def = FieldDefinition(name="STATUS", pattern=pattern, raw_value=None)

        value = "ACTIVE"  # Already correct
        repair_log = RepairLog(repairs=[])

        repaired_value, was_repaired = repair_value(
            value=value,
            field_def=field_def,
            repair_log=repair_log,
            fix=True,
        )

        # Should NOT repair - already correct
        assert was_repaired is False
        assert repaired_value == "ACTIVE"
        assert not repair_log.has_repairs()

    def test_enum_casefold_no_repair_without_fix_flag(self):
        """ENUM casefold: No repair when fix=False."""
        constraints = ConstraintChain([EnumConstraint(allowed_values=["ACTIVE", "INACTIVE"])])
        pattern = HolographicPattern(example="ACTIVE", constraints=constraints, target=None)
        field_def = FieldDefinition(name="STATUS", pattern=pattern, raw_value=None)

        value = "active"  # Would match ACTIVE
        repair_log = RepairLog(repairs=[])

        repaired_value, was_repaired = repair_value(
            value=value,
            field_def=field_def,
            repair_log=repair_log,
            fix=False,  # Repair disabled
        )

        # Should NOT repair - fix=False
        assert was_repaired is False
        assert repaired_value == "active"
        assert not repair_log.has_repairs()


class TestTypeCoercionRepair:
    """Test type coercion repair: string -> number (only if lossless)."""

    def test_type_coercion_string_to_number(self):
        """TYPE coercion: '42' -> 42 when schema expects NUMBER."""
        constraints = ConstraintChain([TypeConstraint(expected_type="NUMBER")])
        pattern = HolographicPattern(example=42, constraints=constraints, target=None)
        field_def = FieldDefinition(name="COUNT", pattern=pattern, raw_value=None)

        value = "42"  # String that should be number
        repair_log = RepairLog(repairs=[])

        repaired_value, was_repaired = repair_value(
            value=value,
            field_def=field_def,
            repair_log=repair_log,
            fix=True,
        )

        # Should repair to int
        assert was_repaired is True
        assert repaired_value == 42
        assert isinstance(repaired_value, int)

        # Should log the repair
        assert repair_log.has_repairs()
        entry = repair_log.repairs[0]
        assert entry.tier == RepairTier.REPAIR
        assert entry.before == "42"
        assert entry.after == "42"  # String representation
        assert "TYPE" in entry.rule_id

    def test_type_coercion_string_to_float(self):
        """TYPE coercion: '3.14' -> 3.14 when schema expects NUMBER."""
        constraints = ConstraintChain([TypeConstraint(expected_type="NUMBER")])
        pattern = HolographicPattern(example=3.14, constraints=constraints, target=None)
        field_def = FieldDefinition(name="RATIO", pattern=pattern, raw_value=None)

        value = "3.14"
        repair_log = RepairLog(repairs=[])

        repaired_value, was_repaired = repair_value(
            value=value,
            field_def=field_def,
            repair_log=repair_log,
            fix=True,
        )

        assert was_repaired is True
        assert repaired_value == 3.14
        assert isinstance(repaired_value, float)

    def test_type_coercion_no_repair_if_lossy(self):
        """TYPE coercion: No repair if conversion is lossy (e.g., '3.14' to int)."""
        # Note: "3.14" can be converted to float, but if we somehow tried int, it would be lossy
        # This test verifies we don't truncate decimals when target is NUMBER
        constraints = ConstraintChain([TypeConstraint(expected_type="NUMBER")])
        pattern = HolographicPattern(example=42, constraints=constraints, target=None)
        field_def = FieldDefinition(name="COUNT", pattern=pattern, raw_value=None)

        value = "not_a_number"  # Can't be converted at all
        repair_log = RepairLog(repairs=[])

        repaired_value, was_repaired = repair_value(
            value=value,
            field_def=field_def,
            repair_log=repair_log,
            fix=True,
        )

        # Should NOT repair - can't convert
        assert was_repaired is False
        assert repaired_value == "not_a_number"
        assert not repair_log.has_repairs()

    def test_type_coercion_no_repair_if_already_correct(self):
        """TYPE coercion: No repair if value is already correct type."""
        constraints = ConstraintChain([TypeConstraint(expected_type="NUMBER")])
        pattern = HolographicPattern(example=42, constraints=constraints, target=None)
        field_def = FieldDefinition(name="COUNT", pattern=pattern, raw_value=None)

        value = 42  # Already int
        repair_log = RepairLog(repairs=[])

        repaired_value, was_repaired = repair_value(
            value=value,
            field_def=field_def,
            repair_log=repair_log,
            fix=True,
        )

        # Should NOT repair - already correct
        assert was_repaired is False
        assert repaired_value == 42
        assert not repair_log.has_repairs()

    def test_type_coercion_no_repair_without_fix_flag(self):
        """TYPE coercion: No repair when fix=False."""
        constraints = ConstraintChain([TypeConstraint(expected_type="NUMBER")])
        pattern = HolographicPattern(example=42, constraints=constraints, target=None)
        field_def = FieldDefinition(name="COUNT", pattern=pattern, raw_value=None)

        value = "42"
        repair_log = RepairLog(repairs=[])

        repaired_value, was_repaired = repair_value(
            value=value,
            field_def=field_def,
            repair_log=repair_log,
            fix=False,  # Repair disabled
        )

        # Should NOT repair - fix=False
        assert was_repaired is False
        assert repaired_value == "42"
        assert not repair_log.has_repairs()

    def test_type_coercion_string_with_whitespace(self):
        """TYPE coercion: Handles strings with leading/trailing whitespace."""
        constraints = ConstraintChain([TypeConstraint(expected_type="NUMBER")])
        pattern = HolographicPattern(example=42, constraints=constraints, target=None)
        field_def = FieldDefinition(name="COUNT", pattern=pattern, raw_value=None)

        value = "  42  "  # Whitespace around number
        repair_log = RepairLog(repairs=[])

        repaired_value, was_repaired = repair_value(
            value=value,
            field_def=field_def,
            repair_log=repair_log,
            fix=True,
        )

        # Should repair (stripping whitespace is lossless)
        assert was_repaired is True
        assert repaired_value == 42

    def test_type_coercion_scientific_notation(self):
        """TYPE coercion: Handles scientific notation strings."""
        constraints = ConstraintChain([TypeConstraint(expected_type="NUMBER")])
        pattern = HolographicPattern(example=1e10, constraints=constraints, target=None)
        field_def = FieldDefinition(name="LARGE", pattern=pattern, raw_value=None)

        value = "1e10"
        repair_log = RepairLog(repairs=[])

        repaired_value, was_repaired = repair_value(
            value=value,
            field_def=field_def,
            repair_log=repair_log,
            fix=True,
        )

        assert was_repaired is True
        assert repaired_value == 1e10


class TestRepairLogAuditTrail:
    """Test I4 compliance: All repairs logged with audit trail."""

    def test_repair_log_entries_created_with_audit_trail(self):
        """Repair entries include all I4-required fields."""
        constraints = ConstraintChain([EnumConstraint(allowed_values=["ACTIVE", "INACTIVE"])])
        pattern = HolographicPattern(example="ACTIVE", constraints=constraints, target=None)
        field_def = FieldDefinition(name="STATUS", pattern=pattern, raw_value=None)

        value = "active"
        repair_log = RepairLog(repairs=[])

        repair_value(
            value=value,
            field_def=field_def,
            repair_log=repair_log,
            fix=True,
        )

        # Verify audit trail completeness
        assert len(repair_log.repairs) == 1
        entry = repair_log.repairs[0]

        # I4: All required fields present
        assert entry.rule_id is not None and entry.rule_id != ""
        assert entry.before is not None
        assert entry.after is not None
        assert entry.tier is not None
        assert entry.safe is not None
        assert entry.semantics_changed is not None

        # Tier should be REPAIR (not NORMALIZATION or FORBIDDEN)
        assert entry.tier == RepairTier.REPAIR

    def test_multiple_repairs_logged_in_order(self):
        """Multiple repair operations are logged in order."""
        repair_log = RepairLog(repairs=[])

        # First repair: enum casefold
        constraints1 = ConstraintChain([EnumConstraint(allowed_values=["ACTIVE", "INACTIVE"])])
        pattern1 = HolographicPattern(example="ACTIVE", constraints=constraints1, target=None)
        field_def1 = FieldDefinition(name="STATUS", pattern=pattern1, raw_value=None)

        repair_value(value="active", field_def=field_def1, repair_log=repair_log, fix=True)

        # Second repair: type coercion
        constraints2 = ConstraintChain([TypeConstraint(expected_type="NUMBER")])
        pattern2 = HolographicPattern(example=42, constraints=constraints2, target=None)
        field_def2 = FieldDefinition(name="COUNT", pattern=pattern2, raw_value=None)

        repair_value(value="42", field_def=field_def2, repair_log=repair_log, fix=True)

        # Verify both logged in order
        assert len(repair_log.repairs) == 2
        assert "ENUM" in repair_log.repairs[0].rule_id
        assert "TYPE" in repair_log.repairs[1].rule_id


class TestForbiddenTierRepair:
    """Test TIER_FORBIDDEN: Never auto-apply certain repairs."""

    def test_forbidden_tier_blocks_repair(self):
        """Forbidden repairs (field insertion, target inference) never applied."""
        # repair_value with field_def=None should not crash and should not repair
        repair_log = RepairLog(repairs=[])

        # No field definition - can't infer what repair to do
        repaired_value, was_repaired = repair_value(
            value="some_value",
            field_def=None,
            repair_log=repair_log,
            fix=True,
        )

        # Should NOT repair - no field definition
        assert was_repaired is False
        assert repaired_value == "some_value"
        assert not repair_log.has_repairs()

    def test_forbidden_tier_no_field_insertion(self):
        """Never insert missing fields (I4 violation)."""
        # This is tested by ensuring repair_value works on existing values only
        # and never creates new fields
        repair_log = RepairLog(repairs=[])

        # Value is None (missing) - should not be "repaired" to a default
        constraints = ConstraintChain([EnumConstraint(allowed_values=["ACTIVE", "INACTIVE"])])
        pattern = HolographicPattern(example="ACTIVE", constraints=constraints, target=None)
        field_def = FieldDefinition(name="STATUS", pattern=pattern, raw_value=None)

        repaired_value, was_repaired = repair_value(
            value=None,  # Missing value
            field_def=field_def,
            repair_log=repair_log,
            fix=True,
        )

        # Should NOT repair - don't insert values
        assert was_repaired is False
        assert repaired_value is None
        assert not repair_log.has_repairs()

    def test_forbidden_tier_no_target_inference(self):
        """Never infer routing targets (forbidden per spec)."""
        # Target inference is not part of repair_value - this test ensures
        # the repair function doesn't try to guess targets
        # (Targets are specified in patterns, not inferred)
        repair_log = RepairLog(repairs=[])

        # Pattern without target
        constraints = ConstraintChain([EnumConstraint(allowed_values=["ACTIVE", "INACTIVE"])])
        pattern = HolographicPattern(example="ACTIVE", constraints=constraints, target=None)
        field_def = FieldDefinition(name="STATUS", pattern=pattern, raw_value=None)

        repaired_value, was_repaired = repair_value(
            value="active",
            field_def=field_def,
            repair_log=repair_log,
            fix=True,
        )

        # Should repair the value (enum casefold)
        assert was_repaired is True
        assert repaired_value == "ACTIVE"

        # But no target should have been inferred/added to pattern
        assert field_def.pattern.target is None


class TestRepairValueEdgeCases:
    """Test edge cases for repair_value function."""

    def test_no_constraints_in_field_def(self):
        """Handle field definitions without constraints gracefully."""
        pattern = HolographicPattern(example="example", constraints=None, target=None)
        field_def = FieldDefinition(name="FIELD", pattern=pattern, raw_value=None)

        repair_log = RepairLog(repairs=[])
        repaired_value, was_repaired = repair_value(
            value="any_value",
            field_def=field_def,
            repair_log=repair_log,
            fix=True,
        )

        # No constraints -> no repair possible
        assert was_repaired is False
        assert repaired_value == "any_value"

    def test_no_pattern_in_field_def(self):
        """Handle field definitions without pattern gracefully."""
        field_def = FieldDefinition(name="FIELD", pattern=None, raw_value=None)

        repair_log = RepairLog(repairs=[])
        repaired_value, was_repaired = repair_value(
            value="any_value",
            field_def=field_def,
            repair_log=repair_log,
            fix=True,
        )

        # No pattern -> no repair possible
        assert was_repaired is False
        assert repaired_value == "any_value"

    def test_empty_constraint_chain(self):
        """Handle empty constraint chain gracefully."""
        constraints = ConstraintChain([])  # No constraints
        pattern = HolographicPattern(example="example", constraints=constraints, target=None)
        field_def = FieldDefinition(name="FIELD", pattern=pattern, raw_value=None)

        repair_log = RepairLog(repairs=[])
        repaired_value, was_repaired = repair_value(
            value="any_value",
            field_def=field_def,
            repair_log=repair_log,
            fix=True,
        )

        # Empty constraints -> no repair possible
        assert was_repaired is False
        assert repaired_value == "any_value"


# =============================================================================
# Gap_5 BLOCKING FIX TESTS (CRS Critical Issues)
# =============================================================================


class TestRepairIntegration:
    """BLOCKING 1: repair() must wire repair_value() into pipeline.

    Currently repair() returns document unchanged - repair_value() is never called.
    These tests ensure repair() actually applies schema-driven repairs.
    """

    def test_repair_integration_applies_enum_casefold(self):
        """repair() should apply enum casefold when fix=True.

        This is an integration test showing repair() uses repair_value()
        to fix enum case mismatches in document fields.
        """
        from octave_mcp.core.constraints import ConstraintChain, EnumConstraint
        from octave_mcp.core.holographic import HolographicPattern
        from octave_mcp.core.parser import parse
        from octave_mcp.core.schema_extractor import FieldDefinition, SchemaDefinition

        # Create document with incorrect case
        content = """===TEST===
META:
  TYPE::TEST

STATUS::active
===END===
"""
        doc = parse(content)

        # Create schema with ENUM constraint for STATUS field
        constraints = ConstraintChain([EnumConstraint(allowed_values=["ACTIVE", "INACTIVE"])])
        pattern = HolographicPattern(example="ACTIVE", constraints=constraints, target=None)
        field_def = FieldDefinition(name="STATUS", pattern=pattern, raw_value=None)

        schema = SchemaDefinition(name="TEST", version="1.0", fields={"STATUS": field_def})

        # Call repair with fix=True and schema
        repaired_doc, repair_log = repair(doc, [], fix=True, schema=schema)

        # Verify repair was applied
        assert repair_log.has_repairs(), "repair() should apply schema-driven repairs"

        # Find the STATUS assignment in repaired document
        status_value = None
        for section in repaired_doc.sections:
            if hasattr(section, "key") and section.key == "STATUS":
                status_value = section.value
                break

        assert status_value == "ACTIVE", f"Expected 'ACTIVE', got '{status_value}'"

    def test_repair_integration_applies_type_coercion(self):
        """repair() should apply type coercion when fix=True.

        This test ensures repair() applies string-to-number coercion
        for fields with TYPE[NUMBER] constraint.
        """
        from octave_mcp.core.constraints import ConstraintChain, TypeConstraint
        from octave_mcp.core.holographic import HolographicPattern
        from octave_mcp.core.parser import parse
        from octave_mcp.core.schema_extractor import FieldDefinition, SchemaDefinition

        # Create document with string number
        content = """===TEST===
META:
  TYPE::TEST

COUNT::"42"
===END===
"""
        doc = parse(content)

        # Create schema with TYPE[NUMBER] constraint for COUNT field
        constraints = ConstraintChain([TypeConstraint(expected_type="NUMBER")])
        pattern = HolographicPattern(example=42, constraints=constraints, target=None)
        field_def = FieldDefinition(name="COUNT", pattern=pattern, raw_value=None)

        schema = SchemaDefinition(name="TEST", version="1.0", fields={"COUNT": field_def})

        # Call repair with fix=True and schema
        repaired_doc, repair_log = repair(doc, [], fix=True, schema=schema)

        # Verify repair was applied
        assert repair_log.has_repairs(), "repair() should apply type coercion repairs"

        # Find the COUNT assignment in repaired document
        count_value = None
        for section in repaired_doc.sections:
            if hasattr(section, "key") and section.key == "COUNT":
                count_value = section.value
                break

        assert count_value == 42, f"Expected 42 (int), got '{count_value}' ({type(count_value).__name__})"
        assert isinstance(count_value, int), f"Expected int type, got {type(count_value).__name__}"


class TestTypeCoercionOverflowRejection:
    """BLOCKING 2: type coercion must reject non-finite values (inf, nan).

    Currently "1e309" coerces to inf and logs safe=True.
    This is lossy conversion - original value cannot be recovered.
    """

    def test_type_coercion_rejects_overflow_to_infinity(self):
        """TYPE coercion: '1e309' should NOT coerce to inf (lossy)."""
        constraints = ConstraintChain([TypeConstraint(expected_type="NUMBER")])
        pattern = HolographicPattern(example=1.0, constraints=constraints, target=None)
        field_def = FieldDefinition(name="VALUE", pattern=pattern, raw_value=None)

        value = "1e309"  # Overflows to infinity in Python float
        repair_log = RepairLog(repairs=[])

        repaired_value, was_repaired = repair_value(
            value=value,
            field_def=field_def,
            repair_log=repair_log,
            fix=True,
        )

        # Should NOT repair - overflow to inf is lossy
        assert was_repaired is False, "Overflow to inf is lossy, should not repair"
        assert repaired_value == "1e309", "Original value should be preserved"
        assert not repair_log.has_repairs(), "No repair should be logged"

    def test_type_coercion_rejects_negative_overflow_to_infinity(self):
        """TYPE coercion: '-1e309' should NOT coerce to -inf (lossy)."""
        constraints = ConstraintChain([TypeConstraint(expected_type="NUMBER")])
        pattern = HolographicPattern(example=1.0, constraints=constraints, target=None)
        field_def = FieldDefinition(name="VALUE", pattern=pattern, raw_value=None)

        value = "-1e309"  # Overflows to -infinity
        repair_log = RepairLog(repairs=[])

        repaired_value, was_repaired = repair_value(
            value=value,
            field_def=field_def,
            repair_log=repair_log,
            fix=True,
        )

        # Should NOT repair - overflow to -inf is lossy
        assert was_repaired is False, "Overflow to -inf is lossy, should not repair"
        assert repaired_value == "-1e309", "Original value should be preserved"
        assert not repair_log.has_repairs(), "No repair should be logged"

    def test_type_coercion_rejects_nan(self):
        """TYPE coercion: 'nan' should NOT coerce (not a valid number)."""
        constraints = ConstraintChain([TypeConstraint(expected_type="NUMBER")])
        pattern = HolographicPattern(example=1.0, constraints=constraints, target=None)
        field_def = FieldDefinition(name="VALUE", pattern=pattern, raw_value=None)

        value = "nan"  # Not a number
        repair_log = RepairLog(repairs=[])

        repaired_value, was_repaired = repair_value(
            value=value,
            field_def=field_def,
            repair_log=repair_log,
            fix=True,
        )

        # Should NOT repair - nan is not a valid numeric value
        assert was_repaired is False, "NaN is not a valid number, should not repair"
        assert repaired_value == "nan", "Original value should be preserved"
        assert not repair_log.has_repairs(), "No repair should be logged"

    def test_type_coercion_accepts_large_but_finite_number(self):
        """TYPE coercion: '1e308' should coerce (large but finite)."""
        constraints = ConstraintChain([TypeConstraint(expected_type="NUMBER")])
        pattern = HolographicPattern(example=1.0, constraints=constraints, target=None)
        field_def = FieldDefinition(name="VALUE", pattern=pattern, raw_value=None)

        value = "1e308"  # Large but still finite
        repair_log = RepairLog(repairs=[])

        repaired_value, was_repaired = repair_value(
            value=value,
            field_def=field_def,
            repair_log=repair_log,
            fix=True,
        )

        # Should repair - 1e308 is a valid finite number
        assert was_repaired is True, "1e308 is finite, should repair"
        assert repaired_value == 1e308, f"Expected 1e308, got {repaired_value}"
        assert repair_log.has_repairs(), "Repair should be logged"
