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

Test taxonomy (post TMG-rework):
- ``TestDecisionLogSchemaLoading`` — each loading assertion drives at least one
  validation call to prove the schema is functionally consumed, not just parsed.
- ``TestDecisionLogSchemaRejectsMalformed`` — parametrised across every REQ
  field, asserting a distinct E003-class rejection per missing field with the
  field name in the error message. Each parametrisation has an on-disk fixture
  counterpart under ``tests/fixtures/decision_log/`` for I4 auditability.
- ``TestDecisionLogFixturesValidate`` — on-disk positive fixtures (one per tier).
- ``TestDecisionLogSchemaRequiredExceptions`` — SCHEMA_REQUIRED_EXCEPTIONS
  stub-pointer path: negative case (non-stub missing DECISION+BECAUSE rejects)
  pins the current contract; positive case (stub missing DECISION+BECAUSE
  validates) is xfail-marked because validator-time exception enforcement is
  not yet implemented (validator currently treats stubs identically to non-stubs
  for REQ-constraint enforcement — surfaced as a known limitation analogous to
  GH#435 ENUM PARTIAL).

North Star compliance:
- I1 SYNTACTIC_FIDELITY: schema source is itself idempotent under octave_write
  (auto-covered by the glob in tests/integration/test_schema_write_idempotency.py).
- I4 TRANSFORM_AUDITABILITY: TDD commit sequence is the audit trail; xfail-marked
  test documents the unimplemented exception-enforcement gap.
- I5 SCHEMA_SOVEREIGNTY: validation_status visible — INVALID for malformed,
  VALIDATED for well-formed.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from octave_mcp.mcp.validate import ValidateTool
from octave_mcp.schemas.loader import load_schema_by_name

# The five SCHEMA_REQUIRED fields per the reference document's META block.
# Drives both the loader-presence assertion and the parametrised REJECTION
# matrix below.
_REQUIRED_FIELDS: tuple[str, ...] = ("TOKEN", "TIER", "STATUS", "DECISION", "BECAUSE")


def _validate_content(content: str) -> dict:
    """Validate ``content`` through the MCP validate tool against DECISION_LOG."""
    tool = ValidateTool()
    return asyncio.run(tool.execute(content=content, schema="DECISION_LOG"))


_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "decision_log"


# ---------------------------------------------------------------------------
# Loading tests — each assertion drives at least one validation case so the
# schema is proven functionally consumed (TMG concern 2: no vacuous
# "loads and parses" assertions).
# ---------------------------------------------------------------------------


class TestDecisionLogSchemaLoading:
    """Test that the DECISION_LOG schema file exists, loads, and is functionally consumed."""

    def test_decision_log_schema_file_exists_and_validates_positive_sample(self) -> None:
        """Schema file exists at the canonical specs/schemas/ location AND a positive sample validates.

        TMG concern 2: strengthens the vacuous "file exists" assertion by also
        proving the validator surface consumes the schema for at least one
        well-formed sample. If the file existed but the schema were unparseable
        or unwired, this test would fail at the validation step rather than
        passing on a tautology.
        """
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

        # Drive validation: a well-formed minimal architectural record must validate.
        result = _validate_content(
            "===DECISIONS_OCTAVE_v20260417===\n"
            "META:\n"
            "  TYPE::DECISION_LOG\n"
            '  VERSION::"1.0"\n'
            "T:\n"
            "  TOKEN::HO-LOADING-PROBE-20260515\n"
            "  TIER::ARCHITECTURAL\n"
            "  STATUS::BINDING\n"
            "  DECISION::loading_probe_decision\n"
            "  BECAUSE::[loading_probe_rationale]\n"
            '  ISSUE_REF::"#999"\n'
            "===END==="
        )
        assert result["validation_status"] == "VALIDATED", (
            f"Schema must be functionally consumed by the validator. "
            f"Got: {result.get('validation_status')}. Errors: {result.get('validation_errors', [])}"
        )

    def test_load_decision_log_schema_by_name_and_rejects_empty_envelope(self) -> None:
        """``load_schema_by_name`` resolves DECISION_LOG AND drives a negative validation case.

        TMG concern 2: strengthens the bare resolver assertion by also proving
        the loaded schema produces INVALID against a manifestly malformed payload
        (an envelope with TYPE::DECISION_LOG but no decision entries — all five
        REQUIRED fields absent). A bare name-equality assertion would tolerate
        a schema whose required-field set silently became empty; this version
        catches that drift.
        """
        schema = load_schema_by_name("DECISION_LOG")
        assert schema is not None, "Should find DECISION_LOG schema"
        assert schema.name == "DECISION_LOG"

        empty_envelope = (
            "===DECISIONS_OCTAVE_v20260417===\n" "META:\n" "  TYPE::DECISION_LOG\n" '  VERSION::"1.0"\n' "===END==="
        )
        result = _validate_content(empty_envelope)
        assert result["validation_status"] == "INVALID", (
            f"An envelope with no decision-entry fields must reject. "
            f"Got: {result.get('validation_status')}. Errors: {result.get('validation_errors', [])}"
        )

    def test_decision_log_schema_has_version_and_loaded_schema_governs_validation(self) -> None:
        """Schema declares version "1.0" AND the loaded definition is the same one driving validation.

        TMG concern 2: pairs the version assertion with a validation call that
        relies on the loaded schema's field set. The validation case (missing
        TOKEN) only succeeds in producing E003 if the loaded schema is actually
        what the validator consumes — proving load-vs-validate identity.
        """
        schema = load_schema_by_name("DECISION_LOG")
        assert schema is not None
        assert schema.version == "1.0"

        result = _validate_content(
            "===DECISIONS_OCTAVE_v20260417===\n"
            "META:\n"
            "  TYPE::DECISION_LOG\n"
            '  VERSION::"1.0"\n'
            "T:\n"
            "  TIER::ARCHITECTURAL\n"
            "  STATUS::BINDING\n"
            "  DECISION::probe\n"
            "  BECAUSE::[probe]\n"
            "===END==="
        )
        assert result["validation_status"] == "INVALID"
        codes = [e.get("code") for e in result.get("validation_errors", [])]
        assert "E003" in codes, f"Expected E003 (required-field missing) from loaded schema; got {codes}"

    def test_decision_log_schema_required_field_set_matches_declared_constant(self) -> None:
        """Schema declares all five SCHEMA_REQUIRED fields AND each one is independently enforced.

        TMG concern 2 + concern 1 hand-shake: the loader-level field-presence
        check is paired with a parametrised RED probe that confirms every
        declared REQUIRED field is independently enforced by the validator,
        not merely present in the SchemaDefinition object.
        """
        schema = load_schema_by_name("DECISION_LOG")
        assert schema is not None

        for field_name in _REQUIRED_FIELDS:
            assert field_name in schema.fields, f"Schema should declare {field_name} field"

            # Drive a negative case per field: a payload missing only this field
            # must reject with a field-named E003.
            payload_fields = {
                "TOKEN": "HO-PROBE-20260515",
                "TIER": "ARCHITECTURAL",
                "STATUS": "BINDING",
                "DECISION": "probe_decision",
                "BECAUSE": "[probe_rationale]",
            }
            payload_fields.pop(field_name)
            body = "\n".join(f"  {k}::{v}" for k, v in payload_fields.items())
            content = (
                "===DECISIONS_OCTAVE_v20260417===\n"
                "META:\n"
                "  TYPE::DECISION_LOG\n"
                '  VERSION::"1.0"\n'
                "T:\n"
                f"{body}\n"
                "===END==="
            )
            result = _validate_content(content)
            assert result["validation_status"] == "INVALID", (
                f"Schema field {field_name} declared REQ but validator accepted payload missing it. "
                f"Errors: {result.get('validation_errors', [])}"
            )


# ---------------------------------------------------------------------------
# RED: parametrised rejection matrix — one assertion per REQ field, each
# backed by an on-disk fixture and asserting a distinct E003-class error
# carrying the missing field's name (TMG concern 1).
# ---------------------------------------------------------------------------


class TestDecisionLogSchemaRejectsMalformed:
    """Parametrised REQ-field rejection matrix, fixture-driven."""

    @pytest.mark.parametrize(
        "missing_field, fixture_name",
        [
            ("TOKEN", "malformed_missing_token.oct.md"),
            ("TIER", "malformed_missing_tier.oct.md"),
            ("STATUS", "malformed_missing_status.oct.md"),
            ("DECISION", "malformed_missing_decision.oct.md"),
            ("BECAUSE", "malformed_missing_because.oct.md"),
        ],
    )
    def test_decision_log_rejects_payload_missing_required_field(self, missing_field: str, fixture_name: str) -> None:
        """A decision-log document missing any SCHEMA_REQUIRED field MUST reject with E003.

        Parametrised across the full SCHEMA_REQUIRED set. Each parametrisation
        is backed by an on-disk fixture under tests/fixtures/decision_log/ so
        the rejection corpus is fully materialised on disk (I4 auditability).

        Assertions per parametrisation:
        1. ``validation_status`` is ``INVALID``.
        2. ``valid`` is False.
        3. At least one validation error carries code ``E003`` (required-field
           constraint violation — the validator's REQ-class rejection code).
        4. The missing field's name appears in the error message, proving
           the error is field-specific (not a generic "something missing").

        Does NOT depend on ENUM rejection (GH#435 PARTIAL). Depends only on
        REQ-constraint enforcement, which the validator implements (see
        ``test_debate_schema.py`` and ``test_cognition_schema.py`` for prior art).
        """
        fixture = _FIXTURES_DIR / fixture_name
        assert fixture.exists(), f"Fixture missing: {fixture}"

        result = _validate_content(fixture.read_text(encoding="utf-8"))

        assert result["validation_status"] == "INVALID", (
            f"Fixture {fixture_name} (missing {missing_field}) should be INVALID. "
            f"Got: {result.get('validation_status')}. "
            f"Errors: {result.get('validation_errors', [])}"
        )
        assert result["valid"] is False, f"Fixture {fixture_name} (missing {missing_field}) should report valid=False"

        errors = result.get("validation_errors", [])
        e003_errors = [e for e in errors if e.get("code") == "E003"]
        assert e003_errors, (
            f"Fixture {fixture_name} (missing {missing_field}) should emit at least one "
            f"E003 (required-field-missing) error. Got error codes: "
            f"{[e.get('code') for e in errors]}"
        )

        field_named_errors = [e for e in e003_errors if missing_field in (e.get("message") or "")]
        assert field_named_errors, (
            f"Fixture {fixture_name}: at least one E003 error must name the missing "
            f"field '{missing_field}'. Got messages: {[e.get('message') for e in e003_errors]}"
        )


# ---------------------------------------------------------------------------
# GREEN: on-disk positive fixtures validate against the DECISION_LOG schema.
#
# Fixtures live in ``tests/fixtures/decision_log/`` and cover one minimal
# record per tier. They are intentionally synthesised (not copied from the
# elevana-studio reference document) to keep the test corpus self-contained
# and stable across the schema sweep — the external reference is enumerated
# in the PR body, not embedded as fixture.
# ---------------------------------------------------------------------------


class TestDecisionLogFixturesValidate:
    """On-disk positive fixture-driven validation tests (one per tier)."""

    @pytest.mark.parametrize(
        "fixture_name",
        [
            "architectural_minimal.oct.md",
            "convention_minimal.oct.md",
            "micro_minimal.oct.md",
        ],
    )
    def test_minimal_tier_fixture_validates(self, fixture_name: str) -> None:
        """Each minimal-per-tier fixture MUST validate clean.

        Parametrised across the three tiers (ARCHITECTURAL with ISSUE_REF,
        CONVENTION inline-only, MICRO with ENFORCEMENT_REF) to prove the
        SCHEMA_REQUIRED set is enforced uniformly while tier-specific optional
        fields are accepted.
        """
        fixture = _FIXTURES_DIR / fixture_name
        assert fixture.exists(), f"Fixture missing: {fixture}"

        result = _validate_content(fixture.read_text(encoding="utf-8"))

        assert result["validation_status"] == "VALIDATED", (
            f"{fixture_name} should validate. "
            f"Got: {result.get('validation_status')}. "
            f"Errors: {result.get('validation_errors', [])}"
        )
        assert result["valid"] is True


# ---------------------------------------------------------------------------
# SCHEMA_REQUIRED_EXCEPTIONS: the schema declares stub-pointer entries
# (STATUS::SUPERSEDED_BY_*) exempt from BECAUSE and DECISION REQUIREDs.
#
# Validator-time enforcement of this exception is NOT YET IMPLEMENTED — the
# validator currently applies the SCHEMA_REQUIRED set uniformly regardless of
# STATUS value (a known limitation analogous to GH#435 ENUM PARTIAL and the
# tier-conditional REQ gap noted in the PR body).
#
# Tests below pin both sides of the contract:
# - Negative case (non-stub missing DECISION+BECAUSE rejects) — PASSES today,
#   proving the validator does enforce REQ for active entries.
# - Positive case (stub missing DECISION+BECAUSE should validate per the
#   declared exception) — xfail-marked because the validator does not yet
#   consume SCHEMA_REQUIRED_EXCEPTIONS. Strict xfail surfaces the gap and
#   will auto-convert to a regression alarm the moment exception enforcement
#   lands in the validator surface.
# ---------------------------------------------------------------------------


class TestDecisionLogSchemaRequiredExceptions:
    """SCHEMA_REQUIRED_EXCEPTIONS stub-pointer path — pins both sides of the contract."""

    def test_nonstub_missing_decision_and_because_rejects(self) -> None:
        """Negative case: a non-stub entry missing DECISION+BECAUSE MUST reject.

        Pins the current validator contract: REQ-class fields are enforced
        for all non-stub entries. This test passes today and guards against
        any future change that would silently relax REQ-constraint enforcement
        for active decision entries.
        """
        fixture = _FIXTURES_DIR / "malformed_nonstub_missing_decision_and_because.oct.md"
        assert fixture.exists(), f"Fixture missing: {fixture}"

        result = _validate_content(fixture.read_text(encoding="utf-8"))

        assert result["validation_status"] == "INVALID", (
            f"Non-stub entry missing DECISION+BECAUSE should reject. "
            f"Got: {result.get('validation_status')}. "
            f"Errors: {result.get('validation_errors', [])}"
        )
        assert result["valid"] is False

        errors = result.get("validation_errors", [])
        e003_codes = [e for e in errors if e.get("code") == "E003"]
        e003_fields = {
            field for e in e003_codes for field in ("DECISION", "BECAUSE") if field in (e.get("message") or "")
        }
        assert e003_fields == {"DECISION", "BECAUSE"}, (
            f"Non-stub rejection should name both DECISION and BECAUSE. "
            f"Got error messages: {[e.get('message') for e in e003_codes]}"
        )

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "SCHEMA_REQUIRED_EXCEPTIONS is declared in the schema but not yet "
            "enforced at validator time — stub-status entries (STATUS::SUPERSEDED_BY_*) "
            "currently produce the same E003 errors as active entries. Tracking "
            "this as a known limitation analogous to GH#435 ENUM PARTIAL. When "
            "the validator learns to consume SCHEMA_REQUIRED_EXCEPTIONS this xfail "
            "will flip to XPASS (strict) and require explicit conversion to a "
            "regular green test, surfacing the change for review."
        ),
    )
    def test_stub_missing_decision_and_because_validates(self) -> None:
        """Positive case: a stub-status entry missing DECISION+BECAUSE SHOULD validate per the declared exception.

        Currently xfail because the validator does not yet enforce
        SCHEMA_REQUIRED_EXCEPTIONS. Reference document
        ``/Volumes/HestAI-Projects/elevana-studio/.hestai/decisions/DECISIONS.oct.md``
        declares (META block, POLICY_SUPERSEDED_AS_STUB):

            Active entries with STATUS::SUPERSEDED_BY carry only TOKEN + STATUS
            + SUPERSEDED_BY pointer + CANONICAL reference to archive section.

        When validator-time exception enforcement lands, this test will XPASS
        (strict=True converts unexpected pass into failure) — that failure is
        the intended regression signal to convert the test to a normal green
        assertion and to remove the xfail marker.
        """
        fixture = _FIXTURES_DIR / "stub_superseded_minimal.oct.md"
        assert fixture.exists(), f"Fixture missing: {fixture}"

        result = _validate_content(fixture.read_text(encoding="utf-8"))

        assert result["validation_status"] == "VALIDATED", (
            f"Stub-pointer entry should validate per SCHEMA_REQUIRED_EXCEPTIONS. "
            f"Got: {result.get('validation_status')}. "
            f"Errors: {result.get('validation_errors', [])}"
        )
        assert result["valid"] is True
