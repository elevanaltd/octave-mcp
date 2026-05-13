"""CLI ``write --changes --format-style preserve`` regression tests.

CE BLOCKER on PR #418: prior to commit 0e90ad3's follow-up fix, the CLI
``write`` command's changes-mode loop mutated the AST without setting
any dirty flags. With ``spans_valid_for_baseline=True`` enabled in T8,
the Strategy A span-aware emit() then sliced the OLD baseline bytes for
every node and silently discarded the user's change while reporting
success (exit code 0). This is a data-loss class functional reliability
failure.

These tests reproduce the CE's exact failure modes and assert against
the WRITTEN FILE CONTENT — not just the exit code — so any future
regression that lands the value in canonical form but also keeps the
old value (or vice versa) is caught.

Coverage:
  * Top-level assignment value replacement.
  * META field replacement.
  * New top-level key addition.
  * Whole-META replacement.

These tests would FAIL if the paired-write fix in cli/main.py is
reverted (verified manually during implementation).
"""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from octave_mcp.cli.main import cli


def _write_then_read(
    tmp_path: Path,
    *,
    initial_content: str,
    changes: dict,
    format_style: str = "preserve",
) -> tuple[int, str, str]:
    """Helper: write ``initial_content`` to a temp file, run CLI write with
    ``--changes`` and ``--format-style``, and return (exit_code, stdout, file_content).
    """
    target = tmp_path / "doc.oct.md"
    target.write_text(initial_content, encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "write",
            str(target),
            "--changes",
            json.dumps(changes),
            "--format-style",
            format_style,
        ],
    )
    return result.exit_code, result.output, target.read_text(encoding="utf-8")


class TestCLIWriteChangesPreserve:
    """CE BLOCKER regression: CLI changes-mode preserve must apply mutations."""

    def test_top_level_value_replacement(self, tmp_path: Path) -> None:
        """CE repro #1: ``KEY::old`` → ``KEY::new`` must land in the file.

        Pre-fix behaviour: file content unchanged, exit code 0.
        """
        initial = "===TEST===\nKEY::old\n===END===\n"
        exit_code, _output, written = _write_then_read(
            tmp_path,
            initial_content=initial,
            changes={"KEY": "new"},
        )
        assert exit_code == 0
        assert "KEY::new" in written, f"new value missing; file is: {written!r}"
        assert (
            "KEY::old" not in written
        ), f"old value persisted; the CLI silently discarded the change. file is: {written!r}"

    def test_meta_field_replacement(self, tmp_path: Path) -> None:
        """CE repro #2: ``META.STATUS::DRAFT`` → ``REVIEWED`` must land in the file.

        Pre-fix behaviour: STATUS stayed DRAFT, exit code 0.
        """
        initial = '===TEST===\nMETA:\n  STATUS::DRAFT\n  VERSION::"1.0"\n===END===\n'
        exit_code, _output, written = _write_then_read(
            tmp_path,
            initial_content=initial,
            changes={"META.STATUS": "REVIEWED"},
        )
        assert exit_code == 0
        assert "STATUS::REVIEWED" in written, f"new META.STATUS missing; file is: {written!r}"
        assert (
            "STATUS::DRAFT" not in written
        ), f"old META.STATUS persisted; the CLI silently discarded the change. file is: {written!r}"
        # And the unchanged META key must still be present (proves we
        # did not whole-doc clobber).
        assert 'VERSION::"1.0"' in written, f"unchanged META.VERSION lost; file is: {written!r}"

    def test_new_top_level_key_addition(self, tmp_path: Path) -> None:
        """A new top-level key not present in the source must appear in the output."""
        initial = "===TEST===\nEXISTING::value\n===END===\n"
        exit_code, _output, written = _write_then_read(
            tmp_path,
            initial_content=initial,
            changes={"NEW_KEY": "new_value"},
        )
        assert exit_code == 0
        assert "NEW_KEY::new_value" in written, f"new key missing; file is: {written!r}"
        # And the existing key must still be present.
        assert "EXISTING::value" in written, f"existing key lost; file is: {written!r}"

    def test_whole_meta_replacement(self, tmp_path: Path) -> None:
        """Whole-META replacement must apply all new fields and drop the old.

        Note: the CLI ``--changes`` payload accepts JSON, so string values
        are bare strings; the emitter handles canonical quoting on output.
        """
        initial = '===TEST===\nMETA:\n  STATUS::DRAFT\n  VERSION::"1.0"\n===END===\n'
        exit_code, _output, written = _write_then_read(
            tmp_path,
            initial_content=initial,
            changes={"META": {"STATUS": "REVIEWED", "OWNER": "alice"}},
        )
        assert exit_code == 0
        assert "STATUS::REVIEWED" in written, f"new META.STATUS missing; file is: {written!r}"
        assert "OWNER::alice" in written, f"new META.OWNER missing; file is: {written!r}"
        assert "STATUS::DRAFT" not in written, (
            f"old META.STATUS persisted; the CLI silently discarded the whole-META replacement. "
            f"file is: {written!r}"
        )
