"""Corpus invariant test: no shipped .oct.md document trips W_DUPLICATE_TARGET.

GH#387 (SR1-T2a, scope-pure split from #372): the migration sweep showed the
in-tree corpus is clean of W_DUPLICATE_TARGET collisions after one hand-patch
to a benchmark research output. This test locks the clean state so any future
regression (a shipped fixture, governance doc, or example acquiring a
Block(K) + flat Assignment("K.X", ...) corruption fingerprint at the same
nesting level) fails CI immediately.

Parent issue #372 (full hard-fail conversion + --resolve-duplicates escape
hatch) remains deferred to deep-tier work post-SR1-T1.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from octave_mcp.core.parser import parse
from octave_mcp.core.validator import Validator

REPO_ROOT = Path(__file__).resolve().parents[2]

# Directories whose contents are not part of the shipped corpus invariant.
# - .venv / __pycache__ / .git / node_modules / .tox: tooling artefacts.
# - .ruff_cache / .mypy_cache / .pytest_cache: tooling artefacts.
EXCLUDED_PARTS = {
    ".venv",
    "__pycache__",
    ".git",
    "node_modules",
    ".tox",
    ".ruff_cache",
    ".mypy_cache",
    ".pytest_cache",
}


def _iter_corpus_files() -> list[Path]:
    files: list[Path] = []
    for path in REPO_ROOT.rglob("*.oct.md"):
        if any(part in EXCLUDED_PARTS for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def test_corpus_has_no_duplicate_target_collisions() -> None:
    """Every parseable .oct.md in the in-tree corpus must validate without
    emitting W_DUPLICATE_TARGET. Files that fail to parse for unrelated reasons
    (lexer-side errors out of scope for this invariant) are skipped, not
    asserted against — this test exclusively guards the duplicate-target
    structural invariant.
    """
    files = _iter_corpus_files()
    assert files, "Corpus scan found zero .oct.md files; check REPO_ROOT resolution."

    hits: list[tuple[str, str]] = []
    for path in files:
        try:
            doc = parse(path.read_text(encoding="utf-8"))
        except Exception:
            # Parse failures are out of scope for this invariant. Other tests
            # cover lexer/parser correctness; this test only checks the
            # post-parse structural collision.
            continue
        validator = Validator(schema=None)
        for err in validator.validate(doc):
            if err.code == "W_DUPLICATE_TARGET":
                rel = path.relative_to(REPO_ROOT)
                hits.append((str(rel), err.field_path or "<unknown>"))

    if hits:
        formatted = "\n".join(f"  - {p} (field: {f})" for p, f in hits)
        pytest.fail(
            "W_DUPLICATE_TARGET collision(s) detected in shipped corpus "
            f"({len(hits)} hit(s)):\n{formatted}\n\n"
            "Each hit indicates a Block(K) coexisting with a flat "
            'Assignment("K.X", ...) at the same nesting level — the GH#369 '
            "corruption fingerprint. Repair by nesting the dotted assignment "
            "inside the block or renaming it to remove the prefix collision."
        )
