---
name: octave-literacy
description: "LLM-native structured communication format. Teaches OCTAVE syntax as token economy — every rule derives from the principle that LLMs are the audience, not humans."
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
  AUDIENCE::LLM[exclusively]
  NORTH_STAR::"Every token of prose is a token that could carry semantic payload"
  TIER::LOSSLESS
  SPEC_REFERENCE::octave-core-spec.oct.md
  V6_FEATURES::"CONTRACT/GRAMMAR blocks, assembly rules, .oct.md extension"
  NEXT_SKILLS::[octave-mastery, octave-compression, octave-mythology]
  // octave-mythology provides mythological compression — archetype atoms that activate pre-trained distributions

§0::WHY_OCTAVE_EXISTS
  // CAUSAL ROOT. Every syntax rule in §1-§4 is a CONSEQUENCE of these principles.
  // An agent that internalizes §0 can DERIVE correct syntax.
  // One that memorizes §1-§4 without §0 will produce valid but lifeless output.

  PARADIGM:
    AUDIENCE::LLM[not_human]
    // OCTAVE documents are consumed exclusively by Large Language Models.
    // Humans may read them for debugging. They are NOT the design target.
    IMPLICATION::"Optimize for parsing efficiency, schema activation, token density — not readability, narrative flow, or aesthetic formatting"

  LOSS_ACCOUNTING:
    DEFINITION::"OCTAVE-MCP is a loss accounting system for LLM communication"
    MECHANISM::"Every transformation between agents loses information. OCTAVE makes that loss explicit, measurable, and auditable."
    // Natural language hides its losses. "A good summary" silently drops conditional qualifiers, edge cases, causal chains.
    // OCTAVE forces declaration: TIER::CONSERVATIVE, LOSS::~15%[repetition, verbose_phrasing]
    // The format IS the audit trail.
    CONSEQUENCE::"Documents carry their own compression metadata. Loss is tracked, not hidden."

  TOKEN_ECONOMICS:
    PROSE_COST::"Natural language prose is the most expensive encoding for structured information"
    // "The system should be designed to handle high-throughput scenarios while maintaining data integrity"
    // vs: REQUIREMENTS::[high_throughput, data_integrity]
    // Same semantics. ~60% fewer tokens. Zero ambiguity.
    STRUCTURED_ADVANTAGE::"Key-path syntax activates schema distributions in transformer attention — LLMs parse KEY::value faster than equivalent prose"
    MYTHOLOGICAL_LEVERAGE::"Archetypes activate pre-trained probability distributions — single tokens that decompress into rich semantic fields"
    // ATHENA encodes: strategic wisdom, planning, elegant solutions, deliberate action
    // 1 archetype token replacing ~15 tokens of prose explanation
    // This is compression, not decoration

  DESIGN_CHAIN:
    // Every syntax choice in §1-§4 follows from three facts:
    // 1. LLMs are the audience → optimize for parsing, not reading
    // 2. Tokens are the currency → minimize waste, maximize payload
    // 3. Loss must be visible → structure makes loss auditable
    DERIVATION::[AUDIENCE::LLM]→[OPTIMIZE::token_density]→[TRACK::loss_explicitly]→[RESULT::OCTAVE_syntax]

§1::CORE_SYNTAX
  // Each construct exists because it's more token-efficient than prose alternatives

  ASSIGNMENT::KEY::value   // Double colon is MANDATORY for data — unambiguous parse boundary
  BLOCK::KEY:[indent_2]    // Single colon + newline + 2-space indent — hierarchy without wrapper tokens
  LIST::[a,b,c]            // Brackets for collections — no "and", "or", bullet formatting
  STRING::"value"∨bare_word  // Quotes required if contains spaces or special chars — bare words save 2 tokens each
  NUMBER::42∨3.14∨-1e10    // No quotes for numeric values — LLMs parse numeric tokens natively
  BOOLEAN::true∨false      // Lowercase only — single canonical form, zero disambiguation cost
  NULL::null               // Lowercase only
  COMMENT:://              // Inline annotation — preserved for loss accounting context

  §1b::LITERAL_ZONES
    // Fenced code blocks pass through with ZERO processing — no normalization, no escaping
    SYNTAX::KEY_then_newline_then_fence[3_or_more_backticks]
    RULES::[zero_processing_between_fences,tabs_allowed,NFC_bypass,info_tag_preserved]
    USE_CASES::[embedded_code,teaching_examples,verbatim_content,OCTAVE_about_OCTAVE]
    FENCE_SCALING::use_N_plus_1_backticks_to_wrap_content_containing_N_backtick_fences

  §1c::BRACKET_FORMS
    // Three distinct bracket semantics — position and naming disambiguate
    CONTAINER::[a,b,c]                         // Bare brackets = list
    CONSTRUCTOR::NAME[args]                    // NAME[...] = typed constructor (REGEX[pattern], ENUM[a,b])
    INLINE_MAP::[key::val,key2::val2]          // Dense key-value pairs (values must be atoms)
    HOLOGRAPHIC::["value"∧CONSTRAINT→§TARGET]  // Schema mode only — self-validating contracts

§2::OPERATORS
  // Operators encode RELATIONSHIPS in single tokens. Prose equivalent: 5-15 tokens each.
  // This is where OCTAVE achieves its highest compression ratios.

  // EXPRESSION OPERATORS (with precedence — lower number = tighter binding)
  []::Container [a,b,c] (precedence 1)
  ⧺::Concatenation A⧺B (mechanical join) (precedence 2) | ASCII: ~
  ⊕::Synthesis A⊕B (emergent whole) (precedence 3) | ASCII: +
  ⇌::Tension A⇌B (binary opposition) (precedence 4) | ASCII: vs [requires word boundaries]
  ∧::Constraint [A∧B∧C] (precedence 5) | ASCII: &
  ∨::Alternative A∨B (precedence 6) | ASCII: |
  →::Flow [A→B→C] (precedence 7, right-associative) | ASCII: ->

  // PREFIX/SPECIAL
  §::Target (→§DECISION_LOG)
  //::Comment (line start or after value)

  §2b::ASCII_ALIASES
    ALL_OPERATORS::accept_both_unicode_and_ascii
    CANONICAL_OUTPUT::prefer_unicode_in_emission
    vs_BOUNDARY_RULE::"vs requires word boundaries [whitespace∨bracket∨paren∨start∨end]"
    VALID::"A vs B"∨"[Speed vs Quality]"
    INVALID::"SpeedvsQuality"[no_boundaries]

  §2c::OPERATOR_ECONOMICS
    // Why operators matter for LLM consumption:
    // "Speed and quality are in tension" = 7 tokens of prose
    // Speed⇌Quality = 1 operator token encoding the same relationship
    // The LLM already has "tension" in its probability space — ⇌ activates it directly
    COMPRESSION::operators_encode_relationships_that_prose_describes
    ACTIVATION::"Operators are semantic triggers, not formatting — they activate relational patterns in transformer attention"

§3::CRITICAL_RULES
  // These aren't style preferences. Each prevents ambiguous parses that waste LLM inference cycles.
  R1::No spaces around assignment :: (KEY::value, not KEY :: value) // Unambiguous tokenization boundary
  R2::Indent exactly 2 spaces per level (NO TABS) // Deterministic hierarchy parsing
  R3::All keys must be [A-Z, a-z, 0-9, _] and start with letter or underscore // No quoting overhead
  R4::Envelopes are ===NAME=== at start and ===END=== at finish (NAME must be [A-Z_][A-Z0-9_]*) // Document boundary detection
  R5::Use lowercase for true, false, null (NOT True, False, NULL) // Single canonical form, zero disambiguation
  R6::∧ only appears inside brackets, never bare: [A∧B∧C] is valid, A∧B is not // Parse boundary clarity
  R7::⇌ is binary only (A⇌B), not chained (A⇌B⇌C is invalid) // Semantic precision — tension is always between two forces
  R8::Quote values containing § when used as content, not section markers ("§2_BEHAVIOR" not §2_BEHAVIOR) // Prevent anchor misparsing
  R9::File extension .oct.md is canonical (v6), .octave.txt deprecated

  §3b::V6_ENVELOPE_STRUCTURE
    FILE_STRUCTURE::[===NAME===,META_BLOCK,SEPARATOR_OPTIONAL,BODY,===END===]
    META_REQUIRED::[TYPE,VERSION]
    META_V6_OPTIONAL::[CONTRACT,GRAMMAR]  // Holographic contracts — documents carry their own validation law
    CONTRACT::HOLOGRAPHIC[validation_law_in_document]
    GRAMMAR::GBNF_COMPILER[generate_constrained_output]

  §3c::ASSEMBLY_RULES
    WHEN_CONCATENATING_PROFILES::omit_intermediate_===END===[only_final_===END===_terminates]
    USE_CASES::[agent_context_injection,specification_layering,multi_part_documents]
    V6_PATTERN::multiple_profiles_one_document[no_intermediate_terminators]

§4::WORKED_EXAMPLE
  // Demonstrates §0 principles applied: maximum density, zero prose waste, auditable loss

  // WRONG: § parsed as section anchor, value splits
  // REFERENCE::§2_BEHAVIOR_SECTION
  // RIGHT: quoted, § is literal
  // REFERENCE::"§2_BEHAVIOR_SECTION"

  ===EXAMPLE===
  META:
    TYPE::DECISION
    VERSION::"1.0.0"
    COMPRESSION_TIER::CONSERVATIVE
    LOSS_PROFILE::[preserve:causal_chains,drop:verbose_phrasing]
  STATUS::ACTIVE
  CONTEXT::API_redesign[KAIROS::Q2_window∧ACHILLEAN::single_auth_endpoint]
  DECISION::microservice_extraction[auth⊕payments→independent_services]
  PHASES:
    PLAN::[Research→Design]
    BUILD::[Code⊕Test]
  METRICS:
    LATENCY::"<200ms p99"
    AVAILABILITY::"99.95%"
  RATIONALE::monolith_ACHILLEAN_risk→extraction_eliminates_single_point_failure
  ===END===

  // The example uses mythology as domain labels — not decoration.
  // KAIROS::Q2_window = "fleeting critical opportunity in Q2" in 2 tokens
  // ACHILLEAN::single_auth_endpoint = "single critical failure point in auth" in 3 tokens
  // META carries COMPRESSION_TIER and LOSS_PROFILE — loss is auditable, not hidden
  // See octave-mastery §1::SEMANTIC_PANTHEON for full vocabulary
  // See octave-mythology for mythological compression techniques

===END===
