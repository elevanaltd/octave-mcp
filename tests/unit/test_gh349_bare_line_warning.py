"""GH#349: Bare line dropped must surface as top-level warning (I4 violation fix).

When content is dropped via bare_line_dropped repair, the tool MUST:
- Return a W_BARE_LINE_DROPPED warning in the top-level warnings array
- Mark the correction as safe=False, semantics_changed=True (data loss)
- Allow agents to detect data loss without parsing repair_log internals

TDD RED phase: These tests define the expected behavior and should FAIL
before implementation.
"""

import os
import tempfile

import pytest

from octave_mcp.mcp.write import WriteTool


class TestBareLineDroppedCorrectionCode:
    """Verify bare_line_dropped gets explicit W_BARE_LINE_DROPPED correction code.

    Currently falls through to generic else handler producing W_LENIENT_BARE_LINE_DROPPED.
    Must produce W_BARE_LINE_DROPPED with safe=False, semantics_changed=True.
    """

    @pytest.mark.asyncio
    async def test_bare_line_produces_explicit_correction_code(self):
        """bare_line_dropped must produce W_BARE_LINE_DROPPED correction, not generic code."""
        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            result = await tool.execute(
                target_path=target_path,
                content="===TEST===\nSTATUS::ACTIVE\nlogin_spike\n===END===",
                lenient=True,
            )

            assert result["status"] == "success"

            # Must have a correction with code W_BARE_LINE_DROPPED
            bare_corrections = [
                c for c in result.get("corrections", []) if c.get("code") == "W_BARE_LINE_DROPPED"
            ]
            assert len(bare_corrections) == 1, (
                f"Expected exactly 1 W_BARE_LINE_DROPPED correction, "
                f"got {len(bare_corrections)}. Corrections: {result.get('corrections', [])}"
            )

    @pytest.mark.asyncio
    async def test_bare_line_correction_marks_data_loss(self):
        """W_BARE_LINE_DROPPED correction must flag safe=False, semantics_changed=True."""
        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            result = await tool.execute(
                target_path=target_path,
                content="===TEST===\nSTATUS::ACTIVE\nlogin_spike\n===END===",
                lenient=True,
            )

            bare_corrections = [
                c for c in result.get("corrections", []) if c.get("code") == "W_BARE_LINE_DROPPED"
            ]
            assert len(bare_corrections) == 1

            correction = bare_corrections[0]
            assert correction["safe"] is False, "Data loss must be marked safe=False"
            assert correction["semantics_changed"] is True, "Data loss must be marked semantics_changed=True"

    @pytest.mark.asyncio
    async def test_bare_line_correction_includes_original_content(self):
        """W_BARE_LINE_DROPPED correction must include the dropped content."""
        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            result = await tool.execute(
                target_path=target_path,
                content="===TEST===\nSTATUS::ACTIVE\nlogin_spike\n===END===",
                lenient=True,
            )

            bare_corrections = [
                c for c in result.get("corrections", []) if c.get("code") == "W_BARE_LINE_DROPPED"
            ]
            assert len(bare_corrections) == 1

            correction = bare_corrections[0]
            assert "login_spike" in correction.get("message", ""), (
                "Correction message must include the dropped content"
            )
            assert correction.get("before") == "login_spike", (
                "Correction 'before' field must contain the dropped bare line"
            )

    @pytest.mark.asyncio
    async def test_multiple_bare_lines_produce_multiple_corrections(self):
        """Each bare line dropped must produce its own W_BARE_LINE_DROPPED correction."""
        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            result = await tool.execute(
                target_path=target_path,
                content="===TEST===\nVALID::value\nbare_one\nbare_two\nANOTHER::value2\n===END===",
                lenient=True,
            )

            bare_corrections = [
                c for c in result.get("corrections", []) if c.get("code") == "W_BARE_LINE_DROPPED"
            ]
            assert len(bare_corrections) == 2, (
                f"Expected 2 W_BARE_LINE_DROPPED corrections for 2 bare lines, "
                f"got {len(bare_corrections)}"
            )


class TestBareLineDroppedTopLevelWarnings:
    """GH#349 core requirement: warnings array in response envelope.

    Agents must be able to detect data loss without parsing repair_log
    or corrections internals. A top-level 'warnings' key makes this trivial.
    """

    @pytest.mark.asyncio
    async def test_response_envelope_includes_warnings_array(self):
        """Success response must include a top-level 'warnings' key."""
        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            result = await tool.execute(
                target_path=target_path,
                content="===TEST===\nKEY::value\n===END===",
                lenient=True,
            )

            assert result["status"] == "success"
            assert "warnings" in result, "Response envelope must include 'warnings' key"
            assert isinstance(result["warnings"], list)

    @pytest.mark.asyncio
    async def test_bare_line_surfaces_in_warnings_array(self):
        """W_BARE_LINE_DROPPED must appear in top-level warnings array."""
        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            result = await tool.execute(
                target_path=target_path,
                content="===TEST===\nSTATUS::ACTIVE\nlogin_spike\n===END===",
                lenient=True,
            )

            assert result["status"] == "success"
            assert "warnings" in result, "Response must include top-level warnings"

            warning_codes = [w.get("code") for w in result["warnings"]]
            assert "W_BARE_LINE_DROPPED" in warning_codes, (
                f"W_BARE_LINE_DROPPED must appear in top-level warnings. "
                f"Got warnings: {result.get('warnings', [])}"
            )

    @pytest.mark.asyncio
    async def test_warnings_array_empty_when_no_data_loss(self):
        """Warnings array must be empty when no data loss occurs."""
        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            result = await tool.execute(
                target_path=target_path,
                content="===TEST===\nKEY::value\n===END===",
                lenient=True,
            )

            assert result["status"] == "success"
            assert "warnings" in result
            assert len(result["warnings"]) == 0, (
                f"Expected empty warnings for clean content, got: {result['warnings']}"
            )

    @pytest.mark.asyncio
    async def test_warnings_array_present_in_strict_mode_too(self):
        """Warnings array must be present even in strict mode (always empty there)."""
        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            result = await tool.execute(
                target_path=target_path,
                content="===TEST===\nKEY::value\n===END===",
            )

            assert result["status"] == "success"
            assert "warnings" in result, "Warnings array must always be present in envelope"
            assert isinstance(result["warnings"], list)

    @pytest.mark.asyncio
    async def test_warning_includes_actionable_detail(self):
        """Each warning must include code, message, and line for agent consumption."""
        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            result = await tool.execute(
                target_path=target_path,
                content="===TEST===\nSTATUS::ACTIVE\nlogin_spike\n===END===",
                lenient=True,
            )

            warnings = result.get("warnings", [])
            bare_warnings = [w for w in warnings if w.get("code") == "W_BARE_LINE_DROPPED"]
            assert len(bare_warnings) == 1

            warning = bare_warnings[0]
            assert "code" in warning
            assert "message" in warning
            assert "line" in warning
            assert "login_spike" in warning["message"]

    @pytest.mark.asyncio
    async def test_duplicate_key_also_surfaces_in_warnings(self):
        """W_DUPLICATE_KEY (existing data-loss correction) should also surface in warnings."""
        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            result = await tool.execute(
                target_path=target_path,
                content="===TEST===\nKEY::value1\nKEY::value2\n===END===",
                lenient=True,
            )

            assert result["status"] == "success"
            # Duplicate key is also data loss (safe=False, semantics_changed=True)
            # It should appear in warnings array too
            if any(c.get("code") == "W_DUPLICATE_KEY" for c in result.get("corrections", [])):
                warning_codes = [w.get("code") for w in result.get("warnings", [])]
                assert "W_DUPLICATE_KEY" in warning_codes, (
                    "W_DUPLICATE_KEY data loss should also surface in warnings array"
                )
