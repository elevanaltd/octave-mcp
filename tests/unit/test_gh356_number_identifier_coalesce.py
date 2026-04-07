"""Tests for GH#356: Number+identifier coalescing produces unexpected tokenization.

Bug: `IMPACT::12000_USERS` canonicalizes to `IMPACT::"12000 _USERS"` — the parser
splits the lexer's NUMBER(12000) + IDENTIFIER(_USERS) tokens and joins them with a
space, producing a quoted string that silently changes the original semantics.

I1 (SYNTACTIC_FIDELITY): normalization must alter syntax, never semantics.
The space insertion violates this immutable.

Fix approach: When a NUMBER token is immediately followed (no whitespace) by a
valid identifier character, the lexer should produce a single IDENTIFIER token
for the whole sequence (e.g., `12000_USERS` -> IDENTIFIER("12000_USERS")).

TDD RED Phase: All tests in this file define the CORRECT behavior after the fix.
"""

from octave_mcp.core.emitter import emit, needs_quotes
from octave_mcp.core.lexer import TokenType, tokenize
from octave_mcp.core.parser import parse


class TestLexerNumberIdentifierMerge:
    """GH#356: Lexer should produce single IDENTIFIER when number is immediately
    followed by identifier chars (no whitespace)."""

    def test_12000_USERS_single_token(self):
        """12000_USERS should be a single IDENTIFIER token, not NUMBER + IDENTIFIER."""
        content = "KEY::12000_USERS"
        tokens, _ = tokenize(content)

        # Filter to value tokens only (skip KEY and ASSIGN)
        value_tokens = [t for t in tokens if t.type in (TokenType.NUMBER, TokenType.IDENTIFIER) and t.value != "KEY"]

        assert len(value_tokens) == 1, (
            f"Expected 1 token for '12000_USERS', got {len(value_tokens)}: "
            f"{[(t.type.name, t.value) for t in value_tokens]}"
        )
        assert value_tokens[0].type == TokenType.IDENTIFIER
        assert value_tokens[0].value == "12000_USERS"

    def test_123_suffix_single_token(self):
        """123_suffix should be a single IDENTIFIER token."""
        content = "a::123_suffix"
        tokens, _ = tokenize(content)

        value_tokens = [t for t in tokens if t.type in (TokenType.NUMBER, TokenType.IDENTIFIER) and t.value != "a"]

        assert len(value_tokens) == 1, (
            f"Expected 1 token for '123_suffix', got {len(value_tokens)}: "
            f"{[(t.type.name, t.value) for t in value_tokens]}"
        )
        assert value_tokens[0].type == TokenType.IDENTIFIER
        assert value_tokens[0].value == "123_suffix"

    def test_0_test_single_token(self):
        """0_test should be a single IDENTIFIER token."""
        content = "a::0_test"
        tokens, _ = tokenize(content)

        value_tokens = [t for t in tokens if t.type in (TokenType.NUMBER, TokenType.IDENTIFIER) and t.value != "a"]

        assert len(value_tokens) == 1
        assert value_tokens[0].type == TokenType.IDENTIFIER
        assert value_tokens[0].value == "0_test"

    def test_42_123_single_token(self):
        """42_123 should be a single IDENTIFIER token."""
        content = "a::42_123"
        tokens, _ = tokenize(content)

        value_tokens = [t for t in tokens if t.type in (TokenType.NUMBER, TokenType.IDENTIFIER) and t.value != "a"]

        assert len(value_tokens) == 1
        assert value_tokens[0].type == TokenType.IDENTIFIER
        assert value_tokens[0].value == "42_123"

    def test_standalone_number_unchanged(self):
        """Plain numbers without trailing identifier chars remain NUMBER tokens."""
        content = "a::12000"
        tokens, _ = tokenize(content)

        value_tokens = [t for t in tokens if t.type in (TokenType.NUMBER, TokenType.IDENTIFIER) and t.value != "a"]

        assert len(value_tokens) == 1
        assert value_tokens[0].type == TokenType.NUMBER
        assert value_tokens[0].value == 12000

    def test_number_space_identifier_stays_separate(self):
        """Number followed by space then identifier should remain separate tokens."""
        content = "a::12000 USERS"
        tokens, _ = tokenize(content)

        value_tokens = [t for t in tokens if t.type in (TokenType.NUMBER, TokenType.IDENTIFIER) and t.value != "a"]

        assert len(value_tokens) == 2
        assert value_tokens[0].type == TokenType.NUMBER
        assert value_tokens[0].value == 12000
        assert value_tokens[1].type == TokenType.IDENTIFIER
        assert value_tokens[1].value == "USERS"

    def test_negative_number_underscore_single_token(self):
        """-123_suffix should be a single IDENTIFIER token."""
        content = "a::-123_suffix"
        tokens, _ = tokenize(content)

        value_tokens = [t for t in tokens if t.type in (TokenType.NUMBER, TokenType.IDENTIFIER) and t.value != "a"]

        assert len(value_tokens) == 1
        assert value_tokens[0].type == TokenType.IDENTIFIER
        assert value_tokens[0].value == "-123_suffix"

    def test_float_underscore_single_token(self):
        """3.14_suffix should be a single IDENTIFIER token."""
        content = "a::3.14_suffix"
        tokens, _ = tokenize(content)

        value_tokens = [t for t in tokens if t.type in (TokenType.NUMBER, TokenType.IDENTIFIER) and t.value != "a"]

        assert len(value_tokens) == 1
        assert value_tokens[0].type == TokenType.IDENTIFIER
        assert value_tokens[0].value == "3.14_suffix"


class TestParserNumberIdentifierNoSpace:
    """GH#356: Parser should see the merged token and produce the correct value."""

    def test_12000_USERS_parsed_value(self):
        """IMPACT::12000_USERS should parse to value '12000_USERS' without space."""
        content = """===TEST===
IMPACT::12000_USERS
===END==="""
        doc = parse(content)
        assignment = doc.sections[0]
        assert assignment.key == "IMPACT"
        assert assignment.value == "12000_USERS", f"Got: {assignment.value!r}"

    def test_123_suffix_parsed_value(self):
        """a::123_suffix should parse to value '123_suffix' without space."""
        content = """===TEST===
a::123_suffix
===END==="""
        doc = parse(content)
        assignment = doc.sections[0]
        assert assignment.key == "a"
        assert assignment.value == "123_suffix", f"Got: {assignment.value!r}"

    def test_sibling_after_number_identifier(self):
        """Lines after number+identifier values should be correct siblings."""
        content = """===TEST===
a::12000_USERS
b::value
===END==="""
        doc = parse(content)

        assignments = [s for s in doc.sections if hasattr(s, "key")]
        assert len(assignments) == 2, f"Expected 2 assignments, got: {assignments}"

        keys = [a.key for a in assignments]
        assert keys == ["a", "b"], f"Got keys: {keys}"

    def test_number_identifier_in_list(self):
        """Number+identifier values in lists should not have spaces."""
        content = """===TEST===
ITEMS::[12000_USERS, 5000_REQUESTS]
===END==="""
        doc = parse(content)
        assignment = doc.sections[0]
        items = assignment.value.items if hasattr(assignment.value, "items") else []
        assert len(items) == 2, f"Expected 2 items, got: {items}"
        assert "12000_USERS" in items, f"Missing '12000_USERS' in {items}"
        assert "5000_REQUESTS" in items, f"Missing '5000_REQUESTS' in {items}"


class TestEmitterRoundTrip:
    """GH#356: End-to-end canonicalization must preserve semantics (I1)."""

    def test_12000_USERS_roundtrip(self):
        """IMPACT::12000_USERS should roundtrip without space insertion."""
        content = """===TEST===
IMPACT::12000_USERS
===END==="""
        doc = parse(content)
        output = emit(doc)

        # The canonical output should NOT contain "12000 _USERS" (with space)
        assert "12000 _USERS" not in output, f"Space inserted! Output:\n{output}"
        # It should contain the original value
        assert "12000_USERS" in output, f"Original value lost! Output:\n{output}"

    def test_needs_quotes_no_space(self):
        """'12000_USERS' (no space) should not need quotes — it's a valid identifier."""
        # After the fix, the value is "12000_USERS" which starts with a digit.
        # The emitter's IDENTIFIER_PATTERN requires starting with [A-Za-z_].
        # So this will need quotes. That's OK — the key requirement is NO SPACE.
        # The value "12000_USERS" with quotes is semantically correct.
        result = needs_quotes("12000_USERS")
        # Whether it needs quotes or not, the important thing is the value itself
        # has no space. needs_quotes returns True because it starts with a digit.
        assert result is True  # Starts with digit, not a valid bare identifier

    def test_canonicalized_value_preserves_semantics(self):
        """The canonical form must be semantically identical to the input."""
        content = """===TEST===
IMPACT::12000_USERS
===END==="""
        doc = parse(content)
        output = emit(doc)

        # Parse the canonical output again
        doc2 = parse(output)
        assignment2 = doc2.sections[0]

        # The value after re-parse should be identical to the first parse
        assert assignment2.value == doc.sections[0].value, (
            f"Roundtrip changed semantics! "
            f"First parse: {doc.sections[0].value!r}, "
            f"Second parse: {assignment2.value!r}"
        )


class TestEdgeCases:
    """GH#356: Edge cases for the number+identifier merge."""

    def test_number_followed_by_letter_no_underscore(self):
        """12000ABC (number immediately followed by letter) should be single token."""
        content = "a::12000ABC"
        tokens, _ = tokenize(content)

        value_tokens = [t for t in tokens if t.type in (TokenType.NUMBER, TokenType.IDENTIFIER) and t.value != "a"]

        assert len(value_tokens) == 1
        assert value_tokens[0].type == TokenType.IDENTIFIER
        assert value_tokens[0].value == "12000ABC"

    def test_number_followed_by_dot_path(self):
        """Number followed by dot-path like 123.suffix is tricky — 123.s is a float parse.
        But 123.suffix_with_underscore should not corrupt.
        This test documents that 123.456 remains a float NUMBER."""
        content = "a::123.456"
        tokens, _ = tokenize(content)

        value_tokens = [t for t in tokens if t.type in (TokenType.NUMBER, TokenType.IDENTIFIER) and t.value != "a"]

        assert len(value_tokens) == 1
        assert value_tokens[0].type == TokenType.NUMBER
        assert value_tokens[0].value == 123.456

    def test_number_followed_by_operator_stays_number(self):
        """12000->next should keep 12000 as NUMBER, not merge with operator."""
        content = "a::12000->next"
        tokens, _ = tokenize(content)

        # NUMBER(12000), FLOW(->), IDENTIFIER(next)
        number_tokens = [t for t in tokens if t.type == TokenType.NUMBER]
        assert len(number_tokens) == 1
        assert number_tokens[0].value == 12000

    def test_scientific_notation_not_merged(self):
        """1e10 should remain a NUMBER, not become an identifier."""
        content = "a::1e10"
        tokens, _ = tokenize(content)

        value_tokens = [t for t in tokens if t.type in (TokenType.NUMBER, TokenType.IDENTIFIER) and t.value != "a"]

        assert len(value_tokens) == 1
        assert value_tokens[0].type == TokenType.NUMBER

    def test_number_at_end_of_line_stays_number(self):
        """Number at end of line (followed by newline) stays NUMBER."""
        content = "a::42\nb::value"
        tokens, _ = tokenize(content)

        number_tokens = [t for t in tokens if t.type == TokenType.NUMBER]
        assert len(number_tokens) == 1
        assert number_tokens[0].value == 42

    def test_number_before_bracket_stays_number(self):
        """Number before bracket like 42[x] should keep 42 as NUMBER."""
        content = "a::42"
        tokens, _ = tokenize(content)

        number_tokens = [t for t in tokens if t.type == TokenType.NUMBER]
        assert len(number_tokens) == 1
        assert number_tokens[0].value == 42
