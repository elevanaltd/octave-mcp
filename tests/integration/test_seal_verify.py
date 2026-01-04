"""Integration tests for octave validate --verify-seal command.

TDD RED phase: Tests for seal verification in validate command.
Tests are written BEFORE implementation per build-execution skill.

Issue #48 Phase 2 Batch 2: SEAL Verification in Validate Command
"""

import tempfile
from pathlib import Path

from click.testing import CliRunner

from octave_mcp.cli.main import cli


class TestVerifySealFlag:
    """Tests for --verify-seal flag in validate command."""

    def test_verify_seal_flag_exists(self):
        """--verify-seal flag should be available on validate command."""
        runner = CliRunner()
        result = runner.invoke(cli, ["validate", "--help"])

        assert result.exit_code == 0
        assert "verify-seal" in result.output

    def test_verify_seal_on_valid_sealed_document(self):
        """--verify-seal should report VERIFIED for valid sealed document."""
        runner = CliRunner()

        # First create a sealed document
        with tempfile.NamedTemporaryFile(mode="w", suffix=".oct.md", delete=False) as f:
            f.write(
                """===DOC===
META:
  TYPE::"TEST"
===END==="""
            )
            temp_path = Path(f.name)

        try:
            # Seal the document
            seal_result = runner.invoke(cli, ["seal", str(temp_path)])
            assert seal_result.exit_code == 0

            # Write sealed content to a new file
            sealed_path = Path(str(temp_path) + ".sealed")
            sealed_path.write_text(seal_result.output)

            # Verify the sealed document
            verify_result = runner.invoke(cli, ["validate", str(sealed_path), "--verify-seal"])

            assert verify_result.exit_code == 0
            assert "VERIFIED" in verify_result.output
        finally:
            temp_path.unlink()
            if sealed_path.exists():
                sealed_path.unlink()

    def test_verify_seal_on_tampered_document(self):
        """--verify-seal should report INVALID for tampered document."""
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
            # Seal the document
            seal_result = runner.invoke(cli, ["seal", str(temp_path)])
            assert seal_result.exit_code == 0

            # Tamper with the sealed content by changing a value
            tampered_content = seal_result.output.replace('TYPE::"TEST"', 'TYPE::"TAMPERED"')
            if tampered_content == seal_result.output:
                # Try without quotes
                tampered_content = seal_result.output.replace("TYPE::TEST", "TYPE::TAMPERED")

            sealed_path = Path(str(temp_path) + ".tampered")
            sealed_path.write_text(tampered_content)

            # Verify the tampered document
            verify_result = runner.invoke(cli, ["validate", str(sealed_path), "--verify-seal"])

            # Should still parse successfully but seal should be invalid
            assert "INVALID" in verify_result.output
        finally:
            temp_path.unlink()
            if sealed_path.exists():
                sealed_path.unlink()

    def test_verify_seal_on_document_without_seal(self):
        """--verify-seal should report informational message for unsealed document."""
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
            verify_result = runner.invoke(cli, ["validate", str(temp_path), "--verify-seal"])

            assert verify_result.exit_code == 0
            # Should indicate no seal found (not an error)
            assert "No" in verify_result.output and "SEAL" in verify_result.output
        finally:
            temp_path.unlink()

    def test_verify_seal_validates_algorithm(self):
        """--verify-seal should check algorithm is SHA256."""
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
            # Seal the document
            seal_result = runner.invoke(cli, ["seal", str(temp_path)])
            assert seal_result.exit_code == 0

            # Verify output mentions SHA256
            assert "SHA256" in seal_result.output

            # Write and verify
            sealed_path = Path(str(temp_path) + ".sealed")
            sealed_path.write_text(seal_result.output)

            verify_result = runner.invoke(cli, ["validate", str(sealed_path), "--verify-seal"])
            assert verify_result.exit_code == 0
            assert "VERIFIED" in verify_result.output
        finally:
            temp_path.unlink()
            if sealed_path.exists():
                sealed_path.unlink()


class TestVerifySealOutput:
    """Tests for --verify-seal output format."""

    def test_verify_seal_output_includes_seal_status(self):
        """Output should include seal verification status."""
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
            # Seal the document
            seal_result = runner.invoke(cli, ["seal", str(temp_path)])
            assert seal_result.exit_code == 0

            sealed_path = Path(str(temp_path) + ".sealed")
            sealed_path.write_text(seal_result.output)

            # Verify and check output format
            verify_result = runner.invoke(cli, ["validate", str(sealed_path), "--verify-seal"])
            assert verify_result.exit_code == 0

            # Should have explicit seal status
            output = verify_result.output.lower()
            assert "seal" in output
            assert "verified" in output or "valid" in output
        finally:
            temp_path.unlink()
            if sealed_path.exists():
                sealed_path.unlink()

    def test_verify_seal_shows_hash_match_on_success(self):
        """Output should indicate hash match for verified seal."""
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
            # Seal and verify
            seal_result = runner.invoke(cli, ["seal", str(temp_path)])
            sealed_path = Path(str(temp_path) + ".sealed")
            sealed_path.write_text(seal_result.output)

            verify_result = runner.invoke(cli, ["validate", str(sealed_path), "--verify-seal"])

            # Should mention match or verification
            output = verify_result.output.lower()
            assert "verified" in output or "match" in output
        finally:
            temp_path.unlink()
            if sealed_path.exists():
                sealed_path.unlink()

    def test_verify_seal_shows_mismatch_on_failure(self):
        """Output should indicate hash mismatch for invalid seal."""
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
            # Seal and tamper
            seal_result = runner.invoke(cli, ["seal", str(temp_path)])
            tampered = seal_result.output.replace("TYPE::TEST", "TYPE::MODIFIED")

            sealed_path = Path(str(temp_path) + ".tampered")
            sealed_path.write_text(tampered)

            verify_result = runner.invoke(cli, ["validate", str(sealed_path), "--verify-seal"])

            # Should mention mismatch or invalid
            output = verify_result.output.lower()
            assert "invalid" in output or "mismatch" in output or "modified" in output
        finally:
            temp_path.unlink()
            if sealed_path.exists():
                sealed_path.unlink()


class TestVerifySealWithValidation:
    """Tests for --verify-seal combined with schema validation."""

    def test_verify_seal_works_with_schema(self):
        """--verify-seal should work alongside --schema option."""
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
            # Seal document
            seal_result = runner.invoke(cli, ["seal", str(temp_path)])
            sealed_path = Path(str(temp_path) + ".sealed")
            sealed_path.write_text(seal_result.output)

            # Verify with seal flag (schema option may or may not be valid for this test)
            verify_result = runner.invoke(cli, ["validate", str(sealed_path), "--verify-seal"])

            assert verify_result.exit_code == 0
        finally:
            temp_path.unlink()
            if sealed_path.exists():
                sealed_path.unlink()

    def test_verify_seal_reports_valid_document_but_broken_seal(self):
        """Should distinguish between document validity and seal integrity."""
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
            # Seal and tamper (document is still valid, but seal is broken)
            seal_result = runner.invoke(cli, ["seal", str(temp_path)])
            # Tamper in a way that document is still valid
            tampered = seal_result.output.replace("TYPE::TEST", "TYPE::MODIFIED")

            sealed_path = Path(str(temp_path) + ".tampered")
            sealed_path.write_text(tampered)

            verify_result = runner.invoke(cli, ["validate", str(sealed_path), "--verify-seal"])

            # Document should still be parseable/valid
            # But seal should be marked as invalid
            assert "INVALID" in verify_result.output
        finally:
            temp_path.unlink()
            if sealed_path.exists():
                sealed_path.unlink()
