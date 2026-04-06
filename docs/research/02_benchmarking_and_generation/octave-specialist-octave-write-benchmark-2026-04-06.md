# OCTAVE Specialist Model Comparison — Round 2: octave_write

**Date**: 2026-04-06
**Purpose**: Test models as OCTAVE "secretary" agents using `octave_write` MCP tool (not text emission). Collect friction feedback from each model.

## Model Matrix

| ID | CLI | Role | Underlying Model |
|----|-----|------|-----------------|
| C1 | claude | octave-specialist | Claude Sonnet 4.6 |
| G1 | gemini | octave-specialist | Gemini 3.1 Pro Preview |
| X1 | codex | octave-specialist | Codex (o4-mini) |
| GA | goose | octave-specialist-a | minimax/minimax-m2.7 |
| GB | goose | octave-specialist-b | qwen/qwen3.6-plus:free (NEW) |
| GC | goose | octave-specialist-c | google/gemini-3.1-pro-preview via OpenRouter (NEW) |

## Results Summary

### File Creation Success

| Model | T1 File? | T2 File? | T3 File? | Success Rate |
|-------|----------|----------|----------|-------------|
| C1 | YES (1587b) | YES (1266b) | YES (629b) | **3/3 (100%)** |
| G1 | YES (676b) | YES (163b) | YES (567b) | **3/3 (100%)** |
| X1 | YES (920b) | YES (1111b) | TIMEOUT | **2/3 (67%)** |
| GA | YES (1797b) | STUCK | YES (534b) | **2/3 (67%)** |
| GB | NO RESPONSE | RATE LIMITED | RATE LIMITED | **0/3 (0%)** |
| GC | YES (268b)* | YES (105b)* | PLANNING LOOP | **2/3 (67%)*** |

*GC files are technically written but nearly empty — values stripped during canonicalization.

### Content Quality Assessment

| Model | T1 Quality | T2 Quality | T3 Quality | Overall |
|-------|-----------|-----------|-----------|---------|
| C1 | Excellent (4 endpoints, P50/P95/P99) | Excellent (full pipeline, environments, notifications) | Excellent (cause chain with →, complete semantics) | **A** |
| G1 | Good (compact, flow lists) | Poor (META block only, 7 lines) | Partial (IMMEDIATE_ACTION and LESSONS_LEARNED empty — data loss) | **C+** |
| X1 | Good (--- separator, clean) | Excellent (read schema first, rich config) | N/A (timeout) | **B** |
| GA | Excellent (5 §sections, infrastructure, alerts) | N/A (stuck) | Poor (affected_users="≈12" should be 12000, timestamps broken) | **C** |
| GB | N/A | N/A | N/A | **F** |
| GC | Failed (all values stripped, only keys remain) | Failed (nearly empty, only keys) | N/A (never called tool) | **F** |

### Self-Correction Ability

| Model | T1 Retries | T2 Retries | T3 Retries | Pattern |
|-------|-----------|-----------|-----------|---------|
| C1 | 0 | 1 (= tokenization) | 0 | **Learns from errors, fixes quickly** |
| G1 | 0 | 0 | 0 | **No retries but silent data loss** |
| X1 | 0 | 0 | N/A | **Reads schema first, avoids errors** |
| GA | 1 (YAML -) | stuck | 7 | **Persistent but slow error recovery** |
| GB | N/A | N/A | N/A | **Cannot produce output** |
| GC | Unknown | 2 (- and :) | N/A | **Self-corrects on syntax but loses content** |

### Latency

| Model | T1 | T2 | T3 | Average |
|-------|-----|-----|-----|---------|
| C1 | 100s | 107s | 88s | **~98s** |
| G1 | 168s* | 31s | 27s | **~75s** |
| X1 | 83s | 54s | 900s+ (timeout) | **~345s** |
| GA | 80s | 36s | 123s | **~80s** |
| GB | N/A | 11s | N/A | **N/A** |
| GC | 97s | 74s | 74s | **~82s** |

*G1 T1 included rate-limit retries.

## Friction Report — Consolidated from All Agents

### Critical Issues (data integrity)

| Issue | Reported By | Severity | Detail |
|-------|-----------|----------|--------|
| **Silent data loss with numeric keys** | G1 | CRITICAL | Keys like `1::"value"`, `2::"value"` silently stripped — no error, no warning |
| **Value stripping in canonical output** | GC | CRITICAL | When Gemini via OpenRouter/Goose calls octave_write, only keys survive — all values lost |
| **Timestamp fragmentation** | GA | HIGH | `"2026-03-15T14:32Z"` becomes `"2026 -03 -15 14"` with colons split |
| **Number+identifier coalescing** | C1 | MEDIUM | `12000_USERS` becomes `"12000 _USERS"` (space before underscore) |

### Syntax Friction (learnable)

| Issue | Reported By | Frequency | Detail |
|-------|-----------|-----------|--------|
| **YAML `-` bullet rejection** | GA, GC | 3/6 models hit this | `E_TOKENIZE: Unexpected character: '-'` — no hint about `[list]` syntax |
| **`=` character in values** | C1 (twice) | 2 tests | `max_unavailable=0` and `branch=main` — `=` not valid in OCTAVE |
| **Single `:` vs `::` confusion** | GC, GA | 2/6 models | **E001 error message praised by GC** as "excellent and self-healing" |
| **Markdown `#` header rejection** | GA | 1 model | `#` not valid; must use `§` prefix |

### UX / Tool Design Friction

| Suggestion | Reported By | Impact |
|-----------|-----------|--------|
| Add hint when `validation_status: UNVALIDATED` — point to `schema` parameter | C1 | HIGH — first-time users don't know why validation didn't run |
| Rename `corrections_only` to `dry_run` | C1 | MEDIUM — more intuitive for CLI users |
| State `lenient` default explicitly | C1 | MEDIUM — unclear if lenient parsing is always-on |
| Provide schema catalog listing | X1, GA | MEDIUM — agents don't know what schemas exist |
| Distinguish syntax validation from schema/domain validation | X1 | MEDIUM — `schema:"META"` validates META block only, not document semantics |
| Add `#` → `§` auto-conversion hint | GA | LOW — uncommon outside goose models |
| Better diff for new files (show "New file" not "0 → N bytes") | GA | LOW |
| **Warn (don't silently drop) invalid keys** | G1 | **CRITICAL** — silent data loss violates I4 (Transform Auditability) |

## Overall Rankings

| Rank | Model | Score | T1 | T2 | T3 | Recommendation |
|------|-------|-------|----|----|-----|----------------|
| 1 | **C1** (Claude Sonnet) | **95** | 100 | 90 | 95 | **RECOMMENDED** — Highest quality, self-corrects, rich content |
| 2 | **X1** (Codex o4-mini) | **60** | 85 | 95 | 0 | Runner-up — excellent when it works, but T3 timeout |
| 3 | **G1** (Gemini 3.1 Pro) | **57** | 80 | 50 | 40 | Consistent but minimal output, data loss risk |
| 4 | **GA** (minimax m2.7) | **40** | 90 | 0 | 30 | High ceiling but unreliable — 7 retries on T3 |
| 5 | **GC** (Gemini via Goose) | **12** | 20 | 15 | 0 | Values stripped, planning loops — not viable |
| 6 | **GB** (qwen3.6-plus:free) | **0** | 0 | 0 | 0 | Zero output across all tests — disqualified |

## Comparison with Round 1 (text emission)

| Model | Round 1 (text) | Round 2 (octave_write) | Delta | Explanation |
|-------|---------------|----------------------|-------|-------------|
| C1 | 80.0 | **95** | +15 | Tool use eliminates backtick/prose issues; self-correction works |
| G1 | 80.7 | **57** | -24 | Data loss via tool is worse than valid text emission |
| X1 | 70.0 | **60** | -10 | Timeout on T3 dragged score down |
| GA | 68.0 | **40** | -28 | YAML contamination blocks tool use more than text emission |
| GB | 26.7 | **0** | -27 | New model (qwen) even worse than mimo-v2-pro |
| GC | 46.7 | **12** | -35 | New model (gemini via goose) loses values through tool |

**Key insight**: Using `octave_write` is **harder** than text emission for most models. The tool's strict parser exposes syntax errors that lenient text validation would accept. Only C1 improved — because the tool catches and reports errors that C1 can self-correct.

## Architecture Recommendation

**Primary secretary: C1 (Claude Sonnet)** — only model that consistently produces complete, valid documents through octave_write with self-correction on errors.

**Pipeline design**:
1. C1 writes via `octave_write` with `schema` parameter where applicable
2. If `octave_write` returns an error, C1 self-corrects (observed to fix within 1 retry)
3. No fallback model is reliable enough — escalate to human review on C1 failure

**Immediate octave_write improvements** (from friction data):
1. **CRITICAL**: Warn on silently dropped keys/values — violates I4 (Transform Auditability)
2. **HIGH**: Add hint for `validation_status: UNVALIDATED` → suggest `schema` parameter
3. **MEDIUM**: Improve `-` rejection error message — suggest `[list]` syntax
4. **MEDIUM**: Expose schema catalog via tool description or hint

## Output Files

All written files are in `docs/research/02_benchmarking_and_generation/octave-write-test-outputs/`:
- `t1-c1.oct.md` through `t3-ga.oct.md` (14 files total)
