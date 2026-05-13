"""DeprecationWarning coverage for the v1.13.0 ``format_style`` Shape B rollout.

ADR-0006 Sprint 2 addendum §5 (PR-4 T10): in v1.13.0 the MCP ``octave_write``
tool and the CLI ``write`` command both keep today's full canonical re-emit
behaviour when ``format_style`` is omitted, BUT emit a ``DeprecationWarning``
when the caller passes ``format_style=None`` *explicitly*. The warning
announces the upcoming v1.14.0 default flip (from canonical re-emit to
span-aware ``"preserve"`` mode).

This test suite enforces the Shape B contract:

  1. ``format_style=None`` passed explicitly → ``DeprecationWarning`` fires.
  2. ``format_style`` omitted entirely      → no warning.
  3. ``format_style`` passed with any valid string ("preserve", "expanded",
     "compact") → no warning.
  4. Byte-shape of output under "explicit None" is identical to byte-shape
     of output when omitted — the v1.13.0 contract is "warn but keep
     today's behaviour exactly". This guards against a careless future
     refactor that warns AND flips the default in the same release.

Hard constraints (from the PR-4 task spec):
  * No default flip in v1.13.0.
  * Warning fires ONLY on explicit None, NOT on omission.
  * All public entrypoints get the warning (MCP tool + CLI).
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import warnings
from pathlib import Path

import pytest
from click.testing import CliRunner

from octave_mcp.cli.main import cli
from octave_mcp.mcp.write import WriteTool

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_mcp_execute(**kwargs) -> dict:
    """Invoke ``WriteTool().execute(**kwargs)`` synchronously and return the result."""
    tool = WriteTool()
    return asyncio.run(tool.execute(**kwargs))


def _make_tmp_file(initial: str) -> str:
    """Create a temp .oct.md file with ``initial`` content; return its path."""
    fd, path = tempfile.mkstemp(suffix=".oct.md")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(initial)
    except Exception:
        os.unlink(path)
        raise
    return path


# ---------------------------------------------------------------------------
# MCP surface coverage
# ---------------------------------------------------------------------------


class TestMCPDeprecationWarning:
    """Shape B coverage for the MCP ``WriteTool.execute`` entrypoint."""

    def test_deprecation_warning_fires_on_explicit_none(self) -> None:
        """Passing ``format_style=None`` explicitly MUST emit a DeprecationWarning."""
        path = _make_tmp_file('===TEST===\nKEY::"v1"\n===END===\n')
        try:
            with pytest.warns(DeprecationWarning, match="format_style=None"):
                _run_mcp_execute(
                    target_path=path,
                    changes={"KEY": "v2"},
                    format_style=None,
                )
        finally:
            os.unlink(path)

    def test_no_warning_when_omitted(self) -> None:
        """Omitting ``format_style`` MUST NOT emit any DeprecationWarning.

        This is the dominant call path. If a warning fired on omission, every
        existing caller would be spammed — defeating the point of Shape B.
        """
        path = _make_tmp_file('===TEST===\nKEY::"v1"\n===END===\n')
        try:
            with warnings.catch_warnings():
                # Promote any DeprecationWarning to an error so a stray warning
                # would fail this test instead of being silently swallowed.
                warnings.simplefilter("error", DeprecationWarning)
                _run_mcp_execute(
                    target_path=path,
                    changes={"KEY": "v2"},
                    # format_style omitted intentionally
                )
        finally:
            os.unlink(path)

    @pytest.mark.parametrize("style", ["preserve", "expanded", "compact"])
    def test_no_warning_on_explicit_valid_style(self, style: str) -> None:
        """Any explicit valid ``format_style`` value MUST be silent."""
        path = _make_tmp_file('===TEST===\nKEY::"v1"\n===END===\n')
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", DeprecationWarning)
                _run_mcp_execute(
                    target_path=path,
                    changes={"KEY": "v2"},
                    format_style=style,
                )
        finally:
            os.unlink(path)

    def test_behavior_unchanged_under_explicit_none_vs_omitted(self) -> None:
        """v1.13.0 contract: byte-shape of output under explicit-None MUST
        match byte-shape under omission. The warning fires but the behaviour
        does NOT flip until v1.14.0. This guards against a careless future
        refactor that warns AND changes the default in the same release.
        """
        initial = '===TEST===\nKEY::"v1"\nOTHER::"stable"\n===END===\n'

        # Run with omitted format_style.
        path_omitted = _make_tmp_file(initial)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                _run_mcp_execute(target_path=path_omitted, changes={"KEY": "v2"})
            output_omitted = Path(path_omitted).read_bytes()
        finally:
            os.unlink(path_omitted)

        # Run with explicit None (suppressing the expected warning so the test
        # is asserting BEHAVIOUR not the warning here).
        path_explicit = _make_tmp_file(initial)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                _run_mcp_execute(target_path=path_explicit, changes={"KEY": "v2"}, format_style=None)
            output_explicit = Path(path_explicit).read_bytes()
        finally:
            os.unlink(path_explicit)

        assert output_omitted == output_explicit, (
            "v1.13.0 contract violated: explicit-None and omitted "
            "format_style produced different output bytes. The default flip "
            "is scheduled for v1.14.0 — not v1.13.0."
        )


# ---------------------------------------------------------------------------
# CLI surface coverage
# ---------------------------------------------------------------------------
#
# Click cannot distinguish "omitted" from "explicitly passed None" at the
# Python signature level — omission always sets format_style=None on the
# wrapped function. To honour the "warn ONLY on explicit None" Shape B
# constraint at the CLI surface, the CLI exposes ``--format-style none`` as
# a literal choice that triggers the warning. Bare omission stays silent.


class TestCLIDeprecationWarning:
    """Shape B coverage for the ``octave write`` CLI entrypoint."""

    def _invoke(self, path: str, *extra_args: str) -> tuple[int, str]:
        """Run the CLI write command and return (exit_code, combined_output).

        ``mix_stderr=True`` is the CliRunner default but we make it
        explicit so the DeprecationWarning text (written to stderr by
        Python's warnings module under ``-W default``) is captured.
        """
        runner = CliRunner()
        args = ["write", path, "--changes", '{"KEY":"v2"}', *extra_args]
        # Force the warnings module to actually emit (default filters may
        # suppress DeprecationWarning depending on Python invocation).
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", DeprecationWarning)
            result = runner.invoke(cli, args)
        deprecation_messages = [str(w.message) for w in caught if issubclass(w.category, DeprecationWarning)]
        return result.exit_code, "\n".join(deprecation_messages)

    def test_deprecation_warning_fires_on_explicit_format_style_none(self) -> None:
        """``--format-style none`` MUST emit a DeprecationWarning."""
        path = _make_tmp_file('===TEST===\nKEY::"v1"\n===END===\n')
        try:
            exit_code, deprecation_text = self._invoke(path, "--format-style", "none")
            assert exit_code == 0, "CLI write should still succeed (the warning is non-fatal)"
            assert "--format-style=none" in deprecation_text or "format_style" in deprecation_text, (
                f"Expected a DeprecationWarning mentioning the format_style flag; " f"got: {deprecation_text!r}"
            )
        finally:
            os.unlink(path)

    def test_no_warning_when_flag_omitted(self) -> None:
        """Omitting ``--format-style`` MUST NOT emit a DeprecationWarning."""
        path = _make_tmp_file('===TEST===\nKEY::"v1"\n===END===\n')
        try:
            exit_code, deprecation_text = self._invoke(path)
            assert exit_code == 0
            assert deprecation_text == "", (
                f"Unexpected DeprecationWarning when --format-style was omitted: " f"{deprecation_text!r}"
            )
        finally:
            os.unlink(path)

    @pytest.mark.parametrize("style", ["preserve", "expanded", "compact"])
    def test_no_warning_on_explicit_valid_style(self, style: str) -> None:
        """Any explicit valid ``--format-style`` value MUST be silent."""
        path = _make_tmp_file('===TEST===\nKEY::"v1"\n===END===\n')
        try:
            exit_code, deprecation_text = self._invoke(path, "--format-style", style)
            assert exit_code == 0
            assert deprecation_text == "", (
                f"Unexpected DeprecationWarning when --format-style={style}: " f"{deprecation_text!r}"
            )
        finally:
            os.unlink(path)

    def test_behavior_unchanged_when_explicit_none_vs_omitted(self) -> None:
        """v1.13.0 contract at the CLI: ``--format-style none`` produces the
        same output bytes as omitting the flag. The warning fires but the
        behaviour does NOT flip until v1.14.0.
        """
        initial = '===TEST===\nKEY::"v1"\nOTHER::"stable"\n===END===\n'

        path_omitted = _make_tmp_file(initial)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self._invoke(path_omitted)
            output_omitted = Path(path_omitted).read_bytes()
        finally:
            os.unlink(path_omitted)

        path_explicit = _make_tmp_file(initial)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                self._invoke(path_explicit, "--format-style", "none")
            output_explicit = Path(path_explicit).read_bytes()
        finally:
            os.unlink(path_explicit)

        assert output_omitted == output_explicit, (
            "v1.13.0 contract violated: --format-style=none and omitted "
            "--format-style produced different output bytes. The default "
            "flip is scheduled for v1.14.0 — not v1.13.0."
        )
