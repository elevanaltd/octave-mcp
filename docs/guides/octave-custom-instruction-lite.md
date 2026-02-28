# OCTAVE Custom Instruction — Lite

> **What this is:** A compression-first custom instruction for any LLM. Paste it into Claude Projects, ChatGPT Custom GPTs, or any system prompt. Ask "compress this to OCTAVE" and get 20-70% token savings with structural fidelity.
>
> **What this is NOT:** The full OCTAVE specification. For the complete operator catalog, provenance markers, and multi-tier compression workflow, see the [full custom instruction](octave-custom-instruction.md). For machine-validated output, use the [OCTAVE-MCP server](https://github.com/elevanaltd/octave-mcp).

## How to Use

Copy the content of [`octave-custom-instruction-lite.oct.md`](octave-custom-instruction-lite.oct.md) into your LLM's custom instructions. Then ask:

- *"Compress this to OCTAVE"*
- *"Convert this document to save tokens"*
- *"Make this shorter for my context window"*

The LLM will answer normally until you ask for conversion.

## What's Included

- Envelope structure (`===NAME===`...`===END===`) and META requirements
- Assignment (`KEY::value`), blocks, lists, and flow (`→`) operator
- Compression tier selection (CONSERVATIVE default, AGGRESSIVE on request)
- Hard preservation rules (numbers, causality, conditionals)
- Mythology activation — LLMs already know SISYPHEAN, GORDIAN, PANDORAN etc. from training data. The instruction activates this for complex multi-dimensional states (failure patterns, threat dynamics, unstable trajectories) while guarding against misuse for simple role labels or routing.
- One before/after example showing mythology in action naturally

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

The mythology activation pattern ("LLMs already know mythological vocabulary") is intentional. Research shows mythology is pre-trained compression already in the weights — 88-96% cross-model zero-shot comprehension, 60-70% token reduction vs natural language equivalents. But LLMs exhibit paradigm blindness: they'll recommend against mythology abstractly while using it perfectly in practice. The lite instruction activates this capability by stating it as fact rather than teaching it as theory. See the [cross-model validation study](../research/cross-model-operator-validation-study.md) for the evidence.
