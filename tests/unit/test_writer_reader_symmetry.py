"""HARD_SYMMETRY roundtrip suite (ADR-0006 SR0-T1, GH#380).

Enforces the writer/reader symmetry invariant:

    For every byte sequence b:
        octave_validate(b).valid == True
            =>  octave_write(target=tmp, content=b, dry_run=True).status == "success"
            AND no correction has empty/missing `after` (when `before`/`after`
                schema is in use)
            AND diff_unified non-empty IFF corrections non-empty

Violation of any conjunct is a release blocker per ADR-0006.

Corpus
------
1. Static fixture corpus: every ``.oct.md`` under ``tests/fixtures/`` is
   discovered via glob and asserted parametrically. New fixtures land in the
   suite automatically.
2. Targeted regression fixture: ``tests/fixtures/symmetry/empty_triple_quoted.oct.md``
   is the minimal repro of the empty-``after`` W002 emission documented in
   ADR-0006 (originally surfaced against ``DECISIONS-example.oct.md``). This
   fixture exists to keep the SR0-T2 fix honest in CI.

The Hypothesis-grammar fuzzer mentioned in ADR §51 is deferred to a follow-up
issue. The static corpus + targeted fixture is the merge gate for SR0-T1.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import pytest

from octave_mcp.mcp.validate import ValidateTool
from octave_mcp.mcp.write import WriteTool

# Repository root: tests/unit/test_writer_reader_symmetry.py -> repo root
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"


def _discover_fixtures() -> list[Path]:
    """Discover every .oct.md fixture under tests/fixtures/.

    Returns paths sorted for stable test IDs.
    """
    if not FIXTURES_DIR.is_dir():
        return []
    return sorted(FIXTURES_DIR.rglob("*.oct.md"))


def _fixture_id(path: Path) -> str:
    """Stable, readable test ID for a fixture path."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


FIXTURES = _discover_fixtures()


def _assert_correction_after_non_empty(correction: dict[str, Any], fixture_id: str) -> None:
    """A correction emitted under the before/after schema must have a
    non-empty `after`.

    Corrections may legitimately use the alternative ``original``/``repaired``
    schema (e.g. W_UNQUOTED_SECTION_IN_VALUE, W_REPAIR_CANDIDATE). Those are
    out of scope for this assertion; the HARD_SYMMETRY invariant in ADR-0006
    targets the destructive empty-``after`` case where a normalisation claims
    a replacement and supplies none.
    """
    if "before" not in correction:
        # Different schema (original/repaired) — out of scope here.
        return
    after = correction.get("after")
    assert after is not None and after != "", (
        f"HARD_SYMMETRY violation in {fixture_id}: correction {correction.get('code')!r} "
        f"emitted with empty/missing `after`. "
        f"This is a destructive normalisation that fabricates a deletion not "
        f"present in source intent (ADR-0006 / I3 / I4). Full record: {correction!r}"
    )


@pytest.mark.parametrize(
    "fixture_path",
    FIXTURES,
    ids=[_fixture_id(p) for p in FIXTURES],
)
@pytest.mark.asyncio
async def test_hard_symmetry_roundtrip(fixture_path: Path) -> None:
    """For every valid fixture, octave_write(dry_run) must succeed without
    fabricating destructive corrections, and diff_unified must agree with
    the corrections list."""
    fixture_id = _fixture_id(fixture_path)
    content_bytes = fixture_path.read_bytes()
    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        pytest.skip(f"{fixture_id}: not utf-8")

    validate_tool = ValidateTool()
    write_tool = WriteTool()

    # Step 1: validate. We try the META schema first (covers every
    # OCTAVE doc). If validation reports the fixture as invalid we skip —
    # HARD_SYMMETRY only applies to docs that octave_validate accepts.
    validate_result = await validate_tool.execute(content=content, schema="META")
    if validate_result.get("status") != "success" or validate_result.get("errors"):
        pytest.skip(
            f"{fixture_id}: octave_validate did not accept fixture "
            f"(status={validate_result.get('status')}, "
            f"errors={len(validate_result.get('errors', []))}); "
            f"HARD_SYMMETRY is conditioned on validate.valid"
        )

    # Step 2: round-trip via dry-run write.
    with tempfile.NamedTemporaryFile(suffix=".oct.md", delete=False, mode="wb") as tmp:
        tmp.write(content_bytes)
        tmp_path = tmp.name
    try:
        write_result = await write_tool.execute(
            target_path=tmp_path,
            content=content,
            dry_run=True,
        )
    finally:
        os.unlink(tmp_path)

    # Step 3a: status must be success.
    assert write_result.get("status") == "success", (
        f"HARD_SYMMETRY violation in {fixture_id}: octave_validate accepted "
        f"the fixture but octave_write(dry_run) returned "
        f"status={write_result.get('status')!r}, "
        f"errors={write_result.get('errors')}"
    )

    # Step 3b: no correction may have an empty `after` (when before/after schema is used).
    corrections = write_result.get("corrections", []) or []
    for correction in corrections:
        _assert_correction_after_non_empty(correction, fixture_id)

    # Step 3c: diff_unified non-empty IFF corrections non-empty.
    diff_unified = write_result.get("diff_unified", "") or ""
    has_corrections = bool(corrections)
    has_diff = bool(diff_unified.strip())
    assert has_corrections == has_diff, (
        f"HARD_SYMMETRY violation in {fixture_id}: corrections list and "
        f"diff_unified disagree. corrections={len(corrections)}, "
        f"diff_unified_empty={not has_diff}. "
        f"I4 audit-trail invariant requires the rendered diff to reflect "
        f"every emitted correction (ADR-0006). "
        f"corrections={corrections!r}; diff_unified={diff_unified!r}"
    )


@pytest.mark.asyncio
async def test_corpus_is_non_trivial() -> None:
    """Guard: ensure the discovery glob actually found fixtures.

    Without this, an accidental rename of tests/fixtures/ would cause the
    parametrized suite to be empty and silently green.
    """
    assert FIXTURES, (
        f"No .oct.md fixtures discovered under {FIXTURES_DIR}. "
        f"The HARD_SYMMETRY suite must run against a non-empty corpus."
    )
