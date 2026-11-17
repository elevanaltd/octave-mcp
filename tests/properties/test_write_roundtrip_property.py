"""R3 -- write fidelity properties (tool-fidelity slice 1, PR-2: parts a, b, d).

Build plan: tool-fidelity slice 1, section 5 R3. Part c (a changes-mode edit
leaves every other top-level node byte-identical) needs F3 and the
changes-mode preserve default, so it lands with PR-3.

  a. When a content-mode write succeeds, F1 and F2 both hold.
  b. Idempotence: writing the output again gives the same bytes and no
     corrections.
  d. Every refusal leaves the file untouched.
"""

from __future__ import annotations

import asyncio
import os
import tempfile

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from octave_mcp.core.parser import parse
from octave_mcp.mcp.write import WriteTool

_TOOL = WriteTool()

_KEY = st.from_regex(r"[A-Z][A-Z0-9_]{0,7}", fullmatch=True).filter(lambda k: k not in {"META", "END"})
_WORD = st.from_regex(r"[a-z][a-z0-9_]{0,7}", fullmatch=True).filter(lambda w: w not in {"true", "false", "null", "vs"})
_QUOTED = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters=" .,-", max_codepoint=127),
    min_size=1,
    max_size=20,
)


@st.composite
def _scalar(draw: st.DrawFn) -> str:
    kind = draw(st.sampled_from(["word", "quoted", "number", "bool", "list"]))
    if kind == "word":
        return draw(_WORD)
    if kind == "quoted":
        return '"' + draw(_QUOTED) + '"'
    if kind == "number":
        return str(draw(st.integers(min_value=0, max_value=999)))
    if kind == "bool":
        return draw(st.sampled_from(["true", "false"]))
    items = draw(st.lists(_WORD, min_size=1, max_size=4))
    return "[" + ",".join(items) + "]"


@st.composite
def _document(draw: st.DrawFn) -> str:
    lines = ["===DOC===", "META:", "  TYPE::T", '  VERSION::"1"']
    used: set[str] = set()
    for _ in range(draw(st.integers(min_value=1, max_value=5))):
        key = draw(_KEY.filter(lambda k: k not in used))
        used.add(key)
        if draw(st.booleans()):
            lines.append(f"// note {draw(_WORD)}")
        shape = draw(st.sampled_from(["assign", "block", "section", "literal"]))
        if shape == "assign":
            lines.append(f"{key}::{draw(_scalar())}")
        elif shape == "block":
            lines.append(f"{key}:")
            child_keys = draw(st.lists(_KEY, min_size=1, max_size=3, unique=True))
            for ck in child_keys:
                lines.append(f"  {ck}::{draw(_scalar())}")
        elif shape == "section":
            lines.append(f"§{len(used)}::{key}")
            lines.append(f"  {draw(_KEY)}::{draw(_scalar())}")
        else:
            lines.append(f"{key}::")
            lines.append("```text")
            lines.append(draw(_WORD) + " " + draw(_WORD))
            lines.append("```")
    lines.append("===END===")
    return "\n".join(lines) + "\n"


def _write(path: str, **kwargs: object) -> dict:
    return asyncio.run(_TOOL.execute(target_path=path, **kwargs))


_SETTINGS = settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])


@_SETTINGS
@given(_document())
def test_success_implies_f1_and_f2_hold_and_output_is_idempotent(content: str) -> None:
    from octave_mcp.mcp.write_fidelity import lexical_violations, semantic_projection

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "doc.oct.md")
        first = _write(path, content=content)
        if first["status"] != "success":
            assert "E_FIDELITY" in [e["code"] for e in first["errors"]]
            assert not os.path.exists(path)
            return
        with open(path, encoding="utf-8") as f:
            written = f.read()
        # a. F1 and F2 hold on the written output.
        assert lexical_violations(content, written) == []
        assert semantic_projection(parse(written)) == semantic_projection(parse(content))
        # b. Idempotence: a second write is a byte-identical no-op.
        second = _write(path, content=written)
        assert second["status"] == "success", second
        with open(path, encoding="utf-8") as f:
            assert f.read() == written
        assert [c for c in second["corrections"] if c.get("tier") != "STRUCTURAL_CHECK"] == []


@_SETTINGS
@given(_document(), st.sampled_from(["  stray words here", "1::numeric"]))
def test_every_refusal_leaves_the_file_untouched(content: str, lossy_line: str) -> None:
    lines = content.splitlines()
    # Insert a lossy line inside the body (after META) so the parser drops it.
    lossy = "\n".join(lines[:4] + ["HOST:", "  K::v", lossy_line] + lines[4:]) + "\n"
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "doc.oct.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        with open(path, "rb") as f:
            before = f.read()
        result = _write(path, content=lossy)
        assert result["status"] == "error", result
        assert "E_FIDELITY" in [e["code"] for e in result["errors"]]
        with open(path, "rb") as f:
            assert f.read() == before
