"""Tests for bare line warning behavior (Issue #64).

Issue #64: Bare lines silently dropped without warning.
Expected: Warning should be added to Document.warnings when bare lines are dropped.

TDD Phase: GREEN - Tests verify warning behavior is now implemented.
"""

from octave_mcp.core.lexer import TokenType, tokenize
from octave_mcp.core.parser import parse


class TestBareLineWarnings:
    """Tests for bare line warning behavior.

    Location: parser.py:98-113 (parse_document body loop)
    Previous behavior: Unexpected tokens were silently consumed.
    New behavior: Warning is logged in doc.warnings for dropped lines.
    """

    def test_bare_line_generates_warning(self):
        """Parser should add warning when bare line is dropped."""
        content = """===TEST===
STATUS::ACTIVE
MISSING_END
===END==="""
        doc = parse(content)

        # Document should parse successfully
        assert doc.name == "TEST"
        # Only STATUS assignment should be present
        assert len(doc.sections) == 1
        assert doc.sections[0].key == "STATUS"

        # Warning should be generated for dropped bare line
        assert len(doc.warnings) == 1
        warning = doc.warnings[0]
        assert warning["type"] == "bare_line_dropped"
        assert "MISSING_END" in warning["value"]
        assert warning["line"] == 3

    def test_multiple_bare_lines_generate_multiple_warnings(self):
        """Each bare line should generate its own warning."""
        content = """===TEST===
VALID::value
bare_one
bare_two
ANOTHER::value2
bare_three
===END==="""
        doc = parse(content)

        # Assignments should be parsed
        assert len(doc.sections) == 2

        # Each bare line should have a warning
        assert len(doc.warnings) == 3
        values = [w["value"] for w in doc.warnings]
        assert "bare_one" in values
        assert "bare_two" in values
        assert "bare_three" in values

    def test_no_warning_for_valid_document(self):
        """Documents without bare lines should have no warnings."""
        content = """===TEST===
FIELD1::value1
FIELD2::value2
===END==="""
        doc = parse(content)

        assert len(doc.sections) == 2
        assert len(doc.warnings) == 0

    def test_lexer_tokenizes_bare_words(self):
        """Lexer should tokenize bare words as IDENTIFIER tokens."""
        tokens, _ = tokenize("bare_word_here")
        identifier_tokens = [t for t in tokens if t.type == TokenType.IDENTIFIER]
        assert len(identifier_tokens) == 1
        assert identifier_tokens[0].value == "bare_word_here"


class TestBareLineDocumentation:
    """Document bare line handling behavior for awareness.

    These tests document what happens with bare lines so developers
    understand the behavior.
    """

    def test_bare_line_at_document_level_dropped_with_warning(self):
        """Bare lines at document level are dropped with warning."""
        content = """===TEST===
VALID::value
bare_line
ANOTHER::value2
===END==="""
        doc = parse(content)

        # Both VALID and ANOTHER should be present, bare_line dropped
        assert len(doc.sections) == 2
        assert doc.sections[0].key == "VALID"
        assert doc.sections[1].key == "ANOTHER"

        # Warning should indicate what was dropped
        assert len(doc.warnings) == 1
        assert doc.warnings[0]["value"] == "bare_line"

    def test_bare_line_in_block_terminates_block(self):
        """Bare lines in blocks cause early block termination.

        This is documented behavior - bare lines inside blocks
        will terminate the block's child parsing.
        Note: Block-level bare lines do not generate warnings (yet).
        """
        content = """===TEST===
BLOCK:
  CHILD1::value1
  bare_line_inside
  CHILD2::value2
===END==="""
        doc = parse(content)

        block = doc.sections[0]
        # Current behavior: bare_line causes early exit, CHILD2 lost
        # This is the current documented behavior
        assert len(block.children) == 1
        assert block.children[0].key == "CHILD1"
