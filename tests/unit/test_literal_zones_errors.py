"""Tests for E006 and E007_NESTED_FENCE error message format.

Issue #235 T16: Error Code Documentation
Blueprint: §9.1, §9.2, §9.3

Verifies that error messages are self-documenting and actionable per I3.
"""

import pytest

from octave_mcp.core.lexer import LexerError, _normalize_with_fence_detection

# ---------------------------------------------------------------------------
# E006: Unterminated literal zone
# ---------------------------------------------------------------------------


def _trigger_e006(marker: str = "```", open_line: int = 1) -> str:
    """Trigger an E006 error and return the message."""
    lines = ["```python", "def hello():", "    pass"]
    if marker != "```":
        lines[0] = f"{marker}python"
    content = "\n".join(lines)
    with pytest.raises(LexerError) as exc_info:
        _normalize_with_fence_detection(content)
    return exc_info.value.args[0]


def test_e006_message_contains_e006_code() -> None:
    """E006 error message must contain the error code 'E006'."""
    msg = _trigger_e006()
    assert "E006" in msg, f"Expected 'E006' in error message, got: {msg!r}"


def test_e006_message_contains_fence_marker() -> None:
    """E006 error message must contain the fence marker that was never closed."""
    marker = "```"
    msg = _trigger_e006(marker=marker)
    assert marker in msg, f"Expected fence marker {marker!r} in error message, got: {msg!r}"


def test_e006_message_contains_longer_fence_marker() -> None:
    """E006 error message must contain the 4-backtick fence marker."""
    marker = "````"
    content = f"{marker}python\ndef hello():\n    pass"
    with pytest.raises(LexerError) as exc_info:
        _normalize_with_fence_detection(content)
    msg = exc_info.value.args[0]
    assert marker in msg, f"Expected fence marker {marker!r} in error message, got: {msg!r}"


def test_e006_message_contains_open_line_number() -> None:
    """E006 error message must contain the line number where the fence opened."""
    # Fence opens on line 1
    content = "```python\ndef hello():\n    pass"
    with pytest.raises(LexerError) as exc_info:
        _normalize_with_fence_detection(content)
    msg = exc_info.value.args[0]
    # Line 1 should appear in the message
    assert "1" in msg, f"Expected open line number '1' in error message, got: {msg!r}"


def test_e006_message_contains_open_line_number_multiline() -> None:
    """E006 error message contains the correct line number for a fence on line 3."""
    content = "KEY::value\nANOTHER::key\n```python\ndef hello():\n    pass"
    with pytest.raises(LexerError) as exc_info:
        _normalize_with_fence_detection(content)
    msg = exc_info.value.args[0]
    assert "3" in msg, f"Expected open line number '3' in error message, got: {msg!r}"


def test_e006_message_contains_add_matching_closing_fence() -> None:
    """E006 error message must contain 'Add a matching closing fence'."""
    msg = _trigger_e006()
    assert (
        "Add a matching closing fence" in msg
    ), f"Expected 'Add a matching closing fence' in error message, got: {msg!r}"


def test_e006_error_code_attribute() -> None:
    """E006 LexerError must have error_code 'E006'."""
    content = "```python\ndef hello():\n    pass"
    with pytest.raises(LexerError) as exc_info:
        _normalize_with_fence_detection(content)
    assert exc_info.value.error_code == "E006"


# ---------------------------------------------------------------------------
# E007_NESTED_FENCE: Nested literal zone
# ---------------------------------------------------------------------------


def _trigger_e007_nested_fence(
    outer_marker: str = "```",
    inner_marker: str = "```",
) -> str:
    """Trigger an E007_NESTED_FENCE error and return the message."""
    content = f"{outer_marker}python\n{inner_marker}json\ncontent\n{outer_marker}"
    with pytest.raises(LexerError) as exc_info:
        _normalize_with_fence_detection(content)
    return exc_info.value.args[0]


def test_e007_nested_fence_message_contains_e007_code() -> None:
    """E007_NESTED_FENCE error message must contain 'E007'."""
    msg = _trigger_e007_nested_fence()
    assert "E007" in msg, f"Expected 'E007' in error message, got: {msg!r}"


def test_e007_nested_fence_message_contains_nested_literal_zone() -> None:
    """E007_NESTED_FENCE error message must contain 'Nested literal zone'."""
    msg = _trigger_e007_nested_fence()
    assert (
        "Nested literal zone" in msg or "nested literal zone" in msg.lower()
    ), f"Expected 'Nested literal zone' in error message, got: {msg!r}"


def test_e007_nested_fence_message_contains_use_a_longer_fence() -> None:
    """E007_NESTED_FENCE error message must contain 'Use a longer fence'."""
    msg = _trigger_e007_nested_fence()
    assert "Use a longer fence" in msg, f"Expected 'Use a longer fence' in error message, got: {msg!r}"


def test_e007_nested_fence_message_contains_outer_fence_marker() -> None:
    """E007_NESTED_FENCE error message must contain the outer fence marker."""
    outer_marker = "```"
    inner_marker = "```"
    msg = _trigger_e007_nested_fence(outer_marker=outer_marker, inner_marker=inner_marker)
    assert outer_marker in msg, f"Expected outer fence marker {outer_marker!r} in error message, got: {msg!r}"


def test_e007_nested_fence_message_contains_outer_longer_marker() -> None:
    """E007_NESTED_FENCE error with 4-tick outer fence includes the outer marker."""
    outer_marker = "````"
    inner_marker = "````"
    msg = _trigger_e007_nested_fence(outer_marker=outer_marker, inner_marker=inner_marker)
    assert outer_marker in msg, f"Expected outer fence marker {outer_marker!r} in error message, got: {msg!r}"


def test_e007_nested_fence_message_contains_open_line_number() -> None:
    """E007_NESTED_FENCE error message must contain the open line number."""
    # Outer fence opens on line 1; inner fence appears on line 2
    content = "```python\n```json\ncontent\n```"
    with pytest.raises(LexerError) as exc_info:
        _normalize_with_fence_detection(content)
    msg = exc_info.value.args[0]
    # Open line = 1 should be mentioned
    assert "1" in msg, f"Expected open line '1' in error message, got: {msg!r}"


def test_e007_nested_fence_longer_fence_triggers_error() -> None:
    """A longer fence inside an open fence raises E007_NESTED_FENCE."""
    # 4-backtick fence inside 3-backtick fence
    content = "```python\n````json\ncontent\n```"
    with pytest.raises(LexerError) as exc_info:
        _normalize_with_fence_detection(content)
    msg = exc_info.value.args[0]
    assert "E007" in msg
    assert "Nested literal zone" in msg or "nested" in msg.lower()


def test_e007_nested_fence_equal_length_with_trailing_content_triggers_error() -> None:
    """A same-length fence with trailing content raises E007_NESTED_FENCE."""
    # Same length fence with trailing non-whitespace = ambiguous, not a closing fence
    content = "```python\n```json\ncontent\n```"
    with pytest.raises(LexerError) as exc_info:
        _normalize_with_fence_detection(content)
    msg = exc_info.value.args[0]
    assert "E007" in msg


def test_e007_error_code_attribute() -> None:
    """E007_NESTED_FENCE LexerError must have error_code 'E007'."""
    content = "```python\n```json\ncontent\n```"
    with pytest.raises(LexerError) as exc_info:
        _normalize_with_fence_detection(content)
    assert exc_info.value.error_code == "E007"
