"""Tests for OCTAVE grammar sentinel (Issue #48 Phase 2).

The grammar sentinel is a version declaration at document start:
    OCTAVE::5.1.0
    ===MY_DOCUMENT===
    ...

This enables:
- Forward compatibility detection
- Migration tool routing
- Schema version binding
"""

from octave_mcp.core.ast_nodes import Document
from octave_mcp.core.emitter import emit
from octave_mcp.core.parser import parse


class TestGrammarSentinelParsing:
    """Test parsing of grammar sentinel at document start."""

    def test_parse_document_with_grammar_sentinel(self):
        """Parse document with OCTAVE grammar sentinel."""
        content = """\
OCTAVE::5.1.0
===MY_DOCUMENT===
META:
  TYPE::"TEST"
===END===
"""
        doc = parse(content)

        assert doc.grammar_version == "5.1.0"
        assert doc.name == "MY_DOCUMENT"
        assert doc.meta.get("TYPE") == "TEST"

    def test_parse_document_without_sentinel(self):
        """Parse document without sentinel - grammar_version should be None."""
        content = """\
===MY_DOCUMENT===
META:
  TYPE::"TEST"
===END===
"""
        doc = parse(content)

        assert doc.grammar_version is None
        assert doc.name == "MY_DOCUMENT"

    def test_parse_sentinel_with_section_marker_syntax(self):
        """Parse sentinel using section marker syntax."""
        content = """\
OCTAVE::5.1.0
===DOCUMENT===
KEY::value
===END===
"""
        doc = parse(content)

        assert doc.grammar_version == "5.1.0"
        assert doc.name == "DOCUMENT"

    def test_parse_sentinel_major_version_only(self):
        """Parse sentinel with major version only (5)."""
        content = """\
OCTAVE::5
===DOCUMENT===
KEY::value
===END===
"""
        doc = parse(content)

        assert doc.grammar_version == "5"

    def test_parse_sentinel_major_minor_version(self):
        """Parse sentinel with major.minor version (5.1)."""
        content = """\
OCTAVE::5.1
===DOCUMENT===
KEY::value
===END===
"""
        doc = parse(content)

        assert doc.grammar_version == "5.1"

    def test_parse_sentinel_semver_full(self):
        """Parse sentinel with full semver (5.1.0)."""
        content = """\
OCTAVE::5.1.0
===DOCUMENT===
KEY::value
===END===
"""
        doc = parse(content)

        assert doc.grammar_version == "5.1.0"

    def test_parse_sentinel_semver_with_prerelease(self):
        """Parse sentinel with prerelease tag (5.1.0-beta.1)."""
        content = """\
OCTAVE::5.1.0-beta.1
===DOCUMENT===
KEY::value
===END===
"""
        doc = parse(content)

        assert doc.grammar_version == "5.1.0-beta.1"


class TestGrammarSentinelEmission:
    """Test emission of grammar sentinel."""

    def test_emit_document_with_grammar_version(self):
        """Emit document with grammar_version includes sentinel."""
        doc = Document(name="TEST_DOC", grammar_version="5.1.0", meta={"TYPE": "TEST"})

        output = emit(doc)

        # Sentinel should appear BEFORE envelope
        assert output.startswith("OCTAVE::5.1.0\n===TEST_DOC===")

    def test_emit_document_without_grammar_version(self):
        """Emit document without grammar_version omits sentinel."""
        doc = Document(name="TEST_DOC", meta={"TYPE": "TEST"})

        output = emit(doc)

        # Should start directly with envelope
        assert output.startswith("===TEST_DOC===")
        assert "OCTAVE::" not in output


class TestGrammarSentinelRoundTrip:
    """Test round-trip preservation of grammar sentinel."""

    def test_roundtrip_with_sentinel(self):
        """Parse -> emit -> parse produces identical grammar_version."""
        original = """\
OCTAVE::5.1.0
===MY_DOC===
META:
  TYPE::"SPEC"
KEY::value
===END===
"""
        # Parse original
        doc1 = parse(original)
        assert doc1.grammar_version == "5.1.0"

        # Emit
        emitted = emit(doc1)

        # Parse again
        doc2 = parse(emitted)

        # Verify round-trip
        assert doc2.grammar_version == doc1.grammar_version
        assert doc2.name == doc1.name

    def test_roundtrip_without_sentinel(self):
        """Parse -> emit -> parse preserves None grammar_version."""
        original = """\
===MY_DOC===
META:
  TYPE::"SPEC"
===END===
"""
        doc1 = parse(original)
        assert doc1.grammar_version is None

        emitted = emit(doc1)
        doc2 = parse(emitted)

        assert doc2.grammar_version is None


class TestGrammarSentinelEdgeCases:
    """Edge cases and error handling for grammar sentinel."""

    def test_sentinel_with_whitespace_before_envelope(self):
        """Whitespace between sentinel and envelope is allowed."""
        content = """\
OCTAVE::5.1.0

===DOCUMENT===
KEY::value
===END===
"""
        doc = parse(content)

        assert doc.grammar_version == "5.1.0"
        assert doc.name == "DOCUMENT"

    def test_sentinel_must_be_first_non_blank(self):
        """Sentinel must be the first non-blank content."""
        content = """\
OCTAVE::5.1.0
===MY_DOC===
META:
  TYPE::"TEST"
===END===
"""
        doc = parse(content)

        assert doc.grammar_version == "5.1.0"

    def test_octave_assignment_in_body_not_sentinel(self):
        """OCTAVE:: in body should NOT be treated as sentinel."""
        content = """\
===MY_DOC===
META:
  TYPE::"TEST"
OCTAVE::value
===END===
"""
        doc = parse(content)

        # No sentinel at start - grammar_version should be None
        assert doc.grammar_version is None
        # The OCTAVE::value in body should be a regular assignment
        # (we'll verify the assignment is preserved)
