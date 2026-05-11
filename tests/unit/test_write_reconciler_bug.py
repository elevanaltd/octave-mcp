"""Regression tests for the reconciler-bridge correctness bug.

Cubic AI surfaced a P2 finding on PR #399 (review id 4265564132):

    "``reconcile_canonical_emission`` is fed old file bytes
    (``baseline_content_for_diff``) instead of pre-emit intended bytes,
    so ordinary user edits can be incorrectly logged as
    ``TN_RECONCILE_CANONICAL`` normalization events."

Root cause: in pre-fix code the reconciler at ``mcp/write.py`` was called
with ``baseline_bytes=baseline_content_for_diff`` — which is the OLD
on-disk file content read from the target path. For ``content``-mode
writes to a NEW file this happened to be fine (baseline empty; canonical
equals the user-submitted content's canonical form; the bug did not
manifest in the original smoke tests). For ``changes``-mode writes (or
``content``-mode overwrites of an existing file with substantively
different user content), the diff between old-on-disk and canonical
conflated **user-intended changes** with **canonical normalisations**,
producing false-positive ``TN_RECONCILE_CANONICAL`` entries.

Correct semantics (per ADR-0006 SR1-T1 design §3a "Reconciler bridge
pattern"): the bridge exists to catch transformations the precise
loggers missed in the **parse → canonical-emit** pipeline. The
comparison must be against **pre-emit intended bytes** — i.e. what the
user submitted, NOT what the file previously contained.

Fix:
* ``content`` mode → reconcile against ``content`` (user-submitted bytes).
* ``changes`` / ``normalize_mode`` → skip the reconciler entirely.
  In those modes the user did not submit raw bytes; they submitted a
  delta or asked for in-place normalisation. There are no "pre-emit
  intended bytes" against which a coarse-grained bridge can correctly
  reconcile. The precise ``was_quoted`` logger still fires; only the
  bridge is suppressed.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_changes_mode_user_edit_does_not_emit_false_reconcile_entry() -> None:
    """``changes`` mode: a legitimate user edit must NOT be logged as a
    ``TN_RECONCILE_CANONICAL`` normalisation receipt.

    Regression for the cubic P2 finding on PR #399.
    """
    from octave_mcp.mcp.write import WriteTool

    # Existing canonical document on disk.
    existing = (
        "===DOC===\n"
        "META:\n"
        '  TYPE::"SPEC"\n'
        '  STATUS::"ACTIVE"\n'
        "§1::CONTENT\n"
        '  DESCRIPTION::"baseline value"\n'
        "===END===\n"
    )

    with tempfile.NamedTemporaryFile(suffix=".oct.md", delete=False, mode="w") as tmp:
        tmp.write(existing)
        path = tmp.name

    try:
        # User submits a legitimate content edit via changes mode.
        # This is NOT a normalisation — it is the user's intent.
        result = await WriteTool().execute(
            target_path=path,
            changes={"§1::CONTENT.DESCRIPTION": "edited value"},
            dry_run=True,
        )
    finally:
        os.unlink(path)

    assert result.get("status") == "success", f"changes-mode write failed: errors={result.get('errors')}"

    corrections = result.get("corrections", []) or []
    reconcile_entries = [c for c in corrections if c.get("code") == "TN_RECONCILE_CANONICAL"]
    assert reconcile_entries == [], (
        "Reconciler bridge falsely logged a TN_RECONCILE_CANONICAL entry "
        "for a legitimate user edit in changes mode. Cubic P2 regression. "
        f"Found entries: {reconcile_entries!r}"
    )


@pytest.mark.asyncio
async def test_normalize_mode_canonical_input_does_not_emit_reconcile_entry() -> None:
    """``normalize_mode`` (no content, no changes): an already-canonical
    file must NOT produce a reconcile entry. Same bug class as the
    cubic finding — reconciler was comparing baseline bytes against
    canonical bytes when both are conceptually the user's intent.

    Note: this case happens to be okay even with the buggy code because
    canonical input parses to AST whose emit equals input. We pin it as
    a positive regression: after the fix, reconciler is skipped in
    normalize_mode and the absence holds for any input.
    """
    from octave_mcp.mcp.write import WriteTool

    canonical = "===DOC===\n" "META:\n" "  TYPE::SPEC\n" "§1::CONTENT\n" "  KEY::value\n" "===END===\n"

    with tempfile.NamedTemporaryFile(suffix=".oct.md", delete=False, mode="w") as tmp:
        tmp.write(canonical)
        path = tmp.name

    try:
        result = await WriteTool().execute(
            target_path=path,
            dry_run=True,
        )
    finally:
        os.unlink(path)

    assert result.get("status") == "success"
    corrections = result.get("corrections", []) or []
    reconcile_entries = [c for c in corrections if c.get("code") == "TN_RECONCILE_CANONICAL"]
    assert reconcile_entries == [], f"Reconciler emitted entry in normalize_mode: {reconcile_entries!r}"


@pytest.mark.asyncio
async def test_content_mode_new_file_smoke_parity_unchanged() -> None:
    """Smoke parity: HO's pre-Step-3 ground-truth fixtures still produce
    the expected canonical_hash and a SINGLE TN_RECONCILE_CANONICAL
    receipt (the legitimate audit signal). The fix must not regress the
    audit-cardinality coverage achieved by Step 3.
    """
    from octave_mcp.mcp.write import WriteTool

    repo_root = Path(__file__).resolve().parent.parent.parent
    fixture = repo_root / "tests" / "fixtures" / "hydration" / "source.oct.md"
    content = fixture.read_text()

    with tempfile.NamedTemporaryFile(suffix=".oct.md", delete=False, mode="w") as tmp:
        tmp.write(content)
        path = tmp.name

    try:
        result = await WriteTool().execute(
            target_path=path,
            content=content,
            dry_run=True,
        )
    finally:
        os.unlink(path)

    assert result.get("status") == "success"
    assert result.get("canonical_hash") == (
        "3f680a6b0d13bce3ad112c4a5f86d6653db3b1b556687bcecee23556b15ab964"
    ), f"canonical_hash drift: {result.get('canonical_hash')!r}"

    corrections = result.get("corrections", []) or []
    reconcile_entries = [c for c in corrections if c.get("code") == "TN_RECONCILE_CANONICAL"]
    assert len(reconcile_entries) == 1, (
        "Expected exactly ONE TN_RECONCILE_CANONICAL entry for the "
        "hydration/source.oct.md fixture (META-side dequoting + blank-"
        f"line stripping). Got {len(reconcile_entries)}: {reconcile_entries!r}"
    )


@pytest.mark.asyncio
async def test_content_mode_overwrite_existing_file_with_user_edits() -> None:
    """``content`` mode overwrite of an existing file: the reconciler
    must compare canonical against the USER-SUBMITTED bytes, not the
    OLD on-disk file. A user submitting substantively different
    already-canonical content must NOT see false-positive
    TN_RECONCILE_CANONICAL entries reflecting their own edits.
    """
    from octave_mcp.mcp.write import WriteTool

    old_on_disk = "===DOC===\n" "META:\n" "  TYPE::SPEC\n" "===END===\n"
    user_submitted_canonical = "===DOC===\n" "META:\n" "  TYPE::OTHER\n" "  STATUS::ACTIVE\n" "===END===\n"

    with tempfile.NamedTemporaryFile(suffix=".oct.md", delete=False, mode="w") as tmp:
        tmp.write(old_on_disk)
        path = tmp.name

    try:
        result = await WriteTool().execute(
            target_path=path,
            content=user_submitted_canonical,
            dry_run=True,
        )
    finally:
        os.unlink(path)

    assert result.get("status") == "success"
    corrections = result.get("corrections", []) or []
    reconcile_entries = [c for c in corrections if c.get("code") == "TN_RECONCILE_CANONICAL"]
    # User-submitted bytes ARE already canonical → no normalisation happened
    # → reconciler must NOT fire. Pre-fix code would compare old_on_disk
    # vs canonical_of_user_submitted and falsely emit an entry.
    assert reconcile_entries == [], (
        "Reconciler falsely logged user edits as normalisation. "
        "Cubic P2 regression (content-mode overwrite variant). "
        f"Found entries: {reconcile_entries!r}"
    )
