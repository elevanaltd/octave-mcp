"""Tests for literal zone parser support (T07).

Issue #235: Verifies parse_literal_zone() and parse_value() integration.
"""

import unicodedata

import pytest

from octave_mcp.core.ast_nodes import Assignment, LiteralZoneValue
from octave_mcp.core.parser import parse


class TestParseLiteralZoneBasic:
    """Basic literal zone parsing tests."""

    def test_parse_simple_literal_zone(self):
        """Parse a simple literal zone with info tag."""
        doc = parse("===DOC===\n" "CODE::\n" "```python\n" "def hello():\n" "    pass\n" "```\n" "===END===")
        assert len(doc.sections) == 1
        assignment = doc.sections[0]
        assert isinstance(assignment, Assignment)
        assert assignment.key == "CODE"
        assert isinstance(assignment.value, LiteralZoneValue)

    def test_literal_zone_info_tag(self):
        """Info tag is correctly extracted."""
        doc = parse("===DOC===\nCODE::\n```python\nhello\n```\n===END===")
        value = doc.sections[0].value
        assert isinstance(value, LiteralZoneValue)
        assert value.info_tag == "python"

    def test_literal_zone_content(self):
        """Content is correctly extracted."""
        doc = parse("===DOC===\nCODE::\n```python\nhello\n```\n===END===")
        value = doc.sections[0].value
        assert isinstance(value, LiteralZoneValue)
        assert value.content == "hello"

    def test_literal_zone_fence_marker(self):
        """Fence marker is correctly extracted."""
        doc = parse("===DOC===\nCODE::\n```python\nhello\n```\n===END===")
        value = doc.sections[0].value
        assert isinstance(value, LiteralZoneValue)
        assert value.fence_marker == "```"

    def test_empty_literal_zone(self):
        """Empty literal zone has content == '' (I2: distinct from absent)."""
        doc = parse("===DOC===\nKEY::\n```\n```\n===END===")
        value = doc.sections[0].value
        assert isinstance(value, LiteralZoneValue)
        assert value.content == ""

    def test_literal_zone_no_info_tag(self):
        """Literal zone without info tag has info_tag == None."""
        doc = parse("===DOC===\nKEY::\n```\nhello\n```\n===END===")
        value = doc.sections[0].value
        assert isinstance(value, LiteralZoneValue)
        assert value.info_tag is None

    def test_info_tag_whitespace_stripped(self):
        """Info tag trailing whitespace is stripped."""
        doc = parse("===DOC===\nKEY::\n```python   \nhello\n```\n===END===")
        value = doc.sections[0].value
        assert isinstance(value, LiteralZoneValue)
        assert value.info_tag == "python"

    def test_info_tag_only_whitespace_becomes_none(self):
        """Info tag that is only whitespace normalizes to None."""
        doc = parse("===DOC===\nKEY::\n```   \nhello\n```\n===END===")
        value = doc.sections[0].value
        assert isinstance(value, LiteralZoneValue)
        assert value.info_tag is None


class TestParseLiteralZoneFenceVariants:
    """Fence variant parsing tests."""

    def test_four_backtick_fence(self):
        """4-backtick fence parsed correctly."""
        doc = parse("===DOC===\nKEY::\n````python\nhello\n````\n===END===")
        value = doc.sections[0].value
        assert isinstance(value, LiteralZoneValue)
        assert value.fence_marker == "````"
        assert value.info_tag == "python"
        assert value.content == "hello"

    def test_five_backtick_fence(self):
        """5-backtick fence parsed correctly."""
        doc = parse("===DOC===\nKEY::\n`````\nhello\n`````\n===END===")
        value = doc.sections[0].value
        assert isinstance(value, LiteralZoneValue)
        assert value.fence_marker == "`````"


class TestParseLiteralZoneContentPreservation:
    """Content preservation tests (I1: verbatim)."""

    def test_tabs_preserved(self):
        """Tabs inside literal zone content are preserved."""
        doc = parse("===DOC===\nKEY::\n```\n\tindented\twith\ttabs\n```\n===END===")
        value = doc.sections[0].value
        assert isinstance(value, LiteralZoneValue)
        assert "\t" in value.content
        assert value.content == "\tindented\twith\ttabs"

    def test_non_nfc_characters_preserved(self):
        """Non-NFC (decomposed) characters inside literal zone are preserved."""
        # U+0065 (e) + U+0301 (combining acute) = decomposed e-acute
        decomposed = "e\u0301"
        # Verify it's NOT NFC
        assert decomposed != unicodedata.normalize("NFC", decomposed)

        content = f"===DOC===\nKEY::\n```\n{decomposed}\n```\n===END==="
        doc = parse(content)
        value = doc.sections[0].value
        assert isinstance(value, LiteralZoneValue)
        assert value.content == decomposed

    def test_multiline_content(self):
        """Multi-line content is preserved."""
        doc = parse("===DOC===\nKEY::\n```python\nline1\nline2\nline3\n```\n===END===")
        value = doc.sections[0].value
        assert isinstance(value, LiteralZoneValue)
        assert value.content == "line1\nline2\nline3"


class TestParseLiteralZoneMultiple:
    """Multiple literal zone tests."""

    def test_multiple_literal_zones(self):
        """Document with multiple literal zone assignments."""
        content = "===DOC===\n" "CODE1::\n```python\nhello\n```\n" "CODE2::\n```json\n{}\n```\n" "===END==="
        doc = parse(content)
        assert len(doc.sections) == 2
        assert isinstance(doc.sections[0].value, LiteralZoneValue)
        assert isinstance(doc.sections[1].value, LiteralZoneValue)
        assert doc.sections[0].value.info_tag == "python"
        assert doc.sections[1].value.info_tag == "json"

    def test_literal_zone_in_nested_block(self):
        """Literal zone at nested block level."""
        content = "===DOC===\n" "OUTER:\n" "  CODE::\n" "```python\n" "hello\n" "```\n" "===END==="
        doc = parse(content)
        assert len(doc.sections) == 1
        block = doc.sections[0]
        assert len(block.children) == 1
        assignment = block.children[0]
        assert isinstance(assignment, Assignment)
        assert isinstance(assignment.value, LiteralZoneValue)


class TestParseLiteralZoneErrors:
    """Error handling tests."""

    def test_unterminated_literal_zone_raises_error(self):
        """Missing closing fence raises error (from lexer E006)."""
        with pytest.raises(Exception) as exc_info:
            parse("===DOC===\nKEY::\n```python\nhello\n===END===")
        # The error should be from the lexer (E006) since the fence is unclosed
        assert "E006" in str(exc_info.value)


class TestParseLiteralZoneDecision2:
    """D2: Triple-quoted strings remain normalizing strings, NOT literal zones."""

    def test_triple_quoted_string_not_literal_zone(self):
        """Triple-quoted string is still parsed as a string, not a literal zone."""
        doc = parse('===DOC===\nKEY::"""hello world"""\n===END===')
        value = doc.sections[0].value
        # Triple-quoted strings produce plain string values, not LiteralZoneValue
        assert not isinstance(value, LiteralZoneValue)
        assert isinstance(value, str)
        assert value == "hello world"
