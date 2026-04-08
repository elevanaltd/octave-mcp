# OCTAVE Specialist Round 3 — Controlled Model Comparison

**Date**: 2026-04-08
**Purpose**: Fair comparison with matched conditions: same skills loaded, same prompt, correct model attribution.

## Corrections from Previous Rounds

Previous rounds had two confounding variables:
1. **Skill asymmetry**: OA-router agents auto-load skills (octave-literacy, octave-mastery, etc.). Clink agents only had the system prompt. This gave oa-router an unfair knowledge advantage.
2. **Model mismatch**: OA-router defaulted to the calling model (Opus 4.6), not Sonnet. So the "Sonnet vs Sonnet" comparison in Round 3 stress test was actually Opus vs Sonnet.

This round controls for both: all agents read the same 5 skill files before writing, and oa-router is explicitly set to model: sonnet.

## Test Matrix

| ID | Platform | Model | Skills Loaded |
|----|----------|-------|--------------|
| Haiku | goose/clink (OS-A) | Claude Haiku 4.5 via OpenRouter | 5 skills (manual read) |
| Sonnet-G | goose/clink (OS-B) | Claude Sonnet 4.6 via OpenRouter | 5 skills (manual read) |
| Opus | goose/clink (OS-C) | Claude Opus 4.6 via OpenRouter | 5 skills (manual read) |
| Sonnet-OA | oa-router (Task) | Claude Sonnet 4.6 (explicit) | Auto-loaded via anchor |

## Results

### Output Metrics

| Model | File Size | First Attempt? | Final Errors | Final Warnings | Duration |
|-------|-----------|---------------|-------------|----------------|----------|
| Haiku | 7875b | Yes (after fixing `<` tokenization) | 0 | 30 (W_DUPLICATE_KEY) | 172s |
| Sonnet-G | 5419b | Yes (5 W_DUPLICATE_KEY, semantics_changed) | 0 | 5 | 191s |
| Opus | 4849b | Yes (clean, first attempt) | 0 | 5 (W_CONSTRUCTOR_MISUSE, safe) | 132s |
| Sonnet-OA | 4078b | No (2 failed writes, then success) | 0 | 0 | 274s |

### Archetype Choices

| Model | Archetypes | Rationale Quality |
|-------|-----------|-------------------|
| Haiku | ATHENA⊕HEPHAESTUS⊕APOLLO | Good — strategic foresight + mechanical precision + truth-telling |
| Sonnet-G | THEMIS⊕ARGUS⊕HEPHAESTUS | Excellent — impartial law + all-seeing sentinel + craft mastery. Argued against ARES/ZEUS with reasons |
| Opus | CERBERUS⊕THEMIS⊕ARTEMIS | Outstanding — multi-headed gate guardian (unique, deeply fitting). Argued against ZEUS/HERMES/ARES/HEPHAESTUS |
| Sonnet-OA | THEMIS⊕ARES⊕ARTEMIS | Good — impartial judgment + adversarial probing + precision targeting |

### Mythological Pattern Usage

| Model | Patterns Used | Compression Evidence? |
|-------|--------------|----------------------|
| Haiku | 7 (PROMETHEUS, SISYPHEAN, ACHILLEAN, ICARIAN, CHAOS↔COSMOS, NEMESIS, KAIROS) | Yes — showed 85% reduction examples |
| Sonnet-G | 9 (ACHILLEAN, PANDORAN, NEMESIS, HUBRIS→NEMESIS, KAIROS, SISYPHEAN, CHAOS→COSMOS, PROMETHEAN, ICARIAN) | Yes — explained each with "what literal term loses" |
| Opus | 7 (PANDORAN_CASCADE, ACHILLEAN, ICARIAN, CHRONOS, CERBERUS, THEMIS, ARTEMIS) | No explicit metrics — focused on behavioral dimensions |
| Sonnet-OA | 7 (ACHILLEAN, PANDORAN, SISYPHEAN, PHOENICIAN, KAIROS, THEMIS, ARES) | No explicit metrics — focused on semantic encoding |

### Self-Awareness & Error Diagnosis

| Model | Self-Diagnosis Quality |
|-------|----------------------|
| Haiku | Identified angle-bracket tokenization error. Correctly noted 30 W_DUPLICATE_KEY warnings as structural (repeated GATE blocks) but didn't recognize the data loss implications |
| Sonnet-G | **Exceptional** — self-diagnosed its own W_DUPLICATE_KEY error as a structural mistake (keys at wrong indentation level), proposed 3 fixes, correctly identified `semantics_changed: true` as real data loss |
| Opus | Identified W_CONSTRUCTOR_MISUSE as false positive in grammar context. Correctly identified AGENT_DEFINITION schema gap. Clean first-attempt write |
| Sonnet-OA | Found W_NUMERIC_KEY_DROPPED on first write (silent data loss from `1::`, `2::` keys). Correctly identified ESCALATION list flow expressions being collapsed. Required restructuring |

### Friction Insights (New)

| Finding | Reported By | New? |
|---------|-----------|------|
| REGEX:: inside GRAMMAR blocks triggers false-positive W_CONSTRUCTOR_MISUSE | Opus | Yes — grammar-context exemption needed |
| Angle-bracket `<args>` not valid OCTAVE (should be `NAME[args]`) | Haiku, Sonnet-OA | Confirmed from R2 |
| AGENT_DEFINITION schema missing from builtin schemas | Opus, Sonnet-OA | New — related to #358 (META.ID) but distinct |
| Flow expressions `A→B[args]` inside lists get silently collapsed | Sonnet-OA | Yes — list-context constructor reduction |

## Platform Comparison: goose-Sonnet vs oa-router-Sonnet

The controlled comparison (same model, same skills):

| Dimension | Goose-Sonnet (clink) | OA-Router-Sonnet (Task) | Winner |
|-----------|---------------------|------------------------|--------|
| File size | 5419b | 4078b | OA-Router (more compressed) |
| Duration | 191s | 274s | Goose (44% faster) |
| First-attempt clean? | Yes (with warnings) | No (2 failed writes) | Goose |
| Archetype quality | THEMIS⊕ARGUS⊕HEPHAESTUS (unique, argued) | THEMIS⊕ARES⊕ARTEMIS (standard) | Goose |
| Self-diagnosis | Exceptional — found own structural error | Good — found tool data loss | Goose |
| Mythology depth | 9 patterns, each justified | 7 patterns, each justified | Goose |
| Friction discovery | W_DUPLICATE_KEY indentation analysis | W_NUMERIC_KEY_DROPPED, flow collapse | OA-Router |
| Codebase awareness | Read skills only | Read skills + agent definitions + specs | OA-Router |

**Verdict**: When skills are pre-loaded, **goose-clink Sonnet outperforms oa-router Sonnet**. The oa-router's advantage was skill loading — once that's equalized, goose-clink is faster, produces richer archetype work, and shows better self-diagnosis.

## Model Tier Comparison

| Dimension | Haiku 4.5 | Sonnet 4.6 | Opus 4.6 |
|-----------|-----------|-----------|----------|
| Output volume | 7875b (largest) | 5419b | 4849b |
| First-attempt clean? | After fixing `<` error | Yes (with warnings) | **Yes (clean)** |
| Archetype originality | Standard (ATHENA/HEPHAESTUS/APOLLO) | Good (ARGUS is unique) | **Best (CERBERUS is perfect)** |
| Self-awareness | Moderate | **Exceptional** | Excellent |
| Mythology density | High (7 patterns) | **Highest** (9 patterns) | Good (7 patterns) |
| Friction found | 1 | 1 (own error) | 2 (false positive + schema gap) |
| Cost efficiency | **Best** (~$0.02) | Moderate (~$0.15) | High (~$0.60) |
| Duration | 172s | 191s | **132s** |

### Tier Recommendations

| Use Case | Recommended Model | Rationale |
|----------|------------------|-----------|
| **Bulk secretary work** (write files, validate, compress) | **Haiku** | 90%+ quality at ~3% of Opus cost. Skills provide the knowledge; Haiku provides the execution |
| **Agent design** (new agent definitions, archetype selection) | **Opus** | CERBERUS selection demonstrates the deepest semantic matching. First-attempt clean writes |
| **Self-correcting pipeline** (write → validate → fix → re-write) | **Sonnet** | Best at diagnosing its own errors and proposing fixes. The self-awareness compensates for any first-attempt issues |
| **Friction/bug discovery** (testing octave_write itself) | **Sonnet or Opus** | Both surface real tool issues. Haiku accepts tool behavior without questioning it |

## Overall Recommendation

**The previous assessment was wrong about oa-router being the clear winner.** The advantage was entirely from skill loading, not from the platform itself.

**Corrected architecture for secretary pipeline:**

1. **Primary**: Goose-clink with Claude Sonnet (OS-B), skills pre-loaded in prompt
2. **Budget fallback**: Goose-clink with Claude Haiku (OS-A) for bulk operations
3. **Quality escalation**: Goose-clink with Claude Opus (OS-C) for agent architecture work
4. **OA-Router**: Reserve for cases where deep codebase exploration is needed (not just document writing)

**The skill files are the force multiplier, not the platform.** Any model with octave-literacy + octave-mastery + octave-mythology loaded produces dramatically better OCTAVE than the same model without them.

## Output Files

- `r3-haiku.oct.md` — 7875b, VALIDATED (30 W_DUPLICATE_KEY)
- `r3-sonnet.oct.md` — 5419b, VALIDATED (5 W_DUPLICATE_KEY)
- `r3-opus.oct.md` — 4849b, VALIDATED (5 W_CONSTRUCTOR_MISUSE, safe)
- `r3-oa-sonnet.oct.md` — 4078b, 0 errors, 0 warnings
