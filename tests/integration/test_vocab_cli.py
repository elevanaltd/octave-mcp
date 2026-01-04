"""Integration tests for the vocab CLI command group.

Issue #48 Task 2.9: Add `octave vocab list` command.
TDD RED phase: These tests define the contract.
"""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from octave_mcp.cli.main import cli

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "hydration"


class TestVocabListCommand:
    """Integration tests for `octave vocab list` command."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def sample_registry(self, tmp_path):
        """Create a sample registry file for testing."""
        registry_content = """===VOCABULARY_REGISTRY===
META:
  TYPE::"REGISTRY"
  VERSION::"1.0.0"
  PURPOSE::"Test vocabulary registry"
  STATUS::ACTIVE

§1::REGISTRY_SCHEMA
  ENTRY_FORMAT::[
    NAME::"Vocabulary capsule name",
    PATH::"Relative path from registry root",
    VERSION::"Semantic version",
    HASH::"SHA-256 hash"
  ]

§2::CORE_VOCABULARIES
  DESCRIPTION::"Built-in vocabularies"

  §2a::SNAPSHOT
    NAME::"SNAPSHOT"
    PATH::"core/SNAPSHOT.oct.md"
    VERSION::"1.0.0"
    TERMS::[SNAPSHOT,MANIFEST,PRUNED,SOURCE_URI,SOURCE_HASH]

  §2b::META
    NAME::"META"
    PATH::"core/META.oct.md"
    VERSION::"2.0.0"
    TERMS::[TYPE,VERSION,PURPOSE,STATUS,AUTHOR]

===END===
"""
        registry_path = tmp_path / "registry.oct.md"
        registry_path.write_text(registry_content)
        return registry_path

    def test_vocab_list_default_output(self, runner, sample_registry):
        """Should list vocabularies in table format by default."""
        result = runner.invoke(
            cli,
            [
                "vocab",
                "list",
                "--registry",
                str(sample_registry),
            ],
        )

        assert result.exit_code == 0
        assert "SNAPSHOT" in result.output
        assert "META" in result.output
        assert "1.0.0" in result.output
        assert "2.0.0" in result.output

    def test_vocab_list_shows_name_version_path(self, runner, sample_registry):
        """Should display name, version, and path for each vocabulary."""
        result = runner.invoke(
            cli,
            [
                "vocab",
                "list",
                "--registry",
                str(sample_registry),
            ],
        )

        assert result.exit_code == 0
        # Check for name column
        assert "SNAPSHOT" in result.output
        # Check for version column
        assert "1.0.0" in result.output
        # Check for path column
        assert "core/SNAPSHOT.oct.md" in result.output

    def test_vocab_list_shows_term_count(self, runner, sample_registry):
        """Should display term count for each vocabulary."""
        result = runner.invoke(
            cli,
            [
                "vocab",
                "list",
                "--registry",
                str(sample_registry),
            ],
        )

        assert result.exit_code == 0
        # SNAPSHOT has 5 terms, META has 5 terms
        assert "5" in result.output

    def test_vocab_list_json_format(self, runner, sample_registry):
        """Should output JSON format with --format json."""
        result = runner.invoke(
            cli,
            [
                "vocab",
                "list",
                "--registry",
                str(sample_registry),
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0

        # Parse output as JSON
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) >= 2

        # Check structure of first item
        vocab = data[0]
        assert "name" in vocab
        assert "version" in vocab
        assert "path" in vocab
        assert "term_count" in vocab

    def test_vocab_list_json_contains_all_fields(self, runner, sample_registry):
        """JSON output should contain all vocabulary entries."""
        result = runner.invoke(
            cli,
            [
                "vocab",
                "list",
                "--registry",
                str(sample_registry),
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)

        names = {v["name"] for v in data}
        assert "SNAPSHOT" in names
        assert "META" in names

    def test_vocab_list_custom_registry_path(self, runner, sample_registry):
        """Should accept custom registry path via --registry."""
        result = runner.invoke(
            cli,
            [
                "vocab",
                "list",
                "--registry",
                str(sample_registry),
            ],
        )

        assert result.exit_code == 0
        assert "SNAPSHOT" in result.output

    def test_vocab_list_missing_registry_exits_one(self, runner):
        """Should exit 1 when registry file doesn't exist."""
        result = runner.invoke(
            cli,
            [
                "vocab",
                "list",
                "--registry",
                "/nonexistent/registry.oct.md",
            ],
        )

        assert result.exit_code != 0

    def test_vocab_list_default_registry(self, runner):
        """Should use default registry path when --registry not specified."""
        # This test may pass or fail depending on whether default registry exists
        result = runner.invoke(
            cli,
            [
                "vocab",
                "list",
            ],
        )

        # Should either succeed (if default exists) or fail with helpful message
        if result.exit_code != 0:
            assert "registry" in result.output.lower()

    def test_vocab_list_table_has_headers(self, runner, sample_registry):
        """Table format should include column headers."""
        result = runner.invoke(
            cli,
            [
                "vocab",
                "list",
                "--registry",
                str(sample_registry),
            ],
        )

        assert result.exit_code == 0
        # Check for header-like text (case insensitive)
        output_lower = result.output.lower()
        assert "name" in output_lower or "vocabulary" in output_lower
        assert "version" in output_lower
        assert "path" in output_lower

    def test_vocab_list_empty_registry(self, runner, tmp_path):
        """Should handle registry with no vocabularies gracefully."""
        empty_registry = tmp_path / "empty_registry.oct.md"
        empty_registry.write_text(
            """===VOCABULARY_REGISTRY===
META:
  TYPE::"REGISTRY"
  VERSION::"1.0.0"

§1::CORE_VOCABULARIES
  DESCRIPTION::"Empty"

===END===
"""
        )

        result = runner.invoke(
            cli,
            [
                "vocab",
                "list",
                "--registry",
                str(empty_registry),
            ],
        )

        # Should succeed but show no vocabularies or a message
        assert result.exit_code == 0

    def test_vocab_command_group_exists(self, runner):
        """vocab command group should exist."""
        result = runner.invoke(cli, ["vocab", "--help"])

        assert result.exit_code == 0
        assert "list" in result.output.lower()

    def test_vocab_list_invalid_format_option(self, runner, sample_registry):
        """Should reject invalid --format values."""
        result = runner.invoke(
            cli,
            [
                "vocab",
                "list",
                "--registry",
                str(sample_registry),
                "--format",
                "xml",  # Invalid format
            ],
        )

        assert result.exit_code != 0


class TestVocabListRealRegistry:
    """Tests using the actual project registry if available."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_vocab_list_project_registry(self, runner):
        """Should list vocabularies from actual project registry."""
        registry_path = Path(__file__).parent.parent.parent / "specs" / "vocabularies" / "registry.oct.md"

        if not registry_path.exists():
            pytest.skip("Project registry not found")

        result = runner.invoke(
            cli,
            [
                "vocab",
                "list",
                "--registry",
                str(registry_path),
            ],
        )

        assert result.exit_code == 0
        # Real registry should have some vocabularies
        assert len(result.output) > 0
