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

Pinned counts
-------------
``EXPECTED_STANDARD = 11`` and ``EXPECTED_CONTAINER = 6`` are exact. An amendment that
adds or removes a list item must change these constants, where review sees it. Without
the pin, dropping an item from the page and from every kernel together would pass.

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
from pathlib import Path

import pytest
from test_p2_8_bundled_skills_language import (
    ALL,
    GLYPH,
    OWN_KERNEL_STRINGS,
    REPO_ROOT,
    SKILLS,
    WORKBENCH_JS,
    _kernel_items,
    _key_text,
    _odyssean_kernel,
    _read,
    _scan,
    _workbench_kernel,
)

SPEC_REL = "src/octave_mcp/resources/specs/pith-spec.md"
SPEC_PATH = REPO_ROOT / SPEC_REL
CONTAINER_ONLY = ["tool-reference"]
TARGET_FORM = {"literacy": "in PITH", "mastery": "written in PITH", "compression": "written in PITH"}
EXPECTED_STANDARD = 11  # the ruled number of standard items (the page has 12 rules, Runbook steps has none)
EXPECTED_CONTAINER = 6  # the ruled number of container items
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
    # range pointer 995-1004: the token sits at the end of the range; the window spans the range
    ("src/octave_mcp/mcp/validate.py", 'result["warnings"].extend(error_dicts)', 0),
]

POINTER = re.compile(r"(?<![\w/.\-])((?:[\w.\-]+/)*[\w.\-]+\.(?:py|ts|mjs|md|json)):(\d+)(?:-(\d+))?")


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


def _parse_item_list(
    spec: str, expect: tuple[int, int] = (EXPECTED_STANDARD, EXPECTED_CONTAINER)
) -> tuple[list[tuple[str, str]], list[str]]:
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
    for tag, want in (("standard", expect[0]), ("container", expect[1])):
        have = sum(1 for t, _ in items if t == tag)
        if have != want:
            problems.append(f"{have} '{tag}' items in the list, ruled count is {want}")
    return items, problems


def _items_or_fail() -> list[tuple[str, str]]:
    items, problems = _parse_item_list(_spec_text())
    assert not problems, f"item list: {problems}"
    return items


# ---------------------------------------------------------------------------
# Check functions (each returns problems; canaries call them on synthetic input)
# ---------------------------------------------------------------------------
def _unquoted_entries(kernel: str, key: str) -> list[str]:
    """Top-level list elements of ``KEY::[...]`` that are not a whole quoted string."""
    body = _key_text(kernel, key)
    if body is None or not body.strip():
        return []
    parts: list[str] = []
    cur: list[str] = []
    in_q = False
    depth = 0
    i = 0
    while i < len(body):
        ch = body[i]
        if in_q:
            cur.append(ch)
            if ch == "\\" and i + 1 < len(body):
                cur.append(body[i + 1])
                i += 1
            elif ch == '"':
                in_q = False
        elif ch == '"':
            in_q = True
            cur.append(ch)
        elif ch in "[(":
            depth += 1
            cur.append(ch)
        elif ch in "])":
            depth -= 1
            cur.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip() and not re.fullmatch(r'"(?:[^"\\]|\\.)*"', p.strip())]


def _mapping_problems(name: str, kernel: str, items: list[tuple[str, str]]) -> list[str]:
    never = _kernel_items(kernel, "NEVER")
    must = _kernel_items(kernel, "MUST")
    if never is None or must is None:
        return ["NEVER or MUST key absent"]
    unquoted = [f"unquoted entry under {k}: {e}" for k in ("NEVER", "MUST") for e in _unquoted_entries(kernel, k)]
    if unquoted:
        return unquoted
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
    if not re.search(r"(?<!\w)" + re.escape(want) + r"(?!\w)", target):
        return [f"TARGET lacks the exact form {want!r}: {target!r}"]
    if re.search(r"\b(?:not|never|no|without)\b[^,;\"]*" + re.escape(want), target, flags=re.IGNORECASE):
        return [f"TARGET negates the form {want!r}: {target!r}"]
    return []


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
    """Owned pointers are repo-relative (``src/octave_mcp/...``); anything else is cross-repo and ignored.

    Two rules: (1) every owned pointer must match a CONTENT_TOKENS row (a token near its line or
    inside its range), else "pointer has no content token"; (2) every row must be matched by
    at least one pointer in the spec.
    """
    problems: list[str] = []
    found: list[tuple[str, int, int]] = []
    for m in POINTER.finditer(spec):
        path, start = m.group(1), int(m.group(2))
        end = int(m.group(3)) if m.group(3) else start
        if not path.startswith("src/octave_mcp/"):
            continue
        target = root / path
        if not target.is_file():
            problems.append(f"octave-mcp pointer does not exist: {path}:{start}")
            continue
        n_lines = len(target.read_text(encoding="utf-8").split("\n"))
        if not 1 <= start <= end <= n_lines:
            problems.append(f"pointer line out of range: {path}:{start}-{end} (file has {n_lines} lines)")
            continue
        found.append((path, start, end))

    def matches(path: str, start: int, end: int, token: str, tol: int) -> bool:
        lines = (root / path).read_text(encoding="utf-8").split("\n")
        return any(token in ln for ln in lines[max(0, start - 1 - tol) : end + tol])

    for path, start, end in found:
        if not any(p == path and matches(path, start, end, t, tol) for p, t, tol in tokens):
            problems.append(f"pointer has no content token: {path}:{start}" + (f"-{end}" if end != start else ""))
    for path, token, tol in tokens:
        if not any(p == path and matches(p, s0, e0, token, tol) for p, s0, e0 in found):
            where = "at" if tol == 0 else f"within {tol} lines of"
            problems.append(f"no pointer to {path} puts {token!r} {where} its line")
    return problems


# ---------------------------------------------------------------------------
# 1. Extractors agree on each of the four kernels (workbench regex in node, odyssean copy)
# ---------------------------------------------------------------------------
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
    stale = _workbench_kernel(doc, stale_js)
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
GOOD_COUNTS = (2, 2)
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
    items, problems = _parse_item_list(GOOD_SPEC, GOOD_COUNTS)
    assert not problems and items == GOOD_ITEMS
    assert not _heading_problems(GOOD_SPEC, items)
    for name in ALL:
        assert not _mapping_problems(name, _kernel_for(name), items), name
    assert not _spec_glyph_problems(GOOD_SPEC)
    assert not _hestai_line_problems(GOOD_SPEC)


def test_canary_item_list_format_errors_fire() -> None:
    no_fence = GOOD_SPEC.replace("```text", "```")
    assert _parse_item_list(no_fence, GOOD_COUNTS)[1]
    bad_tag = GOOD_SPEC.replace("container: no unkeyed lines", "other: no unkeyed lines")
    assert any("bad list line" in p for p in _parse_item_list(bad_tag, GOOD_COUNTS)[1])
    dupe = GOOD_SPEC.replace("standard: Note form\n", "standard: Note form\nstandard: Note form\n")
    assert any("duplicate" in p for p in _parse_item_list(dupe, GOOD_COUNTS)[1])


def test_canary_pinned_counts_fire_on_shrinkage_and_growth() -> None:
    """Dropping an item from the page (and every kernel) must still fail: the counts are pinned."""
    dropped = "\n".join(ln for ln in GOOD_SPEC.split("\n") if not ln.startswith("container: no unkeyed"))
    assert any("'container' items" in p for p in _parse_item_list(dropped, GOOD_COUNTS)[1])
    grown = GOOD_SPEC.replace("```\n\n## Amendment", "standard: A coined rule\n```\n\n## Amendment")
    assert any("'standard' items" in p for p in _parse_item_list(grown, GOOD_COUNTS)[1])
    # the real constants are the ruled numbers
    assert (EXPECTED_STANDARD, EXPECTED_CONTAINER) == (11, 6)
    assert _parse_item_list(GOOD_SPEC)[1], "GOOD_SPEC has 2+2 items, so the pinned 11+6 must reject it"


def test_canary_unquoted_entries_are_reported() -> None:
    kernel = 'TARGET::"x"\nNEVER::["a", bare_item]\nMUST::["Note form", other thing, "no unkeyed lines"]\nGATE::"g"\n'
    problems = _mapping_problems("literacy", kernel, GOOD_ITEMS)
    assert "unquoted entry under NEVER: bare_item" in problems
    assert "unquoted entry under MUST: other thing" in problems
    assert not _unquoted_entries(_kernel_for("literacy"), "MUST")


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
    assert _target_problems("mastery", 'TARGET::"advanced forms, not written in PITH"\n')
    assert _target_problems("literacy", 'TARGET::"parser-safe OCTAVE, never in PITH"\n')
    assert _target_problems("literacy", 'TARGET::"parser-safe OCTAVE within PITH"\n')


def test_canary_meta_pith_check_fires() -> None:
    bad = '===S===\nMETA:\n  TYPE::SKILL\n  PITH::"yes"\n§1::X\n  A::"b"\n===END===\n'
    assert _meta_pith_problems(bad)
    ok = '===S===\nMETA:\n  TYPE::SKILL\n§1::X\n  PITH::"not meta"\n===END===\n'
    assert not _meta_pith_problems(ok)


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
    # a bare basename is not an owned pointer: it is ignored, so its row goes unmatched
    bare = good.replace("src/octave_mcp/core/parser.py:", "parser.py:")
    bare_problems = _pointer_problems(bare, REPO_ROOT, CONTENT_TOKENS)
    assert any("bare_flow" in p for p in bare_problems)
    assert not any("pointer has no content token" in p for p in bare_problems)
    # right path, wrong line: token not near, and the pointer itself has no token
    wrong = f"{good} `src/octave_mcp/mcp/write_detection.py:3`"
    assert any(
        "pointer has no content token: src/octave_mcp/mcp/write_detection.py:3" in p
        for p in _pointer_problems(wrong, REPO_ROOT, CONTENT_TOKENS)
    )
    # a stray owned pointer with no row for its path
    stray = f"{good} `src/octave_mcp/core/lexer.py:10`"
    assert any(
        "pointer has no content token: src/octave_mcp/core/lexer.py:10" in p
        for p in _pointer_problems(stray, REPO_ROOT, CONTENT_TOKENS)
    )
    # a range pointer: the token inside the range passes with tolerance 0
    ranged = good.replace(
        f"src/octave_mcp/mcp/validate.py:{_first_line_of(REPO_ROOT, 'src/octave_mcp/mcp/validate.py', CONTENT_TOKENS[-1][1])}",
        "src/octave_mcp/mcp/validate.py:995-1004",
    )
    assert "995-1004" in ranged and not _pointer_problems(ranged, REPO_ROOT, CONTENT_TOKENS)
    # no pointers at all
    assert len(_pointer_problems("nothing", REPO_ROOT, CONTENT_TOKENS)) == len(CONTENT_TOKENS)
    # cross-repo and bare names are ignored
    assert not _pointer_problems("`messageContract.ts:41` `type_checker.py:143-155` `README.md:5`", REPO_ROOT, [])
