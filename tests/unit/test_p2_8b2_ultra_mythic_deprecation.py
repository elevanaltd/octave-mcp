"""P2-8b2 guard: the ultra-mythic family is deprecated and no longer discoverable.

Authority: record ``OCTAVE-MCP-P2-8B-ULTRA-MYTHIC-DEPRECATION-20261106``
(operator ruling Q1, 2026-11-06). The record deprecates three assets and keeps
them packaged for one release so an explicit load by name or path still works:

- ``resources/skills/octave-ultra-mythic/SKILL.md``
- ``resources/primers/octave-mythology-primer.oct.md``
- ``resources/primers/octave-ultra-mythic-primer.oct.md``

Only the discovery routes are removed: the ``NEXT_SKILLS`` entries in
octave-compression and octave-mastery, the ULTRA_MYTHIC pointer in
octave-compression, the compression primer route, and the data-spec selection
rule. The data-spec ULTRA_MYTHIC tier stays, marked deprecated.

Each check is its own test and has a canary, so a clean result on the real
files cannot be vacuous.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RESOURCES = REPO_ROOT / "src" / "octave_mcp" / "resources"

RECORD_TOKEN = "OCTAVE-MCP-P2-8B-ULTRA-MYTHIC-DEPRECATION-20261106"

ULTRA_MYTHIC_SKILL = RESOURCES / "skills" / "octave-ultra-mythic" / "SKILL.md"
DEPRECATED_FILES = {
    "ultra-mythic skill": ULTRA_MYTHIC_SKILL,
    "mythology primer": RESOURCES / "primers" / "octave-mythology-primer.oct.md",
    "ultra-mythic primer": RESOURCES / "primers" / "octave-ultra-mythic-primer.oct.md",
}
COMPRESSION_SKILL = RESOURCES / "skills" / "octave-compression" / "SKILL.md"
MASTERY_SKILL = RESOURCES / "skills" / "octave-mastery" / "SKILL.md"
COMPRESSION_PRIMER = RESOURCES / "primers" / "octave-compression-primer.oct.md"
DATA_SPEC = RESOURCES / "specs" / "octave-data-spec.oct.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _meta_block(text: str) -> str:
    """Return the indented lines under the first ``META:`` line."""
    lines = text.splitlines()
    if "META:" not in lines:
        return ""
    start = lines.index("META:")
    block: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("  "):
            block.append(line)
        else:
            break
    return "\n".join(block)


def _indented_block(text: str, header: str) -> str:
    """Return the lines nested under ``header`` (matched on the stripped line)."""
    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if line.strip() == header]
    if not starts:
        return ""
    start = starts[0]
    indent = len(lines[start]) - len(lines[start].lstrip())
    block: list[str] = []
    for line in lines[start + 1 :]:
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            break
        block.append(line)
    return "\n".join(block)


# ---------------------------------------------------------------------------
# Retention: the files stay at their paths for one release.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("label", list(DEPRECATED_FILES))
def test_deprecated_file_still_packaged_at_its_path(label: str) -> None:
    assert DEPRECATED_FILES[label].is_file(), f"{label} must stay for one release"


# ---------------------------------------------------------------------------
# (a) NEXT_SKILLS no longer names octave-ultra-mythic.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", [COMPRESSION_SKILL, MASTERY_SKILL], ids=["compression", "mastery"])
def test_a_skill_does_not_name_ultra_mythic_skill(path: Path) -> None:
    assert "octave-ultra-mythic" not in _text(path)


# ---------------------------------------------------------------------------
# (b) octave-compression has no ULTRA_MYTHIC pointer.
# ---------------------------------------------------------------------------


def test_b_compression_has_no_ultra_mythic_pointer() -> None:
    assert "ULTRA_MYTHIC" not in _text(COMPRESSION_SKILL)


# ---------------------------------------------------------------------------
# (c) The three deprecated files say so, in META, with reading-only pointers.
# ---------------------------------------------------------------------------


def _deprecation_problems(text: str, ceiling_bound: bool = False) -> list[str]:
    meta = _meta_block(text)
    problems: list[str] = []
    if not re.search(r"^\s*STATUS::DEPRECATED\s*$", meta, re.MULTILINE):
        problems.append("META lacks STATUS::DEPRECATED")
    if "specs/pith-spec.md" not in meta:
        problems.append("META does not point to specs/pith-spec.md (path must resolve from the file)")
    if "octave-mastery" not in meta or "glossary" not in meta.lower():
        problems.append("META does not point to the octave-mastery reading glossary")
    if "reading" not in meta.lower():
        problems.append("META does not say the file is for reading only")
    if RECORD_TOKEN not in meta:
        problems.append("META does not name the record token")
    if not ceiling_bound:
        if "new documents" not in meta.lower():
            problems.append("META does not say the file is not for new documents")
        if "deleted" not in meta.lower():
            problems.append("META does not say when the file is deleted")
    return problems


@pytest.mark.parametrize("label", list(DEPRECATED_FILES))
def test_c_deprecated_file_meta_carries_status_and_pointers(label: str) -> None:
    # The ultra-mythic primer sits at the 500 cl100k primer ceiling, so its note
    # cannot also carry the not-for-new-documents and deleted-next-release wording.
    assert _deprecation_problems(_text(DEPRECATED_FILES[label]), ceiling_bound=label == "ultra-mythic primer") == []


def test_c_canary_active_meta_is_flagged() -> None:
    doc = '===X===\nMETA:\n  TYPE::SKILL\n  VERSION::"1"\n  STATUS::ACTIVE\n===END===\n'
    assert len(_deprecation_problems(doc)) >= 6


# ---------------------------------------------------------------------------
# (d) The compression primer no longer routes to ULTRA_MYTHIC.
# ---------------------------------------------------------------------------


def test_d_compression_primer_has_no_ultra_mythic_route() -> None:
    assert "ULTRA_MYTHIC" not in _text(COMPRESSION_PRIMER)


# ---------------------------------------------------------------------------
# (e) The data-spec tier is deprecated and the selection rule drops it.
# ---------------------------------------------------------------------------


def test_e_data_spec_ultra_mythic_tier_is_marked_deprecated() -> None:
    block = _indented_block(_text(DATA_SPEC), "ULTRA_MYTHIC:")
    assert block, "ULTRA_MYTHIC tier block must stay in the data spec for one release"
    assert re.search(r"^\s*STATUS::DEPRECATED\s*$", block, re.MULTILINE)
    assert RECORD_TOKEN in block


def test_e_data_spec_selection_rule_no_longer_recommends_ultra_mythic() -> None:
    guide = _indented_block(_text(DATA_SPEC), "SELECTION_GUIDE::[")
    assert guide, "SELECTION_GUIDE block must be found"
    assert "use_ULTRA_MYTHIC" not in _text(DATA_SPEC)
    assert "ULTRA_MYTHIC" not in guide


def test_e_canary_block_helper_stops_at_sibling() -> None:
    doc = "T:\n  A:\n    X::1\n  B:\n    Y::2\n"
    assert _indented_block(doc, "A:").strip() == "X::1"


# ---------------------------------------------------------------------------
# Cubic review fixes (PR #548): frontmatter and exact-identifier form.
# ---------------------------------------------------------------------------

OLD_TRIGGERS = [
    "ultra mythic",
    "mythological compression",
    "semantic atoms",
    "identity compression",
    "binding passport",
    "cognitive passport",
    "60% compression",
    "soul preservation",
]


def _frontmatter_line(text: str, key: str) -> str:
    head = text.split("\n---\n", 1)[0]
    lines = [ln for ln in head.splitlines() if ln.startswith(f"{key}:")]
    return lines[0] if lines else ""


def test_f_deprecated_skill_grants_read_only_tools() -> None:
    line = _frontmatter_line(_text(ULTRA_MYTHIC_SKILL), "allowed-tools")
    assert line, "allowed-tools line must stay in the frontmatter"
    assert "Write" not in line and "Edit" not in line
    assert "Read" in line


def test_f_deprecated_skill_no_longer_advertises_authoring_triggers() -> None:
    line = _frontmatter_line(_text(ULTRA_MYTHIC_SKILL), "triggers").lower()
    for old in OLD_TRIGGERS:
        assert old not in line, f"old trigger still advertised: {old}"


def test_f_canary_frontmatter_line_reader() -> None:
    doc = '---\nallowed-tools: ["Read", "Write"]\n---\nbody'
    assert "Write" in _frontmatter_line(doc, "allowed-tools")


def _note_blocks() -> dict[str, str]:
    return {
        "ultra-mythic skill": _meta_block(_text(ULTRA_MYTHIC_SKILL)),
        "mythology primer": _meta_block(_text(DEPRECATED_FILES["mythology primer"])),
        "ultra-mythic primer": _meta_block(_text(DEPRECATED_FILES["ultra-mythic primer"])),
        "data-spec tier": _indented_block(_text(DATA_SPEC), "ULTRA_MYTHIC:"),
    }


@pytest.mark.parametrize("label", ["ultra-mythic skill", "mythology primer", "ultra-mythic primer", "data-spec tier"])
def test_g_record_id_is_backticked_in_each_note(label: str) -> None:
    block = _note_blocks()[label]
    assert f"`{RECORD_TOKEN}`" in block
    assert block.count(RECORD_TOKEN) == block.count(f"`{RECORD_TOKEN}`")


def test_g_canary_bare_id_is_flagged() -> None:
    block = f"note {RECORD_TOKEN} here"
    assert block.count(RECORD_TOKEN) != block.count(f"`{RECORD_TOKEN}`")


def test_f_deprecated_skill_description_is_a_reading_only_notice() -> None:
    line = _frontmatter_line(_text(ULTRA_MYTHIC_SKILL), "description")
    assert line, "description line must stay in the frontmatter"
    value = line.split(":", 1)[1].strip().strip('"')
    assert value.startswith("DEPRECATED")
    for old in ("60% compression", "identity transmission", "binding protocols"):
        assert old not in value, f"description still advertises: {old}"


def test_f_canary_old_description_is_flagged() -> None:
    old = 'description: "Ultra-high density compression for identity transmission, binding protocols"'
    value = _frontmatter_line(old, "description").split(":", 1)[1].strip().strip('"')
    assert not value.startswith("DEPRECATED")
    assert "identity transmission" in value
