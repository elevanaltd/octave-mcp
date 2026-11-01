"""P2-8 acceptance guard: bundled octave skills taught in the estate language.

RED step. This file implements acceptance criteria A1, A2, A3, A4, A5, A8,
A9, A10, A11 and A12 of the approved design spec
``.hestai-state/reports/2026-10-31-p2-8-octave-skills-change-spec.md`` (r3,
critical-engineer GO), section 5. A6 (full suite) and A7 (CHANGELOG) are not
in this file.

It guards four tracked files:

- ``src/octave_mcp/resources/skills/octave-literacy/SKILL.md``
- ``src/octave_mcp/resources/skills/octave-mastery/SKILL.md``
- ``src/octave_mcp/resources/skills/octave-compression/SKILL.md``
- ``src/octave_mcp/resources/patterns/octave-tool-reference.oct.md``

Rules of this file:

- The real tool entry points are used (``ValidateTool``, ``WriteTool`` with
  ``dry_run``). The parser is never mocked.
- Baseline numbers are hard-coded below, with the spec section that owns
  each one. They are the measured state at ``cdfc963``.
- Every check is its own test, parametrised over files where it fits, so a
  failure names the criterion (A1..A12) and the file.
- Nothing is skipped. If ``node`` is missing, A9 fails with a clear message.
"""

from __future__ import annotations

import asyncio
import re
import shutil
import subprocess
import textwrap
from collections import Counter
from functools import cache
from pathlib import Path
from typing import Any

import pytest
import tiktoken

from octave_mcp.mcp.validate import ValidateTool
from octave_mcp.mcp.write import WriteTool
from octave_mcp.mcp.write_detection import _detect_snake_case_blob

REPO_ROOT = Path(__file__).resolve().parents[2]

FILES: dict[str, tuple[str, str]] = {
    # name: (repo-relative path, validation schema)
    "literacy": ("src/octave_mcp/resources/skills/octave-literacy/SKILL.md", "SKILL"),
    "mastery": ("src/octave_mcp/resources/skills/octave-mastery/SKILL.md", "SKILL"),
    "compression": ("src/octave_mcp/resources/skills/octave-compression/SKILL.md", "SKILL"),
    "tool-reference": ("src/octave_mcp/resources/patterns/octave-tool-reference.oct.md", "META"),
}
SKILLS = ["literacy", "mastery", "compression"]
ALL = list(FILES)
RESOURCES_DIR = REPO_ROOT / "src" / "octave_mcp" / "resources"

# ---------------------------------------------------------------------------
# Baseline constants. Source: spec section 2 "Baseline" table, measured at
# octave-mcp cdfc963 (baseline.py). Do not edit to make a test pass.
# ---------------------------------------------------------------------------
BASELINE_CL100K = {"literacy": 5065, "mastery": 3885, "compression": 2106, "tool-reference": 4218}
# Spec section 5 A1: warnings are measured per file, per code.
BASELINE_WARNINGS: dict[str, dict[str, int]] = {
    "literacy": {"W_FLAT_PREFIX_SCALAR": 5},
    "mastery": {"W_FLAT_PREFIX_SCALAR": 1},
    "compression": {},
}
# Spec section 5 A2 (re-measured at cdfc963 by this file's author: 6 x E007).
BASELINE_E007_FIELDS = {
    "META.PURPOSE",
    "META.VERIFIED_AGAINST",
    "META.CANONICAL",
    "META.SOURCE",
    "META.SINGLE_HOME",
    "META.REVERIFY_TRIGGER",
}
# Spec section 3 C8 and section 5 A4.
KERNEL_CAP_CL100K = 300
TOOL_REFERENCE_GROWTH_CAP = 250
# Spec section 5 A10 deviation: see test_A10 docstring. Measured at cdfc963
# with WriteTool dry_run (not in the spec table); STEP_n runbooks keep their
# sanctioned W_FLAT_PREFIX_SCALAR (spec C4, r3).
A10_ALLOWED_ADVISORY = {
    "literacy": {"W_FLAT_PREFIX_SCALAR": 5},
    "mastery": {"W_FLAT_PREFIX_SCALAR": 1},
    "compression": {},
    "tool-reference": {"W_FLAT_PREFIX_SCALAR": 1},
}

# Spec section 5 A3, regex "defined, CE r2".
GLYPH = re.compile(r"[⊕⇌∧∨→∴⧺≠≤≥≈×]|(?<=\w)\s(->|<->|\+|&|~|\|)\s(?=\w)")

# Spec section 4.0: the standard kernel strings, verbatim.
STD_NEVER = [
    "operators in prose or values",
    "mythology as instruction words",
    "snake_case blobs",
    "invented content; write none or not known",
    "model-written ids, tags or counts",
    "unkeyed lines",
    "a value on a section header",
    "judgement attributed to a named person",
    "shortened or merged identifiers",
]
STD_MUST = [
    "note form",
    "identifiers copied exactly, in backticks",
    "hedges and conditions copied verbatim",
    "relations in words",
    "one calibration sentence on a prohibition that can over-fire",
    "code in fenced blocks",
    "a self-contradicting source kept both ways and flagged",
    "every line keyed, values quoted",
    "contents indented under the section header",
    "edits addressed as section dot key",
    "repairs read, not only the validation status",
]
# Spec 4.0 "Own items" (only the strings the spec fixes).
OWN_KERNEL_STRINGS: dict[str, list[str]] = {
    "literacy": [
        "parser-safe OCTAVE in the estate language",
        "Is every line keyed, in plain words, with identifiers exact, and did repairs come back empty?",
    ],
    "mastery": [
        "glyphs outside schema-definition examples",
        "the glossary used for writing",
        "holographic constraints only in schema-definition files",
        "Is every glyph I wrote inside a schema-definition example, and every other relation in words?",
    ],
    "compression": [
        "compressing before choosing the tier",
        "dropping causal chains, conditions or numbers",
        "tier first; default conservative; references lossless",
        "compressed output says what was kept and what was dropped",
        "Could a reader rebuild every causal chain, condition and number, and does the document say what was dropped?",
    ],
}
# Spec 4.4: tool-reference carries the container items only.
CONTAINER_KERNEL_STRINGS = [
    "unkeyed lines",
    "a value on a section header",
    "every line keyed, values quoted",
    "contents indented under the section header",
    "edits addressed as section dot key",
    "repairs read, not only the validation status",
]

# Spec section 2 "Inbound references that must keep resolving" and A5.
# Anchored regexes, one per reference. Keyed references (tool-reference) are
# searched only inside their parent section.
SECTION_REFERENCES: dict[str, list[tuple[str, str]]] = {
    "literacy": [
        (r"^\s*§1d::", "§1d"),
        (r"^\s*§3b::V6_ENVELOPE_STRUCTURE\s*$", "§3b::V6_ENVELOPE_STRUCTURE"),
        (r"^\s*§5::", "§5"),
    ],
    "mastery": [
        (r"^\s*§1::", "§1"),
        (r"^\s*§1b::", "§1b"),
        (r"^\s*§2::", "§2"),
    ],
    "compression": [
        (r"^\s*§1::", "§1"),
        (r"^\s*§4::COMPRESSION_RULES\s*$", "§4::COMPRESSION_RULES"),
    ],
}
# tool-reference: (parent section number, key regex, label)
TOOL_REFERENCE_KEY_REFERENCES = [
    (3, r"^\s*RECEIPT_GATE:", "§3::RECEIPT_GATE"),
    (3, r"^\s*TRIAGE:", "§3::TRIAGE"),
    (6, r"^\s*SNAKE_CASE_BLOB:", "§6::SNAKE_CASE_BLOB"),
]
STALE_RULE_KEY_REFERENCE = re.compile(r"R3a|literacy R12|literacy R13")

# Spec section 5 A3 allow-list. Pre-rewrite the parent key names are not
# known, so the allow-list is scoped by enclosing section token. Tighten to
# key names at GREEN if the author names them.
FENCE_SECTION_ALLOW: dict[str, str] = {
    "literacy": r"^(1b|2[a-z]?)$",
    "mastery": r"^(1|2|4)[a-z]?$",
}
READING_REFERENCE_MAX_LINES = 40

# Spec section 5 A12.
A12_ORDINARY_E007_ALLOWED = {"META.PURPOSE"}
A12_SANCTIONED_WRONG_KEY = "WRONG_EXAMPLE"

# Spec section 5 A9: byte-for-byte from kernel_draft.py (payloadCompiler.ts:75).
# JS `$` without the m flag differs from Python's, so this runs in node.
WORKBENCH_JS = (
    r"""const fs=require("fs");const n=fs.readFileSync(0,"utf8").replace(/\r\n?/g,"\n");"""
    r"""const m=n.match(/§5::ANCHOR_KERNEL\s*\n([\s\S]*?)(?=\n§\d+::|===END===|$)/);"""
    r"""process.stdout.write(m?m[1].trim():"");"""
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _read(name: str) -> str:
    return (REPO_ROOT / FILES[name][0]).read_text(encoding="utf-8")


def _path(name: str) -> str:
    return str(REPO_ROOT / FILES[name][0])


@cache
def _validate(name: str) -> dict[str, Any]:
    _, schema = FILES[name]
    return asyncio.run(ValidateTool().execute(file_path=_path(name), schema=schema, profile="STRICT"))


@cache
def _dry_run_write(name: str) -> dict[str, Any]:
    _, schema = FILES[name]
    # dry_run never writes; the nonexistent target keeps the real file safe.
    return asyncio.run(
        WriteTool().execute(
            target_path="/nonexistent-p2-8-dry-run/dry.oct.md",
            content=_read(name),
            dry_run=True,
            schema=schema,
        )
    )


def _validate_content(content: str, schema: str = "META") -> dict[str, Any]:
    return asyncio.run(ValidateTool().execute(content=content, schema=schema, profile="STRICT"))


def _codes(items: list[dict[str, Any]], key: str = "code") -> Counter[str]:
    return Counter(str(i.get(key)) for i in items)


_FENCE_OPEN = re.compile(r"^\s*(`{3,})")
_SECTION_HEADER = re.compile(r"^\s*§(\d+[a-z]?)::")
_KEY_LINE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)::?")


def _scan(text: str) -> tuple[list[tuple[int, str]], list[dict[str, Any]]]:
    """Return (lines outside fences as (lineno, text), fenced blocks).

    Each block: start (1-based line of the opening fence), lines (inner),
    parent_key (nearest key line above the fence), section (nearest section
    token above, ignoring section-looking lines inside fences).
    """
    outside: list[tuple[int, str]] = []
    blocks: list[dict[str, Any]] = []
    fence: str | None = None
    current: dict[str, Any] | None = None
    section = ""
    parent_key = ""
    for idx, line in enumerate(text.split("\n"), start=1):
        if fence is None:
            m = _FENCE_OPEN.match(line)
            if m:
                fence = m.group(1)
                current = {"start": idx, "lines": [], "parent_key": parent_key, "section": section}
                continue
            outside.append((idx, line))
            sm = _SECTION_HEADER.match(line)
            if sm:
                section = sm.group(1)
            km = _KEY_LINE.match(line)
            if km:
                parent_key = km.group(1)
        else:
            stripped = line.strip()
            if stripped and set(stripped) == {"`"} and len(stripped) >= len(fence):
                assert current is not None
                blocks.append(current)
                fence, current = None, None
            else:
                assert current is not None
                current["lines"].append(line)
    return outside, blocks


def _odyssean_kernel(text: str) -> str | None:
    """First-match rule of odyssean-anchor.

    Source: odyssean-anchor-mcp src/odyssean_anchor/core/extraction.py:964-980
    (spec section 2 "Second extractor"). It takes the FIRST match of
    ``§(?:\\d+::)?ANCHOR_KERNEL`` anywhere in the file. Any body text that
    names the kernel header hijacks the extraction. The region ends at the
    next line-start ``§N::`` header or ``===END===`` (spec C7). The source
    file was not readable from this worktree, so the region end follows C7.
    """
    m = re.search(r"§(?:\d+::)?ANCHOR_KERNEL", text)
    if not m:
        return None
    rest = text[m.end() :]
    rest = rest.split("\n", 1)[1] if "\n" in rest else ""
    end = re.search(r"^(?:§\d+[a-z]?::|===END===)", rest, flags=re.MULTILINE)
    return (rest[: end.start()] if end else rest).strip()


def _workbench_kernel(text: str) -> str:
    node = shutil.which("node")
    if node is None:
        pytest.fail("A9 requires node on PATH to run the workbench regex byte-for-byte; node was not found")
    proc = subprocess.run([node, "-e", WORKBENCH_JS], input=text, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"A9 node run failed: {proc.stderr}"
    return proc.stdout


def _glyph_lines(lines: list[tuple[int, str]]) -> list[str]:
    return [f"{n}: {t.strip()[:90]}" for n, t in lines if GLYPH.search(t)]


def _tokens(text: str) -> int:
    return len(tiktoken.get_encoding("cl100k_base").encode(text))


# ---------------------------------------------------------------------------
# A1 Validation (skills)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name", SKILLS)
def test_A1_skill_validates_strict_clean(name: str) -> None:
    r = _validate(name)
    assert r["validation_status"] == "VALIDATED", f"A1 {name}: {r['validation_status']}"
    assert r["errors"] == [], f"A1 {name} errors: {r['errors']}"
    assert r["repairs"] == [], f"A1 {name} repairs: {r['repairs']}"
    assert r["validation_errors"] == [], f"A1 {name} validation_errors: {r['validation_errors']}"


@pytest.mark.parametrize("name", SKILLS)
def test_A1_skill_warnings_at_most_baseline_per_code(name: str) -> None:
    got = _codes(_validate(name)["warnings"])
    base = BASELINE_WARNINGS[name]
    new_codes = sorted(set(got) - set(base))
    over = {c: (got[c], base[c]) for c in base if got[c] > base[c]}
    assert not new_codes, f"A1 {name}: new warning codes {new_codes}"
    assert not over, f"A1 {name}: warning counts above baseline (got, base) {over}"


# ---------------------------------------------------------------------------
# A2 tool-reference
# ---------------------------------------------------------------------------
def test_A2_tool_reference_errors_and_repairs_empty() -> None:
    r = _validate("tool-reference")
    assert r["errors"] == [], f"A2 errors: {r['errors']}"
    assert r["repairs"] == [], f"A2 repairs: {r['repairs']}"


def test_A2_tool_reference_validation_errors_equal_baseline_e007_set() -> None:
    errs = _validate("tool-reference")["validation_errors"]
    assert all(e.get("code") == "E007" for e in errs), f"A2 non-E007 validation_errors: {errs}"
    fields = [str(e.get("field")) for e in errs]
    assert set(fields) == BASELINE_E007_FIELDS, f"A2 E007 set differs: got {sorted(fields)}"
    assert len(fields) == len(BASELINE_E007_FIELDS), f"A2 duplicate E007 entries: {sorted(fields)}"


# ---------------------------------------------------------------------------
# A3 Glyphs
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name", ALL)
def test_A3_no_glyphs_outside_fences(name: str) -> None:
    outside, _ = _scan(_read(name))
    hits = _glyph_lines(outside)
    assert not hits, f"A3 {name}: {len(hits)} glyph lines outside fences, first: {hits[:5]}"


@pytest.mark.parametrize("name", ALL)
def test_A3_no_glyphs_in_kernel(name: str) -> None:
    kernel = _odyssean_kernel(_read(name))
    assert kernel is not None, f"A3 {name}: no ANCHOR_KERNEL section"
    hits = [h for h in kernel.split("\n") if GLYPH.search(h)]
    assert not hits, f"A3 {name}: {len(hits)} glyph lines in kernel, first: {hits[:5]}"


@pytest.mark.parametrize("name", ALL)
def test_A3_glyphs_inside_fences_only_where_allowed(name: str) -> None:
    _, blocks = _scan(_read(name))
    allow = re.compile(FENCE_SECTION_ALLOW[name]) if name in FENCE_SECTION_ALLOW else None
    problems: list[str] = []
    for b in blocks:
        body = "\n".join(b["lines"])
        hit = bool(GLYPH.search(body))
        in_allowed = allow is not None and allow.match(b["section"]) is not None
        where = f"fence at line {b['start']} (section §{b['section']}, parent {b['parent_key']})"
        if hit and not in_allowed:
            problems.append(f"{where}: glyphs in a section not on the allow-list")
            continue
        if not in_allowed:
            continue
        if name == "mastery" and re.match(r"^4[a-z]?$", b["section"]):
            if not re.search(r"^\s*TYPE::SCHEMA\b", body, flags=re.MULTILINE):
                problems.append(f"{where}: mastery §4 fence lacks TYPE::SCHEMA")
        elif hit and len(b["lines"]) > READING_REFERENCE_MAX_LINES:
            problems.append(
                f"{where}: reading-reference fence has {len(b['lines'])} lines, max {READING_REFERENCE_MAX_LINES}"
            )
    assert not problems, f"A3 {name}: " + "; ".join(problems)


# ---------------------------------------------------------------------------
# A4 Size
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name", ALL)
def test_A4_kernel_at_most_cap(name: str) -> None:
    kernel = _odyssean_kernel(_read(name))
    assert kernel is not None, f"A4 {name}: no ANCHOR_KERNEL section"
    n = _tokens(kernel)
    assert n <= KERNEL_CAP_CL100K, f"A4 {name}: kernel {n} cl100k > {KERNEL_CAP_CL100K}"


@pytest.mark.parametrize("name", SKILLS)
def test_A4_skill_below_baseline(name: str) -> None:
    n = _tokens(_read(name))
    assert n < BASELINE_CL100K[name], f"A4 {name}: {n} cl100k, baseline {BASELINE_CL100K[name]} (must end below)"


def test_A4_tool_reference_growth_at_most_cap() -> None:
    n = _tokens(_read("tool-reference"))
    limit = BASELINE_CL100K["tool-reference"] + TOOL_REFERENCE_GROWTH_CAP
    assert n <= limit, f"A4 tool-reference: {n} cl100k > {limit} (baseline + {TOOL_REFERENCE_GROWTH_CAP})"


# ---------------------------------------------------------------------------
# A5 References
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name", SKILLS)
def test_A5_section_references_resolve(name: str) -> None:
    lines = _read(name).split("\n")
    missing = [label for rx, label in SECTION_REFERENCES[name] if not any(re.match(rx, ln) for ln in lines)]
    assert not missing, f"A5 {name}: unresolved section references {missing}"


def test_A5_tool_reference_references_resolve() -> None:
    outside, _ = _scan(_read("tool-reference"))
    headers = [(n, _SECTION_HEADER.match(t).group(1)) for n, t in outside if _SECTION_HEADER.match(t)]  # type: ignore[union-attr]
    missing: list[str] = []
    for section, rx, label in TOOL_REFERENCE_KEY_REFERENCES:
        starts = [n for n, s in headers if s == str(section)]
        if not starts:
            missing.append(f"{label} (no §{section} header)")
            continue
        start = starts[0]
        later = [n for n, _ in headers if n > start]
        end = later[0] if later else 10**9
        if not any(re.match(rx, t) for n, t in outside if start < n < end):
            missing.append(label)
    assert not missing, f"A5 tool-reference: unresolved references {missing}"


def test_A5_no_stale_rule_key_references_in_resources() -> None:
    hits: list[str] = []
    for path in sorted(RESOURCES_DIR.rglob("*")):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for n, line in enumerate(text.split("\n"), start=1):
            if STALE_RULE_KEY_REFERENCE.search(line):
                hits.append(f"{path.relative_to(REPO_ROOT)}:{n}")
    assert not hits, f"A5: stale R3a / literacy R12 / literacy R13 references remain: {hits}"


# ---------------------------------------------------------------------------
# A8 Kernel coverage
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name", SKILLS)
def test_A8_skill_kernel_carries_standard_and_own_strings(name: str) -> None:
    kernel = _odyssean_kernel(_read(name))
    assert kernel is not None, f"A8 {name}: no ANCHOR_KERNEL section"
    required = STD_NEVER + STD_MUST + OWN_KERNEL_STRINGS[name]
    missing = [s for s in required if s not in kernel]
    assert not missing, f"A8 {name}: {len(missing)} kernel strings missing, first: {missing[:4]}"


def test_A8_tool_reference_kernel_carries_container_strings() -> None:
    kernel = _odyssean_kernel(_read("tool-reference"))
    assert kernel is not None, "A8 tool-reference: no ANCHOR_KERNEL section"
    missing = [s for s in CONTAINER_KERNEL_STRINGS if s not in kernel]
    assert not missing, f"A8 tool-reference: container strings missing: {missing}"


# ---------------------------------------------------------------------------
# A9 Extractor round trip
# ---------------------------------------------------------------------------
def _kernel_shape_problems(kernel: str) -> list[str]:
    problems: list[str] = []
    first = kernel.split("\n", 1)[0].strip()
    if not first.startswith("TARGET::"):
        problems.append(f"first line is not TARGET:: ({first[:60]!r})")
    for key in ("NEVER", "MUST", "GATE"):
        if not re.search(rf"^\s*{key}::", kernel, flags=re.MULTILINE):
            problems.append(f"no {key}::")
    glyphs = [h for h in kernel.split("\n") if GLYPH.search(h)]
    if glyphs:
        problems.append(f"{len(glyphs)} glyph lines")
    return problems


@pytest.mark.parametrize("name", ALL)
def test_A9_workbench_extractor_returns_whole_kernel(name: str) -> None:
    kernel = _workbench_kernel(_read(name))
    problems = _kernel_shape_problems(kernel) if kernel else ["extractor returned nothing"]
    assert not problems, f"A9 {name} (workbench regex in node): {problems}; kernel {len(kernel)} chars"


@pytest.mark.parametrize("name", ALL)
def test_A9_odyssean_extractor_returns_whole_kernel(name: str) -> None:
    kernel = _odyssean_kernel(_read(name))
    problems = _kernel_shape_problems(kernel) if kernel else ["extractor returned nothing"]
    assert not problems, f"A9 {name} (odyssean first match): {problems}"


@pytest.mark.parametrize("name", ALL)
def test_A9_anchor_kernel_named_exactly_once(name: str) -> None:
    n = _read(name).count("ANCHOR_KERNEL")
    assert n == 1, f"A9 {name}: ANCHOR_KERNEL appears {n} times, must be exactly once"


# ---------------------------------------------------------------------------
# A10 Canonical fixed point
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name", ALL)
def test_A10_write_dry_run_has_no_corrections(name: str) -> None:
    """Spec A10 says ``corrections == []``.

    Deviation, flagged to the reviewer: the spec's own C4 and A1 keep the
    sanctioned ``STEP_n`` runbook, whose ``W_FLAT_PREFIX_SCALAR`` is emitted
    into ``corrections`` by the dry run. A literal ``== []`` would be
    unpassable for literacy and mastery. This test therefore requires that
    every correction code other than ``W_FLAT_PREFIX_SCALAR`` is absent (no
    normalisation, no reconciliation, no annotation advisories) and that
    ``W_FLAT_PREFIX_SCALAR`` stays at most the measured baseline count.
    """
    r = _dry_run_write(name)
    assert r["status"] == "success", f"A10 {name}: dry run status {r['status']} errors {r.get('errors')}"
    got = _codes(r.get("corrections", []))
    allowed = A10_ALLOWED_ADVISORY[name]
    extra = {c: n for c, n in got.items() if c not in allowed}
    over = {c: (got[c], allowed[c]) for c in allowed if got[c] > allowed[c]}
    assert not extra, f"A10 {name}: corrections other than the allowed advisories: {extra}"
    assert not over, f"A10 {name}: advisory counts above baseline (got, allowed) {over}"


# ---------------------------------------------------------------------------
# A11 No blobs
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name", ALL)
def test_A11_no_snake_case_blobs(name: str) -> None:
    hits = _detect_snake_case_blob(_read(name))
    assert hits == [], f"A11 {name}: {len(hits)} W_SNAKE_CASE_BLOB hits, first: {hits[:2]}"


def test_A11_detector_canary_fires_on_a_known_blob() -> None:
    """Guards A11 against going vacuous if the detector signature or behaviour changes."""
    blob = "migration_on_a_moving_target_is_an_anti_pattern_because_app_completion_keeps_shifting"
    hits = _detect_snake_case_blob(f"FIELD::\nKEY::\nWHY::{blob}\n")
    assert [h["code"] for h in hits] == ["W_SNAKE_CASE_BLOB"], f"A11 canary: detector returned {hits}"


# ---------------------------------------------------------------------------
# A12 Examples parse
# ---------------------------------------------------------------------------
_ENVELOPE_OPEN = re.compile(r"^===(?!END===)[A-Z_][A-Z0-9_]*===$")


@pytest.mark.parametrize("name", ALL)
def test_A12_fenced_examples_parse_strict(name: str) -> None:
    _, blocks = _scan(_read(name))
    problems: list[str] = []
    checked = 0
    for b in blocks:
        body = textwrap.dedent("\n".join(b["lines"])).strip("\n")
        first = next((ln.strip() for ln in body.split("\n") if ln.strip()), "")
        is_envelope = bool(_ENVELOPE_OPEN.match(first))
        if not (is_envelope or first == "META:"):
            continue
        if b["parent_key"] == A12_SANCTIONED_WRONG_KEY:
            continue
        checked += 1
        where = f"fence at line {b['start']} (parent {b['parent_key']})"
        content = body if is_envelope else f"===EXAMPLE===\n{body}\n===END===\n"
        if is_envelope and "===END===" not in body:
            content += "\n===END===\n"
        try:
            r = _validate_content(content)
        except Exception as exc:  # noqa: BLE001 - report any parser failure as a finding
            problems.append(f"{where}: validate raised {type(exc).__name__}: {str(exc)[:80]}")
            continue
        if r["errors"]:
            problems.append(f"{where}: errors {[e.get('code') for e in r['errors']]}")
        if r["repairs"]:
            problems.append(f"{where}: repairs {[x.get('subtype') for x in r['repairs']]}")
        is_schema = bool(re.search(r"^\s*TYPE::SCHEMA\b", body, flags=re.MULTILINE))
        for e in r["validation_errors"]:
            field = str(e.get("field"))
            ok = e.get("code") == "E007" and (
                field.startswith("META.") if is_schema else field in A12_ORDINARY_E007_ALLOWED
            )
            if not ok:
                problems.append(f"{where}: {e.get('code')} on {field}")
    assert not problems, f"A12 {name} ({checked} example fences checked): " + "; ".join(problems)
