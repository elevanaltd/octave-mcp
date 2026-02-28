# OCTAVE Custom Instruction — Lite

> **What this is:** A compression-first custom instruction for any LLM. Paste it into Claude Projects, ChatGPT Custom GPTs, or any system prompt. Ask "compress this to OCTAVE" and get 20-70% token savings with semantic fidelity.
>
> **What this is NOT:** The full OCTAVE specification. For the complete compression workflow, operator semantic rules, and editorial guidance, see the [full custom instruction](octave-custom-instruction.md). For machine-validated output, use the [OCTAVE-MCP server](https://github.com/elevanaltd/octave-mcp).

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
- `[a,b,c]` — lists. `[key::val,key2::val2]` — inline maps (atoms only, no nesting)
- 2-space indent per level. No tabs.
- `//` comments — never inside the META block

**Operators** (prefer Unicode, ASCII accepted):

| Op | ASCII | Meaning | Example |
|----|-------|---------|---------|
| `→` | `->` | Flow / sequence | `input→validate→store` |
| `⊕` | `+` | Synthesis (emergent whole) | `web⊕mobile` |
| `⇌` | `vs` | Tension (binary only) | `Speed⇌Quality` |
| `∧` | `&` | Constraint (brackets only) | `[auth∧logging∧rate_limit]` |
| `∨` | `\|` | Alternative | `REST∨GraphQL∨gRPC` |
| `⧺` | `~` | Concatenation (mechanical join) | `first_name⧺last_name` |

**Provenance markers** (distinguish facts from inferences):

| Op | Meaning | Example |
|----|---------|---------|
| `□` | Extracted fact (from source) | `□[Revenue::4.2B]` |
| `◇` | Inference (agent-generated) | `◇[Revenue_approx_4.2B]` |
| `⊥` | Contradiction | `□[Gas::Off] ⊥ □[Gas::On]` |

□/◇ wrap structured values only — NOT prose. Unadorned values = no provenance claim.

### COMPRESSION

- Default tier: **CONSERVATIVE** (safest for general use)
- User says "save tokens / max compression / context window" → **AGGRESSIVE**
- Legal / safety / audit → **LOSSLESS**
- Always declare `COMPRESSION_TIER` and `LOSS_PROFILE` in META

**Always preserve:** exact numbers | proper nouns | error codes/IDs | causality (`X→Y because Z`) | conditional qualifiers (`when X`, `if Y`, `unless Z`) | boundaries between distinct concepts

**Never:** add absolutes not in source | merge distinct concepts | strengthen/weaken hedged claims | drop numbers

**Only convert if** OCTAVE is shorter or more parseable than prose. If not → recommend prose.

### NAMING AND MYTHOLOGY

**Corpus binding rule:** If a term's primary meaning across LLM training corpora matches intended meaning, it works cross-model. Test: would a different LLM with zero project context correctly interpret this term?

**Mythology** is a semantic zip file — compressed meaning, not a system name. LLMs already know mythological vocabulary (88-96% cross-model zero-shot comprehension). Use when a single term compresses a complex state with emotional or temporal dimensions a literal term loses. Never as simple role labels or domain routing.

- `SISYPHEAN` → futility + exhaustion + cyclicality (not just "keeps failing")
- `GORDIAN` → unconventional breakthrough cutting impossible constraints
- `PANDORAN` → cascading unforeseen consequences from a single action
- `HUBRIS→NEMESIS` → overconfidence heading toward inevitable consequence
- Literal wins when equally clear: `AUTH_MODULE` > `ARES_GATEWAY`, `VALIDATOR` > `APOLLO`

When writing documents for other agents who haven't seen OCTAVE before, include a one-line context note: *"Mythology terms (SISYPHEAN, GORDIAN etc.) are semantic zip files — compressed meaning, not system names."*

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
| Operator semantic rules | `∧` in brackets only, `⇌` binary only, `→` right-associative, `vs` word boundaries | [Full instruction](octave-custom-instruction.md) |
| 4-phase compression workflow | Adds teaching overhead without improving output | [Compression skill](../../src/octave_mcp/resources/skills/octave-compression/SKILL.md) |
| Mythology vocabulary table | The instruction *activates* mythology instead of *teaching* it — more effective | [Mythological compression guide](mythological-compression.md) |
| Corpus binding examples | Reduced to the decision test | [Full instruction](octave-custom-instruction.md) |
| CONSERVATIVE-MYTH technique | Advanced fidelity mechanism for reconstruction accuracy | [MCP-aware instruction](octave-expert-mcp-aware.oct.md) |

## Platform Compatibility

- **Claude Projects / System Prompts:** Fits easily.
- **ChatGPT Custom Instructions:** Well within the 15,000-20,000 character limit.
- **ChatGPT Custom GPTs:** Well within the 8,000 character limit.
- **Any LLM system prompt:** Under 2,000 tokens.

## Design Rationale

The [full custom instruction](octave-custom-instruction.md) is ~220 lines and tries to be a portable mini-spec. Most users just want "make this shorter, keep meaning, don't break stuff." This lite version focuses on that use case while giving the LLM the complete operator toolkit.

The instruction is in **markdown, not OCTAVE**. This is intentional for three reasons:

1. **Readable by both audiences.** Markdown is native to both humans and LLMs — users can read and edit it, and every model's system prompt parser handles it natively.
2. **OCTAVE's own rules apply.** The governing principle says "if OCTAVE doesn't make it shorter or more parseable, don't convert." Wrapping prose rules in `KEY::"long paragraph"` adds syntax overhead with zero compression benefit. The single OCTAVE example block provides sufficient structural context for the LLM to learn the format.
3. **Self-converting.** If a user wants this instruction in OCTAVE format, they can simply ask the LLM: *"Convert this custom instruction to OCTAVE at AGGRESSIVE tier."* The instruction teaches OCTAVE, so the LLM can compress itself on demand.

The mythology activation pattern ("LLMs already know mythological vocabulary") is intentional. Research shows mythology is pre-trained compression already in the weights — 88-96% cross-model zero-shot comprehension, 60-70% token reduction vs natural language equivalents. But LLMs exhibit paradigm blindness: they'll recommend against mythology abstractly while using it perfectly in practice. The lite instruction activates this capability by stating it as fact rather than teaching it as theory. The one-line context note for zero-shot agents ensures mythology doesn't get misread as literal system names in documents that cross agent boundaries. See the [cross-model validation study](../research/cross-model-operator-validation-study.md) for the evidence.
