"""Tests for GH#344: Validator false positive TYPE/VERSION missing in META block.

Reproduction test: When TYPE and VERSION are correctly nested inside a META:
block, the validator should NOT report E003 errors for these fields.

Root cause: _check_required_field_coverage() in validate.py only checks
section_schemas (built from doc.sections) for field coverage. Fields in
doc.meta (like TYPE and VERSION) are not considered, causing false E003
errors when the schema's FIELDS block defines TYPE/VERSION with REQ constraint.
"""

import pytest

from octave_mcp.core.parser import parse
from octave_mcp.core.validator import validate
from octave_mcp.mcp.validate import (
    _build_deep_section_schemas,
    _check_required_field_coverage,
)
from octave_mcp.schemas.loader import load_schema_by_name

# Document with TYPE and VERSION correctly inside META block
VALID_SKILL_DOC = """\
===TEST_SKILL===
META:
  TYPE::SKILL
  VERSION::"1.0.0"
  STATUS::ACTIVE
  PURPOSE::"Test OCTAVE file demonstrating literacy concepts"
===END===
"""


class TestGH344MetaFieldFalsePositive:
    """GH#344: TYPE/VERSION in META block should not produce false E003 errors."""

    @pytest.fixture
    def skill_schema(self):
        """Load the SKILL schema which defines TYPE and VERSION in FIELDS."""
        schema = load_schema_by_name("SKILL")
        assert schema is not None, "SKILL schema must be loadable"
        return schema

    def test_skill_schema_has_type_and_version_in_fields(self, skill_schema):
        """Precondition: SKILL schema defines TYPE and VERSION as required fields."""
        assert "TYPE" in skill_schema.fields, "SKILL schema must define TYPE in FIELDS"
        assert "VERSION" in skill_schema.fields, "SKILL schema must define VERSION in FIELDS"
        assert skill_schema.fields["TYPE"].is_required, "TYPE must be required"
        assert skill_schema.fields["VERSION"].is_required, "VERSION must be required"

    def test_meta_type_and_version_present_in_parsed_doc(self):
        """Precondition: parser correctly places TYPE/VERSION in doc.meta."""
        doc = parse(VALID_SKILL_DOC)
        assert doc.meta.get("TYPE") == "SKILL", "TYPE should be in doc.meta"
        assert doc.meta.get("VERSION") is not None, "VERSION should be in doc.meta"

    def test_check_required_field_coverage_no_false_positive(self, skill_schema):
        """GH#344 reproduction: _check_required_field_coverage should NOT flag
        TYPE/VERSION as missing when they exist in doc.meta.

        This is the core bug: _check_required_field_coverage only checks
        section_schemas for coverage, but TYPE/VERSION are in doc.meta,
        not in sections.
        """
        doc = parse(VALID_SKILL_DOC)
        section_schemas = _build_deep_section_schemas(doc, skill_schema)

        coverage_errors = _check_required_field_coverage(skill_schema, section_schemas, doc=doc)

        e003_errors = [e for e in coverage_errors if e.code == "E003"]
        error_fields = [e.field_path for e in e003_errors]
        assert len(e003_errors) == 0, (
            f"False positive E003 errors for META fields: {error_fields}. "
            f"TYPE and VERSION are present in META block and should not be "
            f"reported as missing."
        )

    def test_full_validation_no_false_positive_for_skill(self, skill_schema):
        """End-to-end: validating a valid SKILL document should not produce
        E003 errors for TYPE or VERSION.
        """
        doc = parse(VALID_SKILL_DOC)
        section_schemas = _build_deep_section_schemas(doc, skill_schema)

        # Run validator
        errors = validate(doc, strict=False, section_schemas=section_schemas)

        # Also run coverage check (as validate.py does)
        coverage_errors = _check_required_field_coverage(skill_schema, section_schemas, doc=doc)
        all_errors = errors + coverage_errors

        e003_errors = [e for e in all_errors if e.code == "E003"]
        error_fields = [e.field_path for e in e003_errors]
        assert len(e003_errors) == 0, (
            f"False positive E003 errors: {error_fields}. "
            f"A valid SKILL document with TYPE and VERSION in META block "
            f"should not produce E003 errors."
        )

    def test_truly_missing_required_field_still_detected(self, skill_schema):
        """Negative test: a document ACTUALLY missing a required field should
        still get E003. The fix must not suppress legitimate errors.
        """
        # Document missing VERSION entirely
        doc_missing_version = """\
===TEST_SKILL===
META:
  TYPE::SKILL
  STATUS::ACTIVE
===END===
"""
        doc = parse(doc_missing_version)
        section_schemas = _build_deep_section_schemas(doc, skill_schema)

        coverage_errors = _check_required_field_coverage(skill_schema, section_schemas, doc=doc)

        # VERSION is truly missing - should still be flagged
        version_errors = [e for e in coverage_errors if e.code == "E003" and "VERSION" in e.field_path]
        assert len(version_errors) > 0, "VERSION is truly missing and should be flagged as E003"

    def test_meta_field_present_in_section_not_meta(self, skill_schema):
        """Edge case: a field named TYPE in a section (not META) should be
        covered by section_schemas normally, not by the META check.
        """
        # A document where TYPE appears both in META and in a section
        doc_with_section_type = """\
===TEST_SKILL===
META:
  TYPE::SKILL
  VERSION::"1.0.0"
  STATUS::ACTIVE
SECTION_DATA:
  TYPE::SKILL
  VERSION::"1.0.0"
===END===
"""
        doc = parse(doc_with_section_type)
        section_schemas = _build_deep_section_schemas(doc, skill_schema)

        coverage_errors = _check_required_field_coverage(skill_schema, section_schemas, doc=doc)

        e003_errors = [e for e in coverage_errors if e.code == "E003"]
        assert len(e003_errors) == 0, (
            f"No E003 errors expected when fields are in both META and sections: "
            f"{[e.field_path for e in e003_errors]}"
        )
