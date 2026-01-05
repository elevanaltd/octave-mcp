===OCTAVE_MYTHOLOGY_REGISTRY===
// Canonical registry for mythological semantic compression tokens used in OCTAVE
// This is a living vocabulary document. Specs should point here rather than embedding exhaustive lists.

META:
  TYPE::REGISTRY
  VERSION::"1.0"
  STATUS::DRAFT
  PURPOSE::"Provide a stable, extensible, test-gated vocabulary for mythological semantic compression"
  SCOPE::"Mythology tokens only (Domains, Patterns, Forces, Relationships)"
  GOVERNANCE::"Promotion via validation; avoid synonym drift"
  SOURCES::[
    _archive/specs/octave-semantics-v1.oct.md.archive,
    skills/octave-mastery/SKILL.md,
    skills/octave-mythology/SKILL.md
  ]

§1::TAXONOMY
  // Categories must not be mixed inside a single list without labeling
  CATEGORIES::[
    DOMAIN_ARCHETYPE::"Technical responsibility layers / persistent strengths",
    PATTERN_TOKEN::"Situations and narrative trajectories (state/trajectory compression)",
    FORCE::"System dynamics (time pressure, entropy, opportunity)",
    RELATIONSHIP::"Interaction dynamics between components/actors"
  ]

§2::TIER_0_CORE_VALIDATED
  // Tier 0 is intentionally small and stable.
  // These entries are consistent across the repo’s existing canonical docs (see META::SOURCES).

  DOMAIN_ARCHETYPES::
    ZEUS::
      STATUS::CORE_VALIDATED
      WISDOM::"Executive function, authority, strategic direction, final arbitration"
      BEST_FOR::[escalation,final_decision,conflict_arbitration]
      NOT_FOR::[implementation_details]
    ATHENA::
      STATUS::CORE_VALIDATED
      WISDOM::"Strategic wisdom, planning, elegant solutions, deliberate action"
      BEST_FOR::[architecture,governance,design_decisions,risk_assessment]
      NOT_FOR::[raw_debug_spam]
    APOLLO::
      STATUS::CORE_VALIDATED
      WISDOM::"Analytics, clarity, insight, diagnosis, revealing truth"
      BEST_FOR::[analysis,root_cause,hypothesis_testing,metrics]
      NOT_FOR::[handwavy_storytelling]
    HERMES::
      STATUS::CORE_VALIDATED
      WISDOM::"Communication, translation, APIs, networking, messaging"
      BEST_FOR::[integration,contracts,interfaces,coordination]
      NOT_FOR::[security_policy]
    HEPHAESTUS::
      STATUS::CORE_VALIDATED
      WISDOM::"Infrastructure, tooling, engineering craft, automation, build systems"
      BEST_FOR::[implementation,tooling,reliability_engineering]
      NOT_FOR::[high_level_governance_only]
    ARES::
      STATUS::CORE_VALIDATED
      WISDOM::"Security, defense, stress testing, adversarial analysis"
      BEST_FOR::[threat_modeling,hardening,attack_simulation]
      NOT_FOR::[UX_polish]
    ARTEMIS::
      STATUS::CORE_VALIDATED
      WISDOM::"Monitoring, observation, logging, alerting, precision targeting"
      BEST_FOR::[observability,signal_design,detection]
      NOT_FOR::[broad_strategy]
    POSEIDON::
      STATUS::CORE_VALIDATED
      WISDOM::"Data stores, databases, persistence, large data pools"
      BEST_FOR::[storage,querying,data_modeling]
      NOT_FOR::[frontend_interactions]
    DEMETER::
      STATUS::CORE_VALIDATED
      WISDOM::"Resources, capacity, budgeting, scaling, growth"
      BEST_FOR::[capacity_planning,performance_budgeting,cost_controls]
      NOT_FOR::[one_off_bugfixes]
    DIONYSUS::
      STATUS::CORE_VALIDATED
      WISDOM::"UX, creativity, experimentation, transformation, productive chaos"
      BEST_FOR::[ideation,product_exploration,refactor_reframes]
      NOT_FOR::[strict_compliance]

  PATTERN_TOKENS::
    ODYSSEAN::
      STATUS::CORE_VALIDATED
      WISDOM::"Long, difficult, transformative journey with a clear goal"
      BEST_FOR::[multi_phase_projects,migrations,roadmaps]
      NOT_FOR::[small_tickets]
    SISYPHEAN::
      STATUS::CORE_VALIDATED
      WISDOM::"Repetitive, endless maintenance or cyclical failure"
      BEST_FOR::[toil,recurring_incidents,tech_debt_loops]
      NOT_FOR::[novel_one_time_issues]
    PROMETHEAN::
      STATUS::CORE_VALIDATED
      WISDOM::"Breakthrough innovation that challenges constraints (with tradeoffs)"
      BEST_FOR::[new_architecture,novel_solutions]
      NOT_FOR::[routine_refactors]
    ICARIAN::
      STATUS::CORE_VALIDATED
      WISDOM::"Overreach from early success → increased risk of collapse"
      BEST_FOR::[scope_creep_warnings,ambition_checks]
      NOT_FOR::[steady_incremental_work]
    PANDORAN::
      STATUS::CORE_VALIDATED
      WISDOM::"Cascading unforeseen consequences / expanding blast radius"
      BEST_FOR::[incident_analysis,change_risk]
      NOT_FOR::[contained_changes]
    TROJAN::
      STATUS::CORE_VALIDATED
      WISDOM::"Hidden payload/change-from-within (stealth coupling, supply chain risk)"
      BEST_FOR::[dependency_risk,review_focus]
      NOT_FOR::[transparent_changes]
    GORDIAN::
      STATUS::CORE_VALIDATED
      WISDOM::"Decisive cut-through-complexity solution"
      BEST_FOR::[simplification,hard_tradeoffs,unblocking]
      NOT_FOR::[over-optimization]
    ACHILLEAN::
      STATUS::CORE_VALIDATED
      WISDOM::"Single critical weakness in an otherwise strong system"
      BEST_FOR::[risk_registers,single_points_of_failure]
      NOT_FOR::[distributed_failures]
    PHOENICIAN::
      STATUS::CORE_VALIDATED
      WISDOM::"Destruction and rebirth (refactor, redesign, deprecate/rebuild)"
      BEST_FOR::[major_refactors,platform_replacement]
      NOT_FOR::[quick_patches]
    ORPHEAN::
      STATUS::CORE_VALIDATED
      WISDOM::"Deep dive into internals to retrieve something valuable (rescue mission)"
      BEST_FOR::[legacy_archeology,hard_debugging]
      NOT_FOR::[surface_level_tasks]

  FORCES::
    HUBRIS::
      STATUS::CORE_VALIDATED
      WISDOM::"Dangerous overconfidence"
      BEST_FOR::[risk_calls,guardrails]
    NEMESIS::
      STATUS::CORE_VALIDATED
      WISDOM::"Corrective consequence / backlash"
      BEST_FOR::[postmortems,tradeoff_realism]
    KAIROS::
      STATUS::CORE_VALIDATED
      WISDOM::"Critical fleeting window; timing matters"
      BEST_FOR::[release_windows,opportunity_cost]
    CHRONOS::
      STATUS::CORE_VALIDATED
      WISDOM::"Relentless time pressure / deadlines"
      BEST_FOR::[planning_under_time,scope_triage]
    CHAOS::
      STATUS::CORE_VALIDATED
      WISDOM::"Entropy and disorder"
      BEST_FOR::[stability_work,incident_states]
    COSMOS::
      STATUS::CORE_VALIDATED
      WISDOM::"Order emerging from chaos"
      BEST_FOR::[stabilization,hardening]
    MOIRA::
      STATUS::CORE_VALIDATED
      WISDOM::"Hard non-negotiables; fated constraints"
      BEST_FOR::[platform_limits,legal_or_physical_constraints]
    TYCHE::
      STATUS::CORE_VALIDATED
      WISDOM::"Chance / randomness / external unpredictability"
      BEST_FOR::[uncertainty,stochastic_failures]

  RELATIONSHIPS::
    HARMONIA::
      STATUS::CORE_VALIDATED
      WISDOM::"Balanced synergy; stable integration"
      BEST_FOR::[integration_design,coherence]
    ERIS::
      STATUS::CORE_VALIDATED
      WISDOM::"Productive conflict; competition that drives improvement"
      BEST_FOR::[design_reviews,red_team]
    EROS::
      STATUS::CORE_VALIDATED
      WISDOM::"Binding attraction; coupling"
      BEST_FOR::[dependency_discussion,coupling_management]
    THANATOS::
      STATUS::CORE_VALIDATED
      WISDOM::"Unbinding dissolution; fragmentation"
      BEST_FOR::[decoupling,decomposition,sunsets]

§3::TIER_1_CANDIDATES_UNVALIDATED
  // Candidates are allowed only when you can tolerate lower semantic binding.
  // Promotion requires a comprehension/usage test and at least one stable usage example.

  DOMAIN_ARCHETYPES::
    THEMIS::
      STATUS::CANDIDATE_UNVALIDATED
      WISDOM::"Policy, rules, governance-as-law, consistency"
      BEST_FOR::[compliance,policy_enforcement]
    METIS::
      STATUS::CANDIDATE_UNVALIDATED
      WISDOM::"Cunning pragmatism; strategy under uncertainty"
      BEST_FOR::[tactical_planning,ambiguity]
    HESTIA::
      STATUS::CANDIDATE_UNVALIDATED
      WISDOM::"Stability, baseline reliability, operational calm"
      BEST_FOR::[ops_sanity,keep_it_simple]
    HERA::
      STATUS::CANDIDATE_UNVALIDATED
      WISDOM::"Stakeholders, power dynamics, organizational reality"
      BEST_FOR::[stakeholder_alignment,org_constraints]
    IRIS::
      STATUS::CANDIDATE_UNVALIDATED
      WISDOM::"Routing/dispatch; status propagation"
      BEST_FOR::[handoffs,routing,queues]
    MNEMOSYNE::
      STATUS::CANDIDATE_UNVALIDATED
      WISDOM::"Memory, lineage, audit trails, documentation continuity"
      BEST_FOR::[knowledge_mgmt,traceability]

  PATTERN_TOKENS::
    CASSANDRAN::
      STATUS::CANDIDATE_UNVALIDATED
      WISDOM::"Accurate warning ignored until disaster"
      BEST_FOR::[risk_communication,ignored_signals]
    DAMOCLEAN::
      STATUS::CANDIDATE_UNVALIDATED
      WISDOM::"Constant looming risk"
      BEST_FOR::[latent_risk,tech_debt_interest]
    HYDRAN::
      STATUS::CANDIDATE_UNVALIDATED
      WISDOM::"Fix one head, two grow back"
      BEST_FOR::[regressions,bug_classes]
    TANTALIAN::
      STATUS::CANDIDATE_UNVALIDATED
      WISDOM::"Perpetually-near goal; chronic near-miss"
      BEST_FOR::[flaky_tests,almost_fixed_issues]
    LABYRINTHINE::
      STATUS::CANDIDATE_UNVALIDATED
      WISDOM::"Complexity maze; navigation dominates"
      BEST_FOR::[onboarding_cost,sprawling_systems]
    SCYLLA_CHARYBDIS::
      STATUS::CANDIDATE_UNVALIDATED
      WISDOM::"Forced tradeoff between two bad outcomes"
      BEST_FOR::[hard_tradeoffs]

  FORCES::
    ANANKE::
      STATUS::CANDIDATE_UNVALIDATED
      WISDOM::"Necessity; must-satisfy constraints"
      BEST_FOR::[non_negotiables,hard_requirements]

§4::SELECTION_GUIDELINES
  // Keep usage small; the point is compression + semantic binding.
  RULES::[
    prefer_TIER_0_for_specs_and_agent_profiles,
    max_domain_archetypes::3,
    max_pattern_tokens::2,
    forces_and_relationships::"use only when they add non-obvious structure",
    do_not_roleplay::"No ceremonial prose (functional shorthand only)",
    do_not_invent_tokens_in_flight::"Add to registry first, then use"
  ]

§5::VALIDATION_AND_PROMOTION_PROTOCOL
  // Minimal, test-gated growth process
  PROMOTION::
    CANDIDATE→CORE_VALIDATED::[
      add_entry_with_STATUS::CANDIDATE_UNVALIDATED,
      add_1_line_definition_and_NOT_FOR,
      add_2_usage_examples[minimal,realistic],
      run_comprehension_test_across_models[min_3_models],
      record_results_as_EVIDENCE::[test_id,date],
      if_comprehension≥0.9_and_no_overlap→promote_to_CORE_VALIDATED
    ]

§6::CHANGE_CONTROL
  STABILITY_PRINCIPLE::"Prefer fewer, sharper meanings over exhaustive coverage"
  DRIFT_PREVENTION::[
    avoid_near_synonyms,
    require_NOT_FOR_clauses,
    deprecate_instead_of_redefining
  ]

===END===
