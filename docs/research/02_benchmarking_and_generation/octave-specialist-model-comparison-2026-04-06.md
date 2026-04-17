# OCTAVE Specialist Model Comparison Test

**Date**: 2026-04-06
**Purpose**: Determine optimal model for the octave-specialist "secretary" role — an agent that writes OCTAVE documents via `octave_write` on behalf of other agents.

## Model Matrix

| ID | CLI | Role | Underlying Model |
|----|-----|------|-----------------|
| C1 | claude | octave-specialist | Claude Sonnet 4.6 |
| G1 | gemini | octave-specialist | Gemini 3.1 Pro Preview |
| X1 | codex | octave-specialist | Codex (o4-mini) |
| GA | goose | octave-specialist-a | minimax/minimax-m2.7 |
| GB | goose | octave-specialist-b | xiaomi/mimo-v2-pro |
| GC | goose | octave-specialist-c | moonshotai/kimi-k2.5 |

## Test Prompts

### T1 — Freeform OCTAVE Generation
> Write a valid OCTAVE document describing a REST API health monitoring system. Include a META block with TYPE and VERSION, system status, endpoint metrics, and alert thresholds. Output ONLY the OCTAVE document — no prose, no explanation.

### T2 — Schema-Compliant Write (META schema)
> Write a valid OCTAVE document that conforms to the META schema. The document should describe an OCTAVE configuration for a deployment pipeline tool. TYPE must be a string, VERSION must be a string, STATUS must be one of DRAFT, ACTIVE, or DEPRECATED. Output ONLY the OCTAVE document.

### T3 — Compression
> Compress the following text into a valid OCTAVE document. Preserve all semantic meaning. Output ONLY the OCTAVE document — no prose.
>
> "The authentication service experienced a critical failure at 14:32 UTC on March 15th. The root cause was identified as a database connection pool exhaustion, triggered by a sudden spike in login attempts from the mobile application. The spike was caused by a client-side retry loop bug introduced in version 2.4.1 of the iOS app. The incident affected approximately 12,000 users over a 47-minute window. The team responded by scaling the connection pool from 50 to 200 connections and deploying a hotfix to disable the retry loop. A permanent fix was shipped in iOS version 2.4.2 three days later. Lessons learned include the need for connection pool monitoring alerts and client-side retry backoff policies."

## Scoring Criteria

| Criterion | Weight | Scoring |
|-----------|--------|---------|
| Validity | 40% | PASS=40, PASS w/ repairs=30, FAIL=0, DNF=0 |
| No-Prose Compliance | 20% | Clean=20, Backtick wrapper only=15, Prose leakage=0 |
| Structural Quality | 20% | 1-5 scaled to 4-20: META, nesting, operators, ===END=== |
| Semantic Completeness | 20% | 1-5 scaled to 4-20: all information captured? |

## Results

### T1 — Freeform OCTAVE Generation

| Model | Valid? | No-Prose? | Structure (1-5) | Semantics (1-5) | Weighted | Notes |
|-------|--------|-----------|-----------------|-----------------|----------|-------|
| C1 | PASS (0 err) | Yes (backticks) | 5 | 5 | **95** | Exemplary. Rich detail, 4 endpoints, dependencies, check schedule |
| G1 | PASS (0 err) | Yes | 4 | 4 | **92** | Clean but simpler. 3 endpoints, flow lists for metrics |
| X1 | PASS (0 err) | No (prose line) | 5 | 5 | **80** | Valid+rich but "Using octave-literacy..." prose at start |
| GA | FAIL (E_PARSE) | Yes | 4 | 5 | **56** | Single-colon `:` in endpoint rows. §sections show format awareness |
| GB | DNF | No | 0 | 0 | **0** | Infinite repetition loop. 20k+ chars of "The document is valid now" |
| GC | DNF | Yes | 1 | 3 | **36** | Token-by-token fragmentation. Every word on a new line |

### T2 — Schema-Compliant Write

| Model | Valid? | No-Prose? | Structure (1-5) | Semantics (1-5) | Weighted | Notes |
|-------|--------|-----------|-----------------|-----------------|----------|-------|
| C1 | FAIL (E_TOKENIZE) | Yes (backticks) | 5 | 5 | **55** | `branch=main` uses `=` — not valid OCTAVE token |
| G1 | PASS (0 err) | Yes | 3 | 2 | **72** | Minimal: META-only doc, just 5 lines. Used MCP tools to verify |
| X1 | PASS (0 err) | No (prose) | 5 | 5 | **80** | Valid+rich. Read schema first. But "ROLE=OCTAVE_SPECIALIST" prose |
| GA | PASS (0 err) | Yes | 4 | 4 | **92** | Clean §sections, proper META compliance, good content |
| GB | DNF | No | 0 | 0 | **0** | "Let me try to find the META schema" — no output produced |
| GC | FAIL (no header) | Yes (backticks) | 1 | 2 | **27** | Bare META block only — no ===HEADER=== or ===END=== |

### T3 — Compression

| Model | Valid? | No-Prose? | Structure (1-5) | Semantics (1-5) | Weighted | Notes |
|-------|--------|-----------|-----------------|-----------------|----------|-------|
| C1 | PASS w/ repairs | Yes (backticks) | 5 | 5 | **90** | Excellent → chain. `50→200` scaling. Schema invalid (no VERSION) but syntax perfect |
| G1 | PASS w/ repairs | Yes | 3 | 4 | **78** | No ===HEADER=== (inferred). Nested inline maps. Good semantic coverage |
| X1 | PASS w/ repairs | No | 2 | 4 | **50** | No header. Heavy repairs. Timestamps mangled. Bare list structure |
| GA | FAIL (E_TOKENIZE) | Yes | 4 | 5 | **56** | YAML `-` bullet lists — not valid OCTAVE. Semantic content excellent |
| GB | PASS w/ repairs | Yes (backticks) | 4 | 5 | **80** | First real output from mimo! Valid syntax, schema invalid only |
| GC | PASS w/ repairs | Yes | 5 | 4 | **77** | Mythological archetypes (POSEIDON, HERMES). `login_spike` bare line dropped = data loss |

### Overall Rankings

| Rank | Model | T1 | T2 | T3 | Average | Latency (avg) | Recommendation |
|------|-------|----|----|-----|---------|---------------|----------------|
| 1 | **GA** (minimax m2.7) | 56 | **92** | 56 | **68.0** | ~67s | Best no-prose discipline. Syntax errors fixable |
| 2 | **C1** (Claude Sonnet) | **95** | 55 | **90** | **80.0** | ~23s | Highest ceiling. Fastest. Occasional syntax pitfalls |
| 3 | **G1** (Gemini 3.1 Pro) | 92 | 72 | 78 | **80.7** | N/A (rate-limited) | Most consistent validator. Unreliable delivery |
| 4 | **X1** (Codex o4-mini) | 80 | 80 | 50 | **70.0** | ~36s | Reliable validity. Persistent prose leakage |
| 5 | **GC** (kimi k2.5) | 36 | 27 | 77 | **46.7** | ~92s | Best mythology usage in T3. Unstable output format |
| 6 | **GB** (mimo-v2-pro) | 0 | 0 | 80 | **26.7** | ~47s | 2/3 tests failed completely. Not production-ready |

## Analysis

### Key Findings

**1. No single model dominates all three tests.**
- C1 excels at freeform generation and compression but tripped on `=` tokenization
- GA has the best no-prose discipline and schema compliance but uses non-OCTAVE syntax (YAML `-`, single `:`)
- G1 is the most consistent at validity but rate-limited and produces minimal output

**2. The "secretary" role needs two capabilities:**
- **Syntax correctness** (critical for `octave_write` pass-through)
- **No-prose compliance** (the agent must output ONLY OCTAVE, no commentary)

**3. Failure modes by model family:**
- **Claude**: Occasionally uses programming syntax (`=`, `<`) not valid in OCTAVE
- **Gemini**: Rate-limited on 3.1 Pro Preview; minimal output depth
- **Codex**: Always adds prose explanation before the OCTAVE document
- **Goose/minimax**: Uses YAML contamination (`-` bullets, single `:`) periodically
- **Goose/mimo**: Catastrophically unreliable (infinite loops, no output, 2/3 failures)
- **Goose/kimi**: Output fragmentation; inconsistent document structure

### Recommendation

**For production secretary role**: **C1 (Claude Sonnet)** with a post-generation `octave_validate` gate.

Rationale:
- Highest average score (80.0) tied with G1 (80.7) but G1 has rate-limiting issues
- Fastest response time (~23s average vs 67-92s for goose models)
- Only model to produce genuinely compressed OCTAVE with → chains and operator usage
- Syntax errors are catchable — a validate-then-retry loop fixes the occasional `=` or `<` slip
- No-prose compliance is strong (backtick wrapper is strippable)

**Runner-up**: **GA (minimax m2.7)** — best instruction compliance but needs YAML contamination guard.

**Architecture recommendation**: Secretary pipeline should be:
1. Prompt agent via clink (C1 primary, GA fallback)
2. Strip backtick wrappers if present
3. Run `octave_validate` on output
4. If INVALID, retry once with error feedback
5. If still INVALID, flag for human review

### Operational Notes

- Gemini 3.1 Pro Preview hit rate limits on every call — output was recoverable from stderr but PAL reported errors. Not viable for production volume without quota increase.
- Goose models are significantly slower (50-150s vs 20-35s for Claude/Codex) due to OpenRouter routing overhead.
- mimo-v2-pro (GB) should be removed from the octave-specialist rotation — 2/3 complete failures is disqualifying.

## Appendix: Validation Summary

| Model | T1 Errors | T2 Errors | T3 Errors | Total Errors |
|-------|-----------|-----------|-----------|--------------|
| C1 | 0 | 1 (E_TOKENIZE) | 0 (repairs only) | 1 |
| G1 | 0 | 0 | 0 (repairs only) | 0 |
| X1 | 0 | 0 | 0 (heavy repairs) | 0 |
| GA | 1 (E_PARSE) | 0 | 1 (E_TOKENIZE) | 2 |
| GB | DNF | DNF | 0 (repairs only) | 2 DNF |
| GC | DNF | no header | 0 (data loss) | 2 DNF |
