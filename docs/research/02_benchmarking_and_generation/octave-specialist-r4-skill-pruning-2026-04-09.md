# OCTAVE Specialist Round 4 — Skill Pruning & LLM Consumption Framing

**Date**: 2026-04-09
**Purpose**: Test whether trimming from 5 skills to 3 essential skills, and adding explicit LLM-consumption framing, improves the secretary agent's output.

## Test Matrix

| Variant | Model | Skills | LLM Frame? | File |
|---------|-------|--------|-----------|------|
| R3 Baseline | Haiku 4.5 | 5 (literacy, mastery, compression, mythology, ultra-mythic) | No | r3-haiku.oct.md |
| R4a: 3 Skills | Haiku 4.5 | 3 (literacy, mastery, compression) | No | r4-haiku-3skills.oct.md |
| R4b: LLM Framed | Haiku 4.5 | 3 (literacy, mastery, compression) + LLM framing | Yes | r4-haiku-llm-framed.oct.md |

## Results

| Metric | R3 (5 skills) | R4a (3 skills) | R4b (3 skills + LLM frame) |
|--------|--------------|---------------|---------------------------|
| File size | 7875b | **3943b** | 6441b |
| Duration | 172s | **83s** | 161s |
| Final warnings | 30 W_DUPLICATE_KEY | 0 | 0 |
| Sections | 10 | 7 | 7 |
| Archetypes | 3 | 3 | 5 |
| Decision structure | 5-gate | RED/YELLOW/GREEN tripartite | 5-gate sequential |
| Friction issues found | 1 | 1 | 4 |
| Self-correction quality | Basic | Good | Excellent |
| Cost estimate | ~$0.03 | ~$0.015 | ~$0.03 |

## Key Findings

### 1. Three skills is the sweet spot for the secretary

Removing octave-mythology (181 lines) and octave-ultra-mythic (132 lines) — 313 lines of skill context — produced:
- **50% smaller output** (3943b vs 7875b) — denser, not weaker
- **52% faster** (83s vs 172s)
- **Zero validation warnings** vs 30 in the baseline
- Mythology still used correctly (archetypes from octave-mastery §1 are sufficient)

The mythology skills teach *when and how* to use mythology. But the secretary already knows the vocabulary from training data — it just needs the syntax rules (octave-literacy) and the vocabulary reference (octave-mastery §1).

### 2. LLM-consumption framing dramatically changes output character

The LLM frame produced:
- **5 archetypes** instead of 3 (more aggressive semantic compression)
- **Operators as logic** (`∧`, `∨`, `→`) instead of prose explanations
- **Explicit loss accounting** (LOSS_PROFILE, NARRATIVE_DEPTH metadata)
- **Circuit breaker pattern** (anti-hallucination engineering)
- **4 friction discoveries** vs 1 (pushes harder against edge cases)

The framing shifted the agent from "write a good document" to "write the most information-dense document an LLM can parse." This is exactly the secretary mindset.

### 3. Both pruned variants outperform the baseline

| Quality Dimension | R3 (5 skills) | R4a (3 skills) | R4b (LLM frame) |
|------------------|--------------|---------------|-----------------|
| Syntax correctness | 30 warnings | **0 warnings** | **0 warnings** |
| Semantic completeness | High (verbose) | Good (concise) | **Excellent (dense)** |
| Decision logic preserved | Yes | Yes | **Yes + circuit breaker** |
| Cost efficiency | $0.03 | **$0.015** | $0.03 |
| Friction discovery | Low | Low | **High** |

## Recommendation for Secretary Agent Definition

### Skill loading
- **Always**: octave-literacy, octave-mastery, octave-compression
- **Never**: pattern-mastery (irrelevant to document authoring)
- **On-demand**: octave-mythology (only when explicitly asked to compress with mythological atoms), octave-ultra-mythic (only for binding protocols)

### System prompt addition
Add this framing to the secretary's system prompt:
> "Documents you produce are consumed exclusively by other LLMs. Natural language prose is wasteful. Use OCTAVE operators for logic, mythological archetypes for semantic compression, and structured blocks for data. Maximize information density with zero ambiguity."

### Model selection
Haiku 4.5 with 3 skills + LLM framing produces output comparable to Sonnet with 5 skills, at ~10% of the cost.

## Output Files

- `r4-haiku-3skills.oct.md` — 3943b, 0 warnings, 83s
- `r4-haiku-llm-framed.oct.md` — 6441b, 0 warnings, 161s
