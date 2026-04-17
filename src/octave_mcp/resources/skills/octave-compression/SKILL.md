---
name: octave-compression
description: "Workflow for transforming prose into semantic OCTAVE structures. Covers tier selection, transformation phases, loss accounting, and decision rules. REQUIRES octave-literacy."
allowed-tools: ["Read", "Write", "Edit"]
triggers: ["compress to octave", "semantic compression", "documentation refactoring", "octave compression", "compress documentation", "knowledge artifact", "semantic density", "OCTAVE format conversion"]
version: "3.0.0"
---

===OCTAVE_COMPRESSION===
META:
  TYPE::SKILL
  VERSION::"3.0.0"
  STATUS::ACTIVE
  PURPOSE::"Decision rules and workflow for transforming prose into semantic OCTAVE at the correct fidelity tier"
  REQUIRES::octave-literacy
  SPEC_REFERENCE::octave-data-spec.oct.md
---
§1::TIER_SELECTION
  // Choose tier BEFORE reading source. Tier drives every subsequent decision.
  TIERS:
    LOSSLESS:
      TARGET::"100%_fidelity"
      PRESERVE::everything
      DROP::nothing
      USE::[
        critical_reasoning,
        legal_documents,
        safety_analysis,
        audit_trails
      ]
    CONSERVATIVE:
      TARGET::"85-90%_fidelity"
      PRESERVE::explanatory_depth
      DROP::redundancy
      LOSS::"10-15%[repetition,verbose_phrasing,some_edge_cases]"
      USE::[
        research_summaries,
        design_decisions,
        technical_analysis
      ]
    AGGRESSIVE:
      TARGET::"70%_fidelity"
      PRESERVE::core_thesis∧conclusions
      DROP::nuance∨narrative
      LOSS::"30%[explanatory_depth,tradeoff_narratives,edge_case_exploration]"
      USE::[
        context_window_scarcity,
        quick_reference,
        decision_support
      ]
    ULTRA:
      TARGET::"50%_fidelity"
      PRESERVE::facts∧structure
      DROP::all_narrative
      LOSS::"50%[almost_all_explanatory_content,tradeoff_reasoning]"
      USE::[
        extreme_scarcity,
        embedding_generation,
        dense_reference
      ]
  DECISION_RULES::[
    "IF[reconstruction_accuracy_critical]→CONSERVATIVE∨LOSSLESS",
    "IF[context_window_scarce∧loss_acceptable]→AGGRESSIVE∨ULTRA",
    "IF[decision_relevant_facts_must_survive]→CONSERVATIVE⊕mythology_domain_labels",
    "DEFAULT→CONSERVATIVE"
  ]
§2::LOSS_ACCOUNTING
  // I4::TRANSFORM_AUDITABILITY — every transformation must log what was preserved vs dropped.
  // These META fields are MANDATORY for any compressed output.
  REQUIRED_META_FIELDS::[COMPRESSION_TIER,LOSS_PROFILE]
  LOSS_PROFILE_FORMAT::"[preserve:X,drop:Y]"
  // LOSS_PROFILE must be explicit — never hidden
  EXAMPLES:
    CONSERVATIVE::"[preserve:causal_chains,drop:verbose_phrasing]"
    AGGRESSIVE::"[preserve:core_thesis∧conclusions,drop:explanatory_depth∨edge_cases]"
    ULTRA::"[preserve:facts∧structure,drop:all_narrative∨tradeoff_reasoning]"
  META_BLOCK_TEMPLATE:
    ```
META:
  TYPE::DECISION
  VERSION::"1.0.0"
  COMPRESSION_TIER::CONSERVATIVE
  LOSS_PROFILE::"[preserve:causal_chains,drop:verbose_phrasing]"
    ```
  I4_RULE::"If bits were dropped, the output must carry a receipt. No silent loss."
§3::TRANSFORMATION_WORKFLOW
  PHASE_1_READ:
    MAP::"Identify all causal chains (A causes B, X requires Y)"
    IDENTIFY::[
      Redundancy,
      Verbosity,
      Conditional_Qualifiers
    ]
    NOTE::"Conditional qualifiers (when X, if Y, unless Z) carry material risk — never drop"
  PHASE_2_EXTRACT:
    PRESERVE::[
      causal_chains,
      BECAUSE_statements,
      metrics,
      conditional_qualifiers
    ]
    COMPRESS::[
      stopwords,
      repetition,
      verbose_phrasing,
      narrative_connectives
    ]
    ANCHOR::"One concrete example per major abstraction — anchors reconstruction fidelity"
  PHASE_3_COMPRESS:
    OPERATORS::"Apply ⊕ ⇌ → ∧ ∨ from octave-literacy §2"
    HIERARCHY::"Group related concepts under parent BLOCK keys"
    MYTHOLOGY::"Use domain label prefixes (ARTEMIS::, CHRONOS::) to anchor facts — see §5"
    ARRAYS::"Convert parallel items to [item1,item2,item3]"
  PHASE_4_VALIDATE:
    FIDELITY::"Are all causal chains intact?"
    LOSS_RECEIPT::"Does META carry COMPRESSION_TIER and LOSS_PROFILE?"
    GROUNDING::"Is there at least one concrete example per major abstraction?"
    WARNINGS::"Check octave_write warnings[] — W_BARE_LINE_DROPPED and W_NUMERIC_KEY_DROPPED are silent data loss"
§4::COMPRESSION_RULES
  R1::"Preserve CAUSALITY — X→Y because Z. Never flatten to X→Y alone."
  R2::"Preserve CONDITIONAL QUALIFIERS — when X, if Y, unless Z carry material risk info"
  R3::"Preserve EXPLICIT TRADEOFFS — GAIN⇌LOSS or GAIN vs LOSS"
  R4::"One concrete example per major abstraction — minimum reconstruction anchor"
  R5::"Use mythology as KEY PREFIXES (CHRONOS::audit_6wk) not embedded values — domain labels are reconstruction anchors"
  R6::"Use mythology as PATTERN DESCRIPTORS (SISYPHEAN,ODYSSEAN) for single-token trajectory encoding"
  R7::"Never drop numbers, IDs, thresholds, or named entities — these are irreplaceable"
§5::CONSERVATIVE_PLUS_MYTHOLOGY
  // CONSERVATIVE compression + mythology domain labels = maximum fidelity at minimum tokens
  WHEN::"Decision-relevant content where reconstruction accuracy matters more than minimum tokens"
  METHOD::"Use mythology terms as KEY prefixes (CHRONOS::audit_6wk) not embedded values"
  WHY::"Domain labels force agents to translate each labeled field separately — prevents fact merging"
  RESULT::"11/11 decision-relevant facts preserved at 15% fewer tokens than original prose"
  EVIDENCE::octave-mcp[docs/research/compression-fidelity-round-trip-study.md]
§6::ANTI_PATTERNS
  AP1::"Markdown inside OCTAVE blocks — no bold, no headers, no bullet hyphens"
  AP2::"JSON/YAML syntax — no curly braces, no trailing commas, no YAML bullet hyphens"
  AP3::"Deep nesting beyond 3 levels — restructure with parent BLOCK keys"
  AP4::"Silent loss — always declare COMPRESSION_TIER and LOSS_PROFILE in META"
  AP5::"Paradigm drift — validate for LLM parse efficiency, not human readability"
===END===
