"""
TDD: Test JSON Schema documentation accessibility via importlib.resources

RED phase: These tests MUST FAIL initially because the JSON Schema docs
don't exist yet at the expected location.

Purpose: Verify that JSON Schema documentation is properly packaged
and accessible as a Python package resource.
"""

from importlib.resources import as_file, files


class TestJSONSchemaResources:
    """Test JSON Schema documentation is accessible as package resource."""

    def test_json_schema_directory_exists(self):
        """Verify JSON Schema directory exists in package resources."""
        # ARRANGE: Define expected resource path
        schemas_path = files("octave_mcp.resources.specs.schemas.json")

        # ACT & ASSERT: Directory should exist
        assert schemas_path.is_dir(), "JSON Schema directory must exist in package resources"

    def test_json_schema_md_exists(self):
        """Verify json-schema.md file is accessible."""
        # ARRANGE: Get reference to the JSON Schema markdown file
        json_schema_file = files("octave_mcp.resources.specs.schemas.json").joinpath("json-schema.md")

        # ACT & ASSERT: File should exist
        assert json_schema_file.is_file(), "json-schema.md must be accessible"

    def test_json_schema_readme_exists(self):
        """Verify README.md file is accessible."""
        # ARRANGE: Get reference to the README file
        readme_file = files("octave_mcp.resources.specs.schemas.json").joinpath("README.md")

        # ACT & ASSERT: File should exist
        assert readme_file.is_file(), "README.md must be accessible"

    def test_json_schema_content_readable(self):
        """Verify json-schema.md content is readable and contains expected content."""
        # ARRANGE: Get reference to json-schema.md
        json_schema_file = files("octave_mcp.resources.specs.schemas.json").joinpath("json-schema.md")

        # ACT: Read file content
        with as_file(json_schema_file) as path:
            content = path.read_text(encoding="utf-8")

        # ASSERT: Content should contain expected sections
        assert "# OCTAVE JSON Schema" in content, "Should have main heading"
        assert "Schema Structure" in content, "Should document schema structure"
        assert "6.0" in content, "Should reference v6.0.0"

    def test_readme_content_readable(self):
        """Verify README.md content is readable."""
        # ARRANGE: Get reference to README.md
        readme_file = files("octave_mcp.resources.specs.schemas.json").joinpath("README.md")

        # ACT: Read file content
        with as_file(readme_file) as path:
            content = path.read_text(encoding="utf-8")

        # ASSERT: Content should reference json-schema.md
        assert "json-schema.md" in content, "README should reference main doc"
        assert "OCTAVE JSON Schema" in content, "README should describe purpose"


class TestVocabulariesCoreStructure:
    """Test vocabularies/core/ directory structure and required files."""

    def test_vocabularies_core_directory_exists(self):
        """Verify vocabularies/core/ directory exists."""
        # ARRANGE: Define expected resource path
        core_path = files("octave_mcp.resources.specs.vocabularies.core")

        # ACT & ASSERT: Directory should exist
        assert core_path.is_dir(), "vocabularies/core/ directory must exist"

    def test_meta_oct_md_exists(self):
        """Verify META.oct.md exists in vocabularies/core/."""
        # ARRANGE: Get reference to META.oct.md
        meta_file = files("octave_mcp.resources.specs.vocabularies.core").joinpath("META.oct.md")

        # ACT & ASSERT: File should exist
        assert meta_file.is_file(), "META.oct.md must exist in vocabularies/core/"

    def test_snapshot_oct_md_exists(self):
        """Verify SNAPSHOT.oct.md exists in vocabularies/core/."""
        # ARRANGE: Get reference to SNAPSHOT.oct.md
        snapshot_file = files("octave_mcp.resources.specs.vocabularies.core").joinpath("SNAPSHOT.oct.md")

        # ACT & ASSERT: File should exist
        assert snapshot_file.is_file(), "SNAPSHOT.oct.md must exist in vocabularies/core/"

    def test_meta_oct_content_readable(self):
        """Verify META.oct.md is readable and contains OCTAVE content."""
        # ARRANGE: Get reference to META.oct.md
        meta_file = files("octave_mcp.resources.specs.vocabularies.core").joinpath("META.oct.md")

        # ACT: Read content
        with as_file(meta_file) as path:
            content = path.read_text(encoding="utf-8")

        # ASSERT: Should contain OCTAVE structural markers
        assert "META:" in content or "TYPE::" in content, "Should contain OCTAVE structure"

    def test_snapshot_oct_content_readable(self):
        """Verify SNAPSHOT.oct.md is readable and contains OCTAVE content."""
        # ARRANGE: Get reference to SNAPSHOT.oct.md
        snapshot_file = files("octave_mcp.resources.specs.vocabularies.core").joinpath("SNAPSHOT.oct.md")

        # ACT: Read content
        with as_file(snapshot_file) as path:
            content = path.read_text(encoding="utf-8")

        # ASSERT: Should contain OCTAVE structural markers
        assert "META:" in content or "TYPE::" in content, "Should contain OCTAVE structure"
