"""Tests for SKILL schema §-section body coverage (Issue #428, WAVE_3 deepening).

TDD RED phase: These tests pin the gap GH-428 surfaces — the SKILL schema
today validates only YAML frontmatter (Zone 2 per #244) plus three META
fields (TYPE/VERSION/STATUS); the rich §-section body (Zone 1) is
entirely unchecked.

WAVE_3 of pre-v1.13.0 Schema Sweep extends I5 SCHEMA_SOVEREIGNTY's coverage
from Zone 2 into the Zone 1 §-section body. A SKILL file with no §1
section, or with an §5::ANCHOR_KERNEL block missing the
TARGET/NEVER/MUST/GATE quartet, must surface a validator warning rather
than silently passing.

North Star compliance:
- PROD::I1 SYNTACTIC_FIDELITY — schema source round-trips via the Shape F
  sanctuary (covered automatically by
  ``tests/integration/test_schema_write_idempotency.py``).
- PROD::I4 TRANSFORM_AUDITABILITY — stable warning codes
  (``W_MISSING_REQUIRED_SECTION``, ``W_INCOMPLETE_SECTION_FIELDS``).
- PROD::I5 SCHEMA_SOVEREIGNTY — validation_status surfaces the gap rather
  than declaring a false clean.

Pre-existing limitations honoured by these tests:
- octave_validate ENUM constraints are PARTIAL per #435.
- SCHEMA_REQUIRED_EXCEPTIONS not yet consumed per #439.
- The on-disk SKILL corpus contains two §1-less files
  (``github-labels``, ``stub-detection``) and 43 files without
  ANCHOR_KERNEL. Those gaps are pinned by the allowlist tests below
  (precedent: AUTHORITY_MANDATE allowlist established in PR #437 for
  AGENT_DEFINITION).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from octave_mcp.schemas.loader import load_schema_by_name

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SKILLS_DIR = _REPO_ROOT / ".hestai-sys" / "library" / "skills"
_SCHEMA_PATH = _REPO_ROOT / "src" / "octave_mcp" / "resources" / "specs" / "schemas" / "skill.oct.md"


def _skill_files() -> list[Path]:
    if not _SKILLS_DIR.is_dir():
        return []
    return sorted(_SKILLS_DIR.glob("*/SKILL.md"))


def _validate_content(content: str) -> dict:
    """Helper to validate content through the MCP validate tool."""
    from octave_mcp.mcp.validate import ValidateTool

    tool = ValidateTool()
    return asyncio.run(tool.execute(content=content, schema="SKILL"))


class TestSkillSchemaLoading:
    """SKILL schema is loadable from the resources/specs/schemas/ path."""

    def test_schema_file_exists(self) -> None:
        """SKILL schema source file should exist at the canonical resources path."""
        assert _SCHEMA_PATH.exists(), f"Schema file not found at {_SCHEMA_PATH}"

    def test_load_schema_by_name(self) -> None:
        """``load_schema_by_name('SKILL')`` should find the SKILL schema."""
        schema = load_schema_by_name("SKILL")
        assert schema is not None, "Should find SKILL schema"
        assert schema.name == "SKILL"

    def test_schema_declares_required_section_ids(self) -> None:
        """SKILL schema POLICY should declare at least one required section id.

        The §-section body coverage hinges on the validator knowing which
        section ids (e.g., ``§1::*``) the schema requires. The POLICY block
        carries this as ``REQUIRED_SECTION_IDS``.
        """
        schema = load_schema_by_name("SKILL")
        assert schema is not None
        required_ids = getattr(schema.policy, "required_section_ids", None)
        assert required_ids, (
            "SKILL schema POLICY must declare REQUIRED_SECTION_IDS — without "
            "it the validator cannot enforce §1 presence (GH-428)."
        )
        assert "1" in required_ids, f"§1 should be required; got {required_ids!r}"

    def test_schema_declares_anchor_kernel_conditional_fields(self) -> None:
        """SKILL schema should declare ANCHOR_KERNEL's TARGET/NEVER/MUST/GATE quartet.

        When ``§5::ANCHOR_KERNEL`` is present, the quartet must be checked.
        The schema declares the conditional via
        ``POLICY.SECTION_CONDITIONAL_REQUIRED``.
        """
        schema = load_schema_by_name("SKILL")
        assert schema is not None
        conditional = getattr(schema.policy, "section_conditional_required", None)
        assert conditional, (
            "SKILL schema POLICY must declare SECTION_CONDITIONAL_REQUIRED — "
            "without it the ANCHOR_KERNEL quartet (TARGET/NEVER/MUST/GATE) "
            "remains silently uncovered (GH-428)."
        )
        anchor = conditional.get("ANCHOR_KERNEL")
        assert anchor is not None, f"ANCHOR_KERNEL entry expected; got {conditional!r}"
        expected = {"TARGET", "NEVER", "MUST", "GATE"}
        missing = expected - set(anchor)
        assert not missing, f"ANCHOR_KERNEL quartet missing entries: {missing}"


class TestSkillMalformedRejection:
    """Negative path: malformed SKILL §-section bodies surface diagnostics."""

    _FRONTMATTER = (
        "---\n"
        "name: bogus\n"
        "description: bogus skill for validation coverage\n"
        'allowed-tools: "*"\n'
        "---\n\n"
    )

    def test_skill_missing_section_1_surfaces_warning(self) -> None:
        """A SKILL with no §1 section must surface W_MISSING_REQUIRED_SECTION.

        Today this case validates clean — GH-428's false-negative reproducer.
        Post-fix, the validator surfaces W_MISSING_REQUIRED_SECTION.
        """
        content = (
            self._FRONTMATTER
            + "===SKILL:BOGUS===\n"
            "META:\n"
            "  TYPE::SKILL\n"
            '  VERSION::"1.0"\n'
            "===END===\n"
        )
        result = _validate_content(content)

        warnings = result.get("warnings", []) or []
        warning_codes = [w.get("code") for w in warnings if isinstance(w, dict)]
        assert "W_MISSING_REQUIRED_SECTION" in warning_codes, (
            f"Expected W_MISSING_REQUIRED_SECTION warning for §1-less SKILL. "
            f"Got status={result.get('validation_status')!r} warnings={warnings!r} "
            f"errors={result.get('validation_errors')!r}"
        )

    def test_skill_anchor_kernel_missing_quartet_field_surfaces_warning(self) -> None:
        """An ANCHOR_KERNEL section missing the quartet surfaces a warning.

        Today an ANCHOR_KERNEL with only ``TARGET`` validates clean — GH-428's
        second false-negative. Post-fix, the validator surfaces
        W_INCOMPLETE_SECTION_FIELDS naming the missing fields.
        """
        content = (
            self._FRONTMATTER
            + "===SKILL:BOGUS===\n"
            "META:\n"
            "  TYPE::SKILL\n"
            '  VERSION::"1.0"\n'
            "§1::CORE\n"
            "PURPOSE::test\n"
            "§5::ANCHOR_KERNEL\n"
            "TARGET::just_a_target_no_never_must_or_gate\n"
            "===END===\n"
        )
        result = _validate_content(content)

        warnings = result.get("warnings", []) or []
        incomplete = [
            w for w in warnings if isinstance(w, dict) and w.get("code") == "W_INCOMPLETE_SECTION_FIELDS"
        ]
        assert incomplete, (
            f"Expected W_INCOMPLETE_SECTION_FIELDS warning. "
            f"Got status={result.get('validation_status')!r} warnings={warnings!r}"
        )
        # The warning should name at least one of the missing quartet fields.
        joined = " ".join(w.get("message", "") for w in incomplete)
        for needed in ("NEVER", "MUST", "GATE"):
            assert needed in joined, f"Warning should name missing field {needed!r}; got {joined!r}"


class TestSkillMinimalValid:
    """Positive path: a hand-crafted minimal valid SKILL passes validation."""

    def test_minimal_valid_skill_validates(self) -> None:
        """A SKILL with §1 present and (optionally) a complete ANCHOR_KERNEL validates."""
        content = (
            "---\n"
            "name: minimal-skill\n"
            "description: minimal skill exercising §-section body coverage\n"
            'allowed-tools: "*"\n'
            "---\n\n"
            "===SKILL:MINIMAL===\n"
            "META:\n"
            "  TYPE::SKILL\n"
            '  VERSION::"1.0"\n'
            "§1::CORE\n"
            "PURPOSE::minimal skill body satisfying GH-428\n"
            "§5::ANCHOR_KERNEL\n"
            "TARGET::demonstrate_section_body_coverage\n"
            "NEVER::[skip_kernel_quartet]\n"
            "MUST::[carry_all_four_quartet_fields]\n"
            'GATE::"Is the quartet complete?"\n'
            "===END===\n"
        )
        result = _validate_content(content)

        warnings = result.get("warnings", []) or []
        unexpected = [
            w
            for w in warnings
            if isinstance(w, dict)
            and w.get("code") in {"W_MISSING_REQUIRED_SECTION", "W_INCOMPLETE_SECTION_FIELDS"}
        ]
        assert not unexpected, (
            f"Minimal valid SKILL should not surface §-section body warnings. "
            f"Got: {unexpected!r} ; full warnings={warnings!r}"
        )
        assert result.get("validation_status") == "VALIDATED"
        assert result.get("valid") is True


# Empirically-surfaced gaps in the existing SKILL corpus (WAVE_3 finding).
# These two SKILL files genuinely lack a §1 section — every other on-disk
# skill carries one. Pinned via allowlist precedent established in PR #437
# (AUTHORITY_MANDATE for AGENT_DEFINITION): the schema does not relax to
# paper over upstream omissions; instead the diagnostic is pinned so the
# gap remains visible (PROD::I5).
KNOWN_MISSING_SECTION_1_GAPS: frozenset[str] = frozenset(
    {
        "github-labels",
        "stub-detection",
    }
)


def _skill_dirname(p: Path) -> str:
    """Return the parent directory name for a SKILL.md path."""
    return p.parent.name


class TestExistingSkillFilesValidate:
    """Integration: every on-disk SKILL file validates clean (modulo allowlist).

    The known-gap allowlist (``KNOWN_MISSING_SECTION_1_GAPS``) pins the
    structural gaps the schema surfaces. Files outside the allowlist must
    not emit ``W_MISSING_REQUIRED_SECTION``. The ANCHOR_KERNEL conditional
    is fired only when the block is present — so SKILL files without an
    ANCHOR_KERNEL section are unaffected.
    """

    @pytest.mark.parametrize(
        "skill_path",
        [p for p in _skill_files() if _skill_dirname(p) not in KNOWN_MISSING_SECTION_1_GAPS],
        ids=lambda p: p.parent.name,
    )
    def test_existing_skill_file_validates_no_missing_section_1(self, skill_path: Path) -> None:
        """Non-allowlisted on-disk SKILL files must not surface W_MISSING_REQUIRED_SECTION."""
        content = skill_path.read_text(encoding="utf-8")
        result = _validate_content(content)

        warnings = result.get("warnings", []) or []
        section_warnings = [
            w
            for w in warnings
            if isinstance(w, dict) and w.get("code") == "W_MISSING_REQUIRED_SECTION"
        ]
        assert not section_warnings, (
            f"{skill_path.parent.name}/SKILL.md unexpectedly missing §1. "
            f"Warnings: {section_warnings!r}"
        )

    @pytest.mark.parametrize(
        "skill_dirname",
        sorted(KNOWN_MISSING_SECTION_1_GAPS),
    )
    def test_known_gap_skill_files_surface_section_1_diagnostic(self, skill_dirname: str) -> None:
        """Known-gap SKILL files surface W_MISSING_REQUIRED_SECTION.

        Pins the schema-sovereignty signal (PROD::I5). If this test starts
        failing because the file now validates clean, the gap has been
        closed upstream — remove the entry from
        ``KNOWN_MISSING_SECTION_1_GAPS``.
        """
        skill_path = _SKILLS_DIR / skill_dirname / "SKILL.md"
        if not skill_path.exists():
            pytest.skip(f"{skill_dirname}/SKILL.md no longer exists on disk")

        content = skill_path.read_text(encoding="utf-8")
        result = _validate_content(content)

        warnings = result.get("warnings", []) or []
        section_warnings = [
            w
            for w in warnings
            if isinstance(w, dict) and w.get("code") == "W_MISSING_REQUIRED_SECTION"
        ]
        assert section_warnings, (
            f"{skill_dirname}/SKILL.md: expected W_MISSING_REQUIRED_SECTION diagnostic, "
            f"got warnings={warnings!r}"
        )
