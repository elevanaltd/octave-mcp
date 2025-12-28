"""Tests for tension operator fixes (Issues #62 and #65).

Issue #62: Unicode tension operator swirl causes silent value truncation
Issue #65: ASCII tension operator <-> not recognized by tokenizer

TDD Phase: GREEN - All tests now pass with tension operator fixes.
"""

from octave_mcp.core.lexer import TokenType, tokenize
from octave_mcp.core.parser import parse


class TestASCIITensionOperator:
    """Tests for ASCII tension operator <-> support (Issue #65).

    Expected: <-> should be recognized and normalized to unicode swirl.
    Current: E_TOKENIZE error - Unexpected character '<'
    """

    def test_tokenize_ascii_tension_operator(self):
        """Should tokenize <-> as TENSION operator."""
        tokens, repairs = tokenize("A <-> B")
        tension_tokens = [t for t in tokens if t.type == TokenType.TENSION]
        assert len(tension_tokens) == 1
        assert tension_tokens[0].value == "\u21cc"  # Unicode swirl
        assert tension_tokens[0].normalized_from == "<->"

    def test_ascii_tension_in_assignment(self):
        """Should parse <-> in assignment values."""
        content = """===TEST===
TENSION::Speed <-> Quality
===END==="""
        doc = parse(content)
        assignment = doc.sections[0]
        assert "Speed" in str(assignment.value)
        assert "Quality" in str(assignment.value)

    def test_ascii_tension_without_spaces(self):
        """Should handle <-> without surrounding spaces."""
        tokens, _ = tokenize("A<->B")
        tension_tokens = [t for t in tokens if t.type == TokenType.TENSION]
        assert len(tension_tokens) == 1

    def test_ascii_tension_normalization_logged(self):
        """Should log <-> to swirl normalization in repairs."""
        tokens, repairs = tokenize("X <-> Y")
        norm_repairs = [r for r in repairs if r.get("original") == "<->"]
        assert len(norm_repairs) == 1
        assert norm_repairs[0]["normalized"] == "\u21cc"


class TestUnicodeTensionOperator:
    """Tests for unicode tension operator value preservation (Issue #62).

    Expected: Full value "Speed swirl Quality" should be preserved.
    Current: Value truncated to just "Speed" - everything after operator lost.
    """

    def test_tension_value_preserved_in_flow_expression(self):
        """Should preserve full tension expression in value."""
        content = """===TEST===
TENSION::Speed \u21cc Quality
===END==="""
        doc = parse(content)
        assignment = doc.sections[0]
        value = str(assignment.value)
        assert "Speed" in value
        assert "\u21cc" in value  # Tension operator present
        assert "Quality" in value

    def test_unicode_tension_tokenizes_correctly(self):
        """Unicode swirl should tokenize as TENSION."""
        tokens, _ = tokenize("A \u21cc B")
        tension_tokens = [t for t in tokens if t.type == TokenType.TENSION]
        assert len(tension_tokens) == 1
        assert tension_tokens[0].value == "\u21cc"

    def test_vs_tension_alias_preserved_in_expression(self):
        """'vs' alias should also preserve full expression."""
        content = """===TEST===
COMPARISON::Speed vs Quality
===END==="""
        doc = parse(content)
        assignment = doc.sections[0]
        value = str(assignment.value)
        assert "Speed" in value
        assert "Quality" in value

    def test_tension_in_list(self):
        """Tension expressions in lists should be preserved."""
        content = """===TEST===
TRADEOFFS::[Speed \u21cc Quality, Cost \u21cc Features]
===END==="""
        doc = parse(content)
        assignment = doc.sections[0]
        items = assignment.value.items
        assert len(items) == 2
        assert "Speed" in str(items[0])
        assert "Quality" in str(items[0])


class TestTensionOperatorEdgeCases:
    """Edge cases for tension operator handling."""

    def test_multiple_tension_operators(self):
        """Multiple tension operators in one value."""
        content = """===TEST===
COMPLEX::A \u21cc B \u21cc C
===END==="""
        doc = parse(content)
        assignment = doc.sections[0]
        value = str(assignment.value)
        assert value.count("\u21cc") == 2

    def test_tension_mixed_with_flow(self):
        """Tension operators mixed with flow operators."""
        content = """===TEST===
MIXED::Start->A \u21cc B->End
===END==="""
        doc = parse(content)
        assignment = doc.sections[0]
        value = str(assignment.value)
        assert "Start" in value
        assert "End" in value

    def test_tension_with_synthesis(self):
        """Tension operators with synthesis operators."""
        content = """===TEST===
COMBO::X+Y \u21cc Z
===END==="""
        doc = parse(content)
        assignment = doc.sections[0]
        value = str(assignment.value)
        assert "X" in value
        assert "Z" in value
