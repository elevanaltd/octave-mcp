"""Tests for CRS_REVIEW schema (Issue #342).

Validates the CRS_REVIEW schema for structured code review artifacts.
This schema replaces verbose markdown PR comments with compact OCTAVE output
for the HestAI review gate system.

Tests are organized as:
  S1-S3: Schema loading and field definition (parse-level)
  S4:    Document parsing (parser-level)
  S5:    Schema validation against documents (parser + inspector)
  S6:    Edge cases
  S7:    Integration tests calling the validator end-to-end
  S8:    Negative tests for invalid documents
"""

import pytest

from octave_mcp.core.constraints import EnumConstraint
from octave_mcp.core.parser import parse
from octave_mcp.core.schema_extractor import SchemaDefinition
from octave_mcp.core.validator import validate
from octave_mcp.mcp.validate import _build_deep_section_schemas, _check_required_field_coverage
from octave_mcp.schemas.loader import load_builtin_schemas, load_schema_by_name

# ---------------------------------------------------------------------------
# §1: Schema file loads correctly
# ---------------------------------------------------------------------------


class TestCrsReviewSchemaLoading:
    """Test that CRS_REVIEW schema loads from builtin directory."""

    def test_load_by_name_returns_schema(self):
        """load_schema_by_name('CRS_REVIEW') should return a SchemaDefinition."""
        schema = load_schema_by_name("CRS_REVIEW")
        assert schema is not None
        assert isinstance(schema, SchemaDefinition)

    def test_schema_name_is_crs_review(self):
        """Loaded schema should have name CRS_REVIEW_SCHEMA or envelope name."""
        schema = load_schema_by_name("CRS_REVIEW")
        assert schema is not None
        # The envelope name in the .oct.md file
        assert "CRS_REVIEW" in schema.name

    def test_schema_has_version(self):
        """Schema should have a version defined."""
        schema = load_schema_by_name("CRS_REVIEW")
        assert schema is not None
        assert schema.version is not None

    def test_schema_in_builtin_schemas(self):
        """CRS_REVIEW should appear in load_builtin_schemas() output."""
        schemas = load_builtin_schemas()
        # Find the CRS_REVIEW schema by checking keys
        crs_keys = [k for k in schemas if "CRS_REVIEW" in k]
        assert len(crs_keys) > 0, f"CRS_REVIEW not found in builtin schemas. Available: {list(schemas.keys())}"


# ---------------------------------------------------------------------------
# §2: Schema defines expected META fields
# ---------------------------------------------------------------------------


class TestCrsReviewSchemaFields:
    """Test that CRS_REVIEW schema defines correct section-level fields.

    META fields (TYPE, VERSION, SCHEMA_VERSION) are validated separately
    by the META block validator, not via the FIELDS block. Section-level
    fields are defined in FIELDS for _build_deep_section_schemas() to
    distribute across document sections.
    """

    @pytest.fixture
    def schema(self) -> SchemaDefinition:
        """Load the CRS_REVIEW schema."""
        s = load_schema_by_name("CRS_REVIEW")
        assert s is not None, "CRS_REVIEW schema must be loadable"
        return s

    def test_verdict_field_defined(self, schema: SchemaDefinition):
        """Schema should define VERDICT field for S1::VERDICT section."""
        assert "VERDICT" in schema.fields

    def test_verdict_field_is_required(self, schema: SchemaDefinition):
        """VERDICT field should be required."""
        assert schema.fields["VERDICT"].is_required

    def test_role_field_defined(self, schema: SchemaDefinition):
        """Schema should define ROLE field for S1::VERDICT section."""
        assert "ROLE" in schema.fields

    def test_role_field_is_required(self, schema: SchemaDefinition):
        """ROLE field should be required."""
        assert schema.fields["ROLE"].is_required

    def test_assessment_field_defined(self, schema: SchemaDefinition):
        """Schema should define ASSESSMENT field for S4::SUMMARY section."""
        assert "ASSESSMENT" in schema.fields

    def test_assessment_field_is_required(self, schema: SchemaDefinition):
        """ASSESSMENT field should be required."""
        assert schema.fields["ASSESSMENT"].is_required


# ---------------------------------------------------------------------------
# §3: Schema POLICY configuration
# ---------------------------------------------------------------------------


class TestCrsReviewSchemaPolicy:
    """Test CRS_REVIEW schema POLICY block."""

    @pytest.fixture
    def schema(self) -> SchemaDefinition:
        """Load the CRS_REVIEW schema."""
        s = load_schema_by_name("CRS_REVIEW")
        assert s is not None
        return s

    def test_policy_has_version(self, schema: SchemaDefinition):
        """POLICY should declare version."""
        assert schema.policy.version is not None

    def test_policy_unknown_fields_warn(self, schema: SchemaDefinition):
        """POLICY should WARN on unknown fields.

        WARN is used because the schema defines fields across multiple sections
        (VERDICT, DISTRIBUTION, SUMMARY). Per-section validation only sees the
        subset of fields present in each section, so fields from other sections
        would be falsely flagged as unknown under REJECT.
        """
        assert schema.policy.unknown_fields == "WARN"

    def test_policy_defines_targets(self, schema: SchemaDefinition):
        """POLICY should define section targets for VERDICT, DISTRIBUTION, FINDINGS, SUMMARY."""
        expected_sections = {"VERDICT", "DISTRIBUTION", "FINDINGS", "SUMMARY"}
        actual_targets = set(schema.policy.targets)
        assert expected_sections.issubset(actual_targets), (
            f"Missing targets: {expected_sections - actual_targets}. " f"Got: {actual_targets}"
        )


# ---------------------------------------------------------------------------
# §4: Valid CRS_REVIEW document parses correctly
# ---------------------------------------------------------------------------


VALID_CRS_REVIEW_DOC = """\
===CRS_REVIEW===
META:
  TYPE::CRS_REVIEW
  VERSION::"1.0.0"
  SCHEMA_VERSION::"1"

§1::VERDICT
  ROLE::CRS
  PROVIDER::"claude-opus-4-6"
  VERDICT::BLOCKED
  SHA::"abc1234"
  TIER::T2

§2::DISTRIBUTION
  TOTAL::3
  BLOCKING::1
  TRIAGED::true
  OMITTED::0
  P0::1
  P1::1
  P2::1
  P3::0
  P4::0
  P5::0

§3::FINDINGS
  [tier::P0,confidence::CERTAIN,file::"Utils/Diagnostics.swift",line::"13",category::security,issue::"Command injection via unsanitized host parameter",impact::"Full server compromise",fix::"Use Process with separate arguments array"]
  [tier::P1,confidence::HIGH,file::"Data/DatabaseManager.swift",line::"24-41",category::security,issue::"SQL injection via string interpolation",impact::"Data exfiltration possible",fix::"Use parameterized queries"]
  [tier::P2,confidence::MODERATE,file::"Services/TradingService.swift",line::"27-58",category::reliability,issue::"Race condition on account balances",impact::"Incorrect balance calculations under concurrency",fix::"Add actor isolation or mutex"]

§4::SUMMARY
  ASSESSMENT::"System exhibits critical security and concurrency failures"
  TOP_RISKS::[
    "Remote code execution via command injection (Diagnostics.swift:13)",
    "SQL injection across data layer (DatabaseManager.swift:24-41)",
    "Race condition on account balances (TradingService.swift:27-58)"
  ]

===END===
"""

VALID_CRS_REVIEW_APPROVED = """\
===CRS_REVIEW===
META:
  TYPE::CRS_REVIEW
  VERSION::"1.0.0"
  SCHEMA_VERSION::"1"

§1::VERDICT
  ROLE::CRS
  PROVIDER::"gemini-2.5-pro"
  VERDICT::APPROVED
  SHA::"def5678"
  TIER::T1

§2::DISTRIBUTION
  TOTAL::0
  BLOCKING::0
  TRIAGED::false
  OMITTED::0
  P0::0
  P1::0
  P2::0
  P3::0
  P4::0
  P5::0

§3::FINDINGS

§4::SUMMARY
  ASSESSMENT::"No issues found in this change"
  TOP_RISKS::[]

===END===
"""


class TestCrsReviewDocumentParsing:
    """Test that valid CRS_REVIEW documents parse correctly."""

    def test_valid_blocked_review_parses(self):
        """A valid BLOCKED review document should parse without errors."""
        doc = parse(VALID_CRS_REVIEW_DOC)
        assert doc is not None
        assert doc.name == "CRS_REVIEW"

    def test_valid_blocked_review_has_meta(self):
        """Parsed document should have correct META fields."""
        doc = parse(VALID_CRS_REVIEW_DOC)
        assert doc.meta is not None
        assert doc.meta.get("TYPE") == "CRS_REVIEW"

    def test_valid_blocked_review_has_sections(self):
        """Parsed document should have sections for VERDICT, DISTRIBUTION, FINDINGS, SUMMARY."""
        doc = parse(VALID_CRS_REVIEW_DOC)
        # Document should have at least 4 sections (VERDICT, DISTRIBUTION, FINDINGS, SUMMARY)
        assert len(doc.sections) >= 4

    def test_valid_approved_review_parses(self):
        """A valid APPROVED review with empty findings should parse."""
        doc = parse(VALID_CRS_REVIEW_APPROVED)
        assert doc is not None
        assert doc.name == "CRS_REVIEW"

    def test_valid_approved_review_has_meta(self):
        """APPROVED review should have correct META."""
        doc = parse(VALID_CRS_REVIEW_APPROVED)
        assert doc.meta is not None
        assert doc.meta.get("TYPE") == "CRS_REVIEW"


# ---------------------------------------------------------------------------
# §5: Schema validation of documents
# ---------------------------------------------------------------------------


class TestCrsReviewSchemaValidation:
    """Test schema validation of CRS_REVIEW documents.

    These tests verify that the schema can be used with the validator
    to check documents against the CRS_REVIEW contract.
    """

    @pytest.fixture
    def schema(self) -> SchemaDefinition:
        """Load the CRS_REVIEW schema."""
        s = load_schema_by_name("CRS_REVIEW")
        assert s is not None
        return s

    def test_valid_document_meta_type_matches(self, schema: SchemaDefinition):
        """Document TYPE field should match schema expectation."""
        doc = parse(VALID_CRS_REVIEW_DOC)
        # TYPE field in META should be CRS_REVIEW
        assert doc.meta.get("TYPE") == "CRS_REVIEW"

    def test_schema_verdict_field_has_enum_constraint(self, schema: SchemaDefinition):
        """VERDICT field should have ENUM constraint with APPROVED, BLOCKED, CONDITIONAL."""
        verdict_field = schema.fields.get("VERDICT")
        assert verdict_field is not None
        assert verdict_field.pattern is not None
        assert verdict_field.pattern.constraints is not None

        enum_constraints = [c for c in verdict_field.pattern.constraints.constraints if isinstance(c, EnumConstraint)]
        assert len(enum_constraints) == 1
        assert "APPROVED" in enum_constraints[0].allowed_values
        assert "BLOCKED" in enum_constraints[0].allowed_values
        assert "CONDITIONAL" in enum_constraints[0].allowed_values


# ---------------------------------------------------------------------------
# §6: Edge cases and error handling
# ---------------------------------------------------------------------------


class TestCrsReviewEdgeCases:
    """Test edge cases for CRS_REVIEW schema and documents."""

    def test_findings_with_line_range(self):
        """Finding with line range (e.g., '27-58') should parse correctly."""
        doc = parse(VALID_CRS_REVIEW_DOC)
        assert doc is not None
        # The document should parse without errors even with line ranges

    def test_empty_findings_section(self):
        """An APPROVED review with empty FINDINGS should parse."""
        doc = parse(VALID_CRS_REVIEW_APPROVED)
        assert doc is not None

    def test_document_with_all_priority_tiers(self):
        """Document with findings across P0-P5 should parse."""
        doc_text = """\
===CRS_REVIEW===
META:
  TYPE::CRS_REVIEW
  VERSION::"1.0.0"
  SCHEMA_VERSION::"1"

§1::VERDICT
  ROLE::CRS
  PROVIDER::"claude-opus-4-6"
  VERDICT::BLOCKED
  SHA::"aaa1111"
  TIER::T3

§2::DISTRIBUTION
  TOTAL::6
  BLOCKING::2
  TRIAGED::true
  OMITTED::0
  P0::1
  P1::1
  P2::1
  P3::1
  P4::1
  P5::1

§3::FINDINGS
  [tier::P0,confidence::CERTAIN,file::"auth.py",line::"10",category::security,issue::"Hardcoded secret",impact::"Credential exposure",fix::"Use environment variable"]
  [tier::P1,confidence::HIGH,file::"db.py",line::"20",category::correctness,issue::"Null dereference",impact::"Runtime crash",fix::"Add null check"]
  [tier::P2,confidence::HIGH,file::"api.py",line::"30-35",category::reliability,issue::"Unhandled exception",impact::"500 error in production",fix::"Add try-except block"]
  [tier::P3,confidence::MODERATE,file::"models.py",line::"40",category::architecture,issue::"God object pattern",impact::"Maintenance burden",fix::"Extract responsibilities"]
  [tier::P4,confidence::MODERATE,file::"utils.py",line::"50",category::performance,issue::"N+1 query",impact::"Slow page load",fix::"Use eager loading"]
  [tier::P5,confidence::MODERATE,file::"views.py",line::"60",category::style,issue::"Inconsistent naming",impact::"Readability",fix::"Follow naming convention"]

§4::SUMMARY
  ASSESSMENT::"Multiple issues across all severity tiers"
  TOP_RISKS::[
    "Hardcoded credentials in auth.py",
    "Null dereference in db.py",
    "Unhandled exceptions in api.py"
  ]

===END===
"""
        doc = parse(doc_text)
        assert doc is not None
        assert doc.name == "CRS_REVIEW"

    def test_schema_loads_without_warnings(self):
        """Schema should load cleanly without extraction warnings."""
        schema = load_schema_by_name("CRS_REVIEW")
        assert schema is not None
        assert len(schema.warnings) == 0, f"Schema has warnings: {[w.message for w in schema.warnings]}"


# ---------------------------------------------------------------------------
# S7: Integration tests -- validator end-to-end
# ---------------------------------------------------------------------------


class TestCrsReviewValidatorIntegration:
    """Integration tests that exercise the actual validator, not just the parser.

    These tests verify that octave_validate with schema=CRS_REVIEW works
    end-to-end on valid and invalid documents.
    """

    @pytest.fixture
    def schema(self) -> SchemaDefinition:
        """Load the CRS_REVIEW schema."""
        s = load_schema_by_name("CRS_REVIEW")
        assert s is not None
        return s

    def test_valid_blocked_review_validates_without_errors(self, schema: SchemaDefinition):
        """A valid BLOCKED review should produce zero validation errors."""
        doc = parse(VALID_CRS_REVIEW_DOC)
        section_schemas = _build_deep_section_schemas(doc, schema)
        errors = validate(doc, strict=False, section_schemas=section_schemas)
        error_messages = [f"{e.code}: {e.message} ({e.field_path})" for e in errors]
        assert len(errors) == 0, f"Expected no validation errors but got: {error_messages}"

    def test_valid_approved_review_validates_without_errors(self, schema: SchemaDefinition):
        """A valid APPROVED review should produce zero validation errors."""
        doc = parse(VALID_CRS_REVIEW_APPROVED)
        section_schemas = _build_deep_section_schemas(doc, schema)
        errors = validate(doc, strict=False, section_schemas=section_schemas)
        error_messages = [f"{e.code}: {e.message} ({e.field_path})" for e in errors]
        assert len(errors) == 0, f"Expected no validation errors but got: {error_messages}"

    def test_build_deep_section_schemas_non_empty(self, schema: SchemaDefinition):
        """_build_deep_section_schemas should return non-empty dict for CRS_REVIEW."""
        doc = parse(VALID_CRS_REVIEW_DOC)
        section_schemas = _build_deep_section_schemas(doc, schema)
        assert len(section_schemas) > 0, (
            "_build_deep_section_schemas returned empty dict -- "
            "schema must define section-level fields that match document assignments"
        )

    def test_required_field_coverage_valid_document(self, schema: SchemaDefinition):
        """Required field coverage check should pass for a valid document."""
        doc = parse(VALID_CRS_REVIEW_DOC)
        section_schemas = _build_deep_section_schemas(doc, schema)
        coverage_errors = _check_required_field_coverage(schema, section_schemas)
        error_messages = [f"{e.code}: {e.message}" for e in coverage_errors]
        assert len(coverage_errors) == 0, f"Coverage errors: {error_messages}"

    def test_schema_defines_verdict_section_fields(self, schema: SchemaDefinition):
        """Schema FIELDS should include VERDICT section fields (ROLE, VERDICT, SHA, TIER)."""
        # These fields appear in S1::VERDICT and must be defined in schema FIELDS
        assert "VERDICT" in schema.fields, "Schema must define VERDICT field"
        assert "ROLE" in schema.fields, "Schema must define ROLE field"
        assert "SHA" in schema.fields, "Schema must define SHA field"
        assert "TIER" in schema.fields, "Schema must define TIER field"

    def test_schema_defines_distribution_section_fields(self, schema: SchemaDefinition):
        """Schema FIELDS should include DISTRIBUTION section fields (TOTAL, BLOCKING)."""
        assert "TOTAL" in schema.fields, "Schema must define TOTAL field"
        assert "BLOCKING" in schema.fields, "Schema must define BLOCKING field"

    def test_schema_defines_summary_section_fields(self, schema: SchemaDefinition):
        """Schema FIELDS should include SUMMARY section fields (ASSESSMENT, TOP_RISKS)."""
        assert "ASSESSMENT" in schema.fields, "Schema must define ASSESSMENT field"
        assert "TOP_RISKS" in schema.fields, "Schema must define TOP_RISKS field"

    def test_verdict_field_has_enum_constraint(self, schema: SchemaDefinition):
        """VERDICT field should have ENUM constraint with APPROVED, BLOCKED, CONDITIONAL."""
        verdict_field = schema.fields.get("VERDICT")
        assert verdict_field is not None, "VERDICT field must be defined"
        assert verdict_field.pattern is not None
        assert verdict_field.pattern.constraints is not None
        enum_constraints = [c for c in verdict_field.pattern.constraints.constraints if isinstance(c, EnumConstraint)]
        assert len(enum_constraints) == 1, "VERDICT must have exactly one ENUM constraint"
        for val in ("APPROVED", "BLOCKED", "CONDITIONAL"):
            assert val in enum_constraints[0].allowed_values, f"{val} must be in VERDICT enum"

    def test_tier_field_has_enum_constraint(self, schema: SchemaDefinition):
        """TIER field should have ENUM constraint with T0-T4."""
        tier_field = schema.fields.get("TIER")
        assert tier_field is not None, "TIER field must be defined"
        assert tier_field.pattern is not None
        assert tier_field.pattern.constraints is not None
        enum_constraints = [c for c in tier_field.pattern.constraints.constraints if isinstance(c, EnumConstraint)]
        assert len(enum_constraints) == 1, "TIER must have exactly one ENUM constraint"
        for val in ("T0", "T1", "T2", "T3", "T4"):
            assert val in enum_constraints[0].allowed_values, f"{val} must be in TIER enum"


# ---------------------------------------------------------------------------
# S8: Negative tests -- invalid documents
# ---------------------------------------------------------------------------


class TestCrsReviewNegativeValidation:
    """Negative tests: invalid documents should produce validation errors.

    These tests ensure the validator catches constraint violations.
    """

    @pytest.fixture
    def schema(self) -> SchemaDefinition:
        """Load the CRS_REVIEW schema."""
        s = load_schema_by_name("CRS_REVIEW")
        assert s is not None
        return s

    def _validate_doc(self, content: str, schema: SchemaDefinition) -> list:
        """Helper: parse, build section schemas, validate, return errors."""
        doc = parse(content)
        section_schemas = _build_deep_section_schemas(doc, schema)
        errors = validate(doc, strict=False, section_schemas=section_schemas)
        # Also run required field coverage check
        coverage_errors = _check_required_field_coverage(schema, section_schemas)
        return errors + coverage_errors

    def test_invalid_verdict_value_rejected(self, schema: SchemaDefinition):
        """VERDICT with invalid value (e.g., 'MAYBE') should fail ENUM validation."""
        doc_text = (
            "===CRS_REVIEW===\n"
            "META:\n"
            "  TYPE::CRS_REVIEW\n"
            '  VERSION::"1.0.0"\n'
            '  SCHEMA_VERSION::"1"\n'
            "\n"
            "\u00a71::VERDICT\n"
            "  ROLE::CRS\n"
            '  PROVIDER::"test-model"\n'
            "  VERDICT::MAYBE\n"
            '  SHA::"abc1234"\n'
            "  TIER::T2\n"
            "\n"
            "\u00a72::DISTRIBUTION\n"
            "  TOTAL::0\n"
            "  BLOCKING::0\n"
            "  TRIAGED::false\n"
            "  OMITTED::0\n"
            "  P0::0\n"
            "  P1::0\n"
            "  P2::0\n"
            "  P3::0\n"
            "  P4::0\n"
            "  P5::0\n"
            "\n"
            "\u00a73::FINDINGS\n"
            "\n"
            "\u00a74::SUMMARY\n"
            '  ASSESSMENT::"Test"\n'
            "  TOP_RISKS::[]\n"
            "\n"
            "===END===\n"
        )
        errors = self._validate_doc(doc_text, schema)
        # Should have at least one error about invalid VERDICT value
        verdict_errors = [e for e in errors if "VERDICT" in e.field_path]
        assert len(verdict_errors) > 0, (
            f"Expected ENUM validation error for VERDICT::MAYBE but got none. "
            f"All errors: {[(e.code, e.message, e.field_path) for e in errors]}"
        )

    def test_invalid_tier_value_rejected(self, schema: SchemaDefinition):
        """TIER with invalid value (e.g., 'T9') should fail ENUM validation."""
        doc_text = (
            "===CRS_REVIEW===\n"
            "META:\n"
            "  TYPE::CRS_REVIEW\n"
            '  VERSION::"1.0.0"\n'
            '  SCHEMA_VERSION::"1"\n'
            "\n"
            "\u00a71::VERDICT\n"
            "  ROLE::CRS\n"
            '  PROVIDER::"test-model"\n'
            "  VERDICT::APPROVED\n"
            '  SHA::"abc1234"\n'
            "  TIER::T9\n"
            "\n"
            "\u00a72::DISTRIBUTION\n"
            "  TOTAL::0\n"
            "  BLOCKING::0\n"
            "  TRIAGED::false\n"
            "  OMITTED::0\n"
            "  P0::0\n"
            "  P1::0\n"
            "  P2::0\n"
            "  P3::0\n"
            "  P4::0\n"
            "  P5::0\n"
            "\n"
            "\u00a73::FINDINGS\n"
            "\n"
            "\u00a74::SUMMARY\n"
            '  ASSESSMENT::"Test"\n'
            "  TOP_RISKS::[]\n"
            "\n"
            "===END===\n"
        )
        errors = self._validate_doc(doc_text, schema)
        tier_errors = [e for e in errors if "TIER" in e.field_path]
        assert len(tier_errors) > 0, (
            f"Expected ENUM validation error for TIER::T9 but got none. "
            f"All errors: {[(e.code, e.message, e.field_path) for e in errors]}"
        )

    def test_missing_required_verdict_field_detected(self, schema: SchemaDefinition):
        """Missing required VERDICT field in section should be caught."""
        doc_text = (
            "===CRS_REVIEW===\n"
            "META:\n"
            "  TYPE::CRS_REVIEW\n"
            '  VERSION::"1.0.0"\n'
            '  SCHEMA_VERSION::"1"\n'
            "\n"
            "\u00a71::VERDICT\n"
            "  ROLE::CRS\n"
            '  PROVIDER::"test-model"\n'
            '  SHA::"abc1234"\n'
            "  TIER::T2\n"
            "\n"
            "\u00a72::DISTRIBUTION\n"
            "  TOTAL::0\n"
            "  BLOCKING::0\n"
            "  TRIAGED::false\n"
            "  OMITTED::0\n"
            "  P0::0\n"
            "  P1::0\n"
            "  P2::0\n"
            "  P3::0\n"
            "  P4::0\n"
            "  P5::0\n"
            "\n"
            "\u00a73::FINDINGS\n"
            "\n"
            "\u00a74::SUMMARY\n"
            '  ASSESSMENT::"Test"\n'
            "  TOP_RISKS::[]\n"
            "\n"
            "===END===\n"
        )
        errors = self._validate_doc(doc_text, schema)
        # Should have an E003 required field error for VERDICT
        req_errors = [e for e in errors if e.code == "E003" and "VERDICT" in e.message]
        assert len(req_errors) > 0, (
            f"Expected E003 required field error for missing VERDICT but got none. "
            f"All errors: {[(e.code, e.message, e.field_path) for e in errors]}"
        )

    def test_missing_required_assessment_field_detected(self, schema: SchemaDefinition):
        """Missing required ASSESSMENT field in SUMMARY section should be caught."""
        doc_text = (
            "===CRS_REVIEW===\n"
            "META:\n"
            "  TYPE::CRS_REVIEW\n"
            '  VERSION::"1.0.0"\n'
            '  SCHEMA_VERSION::"1"\n'
            "\n"
            "\u00a71::VERDICT\n"
            "  ROLE::CRS\n"
            '  PROVIDER::"test-model"\n'
            "  VERDICT::APPROVED\n"
            '  SHA::"abc1234"\n'
            "  TIER::T1\n"
            "\n"
            "\u00a72::DISTRIBUTION\n"
            "  TOTAL::0\n"
            "  BLOCKING::0\n"
            "  TRIAGED::false\n"
            "  OMITTED::0\n"
            "  P0::0\n"
            "  P1::0\n"
            "  P2::0\n"
            "  P3::0\n"
            "  P4::0\n"
            "  P5::0\n"
            "\n"
            "\u00a73::FINDINGS\n"
            "\n"
            "\u00a74::SUMMARY\n"
            "  TOP_RISKS::[]\n"
            "\n"
            "===END===\n"
        )
        errors = self._validate_doc(doc_text, schema)
        assessment_errors = [e for e in errors if "ASSESSMENT" in str(e.message) or "ASSESSMENT" in str(e.field_path)]
        assert len(assessment_errors) > 0, (
            f"Expected required field error for missing ASSESSMENT but got none. "
            f"All errors: {[(e.code, e.message, e.field_path) for e in errors]}"
        )
