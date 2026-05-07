# ADR-0006 G3: META Envelope Schema Admission for Audit Markers

**Status:** Proposed
**Date:** 2026-05-07
**Parent:** [ADR-0006: Writer/Reader Symmetry](./adr-0006-writer-reader-symmetry.md)
**Scope:** Sprint 2 Task 3 (SR2-T3) blocker — admission policy for `META.NON_CANONICAL_DEGRADED` and `META.DEGRADED_REGIONS`
**Related:** #365 (raw-ingest escape valve), ADR-0006 §SR2-T3

## Problem Statement

ADR-0006 SR2-T3 (`docs/adr/adr-0006-writer-reader-symmetry.md` line 92) specifies that `octave_write --raw=true` MUST stamp two new META fields on raw-ingested documents:

- `META.NON_CANONICAL_DEGRADED::true`
- `META.DEGRADED_REGIONS::[<offsets>]`

The parent ADR is silent on **how** the validator admits these fields. Without an explicit admission policy, the audit-marked `--raw` escape (#365) is unusable in any STRICT-mode pipeline, and admission in LENIENT pipelines is silent (PROD::I5 SCHEMA_SOVEREIGNTY violation: validation status not visible). This sub-spec resolves the gap before SR2-T3 ships.

## Current Behaviour (Verified)

Validator: `src/octave_mcp/core/validator.py`

| Site | Lines | Behaviour |
|---|---|---|
| `Validator.validate(strict=False)` default | L107 | LENIENT is the default mode |
| META validation gate | L131 | `if "META" in self.schema and doc.meta:` — META validation only fires when the active schema declares a `META` block |
| Required-field check | L168–177 | Emits `E003` for missing required fields |
| Unknown-field check | L180–190 | `if strict:` — unknown META keys raise `E007` **only** when (a) `strict=True` AND (b) `schema.META.fields` is non-empty |
| Loss-accounting warnings | L207–232 | `W_META_001` / `W_META_002` fire on `COMPRESSION_TIER`/`LOSS_PROFILE` consistency, **independent** of any schema (see L134–138 comment: "moved outside the META-in-schema guard") |

**Observed behaviour for unknown META keys today:**

- LENIENT mode (default), no META schema: **silent pass-through** (no validation runs at L131).
- LENIENT mode, schema with META: **silent pass-through** (L180 strict gate skipped).
- STRICT mode, no META schema: **silent pass-through** (L131 still gates).
- STRICT mode, schema with META.fields: **`E007` rejection**.

Skill-side confirmation of the known gap pattern: `src/octave_mcp/resources/skills/octave-literacy/SKILL.md` line 101 — *"LOSS_PROFILE is spec-valid but not yet in octave-validator allowed_meta — validator gap, not spec error"*. The same pattern applies to `COMPRESSION_TIER`, `CONTRACT`, `GRAMMAR` (lines 93–96, 99–103). Net: today the validator has **no positive admission mechanism** for spec-valid extension keys; it admits by silence.

META vocabulary capsule: `src/octave_mcp/resources/specs/vocabularies/core/META.oct.md` enumerates only DOCUMENT_METADATA (§1), AUTHORSHIP (§2), CLASSIFICATION (§3). It contains no audit-marker section, so any spec amendment is non-conflicting.

## Options

### (A) Whitelist amendment

Add `NON_CANONICAL_DEGRADED` and `DEGRADED_REGIONS` to a per-schema or global allowed-META list (and to `META.oct.md`).

- **Pros:** minimal diff; explicit.
- **Cons:** every new audit marker (anticipated: `NORMALIZED_FROM`, `ROUNDTRIP_LOSS`, `REPAIR_LEDGER_REF`) re-opens the schema. Accumulative growth. Does not improve the LENIENT silent-pass-through path.

### (B) Schema bump — extension namespace

Introduce META v2 with a structured extension namespace (e.g. `META.AUDIT.*` or top-level `AUDIT` block) admitting forward-compatible audit markers.

- **Pros:** clean namespace separation.
- **Cons:** requires grammar work (nested META keys), tooling updates across `octave_write`/`octave_eject`/`octave_validate`, breaks downstream consumers' flat-key assumptions, and forces a writer-format migration. Disproportionate for the SR2-T3 surface. Fails MIP `BEFORE_ADDING_LAYER` test.

### (C) Validator policy — pattern admission with named warning  ← **RECOMMENDED**

Extend the existing META warning channel (`W_META_*` at validator.py L207–232) with a bounded prefix admission policy:

```
ADMIT_PATTERNS = ("NON_CANONICAL_", "DEGRADED_", "NORMALIZED_", "ROUNDTRIP_")
```

For unknown META keys matching `ADMIT_PATTERNS`:

- **Both modes:** emit informational `W_META_AUDIT` ("audit marker admitted") — surfaces status (PROD::I5).
- **STRICT mode:** do **not** raise `E007` (admit instead of reject).
- **LENIENT mode:** previously silent → now visible via the warning channel.

For unknown META keys **not** matching the patterns: existing behaviour (LENIENT silent / STRICT `E007`).

Defence in depth: also add the two SR2-T3 keys to `META.oct.md` vocabulary capsule (new §4::AUDIT_MARKERS) so spec-side admission is documented even though the load-bearing mechanism is the validator policy.

**Rationale (PROD::I5 + PROD::I4):** The W_META_001/W_META_002 precedent (L207–232 — emits warnings for content-derived consistency without requiring a schema) is the established shape for "spec-valid, status-visible". (C) extends an existing layer rather than adding a new namespace; satisfies MIP `BEFORE_ADDING_LAYER` ("Can existing layers be extended?"). The named warning code makes every audit-marker admission individually grep-able in the validator output (PROD::I4: every transformation logged with stable IDs).

## Recommendation

**Adopt Option (C)** — bounded-prefix admission via the existing `W_META_*` warning channel — with vocabulary-capsule documentation as defence in depth (the (A) component, narrowed to `META.oct.md` only). (B) is rejected as accumulative.

## Acceptance Criteria

The implementation issue is GREEN when:

1. **Validator changes (`src/octave_mcp/core/validator.py`)**
   - New constant `META_AUDIT_ADMIT_PATTERNS = ("NON_CANONICAL_", "DEGRADED_", "NORMALIZED_", "ROUNDTRIP_")` (or equivalent module-private tuple).
   - `_validate_meta` (L163) extended: before the L180 strict-mode E007 path, keys matching `META_AUDIT_ADMIT_PATTERNS` are skipped from E007.
   - New `_check_meta_warnings` branch (or sibling method) emits `W_META_AUDIT` (informational) for any META key matching the patterns, in both LENIENT and STRICT modes, regardless of schema presence (mirrors W_META_001/002 unconditional pattern at L134–138).
2. **Vocabulary capsule (`src/octave_mcp/resources/specs/vocabularies/core/META.oct.md`)**
   - New `§4::AUDIT_MARKERS` section listing `NON_CANONICAL_DEGRADED`, `DEGRADED_REGIONS` with type signatures (`bool` and `list[int]` respectively).
3. **Tests (TDD: RED before GREEN)**
   - `test_meta_audit_marker_admitted_strict`: STRICT-mode validation of a doc with `META.NON_CANONICAL_DEGRADED::true` against a schema that defines META with non-empty fields produces **no** `E007` and **one** `W_META_AUDIT`.
   - `test_meta_audit_marker_admitted_lenient`: LENIENT validation surfaces `W_META_AUDIT` (no longer silent).
   - `test_meta_unknown_non_audit_key_still_rejected_strict`: STRICT mode still emits `E007` for `META.SOMETHING_RANDOM`.
   - `test_meta_audit_marker_no_schema`: doc with no schema, `W_META_AUDIT` still fires (parity with W_META_001 unconditional behaviour).
   - `test_degraded_regions_field`: `META.DEGRADED_REGIONS::[10, 42, 87]` is admitted; type validation deferred to spec-defined types if/when added.
   - HARD_SYMMETRY roundtrip suite (added in SR0-T1) extended to cover a doc with both audit markers stamped.
4. **No regressions:** the existing 2788-test suite remains green (`PROJECT-CONTEXT.oct.md` L38).

## Migration Impact

**No breaking change to existing valid documents.** Evidence:

- Documents written by current `octave_write` do not contain `NON_CANONICAL_*` or `DEGRADED_*` keys (introduced by SR2-T3, not yet shipped).
- LENIENT-mode behaviour for all other keys is unchanged.
- STRICT-mode behaviour for non-matching keys is unchanged (`E007` still raised).
- Documents currently using `COMPRESSION_TIER`/`LOSS_PROFILE`/`CONTRACT`/`GRAMMAR` are unaffected — those keys do not match `META_AUDIT_ADMIT_PATTERNS` and continue under existing rules (the noted "validator gap" remains, but is out of scope for G3 — see literacy SKILL line 101).

The new `W_META_AUDIT` warning is informational and does not fail validation. Downstream consumers reading validator output gain a new warning code; this is additive, not breaking.

## Out of Scope

- Closing the broader `COMPRESSION_TIER`/`LOSS_PROFILE`/`CONTRACT`/`GRAMMAR` admission gap (separate validator-vocabulary alignment work).
- Type-level validation of `DEGRADED_REGIONS` content (offsets are integers; deferrable to a follow-up if needed).
- Any change to writer behaviour — SR2-T3 owns that.

## Citations

- `docs/adr/adr-0006-writer-reader-symmetry.md` line 92 — SR2-T3 specification.
- `src/octave_mcp/core/validator.py` lines 107, 131, 163–190, 207–232 — validator admission and warning machinery.
- `src/octave_mcp/resources/specs/vocabularies/core/META.oct.md` lines 1–26 — current META vocabulary surface.
- `src/octave_mcp/resources/skills/octave-literacy/SKILL.md` line 101 — known validator-gap pattern.
- `.hestai/north-star/000-OCTAVE-MCP-NORTH-STAR-SUMMARY.oct.md` lines 42–46 — PROD::I5 SCHEMA_SOVEREIGNTY definition.
