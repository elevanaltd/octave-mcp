"""Tests for CRS_REVIEW §3::FINDINGS body coverage + canonical envelope name (GH-426).

WAVE_3 final PR of the pre-v1.13.0 Schema Sweep. Closes the §3::FINDINGS gap
left by the prior CRS_REVIEW schema (only §1::VERDICT / §2::DISTRIBUTION /
§4::SUMMARY had FIELDS coverage; §3::FINDINGS was silent — directly violating
PROD::I5 SCHEMA_SOVEREIGNTY's ``validation_status_visible_in_output`` rationale).

Reuses the POLICY+walker mechanism landed in PR #444 (W_MISSING_REQUIRED_SECTION
/ W_INCOMPLETE_SECTION_FIELDS / W_MALFORMED_POLICY, _PolicyWalkSentinel,
_canonical_schema_dirs). Also pins the envelope-name canonicalisation precedent
from PR #437 (envelope name MUST match META.TYPE; legacy ``CRS_REVIEW_SCHEMA``
form is rejected).

Scope per final-final AC (HO authorisation):
1. Vocabulary: UPPERCASE — REQ ``SEVERITY`` (ENUM[P0..P5]), ``FILE``, ``ISSUE``;
   OPT ``CONFIDENCE``, ``LINES``, ``TITLE``, ``EVIDENCE``, ``IMPACT``, ``FIX``
   and ``REQUIRED_FIX`` (both accepted at OPT level; validator-only alias; no
   emit-time rewriting per HO direction dropping Surprise 3 from the original
   AC).
2. Canonical envelope name ``CRS_REVIEW`` (matches META.TYPE) — schema source
   migrated from ``src/octave_mcp/schemas/builtin/`` to
   ``src/octave_mcp/resources/specs/schemas/`` in the same PR.
3. Six on-disk fixtures (3 positive + 3 negative) under
   ``tests/fixtures/crs_review/`` for I4 auditability.

North Star compliance:
- I1 SYNTACTIC_FIDELITY: schema source is itself idempotent under octave_write
  (auto-covered by the glob in tests/integration/test_schema_write_idempotency.py
  once the schema sits under resources/specs/schemas/).
- I4 TRANSFORM_AUDITABILITY: TDD commit sequence is the audit trail; FIX↔REQUIRED_FIX
  alias acceptance is empirically witnessed by paired positive fixtures rather
  than implemented as runtime mutation (which would have violated I1's bijective
  rationale per the IL→HO Surprise 3 report).
- I5 SCHEMA_SOVEREIGNTY: validation_status visible — INVALID for malformed §3
  findings, VALIDATED for well-formed; W_INCOMPLETE_SECTION_FIELDS surfaces the
  precise missing field per the AC vocabulary.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from octave_mcp.mcp.validate import ValidateTool
from octave_mcp.schemas.loader import load_schema_by_name

# The three REQ fields the §3::FINDINGS POLICY declares per the final-final AC.
# Drives the loader-presence + parametrised W_INCOMPLETE_SECTION_FIELDS matrix.
_REQUIRED_FINDING_FIELDS: tuple[str, ...] = ("SEVERITY", "FILE", "ISSUE")


_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "crs_review"


def _validate_content(content: str) -> dict:
    """Validate ``content`` through the MCP validate tool against CRS_REVIEW."""
    tool = ValidateTool()
    return asyncio.run(tool.execute(content=content, schema="CRS_REVIEW"))


def _validate_fixture(fixture_name: str) -> dict:
    """Read a fixture from tests/fixtures/crs_review/ and validate it."""
    path = _FIXTURES_DIR / fixture_name
    assert path.exists(), f"Fixture not found: {path}"
    return _validate_content(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# §1: Canonical envelope name (GH-426 + #437/#444 precedent)
#
# The migrated schema source MUST declare envelope name ``CRS_REVIEW`` (matching
# META.TYPE), not the legacy ``CRS_REVIEW_SCHEMA`` form. The loader's
# resources-first precedence (PR #444 _canonical_schema_dirs) ensures the
# migrated file at resources/specs/schemas/ wins over any leftover builtin
# copy.
# ---------------------------------------------------------------------------


class TestCrsReviewCanonicalEnvelopeName:
    """The loaded schema MUST report canonical name ``CRS_REVIEW``."""

    def test_loaded_schema_name_is_canonical_crs_review(self) -> None:
        """``schema.name`` MUST equal ``CRS_REVIEW`` (matches META.TYPE).

        Before GH-426 the schema file was ``===CRS_REVIEW_SCHEMA===`` so
        ``load_schema_by_name("CRS_REVIEW").name`` reported the legacy
        ``CRS_REVIEW_SCHEMA``. The migration renames the envelope to match
        META.TYPE per the PR #437 precedent (AGENT_DEFINITION canonicalisation).
        """
        schema = load_schema_by_name("CRS_REVIEW")
        assert schema is not None, "CRS_REVIEW schema must be loadable"
        assert schema.name == "CRS_REVIEW", (
            f"Canonical envelope name MUST be 'CRS_REVIEW' (matches META.TYPE) "
            f"per PR #437 precedent. Got: {schema.name!r}"
        )

    def test_loaded_schema_is_resolved_from_resources_specs_schemas(self) -> None:
        """Schema source MUST live under ``resources/specs/schemas/`` after migration.

        The migration is an in-place move per SYS::I2 SOURCE_FIDELITY: the
        original ``schemas/builtin/crs_review.oct.md`` is DELETED and the
        canonical home is now ``resources/specs/schemas/crs_review.oct.md``.
        This test pins the destination path so the idempotency CI gate
        (which globs ``resources/specs/schemas/*.oct.md``) auto-covers
        the migrated file.
        """
        canonical = (
            Path(__file__).parent.parent.parent
            / "src"
            / "octave_mcp"
            / "resources"
            / "specs"
            / "schemas"
            / "crs_review.oct.md"
        )
        assert canonical.exists(), (
            f"Migrated schema source MUST exist at {canonical}. "
            f"Per SYS::I2 SOURCE_FIDELITY the source-of-truth file is the "
            f"in-place move destination — no legacy duplicate retained."
        )

        legacy = (
            Path(__file__).parent.parent.parent
            / "src"
            / "octave_mcp"
            / "schemas"
            / "builtin"
            / "crs_review.oct.md"
        )
        assert not legacy.exists(), (
            f"Legacy schema source MUST be deleted by the migration "
            f"(SYS::I2 forbids versioned duplicates). Found leftover at: {legacy}"
        )


# ---------------------------------------------------------------------------
# §2: POLICY block declares REQUIRED_SECTION_IDS + SECTION_CONDITIONAL_REQUIRED
# (GH-426; reuses PR #444 mechanism)
# ---------------------------------------------------------------------------


class TestCrsReviewPolicy:
    """POLICY block declarations as authored in the migrated schema source."""

    def test_policy_required_section_ids_includes_3(self) -> None:
        """POLICY.REQUIRED_SECTION_IDS MUST include ``"3"`` (the FINDINGS section).

        Closes the gap where a CRS_REVIEW document could omit §3::FINDINGS
        entirely and validate clean — the prior schema had no
        REQUIRED_SECTION_IDS at all, so the walker had nothing to enforce.
        """
        schema = load_schema_by_name("CRS_REVIEW")
        assert schema is not None
        assert "3" in schema.policy.required_section_ids, (
            f"POLICY.REQUIRED_SECTION_IDS MUST list '3' so §3::FINDINGS absence "
            f"surfaces W_MISSING_REQUIRED_SECTION. Got: "
            f"{schema.policy.required_section_ids!r}"
        )

    def test_policy_section_conditional_required_findings_lists_req_triple(self) -> None:
        """POLICY.SECTION_CONDITIONAL_REQUIRED.FINDINGS MUST list SEVERITY+FILE+ISSUE.

        When §3::FINDINGS is present, the walker must enforce the AC's REQ
        triple (uppercase per HO final-final AC option A). Missing members
        surface W_INCOMPLETE_SECTION_FIELDS per the PR #444 mechanism.
        """
        schema = load_schema_by_name("CRS_REVIEW")
        assert schema is not None
        conditional = schema.policy.section_conditional_required
        assert "FINDINGS" in conditional, (
            f"POLICY.SECTION_CONDITIONAL_REQUIRED MUST declare a FINDINGS key. "
            f"Got: {conditional!r}"
        )
        findings_required = set(conditional["FINDINGS"])
        expected = set(_REQUIRED_FINDING_FIELDS)
        assert expected.issubset(findings_required), (
            f"FINDINGS conditional-required field set MUST include "
            f"{sorted(expected)}. Got: {sorted(findings_required)}"
        )


# ---------------------------------------------------------------------------
# §3: Positive fixtures validate clean
# ---------------------------------------------------------------------------


class TestCrsReviewPositiveFixtures:
    """On-disk positive fixtures MUST produce validation_status==VALIDATED."""

    @pytest.mark.parametrize(
        "fixture_name",
        [
            "valid_complete_review.oct.md",
            "valid_finding_uses_fix_alias.oct.md",
            "valid_finding_uses_required_fix.oct.md",
        ],
    )
    def test_positive_fixture_validates(self, fixture_name: str) -> None:
        """Each positive fixture MUST validate clean (status VALIDATED, no errors)."""
        result = _validate_fixture(fixture_name)
        assert result["validation_status"] == "VALIDATED", (
            f"{fixture_name} must validate clean. Got: "
            f"validation_status={result.get('validation_status')!r}; "
            f"validation_errors={result.get('validation_errors')!r}; "
            f"warnings={result.get('warnings')!r}"
        )


# ---------------------------------------------------------------------------
# §4: FIX↔REQUIRED_FIX alias acceptance (no emit-time rewriting)
#
# Per HO final-final AC: both ``FIX::`` and ``REQUIRED_FIX::`` are accepted at
# OPT level. There is NO emit-time normalisation (Surprise 3 dropped from AC).
# The two fixtures above exercise both directions; this class adds an explicit
# contract assertion against the validation surface so a future regression
# (e.g. POLICY declaring FIX as REQ, or one alias accidentally treated as
# unknown) is caught with a precise failure message.
# ---------------------------------------------------------------------------


class TestCrsReviewFixAliasAcceptance:
    """FIX↔REQUIRED_FIX alias: both names validate clean at OPT level."""

    def test_fix_alias_validates_clean(self) -> None:
        """A finding using ``FIX::`` (not ``REQUIRED_FIX::``) MUST validate clean."""
        result = _validate_fixture("valid_finding_uses_fix_alias.oct.md")
        assert result["validation_status"] == "VALIDATED", (
            f"FIX alias must validate clean (HO AC: both names accepted at OPT "
            f"level). Got: validation_status={result.get('validation_status')!r}; "
            f"errors={result.get('validation_errors')!r}; "
            f"warnings={result.get('warnings')!r}"
        )

    def test_required_fix_canonical_validates_clean(self) -> None:
        """A finding using ``REQUIRED_FIX::`` (recommended canonical) MUST validate clean."""
        result = _validate_fixture("valid_finding_uses_required_fix.oct.md")
        assert result["validation_status"] == "VALIDATED", (
            f"REQUIRED_FIX canonical form must validate clean. Got: "
            f"validation_status={result.get('validation_status')!r}; "
            f"errors={result.get('validation_errors')!r}; "
            f"warnings={result.get('warnings')!r}"
        )

    def test_no_emit_time_field_rewriting(self) -> None:
        """Canonical emit MUST NOT rewrite ``FIX::`` to ``REQUIRED_FIX::``.

        Per HO final-final AC the alias is validator-only — there is NO
        emit-time normalisation (the original AC requirement was rescinded
        after the IL→HO Surprise 3 report flagged the conflict with PROD::I1
        bijective_on_semantic_space and the absence of any precedent for
        runtime field-rename rewriting in the codebase).

        The canonical output of a fixture authoring ``FIX::`` MUST therefore
        still contain ``FIX::`` (the source token), not ``REQUIRED_FIX::``.
        """
        result = _validate_fixture("valid_finding_uses_fix_alias.oct.md")
        canonical = result.get("canonical") or ""
        assert "FIX::" in canonical, (
            f"Canonical output MUST preserve the user-authored ``FIX::`` "
            f"token (no emit-time rewriting per HO direction). Got canonical:\n"
            f"{canonical}"
        )
        # Defence-in-depth: assert REQUIRED_FIX did NOT appear (would only
        # happen if a future regression added emit-time normalisation).
        # Use word-boundary check via simple string scan: the source did not
        # author REQUIRED_FIX so it must not appear in the canonical output.
        assert "REQUIRED_FIX::" not in canonical, (
            f"Canonical output MUST NOT introduce ``REQUIRED_FIX::`` — the "
            f"source authored ``FIX::``. Emit-time field-rename is forbidden "
            f"per HO direction (PROD::I1 bijective_on_semantic_space). "
            f"Got canonical:\n{canonical}"
        )


# ---------------------------------------------------------------------------
# §5: Negative fixtures — missing REQ field surfaces W_INCOMPLETE_SECTION_FIELDS
# (parametrised across SEVERITY / FILE / ISSUE)
# ---------------------------------------------------------------------------


class TestCrsReviewNegativeFixtures:
    """On-disk negative fixtures MUST surface W_INCOMPLETE_SECTION_FIELDS naming the missing field."""

    @pytest.mark.parametrize(
        "fixture_name, missing_field",
        [
            ("malformed_missing_severity.oct.md", "SEVERITY"),
            ("malformed_missing_file.oct.md", "FILE"),
            ("malformed_missing_issue.oct.md", "ISSUE"),
        ],
    )
    def test_malformed_fixture_emits_named_warning(
        self, fixture_name: str, missing_field: str
    ) -> None:
        """Each malformed fixture MUST surface W_INCOMPLETE_SECTION_FIELDS naming its gap.

        The walker (``_validate_section_body_coverage`` in core/validator.py)
        emits W_INCOMPLETE_SECTION_FIELDS with the missing field name in the
        message. We assert the discriminant code AND the field-name presence
        so a generic "something's missing" message would still fail the test.
        """
        result = _validate_fixture(fixture_name)
        # The warning surfaces in either ``warnings`` (STANDARD profile path)
        # or ``validation_errors`` (when promoted to INVALID gating). Per
        # PR #444 the walker uses severity="warning" so it lands in warnings.
        all_messages = []
        for record in result.get("warnings", []):
            all_messages.append((record.get("code"), record.get("message", "")))
        for record in result.get("validation_errors", []):
            all_messages.append((record.get("code"), record.get("message", "")))

        named_warnings = [
            (code, msg)
            for (code, msg) in all_messages
            if code == "W_INCOMPLETE_SECTION_FIELDS" and missing_field in msg
        ]
        assert named_warnings, (
            f"{fixture_name}: expected W_INCOMPLETE_SECTION_FIELDS warning "
            f"naming {missing_field!r}. Got messages: {all_messages!r}"
        )


# ---------------------------------------------------------------------------
# §6: W_MISSING_REQUIRED_SECTION — §3 omitted entirely
# ---------------------------------------------------------------------------


class TestCrsReviewMissingRequiredSection:
    """A document omitting §3::FINDINGS entirely MUST surface W_MISSING_REQUIRED_SECTION."""

    def test_findings_section_omitted_surfaces_w_missing_required_section(self) -> None:
        """A document with §1+§2+§4 but no §3 MUST emit W_MISSING_REQUIRED_SECTION.

        Closes the WAVE_3 gap: the prior schema had no REQUIRED_SECTION_IDS, so
        a CRS_REVIEW with no FINDINGS section validated clean. Per the HO AC
        the new POLICY declares ``REQUIRED_SECTION_IDS::["3"]`` to make the
        gap surface visibly (PROD::I5 SCHEMA_SOVEREIGNTY).
        """
        # Build a doc that has §1/§2/§4 but no §3.
        content = (
            "===CRS_REVIEW===\n"
            "META:\n"
            "  TYPE::CRS_REVIEW\n"
            '  VERSION::"1.0.0"\n'
            "\n"
            "§1::VERDICT\n"
            "  ROLE::CRS\n"
            '  PROVIDER::"test-model"\n'
            "  VERDICT::APPROVED\n"
            '  SHA::"abc1234"\n'
            "  TIER::T1\n"
            "\n"
            "§2::DISTRIBUTION\n"
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
            "§4::SUMMARY\n"
            '  ASSESSMENT::"Empty review with no findings section at all"\n'
            "  TOP_RISKS::[]\n"
            "\n"
            "===END===\n"
        )
        result = _validate_content(content)
        all_messages = []
        for record in result.get("warnings", []):
            all_messages.append((record.get("code"), record.get("message", "")))
        for record in result.get("validation_errors", []):
            all_messages.append((record.get("code"), record.get("message", "")))

        missing_section_warnings = [
            (code, msg)
            for (code, msg) in all_messages
            if code == "W_MISSING_REQUIRED_SECTION" and ("3" in msg or "§3" in msg)
        ]
        assert missing_section_warnings, (
            f"Document omitting §3::FINDINGS must surface "
            f"W_MISSING_REQUIRED_SECTION naming section '3'. "
            f"Got messages: {all_messages!r}"
        )
