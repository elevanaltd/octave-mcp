"""GH-453 / AGR OCTAVE-MCP-PRIMER-TOKEN-BUDGET-500-20260926: primer token
budgets stay within the real tokenizer-measured spec ceiling.

The primers spec ``src/octave_mcp/resources/specs/octave-primers-spec.oct.md``
declares a token budget for each primer (§1). This test enforces that
budget against a real LLM tokenizer count rather than a whitespace proxy.

Tokenizer contract
-------------------
Every count in this module is produced by ``tiktoken``'s ``cl100k_base``
encoding, run over the primer file's *canonical bytes* (the file read as
raw bytes and decoded as UTF-8 — no normalization, no stripping). This is
the same measurement basis used to size the SPEC_MAX_TOKENS ceiling below,
so a primer's real cl100k count is directly comparable to it.

The previous version of this module used two whitespace-based proxies
(``len(content.split())`` and the author-declared ``META.TOKENS`` field
compared against a 300-token ceiling). Both proxies silently under-counted
true LLM tokens by 2.7-4.4x (OCTAVE operators glue identifiers without
whitespace), so the guard never fired even though every primer exceeded
the real budget. This module replaces the whitespace proxy outright with
a real tokenizer count, and tightens the declared-``TOKENS`` check to
require it track the measured count (not just an independent ceiling).
The ``cl100k_base`` encoding is loaded lazily (on first use inside a
token-counting test), not at module import, so an offline test runner
only errors the specific tests that need the tokenizer rather than
failing collection for the whole module.

GH-453 makes the operator-legend section additive (adds ``∧`` and ``∨``
glosses to each primer's legend) and names the ``TELEGRAPHIC_PHRASE`` form
in the compression primer plus a cross-reference from the literacy primer.
The canonical-operator and TELEGRAPHIC_PHRASE tests below guard those
additions; they are unrelated to the token-budget measurement change and
are left unchanged.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import pytest
import tiktoken

PRIMERS_DIR = Path(__file__).resolve().parents[2] / "src" / "octave_mcp" / "resources" / "primers"

# Spec ceiling, raised from 300 to 500 per AGR
# OCTAVE-MCP-PRIMER-TOKEN-BUDGET-500-20260926 (governance PR #530), measured
# against real tiktoken cl100k_base counts rather than the whitespace proxy.
SPEC_MAX_TOKENS = 500

# Declared-vs-measured tolerance: the author-declared META.TOKENS value must
# track the real cl100k_base count within this fraction.
DECLARED_TOLERANCE = 0.10

PRIMER_FILES = sorted(PRIMERS_DIR.glob("*.oct.md"))

# Match TOKENS::"240" (canonical plain-number form). A legacy leading
# approximation tilde ("~240") is still accepted for parsing so this test
# does not force a primer-content edit in the same step that raises the
# ceiling; the canonical authoring form going forward is the bare number.
_TOKENS_DECL_RE = re.compile(r'TOKENS::"~?(\d+)"')


@lru_cache(maxsize=1)
def _encoding() -> tiktoken.Encoding:
    """Lazily load the cl100k_base encoding on first use.

    Loading happens inside a test call, not at module collection time, so
    a missing tokenizer/BPE file (e.g. an offline runner with no cached
    ``data-gym-cache``) only errors the token-counting tests below, not
    every test in this module (including the unrelated legend/TELEGRAPHIC
    tests). No skip path: absence of the tokenizer is still a hard error
    for the tests that need it.
    """
    return tiktoken.get_encoding("cl100k_base")


def _measured_tokens(primer_path: Path) -> int:
    """Real cl100k_base token count over the primer's canonical file bytes."""
    content = primer_path.read_bytes().decode("utf-8")
    return len(_encoding().encode(content))


@pytest.mark.parametrize("primer_path", PRIMER_FILES, ids=lambda p: p.name)
def test_primer_token_count_within_spec_ceiling(primer_path: Path) -> None:
    """Real tiktoken cl100k_base count must stay <= TOKEN_BUDGET::MAX[500]."""
    measured = _measured_tokens(primer_path)
    assert measured <= SPEC_MAX_TOKENS, (
        f"{primer_path.name}: measured cl100k_base token count ({measured}) "
        f"exceeds TOKEN_BUDGET::MAX[{SPEC_MAX_TOKENS}] (primers-spec §1)."
    )


@pytest.mark.parametrize("primer_path", PRIMER_FILES, ids=lambda p: p.name)
def test_primer_declared_tokens_matches_measured(primer_path: Path) -> None:
    """META.TOKENS declaration must parse, stay <= the spec ceiling, and
    track the real cl100k_base count within +/-10%.
    """
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

    measured = _measured_tokens(primer_path)
    lower_bound = measured * (1 - DECLARED_TOLERANCE)
    upper_bound = measured * (1 + DECLARED_TOLERANCE)
    assert lower_bound <= declared <= upper_bound, (
        f"{primer_path.name}: declared TOKENS={declared} is not within "
        f"+/-{DECLARED_TOLERANCE:.0%} of the measured cl100k_base count "
        f"({measured}); the authoring contract must track reality."
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


class TestDeclaredTokensHelper:
    """Regression tests for the strict META.TOKENS parser (CRS/TMG rework, PR #531).

    ``_declared_tokens`` must parse ONLY the indented lines inside the file's
    ``META:`` block (up to the first non-indented line), matching a bare-integer
    ``TOKENS::"NNN"`` declaration exactly once. The prior implementation was an
    unanchored whole-file regex search that (a) still accepted a legacy
    ``~``-prefixed value even though every primer now declares an exact count,
    and (b) could match a TOKENS-shaped substring anywhere in the file body,
    not just inside META. Anything malformed, missing, or misplaced must be
    rejected via ``DeclaredTokensError``, not silently accepted or mis-parsed.
    """

    @pytest.mark.parametrize(
        "content,expected",
        [
            pytest.param(
                'META:\n  TOKENS::"463"\n§1::ESSENCE\n',
                463,
                id="valid_meta_tokens",
            ),
            pytest.param(
                'META:\n  VERSION::"1.0"\n  TOKENS::"463"\n  COMPRESSION_TIER::ULTRA\n§1::ESSENCE\n',
                463,
                id="valid_meta_tokens_among_other_meta_fields",
            ),
            pytest.param(
                'META:\n  TOKENS::"463"\n§1::ESSENCE\nTOKENS::"999"\n',
                463,
                id="meta_tokens_wins_over_body_lookalike",
            ),
        ],
    )
    def test_valid_declarations_parse(self, content: str, expected: int) -> None:
        assert _declared_tokens(content) == expected

    @pytest.mark.parametrize(
        "content",
        [
            pytest.param('META:\n  TOKENS::"~300"\n§1::ESSENCE\n', id="legacy_tilde_rejected"),
            pytest.param('META:\n  TOKENS::"300x"\n§1::ESSENCE\n', id="trailing_junk_rejected"),
            pytest.param('META:\n  TOKENS::"3 00"\n§1::ESSENCE\n', id="embedded_space_rejected"),
            pytest.param('META:\n  TOKENS::""\n§1::ESSENCE\n', id="empty_value_rejected"),
            pytest.param(
                'META:\n  VERSION::"1.0"\n§1::ESSENCE\n',
                id="tokens_missing_from_meta_rejected",
            ),
            pytest.param(
                'META:\n  VERSION::"1.0"\n§1::ESSENCE\nTOKENS::"999"\n',
                id="tokens_only_in_body_not_picked_up",
            ),
        ],
    )
    def test_malformed_or_misplaced_declarations_rejected(self, content: str) -> None:
        with pytest.raises(DeclaredTokensError):
            _declared_tokens(content)


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
