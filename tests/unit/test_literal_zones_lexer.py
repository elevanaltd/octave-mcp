"""Tests for literal zone lexer additions (Issue #235, T03 + T04).

T03: TokenType entries (FENCE_OPEN, FENCE_CLOSE, LITERAL_CONTENT) and FENCE_PATTERN regex.
T04: _evaluate_fence_line() precedence logic with B0-B1 amendment.
"""

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
