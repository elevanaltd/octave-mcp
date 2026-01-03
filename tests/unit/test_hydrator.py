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
        path = registry.resolve("@core/SNAPSHOT")
        assert path is not None
        assert "SNAPSHOT" in str(path)

    def test_resolve_test_namespace(self):
        """Should resolve test namespace to fixture path."""
        from octave_mcp.core.hydrator import VocabularyRegistry

        # Create a test registry that maps @test/vocabulary to fixtures
        registry = VocabularyRegistry.from_mappings({"@test/vocabulary": FIXTURES_DIR / "vocabulary.oct.md"})

        path = registry.resolve("@test/vocabulary")
        assert path == FIXTURES_DIR / "vocabulary.oct.md"

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
