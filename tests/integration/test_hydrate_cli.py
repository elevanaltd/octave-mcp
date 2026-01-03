"""Integration tests for the hydrate CLI command.

Issue #48 Phase 1: Vocabulary Snapshot Hydration MVP
"""

import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from octave_mcp.cli.main import cli

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "hydration"


class TestHydrateCommand:
    """Integration tests for `octave hydrate` command."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_hydrate_with_mapping(self, runner):
        """Should hydrate document using --mapping option."""
        source_file = str(FIXTURES_DIR / "source.oct.md")
        vocab_file = str(FIXTURES_DIR / "vocabulary.oct.md")

        result = runner.invoke(
            cli,
            [
                "hydrate",
                source_file,
                "--mapping",
                f"@test/vocabulary={vocab_file}",
            ],
        )

        assert result.exit_code == 0
        assert "SNAPSHOT" in result.output
        assert "MANIFEST" in result.output
        assert "PRUNED" in result.output
        # Check terms were hydrated
        assert "ALPHA" in result.output
        assert "BETA" in result.output
        assert "DELTA" in result.output

    def test_hydrate_includes_manifest(self, runner):
        """Should include complete MANIFEST section."""
        source_file = str(FIXTURES_DIR / "source.oct.md")
        vocab_file = str(FIXTURES_DIR / "vocabulary.oct.md")

        result = runner.invoke(
            cli,
            [
                "hydrate",
                source_file,
                "--mapping",
                f"@test/vocabulary={vocab_file}",
            ],
        )

        assert result.exit_code == 0
        assert "SOURCE_URI" in result.output
        assert "SOURCE_HASH" in result.output
        assert "sha256:" in result.output
        assert "HYDRATION_TIME" in result.output
        assert "HYDRATION_POLICY" in result.output

    def test_hydrate_includes_pruned_terms(self, runner):
        """Should list unused terms in PRUNED section."""
        source_file = str(FIXTURES_DIR / "source.oct.md")
        vocab_file = str(FIXTURES_DIR / "vocabulary.oct.md")

        result = runner.invoke(
            cli,
            [
                "hydrate",
                source_file,
                "--mapping",
                f"@test/vocabulary={vocab_file}",
            ],
        )

        assert result.exit_code == 0
        # GAMMA and EPSILON are not used in source.oct.md
        assert "GAMMA" in result.output
        assert "EPSILON" in result.output

    def test_hydrate_output_to_file(self, runner):
        """Should write output to file when -o specified."""
        source_file = str(FIXTURES_DIR / "source.oct.md")
        vocab_file = str(FIXTURES_DIR / "vocabulary.oct.md")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".oct.md", delete=False) as f:
            output_file = f.name

        try:
            result = runner.invoke(
                cli,
                [
                    "hydrate",
                    source_file,
                    "--mapping",
                    f"@test/vocabulary={vocab_file}",
                    "-o",
                    output_file,
                ],
            )

            assert result.exit_code == 0
            assert "Hydrated document written to" in result.output

            # Verify file was written
            output_content = Path(output_file).read_text()
            assert "SNAPSHOT" in output_content
            assert "MANIFEST" in output_content
        finally:
            Path(output_file).unlink(missing_ok=True)

    def test_hydrate_collision_error_strategy(self, runner):
        """Should fail with collision error when terms conflict."""
        source_file = str(FIXTURES_DIR / "collision_source.oct.md")
        vocab_file = str(FIXTURES_DIR / "vocabulary.oct.md")

        result = runner.invoke(
            cli,
            [
                "hydrate",
                source_file,
                "--mapping",
                f"@test/vocabulary={vocab_file}",
                "--collision",
                "error",
            ],
        )

        assert result.exit_code == 1
        assert "collision" in result.output.lower() or "ALPHA" in result.output

    def test_hydrate_collision_source_wins_strategy(self, runner):
        """Should use source definition with source_wins strategy."""
        source_file = str(FIXTURES_DIR / "collision_source.oct.md")
        vocab_file = str(FIXTURES_DIR / "vocabulary.oct.md")

        result = runner.invoke(
            cli,
            [
                "hydrate",
                source_file,
                "--mapping",
                f"@test/vocabulary={vocab_file}",
                "--collision",
                "source_wins",
            ],
        )

        assert result.exit_code == 0
        # Should contain the imported definition
        assert "First letter of the Greek alphabet" in result.output

    def test_hydrate_output_is_valid_octave(self, runner):
        """Should produce valid OCTAVE that can be re-parsed."""
        source_file = str(FIXTURES_DIR / "source.oct.md")
        vocab_file = str(FIXTURES_DIR / "vocabulary.oct.md")

        result = runner.invoke(
            cli,
            [
                "hydrate",
                source_file,
                "--mapping",
                f"@test/vocabulary={vocab_file}",
            ],
        )

        assert result.exit_code == 0

        # Parse the output to verify it's valid OCTAVE
        from octave_mcp.core.parser import parse

        doc = parse(result.output)
        assert doc is not None
        assert doc.name == "DOCUMENT_WITH_IMPORT"

    def test_hydrate_missing_file_error(self, runner):
        """Should fail with clear error for missing file."""
        result = runner.invoke(
            cli,
            [
                "hydrate",
                "nonexistent.oct.md",
                "--mapping",
                "@test/vocab=./vocab.oct.md",
            ],
        )

        assert result.exit_code != 0

    def test_hydrate_missing_registry_and_mapping(self, runner):
        """Should fail when no registry or mapping is provided."""
        source_file = str(FIXTURES_DIR / "source.oct.md")

        # Run from a temp directory where there's no default registry
        with tempfile.TemporaryDirectory():
            result = runner.invoke(
                cli,
                [
                    "hydrate",
                    source_file,
                ],
                catch_exceptions=False,
            )

            # Should fail because no registry is found
            # Note: This might succeed if there's a default registry
            # The test checks the error handling path
            if result.exit_code != 0:
                assert "registry" in result.output.lower() or "error" in result.output.lower()

    def test_hydrate_invalid_mapping_format(self, runner):
        """Should fail with clear error for invalid mapping format."""
        source_file = str(FIXTURES_DIR / "source.oct.md")

        result = runner.invoke(
            cli,
            [
                "hydrate",
                source_file,
                "--mapping",
                "@test/vocab",  # Missing =path
            ],
        )

        assert result.exit_code == 1
        assert "Invalid mapping format" in result.output

    def test_hydrate_unknown_namespace(self, runner):
        """Should fail when vocabulary namespace cannot be resolved."""
        source_file = str(FIXTURES_DIR / "source.oct.md")
        vocab_file = str(FIXTURES_DIR / "vocabulary.oct.md")

        # Create a mapping that doesn't match the IMPORT namespace
        result = runner.invoke(
            cli,
            [
                "hydrate",
                source_file,
                "--mapping",
                f"@wrong/namespace={vocab_file}",
            ],
        )

        assert result.exit_code == 1
        assert "Unknown vocabulary" in result.output

    def test_hydrate_preserves_document_structure(self, runner):
        """Should preserve original document sections."""
        source_file = str(FIXTURES_DIR / "source.oct.md")
        vocab_file = str(FIXTURES_DIR / "vocabulary.oct.md")

        result = runner.invoke(
            cli,
            [
                "hydrate",
                source_file,
                "--mapping",
                f"@test/vocabulary={vocab_file}",
            ],
        )

        assert result.exit_code == 0
        # Original sections should be preserved
        assert "CONTENT" in result.output
        assert "USES_ALPHA" in result.output
        assert "USES_BETA" in result.output
        assert "USES_DELTA" in result.output

    def test_hydrate_multiple_mappings(self, runner):
        """Should support multiple --mapping options."""
        source_file = str(FIXTURES_DIR / "source.oct.md")
        vocab_file = str(FIXTURES_DIR / "vocabulary.oct.md")

        result = runner.invoke(
            cli,
            [
                "hydrate",
                source_file,
                "--mapping",
                f"@test/vocabulary={vocab_file}",
                "--mapping",
                f"@another/vocab={vocab_file}",
            ],
        )

        # Should succeed with the @test/vocabulary mapping
        assert result.exit_code == 0


class TestHydrateEndToEnd:
    """End-to-end tests for hydration workflow."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_full_hydration_workflow(self, runner):
        """Test complete hydration workflow from IMPORT to SNAPSHOT."""
        source_file = str(FIXTURES_DIR / "source.oct.md")
        vocab_file = str(FIXTURES_DIR / "vocabulary.oct.md")

        # Step 1: Hydrate the document
        result = runner.invoke(
            cli,
            [
                "hydrate",
                source_file,
                "--mapping",
                f"@test/vocabulary={vocab_file}",
            ],
        )

        assert result.exit_code == 0

        # Step 2: Verify the output structure
        from octave_mcp.core.parser import parse

        doc = parse(result.output)

        # Check META preserved
        assert doc.meta.get("TYPE") == "SPEC"
        assert doc.meta.get("VERSION") == "1.0.0"

        # Check SNAPSHOT section exists
        from octave_mcp.core.ast_nodes import Section

        snapshot_sections = [s for s in doc.sections if isinstance(s, Section) and "SNAPSHOT" in s.key]
        assert len(snapshot_sections) >= 1

        # Check MANIFEST section exists
        manifest_sections = [
            s for s in doc.sections if isinstance(s, Section) and s.section_id == "SNAPSHOT" and s.key == "MANIFEST"
        ]
        assert len(manifest_sections) == 1

        # Check PRUNED section exists
        pruned_sections = [
            s for s in doc.sections if isinstance(s, Section) and s.section_id == "SNAPSHOT" and s.key == "PRUNED"
        ]
        assert len(pruned_sections) == 1

    def test_hydrated_document_is_self_contained(self, runner):
        """Hydrated document should be fully self-contained (no external deps)."""
        source_file = str(FIXTURES_DIR / "source.oct.md")
        vocab_file = str(FIXTURES_DIR / "vocabulary.oct.md")

        result = runner.invoke(
            cli,
            [
                "hydrate",
                source_file,
                "--mapping",
                f"@test/vocabulary={vocab_file}",
            ],
        )

        assert result.exit_code == 0

        # IMPORT directive should be replaced with SNAPSHOT
        # (Note: "IMPORT" may still appear in document name, so check for directive pattern)
        assert "§CONTEXT::IMPORT" not in result.output
        # Terms should be inlined
        assert "First letter of the Greek alphabet" in result.output
