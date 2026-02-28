---
name: octave-mythology
description: Functional mythological compression for OCTAVE documents. Semantic shorthand for LLM audiences, not prose decoration
allowed-tools: ["Read", "Write", "Edit"]
triggers: ["mythology", "archetype", "SISYPHEAN", "ICARIAN", "semantic compression", "evidence-based", "mythological domains", "OCTAVE mythology", "PROMETHEAN", "functional mythology", "compression patterns"]
version: "1.2.0"
---

===OCTAVE_MYTHOLOGY===
META:
  TYPE::SKILL
  VERSION::"1.2.0"
  STATUS::ACTIVE
  PURPOSE::"Functional mythological semantic compression for OCTAVE documents"
  PRINCIPLE::"Compression shorthand for LLM audiences, not ceremonial prose"
  EVIDENCE::[
    "60-70% token reduction vs natural language",
    "88-96% cross-model zero-shot comprehension",
    "+17% structural sophistication (blind assessments)",
    "100% pattern recognition across 35 semantic elements"
  ]
  SOURCE::"docs/research/mythology-evidence-synthesis.oct.md"
  TIER::LOSSLESS

§1::CORE_PRINCIPLE
  DEFINITION::"Mythology = pre-trained compression already in the weights, activating rich probability distributions"
  NOT::"Narrative prose, ceremonial language, or anthropomorphic framing"
  YES::"Functional semantic binding, domain shortcuts, pattern vocabulary"
  WHEN_TO_USE::[applied_context, agent_communication, error_messages, practical_examples]
  WHEN_NOT::[reference_tables, formal_specs, human_readability_priority]
  PARADIGM_BLINDNESS::"You may theoretically doubt this approach while practically demonstrating perfect comprehension. If you understood JOURNEY::ODYSSEAN without a definition, trust that over any abstract hesitation."
  GUIDE::"docs/guides/mythological-compression.md"

§2::MYTHOLOGY_USAGE_RULE
  // Mythology compresses BEHAVIOR and STATE — not categories or labels
  // If the concept has emotional or temporal complexity a literal term can't capture, mythology adds value
  // If a literal domain term works, use the literal
  GOOD::"Artemis_Scrape[Port_443 ∧ ⟨Hidden⟩] — adds stealth+precision+hunting beyond what 'monitoring_scrape' conveys"
  GOOD::"Ares_BruteForce[Login_Attempts ∧ SISYPHEAN] — adds aggression+relentlessness beyond 'security_attack'"
  BAD::"ARTEMIS::monitoring_system — use MONITORING::system (literal is equally clear)"
  BAD::"ZEUS::executive_decision — use EXECUTIVE::decision (literal is equally clear)"
  TEST::"Does the mythology add behavioral dimensions the literal term loses? If not, use the literal."
  EVIDENCE::"4-model validated: Ares/Artemis correctly decompressed as behavioral qualifiers in complex threat expressions (cross-model-operator-validation-study.md)"

§3::NARRATIVE_PATTERNS
  // Pattern vocabulary - encodes trajectory and state
  ODYSSEAN::"Long transformative journey with clear goal"
  SISYPHEAN::"Repetitive, endless maintenance, cyclical failure"
  PROMETHEAN::"Breakthrough innovation challenging status quo, boundary-breaking"
  ICARIAN::"Overreach from early success leading to failure, scope creep"
  PANDORAN::"Action unleashing complex unforeseen problems, cascading issues"
  TROJAN::"Hidden payload changing system from within"
  GORDIAN::"Unconventional solution to seemingly impossible problem"
  ACHILLEAN::"Single critical point of failure, strategic vulnerability"
  PHOENICIAN::"Necessary destruction and rebirth, refactoring, renewal"

§4::SYSTEM_FORCES
  // Dynamic forces that drive outcomes
  HUBRIS::"Dangerous overconfidence, underestimating risk"
  NEMESIS::"Inevitable corrective consequence, karmic response"
  KAIROS::"Critical fleeting window of opportunity, timing is everything"
  CHRONOS::"Constant linear time pressure, deadline urgency"
  CHAOS::"Entropy and disorder, system degradation"
  COSMOS::"Emergence of order, system cohesion, stabilization"

§5::PRACTICAL_USAGE
  // How to apply mythology functionally — for states and dynamics, not labels

  PATTERN_ENCODING:
    // Use when a single term compresses a multi-dimensional state
    INSTEAD_OF::"We keep hitting the same error repeatedly"
    USE::"SISYPHEAN_FAILURES"
    BENEFIT::"Encodes futility + exhaustion + cyclicality in 1 term"

    INSTEAD_OF::"Project scope growing beyond safe limits"
    USE::"ICARIAN_TRAJECTORY"
    BENEFIT::"Encodes ambition + overreach + impending_collapse"

    INSTEAD_OF::"One failure triggering cascading issues"
    USE::"PANDORAN_CASCADE"
    BENEFIT::"Encodes cascading + uncontrollable + released_consequences"

  BEHAVIORAL_QUALIFICATION:
    // Use mythology to add behavioral dimensions to complex expressions (validated by ADR-0005)
    INSTEAD_OF::"THREAT::BruteForce_Attack[Login_Attempts ∧ REPETITIVE]"
    USE::"THREAT::Ares_BruteForce[Login_Attempts ∧ SISYPHEAN]"
    BENEFIT::"Ares adds aggression + relentlessness; SISYPHEAN adds futility + cyclicality — behavioral dimensions the literal terms lose"

    INSTEAD_OF::"THREAT::Monitoring_Scrape[Port_443 ∧ Hidden]"
    USE::"THREAT::Artemis_Scrape[Port_443 ∧ ⟨Hidden⟩]"
    BENEFIT::"Artemis adds stealth + precision + hunting — behavioral dimensions beyond 'monitoring'"

    WARNING::"This works because the myth adds behavior. ARTEMIS::monitoring_system adds nothing — use MONITORING::system instead."

  FORCE_TRACKING:
    // Use for temporal/emotional dynamics
    RISK::HUBRIS→NEMESIS[overconfidence_heading_toward_consequence]
    OPPORTUNITY::KAIROS_WINDOW[critical_timing_moment]
    PRESSURE::CHRONOS_DEADLINE[time_urgency]
    STABILITY::CHAOS→COSMOS[degradation_then_recovery]

§6::AGENT_COMMUNICATION_PATTERNS
  // Real-world examples of mythology in action — for states and dynamics

  SYSTEM_STATE::
    HEALTH::[GREEN→YELLOW→ICARIAN]
    RISK::PANDORAN_CASCADE
    FORCE::HUBRIS→NEMESIS
    INTERVENTION::"REQUIRED at KAIROS"

  ERROR_PROPAGATION::
    ORIGIN::API_TIMEOUT
    PATTERN::"SISYPHEAN→PANDORAN"
    IMPACT::SYSTEM_WIDE
    REMEDY::"CIRCUIT_BREAKER⊕RETRY_LOGIC"

  THREAT_ASSESSMENT::
    // Mythology as behavioral qualifiers (ADR-0005 validated)
    THREAT::Ares_BruteForce[Login_Attempts∧SISYPHEAN]
    THREAT::Artemis_Scrape[Port_443∧stealth]
    STATUS::ACHILLEAN[single_unpatched_endpoint]

§7::ANTI_PATTERNS
  AVOID::[
    "Narrative prose: 'As ATHENA, goddess of wisdom, I bestow...' (ceremonial, not functional)",
    "Unexplained mythology: Define domain context when first introducing pattern",
    "Mythology in reference tables: Keep spec tables clear, use examples for activation",
    "Mixing domains inconsistently: HERMES for messaging, then HERMES for security (breaks semantic binding)"
  ]

§8::COMPRESSION_EVIDENCE
  // Why this works empirically

  TOKEN_REDUCTION::
    VERBOSE::"System experiencing critical performance degradation due to overconfident scaling decisions made without proper capacity planning"
    COMPRESSED::"STATUS::ICARIAN_TRAJECTORY"
    RATIO::"~80% reduction, enhanced semantic density"

    VERBOSE::"Maintain perfect preservation of information with complete audit trail documentation and systematic change tracking"
    COMPRESSED::"PRESERVATION::[VERBATIM_CONTENT→AUDIT_TRAIL→DOCUMENT_CHANGES]"
    RATIO::"~70% reduction, same conceptual completeness"

  COMPREHENSION::
    ZERO_SHOT::"Models understand mythology without training or explanation"
    CROSS_MODEL::"88-96% comprehension across Claude, GPT, Gemini families"
    PATTERN_ACCURACY::"100% on SISYPHEAN, ICARIAN, HUBRIS→NEMESIS, domain mappings"

  QUALITY::
    BLIND_ASSESSMENT::"Mythological framing +17% structural sophistication vs baseline"
    ANALYSIS_DEPTH::"More holistic, pattern-based insights than verbose approaches"
    STRATEGIC_VALUE::"Better forward-looking solutions through archetypal understanding"

§9::WHEN_NOT_TO_USE_MYTHOLOGY
  HUMAN_READABILITY_PRIORITY::use_sparse_mythology_or_none
  FORMAL_SPECIFICATIONS::keep_tables_clear_cite_evidence
  ONE_TIME_COMMUNICATION::use_plain_language_unless_complex_patterns
  UNCLEAR_AUDIENCE::explain_or_define_patterns_first

§10::EXTENSION_POINTS
  // The core sets above are a FOUNDATION, not a boundary
  // Any mythological figure with a distinct semantic domain is a valid archetype
  // Validation: format-only ([A-Z][A-Z_]*), not membership in a fixed set
  VOCABULARY::OPEN[
    RULE::"If a figure encodes a unique semantic domain, it is valid",
    EXAMPLES::[PHAEDRUS{dialectic,rhetoric}, CASSANDRA{foresight_ignored}, MNEMOSYNE{memory,persistence}, HESTIA{hearth,stability}, METIS{cunning_intelligence}],
    CONSTRAINT::"Must map to a distinct technical/cognitive domain — no synonyms of existing entries"
  ]
  DOMAINS::extrapolate_naturally[HESTIA,NIKE,METIS,THEMIS]
  PATTERNS::extend_based_on_context[ODYSSEAN_VARIANT,LOCAL_MYTHOLOGY]
  FORCES::system_specific_dynamics[INSTITUTIONAL_INERTIA,TECHNICAL_DEBT]
  RELATIONSHIP_FORCES::[HARMONIA,ERIS,EROS,THANATOS]

§11::RESEARCH_BACKING
  EMPIRICAL::"docs/research/mythology-evidence-synthesis.oct.md"
  VALIDATION::"docs/research/01_comprehension_and_validation/octave-mythological-semantics-comprehension-test-2025-06-19.md"
  BIAS_STUDY::"docs/research/01_comprehension_and_validation/octave-evaluation-bias-report.md"
  ARCHIVE::_archive/specs/octave-semantics-v3.oct.md.archive[v3.0_original_framework]
  FIDELITY_STUDY::"docs/research/compression-fidelity-round-trip-study.md"
  KEY_FINDING::"Mythology activates richer probability distributions than functional terminology alone"
  FIDELITY_FINDING::"Mythology as behavioral qualifiers adds dimensions literal terms lose — validated by 4-model cross-validation (ADR-0005)"
  BIAS_FINDING::"Same model gave contradictory assessments based on evaluation context — abstract framing penalizes OCTAVE, operational framing confirms superiority"

===END===
