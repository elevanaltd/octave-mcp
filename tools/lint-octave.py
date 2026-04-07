#!/usr/bin/env python3
"""
Minimal OCTAVE v5.1.0 validator - essential checks
Returns "OCTAVE_INVALID: <reason>" or "OCTAVE_VALID"
Handles .oct.md, .octave, and .oct files
"""

import re
import sys

# GH#347: Support typed envelope identifiers (e.g., PATTERN:MIP_BUILD, SKILL:MY_SKILL)
HEADER_RE = re.compile(r"^===([A-Za-z_][A-Za-z0-9_]*(?::[A-Za-z_][A-Za-z0-9_]*)*)===\s*$")
FOOTER_RE = re.compile(r"^===END===$")
PREFACE_RE = re.compile(r"^\s*(//.*)?$")
QUOTED_RE = re.compile(r'"(?:\\.|[^"\\])*"')


def _strip_quoted_strings(line: str) -> str:
    # Replace quoted content so punctuation inside quotes doesn't affect structural checks.
    return QUOTED_RE.sub('""', line)


def lint_octave(content):
    lines = content.splitlines()
    non_ws = [i for i, line in enumerate(lines) if line.strip()]
    if not non_ws:
        return "OCTAVE_INVALID: Empty document"
    first = non_ws[0]
    last = non_ws[-1]

    # Check document markers (envelope)
    if not HEADER_RE.match(lines[first].strip()) or not FOOTER_RE.match(lines[last].strip()):
        return "OCTAVE_INVALID: Missing document markers (===NAME=== and ===END===)"

    # Preface + META
    i = first + 1
    while i < last and PREFACE_RE.match(lines[i]):
        i += 1
    if i >= last or lines[i].strip() != "META:":
        return "OCTAVE_INVALID: Missing META section (META: after optional preface comments)"
    i += 1
    meta_keys = set()
    while i < last:
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("//"):
            i += 1
            continue
        if not line.startswith("  "):
            break
        m = re.match(r"^\s+([A-Za-z_][A-Za-z0-9_]*)::", line)
        if m:
            meta_keys.add(m.group(1))
        i += 1
    if "TYPE" not in meta_keys:
        return "OCTAVE_INVALID: META.TYPE is required"

    # Check basic syntax
    errors = []
    bracket_balance = 0

    for j, line in enumerate(lines[first + 1 : last], first + 2):
        if not line.strip() or line.strip().startswith("//"):
            continue

        scan = _strip_quoted_strings(line)

        # Check indentation (must be 2-space multiples)
        indent = len(line) - len(line.lstrip())
        if indent % 2 != 0:
            errors.append(f"Line {j}: Invalid indent (must be 2-space multiples)")

        # Check assignment operator
        if "::" in scan and not re.match(r"^\s*[A-Za-z_]\w*::", scan):
            errors.append(f"Line {j}: Invalid assignment syntax")

        # Track list brackets across lines (ignore brackets inside quotes)
        bracket_balance += scan.count("[") - scan.count("]")
        if bracket_balance < 0:
            errors.append(f"Line {j}: Unbalanced brackets")
            bracket_balance = 0

        # Check for trailing comma in lists
        if re.search(r",\s*\]", scan):
            errors.append(f"Line {j}: Trailing comma in list")

    if bracket_balance != 0:
        errors.append("Unbalanced brackets across document")

    return f"OCTAVE_INVALID: {'; '.join(errors)}" if errors else "OCTAVE_VALID"


if __name__ == "__main__":
    content = sys.stdin.read() if not sys.argv[1:] else open(sys.argv[1]).read()
    print(lint_octave(content))
