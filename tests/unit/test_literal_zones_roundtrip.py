"""Round-trip and pathological tests for literal zones.

Issue #235 T19: Integration + Property-Based Tests
Blueprint: §10.2

Tests end-to-end parse->emit->parse fidelity including pathological edge cases
from B0-S1 (A8 assumption validation).
"""

import pytest

from octave_mcp.core.ast_nodes import LiteralZoneValue
from octave_mcp.core.emitter import emit
from octave_mcp.core.lexer import LexerError
from octave_mcp.core.parser import parse

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_first_value(content: str) -> LiteralZoneValue:
    """Parse OCTAVE content and return the first section's value."""
    doc = parse(content)
    assert len(doc.sections) >= 1, "Document must have at least one section"
    value = doc.sections[0].value
    assert isinstance(value, LiteralZoneValue), f"Expected LiteralZoneValue, got {type(value).__name__}: {value!r}"
    return value


def _make_doc(key: str, fence: str, content: str, info_tag: str = "") -> str:
    """Build an OCTAVE document with a single literal zone assignment."""
    fence_line = f"{fence}{info_tag}"
    return f"===DOC===\n{key}::\n{fence_line}\n{content}\n{fence}\n===END==="


# ---------------------------------------------------------------------------
# Round-trip fidelity tests
# ---------------------------------------------------------------------------


def test_round_trip_literal_zone() -> None:
    """Parse -> emit -> parse produces identical content (tabs preserved)."""
    inner = 'def hello():\n\tprint("hello")  # tab preserved'
    doc_str = _make_doc("CODE", "```", inner, "python")
    doc1 = parse(doc_str)
    emitted = emit(doc1)
    doc2 = parse(emitted)
    assert doc1.sections[0].value.content == doc2.sections[0].value.content
    # Tabs specifically preserved
    assert "\t" in doc1.sections[0].value.content
    assert "\t" in doc2.sections[0].value.content


def test_round_trip_nfc_bypass() -> None:
    """Non-NFC characters inside literal zones survive round-trip (NFD form preserved)."""
    # U+0065 U+0301 = decomposed e-acute (NFD form)
    decomposed = "caf\u0065\u0301"
    doc_str = _make_doc("TEXT", "```", decomposed)
    value = _parse_first_value(doc_str)
    # Content is NOT NFC-normalized -- stays in NFD form
    assert value.content == decomposed, f"NFD content not preserved. Expected {decomposed!r}, got {value.content!r}"


def test_round_trip_info_tag_preserved() -> None:
    """Info tag is preserved through parse -> emit -> parse."""
    doc_str = _make_doc("CODE", "```", "hello world", "python")
    doc1 = parse(doc_str)
    emitted = emit(doc1)
    doc2 = parse(emitted)
    assert doc1.sections[0].value.info_tag == doc2.sections[0].value.info_tag == "python"


def test_round_trip_fence_marker_preserved() -> None:
    """Fence marker (4 backticks) is preserved through parse -> emit -> parse."""
    doc_str = _make_doc("CODE", "````", "hello world", "python")
    doc1 = parse(doc_str)
    emitted = emit(doc1)
    doc2 = parse(emitted)
    assert doc1.sections[0].value.fence_marker == doc2.sections[0].value.fence_marker == "````"


# ---------------------------------------------------------------------------
# Nested fence detection (I3: nested fences MUST error)
# ---------------------------------------------------------------------------


def test_nested_fence_equal_length_errors() -> None:
    """Same-length fence with trailing content inside literal zone raises E007."""
    # Three-tick fence containing three-tick fence with info tag (ambiguous)
    content = "===DOC===\nCODE::\n```\n```json\ncontent\n```\n===END==="
    with pytest.raises(LexerError) as exc_info:
        parse(content)
    msg = exc_info.value.args[0]
    assert "E007" in msg
    assert "Nested literal zone" in msg or "nested" in msg.lower()


def test_nested_fence_longer_errors() -> None:
    """4-tick fence inside 3-tick literal zone raises E007."""
    content = "===DOC===\nCODE::\n```\n````\ncontent\n```\n===END==="
    with pytest.raises(LexerError) as exc_info:
        parse(content)
    msg = exc_info.value.args[0]
    assert "E007" in msg
    assert "Nested literal zone" in msg or "nested" in msg.lower()


def test_shorter_fence_inside_is_content() -> None:
    """Fence shorter than opening fence is treated as content (fence-length scaling)."""
    # 4-tick fence wrapping content with 3-tick sequence
    content = "===DOC===\nCODE::\n````\n```\nmore content\n````\n===END==="
    value = _parse_first_value(content)
    # The 3-tick sequence is preserved as content
    assert "```" in value.content


# ---------------------------------------------------------------------------
# Pathological edge cases (A8) [B0-S1]
# ---------------------------------------------------------------------------


def test_escaped_backticks_in_content() -> None:
    """Escaped backticks inside literal zone are preserved verbatim."""
    inner = "some \\` escaped \\`\\`\\` backticks"
    doc_str = _make_doc("CODE", "```", inner)
    value = _parse_first_value(doc_str)
    assert "\\`" in value.content
    assert "\\`\\`\\`" in value.content


def test_mixed_indentation_in_literal_zone() -> None:
    """Mixed tabs and spaces inside literal zone are preserved exactly."""
    inner = "\tline1\n  line2\n\t  line3\n    \tline4"
    doc_str = _make_doc("CODE", "```", inner)
    value = _parse_first_value(doc_str)
    assert value.content == inner


def test_deep_nesting_three_levels() -> None:
    """Three levels of fence scaling: 5-tick wraps 4-tick wraps 3-tick content."""
    # Build the nested content that the 5-tick fence contains
    inner_content = "````\n```\ninnermost\n```\n````"
    doc_str = _make_doc("OUTER", "`````", inner_content)
    doc = parse(doc_str)
    lz = doc.sections[0].value
    assert isinstance(lz, LiteralZoneValue)
    assert "````" in lz.content
    assert "```" in lz.content
    assert "innermost" in lz.content
    assert lz.fence_marker == "`````"


def test_trailing_whitespace_on_closing_fence() -> None:
    """Closing fence with trailing whitespace is still recognized as closing."""
    # Manual construction to control exact whitespace on closing fence
    content = "===DOC===\nCODE::\n```\nhello\n```   \n===END==="
    value = _parse_first_value(content)
    assert value.content == "hello"


def test_trailing_whitespace_on_opening_fence() -> None:
    """Opening fence info tag has trailing whitespace stripped."""
    content = "===DOC===\nCODE::\n```python   \nhello\n```\n===END==="
    value = _parse_first_value(content)
    assert value.info_tag == "python"
    assert value.content == "hello"


def test_content_line_is_only_backticks_shorter_than_fence() -> None:
    """A line of 2 backticks inside a 3-backtick fence is preserved as content."""
    content = "===DOC===\nCODE::\n```\n``\n```\n===END==="
    value = _parse_first_value(content)
    assert value.content == "``"


def test_empty_lines_around_content() -> None:
    """Empty lines before/after content inside literal zone are preserved.

    The parser includes lines up to (but not including) the closing fence line.
    The final newline before the closing fence is NOT part of content -- it is
    the line separator that terminates the last content line.
    """
    # Two leading empty lines, then "hello", then one trailing empty line.
    # The closing fence is on its own line after the trailing empty line.
    # Parser produces: "\n\nhello\n" (the trailing \n is the last content line end).
    content = "===DOC===\nCODE::\n```\n\n\nhello\n\n```\n===END==="
    value = _parse_first_value(content)
    # Leading empty lines and trailing empty line are preserved
    assert value.content.startswith("\n\nhello")
    assert value.content.count("\n") >= 3  # at least 3 newlines: 2 leading + 1 after hello


# ---------------------------------------------------------------------------
# I2: Empty literal zone vs. absent
# ---------------------------------------------------------------------------


def test_empty_literal_zone() -> None:
    """Empty literal zone is valid and distinct from absent (I2)."""
    content = "===DOC===\nCODE::\n```\n```\n===END==="
    value = _parse_first_value(content)
    assert isinstance(value, LiteralZoneValue)
    assert value.content == ""  # Empty string, not None and not absent


def test_absent_vs_empty_literal() -> None:
    """Absent value field vs empty literal zone are semantically distinct (I2)."""
    empty_doc = "===DOC===\nCODE::\n```\n```\n===END==="
    absent_doc = "===DOC===\nOTHER::value\n===END==="

    doc_empty = parse(empty_doc)
    doc_absent = parse(absent_doc)

    # Empty doc has a LiteralZoneValue
    assert isinstance(doc_empty.sections[0].value, LiteralZoneValue)

    # Absent doc has no LiteralZoneValue anywhere
    assert not any(isinstance(s.value, LiteralZoneValue) for s in doc_absent.sections if hasattr(s, "value"))
