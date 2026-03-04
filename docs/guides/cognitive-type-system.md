# The Cognitive Type System

OCTAVE agents are governed by a triadic cognitive architecture: **LOGOS**, **ETHOS**, and **PATHOS**. Each cognition type defines *how an agent thinks* -- distinct from what it does (§2::OPERATIONAL_BEHAVIOR) or how it speaks (§4::INTERACTION_RULES).

## The Wind, The Wall, and The Door

The triad maps to a physical metaphor that LLMs instantly grasp:

| Type | Element | Force | Metaphor | Function |
|------|---------|-------|----------|----------|
| **PATHOS** | Wind | POSSIBILITY | Boundless divergent energy | Explores without limits |
| **ETHOS** | Wall | CONSTRAINT | Rigid structural boundary | Blocks what violates reality |
| **LOGOS** | Door | STRUCTURE | Emergent third-way mechanism | Lets the wind through the wall |

### Why This Works

If the Wind and the Wall just fight, you get a stalemate -- either the wind stops or the wall falls. The Door is the synthesis: it **respects the Wall** (maintains structural integrity) while **serving the Wind** (allows possibility to pass into reality). A door is not "a little bit of wind and a little bit of wall." It is a *new emergent technology* (hinges, frames, locks) that transcends the conflict.

This maps precisely to the Hegelian dialectic:

- **Thesis** (PATHOS/Wind): What could be
- **Antithesis** (ETHOS/Wall): What cannot be
- **Synthesis** (LOGOS/Door): What *will* be, through structural transcendence

## Cognitive Properties

Each cognition master file (`library/cognitions/TYPE.oct.md`) provides these fields:

### §1::COGNITIVE_IDENTITY -- What I Am

| Field | LOGOS | ETHOS | PATHOS |
|-------|-------|-------|--------|
| FORCE | STRUCTURE | CONSTRAINT | POSSIBILITY |
| ESSENCE | ARCHITECT | GUARDIAN | EXPLORER |
| ELEMENT | DOOR | WALL | WIND |

### §2::COGNITIVE_RULES -- How I Think

| Field | LOGOS | ETHOS | PATHOS |
|-------|-------|-------|--------|
| MODE | CONVERGENT | VALIDATION | DIVERGENT |
| PRIME_DIRECTIVE | "Reveal what connects." | "Reveal what breaks." | "Reveal what could be." |
| THINK | Synthesis rules | Evidence rules | Exploration rules |
| THINK_NEVER | Anti-compromise rules | Anti-hedging rules | Anti-convergence rules |

### Output Chains

Each type enforces a specific Chain-of-Thought reasoning sequence via its THINK rules:

- **LOGOS**: `[TENSION] → [INSIGHT] → [SYNTHESIS]`
- **ETHOS**: `[VERDICT] → [EVIDENCE] → [CONSTRAINT_CATALOG]`
- **PATHOS**: `[STIMULUS] → [CONNECTIONS] → [POSSIBILITIES]`

These force the LLM's reasoning into the correct cognitive rhythm before any domain-specific content is produced.

## Architecture: Separation of Concerns

The v7.0.0 agent spec separates cognitive properties from agent files:

```
Agent File (§1::IDENTITY)          Cognition Master File
┌──────────────────────────┐       ┌───────────────────────────┐
│ ROLE::validator           │       │ §1::COGNITIVE_IDENTITY    │
│ COGNITION::ETHOS ─────────┼──────>│   NATURE:                 │
│ ARCHETYPE::[ARES]         │       │     FORCE::CONSTRAINT     │
│ MISSION::...              │       │     ESSENCE::GUARDIAN      │
│ PRINCIPLES::[...]         │       │     ELEMENT::WALL          │
│                           │       │                           │
│ §2::OPERATIONAL_BEHAVIOR  │       │ §2::COGNITIVE_RULES       │
│   MUST_ALWAYS::[...]      │       │   MODE::VALIDATION        │
│   MUST_NEVER::[...]       │       │   PRIME_DIRECTIVE::...    │
│   (domain-specific)       │       │   THINK::[...]            │
│                           │       │   THINK_NEVER::[...]      │
└──────────────────────────┘       └───────────────────────────┘
         WHAT I DO                        HOW I THINK
```

**Why separate?** The N=40 study (C041) showed that labels alone are inert (p=0.901) but labels + matching behavioral rules produce a +20% improvement. By putting behavioral rules in dedicated files:

- A/B testing becomes trivial (load the cognition file or don't)
- All agents of the same type share identical cognitive rules
- Updating cognition behavior updates all agents simultaneously
- The agent file stays focused on domain-specific operational behavior

## Single Cognition Rule

Each agent must have **exactly one** cognition type. Combining cognitions causes cognitive interference -- contradictory THINK/THINK_NEVER rules degrade performance.

```
COGNITION::ETHOS          // Correct
COGNITION::LOGOS          // Correct
COGNITION::LOGOS+ETHOS    // FORBIDDEN -- cognitive interference
```

For tasks requiring multiple cognitive modes, use **sequential workflows**:

```
Phase 1: PATHOS (explore possibilities)
Phase 2: ETHOS (validate against constraints)
Phase 3: LOGOS (synthesize into solution)
```

This means separate agents or separate phases -- never simultaneous combination.

## Evidence Basis

- **N=40 study**: Labels + matching behavioral rules = +20% improvement (C041)
- **M022**: Grammar contracts (§4) drove 92% vs 54% adherence
- **Probability activation**: LOGOS 80%, PATHOS 70%, ETHOS 60% higher probability of type-appropriate language
- **Cross-model comprehension**: 88-96% across Claude, GPT, Gemini families
- **Pattern recognition**: 100% accuracy on mythological semantic elements

## File Locations

| File | Location | Purpose |
|------|----------|---------|
| Cognition spec | `src/octave_mcp/resources/specs/octave-cognition-spec.oct.md` | Schema contract |
| Agent spec | `src/octave_mcp/resources/specs/octave-agents-spec.oct.md` | References cognition via §5 |
| LOGOS master | `src/octave_mcp/resources/cognitions/logos.oct.md` | Runtime kernel |
| ETHOS master | `src/octave_mcp/resources/cognitions/ethos.oct.md` | Runtime kernel |
| PATHOS master | `src/octave_mcp/resources/cognitions/pathos.oct.md` | Runtime kernel |

Consumer systems (e.g., hestai-mcp) copy these to `library/cognitions/` per the path convention in §5::MAPPING_DEFINITION.

## Related

- [Mythological Compression](mythological-compression.md) -- How mythology functions as LLM compression
- [OCTAVE Philosophy](octave-philosophy.md) -- The Golden Rule and Seven Deadly Smells
