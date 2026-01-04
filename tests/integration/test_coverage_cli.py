"""Integration tests for octave coverage CLI command.

TDD RED Phase: Tests written before implementation.
These tests should FAIL until the coverage command is added to CLI.

Issue #48 Phase 2 Batch 3: VOID MAPPER CLI integration.
"""

from pathlib import Path

import pytest
from click.testing import CliRunner

from octave_mcp.cli.main import cli


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def fixtures_path():
    """Return path to coverage fixtures."""
    return Path(__file__).parent.parent / "fixtures" / "coverage"


class TestCoverageCommand:
    """Tests for octave coverage CLI command."""

    def test_coverage_command_exists(self, runner):
        """Test that the coverage command is registered."""
        result = runner.invoke(cli, ["coverage", "--help"])
        assert result.exit_code == 0
        assert "coverage" in result.output.lower() or "SPEC_FILE" in result.output

    def test_coverage_with_full_coverage(self, runner, fixtures_path):
        """Test coverage command with full coverage spec/skill pair."""
        spec_file = fixtures_path / "spec_full.oct.md"
        skill_file = fixtures_path / "skill_full.oct.md"

        result = runner.invoke(cli, ["coverage", str(spec_file), str(skill_file)])

        assert result.exit_code == 0
        assert "100%" in result.output
        assert "3/3" in result.output
        assert "GAPS::[]" in result.output

    def test_coverage_with_gaps(self, runner, fixtures_path):
        """Test coverage command with gaps (partial coverage)."""
        spec_file = fixtures_path / "spec_full.oct.md"
        skill_file = fixtures_path / "skill_partial.oct.md"

        result = runner.invoke(cli, ["coverage", str(spec_file), str(skill_file)])

        assert result.exit_code == 0
        # 1 of 3 spec sections covered = 33%
        assert "33%" in result.output or "1/3" in result.output
        # Sections 2 and 3 are gaps
        assert "GAPS::" in result.output
        # Section 4 is novel (in skill, not in spec)
        assert "NOVEL::" in result.output
        assert "4" in result.output

    def test_coverage_format_json(self, runner, fixtures_path):
        """Test coverage command with --format json output."""
        spec_file = fixtures_path / "spec_full.oct.md"
        skill_file = fixtures_path / "skill_full.oct.md"

        result = runner.invoke(cli, ["coverage", str(spec_file), str(skill_file), "--format", "json"])

        assert result.exit_code == 0
        # JSON output should be parseable
        import json

        data = json.loads(result.output)
        assert "coverage_ratio" in data
        assert data["coverage_ratio"] == 1.0
        assert "covered_sections" in data
        assert "gaps" in data
        assert "novel" in data

    def test_coverage_format_text(self, runner, fixtures_path):
        """Test coverage command with --format text output (default)."""
        spec_file = fixtures_path / "spec_full.oct.md"
        skill_file = fixtures_path / "skill_full.oct.md"

        result = runner.invoke(cli, ["coverage", str(spec_file), str(skill_file), "--format", "text"])

        assert result.exit_code == 0
        assert "Coverage Analysis" in result.output
        assert "COVERAGE_RATIO::" in result.output

    def test_coverage_default_format_is_text(self, runner, fixtures_path):
        """Test that default format is text (human-readable)."""
        spec_file = fixtures_path / "spec_full.oct.md"
        skill_file = fixtures_path / "skill_full.oct.md"

        result = runner.invoke(cli, ["coverage", str(spec_file), str(skill_file)])

        assert result.exit_code == 0
        # Default format should include human-readable header
        assert "Coverage Analysis" in result.output or "COVERAGE_RATIO::" in result.output

    def test_coverage_nonexistent_spec_file(self, runner, fixtures_path):
        """Test coverage command with nonexistent spec file."""
        spec_file = fixtures_path / "nonexistent.oct.md"
        skill_file = fixtures_path / "skill_full.oct.md"

        result = runner.invoke(cli, ["coverage", str(spec_file), str(skill_file)])

        assert result.exit_code != 0
        # Should show error about missing file

    def test_coverage_nonexistent_skill_file(self, runner, fixtures_path):
        """Test coverage command with nonexistent skill file."""
        spec_file = fixtures_path / "spec_full.oct.md"
        skill_file = fixtures_path / "nonexistent.oct.md"

        result = runner.invoke(cli, ["coverage", str(spec_file), str(skill_file)])

        assert result.exit_code != 0
        # Should show error about missing file

    def test_coverage_invalid_octave_file(self, runner, tmp_path):
        """Test coverage command with invalid OCTAVE files."""
        # Create files with non-OCTAVE content
        spec_file = tmp_path / "invalid_spec.oct.md"
        skill_file = tmp_path / "invalid_skill.oct.md"

        spec_file.write_text("This is not valid OCTAVE content")
        skill_file.write_text("Neither is this")

        result = runner.invoke(cli, ["coverage", str(spec_file), str(skill_file)])

        # Should handle gracefully (may return 0 with no sections or error)
        # At minimum, should not crash
        assert result.exit_code in (0, 1)


class TestCoverageCliOutputFormat:
    """Tests for coverage CLI output formatting."""

    def test_text_output_includes_file_paths(self, runner, fixtures_path):
        """Test that text output includes spec and skill file paths."""
        spec_file = fixtures_path / "spec_full.oct.md"
        skill_file = fixtures_path / "skill_full.oct.md"

        result = runner.invoke(cli, ["coverage", str(spec_file), str(skill_file)])

        assert result.exit_code == 0
        # Should show file paths in output
        assert "spec_full.oct.md" in result.output or "Spec:" in result.output

    def test_json_output_includes_file_paths(self, runner, fixtures_path):
        """Test that JSON output includes spec and skill file paths."""
        spec_file = fixtures_path / "spec_full.oct.md"
        skill_file = fixtures_path / "skill_full.oct.md"

        result = runner.invoke(cli, ["coverage", str(spec_file), str(skill_file), "--format", "json"])

        assert result.exit_code == 0

        import json

        data = json.loads(result.output)
        assert "spec" in data or "spec_file" in data
        assert "skill" in data or "skill_file" in data

    def test_partial_coverage_json_structure(self, runner, fixtures_path):
        """Test JSON output structure with partial coverage."""
        spec_file = fixtures_path / "spec_full.oct.md"
        skill_file = fixtures_path / "skill_partial.oct.md"

        result = runner.invoke(cli, ["coverage", str(spec_file), str(skill_file), "--format", "json"])

        assert result.exit_code == 0

        import json

        data = json.loads(result.output)

        # Verify structure matches spec
        assert isinstance(data["coverage_ratio"], float)
        assert isinstance(data["covered_sections"], list)
        assert isinstance(data["gaps"], list)
        assert isinstance(data["novel"], list)

        # Verify values
        assert 0.3 <= data["coverage_ratio"] <= 0.34  # 1/3 = 0.333...
        assert "1" in data["covered_sections"]
        assert "2" in data["gaps"]
        assert "3" in data["gaps"]
        assert "4" in data["novel"]
