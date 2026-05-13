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
