---
name: octave-literacy
description: Fundamental reading and writing capability for the OCTAVE format. LLM-native — teaches syntax as token economy, not notation convention.
allowed-tools: ["Read", "Write", "Edit"]
triggers: ["octave format", "write octave", "octave syntax", "structured output", "OCTAVE basics", "OCTAVE literacy", "OCTAVE structure", "semantic format", "key::value", "OCTAVE notation", "llm communication", "token economy", "loss accounting"]
version: "2.0.0"
---

===OCTAVE_LITERACY===
META:
  TYPE::SKILL
  VERSION::"2.0.0"
  STATUS::ACTIVE
  PURPOSE::"Fundamental OCTAVE syntax — taught as token economy for LLM-to-LLM communication"
  OCTAVE::"Olympian Common Text And Vocabulary Engine — loss accounting system for LLM communication"
  AUDIENCE::LLM
  CONSUMPTION_MODEL::"Structured key-paths activate schema distributions. Zero disambiguation overhead."
  TIER::LOSSLESS
  COMPRESSION_TIER::LOSSLESS
  LOSS_PROFILE::[preserve:all_syntax_rules,preserve:all_semantic_rationale,drop:none]
  SPEC_REFERENCE::octave-core-spec.oct.md
  V6_FEATURES::"CONTRACT/GRAMMAR blocks, assembly rules, .oct.md extension"
  NEXT_SKILLS::[octave-mastery,octave-compression,octave-mythology]

§0::LLM_CONSUMPTION_PARADIGM
  // Causal foundation for every rule that follows.
  // Every syntax decision in §1–§3 derives from this chain. Internalize before proceeding.

  NORTH_STAR::"OCTAVE-MCP is a loss accounting system for LLM communication"

  CAUSAL_CHAIN:
    PREMISE_1::"LLMs consume tokens sequentially. Each token activates probability distributions."
    PREMISE_2::"Prose tokens activate scaffolding distributions: articles, prepositions, hedges. Low information yield."
    PREMISE_3::"Structured tokens activate schema distributions: KEY::value, ->, +. High information yield."
    CONCLUSION::"OCTAVE replaces prose scaffolding with operator-compressed semantic payload. Same meaning. Fewer tokens."

  TOKEN_ECONOMY:
    PROSE_SPLIT::"content~40% scaffolding~60%"
    // 'the', 'is', 'a', 'of', 'which means that' — scaffolding tokens carry zero payload
    OCTAVE_SPLIT::"content~85% structure~15%"
    // '::', indent, '[]', operators — structural skeleton, maximum payload fraction
    GAIN::"2x–5x effective information density per context window"

  MYTHOLOGICAL_LEVERAGE:
    MECHANISM::"Archetypes activate pre-trained probability distributions as single tokens"
    COMPARISON:
      PROSE::"responsible for infrastructure, tooling, engineering, and system automation"
      OCTAVE::HEPHAESTUS
      TOKEN_DELTA::"8 tokens → 1 token. Same distribution activation."
    PRINCIPLE::"Use archetypes as semantic compression, not decoration"
    WARNING::"Do not invent mappings. Canonical pantheon defined in octave-mastery §1."

  LOSS_ACCOUNTING:
    DEFINITION::"Every transformation must declare what is preserved vs dropped"
    WHY::"LLMs reconstructing from compressed context must know the fidelity contract"
    HOW::"META carries COMPRESSION_TIER and LOSS_PROFILE on every document"
    TIERS::[LOSSLESS,CONSERVATIVE,AGGRESSIVE,ULTRA]
    // Full tier definitions in octave-compression §1b

  DESIGN_IMPLICATION::"Every syntax rule in §1–§3 serves this paradigm. Rules exist because they eliminate LLM inference overhead — not because they are conventions."

§1::CORE_SYNTAX
  // Rules annotated with LLM-efficiency rationale.
  // WHY comments explain the causal link between rule and token economy.

  ASSIGNMENT::"KEY::value"
  // WHY: Double-colon is unambiguous binding operator. Parser resolves on first ::, no lookahead.
  // Prose equivalent 'KEY is value' requires copula parsing + antecedent resolution: ~3 extra tokens + disambiguation.

  BLOCK::"KEY: newline + 2-space indent"
  // WHY: Depth encoded spatially in whitespace prefix. LLM reads hierarchy from character offset, not
  // natural language cues ('which contains', 'under which', 'nested within'). Zero inference cost.

  LIST::"[a,b,c]"
  // WHY: Brackets signal set membership unambiguously. 'a, b, and c' requires Oxford-comma
  // disambiguation and conjunction parsing. Brackets: zero disambiguation cost.

  STRING::"value in quotes or bare_word"
  // WHY: Quotes signal atomic content — not a key, not an operator.
  // Bare words valid when no spaces or special chars present. Omit quotes when safe — compression advantage.

  NUMBER::"42 or 3.14 or -1e10 — no quotes"
  // WHY: Unquoted numbers declare numeric type at write time. Quoted "42" forces string-vs-number
  // disambiguation at every read. Type clarity eliminates reconstruction drift across context boundaries.

  BOOLEAN::"true or false — lowercase only"
  // WHY: Matches JSON/YAML convention — zero cross-format drift for LLM readers trained on both.

  NULL_TYPE::"null — lowercase only"
  // WHY: Explicit null carries semantic information. Omission is ambiguous — missing key vs null value.

  COMMENT::"//"
  // WHY: Annotations for LLM readers. Every comment token competes with payload.
  // Use when rationale is not recoverable from structure alone. Omit when structure is self-explanatory.

  §1b::LITERAL_ZONES
    SYNTAX::"KEY then newline then fence of 3+ backticks"
    GUARANTEE::bytes_preserved
    // Zero processing between fences: tabs allowed, NFC bypassed, info tag preserved
    FENCE_SCALING::"N+1 backticks wraps content containing N-backtick fences"
    USE::[embedded_code,verbatim_content,OCTAVE_about_OCTAVE,teaching_examples]
    LLM_RATIONALE::"Escaping arbitrary content is token-expensive. Literal zones pass bytes raw — no escape overhead."

  §1c::BRACKET_FORMS
    CONTAINER::"[a,b,c] — flat collection, elements are atoms"
    CONSTRUCTOR::"NAME[args] — semantic intent declared upfront (REGEX[pattern], ENUM[a,b])"
    INLINE_MAP::"[key::val,key2::val2] — dense key-value; values must be atoms, no nesting"
    HOLOGRAPHIC::"[value CONSTRAINT->TARGET] — schema mode: validation law embedded in value position"

§2::OPERATORS
  // Operators are OCTAVE's primary compression mechanism.
  // Each encodes a DISTINCT semantic relationship. Not interchangeable.
  // Choosing the wrong operator activates the wrong probability distribution — semantic error, not style error.

  PRECEDENCE_TABLE:
    P1::"[] Container — set membership"
    P2::"⧺ or ~ — Mechanical join A⧺B — concatenation without synthesis"
    P3::"⊕ or + — Synthesis A⊕B — emergent whole, not sum of parts"
    P4::"⇌ or vs — Tension A⇌B — binary opposition, both forces active simultaneously"
    P5::"∧ or & — Conjunction [A∧B∧C] — all conditions hold (brackets required)"
    P6::"∨ or | — Alternative A∨B — either valid, not both required"
    P7::"→ or -> — Flow A→B→C — causality/sequence, right-associative"

  UNICODE_CANONICAL:
    CONCAT::"⧺ (preferred) or ~"
    SYNTH::"⊕ (preferred) or +"
    TENSION::"⇌ (preferred) or vs"
    CONJ::"∧ (preferred) or &"
    ALT::"∨ (preferred) or |"
    FLOW::"→ (preferred) or ->"
    // All operators accept unicode or ASCII. Emit unicode canonically.

  PREFIX_OPERATORS:
    SECTION::"§ — section anchor for cross-references (→§DECISION_LOG)"
    COMMENT::"// — line annotation, zero payload cost when LLM reader skips"

  DISTINCTION_MATTERS:
    SYNTH_NOT_CONCAT::"⊕ activates emergent-whole distribution. ⧺ activates append distribution. Different inference paths."
    TENSION_NOT_ALT::"⇌ holds both forces active simultaneously. ∨ picks one. Semantically opposite."
    FLOW_NOT_SYNTH::"→ implies causality/sequence. ⊕ implies integration. Wrong choice misleads reconstruction."

  §2b::ASCII_BOUNDARY_RULE
    vs_VALID::"'A vs B' or '[Speed vs Quality]' — word boundaries required"
    vs_INVALID::"SpeedvsQuality — no boundaries, ambiguous tokenization"
    RULE::"vs requires whitespace, bracket, paren, start, or end on both sides"

§3::CRITICAL_RULES
  // Violations produce invalid OCTAVE. Rationale tied to LLM parsing correctness.

  NO_SPACES_AROUND_ASSIGN::"KEY::value — no spaces. KEY :: value is invalid."
  // WHY: Space-padded :: is ambiguous with natural-language colon. Tight binding required for zero-lookahead parsing.

  INDENT_EXACTLY_2::"2 spaces per level. NO TABS."
  // WHY: Tab width is renderer-dependent. Fixed 2-space indent makes depth computable from
  // character offset alone — no render-context dependency for LLM readers.

  KEY_CHARSET::"[A-Za-z0-9_], must start with letter or underscore"
  // WHY: Predictable keyspace. LLM constructs key lookups without character-class disambiguation.

  ENVELOPE::"===NAME=== opens, ===END=== closes. NAME must match [A-Z_][A-Z0-9_]*"
  // WHY: Triple-equals is visually and tokenically unambiguous as document boundary marker.

  LOWERCASE_ATOMS::"true, false, null — never True, False, NULL"
  // WHY: Case variation forces normalization. Lowercase canonical eliminates variant matching at read time.

  CONJ_IN_BRACKETS::"∧ only inside brackets [A∧B∧C]. Bare A∧B is invalid."
  // WHY: Bare ∧ is ambiguous with key continuation. Bracket containment enforces semantic scope.

  TENSION_BINARY::"⇌ is binary only (A⇌B). Chaining A⇌B⇌C is invalid."
  // WHY: Tension encodes exactly two opposing forces. Three-way tension is a different semantic
  // structure — decompose into nested tensions or separate tradeoff blocks.

  SECTION_IN_CONTENT::"Quote § when used as content value: \"§2_BEHAVIOR\" not §2_BEHAVIOR"
  // WHY: Unquoted § is parsed as section anchor operator. Quoting signals content, prevents
  // parser treating value as structural cross-reference.

  FILE_EXTENSION::".oct.md canonical (v6). .octave.txt deprecated."

  §3b::V6_ENVELOPE_STRUCTURE
    FILE_STRUCTURE::[ENVELOPE_OPEN,META_BLOCK,SEPARATOR_OPTIONAL,BODY,ENVELOPE_CLOSE]
    // ENVELOPE_OPEN = ===NAME===   ENVELOPE_CLOSE = ===END===
    META_REQUIRED::[TYPE,VERSION]
    META_V6_OPTIONAL::[CONTRACT,GRAMMAR]
    CONTRACT::"HOLOGRAPHIC[validation_law_embedded_in_document_META]"
    GRAMMAR::"GBNF_COMPILER[constrained_output_for_llama.cpp|vLLM|Outlines]"
    LLM_RATIONALE::"Self-validating documents eliminate external schema lookup. Validation law travels with content."

  §3c::ASSEMBLY_RULES
    PATTERN::"Concatenating profiles: omit intermediate ===END===. Only final ===END=== terminates."
    USE::[agent_context_injection,specification_layering,multi_part_documents]
    EXAMPLE::"core_profile⊕schema_profile→single_===END===_at_finish"
    LLM_RATIONALE::"Multiple ===END=== markers create premature document termination in streaming contexts."

§4::WORKED_EXAMPLE
  // Demonstrates §0 principles applied to a minimal document.
  // Observe what is absent: articles, copulas, explanatory connectives, hedges.
  // Every key carries payload. Every operator encodes a distinct relationship.

EXAMPLE_DOCUMENT:
```
STATUS::ACTIVE
COMPRESSION_TIER::CONSERVATIVE
LOSS_PROFILE::[preserve:decision_logic,preserve:constraints,drop:narrative_scaffolding]
PHASES:
  PLAN::[Research→Design]
  BUILD::[Code⊕Test]
METRICS:
  SPEED::High
  QUALITY::Verified
TRADEOFFS:
  PRIMARY::Speed⇌Quality
```

  ANNOTATION:
    TENSION_SPEED_QUALITY::"⇌ not ∨ — both forces remain active. Not a choice between them."
    CODE_PLUS_TEST::"⊕ not ⧺ — synthesis, not concatenation. Tests emerge from code."
    RESEARCH_THEN_DESIGN::"→ not ⊕ — sequence with causality. Research precedes and informs Design."

§5::MASTERY_PATHWAY
  NEXT_1::octave-mastery
  // Adds: semantic pantheon (canonical archetype mappings), holographic contracts, advanced syntax
  NEXT_2::octave-compression
  // Adds: transformation workflow, tier selection, loss accounting practice
  NEXT_3::octave-mythology
  // Adds: mythological atom compression, 60%+ density targets
  GATE::"Load octave-mastery before applying mythological archetypes. Canonical pantheon required to prevent drift."

===END===
