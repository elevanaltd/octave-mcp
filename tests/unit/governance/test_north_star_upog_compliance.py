"""Regression guard: North Star governance docs MUST be UPOG-compliant.

UPOG = Universal Parse-Only Governance (octave-literacy SKILL.md
§8::UNIVERSAL_GOVERNANCE_GRAMMAR).

WHY THIS TEST EXISTS
--------------------
The legacy immutable form ``I1::NAME::[PRINCIPLE::v, WHY::v, STATUS::v]`` and
the sibling chained form (``I1::NAME`` followed by bare ``PRINCIPLE::``/``WHY::``
/``STATUS::`` keys) silently lose data under the strict 1.13 lexer: the inner
keys hoist to file-top-level and COLLIDE across I1..IN with W_DUPLICATE_KEY
(last-write-wins). Markdown ``## headings`` inside an OCTAVE envelope additionally
fail E_TOKENIZE.

CRITICAL: the bundled regex validator (tools/octave-validator.py) does NOT detect
this — it reports the broken form as "valid". Detection MUST use the strict lexer
(``octave_mcp.core.parser.parse_with_warnings``), which is what this test does.

This guard asserts every committed North Star ``.oct.md`` governance artefact:
  * tokenises without raising ``LexerError``, and
  * emits ZERO data-loss warnings of subtype
    {duplicate_key, bare_line_dropped, bare_flow, multi_word_coalesce}.

The NEGATIVE-CONTROL tests prove the detector actually fires on the broken
legacy forms — guarding against a regression where the detector silently stops
working (which would make the positive tests pass vacuously).
"""

from __future__ import annotations

import glob
from pathlib import Path

import pytest

from octave_mcp.core.lexer import LexerError
from octave_mcp.core.parser import parse_with_warnings

# Data-loss warning subtypes that MUST never appear in a governance doc.
# (octave_mcp/core/parser.py emits these as warning dicts with key "subtype".)
FORBIDDEN_SUBTYPES = frozenset(
    {
        "duplicate_key",
        "bare_line_dropped",
        "bare_flow",
        "multi_word_coalesce",
    }
)

# Repo root: tests/unit/governance/test_*.py -> parents[3] == repo root.
REPO_ROOT = Path(__file__).resolve().parents[3]

# UPOG applies to active governance artefacts. North Star OCTAVE docs in this
# repo live under .hestai/north-star/. Bundled-hub NS summaries (if any are
# committed) are also covered. Runtime copies under .hestai-sys/ are gitignored
# and intentionally excluded.
NORTH_STAR_GLOBS = (
    ".hestai/north-star/**/*.oct.md",
    "src/**/_bundled_hub/**/*NORTH-STAR*SUMMARY*.oct.md",
    "src/**/_bundled_hub/**/*NORTH_STAR*SUMMARY*.oct.md",
)


def _discover_north_star_docs() -> list[Path]:
    """Discover committed North Star OCTAVE governance docs (UPOG surface)."""
    found: set[Path] = set()
    for pattern in NORTH_STAR_GLOBS:
        for hit in glob.glob(str(REPO_ROOT / pattern), recursive=True):
            p = Path(hit)
            # Belt-and-braces: never assert on the gitignored runtime copy.
            if ".hestai-sys" in p.parts:
                continue
            found.add(p)
    return sorted(found)


NORTH_STAR_DOCS = _discover_north_star_docs()


def _forbidden(warnings: list[dict]) -> list[dict]:
    return [w for w in warnings if w.get("subtype") in FORBIDDEN_SUBTYPES]


def test_north_star_docs_were_discovered() -> None:
    """Guard against a vacuous pass: the glob MUST find at least one NS doc.

    If this fails, the NS layout moved and NORTH_STAR_GLOBS needs updating —
    otherwise the parametrized tests below would silently cover nothing.
    """
    assert NORTH_STAR_DOCS, (
        "No North Star .oct.md docs discovered under "
        f"{NORTH_STAR_GLOBS!r} relative to {REPO_ROOT}. "
        "Update NORTH_STAR_GLOBS if the layout changed."
    )


@pytest.mark.parametrize(
    "doc",
    NORTH_STAR_DOCS,
    ids=[str(p.relative_to(REPO_ROOT)) for p in NORTH_STAR_DOCS],
)
def test_north_star_doc_tokenises(doc: Path) -> None:
    """Each NS doc MUST tokenise under the strict lexer (no E_TOKENIZE)."""
    content = doc.read_text(encoding="utf-8")
    try:
        parse_with_warnings(content)
    except LexerError as exc:  # pragma: no cover - failure path
        pytest.fail(
            f"{doc.relative_to(REPO_ROOT)} fails strict-lexer tokenisation "
            f"(markdown headings / non-OCTAVE syntax in envelope?): {exc}"
        )


@pytest.mark.parametrize(
    "doc",
    NORTH_STAR_DOCS,
    ids=[str(p.relative_to(REPO_ROOT)) for p in NORTH_STAR_DOCS],
)
def test_north_star_doc_has_no_data_loss_warnings(doc: Path) -> None:
    """Each NS doc MUST emit zero data-loss warnings (UPOG block form)."""
    content = doc.read_text(encoding="utf-8")
    _doc, warnings = parse_with_warnings(content)
    offending = _forbidden(warnings)
    assert not offending, (
        f"{doc.relative_to(REPO_ROOT)} emits data-loss warnings "
        f"(legacy non-UPOG form?): "
        f"{[(w.get('subtype'), w.get('key')) for w in offending]}"
    )


@pytest.mark.parametrize(
    "doc",
    NORTH_STAR_DOCS,
    ids=[str(p.relative_to(REPO_ROOT)) for p in NORTH_STAR_DOCS],
)
def test_north_star_doc_is_structurally_nonvacuous(doc: Path) -> None:
    """Each NS doc MUST parse to a substantive governance document.

    The no-data-loss check above is necessary but not sufficient: a truncated
    or empty envelope tokenises cleanly with zero forbidden warnings yet carries
    no governance content. This guards against that vacuous-pass mode by
    asserting the parsed document has a META envelope (with TYPE) and at least
    one body section — i.e. UPOG block structure actually survived, not merely
    that nothing was dropped.

    (Full octave_validate STRICT compliance — warnings/errors/repairs all empty
    against the META schema under CONTRACT::HOLOGRAPHIC<parse_only_governance> —
    is enforced at author time by the octave_write gate; this test asserts the
    portable, dependency-free structural floor.)
    """
    content = doc.read_text(encoding="utf-8")
    parsed, _warnings = parse_with_warnings(content)
    assert parsed.meta, f"{doc.relative_to(REPO_ROOT)}: missing/empty META envelope"
    assert parsed.meta.get("TYPE"), f"{doc.relative_to(REPO_ROOT)}: META has no TYPE — not a governance artefact"
    assert parsed.sections, (
        f"{doc.relative_to(REPO_ROOT)}: no body sections — empty/truncated doc "
        "would pass the warning check vacuously"
    )


# ---------------------------------------------------------------------------
# NEGATIVE CONTROLS — prove the detector fires on the broken legacy forms.
# These keep the positive tests honest: if the detector ever silently stops
# emitting these warnings, these tests fail and surface the rot.
# ---------------------------------------------------------------------------

LEGACY_CHAINED_IMMUTABLE = """===LEGACY_NS_SUMMARY===
META:
  TYPE::NORTH_STAR_SUMMARY
  VERSION::"1.0"
IMMUTABLES::2
I1::SYNTACTIC_FIDELITY
STATEMENT::normalization_alters_syntax_never_semantics
STATUS::ENFORCED
I2::DETERMINISTIC_ABSENCE
STATEMENT::distinguish_absent_from_null
STATUS::ENFORCED
===END===
"""

LEGACY_MARKDOWN_HEADINGS = """===LEGACY_NS===
META:
  TYPE::NORTH_STAR
  VERSION::"1.0"

## IMMUTABLE REQUIREMENTS (5 Total)

**I1**: Syntactic Fidelity
===END===
"""


def test_negative_control_legacy_chained_form_triggers_duplicate_key() -> None:
    """The legacy chained-assignment form MUST trigger duplicate_key.

    STATEMENT/STATUS hoist to top level and collide across I1/I2. If this
    stops firing, the positive guard above is no longer trustworthy.
    """
    _doc, warnings = parse_with_warnings(LEGACY_CHAINED_IMMUTABLE)
    offending = _forbidden(warnings)
    subtypes = {w.get("subtype") for w in offending}
    assert "duplicate_key" in subtypes, (
        "Detector regression: legacy chained immutable form no longer emits "
        f"duplicate_key. Got warnings: {[w.get('subtype') for w in warnings]}"
    )


def test_negative_control_markdown_headings_fail_tokenisation() -> None:
    """Markdown ``## headings`` inside an envelope MUST raise LexerError.

    If this stops raising, the tokenisation guard above is no longer
    trustworthy.
    """
    with pytest.raises(LexerError):
        parse_with_warnings(LEGACY_MARKDOWN_HEADINGS)


EMPTY_ENVELOPE = """===EMPTY_NS===
META:
  TYPE::NORTH_STAR_SUMMARY
  VERSION::"1.0"
===END===
"""


def test_negative_control_empty_envelope_is_structurally_vacuous() -> None:
    """An empty envelope tokenises clean yet has NO body sections.

    Proves the structural-nonvacuity guard above is load-bearing: this doc emits
    zero forbidden warnings (would pass the warning check) but MUST be caught by
    the empty-sections assertion.
    """
    parsed, warnings = parse_with_warnings(EMPTY_ENVELOPE)
    assert not _forbidden(warnings), "fixture should emit no data-loss warnings"
    assert not parsed.sections, (
        "Guard regression: empty envelope unexpectedly reports body sections — "
        "the structural-nonvacuity test would no longer catch truncated docs"
    )
