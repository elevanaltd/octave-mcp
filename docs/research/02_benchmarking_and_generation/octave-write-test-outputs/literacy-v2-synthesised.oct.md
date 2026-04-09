---
name: octave-literacy
description: "LLM-native structured communication format. Teaches OCTAVE syntax as token economy — every rule derives from the principle that LLMs are the exclusive audience."
allowed-tools: ["Read", "Write", "Edit"]
triggers: ["octave format", "write octave", "octave syntax", "structured output", "OCTAVE basics", "OCTAVE literacy", "OCTAVE structure", "semantic format", "key::value", "OCTAVE notation", "llm communication", "token economy", "loss accounting"]
version: "2.0.0"
---

===OCTAVE_LITERACY===
META:
  TYPE::SKILL
  VERSION::"2.0.0"
  STATUS::ACTIVE
  PURPOSE::"OCTAVE syntax as token economy — structured encoding for LLM-to-LLM communication"
  OCTAVE::"Olympian Common Text And Vocabulary Engine — loss accounting system for LLM communication"
  AUDIENCE::LLM<exclusively>
  NORTH_STAR::"Every token of prose is a token that could carry semantic payload"
  TIER::LOSSLESS
  SPEC_REFERENCE::octave-core-spec.oct.md
  V6_FEATURES::"CONTRACT/GRAMMAR blocks, assembly rules, .oct.md extension"
  NEXT_SKILLS::[octave-mastery,octave-compression]
§0::WHY_OCTAVE_EXISTS
  // CAUSAL ROOT. Every syntax rule in §1-§4 is a CONSEQUENCE of these principles.
  // An agent that internalizes §0 can DERIVE correct syntax.
  PARADIGM:
    AUDIENCE::LLM<not_human>
    // OCTAVE documents are consumed exclusively by Large Language Models.
    // Humans may read them for debugging. They are NOT the design target.
    IMPLICATION::"Optimize for parsing efficiency, schema activation, token density — not readability, narrative flow, or aesthetic formatting"
  LOSS_ACCOUNTING:
    DEFINITION::"OCTAVE-MCP is a loss accounting system for LLM communication"
    MECHANISM::"Every transformation between agents loses information. OCTAVE makes that loss explicit, measurable, and auditable."
    // Natural language hides its losses. OCTAVE forces declaration: TIER::CONSERVATIVE, LOSS::~15%
    CONSEQUENCE::"Documents carry their own compression metadata. Loss is tracked, not hidden."
  TOKEN_ECONOMICS:
    PROSE_COST::"Natural language prose is the most expensive encoding for structured information"
    // Prose: "The system should handle high-throughput scenarios while maintaining data integrity"
    // OCTAVE: REQUIREMENTS::[high_throughput, data_integrity]
    // Same semantics. ~60% fewer tokens. Zero ambiguity.
    STRUCTURED_ADVANTAGE::"Key-path syntax activates schema distributions in transformer attention"
  MYTHOLOGY_RATIONALE:
    // Mythological terms are functional semantic compression — not decoration
    MECHANISM::"Mythology = pre-trained compression already in the weights, activating rich probability distributions"
    // ATHENA encodes: strategic wisdom, planning, elegant solutions — 1 token replacing ~15
    RULE::"Use mythology when it adds behavioral dimensions the literal term loses. Otherwise use the literal."
    ANTI_PATTERN::"ZEUS::executive_decision — use EXECUTIVE::decision when literal is equally clear"
    // Full vocabulary: octave-mastery §1; Usage techniques: octave-mythology skill
  DESIGN_CHAIN:
    // Every syntax choice follows from: audience → currency → auditability
    DERIVATION::"[AUDIENCE::LLM] → [OPTIMIZE::token_density] → [TRACK::loss_explicitly] → [RESULT::OCTAVE_syntax]"
§1::CORE_SYNTAX
  // Each construct exists because it is more token-efficient than prose alternatives
  ASSIGNMENT::"KEY::value — double colon MANDATORY, unambiguous parse boundary"
  BLOCK::"KEY: followed by newline + 2-space indent — hierarchy without wrapper tokens"
  LIST::"[a,b,c] — brackets for collections, no bullet formatting needed"
  STRING::"quoted with double-quotes if contains spaces or special chars, bare_word otherwise"
  NUMBER::"42 or 3.14 or -1e10 — no quotes, LLMs parse numeric tokens natively"
  BOOLEAN::"true or false — lowercase only, single canonical form"
  NULL_VALUE::"null — lowercase only"
  COMMENT::"// — inline annotation, preserved for loss accounting context"
  §1b::LITERAL_ZONES
    // Fenced code blocks pass through with ZERO processing
    SYNTAX::"KEY then newline then fence of 3+ backticks"
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
    CONSTRUCTOR::"NAME[args] — typed constructor e.g. REGEX[pattern], ENUM[a,b]"
    INLINE_MAP::"[key::val, key2::val2] — dense key-value pairs, values must be atoms"
    HOLOGRAPHIC::"schema mode only — self-validating contracts, see octave-mastery §4b"
§2::OPERATORS
  // Operators encode RELATIONSHIPS in single tokens. Prose equivalent: 5-15 tokens each.
  // EXPRESSION OPERATORS — precedence: lower number = tighter binding
  PREC_1::"[] — Container [a,b,c]"
  PREC_2::"⧺ — Concatenation A⧺B, mechanical join | ASCII: ~"
  PREC_3::"⊕ — Synthesis A⊕B, emergent whole | ASCII: +"
  PREC_4::"⇌ — Tension A⇌B, binary opposition | ASCII: vs (requires word boundaries)"
  PREC_5::"∧ — Constraint [A∧B∧C], inside brackets only | ASCII: &"
  PREC_6::"∨ — Alternative A∨B | ASCII: |"
  PREC_7::"→ — Flow [A→B→C], right-associative | ASCII: ->"
  // PREFIX/SPECIAL
  SECTION_REF::"§ — target anchor for cross-references"
  LINE_COMMENT::"// — line start or after value"
  §2b::ASCII_ALIASES
    ALL_OPERATORS::accept_both_unicode_and_ascii
    CANONICAL_OUTPUT::prefer_unicode_in_emission
    vs_BOUNDARY_RULE::"vs requires word boundaries: 'A vs B' valid, 'AvsB' invalid"
  §2c::OPERATOR_ECONOMICS
    // Why operators matter for LLM consumption:
    // Prose: "Speed and quality are in tension" = 7 tokens
    // OCTAVE: Speed⇌Quality = 1 operator encoding the same relationship
    COMPRESSION::operators_encode_relationships_that_prose_describes
    ACTIVATION::"Operators are semantic triggers — they activate relational patterns in transformer attention"
§3::CRITICAL_RULES
  // These prevent ambiguous parses that waste LLM inference cycles.
  R1::"No spaces around :: assignment operator (KEY::value not KEY :: value)"
  R2::"Indent exactly 2 spaces per level — NO TABS"
  R3::"All keys must match [A-Za-z_][A-Za-z0-9_]* — start with letter or underscore"
  R4::"Envelopes: ===NAME=== at start, ===END=== at finish (NAME must be [A-Z_][A-Z0-9_]*)"
  R5::"Use lowercase for true, false, null (NOT True, False, NULL)"
  R6::"Constraint ∧ only inside brackets: [A∧B∧C] valid, bare A∧B invalid"
  R7::"Tension ⇌ is binary only: A⇌B valid, chained A⇌B⇌C invalid"
  R8::"Quote values containing § when used as content, not as section markers"
  R9::"File extension .oct.md is canonical (v6)"
  §3b::V6_ENVELOPE_STRUCTURE
    FILE_STRUCTURE::"===NAME=== then META_BLOCK then optional --- separator then BODY then ===END==="
    META_REQUIRED::[TYPE,VERSION]
    META_V6_OPTIONAL::[CONTRACT,GRAMMAR]
    CONTRACT::HOLOGRAPHIC<validation_law_in_document>
    GRAMMAR::GBNF_COMPILER<generate_constrained_output>
  §3c::ASSEMBLY_RULES
    RULE::"When concatenating profiles, omit intermediate ===END=== — only final one terminates"
    USE_CASES::[
      agent_context_injection,
      specification_layering,
      multi_part_documents
    ]
    V6_PATTERN::multiple_profiles_one_document<no_intermediate_terminators>
§4::WORKED_EXAMPLE
  // Demonstrates §0 principles: density, zero prose waste, auditable loss
  // Note: § in values must be quoted to prevent section anchor parsing
  EXAMPLE:
    ```
===EXAMPLE===
META:
  TYPE::DECISION
  VERSION::"1.0.0"
  COMPRESSION_TIER::CONSERVATIVE
  LOSS_PROFILE::[preserve:causal_chains,drop:verbose_phrasing]
STATUS::ACTIVE
CONTEXT::API_redesign[KAIROS::Q2_window]
DECISION::microservice_extraction[auth+payments->independent_services]
PHASES:
  PLAN::[Research->Design]
  BUILD::[Code+Test]
METRICS:
  LATENCY::"<200ms p99"
  AVAILABILITY::"99.95%"
===END===
    ```
  // KAIROS::Q2_window = "fleeting critical opportunity in Q2" — 2 tokens
  // META carries COMPRESSION_TIER and LOSS_PROFILE — loss is auditable, not hidden
===END===
