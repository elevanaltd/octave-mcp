"""Tests for OCTAVE lexer with ASCII normalization (P1.2)."""

import pytest

from octave_mcp.core.lexer import LexerError, TokenType, tokenize


class TestLexerBasicTokenization:
    """Test basic tokenization of canonical OCTAVE."""

    def test_tokenize_assignment_operator(self):
        """Should tokenize :: as ASSIGN."""
        tokens, _ = tokenize("KEY::value")
        assert len(tokens) >= 3
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "KEY"
        assert tokens[1].type == TokenType.ASSIGN
        assert tokens[1].value == "::"
        assert tokens[2].type == TokenType.IDENTIFIER
        assert tokens[2].value == "value"

    def test_tokenize_block_operator(self):
        """Should tokenize : as BLOCK."""
        tokens, _ = tokenize("KEY:")
        assert len(tokens) >= 2
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "KEY"
        assert tokens[1].type == TokenType.BLOCK
        assert tokens[1].value == ":"

    def test_tokenize_longest_match_rule(self):
        """Should recognize :: before : (longest match)."""
        tokens, _ = tokenize("KEY::value")
        # Should have ASSIGN (::) not BLOCK (:) + BLOCK (:)
        assign_tokens = [t for t in tokens if t.type == TokenType.ASSIGN]
        block_tokens = [t for t in tokens if t.type == TokenType.BLOCK]
        assert len(assign_tokens) == 1
        assert len(block_tokens) == 0


class TestASCIINormalization:
    """Test ASCII alias normalization to unicode operators."""

    def test_normalize_arrow_operator(self):
        """Should normalize -> to →."""
        tokens, _ = tokenize("A->B")
        arrow_token = [t for t in tokens if t.type == TokenType.FLOW][0]
        assert arrow_token.value == "→"
        assert arrow_token.normalized_from == "->"

    def test_normalize_synthesis_operator(self):
        """Should normalize + to ⊕."""
        tokens, _ = tokenize("A+B")
        synth_token = [t for t in tokens if t.type == TokenType.SYNTHESIS][0]
        assert synth_token.value == "⊕"
        assert synth_token.normalized_from == "+"

    def test_normalize_concat_operator(self):
        """Should normalize ~ to ⧺."""
        tokens, _ = tokenize("A~B")
        concat_token = [t for t in tokens if t.type == TokenType.CONCAT][0]
        assert concat_token.value == "⧺"
        assert concat_token.normalized_from == "~"

    def test_normalize_tension_operator(self):
        """Should normalize vs to ⇌ with word boundaries."""
        tokens, _ = tokenize("A vs B")
        tension_token = [t for t in tokens if t.type == TokenType.TENSION][0]
        assert tension_token.value == "⇌"
        assert tension_token.normalized_from == "vs"

    def test_normalize_alternative_operator(self):
        """Should normalize | to ∨."""
        tokens, _ = tokenize("A|B")
        alt_token = [t for t in tokens if t.type == TokenType.ALTERNATIVE][0]
        assert alt_token.value == "∨"
        assert alt_token.normalized_from == "|"

    def test_normalize_constraint_operator(self):
        """Should normalize & to ∧."""
        tokens, _ = tokenize("[A&B]")
        constraint_token = [t for t in tokens if t.type == TokenType.CONSTRAINT][0]
        assert constraint_token.value == "∧"
        assert constraint_token.normalized_from == "&"

    def test_normalize_section_marker(self):
        """Should normalize # to §."""
        tokens, _ = tokenize("#1::OVERVIEW")
        section_token = [t for t in tokens if t.type == TokenType.SECTION][0]
        assert section_token.value == "§"
        assert section_token.normalized_from == "#"


class TestVsWordBoundaries:
    """Test 'vs' operator requires word boundaries."""

    def test_vs_with_spaces(self):
        """Should accept 'vs' with spaces."""
        tokens, _ = tokenize("Speed vs Quality")
        tension_tokens = [t for t in tokens if t.type == TokenType.TENSION]
        assert len(tension_tokens) == 1
        assert tension_tokens[0].value == "⇌"

    def test_vs_in_brackets(self):
        """Should accept 'vs' in brackets."""
        tokens, _ = tokenize("[A vs B]")
        tension_tokens = [t for t in tokens if t.type == TokenType.TENSION]
        assert len(tension_tokens) == 1

    def test_vs_without_boundaries_is_identifier(self):
        """Identifiers containing 'vs' should tokenize as IDENTIFIER, not error."""
        tokens, _ = tokenize("SpeedvsQuality")
        # Should be a single identifier token, not TENSION operator
        identifier_tokens = [t for t in tokens if t.type == TokenType.IDENTIFIER]
        tension_tokens = [t for t in tokens if t.type == TokenType.TENSION]
        assert len(identifier_tokens) == 1
        assert identifier_tokens[0].value == "SpeedvsQuality"
        assert len(tension_tokens) == 0  # No tension operator


class TestUnicodeNormalization:
    """Test NFC unicode normalization."""

    def test_nfc_normalization_applied(self):
        """Should apply NFC normalization to all text."""
        # Use composed form (NFC) vs decomposed (NFD)
        # The é character: composed é (U+00E9) vs decomposed e + ́ (U+0065 U+0301)
        import unicodedata

        composed = "café"  # NFC form
        decomposed = unicodedata.normalize("NFD", composed)  # NFD form

        tokens, _ = tokenize(f'KEY::"{decomposed}"')
        string_token = [t for t in tokens if t.type == TokenType.STRING][0]
        # Should be normalized to NFC
        assert unicodedata.is_normalized("NFC", string_token.value)


class TestTabRejection:
    """Test that tabs are rejected with E005."""

    def test_tabs_rejected(self):
        """Should reject tabs with clear error E005."""
        with pytest.raises(LexerError) as exc_info:
            tokenize("KEY::\tvalue")
        assert "E005" in str(exc_info.value)
        assert "tab" in str(exc_info.value).lower()


class TestEnvelopeTokenization:
    """Test envelope markers."""

    def test_start_envelope(self):
        """Should tokenize ===NAME=== as ENVELOPE_START."""
        tokens, _ = tokenize("===TEST===")
        assert tokens[0].type == TokenType.ENVELOPE_START
        assert tokens[0].value == "TEST"

    def test_end_envelope(self):
        """Should tokenize ===END=== as ENVELOPE_END."""
        tokens, _ = tokenize("===END===")
        assert tokens[0].type == TokenType.ENVELOPE_END


class TestEnvelopeIdentifierErrors:
    """Test improved error messages for invalid envelope identifiers (GH#145).

    Current behavior: Input like ===architectural-gaps-analysis=== produces
    'Unexpected character: =' which is confusing.

    Expected behavior: Specific error messages that identify the invalid
    character(s) in the envelope identifier and suggest valid alternatives.

    Spec reference:
    - octave-core-spec.oct.md §1::ENVELOPE: START::===NAME===[first_line,exact_match]
    - octave-core-spec.oct.md §4::STRUCTURE: KEYS::[A-Z,a-z,0-9,_][start_with_letter_or_underscore]
    """

    def test_hyphen_in_envelope_identifier(self):
        """Should report specific error for hyphen in envelope identifier.

        Input: ===architectural-gaps-analysis===
        Expected: Clear error about '-' being invalid in envelope identifiers.
        """
        with pytest.raises(LexerError) as exc_info:
            tokenize("===architectural-gaps-analysis===")
        error = exc_info.value
        assert error.error_code == "E_INVALID_ENVELOPE_ID"
        assert "-" in error.message or "hyphen" in error.message.lower()
        assert "underscore" in error.message.lower() or "CamelCase" in error.message
        assert error.line == 1
        assert error.column == 1

    def test_space_in_envelope_identifier(self):
        """Should report specific error for space in envelope identifier."""
        with pytest.raises(LexerError) as exc_info:
            tokenize("===MY DOCUMENT===")
        error = exc_info.value
        assert error.error_code == "E_INVALID_ENVELOPE_ID"
        assert "space" in error.message.lower()
        assert error.line == 1

    def test_special_char_in_envelope_identifier(self):
        """Should report specific error for special characters."""
        with pytest.raises(LexerError) as exc_info:
            tokenize("===MY@DOC===")
        error = exc_info.value
        assert error.error_code == "E_INVALID_ENVELOPE_ID"
        assert "@" in error.message
        assert error.line == 1

    def test_lowercase_envelope_identifier_valid(self):
        """Should accept lowercase envelope identifiers (not just uppercase).

        Per spec: KEYS::[A-Z,a-z,0-9,_] means both upper and lowercase are valid.
        """
        tokens, _ = tokenize("===my_document===")
        assert tokens[0].type == TokenType.ENVELOPE_START
        assert tokens[0].value == "my_document"

    def test_mixed_case_envelope_identifier_valid(self):
        """Should accept CamelCase envelope identifiers."""
        tokens, _ = tokenize("===MyDocument===")
        assert tokens[0].type == TokenType.ENVELOPE_START
        assert tokens[0].value == "MyDocument"

    def test_underscore_envelope_identifier_valid(self):
        """Should accept underscore-separated envelope identifiers."""
        tokens, _ = tokenize("===architectural_gaps_analysis===")
        assert tokens[0].type == TokenType.ENVELOPE_START
        assert tokens[0].value == "architectural_gaps_analysis"

    def test_numeric_suffix_envelope_identifier_valid(self):
        """Should accept envelope identifiers with numeric suffixes."""
        tokens, _ = tokenize("===VERSION_2===")
        assert tokens[0].type == TokenType.ENVELOPE_START
        assert tokens[0].value == "VERSION_2"

    def test_empty_envelope_identifier(self):
        """Should report error for empty envelope identifier."""
        with pytest.raises(LexerError) as exc_info:
            tokenize("======")
        error = exc_info.value
        assert error.error_code == "E_INVALID_ENVELOPE_ID"
        assert "empty" in error.message.lower()

    def test_starts_with_number(self):
        """Should report error for identifier starting with number."""
        with pytest.raises(LexerError) as exc_info:
            tokenize("===123START===")
        error = exc_info.value
        assert error.error_code == "E_INVALID_ENVELOPE_ID"
        assert error.line == 1

    def test_multiple_invalid_chars(self):
        """Should report the first invalid character found."""
        with pytest.raises(LexerError) as exc_info:
            tokenize("===bad-name@here===")
        error = exc_info.value
        assert error.error_code == "E_INVALID_ENVELOPE_ID"
        # Should mention the first invalid char (hyphen)
        assert "-" in error.message

    def test_unclosed_envelope_start(self):
        """Should handle envelope patterns that don't close properly."""
        with pytest.raises(LexerError) as exc_info:
            tokenize("===INCOMPLETE")
        error = exc_info.value
        # This might be E005 or E_INVALID_ENVELOPE_ID depending on implementation
        assert error.line == 1

    def test_error_message_suggests_fix(self):
        """Error message should suggest using underscores or CamelCase."""
        with pytest.raises(LexerError) as exc_info:
            tokenize("===my-kebab-case===")
        error = exc_info.value
        assert error.error_code == "E_INVALID_ENVELOPE_ID"
        # Should suggest alternatives
        assert "underscore" in error.message.lower() or "_" in error.message
        assert "CamelCase" in error.message or "camelcase" in error.message.lower()


class TestStringTokenization:
    """Test string literal handling."""

    def test_quoted_string(self):
        """Should tokenize quoted strings."""
        tokens, _ = tokenize('KEY::"hello world"')
        string_token = [t for t in tokens if t.type == TokenType.STRING][0]
        assert string_token.value == "hello world"

    def test_bare_word_string(self):
        """Should tokenize bare words as identifiers."""
        tokens, _ = tokenize("KEY::value")
        value_token = [t for t in tokens if t.value == "value"][0]
        assert value_token.type == TokenType.IDENTIFIER

    def test_string_escapes(self):
        """Should handle escape sequences in strings."""
        tokens, _ = tokenize(r'KEY::"line1\nline2\ttab\"quote"')
        string_token = [t for t in tokens if t.type == TokenType.STRING][0]
        assert '"' in string_token.value
        # Escapes should be preserved in token value


class TestTripleQuoteI4AuditTrail:
    """Tests for I4 audit trail when triple quotes are normalized (GH#63).

    Location: lexer.py:213-224 (triple quote handling)

    ISSUE: Triple quote to single quote normalization is NOT recorded
    in the repairs array. Per I4 (Discoverable Artifact Persistence),
    all normalizations should be tracked.

    FIX: Set Token.normalized_from when triple quotes detected,
    and add a repairs entry for the normalization.
    """

    def test_triple_quote_normalization_recorded_in_token(self):
        """Triple quote normalization should set normalized_from on token.

        Input: KEY::\"\"\"multi-line content\"\"\"
        Expected: Token.normalized_from = '\"\"\"' (or similar indicator)
        """
        content = 'KEY::"""multi-line content"""'
        tokens, _ = tokenize(content)

        string_token = [t for t in tokens if t.type == TokenType.STRING][0]
        assert string_token.value == "multi-line content"
        # After fix: normalized_from should indicate triple quote source
        assert string_token.normalized_from is not None
        assert '"""' in string_token.normalized_from

    def test_triple_quote_normalization_in_repairs_array(self):
        """Triple quote normalization should appear in repairs array.

        Per I4: If not written and addressable, didn't happen.
        The repairs array is the audit trail for normalizations.
        """
        content = 'DESCRIPTION::"""This is a multi-line description"""'
        tokens, repairs = tokenize(content)

        # After fix: repairs should include triple quote normalization entry
        triple_quote_repairs = [
            r for r in repairs if r.get("type") == "normalization" and '"""' in r.get("original", "")
        ]
        assert len(triple_quote_repairs) >= 1, "Triple quote normalization should be in repairs"
        assert triple_quote_repairs[0]["original"] == '"""'

    def test_single_quote_no_normalization(self):
        """Single-quoted strings should NOT have normalization entries."""
        content = 'KEY::"single quoted"'
        tokens, repairs = tokenize(content)

        string_token = [t for t in tokens if t.type == TokenType.STRING][0]
        assert string_token.value == "single quoted"
        # Single quotes are canonical, no normalization needed
        assert string_token.normalized_from is None

        # No triple-quote related repairs
        triple_quote_repairs = [r for r in repairs if '"""' in r.get("original", "")]
        assert len(triple_quote_repairs) == 0

    def test_triple_quote_with_internal_single_quotes(self):
        """Triple quotes containing single quotes should normalize correctly."""
        content = 'MSG::"""He said "hello" to her"""'
        tokens, repairs = tokenize(content)

        string_token = [t for t in tokens if t.type == TokenType.STRING][0]
        assert string_token.value == 'He said "hello" to her'
        # Should record the normalization
        assert string_token.normalized_from is not None


class TestMultiLineStringLineTracking:
    """Test line/column tracking for multi-line strings (PR #70 review fix).

    When triple-quoted strings span multiple lines, the lexer must count
    embedded newlines and update line/column correctly for subsequent tokens.
    """

    def test_multiline_triple_quote_updates_line_correctly(self):
        """Tokens after multi-line string should have correct line numbers.

        Input:
            ===TEST===
            BODY::\"\"\"Line one
            Line two
            Line three\"\"\"
            NEXT::value
            ===END===

        NEXT should be on line 5, not line 3.
        """
        content = '''===TEST===
BODY::"""Line one
Line two
Line three"""
NEXT::value
===END==='''
        tokens, _ = tokenize(content)

        # Find NEXT identifier
        next_token = [t for t in tokens if t.type == TokenType.IDENTIFIER and t.value == "NEXT"][0]
        # NEXT should be on line 5 (after 3-line string content)
        assert next_token.line == 5, f"Expected line 5, got {next_token.line}"
        assert next_token.column == 1

    def test_multiline_string_column_after_last_newline(self):
        """Column should reset correctly after embedded newlines."""
        content = '''KEY::"""first
second
third"""'''
        tokens, _ = tokenize(content)

        # The closing """ ends at column 8 on line 3
        # Next token should be on new position
        string_token = [t for t in tokens if t.type == TokenType.STRING][0]
        # String token is created at its START position
        assert string_token.line == 1
        assert string_token.column == 6  # After KEY::

    def test_single_line_string_no_line_increment(self):
        """Single-line strings should not increment line counter."""
        content = """KEY::"single line"
NEXT::value"""
        tokens, _ = tokenize(content)

        next_token = [t for t in tokens if t.type == TokenType.IDENTIFIER and t.value == "NEXT"][0]
        assert next_token.line == 2
        assert next_token.column == 1


class TestNumberTokenization:
    """Test number literal handling."""

    def test_integer(self):
        """Should tokenize integers."""
        tokens, _ = tokenize("COUNT::42")
        number_token = [t for t in tokens if t.type == TokenType.NUMBER][0]
        assert number_token.value == 42

    def test_negative_integer(self):
        """Should tokenize negative integers."""
        tokens, _ = tokenize("OFFSET::-10")
        number_token = [t for t in tokens if t.type == TokenType.NUMBER][0]
        assert number_token.value == -10

    def test_float(self):
        """Should tokenize floats."""
        tokens, _ = tokenize("PI::3.14")
        number_token = [t for t in tokens if t.type == TokenType.NUMBER][0]
        assert number_token.value == 3.14

    def test_scientific_notation(self):
        """Should tokenize scientific notation."""
        tokens, _ = tokenize("BIG::-1e10")
        number_token = [t for t in tokens if t.type == TokenType.NUMBER][0]
        assert number_token.value == -1e10


class TestBooleanAndNull:
    """Test boolean and null literal handling."""

    def test_true_literal(self):
        """Should tokenize 'true' as BOOLEAN."""
        tokens, _ = tokenize("ENABLED::true")
        bool_token = [t for t in tokens if t.type == TokenType.BOOLEAN][0]
        assert bool_token.value is True

    def test_false_literal(self):
        """Should tokenize 'false' as BOOLEAN."""
        tokens, _ = tokenize("ENABLED::false")
        bool_token = [t for t in tokens if t.type == TokenType.BOOLEAN][0]
        assert bool_token.value is False

    def test_null_literal(self):
        """Should tokenize 'null' as NULL."""
        tokens, _ = tokenize("VALUE::null")
        null_token = [t for t in tokens if t.type == TokenType.NULL][0]
        assert null_token.value is None


class TestComments:
    """Test comment handling."""

    def test_line_comment(self):
        """Should tokenize // comments."""
        tokens, _ = tokenize("KEY::value // this is a comment")
        comment_tokens = [t for t in tokens if t.type == TokenType.COMMENT]
        assert len(comment_tokens) == 1
        assert "this is a comment" in comment_tokens[0].value

    def test_comment_at_line_start(self):
        """Should tokenize comments at line start."""
        tokens, _ = tokenize("// Full line comment\nKEY::value")
        comment_tokens = [t for t in tokens if t.type == TokenType.COMMENT]
        assert len(comment_tokens) == 1


class TestBrackets:
    """Test bracket tokenization."""

    def test_square_brackets(self):
        """Should tokenize [ and ] as LIST_START/LIST_END."""
        tokens, _ = tokenize("[a,b,c]")
        assert tokens[0].type == TokenType.LIST_START
        list_end_tokens = [t for t in tokens if t.type == TokenType.LIST_END]
        assert len(list_end_tokens) == 1


class TestNormalizationLog:
    """Test that normalizations are logged."""

    def test_normalization_logged(self):
        """Should log all ASCII normalizations."""
        tokens, _ = tokenize("A->B+C")
        normalizations = [t for t in tokens if hasattr(t, "normalized_from") and t.normalized_from]
        assert len(normalizations) >= 2  # -> and +

    def test_unicode_input_not_logged(self):
        """Should not log normalizations for unicode input."""
        tokens, _ = tokenize("A→B⊕C")
        normalizations = [t for t in tokens if hasattr(t, "normalized_from") and t.normalized_from]
        assert len(normalizations) == 0


class TestWhitespace:
    """Test whitespace handling."""

    def test_whitespace_preserved_in_position(self):
        """Should track positions correctly across whitespace."""
        tokens, _ = tokenize("KEY :: value")
        # Positions should reflect actual character positions
        assert all(hasattr(t, "line") and hasattr(t, "column") for t in tokens)

    def test_newlines_tracked(self):
        """Should track line numbers across newlines."""
        tokens, _ = tokenize("LINE1::a\nLINE2::b")
        line2_tokens = [t for t in tokens if hasattr(t, "line") and t.line == 2]
        assert len(line2_tokens) > 0


class TestEdgeOptimizations:
    """Test edge case optimizations (P1.3 Assimilation)."""

    def test_dotted_identifiers(self):
        """Should tokenize identifiers with dots as single tokens (Issue #37)."""
        tokens, _ = tokenize("pkg.tool::value")
        # Should be IDENTIFIER(pkg.tool) ASSIGN(::) IDENTIFIER(value)
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "pkg.tool"
        assert tokens[1].type == TokenType.ASSIGN


class TestHyphenatedIdentifiers:
    """Test hyphen support in identifiers (Issue #53).

    Per specs/octave-5-llm-skills.oct.md:21, skill_identifier should support
    lowercase_hyphens_digits format (kebab-case).
    """

    def test_identifier_with_hyphens(self):
        """Should accept hyphens in identifiers (Issue #53)."""
        tokens, _ = tokenize("TOOL::debate-hall-mcp")
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "TOOL"
        assert tokens[1].type == TokenType.ASSIGN
        assert tokens[2].type == TokenType.IDENTIFIER
        assert tokens[2].value == "debate-hall-mcp"

    def test_kebab_case_identifier(self):
        """Should tokenize kebab-case identifiers."""
        tokens, _ = tokenize("my-project-name")
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "my-project-name"

    def test_mixed_case_with_hyphens(self):
        """Should tokenize mixed case identifiers with hyphens."""
        tokens, _ = tokenize("My-Project-Name")
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "My-Project-Name"

    def test_hyphen_with_numbers(self):
        """Should tokenize identifiers with hyphens and numbers."""
        tokens, _ = tokenize("tool-v2-beta")
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "tool-v2-beta"

    def test_hyphen_does_not_start_identifier(self):
        """Hyphen cannot start an identifier - should fail with E005."""
        with pytest.raises(LexerError) as exc_info:
            list(tokenize("-invalid-start"))
        assert "E005" in str(exc_info.value)

    def test_hyphen_does_not_conflict_with_flow_operator(self):
        """Flow operator -> should still work correctly with hyphenated identifiers."""
        tokens, _ = tokenize("my-tool->next-step")
        identifiers = [t for t in tokens if t.type == TokenType.IDENTIFIER]
        flow_tokens = [t for t in tokens if t.type == TokenType.FLOW]
        assert len(identifiers) == 2
        assert identifiers[0].value == "my-tool"
        assert identifiers[1].value == "next-step"
        assert len(flow_tokens) == 1

    def test_hyphen_does_not_conflict_with_negative_numbers(self):
        """Negative numbers should still work correctly."""
        tokens, _ = tokenize("VALUE::-42")
        number_tokens = [t for t in tokens if t.type == TokenType.NUMBER]
        assert len(number_tokens) == 1
        assert number_tokens[0].value == -42


class TestVersionTokenization:
    """Test VERSION field tokenization (Issues #140 #141).

    The NUMBER token pattern cannot handle semantic versions with multiple dots.
    VERSION field values like "0.1.0" must be handled by a dedicated VERSION token.
    """

    def test_version_tokenization_major_only(self):
        """Should tokenize VERSION::1 as IDENTIFIER + ASSIGN + NUMBER.

        Single integers are NUMBER tokens, not VERSION tokens.
        Parser contract requires VERSION::1 to be IDENTIFIER + ASSIGN + value.
        """
        tokens, _ = tokenize("VERSION::1")
        relevant = [t for t in tokens if t.type != TokenType.EOF]
        assert len(relevant) == 3
        assert relevant[0].type == TokenType.IDENTIFIER
        assert relevant[0].value == "VERSION"
        assert relevant[1].type == TokenType.ASSIGN
        assert relevant[2].type == TokenType.NUMBER
        assert relevant[2].value == 1

    def test_version_tokenization_full_semver(self):
        """Should tokenize VERSION::1.0.0 with full semantic version."""
        tokens, _ = tokenize("VERSION::1.0.0")
        version_token = [t for t in tokens if t.type == TokenType.VERSION][0]
        assert version_token.value == "1.0.0"

    def test_version_with_prerelease(self):
        """Should tokenize VERSION::1.0.0-beta.1 with prerelease identifier."""
        tokens, _ = tokenize("VERSION::1.0.0-beta.1")
        version_token = [t for t in tokens if t.type == TokenType.VERSION][0]
        assert version_token.value == "1.0.0-beta.1"

    def test_version_with_build_metadata(self):
        """Should tokenize VERSION::1.0.0+build.123 with build metadata."""
        tokens, _ = tokenize("VERSION::1.0.0+build.123")
        version_token = [t for t in tokens if t.type == TokenType.VERSION][0]
        assert version_token.value == "1.0.0+build.123"

    def test_version_quoted_string(self):
        """Should tokenize VERSION::"1.0.0" as quoted string."""
        tokens, _ = tokenize('VERSION::"1.0.0"')
        # Quoted versions should still be STRING tokens
        string_token = [t for t in tokens if t.type == TokenType.STRING][0]
        assert string_token.value == "1.0.0"

    def test_version_does_not_consume_regular_numbers(self):
        """VERSION pattern should not interfere with regular NUMBER tokens."""
        tokens, _ = tokenize("COUNT::42")
        number_token = [t for t in tokens if t.type == TokenType.NUMBER][0]
        assert number_token.value == 42

    def test_version_field_preserves_parser_contract(self):
        """VERSION::1.0.0 must tokenize as IDENTIFIER + ASSIGN + VERSION.

        Parser contract violation fix: The parser expects field assignments
        to tokenize as IDENTIFIER('field_name') + ASSIGN('::') + value.
        The VERSION:: collapsing pattern broke this contract, causing silent
        data loss in META blocks.
        """
        tokens, _ = tokenize("VERSION::1.0.0")
        relevant = [t for t in tokens if t.type != TokenType.EOF]
        assert len(relevant) == 3, f"Expected 3 tokens, got {len(relevant)}: {[(t.type, t.value) for t in relevant]}"
        assert relevant[0].type == TokenType.IDENTIFIER
        assert relevant[0].value == "VERSION"
        assert relevant[1].type == TokenType.ASSIGN
        assert relevant[2].type == TokenType.VERSION
        assert relevant[2].value == "1.0.0"

    def test_hyphenated_prerelease_tokens_correctly(self):
        """1.0.0-beta-1 should be a single VERSION token.

        Hyphen support: Prereleases can have hyphens within identifiers
        (e.g., beta-1, rc-2). The VERSION pattern must support this.
        """
        tokens, _ = tokenize("1.0.0-beta-1")
        version_tokens = [t for t in tokens if t.type == TokenType.VERSION]
        assert len(version_tokens) == 1, f"Expected 1 VERSION token, got {len(version_tokens)}"
        assert version_tokens[0].value == "1.0.0-beta-1"

    def test_standalone_version_in_list(self):
        """Should tokenize standalone versions in generic contexts (e.g. lists)."""
        # Verifies regex priority works for 1.2.3 without 'VERSION::' prefix
        tokens, _ = tokenize("[1.2.3, 2.0.0]")

        # Find VERSION tokens (skip LIST_START, COMMA, LIST_END)
        version_tokens = [t for t in tokens if t.type == TokenType.VERSION]
        assert len(version_tokens) == 2
        assert version_tokens[0].value == "1.2.3"
        assert version_tokens[1].value == "2.0.0"

    def test_version_in_dependency_value(self):
        """VERSION tokens should work in dependency specifications."""
        tokens, _ = tokenize("DEPENDENCY::package 1.2.3")

        # Should have IDENTIFIER, ASSIGN, IDENTIFIER, VERSION
        relevant = [t for t in tokens if t.type not in (TokenType.EOF, TokenType.NEWLINE)]
        assert len(relevant) == 4
        assert relevant[3].type == TokenType.VERSION
        assert relevant[3].value == "1.2.3"


class TestGrammarSentinelScoping:
    """Test GRAMMAR_SENTINEL scope restriction to prevent silent data loss.

    ISSUE: OCTAVE:: pattern matches anywhere in documents, not just at document start.
    This causes silent prefix loss when appearing in value positions.

    Example: NOTE::OCTAVE::5.1.0
    Bug: Tokenizes as IDENTIFIER('NOTE'), ASSIGN('::'), GRAMMAR_SENTINEL('5.1.0')
    Result: NOTE field gets value "5.1.0" (loses "OCTAVE::" prefix)

    FIX: Restrict GRAMMAR_SENTINEL to document start only (position 0).
    """

    def test_grammar_sentinel_only_at_document_start(self):
        """OCTAVE:: should not trigger GRAMMAR_SENTINEL mid-document."""
        tokens, _ = tokenize("NOTE::OCTAVE::5.1.0")
        # Should NOT contain GRAMMAR_SENTINEL token
        sentinel_tokens = [t for t in tokens if t.type == TokenType.GRAMMAR_SENTINEL]
        assert len(sentinel_tokens) == 0, "GRAMMAR_SENTINEL must not match mid-document"
        # Should tokenize as regular identifiers
        assert any(
            t.value == "OCTAVE" for t in tokens if t.type == TokenType.IDENTIFIER
        ), "OCTAVE should be an IDENTIFIER when not at document start"

    def test_grammar_sentinel_at_document_start(self):
        """OCTAVE:: at document start should trigger GRAMMAR_SENTINEL."""
        tokens, _ = tokenize("OCTAVE::5.1.0")
        sentinel_tokens = [t for t in tokens if t.type == TokenType.GRAMMAR_SENTINEL]
        assert len(sentinel_tokens) == 1, "GRAMMAR_SENTINEL should match at document start"
        assert sentinel_tokens[0].value == "5.1.0"

    def test_grammar_sentinel_after_whitespace_at_start(self):
        """OCTAVE:: should still match GRAMMAR_SENTINEL after leading whitespace."""
        tokens, _ = tokenize("  OCTAVE::5.1.0")
        # After leading whitespace, we're still at document start logically
        # This may need to be decided: strict position 0, or after indentation?
        # For now, test that it does NOT match (strict position 0 interpretation)
        sentinel_tokens = [t for t in tokens if t.type == TokenType.GRAMMAR_SENTINEL]
        # Strict interpretation: GRAMMAR_SENTINEL only at actual position 0
        assert len(sentinel_tokens) == 0, "GRAMMAR_SENTINEL should require position 0 (no leading whitespace)"

    def test_octave_identifier_in_value_position(self):
        """OCTAVE as identifier should work in value positions."""
        tokens, _ = tokenize("TOOL::OCTAVE")
        relevant = [t for t in tokens if t.type != TokenType.EOF]
        assert len(relevant) == 3
        assert relevant[0].type == TokenType.IDENTIFIER
        assert relevant[0].value == "TOOL"
        assert relevant[1].type == TokenType.ASSIGN
        assert relevant[2].type == TokenType.IDENTIFIER
        assert relevant[2].value == "OCTAVE"

    def test_no_silent_data_loss_in_nested_assignment(self):
        """Nested OCTAVE:: patterns should not lose data."""
        tokens, _ = tokenize("NOTE::OCTAVE::5.1.0")
        relevant = [t for t in tokens if t.type != TokenType.EOF]
        # Should tokenize as: IDENTIFIER('NOTE') ASSIGN('::') IDENTIFIER('OCTAVE') ASSIGN('::') VERSION('5.1.0')
        assert len(relevant) == 5, f"Expected 5 tokens, got {len(relevant)}: {[(t.type, t.value) for t in relevant]}"
        assert relevant[0].type == TokenType.IDENTIFIER
        assert relevant[0].value == "NOTE"
        assert relevant[1].type == TokenType.ASSIGN
        assert relevant[2].type == TokenType.IDENTIFIER
        assert relevant[2].value == "OCTAVE"
        assert relevant[3].type == TokenType.ASSIGN
        assert relevant[4].type == TokenType.VERSION
        assert relevant[4].value == "5.1.0"


class TestUnbalancedBracketDetection:
    """Test unbalanced bracket detection (GH#180).

    The lexer should detect unbalanced brackets and emit clear error messages
    that point to the location of the opening bracket, not where the parser
    gave up.

    Error format: E_UNBALANCED_BRACKET::opening '[' at line N, column M has no matching ']'
    """

    def test_unclosed_square_bracket_simple(self):
        """Should detect unclosed [ with clear error message."""
        with pytest.raises(LexerError) as exc_info:
            tokenize("[a, b, c")
        error = exc_info.value
        assert error.error_code == "E_UNBALANCED_BRACKET"
        assert "opening '['" in error.message
        assert "no matching ']'" in error.message
        assert error.line == 1
        assert error.column == 1  # Points to opening bracket

    def test_unclosed_square_bracket_with_content(self):
        """Should detect unclosed [ in assignment context."""
        with pytest.raises(LexerError) as exc_info:
            tokenize("ITEMS::[a, b, c")
        error = exc_info.value
        assert error.error_code == "E_UNBALANCED_BRACKET"
        assert error.line == 1
        assert error.column == 8  # Opening bracket at column 8

    def test_unclosed_square_bracket_multiline(self):
        """Should detect unclosed [ across multiple lines."""
        content = """ITEMS::[
  a,
  b,
  c"""
        with pytest.raises(LexerError) as exc_info:
            tokenize(content)
        error = exc_info.value
        assert error.error_code == "E_UNBALANCED_BRACKET"
        assert error.line == 1
        assert error.column == 8

    def test_extra_closing_bracket(self):
        """Should detect ] without matching [."""
        with pytest.raises(LexerError) as exc_info:
            tokenize("a, b, c]")
        error = exc_info.value
        assert error.error_code == "E_UNBALANCED_BRACKET"
        assert "']'" in error.message
        assert "no matching '['" in error.message
        assert error.line == 1
        assert error.column == 8  # Points to the unmatched ]

    def test_nested_brackets_balanced(self):
        """Balanced nested brackets should tokenize successfully."""
        tokens, _ = tokenize("[[a, b], [c, d]]")
        list_starts = [t for t in tokens if t.type == TokenType.LIST_START]
        list_ends = [t for t in tokens if t.type == TokenType.LIST_END]
        assert len(list_starts) == 3
        assert len(list_ends) == 3

    def test_nested_brackets_unclosed(self):
        """Should detect unclosed inner bracket."""
        with pytest.raises(LexerError) as exc_info:
            tokenize("[[a, b], [c, d]")
        error = exc_info.value
        assert error.error_code == "E_UNBALANCED_BRACKET"
        # Should point to first unclosed bracket
        assert error.line == 1
        assert error.column == 1

    def test_brackets_in_string_not_counted(self):
        """Brackets inside strings should not be counted."""
        tokens, _ = tokenize('MSG::"contains [ and ] but balanced"')
        # Should succeed because brackets are in string
        assert any(t.type == TokenType.STRING for t in tokens)

    def test_brackets_in_comment_not_counted(self):
        """Brackets inside comments should not be counted."""
        tokens, _ = tokenize("VALUE::42 // note: [unbalanced")
        # Should succeed because bracket is in comment
        assert any(t.type == TokenType.COMMENT for t in tokens)

    def test_multiple_unclosed_brackets_reports_first(self):
        """With multiple unclosed brackets, report the first."""
        with pytest.raises(LexerError) as exc_info:
            tokenize("[[[a")
        error = exc_info.value
        assert error.error_code == "E_UNBALANCED_BRACKET"
        assert error.column == 1  # First opening bracket

    def test_mismatched_bracket_types(self):
        """Should detect mismatched bracket types."""
        # Note: OCTAVE lexer only uses [] for lists, not () or {}
        # This test validates that [ must be closed with ]
        with pytest.raises(LexerError) as exc_info:
            tokenize("[a, b, c")
        error = exc_info.value
        assert error.error_code == "E_UNBALANCED_BRACKET"

    def test_balanced_brackets_complex(self):
        """Complex balanced structure should tokenize correctly."""
        content = """META:
  ITEMS::[
    [a, b],
    [c, d]
  ]
  VALUES::[1, 2, 3]"""
        tokens, _ = tokenize(content)
        list_starts = [t for t in tokens if t.type == TokenType.LIST_START]
        list_ends = [t for t in tokens if t.type == TokenType.LIST_END]
        assert len(list_starts) == len(list_ends)

    def test_error_message_format(self):
        """Error message should follow specified format."""
        with pytest.raises(LexerError) as exc_info:
            tokenize("[unclosed")
        error = exc_info.value
        # Verify full error string format
        error_str = str(error)
        assert "E_UNBALANCED_BRACKET" in error_str
        assert "line 1" in error_str
        assert "column 1" in error_str


class TestAngleBracketAnnotation:
    """Test NAME<qualifier> angle bracket annotation syntax (Issue #248, §2c)."""

    def test_simple_annotation_tokenizes_as_identifier(self):
        """ATHENA<strategic_wisdom> should tokenize as single IDENTIFIER."""
        tokens, _ = tokenize("ATHENA<strategic_wisdom>")
        # Should produce: IDENTIFIER("ATHENA<strategic_wisdom>"), EOF
        identifiers = [t for t in tokens if t.type == TokenType.IDENTIFIER]
        assert len(identifiers) == 1
        assert identifiers[0].value == "ATHENA<strategic_wisdom>"

    def test_annotation_in_assignment(self):
        """NAME<qualifier> should work as a value in assignment."""
        tokens, _ = tokenize("ARCHETYPE::ATHENA<strategic_wisdom>")
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "ARCHETYPE"
        assert tokens[1].type == TokenType.ASSIGN
        assert tokens[2].type == TokenType.IDENTIFIER
        assert tokens[2].value == "ATHENA<strategic_wisdom>"

    def test_annotation_with_underscore_qualifier(self):
        """Qualifier can contain underscores."""
        tokens, _ = tokenize("HERMES<api_translation>")
        identifiers = [t for t in tokens if t.type == TokenType.IDENTIFIER]
        assert len(identifiers) == 1
        assert identifiers[0].value == "HERMES<api_translation>"

    def test_annotation_preserves_case(self):
        """Annotation should preserve case of both name and qualifier."""
        tokens, _ = tokenize("MyArchetype<MyQualifier>")
        identifiers = [t for t in tokens if t.type == TokenType.IDENTIFIER]
        assert len(identifiers) == 1
        assert identifiers[0].value == "MyArchetype<MyQualifier>"

    def test_annotation_in_list(self):
        """NAME<qualifier> should work inside lists."""
        tokens, _ = tokenize("[ATHENA<strategic_wisdom>,ODYSSEUS<navigation>]")
        identifiers = [t for t in tokens if t.type == TokenType.IDENTIFIER]
        assert len(identifiers) == 2
        assert identifiers[0].value == "ATHENA<strategic_wisdom>"
        assert identifiers[1].value == "ODYSSEUS<navigation>"

    def test_tension_operator_still_works(self):
        """<-> tension operator must not be broken by angle bracket support."""
        tokens, _ = tokenize("A<->B")
        tension_tokens = [t for t in tokens if t.type == TokenType.TENSION]
        assert len(tension_tokens) == 1
        assert tension_tokens[0].value == "⇌"  # Normalized to unicode

    def test_standalone_angle_bracket_errors(self):
        """Standalone < outside annotation should error (spec §3b)."""
        with pytest.raises(LexerError):
            tokenize("5 < 10")

    def test_annotation_multiple_words_qualifier(self):
        """Qualifier with multiple words separated by underscores."""
        tokens, _ = tokenize("ATLAS<structural_foundation_deep>")
        identifiers = [t for t in tokens if t.type == TokenType.IDENTIFIER]
        assert len(identifiers) == 1
        assert identifiers[0].value == "ATLAS<structural_foundation_deep>"

    def test_annotation_single_char_qualifier(self):
        """Single-character qualifier should work."""
        tokens, _ = tokenize("X<y>")
        identifiers = [t for t in tokens if t.type == TokenType.IDENTIFIER]
        assert len(identifiers) == 1
        assert identifiers[0].value == "X<y>"

    def test_annotation_as_key_in_assignment(self):
        """NAME<qualifier> as key in KEY::value pattern."""
        tokens, _ = tokenize("ATHENA<strict>::enabled")
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "ATHENA<strict>"
        assert tokens[1].type == TokenType.ASSIGN
        assert tokens[2].type == TokenType.IDENTIFIER
        assert tokens[2].value == "enabled"

    def test_qualifier_must_start_with_letter_or_underscore(self):
        """Qualifier starting with digit should NOT form annotation."""
        # A<1x> — '1' is not a valid identifier start, so '<' is standalone
        with pytest.raises(LexerError):
            tokenize("A<1x>")

    def test_invalid_qualifier_with_hyphen_start(self):
        """Qualifier starting with hyphen should NOT form annotation."""
        # A<-x> — '-' is not a valid identifier start
        with pytest.raises(LexerError):
            tokenize("A<-x>")
