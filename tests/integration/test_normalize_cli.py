"""Integration tests for `octave normalize` CLI command (Issue #48 Phase 2).

The normalize command transforms OCTAVE documents to canonical form:
- UTF-8 encoding
- LF-only line endings (no CRLF)
- Trimmed trailing whitespace
- Normalized indentation (2 spaces)
- Unicode operators (-> to \u2192, + to \u2295, # to \u00a7, etc.)
"""

import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from octave_mcp.cli.main import cli

# Unicode operator constants for readability
FLOW_ARROW = "\u2192"  # ->
SYNTHESIS = "\u2295"  # +
SECTION = "\u00a7"  # SS
TENSION = "\u21cc"  # <->
CONCAT = "\u29fa"  # ~
ALTERNATIVE = "\u2228"  # |
CONSTRAINT = "\u2227"  # &


class TestNormalizeCommand:
    """Test the octave normalize CLI command."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def fixtures_dir(self):
        """Return the normalize fixtures directory."""
        return Path(__file__).parent.parent / "fixtures" / "normalize"

    def test_normalize_ascii_aliases_to_unicode(self, runner, fixtures_dir):
        """Normalize ASCII aliases to canonical Unicode operators."""
        input_file = fixtures_dir / "ascii_aliases.oct.md"

        result = runner.invoke(cli, ["normalize", str(input_file)])

        assert result.exit_code == 0
        # Should convert ASCII to Unicode
        assert "->" not in result.output  # Should become FLOW_ARROW
        # Unicode should be present
        assert FLOW_ARROW in result.output
        assert SYNTHESIS in result.output
        assert SECTION in result.output

    def test_normalize_preserves_semantic_content(self, runner, fixtures_dir):
        """Normalize preserves all semantic content."""
        input_file = fixtures_dir / "ascii_aliases.oct.md"

        result = runner.invoke(cli, ["normalize", str(input_file)])

        assert result.exit_code == 0
        # Document structure preserved
        assert "===TEST_DOC===" in result.output
        assert "===END===" in result.output
        # META preserved
        assert "META:" in result.output
        # Note: EXAMPLE is a valid identifier, so it doesn't need quotes in canonical form
        assert "TYPE::EXAMPLE" in result.output
        # Assignment keys preserved
        assert "FLOW_EXAMPLE::" in result.output
        assert "SYNTHESIS_EXAMPLE::" in result.output

    def test_normalize_is_idempotent(self, runner, fixtures_dir):
        """normalize(normalize(x)) == normalize(x) - idempotency."""
        input_file = fixtures_dir / "ascii_aliases.oct.md"

        # First normalization
        result1 = runner.invoke(cli, ["normalize", str(input_file)])
        assert result1.exit_code == 0

        # Write result to temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".oct.md", delete=False) as f:
            f.write(result1.output)
            temp_path = f.name

        try:
            # Second normalization
            result2 = runner.invoke(cli, ["normalize", temp_path])
            assert result2.exit_code == 0

            # Output should be identical
            assert result1.output == result2.output
        finally:
            Path(temp_path).unlink()

    def test_normalize_output_to_file(self, runner, fixtures_dir):
        """--output writes to specified file instead of stdout."""
        input_file = fixtures_dir / "ascii_aliases.oct.md"

        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "normalized.oct.md"

            result = runner.invoke(cli, ["normalize", str(input_file), "--output", str(output_file)])

            assert result.exit_code == 0
            assert output_file.exists()

            # Read the output file
            content = output_file.read_text()
            # Should have canonical Unicode
            assert FLOW_ARROW in content
            assert "===TEST_DOC===" in content

    def test_normalize_without_output_prints_to_stdout(self, runner, fixtures_dir):
        """Without --output, normalized content goes to stdout."""
        input_file = fixtures_dir / "already_canonical.oct.md"

        result = runner.invoke(cli, ["normalize", str(input_file)])

        assert result.exit_code == 0
        # Output should contain the document
        assert "===CANONICAL_DOC===" in result.output
        assert "===END===" in result.output

    def test_normalize_already_canonical_document(self, runner, fixtures_dir):
        """Normalizing already-canonical document produces same output."""
        input_file = fixtures_dir / "already_canonical.oct.md"

        result = runner.invoke(cli, ["normalize", str(input_file)])

        assert result.exit_code == 0
        # Should maintain canonical form
        assert FLOW_ARROW in result.output
        assert SYNTHESIS in result.output
        assert SECTION in result.output

    def test_normalize_nonexistent_file(self, runner):
        """Normalize reports error for nonexistent file."""
        result = runner.invoke(cli, ["normalize", "/nonexistent/path.oct.md"])

        assert result.exit_code != 0

    def test_normalize_invalid_octave(self, runner):
        """Normalize reports error for invalid OCTAVE content."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".oct.md", delete=False) as f:
            # Write content with tab (not allowed in OCTAVE)
            f.write("===DOC===\n\tTAB_INDENTED::value\n===END===\n")
            temp_path = f.name

        try:
            result = runner.invoke(cli, ["normalize", temp_path])

            # Should fail due to tab character
            assert result.exit_code != 0
            assert "Error" in result.output or "error" in result.output
        finally:
            Path(temp_path).unlink()


class TestNormalizeEndToEnd:
    """End-to-end tests for normalize workflow."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_full_normalization_workflow(self, runner):
        """Complete workflow: create doc with ASCII, normalize, verify canonical."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create input file with ASCII aliases
            input_path = Path(tmpdir) / "input.oct.md"
            input_path.write_text(
                """\
===MY_DOC===
META:
  TYPE::"TEST"
FLOW::A->B->C
MERGE::X+Y
REF::#SECTION
TENSION::Fast vs Accurate
CONCAT::A~B
===END===
"""
            )

            # Normalize
            output_path = Path(tmpdir) / "output.oct.md"
            result = runner.invoke(cli, ["normalize", str(input_path), "--output", str(output_path)])

            assert result.exit_code == 0
            assert output_path.exists()

            # Verify canonical output
            content = output_path.read_text()
            # Unicode operators
            assert FLOW_ARROW in content
            assert SYNTHESIS in content
            assert SECTION in content
            # No ASCII aliases remain
            assert "->" not in content
            assert "#SECTION" not in content
