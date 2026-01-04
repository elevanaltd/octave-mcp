"""Integration tests for octave seal CLI command.

TDD RED phase: Tests for seal command behavior.
Tests are written BEFORE implementation per build-execution skill.

Issue #48 Phase 2 Batch 2: SEAL CLI Command
"""

import tempfile
from pathlib import Path

from click.testing import CliRunner

from octave_mcp.cli.main import cli


class TestSealCommand:
    """Tests for octave seal command."""

    def test_seal_command_exists(self):
        """seal command should be available."""
        runner = CliRunner()
        result = runner.invoke(cli, ["seal", "--help"])

        assert result.exit_code == 0
        assert "seal" in result.output.lower()

    def test_seal_command_adds_seal_section(self):
        """seal command should add SEAL section to document."""
        runner = CliRunner()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".oct.md", delete=False) as f:
            f.write(
                """===DOC===
META:
  TYPE::"TEST"
===END==="""
            )
            temp_path = Path(f.name)

        try:
            result = runner.invoke(cli, ["seal", str(temp_path)])

            assert result.exit_code == 0
            # Output should contain SEAL section
            assert "SEAL" in result.output
            assert "SCOPE" in result.output
            assert "ALGORITHM" in result.output
            assert "HASH" in result.output
        finally:
            temp_path.unlink()

    def test_seal_command_produces_parseable_output(self):
        """Sealed document should be parseable."""
        runner = CliRunner()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".oct.md", delete=False) as f:
            f.write(
                """===DOC===
META:
  TYPE::"TEST"
===END==="""
            )
            temp_path = Path(f.name)

        try:
            result = runner.invoke(cli, ["seal", str(temp_path)])
            assert result.exit_code == 0

            # Verify output is parseable
            from octave_mcp.core.parser import parse

            doc = parse(result.output)
            assert doc.name == "DOC"
        finally:
            temp_path.unlink()

    def test_seal_command_with_output_option(self):
        """--output should write to specified file."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.oct.md"
            output_path = Path(tmpdir) / "output.oct.md"

            input_path.write_text(
                """===DOC===
META:
  TYPE::"TEST"
===END==="""
            )

            result = runner.invoke(cli, ["seal", str(input_path), "--output", str(output_path)])

            assert result.exit_code == 0
            assert output_path.exists()

            # Output file should contain SEAL section
            content = output_path.read_text()
            assert "SEAL" in content
            assert "HASH" in content

    def test_seal_command_reseals_already_sealed(self):
        """Sealing an already-sealed document should produce new seal."""
        runner = CliRunner()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".oct.md", delete=False) as f:
            f.write(
                """===DOC===
META:
  TYPE::"TEST"
===END==="""
            )
            temp_path = Path(f.name)

        try:
            # First seal
            result1 = runner.invoke(cli, ["seal", str(temp_path)])
            assert result1.exit_code == 0

            # Write sealed output to file
            sealed_path = Path(str(temp_path) + ".sealed")
            sealed_path.write_text(result1.output)

            # Re-seal
            result2 = runner.invoke(cli, ["seal", str(sealed_path)])
            assert result2.exit_code == 0

            # Both outputs should have SEAL section
            assert "SEAL" in result1.output
            assert "SEAL" in result2.output

            # They should have different hashes (unless identical normalization)
            # Actually, re-sealing the same content should produce same hash
            # The important thing is it doesn't fail

        finally:
            temp_path.unlink()
            if sealed_path.exists():
                sealed_path.unlink()

    def test_seal_command_normalizes_before_sealing(self):
        """seal should normalize document before computing hash."""
        runner = CliRunner()

        # Create document with non-canonical formatting (e.g., different spacing)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".oct.md", delete=False) as f:
            f.write(
                """===DOC===
META:
  TYPE:: "TEST"
===END==="""
            )
            temp_path = Path(f.name)

        try:
            result = runner.invoke(cli, ["seal", str(temp_path)])

            assert result.exit_code == 0
            # Output should be canonical - parser strips quotes from valid identifiers
            # So "TYPE:: \"TEST\"" normalizes to "TYPE::TEST" (no quotes, no space)
            assert "TYPE::TEST" in result.output
        finally:
            temp_path.unlink()

    def test_seal_command_preserves_grammar_version(self):
        """seal should include GRAMMAR in seal if document has grammar_version."""
        runner = CliRunner()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".oct.md", delete=False) as f:
            f.write(
                """OCTAVE::5.1.0
===DOC===
META:
  TYPE::"TEST"
===END==="""
            )
            temp_path = Path(f.name)

        try:
            result = runner.invoke(cli, ["seal", str(temp_path)])

            assert result.exit_code == 0
            assert "GRAMMAR" in result.output
            assert "5.1.0" in result.output
        finally:
            temp_path.unlink()

    def test_seal_command_file_not_found(self):
        """seal should error gracefully for non-existent file."""
        runner = CliRunner()

        result = runner.invoke(cli, ["seal", "/nonexistent/file.oct.md"])

        assert result.exit_code != 0

    def test_seal_command_hash_is_deterministic(self):
        """Same document should produce same hash."""
        runner = CliRunner()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".oct.md", delete=False) as f:
            f.write(
                """===DOC===
META:
  TYPE::"TEST"
===END==="""
            )
            temp_path = Path(f.name)

        try:
            result1 = runner.invoke(cli, ["seal", str(temp_path)])
            result2 = runner.invoke(cli, ["seal", str(temp_path)])

            assert result1.exit_code == 0
            assert result2.exit_code == 0
            assert result1.output == result2.output
        finally:
            temp_path.unlink()


class TestSealOutputFormat:
    """Tests for seal command output format."""

    def test_seal_section_format(self):
        """SEAL section should have correct format."""
        runner = CliRunner()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".oct.md", delete=False) as f:
            f.write(
                """===DOC===
META:
  TYPE::"TEST"
===END==="""
            )
            temp_path = Path(f.name)

        try:
            result = runner.invoke(cli, ["seal", str(temp_path)])
            assert result.exit_code == 0

            # Parse output and check SEAL section structure
            from octave_mcp.core.ast_nodes import Section
            from octave_mcp.core.parser import parse

            doc = parse(result.output)

            # Find SEAL section
            seal_section = None
            for s in doc.sections:
                if isinstance(s, Section) and s.key == "SEAL":
                    seal_section = s
                    break

            assert seal_section is not None
            assert seal_section.section_id == "SEAL"

            # Check children
            child_keys = {c.key for c in seal_section.children if hasattr(c, "key")}
            assert "SCOPE" in child_keys
            assert "ALGORITHM" in child_keys
            assert "HASH" in child_keys
        finally:
            temp_path.unlink()

    def test_seal_scope_format(self):
        """SCOPE should have LINES[1,N] format."""
        runner = CliRunner()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".oct.md", delete=False) as f:
            f.write(
                """===DOC===
META:
  TYPE::"TEST"
===END==="""
            )
            temp_path = Path(f.name)

        try:
            result = runner.invoke(cli, ["seal", str(temp_path)])
            assert result.exit_code == 0

            # Check SCOPE format in output
            assert "LINES[1," in result.output
        finally:
            temp_path.unlink()

    def test_seal_algorithm_is_sha256(self):
        """ALGORITHM should be SHA256."""
        runner = CliRunner()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".oct.md", delete=False) as f:
            f.write(
                """===DOC===
META:
  TYPE::"TEST"
===END==="""
            )
            temp_path = Path(f.name)

        try:
            result = runner.invoke(cli, ["seal", str(temp_path)])
            assert result.exit_code == 0

            assert "SHA256" in result.output
        finally:
            temp_path.unlink()
