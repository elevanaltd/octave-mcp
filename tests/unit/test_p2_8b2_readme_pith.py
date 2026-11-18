"""OCTAVE-MCP-P2-8B2-README-REWRITE-20261118: the README presents PITH as the writing standard.

OCTAVE is the strict container (schema validation, repair log, loss receipts). Operators and mythology are no
longer sold as an authoring or compression technique; documents that use them stay readable.
"""

from __future__ import annotations

import re
from pathlib import Path

from test_p2_8_bundled_skills_language import _scan

# Operator glyphs only. The skills GLYPH regex also flags a spaced "|" or "+", which a README uses in tables.
GLYPH = re.compile(r"[⊕⇌∧∨→∴⧺]|<->|->")
ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
MYTH = re.compile(
    r"\b(sisyphean|sisyphus|artemis|chronos|demeter|athena|odyssean|solomonic|hermes|zeus|apollo|hephaestus)\b",
    flags=re.IGNORECASE,
)
SELLING = re.compile(
    r"semantic\s+zip|mythological\s+compression|mythology\s+(?:works|isn't|is)\s|pre-compressed|"
    r"that's not branding|encourage operational use",
    flags=re.IGNORECASE,
)


def _text() -> str:
    return README.read_text(encoding="utf-8")


def _outside_fences(text: str) -> str:
    outside, _ = _scan(text)
    return "\n".join(t for _, t in outside)


def test_no_semantic_zip_or_mythology_selling() -> None:
    hits = sorted({m.group(0).lower() for m in SELLING.finditer(_text())})
    assert not hits, f"README still sells mythology as compression: {hits}"


def test_no_mythology_names_anywhere() -> None:
    hits = sorted({m.group(1).upper() for m in MYTH.finditer(_text())})
    assert not hits, f"README still uses mythology as vocabulary: {hits}"


def test_no_glyphs_outside_fences() -> None:
    bad = [ln.strip()[:80] for ln in _outside_fences(_text()).split("\n") if GLYPH.search(ln)]
    assert not bad, f"glyphs in README prose: {bad}"


def test_names_pith_and_links_the_spec() -> None:
    text = _text()
    assert "PITH" in text
    assert "(src/octave_mcp/resources/specs/pith-spec.md)" in text
    assert (ROOT / "src/octave_mcp/resources/specs/pith-spec.md").is_file()


def test_says_existing_operator_documents_stay_readable() -> None:
    text = _outside_fences(_text()).lower()
    assert "stay readable" in text or "remain readable" in text


def test_keeps_three_audience_structure() -> None:
    text = _text()
    for h in ("## For Engineers", "## For Researchers", "## For AI Agents"):
        assert h in text, h


def test_relative_links_and_anchors_resolve() -> None:
    text = _text()
    heads = {
        re.sub(r"[^a-z0-9 -]", "", m.group(1).strip().lower()).replace(" ", "-")
        for m in re.finditer(r"^#+ (.+)$", text, flags=re.MULTILINE)
    }
    for target in re.findall(r"\]\(([^)]+)\)", text):
        if target.startswith("#"):
            assert target[1:] in heads, f"dead anchor {target}"
        elif not target.startswith(("http", "mailto")):
            assert (ROOT / target.split("#")[0]).exists(), f"dead link {target}"


def test_canaries_fire() -> None:
    assert SELLING.search("work like semantic zip files")
    assert SELLING.search("### Mythological compression")
    assert MYTH.search("`ARTEMIS::x`")
    assert not MYTH.search("plain words only")
