"""Schema-source idempotency gate (GH-420 meta-grammar preservation).

This module enforces the structural invariant established in debate thread
``2026-05-14-octave-mcp-octavewrite-meta-gr-01krjzag``: every ``.oct.md``
schema source file under ``src/octave_mcp/resources/specs/schemas/`` MUST
survive ``octave_write`` in normalize mode byte-identically.

Background
==========

The lenient-parsing repair pass ``_auto_quote_section_refs_in_values``
(``src/octave_mcp/mcp/write.py``) was, prior to Shape F, scanning every
line for an unquoted ``§`` token and quoting it. On schema sources this
destroyed holographic operator spans of the form::

    THREAD_ID::["example"∧REQ→§INDEXER]

becoming::

    THREAD_ID::["example"∧REQ→"§INDEXER"]

or, further downstream after canonicalisation, fragmenting the value
entirely. Either outcome violates:

* PROD::I1::SYNTACTIC_FIDELITY — normalisation altered syntax in a way
  that altered semantics (the operator chain is no longer a holographic
  pattern; it is a key with a quoted-section list).
* PROD::I3::MIRROR_CONSTRAINT — repair invented new tokens (``"§"``
  wrappers) rather than reflecting present structure.
* PROD::I4::TRANSFORM_AUDITABILITY — without this gate, no auditable
  receipt proves schema sources round-trip stably.
* PROD::I5::SCHEMA_SOVEREIGNTY — schemas that cannot round-trip
  destabilise the entire validation surface.

Shape F (lexical sanctuary) cures the destruction by skipping repair on
lines whose bracketed value contains the parser-recognised holographic
operator chain (``∧``, ``→§`` / ``->§``). The recognition functions live
in ``src/octave_mcp/core/holographic.py`` (parser sovereignty); the
repair pass defers to them rather than maintaining a parallel operator
catalogue.

CI gate contract
================

Each ``.oct.md`` schema source MUST be byte-identical after one pass of
``octave_write`` in normalize mode (no ``content``, no ``changes``). The
test is parameterised over ``glob('*.oct.md')`` so future schemas land
under the same protection automatically.

The test runs in the default pytest target (no opt-in marker). A failure
blocks the release — see ADR-0006 SR1-T4 ``octave_write_no_op_invariant``
for the precedent.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

import pytest

from octave_mcp.mcp.write import WriteTool

# Locate the schema source corpus from the installed package layout.
# This is intentionally NOT a hardcoded list — new schemas inherit the
# gate automatically.
_SCHEMAS_DIR = Path(__file__).resolve().parents[2] / "src" / "octave_mcp" / "resources" / "specs" / "schemas"


def _discover_schema_sources() -> list[Path]:
    """Return all .oct.md schema source files under the schemas resource dir."""
    if not _SCHEMAS_DIR.is_dir():
        return []
    return sorted(_SCHEMAS_DIR.glob("*.oct.md"))


_SCHEMA_FILES = _discover_schema_sources()


def _run_octave_write_normalize(content_bytes: bytes) -> bytes:
    """Run octave_write in normalize mode on ``content_bytes`` and return result.

    Normalize mode is selected by passing neither ``content`` nor ``changes``.
    The tool re-emits the existing file in canonical form, which is the
    operation that previously destroyed holographic spans.
    """
    tool = WriteTool()

    async def _execute() -> bytes:
        with tempfile.NamedTemporaryFile(suffix=".oct.md", mode="wb", delete=False) as f:
            f.write(content_bytes)
            path = f.name
        try:
            result = await tool.execute(target_path=path)
            assert result.get("status") == "success", (
                f"octave_write normalize-mode failed: {result.get('errors')!r}"
            )
            with open(path, "rb") as fp:
                return fp.read()
        finally:
            os.unlink(path)

    return asyncio.run(_execute())


@pytest.mark.skipif(
    not _SCHEMA_FILES,
    reason="No schema source files discovered under specs/schemas/ — gate trivially passes",
)
@pytest.mark.parametrize(
    "schema_path",
    _SCHEMA_FILES,
    ids=lambda p: p.name,
)
def test_schema_source_round_trips_byte_identical(schema_path: Path) -> None:
    """Every schema source MUST be byte-identical after octave_write normalize.

    This is the release-blocker invariant: if a schema source cannot survive
    octave_write byte-identically, the validation surface is unstable and the
    release is held.
    """
    original_bytes = schema_path.read_bytes()
    round_tripped_bytes = _run_octave_write_normalize(original_bytes)

    if original_bytes != round_tripped_bytes:
        # Surface a precise diagnostic so reviewers see the exact destruction
        # site without having to re-run instrumentation manually.
        original_lines = original_bytes.splitlines()
        rt_lines = round_tripped_bytes.splitlines()
        diff_excerpts: list[str] = []
        for lineno, (a, b) in enumerate(zip(original_lines, rt_lines), start=1):
            if a != b:
                diff_excerpts.append(
                    f"  line {lineno}:\n    IN : {a!r}\n    OUT: {b!r}"
                )
                if len(diff_excerpts) >= 3:
                    break
        if len(original_lines) != len(rt_lines):
            diff_excerpts.append(
                f"  line count: IN={len(original_lines)} OUT={len(rt_lines)}"
            )
        pytest.fail(
            f"Schema source {schema_path.name} is not byte-identical after "
            f"octave_write normalize (PROD::I1/I3/I4/I5 violation):\n"
            + "\n".join(diff_excerpts)
        )


def test_holographic_operator_chain_survives_auto_quote_pass() -> None:
    """Direct unit-level RED: the _auto_quote pass MUST NOT mutate holographic spans.

    This is the minimal reproducer for the destruction mechanism: a single
    line containing a holographic pattern of the form
    ``KEY::["example"∧CONSTRAINT→§TARGET]`` is fed to
    ``_auto_quote_section_refs_in_values`` directly. Before Shape F the
    function wrapped ``§TARGET`` in quotes; after Shape F the function
    defers to the parser's holographic-pattern recognition and leaves the
    line untouched.

    Defends against any future regression to a closed operator regex
    catalogue (which would silently re-introduce the same bug whenever a
    new operator is added to the OCTAVE meta-grammar).
    """
    from octave_mcp.mcp.write import _auto_quote_section_refs_in_values

    holographic_line = '  THREAD_ID::["example-debate-001"∧REQ→§INDEXER]'
    content = (
        "===TEST===\n"
        "META:\n"
        f"{holographic_line}\n"
        "===END===\n"
    )

    output, corrections = _auto_quote_section_refs_in_values(content)

    assert output == content, (
        "Holographic operator span was mutated by _auto_quote_section_refs_in_values "
        "(PROD::I1/I3 violation). Shape F lexical sanctuary must defer to "
        "core.holographic recognition rather than blanket-quoting any unquoted §."
        f"\n  INPUT : {content!r}"
        f"\n  OUTPUT: {output!r}"
        f"\n  CORRECTIONS: {corrections!r}"
    )
    assert not corrections, (
        "Holographic line generated W_UNQUOTED_SECTION_IN_VALUE correction — "
        "the parser-deferred sanctuary should not emit corrections on lines "
        "whose bracketed value is itself a holographic pattern."
    )
