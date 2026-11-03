"""P2-8b1 drift test: the PITH writing-standard spec and the four shipped kernels.

Implements design spec ``.hestai-state/reports/2026-11-03-p2-8b-change-spec.md`` r3, section 3.3.
Ownership: this file owns the *standard* and *container* kernel strings (it reads them
from the machine-readable list in ``src/octave_mcp/resources/specs/pith-spec.md``).
``test_p2_8_bundled_skills_language.py`` (A8) keeps key presence and each kernel's own items.

Machine-readable item list, exact format (octave-secretary writes it into the spec)
-----------------------------------------------------------------------------------
Under the ``## Skill kernels`` heading, exactly one fenced block whose info string is
``text``. One item per line, ``tag: item``:

- ``tag`` is ``standard`` or ``container`` (lower case), then a colon and one space;
- ``item`` is the exact kernel string, with no surrounding quotes (a literal ``"`` is
  written as ``"``, not escaped); it may itself contain ``: ``, because a line splits at
  the first ``: `` only;
- blank lines are ignored; any other line shape fails the test; items are unique.

Declared limits (review constrains these, not this test)
--------------------------------------------------------
- A skill's own kernel items are checked against ``OWN_KERNEL_STRINGS`` in the P2-8 test
  file only. Adding an item plus a row there passes. Review constrains own items.
- Rewording the body of a rule on the page is not detected. This test pins strings, not teaching.
- Pointers into other repositories are not checked (not reachable in CI).

Environment: the workbench regex runs in ``node`` (same as the P2-8 test).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
from test_p2_8_bundled_skills_language import (
    ALL,
    GLYPH,
    KERNEL_CAP_CL100K,
    OWN_KERNEL_STRINGS,
    REPO_ROOT,
    SKILLS,
    WORKBENCH_JS,
    _key_text,
    _odyssean_kernel,
    _read,
    _scan,
    _tokens,
    _workbench_kernel,
)

SPEC_REL = "src/octave_mcp/resources/specs/pith-spec.md"
SPEC_PATH = REPO_ROOT / SPEC_REL
CONTAINER_ONLY = ["tool-reference"]
TARGET_FORM = {"literacy": "in PITH", "mastery": "written in PITH", "compression": "written in PITH"}
UNCHECKED_HEADING = "Runbook steps"  # the page says this rule has no kernel item

# (repo-relative path, content token, tolerance in lines). The spec must carry at least one
# pointer to that path whose line is within tolerance of a line holding the token.
# tolerance 0 means "at" the line; otherwise "near". Cross-repo pointers are not checked.
CONTENT_TOKENS: list[tuple[str, str, int]] = [
    ("src/octave_mcp/core/parser.py", "bare_flow", 2),
    ("src/octave_mcp/core/parser.py", "bare_line_dropped", 2),
    ("src/octave_mcp/core/parser.py", "numeric_key_dropped", 2),
    ("src/octave_mcp/mcp/write_detection.py", "W_SNAKE_CASE_BLOB", 0),
    ("src/octave_mcp/mcp/write_detection.py", "W_FLAT_PREFIX_SCALAR", 2),
    ("src/octave_mcp/core/grammar/tier_normalize.py", "RULE_IDENTIFIER_DEQUOTE", 0),
    ("src/octave_mcp/mcp/write.py", 'result["warnings"] = [', 2),
]

POINTER = re.compile(r"(?<![\w/.\-])((?:[\w.\-]+/)*[\w.\-]+\.(?:py|ts|mjs|md|json)):(\d+)(?:-(\d+))?")
_ITEM = re.compile(r'"((?:[^"\\]|\\.)*)"')


# ---------------------------------------------------------------------------
# Spec readers
# ---------------------------------------------------------------------------
def _spec_text() -> str:
    assert SPEC_PATH.is_file(), f"pith-spec.md is not shipped yet: {SPEC_REL} does not exist"
    return SPEC_PATH.read_text(encoding="utf-8")


def _h2_section(spec: str, heading: str) -> list[str]:
    lines = spec.split("\n")
    out: list[str] = []
    inside = False
    fence = False
    for line in lines:
        if line.lstrip().startswith("```"):
            fence = not fence
        if not fence and line.startswith("## "):
            inside = line[3:].strip() == heading
            continue
        if inside:
            out.append(line)
    return out


def _parse_item_list(spec: str) -> tuple[list[tuple[str, str]], list[str]]:
    """Return ([(tag, item)], problems) from the Skill kernels `text` fence."""
    section = _h2_section(spec, "Skill kernels")
    if not section:
        return [], ["no '## Skill kernels' section"]
    blocks: list[list[str]] = []
    cur: list[str] | None = None
    for line in section:
        s = line.strip()
        if cur is None:
            if s == "```text":
                cur = []
        elif s == "```":
            blocks.append(cur)
            cur = None
        else:
            cur.append(line)
    if len(blocks) != 1:
        return [], [f"expected exactly one ```text fence under Skill kernels, found {len(blocks)}"]
    items: list[tuple[str, str]] = []
    problems: list[str] = []
    for raw in blocks[0]:
        if not raw.strip():
            continue
        m = re.match(r"^(standard|container): (\S.*)$", raw.rstrip())
        if not m:
            problems.append(f"bad list line (want 'standard: item' or 'container: item'): {raw!r}")
            continue
        items.append((m.group(1), m.group(2)))
    texts = [t for _, t in items]
    dupes = sorted({t for t in texts if texts.count(t) > 1})
    if dupes:
        problems.append(f"duplicate items: {dupes}")
    for tag in ("standard", "container"):
        if not any(t == tag for t, _ in items):
            problems.append(f"no '{tag}' items in the list")
    return items, problems


def _items_or_fail() -> list[tuple[str, str]]:
    items, problems = _parse_item_list(_spec_text())
    assert not problems, f"item list: {problems}"
    return items


def _kernel_items(kernel: str, key: str) -> list[str] | None:
    body = _key_text(kernel, key)
    if body is None:
        return None
    return [m.group(1).replace('\\"', '"') for m in _ITEM.finditer(body)]


# ---------------------------------------------------------------------------
# Check functions (each returns problems; canaries call them on synthetic input)
# ---------------------------------------------------------------------------
def _mapping_problems(name: str, kernel: str, items: list[tuple[str, str]]) -> list[str]:
    never = _kernel_items(kernel, "NEVER")
    must = _kernel_items(kernel, "MUST")
    if never is None or must is None:
        return ["NEVER or MUST key absent"]
    standard = [t for tag, t in items if tag == "standard"]
    container = [t for tag, t in items if tag == "container"]
    listed = set(standard) | set(container)
    own = set(OWN_KERNEL_STRINGS[name].get("NEVER", [])) | set(OWN_KERNEL_STRINGS[name].get("MUST", []))
    problems: list[str] = []
    wanted = container if name in CONTAINER_ONLY else standard + container
    problems += [f"MUST lacks listed item: {t}" for t in wanted if t not in must]
    if name in CONTAINER_ONLY:
        problems += [f"container-only kernel carries standard item: {t}" for t in standard if t in must + never]
    # items of the list belong in MUST, never NEVER
    problems += [f"listed item sits under NEVER: {t}" for t in never if t in listed]
    # orphans: every kernel item is listed or an own item
    problems += [
        f"orphan kernel item (not listed, not own): {t}" for t in never + must if t not in listed and t not in own
    ]
    return problems


def _heading_problems(spec: str, items: list[tuple[str, str]]) -> list[str]:
    rules = _h2_section(spec, "Rules")
    headings = [ln[4:].strip() for ln in rules if ln.startswith("### ")]
    standard = [t for tag, t in items if tag == "standard"]
    problems: list[str] = []
    if not headings:
        problems.append("no '###' rule headings under '## Rules'")
    for h in headings:
        if h == UNCHECKED_HEADING:
            continue
        if not any(t.startswith(h) for t in standard):
            problems.append(f"rule heading with no list item beginning with its name: {h!r}")
    for t in standard:
        if not any(t.startswith(h) for h in headings if h != UNCHECKED_HEADING):
            problems.append(f"standard item with no rule heading: {t!r}")
    return problems


def _target_problems(name: str, kernel: str) -> list[str]:
    target = _key_text(kernel, "TARGET") or ""
    want = TARGET_FORM[name]
    return [] if want in target else [f"TARGET lacks the exact form {want!r}: {target!r}"]


def _meta_keys(text: str) -> list[str]:
    keys: list[str] = []
    inside = False
    for line in text.split("\n"):
        if line.strip() == "META:":
            inside = True
            continue
        if inside:
            if line and not line.startswith(" "):
                break
            m = re.match(r"^\s+([A-Za-z0-9_]+)::", line)
            if m:
                keys.append(m.group(1))
    return keys


def _meta_pith_problems(text: str) -> list[str]:
    return [f"META key names PITH: {k}" for k in _meta_keys(text) if "PITH" in k.upper()]


def _spec_glyph_problems(spec: str) -> list[str]:
    outside, _ = _scan(spec)
    return [f"{n}: {t.strip()[:90]}" for n, t in outside if GLYPH.search(t)]


def _hestai_line_problems(spec: str) -> list[str]:
    outside, _ = _scan(spec)
    hits = [t for _, t in outside if re.search(r"HestAI(?: estate)? repositories", t)]
    public = [t for t in hits if "public" in t]
    if len(hits) != 1 or len(public) != 1:
        return [f"want exactly one line about HestAI repositories mentioning 'public', found {len(hits)}"]
    return []


def _pointer_problems(spec: str, root: Path, tokens: list[tuple[str, str, int]]) -> list[str]:
    problems: list[str] = []
    src_names: dict[str, list[str]] = {}
    for f in (root / "src").rglob("*"):
        if f.is_file():
            src_names.setdefault(f.name, []).append(f.relative_to(root).as_posix())
    found: list[tuple[str, int]] = []
    for m in POINTER.finditer(spec):
        path, start = m.group(1), int(m.group(2))
        owned = path.startswith(("src/octave_mcp/", "tests/")) or Path(path).name in src_names
        if not owned:
            continue  # cross-repo pointer: not checked
        target = root / path
        if not target.is_file():
            problems.append(f"octave-mcp pointer is not a repo-relative existing path: {path}:{start}")
            continue
        n_lines = len(target.read_text(encoding="utf-8").split("\n"))
        if not 1 <= start <= n_lines:
            problems.append(f"pointer line out of range: {path}:{start} (file has {n_lines} lines)")
            continue
        found.append((path, start))
    for path, token, tol in tokens:
        file_lines = (root / path).read_text(encoding="utf-8").split("\n")
        ok = False
        for p, line_no in found:
            if p != path:
                continue
            window = file_lines[max(0, line_no - 1 - tol) : line_no + tol]
            if any(token in ln for ln in window):
                ok = True
                break
        if not ok:
            where = "at" if tol == 0 else f"within {tol} lines of"
            problems.append(f"no pointer to {path} puts {token!r} {where} its line")
    return problems


# ---------------------------------------------------------------------------
# 1. Extractors agree on each of the four kernels (workbench regex in node, odyssean copy)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name", ALL)
def test_extractors_return_equal_text(name: str) -> None:
    text = _read(name)
    wb = _workbench_kernel(text).strip()
    od = (_odyssean_kernel(text) or "").strip()
    assert wb and od, f"{name}: an extractor returned nothing"
    assert wb == od, f"{name}: extractors disagree (workbench {len(wb)} chars, odyssean {len(od)} chars)"


def test_canary_workbench_copy_is_the_line_anchored_form() -> None:
    """Since #664 an inline ===END=== inside a kernel item does not end the workbench kernel."""
    doc = '===S===\n§5::ANCHOR_KERNEL\n  TARGET::"t"\n  MUST::["a ===END=== b"]\n  GATE::"g"\n===END===\n'
    wb = _workbench_kernel(doc)
    assert "GATE::" in wb, "workbench copy truncates at an inline ===END===; it is the pre-#664 regex"
    assert wb.strip() == (_odyssean_kernel(doc) or "").strip()


def test_canary_stale_regex_would_disagree() -> None:
    """The equality check can fire: the pre-#664 terminator truncates where odyssean does not."""
    stale_js = WORKBENCH_JS.replace(r"(?=\n§\d+::|\n===END===|$)", r"(?=\n§\d+::|===END===|$)")
    assert stale_js != WORKBENCH_JS
    doc = '===S===\n§5::ANCHOR_KERNEL\n  TARGET::"t"\n  MUST::["a ===END=== b"]\n  GATE::"g"\n===END===\n'
    stale = subprocess.run(["node", "-e", stale_js], input=doc, capture_output=True, text=True, check=True).stdout
    assert stale.strip() != (_odyssean_kernel(doc) or "").strip()


# ---------------------------------------------------------------------------
# 2. The machine-readable list, and the two-way mapping
# ---------------------------------------------------------------------------
def test_spec_item_list_parses() -> None:
    items = _items_or_fail()
    assert len(items) >= 2


@pytest.mark.parametrize("name", ALL)
def test_kernel_maps_both_ways_to_the_list(name: str) -> None:
    kernel = _odyssean_kernel(_read(name)) or ""
    problems = _mapping_problems(name, kernel, _items_or_fail())
    assert not problems, f"{name}: {len(problems)} mapping problems, first: {problems[:4]}"


def test_every_rule_heading_has_a_list_item() -> None:
    problems = _heading_problems(_spec_text(), _items_or_fail())
    assert not problems, problems


@pytest.mark.parametrize("name", SKILLS)
def test_target_cites_pith_in_words(name: str) -> None:
    kernel = _odyssean_kernel(_read(name)) or ""
    problems = _target_problems(name, kernel)
    assert not problems, f"{name}: {problems}"


@pytest.mark.parametrize("name", ALL)
def test_no_meta_key_names_pith(name: str) -> None:
    problems = _meta_pith_problems(_read(name))
    assert not problems, f"{name}: {problems}"


@pytest.mark.parametrize("name", ALL)
def test_kernel_at_most_cap(name: str) -> None:
    kernel = _odyssean_kernel(_read(name)) or ""
    n = _tokens(kernel)
    assert n <= KERNEL_CAP_CL100K, f"{name}: kernel {n} cl100k > {KERNEL_CAP_CL100K}"


# ---------------------------------------------------------------------------
# 3. The spec itself
# ---------------------------------------------------------------------------
def test_spec_has_no_operator_glyphs_outside_fences() -> None:
    problems = _spec_glyph_problems(_spec_text())
    assert not problems, f"{len(problems)} glyph lines outside fences, first: {problems[:3]}"


def test_spec_pointers_are_repo_relative_and_content_matches() -> None:
    problems = _pointer_problems(_spec_text(), REPO_ROOT, CONTENT_TOKENS)
    assert not problems, problems


def test_spec_carries_the_hestai_repositories_line() -> None:
    problems = _hestai_line_problems(_spec_text())
    assert not problems, problems


# ---------------------------------------------------------------------------
# 4. Canaries: each check fires on synthetic bad input
# ---------------------------------------------------------------------------
GOOD_ITEMS = [
    ("standard", "Note form"),
    ("standard", "Exact identifiers (copied exactly, in backticks; never shortened or merged)"),
    ("container", "no unkeyed lines"),
    ("container", "receipt fields read, not the status"),
]
GOOD_SPEC = (
    "# PITH specification\n\n"
    "Evidence outside octave-mcp refers to the HestAI repositories, not all of which are public.\n\n"
    "## Rules\n\n### Note form\n- x\n\n### Exact identifiers\n- x\n\n### Runbook steps\n- x\n\n"
    "## Skill kernels\n\n- Items.\n```text\n"
    "standard: Note form\n"
    "standard: Exact identifiers (copied exactly, in backticks; never shortened or merged)\n"
    "container: no unkeyed lines\n"
    "container: receipt fields read, not the status\n"
    "```\n\n## Amendment\n- y\n"
)


def _kernel_for(
    name: str, drop: str | None = None, extra_never: str | None = None, extra_must: str | None = None
) -> str:
    own = OWN_KERNEL_STRINGS[name]
    tags = GOOD_ITEMS if name not in CONTAINER_ONLY else [i for i in GOOD_ITEMS if i[0] == "container"]
    must_items = [t for _, t in tags] + own.get("MUST", [])
    never_items = list(own.get("NEVER", []))
    if drop:
        must_items = [t for t in must_items if t != drop]
    if extra_never:
        never_items.append(extra_never)
    if extra_must:
        must_items.append(extra_must)

    def q(xs: list[str]) -> str:
        return "[" + ", ".join('"' + x.replace('"', '\\"') + '"' for x in xs) + "]"

    return f'TARGET::"x"\nNEVER::{q(never_items)}\nMUST::{q(must_items)}\nGATE::"g"\n'


def test_canary_good_synthetic_input_is_clean() -> None:
    items, problems = _parse_item_list(GOOD_SPEC)
    assert not problems and items == GOOD_ITEMS
    assert not _heading_problems(GOOD_SPEC, items)
    for name in ALL:
        assert not _mapping_problems(name, _kernel_for(name), items), name
    assert not _spec_glyph_problems(GOOD_SPEC)
    assert not _hestai_line_problems(GOOD_SPEC)


def test_canary_item_list_format_errors_fire() -> None:
    no_fence = GOOD_SPEC.replace("```text", "```")
    assert _parse_item_list(no_fence)[1]
    bad_tag = GOOD_SPEC.replace("container: no unkeyed lines", "other: no unkeyed lines")
    assert any("bad list line" in p for p in _parse_item_list(bad_tag)[1])
    dupe = GOOD_SPEC.replace("standard: Note form\n", "standard: Note form\nstandard: Note form\n")
    assert any("duplicate" in p for p in _parse_item_list(dupe)[1])
    no_container = "\n".join(ln for ln in GOOD_SPEC.split("\n") if not ln.startswith("container:"))
    assert any("no 'container'" in p for p in _parse_item_list(no_container)[1])


def test_canary_mapping_fires_on_missing_orphan_and_wrong_key() -> None:
    items = GOOD_ITEMS
    missing = _mapping_problems("literacy", _kernel_for("literacy", drop="Note form"), items)
    assert any("MUST lacks listed item: Note form" in p for p in missing)
    orphan = _mapping_problems("literacy", _kernel_for("literacy", extra_must="a coined item"), items)
    assert any("orphan" in p for p in orphan)
    orphan_never = _mapping_problems("mastery", _kernel_for("mastery", extra_never="another coined item"), items)
    assert any("orphan" in p for p in orphan_never)
    wrong_key = _mapping_problems("compression", _kernel_for("compression", extra_never="Note form"), items)
    assert any("sits under NEVER" in p for p in wrong_key)
    std_in_tool = _mapping_problems("tool-reference", _kernel_for("tool-reference", extra_must="Note form"), items)
    assert any("container-only kernel carries standard item" in p for p in std_in_tool)
    assert _mapping_problems("literacy", 'TARGET::"x"\n', items) == ["NEVER or MUST key absent"]


def test_canary_heading_check_fires_on_rename_and_addition() -> None:
    items = GOOD_ITEMS
    renamed = GOOD_SPEC.replace("### Note form", "### Note style")
    assert any("Note style" in p for p in _heading_problems(renamed, items))
    added = GOOD_SPEC.replace("### Runbook steps", "### A new rule\n- x\n\n### Runbook steps")
    assert any("A new rule" in p for p in _heading_problems(added, items))
    unkernelled_ok = _heading_problems(GOOD_SPEC, items)
    assert not unkernelled_ok, "Runbook steps must be exempt"


def test_canary_target_check_fires() -> None:
    assert _target_problems("literacy", 'TARGET::"parser-safe OCTAVE in this document language"\n')
    assert not _target_problems("literacy", 'TARGET::"parser-safe OCTAVE in PITH"\n')
    assert _target_problems("mastery", 'TARGET::"advanced forms in PITH"\n')
    assert not _target_problems("compression", 'TARGET::"prose to OCTAVE, written in PITH"\n')


def test_canary_meta_pith_check_fires() -> None:
    bad = '===S===\nMETA:\n  TYPE::SKILL\n  PITH::"yes"\n§1::X\n  A::"b"\n===END===\n'
    assert _meta_pith_problems(bad)
    ok = '===S===\nMETA:\n  TYPE::SKILL\n§1::X\n  PITH::"not meta"\n===END===\n'
    assert not _meta_pith_problems(ok)


def test_canary_cap_check_fires() -> None:
    assert _tokens("word " * 400) > KERNEL_CAP_CL100K


def test_canary_glyph_check_fires_outside_fences_only() -> None:
    assert _spec_glyph_problems("copied a -> b\n")
    assert _spec_glyph_problems("this ⊕ that\n")
    assert not _spec_glyph_problems("```text\nBad: a -> b\n```\n")
    assert not _spec_glyph_problems("copied to docs; blocked by runner\n")


def test_canary_hestai_line_check_fires() -> None:
    assert _hestai_line_problems("nothing here\n")
    two = "HestAI repositories, not all public.\nHestAI repositories, not all public.\n"
    assert _hestai_line_problems(two)


def _first_line_of(root: Path, rel: str, token: str) -> int:
    for i, ln in enumerate((root / rel).read_text(encoding="utf-8").split("\n"), start=1):
        if token in ln:
            return i
    raise AssertionError(f"{token!r} not found in {rel}")


def test_canary_pointer_check_fires_and_passes() -> None:
    good = " ".join(f"`{p}:{_first_line_of(REPO_ROOT, p, t)}`" for p, t, _ in CONTENT_TOKENS)
    assert not _pointer_problems(good, REPO_ROOT, CONTENT_TOKENS)
    # not repo-relative: basename only
    bare = good.replace("src/octave_mcp/core/parser.py:", "parser.py:")
    assert any("not a repo-relative existing path" in p for p in _pointer_problems(bare, REPO_ROOT, CONTENT_TOKENS))
    # right path, wrong line: token not near
    far = good.replace(
        "src/octave_mcp/mcp/write_detection.py:"
        f"{_first_line_of(REPO_ROOT, 'src/octave_mcp/mcp/write_detection.py', 'W_SNAKE_CASE_BLOB')}",
        "src/octave_mcp/mcp/write_detection.py:3",
    )
    assert any("W_SNAKE_CASE_BLOB" in p for p in _pointer_problems(far, REPO_ROOT, CONTENT_TOKENS))
    # no pointers at all
    assert len(_pointer_problems("nothing", REPO_ROOT, CONTENT_TOKENS)) == len(CONTENT_TOKENS)
    # cross-repo pointers are ignored
    assert not _pointer_problems("`messageContract.ts:41` `type_checker.py:143-155`", REPO_ROOT, [])
