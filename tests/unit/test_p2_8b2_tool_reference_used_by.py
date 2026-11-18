"""OCTAVE-MCP-TOOL-REFERENCE-USED-BY-SCOPE-20261118 (PR #560): tool-reference section 8 USED_BY is rebuilt from
the hestai-workbench archetype-matrix rows that load octave-tool-reference, not from the legacy hub load roster.
"""

from __future__ import annotations

import re

from test_p2_8_bundled_skills_language import REPO_ROOT

TOOL_REFERENCE = REPO_ROOT / "src/octave_mcp/resources/patterns/octave-tool-reference.oct.md"

# Measured from elevanaltd/hestai-workbench resources/starter-library/config/archetype-matrix.json at
# commit dbbfa137b41dc43241f074206daf47a89fd6a5c4 (origin/main, 2026-11-18). Every row naming
# octave-tool-reference: octave-secretary, profiles document_authoring and context_maintenance, both under
# "patterns" (the matrix's default kernel extraction); no kernel_only row, no other role.
MATRIX_SHA = "dbbfa137b41dc43241f074206daf47a89fd6a5c4"
MEASURED_ROSTER = ["octave-secretary"]
MEASURED_PROFILES = ["document_authoring", "context_maintenance"]
STALE_NAMES = ["north-star-architect", "system-steward", "agent-expert", "skills-expert", "octave-specialist"]


def _used_by() -> str:
    text = TOOL_REFERENCE.read_text(encoding="utf-8")
    return text[text.index("§8::USED_BY") : text.index("===END===")]


def _list(key: str) -> list[str]:
    m = re.search(rf"^  {key}::\[([^\]]*)\]", _used_by(), flags=re.MULTILINE)
    assert m, f"no {key} list in §8::USED_BY"
    return [x.strip().strip('"') for x in m.group(1).split(",") if x.strip()]


def test_stale_legacy_roster_names_are_gone_from_used_by() -> None:
    used = _used_by()
    assert [n for n in STALE_NAMES if n in used] == []


def test_used_by_agents_equal_the_measured_matrix_roster() -> None:
    assert _list("AGENTS") == MEASURED_ROSTER


def test_used_by_names_the_matrix_profiles_and_no_kernel_only_row() -> None:
    used = _used_by()
    assert all(p in used for p in MEASURED_PROFILES)
    assert re.search(r'^  KERNEL_ONLY::"none', used, flags=re.MULTILINE)


def test_used_by_names_octave_secretary_as_the_only_governance_writer() -> None:
    assert "octave-secretary is the only governance writer" in _used_by()


def test_used_by_cites_the_measured_matrix_commit() -> None:
    assert MATRIX_SHA[:7] in _used_by()


def test_other_section_8_keys_are_kept() -> None:
    used = _used_by()
    assert 'CONTEXT::"document authoring, context maintenance, governance artefact amendment"' in used
    assert (
        'UPSTREAM::"octave-mcp is upstream; copies elsewhere are synced from it and are never a re-alignment source"'
        in used
    )
