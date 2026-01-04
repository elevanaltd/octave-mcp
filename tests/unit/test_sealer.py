"""Unit tests for SEAL cryptographic integrity layer.

TDD RED phase: These tests define the contract for sealer.py.
Tests are written BEFORE implementation per build-execution skill.

Issue #48 Phase 2 Batch 2: SEAL Cryptographic Integrity Layer
"""

import hashlib
from pathlib import Path

# Test fixtures path
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "seal"


class TestComputeSeal:
    """Tests for compute_seal function."""

    def test_compute_seal_produces_sha256(self):
        """Seal should contain SHA256 hash."""
        from octave_mcp.core.sealer import compute_seal

        content = "===DOC===\nMETA:\n  TYPE::TEST\n===END==="
        seal = compute_seal(content, None)

        assert seal["ALGORITHM"] == "SHA256"
        # Hash should be 64 hex characters
        hash_value = seal["HASH"].strip('"')
        assert len(hash_value) == 64
        assert all(c in "0123456789abcdef" for c in hash_value)

    def test_compute_seal_includes_line_count(self):
        """Seal SCOPE should specify correct line range."""
        from octave_mcp.core.sealer import compute_seal

        content = "line1\nline2\nline3"
        seal = compute_seal(content, None)

        # SCOPE should be LINES[1,N] where N is line count
        assert seal["SCOPE"] == "LINES[1,3]"

    def test_compute_seal_includes_grammar_version(self):
        """Seal should include GRAMMAR when provided."""
        from octave_mcp.core.sealer import compute_seal

        content = "===DOC===\n===END==="
        seal = compute_seal(content, "5.1.0")

        assert seal["GRAMMAR"] == "5.1.0"

    def test_compute_seal_omits_grammar_when_none(self):
        """Seal should omit GRAMMAR when not provided."""
        from octave_mcp.core.sealer import compute_seal

        content = "===DOC===\n===END==="
        seal = compute_seal(content, None)

        assert "GRAMMAR" not in seal

    def test_compute_seal_is_deterministic(self):
        """Same content should produce same hash."""
        from octave_mcp.core.sealer import compute_seal

        content = "===DOC===\nMETA:\n  TYPE::TEST\n===END==="

        seal1 = compute_seal(content, None)
        seal2 = compute_seal(content, None)

        assert seal1["HASH"] == seal2["HASH"]

    def test_compute_seal_different_content_different_hash(self):
        """Different content should produce different hash."""
        from octave_mcp.core.sealer import compute_seal

        content1 = "===DOC===\nMETA:\n  TYPE::TEST\n===END==="
        content2 = "===DOC===\nMETA:\n  TYPE::MODIFIED\n===END==="

        seal1 = compute_seal(content1, None)
        seal2 = compute_seal(content2, None)

        assert seal1["HASH"] != seal2["HASH"]

    def test_compute_seal_hash_matches_manual_computation(self):
        """Hash should match manual SHA256 computation."""
        from octave_mcp.core.sealer import compute_seal

        content = "test content"
        seal = compute_seal(content, None)

        expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        actual_hash = seal["HASH"].strip('"')

        assert actual_hash == expected_hash


class TestSealDocument:
    """Tests for seal_document function."""

    def test_seal_document_adds_seal_section(self):
        """seal_document should add SEAL section to document."""
        from octave_mcp.core.parser import parse
        from octave_mcp.core.sealer import seal_document

        content = """===DOC===
META:
  TYPE::"TEST"
===END==="""
        doc = parse(content)
        sealed_doc = seal_document(doc)

        # Check SEAL section was added
        seal_sections = [s for s in sealed_doc.sections if hasattr(s, "key") and s.key == "SEAL"]
        assert len(seal_sections) == 1

    def test_seal_document_seal_has_required_fields(self):
        """SEAL section should have SCOPE, ALGORITHM, HASH."""
        from octave_mcp.core.ast_nodes import Section
        from octave_mcp.core.parser import parse
        from octave_mcp.core.sealer import seal_document

        content = """===DOC===
META:
  TYPE::"TEST"
===END==="""
        doc = parse(content)
        sealed_doc = seal_document(doc)

        # Find SEAL section
        seal_section = None
        for s in sealed_doc.sections:
            if isinstance(s, Section) and s.key == "SEAL":
                seal_section = s
                break

        assert seal_section is not None

        # Check for required children
        child_keys = {c.key for c in seal_section.children if hasattr(c, "key")}
        assert "SCOPE" in child_keys
        assert "ALGORITHM" in child_keys
        assert "HASH" in child_keys

    def test_seal_document_preserves_grammar_version(self):
        """Sealed document should include GRAMMAR if source has grammar_version."""
        from octave_mcp.core.ast_nodes import Section
        from octave_mcp.core.parser import parse
        from octave_mcp.core.sealer import seal_document

        content = """OCTAVE::5.1.0
===DOC===
META:
  TYPE::"TEST"
===END==="""
        doc = parse(content)
        assert doc.grammar_version == "5.1.0"

        sealed_doc = seal_document(doc)

        # Find SEAL section
        seal_section = None
        for s in sealed_doc.sections:
            if isinstance(s, Section) and s.key == "SEAL":
                seal_section = s
                break

        # Check GRAMMAR field
        grammar_fields = [c for c in seal_section.children if hasattr(c, "key") and c.key == "GRAMMAR"]
        assert len(grammar_fields) == 1
        assert grammar_fields[0].value == "5.1.0"

    def test_seal_document_is_deterministic(self):
        """Same document should produce same sealed output."""
        from octave_mcp.core.emitter import emit
        from octave_mcp.core.parser import parse
        from octave_mcp.core.sealer import seal_document

        content = """===DOC===
META:
  TYPE::"TEST"
===END==="""
        doc1 = parse(content)
        doc2 = parse(content)

        sealed1 = seal_document(doc1)
        sealed2 = seal_document(doc2)

        output1 = emit(sealed1)
        output2 = emit(sealed2)

        assert output1 == output2


class TestVerifySeal:
    """Tests for verify_seal function."""

    def test_verify_seal_returns_valid_for_unmodified(self):
        """verify_seal should return VERIFIED for unmodified sealed document."""
        from octave_mcp.core.parser import parse
        from octave_mcp.core.sealer import SealStatus, seal_document, verify_seal

        content = """===DOC===
META:
  TYPE::"TEST"
===END==="""
        doc = parse(content)
        sealed_doc = seal_document(doc)

        result = verify_seal(sealed_doc)

        assert result.status == SealStatus.VERIFIED

    def test_verify_seal_returns_invalid_for_tampered(self):
        """verify_seal should return INVALID for tampered document."""
        from octave_mcp.core.ast_nodes import Assignment
        from octave_mcp.core.parser import parse
        from octave_mcp.core.sealer import SealStatus, seal_document, verify_seal

        content = """===DOC===
META:
  TYPE::"TEST"
===END==="""
        doc = parse(content)
        sealed_doc = seal_document(doc)

        # Tamper with document by adding a field
        sealed_doc.sections.insert(0, Assignment(key="TAMPERED", value="yes"))

        result = verify_seal(sealed_doc)

        assert result.status == SealStatus.INVALID

    def test_verify_seal_returns_no_seal_when_absent(self):
        """verify_seal should return NO_SEAL for unsealed document."""
        from octave_mcp.core.parser import parse
        from octave_mcp.core.sealer import SealStatus, verify_seal

        content = """===DOC===
META:
  TYPE::"TEST"
===END==="""
        doc = parse(content)

        result = verify_seal(doc)

        assert result.status == SealStatus.NO_SEAL

    def test_verify_seal_result_has_expected_hash(self):
        """Verification result should include expected hash for debugging."""
        from octave_mcp.core.parser import parse
        from octave_mcp.core.sealer import SealStatus, seal_document, verify_seal

        content = """===DOC===
META:
  TYPE::"TEST"
===END==="""
        doc = parse(content)
        sealed_doc = seal_document(doc)

        result = verify_seal(sealed_doc)

        # VERIFIED result should have matching hashes
        assert result.status == SealStatus.VERIFIED
        assert result.expected_hash == result.actual_hash


class TestExtractSeal:
    """Tests for extract_seal helper function."""

    def test_extract_seal_returns_none_when_absent(self):
        """extract_seal should return None if no SEAL section."""
        from octave_mcp.core.parser import parse
        from octave_mcp.core.sealer import extract_seal

        content = """===DOC===
META:
  TYPE::"TEST"
===END==="""
        doc = parse(content)

        seal = extract_seal(doc)

        assert seal is None

    def test_extract_seal_returns_dict_when_present(self):
        """extract_seal should return dict with seal data."""
        from octave_mcp.core.parser import parse
        from octave_mcp.core.sealer import extract_seal, seal_document

        content = """===DOC===
META:
  TYPE::"TEST"
===END==="""
        doc = parse(content)
        sealed_doc = seal_document(doc)

        seal = extract_seal(sealed_doc)

        assert seal is not None
        assert "SCOPE" in seal
        assert "ALGORITHM" in seal
        assert "HASH" in seal
