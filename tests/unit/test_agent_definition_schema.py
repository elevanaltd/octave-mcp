"""Tests for AGENT_DEFINITION schema validation (Issue #424, WAVE_2 Schema Sweep).

TDD RED phase: These tests define expected behavior for agent definition
file validation via ``octave_validate --schema AGENT_DEFINITION``.

Agent definition files at ``.hestai-sys/library/agents/*.oct.md`` share the
envelope structure:

- META block with ``TYPE::AGENT_DEFINITION``, ``VERSION``, ``PURPOSE``,
  ``CONTRACT``.
- ``§1::IDENTITY`` (ROLE, COGNITION, ARCHETYPE, MODEL_TIER, MISSION,
  PRINCIPLES, AUTHORITY_*).
- ``§2::OPERATIONAL_BEHAVIOR`` (CONDUCT block with TONE/PROTOCOL).
- ``§3::CAPABILITIES`` (CHASSIS/PROFILES or SKILLS/PATTERNS).
- ``§4::INTERACTION_RULES`` (GRAMMAR with MUST_USE/MUST_NOT regex lists).

North Star compliance:
- PROD::I1 SYNTACTIC_FIDELITY — schema sources round-trip via the Shape F
  sanctuary (covered automatically by
  ``tests/integration/test_schema_write_idempotency.py``).
- PROD::I4 TRANSFORM_AUDITABILITY — every validation receipt is auditable.
- PROD::I5 SCHEMA_SOVEREIGNTY — validation_status surfaces clearly.

Pre-existing limitations honoured by these tests:
- octave_validate ENUM constraints are PARTIAL per #435; tests do NOT
  depend on ENUM rejection. REQ enforcement is verified for the
  negative-path coverage.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from octave_mcp.schemas.loader import load_schema_by_name


_REPO_ROOT = Path(__file__).resolve().parents[2]
_AGENTS_DIR = _REPO_ROOT / ".hestai-sys" / "library" / "agents"
_SCHEMA_PATH = (
    _REPO_ROOT
    / "src"
    / "octave_mcp"
    / "resources"
    / "specs"
    / "schemas"
    / "agent_definition.oct.md"
)


def _agent_files() -> list[Path]:
    if not _AGENTS_DIR.is_dir():
        return []
    return sorted(_AGENTS_DIR.glob("*.oct.md"))


def _validate_content(content: str) -> dict:
    """Helper to validate content through the MCP validate tool."""
    from octave_mcp.mcp.validate import ValidateTool

    tool = ValidateTool()
    return asyncio.run(tool.execute(content=content, schema="AGENT_DEFINITION"))


class TestAgentDefinitionSchemaLoading:
    """Test loading AGENT_DEFINITION schema from specs/schemas/."""

    def test_schema_file_exists(self) -> None:
        """AGENT_DEFINITION schema source file should exist."""
        assert _SCHEMA_PATH.exists(), f"Schema file not found at {_SCHEMA_PATH}"

    def test_load_schema_by_name(self) -> None:
        """``load_schema_by_name`` should find AGENT_DEFINITION schema."""
        schema = load_schema_by_name("AGENT_DEFINITION")
        assert schema is not None, "Should find AGENT_DEFINITION schema"
        assert schema.name == "AGENT_DEFINITION"

    def test_schema_has_required_identity_fields(self) -> None:
        """AGENT_DEFINITION schema should declare core required identity fields.

        These four fields constitute the minimum identity envelope: who the
        agent is (ROLE), how it reasons (COGNITION), what it does (MISSION),
        and its accountability statement (AUTHORITY_MANDATE).
        """
        schema = load_schema_by_name("AGENT_DEFINITION")
        assert schema is not None

        required = {"ROLE", "COGNITION", "MISSION", "AUTHORITY_MANDATE"}
        missing = required - set(schema.fields.keys())
        assert not missing, f"Schema missing required identity fields: {missing}"

        for name in required:
            field = schema.fields[name]
            # Either parsed constraint or raw_value text should mark REQ
            if field.pattern is not None and field.pattern.constraints:
                assert field.is_required, f"{name} should be REQ via pattern"
            else:
                assert "REQ" in (field.raw_value or ""), (
                    f"{name} should carry REQ in raw value: {field.raw_value!r}"
                )

    def test_schema_has_version(self) -> None:
        """Schema should declare an explicit version."""
        schema = load_schema_by_name("AGENT_DEFINITION")
        assert schema is not None
        assert schema.version is not None
        assert schema.version != ""


class TestAgentDefinitionMalformedRejection:
    """Negative path: deliberately malformed AGENT_DEFINITION files reject.

    These tests do NOT depend on ENUM enforcement (per known limitation
    #435). They depend solely on REQ enforcement, which the validator
    implements via per-section coverage + envelope-level checks.
    """

    def test_missing_role_is_invalid(self) -> None:
        """An agent missing ROLE must fail validation."""
        content = """===BROKEN_AGENT===
META:
  TYPE::AGENT_DEFINITION
  VERSION::"1.0.0"
  PURPOSE::"Test agent missing ROLE"
  CONTRACT::HOLOGRAPHIC<JIT_GRAMMAR_COMPILATION>
§1::IDENTITY
  COGNITION::LOGOS
  MISSION::TEST_MISSION
  AUTHORITY_MANDATE::"Test mandate"
§2::OPERATIONAL_BEHAVIOR
  CONDUCT:
    TONE::"Test"
§3::CAPABILITIES
  SKILLS::[]
§4::INTERACTION_RULES
  GRAMMAR:
    MUST_USE::[]
===END==="""
        result = _validate_content(content)
        assert result["validation_status"] == "INVALID", (
            f"Missing ROLE should be INVALID. Got: {result.get('validation_status')}; "
            f"errors={result.get('validation_errors')}"
        )
        assert result["valid"] is False
        error_messages = [e.get("message", "") for e in result.get("validation_errors", [])]
        assert any("ROLE" in msg for msg in error_messages), (
            f"Error should mention ROLE. Got: {error_messages}"
        )

    def test_missing_authority_mandate_is_invalid(self) -> None:
        """An agent missing AUTHORITY_MANDATE must fail validation."""
        content = """===BROKEN_AGENT===
META:
  TYPE::AGENT_DEFINITION
  VERSION::"1.0.0"
  PURPOSE::"Test agent missing AUTHORITY_MANDATE"
  CONTRACT::HOLOGRAPHIC<JIT_GRAMMAR_COMPILATION>
§1::IDENTITY
  ROLE::BROKEN_AGENT
  COGNITION::LOGOS
  MISSION::TEST_MISSION
§2::OPERATIONAL_BEHAVIOR
  CONDUCT:
    TONE::"Test"
§3::CAPABILITIES
  SKILLS::[]
§4::INTERACTION_RULES
  GRAMMAR:
    MUST_USE::[]
===END==="""
        result = _validate_content(content)
        assert result["validation_status"] == "INVALID", (
            f"Missing AUTHORITY_MANDATE should be INVALID. "
            f"Got: {result.get('validation_status')}; errors={result.get('validation_errors')}"
        )
        assert result["valid"] is False
        error_messages = [e.get("message", "") for e in result.get("validation_errors", [])]
        assert any("AUTHORITY_MANDATE" in msg for msg in error_messages), (
            f"Error should mention AUTHORITY_MANDATE. Got: {error_messages}"
        )

    def test_missing_mission_is_invalid(self) -> None:
        """An agent missing MISSION must fail validation."""
        content = """===BROKEN_AGENT===
META:
  TYPE::AGENT_DEFINITION
  VERSION::"1.0.0"
  PURPOSE::"Test agent missing MISSION"
  CONTRACT::HOLOGRAPHIC<JIT_GRAMMAR_COMPILATION>
§1::IDENTITY
  ROLE::BROKEN_AGENT
  COGNITION::LOGOS
  AUTHORITY_MANDATE::"Test mandate"
§2::OPERATIONAL_BEHAVIOR
  CONDUCT:
    TONE::"Test"
§3::CAPABILITIES
  SKILLS::[]
§4::INTERACTION_RULES
  GRAMMAR:
    MUST_USE::[]
===END==="""
        result = _validate_content(content)
        assert result["validation_status"] == "INVALID", (
            f"Missing MISSION should be INVALID. Got: {result.get('validation_status')}"
        )
        assert result["valid"] is False


class TestAgentDefinitionMinimalValid:
    """Positive path: a hand-crafted minimal valid agent passes validation."""

    def test_minimal_valid_agent_validates(self) -> None:
        """A minimal AGENT_DEFINITION carrying every REQ field validates."""
        content = """===MINIMAL_AGENT===
META:
  TYPE::AGENT_DEFINITION
  VERSION::"1.0.0"
  PURPOSE::"Minimal agent definition for schema validation coverage"
  CONTRACT::HOLOGRAPHIC<JIT_GRAMMAR_COMPILATION>
§1::IDENTITY
  ROLE::MINIMAL_AGENT
  COGNITION::LOGOS
  MISSION::TEST_FIDELITY
  AUTHORITY_MANDATE::"Verify the schema accepts the minimum envelope"
§2::OPERATIONAL_BEHAVIOR
  CONDUCT:
    TONE::"Technical, Precise"
§3::CAPABILITIES
  SKILLS::[]
§4::INTERACTION_RULES
  GRAMMAR:
    MUST_USE::[]
===END==="""
        result = _validate_content(content)
        assert result["validation_status"] == "VALIDATED", (
            f"Minimal valid agent should VALIDATE. "
            f"Got: {result.get('validation_status')}; errors={result.get('validation_errors')}"
        )
        assert result["valid"] is True


# Empirically-surfaced gaps in the existing agent corpus (WAVE_2 finding).
# These two files genuinely lack AUTHORITY_MANDATE — every other on-disk
# agent declares one. Tracked as a follow-up gap to be filled in upstream
# (agent-expert authoring), NOT by relaxing the schema. Honours HEPHAESTUS
# bias (anvil of real input surfaces real defects) and ATLAS bias (do not
# weaken load-bearing schema fields to paper over upstream omissions).
KNOWN_AUTHORITY_MANDATE_GAPS: frozenset[str] = frozenset(
    {
        "ideator.oct.md",
        "synthesizer.oct.md",
    }
)


class TestExistingAgentFilesValidate:
    """Integration: every on-disk agent file validates clean against the schema.

    Each ``.hestai-sys/library/agents/*.oct.md`` file is the empirical ground
    truth for the schema. Files NOT on the known-gap allowlist must validate
    clean (forge it on the anvil of real input — HEPHAESTUS bias).

    The known-gap allowlist (``KNOWN_AUTHORITY_MANDATE_GAPS``) records agents
    surfaced as structurally incomplete by this schema. They are pinned by a
    second test to ensure the AUTHORITY_MANDATE diagnostic remains visible
    (PROD::I5 SCHEMA_SOVEREIGNTY).
    """

    @pytest.mark.parametrize(
        "agent_path",
        [p for p in _agent_files() if p.name not in KNOWN_AUTHORITY_MANDATE_GAPS],
        ids=lambda p: p.name,
    )
    def test_existing_agent_file_validates(self, agent_path: Path) -> None:
        """Each on-disk agent file should validate clean against AGENT_DEFINITION."""
        content = agent_path.read_text(encoding="utf-8")
        result = _validate_content(content)

        # Surface the first error compactly to make failures easy to diagnose.
        if result.get("validation_status") != "VALIDATED":
            errors = result.get("validation_errors", [])
            first = errors[0] if errors else "<no error returned>"
            pytest.fail(
                f"{agent_path.name} did not validate clean against AGENT_DEFINITION.\n"
                f"  validation_status={result.get('validation_status')!r}\n"
                f"  first_error={first!r}\n"
                f"  total_errors={len(errors)}"
            )
        assert result["valid"] is True

    @pytest.mark.parametrize(
        "agent_filename",
        sorted(KNOWN_AUTHORITY_MANDATE_GAPS),
    )
    def test_known_gap_agent_files_surface_authority_mandate_diagnostic(
        self, agent_filename: str
    ) -> None:
        """Known-gap agents surface the AUTHORITY_MANDATE E003 diagnostic.

        Pins the schema sovereignty signal (PROD::I5): the schema is doing
        its job by reporting the structural omission. If this test starts
        failing because the file now validates clean, the gap has been
        closed upstream and the entry should be removed from
        ``KNOWN_AUTHORITY_MANDATE_GAPS``.
        """
        agent_path = _AGENTS_DIR / agent_filename
        if not agent_path.exists():
            pytest.skip(f"{agent_filename} no longer exists on disk")

        content = agent_path.read_text(encoding="utf-8")
        result = _validate_content(content)

        assert result.get("validation_status") == "INVALID", (
            f"{agent_filename} unexpectedly validates clean — gap may be closed. "
            f"Remove from KNOWN_AUTHORITY_MANDATE_GAPS."
        )
        errors = result.get("validation_errors", [])
        e003_authority_errors = [
            e
            for e in errors
            if e.get("code") == "E003" and "AUTHORITY_MANDATE" in e.get("message", "")
        ]
        assert e003_authority_errors, (
            f"{agent_filename}: expected E003/AUTHORITY_MANDATE diagnostic, "
            f"got errors={errors!r}"
        )
