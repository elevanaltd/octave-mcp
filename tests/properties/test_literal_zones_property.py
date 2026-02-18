"""Hypothesis property-based tests for literal zones.

Issue #235 T19: Integration + Property-Based Tests
Blueprint: §10.3, B0-S2 amendment

B0-S2: Replaces the old approach of skipping content with fence-like substrings.
This file uses Hypothesis generators that deliberately include backtick runs,
then dynamically scales the fence length to wrap them safely.
"""

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from octave_mcp.core.ast_nodes import LiteralZoneValue
from octave_mcp.core.emitter import emit
from octave_mcp.core.parser import parse

# ---------------------------------------------------------------------------
# Strategy helpers
# ---------------------------------------------------------------------------


def _scale_fence_for_content(content: str) -> tuple[str, str]:
    """Compute the minimum safe fence marker for content.

    Scans content for the longest contiguous run of backticks and returns
    a fence marker that is strictly longer. This eliminates any need to
    skip content with backtick sequences.

    Returns:
        (fence_marker, content) tuple where fence_marker is >= 3 and
        strictly longer than any run of backticks in content.
    """
    max_run = 0
    current_run = 0
    for ch in content:
        if ch == "`":
            current_run += 1
            max_run = max(max_run, current_run)
        else:
            current_run = 0
    # Fence must be at least 3 and strictly longer than any run in content
    fence_len = max(3, max_run + 1)
    return ("`" * fence_len, content)


# Strategy: generate text that may include backtick runs
_text_with_backticks = st.text(
    alphabet=st.sampled_from(list("abcdefghijklmnopqrstuvwxyz \t\n`")),
    min_size=0,
    max_size=200,
)

# Strategy: generate (fence_marker, content) pairs where fence is always safe
_fence_and_content_strategy = _text_with_backticks.map(_scale_fence_for_content)


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


@given(_fence_and_content_strategy)
@settings(max_examples=100)
def test_any_content_round_trips_with_fence_scaling(fence_and_content: tuple[str, str]) -> None:
    """Any string content -- including fence-like substrings -- can be
    placed in a literal zone using fence-length scaling and round-trips.

    B0-S2: Replaces the previous test that skipped fence-containing content.
    This test uses Hypothesis generators that deliberately produce content
    with backtick runs, then dynamically scales the fence length to wrap
    them safely.
    """
    fence, content = fence_and_content

    # Additional check: no line in content starts with a backtick run equal
    # to or longer than our fence -- that would trigger E007_NESTED_FENCE
    lines = content.split("\n")
    max_line_start_run = max(
        (len(line) - len(line.lstrip("`")) for line in lines),
        default=0,
    )
    assume(max_line_start_run < len(fence))

    octave = f"===DOC===\nCODE::\n{fence}\n{content}\n{fence}\n===END==="
    # No except: the outer OCTAVE structure is fixed and valid; fence content
    # is preserved verbatim by the lexer (D3: zero processing).  The assume()
    # above already filters the only known-invalid case (nested fence at line
    # start).  Swallowing LexerError/ParserError here would be validation
    # theater -- any such failure represents a real parser/emitter regression.
    doc1 = parse(octave)
    emitted = emit(doc1)
    doc2 = parse(emitted)
    # Round-trip fidelity: content is identical through parse->emit->parse
    assert doc1.sections[0].value.content == doc2.sections[0].value.content


@given(st.integers(min_value=3, max_value=10))
def test_fence_length_scaling(n: int) -> None:
    """Any fence length >= 3 works correctly for simple content."""
    fence = "`" * n
    octave = f"===DOC===\nCODE::\n{fence}\nhello\n{fence}\n===END==="
    doc = parse(octave)
    value = doc.sections[0].value
    assert isinstance(value, LiteralZoneValue)
    assert value.fence_marker == fence
    assert value.content == "hello"


@given(st.integers(min_value=3, max_value=8), st.integers(min_value=1, max_value=5))
def test_shorter_fences_in_content_are_preserved(outer_len: int, inner_len: int) -> None:
    """Fence-like sequences at line start that are shorter than the wrapping fence
    are treated as content (fence-length scaling per CommonMark).
    """
    assume(inner_len < outer_len)
    outer_fence = "`" * outer_len
    inner_fence = "`" * inner_len
    octave = f"===DOC===\nCODE::\n{outer_fence}\n{inner_fence}\n{outer_fence}\n===END==="
    doc = parse(octave)
    value = doc.sections[0].value
    assert isinstance(value, LiteralZoneValue)
    # The inner_fence sequence is preserved as content
    assert inner_fence in value.content
