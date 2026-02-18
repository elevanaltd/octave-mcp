"""A9 Migration Gate: corpus-scan regression guard for literal zones.

Issue #235 T20: A9 Migration Gate + Regression Guard
Blueprint: Appendix C, §10.4

A9 Assumption: Migration to literal zones is NON-BREAKING for existing .oct.md files.
Files without backtick fences at line start parse identically before and after.

CRITICAL DESIGN: This is a REGRESSION GUARD, not a 100% pass requirement.
Pre-existing failures on main are NOT counted as regressions.
Only NEW failures (files that parse on main but fail on this branch) cause failure.

Implementation approach:
- For each .oct.md file that fails to parse on this branch:
  - Get the main-branch version via `git show main:<path>`
  - If it also fails on main: pre-existing failure (not a regression)
  - If it passes on main but fails here: NEW regression (gate fails)
  - If git show fails (new file): also not a regression
"""

import subprocess
from pathlib import Path

import pytest

from octave_mcp.core.lexer import LexerError
from octave_mcp.core.parser import ParserError, parse

# Repository root (2 levels up from tests/)
REPO_ROOT = Path(__file__).parent.parent

# Directories to exclude from corpus scan
EXCLUDE_DIRS = {".git", ".venv", "__pycache__", "node_modules"}

# Fixture file patterns to exclude (intentionally malformed test fixtures)
EXCLUDE_PATTERNS = {"_invalid", "_error"}


def _collect_oct_files() -> list[Path]:
    """Collect all .oct.md files from the repo, excluding irrelevant directories."""
    all_files = list(REPO_ROOT.rglob("*.oct.md"))
    filtered = []
    for f in all_files:
        # Check if any part of the path is an excluded directory
        parts = set(f.relative_to(REPO_ROOT).parts)
        if parts & EXCLUDE_DIRS:
            continue
        # Skip intentionally malformed fixtures
        if any(pat in f.name for pat in EXCLUDE_PATTERNS):
            continue
        filtered.append(f)
    return sorted(filtered)


def _try_parse(content: str) -> Exception | None:
    """Try to parse content. Returns None on success, exception on failure."""
    try:
        parse(content)
        return None
    except (LexerError, ParserError, Exception) as e:
        return e


def _get_main_content(file_path: Path) -> str | None:
    """Get file content from main branch via git show.

    Returns None if the file doesn't exist on main (new file = not a regression).

    FAIL-CLOSED: Any git error that is NOT a "file not found on main" condition
    causes pytest.fail() so that operational failures are never silently treated
    as "new file -- skip".  Only the following stderr patterns indicate a
    legitimately new file and warrant returning None:
      - "does not exist"
      - "exists on disk"
      - "unknown revision"
    """
    rel_path = file_path.relative_to(REPO_ROOT)
    try:
        result = subprocess.run(
            ["git", "show", f"main:{rel_path}"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(
            f"A9 gate: git show timed out for '{rel_path}'. "
            "The git command took longer than 10 seconds. "
            "Fix the repository environment before re-running."
        )
    except Exception as exc:
        pytest.fail(
            f"A9 gate: git show raised an unexpected exception for '{rel_path}': {exc!r}. "
            "Fix the repository environment before re-running."
        )

    if result.returncode != 0:
        stderr_lower = result.stderr.lower()
        # Patterns that indicate the file genuinely does not exist on main
        _NEW_FILE_PATTERNS = ("does not exist", "exists on disk", "unknown revision")
        if any(pat in stderr_lower for pat in _NEW_FILE_PATTERNS):
            # Legitimately new file -- not a regression
            return None
        # Any other non-zero exit is an operational git error -- fail loudly
        pytest.fail(
            f"A9 gate: git show failed for '{rel_path}' with exit code "
            f"{result.returncode}.\n"
            f"  stderr: {result.stderr.strip()!r}\n"
            f"  stdout: {result.stdout.strip()!r}\n"
            "This is an operational error (bad repo state, path format issue, etc.). "
            "Fix the environment before re-running."
        )

    return result.stdout


def test_a9_migration_no_regressions() -> None:
    """A9 Gate: Scan all .oct.md files. Only fail on NEW failures.

    A file is a regression if:
      - It fails to parse on this branch (issue-235-literal-zones)
      - AND it successfully parses on main

    Pre-existing failures (fail on both main and branch) are NOT counted.
    New files (not on main) are NOT counted as regressions.

    Gate criteria: ZERO regressions.
    """
    files = _collect_oct_files()
    assert len(files) > 0, "No .oct.md files found in corpus -- check REPO_ROOT path"

    regressions = []
    pre_existing = []
    new_files_skipped = []
    passed = []

    for file_path in files:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        branch_error = _try_parse(content)

        if branch_error is None:
            # Passes on branch -- no regression possible
            passed.append(file_path)
            continue

        # Fails on branch -- check if it also fails on main
        main_content = _get_main_content(file_path)

        if main_content is None:
            # File doesn't exist on main -- new file, not a regression
            new_files_skipped.append((file_path, str(branch_error)[:100]))
            continue

        main_error = _try_parse(main_content)

        if main_error is not None:
            # Also fails on main -- pre-existing failure, not a regression
            pre_existing.append((file_path, str(branch_error)[:100]))
        else:
            # REGRESSION: passes on main but fails on branch
            regressions.append(
                {
                    "file": str(file_path.relative_to(REPO_ROOT)),
                    "branch_error": str(branch_error),
                    "main_parses": True,
                }
            )

    # Report summary (always print for visibility)
    print("\nA9 Corpus Scan Results:")
    print(f"  Total files scanned:       {len(files)}")
    print(f"  Passes on branch:          {len(passed)}")
    print(f"  Pre-existing failures:     {len(pre_existing)}")
    print(f"  New files (skipped):       {len(new_files_skipped)}")
    print(f"  REGRESSIONS (NEW failures): {len(regressions)}")

    if regressions:
        regression_report = "\n".join(f"  - {r['file']}\n    Error: {r['branch_error'][:120]}" for r in regressions)
        pytest.fail(
            f"A9 gate FAILED: {len(regressions)} regression(s) detected.\n"
            f"These files parsed on main but fail on this branch:\n"
            f"{regression_report}\n\n"
            f"Fix the parser/lexer so these files continue to parse correctly."
        )

    # Zero regressions -- gate passes
    assert len(regressions) == 0, "Unreachable: regressions found but not reported above"
