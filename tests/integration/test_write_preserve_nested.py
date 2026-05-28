"""Nested Block/Section preserve-mode regression tests (CRS BLOCKER on PR #418).

The Strategy A T8 slice predicate in ``emit()`` originally checked only
``not section.dirty and not section.repaired`` before slicing a whole
top-level node from the baseline. ``body_dirty`` — set by
``_mark_dirty(parent, body=True)`` whenever a CHILD of a Block/Section
mutates — was NOT consulted, so the parent's whole subtree (including
stale children) was sliced verbatim. Result: changes through bare-dict
update on a Block, MERGE on a Block, or MERGE on a Section were
silently discarded while the tool reported success.

These tests reproduce the critical-reviewer-specialist's exact failure
modes via the public ``WriteTool`` path and assert against the WRITTEN
FILE CONTENT — not just the exit status — so any future regression that
leaves the old child value in place (because body_dirty was again
ignored) is caught.

Each test asserts both that the new child value LANDS and that the old
child value is GONE, defending against half-fixes.

A future enhancement (Option B in CRS's review) would add recursive
child-level dispatch where body_dirty containers slice their header
from baseline and dispatch each child individually. The current Option A
fix forces the whole subtree to re-emit canonically when body_dirty —
correct, conservative, and the smallest intervention that closes the
data-loss bug.
"""

from __future__ import annotations

import asyncio
import os
import tempfile

import pytest

from octave_mcp.mcp.write import WriteTool


def _run_write_changes(content: str, changes: dict, format_style: str = "preserve") -> tuple[str, str]:
    """Run WriteTool.execute(changes=...) on ``content`` and return (status, file_content)."""
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


class TestPreserveNestedBlockSection:
    """CRS BLOCKER regression: body_dirty containers must re-emit, not slice."""

    def test_preserve_block_bare_dict_update(self) -> None:
        """CRS repro #1: bare-dict update to existing Block must apply.

        Pre-fix behaviour: status=success, file content unchanged.
        """
        initial = "===TEST===\nBLOCK:\n  CHILD::old\n===END===\n"
        status, written = _run_write_changes(
            content=initial,
            changes={"BLOCK": {"CHILD": "new"}},
        )
        assert status == "success", f"WriteTool failed: status={status!r}"
        assert "CHILD::new" in written, f"new child value missing; file is: {written!r}"
        assert (
            "CHILD::old" not in written
        ), f"old child value persisted; the slice path emitted stale baseline bytes. file is: {written!r}"

    def test_preserve_block_merge_op(self) -> None:
        """CRS repro #2: MERGE $op on Block must apply.

        Pre-fix behaviour: status=success, file content unchanged.
        """
        initial = "===TEST===\nBLOCK:\n  CHILD::old\n===END===\n"
        status, written = _run_write_changes(
            content=initial,
            changes={"BLOCK": {"$op": "MERGE", "value": {"CHILD": "new"}}},
        )
        assert status == "success", f"WriteTool failed: status={status!r}"
        assert "CHILD::new" in written, f"new child value missing; file is: {written!r}"
        assert (
            "CHILD::old" not in written
        ), f"old child value persisted; the slice path emitted stale baseline bytes. file is: {written!r}"

    def test_preserve_section_merge_op(self) -> None:
        """CRS repro #3: MERGE $op on Section must apply.

        Pre-fix behaviour: status=success, file content unchanged.
        """
        initial = "===TEST===\n§1::SEC\n  CHILD::old\n===END===\n"
        status, written = _run_write_changes(
            content=initial,
            changes={"SEC": {"$op": "MERGE", "value": {"CHILD": "new"}}},
        )
        assert status == "success", f"WriteTool failed: status={status!r}"
        assert "CHILD::new" in written, f"new child value missing; file is: {written!r}"
        assert (
            "CHILD::old" not in written
        ), f"old child value persisted; the slice path emitted stale baseline bytes. file is: {written!r}"

    def test_preserve_block_unchanged_siblings_preserved(self) -> None:
        """A body_dirty container re-emits canonically, but unchanged sibling sections must still slice.

        This guards against an over-correction where a body_dirty Block caused
        the entire document to fall through to canonical emit and corrupted
        unrelated sibling sections.
        """
        initial = "===TEST===\nBLOCK:\n  CHILD::old\n§1::SIBLING\n  OTHER::stable\n===END===\n"
        status, written = _run_write_changes(
            content=initial,
            changes={"BLOCK": {"CHILD": "new"}},
        )
        assert status == "success", f"WriteTool failed: status={status!r}"
        assert "CHILD::new" in written
        assert "CHILD::old" not in written
        # Sibling section content must be intact.
        assert "OTHER::stable" in written, f"unrelated sibling section disturbed; file is: {written!r}"


class TestPreserveMetaDeleteCornerCase:
    """Companion regression: META key delete must not be silently swallowed.

    The META slice predicate checked ``any(doc.meta_dirty.get(k, False) for k in doc.meta)``
    which iterates only the CURRENTLY LIVE keys.  When a key is deleted, it
    is removed from ``doc.meta`` but ``meta_dirty[k]=True`` remains.  The
    pre-fix iteration would not see the deleted key, the slice path would
    fire, and the OLD META block (still containing the deleted key) would
    be sliced verbatim — silently re-introducing the deleted key.
    """

    def test_preserve_meta_key_delete(self) -> None:
        initial = '===TEST===\nMETA:\n  STATUS::DRAFT\n  VERSION::"1.0"\n===END===\n'
        status, written = _run_write_changes(
            content=initial,
            changes={"META.STATUS": {"$op": "DELETE"}},
        )
        assert status == "success", f"WriteTool failed: status={status!r}"
        assert "STATUS::DRAFT" not in written, f"deleted META key persisted; file is: {written!r}"
        # And the unchanged META key must still be present.
        assert 'VERSION::"1.0"' in written, f"unchanged META key lost; file is: {written!r}"


@pytest.mark.parametrize(
    "initial,changes,old_marker,new_marker,label",
    [
        (
            "===TEST===\nBLOCK:\n  CHILD::old\n===END===\n",
            {"BLOCK": {"CHILD": "new"}},
            "CHILD::old",
            "CHILD::new",
            "block_bare_dict",
        ),
        (
            "===TEST===\nBLOCK:\n  CHILD::old\n===END===\n",
            {"BLOCK": {"$op": "MERGE", "value": {"CHILD": "new"}}},
            "CHILD::old",
            "CHILD::new",
            "block_merge",
        ),
        (
            "===TEST===\n§1::SEC\n  CHILD::old\n===END===\n",
            {"SEC": {"$op": "MERGE", "value": {"CHILD": "new"}}},
            "CHILD::old",
            "CHILD::new",
            "section_merge",
        ),
    ],
)
def test_preserve_nested_mutation_parametric(
    initial: str, changes: dict, old_marker: str, new_marker: str, label: str
) -> None:
    """Parametric form of the CRS reproductions for easy grep / regression bisection."""
    status, written = _run_write_changes(content=initial, changes=changes)
    assert status == "success", f"[{label}] status={status!r}"
    assert new_marker in written, f"[{label}] new value missing; file is: {written!r}"
    assert old_marker not in written, f"[{label}] old value persisted; file is: {written!r}"


# ---------------------------------------------------------------------------
# CE BLOCKER (PR #418, rework cycle 3): repair-side propagation
# ---------------------------------------------------------------------------
#
# Schema repair recurses into Block/Section children and may set
# ``child.repaired = True`` on an Assignment whose value was normalised
# (e.g. ENUM casefold).  Pre-fix, the containing Block/Section was left
# with ``body_dirty = False``; emit()'s slice predicate then sliced the
# parent's whole subtree from baseline, silently discarding the repair.
#
# The fix in core/repair.py propagates the "I or a descendant was
# repaired" signal upwards: any Block/Section whose descendant tree
# contains a repaired Assignment is marked ``body_dirty = True``.


class TestPreserveRepairNestedPropagation:
    """CE BLOCKER regression: schema repair on a nested Assignment must apply."""

    def test_repair_nested_child_propagates_to_block_body_dirty(self) -> None:
        """Repairing a grandchild Assignment must mark the parent Block body_dirty.

        Uses ``_apply_schema_repairs`` directly with an ENUM casefold
        schema definition.  Pre-fix: ``child.repaired=True`` but
        ``block.body_dirty=False`` → slice path emits stale baseline →
        output still contains the lowercase ``STATUS::active``.
        Post-fix: ``block.body_dirty=True`` → re-emit path → output
        contains canonical ``STATUS::ACTIVE``.
        """
        from octave_mcp.core.constraints import ConstraintChain, EnumConstraint
        from octave_mcp.core.emitter import FormatOptions, emit
        from octave_mcp.core.holographic import HolographicPattern
        from octave_mcp.core.parser import parse
        from octave_mcp.core.repair import _apply_schema_repairs
        from octave_mcp.core.repair_log import RepairLog
        from octave_mcp.core.schema_extractor import FieldDefinition, SchemaDefinition
        from octave_mcp.mcp.write_format import _to_baseline_bytes

        content = "===TEST===\nBLOCK:\n  STATUS::active\n===END===\n"
        doc = parse(content)

        # Sanity-check the AST shape before mutation.
        block = doc.sections[0]
        child = block.children[0]
        assert type(block).__name__ == "Block"
        assert child.key == "STATUS"
        assert getattr(block, "body_dirty", False) is False
        assert child.repaired is False

        # Build a schema with an ENUM casefold rule on STATUS.
        constraints = ConstraintChain([EnumConstraint(allowed_values=["ACTIVE", "INACTIVE"])])
        pattern = HolographicPattern(example="ACTIVE", constraints=constraints, target=None)
        field_def = FieldDefinition(name="STATUS", pattern=pattern, raw_value=None)
        schema = SchemaDefinition(name="TEST", fields={"STATUS": field_def})

        # Apply repair — this is the production code path that triggered
        # CE's BLOCKER finding.
        repair_log = RepairLog(repairs=[])
        _apply_schema_repairs(doc, schema, repair_log)

        # Post-fix invariants: child repaired AND parent body_dirty set
        # by the recursive propagation in _repair_ast_node.
        assert child.repaired is True, "child Assignment was not repaired"
        assert (
            getattr(block, "body_dirty", False) is True
        ), "ancestor Block.body_dirty was NOT propagated — CE BLOCKER regressed"

        # End-to-end: preserve-mode emit must contain the repaired value
        # and NOT the pre-repair source bytes.
        bl = _to_baseline_bytes(content)
        out = emit(doc, FormatOptions(baseline_bytes=bl, enable_preserve=True))
        assert "STATUS::ACTIVE" in out, f"repair did not land in output; file is: {out!r}"
        assert (
            "STATUS::active" not in out
        ), f"pre-repair source bytes persisted; slice path emitted stale baseline. file is: {out!r}"

    def test_repair_nested_child_propagates_to_section_body_dirty(self) -> None:
        """Same propagation rule for Section parents."""
        from octave_mcp.core.constraints import ConstraintChain, EnumConstraint
        from octave_mcp.core.emitter import FormatOptions, emit
        from octave_mcp.core.holographic import HolographicPattern
        from octave_mcp.core.parser import parse
        from octave_mcp.core.repair import _apply_schema_repairs
        from octave_mcp.core.repair_log import RepairLog
        from octave_mcp.core.schema_extractor import FieldDefinition, SchemaDefinition
        from octave_mcp.mcp.write_format import _to_baseline_bytes

        content = "===TEST===\n§1::SEC\n  STATUS::active\n===END===\n"
        doc = parse(content)
        section = doc.sections[0]
        assert type(section).__name__ == "Section"

        constraints = ConstraintChain([EnumConstraint(allowed_values=["ACTIVE", "INACTIVE"])])
        pattern = HolographicPattern(example="ACTIVE", constraints=constraints, target=None)
        field_def = FieldDefinition(name="STATUS", pattern=pattern, raw_value=None)
        schema = SchemaDefinition(name="TEST", fields={"STATUS": field_def})

        _apply_schema_repairs(doc, schema, RepairLog(repairs=[]))

        assert (
            getattr(section, "body_dirty", False) is True
        ), "Section.body_dirty was NOT propagated — CE BLOCKER regressed"

        bl = _to_baseline_bytes(content)
        out = emit(doc, FormatOptions(baseline_bytes=bl, enable_preserve=True))
        assert "STATUS::ACTIVE" in out
        assert "STATUS::active" not in out

    def test_no_repair_leaves_body_dirty_unset(self) -> None:
        """Negative case: if NO descendant is repaired, the parent's body_dirty MUST remain False.

        This guards against an over-correction where we eagerly mark every
        ancestor body_dirty regardless of whether any repair occurred,
        defeating the slice path for clean documents.
        """
        from octave_mcp.core.constraints import ConstraintChain, EnumConstraint
        from octave_mcp.core.holographic import HolographicPattern
        from octave_mcp.core.parser import parse
        from octave_mcp.core.repair import _apply_schema_repairs
        from octave_mcp.core.repair_log import RepairLog
        from octave_mcp.core.schema_extractor import FieldDefinition, SchemaDefinition

        content = "===TEST===\nBLOCK:\n  STATUS::ACTIVE\n===END===\n"  # already canonical
        doc = parse(content)
        block = doc.sections[0]

        constraints = ConstraintChain([EnumConstraint(allowed_values=["ACTIVE", "INACTIVE"])])
        pattern = HolographicPattern(example="ACTIVE", constraints=constraints, target=None)
        field_def = FieldDefinition(name="STATUS", pattern=pattern, raw_value=None)
        schema = SchemaDefinition(name="TEST", fields={"STATUS": field_def})

        _apply_schema_repairs(doc, schema, RepairLog(repairs=[]))

        assert (
            getattr(block, "body_dirty", False) is False
        ), "body_dirty was set without any descendant repair — over-propagation regression"


# ---------------------------------------------------------------------------
# CE BLOCKER (PR #418, rework cycle 5): parser-side propagation
# ---------------------------------------------------------------------------
#
# The parser sets ``assignment.repaired=True`` whenever a lenient value-parse
# repair fires (e.g. multi_word_coalesce: `CHILD::foo bar` → `CHILD::"foo bar"`).
# Pre-fix, the enclosing Block/Section was left with ``body_dirty=False``;
# emit() then sliced the whole parent from baseline, silently dropping the
# parser's repair. The fix in core/parser.py runs a single post-pass over
# the constructed Document (``_propagate_repaired_to_body_dirty``) so every
# Block/Section whose descendant tree contains a ``repaired=True``
# Assignment is marked ``body_dirty=True``.
#
# This is the parser-side analogue of the schema-repair propagation in
# core/repair.py:_repair_ast_node.


class TestPreserveParserRepairPropagation:
    """CE BLOCKER regression: parser-origin lenient repair must propagate body_dirty."""

    def test_preserve_parser_lenient_repair_propagates_to_block_body_dirty(self) -> None:
        """Multi-word coalesce on a child Assignment inside a Block must
        mark the parent Block.body_dirty so preserve-mode emit re-emits
        canonically instead of slicing the stale subtree.
        """
        from octave_mcp.core.emitter import FormatOptions, emit
        from octave_mcp.core.parser import parse_with_warnings
        from octave_mcp.mcp.write_format import _to_baseline_bytes

        content = "===TEST===\nBLOCK:\n  CHILD::foo bar\n===END===\n"
        doc, warnings = parse_with_warnings(content, strict_structure=True)

        # Confirm the parser DID apply the lenient repair we expect.
        assert any(
            w.get("subtype") == "multi_word_coalesce" for w in warnings
        ), f"Parser did not produce the expected lenient repair; warnings={warnings!r}"

        block = doc.sections[0]
        child = block.children[0]
        assert type(block).__name__ == "Block"
        assert child.repaired is True, "child Assignment was not marked repaired by the parser"

        # Internal invariant: ancestor body_dirty propagated.
        assert (
            getattr(block, "body_dirty", False) is True
        ), "Block.body_dirty was NOT propagated from descendant repaired flag — CE BLOCKER regressed"

        # End-to-end: preserve-mode emit must produce the canonical
        # quoted form and NOT the un-canonicalised baseline bytes.
        bl = _to_baseline_bytes(content)
        out = emit(doc, FormatOptions(baseline_bytes=bl, enable_preserve=True))
        assert 'CHILD::"foo bar"' in out, f"canonical repair did not land in output; out={out!r}"
        assert (
            "CHILD::foo bar\n" not in out
        ), f"pre-repair source bytes persisted; slice path emitted stale baseline. out={out!r}"

    def test_preserve_parser_lenient_repair_propagates_to_section_body_dirty(self) -> None:
        """Same propagation contract for Section parents."""
        from octave_mcp.core.emitter import FormatOptions, emit
        from octave_mcp.core.parser import parse_with_warnings
        from octave_mcp.mcp.write_format import _to_baseline_bytes

        content = "===TEST===\n§1::SEC\n  CHILD::foo bar\n===END===\n"
        doc, warnings = parse_with_warnings(content, strict_structure=True)

        assert any(w.get("subtype") == "multi_word_coalesce" for w in warnings)

        section = doc.sections[0]
        child = section.children[0]
        assert type(section).__name__ == "Section"
        assert child.repaired is True

        assert (
            getattr(section, "body_dirty", False) is True
        ), "Section.body_dirty was NOT propagated from descendant repaired flag — CE BLOCKER regressed"

        bl = _to_baseline_bytes(content)
        out = emit(doc, FormatOptions(baseline_bytes=bl, enable_preserve=True))
        assert 'CHILD::"foo bar"' in out
        assert "CHILD::foo bar\n" not in out

    def test_preserve_parser_no_repair_no_propagation(self) -> None:
        """Negative case: a clean parse (no lenient repair) must leave
        ``body_dirty=False`` on every Block/Section so the slice path
        can still fire normally for unchanged documents.

        Guards against an over-correction where every ancestor is eagerly
        marked dirty regardless of repair, defeating the slice path.
        """
        from octave_mcp.core.parser import parse

        content = '===TEST===\nBLOCK:\n  CHILD::clean\n  OTHER::"already quoted"\n===END===\n'
        doc = parse(content)
        block = doc.sections[0]
        for child in block.children:
            assert child.repaired is False, f"unexpected repair on {child.key}"
        assert (
            getattr(block, "body_dirty", False) is False
        ), "body_dirty was set on a clean parse — parser-side over-propagation regression"


# ---------------------------------------------------------------------------
# GH #447: changes_mode resolver must mutate existing FLAT META atom in place
# rather than injecting a new nested ``META:`` block alongside it.
# ---------------------------------------------------------------------------
#
# Pre-fix repro: a META envelope containing flat-form atoms (no ``META:`` block
# prefix) parses such atoms as top-level ``Assignment`` nodes in
# ``doc.sections``, with ``doc.meta`` left EMPTY. The ``META.<field>``
# resolver branch in ``_apply_changes`` unconditionally wrote to
# ``doc.meta[field]``, which on emit produced a NEW canonical
# ``META:\n  STATUS::ratified`` block, while the original flat ``STATUS::``
# Assignment in ``doc.sections`` remained untouched. Net result: duplicate
# atoms with conflicting values, and an I3 (MIRROR_CONSTRAINT) +
# I1 (SYNTACTIC_FIDELITY) violation under ``format_style="preserve"``.
#
# The fix locates the existing flat-form Assignment for the META field and
# mutates it in place BEFORE falling back to the ``doc.meta`` dict path,
# preserving the atom's source form across all four ``format_style`` modes
# (``preserve``, ``expanded``, ``compact``, and omitted/default).


def _run_write_changes_omitted(content: str, changes: dict) -> tuple[str, str]:
    """Variant of ``_run_write_changes`` that does NOT pass ``format_style``.

    Required by GH #447 acceptance criterion 3 — the mutate-in-place
    contract must hold across ``format_style ∈ {preserve, expanded,
    compact, omitted}``. The "omitted" case exercises today's default
    (canonical re-emit) code path; the resolver must still find the
    existing flat atom and not duplicate it.
    """
    tool = WriteTool()

    async def _execute() -> tuple[str, str]:
        with tempfile.NamedTemporaryFile(suffix=".oct.md", mode="w", delete=False, encoding="utf-8") as f:
            f.write(content)
            path = f.name
        try:
            result = await tool.execute(target_path=path, changes=changes)
            with open(path, encoding="utf-8") as fp:
                written = fp.read()
            return result.get("status", "<missing>"), written
        finally:
            os.unlink(path)

    return asyncio.run(_execute())


class TestGH447ChangesModeMutateInPlace:
    """GH #447 regression: ``META.<field>`` change must mutate existing flat atom.

    Document shape under test (issue body repro):

        ===META===
        TYPE::FRAME_CARD
        ID::TEST_CARD
        STATUS::proposed
        ===END===

    With ``changes={"META.STATUS": "ratified"}`` the resolver MUST:
      (a) mutate the existing ``STATUS::proposed`` flat atom in place;
      (b) introduce NO new ``STATUS`` atom (no duplicate key);
      (c) preserve atom form when ``format_style="preserve"`` (flat stays flat);
      (d) hold across ``format_style ∈ {preserve, expanded, compact, omitted}``.
    """

    _SINGLE_ENVELOPE_FLAT = "===META===\n" "TYPE::FRAME_CARD\n" "ID::TEST_CARD\n" "STATUS::proposed\n" "===END===\n"

    def _assert_mutate_in_place(self, written: str, *, expect_flat: bool) -> None:
        """Shared assertion bundle for the four format_style variants."""
        # (a) new value present
        assert "STATUS::ratified" in written, (
            "META.STATUS resolver did NOT land the new value. " f"file is: {written!r}"
        )
        # (b) old value gone — the existing atom must be mutated, not duplicated
        assert "STATUS::proposed" not in written, (
            "GH #447 regression: original flat STATUS::proposed atom "
            "survived alongside the new value (duplicate-key shape). "
            f"file is: {written!r}"
        )
        # No duplicate STATUS atom anywhere in output.
        assert written.count("STATUS::") == 1, (
            f"GH #447 regression: expected exactly one STATUS:: atom, "
            f"found {written.count('STATUS::')}; file is: {written!r}"
        )
        # The injected nested-block META:\n  STATUS:: form must NOT appear
        # when an existing flat atom is being mutated.
        if expect_flat:
            # (c) atom form unchanged — flat stays flat under preserve
            assert "META:\n  STATUS::" not in written, (
                "GH #447 regression: resolver injected a nested-block "
                "META: form instead of mutating the flat atom in place. "
                f"file is: {written!r}"
            )
            # The flat atom must remain at the top level of the envelope.
            assert "\nSTATUS::ratified" in written or written.startswith("STATUS::ratified"), (
                "GH #447 regression: flat-form STATUS atom lost its " f"flat shape. file is: {written!r}"
            )
        # Sibling atoms unchanged.
        assert "TYPE::FRAME_CARD" in written
        assert "ID::TEST_CARD" in written

    def test_gh447_preserve_mutates_flat_meta_atom_in_place(self) -> None:
        status, written = _run_write_changes(
            content=self._SINGLE_ENVELOPE_FLAT,
            changes={"META.STATUS": "ratified"},
            format_style="preserve",
        )
        assert status == "success", f"WriteTool failed: status={status!r}"
        self._assert_mutate_in_place(written, expect_flat=True)

    def test_gh447_expanded_does_not_duplicate_meta_atom(self) -> None:
        status, written = _run_write_changes(
            content=self._SINGLE_ENVELOPE_FLAT,
            changes={"META.STATUS": "ratified"},
            format_style="expanded",
        )
        assert status == "success", f"WriteTool failed: status={status!r}"
        # Under expanded canonical re-emit the atom may legitimately be
        # promoted to a ``META:`` block, but it MUST NOT coexist with the
        # original flat atom — that is the #447 bug.
        self._assert_mutate_in_place(written, expect_flat=False)

    def test_gh447_compact_does_not_duplicate_meta_atom(self) -> None:
        status, written = _run_write_changes(
            content=self._SINGLE_ENVELOPE_FLAT,
            changes={"META.STATUS": "ratified"},
            format_style="compact",
        )
        assert status == "success", f"WriteTool failed: status={status!r}"
        self._assert_mutate_in_place(written, expect_flat=False)

    def test_gh447_omitted_format_style_does_not_duplicate_meta_atom(self) -> None:
        """No-format_style call exercises today's default canonical re-emit path.

        The resolver still must NOT inject a duplicate atom; the existing
        flat atom MUST be located and mutated before any nested-block
        fallback fires.
        """
        status, written = _run_write_changes_omitted(
            content=self._SINGLE_ENVELOPE_FLAT,
            changes={"META.STATUS": "ratified"},
        )
        assert status == "success", f"WriteTool failed: status={status!r}"
        self._assert_mutate_in_place(written, expect_flat=False)

    def test_gh447_preserve_unchanged_siblings_intact(self) -> None:
        """The mutate-in-place fix must NOT disturb sibling flat atoms."""
        status, written = _run_write_changes(
            content=self._SINGLE_ENVELOPE_FLAT,
            changes={"META.STATUS": "ratified"},
            format_style="preserve",
        )
        assert status == "success"
        # Each sibling atom appears exactly once and unchanged.
        assert written.count("TYPE::FRAME_CARD") == 1
        assert written.count("ID::TEST_CARD") == 1

    # ------------------------------------------------------------------ #
    # CE REWORK regression tests (PR #449 CE BLOCKING findings)          #
    # ------------------------------------------------------------------ #

    # CE BLOCKING #1: cross-envelope scope leak. The original fix's
    # flat-atom scan at write.py:3149 iterated ALL ``doc.sections`` rather
    # than being constrained to the ``===META===`` envelope shape. With a
    # document whose envelope is NOT META (e.g. ``===DOC===``) but which
    # happens to carry a same-named flat atom (``STATUS::content_status``),
    # the resolver silently mutated that other envelope's content. Per the
    # GH #447 contract, ``META.<field>`` means "the flat-atom inside the
    # ``===META===`` envelope" -- not "any top-level atom with the matching
    # key anywhere in the document".
    _NON_META_ENVELOPE_WITH_FLAT_STATUS = "===DOC===\nSTATUS::content_status\n===END===\n"

    def test_gh447_meta_field_does_not_leak_into_non_meta_envelope(self) -> None:
        """CE BLOCKING #1: META.<field> change MUST NOT mutate a non-META envelope.

        Repro shape from CE rework:

            ===DOC===
            STATUS::content_status
            ===END===

        With ``changes={"META.STATUS": "meta_status"}`` the resolver MUST NOT
        silently rewrite ``STATUS::meta_status`` inside ``===DOC===``. The
        original content's ``STATUS::content_status`` atom (which lives in the
        DOC envelope, not META) is OUT OF SCOPE for a ``META.<field>`` change.
        """
        status, written = _run_write_changes(
            content=self._NON_META_ENVELOPE_WITH_FLAT_STATUS,
            changes={"META.STATUS": "meta_status"},
            format_style="preserve",
        )
        assert status == "success", f"WriteTool failed: status={status!r}"
        # The DOC envelope's pre-existing flat atom MUST NOT be mutated to
        # the META.STATUS value -- that is CE's exact BLOCKING repro.
        assert "STATUS::meta_status" not in written or "STATUS::content_status" in written, (
            "CE BLOCKING #1 regression: META.STATUS resolver leaked into "
            "the ===DOC=== envelope and silently overwrote its STATUS atom. "
            f"file is: {written!r}"
        )
        # The DOC envelope's pre-existing flat STATUS atom must survive intact.
        assert "STATUS::content_status" in written, (
            "CE BLOCKING #1 regression: the DOC envelope's original "
            "STATUS::content_status atom was destroyed by an unrelated "
            f"META.<field> change. file is: {written!r}"
        )
        # The ===DOC=== envelope wrapper must remain.
        assert "===DOC===" in written

    def test_gh447_meta_field_delete_on_flat_meta_envelope(self) -> None:
        """CE BLOCKING #3 (also CRS gap): ``{"$op": "DELETE"}`` on a flat META atom.

        Document shape: single ``===META===`` envelope with flat atoms.
        Change: ``{"META.STATUS": {"$op": "DELETE"}}``.

        Expected: the ``STATUS::proposed`` atom is removed entirely; no
        duplicate remains anywhere in the output; no ``META:`` block stub
        appears alongside the now-empty slot.
        """
        status, written = _run_write_changes(
            content=self._SINGLE_ENVELOPE_FLAT,
            changes={"META.STATUS": {"$op": "DELETE"}},
            format_style="preserve",
        )
        assert status == "success", f"WriteTool failed: status={status!r}"
        # The atom must be gone, in every form.
        assert "STATUS::proposed" not in written, (
            "CE BLOCKING #3 regression: $op DELETE failed to remove the "
            f"original flat STATUS atom. file is: {written!r}"
        )
        assert "STATUS::" not in written, (
            "CE BLOCKING #3 regression: $op DELETE left a STATUS:: atom "
            f"(possibly a duplicate, possibly the original). file is: {written!r}"
        )
        # No stray nested-block META: fragment with STATUS inside it.
        assert "META:" not in written or "STATUS" not in written.split("META:", 1)[1], (
            "CE BLOCKING #3 regression: $op DELETE left a stub " f"META: block referencing STATUS. file is: {written!r}"
        )
        # Sibling atoms must still be intact and not duplicated.
        assert written.count("TYPE::FRAME_CARD") == 1
        assert written.count("ID::TEST_CARD") == 1

    def test_gh447_meta_field_delete_does_not_leak_into_non_meta_envelope(self) -> None:
        """CE BLOCKING #1 + #3 cross-product: DELETE on META.<field> must not
        delete a same-named flat atom from a non-META envelope.

        Repro shape: ``===DOC===`` envelope with ``STATUS::content_status``.
        Change: ``{"META.STATUS": {"$op": "DELETE"}}``.
        Expected: DOC's flat atom survives (META.STATUS isn't its address).
        """
        status, written = _run_write_changes(
            content=self._NON_META_ENVELOPE_WITH_FLAT_STATUS,
            changes={"META.STATUS": {"$op": "DELETE"}},
            format_style="preserve",
        )
        assert status == "success", f"WriteTool failed: status={status!r}"
        # The DOC envelope's flat STATUS atom MUST survive: META.STATUS does
        # not address it.
        assert "STATUS::content_status" in written, (
            "CE BLOCKING #1 regression (DELETE variant): the DOC envelope's "
            "STATUS::content_status atom was deleted by an unrelated "
            f"META.<field> DELETE change. file is: {written!r}"
        )
