"""GH-427 RED — DEBATE_TRANSCRIPT TURN_SCHEMA enforcement.

The schema source ``src/octave_mcp/resources/specs/schemas/debate_transcript.oct.md``
declares a ``TURN_SCHEMA:`` block describing the structure of each TURN entry
(ROLE REQ ENUM, CONTENT REQ, TURN_INDEX REQ, SPEAKER OPT). Prior to GH-427 the
schema extractor consumed only the top-level ``FIELDS:`` block and the
validator visitor had no concept of per-turn structure, so malformed TURN
entries (missing ROLE, duplicate TURN_INDEX, etc.) silently validated clean —
a documented false negative against North Star invariants:

* PROD::I1 SYNTACTIC_FIDELITY — well-formed transcripts must continue to
  validate (non-regression).
* PROD::I4 TRANSFORM_AUDITABILITY — validation status must reflect the
  declared turn-level contract.
* PROD::I5 SCHEMA_SOVEREIGNTY — a documented schema field block that the
  validator does not enforce is a sovereignty leak.

These tests pin the post-fix contract. They are intentionally written
BEFORE the schema/extractor/validator wiring lands so the RED commit captures
the documented-but-not-enforced gap.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from octave_mcp.mcp.validate import ValidateTool
from octave_mcp.schemas.loader import load_schema_by_name


SCHEMA_PATH = (
    Path(__file__).parent.parent.parent
    / "src"
    / "octave_mcp"
    / "resources"
    / "specs"
    / "schemas"
    / "debate_transcript.oct.md"
)


# ---------------------------------------------------------------------------
# Schema-source extraction contract
# ---------------------------------------------------------------------------


class TestTurnSchemaExtraction:
    """The loaded SchemaDefinition MUST expose a parsed turn schema."""

    def test_loaded_schema_exposes_turn_schema(self) -> None:
        """``SchemaDefinition`` MUST surface ``turn_schema`` as a dict of
        FieldDefinition objects extracted from the source ``TURN_SCHEMA:``
        block. Before GH-427 this attribute did not exist; the source block
        was silently discarded by ``_extract_fields``.
        """
        schema = load_schema_by_name("DEBATE_TRANSCRIPT")
        assert schema is not None

        turn_schema = getattr(schema, "turn_schema", None)
        assert turn_schema is not None, (
            "DEBATE_TRANSCRIPT.SchemaDefinition.turn_schema must be populated "
            "(GH-427 enforcement of the documented TURN_SCHEMA: block)."
        )
        # Required turn fields per GH-427 acceptance criteria.
        for required_key in ("ROLE", "CONTENT", "TURN_INDEX"):
            assert required_key in turn_schema, (
                f"turn_schema must declare REQ field '{required_key}' (GH-427)."
            )
        # Optional fields preserved.
        assert "SPEAKER" in turn_schema, "turn_schema must declare OPT field 'SPEAKER' (GH-427)."

    def test_turn_schema_role_enum_includes_expanded_values(self) -> None:
        """ROLE enum MUST cover Wind|Wall|Door|Synthesis|Human|Mediator per
        the GH-427 issue body. The pre-existing schema source only declared
        Wind|Wall|Door which is a strict subset of consumer reality
        (debate-hall-mcp emits Synthesis, Human, and Mediator turns).
        """
        schema = load_schema_by_name("DEBATE_TRANSCRIPT")
        assert schema is not None

        turn_schema = getattr(schema, "turn_schema", None)
        assert turn_schema is not None, "turn_schema must be populated for GH-427"

        role_field = turn_schema["ROLE"]
        raw = role_field.raw_value or ""
        for required_value in ("Wind", "Wall", "Door", "Synthesis", "Human", "Mediator"):
            assert required_value in raw, (
                f"TURN_SCHEMA.ROLE enum must include '{required_value}' "
                f"(GH-427 expanded enum); got raw={raw!r}"
            )


# ---------------------------------------------------------------------------
# Validator visitor enforcement (positive + negative cases)
# ---------------------------------------------------------------------------


def _run_validate(content: str, *, profile: str = "STANDARD") -> dict:
    """Execute ValidateTool against DEBATE_TRANSCRIPT and return the envelope."""
    tool = ValidateTool()
    return asyncio.run(
        tool.execute(
            content=content,
            schema="DEBATE_TRANSCRIPT",
            profile=profile,
        )
    )


WELL_FORMED_TRANSCRIPT = """===DEBATE_TRANSCRIPT===
META:
  TYPE::DEBATE_TRANSCRIPT
  VERSION::"1.0"

THREAD_ID::test-debate-gh427-positive
TOPIC::TURN_SCHEMA enforcement positive case
MODE::fixed
STATUS::closed
PARTICIPANTS::[Wind, Wall, Door]

TURNS:
  T1:
    ROLE::Wind
    CONTENT::Open the possibility space.
    TURN_INDEX::1
    SPEAKER::wind-agent
  T2:
    ROLE::Wall
    CONTENT::Stress-test against constraints.
    TURN_INDEX::2
  T3:
    ROLE::Door
    CONTENT::Synthesise the third way.
    TURN_INDEX::3

SYNTHESIS::Emergent third way captured.
===END==="""


MISSING_ROLE_TRANSCRIPT = """===DEBATE_TRANSCRIPT===
META:
  TYPE::DEBATE_TRANSCRIPT
  VERSION::"1.0"

THREAD_ID::test-debate-gh427-missing-role
TOPIC::TURN_SCHEMA enforcement missing ROLE
MODE::fixed
STATUS::closed
PARTICIPANTS::[Wind, Wall, Door]

TURNS:
  T1:
    CONTENT::No role declared, should be rejected.
    TURN_INDEX::1
  T2:
    ROLE::Wall
    CONTENT::Second turn is well-formed.
    TURN_INDEX::2
===END==="""


DUPLICATE_TURN_INDEX_TRANSCRIPT = """===DEBATE_TRANSCRIPT===
META:
  TYPE::DEBATE_TRANSCRIPT
  VERSION::"1.0"

THREAD_ID::test-debate-gh427-duplicate-index
TOPIC::TURN_SCHEMA enforcement duplicate TURN_INDEX
MODE::fixed
STATUS::closed
PARTICIPANTS::[Wind, Wall, Door]

TURNS:
  T1:
    ROLE::Wind
    CONTENT::First turn.
    TURN_INDEX::1
  T2:
    ROLE::Wall
    CONTENT::Second turn with colliding index.
    TURN_INDEX::1
===END==="""


INVALID_ROLE_ENUM_TRANSCRIPT = """===DEBATE_TRANSCRIPT===
META:
  TYPE::DEBATE_TRANSCRIPT
  VERSION::"1.0"

THREAD_ID::test-debate-gh427-bad-role
TOPIC::TURN_SCHEMA enforcement invalid ROLE enum
MODE::fixed
STATUS::closed
PARTICIPANTS::[Wind, Wall, Door]

TURNS:
  T1:
    ROLE::Heretic
    CONTENT::Not a permitted ROLE.
    TURN_INDEX::1
===END==="""


class TestTurnSchemaValidatorEnforcement:
    """Acceptance criteria from GH-427."""

    def test_well_formed_transcript_validates(self) -> None:
        """Existing well-formed transcripts MUST continue to validate clean."""
        result = _run_validate(WELL_FORMED_TRANSCRIPT)
        assert result["status"] == "success", result
        # I5: schema sovereignty — VALIDATED is the only acceptable terminal
        # status when no errors are present.
        assert result["validation_status"] == "VALIDATED", (
            f"Expected VALIDATED, got {result['validation_status']}: "
            f"errors={result.get('validation_errors')!r} "
            f"warnings={result.get('warnings')!r}"
        )

    def test_missing_role_is_rejected(self) -> None:
        """A turn missing the REQ ROLE field MUST surface a validation error."""
        result = _run_validate(MISSING_ROLE_TRANSCRIPT)
        # Either the top-level status indicates failure, or validation_errors
        # carries the documented error code. Be explicit and check both.
        assert result["validation_status"] == "INVALID", (
            f"Expected INVALID for missing ROLE, got {result['validation_status']}: "
            f"validation_errors={result.get('validation_errors')!r}"
        )
        validation_errors = result.get("validation_errors") or []
        # E_TURN_FIELD is the GH-427 enforcement code for missing REQ turn fields.
        codes = {err.get("code") for err in validation_errors}
        assert "E_TURN_FIELD" in codes, (
            f"Expected E_TURN_FIELD validation error for missing ROLE; "
            f"got codes={codes!r}"
        )
        # Field path must be specific enough to identify the offending turn.
        offending = [
            err
            for err in validation_errors
            if err.get("code") == "E_TURN_FIELD" and "ROLE" in (err.get("field") or "")
        ]
        assert offending, (
            "Missing-ROLE error must reference the ROLE field path; "
            f"got validation_errors={validation_errors!r}"
        )

    def test_duplicate_turn_index_is_rejected(self) -> None:
        """Two turns sharing TURN_INDEX MUST surface a validation error."""
        result = _run_validate(DUPLICATE_TURN_INDEX_TRANSCRIPT)
        assert result["validation_status"] == "INVALID", (
            f"Expected INVALID for duplicate TURN_INDEX, got "
            f"{result['validation_status']}: "
            f"validation_errors={result.get('validation_errors')!r}"
        )
        codes = {err.get("code") for err in result.get("validation_errors", [])}
        assert "E_TURN_INDEX" in codes, (
            f"Expected E_TURN_INDEX validation error for duplicate TURN_INDEX; "
            f"got codes={codes!r}"
        )

    def test_invalid_role_enum_is_rejected(self) -> None:
        """A ROLE value outside the declared ENUM MUST surface a validation error."""
        result = _run_validate(INVALID_ROLE_ENUM_TRANSCRIPT)
        assert result["validation_status"] == "INVALID", (
            f"Expected INVALID for out-of-enum ROLE, got "
            f"{result['validation_status']}: "
            f"validation_errors={result.get('validation_errors')!r}"
        )
        codes = {err.get("code") for err in result.get("validation_errors", [])}
        # E_TURN_FIELD wraps per-turn constraint violations including enum.
        assert "E_TURN_FIELD" in codes, (
            f"Expected E_TURN_FIELD validation error for invalid ROLE enum; "
            f"got codes={codes!r}"
        )


@pytest.mark.parametrize(
    "fixture,name",
    [
        (WELL_FORMED_TRANSCRIPT, "well_formed"),
        (MISSING_ROLE_TRANSCRIPT, "missing_role"),
        (DUPLICATE_TURN_INDEX_TRANSCRIPT, "duplicate_index"),
        (INVALID_ROLE_ENUM_TRANSCRIPT, "invalid_enum"),
    ],
)
def test_validator_returns_envelope_with_expected_keys(fixture: str, name: str) -> None:
    """All envelopes MUST surface validation_status — never crash on TURN_SCHEMA inputs."""
    result = _run_validate(fixture)
    assert "validation_status" in result, f"fixture={name} envelope missing validation_status"


def test_schema_source_declares_turn_schema_block() -> None:
    """The schema source MUST continue to declare a TURN_SCHEMA block (I1 fidelity)."""
    text = SCHEMA_PATH.read_text(encoding="utf-8")
    assert "TURN_SCHEMA:" in text, (
        "debate_transcript.oct.md must continue to declare TURN_SCHEMA: "
        "(GH-427 enforces this block; do not regress the source)."
    )
