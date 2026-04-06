# OCTAVE Specialist Stress Test — Multi-Turn Interview via clink vs oa-router

**Date**: 2026-04-06
**Purpose**: Compare two platforms (PAL clink vs oa-router Task agent) for multi-turn OCTAVE secretary work using continuation/resume IDs.
**Model**: Claude Sonnet 4.6 on both platforms.

## Test Design

**Scenario**: Write a "deployment-guardian" agent definition via `octave_write`, then 3 follow-up turns:
1. **Turn 1**: Write the agent document, explain structural choices
2. **Turn 2**: Challenge cognition choice, request amendments via `changes` parameter
3. **Turn 3**: Validate with STRICT profile, fix issues, explain intentional ignores

## Platform Comparison

### Turn 1 — Initial Write

| Dimension | Clink (claude CLI) | OA-Router (Task agent) |
|-----------|-------------------|----------------------|
| File written? | YES (116 lines, 3798b) | YES (98 lines) |
| First attempt? | YES | YES |
| COGNITION choice | LOGOS | ETHOS |
| ARCHETYPE | GATEKEEPER+VALIDATOR+ARBITER | ARES+ARTEMIS+ATHENA |
| Mythology usage | Minimal (generic archetypes) | Rich (ARES<adversarial_validation>, PANDORAN_PREVENTION) |
| Structural reasoning | Good — explained priority encoding, modularity | Excellent — referenced spec, octave-specialist patterns, defended with examples |
| Duration | 129s (67s API) | 163s |
| Tool calls | 4 turns | 21 tool uses |

**Turn 1 verdict**: OA-router produced deeper architectural reasoning and richer mythology. Clink was faster.

### Turn 2 — Challenge & Amendment

| Dimension | Clink | OA-Router |
|-----------|-------|-----------|
| Response to challenge | Conceded LOGOS→ETHOS with excellent reasoning | Defended ETHOS with detailed cognitive analysis |
| `changes` parameter | Tried, **partially worked** — delta merged but had junk cleanup | Tried, **failed** (E_UNRESOLVABLE_PATH for section keys) → full rewrite |
| Threshold design | CONFIGURABLE/ABSOLUTE split with OVERRIDE_MECHANISM | 6-block structure (CANARY, HEALTH, DEPS, ROLLBACK, OVERRIDE, VERDICT) |
| Bugs found | W_STRUCT_003 cleanup behavior | Indentation collapse bug, RANGE constructor drop |
| Forward thinking | Suggested CONFIG_PROTOCOL section for future | Explained deterministic verdict logic (ALL_PASS→APPROVE) |
| Duration | 174s (112s API) | 121s |

**Turn 2 verdict**: Clink conceded more gracefully. OA-router found more tool bugs and produced more detailed threshold design. OA-router was faster this turn.

### Turn 3 — Validate & Fix

| Dimension | Clink | OA-Router |
|-----------|-------|-----------|
| Validation approach | Ran STRICT against META schema directly | Tested META schema first, then tried AGENT_DEFINITION schema |
| Issues found | 3 E007s (CLASSIFICATION, DOMAIN, TIER in META) | 2 E007s (PURPOSE, CONTRACT) — correctly identified as schema-mismatch |
| Fix strategy | Removed invalid META fields, relocated TIER to ROLE | No file changes needed — argued the META schema is wrong target |
| Final state | VALIDATED (0 errors, 0 warnings) | UNVALIDATED under AGENT_DEFINITION (constraint eval not yet implemented) |
| Critical insight | "META.ID removal is compliance theater" — flagged schema gap | "Two schemas exist; use the right one" — compared both |
| Duration | 148s (86s API) | 46s |

**Turn 3 verdict**: OA-router was significantly smarter — tested both schemas and correctly concluded the META schema was the wrong validation target. Clink brute-forced compliance by removing fields.

## Aggregate Comparison

| Metric | Clink | OA-Router | Winner |
|--------|-------|-----------|--------|
| Total wall time | **451s** | **330s** | OA-Router |
| Total API time | 265s | N/A (internal) | — |
| Context preservation | 33 turns remaining | Full agent context preserved | Tie |
| `changes` param success | Partial (with junk cleanup) | Failed (E_UNRESOLVABLE_PATH) | Clink |
| Bugs/friction discovered | 1 (W_STRUCT_003) | 3 (E_UNRESOLVABLE_PATH, indentation collapse, RANGE drop) | OA-Router |
| Architectural reasoning | Good | Excellent (spec-grounded) | OA-Router |
| Mythology usage | Generic archetypes | Rich narrative patterns (ARES, PANDORAN, ACHILLEAN) | OA-Router |
| Self-correction | Conceded + fixed quickly | Defended + adapted approach | OA-Router |
| Schema intelligence | Single-schema approach | Multi-schema comparison | OA-Router |
| Final file quality | 116 lines, VALIDATED | 119 lines, structurally sound | Tie |

## Key Findings

### 1. OA-Router produces deeper reasoning
The oa-router agent had access to the full codebase context (it read the octave-specialist.oct.md reference, checked specs, examined existing patterns). This grounded its decisions in evidence rather than generic knowledge. The clink agent worked from its system prompt alone.

### 2. Clink handles `changes` parameter better
Clink's agent successfully used delta updates (albeit with cleanup artifacts). OA-router's agent correctly identified the limitation (section-level paths aren't supported) and adapted by doing a full rewrite.

### 3. OA-Router finds more tool bugs
With deeper codebase access, OA-router discovered 3 octave_write behaviors vs 1 for clink. This makes it more valuable for the "flag issues and create GH issues" part of the secretary role.

### 4. Continuation vs Resume semantics differ
- **Clink**: `continuation_id` preserves the conversation verbatim. 39→35→33 turns remaining.
- **OA-Router**: `resume` preserves agent context within a Task subagent. No turn limit visible, but bounded by context window.

### 5. Cost comparison
- **Clink total**: ~$1.29 (sum of 3 turns: $0.37 + $0.47 + $0.45)
- **OA-Router total**: Not directly measurable (internal token usage), but estimated lower due to Sonnet-level model with smaller context per turn.

## Recommendation

| Use Case | Recommended Platform |
|----------|---------------------|
| Quick single-shot writes | **Clink** — faster for simple tasks |
| Multi-turn iterative work | **OA-Router** — deeper context, better reasoning |
| Bug/friction discovery | **OA-Router** — codebase access finds real issues |
| Delta amendments (`changes`) | **Clink** — handles partial updates better |
| Production secretary pipeline | **OA-Router** — quality of reasoning justifies the overhead |
| Schema gap identification | **OA-Router** — tested multiple schemas, found the right one |

**Overall winner for the secretary role: OA-Router** — the deeper reasoning, mythology usage, multi-schema intelligence, and bug discovery capability outweigh clink's speed advantage for single shots.

## Output Files

- `stress-clink.oct.md` — 116 lines, VALIDATED against META STRICT
- `stress-oa.oct.md` — 119 lines, structurally sound (AGENT_DEFINITION constraint eval pending)
