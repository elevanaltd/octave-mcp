"""GH-453 regression guard: primer token budgets stay within spec.

The primers spec ``src/octave_mcp/resources/specs/octave-primers-spec.oct.md``
declares ``TOKEN_BUDGET::MAX[300]`` (§1) and asserts ``tokens<300`` as a
``VALID_PRIMER`` criterion (§5).

GH-453 makes the operator-legend section additive (adds ``∧`` and ``∨``
glosses to each primer's legend) and names the ``TELEGRAPHIC_PHRASE`` form
in the compression primer plus a cross-reference from the literacy primer.
This test guards against any of those additions (or future ones) tipping a
primer past the spec ceiling.

Token-budget proxy
------------------
No project-wide LLM tokenizer dependency exists, so we use two
complementary, deterministic proxies that together bracket the spec
intent:

1. The author-declared ``META.TOKENS`` field MUST parse to ``<= 300``.
   The spec treats this as the authoring contract.
2. A conservative whitespace-token count (``len(content.split())``) MUST
   stay under a generous ceiling. This proxy under-counts true LLM tokens
   (OCTAVE operators glue identifiers without whitespace) so we use a
   ceiling of 300 directly — if the whitespace-token count alone exceeds
   300 the primer is unambiguously over budget. Today the highest is
   ``octave-mythology-primer.oct.md`` at 122; the additive legend lines
   from GH-453 add ~6 tokens per primer, leaving wide headroom.

Both proxies are documented here so a future change that introduces a
real tokenizer can replace the second proxy without losing the contract.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PRIMERS_DIR = Path(__file__).resolve().parents[2] / "src" / "octave_mcp" / "resources" / "primers"

# Spec ceiling from octave-primers-spec.oct.md §1::DEFINITION TOKEN_BUDGET::MAX[300]
SPEC_MAX_TOKENS = 300

PRIMER_FILES = sorted(PRIMERS_DIR.glob("*.oct.md"))

# Match TOKENS::"~240" or TOKENS::"240" (with or without leading approximation tilde).
_TOKENS_DECL_RE = re.compile(r'TOKENS::"~?(\d+)"')


@pytest.mark.parametrize("primer_path", PRIMER_FILES, ids=lambda p: p.name)
def test_primer_declared_tokens_within_spec_ceiling(primer_path: Path) -> None:
    """META.TOKENS declaration must parse and be <= TOKEN_BUDGET::MAX[300]."""
    content = primer_path.read_text(encoding="utf-8")
    match = _TOKENS_DECL_RE.search(content)
    assert match is not None, (
        f"{primer_path.name}: META.TOKENS field missing or unparseable; "
        f"primers-spec requires authoring contract on token budget."
    )
    declared = int(match.group(1))
    assert declared <= SPEC_MAX_TOKENS, (
        f"{primer_path.name}: declared TOKENS={declared} exceeds "
        f"TOKEN_BUDGET::MAX[{SPEC_MAX_TOKENS}] (primers-spec §1)."
    )


@pytest.mark.parametrize("primer_path", PRIMER_FILES, ids=lambda p: p.name)
def test_primer_whitespace_token_proxy_under_ceiling(primer_path: Path) -> None:
    """Conservative whitespace-token count must stay under spec ceiling.

    This is an under-count of true LLM tokens (OCTAVE glues operators
    without whitespace), so exceeding 300 here is unambiguous over-budget.
    """
    content = primer_path.read_text(encoding="utf-8")
    whitespace_tokens = len(content.split())
    assert whitespace_tokens <= SPEC_MAX_TOKENS, (
        f"{primer_path.name}: whitespace-token proxy "
        f"({whitespace_tokens}) exceeds {SPEC_MAX_TOKENS}. "
        f"This is an under-count of true LLM tokens; the primer is over budget."
    )


CANONICAL_OPERATORS = ("::", "→", "⊕", "⇌", "∧", "∨")


@pytest.mark.parametrize("primer_path", PRIMER_FILES, ids=lambda p: p.name)
def test_primer_legends_canonical_operator_set(primer_path: Path) -> None:
    """GH-453 Finding 1: every primer's operator-legend area must mention
    each canonical operator [::, →, ⊕, ⇌, ∧, ∨].

    The legend area is conventionally §3::SYNTAX, but the reading primer
    uses §2::MAP as its legend (named operators: ASSIGN/FLOW/TENSION/
    SYNTHESIS/...). We therefore search the whole primer text for each
    operator glyph; absence anywhere is a legend gap.
    """
    content = primer_path.read_text(encoding="utf-8")
    missing = [op for op in CANONICAL_OPERATORS if op not in content]
    assert not missing, (
        f"{primer_path.name}: missing canonical operator(s) {missing} "
        f"from primer body/legend. GH-453 Option A requires the canonical "
        f"set [::, →, ⊕, ⇌, ∧, ∨] to be legended in every primer."
    )


def test_compression_primer_names_telegraphic_phrase() -> None:
    """GH-453 Finding 2: the compression primer must name the
    operator-bearing-quoted-value form as ``TELEGRAPHIC_PHRASE``.
    """
    path = PRIMERS_DIR / "octave-compression-primer.oct.md"
    content = path.read_text(encoding="utf-8")
    assert "TELEGRAPHIC_PHRASE" in content, (
        f"{path.name}: GH-453 Finding 2 requires a named form " f"(TELEGRAPHIC_PHRASE::...) in §1::ESSENCE or §2::MAP."
    )


def test_literacy_primer_cross_references_telegraphic_phrase() -> None:
    """GH-453: literacy primer must cross-reference the named form so
    both reader-facing primers expose the label.
    """
    path = PRIMERS_DIR / "octave-literacy-primer.oct.md"
    content = path.read_text(encoding="utf-8")
    assert "TELEGRAPHIC_PHRASE" in content, (
        f"{path.name}: GH-453 requires a cross-reference to " f"TELEGRAPHIC_PHRASE (named in compression primer)."
    )


def test_all_six_primers_present() -> None:
    """Sanity: GH-453 acceptance assumes the six canonical primers."""
    names = {p.name for p in PRIMER_FILES}
    expected = {
        "octave-compression-primer.oct.md",
        "octave-literacy-primer.oct.md",
        "octave-mastery-primer.oct.md",
        "octave-mythology-primer.oct.md",
        "octave-reading-primer.oct.md",
        "octave-ultra-mythic-primer.oct.md",
    }
    assert expected.issubset(names), (
        f"Missing primers: {expected - names}; GH-453 acceptance requires "
        f"all six canonical primers under src/octave_mcp/resources/primers/."
    )
