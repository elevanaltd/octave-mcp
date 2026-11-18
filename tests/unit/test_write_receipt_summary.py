"""R1 -- octave_write opt-in ``receipt`` parameter (tool-fidelity slice 1, PR-1).

Governing record: OCTAVE-MCP-DIRECTION-CONTAINER-RECEIPTS-PITH-20261110
(field ``summary_receipt``). Build plan: tool-fidelity slice 1, section 4
(API surface) and section 5 R1 (receipt shape).

Contract pinned here:

* ``receipt`` is optional and defaults to ``"full"``. The default receipt is
  byte-for-byte today's key set (pinned by snapshot below), so the change is
  non-breaking.
* ``receipt="summary"`` keeps ``status``, ``path``, ``canonical_hash``,
  ``corrections``, ``warnings``, ``errors``, ``validation_status``, ``mode``
  (when set), and the literal-zone flags (I5: validation status and
  literal-zone validation visible). It leaves out ``diff``, ``diff_unified``,
  ``validation_hint``, ``debug_info``, ``zone_report``,
  ``literal_zone_repair_log`` and an empty ``compilations``.
* The error envelope is identical in both modes.
* An invalid ``receipt`` value returns a structured ``E_INPUT`` error and
  does not touch the target file.
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any

import pytest
import tiktoken

from octave_mcp.mcp.write import WriteTool

_TOOL = WriteTool()

_DOC_PLAIN = """===DOC===
META:
  TYPE::"TEST"
  VERSION::"1.0"

§1::BODY
KEY::"value"
===END===
"""

_DOC_ONE_ZONE = """\
===DOC===
META:
  TYPE::"TEST"
  VERSION::"1.0"

CODE::
```python
print("hello")
```
===END===
"""

_DOC_ASCII_OPERATOR = '===DOC===\nMETA:\n  TYPE::"T"\n\nK::a->b\nL::x vs y\n===END===\n'

# Today's full receipt key set on a plain successful content write (snapshot).
_FULL_SUCCESS_KEYS = {
    "status",
    "path",
    "canonical_hash",
    "corrections",
    "warnings",
    "diff",
    "diff_unified",
    "errors",
    "validation_status",
    "validation_hint",
    "compilations",
}

# Today's error envelope key set (snapshot).
_ERROR_KEYS = {
    "status",
    "path",
    "canonical_hash",
    "corrections",
    "diff",
    "diff_unified",
    "errors",
    "validation_status",
    "validation_hint",
}

_SUMMARY_SUCCESS_KEYS = {
    "status",
    "path",
    "canonical_hash",
    "corrections",
    "warnings",
    "errors",
    "validation_status",
}

_DROPPED_KEYS = {"diff", "diff_unified", "validation_hint"}


async def _write(tmpdir: str, content: str | None = None, name: str = "t.oct.md", **kwargs: Any) -> dict[str, Any]:
    target = os.path.join(tmpdir, name)
    if content is not None:
        kwargs["content"] = content
    return await _TOOL.execute(target_path=target, **kwargs)


def _blank_path(result: dict[str, Any]) -> dict[str, Any]:
    """Return a copy without the tmp path so two runs can be compared."""
    return {k: v for k, v in result.items() if k != "path"}


class TestReceiptSchema:
    """The tool schema advertises the new parameter."""

    def test_receipt_in_schema_with_enum(self) -> None:
        schema = _TOOL.get_input_schema()
        assert "receipt" in schema["properties"]
        prop = schema["properties"]["receipt"]
        assert prop["enum"] == ["full", "summary"]
        assert "receipt" not in schema["required"]

    def test_receipt_description_names_both_levels_and_default(self) -> None:
        desc = _TOOL.get_input_schema()["properties"]["receipt"]["description"]
        assert "full" in desc
        assert "summary" in desc
        assert "diff" in desc


class TestFullReceiptUnchanged:
    """Default and explicit ``full`` keep today's receipt exactly."""

    @pytest.mark.asyncio
    async def test_default_key_set_is_today_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = await _write(tmpdir, _DOC_PLAIN)
        assert result["status"] == "success"
        assert set(result) == _FULL_SUCCESS_KEYS

    @pytest.mark.asyncio
    async def test_explicit_full_equals_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            default = await _write(tmpdir, _DOC_PLAIN, name="a.oct.md")
            full = await _write(tmpdir, _DOC_PLAIN, name="b.oct.md", receipt="full")
        assert set(full) == set(default)
        assert full["canonical_hash"] == default["canonical_hash"]
        assert full["diff"] == default["diff"]


class TestSummaryReceiptShape:
    """``receipt="summary"`` keeps the kept set and drops the rest."""

    @pytest.mark.asyncio
    async def test_summary_key_set_is_exactly_the_kept_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = await _write(tmpdir, _DOC_PLAIN, receipt="summary")
        assert result["status"] == "success"
        assert set(result) == _SUMMARY_SUCCESS_KEYS
        assert not (_DROPPED_KEYS & set(result))

    @pytest.mark.asyncio
    async def test_summary_values_match_full_for_kept_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            full = await _write(tmpdir, _DOC_ASCII_OPERATOR, name="a.oct.md", lenient=True)
            summary = await _write(tmpdir, _DOC_ASCII_OPERATOR, name="b.oct.md", lenient=True, receipt="summary")
        for key in ("status", "canonical_hash", "corrections", "warnings", "errors", "validation_status"):
            assert summary[key] == full[key], key
        # I4: corrections are the audit trail and must survive.
        assert summary["corrections"]

    @pytest.mark.asyncio
    async def test_summary_keeps_nonempty_compilations(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            full = await _write(tmpdir, _DOC_ASCII_OPERATOR, name="a.oct.md", lenient=True)
            summary = await _write(tmpdir, _DOC_ASCII_OPERATOR, name="b.oct.md", lenient=True, receipt="summary")
        assert full["compilations"]
        assert summary["compilations"] == full["compilations"]

    @pytest.mark.asyncio
    async def test_summary_keeps_literal_zone_flags_and_drops_zone_detail(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            full = await _write(tmpdir, _DOC_ONE_ZONE, name="a.oct.md")
            summary = await _write(tmpdir, _DOC_ONE_ZONE, name="b.oct.md", receipt="summary")
        assert full["contains_literal_zones"] is True
        # I5: literal-zone flags stay visible.
        assert summary["contains_literal_zones"] is True
        assert summary["literal_zones_validated"] is False
        assert summary["literal_zone_count"] == full["literal_zone_count"]
        # Bulky derived detail goes.
        assert "zone_report" in full and "zone_report" not in summary
        assert "literal_zone_repair_log" in full and "literal_zone_repair_log" not in summary

    @pytest.mark.asyncio
    async def test_summary_keeps_mode_in_normalize_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            await _write(tmpdir, _DOC_PLAIN)
            summary = await _write(tmpdir, None, receipt="summary")
        assert summary["status"] == "success"
        assert summary["mode"] == "normalize"
        assert not (_DROPPED_KEYS & set(summary))

    @pytest.mark.asyncio
    async def test_summary_in_changes_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            await _write(tmpdir, _DOC_PLAIN)
            summary = await _write(tmpdir, None, changes={"META": {"VERSION": "2.0"}}, receipt="summary")
        assert summary["status"] == "success"
        assert not (_DROPPED_KEYS & set(summary))
        assert summary["validation_status"] == "UNVALIDATED"  # I5 visible

    @pytest.mark.asyncio
    async def test_summary_in_dry_run_still_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = await _write(tmpdir, _DOC_PLAIN, dry_run=True, receipt="summary")
            assert summary["status"] == "success"
            assert not (_DROPPED_KEYS & set(summary))
            assert not os.path.exists(os.path.join(tmpdir, "t.oct.md"))


class TestErrorEnvelopeIdentical:
    """Errors are the same in both modes (a refusal is never trimmed)."""

    @pytest.mark.asyncio
    async def test_error_envelope_identical_under_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bad = {"content": _DOC_PLAIN, "changes": {"KEY": "x"}}
            full = await _write(tmpdir, **bad)
            summary = await _write(tmpdir, receipt="summary", **bad)
        assert full["status"] == "error"
        assert set(full) == _ERROR_KEYS
        assert summary == full

    @pytest.mark.asyncio
    async def test_path_error_envelope_identical_under_summary(self) -> None:
        full = await _TOOL.execute(target_path="relative/../escape.oct.md", content=_DOC_PLAIN)
        summary = await _TOOL.execute(target_path="relative/../escape.oct.md", content=_DOC_PLAIN, receipt="summary")
        assert full["status"] == "error"
        assert summary == full


class TestInvalidReceiptValue:
    """An invalid value is a structured E_INPUT error and writes nothing."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad", ["bogus", "SUMMARY", "", None, 1, ["summary"]])
    async def test_invalid_receipt_returns_e_input(self, bad: Any) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = await _write(tmpdir, _DOC_PLAIN, receipt=bad)
            assert result["status"] == "error"
            assert result["errors"][0]["code"] == "E_INPUT"
            assert "receipt" in result["errors"][0]["message"]
            assert set(result) == _ERROR_KEYS
            assert result["validation_status"] == "UNVALIDATED"
            assert not os.path.exists(os.path.join(tmpdir, "t.oct.md"))


class TestSummaryIsSmaller:
    """The point of the level: fewer tokens for a large document."""

    @pytest.mark.asyncio
    async def test_summary_smaller_in_tokens_for_200_line_fixture(self) -> None:
        lines = ["===BIG===", "META:", '  TYPE::"TEST"', '  VERSION::"1.0"', "", "§1::BODY"]
        lines += [f'KEY_{i:03d}::"value number {i}"' for i in range(194)]
        lines += ["===END==="]
        content = "\n".join(lines) + "\n"
        assert len(content.splitlines()) >= 200
        enc = tiktoken.get_encoding("cl100k_base")
        with tempfile.TemporaryDirectory() as tmpdir:
            # Seed then edit one key so the full receipt carries a real diff.
            await _write(tmpdir, content)
            edited = content.replace('KEY_007::"value number 7"', 'KEY_007::"changed"')
            full = await _write(tmpdir, edited, name="t.oct.md")
            await _write(tmpdir, content)
            summary = await _write(tmpdir, edited, name="t.oct.md", receipt="summary")
        full_tokens = len(enc.encode(json.dumps(full, ensure_ascii=False)))
        summary_tokens = len(enc.encode(json.dumps(summary, ensure_ascii=False)))
        assert summary_tokens < full_tokens
