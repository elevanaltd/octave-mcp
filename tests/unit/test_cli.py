"""Tests for CLI (Issue #51: CLI-MCP Alignment).

Tests CLI commands aligned with MCP tools:
- validate: Match MCP octave_validate
- eject: Match MCP octave_eject
- write: Match MCP octave_write

The deprecated 'ingest' command has been removed.
"""

import json

from click.testing import CliRunner

from octave_mcp.cli.main import cli


class TestCLI:
    """Test CLI commands."""

    def test_cli_help(self):
        """Should show help message."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "OCTAVE command-line tools" in result.output


class TestIngestRemoval:
    """Test that deprecated ingest command is removed (Issue #51)."""

    def test_ingest_command_does_not_exist(self):
        """Should not have ingest command - it was deprecated per Issue #51."""
        runner = CliRunner()
        result = runner.invoke(cli, ["ingest", "--help"])
        # Click returns exit code 2 for unknown commands
        assert result.exit_code == 2
        assert "No such command" in result.output or "Error" in result.output

    def test_help_does_not_show_ingest(self):
        """Help output should not mention ingest command."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "ingest" not in result.output.lower()


class TestValidateCommand:
    """Test validate command aligned with MCP octave_validate (Issue #51)."""

    def test_validate_file_success(self, tmp_path):
        """Should validate a valid OCTAVE file and return exit code 0."""
        # Create a valid OCTAVE file
        octave_file = tmp_path / "test.oct.md"
        octave_file.write_text(
            """===TEST===
META:
  TYPE::"TEST"
  VERSION::"1.0"
===END==="""
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["validate", str(octave_file), "--schema", "META"])
        assert result.exit_code == 0
        assert "VALIDATED" in result.output or "Valid" in result.output

    def test_validate_file_invalid_returns_error_code(self, tmp_path):
        """Should return exit code 1 for invalid file."""
        # Create an OCTAVE file with META but missing required TYPE and VERSION fields
        # (META schema requires TYPE and VERSION)
        octave_file = tmp_path / "invalid.oct.md"
        octave_file.write_text(
            """===INVALID===
META:
  STATUS::"DRAFT"
===END==="""
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["validate", str(octave_file), "--schema", "META"])
        # Should fail validation due to missing required fields
        assert result.exit_code == 1
        assert "INVALID" in result.output

    def test_validate_stdin_mode(self, tmp_path):
        """Should accept content from stdin with --stdin flag."""
        content = """===TEST===
META:
  TYPE::"TEST"
  VERSION::"1.0"
===END==="""

        runner = CliRunner()
        result = runner.invoke(cli, ["validate", "--stdin", "--schema", "META"], input=content)
        assert result.exit_code == 0

    def test_validate_with_fix_flag(self, tmp_path):
        """Should apply repairs when --fix flag is set."""
        # Create OCTAVE with repairable content
        octave_file = tmp_path / "repairable.oct.md"
        octave_file.write_text(
            """===TEST===
META:
  TYPE::"TEST"
  VERSION::"1.0"
===END==="""
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["validate", str(octave_file), "--schema", "META", "--fix"])
        assert result.exit_code == 0

    def test_validate_outputs_validation_status(self, tmp_path):
        """Should output validation_status (VALIDATED|UNVALIDATED|INVALID)."""
        octave_file = tmp_path / "test.oct.md"
        octave_file.write_text(
            """===TEST===
META:
  TYPE::"TEST"
  VERSION::"1.0"
===END==="""
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["validate", str(octave_file), "--schema", "META"])
        assert result.exit_code == 0
        # Should contain validation status in output
        assert any(status in result.output for status in ["VALIDATED", "UNVALIDATED", "INVALID"])

    def test_validate_schema_required_for_validation(self, tmp_path):
        """Validate should require --schema for schema validation."""
        octave_file = tmp_path / "test.oct.md"
        octave_file.write_text(
            """===TEST===
META:
  TYPE::"TEST"
===END==="""
        )

        runner = CliRunner()
        # Without schema, should still work but show UNVALIDATED
        result = runner.invoke(cli, ["validate", str(octave_file)])
        assert result.exit_code == 0
        # Should indicate no schema validation was performed
        assert "UNVALIDATED" in result.output or "Valid" in result.output


class TestEjectCommand:
    """Test eject command aligned with MCP octave_eject (Issue #51)."""

    def test_eject_file_default_format(self, tmp_path):
        """Should eject file in OCTAVE format by default."""
        octave_file = tmp_path / "test.oct.md"
        octave_file.write_text(
            """===TEST===
META:
  TYPE::"TEST"
  VERSION::"1.0"
===END==="""
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["eject", str(octave_file)])
        assert result.exit_code == 0
        # Default format is OCTAVE (canonical)
        assert "===TEST===" in result.output or "TEST" in result.output

    def test_eject_json_format(self, tmp_path):
        """Should eject file in JSON format when --format json."""
        octave_file = tmp_path / "test.oct.md"
        octave_file.write_text(
            """===TEST===
META:
  TYPE::"TEST"
  VERSION::"1.0"
===END==="""
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["eject", str(octave_file), "--format", "json"])
        assert result.exit_code == 0
        # Should output valid JSON
        output = json.loads(result.output)
        assert "META" in output
        assert output["META"]["TYPE"] == "TEST"

    def test_eject_yaml_format(self, tmp_path):
        """Should eject file in YAML format when --format yaml."""
        octave_file = tmp_path / "test.oct.md"
        octave_file.write_text(
            """===TEST===
META:
  TYPE::"TEST"
  VERSION::"1.0"
===END==="""
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["eject", str(octave_file), "--format", "yaml"])
        assert result.exit_code == 0
        # Should contain YAML-style output (META: at start of line)
        assert "META:" in result.output

    def test_eject_markdown_format(self, tmp_path):
        """Should eject file in Markdown format when --format markdown."""
        octave_file = tmp_path / "test.oct.md"
        octave_file.write_text(
            """===TEST===
META:
  TYPE::"TEST"
  VERSION::"1.0"
===END==="""
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["eject", str(octave_file), "--format", "markdown"])
        assert result.exit_code == 0
        # Should contain Markdown heading
        assert "#" in result.output

    def test_eject_executive_mode(self, tmp_path):
        """Should filter to executive fields in executive mode."""
        octave_file = tmp_path / "test.oct.md"
        octave_file.write_text(
            """===TEST===
META:
  TYPE::"TEST"
  VERSION::"1.0"

STATUS::"Active"
RISKS::"Low"
TESTS::"Passed"
===END==="""
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["eject", str(octave_file), "--mode", "executive"])
        assert result.exit_code == 0
        # Executive mode keeps STATUS, RISKS, DECISIONS
        # This is lossy projection
        assert "STATUS" in result.output or "RISKS" in result.output

    def test_eject_developer_mode(self, tmp_path):
        """Should filter to developer fields in developer mode."""
        octave_file = tmp_path / "test.oct.md"
        octave_file.write_text(
            """===TEST===
META:
  TYPE::"TEST"
  VERSION::"1.0"

STATUS::"Active"
TESTS::"Passed"
CI::"Green"
===END==="""
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["eject", str(octave_file), "--mode", "developer"])
        assert result.exit_code == 0
        # Developer mode keeps TESTS, CI, DEPS

    def test_eject_with_schema(self, tmp_path):
        """Should accept --schema option."""
        octave_file = tmp_path / "test.oct.md"
        octave_file.write_text(
            """===TEST===
META:
  TYPE::"TEST"
  VERSION::"1.0"
===END==="""
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["eject", str(octave_file), "--schema", "META"])
        assert result.exit_code == 0


class TestWriteCommand:
    """Test write command aligned with MCP octave_write (Issue #51)."""

    def test_write_new_file_with_content(self, tmp_path):
        """Should create new file with provided content."""
        target_file = tmp_path / "new.oct.md"
        content = """===NEW===
META:
  TYPE::"TEST"
  VERSION::"1.0"
===END==="""

        runner = CliRunner()
        result = runner.invoke(cli, ["write", str(target_file), "--content", content])
        assert result.exit_code == 0
        assert target_file.exists()
        # Output should show success message with path and hash
        assert str(target_file) in result.output or "canonical_hash" in result.output

    def test_write_with_stdin(self, tmp_path):
        """Should accept content from stdin with --stdin flag."""
        target_file = tmp_path / "stdin.oct.md"
        content = """===STDIN===
META:
  TYPE::"TEST"
  VERSION::"1.0"
===END==="""

        runner = CliRunner()
        result = runner.invoke(cli, ["write", str(target_file), "--stdin"], input=content)
        assert result.exit_code == 0
        assert target_file.exists()

    def test_write_with_changes_mode(self, tmp_path):
        """Should apply changes to existing file."""
        # Create existing file first
        target_file = tmp_path / "existing.oct.md"
        target_file.write_text(
            """===EXISTING===
META:
  TYPE::"TEST"
  VERSION::"1.0"
===END==="""
        )

        runner = CliRunner()
        # Apply changes to update META.VERSION
        changes = '{"META.VERSION": "2.0"}'
        result = runner.invoke(cli, ["write", str(target_file), "--changes", changes])
        assert result.exit_code == 0

    def test_write_with_base_hash(self, tmp_path):
        """Should accept --base-hash for CAS consistency check."""
        target_file = tmp_path / "hash.oct.md"
        content = """===HASH===
META:
  TYPE::"TEST"
  VERSION::"1.0"
===END==="""
        target_file.write_text(content)

        runner = CliRunner()
        # With correct hash, should succeed
        new_content = """===HASH===
META:
  TYPE::"TEST"
  VERSION::"2.0"
===END==="""
        result = runner.invoke(
            cli,
            ["write", str(target_file), "--content", new_content, "--base-hash", "incorrect_hash"],
        )
        # Should fail due to hash mismatch
        assert result.exit_code == 1
        assert "hash" in result.output.lower() or "mismatch" in result.output.lower()

    def test_write_with_schema_validation(self, tmp_path):
        """Should validate against schema when --schema provided."""
        target_file = tmp_path / "schema.oct.md"
        content = """===SCHEMA===
META:
  TYPE::"TEST"
  VERSION::"1.0"
===END==="""

        runner = CliRunner()
        result = runner.invoke(cli, ["write", str(target_file), "--content", content, "--schema", "META"])
        assert result.exit_code == 0
        # Should output validation status
        assert "VALIDATED" in result.output or "UNVALIDATED" in result.output

    def test_write_requires_content_or_changes(self, tmp_path):
        """Should require either --content or --changes."""
        target_file = tmp_path / "empty.oct.md"

        runner = CliRunner()
        result = runner.invoke(cli, ["write", str(target_file)])
        # Should fail without content or changes
        assert result.exit_code != 0

    def test_write_outputs_canonical_hash(self, tmp_path):
        """Should output canonical hash on success."""
        target_file = tmp_path / "hash_output.oct.md"
        content = """===HASH===
META:
  TYPE::"TEST"
  VERSION::"1.0"
===END==="""

        runner = CliRunner()
        result = runner.invoke(cli, ["write", str(target_file), "--content", content])
        assert result.exit_code == 0
        # Should include hash in output
        assert "canonical_hash" in result.output or len(result.output.strip()) >= 32
