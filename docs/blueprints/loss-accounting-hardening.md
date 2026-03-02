# Blueprint: Loss Accounting Hardening

**Phase**: B2 (TDD Implementation)
**Branch**: From `anchor-technical-architect`
**Author**: technical-architect
**Status**: APPROVED FOR IMPLEMENTATION

## Problem Statement

OCTAVE's core identity claim is "loss accounting system for LLM communication." Two implementation gaps undermine this claim:

1. **LiteralZoneRepairLog is hollow** — The SHA-256 pre/post hash infrastructure exists in `repair_log.py` (lines 72-125) but is never populated. All three instantiation sites (`write.py:1362`, `validate.py:467`, `eject.py:316`) create `LiteralZoneRepairLog(entries=[])`.

2. **Compression tier metadata is unvalidated** — `COMPRESSION_TIER` and `LOSS_PROFILE` are parsed as opaque data. A document can declare `COMPRESSION_TIER::LOSSLESS` with `LOSS_PROFILE::"none"` and no validation catches the inconsistency. The spec itself admits this: `CRITICAL_GAPS::[compression_rules_enforcement, tier_specific_logic, loss_profile_tracking]`.

## Scope (MIP-filtered)

### In Scope (Essential)

**Task 1: Populate LiteralZoneRepairLog with SHA-256 receipts**

- When literal zones exist in a document, compute SHA-256 of each zone's `content` field
- Since literal zones are guaranteed untouched (D3: zero processing), `pre_hash == post_hash`
- Populate `RepairLogEntry` with: zone_key, line, action="preserved", pre_hash, post_hash, timestamp, source_stage

**Task 2: Add LOSS_PROFILE consistency warning**

- When `COMPRESSION_TIER` is declared in META but `LOSS_PROFILE` is absent, emit a validation warning
- When `LOSS_PROFILE` is `"none"` and `COMPRESSION_TIER` is not `LOSSLESS`, emit a validation warning
- This is a WARNING (W-code), not an ERROR — it flags inconsistency without blocking

### Out of Scope (Accumulative)

- Full compression tier enforcement (server doesn't control what LLMs write)
- Cross-document loss tracking
- Content-level semantic loss detection

## Implementation Details

### Task 1: LiteralZoneRepairLog Population

**Files to modify:**
- `src/octave_mcp/mcp/write.py` (~line 1342-1362)
- `src/octave_mcp/mcp/validate.py` (~line 467)
- `src/octave_mcp/mcp/eject.py` (~line 316)

**Approach:**

The `_count_literal_zones()` function (validator.py:556) already walks the AST and returns per-zone metadata (key, info_tag, line). Extend the zone-reporting flow:

```python
import hashlib
from datetime import datetime, timezone

def _build_literal_zone_repair_log(
    zones: list[dict],
    doc: Document,
    source_stage: str,
) -> LiteralZoneRepairLog:
    """Build repair log with SHA-256 receipts for each literal zone.

    Since literal zones are exempt from normalization (D3: zero processing),
    pre_hash always equals post_hash, proving content preservation.
    """
    entries = []
    for zone_meta in zones:
        # Find the actual LiteralZoneValue content from the AST
        content = _get_literal_zone_content(doc, zone_meta["key"], zone_meta["line"])
        if content is not None:
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            entries.append(RepairLogEntry(
                zone_key=zone_meta["key"],
                line=zone_meta["line"],
                action="preserved",
                pre_hash=content_hash,
                post_hash=content_hash,  # D3: zero processing guarantees equality
                timestamp=datetime.now(timezone.utc).isoformat(),
                source_stage=source_stage,
            ))
    return LiteralZoneRepairLog(entries=entries)
```

The helper `_get_literal_zone_content(doc, key, line)` walks the document AST sections to find the `LiteralZoneValue` matching the given key and line, returning its `.content` string.

**Integration points:**
- `write.py:1362` → `_build_literal_zone_repair_log(zones, doc, "octave_write")`
- `validate.py:467` → `_build_literal_zone_repair_log(zones, doc, "octave_validate")`
- `eject.py:316` → `_build_literal_zone_repair_log(zones, doc, "octave_eject")`

Extract the shared helper to `src/octave_mcp/core/literal_zone_audit.py` or add it alongside `_count_literal_zones` in `validator.py`.

### Task 2: LOSS_PROFILE Consistency Warning

**Files to modify:**
- `src/octave_mcp/core/validator.py` (~line 146, inside `_validate_meta()`)

**New warning codes:**
- `W_META_001`: "COMPRESSION_TIER declared but LOSS_PROFILE absent — loss accounting incomplete"
- `W_META_002`: "LOSS_PROFILE is 'none' but COMPRESSION_TIER is not LOSSLESS — verify accuracy"

**Approach:**

Add to `_validate_meta()` after existing field checks:

```python
# Loss accounting consistency (I4)
compression_tier = meta.get("COMPRESSION_TIER")
loss_profile = meta.get("LOSS_PROFILE")

if compression_tier and not loss_profile:
    self.warnings.append({
        "code": "W_META_001",
        "path": "META.LOSS_PROFILE",
        "message": "COMPRESSION_TIER declared but LOSS_PROFILE absent",
    })

if (loss_profile and str(loss_profile).strip('"').lower() == "none"
        and compression_tier
        and str(compression_tier).strip('"').upper() != "LOSSLESS"):
    self.warnings.append({
        "code": "W_META_002",
        "path": "META.LOSS_PROFILE",
        "message": f"LOSS_PROFILE is 'none' but COMPRESSION_TIER is {compression_tier}",
    })
```

This does NOT require a schema — it fires on any document with these META fields, regardless of whether a schema is loaded. This is I4 self-enforcement.

## Test Plan (TDD: RED first)

### Task 1 Tests
- `test_literal_zone_repair_log_populated`: Write doc with literal zone → call octave_write → assert `literal_zone_repair_log` entries are non-empty
- `test_literal_zone_hash_matches`: Assert `pre_hash == post_hash` for preserved zone
- `test_literal_zone_hash_is_sha256`: Assert hash is 64-char hex string
- `test_multiple_zones_all_logged`: Doc with 3 literal zones → assert 3 entries
- `test_no_zones_empty_log`: Doc without literal zones → assert no log key in response
- `test_zone_key_and_line_correct`: Assert zone_key and line match the source document

### Task 2 Tests
- `test_w_meta_001_tier_without_profile`: META has COMPRESSION_TIER but no LOSS_PROFILE → warning
- `test_w_meta_002_none_profile_non_lossless`: META has COMPRESSION_TIER::CONSERVATIVE + LOSS_PROFILE::"none" → warning
- `test_no_warning_lossless_with_none`: META has COMPRESSION_TIER::LOSSLESS + LOSS_PROFILE::"none" → no warning
- `test_no_warning_tier_with_profile`: META has both COMPRESSION_TIER and non-none LOSS_PROFILE → no warning
- `test_no_warning_no_tier`: No COMPRESSION_TIER in META → no warning at all

## Quality Gates

- [ ] All tests written RED first, then made GREEN
- [ ] `ruff check` passes
- [ ] `black --check` passes
- [ ] `mypy` passes
- [ ] `pytest` passes (full suite)
- [ ] No regression in existing literal zone tests

## Risk Assessment

- **Low risk**: Task 1 adds data to an existing empty structure — no API shape change
- **Low risk**: Task 2 adds warnings only — non-blocking, won't break existing workflows
- **Dependency**: Both tasks are independent and can be implemented in either order
