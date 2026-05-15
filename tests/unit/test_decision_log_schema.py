"""Tests for DECISION_LOG schema validation (GH-425, WAVE_2 of pre-v1.13.0 Schema Sweep).

DECISIONS_OCTAVE_v20260417 documents (single-envelope OCTAVE with TYPE::DECISION_LOG)
declare a structured schema in their own META block — see reference document at
``/Volumes/HestAI-Projects/elevana-studio/.hestai/decisions/DECISIONS.oct.md``.

This module codifies that self-declared schema into a proper validator schema at
``src/octave_mcp/resources/specs/schemas/decision_log.oct.md``.

Per-decision entries carry:
- TOKEN: stable identifier (e.g., HO-MONOREPO-GOVERNANCE-20251107)
- TIER: ARCHITECTURAL | CONVENTION | MICRO
- STATUS: BINDING | ACTIVE | SUPERSEDED_BY_... | etc.
- DECISION: the decision essence (required except for stub/superseded entries)
- BECAUSE: rationale (required except for stub/superseded entries)
- Tier-conditional fields (ISSUE_REF for ARCHITECTURAL, ENFORCEMENT_REF for MICRO)
  validated by document conventions but ENUM-rejection cannot be relied upon at
  validator-test level per GH#435 (octave_validate ENUM constraints PARTIAL).

North Star compliance:
- I1 SYNTACTIC_FIDELITY: schema source is itself idempotent under octave_write
  (auto-covered by the glob in tests/integration/test_schema_write_idempotency.py).
- I4 TRANSFORM_AUDITABILITY: TDD commit sequence (RED → feat → GREEN) is the audit trail.
- I5 SCHEMA_SOVEREIGNTY: validation_status visible — INVALID for malformed,
  VALIDATED for well-formed.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from octave_mcp.mcp.validate import ValidateTool
from octave_mcp.schemas.loader import load_schema_by_name


def _validate_content(content: str) -> dict:
    """Validate ``content`` through the MCP validate tool against DECISION_LOG."""
    tool = ValidateTool()
    return asyncio.run(tool.execute(content=content, schema="DECISION_LOG"))


class TestDecisionLogSchemaLoading:
    """Test that the DECISION_LOG schema file exists and loads."""

    def test_decision_log_schema_file_exists(self) -> None:
        """Schema file should exist at the canonical specs/schemas/ location."""
        schema_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "octave_mcp"
            / "resources"
            / "specs"
            / "schemas"
            / "decision_log.oct.md"
        )
        assert schema_path.exists(), f"Schema file not found at {schema_path}"

    def test_load_decision_log_schema_by_name(self) -> None:
        """``load_schema_by_name`` should resolve DECISION_LOG to a SchemaDefinition."""
        schema = load_schema_by_name("DECISION_LOG")
        assert schema is not None, "Should find DECISION_LOG schema"
        assert schema.name == "DECISION_LOG"

    def test_decision_log_schema_has_version(self) -> None:
        """Schema should declare a version string."""
        schema = load_schema_by_name("DECISION_LOG")
        assert schema is not None
        assert schema.version is not None
        assert schema.version == "1.0"

    def test_decision_log_schema_has_required_fields(self) -> None:
        """Per GH-425, the per-entry SCHEMA_REQUIRED set is TOKEN/TIER/STATUS/DECISION/BECAUSE."""
        schema = load_schema_by_name("DECISION_LOG")
        assert schema is not None

        required_fields = ["TOKEN", "TIER", "STATUS", "DECISION", "BECAUSE"]
        for field_name in required_fields:
            assert field_name in schema.fields, f"Schema should declare {field_name} field"


class TestDecisionLogSchemaRejectsMalformed:
    """RED tests pinned to structural rejection (no reliance on ENUM rejection per GH#435)."""

    def test_decision_log_missing_required_field_is_invalid(self) -> None:
        """A decision-log document missing a SCHEMA_REQUIRED field MUST be INVALID.

        The minimal malformed corpus drops the ``TOKEN`` field, which is required
        by SCHEMA_REQUIRED per the reference document's META block. Validator must
        surface validation_status::INVALID with an error citing the missing field.

        This is the structural RED case: it does NOT depend on ENUM rejection
        (GH#435 PARTIAL) — it depends only on REQ-constraint enforcement which
        the validator already implements (see test_debate_schema.py for prior art).
        """
        content = """===DECISIONS_OCTAVE_v20260417===
META:
  TYPE::DECISION_LOG
  VERSION::"1.0"
TEST_DECISION:
  TIER::ARCHITECTURAL
  STATUS::BINDING
  DECISION::test_decision_essence
  BECAUSE::[test_rationale]
  ISSUE_REF::"#999"
===END==="""

        result = _validate_content(content)

        assert result["validation_status"] == "INVALID", (
            f"Missing TOKEN should be INVALID. Got: {result.get('validation_status')}. "
            f"Errors: {result.get('validation_errors', [])}"
        )
        assert result["valid"] is False


# ---------------------------------------------------------------------------
# GREEN: on-disk fixtures validate against the DECISION_LOG schema.
#
# Fixtures live in ``tests/fixtures/decision_log/`` and cover one minimal
# record per tier plus a malformed-rejection corpus. They are intentionally
# synthesised (not copied from the elevana-studio reference document) to keep
# the test corpus self-contained and stable across the schema sweep — the
# external reference is enumerated in the PR body, not embedded as fixture.
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "decision_log"


class TestDecisionLogFixturesValidate:
    """On-disk fixture-driven validation tests (GREEN)."""

    def test_architectural_minimal_fixture_validates(self) -> None:
        """The minimal ARCHITECTURAL-tier fixture MUST validate clean."""
        fixture = _FIXTURES_DIR / "architectural_minimal.oct.md"
        assert fixture.exists(), f"Fixture missing: {fixture}"

        result = _validate_content(fixture.read_text(encoding="utf-8"))

        assert result["validation_status"] == "VALIDATED", (
            f"architectural_minimal.oct.md should validate. "
            f"Got: {result.get('validation_status')}. "
            f"Errors: {result.get('validation_errors', [])}"
        )
        assert result["valid"] is True

    def test_convention_minimal_fixture_validates(self) -> None:
        """The minimal CONVENTION-tier fixture MUST validate clean."""
        fixture = _FIXTURES_DIR / "convention_minimal.oct.md"
        assert fixture.exists(), f"Fixture missing: {fixture}"

        result = _validate_content(fixture.read_text(encoding="utf-8"))

        assert result["validation_status"] == "VALIDATED", (
            f"convention_minimal.oct.md should validate. "
            f"Got: {result.get('validation_status')}. "
            f"Errors: {result.get('validation_errors', [])}"
        )
        assert result["valid"] is True

    def test_micro_minimal_fixture_validates(self) -> None:
        """The minimal MICRO-tier fixture (carrying ENFORCEMENT_REF) MUST validate clean."""
        fixture = _FIXTURES_DIR / "micro_minimal.oct.md"
        assert fixture.exists(), f"Fixture missing: {fixture}"

        result = _validate_content(fixture.read_text(encoding="utf-8"))

        assert result["validation_status"] == "VALIDATED", (
            f"micro_minimal.oct.md should validate. "
            f"Got: {result.get('validation_status')}. "
            f"Errors: {result.get('validation_errors', [])}"
        )
        assert result["valid"] is True

    def test_malformed_missing_token_fixture_rejects(self) -> None:
        """The malformed-missing-TOKEN fixture MUST reject (mirrors RED unit test, fixture-driven)."""
        fixture = _FIXTURES_DIR / "malformed_missing_token.oct.md"
        assert fixture.exists(), f"Fixture missing: {fixture}"

        result = _validate_content(fixture.read_text(encoding="utf-8"))

        assert result["validation_status"] == "INVALID", (
            f"malformed_missing_token.oct.md should be INVALID. "
            f"Got: {result.get('validation_status')}. "
            f"Errors: {result.get('validation_errors', [])}"
        )
        assert result["valid"] is False
