"""Regression tests for parser.py:98-113 - Bare line token handling.

These tests document the CURRENT behavior of the parser when encountering
tokens that cannot form valid assignments or blocks. This serves as a
safety net before implementing fixes for issues #62, #63, #64, #65, #66.

Test Strategy:
1. Document current "silent drop" behavior for bare lines (issue #64)
2. Establish baseline for tension operator handling (issues #62, #65)
3. Create foundation for multi-word value tests (issues #63, #66)
"""

from octave_mcp.core.ast_nodes import Assignment, Block
from octave_mcp.core.parser import parse


class TestBareLineCurrentBehavior:
    """Document current behavior of bare lines without :: or :

    Location: parser.py:98-113 (parse_document body loop)
    Current behavior: Unexpected tokens are silently consumed to prevent infinite loop.
    Issue #64 requests: Replace silent drop with warning in repairs array.
    """

    def test_bare_identifier_is_silently_dropped(self):
        """Current behavior: Bare identifiers without :: are silently dropped.

        This test documents the EXISTING behavior that issue #64 addresses.
        The line 'MISSING_END' has no operator so parse_section returns None,
        and line 112 consumes the token with no warning.
        """
        content = """===MALFORMED===
STATUS::ACTIVE
MISSING_END
===END==="""
        doc = parse(content)

        # Current behavior: MISSING_END is silently dropped
        assert doc.name == "MALFORMED"
        assert len(doc.sections) == 1  # Only STATUS is parsed
        assignment = doc.sections[0]
        assert isinstance(assignment, Assignment)
        assert assignment.key == "STATUS"
        assert assignment.value == "ACTIVE"

    def test_multiple_bare_lines_all_dropped(self):
        """All bare lines without operators are dropped silently."""
        content = """===TEST===
VALID::value
bare_line_one
bare_line_two
ANOTHER::value2
bare_line_three
===END==="""
        doc = parse(content)

        # Only assignments with :: are kept
        assert len(doc.sections) == 2
        assert doc.sections[0].key == "VALID"
        assert doc.sections[1].key == "ANOTHER"

    def test_bare_line_between_block_children(self):
        """Bare lines inside blocks terminate child parsing.

        Current behavior: When parse_section returns None for bare_line_inside,
        the block parsing loop at line 410-412 exits, dropping CHILD2.
        This is more severe than just dropping the bare line.
        """
        content = """===TEST===
BLOCK:
  CHILD1::value1
  bare_line_inside
  CHILD2::value2
===END==="""
        doc = parse(content)

        block = doc.sections[0]
        assert isinstance(block, Block)
        # Current behavior: bare_line_inside causes early exit, CHILD2 is lost
        assert len(block.children) == 1
        assert block.children[0].key == "CHILD1"

    def test_bare_line_at_document_end(self):
        """Bare line at end of document is dropped."""
        content = """===TEST===
FIELD::value
bare_at_end
===END==="""
        doc = parse(content)

        assert len(doc.sections) == 1
        assert doc.sections[0].key == "FIELD"


class TestTensionOperatorCurrentBehavior:
    """Document current tension operator behavior in parse_flow_expression.

    Location: parser.py:539-556 (parse_flow_expression)
    Issue #62: Unicode tension operator (swirl) causes silent value truncation
    Issue #65: ASCII tension operator <-> not recognized

    Current behavior: TENSION token type is NOT in the while loop at line 539,
    so when parser encounters tension operator, it exits the loop early,
    causing truncation.
    """

    def test_flow_expression_captures_flow_operators(self):
        """FLOW operators (->) are captured and normalized to unicode."""
        content = """===TEST===
PIPELINE::A->B->C
===END==="""
        doc = parse(content)

        assignment = doc.sections[0]
        assert assignment.key == "PIPELINE"
        # Lexer normalizes -> to unicode arrow
        assert assignment.value == "A\u2192B\u2192C"  # A→B→C in unicode

    def test_synthesis_expression_captured(self):
        """SYNTHESIS operators (+) are captured correctly."""
        content = """===TEST===
COMBINED::X+Y
===END==="""
        doc = parse(content)

        assignment = doc.sections[0]
        # Note: + normalizes to unicode synthesis operator
        assert "X" in str(assignment.value)
        assert "Y" in str(assignment.value)

    def test_tension_operator_unicode_truncates(self):
        """CURRENT BUG (Issue #62): Unicode tension causes truncation.

        The parse_flow_expression while loop at line 539-546 does NOT include
        TokenType.TENSION, so encountering it exits the loop early.
        """
        content = """===TEST===
TENSION::Speed
===END==="""
        doc = parse(content)

        # This passes - single word works
        assignment = doc.sections[0]
        assert assignment.key == "TENSION"
        assert assignment.value == "Speed"


class TestTensionOperatorFixedBehavior:
    """Tests for CORRECT tension operator behavior after fixes.

    These tests define the EXPECTED behavior after fixing issues #62 and #65.
    They should FAIL before the fix and PASS after.

    Issue #62: Unicode tension operator (swirl) should capture full expression
    Issue #65: ASCII tension operator <-> should be recognized and normalized
    """

    def test_tension_operator_unicode_captures_full_expression(self):
        """FIX for Issue #62: Unicode tension captures full expression.

        After fix: parse_flow_expression should include TokenType.TENSION
        in its while loop, allowing expressions like "Speed ⇌ Quality".
        """
        content = """===TEST===
TRADEOFF::Speed⇌Quality
===END==="""
        doc = parse(content)

        assignment = doc.sections[0]
        assert assignment.key == "TRADEOFF"
        # After fix: should capture the full expression including tension operator
        assert assignment.value == "Speed⇌Quality"

    def test_tension_operator_unicode_with_spaces(self):
        """Unicode tension with identifiers on both sides."""
        content = """===TEST===
BALANCE::Performance⇌Readability
===END==="""
        doc = parse(content)

        assignment = doc.sections[0]
        assert assignment.key == "BALANCE"
        assert "Performance" in assignment.value
        assert "Readability" in assignment.value
        assert "⇌" in assignment.value

    def test_tension_operator_ascii_recognized(self):
        """FIX for Issue #65: ASCII <-> is recognized as TENSION operator.

        After fix: <-> should be in TOKEN_PATTERNS and ASCII_ALIASES,
        tokenizing as TokenType.TENSION and normalizing to unicode swirl.
        """
        content = """===TEST===
TRADEOFF::Speed<->Quality
===END==="""
        doc = parse(content)

        assignment = doc.sections[0]
        assert assignment.key == "TRADEOFF"
        # ASCII <-> should normalize to unicode swirl
        assert assignment.value == "Speed⇌Quality"

    def test_tension_operator_ascii_vs_embedded_is_not_recognized(self):
        """Embedded 'vs' in identifier is NOT recognized (word boundary required).

        The lexer pattern uses \\bvs\\b which requires word boundaries.
        'GoodvsBad' is parsed as a single identifier, not as 'Good' vs 'Bad'.
        This is expected behavior - use <-> for embedded tension.
        """
        content = """===TEST===
VERSUS::GoodvsBad
===END==="""
        doc = parse(content)

        assignment = doc.sections[0]
        assert assignment.key == "VERSUS"
        # Without word boundaries, vs is part of the identifier
        assert assignment.value == "GoodvsBad"  # Not normalized

    def test_tension_operator_ascii_vs_with_unicode_swirl(self):
        """Unicode swirl (not vs) can be embedded in expressions."""
        content = """===TEST===
VERSUS::Good⇌Bad
===END==="""
        doc = parse(content)

        assignment = doc.sections[0]
        assert assignment.key == "VERSUS"
        # Unicode swirl is always recognized
        assert assignment.value == "Good⇌Bad"

    def test_tension_in_complex_expression(self):
        """Tension operator mixed with other operators."""
        content = """===TEST===
COMPLEX::A→B⇌C→D
===END==="""
        doc = parse(content)

        assignment = doc.sections[0]
        assert assignment.key == "COMPLEX"
        # Full expression should be captured
        assert "A" in assignment.value
        assert "B" in assignment.value
        assert "C" in assignment.value
        assert "D" in assignment.value
        assert "→" in assignment.value
        assert "⇌" in assignment.value

    def test_constraint_operator_in_expression(self):
        """CONSTRAINT operator (∧) should also work in expressions."""
        content = """===TEST===
RULE::ConditionA∧ConditionB
===END==="""
        doc = parse(content)

        assignment = doc.sections[0]
        assert assignment.key == "RULE"
        assert "ConditionA" in assignment.value
        assert "ConditionB" in assignment.value
        assert "∧" in assignment.value

    def test_alternative_operator_in_expression(self):
        """ALTERNATIVE operator (∨) should also work in expressions."""
        content = """===TEST===
CHOICE::OptionA∨OptionB
===END==="""
        doc = parse(content)

        assignment = doc.sections[0]
        assert assignment.key == "CHOICE"
        assert "OptionA" in assignment.value
        assert "OptionB" in assignment.value
        assert "∨" in assignment.value


class TestMultiWordValueCurrentBehavior:
    """Document current multi-word value handling behavior.

    Location: parser.py:441-466 (parse_value identifier handling)
    Issue #63: Triple quotes cause complete value loss
    Issue #66: Markdown eject truncates multi-word values
    """

    def test_quoted_string_preserves_spaces(self):
        """Quoted strings correctly preserve spaces."""
        content = """===TEST===
PHRASE::"Hello World"
===END==="""
        doc = parse(content)

        assignment = doc.sections[0]
        assert assignment.value == "Hello World"

    def test_bare_words_stop_at_operators(self):
        """Bare words terminate at operators or whitespace."""
        content = """===TEST===
SINGLE::word
===END==="""
        doc = parse(content)

        assignment = doc.sections[0]
        assert assignment.value == "word"


class TestParserLoopSafety:
    """Tests ensuring parser loop at 98-113 doesn't hang on edge cases.

    The current behavior at line 112 is to advance() past unrecognized tokens
    to prevent infinite loops. These tests verify that safety.
    """

    def test_empty_document_terminates(self):
        """Parser terminates on empty content."""
        doc = parse("===EMPTY===\n===END===")
        assert doc.name == "EMPTY"
        assert len(doc.sections) == 0

    def test_only_bare_lines_terminates(self):
        """Parser terminates with only bare lines."""
        content = """===BARE===
first
second
third
===END==="""
        doc = parse(content)

        assert doc.name == "BARE"
        assert len(doc.sections) == 0  # All dropped

    def test_deeply_nested_terminates(self):
        """Deeply nested content terminates properly."""
        content = """===NESTED===
L1:
  L2:
    L3:
      L4::deep_value
===END==="""
        doc = parse(content)

        assert len(doc.sections) == 1
        l1 = doc.sections[0]
        assert l1.key == "L1"
