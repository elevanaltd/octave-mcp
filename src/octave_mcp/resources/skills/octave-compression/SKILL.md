---
name: octave-compression
description: "Workflow for transforming prose into semantic OCTAVE structures. Covers tier selection, transformation phases, loss accounting, and decision rules. REQUIRES octave-literacy."
allowed-tools: ["Read", "Write", "Edit"]
triggers: ["compress to octave", "semantic compression", "documentation refactoring", "octave compression", "compress documentation", "knowledge artifact", "semantic density", "OCTAVE format conversion"]
version: "4.0.0"
---

===OCTAVE_COMPRESSION===
META:
  TYPE::SKILL
  VERSION::"4.0.0"
  STATUS::ACTIVE
  PURPOSE::"Decision rules and workflow for turning prose into OCTAVE at the right fidelity tier"
  REQUIRES::octave-literacy
  NEXT_SKILLS::[octave-ultra-mythic]
  PATTERNS::[octave-tool-reference]
  SPEC_REFERENCE::octave-data-spec.oct.md
---
§1::TIER_SELECTION
  WHEN::"choose the tier before reading the source; the tier drives every later decision"
  TIERS:
    LOSSLESS:
      TARGET::"100 percent fidelity"
      PRESERVE::everything
      DROP::nothing
      USE::[
        "critical reasoning",
        "legal documents",
        "safety analysis",
        "audit trails",
        "syntax references"
      ]
    CONSERVATIVE:
      TARGET::"85 to 90 percent fidelity"
      PRESERVE::"explanatory depth"
      DROP::redundancy
      LOSS::"10 to 15 percent: repetition, verbose phrasing, some edge cases"
      USE::[
        "research summaries",
        "design decisions",
        "technical analysis"
      ]
    AGGRESSIVE:
      TARGET::"70 percent fidelity"
      PRESERVE::"core thesis and conclusions"
      DROP::"nuance or narrative"
      LOSS::"30 percent: explanatory depth, trade-off narratives, edge-case exploration"
      USE::[
        "context window scarcity",
        "quick reference",
        "decision support"
      ]
    ULTRA:
      TARGET::"50 percent fidelity"
      PRESERVE::"facts and structure"
      DROP::"all narrative"
      LOSS::"50 percent: almost all explanatory content, trade-off reasoning"
      USE::[
        "extreme scarcity",
        "embedding generation",
        "dense reference"
      ]
    ULTRA_MYTHIC:
      POINTER::"identity compression for agent binding and identity transfer lives in the octave-ultra-mythic skill; read it there"
  DECISION_RULES::[
    "Reconstruction accuracy critical: CONSERVATIVE or LOSSLESS.",
    "Context window scarce and loss acceptable: AGGRESSIVE or ULTRA.",
    "Decision-relevant facts must survive: CONSERVATIVE.",
    "Source is a rule or syntax reference: LOSSLESS; a reference compressed below its rules is a broken reference.",
    "Otherwise: CONSERVATIVE."
  ]
  EVIDENCE::"stated both ways. octave-mcp study (`docs/research/compression-fidelity-round-trip-study.md`): CONSERVATIVE with mythology domain labels as key prefixes kept 11 of 11 decision-relevant facts at 15 percent fewer tokens than the prose, because each labelled field was translated separately, which prevents fact merging. Estate bench (hestai-workbench `.hestai-state/reports/2026-10-19-octave-wire-bench-closing-report.md`): mythology escalates when misapplied and, under exact fit, does no work plain words do not; the operator ruled it is not instruction vocabulary. Write labels in plain words."
§2::LOSS_ACCOUNTING
  RECEIPT_RULE::"North Star I4 (transform auditability): if bits were dropped, the output carries a receipt; no silent loss"
  REQUIRED_META_FIELDS::[COMPRESSION_TIER,LOSS_PROFILE]
  SCOPE::"the pair belongs in the META of compressed outputs only, as the named exception; skills and other documents do not carry it"
  LOSS_PROFILE_FORM::"a note-form sentence saying what was kept and what was dropped"
  EXAMPLES:
    CONSERVATIVE::"kept causal chains; dropped verbose phrasing"
    AGGRESSIVE::"kept core thesis and conclusions; dropped explanatory depth and edge cases"
    ULTRA::"kept facts and structure; dropped all narrative and trade-off reasoning"
  META_BLOCK_TEMPLATE:
    ```
    META:
      TYPE::DECISION
      VERSION::"1.0.0"
      COMPRESSION_TIER::CONSERVATIVE
      LOSS_PROFILE::"kept causal chains and numbers; dropped verbose phrasing"
    ```
  KNOWN_GAP::"under `schema=META` STRICT both keys give `E007` today (#514); the validator still pairs them: `W_META_001` when COMPRESSION_TIER has no LOSS_PROFILE, `W_META_002` when LOSS_PROFILE is `none` on a tier other than LOSSLESS (`src/octave_mcp/core/validator.py`, `_check_meta_warnings`)"
  CONSISTENCY_RULE::"LOSSLESS with a non-empty dropped list is a contradiction; if LOSS_PROFILE names anything dropped, the tier is not LOSSLESS"
§3::TRANSFORMATION_WORKFLOW
  PHASE_1_READ:
    MAP::"find every causal chain (A causes B, X requires Y)"
    IDENTIFY::[
      redundancy,
      verbosity,
      "conditional qualifiers"
    ]
    NOTE::"conditional qualifiers (when X, if Y, unless Z) carry material risk; never drop them"
  PHASE_2_EXTRACT:
    PRESERVE::[
      "causal chains",
      "BECAUSE statements",
      metrics,
      "conditional qualifiers",
      "identifiers, copied exactly",
      "hedges, copied verbatim"
    ]
    COMPRESS::[
      stopwords,
      repetition,
      "verbose phrasing",
      "narrative connectives"
    ]
    ANCHOR::"one concrete example per major abstraction anchors reconstruction fidelity"
  PHASE_3_COMPRESS:
    HIERARCHY::"group related concepts under parent block keys"
    ARRAYS::"turn parallel items into a list of quoted sentences or atoms"
    RELATIONS::"write relations in words, per the literacy §4b rules list"
    CONTRADICTIONS::"a source that contradicts itself is kept both ways and flagged"
  PHASE_4_VALIDATE:
    FIDELITY::"are all causal chains intact?"
    LOSS_RECEIPT::"does META carry COMPRESSION_TIER and LOSS_PROFILE?"
    GROUNDING::"is there at least one concrete example per major abstraction?"
    RECEIPTS::"read `corrections[]`, `warnings[]` and `repairs[]` from `octave_write` and triage them per octave-tool-reference §3::TRIAGE; `W_BARE_LINE_DROPPED` and `W_NUMERIC_KEY_DROPPED` are silent data loss; empty warnings alone are not a clean receipt"
§4::COMPRESSION_RULES
  RULES::[
    "Keep causality: X leads to Y because Z; never flatten it to X leads to Y alone.",
    "Keep conditional qualifiers (when X, if Y, unless Z); they carry material risk.",
    "Keep trade-offs in words: gain versus loss.",
    "Keep one concrete example per major abstraction as the minimum reconstruction anchor.",
    "Never drop numbers, identifiers, thresholds or named entities; they cannot be rebuilt.",
    "Never place a value on a section header; it is dropped silently (literacy §3, the rule that a section header carries no value); content goes on child lines.",
    "Never invent to fill a slot or field: write `none` or `not known`."
  ]
§5::ANCHOR_KERNEL
  TARGET::"prose to OCTAVE at a declared fidelity tier"
  NEVER::[
    "operators in prose or values",
    "mythology as instruction words",
    "snake_case blobs",
    "invented content; write none or not known",
    "model-written ids, tags or counts",
    "unkeyed lines",
    "a value on a section header",
    "judgement attributed to a named person",
    "shortened or merged identifiers",
    "compressing before choosing the tier",
    "dropping causal chains, conditions or numbers"
  ]
  MUST::[
    "note form",
    "identifiers copied exactly, in backticks",
    "hedges and conditions copied verbatim",
    "relations in words",
    "one calibration sentence on a prohibition that can over-fire",
    "code in fenced blocks",
    "a self-contradicting source kept both ways and flagged",
    "every line keyed, multi-word values quoted",
    "contents indented under the section header",
    "edits addressed as section dot key",
    "repairs read, not only the validation status",
    "tier first; default conservative; references lossless",
    "compressed output says what was kept and what was dropped"
  ]
  GATE::"Could a reader rebuild every causal chain, condition and number, and does the document say what was dropped?"
§7::ANTI_PATTERNS
  ANTI_PATTERNS::[
    "Markdown inside OCTAVE: no bold, no headings, no bullet hyphens.",
    "JSON or YAML syntax: no curly braces, no trailing commas, no YAML bullet hyphens.",
    "Nesting deeper than 3 levels: restructure with parent block keys.",
    "Silent loss: a compressed output always declares COMPRESSION_TIER and LOSS_PROFILE in META.",
    "Paradigm drift: validate for LLM parse efficiency, not human readability.",
    "Compressing the rulebook: a syntax or governance reference at AGGRESSIVE drops the examples that make it a reference; references are LOSSLESS."
  ]
===END===
