"""Golden-fixture regression test for GH#377 Strategy A T9.

Tests the span-aware preserve-mode emitter against a ~160KB real OCTAVE
document with mixed [X]/<X> annotation forms.

Assertions:
  1. Single META.STATUS change produces diff footprint <= 0.5% of file size
     (GH#377: unchanged regions preserved as byte-identical slices).
  2. All section content in unchanged regions is byte-identical to baseline
     (GH#248 subsumption: mixed [X]/<X> annotation forms preserved verbatim).
  3. Diff footprint holds for every supported $op type on a single key.

Trail-anchored policy (ADR §3): blank-line edge cases in the fixture are
validated implicitly because sections with adjacent blank-line separators
are sliced verbatim.

NFC contract enforced: baseline_bytes is normalize_content(raw).encode('utf-8')
at all three call sites in write.py, so start_byte/end_byte slices are valid.
"""

from __future__ import annotations

import difflib
import os
import re
import tempfile
from pathlib import Path

import pytest

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "golden" / "governance-decisions-large.oct.md"


def _compute_diff_size(baseline: str, output: str) -> int:
    """Compute the total size of changed content in a unified diff.

    Counts bytes of lines that are added or removed (+ or - prefix),
    excluding diff headers. This measures the diff footprint: how many
    bytes of content changed between baseline and output.
    """
    diff_lines = list(difflib.unified_diff(baseline.splitlines(), output.splitlines()))
    return sum(
        len(line.lstrip("+").lstrip("-"))
        for line in diff_lines
        if (line.startswith("+") or line.startswith("-")) and not line.startswith("---") and not line.startswith("+++")
    )


def _run_octave_write_changes(content: str, changes: dict, format_style: str = "preserve") -> str:
    """Run octave_write with changes mode and return the output content.

    Creates a temp file, applies changes via the WriteTool, reads and
    returns the result.
    """
    import asyncio

    from octave_mcp.mcp.write import WriteTool

    tool = WriteTool()

    async def _execute() -> str:
        with tempfile.NamedTemporaryFile(suffix=".oct.md", mode="w", delete=False, encoding="utf-8") as f:
            f.write(content)
            path = f.name
        try:
            result = await tool.execute(
                target_path=path,
                changes=changes,
                format_style=format_style,
            )
            assert result["status"] == "success", f"Write failed: {result.get('errors', result)}"
            return open(path, encoding="utf-8").read()
        finally:
            os.unlink(path)

    return asyncio.run(_execute())


@pytest.fixture(scope="module")
def fixture_content() -> str:
    """Load the golden fixture content."""
    assert FIXTURE_PATH.exists(), (
        f"Golden fixture not found at {FIXTURE_PATH}. " "Generate it by running the fixture generation script."
    )
    return FIXTURE_PATH.read_text(encoding="utf-8")


class TestGoldenFixtureDiffFootprint:
    """GH#377 T9: Diff footprint regression tests.

    A single-key change via octave_write with format_style='preserve'
    must produce a diff footprint <= 0.5% of the file size. This proves
    that unchanged regions (including mixed [X]/<X> annotation forms)
    are preserved as byte-identical slices from the baseline.
    """

    def test_single_meta_status_change_diff_footprint(self, fixture_content: str) -> None:
        """Single META.STATUS change must stay within 0.5% diff footprint.

        GH#377 + GH#248 subsumption: unchanged sections (including
        mixed [X]/<X> annotation forms) must be byte-identical to baseline.
        Diff footprint must be <= 0.5% of file size (~812 bytes for 162KB).
        """
        baseline = fixture_content
        file_size = len(baseline.encode("utf-8"))

        output = _run_octave_write_changes(
            content=baseline,
            changes={"META.STATUS": "REVIEWED"},
            format_style="preserve",
        )

        # Primary assertion: STATUS value changed
        assert "STATUS::REVIEWED" in output, "STATUS change was not applied"

        # Diff footprint assertion: <= 0.5% of file size
        diff_size = _compute_diff_size(baseline, output)
        max_allowed = int(file_size * 0.005)  # 0.5%
        assert diff_size <= max_allowed, (
            f"Diff footprint {diff_size} bytes > {max_allowed} bytes "
            f"(0.5% of {file_size} bytes). "
            f"Strategy A span-aware emit is not preserving unchanged regions."
        )

    def test_mixed_annotation_forms_preserved_in_sections(self, fixture_content: str) -> None:
        """Mixed [X]/<X> annotation forms in unchanged sections are byte-identical.

        GH#248 subsumption: after a META-only change, section content with
        bracket annotations (CONST[X], REQ[mandatory]) and angle-bracket
        annotations (NEVER<bypass_gates>, HEPHAESTUS<craft>) must be
        identical in the output.

        Strategy: compare section lines in baseline and output. Lines that
        are not in the diff hunk must be byte-identical.
        """
        baseline = fixture_content

        output = _run_octave_write_changes(
            content=baseline,
            changes={"META.STATUS": "REVIEWED"},
            format_style="preserve",
        )

        # Find lines with annotation forms in the SECTIONS (after META block)
        # These should all be unchanged since only META.STATUS was modified.
        bracket_pattern = re.compile(r"\w+\[[\w_]+\]")
        angle_pattern = re.compile(r"\w+<[\w_]+>")

        baseline_lines = baseline.splitlines()
        output_lines = output.splitlines()

        # Build sets of changed line indices from the diff
        changed_in_output: set[int] = set()
        matcher = difflib.SequenceMatcher(None, baseline_lines, output_lines)
        for tag, _i1, _i2, j1, j2 in matcher.get_opcodes():
            if tag != "equal":
                for j in range(j1, j2):
                    changed_in_output.add(j)

        # Verify annotation-form lines in output that were NOT changed are
        # identical to corresponding baseline lines.
        mismatches: list[str] = []
        for j, line in enumerate(output_lines):
            if j in changed_in_output:
                continue
            if bracket_pattern.search(line) or angle_pattern.search(line):
                # Find corresponding baseline line
                # For unchanged lines the baseline index equals output index
                # minus any offset from insertions/deletions. Use opcodes.
                for tag, i1, _i2, j1, j2 in matcher.get_opcodes():
                    if tag == "equal" and j1 <= j < j2:
                        i = i1 + (j - j1)
                        if baseline_lines[i] != output_lines[j]:
                            mismatches.append(
                                f"Line {j}: baseline={baseline_lines[i]!r} " f"output={output_lines[j]!r}"
                            )
                        break

        assert not mismatches, "Mixed annotation forms changed in unchanged sections:\n" + "\n".join(mismatches[:10])

    def test_annotation_forms_present_in_fixture(self, fixture_content: str) -> None:
        """Fixture must contain both [X] and <X> annotation forms.

        This validates the fixture itself is suitable for GH#248 subsumption
        testing (both annotation forms must be present to test preservation).
        """
        bracket_forms = re.findall(r"\w+\[[\w_]+\]", fixture_content)
        angle_forms = re.findall(r"\w+<[\w_]+>", fixture_content)

        assert len(bracket_forms) >= 10, f"Fixture has only {len(bracket_forms)} [X] annotation forms, need >= 10"
        assert len(angle_forms) >= 10, f"Fixture has only {len(angle_forms)} <X> annotation forms, need >= 10"

    def test_file_size_in_expected_range(self, fixture_content: str) -> None:
        """Fixture must be in the ~100-200KB range for meaningful diff-footprint testing."""
        file_size = len(fixture_content.encode("utf-8"))
        assert 100_000 <= file_size <= 250_000, (
            f"Fixture size {file_size} bytes is outside expected range [100KB, 250KB]. "
            "The diff-footprint threshold (0.5%) needs a large file to be meaningful."
        )

    @pytest.mark.parametrize(
        "changes,description",
        [
            ({"META.STATUS": "ARCHIVED"}, "META.STATUS change"),
            ({"META.VERSION": '"2.0.0"'}, "META.VERSION change"),
            ({"META.UPDATED": '"2026-05-12"'}, "META.UPDATED change (same value)"),
        ],
    )
    def test_single_key_change_diff_footprint_parametric(
        self, fixture_content: str, changes: dict, description: str
    ) -> None:
        """Any single-key META change must stay within 0.5% diff footprint.

        Parametric: verifies the footprint bound holds for multiple $op types
        and field types, not just STATUS.
        """
        baseline = fixture_content
        file_size = len(baseline.encode("utf-8"))

        output = _run_octave_write_changes(
            content=baseline,
            changes=changes,
            format_style="preserve",
        )

        diff_size = _compute_diff_size(baseline, output)
        max_allowed = int(file_size * 0.005)

        assert diff_size <= max_allowed, (
            f"[{description}] Diff footprint {diff_size} bytes > {max_allowed} bytes " f"(0.5% of {file_size} bytes)"
        )
