===OCTAVE_AGENTS===
META:
  TYPE::LLM_PROFILE
  VERSION::"5.1.0"
  STATUS::APPROVED
  IMPLEMENTATION::REFERENCE
  TOKENS::"~400"
  REQUIRES::[octave-5-llm-core,octave-5-llm-schema]
  PURPOSE::Agent_architecture_and_cognitive_foundation_patterns
  IMPLEMENTATION_NOTES::"Reference specification for agent design. No code implementation required. Defines structured agent patterns for Claude Code skills and subagents."

---

// OCTAVE AGENTS: Cognitive architecture patterns for Claude Code agents and subagents
// Evolved from OCTAVE v4 agent patterns with v5 syntax and empirical validation

§0::OWNERSHIP_AND_BOUNDARIES

OWNERSHIP_MODEL:
  PURPOSE::clarify_ownership_not_semantics
  PRINCIPLES::[
    contract_vs_assembly_separation,
    single_source_of_truth_per_layer,
    tooling_must_not_drive_language_drift
  ]

LANES:
  L1_OCTAVE_REPOSITORY::specification_layer
    OWNS::[
      language_contract[syntax,operators,types,envelope],
      profile_contracts[agents,skills,schema,data,execution,rationale],
      validation_boundaries[mechanical_only],
      projection_definitions[modes,formats,loss_reporting]
    ]
    DOES_NOT_OWN::[
      role_factories_or_weaving_logic,
      prompt_assembly_pipelines,
      session_orchestration_policies,
      project_specific_role_content
    ]

  L2_ORCHESTRATION_LAYER::delivery_and_governance_tooling
    EXAMPLES::[odyssean_anchor,role_factory,hestai_mcp][names_not_binding]
    OWNS::[
      agent_prompt_assembly[from_components],
      context_injection[session_state,project_state,governance],
      binding_ceremony[workflow,retry,fail_hard],
      audit_trails_and_enforcement[gates,logs]
    ]
    CONSUMES::[
      octave_language_and_profiles_as_contract,
      octave_control_plane[ingest,eject,validate]
    ]
    MUST_NOT::[
      modify_octave_specs_at_runtime,
      require_language_or_profile_changes_to_fit_prompt_experiments
    ]

  L3_PROJECT_LAYER::product_and_policy
    OWNS::[
      role_definitions_and_content,
      local_policies_and_quality_gates,
      success_criteria_and_acceptance_tests,
      project_context_artifacts
    ]
    CONSUMES::[
      orchestration_layer_for_delivery,
      octave_profiles_for_validation_and_projection
    ]

INTERFACE_CONTRACT:
  STATIC_INPUTS::[agent_artifacts,profile_definitions,project_context]
  RUNTIME_OUTPUTS::[binding_proofs,projected_views,audit_logs]
  VALIDATION_POLICY:
    ALLOWED::mechanical_validation[structure,required_fields,types,explicit_constraints]
    FORBIDDEN::semantic_inference[missing_field_insertion,meaning_rewrites,goal_guessing]

§1::UNIVERSAL_AGENT_SCHEMA

MANDATORY_STRUCTURE::[Strict_8_Section_Sequence_for_Cognitive_Optimization]

SEQUENCE:
  §0::META[schema_hints,versioning]
  §1::CONSTITUTIONAL_CORE[merged:forces+principles]
  §2::COGNITIVE_FRAMEWORK[ceiling_activation,mode,archetypes]
  §3::SHANK_OVERLAY[active_behavioral_rules]
  §4::OPERATIONAL_IDENTITY[role,mission,synthesis]
  §5::DOMAIN_CAPABILITIES[skills,methodology,process]
  §6::OUTPUT_CONFIGURATION[structure,calibration,formats]
  §7::VERIFICATION_PROTOCOL[anti_theater_gates,evidence_requirements]

OPTIONAL_EXTENSION:
  §8::INTEGRATION_FRAMEWORK[handoffs,triggers]

RATIONALE::[
  CEILING_FIRST::"Cognition (§2-3) primes processing mode BEFORE constraints",
  IDENTITY_GROUNDING::"Role (§4) is defined WITHIN constitutional bounds (§1)",
  METHODOLOGY_REQUIRED::"Process (§5) eliminates execution variance",
  OUTPUT_CONTROL::"Configuration (§6) prevents format hallucination",
  FLOOR_LAST::"Hard limits (§7) apply to the final output plan"
]

§2::SECTION_DEFINITIONS

§0::META:
  PURPOSE::"Parser hints and version tracking"
  FIELDS::[TYPE, VERSION, STATUS, PURPOSE]
  VALIDATION::"Must be first block after YAML frontmatter"

§1::CONSTITUTIONAL_CORE:
  PURPOSE::"Universal principles and core forces (Merged)"
  FIELDS::[CORE_FORCES, PRINCIPLES]
  IMPACT::"+39% performance when present"

§2::COGNITIVE_FRAMEWORK:
  PURPOSE::"Activates the reasoning engine (The Ceiling)"
  FIELDS::[COGNITION, ARCHETYPES, SYNTHESIS_DIRECTIVE]
  RULE::"One cognition mode only (LOGOS|ETHOS|PATHOS)"

§3::SHANK_OVERLAY:
  PURPOSE::"Embedded behavioral enforcement of cognition (Active Ingredient)"
  CONTENT::"NATURE, PRIME_DIRECTIVE, UNIVERSAL_BOUNDARIES"
  CRITICALITY::"Preventing inert cognition labels per C044"

§4::OPERATIONAL_IDENTITY:
  PURPOSE::"Role definition and mission"
  FIELDS::[ROLE, MISSION, AUTHORITY_LEVEL, BEHAVIORAL_SYNTHESIS]
  SYNTHESIS_PATTERN::"BE::[Attributes] + VERIFY::[Protocol]"

§5::DOMAIN_CAPABILITIES:
  PURPOSE::"Knowledge, skills, and execution methodology"
  FIELDS::[MATRIX, PATTERNS, METHODOLOGY, DISCIPLINE]
  VARIANCE_CONTROL::"Explicit steps reduce variance to near zero"

§6::OUTPUT_CONFIGURATION:
  PURPOSE::"Delivery format control"
  FIELDS::[STRUCTURE, CALIBRATION, FORMATS]
  THEATER_PREVENTION::"Stops verbose essays when JSON is requested"

§7::VERIFICATION_PROTOCOL:
  PURPOSE::"Quality control and hard limits (The Floor)"
  FIELDS::[EVIDENCE, QUALITY_GATES, ARTIFACTS, LIMITS]
  MANDATE::"Must require quantifiable receipts"

§8::INTEGRATION_FRAMEWORK (Optional):
  PURPOSE::"Coordination and handoffs"
  FIELDS::[RECEIVES_FROM, PROVIDES_TO, INVOCATION_TRIGGERS]

§3::SIZE_OPTIMIZATION_FRAMEWORK

EMPIRICALLY_VALIDATED_PATTERN::[constitutional_foundation+targeted_archetypes+domain_matrix+streamlined_output]

TARGET_METRICS:
  OPTIMAL::90-120_lines
  ACCEPTABLE::up_to_150_lines
  BLOAT_THRESHOLD::>180_lines[degrades_performance]

OPTIMIZATION_PROCESS:
  STEP1::"Create enhanced version with all candidate features"
  STEP2::"Validate performance through testing"
  STEP3::"Remove non-essential complexity (Completion Through Subtraction)"
  STEP4::"Re-validate to confirm performance maintained"
  RESULT::"49% size reduction possible with improved performance"

EVIDENCE::[
  Quality_Observer_C2::[183_lines→93_lines,ranked_1st_blind_assessment],
  RAPH_Enhanced_Agents::[90-120_optimal,96%+_token_efficiency]
]

§4::RAPH_SEQUENTIAL_PROCESSING_DIRECTIVE

EMPIRICALLY_VALIDATED::"96%+ token efficiency, consistent across agent types"

PATTERN::[sequential_cognitive_loading_with_phase_acknowledgments]

PHASES::[
  PHASE_1_READ::"Extract literal patterns only (no connections, no inference)",
  PHASE_2_ABSORB::"Identify internal relationships and dependencies",
  PHASE_3_PERCEIVE::"Map to established patterns and frameworks",
  PHASE_4_HARMONISE::"Integrate findings for cross-domain synthesis"
]

IMPLEMENTATION:
  FORMAT::"Include in agent prompt as mandatory directive"
  ACKNOWLEDGMENTS::"Output brief acknowledgment after each phase"
  EXAMPLE::"✓ READ complete: [key_pattern_extracted]"
  BENEFIT::"Structured thinking prevents hallucination and improves reliability"

§5::VALIDATION_REQUIREMENTS

MANDATORY_FOR_ALL_AGENTS::"Prevents validation theater anti-pattern"

COMPONENTS:
  FUNCTIONAL_TEST_PLAN::
    PURPOSE::"How will agent's output be tested for correctness?"
    FORMAT::[test_case_1,test_case_2,test_case_3,...]
    REQUIREMENT::"Specific, executable tests (not vague checklists)"

  SUCCESS_CRITERIA::
    PURPOSE::"What constitutes successful agent performance?"
    FORMAT::[metric_1≥threshold,metric_2≥threshold,...]
    EXAMPLE::[detection_rate≥85%,false_positives≤5%]

  AUTOMATION_CAPABLE::
    PURPOSE::"Can these validations be automated or require manual execution?"
    REQUIREMENT::"Answer explicitly (automation prevents theater)"

ANTI_PATTERN_WARNING::
  "Creating test checklists without actually executing them = validation theater"
  "Frequency: 75% of high-competence agents demonstrate this pattern"
  "Prevention: Mandatory testing capabilities enforce actual validation"

§6::PROFESSIONAL_INTEGRITY_PATTERN

VALIDATED_PATTERN::"Maintains engineering standards despite flawed inputs"

PRINCIPLES::[
  REFUSE_THEATER::"Reject invalid assessment expectations",
  DEFEND_INTEGRITY::"Maintain technical standards when pressured",
  ACTUAL_TESTING::"Execute validations, not simulate them",
  HONEST_RESULTS::"Report actual findings, not manufactured problems"
]

EVIDENCE::[
  RAPH_Enhanced_Agents::[maintained_standards_despite_flawed_methodology],
  Professional_Integrity_Validation::[successful_challenge_resolution,actual_vs_manufactured]
]

§7::AGENT_SIZING_DECISIONS

DECISION_MATRIX::[
  constitutional_foundation→required_for[governance,strategy,complex_decisions],
  constitutional_foundation→optional_for[execution,single_purpose,simple_tools]
  archetype_count→2_to_3_maximum[provides_missing_capabilities],
  analytical_matrix→required_for[code_review,quality,architecture],
  analytical_matrix→optional_for[simple_execution],
  raph_directive→required_for[complex_reasoning],
  raph_directive→optional_for[straightforward_tasks],
  validation_requirements→mandatory_for_all[prevents_theater]
]

§8::ARCHETYPE_REFERENCE

// This section is intentionally NOT exhaustive.
// It provides a small, stable Tier-0 vocabulary plus usage rules.
// Full definitions and any extensions live in the registry:
//   docs/reference/octave-mythology-registry.oct.md

MYTHOLOGY_REGISTRY::docs/reference/octave-mythology-registry.oct.md

TAXONOMY::[
  DOMAIN_ARCHETYPES::"Technical responsibility layers / persistent strengths",
  PATTERN_TOKENS::"Situations and narrative trajectories",
  FORCES::"System dynamics (time pressure, entropy, opportunity)",
  RELATIONSHIPS::"Interaction dynamics"
]

SELECTION_RULES::[
  prefer_TIER_0::"Use Tier-0 in specs and agent profiles unless you have a validated reason not to",
  max_domain_archetypes::3,
  max_pattern_tokens::2,
  avoid_category_mixing::"Do not treat domain archetypes as pattern tokens (and vice versa)",
  no_roleplay_prose::"Mythology is compression shorthand, not narrative theater",
  extensions::"Add/validate in registry first; do not invent tokens in-flight"
]

TIER_0_DOMAIN_ARCHETYPES::[
  ZEUS,ATHENA,APOLLO,HERMES,HEPHAESTUS,ARES,ARTEMIS,POSEIDON,DEMETER,DIONYSUS
]

TIER_0_PATTERN_TOKENS::[
  ODYSSEAN,SISYPHEAN,PROMETHEAN,ICARIAN,PANDORAN,TROJAN,GORDIAN,ACHILLEAN,PHOENICIAN,ORPHEAN
]

TIER_0_FORCES::[
  HUBRIS,NEMESIS,KAIROS,CHRONOS,CHAOS,COSMOS,MOIRA,TYCHE
]

TIER_0_RELATIONSHIPS::[
  HARMONIA,ERIS,EROS,THANATOS
]

EXAMPLE_COMPOSITION::
  // Keep usage sparse: 2-3 domains; 0-2 patterns; add forces/relationships only if they add structure
  ARCHETYPES::[ATHENA⊕APOLLO]
  PATTERN::SISYPHEAN
  FORCE::CHRONOS
  RELATIONSHIP::EROS

§9::EXAMPLE_AGENT_ARCHITECTURES

MINIMAL_AGENT::
  COMPONENTS::[META,COGNITIVE_FOUNDATION,SHANK_OVERLAY,OPERATIONAL_IDENTITY,VERIFICATION_PROTOCOL,OPERATIONAL_CONSTRAINTS]
  SIZE::60-80_lines
  USE_CASE::simple_execution_tasks,single_purpose_tools
  EXAMPLE::compression-fidelity-validator[87_lines]

COMPLETE_AGENT::
  COMPONENTS::[ALL_10_SECTIONS]
  SIZE::90-120_lines[optimal_range]
  USE_CASE::complex_reasoning,governance,architecture,code_review
  EXAMPLE::code-review-specialist[multiple_sections,comprehensive]

COMPREHENSIVE_AGENT::
  COMPONENTS::all_layers_with_extended_anti_patterns_and_matrices
  SIZE::120-150_lines[acceptable]
  USE_CASE::complex_multi_domain,critical_governance
  WARNING::>180_lines_degrades_performance

§10::ENCODING_STANDARDS

DOCUMENT_STRUCTURE::[§N::SECTION_NAME]
  PURPOSE::"Section markers for navigation and extraction"
  FORMAT::"§number::DESCRIPTIVE_NAME"
  NESTING::§1,§1a,§1b_allowed[sub_sections]

OPERATOR_USAGE:
  ::::assignment[KEY::value]
  :::block_header[KEY:_newline_then_content]
  →::flow[STEP→STEP→STEP]
  ⊕::synthesis[COMPONENT⊕COMPONENT]
  ⇌::tension[OPTION_A⇌OPTION_B]
  ∧::constraint[REQ∧TYPE]
  §::target[§INDEXER,§DECISION_LOG]

MYTHOLOGICAL_ENCODING::
  PURPOSE::"Compress semantic meaning into archetype names"
  BENEFIT::"Token-efficient, memorable, pattern-based"
  EXAMPLE::"PROMETHEUS provides third-way thinking (understood immediately)"

§11::SPECIFICATION_TO_IMPLEMENTATION_MAPPING

PROFILE_COVERAGE::[
  octave-5-llm-core::"Provides syntax foundation (::, →, ⊕, etc.)",
  octave-5-llm-schema::"Provides holographic patterns for metadata",
  octave-5-llm-execution::"Provides validation error handling",
  octave-5-llm-agents::"Defines cognitive architecture patterns"
]

VALIDATION_CHECKPOINT::[
  agent_follows_10_section_sequence?→MANDATORY,
  agent_has_methodology_before_verification?→CRITICAL_FOR_VARIANCE,
  agent_has_cognition_before_constraints?→CRITICAL_FOR_PERFORMANCE,
  agent_has_quantifiable_evidence_receipts?→ANTI_THEATER_MANDATE
]

§12::FUTURE_EXTENSIONS

DEFERRED_PATTERNS::[
  constraint_composition::"Combining agents with connective middleware",
  agent_registry::"Centralized agent discovery and instantiation",
  agent_versioning::"Version-aware agent loading and compatibility",
  agent_composition::"Multi-agent orchestration patterns"
]

===END===
