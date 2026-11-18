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


def test_loci_carry_the_writer_scope_sentence_verbatim_once() -> None:
    assert _text().count(f'"{WRITER_SCOPE}"') == 1


def test_old_sole_write_path_text_is_gone() -> None:
    assert "sole valid `.oct.md` write path" not in _text()


def test_version_is_5_1_1_in_frontmatter_and_meta() -> None:
    text = _text()
    assert re.search(r'^version: "5\.1\.1"$', text, flags=re.MULTILINE)
    assert re.search(r'^  VERSION::"5\.1\.1"$', text, flags=re.MULTILINE)
    assert "5.1.0" not in text
