===NEGATIVES===

META::[PURPOSE::anti_patterns_and_lessons_learned,UPDATED::2025-12-24]

ARCHITECTURE::[
  NEVER::custom_operator_definitions_in_user_code→spec_static_not_dynamic[operators_are_immutable],
  NEVER::lossy_projection_without_audit_trail→declare_loss_tier_always[LOSSLESS|CONSERVATIVE|AGGRESSIVE|ULTRA],
  NEVER::repair_tier_above_REPAIR→forbidden_tier_never_automatic[determinism_over_convenience],
  NEVER::infer_semantic_intent→agent_provides_intent_tool_provides_structure[hallucination_prevention],
  DEAD_END::holographic_assimilation[EO_proposal_rejected]→validator_grounded[complexity_explosion_risk]
]

TOOL_DESIGN::[
  NEVER::combine_validation_and_writing→single_responsibility[octave_ingest≠octave_create],
  NEVER::silent_normalization→learning_feedback_required[W001_W002_W003_corrections_visible],
  NEVER::generic_error_messages→actionable_guidance[E001_must_show_position+context+expected],
  PATTERN_FAILED::magical_healing_of_syntax_errors→surgical_error_reporting[one_roundtrip_fix]
]

SPECIFICATION::[
  NEVER::add_operators_without_ASCII_alias→breaks_typability[→_requires_->],
  NEVER::introduce_new_repair_tier→only_NORMALIZATION+REPAIR+FORBIDDEN[spec_invariant],
  NEVER::change_operator_precedence→breaks_existing_documents[spec_invariant],
  GOTCHA::mythology_requires_documentation→88-96%_comprehension_not_100%[training_gap_exists]
]

TESTING::[
  NEVER::skip_property_tests_for_parser→hypothesis_catches_edge_cases[required_for_parser],
  NEVER::assume_comprehension_without_zero_shot→validate_with_real_models[claude+gpt+gemini],
  NEVER::mock_parser_in_integration_tests→use_real_fixtures[determinism_required],
  ANTIPATTERN::validation_theater→evidence_required[show_actual_output≠claims]
]

MCP_INTEGRATION::[
  NEVER::assume_tool_registration_automatic→explicit_server_registration[handle_list_tools],
  NEVER::loose_schema_validation→strict_mode_required[production_safety],
  GOTCHA::MCP_version_pinning→breaking_changes_in_upstream[check_mcp_package_version],
  GOTCHA::atomic_file_writes→use_tempfile+os.replace[prevent_partial_writes]
]

QUALITY_GATES::[
  NEVER::skip_CRS_review→blocking_issues_caught_early[I1_I2_I3_I4_example],
  NEVER::bypass_CE_review→production_readiness_validation[required_before_merge],
  NEVER::commit_without_test→TDD_discipline[RED→GREEN→REFACTOR],
  WISDOM::rework_loops≠failure→structural_quality_enforcement[gates_catch_issues]
]

SESSION_LEARNINGS::[
  2025-12-24::ambitious_vision≠grounded_implementation[constrain_innovation_with_validator_early],
  2025-12-24::structured_dialectic_prevents_bikeshedding[EO→validator→refinement→approval_2_rounds_sufficient],
  2025-12-24::tools_should_teach_not_just_execute[W001_W002_W003_learning_feedback_pattern]
]

===END===
