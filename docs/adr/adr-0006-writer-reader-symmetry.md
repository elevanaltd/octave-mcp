# ADR-0006: Writer/Reader Symmetry — Killing the `octave_validate`/`octave_write` Asymmetry

**Status:** Proposed
**Date:** 2026-05-07
**Supersedes:** None
**Related:** #365, #369, #371, #372, #373, #376, #377; ADR-0004 (tool consolidation)

## Context

`octave_validate` returns `valid: true` for content that `octave_write` then refuses to re-parse, mangles, or canonicalises destructively. This violates North Star Immutables I1 (canon must be idempotent and bijective on semantic space), I3 (mirror constraint), and I4 (transform auditability).

Reproduction (verified 2026-05-07 against `DECISIONS-example.oct.md`, ~140KB, 2115 lines, declares `COMPRESSION_TIER::AGGRESSIVE`):

```
mcp__octave__octave_validate(schema=META) → valid: true, errors: 0, warnings: 0
mcp__octave__octave_write(target_path=<copy>, dry_run=true)
  → status: success
  → corrections: [3× W002 ASCII→Unicode with EMPTY `after`,
                  targeting long-underscored identifiers at lines 559, 818, 875]
  → diff_unified: "" (claims no diff while logging destructive corrections)
```

The repair-log + diff inconsistency is the proximate bug. The deeper cause is that `octave_validate` and `octave_write` execute different normalisation paths: `validate` parses + reports, `write` parses + always-applies `TIER_NORMALIZATION` repairs (`core/repair.py`) + canonical re-emit (`core/emitter.py`). Divergence creeps in at the always-applied repair layer.

Prior empirical research (already in `docs/research/`) confirms that the *format* is sound:
- Mythological compression validated at 100% comprehension across 4 models
- Operators `→ ⊕ ⇌ ∧ □ ◇ ⊥` validated at 100%; `⊙` failed on ChatGPT 5.2 (guardrail)
- CONSERVATIVE-MYTH tier achieves 11/11 fact retention at −15% tokens vs prose
- JIT Literacy Injection: ~200-token primer makes any LLM produce valid OCTAVE

The defect is tooling, not format. The format mantra — *"Keys are strict, values are tier-tunable, and the tier is declared"* — is upheld by the fix proposed here, not changed.

## Decision

Establish **HARD_SYMMETRY** as a release invariant, enforced by property-based regression tests, and deliver it through a four-sprint engineering programme. The full investigation (debates, prior-art review, retracted Phase 1.5) is preserved in `.hestai-state/research/OCTAVE-OPTIMIZATION-ROADMAP.md` for reference; this ADR is the buildable subset.

### The invariant

```
∀ bytes b: octave_validate(b).valid == true ⇒ octave_write(target=tmp, content=b, dry_run=true).status == "success"
                                            ∧ no corrections with empty `after` field
                                            ∧ diff_unified accurately reflects corrections
```

Violation of any conjunct is a release blocker.

### Four sprints

#### Sprint 0 — Make the asymmetry observable (≤1 week, single PR)

**SR0-T1.** Property-based round-trip test suite. New `tests/test_roundtrip_symmetry.py`:
- Walk every `.oct.md` fixture in `tests/fixtures/`, `examples/`, and any committed governance docs.
- For each: assert the HARD_SYMMETRY invariant. Failures become tracked GH issues automatically (via test output).
- Hypothesis fuzzing layer: generate documents from the EBNF grammar in `docs/grammar/octave-v1.0-grammar.ebnf`, assert symmetry.

**SR0-T2.** W002 destructive-correction guard in `core/lexer.py`. The W002 emit path currently produces corrections with empty `after` when the ASCII→Unicode regex matches but does not extract a Unicode operator. Patch:

```python
# core/lexer.py — W002 emit (~5 lines)
if not after_value:
    # Destructive correction: pass-through unchanged. Log internally as W002_SUPPRESSED.
    self._log_internal("W002_SUPPRESSED", before=before_value, line=line, col=col)
    continue
```

Add `tests/test_w002_destructive_guard.py` with the line 559 / 818 / 875 fixtures from `DECISIONS-example.oct.md` extracted to minimal repros.

**Exit criteria:** roundtrip suite is green or every failure has a fixture-backed open issue. W002 never produces empty `after` again.

#### Sprint 1 — Single grammar core (lite) + corruption hard-fail (1.5–2 weeks)

**SR1-T1.** Extract grammar entry point. New `core/grammar.py` exposing:
```python
def parse(source: bytes, *, lenient: bool = False) -> CST: ...
```
Both `octave_validate` and `octave_write` call this single entry. The existing parser/lexer logic moves behind it but is not yet rewritten. This is a routing change, not a rewrite.

**SR1-T2.** Hard-fail on `W_DUPLICATE_TARGET` (closes #372). Currently silent merge → corruption. Change classification to `E_DUPLICATE_TARGET` fatal in the parser. Migration: file an issue per pre-existing corruption surfaced by the change. Provide `octave_write --resolve-duplicates=last_wins|first_wins|interactive` as escape hatch.

**SR1-T3.** Path-resolver disambiguation (closes #369). `Block.child` paths like `NAV.OPERATIONAL_CONVENTIONS` currently silently corrupt when ambiguous. Change resolver to fail with `E_AMBIGUOUS_PATH` listing all matching resolutions. Force callers to use unambiguous form (e.g. `§N.NAV.OPERATIONAL_CONVENTIONS` or `NAV::OPERATIONAL_CONVENTIONS`).

**SR1-T4.** Make in-place normalize a no-op-by-default. Calling `octave_write(target_path=X)` with no content/changes today runs full canonicalisation. Change to parse-validate-no-emit unless explicit `canonicalize=true` flag is passed. Existing callers that depended on side-effects file an issue.

**Exit criteria:** roundtrip suite green across full fixture corpus + governance docs. Silent-corruption error codes never reach disk.

#### Sprint 2 — Default preserve mode + span coverage audit (1.5–2 weeks)

**SR2-T1.** Flip `format_style` default to `"preserve"` (closes #376 fully). The existing Strategy-C `preserve` mode (no-op when new-content parse-equals baseline) becomes the default. `expanded` and `compact` become explicit opt-ins. Document the change as a v2.0.0 breaking change for consumers depending on canonical re-emit.

**SR2-T2.** AST node span coverage audit. Catalogue every node type in `core/ast_nodes.py`; identify which carry `(start_offset, end_offset)` and which need them for Strategy-A preserve. Output: spreadsheet + Phase-2-proper task list. Currently only `ListValue` and `HolographicValue` carry spans (per #377).

**SR2-T3.** RAW_INGEST escape valve (closes #365, demoted scope). `octave_write --raw=true` writes bytes verbatim, stamps `META.NON_CANONICAL_DEGRADED::true` and `META.DEGRADED_REGIONS::[<offsets>]`, and blocks AST-traversal mutations on degraded regions until `octave_write --resolve` is run. Demoted from "primary escape" because Sprints 0 + 1 should remove most of the friction agents bypass for; this stays as audit-marked tail-case.

**Exit criteria:** single-key edits on `DECISIONS-example.oct.md` produce diffs ≤2% of file size (Strategy C cap; Strategy A delivers ≤0.5% in Phase 2 proper).

#### Sprint 3 — Cursor-backed CST + pipeline bifurcation (4–6 weeks)

**SR3-T1.** Strategy-A preserve (closes #377). Extend every AST node with `(start_offset, end_offset, source_hash)`. Implement dirty-bit propagation. Render path: `if not node.dirty: emit_bytes(source[start:end])`. Refactor changes-mode (#373) to operate over the cursored CST.

**SR3-T2.** Pipeline bifurcation. Split `core/repair.py` into:
- `core/repair_syntactic.py` — bracket balancing, indent, envelope. Always runs. Idempotent.
- `core/repair_schema.py` — W002 ASCII→Unicode, key-ordering, dedup. **Never runs on `octave_write`.** Exposed as separate `octave_fmt` CLI/MCP tool.

**Exit criteria:** single-key edit diff footprint ≤0.5% on 140KB doc. No W002-class correction ever appears in a write-mode response. `octave_fmt` is the only path that produces canonical-style diffs.

## Consequences

### Positive
- HARD_SYMMETRY invariant enforced in CI; structural elimination of the "valid but unwriteable" defect class.
- Closes 7 open issues (#365, #369, #371, #372, #373, #376, #377).
- Format itself untouched — existing CONSERVATIVE-MYTH / AGGRESSIVE / ULTRA tier system, mythology compression, and operator vocabulary all preserved.
- Agents stop bypassing `octave_write` because the writer stops being hostile (#365 root cause addressed structurally, not patched).

### Negative
- Sprint 2's flip of `format_style` default is a v2.0.0 breaking change for consumers depending on canonical re-emit. Mitigation: `canonicalize=true` opt-in flag + migration note + advance warning in v1.5 release.
- Sprint 1's hard-fail on duplicate-target may surface pre-existing corruption in shipped repos (covered by #372). Mitigation: `--resolve-duplicates` escape hatch + migration sweep tooling.
- Sprint 3 is the only sprint that touches AST node shape; every consumer (validator, projector, hydrator, holographic, sealer) needs migration. Plan as a single coordinated PR family, not staged.

### Out of scope
- Format changes (no "OCTAVE-Fluid", no YAML pipe, no value grammar redesign). The retracted Phase 1.5 from the research roadmap is explicitly not adopted; existing tier system already implements "values tunable per tier."
- Empirical work — tokenizer benchmark, comprehension test, needle-in-haystack — runs on a separate research track. Findings may inform agent prompt calibration but do not block this engineering programme.
- Mirror feedback loop (research-roadmap Phase 5) — separate research track, depends on Sprint 3 outputs.

## Implementation Plan for HO

HO can decompose this ADR into the following work items immediately:

| Sprint | Issue | Deliverable | Effort |
|--------|-------|-------------|--------|
| 0 | (new) Roundtrip symmetry suite | `tests/test_roundtrip_symmetry.py` + fixture corpus | 2–3 days |
| 0 | (new) W002 destructive guard | `core/lexer.py` patch + regression test | 1 day |
| 1 | (new) Single grammar core extraction | `core/grammar.py` + routing change | 3–4 days |
| 1 | #372 | Hard-fail duplicate-target + `--resolve-duplicates` | 2–3 days |
| 1 | #369 | Path-resolver disambiguation | 2 days |
| 1 | (new) In-place normalize no-op default | `octave_write` behaviour change + flag | 1 day |
| 2 | #376 | `format_style="preserve"` default | 2 days |
| 2 | (new) AST node span audit | Spreadsheet + Phase-2-proper task list | 1 day |
| 2 | #365 | `--raw=true` audit-marked escape | 3 days |
| 3 | #377 | Strategy-A cursor-CST + dirty tracking | 3 weeks |
| 3 | #371 #373 | Pipeline bifurcation + cursored changes-mode | 1–2 weeks |

Sprints 0 and 1 are HO-ready today and unblock everything downstream. Sprint 2 depends on Sprint 1 landing. Sprint 3 depends on Sprint 2's span audit.

## References

- Full research roadmap (gitignored, narrative): `.hestai-state/research/OCTAVE-OPTIMIZATION-ROADMAP.md`
- Compression-fidelity round-trip study: `docs/research/compression-fidelity-round-trip-study.md`
- Cross-model operator validation: `docs/research/cross-model-operator-validation-study.md`
- Subagent compression behavioural study: `docs/research/subagent-compression-study.md`
- JIT Literacy Injection debate: `docs/research/jit-literacy-injection-debate.oct.md`
- Three Wind/Wall/Door debates (synthesis input):
  - `2026-05-07-octave-writerreader-asymmetry--01kr2171` (standard)
  - `2026-05-07-octave-writerreader-asymmetry--01kr21ew` (premium)
  - `2026-05-07-octave-writerreader-asymmetry--01kr21zn` (ultra)
