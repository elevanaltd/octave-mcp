---
name: octave-literacy
description: "LLM-native structured communication format. Teaches OCTAVE syntax rules, canonical forms, and warning prevention for zero-error .oct.md authoring."
allowed-tools: ["Read", "Write", "Edit"]
triggers: ["octave format", "write octave", "octave syntax", "structured output", "OCTAVE basics", "OCTAVE literacy", "OCTAVE structure", "key::value", "OCTAVE notation", "llm communication", "token economy", "loss accounting"]
version: "3.2.1"
---

===OCTAVE_LITERACY===
META:
  TYPE::SKILL
  VERSION::"3.2.1"
  STATUS::ACTIVE
  PURPOSE::"Zero-error OCTAVE authoring — syntax rules, canonical forms, warning prevention"
  OCTAVE::"Olympian Common Text And Vocabulary Engine — loss accounting system for LLM communication"
  AUDIENCE::LLM<exclusively>
  SPEC_REFERENCE::octave-core-spec.oct.md
  NEXT_SKILLS::[octave-mastery,octave-compression]
---
§0::CONSUMPTION_DIRECTIVE
  // You are writing for LLM consumption only. No prose. No narrative. Every token carries payload.
  // Optimize for parsing efficiency and token density. Readability is irrelevant.
  MYTHOLOGY::"Use as compression — zero-shot, trust it. ATHENA<strategic_wisdom> = 1 token replacing 15."
  MYTHOLOGY_ANTI_PATTERN::"ZEUS::executive_decision — use EXECUTIVE::decision when literal is equally clear"
  // Full vocabulary: octave-mastery §1
§1::CORE_SYNTAX
  ASSIGNMENT::"KEY::value — double colon, no spaces around ::"
  BLOCK::"KEY: + newline + 2-space indent — use when value has nested children"
  CHOICE::"scalar value → ASSIGNMENT. nested children → BLOCK. Never mix."
  LIST::"[a,b,c] — square brackets, no YAML bullets ever"
  STRING::"bare_word if no spaces/special chars, else double-quoted"
  NUMBER::"42 or 3.14 or -1e10 — no quotes"
  BOOLEAN::"true or false — lowercase only"
  NULL_VALUE::"null — lowercase only"
  COMMENT::"// — line start or after value"
  §1b::BRACKET_FORMS
    CONTAINER::"[a,b,c] — bare brackets = list"
    ANNOTATION::"NAME<qualifier> — semantic facet on identity (ATHENA<strategic_wisdom>, LLM<exclusively>)"
    ANNOTATION_DISCIPLINE::"Annotations are SHORT qualifiers (1-3 words, ≤32 chars, identifier-only). Multi-word reasoning belongs in a sibling RATIONALE value as a quoted telegraphic phrase (see octave-mastery §6a)."
    ANNOTATION_WRONG::"I6<migration_on_moving_target_is_anti_pattern_for_zero_warnings>"
    ANNOTATION_RIGHT::"I6<production_grade_quality> + RATIONALE::\"Migration on moving target is anti-pattern for strict typing during data model changes.\""
    CONSTRUCTOR::"NAME[args] — structured arguments on identifier (REGEX[pattern], ENUM[a,b], JIT_GRAMMAR_COMPILATION[META→GBNF])"
    // These are SEPARATE forms. <> qualifies what something IS. [] parameterizes what something DOES.
    // ATHENA<strategic_wisdom> = annotation (identity facet). ENUM[a,b,c] = constructor (validation args).
    // Lenient parser canonicalizes []→<> ONLY for annotation-context uses. Genuine constructors keep [].
    // When in doubt: identity/archetype qualifier → <>. Parameterized operation/schema → [].
    INLINE_MAP::"[key::val, key2::val2] — dense key-value pairs, values must be atoms, no nesting"
  §1c::LITERAL_ZONES
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
  §1d::BLOCK_CANONICAL_FORMS
    // Three shapes agents reach for when nesting — only one is correct
    RULE::"Multi-field token (any key whose value is a map) → BLOCK form. Never inline-array root. Never flat prefix-scalars."
    THREE_SHAPES:
      ```
      ✓ BLOCK (canonical):         ✗ inline-array root:              ✗ flat prefix-scalars:
        PLATFORM:                    PLATFORM::[                        PLATFORM_TOKEN::HO-v1
          TOKEN::HO-v1                 TOKEN::HO-v1,                   PLATFORM_RUNTIME_FLOOR::"Node >=22"
          RUNTIME:                     RUNTIME::[FLOOR::"Node >=22"]]  PLATFORM_RUNTIME_BECAUSE::"…"
            FLOOR::"Node >=22"
            BECAUSE::"…"
      ```
    SCALAR_LIST_ONLY::"Inline arrays ([a,b,c]) are for scalar lists only — IMMUTABLES::[…], CONSOLIDATES::[a,b] — never for maps-of-maps"
    WHY_BLOCK::"Indented children inherit parent context → fewer key tokens, better LLM attention, zero W_DUPLICATE_KEY collisions"
    WHY_NOT_INLINE_ARRAY_ROOT::"Inline map as token root is non-canonical for map tokens even when values are atomic (§1b::INLINE_MAP). Triggers E_NESTED_INLINE_MAP as soon as any child value needs nesting — restructuring after the fact is mechanical waste. Use BLOCK form from the start."
    WHY_NOT_FLAT_PREFIX::"PARENT_CHILD1 + PARENT_CHILD2 key proliferation destroys hierarchical grouping and LLM attention"
§2::OPERATORS
  // Each operator encodes a relationship in a single token
  CONTAINER::"[] — List [a,b,c]"
  CONCAT::"⧺ — Mechanical join A⧺B | ASCII: ~"
  SYNTHESIS::"⊕ — Emergent whole A⊕B | ASCII: +"
  TENSION::"⇌ — Binary opposition A⇌B | ASCII: vs (requires word boundaries)"
  CONSTRAINT::"∧ — Inside brackets only [A∧B∧C] | ASCII: &"
  ALT::"∨ — Alternative A∨B | ASCII: |"
  FLOW::"→ — Right-associative A→B→C, often in lists [A→B→C] | ASCII: ->"
  SECTION_REF::"§ — target anchor e.g. §3c::ASSEMBLY_RULES"
  LINE_COMMENT::"// — line start or after value"
  ASCII_RULE::"All operators accept both unicode and ASCII. Always emit unicode."
  VS_RULE::"vs requires word boundaries: 'A vs B' valid, 'AvsB' invalid"
  TELEGRAPHIC_PHRASE::"see octave-compression §4::R3a — operators carry the English connectives inside quoted values"
§3::CRITICAL_RULES
  R1::"No spaces around :: (KEY::value not KEY :: value)"
  R2::"Indent exactly 2 spaces per level — NO TABS"
  R3::"Keys must match [A-Za-z_][A-Za-z0-9_]* — start with letter or underscore"
  R4::"Envelopes: ===NAME=== open, ===END=== close (NAME must be [A-Z_][A-Z0-9_]*)"
  R5::"true, false, null — lowercase only (NOT True, False, NULL)"
  R6::"∧ only inside brackets: [A∧B∧C] valid, bare A∧B invalid"
  R6_CLARIFICATION::"Structural position: ∧ inside brackets only. Value position: operators inside quoted strings are valid telegraphic phrases — 'security ⇌ usability' not 'security at odds with usability' (see §2::TELEGRAPHIC_PHRASE, mastery §6a)"
  R7::"⇌ is binary only: A⇌B valid, chained A⇌B⇌C invalid"
  R8::"Values containing § must be quoted: \"see §3b\" not bare §3b"
  R9::"File extension .oct.md is canonical"
  R10::"Bare numeric keys trigger W_NUMERIC_KEY_DROPPED — use R1, STEP_1, not 1"
  R11::"Unkeyed prose sentences trigger W_BARE_LINE_DROPPED — comments (//) and list body lines are exempt"
  §3b::V6_ENVELOPE_STRUCTURE
    FILE_STRUCTURE::"===NAME=== then META then optional --- separator then BODY then ===END==="
    SEPARATOR::"--- signals metadata boundary to discovery/indexing tools. Place after META block."
    META_REQUIRED::[TYPE,VERSION]
    META_COMMON_OPTIONAL::[
      STATUS,
      UPDATED,
      COMPRESSION_TIER,
      LOSS_PROFILE,
      CONTRACT,
      GRAMMAR
    ]
    // STATUS in META = document lifecycle (ACTIVE, DRAFT). STATUS in BODY = subject state. Both valid.
    COMPRESSION_TIER::ENUM[LOSSLESS,CONSERVATIVE,AGGRESSIVE,ULTRA]
    LOSS_PROFILE::"[preserve:causal_chains,drop:verbose_phrasing] — loss is explicit, never hidden"
    // NOTE: LOSS_PROFILE is spec-valid; older validators may not list it in allowed_meta — validator gap, not spec error
    CONTRACT::HOLOGRAPHIC<validation_law_in_document>
    GRAMMAR::GBNF_COMPILER<generate_constrained_output>
  §3c::ASSEMBLY_RULES
    RULE::"When concatenating profiles, omit intermediate ===END=== — only final one terminates"
    USE_CASES::[
      agent_context_injection,
      specification_layering,
      multi_part_documents
    ]
  §3d::SECTION_PATH_REFERENCES
    SYNTAX::"§N::NAME — section reference. §3b::V6_ENVELOPE_STRUCTURE is a valid cross-reference."
    QUOTING::"Quote § when used as content value: VALUE::\"see §3b\" not VALUE::§3b"
    NESTING::"§3b inside §3 — subsection. Prefix digit tracks depth."
§4::WARNING_PREVENTION
  // octave_write returns warnings[] — each warning is silent data loss
  W_BARE_LINE_DROPPED::"Cause: line has no key:: prefix. Fix: add a key or use // comment."
  W_NUMERIC_KEY_DROPPED::"Cause: bare integer key (1::thing). Fix: use R1::thing or STEP_1::thing."
  W_CHECK::"After every octave_write call, inspect warnings[]. Today: Empty = clean. Non-empty = data lost. AFTER ADR-0006 SR1-T4: see §6 — empty no longer implies clean."
  W_CHANGES_MODE_NESTED_MAP::"Cause: passing a nested dict as a changes-mode value to octave_write. Fix: use content= with format_style=preserve for any block-nested content. Changes-mode serializes nested dicts as inline maps → E_NESTED_INLINE_MAP. Exception: scalar-array appends (e.g. into AMENDS::[…]) remain changes-mode-friendly."
  // W_CHANGES_MODE_NESTED_MAP: per octave-mcp changes-mode footgun — revisit post-ADR-0006-SR3-T2 when changes-mode gains native nesting support
  // Semantic of warnings[] is changing. See §6::FORTHCOMING_BEHAVIOR for timing markers.
§5::WORKED_EXAMPLE
  // Shows: envelope, META with optional fields, separator, operators, annotation, loss accounting
  EXAMPLE:
    ```
===DECISION===
META:
  TYPE::DECISION
  VERSION::"1.0.0"
  COMPRESSION_TIER::CONSERVATIVE
  LOSS_PROFILE::"[preserve:causal_chains,drop:verbose_phrasing]"
---
STATUS::ACTIVE
CONTEXT::API_redesign[KAIROS<Q2_window>]
DECISION::microservice_extraction[auth⊕payments→independent_services]
PHASES:
  PLAN::[Research→Design]
  BUILD::[Code⊕Test]
METRICS:
  LATENCY::"<200ms p99"
  AVAILABILITY::"99.95%"
===END===
    ```
  // KAIROS<Q2_window> = annotation form. Semantic facet on identifier, not a list.
  // META carries COMPRESSION_TIER and LOSS_PROFILE — loss is auditable.
  // PHASES uses BLOCK because children are nested. STATUS uses ASSIGNMENT because scalar.
§6::FORTHCOMING_BEHAVIOR
  // Per ADR-0006 (Writer/Reader Symmetry Programme). The writer surface is bifurcating.
  // This section is truthful BEFORE and AFTER the milestones land — read the timing markers.
  REF::"octave-mcp:docs/adr/ADR-0006-writer-reader-symmetry.md"
  // ^ path is in the octave-mcp repo (upstream OCTAVE spec authority), not this repo.
  §6a::TIMELINE
    TODAY::"octave_write canonicalises (normalises syntax) on every write. warnings[] enumerates what changed during normalisation. Empty warnings[] ⇒ source was already canonical."
    AFTER_SR1_T4::"Default behaviour becomes NO-OP normalisation. octave_write commits bytes as supplied (subject to schema validation). warnings[] enumerates what would have changed had normalisation been ATTEMPTED. Empty warnings[] ⇒ no normalisation was attempted — NOT a guarantee of canonicality. Sprint 1 milestone."
    AFTER_SR3_T2::"Canonicalisation moves to a separate octave_fmt tool. Use octave_write to PERSIST bytes; use octave_fmt to CANONICALISE on demand. Two distinct calls, two distinct receipts. Sprint 3 milestone."
  §6b::SEMANTIC_SHIFT_OF_EMPTY_WARNINGS
    // The same wire shape (warnings: []) carries different meaning across the timeline.
    TODAY::"warnings:[] ≡ source_already_canonical[no_changes_needed]"
    AFTER_SR1_T4::"warnings:[] ≡ no_normalisation_attempted[canonicality_unknown]"
    IMPLICATION::"Post-SR1-T4, do NOT infer canonicality from absence of warnings. Run octave_fmt (post-SR3-T2) or call octave_validate to check canonicality."
    I4_RECEIPT::"This semantic shift is itself a TRANSFORM_AUDITABILITY event — logged here in skill text rather than absorbed silently into existing wording. PROD::I4."
  §6c::AGENT_GUIDANCE_BY_PHASE
    PHASE_TODAY::[
      "Use octave_write for both persistence AND canonicalisation",
      "Inspect warnings[] to learn what was normalised",
      "Empty warnings[] = clean[input was canonical]"
    ]
    PHASE_AFTER_SR1_T4::[
      "Use octave_write for persistence",
      "Inspect warnings[] to learn what WOULD have been normalised — these are now diagnostics, not data-loss receipts",
      "Empty warnings[] = NOT a canonicality guarantee — call octave_validate or (post-SR3-T2) octave_fmt"
    ]
    PHASE_AFTER_SR3_T2::[
      "octave_write::persistence_only[no_canonicalisation]",
      "octave_fmt::explicit_canonicalisation[on_demand,returns_diff_receipt]",
      "Two-call pattern: write_then_fmt for canonical persistence; write_only for raw persistence"
    ]
  §6d::INVARIANT_RELOCATION_NOT_RELAXATION
    // PROD::I1 (SYNTACTIC_FIDELITY: normalization_alters_syntax_never_semantics) is NOT being weakened.
    // The bifurcation RELOCATES the I1 enforcement locus from octave_write to octave_fmt.
    // octave_fmt remains bound by I1 (idempotent, bijective on semantic space).
    // octave_write becomes a pure persistence path; canonicalisation is opt-in.
    AUTHORS::"Treat octave_write as 'commit bytes' and octave_fmt as 'canonicalise bytes' — they compose, they do not duplicate."
§7::REPAIRLOG_AUDIT_COMPLETENESS
  // ADR-0006 SR1-T1 Step 3 (v1.12.0): RepairLog is the complete I4 record.
  POST_V1_12_0::"RepairLog is the complete I4 (TRANSFORM_AUDITABILITY) record. All TIER_NORMALIZATION events (whitespace, blank-line, identifier dequoting, triple-quote collapse, W002) emit corrections via the central core/grammar/tier_normalize channel."
  EMPTY_LOG_SEMANTICS::"An empty RepairLog means no normalisation was applied. Do not assert empty-log on documents containing trivia normalisation (blank-line stripping, triple-quote collapse) — those now produce corrections."
  CONSUMER_GUIDANCE::[
    "If your test pre-v1.12.0 asserted len(corrections)==0 on a document that strips blank lines or collapses triple-quoted empties, it will now see corrections — this reflects correct I4 behaviour. The prior empty-list was an under-reporting bug.",
    "To detect content normalisation: filter corrections by tier=='NORMALIZATION'.",
    "To detect schema repairs: filter by tier=='REPAIR'."
  ]
§8::UNIVERSAL_GOVERNANCE_GRAMMAR
  // UPOG (Universal Parse-Only Governance) — structural composition for governance artefacts
  // (North Stars, ADRs, RFCs, project-context docs). Composes on top of §2 R3a value-form
  // and §3 critical rules. Establishes parse-only validation as the gate, eliminating
  // per-doctype schema registration tax. Convention IS the schema, enforced by the strict
  // parser ⊕ this skill ⊕ octave-secretary write gate.
  §8a::ORGANIZING_PRINCIPLE
    MOTTO::"strict AST parse → gate. skill → schema. doctypes → zero registration tax."
    INSIGHT::"governance bodies → schema-exempt by declaration. META envelope → still validates."
    APPLIES_TO::[
      North_Star_Summary,
      Architectural_Decision_Record,
      Request_For_Comments,
      project_context_documents,
      any_repeated_entity_governance_artefact
    ]
  §8b::BLOCK_FORM_FOR_REPEATED_ENTITIES
    // The structural anti-pattern that broke pre-UPOG governance docs:
    // I1::NAME::[PRINCIPLE::v, WHY::v, STATUS::v]
    // The chained ::NAME::[...] form reads as ASSIGNMENT under strict 1.13 lexer,
    // hoisting inner KV pairs to file-top-level. Across I1..IN, PRINCIPLE/WHY/STATUS
    // collide with W_DUPLICATE_KEY × 3N — last-write-wins data loss.
    PATTERN::"ID<LABEL>: + indented children"
    SYNTAX::"Block opener uses ID<LABEL>: form. NAME<facet> annotation (§3 of octave-mastery) carries the human-readable label. Indented children scope KEY tokens per-parent."
    EXAMPLE_FORBIDDEN::"I1::PERSISTENT_COGNITIVE_CONTINUITY::[PRINCIPLE::v,WHY::v,STATUS::v]"
    EXAMPLE_CANONICAL:
      ```
      §1::IMMUTABLES
        COUNT::6
        I1<PERSISTENT_COGNITIVE_CONTINUITY>:
          PRINCIPLE::"persist context⊕decisions⊕learnings → cross-session continuity"
          WHY::"amnesia → system failure [prevent re-learning cost]"
          STATUS::PENDING
          OWNER::implementation-lead
          GATE::B1
        I2<STRUCTURAL_INTEGRITY_PRIORITY>:
          PRINCIPLE::"correctness⊕compliance → precedence over velocity"
          ...
      ```
    GUARANTEE::"each I<N> block scopes children → ZERO W_DUPLICATE_KEY across the §"
    APPLIES_ALSO_TO::[
      assumptions<A1..AN>,
      ADR_records<ADR-NNNN>,
      RFC_records<RFC-NNN>,
      constrained_variables,
      any_homogeneous_repeated_record_block
    ]
  §8c::MARKDOWN_ERADICATION
    // Mixed markdown ## headings inside ===NAME=== envelopes fail E_TOKENIZE under
    // strict 1.13 lexer (the `(` in "## IMMUTABLES (6 Total)" trips the lexer).
    RULE::"governance .oct.md → ZERO markdown headings inside envelope"
    SCOPE::"applies to active governance artefacts. Generators (template files, /ns-summary-create skill, north-star-architect agent) that still emit legacy ## headings are Phase B follow-up — not retro-non-compliant, but MUST migrate before next governance amendment cycle."
    TRANSFORM:
      FROM::"^## (.*)$"
      TO::"§N::SECTION_NAME"
    EXAMPLE_BEFORE::"## IMMUTABLES (6 Total)"
    EXAMPLE_AFTER:
      ```
      §1::IMMUTABLES
        COUNT::6
      ```
    RATIONALE::"§N::NAME is structurally targetable. ## is text annotation lexer rejects."
  §8d::SCHEMA_EXEMPTION_VIA_CONTRACT
    // Declaratively scope schema validation to the META envelope; body fields are governed
    // by parse correctness, NOT by per-doctype schema registration. Eliminates the tax of
    // creating NORTH_STAR_SUMMARY / ADR / RFC schemas for every new artefact class.
    META_ANNOTATION::"CONTRACT::HOLOGRAPHIC<parse_only_governance>"
    SEMANTIC::"META → still validates against generic META schema. Body → parse-only governed. Body schema_validation_errors → non-load-bearing by declaration."
    PRECEDENT::"§3b META_COMMON_OPTIONAL already permits the HOLOGRAPHIC contract facet — we are using the existing hook, no spec change required."
    SUCCESS_CRITERION::"octave_validate STRICT → warnings:[] ⊕ errors:[] ⊕ repairs:[]"
  §8e::CANONICAL_AND_SOURCE_META
    // Path-tracking META fields enforced by canonical-paths pre-commit hook.
    CANONICAL::"runtime delivery path (e.g. .hestai/north-star/… or .hestai-sys/…)"
    SOURCE::"git-committed source path (e.g. src/<pkg>/_bundled_hub/… or repo-local)"
    RULE::"every governance .oct.md → META.CANONICAL ⊕ META.SOURCE required"
    PROJECT_LOCAL::"if file lives only in project tree → CANONICAL == SOURCE"
    BUNDLED_HUB::"source ≠ canonical → CANONICAL points to .hestai-sys/, SOURCE points to _bundled_hub/"
  §8f::VALUE_FORM_DELEGATION
    // Reasoning-field values (PRINCIPLE, WHY, RATIONALE, EVIDENCE, …) → R3a §4 of octave-compression.
    // Do NOT use snake_case_blobs in reasoning fields → triggers W_SNAKE_CASE_BLOB advisory
    // (see octave-secretary §5::SNAKE_CASE_BLOB anti-pattern, octave-mcp 1.13.0).
    SEE_COMPRESSION::"octave-compression §4::R3a"
    SEE_SECRETARY::"octave-secretary §5::SNAKE_CASE_BLOB"
    RULE::"quoted prose ∨ telegraphic operator form. NEVER bare snake_case_blob in reasoning fields."
  §8g::MIGRATION_CHECKLIST
    // Mechanical migration recipe — every legacy field preserved verbatim, only shape changes.
    STEP_1::"replace every ## Heading → §N::SECTION_NAME"
    STEP_2::"replace every I#::NAME::[KEY::v,…] → I#<NAME>:\\n  KEY::v indented children"
    STEP_3::"add META.CONTRACT::HOLOGRAPHIC<parse_only_governance>"
    STEP_4::"add META.CANONICAL ⊕ META.SOURCE"
    STEP_5::"telegraphic-compress reasoning values per R3a (operators carry connectives)"
    STEP_6::"octave_validate STRICT → confirm warnings:[] ⊕ errors:[] ⊕ repairs:[]"
    INVARIANT::"core structural field names preserved (PRINCIPLE, WHY, STATUS, INHERITS, IS, IS_NOT, GATES, LOAD_FULL_NORTH_STAR_IF, THE_OATH, …). Permitted semantic splits where the legacy form encoded multiple values in one slot: ASSUMPTIONS::N[note] → ASSUMPTIONS_COUNT::N ⊕ ASSUMPTIONS_NOTE::note. RELATED::[issues]∨[adrs] → RELATED_ISSUES::[…] ⊕ RELATED_ADRS::[…]. IF::trigger,THEN::[actions] → TRIGGER::trigger ⊕ ACTION::[actions] (within §::PROTECTION_CLAUSE block). Splits are mechanical and lossless — no semantic content dropped."
  §8h::ENFORCEMENT_LOCI
    // The convention is enforced at three structural points — drift in any one is detectable.
    LOCUS_1::"this skill — declares the pattern (vault delivery via _bundled_hub)"
    LOCUS_2::"octave-secretary agent — sole valid .oct.md write path, invokes octave_write"
    LOCUS_3::"octave-mcp 1.13 STRICT lexer — refuses non-compliant grammar at parse"
    DRIFT_DETECTION::"file hash on bundled-hub skill source ⊕ pre-commit OCTAVE validation"
===END===
