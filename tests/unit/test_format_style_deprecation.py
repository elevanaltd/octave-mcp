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


# ---------------------------------------------------------------------------
# CE + CRS CONDITIONAL on PR #422: schema-level regression
# ---------------------------------------------------------------------------
#
# The MCP input schema is the protocol-boundary contract. If the
# ``format_style`` schema description claims Strategy C semantics (the
# pre-PR-#418 narrow short-circuit) or references GH#377 as
# "tracked separately" (#377 IS the Strategy A work, now landed), then
# JSON-RPC clients see stale metadata while the Python-side runtime
# behaves correctly — a silent protocol-level lie.
#
# Worse: if the schema declares ``"type": "string"`` (enum-only) without
# a null variant, JSON-RPC clients passing explicit ``null`` are
# rejected at the JSON Schema boundary BEFORE reaching the Python-side
# DeprecationWarning code, making the Shape B deprecation contract
# unreachable for protocol clients.


class TestFormatStyleInputSchema:
    """Schema-level regression: protocol-boundary metadata must reflect reality.

    These checks guard against the schema going stale again as the
    underlying ``format_style`` semantics evolve. They assert the
    invariants the CE + CRS CONDITIONAL findings on PR #422 surfaced.
    """

    def _format_style_schema(self) -> dict:
        """Return the ``format_style`` property dict from the MCP input schema."""
        schema = WriteTool().get_input_schema()
        properties = schema["properties"]
        assert "format_style" in properties, "format_style missing from input schema"
        return properties["format_style"]

    def test_description_reflects_strategy_a_not_strategy_c(self) -> None:
        """Description MUST describe Strategy A semantics, not the pre-PR-#418 Strategy C."""
        desc = self._format_style_schema().get("description", "")
        # Strategy A markers that MUST be present.
        assert "Strategy A" in desc, (
            "format_style schema description does not mention 'Strategy A' — "
            "JSON-RPC clients still see stale Strategy-C metadata. "
            "See CE+CRS CONDITIONAL on PR #422."
        )
        # Pre-PR-#418 phrases that MUST NOT be present.
        for stale_marker in ("Strategy C", "parse-equality", "AST-equal to"):
            assert stale_marker not in desc, (
                f"format_style schema description contains stale Strategy-C "
                f"phrase {stale_marker!r}. The schema must be updated to "
                f"reflect Strategy A semantics (PR #418). "
                f"See CE+CRS CONDITIONAL on PR #422."
            )

    def test_description_does_not_claim_gh_377_is_tracked_separately(self) -> None:
        """GH#377 IS the Strategy A work landed in PR #418; the schema must not
        claim it is still tracked elsewhere as outstanding."""
        desc = self._format_style_schema().get("description", "")
        # The literal "tracked separately as #377" phrasing from the
        # pre-PR-#418 schema description.
        assert "tracked separately as #377" not in desc, (
            "format_style schema description still claims '#377 tracked "
            "separately' — but GH#377 IS the Strategy A work, now landed "
            "in PR #418. See CE+CRS CONDITIONAL on PR #422."
        )

    def test_description_surfaces_v1_13_0_deprecation_contract(self) -> None:
        """The Shape B deprecation contract MUST be visible at the protocol boundary.

        Without this, JSON-RPC clients have no warning at the schema level
        that explicit ``null`` is deprecated and the v1.14.0 default flip
        is coming.
        """
        desc = self._format_style_schema().get("description", "")
        assert "DEPRECATED" in desc or "Deprecated" in desc or "deprecated" in desc, (
            "format_style schema description does not surface the Shape B "
            "deprecation contract. The protocol-boundary metadata must "
            "match docstring + CHANGELOG visibility."
        )
        assert "v1.14.0" in desc, (
            "format_style schema description does not name the v1.14.0 "
            "flip target version. The protocol-boundary metadata must "
            "match docstring + CHANGELOG visibility."
        )

    def test_schema_type_admits_null(self) -> None:
        """The JSON Schema type MUST admit ``null`` so JSON-RPC clients
        passing explicit ``null`` reach the Python-side DeprecationWarning
        instead of being rejected at the schema boundary.
        """
        type_field = self._format_style_schema().get("type")
        assert type_field is not None, "format_style schema missing 'type'"
        if isinstance(type_field, str):
            pytest.fail(
                f"format_style schema declares type={type_field!r} (scalar "
                f"string). JSON-RPC clients passing explicit null would be "
                f"rejected at the schema boundary BEFORE reaching the "
                f"Python-side DeprecationWarning. The type must be a list "
                f"that includes 'null'. See CE+CRS CONDITIONAL on PR #422."
            )
        # type is a list — assert null is one of the admitted variants.
        assert "null" in type_field, (
            f"format_style schema type {type_field!r} does not include "
            f"'null'. JSON-RPC clients passing explicit null would be "
            f"rejected at the schema boundary."
        )
        # And 'string' is still admitted for the normal enum values.
        assert "string" in type_field, (
            f"format_style schema type {type_field!r} dropped 'string' — " f"normal enum values would now be rejected."
        )

    def test_schema_enum_admits_none(self) -> None:
        """The enum MUST include ``None`` as a valid value alongside the
        three string options so JSON-RPC clients passing literal null
        validate successfully and reach the Python-side warning.
        """
        enum = self._format_style_schema().get("enum")
        assert enum is not None, "format_style schema missing 'enum'"
        assert None in enum, (
            f"format_style schema enum {enum!r} does not include None. "
            f"Explicit null from a JSON-RPC client would fail enum "
            f"validation before reaching the DeprecationWarning. "
            f"See CE+CRS CONDITIONAL on PR #422."
        )
        # And the three valid string values are still present.
        for value in ("preserve", "expanded", "compact"):
            assert value in enum, f"format_style schema enum dropped {value!r}"
