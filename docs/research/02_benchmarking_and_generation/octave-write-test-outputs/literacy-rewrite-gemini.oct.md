---
name: octave-literacy
description: Fundamental reading and writing capability for the OCTAVE format. Basic structural competence without full architectural specifications
allowed-tools: ["Read", "Write", "Edit"]
triggers: ["octave format", "write octave", "octave syntax", "structured output", "OCTAVE basics", "OCTAVE literacy", "OCTAVE structure", "semantic format", "key::value", "OCTAVE notation"]
version: "1.6.0"
---

===OCTAVE_LITERACY===
META:
  TYPE::SKILL
  VERSION::"1.6.0"
  STATUS::ACTIVE
  PURPOSE::"Essential syntax and operators for basic OCTAVE competence"
  OCTAVE::"Olympian Common Text And Vocabulary Engine — Semantic DSL for LLMs"
  TIER::LOSSLESS
  SPEC_REFERENCE::octave-core-spec.oct.md
  V6_FEATURES::"Adds CONTRACT/GRAMMAR blocks, assembly rules, .oct.md extension"
  NEXT_SKILLS::[octave-mastery,octave-mythology]
§0::LLM_CONSUMPTION_PARADIGM
  AUDIENCE::"OCTAVE documents are consumed exclusively by LLMs, not humans"
  NORTH_STAR::"OCTAVE-MCP is a loss accounting system for LLM communication"
  CORE_TENETS:
    PROSE_IS_WASTE::"Natural language prose is wasteful — LLMs parse structured data more efficiently"
    TOKEN_ECONOMY::"Every token of prose explanation is a token that could carry semantic payload"
    MYTHOLOGICAL_LEVERAGE::"Mythological archetypes activate pre-trained probability distributions — use them as semantic compression, not decoration"
    GOAL::"Maximum information density with zero ambiguity"
§1::CORE_SYNTAX
  ASSIGNMENT::"KEY::value"
  BLOCK::"KEY:[indent_2]"
  LIST::"[a,b,c]"
  STRING::"\"value\"∨bare_word"
  NUMBER::"42∨3.14∨-1e10"
  BOOLEAN::true∨false
  NULL::"null"
  COMMENT::"//"
  §1b::LITERAL_ZONES
    SYNTAX::"KEY_then_newline_then_fence[3_or_more_backticks]"
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
    FENCE_SCALING::use_N_plus_1_backticks_to_wrap_content_containing_N_backtick_fences
  §1c::BRACKET_FORMS
    CONTAINER::"[a,b,c]"
    CONSTRUCTOR::"NAME[args]"
    INLINE_MAP::"[key::val,key2::val2]"
    HOLOGRAPHIC::"[\"value\"∧CONSTRAINT→\"§TARGET\"]"
§2::OPERATORS
  OP_CONTAINER::"[] Container [a,b,c] (precedence 1)"
  OP_CONCAT::"⧺ Concatenation A⧺B (mechanical join) (precedence 2) | ASCII: ~"
  OP_SYNTHESIS::"⊕ Synthesis A⊕B (emergent whole) (precedence 3) | ASCII: +"
  OP_TENSION::"⇌ Tension A⇌B (binary opposition) (precedence 4) | ASCII: vs [requires word boundaries]"
  OP_CONSTRAINT::"∧ Constraint [A∧B∧C] (precedence 5) | ASCII: &"
  OP_ALTERNATIVE::"∨ Alternative A∨B (precedence 6) | ASCII: |"
  OP_FLOW::"→ Flow [A→B→C] (precedence 7, right-associative) | ASCII: ->"
  OP_TARGET::"§ Target (→\"§DECISION_LOG\")"
  OP_COMMENT::"// Comment (line start or after value)"
  §2b::ASCII_ALIASES
    ALL_OPERATORS::accept_both_unicode_and_ascii
    CANONICAL_OUTPUT::prefer_unicode_in_emission
    vs_BOUNDARY_RULE::"vs requires word boundaries [whitespace∨bracket∨paren∨start∨end]"
    VALID::"A vs B ∨ [Speed vs Quality]"
    INVALID::"SpeedvsQuality [no_boundaries]"
§3::CRITICAL_RULES
  RULE_1::"No spaces around assignment :: (KEY::value, not KEY :: value)"
  RULE_2::"Indent exactly 2 spaces per level (NO TABS)"
  RULE_3::"All keys must be [A-Z, a-z, 0-9, _] and start with letter or underscore"
  RULE_4::"Envelopes are ===NAME=== at start and ===END=== at finish (NAME must be [A-Z_][A-Z0-9_]*)"
  RULE_5::"Use lowercase for true, false, null (NOT True, False, NULL)"
  RULE_6::"∧ only appears inside brackets, never bare: [A∧B∧C] is valid, A∧B is not"
  RULE_7::"⇌ is binary only (A⇌B), not chained (A⇌B⇌C is invalid)"
  RULE_8::"Quote values containing § when used as content, not section markers"
  RULE_9::"File extension .oct.md is canonical (v6), .octave.txt deprecated"
  §3b::V6_ENVELOPE_STRUCTURE
    FILE_STRUCTURE::[
      "===NAME===",
      META_BLOCK,
      SEPARATOR_OPTIONAL,
      BODY,
      "===END==="
    ]
    META_REQUIRED::[TYPE,VERSION]
    META_V6_OPTIONAL::[CONTRACT,GRAMMAR]
    CONTRACT::"HOLOGRAPHIC[validation_law_in_document]"
    GRAMMAR::"GBNF_COMPILER[generate_constrained_output]"
  §3c::ASSEMBLY_RULES
    WHEN_CONCATENATING_PROFILES::"omit_intermediate_===END===[only_final_===END===_terminates]"
    USE_CASES::[
      agent_context_injection,
      specification_layering,
      multi_part_documents
    ]
    EXAMPLE::"[core_profile⊕schema_profile→single_===END===_at_finish]"
    V6_PATTERN::"multiple_profiles_one_document[no_intermediate_terminators]"
§4::EXAMPLE_BLOCK
STATUS::ACTIVE
PHASES:
  PLAN::"[Research → Design]"
  BUILD::"[Code ⊕ Test]"
METRICS:
  SPEED::High
  QUALITY::Verified
===END===
