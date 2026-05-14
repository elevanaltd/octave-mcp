"""Schema-source idempotency gate (GH-420 meta-grammar preservation).

This module enforces the structural invariant established in debate thread
``2026-05-14-octave-mcp-octavewrite-meta-gr-01krjzag``: every ``.oct.md``
schema source file under ``src/octave_mcp/resources/specs/schemas/`` MUST:

1. **Be mathematically idempotent** through ``octave_write`` normalise mode —
   the second pass MUST produce bytes identical to the first pass (the
   canonical form is a stable fixed point).
2. **Preserve every holographic operator chain** verbatim across one
   round-trip — the parser-recognised operators ``∧``, ``→§``, and
   ``->§`` and their surrounding bracket spans MUST appear in the
   round-tripped output exactly as they appear in the source. No
   fragmentation, no quote-wrapping of ``§TARGET`` tokens, no operator
   substitution.

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

Scope of the gate
=================

The invariants asserted here are the structural ones from the debate
verdict. They intentionally do NOT require *first-pass* byte-identity:
a schema source authored with extra blank lines, or with a bare-section
list value like ``TARGETS::[§INDEXER, §SELF]`` (which is NOT a
holographic pattern and is correctly auto-quoted under I1), will
canonicalise to a slightly different layout on its first pass through
``octave_write``. That is by design — canonicalisation is *expected* to
collapse non-load-bearing whitespace and quote bare-section refs in
non-holographic value positions.

What the gate forbids is:

* Destruction of holographic operator chains (the v1.13.0 release-blocker
  bug; cured by Shape F).
* Canonical-form drift (the fixed-point property of canonicalisation;
  the foundational invariant for every downstream auditor).

The tests are parameterised across ``glob('*.oct.md')`` so future
schemas inherit the protection automatically. They run in the default
pytest target (no opt-in marker). A failure blocks the release — see
ADR-0006 SR1-T4 ``octave_write_no_op_invariant`` for the precedent.
"""

from __future__ import annotations

import asyncio
import os
import re
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


# Regex matching one complete bracketed holographic value at the parser's
# recognition boundaries: the outer ``[...]`` containing at least one
# constraint operator (``∧``) or target arrow (``→§`` / ``->§``). Used by
# the preservation test below to extract every holographic span from the
# source and assert each one appears verbatim in the round-tripped output.
#
# The pattern is intentionally simple — it matches one level of nesting
# inside the outer brackets via ``[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*`` which
# accommodates inner brackets like ``ENUM[a,b]`` while still anchoring on
# the outer span. Holographic patterns nested more than one level deep are
# extremely rare in schema sources; if a future schema introduces deeper
# nesting the recognition can be widened (or, better, the test can call
# ``core.holographic`` directly).
_HOLOGRAPHIC_SPAN_RE = re.compile(
    r"\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*(?:∧|→§|->§)[^\[\]]*"
    r"(?:\[[^\[\]]*\][^\[\]]*)*\]"
)


@pytest.mark.skipif(
    not _SCHEMA_FILES,
    reason="No schema source files discovered under specs/schemas/ — gate trivially passes",
)
@pytest.mark.parametrize(
    "schema_path",
    _SCHEMA_FILES,
    ids=lambda p: p.name,
)
def test_schema_canonical_form_is_idempotent_fixed_point(schema_path: Path) -> None:
    """The canonical form of every schema source MUST be a fixed point of octave_write.

    Mathematical idempotency: octave_write(octave_write(x)) == octave_write(x).
    This is the foundational invariant that all downstream auditors rely on.
    If the second pass produces different bytes from the first, the
    transformation has no stable canonical form and PROD::I4
    (TRANSFORM_AUDITABILITY) is unenforceable.
    """
    original_bytes = schema_path.read_bytes()
    first_pass = _run_octave_write_normalize(original_bytes)
    second_pass = _run_octave_write_normalize(first_pass)

    if first_pass != second_pass:
        first_lines = first_pass.splitlines()
        second_lines = second_pass.splitlines()
        diff_excerpts: list[str] = []
        for lineno, (a, b) in enumerate(zip(first_lines, second_lines), start=1):
            if a != b:
                diff_excerpts.append(
                    f"  line {lineno}:\n    PASS1: {a!r}\n    PASS2: {b!r}"
                )
                if len(diff_excerpts) >= 3:
                    break
        if len(first_lines) != len(second_lines):
            diff_excerpts.append(
                f"  line count: PASS1={len(first_lines)} PASS2={len(second_lines)}"
            )
        pytest.fail(
            f"Canonical form of {schema_path.name} is not a fixed point "
            f"(PROD::I4 violation):\n" + "\n".join(diff_excerpts)
        )


@pytest.mark.skipif(
    not _SCHEMA_FILES,
    reason="No schema source files discovered under specs/schemas/ — gate trivially passes",
)
@pytest.mark.parametrize(
    "schema_path",
    _SCHEMA_FILES,
    ids=lambda p: p.name,
)
def test_schema_holographic_spans_survive_round_trip(schema_path: Path) -> None:
    """Every holographic operator span in the source MUST appear verbatim after octave_write.

    This is the Shape F structural invariant: the lenient-parse repair pass
    is forbidden from mutating any bracketed value whose contents include
    a parser-recognised holographic operator (``∧``, ``→§``, ``->§``). If
    any such span fails to appear verbatim in the round-tripped output, the
    repair pass has either fragmented it, quote-wrapped a ``§TARGET``
    token, or otherwise altered its lexical form — all of which violate
    PROD::I1 (SYNTACTIC_FIDELITY) and PROD::I3 (MIRROR_CONSTRAINT).
    """
    original_text = schema_path.read_text(encoding="utf-8")
    original_spans = _HOLOGRAPHIC_SPAN_RE.findall(original_text)

    if not original_spans:
        pytest.skip(
            f"{schema_path.name} contains no holographic spans — preservation "
            f"check trivially passes (the idempotency fixed-point test still applies)."
        )

    round_tripped_text = _run_octave_write_normalize(
        original_text.encode("utf-8")
    ).decode("utf-8")

    missing: list[str] = []
    for span in original_spans:
        if span not in round_tripped_text:
            missing.append(span)

    if missing:
        # Surface the first missing span and a snippet of the round-tripped
        # output so the destruction site is easy to find.
        pytest.fail(
            f"{schema_path.name}: {len(missing)} holographic operator span(s) "
            f"were destroyed by octave_write (PROD::I1/I3 violation):\n"
            f"  First missing: {missing[0]!r}\n"
            f"  Round-tripped output excerpt:\n"
            + "\n".join(
                f"    {line}"
                for line in round_tripped_text.splitlines()
                if "§" in line or "∧" in line
            )[:2000]
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


def test_ascii_arrow_holographic_pattern_also_protected() -> None:
    """ASCII variant ``->§`` of the target arrow MUST be protected too.

    The parser recognises both ``→§`` (Unicode) and ``->§`` (ASCII)
    forms (see ``core.holographic._find_target_start``). The sanctuary
    must defer to the parser for BOTH forms — otherwise a schema source
    using ASCII operators would still be silently destroyed.
    """
    from octave_mcp.mcp.write import _auto_quote_section_refs_in_values

    ascii_line = '  THREAD_ID::["example"∧REQ->§INDEXER]'
    content = f"===TEST===\nMETA:\n{ascii_line}\n===END===\n"
    output, corrections = _auto_quote_section_refs_in_values(content)
    assert output == content, (
        f"ASCII-arrow holographic span destroyed:\n  IN : {content!r}\n  OUT: {output!r}"
    )
    assert not corrections


def test_non_holographic_section_ref_still_gets_quoted() -> None:
    """The sanctuary is narrow: bare ``§REF`` in a non-holographic value MUST still be quoted.

    A line like ``KEY::§SOMETHING`` (no brackets, no operators) is the
    historic ``_auto_quote_section_refs_in_values`` target and remains
    so. Shape F adds protection only for lines whose bracketed value
    contains the parser-recognised holographic operator chain. This test
    pins the boundary: lift the sanctuary too widely and the original
    silent-data-loss bug (GH#329, GH#334) returns.
    """
    from octave_mcp.mcp.write import _auto_quote_section_refs_in_values

    content = "===TEST===\nMETA:\n  KEY::§SOMETHING\n===END===\n"
    output, corrections = _auto_quote_section_refs_in_values(content)
    assert output != content, (
        "Non-holographic bare §SOMETHING should be auto-quoted; sanctuary too wide"
    )
    assert any(c["code"] == "W_UNQUOTED_SECTION_IN_VALUE" for c in corrections), (
        "Auto-quote of non-holographic § value should emit W_UNQUOTED_SECTION_IN_VALUE"
    )
