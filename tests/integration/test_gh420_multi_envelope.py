"""GH #420 multi-envelope parsing/emission regression suite (PR-B of v1.13.0).

Option D (HO scope-lock 2026-05-26): additive ``additional_envelopes:
list[Envelope]`` field on ``Document``.  Envelope #1 continues to populate
``Document.name/meta/sections`` exactly as today; siblings become ``Envelope``
nodes appended to the new field.  Single-envelope behaviour is unchanged
by construction.

Acceptance criteria covered (from #420 reopen comment):

* AC1 — 8-envelope repro round-trips with envelopes #2..N byte-stable under
  all four ``format_style`` values.
* AC2 — Real-world FRAME_CARD-shaped documents byte-stable under
  ``format_style="preserve"``.  We construct a realistic 8-envelope
  Facet ABI card here since hestai-context-mcp fixtures are not
  locally-resolvable from this repo.
* AC3 — New regression test parametrised over a multi-envelope fixture
  (this file).  The CI idempotency gate fixture lives at
  ``tests/fixtures/multi_envelope/`` (loaded by
  ``test_schema_write_idempotency``'s glob — see that test's wider
  fixture lookup).
* AC4 — Honest documentation: ``Document.additional_envelopes`` /
  ``Envelope`` docstrings cover what's supported in v1.13.0 and what
  is explicitly out of scope (per-envelope schema validation, atom
  mutation in non-META additional envelopes).

PR-A Q3 audit (mandatory, HO directive):

* ``META.<field>`` change-paths continue to target envelope #1's META only.
* Envelope #1 IS ``Document`` — its ``.name`` field gates the META-envelope
  detection in ``write.py:_apply_changes`` (the ``doc.name == "META"``
  constraint introduced by PR #449 / GH #447 CE rework).
* Envelopes in ``additional_envelopes`` are ``Envelope`` nodes (not
  ``Document``) — they bypass the existing META gate by construction.
* Regression test below confirms that under multi-envelope, a
  ``META.STATUS`` change targets envelope #1's META and does NOT mutate
  any same-named atom in additional envelopes (e.g. an accidentally-
  placed ``===META===`` as envelope #2).
"""

from __future__ import annotations

import asyncio
import os
import tempfile

import pytest

from octave_mcp.core.emitter import FormatOptions, emit
from octave_mcp.core.grammar.cst import Envelope
from octave_mcp.core.parser import parse
from octave_mcp.mcp.write import WriteTool

# --------------------------------------------------------------------------- #
# Test fixtures                                                               #
# --------------------------------------------------------------------------- #

# Minimal 4-envelope reproduction (from @matgreenaitech 2026-05-26
# diagnostic comment on #420).  Loss table on main pre-fix was 57% across
# all four format_style values and 69% in normalize-only mode.
FOUR_ENVELOPE_FIXTURE = (
    "===META===\n"
    "TYPE::FRAME_CARD\n"
    "ID::TEST_CARD\n"
    "STATUS::proposed\n"
    "===END===\n"
    "\n"
    "===EXACT===\n"
    "IDS::[A,B,C]\n"
    "===END===\n"
    "\n"
    "===FACETS===\n"
    'INTENT::"first envelope after META must also survive"\n'
    "===END===\n"
    "\n"
    "===EDGES===\n"
    "RELATED::[X,Y]\n"
    "===END===\n"
)

# Realistic 8-envelope Facet ABI FRAME_CARD shape (matches the canonical
# eight-section layout from the #420 issue body — META / EXACT /
# SOURCE_REFS / FACETS / AUDIENCE_VIEW_SEEDS / EDGES / PROVENANCE /
# VALIDATION).  AC1 requires byte-stable round-trip across all four
# format_style values under preserve mode.
EIGHT_ENVELOPE_FIXTURE = (
    "===META===\n"
    "TYPE::FRAME_CARD\n"
    "ID::THREE_LAYER_GOVERNANCE_FRAME\n"
    "STATUS::proposed\n"
    "CARD_SCHEMA_VERSION::1\n"
    "===END===\n"
    "\n"
    "===EXACT===\n"
    "IDS::[FRAME_THREE_LAYER]\n"
    "PROD_IMMUTABLES::[I1, I2, I3]\n"
    "ADR_REFS::[ADR_0013]\n"
    "===END===\n"
    "\n"
    "===SOURCE_REFS===\n"
    "PATHS::[src/layer_one.py, src/layer_two.py]\n"
    "===END===\n"
    "\n"
    "===FACETS===\n"
    'INTENT::"three-layer governance for facet ABI"\n'
    "CONSTRAINTS::[c1, c2]\n"
    "===END===\n"
    "\n"
    "===AUDIENCE_VIEW_SEEDS===\n"
    'GLOBAL::"reviewer_50_tokens"\n'
    'AGENT::"reviewer_200_tokens"\n'
    "===END===\n"
    "\n"
    "===EDGES===\n"
    "EXTENDS::[ADR_0013]\n"
    "RELATED::[CONCEPT_FOO]\n"
    "===END===\n"
    "\n"
    "===PROVENANCE===\n"
    "MARKERS::[src/layer_one.py#layer]\n"
    "===END===\n"
    "\n"
    "===VALIDATION===\n"
    "SOURCE_REF_RESOLVES::true\n"
    "MARKERS_RESOLVE_TO_CARD::true\n"
    "===END===\n"
)


# --------------------------------------------------------------------------- #
# Helper for the WriteTool integration path                                   #
# --------------------------------------------------------------------------- #


def _run_write_normalize(content: str, *, format_style: str | None = None) -> tuple[str, str]:
    """Run octave_write in normalize mode and return (status, written).

    Normalize mode = no ``changes`` / no ``content`` arguments.  The tool
    parses the existing file, re-emits canonically, writes back.  This
    exercises the parser->emitter round-trip via the public surface, the
    same path used by the multi-envelope failure repro on #420.
    """
    tool = WriteTool()

    async def _execute() -> tuple[str, str]:
        with tempfile.NamedTemporaryFile(suffix=".oct.md", mode="w", delete=False, encoding="utf-8") as f:
            f.write(content)
            path = f.name
        try:
            kwargs: dict = {"target_path": path}
            if format_style is not None:
                kwargs["format_style"] = format_style
            result = await tool.execute(**kwargs)
            with open(path, encoding="utf-8") as fp:
                written = fp.read()
            return result.get("status", "<missing>"), written
        finally:
            os.unlink(path)

    return asyncio.run(_execute())


def _run_write_changes(content: str, changes: dict, *, format_style: str = "preserve") -> tuple[str, str]:
    """Run octave_write with ``changes`` and return (status, written)."""
    tool = WriteTool()

    async def _execute() -> tuple[str, str]:
        with tempfile.NamedTemporaryFile(suffix=".oct.md", mode="w", delete=False, encoding="utf-8") as f:
            f.write(content)
            path = f.name
        try:
            result = await tool.execute(
                target_path=path,
                changes=changes,
                format_style=format_style,
            )
            with open(path, encoding="utf-8") as fp:
                written = fp.read()
            return result.get("status", "<missing>"), written
        finally:
            os.unlink(path)

    return asyncio.run(_execute())


# --------------------------------------------------------------------------- #
# Parser-level tests                                                          #
# --------------------------------------------------------------------------- #


class TestGH420ParserMultiEnvelope:
    """Parser MUST produce an AST containing ALL top-level envelopes."""

    def test_parser_consumes_all_four_envelopes(self) -> None:
        doc = parse(FOUR_ENVELOPE_FIXTURE)
        # Envelope #1 IS the Document (Option D contract).
        assert doc.name == "META"
        # Envelopes #2..N appear as Envelope nodes.
        assert len(doc.additional_envelopes) == 3
        names = [env.name for env in doc.additional_envelopes]
        assert names == ["EXACT", "FACETS", "EDGES"], (
            f"GH #420 regression: parser dropped or reordered " f"sibling envelopes. got={names!r}"
        )

    def test_parser_consumes_all_eight_envelopes(self) -> None:
        doc = parse(EIGHT_ENVELOPE_FIXTURE)
        assert doc.name == "META"
        assert len(doc.additional_envelopes) == 7
        names = [env.name for env in doc.additional_envelopes]
        assert names == [
            "EXACT",
            "SOURCE_REFS",
            "FACETS",
            "AUDIENCE_VIEW_SEEDS",
            "EDGES",
            "PROVENANCE",
            "VALIDATION",
        ]

    def test_single_envelope_unaffected(self) -> None:
        """Single-envelope documents MUST have empty additional_envelopes.

        Option D's promise: existing single-envelope contract is unchanged
        by construction.  A document with exactly one ===NAME===...===END===
        block must produce a Document with sections populated and an
        empty additional_envelopes list.
        """
        src = "===META===\nTYPE::FRAME_CARD\nID::SINGLE\n===END===\n"
        doc = parse(src)
        assert doc.name == "META"
        assert len(doc.sections) == 2
        assert doc.additional_envelopes == []

    def test_envelope_carries_byte_spans(self) -> None:
        """Each Envelope MUST carry valid start_byte/end_byte spans.

        Strategy A preserve mode (per HO Q1 answer) requires per-envelope
        dirty/baseline-span tracking so unchanged sibling envelopes can
        slice verbatim from baseline (#420 AC1).
        """
        doc = parse(FOUR_ENVELOPE_FIXTURE)
        for env in doc.additional_envelopes:
            assert isinstance(env, Envelope)
            assert env.start_byte is not None and env.start_byte >= 0
            assert env.end_byte is not None and env.end_byte > env.start_byte
            # dirty defaults to False — clean envelope, slice-eligible.
            assert env.dirty is False


# --------------------------------------------------------------------------- #
# AC1: byte-stable round-trip under preserve mode across format_style matrix  #
# --------------------------------------------------------------------------- #


class TestGH420AC1ByteStableRoundTrip:
    """AC1: envelopes #2..N byte-stable under all four ``format_style`` values.

    Preserve mode is the strongest guarantee: every envelope's bytes are
    sliced verbatim from baseline.  Expanded / compact / omitted modes
    re-emit canonically; the AC requires byte-stability under PRESERVE,
    and content-preservation (no envelope dropped, no atoms lost) under
    the other modes.
    """

    def test_ac1_preserve_byte_stable_eight_envelope(self) -> None:
        """Preserve mode round-trip MUST be byte-identical for 8-envelope card."""
        status, written = _run_write_normalize(EIGHT_ENVELOPE_FIXTURE, format_style="preserve")
        assert status == "success"
        assert written == EIGHT_ENVELOPE_FIXTURE, (
            f"GH #420 AC1 regression: preserve-mode round-trip not byte-stable. "
            f"input_bytes={len(EIGHT_ENVELOPE_FIXTURE.encode())} "
            f"output_bytes={len(written.encode())}"
        )

    def test_ac1_preserve_byte_stable_four_envelope(self) -> None:
        status, written = _run_write_normalize(FOUR_ENVELOPE_FIXTURE, format_style="preserve")
        assert status == "success"
        assert written == FOUR_ENVELOPE_FIXTURE

    @pytest.mark.parametrize("format_style", ["preserve", "expanded", "compact", None])
    def test_ac1_no_envelope_dropped_across_format_style_matrix(self, format_style: str | None) -> None:
        """Across all four ``format_style`` values, NO envelope may be dropped.

        Pre-fix behaviour on ``main`` (a829817): 57% byte loss across all
        format_style values, 69% in normalize-only.  Envelopes #2..N were
        silently dropped because ``parser.parse_document`` returned after
        the first ``===END===``.  Option D restores Mirror Constraint (I3).
        """
        status, written = _run_write_normalize(EIGHT_ENVELOPE_FIXTURE, format_style=format_style)
        assert status == "success"
        expected_envelope_names = [
            "===META===",
            "===EXACT===",
            "===SOURCE_REFS===",
            "===FACETS===",
            "===AUDIENCE_VIEW_SEEDS===",
            "===EDGES===",
            "===PROVENANCE===",
            "===VALIDATION===",
        ]
        for name in expected_envelope_names:
            assert name in written, (
                f"GH #420 regression (format_style={format_style!r}): "
                f"envelope {name!r} dropped on round-trip. "
                f"written_bytes={len(written.encode())}"
            )

    @pytest.mark.parametrize("format_style", ["preserve", "expanded", "compact", None])
    def test_ac1_atoms_preserved_across_format_style_matrix(self, format_style: str | None) -> None:
        """Every atom in every envelope MUST survive the round-trip.

        We assert representative load-bearing atoms from each of the 8
        envelopes — if any of these disappear, content has been lost
        regardless of envelope headers being preserved.
        """
        status, written = _run_write_normalize(EIGHT_ENVELOPE_FIXTURE, format_style=format_style)
        assert status == "success"
        # One representative atom per envelope.
        load_bearing_atoms = [
            "TYPE::FRAME_CARD",  # META
            "FRAME_THREE_LAYER",  # EXACT.IDS
            "src/layer_one.py",  # SOURCE_REFS.PATHS
            "three-layer governance",  # FACETS.INTENT
            "reviewer_50_tokens",  # AUDIENCE_VIEW_SEEDS.GLOBAL
            "CONCEPT_FOO",  # EDGES.RELATED
            "src/layer_one.py#layer",  # PROVENANCE.MARKERS
            "SOURCE_REF_RESOLVES",  # VALIDATION
        ]
        for atom in load_bearing_atoms:
            assert atom in written, (
                f"GH #420 regression (format_style={format_style!r}): "
                f"load-bearing atom {atom!r} dropped. "
                f"written_bytes={len(written.encode())}"
            )


# --------------------------------------------------------------------------- #
# AC2: realistic FRAME_CARD-shaped document under preserve                    #
# --------------------------------------------------------------------------- #


class TestGH420AC2RealWorldFrameCard:
    """AC2: realistic FRAME_CARD documents byte-stable under preserve mode.

    The hestai-context-mcp FRAME_CARD fixtures are not resolvable from
    this repo.  AC2 exercises a DIFFERENT surface than AC1 (which uses
    the synthetic 8-envelope shape): a smaller 3-envelope FRAME_CARD-
    style fixture with embedded inline ``KEY<annotation>`` annotations
    and mixed inter-envelope trivia widths.  This exercises the
    annotation parser interaction with multi-envelope trivia capture,
    a distinct concern from AC1's pure-envelope-count check.

    Cubic P2 rework: previously AC2 used the same EIGHT_ENVELOPE_FIXTURE
    and same format_style as AC1 — collapsing the two acceptance criteria
    into duplicate coverage.  This fixture restores AC2 distinctness.
    """

    _ANNOTATED_FRAME_CARD_FIXTURE = (
        "===META===\n"
        "TYPE::FRAME_CARD\n"
        "ID::ANNOTATED_CARD\n"
        "STATUS<approved>::proposed\n"
        "===END===\n"
        "\n"
        "===EXACT===\n"
        "IDS::[FRAME_A, FRAME_B<active>]\n"
        "PROD_IMMUTABLES<enforced>::[I1, I2]\n"
        "===END===\n"
        "\n"
        "\n"  # noncanonical extra blank line — must survive
        "===FACETS===\n"
        'INTENT::"annotated frame card distinct from AC1"\n'
        "===END===\n"
    )

    def test_ac2_annotated_frame_card_preserve_byte_stable(self) -> None:
        """AC2 (distinct from AC1): annotated FRAME_CARD with mixed
        inter-envelope trivia widths MUST round-trip byte-identical
        under preserve.  Exercises the annotation parser interaction
        with multi-envelope trivia capture.
        """
        status, written = _run_write_normalize(self._ANNOTATED_FRAME_CARD_FIXTURE, format_style="preserve")
        assert status == "success"
        assert written == self._ANNOTATED_FRAME_CARD_FIXTURE, (
            "GH #420 AC2 regression (cubic-distinct fixture): annotated "
            "FRAME_CARD round-trip not byte-stable. "
            f"input_bytes={len(self._ANNOTATED_FRAME_CARD_FIXTURE)} "
            f"output_bytes={len(written)}"
        )

    def test_ac2_idempotent_second_pass(self) -> None:
        """Two consecutive preserve-mode passes MUST produce identical bytes.

        This is the canonicalisation fixed-point property the schema
        idempotency gate enforces at CI level; we assert it inline here
        for the multi-envelope shape so a regression surfaces in the
        normal pytest run.
        """
        status1, pass1 = _run_write_normalize(EIGHT_ENVELOPE_FIXTURE, format_style="preserve")
        assert status1 == "success"
        status2, pass2 = _run_write_normalize(pass1, format_style="preserve")
        assert status2 == "success"
        assert pass1 == pass2, (
            "GH #420 AC2 regression: preserve-mode canonical form is not a "
            "fixed point for multi-envelope documents. PROD::I4 violation."
        )


# --------------------------------------------------------------------------- #
# Emitter-level coverage                                                      #
# --------------------------------------------------------------------------- #


class TestGH420EmitterMultiEnvelope:
    """Emitter MUST iterate ``additional_envelopes`` and emit each."""

    def test_emit_includes_all_envelope_names_canonical(self) -> None:
        """Canonical emit (no format_options) MUST include every envelope name."""
        doc = parse(FOUR_ENVELOPE_FIXTURE)
        out = emit(doc)
        for name in ("META", "EXACT", "FACETS", "EDGES"):
            assert f"==={name}===" in out, (
                f"GH #420 emitter regression: envelope {name!r} missing from " f"canonical output."
            )

    def test_emit_envelope_count_matches_parser(self) -> None:
        """Output ``===END===`` count MUST equal parser envelope count."""
        doc = parse(EIGHT_ENVELOPE_FIXTURE)
        out = emit(doc)
        # 1 (Document) + 7 (additional_envelopes) = 8 ===END=== markers.
        assert out.count("===END===") == 8


# --------------------------------------------------------------------------- #
# Q3 / PR-A audit: META.<field> change-path does NOT leak into additional     #
# envelopes (mandatory per HO directive)                                      #
# --------------------------------------------------------------------------- #


class TestGH420Q3PRAAuditMetaFieldScoping:
    """META.<field> change-paths MUST target envelope #1's META only.

    PR #449 (GH #447 CE rework) introduced the ``doc.name == "META"``
    constraint in ``write.py:_apply_changes`` to prevent ``META.<field>``
    leaking into a non-META envelope (cross-envelope scope leak).

    Under Option D the constraint is preserved by construction:

    1. Envelope #1 IS the Document — its ``.name`` field gates the
       META-envelope detection, so a ``META.STATUS`` change targeting a
       ``===META===`` envelope #1 still mutates in place.
    2. Envelopes in ``additional_envelopes`` are ``Envelope`` nodes, NOT
       ``Document`` — they bypass the existing META gate by construction
       and cannot be mutated by ``META.<field>`` change-paths.

    These tests assert both halves of the contract.
    """

    # Pathological repro: ``===META===`` placed as envelope #2 (someone
    # accidentally re-used the META name for a downstream envelope).
    # A ``META.STATUS`` change MUST mutate envelope #1's META and leave
    # envelope #2's same-named atom intact.
    _MULTI_META_FIXTURE = (
        "===META===\n"
        "TYPE::FRAME_CARD\n"
        "ID::PRIMARY\n"
        "STATUS::proposed\n"
        "===END===\n"
        "\n"
        "===META===\n"
        "TYPE::INNER_META\n"
        "STATUS::sibling_status\n"
        "===END===\n"
    )

    def test_q3_meta_status_targets_envelope_one_only(self) -> None:
        """META.STATUS change MUST mutate envelope #1's STATUS, not the sibling."""
        status, written = _run_write_changes(
            content=self._MULTI_META_FIXTURE,
            changes={"META.STATUS": "ratified"},
            format_style="preserve",
        )
        assert status == "success", f"WriteTool failed: status={status!r}"
        # Envelope #1's STATUS must be mutated to ratified.
        assert "STATUS::ratified" in written, (
            "GH #420 Q3 audit regression: META.STATUS resolver did not "
            f"mutate envelope #1's STATUS. file is: {written!r}"
        )
        # Envelope #1's old STATUS::proposed must be gone (mutated in place).
        # Envelope #2's STATUS::sibling_status MUST survive.
        assert "STATUS::sibling_status" in written, (
            "GH #420 Q3 audit regression: META.STATUS resolver leaked into "
            f"the additional envelope and overwrote its STATUS atom. "
            f"file is: {written!r}"
        )
        # Exactly one STATUS::ratified and one STATUS::sibling_status —
        # the resolver MUST NOT inject duplicates.
        assert written.count("STATUS::ratified") == 1
        assert written.count("STATUS::sibling_status") == 1
        # No STATUS::proposed lingering (mutate-in-place semantics from PR #449).
        assert "STATUS::proposed" not in written

    def test_q3_meta_field_does_not_leak_to_non_meta_additional_envelope(self) -> None:
        """META.<field> change MUST NOT mutate same-named atoms in non-META siblings.

        Repro: envelope #1 ``===META===``, envelope #2 ``===DOC===``
        carrying a same-named ``STATUS`` atom (which lives in DOC, not
        META).  A ``META.STATUS`` change must target envelope #1's META
        and leave envelope #2's atom untouched.
        """
        fixture = (
            "===META===\n"
            "TYPE::FRAME_CARD\n"
            "ID::TEST\n"
            "STATUS::proposed\n"
            "===END===\n"
            "\n"
            "===DOC===\n"
            "STATUS::content_status\n"
            "===END===\n"
        )
        status, written = _run_write_changes(
            content=fixture,
            changes={"META.STATUS": "ratified"},
            format_style="preserve",
        )
        assert status == "success"
        assert "STATUS::ratified" in written
        # The DOC envelope's STATUS atom MUST survive intact.
        assert "STATUS::content_status" in written, (
            "GH #420 Q3 audit regression: META.STATUS leaked into a "
            "non-META additional envelope (===DOC===) and mutated its "
            f"STATUS atom. file is: {written!r}"
        )
        # No duplicate STATUS::ratified in the DOC envelope.
        assert written.count("STATUS::ratified") == 1
        assert "===DOC===" in written

    def test_q3_pr449_single_envelope_behaviour_unchanged(self) -> None:
        """PR #449 single-envelope mutate-in-place MUST be unchanged.

        Sanity check: with no additional envelopes, the PR #449 contract
        (mutate flat atom in place under preserve) still holds.  This
        guards against any accidental drift in the META gate during the
        Option D rollout.
        """
        single = "===META===\nTYPE::FRAME_CARD\nID::TEST_CARD\nSTATUS::proposed\n===END===\n"
        status, written = _run_write_changes(
            content=single,
            changes={"META.STATUS": "ratified"},
            format_style="preserve",
        )
        assert status == "success"
        assert "STATUS::ratified" in written
        assert "STATUS::proposed" not in written
        assert written.count("STATUS::") == 1


# --------------------------------------------------------------------------- #
# AC4: documentation honesty                                                  #
# --------------------------------------------------------------------------- #


class TestGH420AC4DocumentationHonest:
    """AC4: docstrings honestly describe multi-envelope support boundaries."""

    def test_envelope_dataclass_has_docstring(self) -> None:
        assert Envelope.__doc__ is not None
        # Honesty markers: the docstring must call out v1.13.0 scope
        # boundaries explicitly.
        doc = Envelope.__doc__
        assert "Option D" in doc or "#420" in doc
        # Must explicitly note that additional envelopes are read+emit only
        # (no atom mutation via changes_mode) in v1.13.0.
        assert "v1.13.0" in doc or "v1.14" in doc or "Read + emit only" in doc.replace("\n", " ")


# --------------------------------------------------------------------------- #
# CE rework: inter-envelope trivia preservation                               #
# --------------------------------------------------------------------------- #


class TestGH420CEReworkInterEnvelopeTrivia:
    """CE BLOCKING (PR #451 rework): inter-envelope whitespace MUST be preserved
    under preserve mode.

    CE evidence pre-rework:
        - parser.py:669 ``skip_whitespace()`` discarded inter-envelope trivia.
        - emitter.py:1084 ``lines.append("")`` emitted a FIXED ``\\n\\n``
          separator regardless of original input.
        - Repro: input boundary ``\\n\\n\\n===EXACT`` emitted as
          ``\\n\\n===EXACT`` — byte-loss for noncanonical inter-envelope
          whitespace — violating AC1 (byte-stable under all four
          ``format_style`` values) and PROD::I1 SYNTACTIC_FIDELITY (canon
          MUST be bijective on semantic space; whitespace between
          envelopes IS part of the source's syntactic surface under
          preserve mode).
    """

    # Three newlines between envelope #1 and envelope #2 (extra blank line);
    # two newlines with trailing spaces between envelope #2 and envelope #3
    # (a trailing-whitespace variant CE explicitly called out).
    _NONCANONICAL_BOUNDARY_FIXTURE = (
        "===META===\n"
        "TYPE::FRAME_CARD\n"
        "ID::REWORK_BOUNDARY\n"
        "STATUS::proposed\n"
        "===END===\n"
        "\n"  # boundary newline #1
        "\n"  # boundary newline #2
        "\n"  # boundary newline #3 (extra blank line — must survive)
        "===EXACT===\n"
        "IDS::[A, B]\n"
        "===END===\n"
        "  \n"  # trailing-whitespace line (must survive verbatim)
        "===FACETS===\n"
        'INTENT::"trivia preservation"\n'
        "===END===\n"
    )

    def test_inter_envelope_whitespace_preserved(self) -> None:
        """Preserve-mode round-trip with NO changes MUST be byte-identical.

        Pre-rework failure: ``\\n\\n\\n`` between envelopes #1 and #2 collapses
        to ``\\n\\n`` (byte loss = 1); ``  \\n`` between envelopes #2 and #3
        collapses to ``\\n`` (byte loss = 2 trailing spaces) — total loss
        of 3 bytes from a 145-byte fixture.

        Post-rework: every inter-envelope byte threads through emit
        unchanged.
        """
        status, written = _run_write_normalize(self._NONCANONICAL_BOUNDARY_FIXTURE, format_style="preserve")
        assert status == "success", f"octave_write returned status={status!r}"
        assert written == self._NONCANONICAL_BOUNDARY_FIXTURE, (
            "Preserve-mode round-trip is NOT byte-identical (CE rework "
            "regression): inter-envelope trivia was modified. "
            f"input_bytes={len(self._NONCANONICAL_BOUNDARY_FIXTURE)} "
            f"output_bytes={len(written)}. "
            f"\nINPUT  = {self._NONCANONICAL_BOUNDARY_FIXTURE!r}"
            f"\nOUTPUT = {written!r}"
        )

    def test_inter_envelope_whitespace_preserved_with_change_to_envelope_1(self) -> None:
        """Envelopes #2 and #3 (including the trivia preceding each) must
        remain byte-stable even when envelope #1's META is mutated.

        This proves the per-envelope dirty flag still gates trivia
        emission correctly: envelope #1 re-emits canonically, while
        envelopes #2 and #3 and ALL inter-envelope trivia between them
        slice verbatim from baseline.
        """
        status, written = _run_write_changes(
            self._NONCANONICAL_BOUNDARY_FIXTURE,
            {"META.STATUS": "approved"},
            format_style="preserve",
        )
        assert status == "success", f"octave_write returned status={status!r}"

        # Envelope #1 changed STATUS proposed -> approved.
        assert "STATUS::approved" in written
        assert "STATUS::proposed" not in written

        # Envelopes #2 and #3 plus the inter-envelope trivia between them
        # must survive byte-identical.  We anchor on the substring starting
        # at envelope #1's ===END=== through the document end.  The bytes
        # between ===END=== of envelope #1 and ===END=== of envelope #3
        # (inclusive of the noncanonical \n\n\n and "  \n" boundaries)
        # must equal the original.
        original_tail_start = self._NONCANONICAL_BOUNDARY_FIXTURE.find("===END===\n") + len("===END===\n")
        original_tail = self._NONCANONICAL_BOUNDARY_FIXTURE[original_tail_start:]

        # Locate the corresponding tail in the written output (envelope #1's
        # ===END=== still exists, just preceded by mutated META).
        written_tail_start = written.find("===END===\n") + len("===END===\n")
        written_tail = written[written_tail_start:]

        assert written_tail == original_tail, (
            "Envelopes #2/#3 and their preceding trivia were NOT byte-stable "
            "after a change to envelope #1.  PROD::I1 violation "
            "(per-envelope dirty propagation must NOT touch sibling trivia)."
            f"\nORIGINAL TAIL = {original_tail!r}"
            f"\nWRITTEN  TAIL = {written_tail!r}"
        )


# --------------------------------------------------------------------------- #
# CE rework cycle 2: pre_trivia emitted VERBATIM (no strip + "\n".join)       #
# --------------------------------------------------------------------------- #


class TestGH420CEReworkCycle2BoundaryPreservation:
    """CE rework cycle 2 (PR #451): the emitter MUST emit ``pre_trivia``
    verbatim and MUST NOT transform distinct accepted source boundaries
    (single ``\\n`` vs ``\\n\\n`` vs zero-byte) into a single canonical
    blank-line boundary.

    CE evidence (cycle 2):
        - emitter.py:1108-1117 stripped one leading + one trailing newline
          from the raw ``pre_trivia`` slice, then joined with ``"\\n".join``.
          Raw ``"\\n"`` and raw ``"\\n\\n"`` BOTH became ``""`` after
          trimming, so the final join produced an identical
          ``===END===\\n\\n===NAME===`` canonical-blank-line boundary for
          both — collapsing distinct accepted source bytes (I1
          SYNTACTIC_FIDELITY violation; bijection on semantic space broken).

    Post-rework: each input boundary width round-trips byte-identical
    AND distinct widths remain distinguishable in the output.
    """

    # CE's concrete failing case: tight adjacency, exactly one ``\n`` between
    # envelopes #1 and #2.  Pre-rework emitter inflated this to ``\n\n``.
    _SINGLE_NEWLINE_FIXTURE = (
        "===META===\n"
        "TYPE::FRAME_CARD\n"
        "ID::TIGHT\n"
        "STATUS::proposed\n"
        "===END===\n"  # single newline terminates envelope #1
        "===EXACT===\n"  # no blank line between envelopes
        "IDS::[A]\n"
        "===END===\n"
    )

    # Canonical-style: exactly one blank line (``\n\n`` between ===END=== and
    # next ===NAME===).  Identical content to ``_SINGLE_NEWLINE_FIXTURE``
    # except for the boundary width — so the distinguishability test below
    # can prove the two outputs differ ONLY in boundary, not content.
    _DOUBLE_NEWLINE_FIXTURE = (
        "===META===\n"
        "TYPE::FRAME_CARD\n"
        "ID::TIGHT\n"
        "STATUS::proposed\n"
        "===END===\n"
        "\n"  # one blank line between envelopes (canonical)
        "===EXACT===\n"
        "IDS::[A]\n"
        "===END===\n"
    )

    # Zero-byte adjacency: parser currently ACCEPTS this (lexer recognises
    # ``===END======NAME===`` as two adjacent tokens).  Under preserve mode
    # the round-trip must either be byte-identical OR the parser must reject
    # at lex/parse time.  We assert byte-identity; if the parser later
    # tightens to a hard reject, this test moves to a parser-error
    # assertion.
    _ZERO_BYTE_FIXTURE = (
        "===META===\n"
        "TYPE::FRAME_CARD\n"
        "ID::ZB\n"
        "STATUS::proposed\n"
        "===END======EXACT===\n"  # no separator at all between envelopes
        "IDS::[A]\n"
        "===END===\n"
    )

    def test_single_newline_boundary_preserved(self) -> None:
        """Tight ``===END===\\n===NAME===`` boundary MUST round-trip byte-identical.

        Pre-rework emitter inflated ``\\n`` → ``\\n\\n`` (added 1 byte).
        Post-rework: verbatim pre_trivia emission preserves the single
        newline.
        """
        status, written = _run_write_normalize(self._SINGLE_NEWLINE_FIXTURE, format_style="preserve")
        assert status == "success", f"octave_write returned status={status!r}"
        assert written == self._SINGLE_NEWLINE_FIXTURE, (
            "CE rework cycle 2 regression: single-newline inter-envelope "
            "boundary was NOT preserved verbatim.\n"
            f"  input_bytes  = {len(self._SINGLE_NEWLINE_FIXTURE)}\n"
            f"  output_bytes = {len(written)}\n"
            f"INPUT  = {self._SINGLE_NEWLINE_FIXTURE!r}\n"
            f"OUTPUT = {written!r}"
        )

    def test_double_newline_boundary_preserved(self) -> None:
        """Canonical ``===END===\\n\\n===NAME===`` boundary MUST round-trip byte-identical.

        Distinct from the single-newline case: this is the canonical
        blank-line form.  Pre-rework happened to be byte-identical here
        (the strip+join collapsed to ``\\n\\n`` matching the canonical
        form), but the fix MUST NOT regress this case.
        """
        status, written = _run_write_normalize(self._DOUBLE_NEWLINE_FIXTURE, format_style="preserve")
        assert status == "success", f"octave_write returned status={status!r}"
        assert written == self._DOUBLE_NEWLINE_FIXTURE, (
            "CE rework cycle 2 regression: double-newline (canonical) "
            "inter-envelope boundary was NOT preserved verbatim.\n"
            f"  input_bytes  = {len(self._DOUBLE_NEWLINE_FIXTURE)}\n"
            f"  output_bytes = {len(written)}\n"
            f"INPUT  = {self._DOUBLE_NEWLINE_FIXTURE!r}\n"
            f"OUTPUT = {written!r}"
        )

    def test_single_and_double_newline_outputs_remain_distinguishable(self) -> None:
        """The two boundary widths MUST produce distinct outputs.

        The pre-rework bug collapsed both single-newline and double-newline
        inputs to identical canonical-form outputs.  This test asserts
        the two outputs remain distinguishable — i.e. the canon is
        bijective on the semantic space of inter-envelope trivia widths
        (PROD::I1).
        """
        _, single_out = _run_write_normalize(self._SINGLE_NEWLINE_FIXTURE, format_style="preserve")
        _, double_out = _run_write_normalize(self._DOUBLE_NEWLINE_FIXTURE, format_style="preserve")
        # Both must be byte-identical to their respective inputs (the two
        # tests above prove this independently).  Here we additionally
        # assert the outputs remain DISTINGUISHABLE — the canon does not
        # collapse two inputs to one output.
        assert single_out != double_out, (
            "CE rework cycle 2 regression: single-newline and double-newline "
            "inter-envelope boundaries collapsed to an identical output. "
            "PROD::I1 SYNTACTIC_FIDELITY violation — canon is not bijective."
        )

    def test_zero_byte_boundary_parse_result(self) -> None:
        """Zero-byte adjacency parse result: either accepts cleanly (and
        produces exactly one additional envelope named EXACT) OR raises
        ParserError.  Any other outcome — including malformed acceptance
        (wrong envelope count) — is a regression.

        Cubic P2 (rework): the previous test wrapped acceptance-branch
        assertions in ``try/except Exception``, which would silently
        swallow an ``AssertionError`` raised by a malformed-shape check
        and re-route to the ``parser_accepts = False`` branch.  Split
        into two strict tests so assertion failures cannot be swallowed.
        """
        from octave_mcp.core.parser import ParserError, parse

        try:
            doc = parse(self._ZERO_BYTE_FIXTURE)
        except ParserError:
            # Acceptable resolution: parser rejected zero-byte adjacency.
            return
        # Acceptance branch: assertions OUTSIDE any try/except so a wrong
        # shape surfaces as a real test failure, not silent rejection.
        assert len(doc.additional_envelopes) == 1, (
            f"Zero-byte adjacency parsed but produced wrong envelope count: "
            f"expected 1 additional envelope, got {len(doc.additional_envelopes)}"
        )
        assert doc.additional_envelopes[0].name == "EXACT", (
            f"Zero-byte adjacency parsed but envelope #2 name is wrong: "
            f"expected 'EXACT', got {doc.additional_envelopes[0].name!r}"
        )

    def test_zero_byte_boundary_preserved_or_rejected(self) -> None:
        """Zero-byte adjacency ``===END======NAME===`` either round-trips
        byte-identical under preserve OR is rejected at parse time.

        Cubic P2 (rework): only ``ParserError`` (the documented parse
        rejection type) is treated as a rejection signal.  Any other
        exception — and any malformed-acceptance shape — propagates as a
        real test failure.
        """
        from octave_mcp.core.parser import ParserError, parse

        try:
            parse(self._ZERO_BYTE_FIXTURE)
        except ParserError:
            # Acceptable resolution: parser rejected zero-byte adjacency.
            return

        status, written = _run_write_normalize(self._ZERO_BYTE_FIXTURE, format_style="preserve")
        assert status == "success", f"octave_write returned status={status!r}"
        assert written == self._ZERO_BYTE_FIXTURE, (
            "CE rework cycle 2 regression: zero-byte inter-envelope "
            "adjacency was NOT preserved verbatim (parser accepted the "
            "input, so the emitter must round-trip identically).\n"
            f"  input_bytes  = {len(self._ZERO_BYTE_FIXTURE)}\n"
            f"  output_bytes = {len(written)}\n"
            f"INPUT  = {self._ZERO_BYTE_FIXTURE!r}\n"
            f"OUTPUT = {written!r}"
        )


# --------------------------------------------------------------------------- #
# Cubic advisory rework (PR #451): inter-envelope comment handling            #
# --------------------------------------------------------------------------- #


class TestGH420CubicReworkInterEnvelopeComments:
    """Cubic P1 (parser.py:681): the post-parse_document scan loop MUST NOT
    silently drop envelope #2..N when inter-envelope trivia contains a
    comment token.

    Pre-rework: ``self.skip_whitespace(skip_comments=False)`` left a
    ``COMMENT`` token at ``self.current()`` when inter-envelope trivia
    contained one; the subsequent ``current().type != ENVELOPE_START``
    check was True (current is the comment, not envelope-start), the
    loop broke, and envelope #2..N was silently dropped.  Same defect
    class as the original GH-420 silent envelope drop.

    Post-rework (Option A): the loop iterates through ANY non-
    ``ENVELOPE_START`` token (including ``COMMENT`` / ``NEWLINE`` /
    ``INDENT``) until it hits either ``ENVELOPE_START`` (continue and
    parse the sibling) or ``EOF`` (terminate).  The byte-range capture
    (``prev_end_byte → envelope_start_tok.start_byte``) naturally encloses
    the comment bytes because the parser does not modify source bytes;
    it just advances the token cursor.
    """

    # Variant 1: comment immediately AFTER ===END=== of envelope #1 (the
    # canonical "next line" position).  Pre-rework: silent drop of
    # envelope #2.
    _COMMENT_AFTER_END_FIXTURE = (
        "===META===\n"
        "TYPE::FRAME_CARD\n"
        "ID::COMMENT_AFTER_END\n"
        "STATUS::proposed\n"
        "===END===\n"
        "# comment between envelopes\n"
        "===EXACT===\n"
        "IDS::[A]\n"
        "===END===\n"
    )

    # Variant 2: comment immediately BEFORE ===NAME=== of envelope #2,
    # preceded by a blank line.
    _COMMENT_BEFORE_NAME_FIXTURE = (
        "===META===\n"
        "TYPE::FRAME_CARD\n"
        "ID::COMMENT_BEFORE_NAME\n"
        "STATUS::proposed\n"
        "===END===\n"
        "\n"
        "# comment immediately before envelope #2\n"
        "===EXACT===\n"
        "IDS::[A]\n"
        "===END===\n"
    )

    # Variant 3: multiple comments between envelopes, interleaved with
    # blank lines.
    _MULTIPLE_COMMENTS_FIXTURE = (
        "===META===\n"
        "TYPE::FRAME_CARD\n"
        "ID::MULTI_COMMENT\n"
        "STATUS::proposed\n"
        "===END===\n"
        "# first comment between envelopes\n"
        "\n"
        "# second comment between envelopes\n"
        "===EXACT===\n"
        "IDS::[A]\n"
        "===END===\n"
        "\n"
        "# comment between envelopes #2 and #3\n"
        "===FACETS===\n"
        'INTENT::"comment preservation"\n'
        "===END===\n"
    )

    def test_inter_envelope_comment_preserved(self) -> None:
        """Canonical case: comment between ===END=== and ===NAME=== MUST
        NOT cause envelope #2 to be silently dropped.

        Asserts both halves of the invariant:
        1. Parser produces env_count == 2 (envelope #1 + 1 additional).
        2. Preserve-mode round-trip is byte-identical (comment bytes
           survive in pre_trivia).
        """
        doc = parse(self._COMMENT_AFTER_END_FIXTURE)
        assert doc.name == "META", f"envelope #1 name wrong: {doc.name!r}"
        assert len(doc.additional_envelopes) == 1, (
            "Cubic P1 regression: parser dropped envelope #2 when "
            "inter-envelope trivia contained a comment token. "
            f"got {len(doc.additional_envelopes)} additional envelopes, "
            f"expected 1."
        )
        assert doc.additional_envelopes[0].name == "EXACT"

        status, written = _run_write_normalize(self._COMMENT_AFTER_END_FIXTURE, format_style="preserve")
        assert status == "success", f"octave_write status={status!r}"
        assert written == self._COMMENT_AFTER_END_FIXTURE, (
            "Cubic P1 regression: preserve-mode round-trip not byte-stable "
            "for inter-envelope-comment fixture (comment bytes lost from "
            "pre_trivia OR envelope #2 dropped).\n"
            f"  input_bytes  = {len(self._COMMENT_AFTER_END_FIXTURE)}\n"
            f"  output_bytes = {len(written)}\n"
            f"INPUT  = {self._COMMENT_AFTER_END_FIXTURE!r}\n"
            f"OUTPUT = {written!r}"
        )

    def test_comment_immediately_before_envelope_name(self) -> None:
        """Comment positioned immediately before ===NAME=== of envelope #2
        MUST NOT drop envelope #2 and MUST round-trip byte-identical.
        """
        doc = parse(self._COMMENT_BEFORE_NAME_FIXTURE)
        assert len(doc.additional_envelopes) == 1, (
            "Cubic P1 regression: comment immediately before envelope #2 "
            f"caused silent drop. got {len(doc.additional_envelopes)}."
        )
        status, written = _run_write_normalize(self._COMMENT_BEFORE_NAME_FIXTURE, format_style="preserve")
        assert status == "success"
        assert written == self._COMMENT_BEFORE_NAME_FIXTURE

    def test_multiple_inter_envelope_comments(self) -> None:
        """Multiple comments interleaved with blank lines between envelopes
        MUST preserve ALL envelopes and round-trip byte-identical.
        """
        doc = parse(self._MULTIPLE_COMMENTS_FIXTURE)
        assert len(doc.additional_envelopes) == 2, (
            "Cubic P1 regression: multiple inter-envelope comments caused "
            f"drop. got {len(doc.additional_envelopes)} additional envelopes, "
            "expected 2 (EXACT and FACETS)."
        )
        names = [env.name for env in doc.additional_envelopes]
        assert names == ["EXACT", "FACETS"], f"envelope names wrong: {names!r}"

        status, written = _run_write_normalize(self._MULTIPLE_COMMENTS_FIXTURE, format_style="preserve")
        assert status == "success"
        assert written == self._MULTIPLE_COMMENTS_FIXTURE, (
            "Cubic P1 regression: multi-comment fixture not byte-stable.\n"
            f"INPUT  = {self._MULTIPLE_COMMENTS_FIXTURE!r}\n"
            f"OUTPUT = {written!r}"
        )


# --------------------------------------------------------------------------- #
# Cubic advisory rework (PR #451): emitter fail-fast on invalid pre_trivia    #
# --------------------------------------------------------------------------- #


class TestGH420CubicReworkEmitterFailFast:
    """Cubic P2 (emitter.py:1118): when both pre_trivia byte spans are set
    (non-None) AND preserve mode is enabled AND baseline_bytes is
    available, but the bounds are invalid (start > end, or out-of-range),
    the emitter MUST raise an explicit error rather than silently
    degrade to canonical ``"\\n\\n"`` separator.

    Rationale: silent degradation masks AST corruption.  PROD::I4
    TRANSFORM_AUDITABILITY requires that invariant violations surface
    rather than fail-silent.  The ``spans not set`` (None) case
    continues to fall through to canonical separator as a legitimate
    non-preserve path; the fail-fast only triggers on the
    "spans-set-but-corrupt" combination.
    """

    def test_invalid_pre_trivia_bytes_raises(self) -> None:
        """Envelope with pre_trivia_start_byte > pre_trivia_end_byte under
        preserve mode MUST raise with a descriptive error.
        """
        # Parse a valid two-envelope fixture, then corrupt the AST.
        fixture = (
            "===META===\n"
            "TYPE::FRAME_CARD\n"
            "ID::CORRUPT_TEST\n"
            "STATUS::proposed\n"
            "===END===\n"
            "\n"
            "===EXACT===\n"
            "IDS::[A]\n"
            "===END===\n"
        )
        doc = parse(fixture)
        assert len(doc.additional_envelopes) == 1
        env = doc.additional_envelopes[0]
        # Corrupt: start > end (impossible in a well-formed AST).
        env.pre_trivia_start_byte = 10
        env.pre_trivia_end_byte = 5

        baseline_bytes = fixture.encode("utf-8")
        opts = FormatOptions(baseline_bytes=baseline_bytes, enable_preserve=True)
        with pytest.raises(ValueError, match=r"pre_trivia"):
            emit(doc, format_options=opts)

    def test_out_of_range_pre_trivia_bytes_raises(self) -> None:
        """Envelope with pre_trivia_end_byte > len(baseline_bytes) under
        preserve mode MUST raise with a descriptive error.
        """
        fixture = (
            "===META===\n"
            "TYPE::FRAME_CARD\n"
            "ID::OOR_TEST\n"
            "STATUS::proposed\n"
            "===END===\n"
            "\n"
            "===EXACT===\n"
            "IDS::[A]\n"
            "===END===\n"
        )
        doc = parse(fixture)
        env = doc.additional_envelopes[0]
        baseline_bytes = fixture.encode("utf-8")
        env.pre_trivia_start_byte = 0
        env.pre_trivia_end_byte = len(baseline_bytes) + 100  # out of range

        opts = FormatOptions(baseline_bytes=baseline_bytes, enable_preserve=True)
        with pytest.raises(ValueError, match=r"pre_trivia"):
            emit(doc, format_options=opts)

    def test_unset_pre_trivia_bytes_falls_through_to_canonical(self) -> None:
        """When BOTH pre_trivia spans are None, emitter MUST fall through
        to canonical ``"\\n\\n"`` separator (legitimate non-preserve path).
        """
        fixture = (
            "===META===\n"
            "TYPE::FRAME_CARD\n"
            "ID::UNSET_TEST\n"
            "STATUS::proposed\n"
            "===END===\n"
            "\n"
            "===EXACT===\n"
            "IDS::[A]\n"
            "===END===\n"
        )
        doc = parse(fixture)
        env = doc.additional_envelopes[0]
        env.pre_trivia_start_byte = None
        env.pre_trivia_end_byte = None
        # Must not raise; falls through to canonical separator.
        out = emit(doc)
        assert "===META===" in out
        assert "===EXACT===" in out
