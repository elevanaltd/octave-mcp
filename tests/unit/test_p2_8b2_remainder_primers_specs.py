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
    _OPERATORS_CARRY,
    _TELEGRAPHIC,
    GLYPH,
    REPO_ROOT,
    _detect_snake_case_blob,
    _mythology_problems,
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
    assert res.get("errors") == [], res.get("errors")
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


@pytest.mark.parametrize("name", SPECS)
def test_spec_teaches_no_old_language(name: str) -> None:
    hits = sorted({m.group(0) for m in OLD_TEACHING.finditer(_text(SPECS[name]))})
    assert not hits, f"{name} spec teaches the old language: {hits}"


@pytest.mark.parametrize("name", SPECS)
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


# Migration guards for the two full-content rewrites (no silent loss through octave_write).
@pytest.mark.parametrize("name", ["skills", "patterns"])
def test_migrated_spec_dry_run_write_drops_nothing(name: str) -> None:
    import asyncio

    from octave_mcp.mcp.write import WriteTool

    res = asyncio.run(
        WriteTool().execute(target_path="/nonexistent-p2-8b2/dry.oct.md", content=_text(SPECS[name]), dry_run=True)
    )
    codes = [w.get("code") for w in res.get("warnings", [])] + [c.get("code") for c in res.get("corrections", [])]
    lossy = {"W_BARE_LINE_DROPPED", "W_NUMERIC_KEY_DROPPED", "W_DUPLICATE_KEY"}
    assert not lossy & set(codes), sorted(lossy & set(codes))
    assert res.get("errors") == [], res.get("errors")


@pytest.mark.parametrize("name", ["skills", "patterns"])
def test_migrated_spec_keeps_header_comments_as_keyed_notes(name: str) -> None:
    text = _text(SPECS[name])
    assert not re.search(r"^\s*//", text, flags=re.MULTILINE), "a // comment line remains; comments drop on rewrite"
    assert re.search(r"^\s*NOTE", text, flags=re.MULTILINE)


# ---------------------------------------------------------------------------
# #559 rework: SR items 1-3, cubic threads
# ---------------------------------------------------------------------------
READING_FENCE_KEYS = {"READING_LEGEND", "SCHEMA_EXAMPLE"}


def _spec_glyph_hits(text: str) -> list[str]:
    """Glyphs in a spec value, comment or key outside a fenced reading legend or schema example."""
    outside, blocks = _scan(text)
    hits = [f"{n}: {t.strip()[:70]}" for n, t in outside if GLYPH.search(t)]
    hits += [
        f"fence {b['start']} under {b['parent_key']!r}"
        for b in blocks
        if any(GLYPH.search(ln) for ln in b["lines"]) and b["parent_key"] not in READING_FENCE_KEYS
    ]
    return hits


@pytest.mark.parametrize("name", SPECS)
def test_spec_values_have_no_glyph_relations(name: str) -> None:
    hits = _spec_glyph_hits(_text(SPECS[name]))
    assert not hits, f"{name} spec: glyph relation outside a fenced reading legend: {hits}"


def test_spec_glyph_guard_canaries() -> None:
    assert _spec_glyph_hits('KEY::"a⊕b"')
    assert _spec_glyph_hits("// v1→v2 notes")
    assert _spec_glyph_hits('X::"a->b"')
    assert not _spec_glyph_hits("READING_LEGEND:\n  ```\n  ⊕ synthesis\n  ```\n")
    assert _spec_glyph_hits("OTHER:\n  ```\n  ⊕ synthesis\n  ```\n")
    assert not _spec_glyph_hits('KEY::"a and b, then c"')


def test_primers_spec_documents_the_fenced_reading_legend() -> None:
    text = _text(SPECS["primers"])
    assert re.search(
        r"^\s+READING_LEGEND:\s*$", text, flags=re.MULTILINE
    ), "the legend example is not a READING_LEGEND block"
    assert "fenced READING_LEGEND" in text, "§2c does not say the legend must be a fenced READING_LEGEND block"
    valid = text[text.index("VALID_PRIMER") :]
    assert "fenced_READING_LEGEND" in valid or "fenced READING_LEGEND" in valid


def test_primers_spec_does_not_require_ultra_or_present_it_as_current() -> None:
    text = _text(SPECS["primers"])
    assert "compression_tier==ULTRA" not in text
    assert "ULTRA[50%]" not in text
    assert "META_records_its_own_tier_and_loss_profile" in text


def test_compression_primer_has_no_live_aggressive_or_ultra_selection() -> None:
    text = _text(PRIMERS["compression"])
    outside, blocks = _scan(text)
    meta_free = [t for _, t in outside if not t.lstrip().startswith(("COMPRESSION_TIER", "LOSS_PROFILE"))]
    for line in meta_free + [ln for b in blocks for ln in b["lines"]]:
        if re.search(r"AGGRESSIVE|ULTRA", line):
            assert re.search(r"frozen|reading", line, flags=re.IGNORECASE), f"live tier guidance: {line.strip()}"
    assert "choose the tier" not in text
    assert "LOSSLESS" in text and "CONSERVATIVE" in text


def test_literacy_primer_keeps_alert_in_the_one_shot() -> None:
    text = _text(PRIMERS["literacy"])
    assert "page the on-call" not in text
    assert "failed logins alert the on-call" in text


def test_compression_primer_one_shot_keeps_relation_and_subject_and_invents_nothing() -> None:
    text = _text(PRIMERS["compression"])
    shot = text[text.index("§4::ONE_SHOT") : text.index("§5::VALIDATE")]
    assert "validate" not in shot.lower().split("out:")[1]
    out = shot.split("OUT:")[1]
    assert re.search(r'AUTH::"authenticate before the dashboard"', out)
    assert re.search(r'FAIL::"failed logins alert"', out)


def test_reading_primer_mythology_is_read_by_one_domain_not_shorthand() -> None:
    text = _text(PRIMERS["reading"])
    assert "shorthand" not in text
    assert "mythology terms read by their one domain, not as system names" in text


def test_chatter_peer_line_says_no_envelope() -> None:
    chatter = (RES / "skills/octave-chatter/SKILL.md").read_text(encoding="utf-8")
    peer = [ln for ln in chatter.split("\n") if ln.strip().startswith("PEER::")]
    assert len(peer) == 1 and "no envelope" in peer[0], peer


def test_patterns_spec_chassis_example_is_a_nested_block() -> None:
    text = _text(SPECS["patterns"])
    assert re.search(
        r"^( +)PROFILES:\n\1  STANDARD:\n\1    \w+::", text, flags=re.MULTILINE
    ), "PROFILES and STANDARD are not nested parent keys (a real block or a fenced literal example)"


# ---------------------------------------------------------------------------
# #559 rework 2: cubic threads on 954ff9d
# ---------------------------------------------------------------------------
def test_skills_spec_version_is_9_2_0_and_the_skill_schema_implements_it() -> None:
    spec = _text(SPECS["skills"])
    assert re.search(r'^  VERSION::"9\.2\.0"$', spec, flags=re.MULTILINE)
    schema = (RES / "specs/schemas/skill.oct.md").read_text(encoding="utf-8")
    assert 'IMPLEMENTS_SPEC::"octave-skills-spec@9.2.0"' in schema


def test_primers_spec_meta_records_its_own_loss_profile() -> None:
    text = _text(SPECS["primers"])
    meta = text[: text.index("§1::")]
    assert re.search(r"^  COMPRESSION_TIER::", meta, flags=re.MULTILINE)
    m = re.search(r'^  LOSS_PROFILE::"([^"]*)"', meta, flags=re.MULTILINE)
    assert m and " " in m.group(1) and not re.search(r"[\[\]:]", m.group(1)), "LOSS_PROFILE is not a PITH sentence"


def test_primers_spec_legend_example_has_at_least_four_operator_rows() -> None:
    _, blocks = _scan(_text(SPECS["primers"]))
    legend = [b for b in blocks if b["parent_key"] == "READING_LEGEND"]
    assert len(legend) == 1
    rows = [ln for ln in legend[0]["lines"] if ln.strip()]
    assert len(rows) >= 4, rows


def test_compression_primer_states_the_conservative_default() -> None:
    assert "otherwise choose CONSERVATIVE" in _text(PRIMERS["compression"])
