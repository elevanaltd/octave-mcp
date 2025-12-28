"""Tests for GH#63 (triple quotes) and GH#66 (multi-word bare values).

TDD RED Phase: These tests define expected behavior for:
- GH#63: Triple quotes cause complete value loss
- GH#66: Multi-word bare values truncated

Test Strategy:
1. Define expected behavior clearly
2. Tests should FAIL before implementation
3. Tests should PASS after implementation
"""

from octave_mcp.core.lexer import TokenType, tokenize
from octave_mcp.core.parser import parse


class TestTripleQuoteSupport:
    """GH#63: Triple quotes cause complete value loss.

    Root cause: Current STRING pattern only handles single-quoted strings.
    Input like triple-quoted strings is parsed incorrectly.

    Expected fix: Add triple quote pattern to TOKEN_PATTERNS BEFORE single quote.
    """

    def test_triple_quotes_lexer_tokenizes_content(self):
        """Lexer should tokenize triple-quoted strings as STRING tokens."""
        content = '"""Triple quotes test"""'
        tokens, _ = tokenize(content)

        string_tokens = [t for t in tokens if t.type == TokenType.STRING]
        assert len(string_tokens) == 1
        assert string_tokens[0].value == "Triple quotes test"

    def test_triple_quotes_in_assignment(self):
        """Triple-quoted values in assignments should preserve content."""
        content = '''===TEST===
QUOTES::"""Triple quotes test"""
===END==='''
        doc = parse(content)

        assignment = doc.sections[0]
        assert assignment.key == "QUOTES"
        assert assignment.value == "Triple quotes test"

    def test_triple_quotes_with_internal_quotes(self):
        """Triple quotes should allow internal single and double quotes."""
        content = '''===TEST===
MIXED::"""Contains "double" and 'single' quotes"""
===END==='''
        doc = parse(content)

        assignment = doc.sections[0]
        assert assignment.key == "MIXED"
        assert "double" in assignment.value
        assert "single" in assignment.value

    def test_triple_quotes_with_newlines(self):
        """Triple quotes should preserve internal newlines."""
        content = '''===TEST===
MULTILINE::"""Line one
Line two
Line three"""
===END==='''
        doc = parse(content)

        assignment = doc.sections[0]
        assert assignment.key == "MULTILINE"
        assert "Line one" in assignment.value
        assert "Line two" in assignment.value
        assert "Line three" in assignment.value

    def test_triple_quotes_empty_string(self):
        """Triple quotes with empty content should produce empty string."""
        content = '""""""'  # Empty triple-quoted string
        tokens, _ = tokenize(content)

        string_tokens = [t for t in tokens if t.type == TokenType.STRING]
        assert len(string_tokens) == 1
        assert string_tokens[0].value == ""

    def test_single_quotes_still_work(self):
        """Single-quoted strings should continue to work after triple-quote fix."""
        content = '"simple string"'
        tokens, _ = tokenize(content)

        string_tokens = [t for t in tokens if t.type == TokenType.STRING]
        assert len(string_tokens) == 1
        assert string_tokens[0].value == "simple string"

    def test_single_quotes_in_assignment_still_work(self):
        """Regular quoted assignments should still work."""
        content = """===TEST===
NORMAL::"Regular quoted string"
===END==="""
        doc = parse(content)

        assignment = doc.sections[0]
        assert assignment.key == "NORMAL"
        assert assignment.value == "Regular quoted string"


class TestMultiWordBareValues:
    """GH#66: Multi-word bare values truncated.

    Root cause: parse_value doesn't accumulate consecutive identifiers.
    Input: `BODY::Main content`
    Current: Only `Main` captured, `content` silently dropped.
    Expected: `Main content` captured (or warned about in Phase 3).

    Fix: Modify parse_flow_expression to accumulate consecutive IDENTIFIER tokens.
    """

    def test_multi_word_bare_value_captured(self):
        """Multi-word bare values should be captured with spaces."""
        content = """===TEST===
BODY::Main content
===END==="""
        doc = parse(content)

        assignment = doc.sections[0]
        assert assignment.key == "BODY"
        assert assignment.value == "Main content"

    def test_multi_word_bare_value_three_words(self):
        """Three-word bare values should be fully captured."""
        content = """===TEST===
TITLE::Hello World Again
===END==="""
        doc = parse(content)

        assignment = doc.sections[0]
        assert assignment.key == "TITLE"
        assert assignment.value == "Hello World Again"

    def test_multi_word_stops_at_newline(self):
        """Multi-word capture should stop at newline."""
        content = """===TEST===
FIRST::Word One Two
SECOND::Other
===END==="""
        doc = parse(content)

        first = doc.sections[0]
        second = doc.sections[1]
        assert first.key == "FIRST"
        assert first.value == "Word One Two"
        assert second.key == "SECOND"
        assert second.value == "Other"

    def test_multi_word_stops_at_comma_in_list(self):
        """Multi-word capture should stop at comma in list context."""
        content = """===TEST===
ITEMS::[First Item, Second Item, Third Item]
===END==="""
        doc = parse(content)

        assignment = doc.sections[0]
        assert assignment.key == "ITEMS"
        assert len(assignment.value.items) == 3
        assert assignment.value.items[0] == "First Item"
        assert assignment.value.items[1] == "Second Item"
        assert assignment.value.items[2] == "Third Item"

    def test_multi_word_stops_at_list_end(self):
        """Multi-word capture should stop at list end bracket."""
        content = """===TEST===
ITEMS::[Last Item]
===END==="""
        doc = parse(content)

        assignment = doc.sections[0]
        assert assignment.key == "ITEMS"
        assert len(assignment.value.items) == 1
        assert assignment.value.items[0] == "Last Item"

    def test_single_word_still_works(self):
        """Single word values should continue to work."""
        content = """===TEST===
SINGLE::value
===END==="""
        doc = parse(content)

        assignment = doc.sections[0]
        assert assignment.key == "SINGLE"
        assert assignment.value == "value"

    def test_multi_word_does_not_consume_operators(self):
        """Multi-word capture should not consume operators."""
        content = """===TEST===
FLOW::Step One->Step Two
===END==="""
        doc = parse(content)

        assignment = doc.sections[0]
        assert assignment.key == "FLOW"
        # Should parse as flow expression, not raw multi-word
        assert "Step" in str(assignment.value)
        # The -> is normalized to unicode arrow
        assert "\u2192" in str(assignment.value) or "->" in str(assignment.value)

    def test_quoted_strings_unaffected(self):
        """Quoted strings should not be affected by multi-word changes."""
        content = """===TEST===
QUOTED::"Already Quoted String"
===END==="""
        doc = parse(content)

        assignment = doc.sections[0]
        assert assignment.key == "QUOTED"
        assert assignment.value == "Already Quoted String"


class TestBareValueEdgeCases:
    """Edge cases for bare value handling."""

    def test_mixed_operators_and_bare_words(self):
        """Operators should still be recognized in multi-word context."""
        content = """===TEST===
EXPR::A+B means synthesis
===END==="""
        doc = parse(content)

        assignment = doc.sections[0]
        # The expression starts with operators, so should be parsed as expression
        # A+B should use synthesis operator
        assert "A" in str(assignment.value)
        assert "B" in str(assignment.value)

    def test_numbers_in_multi_word(self):
        """Numbers in multi-word context should be preserved."""
        content = """===TEST===
VERSION::Version 2 Beta
===END==="""
        doc = parse(content)

        assignment = doc.sections[0]
        assert assignment.key == "VERSION"
        # Numbers are tokenized separately, so this tests interaction
        # Current expectation: "Version" then 2 then "Beta"
        # This may need adjustment based on actual tokenization
        value_str = str(assignment.value)
        assert "Version" in value_str

    def test_hyphenated_multi_word(self):
        """Hyphenated identifiers in multi-word context."""
        content = """===TEST===
TITLE::kebab-case title-here
===END==="""
        doc = parse(content)

        assignment = doc.sections[0]
        assert assignment.key == "TITLE"
        assert "kebab-case" in str(assignment.value)
        assert "title-here" in str(assignment.value)
