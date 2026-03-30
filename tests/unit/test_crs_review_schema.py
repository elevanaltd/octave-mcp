"""Tests for CRS_REVIEW schema (Issue #342).

Validates the CRS_REVIEW schema for structured code review artifacts.
This schema replaces verbose markdown PR comments with compact OCTAVE output
for the HestAI review gate system.

TDD RED phase: These tests should fail until the schema is implemented.
"""

import pytest

from octave_mcp.core.constraints import EnumConstraint
from octave_mcp.core.parser import parse
from octave_mcp.core.schema_extractor import SchemaDefinition
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
    """Test that CRS_REVIEW schema defines correct fields."""

    @pytest.fixture
    def schema(self) -> SchemaDefinition:
        """Load the CRS_REVIEW schema."""
        s = load_schema_by_name("CRS_REVIEW")
        assert s is not None, "CRS_REVIEW schema must be loadable"
        return s

    def test_type_field_defined(self, schema: SchemaDefinition):
        """Schema should define TYPE field."""
        assert "TYPE" in schema.fields

    def test_type_field_is_required(self, schema: SchemaDefinition):
        """TYPE field should be required."""
        assert schema.fields["TYPE"].is_required

    def test_version_field_defined(self, schema: SchemaDefinition):
        """Schema should define VERSION field."""
        assert "VERSION" in schema.fields

    def test_version_field_is_required(self, schema: SchemaDefinition):
        """VERSION field should be required."""
        assert schema.fields["VERSION"].is_required

    def test_schema_version_field_defined(self, schema: SchemaDefinition):
        """Schema should define SCHEMA_VERSION field."""
        assert "SCHEMA_VERSION" in schema.fields

    def test_schema_version_field_is_required(self, schema: SchemaDefinition):
        """SCHEMA_VERSION field should be required."""
        assert schema.fields["SCHEMA_VERSION"].is_required


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

    def test_policy_unknown_fields_reject(self, schema: SchemaDefinition):
        """POLICY should REJECT unknown fields for strict review artifacts."""
        assert schema.policy.unknown_fields == "REJECT"

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
        # Schema defines TYPE with ENUM constraint
        type_field = schema.fields.get("TYPE")
        assert type_field is not None
        if type_field.pattern and type_field.pattern.constraints:
            # Verify ENUM includes CRS_REVIEW
            for constraint in type_field.pattern.constraints.constraints:
                if isinstance(constraint, EnumConstraint):
                    assert "CRS_REVIEW" in constraint.allowed_values

    def test_schema_type_field_has_enum_constraint(self, schema: SchemaDefinition):
        """TYPE field should have ENUM constraint with CRS_REVIEW."""
        from octave_mcp.core.constraints import EnumConstraint

        type_field = schema.fields.get("TYPE")
        assert type_field is not None
        assert type_field.pattern is not None
        assert type_field.pattern.constraints is not None

        enum_constraints = [c for c in type_field.pattern.constraints.constraints if isinstance(c, EnumConstraint)]
        assert len(enum_constraints) == 1
        assert "CRS_REVIEW" in enum_constraints[0].allowed_values


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
