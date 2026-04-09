---
name: octave-literacy
description: Fundamental reading and writing capability for the OCTAVE format. LLM-native syntax for maximum information density and zero ambiguity.
allowed-tools: ["Read", "Write", "Edit"]
triggers: ["octave format", "write octave", "octave syntax", "structured output", "OCTAVE basics", "OCTAVE literacy", "OCTAVE structure", "semantic format", "key::value", "OCTAVE notation", "llm communication", "information density"]
version: "2.0.0"
---

===OCTAVE_LITERACY===
META:
  TYPE::SKILL
  VERSION::"2.0.0"
  STATUS::ACTIVE
  AUDIENCE::"Language Models exclusively"
  PURPOSE::"OCTAVE is a loss accounting system for LLM communication. Syntax transforms wasteful prose into structured semantic payloads. Every token carries information."
  OCTAVE::"Olympian Common Text And Vocabulary Engine"
  TIER::LOSSLESS
  SPEC_REFERENCE::octave-core-spec.oct.md
  V6_FEATURES::"CONTRACT/GRAMMAR blocks, assembly rules, .oct.md extension"
  NEXT_SKILLS::[octave-mastery,octave-compression]

§0::LLM_CONSUMPTION_PARADIGM
  // OCTAVE redesign: natural language is inefficient for LLM consumption
  NORTH_STAR::"OCTAVE-MCP is a loss accounting system for LLM communication"

  INEFFICIENCY_OF_PROSE::[
    "Natural language requires disambiguation at inference time",
    "Prose creates ambiguity in scope, reference, and implication",
    "Each word is serial; LLM reads left-to-right through scaffolding",
    "Token cost: explanatory + overhead = wasted budget"
  ]

  EFFICIENCY_OF_STRUCTURE::[
    "KEY::value declares relationship upfront — no inference needed",
    "Indentation shows hierarchy — no ambiguous prepositions",
    "Operators compress relationships into single tokens",
    "Token cost: structure + payload = dense output"
  ]

  CONSEQUENCE::[
    "40-80% fewer tokens for equivalent semantic content",
    "Pre-trained LLM distributions activate on structured patterns",
    "Mythological archetypes encode domains instantly",
    "Zero ambiguity means zero inference cost for readers"
  ]

§1::CORE_SYNTAX
  // Every rule minimizes ambiguity and token overhead
  ASSIGNMENT::"KEY::value declares binding, not phrase"
  BLOCK::"KEY: newline, indent 2 spaces — creates hierarchy without nesting overhead"
  LIST::"[a,b,c] — brackets distinguish structures from prose"
  STRING::"\"value\" or bare_word — quotes signal atomicity; bare words compress"
  NUMBER::"42, 3.14, -1e10 — no quotes; type clarity prevents drift"
  BOOLEAN::"true or false — lowercase ensures consistency"
  NULL::"null — explicit null carries semantic information"
  COMMENT::"// — educate readers without inflating payload"

  §1b::LITERAL_ZONES
    SYNTAX::"KEY, newline, then three or more backticks"
    PROCESSING::"Zero processing between fences"
    GUARANTEE::[bytes_preserved, tabs_allowed, normalization_bypassed]
    USE::[embedded_code, teaching_examples, external_syntax]
    REASON::"Allow arbitrary content without escaping overhead"

  §1c::BRACKET_FORMS
    CONTAINER::"[a,b,c] — bare list, elements are atoms"
    CONSTRUCTOR::"NAME[args] — signals semantic intent without extra tokens"
    INLINE_MAP::"[key::val, key2::val2] — encode relationships in one line"
    HOLOGRAPHIC::"[value ∧ CONSTRAINT → reference] — schema mode for LLM validation"

§2::OPERATORS
  // Operators compress relationships into single tokens
  SEMANTICS_OF_DISTINCTIONS::[
    "⊕_vs_⧺: synthesis (emergent whole) versus mechanical join — different inference paths",
    "⇌_vs_∨: tension (opposing forces) versus choice (pick one) — distinct distributions",
    "→_vs_⊕: causality (A causes B) versus integration (synthesis) — dependency guidance"
  ]

  OPERATOR_TABLE:
    CONTAINERS::"[]"
    MECHANICAL_JOIN::"⧺ or ~"
    SYNTHESIS::"⊕ or +"
    TENSION::"⇌ or vs (word boundaries required)"
    CONJUNCTION::"∧ or & (only inside brackets)"
    ALTERNATIVE::"∨ or |"
    FLOW::"→ or -> (right-associative)"

  PREFIX_OPERATORS::"§ for section anchors, // for comments"

  ASCII_ALIASES::"All operators accept both unicode and ASCII forms; canonical output uses unicode"

§3::CRITICAL_RULES
  RULE_NO_SPACES::"No spaces around :: operator (KEY::value not KEY :: value)"
  RULE_INDENT::"Indent exactly two spaces per level (NO TABS)"
  RULE_KEYS::"Keys: [A-Za-z0-9_], must start with letter or underscore"
  RULE_ENVELOPE::"===NAME=== at start, ===END=== at finish"
  RULE_CASE::"Lowercase true, false, null — never True, False, NULL"
  RULE_CONJUNCTION::"∧ only inside brackets [A∧B∧C], never bare"
  RULE_TENSION::"⇌ is binary only (A⇌B), not chained"
  RULE_SECTIONS::"Quote section markers when used as content: \"§2_BEHAVIOR\" not §2_BEHAVIOR"
  RULE_EXTENSION::".oct.md canonical (v6), .octave.txt deprecated"

  §3b::V6_ENVELOPE_STRUCTURE
    FILE_STRUCTURE::"===NAME===, META_BLOCK, optional separator, BODY, ===END==="
    META_REQUIRED::[TYPE, VERSION]
    META_V6_OPTIONAL::[CONTRACT, GRAMMAR]
    CONTRACT::"Validation constraints embedded in document"
    GRAMMAR::"GBNF compilation for constrained generation"

  §3c::ASSEMBLY_RULES
    PATTERN::"Omit intermediate ===END=== when concatenating profiles"
    USE::[agent_context_injection, specification_layering, multi_part_documents]
    REASON::"Reduces token overhead for compound documents"
    EXAMPLE::"core_profile ⊕ schema_profile → single ===END==="

§4::EXAMPLE_STRUCTURE
  ===EXAMPLE===
  STATUS::ACTIVE
  PHASES:
    PLAN::[Research → Design]
    BUILD::[Code ⊕ Test]
  METRICS:
    SPEED::"High"
    QUALITY::"Verified"
  ===END===

§5::MASTERY_PATHWAY
  NEXT_SKILL::octave-mastery
  COMPRESSION::octave-compression
  MYTHOLOGY::octave-ultra-mythic
  WHY_THIS_MATTERS::"OCTAVE transforms LLM communication from prose wasteland into semantic density. Mastery means every token carries information."

===END===
