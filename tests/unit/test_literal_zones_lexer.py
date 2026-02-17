"""Tests for literal zone lexer additions (Issue #235, T03 + T04 + T05).

T03: TokenType entries (FENCE_OPEN, FENCE_CLOSE, LITERAL_CONTENT) and FENCE_PATTERN regex.
T04: _evaluate_fence_line() precedence logic with B0-B1 amendment.
T05: _normalize_with_fence_detection() single-pass NFC bypass and fence span tracking.
"""

import unicodedata

import pytest

# ---------------------------------------------------------------------------
# T03: TokenType enum entries
# ---------------------------------------------------------------------------


class TestTokenTypeEntries:
    """Verify new TokenType enum members exist and have values."""

    def test_fence_open_exists(self) -> None:
        from octave_mcp.core.lexer import TokenType

        assert hasattr(TokenType, "FENCE_OPEN")
        assert TokenType.FENCE_OPEN.value is not None

    def test_fence_close_exists(self) -> None:
        from octave_mcp.core.lexer import TokenType

        assert hasattr(TokenType, "FENCE_CLOSE")
        assert TokenType.FENCE_CLOSE.value is not None

    def test_literal_content_exists(self) -> None:
        from octave_mcp.core.lexer import TokenType

        assert hasattr(TokenType, "LITERAL_CONTENT")
        assert TokenType.LITERAL_CONTENT.value is not None

    def test_all_three_are_distinct(self) -> None:
        from octave_mcp.core.lexer import TokenType

        values = {
            TokenType.FENCE_OPEN.value,
            TokenType.FENCE_CLOSE.value,
            TokenType.LITERAL_CONTENT.value,
        }
        assert len(values) == 3, "All three token types must have distinct values"


# ---------------------------------------------------------------------------
# T03: FENCE_PATTERN regex
# ---------------------------------------------------------------------------


class TestFencePattern:
    """Verify FENCE_PATTERN regex matches and rejects correctly."""

    def test_three_backticks(self) -> None:
        from octave_mcp.core.lexer import FENCE_PATTERN

        m = FENCE_PATTERN.match("```")
        assert m is not None
        assert m.group(3) == "```"

    def test_three_backticks_with_info_tag(self) -> None:
        from octave_mcp.core.lexer import FENCE_PATTERN

        m = FENCE_PATTERN.match("```python")
        assert m is not None
        assert m.group(3) == "```"
        assert m.group(4).strip() == "python"

    def test_four_backticks(self) -> None:
        from octave_mcp.core.lexer import FENCE_PATTERN

        m = FENCE_PATTERN.match("````")
        assert m is not None
        assert m.group(3) == "````"

    def test_four_backticks_with_info_tag(self) -> None:
        from octave_mcp.core.lexer import FENCE_PATTERN

        m = FENCE_PATTERN.match("````python")
        assert m is not None
        assert m.group(3) == "````"

    def test_two_spaces_indent(self) -> None:
        from octave_mcp.core.lexer import FENCE_PATTERN

        m = FENCE_PATTERN.match("  ```python")
        assert m is not None
        assert m.group(1) == "  "
        assert m.group(3) == "```"

    def test_three_spaces_indent_allowed(self) -> None:
        from octave_mcp.core.lexer import FENCE_PATTERN

        m = FENCE_PATTERN.match("   ```")
        assert m is not None
        assert m.group(1) == "   "

    def test_four_spaces_indent_rejected(self) -> None:
        from octave_mcp.core.lexer import FENCE_PATTERN

        m = FENCE_PATTERN.match("    ```")
        assert m is None

    def test_two_backticks_rejected(self) -> None:
        from octave_mcp.core.lexer import FENCE_PATTERN

        m = FENCE_PATTERN.match("``")
        assert m is None

    def test_text_before_backticks_rejected(self) -> None:
        from octave_mcp.core.lexer import FENCE_PATTERN

        m = FENCE_PATTERN.match("text ```")
        assert m is None

    def test_backtick_in_info_tag_rejected(self) -> None:
        """Info tag must not contain backticks (per CommonMark spec)."""
        from octave_mcp.core.lexer import FENCE_PATTERN

        m = FENCE_PATTERN.match("```py`thon")
        # The pattern should either not match or not capture the backtick in group 4
        if m is not None:
            assert "`" not in m.group(4)


# ---------------------------------------------------------------------------
# T04: _evaluate_fence_line() precedence logic
# ---------------------------------------------------------------------------


class TestEvaluateFenceLine:
    """Verify fence precedence: close BEFORE error (B0-B1 amendment)."""

    def test_case1_exact_match_clean_line_returns_close(self) -> None:
        """Equal length, no trailing content -> 'close'."""
        from octave_mcp.core.lexer import _evaluate_fence_line

        result = _evaluate_fence_line(
            backtick_seq="```",
            open_fence_marker="```",
            trailing_content="",
            line=5,
            column=1,
            open_line=1,
        )
        assert result == "close"

    def test_case1b_exact_match_trailing_whitespace_returns_close(self) -> None:
        """Equal length, trailing whitespace only -> 'close'."""
        from octave_mcp.core.lexer import _evaluate_fence_line

        result = _evaluate_fence_line(
            backtick_seq="```",
            open_fence_marker="```",
            trailing_content="   ",
            line=5,
            column=1,
            open_line=1,
        )
        assert result == "close"

    def test_case2_exact_match_trailing_content_raises_e007(self) -> None:
        """Equal length WITH trailing non-whitespace -> raises LexerError E007."""
        from octave_mcp.core.lexer import LexerError, _evaluate_fence_line

        with pytest.raises(LexerError) as exc_info:
            _evaluate_fence_line(
                backtick_seq="```",
                open_fence_marker="```",
                trailing_content="python",
                line=5,
                column=1,
                open_line=1,
            )
        assert "E007" in str(exc_info.value)

    def test_case3_greater_length_raises_e007(self) -> None:
        """Greater length fence -> raises LexerError E007."""
        from octave_mcp.core.lexer import LexerError, _evaluate_fence_line

        with pytest.raises(LexerError) as exc_info:
            _evaluate_fence_line(
                backtick_seq="````",
                open_fence_marker="```",
                trailing_content="",
                line=5,
                column=1,
                open_line=1,
            )
        assert "E007" in str(exc_info.value)

    def test_case4_shorter_length_returns_content(self) -> None:
        """Shorter fence -> 'content'."""
        from octave_mcp.core.lexer import _evaluate_fence_line

        result = _evaluate_fence_line(
            backtick_seq="```",
            open_fence_marker="````",
            trailing_content="",
            line=5,
            column=1,
            open_line=1,
        )
        assert result == "content"

    def test_e007_message_contains_nested_fence(self) -> None:
        """E007 error message mentions nested literal zone."""
        from octave_mcp.core.lexer import LexerError, _evaluate_fence_line

        with pytest.raises(LexerError) as exc_info:
            _evaluate_fence_line(
                backtick_seq="````",
                open_fence_marker="```",
                trailing_content="",
                line=5,
                column=1,
                open_line=1,
            )
        error = exc_info.value
        assert "E007_NESTED_FENCE" in error.message
        assert "Nested literal zone" in error.message

    def test_e007_message_contains_educational_guidance(self) -> None:
        """E007 error message includes fence scaling guidance (I3)."""
        from octave_mcp.core.lexer import LexerError, _evaluate_fence_line

        with pytest.raises(LexerError) as exc_info:
            _evaluate_fence_line(
                backtick_seq="````",
                open_fence_marker="```",
                trailing_content="",
                line=5,
                column=1,
                open_line=1,
            )
        error = exc_info.value
        assert "Use a longer fence" in error.message
        assert "````" in error.message  # Suggests scaling up

    def test_e007_message_contains_open_line_number(self) -> None:
        """E007 error message references the line where the outer fence opened."""
        from octave_mcp.core.lexer import LexerError, _evaluate_fence_line

        with pytest.raises(LexerError) as exc_info:
            _evaluate_fence_line(
                backtick_seq="````",
                open_fence_marker="```",
                trailing_content="",
                line=10,
                column=1,
                open_line=3,
            )
        error = exc_info.value
        assert "line 3" in error.message

    def test_e007_error_code_is_e007(self) -> None:
        """LexerError.error_code is 'E007'."""
        from octave_mcp.core.lexer import LexerError, _evaluate_fence_line

        with pytest.raises(LexerError) as exc_info:
            _evaluate_fence_line(
                backtick_seq="````",
                open_fence_marker="```",
                trailing_content="",
                line=5,
                column=1,
                open_line=1,
            )
        assert exc_info.value.error_code == "E007"

    def test_precedence_close_before_error(self) -> None:
        """CRITICAL: Exact match with clean line CLOSES, does NOT error.

        This tests the B0-B1 amendment requirement: closing fence check
        must happen BEFORE the nested fence error check.
        """
        from octave_mcp.core.lexer import _evaluate_fence_line

        # If precedence is wrong, this would raise E007 instead of returning "close"
        result = _evaluate_fence_line(
            backtick_seq="```",
            open_fence_marker="```",
            trailing_content="",
            line=5,
            column=1,
            open_line=1,
        )
        assert result == "close"

    def test_four_backtick_fence_close(self) -> None:
        """4-backtick fence closes correctly with exact match."""
        from octave_mcp.core.lexer import _evaluate_fence_line

        result = _evaluate_fence_line(
            backtick_seq="````",
            open_fence_marker="````",
            trailing_content="",
            line=5,
            column=1,
            open_line=1,
        )
        assert result == "close"

    def test_shorter_three_inside_four_is_content(self) -> None:
        """3-backtick sequence inside 4-backtick fence is content."""
        from octave_mcp.core.lexer import _evaluate_fence_line

        result = _evaluate_fence_line(
            backtick_seq="```",
            open_fence_marker="````",
            trailing_content="python",
            line=5,
            column=1,
            open_line=1,
        )
        assert result == "content"


# ---------------------------------------------------------------------------
# T05: _normalize_with_fence_detection() single-pass approach
# ---------------------------------------------------------------------------


class TestNormalizeWithFenceDetectionBasic:
    """Basic behavior of _normalize_with_fence_detection()."""

    def test_no_fences_returns_nfc_normalized(self) -> None:
        """Document with no fences: entire content is NFC-normalized."""
        from octave_mcp.core.lexer import _normalize_with_fence_detection

        content = "hello world"
        result, spans = _normalize_with_fence_detection(content)
        assert result == unicodedata.normalize("NFC", content)
        assert spans == []

    def test_no_fences_empty_spans(self) -> None:
        """Document with no fences: empty spans list returned."""
        from octave_mcp.core.lexer import _normalize_with_fence_detection

        _, spans = _normalize_with_fence_detection("just some text\nand more")
        assert spans == []

    def test_simple_fence_returns_span(self) -> None:
        """Simple document with one fence: correct span returned."""
        from octave_mcp.core.lexer import _normalize_with_fence_detection

        content = "before\n```\nhello\n```\nafter"
        result, spans = _normalize_with_fence_detection(content)
        assert len(spans) == 1
        # Span should be valid for the returned string
        start, end, marker, tag = spans[0]
        assert marker == "```"
        assert tag is None
        # Verify the span covers from the opening fence through closing fence
        span_text = result[start:end]
        assert "```" in span_text
        assert "hello" in span_text

    def test_nfc_applied_outside_fence(self) -> None:
        """NFC-sensitive characters outside a fence are normalized."""
        from octave_mcp.core.lexer import _normalize_with_fence_detection

        # U+0065 (e) + U+0301 (combining acute) = decomposed e-acute
        decomposed = "e\u0301"  # NFD form
        precomposed = "\u00e9"  # NFC form (e-acute)
        content = f"{decomposed}\n```\nhello\n```"
        result, _ = _normalize_with_fence_detection(content)
        # Outside fence: decomposed form should be NFC-normalized to precomposed
        assert result.startswith(precomposed)

    def test_nfc_not_applied_inside_fence(self) -> None:
        """NFC-sensitive characters inside a fence are preserved as-is (NFD preserved)."""
        from octave_mcp.core.lexer import _normalize_with_fence_detection

        # U+0065 (e) + U+0301 (combining acute) = decomposed e-acute
        decomposed = "e\u0301"
        content = f"```\n{decomposed}\n```"
        result, spans = _normalize_with_fence_detection(content)
        # Inside fence: decomposed form should be preserved verbatim
        assert decomposed in result

    def test_precomposed_outside_fence_normalized(self) -> None:
        """U+00E9 outside fence -> normalized to precomposed form."""
        from octave_mcp.core.lexer import _normalize_with_fence_detection

        # Already precomposed, NFC is idempotent
        content = "\u00e9 hello"
        result, _ = _normalize_with_fence_detection(content)
        assert "\u00e9" in result

    def test_decomposed_inside_fence_preserved(self) -> None:
        """U+0065 U+0301 (decomposed e-acute) inside fence preserved as-is."""
        from octave_mcp.core.lexer import _normalize_with_fence_detection

        decomposed = "e\u0301"  # Two codepoints
        content = f"```\n{decomposed}\n```"
        result, _ = _normalize_with_fence_detection(content)
        # The decomposed form must survive -- it should NOT become \u00e9
        # Verify by checking the actual codepoints are preserved
        lines = result.split("\n")
        content_line = lines[1]  # The line between fences
        assert content_line == decomposed
        assert len(content_line) == 2  # Two codepoints, not one


class TestNormalizeWithFenceDetectionSpanOffsets:
    """Verify fence span offsets are valid for the RETURNED string."""

    def test_span_offsets_valid_for_returned_string(self) -> None:
        """Fence span offsets must index correctly into the returned string."""
        from octave_mcp.core.lexer import _normalize_with_fence_detection

        content = "before\n```python\nhello world\n```\nafter"
        result, spans = _normalize_with_fence_detection(content)
        assert len(spans) == 1
        start, end, marker, tag = spans[0]
        # Extract the span from the returned string
        span_text = result[start:end]
        # Must contain opening fence, content, and closing fence
        assert "```python" in span_text or "```" in span_text
        assert "hello world" in span_text

    def test_span_offsets_with_nfc_length_change(self) -> None:
        """When NFC changes string length outside fence, offsets still valid.

        This is the CRITICAL SINGLE-PASS INVARIANT test: offsets must be
        valid for the returned normalized string, not the original input.
        """
        from octave_mcp.core.lexer import _normalize_with_fence_detection

        # Decomposed e-acute (2 codepoints) outside fence becomes precomposed (1 codepoint)
        decomposed = "e\u0301"  # 2 codepoints
        content = f"{decomposed}\n```\ncontent\n```"
        result, spans = _normalize_with_fence_detection(content)

        assert len(spans) == 1
        start, end, marker, tag = spans[0]

        # The NFC normalization shortened the first line by 1 codepoint
        # Verify offsets are for the RETURNED string (post-NFC)
        span_text = result[start:end]
        assert "content" in span_text
        assert result[:start].endswith("\n") or start == 0

    def test_info_tag_captured(self) -> None:
        """Info tag is captured in the span tuple."""
        from octave_mcp.core.lexer import _normalize_with_fence_detection

        content = "```python\nhello\n```"
        _, spans = _normalize_with_fence_detection(content)
        assert len(spans) == 1
        _, _, marker, tag = spans[0]
        assert marker == "```"
        assert tag == "python"

    def test_info_tag_none_when_absent(self) -> None:
        """Info tag is None when no tag provided."""
        from octave_mcp.core.lexer import _normalize_with_fence_detection

        content = "```\nhello\n```"
        _, spans = _normalize_with_fence_detection(content)
        assert len(spans) == 1
        _, _, _, tag = spans[0]
        assert tag is None

    def test_info_tag_stripped(self) -> None:
        """Info tag has trailing whitespace stripped."""
        from octave_mcp.core.lexer import _normalize_with_fence_detection

        content = "```python   \nhello\n```"
        _, spans = _normalize_with_fence_detection(content)
        _, _, _, tag = spans[0]
        assert tag == "python"


class TestNormalizeWithFenceDetectionErrors:
    """Error cases for _normalize_with_fence_detection()."""

    def test_unterminated_fence_raises_e006(self) -> None:
        """Fence opened but never closed raises E006."""
        from octave_mcp.core.lexer import LexerError, _normalize_with_fence_detection

        content = "```python\nhello\nworld"
        with pytest.raises(LexerError) as exc_info:
            _normalize_with_fence_detection(content)
        assert exc_info.value.error_code == "E006"

    def test_e006_message_contains_fence_marker(self) -> None:
        """E006 error message contains the fence marker."""
        from octave_mcp.core.lexer import LexerError, _normalize_with_fence_detection

        content = "````python\nhello"
        with pytest.raises(LexerError) as exc_info:
            _normalize_with_fence_detection(content)
        assert "````" in str(exc_info.value)

    def test_e006_message_contains_open_line(self) -> None:
        """E006 error message contains the line number where fence opened."""
        from octave_mcp.core.lexer import LexerError, _normalize_with_fence_detection

        content = "before\n```\nhello"
        with pytest.raises(LexerError) as exc_info:
            _normalize_with_fence_detection(content)
        assert "line 2" in str(exc_info.value)

    def test_nested_fence_equal_length_raises_e007(self) -> None:
        """Equal length fence inside open fence raises E007."""
        from octave_mcp.core.lexer import LexerError, _normalize_with_fence_detection

        content = "```\n```python\nhello\n```"
        with pytest.raises(LexerError) as exc_info:
            _normalize_with_fence_detection(content)
        assert exc_info.value.error_code == "E007"

    def test_nested_fence_longer_raises_e007(self) -> None:
        """Longer fence inside open fence raises E007."""
        from octave_mcp.core.lexer import LexerError, _normalize_with_fence_detection

        content = "```\n````\nhello\n```"
        with pytest.raises(LexerError) as exc_info:
            _normalize_with_fence_detection(content)
        assert exc_info.value.error_code == "E007"

    def test_shorter_fence_inside_is_content(self) -> None:
        """Shorter fence inside open fence treated as content (not error)."""
        from octave_mcp.core.lexer import _normalize_with_fence_detection

        content = "````\n```\nhello\n````"
        result, spans = _normalize_with_fence_detection(content)
        assert len(spans) == 1
        # The ``` inside should be preserved as content
        start, end, _, _ = spans[0]
        span_text = result[start:end]
        assert "```" in span_text


class TestNormalizeWithFenceDetectionMultiple:
    """Multiple literal zones and edge cases."""

    def test_multiple_fences(self) -> None:
        """Multiple literal zones in one document."""
        from octave_mcp.core.lexer import _normalize_with_fence_detection

        content = "```\nfirst\n```\nbetween\n```\nsecond\n```"
        result, spans = _normalize_with_fence_detection(content)
        assert len(spans) == 2
        # Verify both spans are valid
        for start, end, marker, _tag in spans:
            assert marker == "```"
            span_text = result[start:end]
            assert "```" in span_text

    def test_empty_literal_zone(self) -> None:
        """Empty literal zone: opening fence immediately followed by closing fence."""
        from octave_mcp.core.lexer import _normalize_with_fence_detection

        content = "```\n```"
        result, spans = _normalize_with_fence_detection(content)
        assert len(spans) == 1
        start, end, marker, tag = spans[0]
        assert marker == "```"

    def test_idempotent_without_fences(self) -> None:
        """Round-trip: result is idempotent for content without literal zones."""
        from octave_mcp.core.lexer import _normalize_with_fence_detection

        content = "hello world\nline two"
        result1, _ = _normalize_with_fence_detection(content)
        result2, _ = _normalize_with_fence_detection(result1)
        assert result1 == result2

    def test_fence_marker_four_backticks(self) -> None:
        """4-backtick fence marker correctly tracked."""
        from octave_mcp.core.lexer import _normalize_with_fence_detection

        content = "````python\nhello\n````"
        _, spans = _normalize_with_fence_detection(content)
        assert len(spans) == 1
        _, _, marker, tag = spans[0]
        assert marker == "````"
        assert tag == "python"


# ---------------------------------------------------------------------------
# T06: tokenize() wiring — token emission + tab bypass
# ---------------------------------------------------------------------------


class TestTokenizeTabBypass:
    """Tab bypass: tabs inside literal zones do NOT raise E005."""

    def test_tab_inside_literal_zone_does_not_raise(self) -> None:
        """Tabs inside a literal zone must NOT raise E005."""
        from octave_mcp.core.lexer import tokenize

        content = "```\n\thello\n```"
        tokens, _ = tokenize(content)
        # Should succeed without raising LexerError
        types = [t.type.name for t in tokens]
        assert "FENCE_OPEN" in types

    def test_tab_outside_literal_zone_still_raises_e005(self) -> None:
        """Tabs outside literal zones must still raise E005."""
        from octave_mcp.core.lexer import LexerError, tokenize

        content = "\thello"
        with pytest.raises(LexerError) as exc_info:
            tokenize(content)
        assert exc_info.value.error_code == "E005"

    def test_tab_before_literal_zone_raises_e005(self) -> None:
        """Tab on a line before the literal zone raises E005."""
        from octave_mcp.core.lexer import LexerError, tokenize

        content = "\tbad\n```\n\tok inside\n```"
        with pytest.raises(LexerError) as exc_info:
            tokenize(content)
        assert exc_info.value.error_code == "E005"

    def test_tab_after_literal_zone_raises_e005(self) -> None:
        """Tab on a line after the literal zone raises E005."""
        from octave_mcp.core.lexer import LexerError, tokenize

        content = "```\n\tok inside\n```\n\tbad"
        with pytest.raises(LexerError) as exc_info:
            tokenize(content)
        assert exc_info.value.error_code == "E005"

    def test_mixed_tabs_and_spaces_inside_literal_zone_preserved(self) -> None:
        """Mixed tabs and spaces inside literal zone are preserved."""
        from octave_mcp.core.lexer import TokenType, tokenize

        content = "```\n\t  mixed\t\n```"
        tokens, _ = tokenize(content)
        literal_tokens = [t for t in tokens if t.type == TokenType.LITERAL_CONTENT]
        assert len(literal_tokens) == 1
        assert "\t" in literal_tokens[0].value


class TestTokenizeFenceTokenEmission:
    """Token emission: FENCE_OPEN, LITERAL_CONTENT, FENCE_CLOSE."""

    def test_simple_literal_zone_emits_three_tokens(self) -> None:
        """A simple literal zone emits FENCE_OPEN, LITERAL_CONTENT, FENCE_CLOSE."""
        from octave_mcp.core.lexer import TokenType, tokenize

        content = "```\nhello\n```"
        tokens, _ = tokenize(content)
        types = [t.type for t in tokens]
        assert TokenType.FENCE_OPEN in types
        assert TokenType.LITERAL_CONTENT in types
        assert TokenType.FENCE_CLOSE in types

    def test_fence_open_value_is_dict(self) -> None:
        """FENCE_OPEN token value is a dict with fence_marker and info_tag."""
        from octave_mcp.core.lexer import TokenType, tokenize

        content = "```python\nhello\n```"
        tokens, _ = tokenize(content)
        fence_open = next(t for t in tokens if t.type == TokenType.FENCE_OPEN)
        assert isinstance(fence_open.value, dict)
        assert fence_open.value["fence_marker"] == "```"
        assert fence_open.value["info_tag"] == "python"

    def test_fence_open_info_tag_none_when_absent(self) -> None:
        """FENCE_OPEN info_tag is None when no tag provided."""
        from octave_mcp.core.lexer import TokenType, tokenize

        content = "```\nhello\n```"
        tokens, _ = tokenize(content)
        fence_open = next(t for t in tokens if t.type == TokenType.FENCE_OPEN)
        assert fence_open.value["info_tag"] is None

    def test_literal_content_is_raw_string(self) -> None:
        """LITERAL_CONTENT token value is the raw content string."""
        from octave_mcp.core.lexer import TokenType, tokenize

        content = "```\nhello world\n```"
        tokens, _ = tokenize(content)
        literal = next(t for t in tokens if t.type == TokenType.LITERAL_CONTENT)
        assert literal.value == "hello world"

    def test_fence_close_value_is_marker(self) -> None:
        """FENCE_CLOSE token value is the fence marker string."""
        from octave_mcp.core.lexer import TokenType, tokenize

        content = "```\nhello\n```"
        tokens, _ = tokenize(content)
        fence_close = next(t for t in tokens if t.type == TokenType.FENCE_CLOSE)
        assert fence_close.value == "```"

    def test_empty_literal_zone(self) -> None:
        """Empty literal zone produces empty LITERAL_CONTENT."""
        from octave_mcp.core.lexer import TokenType, tokenize

        content = "```\n```"
        tokens, _ = tokenize(content)
        types = [t.type for t in tokens]
        assert TokenType.FENCE_OPEN in types
        assert TokenType.FENCE_CLOSE in types
        # Empty literal zone may or may not have LITERAL_CONTENT with empty string
        literal_tokens = [t for t in tokens if t.type == TokenType.LITERAL_CONTENT]
        if literal_tokens:
            assert literal_tokens[0].value == ""

    def test_four_backtick_fence(self) -> None:
        """4-backtick fence: FENCE_OPEN has fence_marker='````'."""
        from octave_mcp.core.lexer import TokenType, tokenize

        content = "````\nhello\n````"
        tokens, _ = tokenize(content)
        fence_open = next(t for t in tokens if t.type == TokenType.FENCE_OPEN)
        assert fence_open.value["fence_marker"] == "````"

    def test_multiple_literal_zones(self) -> None:
        """Multiple literal zones tokenize correctly."""
        from octave_mcp.core.lexer import TokenType, tokenize

        content = "```\nfirst\n```\n```\nsecond\n```"
        tokens, _ = tokenize(content)
        fence_opens = [t for t in tokens if t.type == TokenType.FENCE_OPEN]
        fence_closes = [t for t in tokens if t.type == TokenType.FENCE_CLOSE]
        literals = [t for t in tokens if t.type == TokenType.LITERAL_CONTENT]
        assert len(fence_opens) == 2
        assert len(fence_closes) == 2
        assert len(literals) == 2
        assert literals[0].value == "first"
        assert literals[1].value == "second"

    def test_literal_zone_with_info_tag(self) -> None:
        """Info tag is captured in FENCE_OPEN token."""
        from octave_mcp.core.lexer import TokenType, tokenize

        content = '```json\n{"key": "value"}\n```'
        tokens, _ = tokenize(content)
        fence_open = next(t for t in tokens if t.type == TokenType.FENCE_OPEN)
        assert fence_open.value["info_tag"] == "json"

    def test_multiline_literal_content(self) -> None:
        """Multi-line content inside literal zone is preserved."""
        from octave_mcp.core.lexer import TokenType, tokenize

        content = "```\nline1\nline2\nline3\n```"
        tokens, _ = tokenize(content)
        literal = next(t for t in tokens if t.type == TokenType.LITERAL_CONTENT)
        assert literal.value == "line1\nline2\nline3"


class TestTokenizeFenceLineTracking:
    """Line numbers on fence tokens are correct."""

    def test_fence_open_line_number(self) -> None:
        """FENCE_OPEN token has correct line number."""
        from octave_mcp.core.lexer import TokenType, tokenize

        content = "```\nhello\n```"
        tokens, _ = tokenize(content)
        fence_open = next(t for t in tokens if t.type == TokenType.FENCE_OPEN)
        assert fence_open.line == 1

    def test_fence_open_at_line_3(self) -> None:
        """FENCE_OPEN on line 3 (after two lines of normal content)."""
        from octave_mcp.core.lexer import TokenType, tokenize

        content = "KEY::value\nKEY2::value2\n```\nhello\n```"
        tokens, _ = tokenize(content)
        fence_open = next(t for t in tokens if t.type == TokenType.FENCE_OPEN)
        assert fence_open.line == 3

    def test_literal_content_line_number(self) -> None:
        """LITERAL_CONTENT token has correct line number (line after FENCE_OPEN)."""
        from octave_mcp.core.lexer import TokenType, tokenize

        content = "```\nhello\n```"
        tokens, _ = tokenize(content)
        literal = next(t for t in tokens if t.type == TokenType.LITERAL_CONTENT)
        assert literal.line == 2

    def test_fence_close_line_number(self) -> None:
        """FENCE_CLOSE token has correct line number."""
        from octave_mcp.core.lexer import TokenType, tokenize

        content = "```\nhello\n```"
        tokens, _ = tokenize(content)
        fence_close = next(t for t in tokens if t.type == TokenType.FENCE_CLOSE)
        assert fence_close.line == 3

    def test_fence_close_after_multiline_content(self) -> None:
        """FENCE_CLOSE line number correct after multi-line content."""
        from octave_mcp.core.lexer import TokenType, tokenize

        content = "```\nline1\nline2\nline3\n```"
        tokens, _ = tokenize(content)
        fence_close = next(t for t in tokens if t.type == TokenType.FENCE_CLOSE)
        assert fence_close.line == 5

    def test_tokens_after_literal_zone_have_correct_line(self) -> None:
        """Tokens after a literal zone have correct line numbers."""
        from octave_mcp.core.lexer import TokenType, tokenize

        content = "```\nhello\n```\nKEY::value"
        tokens, _ = tokenize(content)
        # Find the IDENTIFIER token for "KEY"
        key_token = next(t for t in tokens if t.type == TokenType.IDENTIFIER and t.value == "KEY")
        assert key_token.line == 4


class TestTokenizeNFCPreservationInLiteralZones:
    """NFC-sensitive content inside literal zones preserved in token value."""

    def test_nfc_sensitive_content_preserved_in_literal_token(self) -> None:
        """Decomposed e-acute inside fence: preserved in LITERAL_CONTENT value."""
        from octave_mcp.core.lexer import TokenType, tokenize

        # U+0065 (e) + U+0301 (combining acute) = decomposed e-acute
        decomposed = "e\u0301"
        content = f"```\n{decomposed}\n```"
        tokens, _ = tokenize(content)
        literal = next(t for t in tokens if t.type == TokenType.LITERAL_CONTENT)
        # The decomposed form must survive (2 codepoints, NOT normalized to 1)
        assert literal.value == decomposed
        assert len(literal.value) == 2
