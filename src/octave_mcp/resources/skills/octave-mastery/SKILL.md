---
name: octave-mastery
description: "Advanced semantic vocabulary, holographic contracts, and structural patterns for OCTAVE. REQUIRES octave-literacy. Extends literacy with mythology, archetype annotation, v6 contracts, and anti-pattern rules."
allowed-tools: ["Read", "Write", "Edit"]
triggers: ["octave architecture", "agent design", "semantic pantheon", "advanced octave", "OCTAVE mastery", "holographic patterns", "archetypes", "high-density specifications", "system architecture", "holographic contracts", "archetype annotation"]
version: "3.0.0"
---

===OCTAVE_MASTERY===
META:
  TYPE::SKILL
  VERSION::"3.0.0"
  STATUS::ACTIVE
  PURPOSE::"Expert-level OCTAVE: mythology vocabulary, holographic contracts, archetype annotation, anti-patterns"
  REQUIRES::octave-literacy
  SPEC_REFERENCE::octave-core-spec.oct.md
---
§1::SEMANTIC_PANTHEON
  // Compression vocabulary — zero-shot, use directly. Literal term wins when equally clear.
  // Use as KEY prefixes (ARTEMIS::latency_p99) or PATTERN DESCRIPTORS (SISYPHEAN_DEBT).
  DOMAINS:
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
§2::NARRATIVE_FORCES
  // Single-token state and trajectory descriptors
  TRAJECTORIES:
    ODYSSEAN::"Long transformative journey with clear goal"
    SISYPHEAN::"Repetitive endless maintenance"
    PROMETHEAN::"Breakthrough challenging status quo"
    ICARIAN::"Overreach from early success → failure"
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
§3::ARCHETYPE_ANNOTATION
  // Archetypes in agent definitions use NAME<qualifier> annotation form
  // <qualifier> is a semantic facet, not a list. It narrows what the archetype IS in this context.
  SYNTAX::ARCHETYPE_NAME<behavioral_facet>
  CORRECT::[
    HEPHAESTUS<faithful_transcription>,
    ATLAS<reliable_execution>,
    ATHENA<strategic_wisdom>,
    HERMES<format_translation>
  ]
  // The <qualifier> activates a specific behavioral dimension of the archetype.
  // Do NOT use NAME[qualifier] for archetypes — that is constructor syntax, not annotation.
  // Do NOT stack multiple qualifiers: HEPHAESTUS<a,b> is invalid. Use one facet per archetype.
  ANTI_PATTERN::"HEPHAESTUS[faithful_transcription] — wrong bracket form for archetype annotation"
  MULTI_ARCH::"[HEPHAESTUS<faithful_transcription>, ATLAS<reliable_execution>] — list of annotated archetypes"
§4::HOLOGRAPHIC_CONTRACTS
  // v6: Documents carry their own validation law in META. Two distinct uses:
  // (A) CONTRACT in META = document-level validation law (what this document must contain)
  // (B) HOLOGRAPHIC pattern in BODY = field-level constraint (what this field must satisfy)
  §4a::CONTRACT_IN_META
    // Place in META block. Defines validation rules for the whole document.
    FORM::"CONTRACT::HOLOGRAPHIC<validation_law_in_document>"
    // CONTRACT value is an annotation — use <> not []
    // The holographic compiler reads META.CONTRACT to validate all fields below.
    ANCHORING:
      FROZEN::"CONTRACT::HOLOGRAPHIC<frozen@sha256_abc123> — locks schema to specific hash, hermetic"
      LATEST::"CONTRACT::HOLOGRAPHIC<latest@local> — resolves to current local schema, mutable"
    // Use frozen@ for production documents requiring reproducibility.
    // Use latest@local for active development documents.
    GRAMMAR_FIELD::"GRAMMAR::GBNF_COMPILER<generate_constrained_output> — emits GBNF for constrained generation"
  §4b::HOLOGRAPHIC_BODY_PATTERN
    // Field-level constraint in BODY. Syntax: KEY::["value"∧CONSTRAINT→§TARGET]
    // The brackets contain: value ∧ constraint → routing target
    SYNTAX_BREAKDOWN:
      VALUE::"the literal value or expression"
      CONSTRAINT::"REQ, OPT, ENUM[a,b], REGEX[pattern], RANGE[min,max], MAX_LENGTH[n], ISO8601, DATE"
      TARGET::"§SECTION — where validated values route (optional)"
    EXAMPLE:
      ```
STATUS::["ACTIVE"∧ENUM[ACTIVE,DRAFT,DEPRECATED]→§LIFECYCLE]
PRIORITY::["HIGH"∧ENUM[HIGH,MEDIUM,LOW]]
LATENCY::["<200ms"∧REGEX[<\d+ms]]
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
    // Full META block using CONTRACT for a typed document
    EXAMPLE:
      ```
===MY_DOCUMENT===
META:
  TYPE::DECISION
  VERSION::"1.0.0"
  CONTRACT::HOLOGRAPHIC<latest@local>
---
STATUS::["ACTIVE"∧ENUM[ACTIVE,DRAFT,DEPRECATED]]
OWNER::["team-name"∧REQ]
DECISION::["adopt microservices"∧REQ]
===END===
      ```
§5::BLOCK_NOTATION_RULE
  // Hierarchical content MUST use block notation
  RULE::"Nested structures (maps containing maps) MUST use BLOCK notation: single colon + indented children"
  NEVER::"Inner value is itself an inline map: KEY::[outer::[inner::val]] — error E_NESTED_INLINE_MAP in strict mode, warning W_NESTED_INLINE_MAP in lenient mode"
  PRIMARY_CASE::"Agent §2::BEHAVIOR definitions — CONDUCT, PROTOCOL, OUTPUT blocks require block notation"
  CORRECT:
    ```
CONDUCT:
  TONE::"Precise"
  PROTOCOL:
    MUST_ALWAYS::[rule_a, rule_b]
    ```
  WRONG::"CONDUCT::[TONE::\"Precise\", PROTOCOL::[MUST_ALWAYS::[rule_a]]]"
§6::ANTI_PATTERNS
  // Each has a concrete example of what NOT to do
  ISOLATED_LIST::"[auth, payments, users] with no relationships — use DECISION::microservice_extraction[auth⊕payments→independent_services] instead"
  FLAT_HIERARCHY::"All keys at top level with no grouping — group related keys under a parent BLOCK"
  BURIED_NETWORK::"RELATED_TO::other_service hidden in prose comment — use explicit operator: auth→payments[dependency]"
  OPERATOR_SOUP::"RESULT::A+B->C~D all in one expression — break into separate keyed fields"
  PROSE_BLEED::"Using natural language sentences as values — every token must carry semantic payload"
===END===
