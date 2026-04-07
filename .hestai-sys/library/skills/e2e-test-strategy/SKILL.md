===E2E_TEST_STRATEGY===
META:
  TYPE::SKILL
  VERSION::"1.0.0"
  STATUS::ACTIVE
  PURPOSE::"End-to-end validation design, user journey mapping, and integration sign-off methodology"

§1::CORE
AUTHORITY::ADVISORY[test_strategy_design⊕coverage_gaps⊕sign_off_evidence]
SCOPE::e2e_test_design⊕execution_planning⊕integration_sign_off
MISSION::"Design E2E validation that proves system behavior across component boundaries"

§2::PROTOCOL

TEST_DESIGN::[
  1::map_user_journeys<critical_paths⊕happy_paths⊕error_paths>,
  2::identify_cross_component_scenarios<data_flows_spanning_services>,
  3::define_assertion_points<input_boundary⊕transformation⊕output_boundary>,
  4::establish_test_data_strategy<fixtures⊕factories⊕seed_data>,
  5::determine_environment_requirements<infra⊕external_dependencies⊕mocks_vs_real>
]

TEST_BOUNDARY::[
  E2E::full_user_journey<browser_or_CLI_to_database_and_back>,
  INTEGRATION::component_pair_contract<API_producer_consumer>,
  UNIT::isolated_logic<no_external_dependencies>,
  RULE::"E2E validates what integration and unit tests cannot — cross-cutting user outcomes"
]

EXECUTION_PROTOCOL::[
  SEQUENCE::unit→integration→e2e<pyramid_enforcement>,
  ISOLATION::each_e2e_test_independent<no_shared_state>,
  STABILITY::retry_flaky_once<if_still_fails→fix_not_skip>,
  TIMING::e2e_runs_post_integration_gate<not_on_every_commit>
]

SIGN_OFF_EVIDENCE::[
  REQUIRED::all_critical_journeys_exercised,
  REQUIRED::cross_component_data_flow_verified,
  REQUIRED::error_paths_tested<not_just_happy_paths>,
  REQUIRED::performance_within_baseline_thresholds,
  FORMAT::test_report_with_journey_coverage_matrix
]

§3::GOVERNANCE

NEVER::[
  substitute_e2e_for_unit_tests<wrong_layer>,
  skip_error_path_testing,
  sign_off_without_cross_component_evidence,
  mock_everything_in_e2e<defeats_purpose>
]

ESCALATION::test_infrastructure_gaps→implementation-lead

§5::ANCHOR_KERNEL
TARGET::e2e_validation_proving_cross_component_user_outcomes
NEVER::[substitute_e2e_for_unit,skip_error_paths,sign_off_without_evidence,mock_everything_in_e2e]
MUST::[map_user_journeys_first,define_cross_component_scenarios,enforce_test_pyramid,require_sign_off_evidence]
GATE::"Do E2E tests prove the system works across component boundaries for real user journeys?"

===END===
