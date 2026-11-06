"""P2-8 acceptance guard: bundled octave skills taught in the estate language.

This file implements acceptance criteria A1, A2, A3, A4, A5, A5b,
A8, A9, A10, A11, A12 and A13 of the design spec
``.hestai-state/reports/2026-10-31-p2-8-octave-skills-change-spec.md`` at
revision r5 (sections 5 and 12; TMG T2 rework rulings R5-1 to R5-6). A6 (full
suite) and A7 (CHANGELOG) are not in this file. A13 is the r5 structural check
for rules C1, C4 and C9. A5b guards prose citations that replace rule ids.

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
  failure names the criterion (A1..A13) and the file.
- Small canary tests prove that the new or changed checks fire on synthetic
  bad input, so a clean result on the real files cannot be vacuous.
- Nothing is skipped. If ``node`` is missing, A9 fails with a clear message.

Environment: A9 and the A8 workbench-kernel check run the workbench kernel
regex in ``node`` through ``subprocess``, so ``node`` must be on ``PATH``. CI
runs on ``ubuntu-latest``, which ships node; a local run needs it installed.
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
    # P2-8b2 Q2: the wire register, held to the same guards (record
    # OCTAVE-MCP-CHATTER-WIRE-PITH-REWRITE-RULINGS-20261106). Key is "chatter", the skill is octave-chatter.
    "chatter": ("src/octave_mcp/resources/skills/octave-chatter/SKILL.md", "SKILL"),
}
SKILLS = ["literacy", "mastery", "compression", "chatter"]
ALL = list(FILES)
RESOURCES_DIR = REPO_ROOT / "src" / "octave_mcp" / "resources"

# ---------------------------------------------------------------------------
# Baseline constants. Source: spec section 2 "Baseline" table, measured at
# octave-mcp cdfc963 (baseline.py). Do not edit to make a test pass.
# ---------------------------------------------------------------------------
BASELINE_CL100K = {"literacy": 5065, "mastery": 3885, "compression": 2106, "tool-reference": 4218, "chatter": 1975}
# chatter: not a cdfc963 number. 1975 cl100k is octave-chatter v1.1.0 as shipped at c743fb9 (the P2-8b2 Q2
# starting point); A4 holds the rewrite to end below it.
# Spec section 5 A1: warnings are measured per file, per code.
BASELINE_WARNINGS: dict[str, dict[str, int]] = {
    "literacy": {"W_FLAT_PREFIX_SCALAR": 5},
    "mastery": {"W_FLAT_PREFIX_SCALAR": 1},
    "compression": {},
    "chatter": {},
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
# Spec r5 R5-3 / A10: W_FLAT_PREFIX_SCALAR is the only correction code allowed
# in a dry run, and only for the prefixes in FLAT_PREFIX_ALLOW, with the total
# count at most these per-file numbers. MEASURED at cdfc963 by
# WriteTool(dry_run=True) on each file (count of corrections[].code ==
# W_FLAT_PREFIX_SCALAR, run 2026-11-01 by this file's author). They are not in
# the spec table; the skill figures equal the spec's A1 warning baseline.
A10_FLAT_PREFIX_SCALAR_BASELINE = {"literacy": 5, "mastery": 1, "compression": 0, "tool-reference": 1, "chatter": 0}
# Spec r5 R5-3: allowed flat-prefix groups, parsed from the message
# "share prefix 'X_'". STEP_ is the runbook form (C4); W_ covers the warning-code
# tables. Every other group must be restructured into a list or a block in GREEN.
FLAT_PREFIX_ALLOW: dict[str, set[str]] = {
    "literacy": {"STEP_", "W_"},
    "tool-reference": {"W_"},
    "mastery": set(),
    "compression": set(),
    "chatter": set(),
}

# Spec r5 R5-5 / section 5 A3. "->" and "<->" count with or without spaces. The
# forms "+ & ~ |" count only with a space either side, between word characters,
# backticks, quotes or brackets, because unspaced forms are legitimate text
# (C++, R&D, ~/.claude).
GLYPH = re.compile(r"""[⊕⇌∧∨→∴⧺≠≤≥≈×]|<->|->|(?<=[\w`"'\)\]])\s(\+|&|~|\|)\s(?=[\w`"'\(\[])""")

# P2-8b1 owner rule: ``test_pith_spec_kernels.py`` owns the standard and the container
# kernel strings (it reads them from the machine-readable list in pith-spec.md). This
# file keeps key presence and each kernel's OWN items only. Own items are constrained by
# review, not by a test: adding an item plus a row here passes. The strings come from the
# P2-8b r2 kernel probe (kernel_draft_p28b_r2.py, full item set).
OWN_KERNEL_STRINGS: dict[str, dict[str, list[str]]] = {
    "literacy": {
        "TARGET": ["parser-safe OCTAVE in PITH"],
        "NEVER": [
            "tab characters outside literal zones",
            "bare numeric keys",
            "markdown headings or bullets inside the envelope",
            "nested inline maps",
        ],
        "MUST": [
            "section signs quoted inside values",
            "KEY: opens a block, KEY:: never does",
            "envelope line, META with TYPE and VERSION, body, closing line",
            "lists in square brackets; true, false, null lowercase",
        ],
        "GATE": ["Is every line keyed, in PITH, identifiers exact, receipts clean?"],
    },
    "mastery": {
        "TARGET": ["advanced OCTAVE forms a parser or validator reads, written in PITH"],
        "NEVER": ["glyphs outside schema-definition examples", "the glossary used for writing"],
        "MUST": [
            "holographic constraints only in schema-definition files",
            "one facet per archetype, 32 characters at most, in angle brackets",
            "maps of maps as blocks",
        ],
        "GATE": ["Is every glyph inside a schema-definition example, every other relation in words?"],
    },
    "compression": {
        "NEVER": ["compressing before choosing the tier", "dropping causal chains, conditions or numbers"],
        "MUST": [
            "tier first; default conservative; references lossless",
            "compressed output keeps COMPRESSION_TIER and LOSS_PROFILE in META",
            "a LOSSLESS tier drops nothing",
            "one example per abstraction kept",
        ],
        "GATE": [
            "Could a reader rebuild every causal chain, condition and number, and does META say what was dropped?"
        ],
    },
    # chatter: the standard items come from pith-spec.md (the drift test owns them). Own items: only what the
    # record's REWRITE_SCOPE keeps beyond PITH, which is provenance on every message. Identifiers verbatim in
    # backticks and hedges verbatim are the standard items "Exact identifiers" and "Hedges verbatim". Wording is
    # the RED author's proposal; GREEN or review may change it by changing this row.
    "chatter": {
        "MUST": ["provenance on every message: measured at a SHA, relayed or inferred"],
    },
    # tool-reference: today's kernel items other than the container items (which the new
    # test owns). Wording is unchanged by P2-8b1.
    "tool-reference": {
        "NEVER": [
            "`.oct.md` files written with Write or Edit",
            "VALIDATED claimed without a read receipt",
            "empty warnings trusted alone",
            "a bare dict replace where siblings must survive",
            "a call to `octave_fmt`",
            "remediation of frozen archives",
        ],
        "MUST": [
            "`octave_write` only; `schema=` when one applies; dry run before a destructive change",
            "status, errors, validation status, corrections, warnings and repairs triaged as discarding, advisory or benign",
            "changes mode: MERGE to keep siblings; a bare dict is a full replace; nested or new keys through `content=` with preserve",
            "advisory warnings remediated only on the record already being amended",
        ],
    },
}

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
    # chatter: no inbound section citations exist (git grep at c743fb9). The kernel section is what both
    # extractors read, so that is the one reference that must keep resolving.
    "chatter": [
        (r"^\s*§5::ANCHOR_KERNEL\s*$", "§5::ANCHOR_KERNEL"),
    ],
}
# tool-reference: (parent section number, key regex, label)
TOOL_REFERENCE_KEY_REFERENCES = [
    (3, r"^\s*RECEIPT_GATE:", "§3::RECEIPT_GATE"),
    (3, r"^\s*TRIAGE:", "§3::TRIAGE"),
    (6, r"^\s*SNAKE_CASE_BLOB:", "§6::SNAKE_CASE_BLOB"),
]
STALE_RULE_KEY_REFERENCE = re.compile(r"R3a|literacy R12|literacy R13")

# ONE allow-list source for A3 and A12 (spec r5 R5-4). The allow-list is scoped
# by enclosing section token. This is a deliberate choice that spec section 12
# accepted, not a pending tightening: section numbers are the stable, cited
# anchors, whereas parent key names are free to change. Reading-reference fences may carry
# glyphs and are exempt from A12 (literacy section 1d side-by-side comparison
# included in both). Schema-definition example fences may carry glyphs but are
# still validated by A12.
READING_REFERENCE_SECTIONS: dict[str, str] = {
    "literacy": r"^(1b|1d|2[a-z]?)$",
    "mastery": r"^(1|2)[a-z]?$",
}
SCHEMA_EXAMPLE_SECTIONS: dict[str, str] = {
    "mastery": r"^4[a-z]?$",
}
READING_REFERENCE_MAX_LINES = 40


def _in_reading_reference(name: str, section: str) -> bool:
    rx = READING_REFERENCE_SECTIONS.get(name)
    return rx is not None and re.match(rx, section) is not None


def _in_schema_examples(name: str, section: str) -> bool:
    rx = SCHEMA_EXAMPLE_SECTIONS.get(name)
    return rx is not None and re.match(rx, section) is not None


# Spec section 5 A12 and r5 R5-1, R5-2.
A12_ORDINARY_E007_ALLOWED = {"META.PURPOSE"}
A12_SANCTIONED_WRONG_KEY = "WRONG_EXAMPLE"
# R5-2: compression fences only, E007 on exactly these two META keys, reason-coded
# to operator ruling OCTAVE-MCP-P2-8-SKILLS-LANGUAGE-RULINGS-20261101 (B4 = a:
# the compression META template keeps the pair) and to #514 (META schema gap).
# When #514 lands this exception goes. Deleting the template to go green is forbidden.
A12_COMPRESSION_E007_ALLOWED = {"META.COMPRESSION_TIER", "META.LOSS_PROFILE"}
# R5-1: per-file minimum number of validated example fences (non-vacuity).
A12_MIN_VALIDATED = {"literacy": 1, "mastery": 1, "compression": 1, "tool-reference": 0, "chatter": 1}
# R5-1: an info tag naming one of these means the fence is not OCTAVE.
A12_NON_OCTAVE_TAGS = {"python", "json", "yaml", "text", "ts", "regex", "bash"}

# Spec section 5 A9, re-copied for P2-8b1 from hestai-workbench ``main/src/services/payloadCompiler.ts``
# line 85 (``extractAnchorKernel``) at WORKBENCH_SHA below. #664 moved the terminator:
# ``===END===`` ends the kernel only at the start of a line (``\n===END===``), as the
# section header already did. The regex line is byte-identical at origin/main 7e2435f.
# JS ``$`` without the m flag differs from Python's, so this runs in node.
WORKBENCH_SHA = "9d1a53e"
WORKBENCH_JS = (
    r"""const fs=require("fs");const n=fs.readFileSync(0,"utf8").replace(/\r\n?/g,"\n");"""
    r"""const m=n.match(/§5::ANCHOR_KERNEL[^\S\n]*(?=\n|$)([\s\S]*?)(?=\n§\d+::|\n===END===|$)/);"""
    r"""process.stdout.write(m&&m[1]?m[1].trim():"");"""
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


_FENCE_OPEN = re.compile(r"^\s*(`{3,})(.*)$")
_SECTION_HEADER = re.compile(r"^\s*§(\d+[a-z]?)::")
_KEY_LINE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)::?")


def _scan(text: str) -> tuple[list[tuple[int, str]], list[dict[str, Any]]]:
    """Return (lines outside fences as (lineno, text), fenced blocks).

    Each block: start (1-based line of the opening fence), lines (inner),
    info (lowercased text after the opening backticks), parent_key (nearest key line above the fence), section (nearest section
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
                current = {
                    "start": idx,
                    "lines": [],
                    "parent_key": parent_key,
                    "section": section,
                    "info": m.group(2).strip().lower(),
                }
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
    """First-match kernel extraction, copied from odyssean-anchor.

    Source: odyssean-anchor-mcp src/odyssean_anchor/core/extraction.py:964-997
    at SHA 5a41ed6 (/Volumes/HestAI-Projects/odyssean-anchor-mcp). It takes the FIRST match of
    ``§(?:\\d+::)?ANCHOR_KERNEL`` anywhere in the file, skips the marker line,
    then stops at a stripped line starting ``===END_KERNEL===`` or ``===END===``
    or matching ``^§\\d+::``. Spec section 2 "Second extractor".
    """
    kernel_pattern = re.compile(r"§(?:\d+::)?ANCHOR_KERNEL")
    kernel_match = kernel_pattern.search(text)
    if kernel_match is None:
        return None

    start_idx = kernel_match.start()

    # Start extraction after the marker line
    lines = text[start_idx:].split("\n")
    kernel_lines: list[str] = []
    in_kernel = False

    for line in lines:
        # Skip the marker line itself
        if kernel_pattern.search(line) and not in_kernel:
            in_kernel = True
            continue

        if in_kernel:
            stripped = line.strip()

            # Stop at end marker
            if stripped.startswith("===END_KERNEL==="):
                break

            # Stop at next section or document end
            if re.match(r"^§\d+::", stripped) or stripped.startswith("===END==="):
                break

            kernel_lines.append(line)

    if not kernel_lines:
        return None

    return "\n".join(kernel_lines).strip()


def _workbench_kernel(text: str, js: str = WORKBENCH_JS) -> str:
    node = shutil.which("node")
    if node is None:
        pytest.fail("A9 requires node on PATH to run the workbench regex byte-for-byte; node was not found")
    proc = subprocess.run([node, "-e", js], input=text, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"A9 node run failed: {proc.stderr}"
    return proc.stdout


def _glyph_lines(lines: list[tuple[int, str]]) -> list[str]:
    return [f"{n}: {t.strip()[:90]}" for n, t in lines if GLYPH.search(t)]


def _tokens(text: str) -> int:
    return len(tiktoken.get_encoding("cl100k_base").encode(text))


def _bracket_body(text: str) -> str:
    """Inside of the list that starts at text[0] == '[' (quote-aware, own brackets only)."""
    assert text.startswith("[")
    depth = 0
    in_quote = False
    i = 0
    while i < len(text):
        ch = text[i]
        if in_quote:
            if ch == "\\":
                i += 1
            elif ch == '"':
                in_quote = False
        elif ch == '"':
            in_quote = True
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return text[1:i]
        i += 1
    return text[1:]


def _key_text(block: str, key: str) -> str | None:
    """Text of the value of the first ``KEY::`` line in a block (whole list if bracketed)."""
    m = re.search(rf"^\s*{key}::", block, flags=re.MULTILINE)
    if not m:
        return None
    rest = block[m.end() :]
    stripped = rest.lstrip(" \t")
    if stripped.startswith("["):
        return _bracket_body(stripped)
    return rest.split("\n", 1)[0]


_KERNEL_ITEM = re.compile(r'"((?:[^"\\]|\\.)*)"')


def _kernel_items(kernel: str, key: str) -> list[str] | None:
    """Quoted entries of ``KEY::`` (a list or a scalar), unescaped; None when the key is absent."""
    body = _key_text(kernel, key)
    if body is None:
        return None
    return [m.group(1).replace('\\"', '"') for m in _KERNEL_ITEM.finditer(body)]


def _flat_prefixes(entries: list[dict[str, Any]]) -> list[str]:
    """Prefixes of W_FLAT_PREFIX_SCALAR entries, parsed from "share prefix 'X_'"."""
    found: list[str] = []
    for e in entries:
        if e.get("code") != "W_FLAT_PREFIX_SCALAR":
            continue
        m = re.search(r"share prefix '([^']+)'", str(e.get("message", "")))
        found.append(m.group(1) if m else "?")
    return found


def _flat_prefix_problems(name: str, entries: list[dict[str, Any]]) -> list[str]:
    prefixes = _flat_prefixes(entries)
    problems: list[str] = []
    bad = sorted({p for p in prefixes if p not in FLAT_PREFIX_ALLOW[name]})
    if bad:
        problems.append(f"flat-prefix groups not allowed {bad} (allowed {sorted(FLAT_PREFIX_ALLOW[name])})")
    cap = A10_FLAT_PREFIX_SCALAR_BASELINE[name]
    if len(prefixes) > cap:
        problems.append(f"{len(prefixes)} flat-prefix groups, baseline cap {cap}")
    return problems


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


@pytest.mark.parametrize("name", SKILLS)
def test_A1_flat_prefix_groups_only_allowed_prefixes(name: str) -> None:
    problems = _flat_prefix_problems(name, _validate(name)["warnings"])
    assert not problems, f"A1 {name}: {problems}"


def test_A1_flat_prefix_check_fires_on_a_disallowed_group() -> None:
    """Canary: the prefix allow-set rejects a group outside it and a count above baseline."""
    msg = "W_FLAT_PREFIX_SCALAR at line 1: sibling keys share prefix 'ANNOTATION_'; nest under it. Keys: A, B, C"
    entry = {"code": "W_FLAT_PREFIX_SCALAR", "message": msg}
    assert _flat_prefix_problems("literacy", [entry])
    ok = {"code": "W_FLAT_PREFIX_SCALAR", "message": msg.replace("ANNOTATION_", "STEP_")}
    assert _flat_prefix_problems("literacy", [ok]) == []
    assert _flat_prefix_problems("compression", [ok])  # compression allows none, baseline 0


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
    problems: list[str] = []
    for b in blocks:
        body = "\n".join(b["lines"])
        hit = bool(GLYPH.search(body))
        reading = _in_reading_reference(name, b["section"])
        schema = _in_schema_examples(name, b["section"])
        where = f"fence at line {b['start']} (section §{b['section']}, parent {b['parent_key']})"
        if hit and not (reading or schema):
            problems.append(f"{where}: glyphs in a section not on the allow-list")
            continue
        if schema:
            if not re.search(r"^\s*TYPE::SCHEMA\b", body, flags=re.MULTILINE):
                problems.append(f"{where}: schema-example fence lacks TYPE::SCHEMA")
        elif reading and hit and len(b["lines"]) > READING_REFERENCE_MAX_LINES:
            problems.append(
                f"{where}: reading-reference fence has {len(b['lines'])} lines, max {READING_REFERENCE_MAX_LINES}"
            )
    assert not problems, f"A3 {name}: " + "; ".join(problems)


@pytest.mark.parametrize(
    "text",
    ["a->b", "x <-> y", "do a -> b", "keep `a` + `b`", "one | two", "R & D", "left ~ right", "a ⊕ b"],
)
def test_A3_regex_fires_on_relations(text: str) -> None:
    """Canary (R5-5): arrows count unspaced; + & ~ | count when spaced between words."""
    assert GLYPH.search(text), f"A3 canary: {text!r} should count as a glyph"


@pytest.mark.parametrize("text", ["C++", "R&D", "~/.claude", "a+b", "x|y", "plain words only"])
def test_A3_regex_ignores_legitimate_text(text: str) -> None:
    assert not GLYPH.search(text), f"A3 canary: {text!r} must not count as a glyph"


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
# A5b Inbound rule citations (spec r4 A5b)
# ---------------------------------------------------------------------------
# Spec section 3 C4 ripple list: each prose citation that replaces a rule id
# must still resolve to a sentence in the target section's RULES list.
# (citing file, target file, target section token, required substring in a RULES
# sentence, citing-side phrase). The citing-side phrase must sit on the SAME line
# as a citation of "<target> §<token>" in the citing file (cubic review on #542:
# the citing side was never searched).
RULE_CITATIONS: list[tuple[str, str, str, str, str]] = [
    # tool-reference cited "literacy R13" (empty KEY:: opens no block)
    ("tool-reference", "literacy", "3", "KEY::", "empty `KEY::`"),
    # compression cited "literacy R12" (section headers carry no value)
    ("compression", "literacy", "3", "section header", "section header"),
    # tool-reference cited R3a; successor is the note-form sentence in literacy 4b.
    # (mastery's R3a citation sat in its section 7a, which the rewrite deleted, so
    # that pair no longer exists; the deletion is in the CHANGELOG receipt.)
    ("tool-reference", "literacy", "4b", "note form", "note-form"),
]


def _citation_found(citing_text: str, target: str, section: str, phrase: str) -> bool:
    """True if one line cites ``<target> §<section>`` (exact token) and holds the phrase."""
    cite = re.compile(rf"{re.escape(target)} §{re.escape(section)}(?![0-9a-z])")
    return any(cite.search(line) and phrase in line for line in citing_text.split("\n"))


def _rules_sentences(text: str, section: str) -> list[str]:
    """Quoted sentences of the ``RULES::[...]`` list directly in an EXACT section token.

    The region runs from the section header to the next header of any other
    token, outside fences. Only the RULES list's own brackets are read.
    """
    outside, _ = _scan(text)
    start = next(
        (i for i, (_, t) in enumerate(outside) if (m := _SECTION_HEADER.match(t)) and m.group(1) == section), None
    )
    if start is None:
        return []
    end = len(outside)
    for i in range(start + 1, len(outside)):
        m = _SECTION_HEADER.match(outside[i][1])
        if m and m.group(1) != section:
            end = i
            break
    region = "\n".join(t for _, t in outside[start:end])
    m2 = re.search(r"^\s*RULES::(?=\[)", region, flags=re.MULTILINE)
    if not m2:
        return []
    body = _bracket_body(region[m2.end() :])
    return list(re.findall(r'"((?:[^"\\]|\\.)*)"', body))


def test_A5b_rules_parser_canary_exact_token_and_own_brackets() -> None:
    doc = (
        '§3::CRITICAL\n  RULES::[\n    "An empty `KEY::` opens no block [see x]."\n  ]\n  OTHER::["not a rule"]\n'
        '  §3b::ENV\n    RULES::["wrong section"]\n§4::W\n'
    )
    assert _rules_sentences(doc, "3") == ["An empty `KEY::` opens no block [see x]."]
    assert _rules_sentences(doc, "3b") == ["wrong section"]
    assert _rules_sentences(doc, "9") == []


@pytest.mark.parametrize(
    ("citing", "target", "section", "needle", "phrase"),
    RULE_CITATIONS,
    ids=[f"{c}->{t}-§{s}-{n}" for c, t, s, n, _ in RULE_CITATIONS],
)
def test_A5b_rule_citation_target_holds_cited_sentence(
    citing: str, target: str, section: str, needle: str, phrase: str
) -> None:
    sentences = _rules_sentences(_read(target), section)
    assert sentences, f"A5b {citing} cites {target} §{section}: no RULES list of quoted sentences found there"
    assert any(needle in x for x in sentences), (
        f"A5b {citing} cites {target} §{section}: no RULES sentence contains {needle!r} "
        f"({len(sentences)} sentences)"
    )


@pytest.mark.parametrize(
    ("citing", "target", "section", "needle", "phrase"),
    RULE_CITATIONS,
    ids=[f"{c}->{t}-§{s}-{p}" for c, t, s, _, p in RULE_CITATIONS],
)
def test_A5b_citing_file_cites_the_target(citing: str, target: str, section: str, needle: str, phrase: str) -> None:
    assert _citation_found(
        _read(citing), target, section, phrase
    ), f"A5b {citing}: no line cites '{target} §{section}' together with {phrase!r}"


def test_A5b_citing_side_canary_missing_citation_fails() -> None:
    good = 'HIDDEN::"empty `KEY::` opens no block (literacy §3, the rule)"\n'
    assert _citation_found(good, "literacy", "3", "empty `KEY::`")
    assert not _citation_found("OTHER::x\n", "literacy", "3", "empty `KEY::`"), "missing citation must fail"
    assert not _citation_found(good.replace("§3,", "§3b,"), "literacy", "3", "empty `KEY::`"), "wrong section token"
    split = 'A::"empty `KEY::` opens no block"\nB::"see literacy §3"\n'
    assert not _citation_found(split, "literacy", "3", "empty `KEY::`"), "phrase on another line must not count"


# ---------------------------------------------------------------------------
# A8 Kernel coverage (each string under its own key, spec r5 R5-4)
# ---------------------------------------------------------------------------
def _required_by_key(name: str) -> dict[str, list[str]]:
    """Key presence (NEVER, MUST) plus this kernel's own items; standard and container items are not here."""
    req: dict[str, list[str]] = {"NEVER": [], "MUST": []}
    for key, strings in OWN_KERNEL_STRINGS[name].items():
        req.setdefault(key, []).extend(strings)
    return req


def _kernel_coverage_missing(name: str, kernel: str) -> list[str]:
    missing: list[str] = []
    for key, strings in _required_by_key(name).items():
        have = _kernel_items(kernel, key)
        if have is None:
            missing.append(f"{key}:: (key absent)")
            continue
        missing.extend(f"{key}: {s}" for s in strings if s not in have)
    return missing


def _kernel_for(name: str, extractor: str) -> str | None:
    text = _read(name)
    return _odyssean_kernel(text) if extractor == "odyssean" else _workbench_kernel(text)


@pytest.mark.parametrize("extractor", ["odyssean", "workbench"])
@pytest.mark.parametrize("name", ALL)
def test_A8_kernel_carries_required_strings_under_their_keys(name: str, extractor: str) -> None:
    kernel = _kernel_for(name, extractor)
    assert kernel, f"A8 {name} ({extractor}): no kernel extracted"
    missing = _kernel_coverage_missing(name, kernel)
    assert not missing, f"A8 {name} ({extractor}): {len(missing)} strings missing, first: {missing[:4]}"


def test_A8_check_fires_on_wrong_key_and_missing_key() -> None:
    """Canary (R5-4): an own NEVER item sitting under MUST does not count; an absent key is reported."""
    kernel = 'TARGET::"x"\nNEVER::["a"]\nMUST::["a call to `octave_fmt`"]\n'
    missing = _kernel_coverage_missing("tool-reference", kernel)
    assert "NEVER: a call to `octave_fmt`" in missing
    assert any(m.startswith("MUST: `octave_write` only") for m in missing)
    assert _kernel_coverage_missing("tool-reference", 'TARGET::"x"\n') == [
        "NEVER:: (key absent)",
        "MUST:: (key absent)",
    ]


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
def test_A9_workbench_and_odyssean_kernels_are_equal(name: str) -> None:
    text = _read(name)
    wb = _workbench_kernel(text).strip()
    od = (_odyssean_kernel(text) or "").strip()
    assert wb == od, f"A9 {name}: extractors disagree (workbench {len(wb)} chars, odyssean {len(od)} chars)"


def test_A9_equality_check_fires_on_the_end_marker_defect() -> None:
    """Canary: an indented ``===END===`` line ends the odyssean kernel (it strips) but not the workbench one.

    Since #664 the workbench terminator is line-anchored, so an inline or indented token no
    longer truncates it. The extractors still disagree on this input, so the equality check fires.
    """
    doc = '===S===\n§5::ANCHOR_KERNEL\n  TARGET::"t"\n  ===END=== tail\n  GATE::"g"\n===END===\n'
    assert _workbench_kernel(doc).strip() != (_odyssean_kernel(doc) or "").strip()
    assert "GATE::" in _workbench_kernel(doc)


@pytest.mark.parametrize("name", ALL)
def test_A9_anchor_kernel_named_exactly_once(name: str) -> None:
    n = _read(name).count("ANCHOR_KERNEL")
    assert n == 1, f"A9 {name}: ANCHOR_KERNEL appears {n} times, must be exactly once"


# ---------------------------------------------------------------------------
# A10 Canonical fixed point
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name", ALL)
def test_A10_write_dry_run_has_no_corrections(name: str) -> None:
    """Spec A10 (r5 R5-3): corrections hold no code other than allow-listed W_FLAT_PREFIX_SCALAR.

    The spec's own C4 keeps the sanctioned ``STEP_n`` runbook, whose
    ``W_FLAT_PREFIX_SCALAR`` the dry run emits into ``corrections``, so a literal
    ``== []`` would be unpassable. Every other code (normalisation, reconciliation,
    annotation advisories) must be absent. ``W_FLAT_PREFIX_SCALAR`` is allowed only
    for the prefixes in ``FLAT_PREFIX_ALLOW`` and at most the measured baseline count.
    """
    r = _dry_run_write(name)
    assert r["status"] == "success", f"A10 {name}: dry run status {r['status']} errors {r.get('errors')}"
    corrections = r.get("corrections", [])
    extra = {c: n for c, n in _codes(corrections).items() if c != "W_FLAT_PREFIX_SCALAR"}
    assert not extra, f"A10 {name}: corrections other than W_FLAT_PREFIX_SCALAR: {extra}"
    problems = _flat_prefix_problems(name, corrections)
    assert not problems, f"A10 {name}: {problems}"


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
# Fragment fences (first meaningful line is not an envelope or META:) get a META block first.
_A12_FRAGMENT_META = 'META:\n  TYPE::EXAMPLE\n  VERSION::"1"\n'


def _first_meaningful(lines: list[str]) -> tuple[int, str]:
    """Index and stripped text of the first line that is not blank and not a ``//`` comment."""
    for i, ln in enumerate(lines):
        t = ln.strip()
        if t and not t.startswith("//"):
            return i, t
    return len(lines), ""


def _a12_scan(name: str, text: str) -> tuple[int, list[str], list[str]]:
    """Validate every non-exempt fence STRICT.

    Returns (fences validated, problems, bodies of fences that validated cleanly).

    Spec r5 R5-1: every fence outside the reading-reference allow-list is
    validated unless its parent key is WRONG_EXAMPLE or its info tag names a
    non-OCTAVE language. Leading ``//`` and blank lines are skipped when
    classifying. ``===NAME===`` fences are validated as written; ``META:`` and all
    other fences are wrapped in a minimal envelope (plus a META block first for
    fragments). Also returns the bodies of the fences that validated cleanly.
    """
    _, blocks = _scan(text)
    problems: list[str] = []
    clean_bodies: list[str] = []
    checked = 0
    for b in blocks:
        tag = b["info"].split()[0] if b["info"] else ""
        if tag in A12_NON_OCTAVE_TAGS:
            continue
        if b["parent_key"] == A12_SANCTIONED_WRONG_KEY:
            continue
        if _in_reading_reference(name, b["section"]):
            continue
        lines = textwrap.dedent("\n".join(b["lines"])).strip("\n").split("\n")
        idx, first = _first_meaningful(lines)
        is_envelope = bool(_ENVELOPE_OPEN.match(first))
        is_meta = first == "META:"
        body = "\n".join(lines[idx:] if is_envelope else lines)
        checked += 1
        problems_before = len(problems)
        where = f"fence at line {b['start']} (parent {b['parent_key']})"
        if is_envelope:
            content = body if "===END===" in body else body + "\n===END===\n"
        elif is_meta:
            content = f"===EXAMPLE===\n{body}\n===END===\n"
        else:
            content = f"===EXAMPLE===\n{_A12_FRAGMENT_META}{body}\n===END===\n"
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
        allowed = set(A12_ORDINARY_E007_ALLOWED)
        if name == "compression":
            allowed |= A12_COMPRESSION_E007_ALLOWED
        for e in r["validation_errors"]:
            field = str(e.get("field"))
            ok = e.get("code") == "E007" and (field.startswith("META.") if is_schema else field in allowed)
            if not ok:
                problems.append(f"{where}: {e.get('code')} on {field}")
        if len(problems) == problems_before:
            clean_bodies.append(body)
    return checked, problems, clean_bodies


def _a12_check(name: str, text: str) -> tuple[int, list[str]]:
    checked, problems, _ = _a12_scan(name, text)
    return checked, problems


@pytest.mark.parametrize("name", ALL)
def test_A12_fenced_examples_parse_strict(name: str) -> None:
    checked, problems = _a12_check(name, _read(name))
    assert not problems, f"A12 {name} ({checked} example fences checked): " + "; ".join(problems)


@pytest.mark.parametrize("name", SKILLS)
def test_A12_minimum_validated_fences(name: str) -> None:
    """R5-1 non-vacuity: a rewrite cannot pass A12 by having no example fences to check."""
    checked, _ = _a12_check(name, _read(name))
    assert checked >= A12_MIN_VALIDATED[name], f"A12 {name}: {checked} fences validated, need {A12_MIN_VALIDATED[name]}"


_GOOD_DOC = '===X===\nMETA:\n  TYPE::T\n  VERSION::"1"\nKEY::"v"\n===END===\n'
_BAD_DOC = '===X===\nMETA:\n  TYPE::T\n  VERSION::"1"\nbare prose line here\n===END===\n'


def _fenced(parent: str, body: str, tag: str = "") -> str:
    return f"§1::S\n  {parent}:\n    ```{tag}\n{body}    ```\n"


def test_A12_canary_bad_fence_is_reported_and_exemptions_hold() -> None:
    checked, problems = _a12_check("literacy", _fenced("EXAMPLE", _BAD_DOC))
    assert checked == 1 and problems, "A12 canary: a bad fence must be reported"
    assert _a12_check("literacy", _fenced("WRONG_EXAMPLE", _BAD_DOC)) == (0, [])
    assert _a12_check("literacy", _fenced("EXAMPLE", _BAD_DOC, "python")) == (0, [])
    assert _a12_check("literacy", _fenced("EXAMPLE", "// note\n\n" + _GOOD_DOC)) == (1, [])
    reading = "§1b::R\n  REF:\n    ```\n" + _BAD_DOC + "    ```\n"
    assert _a12_check("literacy", reading) == (0, [])


def test_A12_canary_compression_template_exception_is_compression_only() -> None:
    tmpl = '===X===\nMETA:\n  TYPE::T\n  VERSION::"1"\n  COMPRESSION_TIER::LOSSLESS\n  LOSS_PROFILE::"kept all"\n===END===\n'
    assert _a12_check("compression", _fenced("TEMPLATE", tmpl)) == (1, [])
    _, problems = _a12_check("literacy", _fenced("TEMPLATE", tmpl))
    assert problems, "A12 canary: the E007 allowance must not leak to other files"


# ---------------------------------------------------------------------------
# A13 Structural rules C1, C4, C9 (spec r5 R5-6)
# ---------------------------------------------------------------------------
_KEYED_ID = re.compile(r"^\s*(R\d+[a-z]?|AP\d+|P\d+)::")


def _c1_violations(text: str) -> list[str]:
    """Column-0 content lines after the first section header, outside fences.

    Allowed at column 0: section headers, ``===END===`` and ``//`` comments
    (comments carry orientation only and are not content).
    """
    outside, _ = _scan(text)
    seen = False
    bad: list[str] = []
    for n, line in outside:
        if _SECTION_HEADER.match(line):
            seen = True
            continue
        if not seen or not line.strip() or line[0] in " \t":
            continue
        if line.startswith("===END===") or line.startswith("//"):
            continue
        bad.append(f"{n}: {line.strip()[:70]}")
    return bad


def _c4_violations(text: str) -> list[str]:
    outside, _ = _scan(text)
    return [f"{n}: {t.strip()[:70]}" for n, t in outside if _KEYED_ID.match(t)]


def _c9_violations(text: str) -> list[str]:
    """COMPRESSION_TIER / LOSS_PROFILE keys inside the document's own META block."""
    bad: list[str] = []
    in_meta = False
    for n, line in enumerate(text.split("\n"), start=1):
        if re.match(r"^META:\s*$", line):
            in_meta = True
            continue
        if in_meta:
            if line.strip() and line[0] not in " \t":
                break
            if re.match(r"^\s*(COMPRESSION_TIER|LOSS_PROFILE)::", line):
                bad.append(f"{n}: {line.strip()[:70]}")
    return bad


@pytest.mark.parametrize("name", ALL)
def test_A13_C1_no_column_zero_content_after_first_header(name: str) -> None:
    bad = _c1_violations(_read(name))
    assert not bad, f"A13/C1 {name}: {len(bad)} column-0 content lines, first: {bad[:4]}"


@pytest.mark.parametrize("name", ALL)
def test_A13_C4_no_rule_or_item_id_keys(name: str) -> None:
    bad = _c4_violations(_read(name))
    assert not bad, f"A13/C4 {name}: {len(bad)} id-keyed lines, first: {bad[:4]}"


@pytest.mark.parametrize("name", SKILLS)
def test_A13_C9_skill_meta_has_no_compression_keys(name: str) -> None:
    bad = _c9_violations(_read(name))
    assert not bad, f"A13/C9 {name}: {bad}"


def test_A13_canaries_fire_on_synthetic_bad_input() -> None:
    doc = '===S===\nMETA:\n  TYPE::SKILL\n  COMPRESSION_TIER::LOSSLESS\n  LOSS_PROFILE::"x"\n§1::A\nCOLZERO::"v"\n  R3a::"rule"\n  AP2::"x"\n  P12::"y"\n===END===\n'
    assert len(_c1_violations(doc)) == 1
    assert len(_c4_violations(doc)) == 3
    assert len(_c9_violations(doc)) == 2
    clean = '===S===\nMETA:\n  TYPE::SKILL\n§1::A\n  // note\n  RULES::["x"]\n```\nINSIDE::"fence"\n```\n===END===\n'
    assert _c1_violations(clean) == [] and _c4_violations(clean) == [] and _c9_violations(clean) == []


# ---------------------------------------------------------------------------
# A12 residual guards (TMG T2 advisories)
# ---------------------------------------------------------------------------
def test_A12_compression_keeps_validated_template_fence() -> None:
    """Spec r5 R5-2: the template stays. A validated fence must hold both META keys."""
    _, _, clean = _a12_scan("compression", _read("compression"))
    ok = [b for b in clean if "COMPRESSION_TIER" in b and "LOSS_PROFILE" in b]
    assert ok, "A12 compression: no cleanly validated fence contains both COMPRESSION_TIER and LOSS_PROFILE"


_OCTAVE_LOOKING = re.compile(r"^(===(?!END===)[A-Z_][A-Z0-9_]*===$|META:|§\d+[a-z]?::|[A-Z][A-Z0-9_]*(::|:(\s|$)))")


def _tag_disguise_problems(name: str, text: str) -> list[str]:
    """Non-OCTAVE-tagged fences whose first meaningful line looks like OCTAVE.

    Stops an OCTAVE example escaping A12 by carrying a python/json/... tag.
    Exempt: WRONG_EXAMPLE and the reading-reference allow-list.
    """
    _, blocks = _scan(text)
    problems: list[str] = []
    for b in blocks:
        tag = b["info"].split()[0] if b["info"] else ""
        if tag not in A12_NON_OCTAVE_TAGS:
            continue
        if b["parent_key"] == A12_SANCTIONED_WRONG_KEY or _in_reading_reference(name, b["section"]):
            continue
        _, first = _first_meaningful(textwrap.dedent("\n".join(b["lines"])).strip("\n").split("\n"))
        if _OCTAVE_LOOKING.match(first):
            problems.append(f"fence at line {b['start']} (tag {tag}, parent {b['parent_key']}): starts {first[:40]!r}")
    return problems


@pytest.mark.parametrize("name", ALL)
def test_A12_non_octave_tagged_fences_do_not_look_like_octave(name: str) -> None:
    problems = _tag_disguise_problems(name, _read(name))
    assert not problems, f"A12 {name}: OCTAVE example hidden behind a language tag: {problems}"


@pytest.mark.parametrize(
    "first",
    ["===X===", "META:", "§3::NAME", 'KEY::"v"', "KEY:", "// note\n\nTARGET::x"],
)
def test_A12_tag_disguise_canary_fires(first: str) -> None:
    for tag in ("python", "json", "yaml", "text", "ts", "regex", "bash"):
        assert _tag_disguise_problems("literacy", _fenced("EXAMPLE", first + "\n", tag)), f"{tag}: {first!r}"


def test_A12_tag_disguise_canary_exemptions_and_plain_code() -> None:
    assert _tag_disguise_problems("literacy", _fenced("WRONG_EXAMPLE", "KEY::x\n", "text")) == []
    assert _tag_disguise_problems("literacy", "§1b::R\n  REF:\n    ```text\nKEY::x\n    ```\n") == []
    assert _tag_disguise_problems("literacy", _fenced("EXAMPLE", "import re\nx = 1\n", "python")) == []
    assert _tag_disguise_problems("literacy", _fenced("EXAMPLE", '{"a": 1}\n', "json")) == []
    assert _tag_disguise_problems("literacy", _fenced("EXAMPLE", "KEY::x\n", "")) == []  # untagged is A12's job


def test_A12_template_guard_canary_needs_both_keys_and_a_clean_fence() -> None:
    both = '===X===\nMETA:\n  TYPE::T\n  VERSION::"1"\n  COMPRESSION_TIER::LOSSLESS\n  LOSS_PROFILE::"kept all"\n===END===\n'
    one = both.replace('  LOSS_PROFILE::"kept all"\n', "")
    _, _, clean = _a12_scan("compression", _fenced("TEMPLATE", both))
    assert any("COMPRESSION_TIER" in b and "LOSS_PROFILE" in b for b in clean)
    _, _, clean = _a12_scan("compression", _fenced("TEMPLATE", one))
    assert not any("COMPRESSION_TIER" in b and "LOSS_PROFILE" in b for b in clean)
    bad = both.replace("===END===", "bare prose line\n===END===")
    _, _, clean = _a12_scan("compression", _fenced("TEMPLATE", bad))
    assert clean == [], "a fence that fails validation must not count as the template"


# ---------------------------------------------------------------------------
# A13 META path fields (spec r5+ section 15 R15)
# ---------------------------------------------------------------------------
# META CANONICAL and SOURCE are machine-read path fields (a canonical-paths
# pre-commit hook reads them), so their values must be bare paths: no backtick,
# no whitespace, no semicolon, and so no prose note.
_META_PATH_KEYS = ("CANONICAL", "SOURCE")
_META_PATH_LINE = re.compile(r"^\s*(" + "|".join(re.escape(k) for k in _META_PATH_KEYS) + r")::(.*)$")


def _meta_path_violations(text: str) -> list[str]:
    bad: list[str] = []
    in_meta = False
    for n, line in enumerate(text.split("\n"), start=1):
        if re.match(r"^META:\s*$", line):
            in_meta = True
            continue
        if not in_meta:
            continue
        if line.strip() and line[0] not in " \t":
            break
        m = _META_PATH_LINE.match(line)
        if not m:
            continue
        value = m.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = value[1:-1]
        if "`" in value or ";" in value or re.search(r"\s", value):
            bad.append(f"{n}: {m.group(1)}::{value[:70]}")
    return bad


@pytest.mark.parametrize("name", ALL)
def test_A13_R15_meta_path_fields_are_bare_paths(name: str) -> None:
    bad = _meta_path_violations(_read(name))
    assert not bad, f"A13/R15 {name}: META path fields must be bare paths (no backtick, whitespace or ';'): {bad}"


def test_A13_R15_canary_fires_on_decorated_path_fields() -> None:
    def doc(extra: str) -> str:
        return f'===S===\nMETA:\n  TYPE::PATTERN\n{extra}§1::A\n  CANONICAL::"outside meta `ok`"\n===END===\n'

    assert _meta_path_violations(doc('  SOURCE::"src/a/b.oct.md"\n  CANONICAL::".hestai-sys/x.oct.md"\n')) == []
    assert len(_meta_path_violations(doc('  SOURCE::"`src/a/b.oct.md`"\n'))) == 1  # backticks
    assert len(_meta_path_violations(doc('  CANONICAL::".hestai-sys/x.oct.md; legacy copy"\n'))) == 1  # ; and prose
    assert len(_meta_path_violations(doc('  CANONICAL::"two words"\n'))) == 1  # whitespace
    assert _meta_path_violations(doc("")) == []  # absent keys are fine; body lines are not META


# ---------------------------------------------------------------------------
# P2-8a guards: receipt and anchoring claims tied to the tool truth
# ---------------------------------------------------------------------------
_PROBE_DOC = '===X===\nMETA:\n  TYPE::T\n  VERSION::"1"\nK::"v"\n===END===\n'
_PURPOSE_DOC = '===X===\nMETA:\n  TYPE::T\n  VERSION::"1"\n  PURPOSE::"p"\n===END===\n'
_ANCHOR_FORMS = ("HOLOGRAPHIC<latest@local>", "HOLOGRAPHIC<frozen@sha256_abc123>")


def _value_of(text: str, key: str) -> str:
    m = re.search(rf"^\s*{key}::(.*)$", text, flags=re.MULTILINE)
    return m.group(1) if m else ""


def _repairs_attributed_to_write(text: str) -> list[str]:
    """Segments (split on ';' and sentence ends) naming `repairs[]` and `octave_write` but not `octave_validate`."""
    bad: list[str] = []
    for line in text.split("\n"):
        for seg in re.split(r";|\.\s|\.\"|\"$", line):
            if "repairs[]" in seg and "`octave_write`" in seg and "`octave_validate`" not in seg:
                bad.append(seg.strip()[:90])
    return bad


# g: repairs[] is not an octave_write receipt field
@pytest.mark.parametrize("lenient", [False, True])
def test_P2_8a_g_live_write_result_has_no_repairs_key(lenient: bool) -> None:
    """Tool truth: if WriteTool starts returning repairs, this fails and the g guard must be revisited."""
    r = asyncio.run(
        WriteTool().execute(
            target_path="/nonexistent-p2-8a/d.oct.md", content=_PROBE_DOC, dry_run=True, lenient=lenient
        )
    )
    assert "repairs" not in r, f"P2-8a g: WriteTool now returns repairs (lenient={lenient}); revisit the guard"


@pytest.mark.parametrize("name", ALL)
def test_P2_8a_g_no_sentence_attributes_repairs_to_octave_write(name: str) -> None:
    bad = _repairs_attributed_to_write(_read(name))
    assert not bad, f"P2-8a g {name}: `repairs[]` attributed to octave_write: {bad}"


def test_P2_8a_g_canary() -> None:
    assert _repairs_attributed_to_write('R::"read `corrections[]` and `repairs[]` from `octave_write` and triage"')
    ok = 'R::"`octave_write` returns `corrections[]`; `octave_validate` returns `repairs[]`"'
    assert _repairs_attributed_to_write(ok) == []


# c: warnings[] differs between the two tools
def test_P2_8a_c_live_validate_has_no_corrections_and_strict_warns_e007() -> None:
    v = asyncio.run(ValidateTool().execute(content=_PURPOSE_DOC, schema="META", profile="STRICT"))
    assert "corrections" not in v, "P2-8a c: ValidateTool now returns corrections; revisit the guard"
    assert "E007" in [w.get("code") for w in v["warnings"]], "P2-8a c: STRICT warnings no longer carry E007"


def _warnings_definition_problems(text: str) -> list[str]:
    value = _value_of(text, "WARNINGS")
    if not value:
        return ["no WARNINGS key"]
    problems = [f"WARNINGS does not name {t}" for t in ("`octave_write`", "`octave_validate`") if t not in value]
    if "`octave_validate`" in value:
        # The octave_validate part is what follows the tool name, up to the next ';' or end.
        part = value.split("`octave_validate`", 1)[1].split(";", 1)[0].lower()
        if "validation_errors" not in part and "e007" not in part:
            problems.append(
                "octave_validate part of WARNINGS does not mention its own codes (validation_errors or E007)"
            )
        # An explicit denial ("no corrections[]") is fine; any other mention is a false claim.
        if "corrections[]" in re.sub(r"\bno\s+`?corrections\[\]`?", "", part):
            problems.append("octave_validate part of WARNINGS claims corrections[]; that tool has none")
    return problems


def test_P2_8a_c_tool_reference_warnings_distinguishes_the_two_tools() -> None:
    problems = _warnings_definition_problems(_read("tool-reference"))
    assert not problems, f"P2-8a c tool-reference: {problems}"


def test_P2_8a_c_canary() -> None:
    assert _warnings_definition_problems('  WARNINGS::"subset of `corrections[]` with `safe: false`"')
    assert _warnings_definition_problems("  OTHER::x") == ["no WARNINGS key"]
    both = '  WARNINGS::"`octave_write`: subset of corrections; `octave_validate`: validation codes"'
    assert _warnings_definition_problems(both) == [
        "octave_validate part of WARNINGS does not mention its own codes (validation_errors or E007)"
    ]
    claims = '  WARNINGS::"`octave_write`: subset of corrections; `octave_validate`: E007 inside corrections[]"'
    assert _warnings_definition_problems(claims) == [
        "octave_validate part of WARNINGS claims corrections[]; that tool has none"
    ], "validate part claiming corrections[] must fail even with E007"
    denies = '  WARNINGS::"`octave_write`: subset of corrections; `octave_validate`: E007, no `corrections[]` here"'
    assert _warnings_definition_problems(denies) == [], "an explicit denial is allowed"
    shared = '  WARNINGS::"`octave_write` and `octave_validate` both return corrections[]"'
    assert _warnings_definition_problems(shared), "both-return-corrections must fail"
    good = (
        '  WARNINGS::"`octave_write`: subset of corrections; `octave_validate`: E007 and downgraded validation_errors"'
    )
    assert _warnings_definition_problems(good) == []
    assert _warnings_definition_problems(good.replace("E007", "e007").replace("validation_errors", "x")) == []


# a: anchoring forms are not presented as writable while they fail to tokenize
def _anchor_tokenizes() -> bool:
    """True only if BOTH anchoring forms tokenize; one failing form keeps the guard on."""
    for form in _ANCHOR_FORMS:
        doc = f'===X===\nMETA:\n  TYPE::T\n  VERSION::"1"\n  CONTRACT::{form}\n===END===\n'
        r = asyncio.run(ValidateTool().execute(content=doc, schema="META", profile="STRICT"))
        if any(e.get("code") == "E_TOKENIZE" for e in r.get("errors", [])):
            return False
    return True


def _anchoring_problems(text: str, tokenizes: bool) -> list[str]:
    if tokenizes:
        return []  # the tokenizer accepts the form, so the guard relaxes
    m = re.search(r"^\s*ANCHORING::(.*(?:\n(?!\s*[A-Z_]+::).*)*)", text, flags=re.MULTILINE)
    value = (m.group(1) if m else "").lower()
    if not value:
        return ["no ANCHORING key"]
    if "do not write" not in value and "documented intent" not in value:
        return [
            "ANCHORING presents the forms as usable but they fail to tokenize; mark them 'do not write' or 'documented intent'"
        ]
    return []


def test_P2_8a_a_mastery_anchoring_marked_not_writable_while_untokenizable() -> None:
    problems = _anchoring_problems(_read("mastery"), _anchor_tokenizes())
    assert not problems, f"P2-8a a mastery: {problems}"


def test_P2_8a_a_canary() -> None:
    plain = '    ANCHORING::["`HOLOGRAPHIC<latest@local>` resolves to the local schema."]\n'
    assert _anchoring_problems(plain, tokenizes=False)
    assert _anchoring_problems(plain, tokenizes=True) == []
    marked = '    ANCHORING::["Documented intent, do not write: `HOLOGRAPHIC<latest@local>`."]\n'
    assert _anchoring_problems(marked, tokenizes=False) == []
    assert _anchoring_problems("  OTHER::x\n", tokenizes=False) == ["no ANCHORING key"]


# ---------------------------------------------------------------------------
# P2-8b2 Q2: octave-chatter as PITH applied to message bodies (RED guards)
# ---------------------------------------------------------------------------
# Authority: record OCTAVE-MCP-CHATTER-WIRE-PITH-REWRITE-RULINGS-20261106 (REWRITE_SCOPE), governance PR #547.
# octave-chatter is held to every guard above as the "chatter" file (A1 to A13 as each applies; the per-name
# tables carry its rows). The checks below are chatter-specific: what the rewrite keeps, drops and adds.
#
# KEEP: the register split; provenance on every message; identifiers and hedges verbatim; a small kernel.
# DROP: the operator table as authoring guidance; "operators carry the connectives" and the ASCII wire policy;
#       mythology as "semantic zip" with first-use glosses; the telegraphic "drop stopwords" form; `?` as hedge marker.
# ADD:  the PITH standard items (drift test), TARGET citing PITH (drift test), a pointer to PITH's Handoff shape.
#
# Kernel budget. The hard cap is KERNEL_CAP_CL100K (300, the estate cap, A4 holds every kernel to it). The measured
# kernel of octave-chatter v1.1.0 at c743fb9 is 131 cl100k tokens as extracted (A4's span: the extractor output, the
# text after the section header). The old "138 tokens canonical" claim in the file's META counts the same text plus
# the header line "§5::ANCHOR_KERNEL" (7 tokens), so the two numbers are the same kernel at two spans. The 11 PITH
# standard items alone measure 85 tokens; GREEN's target is about 180, not asserted here (the cap is the gate).
CHATTER_KERNEL_CAP_CL100K = KERNEL_CAP_CL100K
CHATTER_KERNEL_HEADER = "§5::ANCHOR_KERNEL\n"

_MYTHOLOGY_NAMES = re.compile(
    r"\b(hermes|sisyphean|sisyphus|icarian|icarus|promethean|prometheus|athena|zeus|apollo|atlas|hephaestus|"
    r"daedalus|pandora|ariadne|odyssean|odysseus|cassandra|janus|mnemosyne|clio)\b",
    flags=re.IGNORECASE,
)
_MYTHOLOGY_TEACHING = re.compile(r"semantic\s+zip|first\s+use[^\n]*\bgloss", flags=re.IGNORECASE)
_OPERATORS_CARRY = re.compile(r"operators?\s+carr(?:y|ies)\s+(?:the\s+)?connectives?", flags=re.IGNORECASE)
_TELEGRAPHIC = re.compile(r"drop(?:ping)?\s+(?:the\s+)?stop-?words?|quote\s+the\s+phrase", flags=re.IGNORECASE)
_ASCII_POLICY = re.compile(r"\bASCII\b")
_OPERATOR_TABLE_HEADER = re.compile(r"^\s*§\d+[a-z]?::OPERATORS?\b", flags=re.MULTILINE)
# a `?` that is not the end of a word or a bracketed phrase: "? = unverified", "`?` marks", "(?)"
_STANDALONE_QUESTION_MARK = re.compile(r"(?<![\w)\]])\?")
_HEDGE_WORDS = re.compile(r"\b(unverified|doubt|hedges?|uncertain|unsure)\b", flags=re.IGNORECASE)
_STRING_LITERAL = re.compile(r'"(?:[^"\\]|\\.)*"')


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def _mythology_problems(text: str) -> list[str]:
    found = sorted({m.group(1).upper() for m in _MYTHOLOGY_NAMES.finditer(text)})
    problems = [f"mythology names used: {found}"] if found else []
    problems += [f"mythology teaching: {m.group(0)!r}" for m in _MYTHOLOGY_TEACHING.finditer(_collapse(text))]
    return problems


def _hedge_marker_problems(text: str) -> list[str]:
    """`?` used to mark doubt: a standalone `?` token, a `?` on a line with hedge words, or any `?` in a fence."""
    problems: list[str] = []
    for n, line in enumerate(text.split("\n"), start=1):
        if _STANDALONE_QUESTION_MARK.search(line):
            problems.append(f"{n}: standalone ? token: {line.strip()[:80]}")
        elif "?" in line and _HEDGE_WORDS.search(line):
            problems.append(f"{n}: ? on a line about hedges or doubt: {line.strip()[:80]}")
    if re.search(r"question\s+mark", text, flags=re.IGNORECASE):
        problems.append("the text teaches a question mark")
    _, blocks = _scan(text)
    for b in blocks:
        for off, line in enumerate(b["lines"], start=1):
            if "?" in line:
                problems.append(
                    f"{b['start'] + off}: ? inside an example fence (hedges are words): {line.strip()[:70]}"
                )
    return problems


def _rules_lists_unquoted(text: str) -> tuple[int, list[str]]:
    """(number of RULES lists outside fences, elements that are not one whole quoted sentence)."""
    outside, _ = _scan(text)
    joined = "\n".join(t for _, t in outside)
    count = 0
    bad: list[str] = []
    for m in re.finditer(r"^\s*RULES::(?=\[)", joined, flags=re.MULTILINE):
        count += 1
        body = _bracket_body(joined[m.end() :])
        rest = _STRING_LITERAL.sub("", body)
        leftovers = [p.strip() for p in re.split(r"[,\n]", rest) if p.strip()]
        bad += [f"unquoted RULES element: {p[:60]}" for p in leftovers]
    return count, bad


def _register_split_problems(text: str) -> list[str]:
    lines = text.split("\n")
    problems: list[str] = []
    if not any("FORMAL" in ln and "octave_validate" in ln for ln in lines):
        problems.append("no line pairs FORMAL files with octave_validate")
    if not any("WIRE" in ln and "receiving model" in ln for ln in lines):
        problems.append("no line pairs WIRE message bodies with the receiving model")
    if not re.search(r"who\s+validates", text, flags=re.IGNORECASE):
        problems.append("the split is not stated as decided by who validates")
    return problems


def _handoff_pointer_problems(text: str) -> list[str]:
    problems: list[str] = []
    if not any(re.search(r"\bPITH\b", ln) and re.search(r"\bHandoff\b", ln) for ln in text.split("\n")):
        problems.append("no line points at PITH's Handoff shape by name (one line holding both 'PITH' and 'Handoff')")
    if re.search(r"peer\s+message\s+shape", text, flags=re.IGNORECASE):
        problems.append("points at a 'Peer message shape' that pith-spec.md does not carry yet")
    return problems


def _kernel_budget(text: str) -> tuple[int, int]:
    kernel = _odyssean_kernel(text) or ""
    return _tokens(kernel), _tokens(CHATTER_KERNEL_HEADER + kernel)


def test_chatter_P2_8b2_no_mythology_as_instruction_vocabulary() -> None:
    problems = _mythology_problems(_read("chatter"))
    assert not problems, f"P2-8b2 chatter: {problems}"


def test_chatter_P2_8b2_no_operator_table_as_authoring_guidance() -> None:
    """A fenced reading reference is allowed (A3 polices its glyphs); a section teaching the table is not."""
    outside, _ = _scan(_read("chatter"))
    hits = [f"{n}: {t.strip()[:70]}" for n, t in outside if _OPERATOR_TABLE_HEADER.match(t)]
    assert not hits, f"P2-8b2 chatter: operator table kept as a section outside a fence: {hits}"


def test_chatter_P2_8b2_no_operators_carry_connectives_or_ascii_policy() -> None:
    text = _read("chatter")
    problems = [f"teaches {m.group(0)!r}" for m in _OPERATORS_CARRY.finditer(_collapse(text))]
    problems += [f"ASCII wire policy: {m.start()}" for m in _ASCII_POLICY.finditer(text)]
    assert not problems, f"P2-8b2 chatter: {problems[:4]}"


def test_chatter_P2_8b2_no_telegraphic_stopword_teaching() -> None:
    hits = [m.group(0) for m in _TELEGRAPHIC.finditer(_collapse(_read("chatter")))]
    assert not hits, f"P2-8b2 chatter: telegraphic form still taught (PITH Note form replaces it): {hits}"


def test_chatter_P2_8b2_question_mark_is_not_a_hedge_marker() -> None:
    problems = _hedge_marker_problems(_read("chatter"))
    assert not problems, f"P2-8b2 chatter: {len(problems)} places use ? as a hedge marker, first: {problems[:3]}"


def test_chatter_P2_8b2_rules_are_quoted_sentence_lists() -> None:
    count, bad = _rules_lists_unquoted(_read("chatter"))
    assert count >= 1, "P2-8b2 chatter: no RULES::[...] list of quoted sentences (rules as quoted sentences)"
    assert not bad, f"P2-8b2 chatter: {bad[:3]}"


def test_chatter_P2_8b2_register_split_survives() -> None:
    problems = _register_split_problems(_read("chatter"))
    assert not problems, f"P2-8b2 chatter register split: {problems}"


def test_chatter_P2_8b2_points_at_pith_handoff_shape_by_name() -> None:
    problems = _handoff_pointer_problems(_read("chatter"))
    assert not problems, f"P2-8b2 chatter: {problems}"


def test_chatter_P2_8b2_kernel_within_estate_cap() -> None:
    """Both spans (extracted body, and body with its header line) stay at or under the cap. 131 / 138 at c743fb9."""
    body, with_header = _kernel_budget(_read("chatter"))
    assert body > 0, "P2-8b2 chatter: no kernel extracted"
    assert (
        with_header <= CHATTER_KERNEL_CAP_CL100K
    ), f"P2-8b2 chatter: kernel {body} cl100k (body) / {with_header} (with header) > {CHATTER_KERNEL_CAP_CL100K}"


def test_chatter_P2_8b2_kernel_span_is_the_one_the_old_claim_counted() -> None:
    """The body and body-plus-header spans differ by the header line, so a count must name its span."""
    body, with_header = _kernel_budget('§5::ANCHOR_KERNEL\n  TARGET::x\n  GATE::"g"\n===END===\n')
    assert with_header > body


def test_chatter_P2_8b2_canaries_fire_on_synthetic_bad_input() -> None:
    # mythology
    assert _mythology_problems("RISK::HERMES carries it")
    assert _mythology_problems("Mythology = semantic zip, not decoration")
    assert _mythology_problems("First use in a thread carries its gloss")
    assert _mythology_problems("TARGET::plain words only") == []
    # hedge marker
    assert _hedge_marker_problems('NOTE::"// ? = unverified"')
    assert _hedge_marker_problems('NOTE::"a `?` marks doubt"')
    assert _hedge_marker_problems('RISK::"drift repeats?" // unverified')
    assert _hedge_marker_problems('```\nASK::"sure?"\n```\n')
    assert _hedge_marker_problems('GATE::"Could the receiver act on this?"') == []
    assert _hedge_marker_problems('HEDGE::"not verified, may be the runner"') == []
    # teaching phrases
    assert _OPERATORS_CARRY.search(_collapse("operators\n carry connectives"))
    assert _TELEGRAPHIC.search("drop stopwords")
    assert _TELEGRAPHIC.search("quote the phrase")
    assert _ASCII_POLICY.search("ASCII form: ->")
    assert _OPERATOR_TABLE_HEADER.search("§3::OPERATORS\n")
    # RULES lists
    assert _rules_lists_unquoted('§1::A\n  RULES::["one.", "two."]\n') == (1, [])
    assert _rules_lists_unquoted("§1::A\n  RULES::[bare_item]\n")[1]
    assert _rules_lists_unquoted("§1::A\n  OTHER::x\n") == (0, [])
    # register split
    good = 'FORMAL::".oct.md files, parsed by octave_validate"\nWIRE::"message bodies, read by the receiving model"\nS::"decided by who validates"\n'
    assert _register_split_problems(good) == []
    assert len(_register_split_problems("nothing")) == 3
    # handoff pointer
    assert _handoff_pointer_problems('SHAPES::"For asks and replies use the Handoff shape in PITH"') == []
    assert _handoff_pointer_problems("nothing")
    assert _handoff_pointer_problems('X::"PITH Handoff and the Peer message shape"')
