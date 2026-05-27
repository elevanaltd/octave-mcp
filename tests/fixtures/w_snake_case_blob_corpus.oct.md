===W_SNAKE_CASE_BLOB_CORPUS===
META:
  TYPE::TEST_FIXTURE
  VERSION::"1.0"
  PURPOSE::"Empirical corpus for GH#452 W_SNAKE_CASE_BLOB detector — positive and negative cases"

§1::POSITIVE_CASES [must_trigger_W_SNAKE_CASE_BLOB]

P1::
  BECAUSE::replace_app_completion_build_order_with_workflow_first_build_order_to_enable_progressive_SmartSuite_replacement

P2::
  RATIONALE::migration_on_a_moving_target_is_an_anti_pattern_because_app_completion_keeps_shifting

P3::
  GUIDANCE::manual_port_of_5_to_10_active_projects

P4::
  WHY::storage_provider_interface_contract_enables_layer_one_vendor_swap_without_app_redeploys

P5::
  NOTE::progressive_replacement_is_safer_than_big_bang_migration_for_long_running_projects

P6::
  DECISION::[primary_decision_is_to_proceed_with_phase_one_and_revisit_phase_two_in_q3,backup_decision_is_to_defer_phase_three_to_next_year]

P7::
  EVIDENCE::the_observed_pattern_is_that_app_completion_shifts_each_sprint_by_3_to_5_percent

P8::
  CONSEQUENCES::any_change_to_the_interface_breaks_three_or_more_downstream_consumers_at_once

P9::
  TRADEOFFS::speed_of_delivery_is_traded_off_against_correctness_and_long_term_maintainability

P10::
  CAVEAT::this_assumes_that_the_upstream_provider_does_not_change_its_contract

§2::NEGATIVE_CASES [must_NOT_trigger_W_SNAKE_CASE_BLOB]

N1::
  REF::HO-AGREEMENT-SIGNING-OPTION-A-20260427

N2::
  STATUS::SUPERSEDED_BY

N3::
  TABLE::agreement_render_jobs

N4::
  CONFIG_KEY::database_pool_size

N5::
  FLAG::is_user_active

N6::
  PATH::src/octave_mcp/core/grammar/cst.py

N7::
  TOKEN::HEPHAESTUS

N8::
  ID::v1.13.0

N9::
  IDENTIFIER::SmartSuite_API_v2

N10::
  // Non-reasoning field: structural identifier in value position
  PROVIDER_TYPE::storage_provider_interface_contract_for_vendor_swap

===END===
