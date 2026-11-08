---
name: octave-mastery
description: "Advanced OCTAVE forms that a parser or validator reads: holographic schema definitions, grammar compilation, typed archetype annotations, and structural patterns, plus a reading glossary of mythology and narrative terms. REQUIRES octave-literacy."
allowed-tools: ["Read", "Write", "Edit"]
triggers: ["octave architecture", "agent design", "semantic pantheon", "advanced octave", "OCTAVE mastery", "holographic patterns", "archetypes", "high-density specifications", "system architecture", "holographic contracts", "archetype annotation", "mythology", "OCTAVE mythology", "functional mythology", "SISYPHEAN", "ICARIAN", "PROMETHEAN", "mythological domains"]
version: "5.1.1"
---

===OCTAVE_MASTERY===
META:
  TYPE::SKILL
  VERSION::"5.1.1"
  STATUS::ACTIVE
  PURPOSE::"Forms a parser or validator reads (schema definitions, grammar compilation, typed annotations), structural patterns, and a reading glossary"
  REQUIRES::octave-literacy
  ABSORBS::"octave-mythology 1.3.0: vocabulary kept as a reading glossary; research narrative stays at octave-mcp `docs/research/`"
  SPEC_REFERENCE::octave-core-spec.oct.md
---
§1::READING_GLOSSARY
  PURPOSE::"decode mythology terms met in documents you read; this glossary is for reading, not for writing instructions"
  GLOSSARY:
    ```
    ZEUS::"Executive authority, final arbitration, strategic direction"
    ATHENA::"Strategic wisdom, planning, elegant solutions"
    APOLLO::"Analytics, insight, clarity, prediction"
    HERMES::"Communication, APIs, translation, messaging"
    HEPHAESTUS::"Infrastructure, tooling, engineering, automation"
    ARES::"Security, defense, stress testing, adversarial analysis"
    ARTEMIS::"Monitoring, alerting, precision targeting, observation"
    POSEIDON::"Storage, databases, data lakes, unstructured pools"
    DEMETER::"Resource allocation, budgeting, scaling, growth"
    DIONYSUS::"UX, engagement, creativity, chaotic innovation"
    ```
  READING_NOTES::["A Title_Case prefix (`Artemis_Scrape`, `Ares_BruteForce`) is a qualified action, not a standalone archetype; a standalone archetype matches `[A-Z][A-Z_]*`.","Mythology used as a key prefix (`ARTEMIS::latency_p99`) or a pattern descriptor (`SISYPHEAN_DEBT`) in older documents: read it by the glossary sense."]
  §1a::USAGE_LAW
    RULE::"Mythology is not instruction vocabulary: write rules, keys and values in plain words. It is allowed as style only where a term fits exactly; plain words still carry the meaning."
  §1b::OPEN_VOCABULARY
    READING_RULE::"a figure outside this glossary is valid when it names one distinct domain (format `[A-Z][A-Z_]*`, not membership in a fixed set); read it by that one domain, never as a synonym of another figure; examples: `PHAEDRUS<dialectic>`, `CASSANDRA<foresight_ignored>`, `MNEMOSYNE<memory_persistence>`, `HESTIA<hearth_stability>`, `METIS<cunning_intelligence>`"
  §1c::EVIDENCE
    STUDY::"octave-mcp study: 60 to 70 percent token reduction versus natural language; 88 to 96 percent cross-model zero-shot comprehension; 17 percent more structural sophistication in blind assessment; 4-model validation of Ares and Artemis as behavioural qualifiers (`docs/research/mythology-evidence-synthesis.oct.md`, guide `docs/guides/mythological-compression.md`)"
    COUNTER_EVIDENCE::"a later bench of this document language: mythology as writing escalates when misapplied and, under exact fit, is harmless and does no work plain words do not (confidence High); myth names as instruction vocabulary carried no readable weight over plain names (confidence Medium: never had headroom to read); hence the rule in §1a"
§2::NARRATIVE_FORCES
  PURPOSE::"decode single-token state and trajectory terms met in documents you read; reading only"
  GLOSSARY:
    ```
    TRAJECTORIES:
      ODYSSEAN::"Long transformative journey with clear goal"
      SISYPHEAN::"Repetitive endless maintenance, cyclical failure"
      PROMETHEAN::"Breakthrough challenging status quo"
      ICARIAN::"Overreach from early success → failure, scope creep"
      PANDORAN::"Action unleashing unforeseen cascades"
      TROJAN::"Hidden payload transforming system from within"
      GORDIAN::"Unconventional cut through impossible problem"
      ACHILLEAN::"Single critical point of failure"
      PHOENICIAN::"Necessary destruction and rebirth"
    FORCES:
      KAIROS::"Critical fleeting opportunity window"
      CHRONOS::"Linear time pressure"
      HUBRIS::"Dangerous overconfidence"
      NEMESIS::"Inevitable corrective consequence"
      CHAOS::"Entropy and disorder"
      COSMOS::"Emergence of order from complexity"
    FORCE_TRACKING:
      RISK::"HUBRIS→NEMESIS [overconfidence heading toward consequence]"
      OPPORTUNITY::"KAIROS_WINDOW [critical timing moment]"
      STABILITY::"CHAOS→COSMOS [degradation then recovery]"
      STATE::"HEALTH::[GREEN→YELLOW→ICARIAN] — trajectory encoded in the last token"
    ```
§3::ARCHETYPE_ANNOTATION
  FIELD::"typed field `AGENT_DEFINITION.ARCHETYPE`: a list of annotated archetypes, each `NAME<qualifier>`; the qualifier is one behavioural facet that narrows what the archetype is in this context"
  SYNTAX::ARCHETYPE_NAME<behavioral_facet>
  CORRECT::[
    HEPHAESTUS<faithful_transcription>,
    ATLAS<reliable_execution>,
    ATHENA<strategic_wisdom>,
    HERMES<format_translation>
  ]
  RULES::[
    "Annotation brackets only: `NAME[qualifier]` is constructor syntax, not annotation.",
    "One facet per archetype: stacked qualifiers such as `HEPHAESTUS<a,b>` are invalid.",
    "Qualifier at most 32 characters and at most 4 underscore-tokens; longer content is prose posing as an annotation, so move it to a sibling field."
  ]
  WRONG_EXAMPLE::["`HEPHAESTUS[faithful_transcription]`: constructor brackets on an archetype","`HEPHAESTUS<faithful_and_precise_transcription_of_all_content_without_loss>`: qualifier too long"]
  RIGHT_EXAMPLE::"`HEPHAESTUS<faithful_transcription>` with a sibling PRINCIPLE reading: transcribe all content without loss"
§4::HOLOGRAPHIC_CONTRACTS
  SCOPE::"the only section that teaches writing operator glyphs, and only inside schema-definition files (`TYPE::SCHEMA`), because the validator reads them; every other document writes relations in words"
  USES::"two places: META.CONTRACT, which a tool reads only in the list form below; and holographic patterns in a schema's FIELDS block, the field-level law the validator reads"
  §4a::CONTRACT_IN_META
    FORM::"`CONTRACT::HOLOGRAPHIC<validation_law_in_document>` in META is a descriptive label that no tool interprets (literacy §7d); but `octave_compile_grammar` checks only that CONTRACT is present, so on a schema-definition file the label makes it skip the POLICY and FIELDS blocks; keep it off schema-definition files"
    COMPILER::"the one CONTRACT form a tool consumes: `octave_compile_grammar` reads `META.CONTRACT` as a list of `FIELD[name]::constraint_chain` specs (`src/octave_mcp/mcp/compile_grammar.py`)"
    ANCHORING::[
      "Documented intent; do not write either form until the tokenizer accepts `@` (KNOWN_GAP).",
      "`HOLOGRAPHIC<frozen@sha256_abc123>` would lock the schema to a hash, hermetic; intended for production documents that need reproducibility.",
      "`HOLOGRAPHIC<latest@local>` would resolve to the current local schema, mutable; intended for active development documents."
    ]
    KNOWN_GAP::"on octave-mcp 1.16.0 both anchoring forms fail `E_TOKENIZE` (the `@` inside the annotation), so no validated example carries them"
    GRAMMAR_FIELD::"`GRAMMAR::GBNF_COMPILER<generate_constrained_output>` is a descriptive label; no tool reads `META.GRAMMAR`; for GBNF, call `octave_compile_grammar` on a document carrying META.CONTRACT or a POLICY and FIELDS block"
    SCHEMA_GAP::"under `schema=META` STRICT, CONTRACT and GRAMMAR give `E007` (#514)"
  §4b::HOLOGRAPHIC_BODY_PATTERN
    FORM::"in a schema's FIELDS block, each field reads: value, joined by the constraint glyph to its constraints, then the flow glyph to an optional routing target section; see the example"
    SYNTAX_BREAKDOWN:
      VALUE::"the literal value or expression"
      CONSTRAINT::"REQ, OPT, ENUM[a,b], REGEX[pattern], RANGE[min,max], MAX_LENGTH[n], ISO8601, DATE"
      TARGET::"section where validated values route; optional"
    EXAMPLE:
      ```
      ===STATUS_FIELDS===
      META:
        TYPE::SCHEMA
        VERSION::"1.0"
      FIELDS:
        STATUS::["ACTIVE"∧REQ∧ENUM[ACTIVE,DRAFT,DEPRECATED]→§LIFECYCLE]
        PRIORITY::["HIGH"∧OPT∧ENUM[HIGH,MEDIUM,LOW]]
        LATENCY::["200ms"∧REGEX["^[0-9]+ms$"]]
      ===END===
      ```
    CONSTRAINT_TYPES:
      CORE::[
        REQ,
        OPT,
        CONST,
        ENUM,
        TYPE,
        REGEX,
        DIR,
        APPEND_ONLY
      ]
      EXTENDED::[
        RANGE,
        MAX_LENGTH,
        MIN_LENGTH,
        DATE,
        ISO8601
      ]
  §4c::CONTRACT_BLOCK_EXAMPLE
    PURPOSE::"a full schema definition: META, POLICY and FIELDS together"
    EXAMPLE:
      ```
      ===DECISION_RECORD===
      META:
        TYPE::SCHEMA
        VERSION::"1.0"
        STATUS::ACTIVE
      POLICY:
        VERSION::"1.0"
        UNKNOWN_FIELDS::REJECT
        TARGETS::["§LIFECYCLE"]
      FIELDS:
        STATUS::["ACTIVE"∧REQ∧ENUM[ACTIVE,DRAFT,DEPRECATED]→§LIFECYCLE]
        OWNER::["team-name"∧REQ]
        DECISION::["adopt microservices"∧REQ]
      ===END===
      ```
§5::ANCHOR_KERNEL
  TARGET::"advanced OCTAVE forms a parser or validator reads, written in PITH"
  NEVER::["glyphs outside schema-definition examples","the glossary used for writing"]
  MUST::[
    "Note form",
    "Exact identifiers (copied exactly, in backticks; never shortened or merged)",
    "Hedges verbatim",
    "Relations in words (no operators in prose or values)",
    "Nothing invented (none or not known)",
    "No writer-made ids, tags or counts",
    "One calibration sentence",
    "Judgement unattributed",
    "Code in fences",
    "Contradictions kept and flagged",
    "Plain vocabulary (no blobs, no mythology as instruction words)",
    "every line keyed, values with spaces or punctuation quoted",
    "no unkeyed lines",
    "no value on a section header",
    "contents indented under the header",
    "edits addressed as section dot key (§N.KEY)",
    "receipt fields read, not the status",
    "holographic constraints only in schema-definition files",
    "one facet per archetype, 32 characters at most, in angle brackets",
    "maps of maps as blocks"
  ]
  GATE::"Is every glyph inside a schema-definition example, every other relation in words?"
§6::BLOCK_NOTATION_RULE
  RULE::"nested structures (maps containing maps) MUST use block notation: single colon plus indented children"
  NEVER::"an inner value that is itself an inline map, `KEY::[outer::[inner::val]]`: error `E_NESTED_INLINE_MAP` in strict mode, warning `W_NESTED_INLINE_MAP` in lenient mode"
  PRIMARY_CASE::"agent `§2::BEHAVIOR` definitions: CONDUCT, PROTOCOL and OUTPUT blocks need block notation"
  CORRECT:
    ```
    CONDUCT:
      TONE::"Precise"
      PROTOCOL:
        MUST_ALWAYS::[rule_a, rule_b]
    ```
  WRONG_EXAMPLE::"`CONDUCT::[TONE::Precise, PROTOCOL::[MUST_ALWAYS::[rule_a]]]`"
  RECOVERY_ON_E_NESTED_INLINE_MAP::"the fix is block form; not flattening to scalars (creates the flat-prefix anti-pattern, §7), not collapsing to a blob (creates `W_SNAKE_CASE_BLOB`); those escapes give a different error class, not a solution"
§7::ANTI_PATTERNS
  ISOLATED_LIST::"a list such as auth, payments, users with no stated relationships; state the relation in words, for example a DECISION reading: extract auth and payments into independent services"
  FLAT_HIERARCHY::"all keys at top level with no grouping; group related keys under a parent block"
  BURIED_NETWORK::"a relationship hidden in a prose comment, such as auth depending on payments; state it on a keyed line, for example `DEPENDS_ON::payments` inside the auth block"
  INLINE_ARRAY_ROOT::"`TOKEN::[KEY::v, KEY2::v2]`, an inline map as a multi-field token root: non-canonical for map tokens even when values are atomic, and it gives `E_NESTED_INLINE_MAP` as soon as a child needs nesting (§6); use block form (`TOKEN:` plus indented children) from the start"
  FLAT_PREFIX_SCALARS::"`PARENT_CHILD::v`, `PARENT_CHILD2::v2`: a hierarchy flattened into key prefixes instead of block nesting loses grouping and attention; group under a `PARENT:` block with `CHILD::v` children"
  STRUCTURAL_SYNTAX_IN_VALUE::"an annotation or constructor embedded inside a quoted value, such as `migration[high_risk]<legacy_db>` in a sentence: structural forms are key and identifier only (§3, literacy §1b); inside a value the parser treats them as opaque text, so they bring the ambiguity and none of the validation. Inside a value, write relations in words per the note-form rule in the literacy §4b rules list; push facets to a sibling field (`RISK::high`) or open a block `MIGRATION<legacy_db>:` with the facts as children."
  STRUCTURAL_SYNTAX_SCOPE::"applies to data values; documentation that names a form (literacy §1b) and fenced examples are exempt, because the rule targets facts smuggled into strings, not syntax being described"
  CEREMONIAL_MYTHOLOGY::"narrative prose such as 'As ATHENA, goddess of wisdom, I bestow...' is not compression; mythology is a handle, never a voice"
  MYTHOLOGY_IN_REFERENCE_TABLES::"spec tables and formal definitions stay literal"
===END===
