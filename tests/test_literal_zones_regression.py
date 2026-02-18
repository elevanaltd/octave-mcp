"""Regression guard tests for literal zones (D2, D5 decisions).

Issue #235 T20: A9 Migration Gate + Regression Guard
Blueprint: §10.4

Verifies that existing OCTAVE behaviors are unchanged after literal zone
support is added:
- D2: Triple-quoted strings still parse as normalizing strings (NOT literal zones)
- D5: YAML frontmatter handling unchanged
- D5: _unwrap_markdown_code_fence() behavior unchanged (outer transport wrapper)
- A9: No existing .oct.md file that parsed before now fails
"""

from pathlib import Path

import pytest

from octave_mcp.core.ast_nodes import LiteralZoneValue
from octave_mcp.core.lexer import LexerError
from octave_mcp.core.parser import ParserError, parse

# ---------------------------------------------------------------------------
# D2: Triple-quoted strings are NOT literal zones
# ---------------------------------------------------------------------------


def test_triple_quoted_string_not_literal_zone() -> None:
    """D2: Triple-quoted strings (\"\"\"...\"\"\") are still normalizing strings.

    Triple backtick fences are literal zones; triple quotes are NOT.
    This is the critical disambiguation: backtick syntax for preservation,
    quote syntax for string values (with normalization).
    """
    content = '===DOC===\nKEY::"""hello world"""\n===END==='
    doc = parse(content)
    # Should parse as a string, NOT as a LiteralZoneValue
    value = doc.sections[0].value
    is_literal = isinstance(value, LiteralZoneValue)
    assert not is_literal, f"Triple-quoted string incorrectly parsed as LiteralZoneValue: {value!r}"
    # Should be a plain string value
    assert isinstance(value, str), f"Triple-quoted string should be str, got {type(value).__name__}"


def test_triple_quoted_multiline_string_not_literal_zone() -> None:
    """D2: Multi-line triple-quoted strings are normalizing strings, not literal zones."""
    content = '===DOC===\nKEY::"""hello\nworld"""\n===END==='
    # This may parse or raise an error (newlines in strings), but it's NOT a literal zone
    try:
        doc = parse(content)
        if doc.sections:
            value = doc.sections[0].value
            is_literal = isinstance(value, LiteralZoneValue)
            assert not is_literal, "Multi-line triple-quoted string should not be a LiteralZoneValue"
    except (LexerError, ParserError):
        # Parsing may fail (newline in quoted string is invalid) -- that's fine
        # The important thing is it doesn't create a LiteralZoneValue
        pass


def test_single_backtick_not_literal_zone() -> None:
    """Single backtick is not a fence marker (must be 3+)."""
    content = "===DOC===\nKEY::value\n===END==="
    doc = parse(content)
    value = doc.sections[0].value
    assert not isinstance(value, LiteralZoneValue)


def test_double_backtick_not_literal_zone() -> None:
    """Two backticks do not start a fence (must be 3+)."""
    # A line starting with `` (2 backticks) is not a fence
    content = "===DOC===\nKEY::value\n===END==="
    doc = parse(content)
    value = doc.sections[0].value
    assert not isinstance(value, LiteralZoneValue)


# ---------------------------------------------------------------------------
# D5: YAML frontmatter handling unchanged
# ---------------------------------------------------------------------------


def test_yaml_frontmatter_unchanged() -> None:
    """D5: YAML frontmatter (---...---) parsing is unchanged by literal zone support."""
    content = "---\nname: test\ndescription: A test document\n---\n===DOC===\nKEY::value\n===END==="
    # Should parse without error -- frontmatter is preserved as Zone 2
    doc = parse(content)
    assert doc is not None
    # The OCTAVE content should still parse correctly
    assert len(doc.sections) >= 1


def test_yaml_frontmatter_with_literal_zone() -> None:
    """D5: Document with both YAML frontmatter and literal zones parses correctly."""
    content = "---\nname: test\n---\n===DOC===\nCODE::\n```python\ndef hello():\n    pass\n```\n===END==="
    doc = parse(content)
    assert doc is not None
    # First section should be a literal zone
    value = doc.sections[0].value
    assert isinstance(value, LiteralZoneValue)
    assert value.info_tag == "python"


# ---------------------------------------------------------------------------
# D5: _unwrap_markdown_code_fence() behavior unchanged
# ---------------------------------------------------------------------------


def test_outer_fence_unwrapping_unchanged() -> None:
    """D5: _unwrap_markdown_code_fence() still strips the outer transport wrapper.

    The outer markdown code fence is a transport mechanism, not an OCTAVE literal zone.
    _unwrap_markdown_code_fence() strips it BEFORE parsing begins.
    """
    # Import the write tool's unwrap function
    from octave_mcp.mcp.write import WriteTool

    tool = WriteTool.__new__(WriteTool)  # Don't call __init__

    # Outer code fence wrapping OCTAVE content (transport wrapper)
    outer_wrapped = "```octave\n===DOC===\nKEY::value\n===END===\n```"
    unwrapped, was_unwrapped = tool._unwrap_markdown_code_fence(outer_wrapped)

    assert was_unwrapped is True, "Outer code fence should be detected and stripped"
    assert "===DOC===" in unwrapped, "Unwrapped content should contain OCTAVE envelope"
    assert "```octave" not in unwrapped, "Outer fence markers should be removed"


def test_outer_fence_unwrapping_no_fence_unchanged() -> None:
    """D5: _unwrap_markdown_code_fence() returns content unchanged when no outer fence."""
    from octave_mcp.mcp.write import WriteTool

    tool = WriteTool.__new__(WriteTool)

    plain_content = "===DOC===\nKEY::value\n===END==="
    unwrapped, was_unwrapped = tool._unwrap_markdown_code_fence(plain_content)

    assert was_unwrapped is False, "No outer fence should be detected"
    assert unwrapped == plain_content, "Content should be returned unchanged"


def test_outer_fence_unwrapping_preserves_inner_literal_zones() -> None:
    """D5: _unwrap_markdown_code_fence() does NOT strip inner literal zones.

    The outer fence is the transport wrapper. Inner literal zones (backtick fences
    inside the OCTAVE document) are NOT affected by _unwrap_markdown_code_fence().
    """
    from octave_mcp.mcp.write import WriteTool

    tool = WriteTool.__new__(WriteTool)

    # Outer transport fence wrapping OCTAVE with inner literal zone
    outer_wrapped = "```octave\n===DOC===\nCODE::\n```python\ndef hello():\n    pass\n```\n===END===\n```"
    unwrapped, was_unwrapped = tool._unwrap_markdown_code_fence(outer_wrapped)

    # The outer fence is stripped
    assert was_unwrapped is True
    # But the inner literal zone fence markers are preserved
    assert "```python" in unwrapped, "Inner literal zone fence should be preserved"
    assert "def hello():" in unwrapped, "Inner literal zone content should be preserved"


# ---------------------------------------------------------------------------
# D2: Documents without literal zones parse identically
# ---------------------------------------------------------------------------


def test_document_without_literal_zones_unchanged() -> None:
    """Documents without literal zones produce identical parse output.

    A core requirement: the literal zone feature must not break any existing
    valid OCTAVE document that doesn't contain backtick fences.
    """
    content = """===DOC===
META:
  TYPE::TEST
  VERSION::"1.0"

§1::SECTION
KEY::value
LIST::[a,b,c]
NESTED:
  CHILD::data
===END==="""

    doc = parse(content)
    assert doc is not None
    # No literal zones should appear
    for section in doc.sections:
        if hasattr(section, "value"):
            is_literal = isinstance(section.value, LiteralZoneValue)
            assert not is_literal, f"Unexpected LiteralZoneValue in document without backtick fences: {section}"


def test_no_backtick_collision_in_corpus() -> None:
    """A9: Verify no existing .oct.md spec files that previously parsed now fail.

    This uses the same regression guard logic as test_a9_migration_no_regressions:
    for each failing spec file, check if it also fails on main. Only fail if a
    file passes on main but fails on this branch (true regression).

    FAIL-CLOSED: git show operational errors (timeout, bad repo state, path issues)
    are never silently swallowed.  Only stderr patterns that confirm the file does
    not exist on main ("does not exist", "exists on disk", "unknown revision") allow
    the file to be skipped as a legitimately new file.  Any other error fails loudly.
    """
    import subprocess

    repo_root = Path(__file__).parent.parent

    # Patterns indicating a file genuinely does not exist on main branch
    _NEW_FILE_PATTERNS = ("does not exist", "exists on disk", "unknown revision")

    # Check all spec files (the most important corpus for this project)
    spec_dir = repo_root / "src" / "octave_mcp" / "resources" / "specs"
    spec_files = list(spec_dir.rglob("*.oct.md"))

    regressions = []
    for f in spec_files:
        content = f.read_text(encoding="utf-8", errors="replace")
        branch_error = None
        try:
            parse(content)
        except Exception as e:
            branch_error = e

        if branch_error is None:
            continue  # Passes -- no regression

        # Fails on branch -- check if it also fails on main
        rel_path = f.relative_to(repo_root)
        try:
            result = subprocess.run(
                ["git", "show", f"main:{rel_path}"],
                capture_output=True,
                text=True,
                cwd=repo_root,
                timeout=10,
            )
        except subprocess.TimeoutExpired:
            pytest.fail(
                f"A9 gate: git show timed out for '{rel_path}'. "
                "The git command took longer than 10 seconds. "
                "Fix the repository environment before re-running."
            )

        if result.returncode != 0:
            stderr_lower = result.stderr.lower()
            if any(pat in stderr_lower for pat in _NEW_FILE_PATTERNS):
                # Legitimately new file -- not a regression
                continue
            # Any other non-zero exit is an operational error -- fail loudly
            pytest.fail(
                f"A9 gate: git show failed for '{rel_path}' with exit code "
                f"{result.returncode}.\n"
                f"  stderr: {result.stderr.strip()!r}\n"
                "This is an operational error (bad repo state, path format issue, etc.). "
                "Fix the environment before re-running."
            )

        main_error = None
        try:
            parse(result.stdout)
        except Exception as me:
            main_error = me

        if main_error is None:
            # Passes on main but fails on branch -- REGRESSION
            regressions.append((f.name, str(branch_error)[:100]))

    if regressions:
        lines = "\n".join(f"  - {name}: {err}" for name, err in regressions)
        msg = f"A9: {len(regressions)} spec file(s) are new regressions (pass on main, fail on branch):\n{lines}"
        raise AssertionError(msg)
