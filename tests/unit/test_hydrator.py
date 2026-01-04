"""Unit tests for vocabulary snapshot hydration.

TDD RED phase: These tests define the contract for hydrator.py.
Tests are written BEFORE implementation per build-execution skill.

Issue #48 Phase 1: Vocabulary Snapshot Hydration MVP
"""

from pathlib import Path

import pytest

# Test fixtures path
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "hydration"


class TestHydrationPolicy:
    """Tests for HydrationPolicy dataclass."""

    def test_hydration_policy_defaults(self):
        """HydrationPolicy should have correct defaults per decided parameters."""
        from octave_mcp.core.hydrator import HydrationPolicy

        policy = HydrationPolicy()

        # LOCKED defaults from implementation plan
        assert policy.prune_strategy == "list"
        assert policy.collision_strategy == "error"
        assert policy.max_depth == 1

    def test_hydration_policy_custom_values(self):
        """HydrationPolicy should accept custom values."""
        from octave_mcp.core.hydrator import HydrationPolicy

        policy = HydrationPolicy(
            prune_strategy="list",
            collision_strategy="source_wins",
            max_depth=2,
        )

        assert policy.prune_strategy == "list"
        assert policy.collision_strategy == "source_wins"
        assert policy.max_depth == 2


class TestVocabularyParsing:
    """Tests for parsing vocabulary capsules."""

    def test_parse_vocabulary_capsule(self):
        """Should extract terms from vocabulary capsule."""
        from octave_mcp.core.hydrator import parse_vocabulary

        vocab_path = FIXTURES_DIR / "vocabulary.oct.md"
        terms = parse_vocabulary(vocab_path)

        # Should extract all terms from all sections
        assert "ALPHA" in terms
        assert "BETA" in terms
        assert "GAMMA" in terms
        assert "DELTA" in terms
        assert "EPSILON" in terms

        # Should preserve definitions
        assert terms["ALPHA"] == "First letter of the Greek alphabet"
        assert terms["BETA"] == "Second letter of the Greek alphabet"

    def test_parse_vocabulary_validates_capsule_type(self):
        """Should validate that META.TYPE is CAPSULE."""
        # Create a temp file that is not a CAPSULE
        import tempfile

        from octave_mcp.core.hydrator import VocabularyError, parse_vocabulary

        with tempfile.NamedTemporaryFile(mode="w", suffix=".oct.md", delete=False) as f:
            f.write(
                """===NOT_A_CAPSULE===
META:
  TYPE::"SPEC"
  VERSION::"1.0.0"
===END===
"""
            )
            temp_path = Path(f.name)

        try:
            with pytest.raises(VocabularyError, match="not a CAPSULE"):
                parse_vocabulary(temp_path)
        finally:
            temp_path.unlink()


class TestImportParsing:
    """Tests for parsing IMPORT directives."""

    def test_detect_import_section(self):
        """Should detect §CONTEXT::IMPORT sections."""
        from octave_mcp.core.hydrator import find_imports
        from octave_mcp.core.parser import parse

        content = """===DOC===
META:
  TYPE::"SPEC"

§CONTEXT::IMPORT["@test/vocabulary"]

§1::CONTENT
  KEY::"value"
===END===
"""
        doc = parse(content)
        imports = find_imports(doc)

        assert len(imports) == 1
        assert imports[0].namespace == "@test/vocabulary"

    def test_detect_multiple_imports(self):
        """Should detect multiple IMPORT sections."""
        from octave_mcp.core.hydrator import find_imports
        from octave_mcp.core.parser import parse

        content = """===DOC===
META:
  TYPE::"SPEC"

§CONTEXT::IMPORT["@core/meta"]
§CONTEXT::IMPORT["@core/snapshot"]

§1::CONTENT
  KEY::"value"
===END===
"""
        doc = parse(content)
        imports = find_imports(doc)

        assert len(imports) == 2
        assert imports[0].namespace == "@core/meta"
        assert imports[1].namespace == "@core/snapshot"

    def test_detect_import_with_version(self):
        """Should detect IMPORT with version specifier."""
        from octave_mcp.core.hydrator import find_imports
        from octave_mcp.core.parser import parse

        content = """===DOC===
META:
  TYPE::"SPEC"

§CONTEXT::IMPORT["@test/vocabulary","1.0.0"]

§1::CONTENT
  KEY::"value"
===END===
"""
        doc = parse(content)
        imports = find_imports(doc)

        assert len(imports) == 1
        assert imports[0].namespace == "@test/vocabulary"
        assert imports[0].version == "1.0.0"


class TestRegistryResolution:
    """Tests for resolving vocabulary namespaces via registry."""

    def test_resolve_namespace_to_path(self):
        """Should resolve @namespace/name to file path."""
        from octave_mcp.core.hydrator import VocabularyRegistry

        registry_path = Path(__file__).parent.parent.parent / "specs" / "vocabularies" / "registry.oct.md"
        registry = VocabularyRegistry(registry_path)

        # @core/SNAPSHOT should resolve to core/SNAPSHOT.oct.md
        # Issue #48: resolve now returns tuple (path, version)
        path, version = registry.resolve("@core/SNAPSHOT")
        assert path is not None
        assert "SNAPSHOT" in str(path)
        # Registry file has version 1.0.0 for SNAPSHOT
        assert version == "1.0.0"

    def test_resolve_test_namespace(self):
        """Should resolve test namespace to fixture path."""
        from octave_mcp.core.hydrator import VocabularyRegistry

        # Create a test registry that maps @test/vocabulary to fixtures
        registry = VocabularyRegistry.from_mappings({"@test/vocabulary": FIXTURES_DIR / "vocabulary.oct.md"})

        # Issue #48: resolve now returns tuple (path, version)
        path, version = registry.resolve("@test/vocabulary")
        assert path == FIXTURES_DIR / "vocabulary.oct.md"
        assert version is None  # from_mappings doesn't include version

    def test_resolve_unknown_namespace_raises(self):
        """Should raise error for unknown namespace."""
        from octave_mcp.core.hydrator import VocabularyError, VocabularyRegistry

        registry = VocabularyRegistry.from_mappings({})

        with pytest.raises(VocabularyError, match="Unknown vocabulary"):
            registry.resolve("@unknown/vocab")


class TestTermUsageDetection:
    """Tests for detecting which imported terms are actually used."""

    def test_detect_used_terms(self):
        """Should detect which terms from vocabulary are used in document."""
        from octave_mcp.core.hydrator import detect_used_terms
        from octave_mcp.core.parser import parse

        content = """===DOC===
META:
  TYPE::"SPEC"

§1::CONTENT
  USES_ALPHA::true
  DESCRIPTION::"Uses ALPHA and BETA terms"
===END===
"""
        doc = parse(content)
        available_terms = {"ALPHA", "BETA", "GAMMA", "DELTA", "EPSILON"}

        used = detect_used_terms(doc, available_terms)

        assert "ALPHA" in used
        assert "BETA" in used
        assert "GAMMA" not in used
        assert "DELTA" not in used
        assert "EPSILON" not in used

    def test_detect_terms_in_values(self):
        """Should detect terms used in string values."""
        from octave_mcp.core.hydrator import detect_used_terms
        from octave_mcp.core.parser import parse

        content = """===DOC===
META:
  TYPE::"SPEC"

§1::CONTENT
  REF::"GAMMA is the third letter"
===END===
"""
        doc = parse(content)
        available_terms = {"ALPHA", "BETA", "GAMMA"}

        used = detect_used_terms(doc, available_terms)

        assert "GAMMA" in used


class TestCollisionDetection:
    """Tests for term collision detection and handling."""

    def test_detect_collision_with_local_terms(self):
        """Should detect collision between imported and local terms."""
        from octave_mcp.core.hydrator import detect_collisions
        from octave_mcp.core.parser import parse

        content = """===DOC===
META:
  TYPE::"SPEC"

§CONTEXT::LOCAL
  ALPHA::"Local definition"

§1::CONTENT
  KEY::"value"
===END===
"""
        doc = parse(content)
        imported_terms = {"ALPHA", "BETA", "GAMMA"}

        collisions = detect_collisions(doc, imported_terms)

        assert "ALPHA" in collisions
        assert "BETA" not in collisions

    def test_collision_error_strategy(self):
        """Should raise error with 'error' collision strategy."""
        from octave_mcp.core.hydrator import CollisionError, HydrationPolicy, hydrate

        source_path = FIXTURES_DIR / "collision_source.oct.md"
        registry = _create_test_registry()
        policy = HydrationPolicy(collision_strategy="error")

        with pytest.raises(CollisionError, match="ALPHA"):
            hydrate(source_path, registry, policy)

    def test_collision_source_wins_strategy(self):
        """Should use source definition with 'source_wins' strategy."""
        from octave_mcp.core.hydrator import HydrationPolicy, hydrate

        source_path = FIXTURES_DIR / "collision_source.oct.md"
        registry = _create_test_registry()
        policy = HydrationPolicy(collision_strategy="source_wins")

        result = hydrate(source_path, registry, policy)

        # ALPHA should have the imported definition, not local
        snapshot_section = _find_snapshot_section(result)
        assert snapshot_section is not None
        alpha_def = _get_term_definition(snapshot_section, "ALPHA")
        assert alpha_def == "First letter of the Greek alphabet"

    def test_collision_local_wins_produces_self_contained_output(self):
        """Should produce self-contained output with 'local_wins' strategy.

        Issue #48 CRS fix: When local_wins is used, the local definition
        MUST be merged into the snapshot section so the hydrated document
        remains self-contained and the term is not dropped.
        """
        from octave_mcp.core.hydrator import HydrationPolicy, hydrate

        source_path = FIXTURES_DIR / "collision_source.oct.md"
        registry = _create_test_registry()
        policy = HydrationPolicy(collision_strategy="local_wins")

        result = hydrate(source_path, registry, policy)

        # ALPHA should be present with local definition (not dropped!)
        snapshot_section = _find_snapshot_section(result)
        assert snapshot_section is not None, "SNAPSHOT section should exist"

        alpha_def = _get_term_definition(snapshot_section, "ALPHA")
        assert alpha_def is not None, "ALPHA term should be in SNAPSHOT (not dropped)"
        assert (
            alpha_def == "Local definition of ALPHA that conflicts"
        ), "ALPHA should have local definition when local_wins"

        # Verify document is self-contained by checking emitted output can be reparsed
        # and still contains the ALPHA definition
        from octave_mcp.core.emitter import emit
        from octave_mcp.core.parser import parse

        output = emit(result)
        reparsed = parse(output)

        # Find SNAPSHOT in reparsed doc
        from octave_mcp.core.ast_nodes import Section

        reparsed_snapshot = None
        for section in reparsed.sections:
            if isinstance(section, Section) and "SNAPSHOT" in section.key:
                reparsed_snapshot = section
                break

        assert reparsed_snapshot is not None, "Reparsed doc should have SNAPSHOT"
        reparsed_alpha = _get_term_definition(reparsed_snapshot, "ALPHA")
        assert reparsed_alpha is not None, "Reparsed SNAPSHOT should contain ALPHA"


class TestSnapshotGeneration:
    """Tests for generating §CONTEXT::SNAPSHOT from IMPORT."""

    def test_generate_snapshot_section(self):
        """Should transform IMPORT into SNAPSHOT with used terms."""
        from octave_mcp.core.hydrator import HydrationPolicy, hydrate

        source_path = FIXTURES_DIR / "source.oct.md"
        registry = _create_test_registry()
        policy = HydrationPolicy()

        result = hydrate(source_path, registry, policy)

        # Should have SNAPSHOT section instead of IMPORT
        snapshot = _find_snapshot_section(result)
        assert snapshot is not None
        assert snapshot.key == 'SNAPSHOT["@test/vocabulary"]'

    def test_snapshot_contains_used_terms(self):
        """Should include only used terms in SNAPSHOT."""
        from octave_mcp.core.hydrator import HydrationPolicy, hydrate

        source_path = FIXTURES_DIR / "source.oct.md"
        registry = _create_test_registry()
        policy = HydrationPolicy()

        result = hydrate(source_path, registry, policy)

        snapshot = _find_snapshot_section(result)
        terms = _get_snapshot_terms(snapshot)

        # Source uses ALPHA, BETA, DELTA
        assert "ALPHA" in terms
        assert "BETA" in terms
        assert "DELTA" in terms
        # GAMMA and EPSILON are not used
        assert "GAMMA" not in terms
        assert "EPSILON" not in terms


class TestManifestGeneration:
    """Tests for §SNAPSHOT.MANIFEST generation."""

    def test_manifest_contains_source_uri(self):
        """Should include SOURCE_URI in manifest."""
        from octave_mcp.core.hydrator import HydrationPolicy, hydrate

        source_path = FIXTURES_DIR / "source.oct.md"
        registry = _create_test_registry()
        policy = HydrationPolicy()

        result = hydrate(source_path, registry, policy)

        manifest = _find_manifest_section(result)
        assert manifest is not None
        source_uri = _get_field_value(manifest, "SOURCE_URI")
        assert source_uri is not None
        assert "vocabulary.oct.md" in source_uri

    def test_manifest_contains_source_hash(self):
        """Should include SHA-256 hash in manifest."""
        from octave_mcp.core.hydrator import HydrationPolicy, hydrate

        source_path = FIXTURES_DIR / "source.oct.md"
        registry = _create_test_registry()
        policy = HydrationPolicy()

        result = hydrate(source_path, registry, policy)

        manifest = _find_manifest_section(result)
        source_hash = _get_field_value(manifest, "SOURCE_HASH")
        assert source_hash is not None
        assert source_hash.startswith("sha256:")
        # SHA-256 produces 64 hex characters
        assert len(source_hash.split(":")[1]) == 64

    def test_manifest_contains_hydration_time(self):
        """Should include ISO-8601 timestamp in manifest."""
        from octave_mcp.core.hydrator import HydrationPolicy, hydrate

        source_path = FIXTURES_DIR / "source.oct.md"
        registry = _create_test_registry()
        policy = HydrationPolicy()

        result = hydrate(source_path, registry, policy)

        manifest = _find_manifest_section(result)
        hydration_time = _get_field_value(manifest, "HYDRATION_TIME")
        assert hydration_time is not None
        # Should be ISO-8601 format
        assert "T" in hydration_time
        assert "Z" in hydration_time or "+" in hydration_time

    def test_manifest_contains_policy(self):
        """Should include hydration policy in manifest."""
        from octave_mcp.core.hydrator import HydrationPolicy, hydrate

        source_path = FIXTURES_DIR / "source.oct.md"
        registry = _create_test_registry()
        policy = HydrationPolicy()

        result = hydrate(source_path, registry, policy)

        manifest = _find_manifest_section(result)
        assert manifest is not None

        # Check policy block
        policy_block = _find_child_block(manifest, "HYDRATION_POLICY")
        assert policy_block is not None

        depth = _get_field_value(policy_block, "DEPTH")
        assert depth == 1

        prune = _get_field_value(policy_block, "PRUNE")
        assert prune == "list"

        collision = _get_field_value(policy_block, "COLLISION")
        assert collision == "error"


class TestPrunedGeneration:
    """Tests for §SNAPSHOT.PRUNED generation."""

    def test_pruned_lists_unused_terms(self):
        """Should list available-but-unused terms."""
        from octave_mcp.core.hydrator import HydrationPolicy, hydrate

        source_path = FIXTURES_DIR / "source.oct.md"
        registry = _create_test_registry()
        policy = HydrationPolicy()

        result = hydrate(source_path, registry, policy)

        pruned = _find_pruned_section(result)
        assert pruned is not None

        terms = _get_field_value(pruned, "TERMS")
        assert terms is not None
        # GAMMA and EPSILON should be in PRUNED
        assert "GAMMA" in str(terms)
        assert "EPSILON" in str(terms)

    def test_pruned_empty_when_all_used(self):
        """Should have empty TERMS when all vocabulary terms are used."""
        from octave_mcp.core.hydrator import HydrationPolicy, hydrate

        source_path = FIXTURES_DIR / "source_all_terms.oct.md"
        registry = _create_test_registry()
        policy = HydrationPolicy()

        result = hydrate(source_path, registry, policy)

        pruned = _find_pruned_section(result)
        assert pruned is not None

        terms = _get_field_value(pruned, "TERMS")
        # Should be empty list when all terms are used
        if terms is not None:
            from octave_mcp.core.ast_nodes import ListValue

            if isinstance(terms, ListValue):
                assert len(terms.items) == 0
            elif isinstance(terms, list):
                assert len(terms) == 0


class TestHydrationOutput:
    """Tests for hydration output format."""

    def test_hydration_preserves_original_content(self):
        """Should preserve non-import sections unchanged."""
        from octave_mcp.core.hydrator import HydrationPolicy, hydrate

        source_path = FIXTURES_DIR / "source.oct.md"
        registry = _create_test_registry()
        policy = HydrationPolicy()

        result = hydrate(source_path, registry, policy)

        # §1::CONTENT should still exist
        from octave_mcp.core.ast_nodes import Section

        content_section = None
        for section in result.sections:
            if isinstance(section, Section) and section.key == "CONTENT":
                content_section = section
                break

        assert content_section is not None

    def test_hydration_output_is_valid_octave(self):
        """Should produce valid OCTAVE that can be re-parsed."""
        from octave_mcp.core.emitter import emit
        from octave_mcp.core.hydrator import HydrationPolicy, hydrate
        from octave_mcp.core.parser import parse

        source_path = FIXTURES_DIR / "source.oct.md"
        registry = _create_test_registry()
        policy = HydrationPolicy()

        result = hydrate(source_path, registry, policy)

        # Emit to string
        output = emit(result)

        # Should be parseable
        reparsed = parse(output)
        assert reparsed is not None
        assert reparsed.name == result.name


class TestVersionHandling:
    """Tests for version string handling in vocabulary resolution.

    Issue #48: Version strings in IMPORT directives should be respected.
    These tests define the contract for version-aware resolution.
    """

    def test_registry_extracts_version_from_entries(self):
        """Registry should extract VERSION field from vocabulary entries."""
        from octave_mcp.core.hydrator import VocabularyRegistry

        registry_path = Path(__file__).parent.parent.parent / "specs" / "vocabularies" / "registry.oct.md"
        registry = VocabularyRegistry(registry_path)

        # Registry should now provide version info
        path, version = registry.resolve("@core/SNAPSHOT")
        assert path is not None
        assert version == "1.0.0"

    def test_registry_from_mappings_with_version(self):
        """Registry from_mappings should support version information."""
        from octave_mcp.core.hydrator import VocabularyRegistry

        # New API: mappings include version
        registry = VocabularyRegistry.from_mappings_with_versions(
            {
                "@test/vocabulary": {
                    "path": FIXTURES_DIR / "vocabulary.oct.md",
                    "version": "1.0.0",
                }
            }
        )

        path, version = registry.resolve("@test/vocabulary")
        assert path == FIXTURES_DIR / "vocabulary.oct.md"
        assert version == "1.0.0"

    def test_registry_from_mappings_without_version(self):
        """Registry from_mappings should work without version (backwards compatible)."""
        from octave_mcp.core.hydrator import VocabularyRegistry

        # Original API still works, returns None for version
        registry = VocabularyRegistry.from_mappings({"@test/vocabulary": FIXTURES_DIR / "vocabulary.oct.md"})

        path, version = registry.resolve("@test/vocabulary")
        assert path == FIXTURES_DIR / "vocabulary.oct.md"
        assert version is None

    def test_version_match_succeeds(self):
        """Should succeed when requested version matches registry version."""
        from octave_mcp.core.hydrator import VocabularyRegistry

        registry = VocabularyRegistry.from_mappings_with_versions(
            {
                "@test/vocabulary": {
                    "path": FIXTURES_DIR / "vocabulary.oct.md",
                    "version": "1.0.0",
                }
            }
        )

        # Request specific version that matches
        path, version = registry.resolve("@test/vocabulary", requested_version="1.0.0")
        assert path == FIXTURES_DIR / "vocabulary.oct.md"
        assert version == "1.0.0"

    def test_version_mismatch_raises_error(self):
        """Should raise error when requested version doesn't match registry version."""
        from octave_mcp.core.hydrator import VersionMismatchError, VocabularyRegistry

        registry = VocabularyRegistry.from_mappings_with_versions(
            {
                "@test/vocabulary": {
                    "path": FIXTURES_DIR / "vocabulary.oct.md",
                    "version": "1.0.0",
                }
            }
        )

        # Request version that doesn't match
        with pytest.raises(VersionMismatchError) as exc_info:
            registry.resolve("@test/vocabulary", requested_version="2.0.0")

        assert "2.0.0" in str(exc_info.value)
        assert "1.0.0" in str(exc_info.value)

    def test_version_request_without_registry_version(self):
        """Should raise error when version requested but registry has no version."""
        from octave_mcp.core.hydrator import VersionMismatchError, VocabularyRegistry

        registry = VocabularyRegistry.from_mappings({"@test/vocabulary": FIXTURES_DIR / "vocabulary.oct.md"})

        # Request specific version when registry has none
        with pytest.raises(VersionMismatchError):
            registry.resolve("@test/vocabulary", requested_version="1.0.0")

    def test_hydration_passes_version_to_resolve(self):
        """Hydration should pass import version to registry.resolve()."""
        from octave_mcp.core.hydrator import HydrationPolicy, VocabularyRegistry, hydrate

        source_path = FIXTURES_DIR / "source_with_version.oct.md"

        # Create registry with version
        registry = VocabularyRegistry.from_mappings_with_versions(
            {
                "@test/vocabulary": {
                    "path": FIXTURES_DIR / "vocabulary.oct.md",
                    "version": "1.0.0",
                }
            }
        )
        policy = HydrationPolicy()

        # Should succeed since versions match
        result = hydrate(source_path, registry, policy)
        assert result is not None

    def test_hydration_fails_on_version_mismatch(self):
        """Hydration should fail when import version doesn't match registry."""
        from octave_mcp.core.hydrator import (
            HydrationPolicy,
            VersionMismatchError,
            VocabularyRegistry,
            hydrate,
        )

        source_path = FIXTURES_DIR / "source_with_wrong_version.oct.md"

        # Registry has version 1.0.0
        registry = VocabularyRegistry.from_mappings_with_versions(
            {
                "@test/vocabulary": {
                    "path": FIXTURES_DIR / "vocabulary.oct.md",
                    "version": "1.0.0",
                }
            }
        )
        policy = HydrationPolicy()

        # Should fail because import requests 2.0.0
        with pytest.raises(VersionMismatchError):
            hydrate(source_path, registry, policy)

    def test_manifest_contains_requested_version(self):
        """Manifest should include REQUESTED_VERSION field."""
        from octave_mcp.core.hydrator import HydrationPolicy, VocabularyRegistry, hydrate

        source_path = FIXTURES_DIR / "source_with_version.oct.md"

        registry = VocabularyRegistry.from_mappings_with_versions(
            {
                "@test/vocabulary": {
                    "path": FIXTURES_DIR / "vocabulary.oct.md",
                    "version": "1.0.0",
                }
            }
        )
        policy = HydrationPolicy()

        result = hydrate(source_path, registry, policy)

        manifest = _find_manifest_section(result)
        requested_version = _get_field_value(manifest, "REQUESTED_VERSION")
        assert requested_version == "1.0.0"

    def test_manifest_contains_resolved_version(self):
        """Manifest should include RESOLVED_VERSION field."""
        from octave_mcp.core.hydrator import HydrationPolicy, VocabularyRegistry, hydrate

        source_path = FIXTURES_DIR / "source_with_version.oct.md"

        registry = VocabularyRegistry.from_mappings_with_versions(
            {
                "@test/vocabulary": {
                    "path": FIXTURES_DIR / "vocabulary.oct.md",
                    "version": "1.0.0",
                }
            }
        )
        policy = HydrationPolicy()

        result = hydrate(source_path, registry, policy)

        manifest = _find_manifest_section(result)
        resolved_version = _get_field_value(manifest, "RESOLVED_VERSION")
        assert resolved_version == "1.0.0"

    def test_manifest_unspecified_requested_version(self):
        """Manifest should show 'unspecified' when import has no version."""
        from octave_mcp.core.hydrator import HydrationPolicy, hydrate

        source_path = FIXTURES_DIR / "source.oct.md"
        registry = _create_test_registry_with_version()
        policy = HydrationPolicy()

        result = hydrate(source_path, registry, policy)

        manifest = _find_manifest_section(result)
        requested_version = _get_field_value(manifest, "REQUESTED_VERSION")
        assert requested_version == "unspecified"


def _create_test_registry_with_version():
    """Create a test registry with version information."""
    from octave_mcp.core.hydrator import VocabularyRegistry

    return VocabularyRegistry.from_mappings_with_versions(
        {
            "@test/vocabulary": {
                "path": FIXTURES_DIR / "vocabulary.oct.md",
                "version": "1.0.0",
            }
        }
    )


class TestStalenessDetection:
    """Tests for staleness detection in hydrated documents.

    TDD RED phase: Tests for check_staleness() function.
    Issue #48 Task 2.8: octave hydrate --check staleness detection.

    Note: After CE Review security fixes (Issue #48 Phase 2-3), SOURCE_URI
    must use relative paths. Tests use relative paths from a controlled base.
    """

    def test_check_staleness_returns_fresh_when_hash_matches(self):
        """Should return FRESH status when source hash matches manifest."""
        import os
        import tempfile
        from pathlib import Path

        from octave_mcp.core.hydrator import check_staleness, compute_vocabulary_hash
        from octave_mcp.core.parser import parse

        # Security: Use relative path from a temp directory with a copy of the vocab
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            # Copy vocabulary to temp dir
            vocab_source = FIXTURES_DIR / "vocabulary.oct.md"
            vocab_copy = base / "vocabulary.oct.md"
            vocab_copy.write_text(vocab_source.read_text())
            vocab_hash = compute_vocabulary_hash(vocab_copy)

            # Use relative path in manifest
            hydrated_content = f"""===HYDRATED_DOC===
META:
  TYPE::"SPEC"
  VERSION::"1.0.0"

§CONTEXT::SNAPSHOT["@test/vocabulary"]
  ALPHA::"First letter of the Greek alphabet"

§SNAPSHOT::MANIFEST
  SOURCE_URI::"vocabulary.oct.md"
  SOURCE_HASH::"{vocab_hash}"
  HYDRATION_TIME::"2024-01-01T00:00:00Z"
  REQUESTED_VERSION::"unspecified"
  RESOLVED_VERSION::"1.0.0"

===END===
"""

            # Change to temp directory so relative path resolves correctly
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                doc = parse(hydrated_content)
                results = check_staleness(doc)

                assert len(results) == 1
                assert results[0].status == "FRESH"
                assert results[0].namespace == "@test/vocabulary"
                assert results[0].expected_hash == vocab_hash
                assert results[0].actual_hash == vocab_hash
            finally:
                os.chdir(original_cwd)

    def test_check_staleness_returns_stale_when_hash_differs(self):
        """Should return STALE status when source hash doesn't match manifest."""
        import os
        import tempfile
        from pathlib import Path

        from octave_mcp.core.hydrator import check_staleness
        from octave_mcp.core.parser import parse

        fake_hash = "sha256:0000000000000000000000000000000000000000000000000000000000000000"

        # Security: Use relative path from a temp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            # Copy vocabulary to temp dir
            vocab_source = FIXTURES_DIR / "vocabulary.oct.md"
            vocab_copy = base / "vocabulary.oct.md"
            vocab_copy.write_text(vocab_source.read_text())

            hydrated_content = f"""===HYDRATED_DOC===
META:
  TYPE::"SPEC"
  VERSION::"1.0.0"

§CONTEXT::SNAPSHOT["@test/vocabulary"]
  ALPHA::"First letter of the Greek alphabet"

§SNAPSHOT::MANIFEST
  SOURCE_URI::"vocabulary.oct.md"
  SOURCE_HASH::"{fake_hash}"
  HYDRATION_TIME::"2024-01-01T00:00:00Z"
  REQUESTED_VERSION::"unspecified"
  RESOLVED_VERSION::"1.0.0"

===END===
"""

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                doc = parse(hydrated_content)
                results = check_staleness(doc)

                assert len(results) == 1
                assert results[0].status == "STALE"
                assert results[0].namespace == "@test/vocabulary"
                assert results[0].expected_hash == fake_hash
                assert results[0].actual_hash != fake_hash
            finally:
                os.chdir(original_cwd)

    def test_check_staleness_handles_missing_source_file(self):
        """Should return ERROR status when source file no longer exists."""
        import os
        import tempfile

        from octave_mcp.core.hydrator import check_staleness
        from octave_mcp.core.parser import parse

        # Use relative path (security-compliant) to a non-existent file
        hydrated_content = """===HYDRATED_DOC===
META:
  TYPE::"SPEC"
  VERSION::"1.0.0"

§CONTEXT::SNAPSHOT["@test/vocabulary"]
  ALPHA::"First letter of the Greek alphabet"

§SNAPSHOT::MANIFEST
  SOURCE_URI::"nonexistent_vocab.oct.md"
  SOURCE_HASH::"sha256:abcd1234"
  HYDRATION_TIME::"2024-01-01T00:00:00Z"

===END===
"""

        # Run from a temp directory where the file doesn't exist
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                doc = parse(hydrated_content)
                results = check_staleness(doc)

                assert len(results) == 1
                assert results[0].status == "ERROR"
                assert "not found" in results[0].error.lower()
            finally:
                os.chdir(original_cwd)

    def test_check_staleness_handles_multiple_snapshots(self):
        """Should check staleness for all SNAPSHOT manifests in document."""
        import os
        import tempfile
        from pathlib import Path

        from octave_mcp.core.hydrator import check_staleness, compute_vocabulary_hash
        from octave_mcp.core.parser import parse

        fake_hash = "sha256:0000000000000000000000000000000000000000000000000000000000000000"

        # Security: Use relative paths from a temp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            # Copy vocabulary to temp dir
            vocab_source = FIXTURES_DIR / "vocabulary.oct.md"
            vocab_copy = base / "vocabulary.oct.md"
            vocab_copy.write_text(vocab_source.read_text())
            vocab_hash = compute_vocabulary_hash(vocab_copy)

            # Document with two snapshots - one fresh, one stale
            hydrated_content = f"""===HYDRATED_DOC===
META:
  TYPE::"SPEC"
  VERSION::"1.0.0"

§CONTEXT::SNAPSHOT["@test/vocabulary"]
  ALPHA::"First letter"

§SNAPSHOT::MANIFEST
  SOURCE_URI::"vocabulary.oct.md"
  SOURCE_HASH::"{vocab_hash}"
  HYDRATION_TIME::"2024-01-01T00:00:00Z"

§CONTEXT::SNAPSHOT["@test/other"]
  BETA::"Second letter"

§SNAPSHOT::MANIFEST
  SOURCE_URI::"vocabulary.oct.md"
  SOURCE_HASH::"{fake_hash}"
  HYDRATION_TIME::"2024-01-01T00:00:00Z"

===END===
"""

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                doc = parse(hydrated_content)
                results = check_staleness(doc)

                assert len(results) == 2
                statuses = {r.namespace: r.status for r in results}
                assert statuses.get("@test/vocabulary") == "FRESH"
                assert statuses.get("@test/other") == "STALE"
            finally:
                os.chdir(original_cwd)

    def test_check_staleness_returns_empty_for_non_hydrated_document(self):
        """Should return empty list for document without SNAPSHOT sections."""
        from octave_mcp.core.hydrator import check_staleness
        from octave_mcp.core.parser import parse

        content = """===DOC===
META:
  TYPE::"SPEC"
  VERSION::"1.0.0"

§1::CONTENT
  KEY::"value"

===END===
"""

        doc = parse(content)
        results = check_staleness(doc)

        assert len(results) == 0

    def test_staleness_result_dataclass(self):
        """StalenessResult should have correct fields."""
        from octave_mcp.core.hydrator import StalenessResult

        result = StalenessResult(
            namespace="@test/vocab",
            status="FRESH",
            expected_hash="sha256:abc",
            actual_hash="sha256:abc",
        )

        assert result.namespace == "@test/vocab"
        assert result.status == "FRESH"
        assert result.expected_hash == "sha256:abc"
        assert result.actual_hash == "sha256:abc"
        assert result.error is None

    def test_staleness_result_with_error(self):
        """StalenessResult should support error field."""
        from octave_mcp.core.hydrator import StalenessResult

        result = StalenessResult(
            namespace="@test/vocab",
            status="ERROR",
            expected_hash="sha256:abc",
            actual_hash=None,
            error="File not found",
        )

        assert result.status == "ERROR"
        assert result.error == "File not found"


class TestSourceUriSecurityValidation:
    """Tests for SOURCE_URI security validation.

    Issue #48 CE Review BLOCKING: Prevent path traversal attacks via SOURCE_URI.
    A malicious document could use absolute paths like /etc/passwd,
    path traversal like ../../../sensitive/file, or symlinks to sensitive locations.

    TDD RED phase: Tests for _validate_source_uri() function.
    """

    def test_validate_source_uri_rejects_absolute_path(self):
        """Should reject absolute paths like /etc/passwd.

        Note: validate_source_uri is for validating relative paths that should
        stay within a base directory. Absolute paths bypass this model entirely.
        """
        from octave_mcp.core.hydrator import SourceUriSecurityError, validate_source_uri

        with pytest.raises(SourceUriSecurityError, match="absolute"):
            validate_source_uri("/etc/passwd", base_path=Path("/tmp/registry"))

    def test_validate_source_uri_rejects_path_traversal(self):
        """Should reject path traversal patterns like ../../../sensitive."""
        from octave_mcp.core.hydrator import SourceUriSecurityError, validate_source_uri

        with pytest.raises(SourceUriSecurityError, match="traversal"):
            validate_source_uri(
                "../../../etc/passwd",
                base_path=Path("/tmp/registry"),
            )

    def test_validate_source_uri_rejects_hidden_traversal(self):
        """Should reject hidden traversal patterns like vocab/../../etc/passwd."""
        from octave_mcp.core.hydrator import SourceUriSecurityError, validate_source_uri

        with pytest.raises(SourceUriSecurityError, match="traversal"):
            validate_source_uri(
                "vocab/../../etc/passwd",
                base_path=Path("/tmp/registry"),
            )

    def test_validate_source_uri_allows_relative_path_within_base(self):
        """Should allow relative paths that stay within base directory."""
        from octave_mcp.core.hydrator import validate_source_uri

        # Use actual fixtures directory as base
        result = validate_source_uri(
            "vocabulary.oct.md",
            base_path=FIXTURES_DIR,
        )

        assert result == FIXTURES_DIR / "vocabulary.oct.md"

    def test_validate_source_uri_allows_nested_relative_path(self):
        """Should allow nested relative paths within base."""
        import tempfile
        from pathlib import Path

        from octave_mcp.core.hydrator import validate_source_uri

        # Create nested temp structure
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            nested = base / "subdir" / "vocab.oct.md"
            nested.parent.mkdir(parents=True)
            nested.write_text("test content")

            result = validate_source_uri(
                "subdir/vocab.oct.md",
                base_path=base,
            )

            # Compare resolved paths (macOS /var -> /private/var symlink)
            assert result.resolve() == nested.resolve()

    def test_validate_source_uri_rejects_symlink_escape(self):
        """Should reject symlinks that point outside base directory.

        Note: This test creates a symlink to /etc/passwd to verify
        that symlinks are properly resolved and rejected.
        """
        import tempfile
        from pathlib import Path

        from octave_mcp.core.hydrator import SourceUriSecurityError, validate_source_uri

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            symlink = base / "malicious_link"

            # Create symlink to /etc/passwd (or any file outside base)
            symlink.symlink_to("/etc/passwd")

            with pytest.raises(SourceUriSecurityError, match="outside"):
                validate_source_uri(
                    "malicious_link",
                    base_path=base,
                )

    def test_check_staleness_returns_error_for_path_traversal(self):
        """Should return ERROR StalenessResult for malicious SOURCE_URI."""
        from octave_mcp.core.hydrator import check_staleness
        from octave_mcp.core.parser import parse

        # Malicious document with path traversal in SOURCE_URI
        malicious_content = """===HYDRATED_DOC===
META:
  TYPE::"SPEC"
  VERSION::"1.0.0"

§CONTEXT::SNAPSHOT["@test/vocabulary"]
  ALPHA::"First letter"

§SNAPSHOT::MANIFEST
  SOURCE_URI::"../../../etc/passwd"
  SOURCE_HASH::"sha256:abc123"
  HYDRATION_TIME::"2024-01-01T00:00:00Z"

===END===
"""

        doc = parse(malicious_content)
        results = check_staleness(doc)

        assert len(results) == 1
        assert results[0].status == "ERROR"
        assert "security" in results[0].error.lower() or "traversal" in results[0].error.lower()

    def test_check_staleness_rejects_absolute_path(self):
        """Should reject absolute paths in SOURCE_URI with ERROR status.

        Security model (Debate Decision): Absolute paths are FORBIDDEN in
        SOURCE_URI for unified security model with validate_source_uri().
        Error messages should not echo the raw absolute path.
        """
        from octave_mcp.core.hydrator import check_staleness
        from octave_mcp.core.parser import parse

        # Document with absolute path in SOURCE_URI (now rejected)
        content = """===HYDRATED_DOC===
META:
  TYPE::"SPEC"
  VERSION::"1.0.0"

§CONTEXT::SNAPSHOT["@test/vocabulary"]
  ALPHA::"First letter"

§SNAPSHOT::MANIFEST
  SOURCE_URI::"/etc/passwd"
  SOURCE_HASH::"sha256:abc123"
  HYDRATION_TIME::"2024-01-01T00:00:00Z"

===END===
"""

        doc = parse(content)
        results = check_staleness(doc)

        assert len(results) == 1
        assert results[0].status == "ERROR"
        # Error message should mention security but NOT echo the raw path
        assert "absolute" in results[0].error.lower() or "security" in results[0].error.lower()
        # Should NOT contain the actual path (security: don't echo)
        assert "/etc/passwd" not in results[0].error

    def test_check_staleness_works_with_relative_path(self):
        """Should correctly handle relative paths in SOURCE_URI.

        This confirms relative paths still work after the absolute path
        prohibition - the intended behavior for trusted hydration.
        """
        from octave_mcp.core.hydrator import check_staleness, compute_vocabulary_hash
        from octave_mcp.core.parser import parse

        # Use a real file that exists (vocabulary fixture)
        vocab_path = FIXTURES_DIR / "vocabulary.oct.md"
        vocab_hash = compute_vocabulary_hash(vocab_path)

        # Calculate relative path from cwd to fixture
        cwd = Path.cwd()
        try:
            rel_path = vocab_path.relative_to(cwd)
        except ValueError:
            # If can't make relative, skip this test
            pytest.skip("Cannot create relative path from cwd to fixture")

        # Document with relative path in SOURCE_URI (allowed)
        content = f"""===HYDRATED_DOC===
META:
  TYPE::"SPEC"
  VERSION::"1.0.0"

§CONTEXT::SNAPSHOT["@test/vocabulary"]
  ALPHA::"First letter"

§SNAPSHOT::MANIFEST
  SOURCE_URI::"{rel_path}"
  SOURCE_HASH::"{vocab_hash}"
  HYDRATION_TIME::"2024-01-01T00:00:00Z"

===END===
"""

        doc = parse(content)
        results = check_staleness(doc)

        assert len(results) == 1
        assert results[0].status == "FRESH"  # File exists and hash matches


class TestMalformedManifestHandling:
    """Tests for handling malformed MANIFEST sections.

    Issue #48 CE Review BLOCKING: Emit explicit ERROR for malformed manifests
    instead of silently skipping them.

    TDD RED phase: Tests for malformed manifest detection.
    """

    def test_check_staleness_returns_error_for_missing_source_uri(self):
        """Should return ERROR when MANIFEST is missing SOURCE_URI."""
        from octave_mcp.core.hydrator import check_staleness
        from octave_mcp.core.parser import parse

        content = """===HYDRATED_DOC===
META:
  TYPE::"SPEC"
  VERSION::"1.0.0"

§CONTEXT::SNAPSHOT["@test/vocabulary"]
  ALPHA::"First letter"

§SNAPSHOT::MANIFEST
  SOURCE_HASH::"sha256:abc123"
  HYDRATION_TIME::"2024-01-01T00:00:00Z"

===END===
"""

        doc = parse(content)
        results = check_staleness(doc)

        # Should report error, not silently skip
        assert len(results) == 1
        assert results[0].status == "ERROR"
        assert "SOURCE_URI" in results[0].error or "missing" in results[0].error.lower()

    def test_check_staleness_returns_error_for_missing_source_hash(self):
        """Should return ERROR when MANIFEST is missing SOURCE_HASH."""
        from octave_mcp.core.hydrator import check_staleness
        from octave_mcp.core.parser import parse

        vocab_path = FIXTURES_DIR / "vocabulary.oct.md"

        content = f"""===HYDRATED_DOC===
META:
  TYPE::"SPEC"
  VERSION::"1.0.0"

§CONTEXT::SNAPSHOT["@test/vocabulary"]
  ALPHA::"First letter"

§SNAPSHOT::MANIFEST
  SOURCE_URI::"{vocab_path}"
  HYDRATION_TIME::"2024-01-01T00:00:00Z"

===END===
"""

        doc = parse(content)
        results = check_staleness(doc)

        # Should report error, not silently skip
        assert len(results) == 1
        assert results[0].status == "ERROR"
        assert "SOURCE_HASH" in results[0].error or "missing" in results[0].error.lower()

    def test_check_staleness_returns_error_for_empty_source_uri(self):
        """Should return ERROR when SOURCE_URI is empty string."""
        from octave_mcp.core.hydrator import check_staleness
        from octave_mcp.core.parser import parse

        content = """===HYDRATED_DOC===
META:
  TYPE::"SPEC"
  VERSION::"1.0.0"

§CONTEXT::SNAPSHOT["@test/vocabulary"]
  ALPHA::"First letter"

§SNAPSHOT::MANIFEST
  SOURCE_URI::""
  SOURCE_HASH::"sha256:abc123"
  HYDRATION_TIME::"2024-01-01T00:00:00Z"

===END===
"""

        doc = parse(content)
        results = check_staleness(doc)

        # Should report error for empty SOURCE_URI
        assert len(results) == 1
        assert results[0].status == "ERROR"
        assert "empty" in results[0].error.lower() or "SOURCE_URI" in results[0].error

    def test_check_staleness_reports_all_malformed_manifests(self):
        """Should report errors for ALL malformed manifests in document."""
        import tempfile

        from octave_mcp.core.hydrator import check_staleness
        from octave_mcp.core.parser import parse

        # Use a temporary directory to create test content
        with tempfile.TemporaryDirectory() as tmpdir:
            content = f"""===HYDRATED_DOC===
META:
  TYPE::"SPEC"
  VERSION::"1.0.0"

§CONTEXT::SNAPSHOT["@test/vocab1"]
  ALPHA::"First"

§SNAPSHOT::MANIFEST
  SOURCE_HASH::"sha256:abc123"

§CONTEXT::SNAPSHOT["@test/vocab2"]
  BETA::"Second"

§SNAPSHOT::MANIFEST
  SOURCE_URI::"{tmpdir}/vocab.oct.md"

===END===
"""

            doc = parse(content)
            results = check_staleness(doc)

            # Should have two ERROR results, not silently skip
            assert len(results) == 2
            assert all(r.status == "ERROR" for r in results)


class TestHashComputation:
    """Tests for vocabulary hash computation."""

    def test_hash_is_deterministic(self):
        """Should produce same hash for same content."""
        from octave_mcp.core.hydrator import compute_vocabulary_hash

        vocab_path = FIXTURES_DIR / "vocabulary.oct.md"

        hash1 = compute_vocabulary_hash(vocab_path)
        hash2 = compute_vocabulary_hash(vocab_path)

        assert hash1 == hash2

    def test_hash_format(self):
        """Should produce sha256:HEX format."""
        from octave_mcp.core.hydrator import compute_vocabulary_hash

        vocab_path = FIXTURES_DIR / "vocabulary.oct.md"

        result = compute_vocabulary_hash(vocab_path)

        assert result.startswith("sha256:")
        hex_part = result.split(":")[1]
        assert len(hex_part) == 64
        assert all(c in "0123456789abcdef" for c in hex_part)

    def test_hash_computation_streaming(self):
        """Should use streaming to compute hash for memory efficiency.

        Issue #48 CE Review fix: Verify streaming implementation produces
        same hash as non-streaming approach. This ensures the refactor
        from content = vocab_path.read_bytes() to chunked reading is correct.
        """
        import hashlib
        import tempfile
        from pathlib import Path

        from octave_mcp.core.hydrator import compute_vocabulary_hash

        # Create test content large enough to verify streaming works
        # (though any size should produce same hash)
        test_content = b"Test content for streaming hash verification.\n" * 100

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".oct.md", delete=False) as f:
            f.write(test_content)
            temp_path = Path(f.name)

        try:
            # Compute expected hash using standard non-streaming approach
            expected_hash = f"sha256:{hashlib.sha256(test_content).hexdigest()}"

            # Compute actual hash using the function (which should now use streaming)
            actual_hash = compute_vocabulary_hash(temp_path)

            # Hashes must match - this verifies streaming produces identical results
            assert actual_hash == expected_hash, f"Streaming hash mismatch: expected {expected_hash}, got {actual_hash}"
        finally:
            temp_path.unlink()


# Helper functions for test assertions


def _create_test_registry():
    """Create a test registry with fixture mappings."""
    from octave_mcp.core.hydrator import VocabularyRegistry

    return VocabularyRegistry.from_mappings({"@test/vocabulary": FIXTURES_DIR / "vocabulary.oct.md"})


def _find_snapshot_section(doc):
    """Find §CONTEXT::SNAPSHOT section in document."""
    from octave_mcp.core.ast_nodes import Section

    for section in doc.sections:
        if isinstance(section, Section):
            if section.section_id == "CONTEXT" and "SNAPSHOT" in section.key:
                return section
    return None


def _find_manifest_section(doc):
    """Find §SNAPSHOT::MANIFEST section in document."""
    from octave_mcp.core.ast_nodes import Section

    for section in doc.sections:
        if isinstance(section, Section):
            if section.section_id == "SNAPSHOT" and section.key == "MANIFEST":
                return section
    return None


def _find_pruned_section(doc):
    """Find §SNAPSHOT::PRUNED section in document."""
    from octave_mcp.core.ast_nodes import Section

    for section in doc.sections:
        if isinstance(section, Section):
            if section.section_id == "SNAPSHOT" and section.key == "PRUNED":
                return section
    return None


def _find_child_block(section, name: str):
    """Find a child block within a section."""
    from octave_mcp.core.ast_nodes import Block

    for child in section.children:
        if isinstance(child, Block) and child.key == name:
            return child
    return None


def _get_snapshot_terms(snapshot_section) -> dict:
    """Get terms from a SNAPSHOT section."""
    from octave_mcp.core.ast_nodes import Assignment

    terms = {}
    for child in snapshot_section.children:
        if isinstance(child, Assignment):
            terms[child.key] = child.value
    return terms


def _get_term_definition(snapshot_section, term_name: str):
    """Get a specific term definition from SNAPSHOT."""
    terms = _get_snapshot_terms(snapshot_section)
    return terms.get(term_name)


def _get_field_value(section_or_block, field_name: str):
    """Get a field value from section or block."""
    from octave_mcp.core.ast_nodes import Assignment

    for child in section_or_block.children:
        if isinstance(child, Assignment) and child.key == field_name:
            return child.value
    return None
