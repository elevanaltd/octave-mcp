"""Tests for GH#266 narrowed exception handling: W_BASELINE_METRICS_SKIPPED audit.

When baseline content cannot be parsed (e.g., NAME{qualifier} curly braces),
the outer except block must:
1. Catch only parse-related exceptions (LexerError, ParserError)
2. Log a W_BASELINE_METRICS_SKIPPED correction for I4 auditability

TDD RED phase: this test should FAIL before the implementation change.
"""

import pytest

from octave_mcp.mcp.write import WriteTool


class TestBaselineMetricsSkippedAudit:
    """GH#266: W_BASELINE_METRICS_SKIPPED correction must appear when baseline parse fails."""

    @pytest.fixture
    def write_tool(self):
        return WriteTool()

    @pytest.mark.asyncio
    async def test_baseline_parse_failure_logs_correction(self, write_tool, tmp_path):
        """Content mode overwriting unparseable file must emit W_BASELINE_METRICS_SKIPPED.

        Scenario: existing file has NAME{qualifier} curly braces that cause
        both parse() and parse_with_warnings() to fail. The new content is valid.
        The correction list must include W_BASELINE_METRICS_SKIPPED for I4 auditability.
        """
        target = str(tmp_path / "test.oct.md")

        # Write an unparseable file to disk (curly braces cause LexerError)
        unparseable_content = (
            "===TEST===\n" "META:\n" '  TYPE::"EXAMPLE"\n' "ARCHETYPE::ATLAS{structural_foundation}\n" "===END==="
        )
        with open(target, "w", encoding="utf-8") as f:
            f.write(unparseable_content)

        # Overwrite with valid content (content mode)
        valid_content = (
            "===TEST===\n" "META:\n" '  TYPE::"EXAMPLE"\n' "ARCHETYPE::ATLAS<structural_foundation>\n" "===END==="
        )
        result = await write_tool.execute(target_path=target, content=valid_content, lenient=True)
        assert result["status"] == "success", f"Write failed: {result.get('errors', [])}"

        # Verify W_BASELINE_METRICS_SKIPPED correction is present (I4 auditability)
        corrections = result.get("corrections", [])
        skipped_corrections = [c for c in corrections if c.get("code") == "W_BASELINE_METRICS_SKIPPED"]
        assert len(skipped_corrections) == 1, (
            f"Expected exactly 1 W_BASELINE_METRICS_SKIPPED correction, "
            f"got {len(skipped_corrections)}. All corrections: {corrections}"
        )

        # Verify the correction contains useful diagnostic info
        correction = skipped_corrections[0]
        assert (
            "LexerError" in correction["message"]
        ), f"Correction message should mention the exception type, got: {correction['message']}"
        assert correction["safe"] is True
        assert correction["semantics_changed"] is False
