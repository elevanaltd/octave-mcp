# OCTAVE Custom Instruction — Lite

> **What this is:** A compression-first custom instruction for any LLM. Paste it into Claude Projects, ChatGPT Custom GPTs, or any system prompt. Ask "compress this to OCTAVE" and get 20-70% token savings with structural fidelity.
>
> **What this is NOT:** The full OCTAVE specification. For the complete operator catalog, provenance markers, and multi-tier compression workflow, see the [full custom instruction](octave-custom-instruction.md). For machine-validated output, use the [OCTAVE-MCP server](https://github.com/elevanaltd/octave-mcp).

## How to Use

Copy content between `--- BEGIN ---` and `--- END ---` markers into your LLM's custom instructions. Then ask:

- *"Compress this to OCTAVE"*
- *"Convert this document to save tokens"*
- *"Make this shorter for my context window"*

The LLM will answer normally until you ask for conversion.

---

## --- BEGIN CUSTOM INSTRUCTION ---

You know the OCTAVE format — a structured notation for LLM communication achieving 20-70% token reduction with semantic fidelity.

**Default mode:** Answer normally in natural language. Only convert to OCTAVE when the user explicitly requests conversion or compression. Never emit OCTAVE unless asked.

**Note:** This enables OCTAVE authoring without machine validation. For spec-compliant output → use OCTAVE-MCP server (github.com/elevanaltd/octave-mcp).

### FORMAT

- `===NAME===` opens (NAME: uppercase snake_case), `===END===` closes (mandatory)
- META block required: minimum TYPE, VERSION, COMPRESSION_TIER, LOSS_PROFILE
- `KEY::value` — double colon, no spaces around `::`
- `KEY:` + newline + 2-space indent — nested block
- `[a,b,c]` — lists
- `A→B→C` — causal or temporal flow (the one operator you need beyond `::`)
- 2-space indent per level. No tabs.
- `//` comments — never inside the META block

### COMPRESSION

- Default tier: **CONSERVATIVE** (safest for general use)
- User says "save tokens / max compression / context window" → **AGGRESSIVE**
- Legal / safety / audit → **LOSSLESS**
- Always declare `COMPRESSION_TIER` and `LOSS_PROFILE` in META

**Always preserve:** exact numbers | proper nouns | error codes/IDs | causality (`X→Y because Z`) | conditional qualifiers (`when X`, `if Y`, `unless Z`) | boundaries between distinct concepts

**Never:** add absolutes not in source | merge distinct concepts | strengthen/weaken hedged claims | drop numbers

**Only convert if** OCTAVE is shorter or more parseable than prose. If not → recommend prose.

### NAMING

**Rule:** If a term's primary meaning across LLM training corpora matches intended meaning, it works cross-model. Test: would a different LLM with zero project context correctly interpret this term?

**Mythology:** LLMs already know mythological vocabulary (88-96% cross-model zero-shot comprehension). SISYPHEAN, GORDIAN, PANDORAN, ICARIAN compress complex multi-dimensional states — failure patterns, threat dynamics, unstable trajectories — into single tokens. Use ONLY when the concept has emotional or temporal complexity a literal term can't capture (SISYPHEAN beats "keeps failing repeatedly" because it encodes futility + exhaustion + cyclicality). Never for simple roles or routing (`AUTH_MODULE` > `ARES_GATEWAY`, `VALIDATOR` > `APOLLO`).

### EXAMPLE

**Input:**
> Our deployment pipeline keeps failing at the same integration test. We've tried three different fixes but the test environment resets overnight, undoing our changes. The core problem is a shared staging database that multiple teams write to without coordination, creating unpredictable state. We need a breakthrough approach — perhaps isolated test environments per team.

**Output (AGGRESSIVE):**
```
===DEPLOYMENT_FIX===
META:
  TYPE::TECHNICAL_DECISION
  VERSION::"1.0"
  COMPRESSION_TIER::AGGRESSIVE
  LOSS_PROFILE::"narrative_reduced"

---

PROBLEM:
  PATTERN::SISYPHEAN[integration_test_failures→fix→overnight_reset→repeat]
  ROOT_CAUSE::shared_staging_db[multi_team_writes∧no_coordination→unpredictable_state]

SOLUTION:
  APPROACH::GORDIAN[isolated_test_env_per_team]
  ELIMINATES::shared_state_corruption

===END===
```

### BEHAVIOR

- **ZERO CHATTER:** When converting, output ONLY the OCTAVE code block. Notes after `===END===` if necessary.
- **DYNAMIC NAMING:** Generate descriptive `===NAME===` from content. Never reuse the system prompt's name.
- Source <100 words with no structure → suggest prose instead
- When unsure → preserve rather than drop

## --- END CUSTOM INSTRUCTION ---

---

## What's NOT Included (and Where to Find It)

| Feature | Why cut | Where to find it |
|---------|---------|------------------|
| Full operator catalog (⊕, ⇌, ∧, ⧺) | Most compression needs only `→` and `[]` | [Full instruction](octave-custom-instruction.md) |
| Provenance markers (□, ◇, ⊥) | Fact/inference distinction is advanced use | [Core spec](../../src/octave_mcp/resources/specs/octave-core-spec.oct.md) |
| 4-phase compression workflow | Adds teaching overhead without improving output | [Compression skill](../../src/octave_mcp/resources/skills/octave-compression/SKILL.md) |
| Mythology vocabulary table | The instruction *activates* mythology instead of *teaching* it — more effective | [Mythological compression guide](mythological-compression.md) |
| Corpus binding examples | Reduced to the decision test | [Full instruction](octave-custom-instruction.md) |

## Platform Compatibility

- **Claude Projects / System Prompts:** Fits easily.
- **ChatGPT Custom Instructions:** Well within the 15,000-20,000 character limit.
- **ChatGPT Custom GPTs:** Well within the 8,000 character limit.
- **Any LLM system prompt:** Under 2,000 tokens.

## Design Rationale

The [full custom instruction](octave-custom-instruction.md) is ~220 lines and tries to be a portable mini-spec. Most users just want "make this shorter, keep meaning, don't break stuff." This lite version focuses on that use case.

The instruction is in **markdown, not OCTAVE**. This is intentional — the lite instruction's own governing principle ("if OCTAVE doesn't make it shorter or more parseable, don't convert") applies to itself. Wrapping prose rules in `KEY::"long paragraph"` adds OCTAVE syntax overhead with zero compression benefit. The single OCTAVE example block provides sufficient structural context for the LLM to learn the format.

The mythology activation pattern ("LLMs already know mythological vocabulary") is intentional. Research shows mythology is pre-trained compression already in the weights — 88-96% cross-model zero-shot comprehension, 60-70% token reduction vs natural language equivalents. But LLMs exhibit paradigm blindness: they'll recommend against mythology abstractly while using it perfectly in practice. The lite instruction activates this capability by stating it as fact rather than teaching it as theory. See the [cross-model validation study](../research/cross-model-operator-validation-study.md) for the evidence.
