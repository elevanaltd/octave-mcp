"""Tests for variable syntax support (Issue #181).

Variables are placeholders in OCTAVE documents that use the `$` prefix.
They are treated as atomic values (like strings) without expansion.

Patterns:
- $VAR - Simple variable
- $1:name - Positional with type hint
- $STAGE, $SAVED, $ANSWER - Named variables

TDD: These tests are written FIRST (RED phase) before implementation.
"""

import pytest

from octave_mcp.core.ast_nodes import Assignment, ListValue
from octave_mcp.core.emitter import emit
from octave_mcp.core.lexer import LexerError, TokenType, tokenize
from octave_mcp.core.parser import parse, parse_with_warnings


class TestVariableLexer:
    """Test variable tokenization in lexer."""

    def test_simple_variable_tokenized(self):
        """Simple $VAR should tokenize as VARIABLE token."""
        tokens, _ = tokenize("KEY::$VAR")

        # Find the variable token
        var_tokens = [t for t in tokens if t.type == TokenType.VARIABLE]
        assert len(var_tokens) == 1
        assert var_tokens[0].value == "$VAR"

    def test_positional_variable_with_type_hint(self):
        """$1:name pattern should tokenize as VARIABLE."""
        tokens, _ = tokenize("KEY::$1:name")

        var_tokens = [t for t in tokens if t.type == TokenType.VARIABLE]
        assert len(var_tokens) == 1
        assert var_tokens[0].value == "$1:name"

    def test_positional_variable_with_default(self):
        """$2:tier|default pattern should tokenize as VARIABLE."""
        tokens, _ = tokenize("KEY::$2:tier|default")

        var_tokens = [t for t in tokens if t.type == TokenType.VARIABLE]
        assert len(var_tokens) == 1
        assert var_tokens[0].value == "$2:tier"
        # Note: |default is a separate ALTERNATIVE operator + IDENTIFIER

    def test_named_variables(self):
        """Named variables like $STAGE, $SAVED, $ANSWER should tokenize."""
        tokens, _ = tokenize("KEY::[$STAGE,$SAVED,$ANSWER]")

        var_tokens = [t for t in tokens if t.type == TokenType.VARIABLE]
        assert len(var_tokens) == 3
        assert var_tokens[0].value == "$STAGE"
        assert var_tokens[1].value == "$SAVED"
        assert var_tokens[2].value == "$ANSWER"

    def test_variable_with_underscore(self):
        """Variables can contain underscores."""
        tokens, _ = tokenize("KEY::$MY_VAR")

        var_tokens = [t for t in tokens if t.type == TokenType.VARIABLE]
        assert len(var_tokens) == 1
        assert var_tokens[0].value == "$MY_VAR"

    def test_variable_with_numbers(self):
        """Variables can contain numbers (not just start with them)."""
        tokens, _ = tokenize("KEY::$VAR123")

        var_tokens = [t for t in tokens if t.type == TokenType.VARIABLE]
        assert len(var_tokens) == 1
        assert var_tokens[0].value == "$VAR123"

    def test_dollar_alone_is_error(self):
        """Bare $ without alphanumeric suffix should error."""
        with pytest.raises(LexerError):
            tokenize("KEY::$")

    def test_dollar_followed_by_invalid_is_error(self):
        """$ followed by non-alphanumeric should error."""
        # $ followed by space
        with pytest.raises(LexerError):
            tokenize("KEY::$ VAR")


class TestVariableParser:
    """Test variable parsing."""

    def test_variable_as_assignment_value(self):
        """Variables work as assignment values."""
        doc = parse("===TEST===\nKEY::$VAR\n===END===")

        assert len(doc.sections) == 1
        assignment = doc.sections[0]
        assert isinstance(assignment, Assignment)
        assert assignment.key == "KEY"
        assert assignment.value == "$VAR"

    def test_variable_in_list(self):
        """Variables work as list elements."""
        doc = parse("===TEST===\nARGS::[$1:role,$2:tier,$3:topic]\n===END===")

        assert len(doc.sections) == 1
        assignment = doc.sections[0]
        assert isinstance(assignment, Assignment)
        assert isinstance(assignment.value, ListValue)
        assert len(assignment.value.items) == 3
        assert assignment.value.items[0] == "$1:role"
        assert assignment.value.items[1] == "$2:tier"
        assert assignment.value.items[2] == "$3:topic"

    def test_variable_in_inline_map(self):
        """Variables work within inline maps."""
        doc = parse("===TEST===\nPROOF::[proves::$STAGE,nonce::$SAVED,receipt::$ANSWER]\n===END===")

        assert len(doc.sections) == 1
        assignment = doc.sections[0]
        assert isinstance(assignment, Assignment)
        assert isinstance(assignment.value, ListValue)

        # Check inline map values
        inline_map = assignment.value.items[0]
        assert inline_map.pairs.get("proves") == "$STAGE"

        inline_map2 = assignment.value.items[1]
        assert inline_map2.pairs.get("nonce") == "$SAVED"

        inline_map3 = assignment.value.items[2]
        assert inline_map3.pairs.get("receipt") == "$ANSWER"

    def test_variable_preserves_full_pattern(self):
        """Variable patterns are preserved completely."""
        doc = parse("===TEST===\nVAR::$1:role\n===END===")

        assignment = doc.sections[0]
        assert assignment.value == "$1:role"

    def test_variable_in_expression(self):
        """Variables can appear in flow expressions."""
        doc, warnings = parse_with_warnings("===TEST===\nFLOW::[$VAR->$OTHER]\n===END===")

        assignment = doc.sections[0]
        assert isinstance(assignment, Assignment)
        # Inside brackets, flow is allowed
        assert isinstance(assignment.value, ListValue)
        # The expression should contain variables
        assert "$VAR" in str(assignment.value.items[0])
        assert "$OTHER" in str(assignment.value.items[0])


class TestVariableEmitter:
    """Test variable emission."""

    def test_variable_emitted_unchanged(self):
        """Variables should be emitted without quotes."""
        doc = parse("===TEST===\nKEY::$VAR\n===END===")
        output = emit(doc)

        assert "KEY::$VAR" in output
        # Should NOT have quotes around the variable
        assert '"$VAR"' not in output

    def test_variable_list_emitted(self):
        """Variables in lists should be emitted without quotes."""
        doc = parse("===TEST===\nARGS::[$1:role,$2:tier]\n===END===")
        output = emit(doc)

        assert "[$1:role,$2:tier]" in output

    def test_variable_in_inline_map_emitted(self):
        """Variables in inline maps should be emitted without quotes."""
        doc = parse("===TEST===\nPROOF::[proves::$STAGE]\n===END===")
        output = emit(doc)

        assert "proves::$STAGE" in output
        assert '"$STAGE"' not in output


class TestVariableRoundTrip:
    """Test parse -> emit roundtrip preserves variables."""

    def test_simple_variable_roundtrip(self):
        """Simple variable survives roundtrip."""
        content = "===TEST===\nKEY::$VAR\n===END==="
        doc = parse(content)
        output = emit(doc)

        doc2 = parse(output)
        assert doc2.sections[0].value == doc.sections[0].value

    def test_complex_args_roundtrip(self):
        """Complex ARGS pattern survives roundtrip."""
        content = "===TEST===\nARGS::[$1:role,$2:tier|default,$3:topic]\n===END==="
        doc = parse(content)
        output = emit(doc)

        # Parse the output and verify structure preserved
        doc2 = parse(output)
        assert isinstance(doc2.sections[0].value, ListValue)
        assert len(doc2.sections[0].value.items) == len(doc.sections[0].value.items)

    def test_proof_pattern_roundtrip(self):
        """PROOF pattern from issue survives roundtrip."""
        content = "===TEST===\nPROOF::[proves::$STAGE,nonce::$SAVED,receipt::$ANSWER]\n===END==="
        doc = parse(content)
        output = emit(doc)

        doc2 = parse(output)
        # Verify inline maps preserved
        assert isinstance(doc2.sections[0].value, ListValue)
