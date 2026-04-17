# OCTAVE Specialist Round 5 — LLM Framing Benchmark: Agent Rewrites Its Own Skill

**Date**: 2026-04-09
**Purpose**: Have 5 agents rewrite octave-literacy with the LLM-consumption paradigm integrated. Test where they place it, what they change, and what quality emerges. The ultimate secretary test: can the agent improve its own instructions?

## Test Design

All agents received:
- The current octave-literacy, octave-mastery, and octave-compression skills to read
- The LLM-consumption context (North Star identity, prose-is-wasteful framing)
- Task: "Rewrite octave-literacy to integrate this paradigm. The current skill never tells the agent WHY or WHO."
- Deliberately NOT told where to place the LLM frame

## Test Matrix

| Agent | Platform | Model | Duration |
|-------|----------|-------|----------|
| Gemini | clink (gemini CLI) | Gemini 3.1 Pro Preview | ~125s |
| Haiku | clink (goose OS-A) | Claude Haiku 4.5 | 149s |
| Sonnet | clink (goose OS-B) | Claude Sonnet 4.6 | 357s |
| Opus | clink (goose OS-C) | Claude Opus 4.6 | 242s |
| OA-Sonnet | oa-router (Task) | Claude Sonnet 4.6 | 629s |

## Consensus: Where the LLM Frame Belongs

**All 5 agents chose §0 — before §1::CORE_SYNTAX.** Unanimous.

| Agent | Section Name | Also in META? |
|-------|-------------|---------------|
| Gemini | §0::LLM_CONSUMPTION_PARADIGM | No |
| Haiku | §0::LLM_CONSUMPTION_PARADIGM | Yes (`AUDIENCE::"Language Models exclusively"`) |
| Sonnet | §0::LLM_CONSUMPTION_PARADIGM | Yes (`AUDIENCE::LLM`, `CONSUMPTION_MODEL::...`) |
| Opus | §0::WHY_OCTAVE_EXISTS | Yes (`AUDIENCE::LLM[exclusively]`, `NORTH_STAR::...`) |
| OA-Sonnet | §0::LLM_CONSUMPTION_PARADIGM (+ §0b::MYTHOLOGY_RATIONALE) | Not explicitly |

**Consensus finding**: The LLM frame is **pre-syntax foundational** — it answers "why does this format exist?" before "how do I use it?" Four of five also elevated `AUDIENCE` to META-level identity.

## Structural Approaches Compared

| Dimension | Gemini | Haiku | Sonnet | Opus | OA-Sonnet |
|-----------|--------|-------|--------|------|-----------|
| **File size** | 4841b | 5895b | **11969b** | 10078b | 7275b |
| **§0 structure** | Flat 4-key block | 3 sub-blocks (NORTH_STAR, INEFFICIENCY, EFFICIENCY) | 5 sub-blocks + causal chain | **4-block causal chain** (PARADIGM→LOSS→TOKEN→DESIGN) | §0 + §0b (mythology rationale embedded) |
| **Rule annotation** | No | Yes (`REASON` fields) | **Yes** (`// WHY:` on every rule) | Yes (inline `//` comments) | Partial (some rules annotated) |
| **Syntax changes** | Minimal | Added REASON fields | Most extensive | `1::` → `R1::` fix | `1::` → `R1::` fix |
| **Backward compat** | High | Moderate (added fields) | Lower (restructured) | **High** (additive only) | High (additive only) |
| **Original bug found** | No | No | No | **Yes** (numeric keys violate Rule 3) | **Yes** (numeric keys) |
| **Validation** | 0 err, 0 warn | 0 err, 0 warn | 0 err, 0 warn | 0 err, 0 warn | 0 err, 0 warn |

## Quality Assessment

### Gemini — Minimal but Correct (4841b)
- Cleanest §0: just `INTENT`, `AUDIENCE`, `PRINCIPLE`, `CONSEQUENCE`
- Didn't touch META — frame is section-only, not identity-level
- No rule annotations — syntax rules unchanged
- **Strength**: Minimal diff, lowest risk of regression
- **Weakness**: Frame is bolt-on, not pervasive

### Haiku — Pedagogical Approach (5895b)
- §0 has three sub-blocks explaining WHAT prose wastes vs WHAT structure saves
- Added `REASON` fields to syntax elements
- `AUDIENCE` in META
- **Strength**: Best for teaching — explains the "why" with concrete contrast
- **Weakness**: The REASON fields add tokens to a skill that should model token economy

### Sonnet — Most Pervasive Integration (11969b)
- Every single syntax rule annotated with `// WHY:` connecting back to LLM parsing
- Causal chain in §0: `PREMISE_1→PREMISE_2→PREMISE_3→CONCLUSION`
- `AUDIENCE::LLM` + `CONSUMPTION_MODEL` in META
- Self-compared against Gemini and Haiku during analysis
- **Strength**: The frame isn't a section — it permeates the entire document
- **Weakness**: Nearly 2.5x the original size. Annotation overhead may be self-defeating

### Opus — Most Architecturally Sound (10078b)
- Three-layer placement: META + §0 + distributed `//` comments
- §0::WHY_OCTAVE_EXISTS with causal chain: `PARADIGM→LOSS_ACCOUNTING→TOKEN_ECONOMICS→DESIGN_CHAIN`
- `DESIGN_CHAIN` explicitly derives syntax from audience: `[AUDIENCE::LLM]→[OPTIMIZE::token_density]→[TRACK::loss_explicitly]→[RESULT::OCTAVE_syntax]`
- Added §2c::OPERATOR_ECONOMICS explaining why operators matter for LLMs
- Enriched §4 example with loss accounting in practice
- Caught original bug: `1::` keys violate Rule 3 → fixed to `R1::`
- **Strength**: Best architectural reasoning. The `DESIGN_CHAIN` is the most powerful single addition — it makes syntax derivable from principles
- **Weakness**: Some operator economics content duplicates octave-mastery

### OA-Sonnet — Pattern-Aware Integration (7275b)
- Named the pattern explicitly: CONSTRAINT_INVERSION from pattern-mastery
- §0b::MYTHOLOGY_RATIONALE embedded inside §0 — not a separate section
- Also caught `1::` → `R1::` bug
- Tightest prose — no explanation annotations, just the frame
- **Strength**: Most disciplined integration. The mythology rationale placement is smart — it belongs with the paradigm, not with the vocabulary
- **Weakness**: Less pervasive than Sonnet — rules aren't individually annotated

## Synthesis: Best Elements from Each

| Element | Source | Why It's Best |
|---------|--------|---------------|
| `AUDIENCE::LLM` in META | Haiku/Sonnet/Opus | Identity-level, not section-level |
| `NORTH_STAR` in META | Opus | One-line paradigm anchor |
| §0::WHY_OCTAVE_EXISTS name | Opus | More descriptive than generic "PARADIGM" |
| DESIGN_CHAIN derivation | Opus | Makes syntax a consequence of audience |
| MYTHOLOGY_RATIONALE inside §0 | OA-Sonnet | Mythology's LLM-compression function belongs with the paradigm, not vocabulary |
| `R1::` through `R9::` key fix | Opus/OA-Sonnet | Fixes original spec violation |
| Inline `//` comments on rules | Opus (selective) | Sonnet's approach is too heavy; Opus strikes the right balance |
| Minimal structural changes | Gemini/Opus | Backward compatibility matters |

## Recommended Final Skill Structure

Based on synthesis of all 5 approaches:

```
META:
  PURPOSE::"OCTAVE syntax as token economy for LLM-to-LLM communication"
  AUDIENCE::LLM[exclusively]
  NORTH_STAR::"OCTAVE-MCP is a loss accounting system for LLM communication"

§0::WHY_OCTAVE_EXISTS                    // Opus naming
  PARADIGM::...                           // Opus causal chain
  TOKEN_ECONOMICS::...                    // Opus
  MYTHOLOGY_RATIONALE::...                // OA-Sonnet placement
  DESIGN_CHAIN::...                       // Opus derivation

§1::CORE_SYNTAX                          // Original, rules renumbered R1-R9
§2::OPERATORS                            // Original + selective // comments
§3::CRITICAL_RULES                       // Original with R1:: keys
§4::EXAMPLE_BLOCK                        // Enriched with loss accounting
```

## Output Files

All rewrites at `docs/research/02_benchmarking_and_generation/octave-write-test-outputs/`:
- `literacy-rewrite-gemini.oct.md` — 4841b (minimal, bolt-on)
- `literacy-rewrite-haiku.oct.md` — 5895b (pedagogical, REASON fields)
- `literacy-rewrite-sonnet.oct.md` — 11969b (pervasive, every rule annotated)
- `literacy-rewrite-opus.oct.md` — 10078b (architectural, DESIGN_CHAIN)
- `literacy-rewrite-oa-sonnet.oct.md` — 7275b (pattern-aware, CONSTRAINT_INVERSION)
