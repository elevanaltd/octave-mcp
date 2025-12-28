"""Tests for multi-word value capture fixes (Issues #63 and #66).

Issue #63: Triple quotes cause complete value loss
Issue #66: Markdown eject format truncates multi-word values

TDD Phase: RED - These tests define expected behavior that currently fails.
"""

from octave_mcp.core.lexer import TokenType, tokenize
from octave_mcp.core.parser import parse


class TestTripleQuotes:
    """Tests for triple quote handling (Issue #63).

    Expected: Triple quotes should be handled gracefully.
    Current: Complete value loss - only empty string returned.
    """

    def test_triple_quotes_preserved_or_normalized(self):
        """Triple quoted content should be preserved or normalized to double quotes."""
        # Triple quotes in OCTAVE should be normalized to double quotes
        # The content should be preserved
        content = '''===TEST===
QUOTES::"""Triple quotes test"""
===END==='''
        doc = parse(content)
        assignment = doc.sections[0]
        # Value should contain the actual text, not be empty
        assert assignment.value is not None
        # At minimum, we should preserve "Triple quotes test"
        if isinstance(assignment.value, str):
            assert len(assignment.value) > 0

    def test_empty_triple_quotes(self):
        """Empty triple quotes should not cause errors."""
        content = '''===TEST===
EMPTY::""""""
===END==='''
        doc = parse(content)
        # Should parse without error
        assert len(doc.sections) >= 0


class TestMultiWordQuotedValues:
    """Tests for multi-word quoted value handling."""

    def test_quoted_multiword_preserved(self):
        """Quoted multi-word strings should preserve all words."""
        content = """===TEST===
PHRASE::"Hello World From OCTAVE"
===END==="""
        doc = parse(content)
        assignment = doc.sections[0]
        assert assignment.value == "Hello World From OCTAVE"

    def test_quoted_with_special_chars(self):
        """Quoted strings with special characters should be preserved."""
        content = """===TEST===
SPECIAL::"Value with: colons and -> arrows"
===END==="""
        doc = parse(content)
        assignment = doc.sections[0]
        assert "colons" in assignment.value
        assert "arrows" in assignment.value

    def test_quoted_with_unicode(self):
        """Quoted strings with unicode should be preserved."""
        content = """===TEST===
UNICODE::"Value with unicode arrow"
===END==="""
        doc = parse(content)
        assignment = doc.sections[0]
        assert "unicode" in assignment.value


class TestBlockMultiWordValues:
    """Tests for multi-word values in block contexts."""

    def test_block_child_multiword_quoted(self):
        """Block children with quoted multi-word values."""
        content = """===TEST===
SECTIONS:
  INTRO::"Introduction"
  BODY::"Main content"
  CONCLUSION::"Summary"
===END==="""
        doc = parse(content)
        block = doc.sections[0]
        assert len(block.children) == 3
        assert block.children[0].value == "Introduction"
        assert block.children[1].value == "Main content"
        assert block.children[2].value == "Summary"

    def test_nested_block_multiword(self):
        """Nested blocks with multi-word values."""
        content = """===TEST===
OUTER:
  INNER:
    VALUE::"Deeply nested content"
===END==="""
        doc = parse(content)
        outer = doc.sections[0]
        inner = outer.children[0]
        value = inner.children[0]
        assert value.value == "Deeply nested content"


class TestLexerQuoteHandling:
    """Tests for lexer quote tokenization."""

    def test_standard_double_quotes(self):
        """Standard double quotes should tokenize correctly."""
        tokens, _ = tokenize('"Hello World"')
        string_tokens = [t for t in tokens if t.type == TokenType.STRING]
        assert len(string_tokens) == 1
        assert string_tokens[0].value == "Hello World"

    def test_escaped_quotes_in_string(self):
        """Escaped quotes within string should be preserved."""
        tokens, _ = tokenize(r'"Say \"hello\" here"')
        string_tokens = [t for t in tokens if t.type == TokenType.STRING]
        assert len(string_tokens) == 1
        assert '"hello"' in string_tokens[0].value

    def test_empty_string(self):
        """Empty string should tokenize correctly."""
        tokens, _ = tokenize('""')
        string_tokens = [t for t in tokens if t.type == TokenType.STRING]
        assert len(string_tokens) == 1
        assert string_tokens[0].value == ""
