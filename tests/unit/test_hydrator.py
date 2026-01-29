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
            f.write("""===NOT_A_CAPSULE===
META:
  TYPE::"SPEC"
  VERSION::"1.0.0"
===END===
""")
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
        assert imports[0].version is None

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


class TestHermeticStandardResolution:
    """Tests for hermetic standard resolution (resolve_hermetic_standard)."""

    def test_resolve_hermetic_standard_rejects_invalid_hash_format(self):
        """Should reject malformed frozen@sha256 references (security: no path traversal)."""
        import tempfile

        from octave_mcp.core.hydrator import VocabularyError, resolve_hermetic_standard

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)

            with pytest.raises(VocabularyError):
                resolve_hermetic_standard("frozen@sha256:../evil", cache_dir=cache_dir)

    def test_resolve_hermetic_standard_resolves_valid_hash(self):
        """Should resolve a valid frozen@sha256 reference to a cached file."""
        import hashlib
        import tempfile

        from octave_mcp.core.hydrator import resolve_hermetic_standard

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)

            content = b"===STANDARD===\nKEY::value\n===END===\n"
            digest = hashlib.sha256(content).hexdigest()
            expected_hash = f"sha256:{digest}"

            cached_path = cache_dir / f"{digest[:16]}.oct.md"
            cached_path.write_bytes(content)

            resolved = resolve_hermetic_standard(f"frozen@{expected_hash}", cache_dir=cache_dir)
            assert resolved == cached_path


class TestRegistryResolution:
    """Tests for resolving vocabulary namespaces via registry."""

    def test_resolve_namespace_to_path(self):
        """Should resolve @namespace/name to file path."""
        from octave_mcp.core.hydrator import VocabularyRegistry

        # Try new location first, fall back to old location
        registry_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "octave_mcp"
            / "resources"
            / "specs"
            / "vocabularies"
            / "registry.oct.md"
        )
        if not registry_path.exists():
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

        # Try new location first, fall back to old location
        registry_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "octave_mcp"
            / "resources"
            / "specs"
            / "vocabularies"
            / "registry.oct.md"
        )
        if not registry_path.exists():
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
        """Should reject path traversal patterns like ../../../sensitive.

        Issue #48 CE Review FIX: validate_source_uri now allows ".." patterns
        but rejects them if the resolved path is OUTSIDE the base directory.
        The error message says "outside allowed directory" not "traversal".
        """
        from octave_mcp.core.hydrator import SourceUriSecurityError, validate_source_uri

        with pytest.raises(SourceUriSecurityError, match="outside"):
            validate_source_uri(
                "../../../etc/passwd",
                base_path=Path("/tmp/registry"),
            )

    def test_validate_source_uri_rejects_hidden_traversal(self):
        """Should reject hidden traversal patterns like vocab/../../etc/passwd.

        Issue #48 CE Review FIX: validate_source_uri now allows ".." patterns
        but rejects them if the resolved path is OUTSIDE the base directory.
        """
        from octave_mcp.core.hydrator import SourceUriSecurityError, validate_source_uri

        with pytest.raises(SourceUriSecurityError, match="outside"):
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
        """Should return ERROR StalenessResult for malicious SOURCE_URI.

        Issue #48 CE Review FIX: _check_single_snapshot now allows ".." patterns
        for cross-directory layouts. The path traversal is rejected because:
        1. The file doesn't exist, OR
        2. A security check catches the escape (for strict validation)

        Either way, the staleness check returns ERROR status.
        """
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
        # Error can be "file not found" (file doesn't exist) or security-related
        error_lower = results[0].error.lower()
        assert any(
            keyword in error_lower for keyword in ["not found", "security", "outside"]
        ), f"Error should indicate file not found or security issue, got: {results[0].error}"

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


class TestCrossDirectoryLayout:
    """Tests for cross-directory vocabulary layouts.

    Issue #48 CE Review: hydrate() generates `../` in SOURCE_URI when vocab is
    in a different directory than the output file. The staleness check must
    accept these paths (via validate_source_uri resolution) while still
    rejecting actual path traversal attacks.

    Test case: vocab in `specs/`, output in `docs/`, verify --check works.
    """

    def test_cross_directory_hydration_and_staleness_check(self):
        """Should handle cross-directory layouts: vocab in specs/, output in docs/.

        This is the critical integration test for Issue #48 CE Review fix.
        The hydrate() function generates SOURCE_URI like "../specs/vocab.oct.md"
        when the output is in a different directory. The staleness check MUST
        accept this path (it's within the project) and verify the hash.
        """
        import tempfile
        from pathlib import Path

        from octave_mcp.core.emitter import emit
        from octave_mcp.core.hydrator import (
            HydrationPolicy,
            VocabularyRegistry,
            check_staleness,
            hydrate,
        )
        from octave_mcp.core.parser import parse

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            # Create cross-directory structure:
            # project/
            #   specs/vocabulary.oct.md  <-- vocab file
            #   docs/output.oct.md       <-- hydrated output
            specs_dir = base / "specs"
            docs_dir = base / "docs"
            specs_dir.mkdir()
            docs_dir.mkdir()

            # Create vocabulary in specs/
            vocab_path = specs_dir / "vocabulary.oct.md"
            vocab_path.write_text("""===VOCAB===
META:
  TYPE::"CAPSULE"
  VERSION::"1.0.0"

§1::TERMS
  ALPHA::"First term"
  BETA::"Second term"

===END===
""")

            # Create source document (will import the vocabulary)
            source_path = base / "source.oct.md"
            source_path.write_text("""===SOURCE===
META:
  TYPE::"SPEC"
  VERSION::"1.0.0"

§CONTEXT::IMPORT["@test/vocabulary"]

§1::CONTENT
  REF::"Uses ALPHA term"

===END===
""")

            # Create registry pointing to vocab in specs/
            registry = VocabularyRegistry.from_mappings({"@test/vocabulary": vocab_path})
            policy = HydrationPolicy()

            # Hydrate with output_path in docs/
            output_path = docs_dir / "output.oct.md"
            result = hydrate(source_path, registry, policy, output_path=output_path)

            # Emit to output file
            output_content = emit(result)
            output_path.write_text(output_content)

            # Verify SOURCE_URI contains relative path with ".."
            # (this is the path from docs/ to specs/)
            manifest = _find_manifest_section(result)
            source_uri = _get_field_value(manifest, "SOURCE_URI")
            assert source_uri is not None, "SOURCE_URI should be present in manifest"
            assert ".." in source_uri, f"SOURCE_URI should contain '..' for cross-directory: {source_uri}"

            # THE CRITICAL TEST: staleness check should work with the cross-directory path
            # This is where the old code FAILED - it rejected ALL ".." patterns
            # Issue #48 CE Security Fix: Pass allowed_root=base (project root) to allow
            # cross-directory access within the project
            hydrated_doc = parse(output_content)
            results = check_staleness(hydrated_doc, base_path=docs_dir, allowed_root=base)

            assert len(results) == 1, "Should have one staleness result"
            assert results[0].status == "FRESH", (
                f"Cross-directory staleness check should return FRESH, got {results[0].status}. "
                f"Error: {results[0].error}"
            )

    def test_cross_directory_rejects_escape_attempt(self):
        """Should reject path traversal that escapes the project directory.

        Even with the fix allowing `../` paths, we must still reject paths
        that resolve to non-existent files or security violations.
        """
        import tempfile
        from pathlib import Path

        from octave_mcp.core.hydrator import check_staleness
        from octave_mcp.core.parser import parse

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            project_dir = base / "project"
            project_dir.mkdir()

            # Malicious document trying to escape project directory
            # Even though ../../../etc/passwd uses "..", it should fail
            # because the path either doesn't exist or is blocked by security
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
            results = check_staleness(doc, base_path=project_dir)

            assert len(results) == 1
            assert results[0].status == "ERROR", "Should reject path that escapes base directory"
            # Error should be either:
            # - "file not found" (path resolves but doesn't exist)
            # - "security" (blocked by security check)
            # Both are acceptable - the key is that it fails with ERROR
            error_lower = results[0].error.lower()
            assert any(
                keyword in error_lower for keyword in ["not found", "security", "outside"]
            ), f"Error should mention 'not found', 'security', or 'outside', got: {results[0].error}"

    def test_cross_directory_within_project_is_allowed(self):
        """Should allow `../sibling/` paths that stay within base directory.

        This tests the valid use case: different directories within the same project.
        """
        import tempfile
        from pathlib import Path

        from octave_mcp.core.hydrator import check_staleness, compute_vocabulary_hash
        from octave_mcp.core.parser import parse

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            # Create sibling directories within the project
            # project/
            #   specs/vocab.oct.md
            #   docs/  <-- base_path for staleness check
            specs_dir = base / "specs"
            docs_dir = base / "docs"
            specs_dir.mkdir()
            docs_dir.mkdir()

            # Create vocab file
            vocab_path = specs_dir / "vocab.oct.md"
            vocab_path.write_text("test vocabulary content")
            vocab_hash = compute_vocabulary_hash(vocab_path)

            # Document with SOURCE_URI pointing to sibling directory
            # From docs/, ../specs/vocab.oct.md resolves to specs/vocab.oct.md
            # which is a valid cross-directory reference
            content = f"""===HYDRATED_DOC===
META:
  TYPE::"SPEC"
  VERSION::"1.0.0"

§CONTEXT::SNAPSHOT["@test/vocabulary"]
  ALPHA::"First letter"

§SNAPSHOT::MANIFEST
  SOURCE_URI::"../specs/vocab.oct.md"
  SOURCE_HASH::"{vocab_hash}"
  HYDRATION_TIME::"2024-01-01T00:00:00Z"

===END===
"""

            doc = parse(content)
            # Use docs_dir as base_path (simulating running staleness check from docs/)
            # Use base as allowed_root (the project root that contains both specs/ and docs/)
            # Issue #48 CE Security Fix: allowed_root must encompass all cross-directory paths
            results = check_staleness(doc, base_path=docs_dir, allowed_root=base)

            assert len(results) == 1
            assert results[0].status == "FRESH", (
                f"Should allow sibling directory access within project. " f"Error: {results[0].error}"
            )


class TestPostResolutionContainment:
    """Tests for post-resolution path containment enforcement.

    Issue #48 CE Security Fix: After resolving a path (with ..), verify
    the resolved path stays within the allowed_root directory.

    This prevents path traversal attacks where a crafted SOURCE_URI like
    "../../../../../../../etc/passwd" could escape the project directory.
    """

    def test_escape_attempt_via_traversal_blocked(self):
        """Should return ERROR for path traversal that escapes allowed_root.

        CRITICAL REGRESSION TEST: This is the exact vulnerability CE identified.
        A crafted SOURCE_URI with enough "../" components could escape the project
        and access sensitive files like /etc/passwd.

        The fix: After resolving the path, check that it's still within allowed_root.
        """
        import tempfile
        from pathlib import Path

        from octave_mcp.core.hydrator import check_staleness
        from octave_mcp.core.parser import parse

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            # Create project structure
            project_dir = base / "project"
            docs_dir = project_dir / "docs"
            docs_dir.mkdir(parents=True)

            # Dynamically compute how many "../" are needed to escape to /etc/passwd
            # This makes the test work regardless of directory depth
            # For example, if project is at /tmp/xyz/project/docs, we need enough
            # "../" to get to / and then navigate to etc/passwd
            docs_resolved = docs_dir.resolve()
            depth_to_root = len(docs_resolved.parts) - 1  # -1 for root itself
            traversal_path = "../" * depth_to_root + "etc/passwd"

            # Create malicious document with escape attempt
            content = f"""===HYDRATED_DOC===
META:
  TYPE::"SPEC"
  VERSION::"1.0.0"

§CONTEXT::SNAPSHOT["@test/vocabulary"]
  ALPHA::"First letter"

§SNAPSHOT::MANIFEST
  SOURCE_URI::"{traversal_path}"
  SOURCE_HASH::"sha256:abc123"
  HYDRATION_TIME::"2024-01-01T00:00:00Z"

===END===
"""

            doc = parse(content)

            # allowed_root is the PROJECT directory (parent of docs)
            # The resolved path (../../../.../etc/passwd) escapes project_dir
            # So it MUST be rejected even though the file might exist
            results = check_staleness(doc, base_path=docs_dir, allowed_root=project_dir)

            assert len(results) == 1
            assert results[0].status == "ERROR", (
                f"Escape attempt should return ERROR, got {results[0].status}. " f"Error: {results[0].error}"
            )
            # Error should mention security violation
            error_lower = results[0].error.lower()
            assert (
                "security" in error_lower or "escapes" in error_lower or "outside" in error_lower
            ), f"Error should mention security violation, got: {results[0].error}"

    def test_cross_directory_within_allowed_root_allowed(self):
        """Should allow cross-directory paths that stay within allowed_root.

        This ensures the fix doesn't break legitimate cross-directory layouts
        where vocab is in specs/ and output is in docs/, both within project/.
        """
        import tempfile
        from pathlib import Path

        from octave_mcp.core.hydrator import check_staleness, compute_vocabulary_hash
        from octave_mcp.core.parser import parse

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            # Project structure with allowed cross-directory layout:
            # project/
            #   specs/vocab.oct.md
            #   docs/  <-- base_path for staleness check
            project_dir = base / "project"
            specs_dir = project_dir / "specs"
            docs_dir = project_dir / "docs"
            specs_dir.mkdir(parents=True)
            docs_dir.mkdir(parents=True)

            # Create vocab file
            vocab_path = specs_dir / "vocab.oct.md"
            vocab_path.write_text("test vocabulary content")
            vocab_hash = compute_vocabulary_hash(vocab_path)

            # Cross-directory path: from docs/, go up to project/, then into specs/
            content = f"""===HYDRATED_DOC===
META:
  TYPE::"SPEC"
  VERSION::"1.0.0"

§CONTEXT::SNAPSHOT["@test/vocabulary"]
  ALPHA::"First letter"

§SNAPSHOT::MANIFEST
  SOURCE_URI::"../specs/vocab.oct.md"
  SOURCE_HASH::"{vocab_hash}"
  HYDRATION_TIME::"2024-01-01T00:00:00Z"

===END===
"""

            doc = parse(content)

            # base_path is docs/, allowed_root is project/
            # The resolved path (project/specs/vocab.oct.md) is within project/
            # So it should be allowed
            results = check_staleness(doc, base_path=docs_dir, allowed_root=project_dir)

            assert len(results) == 1
            assert results[0].status == "FRESH", (
                f"Cross-directory within allowed_root should work. " f"Error: {results[0].error}"
            )

    def test_allowed_root_defaults_to_base_path(self):
        """When allowed_root is not specified, should use base_path as default.

        This maintains backwards compatibility and ensures existing behavior
        where base_path was the only containment check still works.
        """
        import tempfile
        from pathlib import Path

        from octave_mcp.core.hydrator import check_staleness, compute_vocabulary_hash
        from octave_mcp.core.parser import parse

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            # Create vocab in the same directory (no cross-directory)
            vocab_path = base / "vocab.oct.md"
            vocab_path.write_text("test vocabulary content")
            vocab_hash = compute_vocabulary_hash(vocab_path)

            content = f"""===HYDRATED_DOC===
META:
  TYPE::"SPEC"
  VERSION::"1.0.0"

§CONTEXT::SNAPSHOT["@test/vocabulary"]
  ALPHA::"First letter"

§SNAPSHOT::MANIFEST
  SOURCE_URI::"vocab.oct.md"
  SOURCE_HASH::"{vocab_hash}"
  HYDRATION_TIME::"2024-01-01T00:00:00Z"

===END===
"""

            doc = parse(content)

            # Don't pass allowed_root - it should default to base_path
            results = check_staleness(doc, base_path=base)

            assert len(results) == 1
            assert results[0].status == "FRESH", f"Default allowed_root should work. Error: {results[0].error}"

    def test_escape_attempt_blocked_even_when_file_exists(self):
        """Should block escape even if the target file exists.

        This is critical: the old code would allow access if the file existed.
        The new code must block access based on containment, not file existence.
        """
        import tempfile
        from pathlib import Path

        from octave_mcp.core.hydrator import check_staleness
        from octave_mcp.core.parser import parse

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            # Create project structure
            project_dir = base / "project"
            docs_dir = project_dir / "docs"
            docs_dir.mkdir(parents=True)

            # Create a file OUTSIDE the project that we try to access
            outside_file = base / "sensitive.txt"
            outside_file.write_text("sensitive data")

            # Create malicious document trying to escape to parent directory
            # ../sensitive.txt from project/docs/ goes to project/../sensitive.txt = base/sensitive.txt
            # which is OUTSIDE project_dir
            content = """===HYDRATED_DOC===
META:
  TYPE::"SPEC"
  VERSION::"1.0.0"

§CONTEXT::SNAPSHOT["@test/vocabulary"]
  ALPHA::"First letter"

§SNAPSHOT::MANIFEST
  SOURCE_URI::"../../sensitive.txt"
  SOURCE_HASH::"sha256:abc123"
  HYDRATION_TIME::"2024-01-01T00:00:00Z"

===END===
"""

            doc = parse(content)

            # allowed_root is project_dir
            # The resolved path (base/sensitive.txt) escapes project_dir
            # MUST be rejected even though the file exists
            results = check_staleness(doc, base_path=docs_dir, allowed_root=project_dir)

            assert len(results) == 1
            assert results[0].status == "ERROR", (
                f"Should block escape even when file exists. Got: {results[0].status}. " f"Error: {results[0].error}"
            )


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


class TestCycleDetection:
    """Tests for cycle detection in recursive imports.

    TDD RED phase: Issue #48 Task 2.12 - Cycle Detection for Recursive Imports.

    Cycle detection prevents infinite loops when:
    - A imports B, B imports A (simple cycle)
    - A imports A (self-import)
    - A -> B -> C -> A (transitive cycle, if depth > 1 supported)

    The CycleDetectionError should provide:
    - cycle_path: list of paths showing the import chain
    - Clear error message describing the cycle
    """

    def test_cycle_detection_error_exists(self):
        """CycleDetectionError should be a subclass of VocabularyError."""
        from octave_mcp.core.hydrator import CycleDetectionError, VocabularyError

        assert issubclass(CycleDetectionError, VocabularyError)

    def test_cycle_detection_error_has_cycle_path(self):
        """CycleDetectionError should have cycle_path attribute."""
        from octave_mcp.core.hydrator import CycleDetectionError

        error = CycleDetectionError(cycle_path=["A.oct.md", "B.oct.md", "A.oct.md"])

        assert hasattr(error, "cycle_path")
        assert error.cycle_path == ["A.oct.md", "B.oct.md", "A.oct.md"]

    def test_cycle_detection_error_message(self):
        """CycleDetectionError should have descriptive message."""
        from octave_mcp.core.hydrator import CycleDetectionError

        error = CycleDetectionError(cycle_path=["A.oct.md", "B.oct.md", "A.oct.md"])

        message = str(error)
        assert "circular" in message.lower() or "cycle" in message.lower()
        assert "A.oct.md" in message

    def test_self_import_detected(self):
        """Should detect when a document imports itself."""
        import tempfile
        from pathlib import Path

        from octave_mcp.core.hydrator import (
            CycleDetectionError,
            HydrationPolicy,
            VocabularyRegistry,
            hydrate,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            # Create a document that imports itself
            self_importing = base / "self_import.oct.md"
            self_importing.write_text("""===SELF_IMPORT===
META:
  TYPE::"SPEC"
  VERSION::"1.0.0"

§CONTEXT::IMPORT["@test/self"]

§1::CONTENT
  KEY::"value"

===END===
""")

            # Registry that maps the namespace back to the same file
            registry = VocabularyRegistry.from_mappings({"@test/self": self_importing})
            policy = HydrationPolicy()

            with pytest.raises(CycleDetectionError) as exc_info:
                hydrate(self_importing, registry, policy)

            # Should detect self-import cycle
            assert len(exc_info.value.cycle_path) >= 1
            assert "self_import.oct.md" in str(exc_info.value.cycle_path[-1])

    def test_simple_cycle_detected(self):
        """Should detect A -> B -> A cycle."""
        import tempfile
        from pathlib import Path

        from octave_mcp.core.hydrator import (
            CycleDetectionError,
            HydrationPolicy,
            VocabularyRegistry,
            hydrate,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            # Create two documents that import each other
            # A imports B (via @test/b namespace)
            doc_a = base / "doc_a.oct.md"
            doc_a.write_text("""===DOC_A===
META:
  TYPE::"SPEC"
  VERSION::"1.0.0"

§CONTEXT::IMPORT["@test/b"]

§1::CONTENT
  KEY::"value"

===END===
""")

            # B is a CAPSULE that conceptually would import A
            # For MVP with max_depth=1, we simulate the cycle by having
            # the import target resolve back to the source
            # NOTE: This test validates the infrastructure for cycle detection
            # The actual A->B->A would require depth>1 which is future work
            doc_b = base / "doc_b.oct.md"
            doc_b.write_text("""===DOC_B===
META:
  TYPE::"CAPSULE"
  VERSION::"1.0.0"

§1::TERMS
  TERM::"definition"

===END===
""")

            # For this test, we simulate by making @test/b point back to doc_a
            # This creates the simplest possible cycle: A -> A
            registry = VocabularyRegistry.from_mappings({"@test/b": doc_a})
            policy = HydrationPolicy()

            with pytest.raises(CycleDetectionError) as exc_info:
                hydrate(doc_a, registry, policy)

            # Cycle should be detected
            assert len(exc_info.value.cycle_path) >= 1

    def test_no_cycle_with_normal_import(self):
        """Should NOT raise CycleDetectionError for normal imports."""
        from octave_mcp.core.hydrator import HydrationPolicy, hydrate

        source_path = FIXTURES_DIR / "source.oct.md"
        registry = _create_test_registry()
        policy = HydrationPolicy()

        # Should not raise - normal import has no cycle
        result = hydrate(source_path, registry, policy)
        assert result is not None

    def test_cycle_detection_before_parsing(self):
        """Cycle should be detected before attempting to parse as CAPSULE.

        If A imports A (self-import), we should detect the cycle BEFORE
        trying to parse A as a CAPSULE (which would fail since it's a SPEC).
        This is fail-fast behavior.
        """
        import tempfile
        from pathlib import Path

        from octave_mcp.core.hydrator import (
            CycleDetectionError,
            HydrationPolicy,
            VocabularyRegistry,
            hydrate,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            # Create a SPEC document that tries to import itself
            # (SPEC is not a CAPSULE, so parsing as vocab would fail)
            doc = base / "spec.oct.md"
            doc.write_text("""===SPEC===
META:
  TYPE::"SPEC"
  VERSION::"1.0.0"

§CONTEXT::IMPORT["@test/myself"]

§1::CONTENT
  KEY::"value"

===END===
""")

            registry = VocabularyRegistry.from_mappings({"@test/myself": doc})
            policy = HydrationPolicy()

            # Should raise CycleDetectionError, NOT VocabularyError("not a CAPSULE")
            with pytest.raises(CycleDetectionError):
                hydrate(doc, registry, policy)


class TestPruneStrategyOptions:
    """Tests for prune_strategy policy options.

    TDD RED phase: Issue #48 Task 2.11 - PRUNE_MANIFEST Policy Options.

    The prune_strategy field controls how pruned (unused) terms are manifested:
    - "list" (default): List all pruned term names in TERMS
    - "hash": Create HASH field with SHA256 of sorted term names
    - "count": Create COUNT field with integer count of pruned terms
    - "elide": Don't include PRUNED section at all
    """

    def test_hydration_policy_accepts_hash_strategy(self):
        """HydrationPolicy should accept prune_strategy='hash'."""
        from octave_mcp.core.hydrator import HydrationPolicy

        policy = HydrationPolicy(prune_strategy="hash")

        assert policy.prune_strategy == "hash"

    def test_hydration_policy_accepts_count_strategy(self):
        """HydrationPolicy should accept prune_strategy='count'."""
        from octave_mcp.core.hydrator import HydrationPolicy

        policy = HydrationPolicy(prune_strategy="count")

        assert policy.prune_strategy == "count"

    def test_hydration_policy_accepts_elide_strategy(self):
        """HydrationPolicy should accept prune_strategy='elide'."""
        from octave_mcp.core.hydrator import HydrationPolicy

        policy = HydrationPolicy(prune_strategy="elide")

        assert policy.prune_strategy == "elide"

    def test_prune_strategy_list_produces_terms_list(self):
        """prune_strategy='list' should list pruned term names in TERMS field.

        This is the current default behavior - verify it still works.
        """
        from octave_mcp.core.hydrator import HydrationPolicy, hydrate

        source_path = FIXTURES_DIR / "source.oct.md"
        registry = _create_test_registry()
        policy = HydrationPolicy(prune_strategy="list")

        result = hydrate(source_path, registry, policy)

        pruned = _find_pruned_section(result)
        assert pruned is not None

        terms = _get_field_value(pruned, "TERMS")
        assert terms is not None
        # GAMMA and EPSILON should be in PRUNED as a list
        assert "GAMMA" in str(terms)
        assert "EPSILON" in str(terms)

    def test_prune_strategy_hash_produces_hash_field(self):
        """prune_strategy='hash' should create HASH field with SHA256.

        Expected format: HASH::"sha256:HEXDIGEST"
        The hash is computed from sorted term names, not their definitions.
        """
        from octave_mcp.core.hydrator import HydrationPolicy, hydrate

        source_path = FIXTURES_DIR / "source.oct.md"
        registry = _create_test_registry()
        policy = HydrationPolicy(prune_strategy="hash")

        result = hydrate(source_path, registry, policy)

        pruned = _find_pruned_section(result)
        assert pruned is not None

        # Should NOT have TERMS field
        terms = _get_field_value(pruned, "TERMS")
        assert terms is None, "hash strategy should not produce TERMS field"

        # Should have HASH field
        hash_value = _get_field_value(pruned, "HASH")
        assert hash_value is not None, "hash strategy should produce HASH field"
        assert hash_value.startswith("sha256:"), f"HASH should start with 'sha256:', got: {hash_value}"
        # SHA-256 produces 64 hex characters
        hex_part = hash_value.split(":")[1]
        assert len(hex_part) == 64, f"SHA256 hex should be 64 chars, got: {len(hex_part)}"

    def test_prune_strategy_hash_is_deterministic(self):
        """prune_strategy='hash' should produce same hash for same pruned terms.

        The hash should be computed from sorted term names to ensure determinism.
        """
        from octave_mcp.core.hydrator import HydrationPolicy, hydrate

        source_path = FIXTURES_DIR / "source.oct.md"
        registry = _create_test_registry()
        policy = HydrationPolicy(prune_strategy="hash")

        # Hydrate twice
        result1 = hydrate(source_path, registry, policy)
        result2 = hydrate(source_path, registry, policy)

        pruned1 = _find_pruned_section(result1)
        pruned2 = _find_pruned_section(result2)

        hash1 = _get_field_value(pruned1, "HASH")
        hash2 = _get_field_value(pruned2, "HASH")

        assert hash1 == hash2, "Hash should be deterministic for same pruned terms"

    def test_prune_strategy_count_produces_count_field(self):
        """prune_strategy='count' should create COUNT field with integer.

        Expected format: COUNT::N where N is the number of pruned terms.
        """
        from octave_mcp.core.hydrator import HydrationPolicy, hydrate

        source_path = FIXTURES_DIR / "source.oct.md"
        registry = _create_test_registry()
        policy = HydrationPolicy(prune_strategy="count")

        result = hydrate(source_path, registry, policy)

        pruned = _find_pruned_section(result)
        assert pruned is not None

        # Should NOT have TERMS field
        terms = _get_field_value(pruned, "TERMS")
        assert terms is None, "count strategy should not produce TERMS field"

        # Should have COUNT field
        count_value = _get_field_value(pruned, "COUNT")
        assert count_value is not None, "count strategy should produce COUNT field"
        assert isinstance(count_value, int), f"COUNT should be int, got: {type(count_value)}"
        # GAMMA and EPSILON are pruned in source.oct.md
        assert count_value == 2, f"Expected 2 pruned terms, got: {count_value}"

    def test_prune_strategy_elide_produces_no_pruned_section(self):
        """prune_strategy='elide' should NOT include PRUNED section.

        The hydrated document should have SNAPSHOT and MANIFEST but no PRUNED.
        """
        from octave_mcp.core.hydrator import HydrationPolicy, hydrate

        source_path = FIXTURES_DIR / "source.oct.md"
        registry = _create_test_registry()
        policy = HydrationPolicy(prune_strategy="elide")

        result = hydrate(source_path, registry, policy)

        # Should have SNAPSHOT section
        snapshot = _find_snapshot_section(result)
        assert snapshot is not None, "SNAPSHOT section should exist"

        # Should have MANIFEST section
        manifest = _find_manifest_section(result)
        assert manifest is not None, "MANIFEST section should exist"

        # Should NOT have PRUNED section
        pruned = _find_pruned_section(result)
        assert pruned is None, "elide strategy should not produce PRUNED section"

    def test_prune_strategy_elide_with_empty_pruned_terms(self):
        """prune_strategy='elide' should work when all terms are used.

        Even when there are no pruned terms, 'elide' should produce
        consistent behavior (no PRUNED section).
        """
        from octave_mcp.core.hydrator import HydrationPolicy, hydrate

        # source_all_terms.oct.md uses all vocabulary terms
        source_path = FIXTURES_DIR / "source_all_terms.oct.md"
        registry = _create_test_registry()
        policy = HydrationPolicy(prune_strategy="elide")

        result = hydrate(source_path, registry, policy)

        # Should NOT have PRUNED section (elided)
        pruned = _find_pruned_section(result)
        assert pruned is None, "elide strategy should not produce PRUNED section even when empty"

    def test_prune_strategy_count_zero_when_all_terms_used(self):
        """prune_strategy='count' should produce COUNT::0 when all terms used."""
        from octave_mcp.core.hydrator import HydrationPolicy, hydrate

        source_path = FIXTURES_DIR / "source_all_terms.oct.md"
        registry = _create_test_registry()
        policy = HydrationPolicy(prune_strategy="count")

        result = hydrate(source_path, registry, policy)

        pruned = _find_pruned_section(result)
        assert pruned is not None

        count_value = _get_field_value(pruned, "COUNT")
        assert count_value == 0, f"Expected COUNT::0 when all terms used, got: {count_value}"

    def test_manifest_records_prune_strategy(self):
        """MANIFEST HYDRATION_POLICY should record the prune_strategy used.

        The PRUNE field in HYDRATION_POLICY should show the strategy used.
        """
        from octave_mcp.core.hydrator import HydrationPolicy, hydrate

        source_path = FIXTURES_DIR / "source.oct.md"
        registry = _create_test_registry()

        for strategy in ["list", "hash", "count", "elide"]:
            policy = HydrationPolicy(prune_strategy=strategy)  # type: ignore
            result = hydrate(source_path, registry, policy)

            manifest = _find_manifest_section(result)
            policy_block = _find_child_block(manifest, "HYDRATION_POLICY")
            prune_value = _get_field_value(policy_block, "PRUNE")

            assert prune_value == strategy, f"PRUNE field should be '{strategy}', got: {prune_value}"

    def test_invalid_prune_strategy_raises_vocabulary_error(self):
        """Invalid prune_strategy must raise VocabularyError, not silent fallback.

        Issue #48 CE Review H1: Production risk - misconfiguration should fail loudly.
        Previously, any invalid strategy silently became COUNT mode.
        """
        from octave_mcp.core.hydrator import VocabularyError, _create_pruned_section

        with pytest.raises(VocabularyError, match="Invalid prune_strategy"):
            _create_pruned_section({"term1", "term2"}, "bogus")  # type: ignore

    def test_invalid_prune_strategy_shows_valid_options(self):
        """Error message should list valid options for discoverability."""
        from octave_mcp.core.hydrator import VocabularyError, _create_pruned_section

        with pytest.raises(VocabularyError, match=r"list.*hash.*count.*elide"):
            _create_pruned_section({"term1"}, "invalid_strategy")  # type: ignore
