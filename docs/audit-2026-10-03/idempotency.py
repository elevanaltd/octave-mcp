"""Idempotency check: emit(parse(emit(parse(x)))) == emit(parse(x)) for every .oct.md."""
import difflib
import sys
import traceback
from pathlib import Path

ROOT = Path("/home/user/octave-mcp")
sys.path.insert(0, str(ROOT / "src"))

from octave_mcp.core.emitter import emit  # noqa: E402
from octave_mcp.core.parser import parse, parse_with_warnings  # noqa: E402

dirs = [
    ROOT / "src/octave_mcp/resources",
    ROOT / "docs/grammar/test-vectors",
    ROOT / "examples",
]
files = sorted({p for d in dirs for p in d.rglob("*.oct.md")})

stats = {"total": 0, "parse_fail": 0, "emit2_parse_fail": 0, "non_idempotent": 0, "ok": 0, "lossy_vs_source": 0}
failures = []
for f in files:
    stats["total"] += 1
    rel = f.relative_to(ROOT)
    src = f.read_text(encoding="utf-8")
    try:
        doc = parse(src)
    except Exception as e:  # noqa: BLE001
        stats["parse_fail"] += 1
        failures.append((rel, "PARSE_FAIL", f"{type(e).__name__}: {str(e)[:200]}"))
        continue
    try:
        e1 = emit(doc)
    except Exception as e:  # noqa: BLE001
        stats["parse_fail"] += 1
        failures.append((rel, "EMIT1_FAIL", f"{type(e).__name__}: {str(e)[:200]}"))
        continue
    try:
        doc2 = parse(e1)
        e2 = emit(doc2)
    except Exception as e:  # noqa: BLE001
        stats["emit2_parse_fail"] += 1
        failures.append((rel, "REPARSE_FAIL", f"{type(e).__name__}: {str(e)[:300]}"))
        continue
    if e1 != e2:
        stats["non_idempotent"] += 1
        diff = "\n".join(difflib.unified_diff(e1.splitlines(), e2.splitlines(), "emit1", "emit2", lineterm="", n=1))
        failures.append((rel, "NON_IDEMPOTENT", diff[:3000]))
    else:
        stats["ok"] += 1
    if e1 != src:
        stats["lossy_vs_source"] += 1

print("STATS:", stats)
for rel, kind, detail in failures:
    print("=" * 80)
    print(kind, rel)
    print(detail)
