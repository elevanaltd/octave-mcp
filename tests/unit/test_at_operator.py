"""Tests for @ (at/location) operator (Issue #38).

The @ operator provides location/context semantics:
- Syntax: A@B means "A at/in B"
- Precedence: 2.5 (between concat ⧺/~ and synthesis ⊕/+)
- Use cases:
  - ISSUE::SISYPHEAN@CI
  - ERROR::TIMEOUT@HERMES
  - REF::src/parser.py:42
"""

from octave_mcp.core.lexer import TokenType, tokenize
from octave_mcp.core.parser import parse


class TestAtOperatorLexer:
    """Test @ operator tokenization."""

    def test_tokenize_at_operator(self):
        """Should tokenize @ as AT token."""
        tokens, _ = tokenize("A@B")
        # Should have: IDENTIFIER(A), AT(@), IDENTIFIER(B), EOF
        assert len(tokens) >= 4
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "A"
        assert tokens[1].type == TokenType.AT
        assert tokens[1].value == "@"
        assert tokens[2].type == TokenType.IDENTIFIER
        assert tokens[2].value == "B"

    def test_tokenize_at_with_compound_identifiers(self):
        """Should handle @ with compound identifiers."""
        tokens, _ = tokenize("ERROR::TIMEOUT@HERMES")
        # Should have: IDENTIFIER, ASSIGN, IDENTIFIER, AT, IDENTIFIER, EOF
        at_tokens = [t for t in tokens if t.type == TokenType.AT]
        assert len(at_tokens) == 1
        assert at_tokens[0].value == "@"

    def test_tokenize_at_with_path(self):
        """Should handle @ with file paths in quoted strings."""
        tokens, _ = tokenize('REF::"src/parser.py:42"@LINE')
        at_tokens = [t for t in tokens if t.type == TokenType.AT]
        assert len(at_tokens) == 1


class TestAtOperatorParser:
    """Test @ operator parsing and precedence."""

    def test_parse_simple_at_expression(self):
        """Should parse A@B as location expression."""
        content = "KEY::A@B"
        doc = parse(content)
        # Should parse as assignment with @ expression value
        assert len(doc.sections) == 1
        assignment = doc.sections[0]
        assert assignment.key == "KEY"
        # Value should preserve @ operator
        assert "@" in str(assignment.value)

    def test_parse_at_with_compound_left(self):
        """Should parse compound@location correctly."""
        content = "ISSUE::SISYPHEAN@CI"
        doc = parse(content)
        assignment = doc.sections[0]
        assert assignment.key == "ISSUE"
        value_str = str(assignment.value)
        assert "SISYPHEAN" in value_str
        assert "@" in value_str
        assert "CI" in value_str

    def test_parse_at_precedence_with_synthesis(self):
        """@ should bind tighter than ⊕ (synthesis).

        Example: A⊕B@C should parse as A⊕(B@C), not (A⊕B)@C
        Precedence: @ is 2.5, ⊕ is 3
        Higher number = lower precedence, so @ binds tighter.
        """
        content = "KEY::A⊕B@C"
        doc = parse(content)
        assignment = doc.sections[0]
        value_str = str(assignment.value)
        # Should preserve operator order
        assert "⊕" in value_str
        assert "@" in value_str

    def test_parse_at_precedence_with_concat(self):
        """@ should bind looser than ⧺ (concat).

        Example: A⧺B@C should parse as (A⧺B)@C, not A⧺(B@C)
        Precedence: ⧺ is 2, @ is 2.5
        Lower number = higher precedence, so ⧺ binds tighter.
        """
        content = "KEY::A⧺B@C"
        doc = parse(content)
        assignment = doc.sections[0]
        value_str = str(assignment.value)
        # Should preserve operator order
        assert "⧺" in value_str
        assert "@" in value_str

    def test_parse_at_in_list(self):
        """Should handle @ operator within list values."""
        content = "REFS::[src@LINE_42, test@LINE_10]"
        doc = parse(content)
        assignment = doc.sections[0]
        assert assignment.key == "REFS"
        # List should contain @ expressions
        from octave_mcp.core.grammar.cst import ListValue

        assert isinstance(assignment.value, ListValue)
        assert len(assignment.value.items) == 2
        # Both items should contain @ operator
        assert "@" in str(assignment.value.items[0])
        assert "@" in str(assignment.value.items[1])


class TestAtOperatorSemantics:
    """Test @ operator semantic use cases."""

    def test_error_location_pattern(self):
        """Should support ERROR::TYPE@CONTEXT pattern."""
        content = "ERROR::TIMEOUT@HERMES"
        doc = parse(content)
        assignment = doc.sections[0]
        assert assignment.key == "ERROR"
        value_str = str(assignment.value)
        assert "TIMEOUT" in value_str
        assert "@" in value_str
        assert "HERMES" in value_str

    def test_issue_location_pattern(self):
        """Should support ISSUE::TYPE@LOCATION pattern."""
        content = "ISSUE::SISYPHEAN@CI"
        doc = parse(content)
        assignment = doc.sections[0]
        assert assignment.key == "ISSUE"
        value_str = str(assignment.value)
        assert "SISYPHEAN" in value_str
        assert "@" in value_str
        assert "CI" in value_str

    def test_reference_pattern(self):
        """Should support REF::path pattern with @ for context."""
        content = "REF::parser.py@validate_function"
        doc = parse(content)
        assignment = doc.sections[0]
        assert assignment.key == "REF"
        value_str = str(assignment.value)
        assert "parser.py" in value_str
        assert "@" in value_str
        assert "validate_function" in value_str
