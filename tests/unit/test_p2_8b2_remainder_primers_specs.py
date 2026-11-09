"""P2-8b2 remainder: the four live primers and the skills, primers and patterns specs speak PITH.

Records: OCTAVE-MCP-P2-8-SKILLS-LANGUAGE-RULINGS-20261101 (follow-on aligns specs, primers),
OCTAVE-MCP-PRIMER-TOKEN-BUDGET-500-20260926 (primers at most 500 cl100k), and the PITH rules in
``pith-spec.md``. The deprecated mythology and ultra-mythic primers are not covered here.

Glyphs stay readable where a reader meets them: inside a fenced ``READING_LEGEND`` (every primer), and the
mastery primer's one schema-definition example (``SCHEMA_EXAMPLE``). Nowhere else.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from test_p2_8_bundled_skills_language import (
    _TELEGRAPHIC,
    GLYPH,
    REPO_ROOT,
    _detect_snake_case_blob,
    _mythology_problems,
    _OPERATORS_CARRY,
    _scan,
    _tokens,
    _validate_content,
)

RES = REPO_ROOT / "src" / "octave_mcp" / "resources"
PRIMERS = {
    name: RES / "primers" / f"octave-{name}-primer.oct.md" for name in ("literacy", "mastery", "compression", "reading")
}
SPECS = {name: RES / "specs" / f"octave-{name}-spec.oct.md" for name in ("skills", "primers", "patterns")}
GLYPH_FENCE_KEYS = {"READING_LEGEND", "SCHEMA_EXAMPLE"}
# What a spec must not teach an author to write.
OLD_TEACHING = re.compile(
    r"atoms[_ ]only|no_prose|stopwords|dense_KEY::value|operators\s+carry|"
    r"\b(zeus|atlas|hermes|athena|apollo|hephaestus|sisyphean|icarian|promethean)\b",
    flags=re.IGNORECASE,
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize("name", PRIMERS)
def test_primer_no_glyphs_outside_a_reading_fence(name: str) -> None:
    outside, blocks = _scan(_text(PRIMERS[name]))
    bad = [f"{n}: {t.strip()[:80]}" for n, t in outside if GLYPH.search(t)]
    bad += [
        f"fence at {b['start']} under {b['parent_key']!r}"
        for b in blocks
        if any(GLYPH.search(ln) for ln in b["lines"]) and b["parent_key"] not in GLYPH_FENCE_KEYS
    ]
    assert not bad, f"{name} primer: glyph outside a reading fence: {bad}"


@pytest.mark.parametrize("name", PRIMERS)
def test_primer_no_mythology_as_instruction_vocabulary(name: str) -> None:
    assert not _mythology_problems(_text(PRIMERS[name])), f"{name} primer: {_mythology_problems(_text(PRIMERS[name]))}"


@pytest.mark.parametrize("name", PRIMERS)
def test_primer_teaches_no_telegraphic_form(name: str) -> None:
    text = _text(PRIMERS[name])
    hits = [m.group(0) for m in _TELEGRAPHIC.finditer(text)] + [m.group(0) for m in _OPERATORS_CARRY.finditer(text)]
    assert not hits and "TELEGRAPHIC_PHRASE" not in text, f"{name} primer teaches the old telegraphic form: {hits}"


@pytest.mark.parametrize("name", PRIMERS)
def test_primer_no_snake_case_blobs(name: str) -> None:
    hits = _detect_snake_case_blob(_text(PRIMERS[name]))
    assert hits == [], f"{name} primer: {len(hits)} W_SNAKE_CASE_BLOB hits, first: {hits[:2]}"


@pytest.mark.parametrize("name", PRIMERS)
def test_primer_names_pith(name: str) -> None:
    assert "PITH" in _text(PRIMERS[name]), f"{name} primer does not name PITH"


# GH-514: under schema META STRICT these three primer META keys are E007; nothing else may be.
KNOWN_E007_FIELDS = {"META.TOKENS", "META.COMPRESSION_TIER", "META.LOSS_PROFILE"}


@pytest.mark.parametrize("name", PRIMERS)
def test_primer_validates_strict_with_only_the_known_meta_e007(name: str) -> None:
    res = _validate_content(_text(PRIMERS[name]))
    errors = {(e.get("code"), e.get("field")) for e in res.get("validation_errors", [])}
    assert errors <= {("E007", f) for f in KNOWN_E007_FIELDS}, errors
    assert not res.get("repairs"), res.get("repairs")


@pytest.mark.parametrize("name", PRIMERS)
def test_primer_loss_profile_is_a_sentence(name: str) -> None:
    m = re.search(r'^\s+LOSS_PROFILE::"([^"]*)"', _text(PRIMERS[name]), flags=re.MULTILINE)
    assert m and " " in m.group(1) and not re.search(r"[\[\]:∧∨]", m.group(1)), "LOSS_PROFILE is not a PITH sentence"


@pytest.mark.parametrize("name", PRIMERS)
def test_primer_at_most_500_cl100k(name: str) -> None:
    assert _tokens(_text(PRIMERS[name])) <= 500


# BLOCKED (reported to the dispatcher): the skills and patterns specs cannot be edited through octave_write
# without silent loss (header comments dropped; lenient parse drops list items; nested section lines mangled),
# and Write/Edit on *.oct.md is not allowed. strict xfail: it turns into a failure the moment the spec is
# aligned, so the marker cannot rot.
_BLOCKED = pytest.mark.xfail(strict=True, reason="spec not editable through octave_write without silent loss")
SPEC_PARAMS = [
    pytest.param("skills", marks=_BLOCKED),
    "primers",
    pytest.param("patterns", marks=_BLOCKED),
]


@pytest.mark.parametrize("name", SPEC_PARAMS)
def test_spec_teaches_no_old_language(name: str) -> None:
    hits = sorted({m.group(0) for m in OLD_TEACHING.finditer(_text(SPECS[name]))})
    assert not hits, f"{name} spec teaches the old language: {hits}"


@pytest.mark.parametrize("name", SPEC_PARAMS)
def test_spec_points_at_pith_spec(name: str) -> None:
    text = _text(SPECS[name])
    assert "pith-spec.md" in text and "PITH" in text, f"{name} spec does not point at pith-spec.md"


def test_canary_old_teaching_fires() -> None:
    assert OLD_TEACHING.search("CONTENT::atoms_only<no_prose_no_rationale>")
    assert OLD_TEACHING.search('EXAMPLE::"ARCHETYPE→ZEUS∨ATLAS"')
    assert OLD_TEACHING.search("drop_narrative⊕stopwords")
    assert OLD_TEACHING.search("AGGRESSIVE<dense_KEY::value⊕operators>")
    assert not OLD_TEACHING.search('CONTENT::"quoted note-form items"')


def test_canary_primer_glyph_scan_fires() -> None:
    doc = 'KEY::"a ⊕ b"\nREADING_LEGEND::\n```\n⊕ synthesis\n```\n'
    outside, blocks = _scan(doc)
    assert [t for _, t in outside if GLYPH.search(t)] and blocks[0]["parent_key"] == "READING_LEGEND"
