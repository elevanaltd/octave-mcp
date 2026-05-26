"""Multi-envelope idempotency CI gate (GH #420 AC3, PR-B of v1.13.0).

Parallel to ``test_schema_write_idempotency`` but parametrised over
``tests/fixtures/multi_envelope/*.oct.md`` rather than the schemas
resource dir.  Asserts that every multi-envelope fixture is:

1. **Mathematically idempotent** through ``octave_write`` normalise mode
   — the second pass MUST produce bytes identical to the first pass
   (the canonical form is a stable fixed point).
2. **Byte-stable under preserve mode** — the first pass MUST equal the
   original input.  Preserve mode is the strongest guarantee multi-
   envelope documents need: every envelope's bytes slice verbatim from
   baseline when no atom has changed.

Why a separate test module rather than widening the schemas glob: the
schemas idempotency gate enforces canonical-form properties scoped to
schema source files (holographic operator preservation, etc.) that don't
apply to multi-envelope content cards.  Keeping the two gates separate
preserves each glob's scope intent while still covering AC3.

A failure here blocks v1.13.0 — the multi-envelope round-trip is the
release-blocker this PR resolves.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

import pytest

from octave_mcp.mcp.write import WriteTool

_MULTI_ENVELOPE_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "multi_envelope"


def _discover_multi_envelope_fixtures() -> list[Path]:
    """Return all ``.oct.md`` multi-envelope fixtures under the fixture dir.

    Future fixtures (additional FRAME_CARD shapes, CONCEPT_CARD shapes,
    or any other multi-envelope document family) inherit the gate
    automatically by dropping a file into the directory.
    """
    if not _MULTI_ENVELOPE_FIXTURE_DIR.is_dir():
        return []
    return sorted(_MULTI_ENVELOPE_FIXTURE_DIR.glob("*.oct.md"))


_FIXTURE_FILES = _discover_multi_envelope_fixtures()


def _run_octave_write_normalize(content_bytes: bytes, *, format_style: str | None = None) -> bytes:
    """Run octave_write in normalize mode on ``content_bytes``; return result.

    Normalize mode is selected by passing neither ``content`` nor
    ``changes``.  The tool re-emits the existing file in canonical (or
    preserve) form, exercising the parser->emitter round-trip via the
    public surface.
    """
    tool = WriteTool()

    async def _execute() -> bytes:
        with tempfile.NamedTemporaryFile(suffix=".oct.md", mode="wb", delete=False) as f:
            f.write(content_bytes)
            path = f.name
        try:
            kwargs: dict = {"target_path": path}
            if format_style is not None:
                kwargs["format_style"] = format_style
            result = await tool.execute(**kwargs)
            assert result.get("status") == "success", f"octave_write normalize-mode failed: {result.get('errors')!r}"
            with open(path, "rb") as fp:
                return fp.read()
        finally:
            os.unlink(path)

    return asyncio.run(_execute())


@pytest.mark.skipif(
    not _FIXTURE_FILES,
    reason="No multi-envelope fixtures discovered — gate trivially passes",
)
@pytest.mark.parametrize(
    "fixture_path",
    _FIXTURE_FILES,
    ids=lambda p: p.name,
)
def test_multi_envelope_preserve_is_byte_stable(fixture_path: Path) -> None:
    """AC1/AC2: preserve-mode round-trip MUST be byte-identical.

    Every multi-envelope fixture, when fed through octave_write in
    preserve mode (no changes/content), must return bytes IDENTICAL to
    the input.  This is the strongest guarantee multi-envelope documents
    need: it proves that Strategy A's per-envelope dirty/baseline-span
    contract correctly slices unchanged envelopes verbatim from
    baseline.

    Pre-fix behaviour (#420 on main): 57% byte loss because the parser
    dropped envelopes #2..N.  Option D restores Mirror Constraint (I3).
    """
    original_bytes = fixture_path.read_bytes()
    round_tripped = _run_octave_write_normalize(original_bytes, format_style="preserve")

    if round_tripped != original_bytes:
        pytest.fail(
            f"GH #420 regression on {fixture_path.name}: preserve-mode "
            f"round-trip is NOT byte-stable.\n"
            f"  input_bytes  = {len(original_bytes)}\n"
            f"  output_bytes = {len(round_tripped)}\n"
            f"  byte_delta   = {len(original_bytes) - len(round_tripped)}\n"
            f"PROD::I1 (SYNTACTIC_FIDELITY) violation."
        )


@pytest.mark.skipif(
    not _FIXTURE_FILES,
    reason="No multi-envelope fixtures discovered — gate trivially passes",
)
@pytest.mark.parametrize(
    "fixture_path",
    _FIXTURE_FILES,
    ids=lambda p: p.name,
)
def test_multi_envelope_canonical_form_is_idempotent_fixed_point(fixture_path: Path) -> None:
    """AC3: canonical form of every multi-envelope fixture MUST be a fixed point.

    Mathematical idempotency: octave_write(octave_write(x)) == octave_write(x).
    The second pass must produce bytes IDENTICAL to the first.  This is
    the foundational invariant downstream auditors rely on.  If the
    second pass produces different bytes, the multi-envelope
    canonicalisation has no stable fixed point and PROD::I4
    (TRANSFORM_AUDITABILITY) is unenforceable.

    Tested under default (no format_style) normalize mode — the canonical
    pipeline that produces the on-disk shape.
    """
    original_bytes = fixture_path.read_bytes()
    first_pass = _run_octave_write_normalize(original_bytes)
    second_pass = _run_octave_write_normalize(first_pass)

    if first_pass != second_pass:
        first_lines = first_pass.splitlines()
        second_lines = second_pass.splitlines()
        diff_excerpts: list[str] = []
        for lineno, (a, b) in enumerate(zip(first_lines, second_lines, strict=False), start=1):
            if a != b:
                diff_excerpts.append(f"  line {lineno}:\n    PASS1: {a!r}\n    PASS2: {b!r}")
                if len(diff_excerpts) >= 3:
                    break
        if len(first_lines) != len(second_lines):
            diff_excerpts.append(f"  line count: PASS1={len(first_lines)} PASS2={len(second_lines)}")
        pytest.fail(
            f"GH #420 regression on {fixture_path.name}: canonical form is "
            f"not a fixed point (PROD::I4 violation):\n" + "\n".join(diff_excerpts)
        )


@pytest.mark.skipif(
    not _FIXTURE_FILES,
    reason="No multi-envelope fixtures discovered — gate trivially passes",
)
@pytest.mark.parametrize("format_style", ["preserve", "expanded", "compact", None])
@pytest.mark.parametrize(
    "fixture_path",
    _FIXTURE_FILES,
    ids=lambda p: p.name,
)
def test_multi_envelope_all_envelopes_survive_format_style_matrix(fixture_path: Path, format_style: str | None) -> None:
    """AC1: across the full ``format_style`` matrix, every envelope name survives.

    Even though canonical-form differences are expected between modes
    (e.g. expanded breaks short lists across multiple lines), NO mode
    may DROP an envelope.  We extract every ``===NAME===`` header from
    the source and assert each appears verbatim in the round-tripped
    output.
    """
    original_text = fixture_path.read_text(encoding="utf-8")
    # Extract every envelope name from the source.  The shape is
    # ``===NAME===`` on its own line; we accept any non-empty identifier.
    envelope_headers = [
        line
        for line in original_text.splitlines()
        if line.startswith("===") and line.endswith("===") and line != "===END==="
    ]
    assert envelope_headers, f"Fixture {fixture_path.name} contains no envelope headers"

    round_tripped = _run_octave_write_normalize(original_text.encode("utf-8"), format_style=format_style).decode(
        "utf-8"
    )

    missing = [h for h in envelope_headers if h not in round_tripped]
    if missing:
        pytest.fail(
            f"GH #420 regression on {fixture_path.name} "
            f"(format_style={format_style!r}): {len(missing)} envelope header(s) "
            f"dropped on round-trip:\n  missing: {missing!r}"
        )
