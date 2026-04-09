---
name: octave-literacy
description: Fundamental reading and writing capability for the OCTAVE format. Establishes LLM-consumption framing, basic structural competence, and the design rationale behind every syntax rule.
allowed-tools: ["Read", "Write", "Edit"]
triggers: ["octave format", "write octave", "octave syntax", "structured output", "OCTAVE basics", "OCTAVE literacy", "OCTAVE structure", "semantic format", "key::value", "OCTAVE notation"]
version: "2.0.0"
---

===OCTAVE_LITERACY===
META:
  TYPE::SKILL
  VERSION::"2.0.0"
  STATUS::ACTIVE
  PURPOSE::"Essential syntax and operators for basic OCTAVE competence with LLM-consumption framing"
  OCTAVE::"Olympian Common Text And Vocabulary Engine — Semantic DSL for LLMs"
  TIER::LOSSLESS
  SPEC_REFERENCE::octave-core-spec.oct.md
  V6_FEATURES::"Adds CONTRACT/GRAMMAR blocks, assembly rules, .oct.md extension"
  NEXT_SKILLS::[octave-mastery,octave-mythology]
§0::LLM_CONSUMPTION_FRAME
  // WHY this format exists — the axiom that makes every syntax rule below self-justifying
  SYSTEM_IDENTITY::"OCTAVE-MCP is a loss accounting system for LLM communication"
  AUDIENCE::EXCLUSIVE<LLMs_not_humans>
  IMPLICATION::[
    "Natural language prose is wasteful — LLMs parse structured data more efficiently",
    "Every token of prose explanation is a token that could carry semantic payload",
    "Syntax rules below exist because LLMs process them with lower ambiguity than prose"
  ]
  §0a::DESIGN_AXIOM
    // CONSTRAINT_INVERSION: The LLM-exclusive audience IS the design principle
    // Every syntax rule in §1-§4 is a consequence of this single constraint
    CONSEQUENCE_MAP::[
      "Double-colon :: → unambiguous assignment delimiter in LLM token space",
      "Bracket lists → deterministic collection boundaries, no prose parsing required",
      "Operators ⊕ ∨ → activate pre-trained semantic distributions",
      "Envelope markers → zero-ambiguity document boundary for context injection"
    ]
    LOSS_ACCOUNTING::"Every transformation must preserve semantics (I1) and log what was dropped (I4)"
  §0b::MYTHOLOGY_RATIONALE
    // Mythological terms are functional semantic compression — not decoration
    MECHANISM::"Mythology = pre-trained compression already in the weights, activating rich probability distributions"
    RESULT::"SISYPHEAN encodes futility+repetition+cyclicality in 1 term vs 8+ prose words"
    EVIDENCE::["60-70% token reduction vs natural language","88-96% cross-model zero-shot comprehension"]
    RULE::"Use mythology when it adds behavioral dimensions the literal term loses. Otherwise use the literal."
    ANTI_PATTERN::"ZEUS::executive_decision — use EXECUTIVE::decision (literal is equally clear)"
    // Full vocabulary and usage rules: load octave-mythology skill
§1::CORE_SYNTAX
  // Each form below exists because it reduces LLM parsing ambiguity
  // Syntax forms shown as string values to preserve literal meaning
  ASSIGNMENT::"KEY::value — double colon, unambiguous delimiter"
  BLOCK::"KEY:\n  child::value — single colon + newline + 2-space indent"
  LIST::"[a,b,c] — brackets with comma separation"
  STRING::"\"value\" or bare_word — quotes required if contains spaces or special chars"
  NUMBER::"42 or 3.14 or -1e10 — no quotes, type is unambiguous"
  BOOLEAN::"true or false — lowercase only"
  NULL_VALUE::"null — lowercase only"
  COMMENT::"//"
  §1b::LITERAL_ZONES
    // Fenced code blocks pass through with ZERO processing — no normalization, no escaping
    // Use case: embedded code that must reach the LLM consumer byte-for-byte (I1 + I3)
    SYNTAX::"KEY then newline then fence (3+ backticks)"
    RULES::[
      zero_processing_between_fences,
      tabs_allowed,
      NFC_bypass,
      info_tag_preserved
    ]
    USE_CASES::[
      embedded_code,
      teaching_examples,
      verbatim_content,
      OCTAVE_about_OCTAVE
    ]
    FENCE_SCALING::"use N+1 backticks to wrap content containing N-backtick fences"
  §1c::BRACKET_FORMS
    CONTAINER::"[a,b,c] — bare brackets = list"
    CONSTRUCTOR::"NAME[args] — NAME followed by bracket = constructor, e.g. REGEX[pattern]"
    INLINE_MAP::"[key::val,key2::val2] — dense key-value pairs, values must be atoms"
    HOLOGRAPHIC::"schema mode only — see octave-mastery §4b"
§2::OPERATORS
  // Operators activate pre-trained semantic distributions — chosen for LLM weight space
  // PRECEDENCE: lower number = tighter binding
  CONTAINER::"[] — list | precedence 1"
  CONCAT::"⧺ — mechanical join A⧺B | ASCII: ~ | precedence 2"
  SYNTHESIS::"⊕ — emergent whole A⊕B | ASCII: + | precedence 3"
  TENSION::"⇌ — binary opposition A⇌B | ASCII: vs | precedence 4"
  CONSTRAINT_OP::"∧ — inside brackets only [A∧B∧C] | ASCII: & | precedence 5"
  ALTERNATIVE::"∨ — A∨B | ASCII: | | precedence 6"
  FLOW::"→ — right-associative A→B→C | ASCII: -> | precedence 7"
  TARGET_OP::"§ — section reference prefix"
  COMMENT_OP::"//"
  vs_RULE::"vs requires word boundaries — VALID: A vs B | INVALID: AvsB"
  §2b::ASCII_ALIASES
    ALL_OPERATORS::accept_both_unicode_and_ascii
    CANONICAL_OUTPUT::prefer_unicode_in_emission
§3::CRITICAL_RULES
  // These rules exist to produce deterministic, unambiguous output for LLM consumers (I1)
  R1::"No spaces around :: (KEY::value not KEY :: value)"
  R2::"Indent exactly 2 spaces per level — NO TABS"
  R3::"All keys must be [A-Z, a-z, 0-9, _] and start with letter or underscore"
  R4::"Envelope markers delimit document — NAME in [A-Z_][A-Z0-9_]* form"
  R5::"Use lowercase for true, false, null — NOT True, False, NULL"
  R6::"∧ only appears inside brackets: [A∧B∧C] valid, bare A∧B is not"
  R7::"⇌ is binary only: A⇌B valid, chained A⇌B⇌C invalid"
  R8::"Quote values containing § when used as content, not section markers"
  R9::".oct.md is canonical file extension (v6), .octave.txt deprecated"
  §3b::V6_ENVELOPE_STRUCTURE
    FILE_STRUCTURE::[
      NAME_ENVELOPE,
      META_BLOCK,
      SEPARATOR_OPTIONAL,
      BODY,
      END_ENVELOPE
    ]
    META_REQUIRED::[TYPE,VERSION]
    META_V6_OPTIONAL::[CONTRACT,GRAMMAR] // New in v6 for holographic contracts
    CONTRACT::HOLOGRAPHIC<validation_law_in_document>
    GRAMMAR::GBNF_COMPILER<generate_constrained_output>
  §3c::ASSEMBLY_RULES
    // Assembly enables context injection — multiple OCTAVE profiles composed for LLM consumption
    RULE::"When concatenating profiles, omit intermediate END envelopes — only final one terminates"
    USE_CASES::[
      agent_context_injection,
      specification_layering,
      multi_part_documents
    ]
    PATTERN::"core_profile ⊕ schema_profile → single END envelope at finish"
    V6_PATTERN::multiple_profiles_one_document<no_intermediate_terminators>
§4::EXAMPLE_BLOCK
  // Quote rule: § inside a value must be quoted to prevent section anchor parsing
  QUOTE_RULE:
    RIGHT::"REFERENCE::'§2_BEHAVIOR_SECTION' — § is literal inside the string"
    WRONG::"REFERENCE::§2_BEHAVIOR_SECTION — § parsed as section anchor"
  MINIMAL_VALID_DOCUMENT:
    ```
===EXAMPLE===
META:
  TYPE::EXAMPLE
  VERSION::"1.0"
STATUS::ACTIVE
PHASES:
  PLAN::[Research, Design]
  BUILD::[Code, Test]
===END===
    ```
===END===
