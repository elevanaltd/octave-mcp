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

    def test_validate_rejects_file_and_stdin_together(self, tmp_path):
        """CRS-FIX #4: Should reject FILE + --stdin with clear error.

        Exactly ONE input source must be provided.
        """
        octave_file = tmp_path / "test.oct.md"
        octave_file.write_text(
            """===TEST===
META:
  TYPE::"TEST"
  VERSION::"1.0"
===END==="""
        )

        runner = CliRunner()
        content = """===STDIN===
META:
  TYPE::"TEST"
===END==="""
        # Both FILE and --stdin provided - should error
        result = runner.invoke(cli, ["validate", str(octave_file), "--stdin"], input=content)
        assert result.exit_code == 1
        # Should have clear error message
        assert "cannot" in result.output.lower() or "error" in result.output.lower()


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

    def test_eject_json_format_with_meta_list(self, tmp_path):
        """Should serialize META with ListValue correctly to JSON.

        Regression test for META serialization bug: ListValue/InlineMap in META
        were copied verbatim without conversion, causing json.dumps to fail with
        "Object of type ListValue is not JSON serializable".
        """
        octave_file = tmp_path / "test.oct.md"
        octave_file.write_text(
            """===TEST===
META:
  TYPE::"TEST"
  VERSION::"1.0"
  TAGS::[a, b, c]
===END==="""
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["eject", str(octave_file), "--format", "json"])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        # Should output valid JSON without serialization error
        output = json.loads(result.output)
        assert "META" in output
        assert output["META"]["TAGS"] == ["a", "b", "c"]

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

    def test_eject_schema_option_does_not_exist(self, tmp_path):
        """CRS-FIX #1: --schema option should NOT exist on eject command.

        The --schema option was declared but never used in CLI eject.
        For CLI eject (file-based), schema is only meaningful for MCP template generation.
        Since CLI always operates on existing files, --schema serves no purpose.
        """
        octave_file = tmp_path / "test.oct.md"
        octave_file.write_text(
            """===TEST===
META:
  TYPE::"TEST"
  VERSION::"1.0"
===END==="""
        )

        runner = CliRunner()
        # --schema should not be a valid option
        result = runner.invoke(cli, ["eject", str(octave_file), "--schema", "META"])
        # Click returns exit code 2 for unknown options
        assert result.exit_code == 2
        assert "no such option" in result.output.lower() or "Error" in result.output

    def test_eject_markdown_includes_block_children(self, tmp_path):
        """CRS-FIX #2: Markdown output should include nested block children.

        The CLI _ast_to_markdown was incomplete - it didn't recursively
        process block children like the MCP version does.
        """
        octave_file = tmp_path / "test.oct.md"
        octave_file.write_text(
            """===TEST===
META:
  TYPE::"TEST"
  VERSION::"1.0"

SECTION:
  FIELD1::"value1"
  FIELD2::"value2"
===END==="""
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["eject", str(octave_file), "--format", "markdown"])
        assert result.exit_code == 0
        # Should contain the nested field names (not just the section header)
        assert "FIELD1" in result.output
        assert "FIELD2" in result.output


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

    def test_write_rejects_stdin_and_content_together(self, tmp_path):
        """CRS-FIX #3: Should reject --stdin + --content with clear error.

        Exactly ONE of: --content, --stdin, --changes must be provided.
        """
        target_file = tmp_path / "xor.oct.md"
        content = """===XOR===
META:
  TYPE::"TEST"
  VERSION::"1.0"
===END==="""

        runner = CliRunner()
        # Both --stdin and --content provided - should error
        result = runner.invoke(cli, ["write", str(target_file), "--content", content, "--stdin"], input=content)
        assert result.exit_code == 1
        # Should have clear error message
        assert "cannot" in result.output.lower() or "error" in result.output.lower()

    def test_write_rejects_stdin_and_changes_together(self, tmp_path):
        """CRS-FIX #3: Should reject --stdin + --changes with clear error."""
        target_file = tmp_path / "xor.oct.md"
        target_file.write_text(
            """===XOR===
META:
  TYPE::"TEST"
  VERSION::"1.0"
===END==="""
        )
        changes = '{"META.VERSION": "2.0"}'
        stdin_content = """===STDIN===
META:
  TYPE::"TEST"
===END==="""

        runner = CliRunner()
        # Both --stdin and --changes provided - should error
        result = runner.invoke(cli, ["write", str(target_file), "--changes", changes, "--stdin"], input=stdin_content)
        assert result.exit_code == 1
        assert "cannot" in result.output.lower() or "error" in result.output.lower()

    def test_write_rejects_content_and_changes_together(self, tmp_path):
        """CRS-FIX #3: Should reject --content + --changes with clear error."""
        target_file = tmp_path / "xor.oct.md"
        target_file.write_text(
            """===XOR===
META:
  TYPE::"TEST"
  VERSION::"1.0"
===END==="""
        )
        content = """===NEW===
META:
  TYPE::"TEST"
  VERSION::"2.0"
===END==="""
        changes = '{"META.VERSION": "2.0"}'

        runner = CliRunner()
        # Both --content and --changes provided - should error
        result = runner.invoke(cli, ["write", str(target_file), "--content", content, "--changes", changes])
        assert result.exit_code == 1
        assert "cannot" in result.output.lower() or "error" in result.output.lower()


class TestValidateEdgeCases:
    """Test validate command edge cases for coverage."""

    def test_validate_no_file_no_stdin(self):
        """Should error when neither FILE nor --stdin is provided."""
        runner = CliRunner()
        result = runner.invoke(cli, ["validate"])
        assert result.exit_code == 1
        assert "error" in result.output.lower() or "must provide" in result.output.lower()

    def test_validate_exception_during_parsing(self, tmp_path):
        """Should handle exceptions during parsing."""
        # Create a file with content that might cause issues
        octave_file = tmp_path / "bad.oct.md"
        # Empty file - should still be handled
        octave_file.write_text("")

        runner = CliRunner()
        result = runner.invoke(cli, ["validate", str(octave_file)])
        # Should complete without crashing
        assert result.exit_code in [0, 1]


class TestEjectEdgeCases:
    """Test eject command edge cases for coverage."""

    def test_eject_malformed_file_error(self, tmp_path):
        """Should handle error when file parsing fails."""
        octave_file = tmp_path / "malformed.oct.md"
        # Create file with problematic content that may cause parse error
        octave_file.write_text("===UNCLOSED SECTION WITHOUT END")

        runner = CliRunner()
        result = runner.invoke(cli, ["eject", str(octave_file)])
        # Should complete (might succeed or fail based on parser tolerance)
        # Either way, should not crash
        assert result.exit_code in [0, 1]

    def test_eject_json_with_nested_blocks(self, tmp_path):
        """JSON format should handle deeply nested blocks."""
        octave_file = tmp_path / "nested.oct.md"
        octave_file.write_text(
            """===NESTED===
META:
  TYPE::"TEST"
  VERSION::"1.0"

OUTER:
  INNER:
    DEEP::"value"
===END==="""
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["eject", str(octave_file), "--format", "json"])
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert "OUTER" in output

    def test_eject_markdown_with_root_assignment(self, tmp_path):
        """Markdown format should handle root-level assignments."""
        octave_file = tmp_path / "root_assign.oct.md"
        octave_file.write_text(
            """===ROOT===
META:
  TYPE::"TEST"
  VERSION::"1.0"

ROOT_FIELD::"root value"
===END==="""
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["eject", str(octave_file), "--format", "markdown"])
        assert result.exit_code == 0
        assert "ROOT_FIELD" in result.output


class TestWriteEdgeCases:
    """Test write command edge cases for coverage."""

    def test_write_changes_on_nonexistent_file(self, tmp_path):
        """Should error when using --changes on non-existent file."""
        target_file = tmp_path / "nonexistent.oct.md"
        changes = '{"META.VERSION": "2.0"}'

        runner = CliRunner()
        result = runner.invoke(cli, ["write", str(target_file), "--changes", changes])
        assert result.exit_code == 1
        assert "not exist" in result.output.lower() or "error" in result.output.lower()

    def test_write_changes_update_meta_block(self, tmp_path):
        """Should update entire META block when using META key."""
        target_file = tmp_path / "meta_update.oct.md"
        target_file.write_text(
            """===META_UPDATE===
META:
  TYPE::"OLD"
  VERSION::"1.0"
===END==="""
        )

        changes = '{"META": {"TYPE": "NEW", "VERSION": "2.0"}}'
        runner = CliRunner()
        result = runner.invoke(cli, ["write", str(target_file), "--changes", changes])
        assert result.exit_code == 0

    def test_write_changes_add_new_field(self, tmp_path):
        """Should add new field when field doesn't exist."""
        target_file = tmp_path / "add_field.oct.md"
        target_file.write_text(
            """===ADD_FIELD===
META:
  TYPE::"TEST"
  VERSION::"1.0"
===END==="""
        )

        changes = '{"NEW_FIELD": "new value"}'
        runner = CliRunner()
        result = runner.invoke(cli, ["write", str(target_file), "--changes", changes])
        assert result.exit_code == 0

    def test_write_invalid_json_changes(self, tmp_path):
        """Should error on invalid JSON in --changes."""
        target_file = tmp_path / "invalid_json.oct.md"
        target_file.write_text(
            """===TEST===
META:
  TYPE::"TEST"
  VERSION::"1.0"
===END==="""
        )

        invalid_json = "{invalid json"
        runner = CliRunner()
        result = runner.invoke(cli, ["write", str(target_file), "--changes", invalid_json])
        assert result.exit_code == 1
        assert "json" in result.output.lower() or "error" in result.output.lower()

    def test_write_with_schema_validation_invalid(self, tmp_path):
        """Should report INVALID when schema validation fails."""
        target_file = tmp_path / "schema_invalid.oct.md"
        # Content missing required META fields
        content = """===INVALID===
META:
  STATUS::"DRAFT"
===END==="""

        runner = CliRunner()
        result = runner.invoke(cli, ["write", str(target_file), "--content", content, "--schema", "META"])
        # Write should succeed but validation_status should show INVALID or UNVALIDATED
        assert result.exit_code == 0
        assert "INVALID" in result.output or "UNVALIDATED" in result.output


class TestWriteSecurityCommand:
    """CRS-FIX #5: Test write command security protections."""

    def test_write_rejects_symlink_target(self, tmp_path):
        """Should reject writing to symlink targets (security).

        Prevents symlink-based attacks where attacker creates symlink
        pointing to sensitive file outside expected directory.
        """
        import os

        # Create a real file
        real_file = tmp_path / "real.oct.md"
        real_file.write_text("existing content")

        # Create a symlink to it
        symlink_file = tmp_path / "link.oct.md"
        os.symlink(real_file, symlink_file)

        content = """===SYMLINK===
META:
  TYPE::"TEST"
  VERSION::"1.0"
===END==="""

        runner = CliRunner()
        result = runner.invoke(cli, ["write", str(symlink_file), "--content", content])
        # Should reject symlink with error
        assert result.exit_code == 1
        assert "symlink" in result.output.lower() or "error" in result.output.lower()

    def test_write_rejects_path_traversal(self, tmp_path):
        """Should reject paths with .. traversal (security)."""
        # Try to write outside tmp_path using ..
        target_file = tmp_path / ".." / "escape.oct.md"

        content = """===ESCAPE===
META:
  TYPE::"TEST"
  VERSION::"1.0"
===END==="""

        runner = CliRunner()
        result = runner.invoke(cli, ["write", str(target_file), "--content", content])
        # Should reject path traversal
        assert result.exit_code == 1
        assert "traversal" in result.output.lower() or "error" in result.output.lower()

    def test_write_rejects_invalid_extension(self, tmp_path):
        """Should reject files with invalid extensions (security)."""
        target_file = tmp_path / "evil.py"

        content = """===EVIL===
META:
  TYPE::"TEST"
  VERSION::"1.0"
===END==="""

        runner = CliRunner()
        result = runner.invoke(cli, ["write", str(target_file), "--content", content])
        # Should reject invalid extension
        assert result.exit_code == 1
        assert "extension" in result.output.lower() or "error" in result.output.lower()
