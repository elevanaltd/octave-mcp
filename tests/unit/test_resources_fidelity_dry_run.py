"""Every shipped ``*.oct.md`` resource passes ``octave_write``'s fidelity rule in a content-mode dry run.

Records: OCTAVE-MCP-DIRECTION-RULINGS-AMENDMENT-20261117 (WRITE_RULE: refuse writes that drop or alter
content). A shipped resource that the tool would refuse cannot be maintained through the tool, so each one
must round-trip with ``status == "success"``.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from octave_mcp.mcp.write import WriteTool

REPO_ROOT = Path(__file__).resolve().parents[2]
RESOURCES = REPO_ROOT / "src" / "octave_mcp" / "resources"
RESOURCE_FILES = sorted(RESOURCES.rglob("*.oct.md"))

# Files whose refusal is a product (emitter) defect, not an input defect: no workaround in the spec text.
# strict=True makes the xfail fail loudly the moment the emitter is fixed, so the mark gets removed.
EMITTER_DEFECTS: dict[str, str] = {}


def _param(path: Path) -> object:
    rel = path.relative_to(RESOURCES).as_posix()
    reason = EMITTER_DEFECTS.get(rel)
    marks = [pytest.mark.xfail(strict=True, reason=reason)] if reason else []
    return pytest.param(path, id=rel, marks=marks)


def test_resource_corpus_is_not_vacuous() -> None:
    assert len(RESOURCE_FILES) >= 31, len(RESOURCE_FILES)


@pytest.mark.parametrize("path", [_param(p) for p in RESOURCE_FILES])
def test_resource_dry_run_write_succeeds(path: Path) -> None:
    result = asyncio.run(
        WriteTool().execute(target_path=str(path), content=path.read_text(encoding="utf-8"), dry_run=True)
    )
    assert result.get("status") == "success", (
        result.get("fidelity_violation_counts"),
        result.get("fidelity_violations"),
        result.get("errors"),
    )
