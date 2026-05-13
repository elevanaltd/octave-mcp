"""Lint gate: paired-write symmetry between value mutations and dirty flags.

ADR-0006 SR2-T2 Strategy A PR-2 (GH#377), task T6 follow-on. This test
enforces the structural invariant that EVERY ``node.value = ...``
mutation in ``mcp/write.py`` AND ``core/repair.py`` is paired with
either:

* ``node.dirty = True`` / ``node.repaired = True`` /
  ``node.body_dirty = True`` within +/- 10 source lines, OR
* ``_mark_dirty(...)`` within +/- 10 source lines, OR
* ``doc.meta_dirty[...] = True`` (for META key mutations), OR
* a constructor call like ``Assignment(..., dirty=True, ...)`` /
  ``Assignment(..., repaired=True, ...)`` that wraps the value
  (the node is born dirty/repaired).

The gate is the I3+I4 hinge: splicing a "clean" node whose value was
mutated post-parse re-introduces stale source bytes (I1 violation
under Strategy A's emitter in PR-3). The lint gate ensures the
symmetry is enforced structurally, not by convention.

Scope: write-side mutation surface (``mcp/write.py``, ``core/repair.py``,
and ``cli/main.py``). The CLI was added to the gate after a critical-
engineer review on PR #418 found that ``cli/main.py``'s changes-mode
loop was mutating the AST WITHOUT setting dirty flags, causing the
Strategy A T8 slice path to splice the OLD baseline bytes and silently
discard the user's change. Tests, fixtures, and the parser itself are
excluded because:

* Parser nodes are constructed at parse-time with no source-byte
  drift between mutation and birth — ``Assignment(value=...)`` is the
  authoring path, not the post-parse mutation path.
* Tests assert state; they are allowed to set ``.value`` without
  flipping dirty flags (the production path under test does that).

How violations are reported: the test prints the file path, line
number, and surrounding context for any unpaired mutation site,
making it easy to diagnose orphan writes during code review.
"""

from __future__ import annotations

import re
from pathlib import Path

# Project root (this test lives under tests/unit/).
_ROOT = Path(__file__).resolve().parents[2]

# Files under the I3+I4 paired-write contract.
_FILES_UNDER_LINT: tuple[Path, ...] = (
    _ROOT / "src" / "octave_mcp" / "mcp" / "write.py",
    _ROOT / "src" / "octave_mcp" / "core" / "repair.py",
    # Added after CE BLOCKER on PR #418: the CLI write command's changes
    # loop is a parallel mutation surface to mcp/write.py and is subject
    # to the same paired-write discipline under Strategy A T8.
    _ROOT / "src" / "octave_mcp" / "cli" / "main.py",
)

# Line patterns that COUNT as a mutation site. We match on:
#   <ident>.value = <something>
# where <something> is NOT another equals (to avoid catching ==).
# We require the LHS to be an attribute access (a dot) — bare
# ``value = ...`` is a local variable and not a mutation site.
# We also exclude lines inside docstrings via _strip_docstrings.
_MUTATION_RE = re.compile(r"(?<!#)\b(\w+)\.value\s*=\s*[^=]")

# META key mutations: doc.meta[<key>] = <value>.
_META_MUTATION_RE = re.compile(r"(?<!#)\b(\w+)\.meta\[[^\]]+\]\s*=\s*[^=]")

# Patterns that SATISFY the paired-write rule. Any of these inside a
# +/-10-line window around the mutation site discharges the obligation.
_PAIRING_PATTERNS = (
    re.compile(r"\.dirty\s*=\s*True\b"),
    re.compile(r"\.repaired\s*=\s*True\b"),
    re.compile(r"\.body_dirty\s*=\s*True\b"),
    re.compile(r"\bdoc\.meta_dirty\["),
    re.compile(r"_mark_dirty\("),
    # New-node constructor where the node is born dirty/repaired:
    re.compile(r"\b(Assignment|Block|Section|Document)\([^)]*\bdirty\s*=\s*True"),
    re.compile(r"\b(Assignment|Block|Section|Document)\([^)]*\brepaired\s*=\s*True"),
)


def _strip_docstrings(lines: list[str]) -> list[str]:
    """Replace lines inside triple-quoted strings with empty strings.

    Crude but sufficient: tracks single-line and multi-line triple-quoted
    blocks (both ``\"\"\"`` and ``'''``). Lines INSIDE a docstring become
    empty strings (preserving line numbers for diagnostics) so the
    mutation regex cannot match docstring examples.
    """
    out: list[str] = []
    in_triple: str | None = None  # tracks the closing delimiter
    for line in lines:
        if in_triple is None:
            # Look for triple-quote opener.
            opener_idx_double = line.find('"""')
            opener_idx_single = line.find("'''")
            # Choose the leftmost opener present.
            candidates = [c for c in (opener_idx_double, opener_idx_single) if c != -1]
            if candidates:
                opener_idx = min(candidates)
                delim = line[opener_idx : opener_idx + 3]
                # Check if a matching closer exists on the same line AFTER
                # the opener.
                rest = line[opener_idx + 3 :]
                closer_idx = rest.find(delim)
                if closer_idx != -1:
                    # Single-line docstring/string — strip the inner span.
                    cleaned = line[:opener_idx] + ("X" * 3) + rest[closer_idx:]
                    out.append(cleaned)
                else:
                    # Multi-line opens here.
                    in_triple = delim
                    out.append(line[:opener_idx])
            else:
                out.append(line)
        else:
            # We are inside a multi-line docstring; look for closer.
            closer_idx = line.find(in_triple)
            if closer_idx == -1:
                out.append("")
            else:
                # Closer present — keep only the part AFTER the closer.
                out.append(line[closer_idx + 3 :])
                in_triple = None
    return out


def _scan_file(path: Path) -> list[tuple[int, str, str]]:
    """Return list of (line_number, mutation_line, reason) for unpaired sites.

    Reason is one of: "value_unpaired" | "meta_unpaired".
    """
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    lines = _strip_docstrings(raw_lines)
    violations: list[tuple[int, str, str]] = []
    for idx, line in enumerate(lines):
        # Skip blank/comment-only lines for performance.
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # value-mutation match
        m_val = _MUTATION_RE.search(line)
        if m_val:
            # Skip constructor kwarg pattern: e.g. `Assignment(value=...)`.
            # These are NOT post-parse mutations — they are births.
            # The ident before .value would not exist; we detect them via
            # the absence of an attribute chain by checking the matched
            # ident is followed by ".value =" preceded by an attribute
            # selector. The regex already requires `\w+\.value`, so a
            # bare `value=` in a kwarg list is excluded.
            if not _is_paired(lines, idx):
                violations.append((idx + 1, raw_lines[idx], "value_unpaired"))
        m_meta = _META_MUTATION_RE.search(line)
        if m_meta:
            if not _is_paired(lines, idx):
                violations.append((idx + 1, raw_lines[idx], "meta_unpaired"))
    return violations


def _is_paired(lines: list[str], idx: int) -> bool:
    """True iff some pairing pattern matches within +/- 10 lines of idx."""
    lo = max(0, idx - 10)
    hi = min(len(lines), idx + 11)
    window = "\n".join(lines[lo:hi])
    return any(pat.search(window) for pat in _PAIRING_PATTERNS)


def test_paired_write_symmetry_across_write_and_repair() -> None:
    """Every value/meta mutation in write.py + repair.py is paired with a dirty/repaired flag.

    See module docstring for the rationale.
    """
    all_violations: list[tuple[str, int, str, str]] = []
    for path in _FILES_UNDER_LINT:
        assert path.exists(), f"lint-gate target missing: {path}"
        for line_no, line_text, reason in _scan_file(path):
            all_violations.append((str(path.relative_to(_ROOT)), line_no, line_text, reason))
    if all_violations:
        msg_lines = [
            "Dirty-bit lint gate FAILED: the following mutation sites are NOT paired",
            "with a dirty/repaired/meta_dirty/_mark_dirty marker within 10 lines.",
            "Add the appropriate paired write to preserve I1 (Syntactic Fidelity)",
            "under Strategy A's emitter (PR-3 / T8).",
            "",
        ]
        for rel, line_no, line_text, reason in all_violations:
            msg_lines.append(f"  {rel}:{line_no} [{reason}]: {line_text.strip()}")
        raise AssertionError("\n".join(msg_lines))


def test_repair_ast_node_propagates_body_dirty_to_ancestors() -> None:
    """CE BLOCKER (PR #418): the recursive repair walker MUST return its
    propagation signal so ancestor Block/Section parents can mark body_dirty.

    The 10-line proximity lint above only verifies that ``.repaired = True``
    is set on the mutated Assignment. It does NOT enforce the cross-node
    invariant: "if a descendant Assignment is repaired, every ancestor
    Block/Section MUST be marked body_dirty so the slice path in emit()
    falls through to canonical re-emit."

    This complementary structural check guards the recursion contract by
    parsing core/repair.py with the ``ast`` module and inspecting ONLY
    the body of the ``_repair_ast_node`` function:

      1. Its return annotation MUST be ``bool`` so callers can propagate
         the "descendant was repaired" signal upward.
      2. The function body MUST contain at least 2 assignments of the
         form ``<target>.body_dirty = True`` (one for the Block branch,
         one for the Section branch).

    Cubic P2 (PR #418): the lint is scoped to the function body so an
    unrelated ``body_dirty = True`` write elsewhere in repair.py — or a
    refactor that moves body_dirty propagation OUT of
    ``_repair_ast_node`` into a sibling function — cannot falsely
    satisfy a whole-file substring count.
    """
    import ast

    src = (_ROOT / "src" / "octave_mcp" / "core" / "repair.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    func: ast.FunctionDef | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_repair_ast_node":
            func = node
            break
    assert func is not None, "_repair_ast_node missing from repair.py"

    # 1. Return annotation MUST be `bool`.
    assert isinstance(func.returns, ast.Name) and func.returns.id == "bool", (
        "_repair_ast_node MUST be declared `-> bool` so callers can propagate "
        "the 'descendant was repaired' signal up to ancestor Block/Section "
        "body_dirty. See CE BLOCKER on PR #418."
    )

    # 2. Count `<target>.body_dirty = True` assignments INSIDE the function
    # body only (ast.walk(func) does not descend into sibling functions).
    body_dirty_assigns = [
        n
        for n in ast.walk(func)
        if isinstance(n, ast.Assign)
        and len(n.targets) == 1
        and isinstance(n.targets[0], ast.Attribute)
        and n.targets[0].attr == "body_dirty"
        and isinstance(n.value, ast.Constant)
        and n.value.value is True
    ]
    assert len(body_dirty_assigns) >= 2, (
        f"Expected body_dirty=True propagation in BOTH the Block and Section "
        f"branches of _repair_ast_node, found {len(body_dirty_assigns)} "
        f"occurrence(s) inside the function body. "
        f"See CE BLOCKER and Cubic P2 on PR #418."
    )


def test_parser_propagates_repaired_to_body_dirty_post_pass() -> None:
    """CE BLOCKER cycle 5 (PR #418): parser.py MUST invoke a post-pass that
    propagates descendant ``repaired=True`` to ancestor ``body_dirty=True``.

    The parser sets ``assignment.repaired=True`` on a child Assignment
    when a lenient value-parse repair fires (e.g. multi_word_coalesce).
    Without a post-pass that sweeps the constructed Document and marks
    every ancestor Block/Section ``body_dirty=True``, preserve-mode
    emit() slices the parent's whole subtree from baseline and silently
    drops the repair.

    The dirty-paired-write proximity lint (top of this file) intentionally
    EXCLUDES parser.py because the parser builds nodes structurally
    rather than mutating them post-hoc — so a proximity rule cannot catch
    a missing post-construction sweep. This complementary AST-scoped
    structural check enforces the recurrence-free contract: the helper
    ``_propagate_repaired_to_body_dirty`` exists AND is invoked from
    ``Parser.parse_document``.
    """
    import ast

    src = (_ROOT / "src" / "octave_mcp" / "core" / "parser.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    # 1. The helper itself must exist as a module-level FunctionDef.
    helper: ast.FunctionDef | None = None
    for top in tree.body:
        if isinstance(top, ast.FunctionDef) and top.name == "_propagate_repaired_to_body_dirty":
            helper = top
            break
    assert helper is not None, (
        "_propagate_repaired_to_body_dirty MUST exist at module scope in "
        "core/parser.py. See CE BLOCKER cycle 5 on PR #418."
    )

    # The helper must set body_dirty at least once (the propagation point).
    helper_body_dirty = [
        n
        for n in ast.walk(helper)
        if isinstance(n, ast.Assign)
        and len(n.targets) == 1
        and isinstance(n.targets[0], ast.Attribute)
        and n.targets[0].attr == "body_dirty"
        and isinstance(n.value, ast.Constant)
        and n.value.value is True
    ]
    assert len(helper_body_dirty) >= 1, (
        "_propagate_repaired_to_body_dirty MUST contain at least one "
        "`<target>.body_dirty = True` assignment — otherwise the post-pass "
        "is a no-op."
    )

    # 2. Parser.parse_document MUST invoke the helper.
    parse_document: ast.FunctionDef | None = None
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == "parse_document":
            parse_document = n
            break
    assert parse_document is not None, "Parser.parse_document missing from parser.py"

    invoked = False
    for n in ast.walk(parse_document):
        if (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "_propagate_repaired_to_body_dirty"
        ):
            invoked = True
            break
    assert invoked, (
        "Parser.parse_document MUST invoke `_propagate_repaired_to_body_dirty(doc)` "
        "after the structural walk so descendant repaired flags propagate to "
        "ancestor body_dirty. Without this, preserve-mode emit slices stale "
        "baseline bytes when a child Assignment is lenient-repaired. "
        "See CE BLOCKER cycle 5 on PR #418."
    )
