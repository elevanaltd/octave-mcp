"""OCTAVE-MCP-LITERACY-WRITER-SCOPE-AND-LIMITS-20261118: octave-literacy section 7h names the writer scope."""

from __future__ import annotations

import re

from test_p2_8_bundled_skills_language import REPO_ROOT

SKILL = REPO_ROOT / "src/octave_mcp/resources/skills/octave-literacy/SKILL.md"

WRITER_SCOPE = (
    "Governance artefacts (decision records, North Stars, ADRs, RFCs, project context) are written only by the "
    "octave-secretary agent through `octave_write` (procedure: octave-tool-reference); library content (agent "
    "files, skill and pattern bodies, archetype files) is written by library-expert through `octave_write`."
)


def _text() -> str:
    return SKILL.read_text(encoding="utf-8")


def _loci_block() -> str:
    text = _text()
    start = text.index("§7h::ENFORCEMENT_LOCI")
    loci = text.index("LOCI::[", start)
    return text[loci : text.index("\n    ]", loci)]


def _frontmatter() -> str:
    parts = _text().split("\n---\n")
    assert _text().startswith("---\n")
    return parts[0]


def _top_level_meta() -> str:
    text = _text()
    start = text.index("\nMETA:\n") + len("\nMETA:\n")
    out = []
    for line in text[start:].split("\n"):
        if line and not line.startswith(" "):
            break
        out.append(line)
    return "\n".join(out)


def test_loci_list_carries_the_writer_scope_sentence_verbatim_once() -> None:
    assert _loci_block().count(f'"{WRITER_SCOPE}"') == 1
    assert _text().count(WRITER_SCOPE) == 1


def test_old_sole_write_path_text_is_gone() -> None:
    assert "sole valid `.oct.md` write path" not in _text()


def test_version_is_5_1_1_in_frontmatter_and_top_level_meta() -> None:
    assert re.findall(r'^version: "([^"]+)"$', _frontmatter(), flags=re.MULTILINE) == ["5.1.1"]
    assert re.findall(r'^  VERSION::"([^"]+)"$', _top_level_meta(), flags=re.MULTILINE) == ["5.1.1"]
    assert "5.1.0" not in _text()


def test_scoped_helpers_fire() -> None:
    assert "version:" in _frontmatter() and "TYPE::SKILL" in _top_level_meta()
    assert "STEP_1" not in _top_level_meta()


# octave-expert-3d ruling on #559 cubic finding 1: UPOG and 7a classify by structure (agent files follow the
# parse-only structure), 7h classifies by writer. The lists stay as they are.
APPLIES_TO_ITEMS = [
    "North Star summaries",
    "architectural decision records",
    "requests for comments",
    "project-context documents",
    "agent definitions",
    "any repeated-entity governance artefact",
]


def test_upog_and_7a_scope_wording_names_governance_and_library_artefacts() -> None:
    text = _text()
    upog = re.search(r'^  UPOG::"([^"]*)"', text, flags=re.MULTILINE)
    assert upog and "structure for governance and library artefacts (" in upog.group(1)
    principle = text[text.index("§7a::ORGANIZING_PRINCIPLE") :].split("\n")[1]
    assert "governance and library bodies are schema-exempt by declaration" in principle


def test_upog_and_7a_lists_and_7h_sentence_are_unchanged() -> None:
    text = _text()
    block = text[text.index("APPLIES_TO::[") : text.index("]", text.index("APPLIES_TO::["))]
    assert re.findall(r'"([^"]+)"', block) == APPLIES_TO_ITEMS
    assert "(North Stars, ADRs, RFCs, project-context docs, agent definitions)" in text
    assert text.count(WRITER_SCOPE) == 1
