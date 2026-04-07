"""Tests for emoji and unicode symbol support in lexer identifiers (GH#186).

OCTAVE supports mythic compression style using emoji and unicode symbols as keys.
This enables expressive, semantic markup like:

    ⚠️::AT[ARM.result]→MUST_READ[skill_selectors]

Current behavior: E005 - Unexpected character: '⚠'
Expected behavior: Parse as valid IDENTIFIER token.

Implementation approach:
- Use Python's unicodedata module to check character categories
- Allow Letter (L*), Symbol Other (So), and specific Math Symbols (Sm)
- Exclude symbols that are OCTAVE operators (→, ⊕, ⇌, ∧, ∨, §, etc.)
- Handle multi-codepoint emoji gracefully (document as limited support)
"""

import unicodedata

import pytest

from octave_mcp.core.lexer import LexerError, TokenType, tokenize


class TestEmojiIdentifiers:
    """Test emoji support as identifier starts and characters."""

    def test_warning_emoji_as_identifier(self):
        """Warning sign should be valid identifier start.

        Input: ⚠️::warning_message
        Expected: IDENTIFIER('⚠️'), ASSIGN, IDENTIFIER
        """
        tokens, _ = tokenize("⚠️::warning_message")
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "⚠️"
        assert tokens[1].type == TokenType.ASSIGN
        assert tokens[2].type == TokenType.IDENTIFIER
        assert tokens[2].value == "warning_message"

    def test_checkmark_emoji_as_identifier(self):
        """Checkmark should be valid identifier."""
        tokens, _ = tokenize("✓::PASSED")
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "✓"
        assert tokens[1].type == TokenType.ASSIGN

    def test_cross_mark_emoji_as_identifier(self):
        """Cross mark should be valid identifier."""
        tokens, _ = tokenize("✗::FAILED")
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "✗"

    def test_star_emoji_as_identifier(self):
        """Star emoji should be valid identifier."""
        tokens, _ = tokenize("⭐::PRIORITY")
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "⭐"

    def test_fire_emoji_as_identifier(self):
        """Fire emoji should be valid identifier."""
        tokens, _ = tokenize("🔥::CRITICAL")
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "🔥"

    def test_emoji_in_list(self):
        """Emoji identifiers should work in lists."""
        tokens, _ = tokenize("STATUS::[✓,✗,⚠️]")
        identifiers = [t for t in tokens if t.type == TokenType.IDENTIFIER]
        # STATUS, ✓, ✗, ⚠️
        emoji_ids = [t for t in identifiers if ord(t.value[0]) > 127]
        assert len(emoji_ids) >= 3

    def test_emoji_mixed_with_ascii(self):
        """Emoji can be combined with ASCII in identifiers."""
        tokens, _ = tokenize("⚠️_warning::message")
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "⚠️_warning"

    def test_emoji_at_end_of_identifier(self):
        """Emoji can appear at end of identifier."""
        tokens, _ = tokenize("status_⚠️::warning")
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "status_⚠️"

    def test_multiple_emoji_identifier(self):
        """Multiple emoji in sequence should work."""
        tokens, _ = tokenize("⚠️⭐::urgent_priority")
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "⚠️⭐"


class TestUnicodeSymbolIdentifiers:
    """Test unicode symbol support as identifiers (non-operator symbols)."""

    def test_bullet_point_identifier(self):
        """Bullet point should be valid identifier."""
        tokens, _ = tokenize("•::item")
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "•"

    def test_arrow_bullet_identifier(self):
        """Arrow bullet should be valid identifier (not flow operator)."""
        tokens, _ = tokenize("▸::action")
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "▸"

    def test_box_drawing_identifier(self):
        """Box drawing characters should be valid."""
        tokens, _ = tokenize("├::tree_branch")
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "├"

    def test_circled_numbers_identifier(self):
        """Circled numbers should work as identifiers."""
        tokens, _ = tokenize("①::first_step")
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "①"

    def test_mathematical_subscript(self):
        """Mathematical subscripts should work."""
        tokens, _ = tokenize("x₁::value")
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "x₁"


class TestOperatorSymbolsNotIdentifiers:
    """Ensure OCTAVE operators remain operators, not identifiers."""

    def test_flow_arrow_remains_operator(self):
        """→ (U+2192) should remain FLOW operator."""
        tokens, _ = tokenize("A→B")
        flow_tokens = [t for t in tokens if t.type == TokenType.FLOW]
        assert len(flow_tokens) == 1
        assert flow_tokens[0].value == "→"

    def test_synthesis_remains_operator(self):
        """⊕ (U+2295) should remain SYNTHESIS operator."""
        tokens, _ = tokenize("A⊕B")
        synth_tokens = [t for t in tokens if t.type == TokenType.SYNTHESIS]
        assert len(synth_tokens) == 1

    def test_tension_remains_operator(self):
        """⇌ (U+21CC) should remain TENSION operator."""
        tokens, _ = tokenize("A⇌B")
        tension_tokens = [t for t in tokens if t.type == TokenType.TENSION]
        assert len(tension_tokens) == 1

    def test_constraint_remains_operator(self):
        """∧ (U+2227) should remain CONSTRAINT operator."""
        tokens, _ = tokenize("[A∧B]")
        constraint_tokens = [t for t in tokens if t.type == TokenType.CONSTRAINT]
        assert len(constraint_tokens) == 1

    def test_alternative_remains_operator(self):
        """∨ (U+2228) should remain ALTERNATIVE operator."""
        tokens, _ = tokenize("[A∨B]")
        alt_tokens = [t for t in tokens if t.type == TokenType.ALTERNATIVE]
        assert len(alt_tokens) == 1

    def test_section_remains_operator(self):
        """§ (U+00A7) should remain SECTION operator."""
        tokens, _ = tokenize("§1::OVERVIEW")
        section_tokens = [t for t in tokens if t.type == TokenType.SECTION]
        assert len(section_tokens) == 1

    def test_concat_remains_operator(self):
        """⧺ (U+29FA) should remain CONCAT operator."""
        tokens, _ = tokenize("A⧺B")
        concat_tokens = [t for t in tokens if t.type == TokenType.CONCAT]
        assert len(concat_tokens) == 1


class TestMultiCodepointEmoji:
    """Test handling of multi-codepoint emoji (ZWJ sequences, skin tones).

    Multi-codepoint emoji like 👨‍👩‍👧‍👦 (family) or 👍🏽 (thumbs up with skin tone)
    consist of multiple Unicode codepoints joined by ZWJ or modifiers.

    Approach: We support what Python's regex can reasonably handle.
    Complex ZWJ sequences may split into components, which is acceptable.
    """

    def test_simple_emoji_with_variation_selector(self):
        """Warning sign with variation selector (⚠️ = U+26A0 U+FE0F)."""
        tokens, _ = tokenize("⚠️::warning")
        assert tokens[0].type == TokenType.IDENTIFIER
        # Should preserve the full sequence including variation selector
        assert "⚠" in tokens[0].value

    def test_emoji_with_skin_tone_modifier(self):
        """Emoji with skin tone modifier should work reasonably.

        Note: Behavior with skin tones may vary. The key is no crash.
        """
        # 👍🏽 = U+1F44D U+1F3FD (thumbs up + medium skin tone)
        try:
            tokens, _ = tokenize("👍🏽::approved")
            # If it works, first token should be an identifier
            assert tokens[0].type == TokenType.IDENTIFIER
        except LexerError:
            # If it raises, that's acceptable for complex emoji
            # as long as the error is clear
            pytest.skip("Skin tone modifiers not supported in identifiers")

    def test_zwj_sequence_family_emoji(self):
        """Family emoji (ZWJ sequence) should be handled gracefully.

        Note: ZWJ sequences are complex. We document limited support.
        """
        # 👨‍👩‍👧 = man + ZWJ + woman + ZWJ + girl
        try:
            tokens, _ = tokenize("👨‍👩‍👧::family_group")
            # If it works, check it doesn't crash
            assert tokens[0].type == TokenType.IDENTIFIER
        except LexerError:
            # ZWJ sequences may not be fully supported
            pytest.skip("ZWJ emoji sequences not supported in identifiers")

    def test_flag_emoji(self):
        """Flag emoji (regional indicator pairs) may have limited support."""
        # 🇺🇸 = U+1F1FA U+1F1F8 (US flag)
        try:
            tokens, _ = tokenize("🇺🇸::country")
            assert tokens[0].type == TokenType.IDENTIFIER
        except LexerError:
            pytest.skip("Flag emoji not supported in identifiers")


class TestEmojiInValues:
    """Test emoji work in value positions (strings, identifiers)."""

    def test_emoji_in_quoted_string(self):
        """Emoji should work fine in quoted strings."""
        tokens, _ = tokenize('MESSAGE::"Status: ⚠️ Warning"')
        string_token = [t for t in tokens if t.type == TokenType.STRING][0]
        assert "⚠️" in string_token.value

    def test_emoji_in_list_values(self):
        """Emoji identifiers should work as list values."""
        tokens, _ = tokenize("ICONS::[⭐, 🔥, ✓]")
        identifiers = [t for t in tokens if t.type == TokenType.IDENTIFIER and ord(t.value[0]) > 127]
        assert len(identifiers) >= 3

    def test_emoji_after_flow_operator(self):
        """Emoji should work after flow operator."""
        tokens, _ = tokenize("START→⚠️→END")
        identifiers = [t for t in tokens if t.type == TokenType.IDENTIFIER]
        assert len(identifiers) == 3
        assert "⚠️" in [t.value for t in identifiers]


class TestEmojiEdgeCases:
    """Test edge cases and boundary conditions for emoji support."""

    def test_emoji_only_identifier(self):
        """Single emoji should be valid identifier."""
        tokens, _ = tokenize("⚠️")
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "⚠️"

    def test_emoji_with_numbers(self):
        """Emoji followed by numbers should work."""
        tokens, _ = tokenize("⚠️123::warning_level")
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "⚠️123"

    def test_number_followed_by_emoji_is_merged_identifier(self):
        """GH#356: Numbers immediately followed by emoji merge into single IDENTIFIER.

        In OCTAVE, 123⚠️ (no whitespace) is merged into IDENTIFIER("123⚠️")
        to prevent space insertion during canonicalization (I1 SYNTACTIC_FIDELITY).
        If the user wants them separate, they should write "123 ⚠️" with a space.
        """
        tokens, _ = tokenize("123⚠️")
        # GH#356: Should be a single IDENTIFIER token (merged at lexer level)
        identifier_tokens = [t for t in tokens if t.type == TokenType.IDENTIFIER]
        number_tokens = [t for t in tokens if t.type == TokenType.NUMBER]
        assert len(identifier_tokens) == 1
        assert identifier_tokens[0].value == "123⚠️"
        assert len(number_tokens) == 0

    def test_emoji_does_not_break_line_tracking(self):
        """Multi-byte emoji should not break line/column tracking."""
        content = """LINE1::⚠️
LINE2::value"""
        tokens, _ = tokenize(content)
        line2_tokens = [t for t in tokens if t.line == 2]
        assert len(line2_tokens) > 0
        line2_identifier = [t for t in line2_tokens if t.type == TokenType.IDENTIFIER][0]
        assert line2_identifier.value == "LINE2"
        assert line2_identifier.column == 1

    def test_emoji_column_tracking(self):
        """Column tracking should work correctly with emoji."""
        tokens, _ = tokenize("⚠️::value")
        assign_token = [t for t in tokens if t.type == TokenType.ASSIGN][0]
        # ⚠️ may be 1 or 2 characters depending on variation selector
        # The key is that column is >= 2 (after the emoji)
        assert assign_token.column >= 2

    def test_emoji_in_complex_expression(self):
        """Emoji should work in complex OCTAVE expressions."""
        # Note: Use @ symbol for AT operator, not "AT" word
        content = "⚠️::@[ARM.result]→MUST_READ[skill_selectors]"
        tokens, _ = tokenize(content)
        # Should tokenize without error
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "⚠️"
        # Should have AT token (@ symbol)
        at_tokens = [t for t in tokens if t.type == TokenType.AT]
        assert len(at_tokens) >= 1
        # Should have FLOW token
        flow_tokens = [t for t in tokens if t.type == TokenType.FLOW]
        assert len(flow_tokens) >= 1

    def test_nfc_normalization_preserves_emoji(self):
        """NFC normalization should not break emoji."""
        # Some emoji may have different normalization forms
        content = "⚠️::test"
        normalized_content = unicodedata.normalize("NFC", content)
        tokens, _ = tokenize(normalized_content)
        assert tokens[0].type == TokenType.IDENTIFIER


class TestMythicCompressionStyle:
    """Integration tests for mythic compression patterns.

    These test real-world usage patterns from OCTAVE mythic compression.
    """

    def test_warning_annotation(self):
        """Warning annotation pattern from issue #186."""
        content = "⚠️::AT[ARM.result]→MUST_READ[skill_selectors]"
        tokens, _ = tokenize(content)
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "⚠️"

    def test_status_indicators(self):
        """Status indicator pattern."""
        content = "STATUS::[✓_complete, ⚠️_warning, ✗_failed]"
        tokens, _ = tokenize(content)
        identifiers = [t for t in tokens if t.type == TokenType.IDENTIFIER]
        # Should have STATUS and three status indicators
        assert len([t for t in identifiers if t.value.startswith("✓")]) >= 1
        assert len([t for t in identifiers if "⚠️" in t.value]) >= 1
        assert len([t for t in identifiers if t.value.startswith("✗")]) >= 1

    def test_priority_markers(self):
        """Priority marker pattern."""
        content = """⭐::high_priority
🔥::critical_priority
📌::pinned"""
        tokens, _ = tokenize(content)
        emoji_identifiers = [t for t in tokens if t.type == TokenType.IDENTIFIER and ord(t.value[0]) > 127]
        assert len(emoji_identifiers) >= 3

    def test_section_with_emoji_marker(self):
        """Section with emoji marker should work."""
        content = "§1::⚠️_WARNINGS"
        tokens, _ = tokenize(content)
        section_tokens = [t for t in tokens if t.type == TokenType.SECTION]
        assert len(section_tokens) == 1
        # The value after section should be an identifier with emoji
        identifiers = [t for t in tokens if t.type == TokenType.IDENTIFIER]
        emoji_ids = [t for t in identifiers if "⚠️" in t.value]
        assert len(emoji_ids) >= 1
