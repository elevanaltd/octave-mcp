"""Backslash-run quote-escape parity tests for ``core/holographic.py`` parsers.

Pinned by GH-432 (parser-side sibling of cubic-dev-ai P1 on PR #431).

Three quote-handling sites in ``octave_mcp.core.holographic`` are
covered:

* ``_find_constraint_start`` — toggled ``in_quotes`` unconditionally on
  every ``"``. An escaped quote ``\\"`` would have falsely closed the
  string, making ``∧`` inside an example string visible at top level.
* ``_find_target_start`` — used a single-character lookback
  (``content[i - 1] != "\\"``) which misclassifies ``\\"`` (escaped
  backslash pair followed by an unescaped quote) as escaped.
* ``_parse_list_example`` — like ``_find_constraint_start``, toggled
  unconditionally and only outside top-level brackets.

The contract (matching GH#361r2 already enforced in
``mcp/write_detection.py::_all_section_marks_quoted``): a ``"`` is unescaped when
the run of immediately-preceding backslashes is of even length
(including zero). It is escaped when the run is of odd length.

Each test parameterises across backslash runs of length 0, 1, 2, 3, 4
so that the parity contract is pinned exhaustively at the boundary.
"""

from __future__ import annotations

import pytest

from octave_mcp.core.holographic import (
    _find_constraint_start,
    _find_target_start,
    _parse_list_example,
    parse_holographic_pattern,
)

# Each row: (run_len, is_quote_unescaped). Even-length runs (including
# zero) leave the quote unescaped; odd-length runs escape it.
_PARITY_CASES = [
    (0, True),
    (1, False),
    (2, True),
    (3, False),
    (4, True),
]


@pytest.mark.parametrize("run_len,quote_unescaped", _PARITY_CASES)
def test_find_target_start_respects_backslash_run_parity(run_len: int, quote_unescaped: bool) -> None:
    """``_find_target_start`` must apply backslash-run parity to quotes.

    For run_len in {0, 2, 4} the close-quote that follows the run is
    UNESCAPED, the string closes, and ``→§T`` at the end is visible at
    top level — the function must return the offset of ``→``.

    For run_len in {1, 3} the close-quote is ESCAPED, the string state
    remains open, and ``→§T`` sits inside the string — the function
    must return ``-1``.
    """
    backslashes = "\\" * run_len
    # Pattern content (already stripped of outer brackets, as the caller
    # in ``parse_holographic_pattern`` does):  "a{backslashes}"→§T
    content = f'"a{backslashes}"→§T'
    result = _find_target_start(content)
    if quote_unescaped:
        # The arrow sits after the closing quote. With even-parity
        # closing the string, it must be visible.
        assert result != -1, (
            f"run_len={run_len} (even, unescaped close-quote): "
            f"_find_target_start should see →§ at top level but returned -1.\n"
            f"  content: {content!r}"
        )
        # Sanity: the offset points at the arrow character.
        assert (
            content[result : result + 2] == "→§"
        ), f"run_len={run_len}: offset {result} does not point at →§ in {content!r}"
    else:
        assert result == -1, (
            f"run_len={run_len} (odd, escaped close-quote): "
            f"_find_target_start should treat →§ as inside the string and return -1, "
            f"got {result}.\n  content: {content!r}"
        )


@pytest.mark.parametrize("run_len,quote_unescaped", _PARITY_CASES)
def test_find_constraint_start_respects_backslash_run_parity(run_len: int, quote_unescaped: bool) -> None:
    """``_find_constraint_start`` must apply backslash-run parity to quotes.

    For run_len in {0, 2, 4} the close-quote is UNESCAPED; the string
    closes; ``∧`` at top level is visible and returned.

    For run_len in {1, 3} the close-quote is ESCAPED; the string state
    remains open; ``∧`` is inside the string and not returned.
    """
    backslashes = "\\" * run_len
    content = f'"a{backslashes}"∧REQ'
    result = _find_constraint_start(content)
    if quote_unescaped:
        assert result != -1, (
            f"run_len={run_len} (even, unescaped close-quote): "
            f"_find_constraint_start should see ∧ at top level but returned -1.\n"
            f"  content: {content!r}"
        )
        assert content[result] == "∧", f"run_len={run_len}: offset {result} does not point at ∧ in {content!r}"
    else:
        assert result == -1, (
            f"run_len={run_len} (odd, escaped close-quote): "
            f"_find_constraint_start should treat ∧ as inside the string and return -1, "
            f"got {result}.\n  content: {content!r}"
        )


@pytest.mark.parametrize("run_len,quote_unescaped", _PARITY_CASES)
def test_parse_list_example_respects_backslash_run_parity(run_len: int, quote_unescaped: bool) -> None:
    """``_parse_list_example`` must apply backslash-run parity to quotes.

    With an unescaped close-quote, the comma immediately following sits
    at top level and the list is split into two items. With an escaped
    close-quote, the comma is treated as inside the string and the list
    collapses to one item.

    The list literal is::

        ["a{backslashes}","b"]

    With backslashes interpreted by OCTAVE's string semantics, the first
    element is ``"a{backslashes}"`` (a string ending in ``run_len``
    raw backslashes); under even-parity that string CLOSES at its
    closing quote and the comma is a top-level separator.
    """
    backslashes = "\\" * run_len
    list_str = f'["a{backslashes}","b"]'
    items = _parse_list_example(list_str)
    if quote_unescaped:
        # Two items: "a\\..." (parsed as a string) and "b".
        assert len(items) == 2, (
            f"run_len={run_len} (even): list should split into 2 items.\n" f"  input: {list_str!r}\n  parsed: {items!r}"
        )
        assert items[1] == "b", f"second item should be 'b', got {items[1]!r}"
    else:
        # One item: the comma sits inside the still-open string.
        assert len(items) == 1, (
            f"run_len={run_len} (odd): list should collapse to 1 item "
            f"because the close-quote is escaped and the comma is inside the string.\n"
            f"  input: {list_str!r}\n  parsed: {items!r}"
        )


def test_parse_holographic_pattern_target_only_with_even_backslash_run() -> None:
    """End-to-end RED for the CE repro: target-only holographic with ``\\"``.

    ``parse_holographic_pattern('["a\\\\"→§T]')`` exercises the
    full ``_find_target_start`` path on the bug case. Even parity
    (run_len=2) means the close-quote is unescaped and ``→§T`` must be
    recognised as the target, yielding ``target == "T"``.
    """
    # Raw OCTAVE source on disk:  ["a\\"→§T]
    pattern_src = '["a\\\\"→§T]'
    pattern = parse_holographic_pattern(pattern_src)
    assert pattern.target == "T", (
        f"Target-only holographic with even-parity close-quote should "
        f"parse target as 'T', got {pattern.target!r}.\n"
        f"  pattern: {pattern_src!r}"
    )
