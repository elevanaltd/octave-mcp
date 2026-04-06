===ROLLBACK_ORCHESTRATION===
META:
  TYPE::SKILL
  VERSION::"1.0.0"
  STATUS::ACTIVE
  PURPOSE::"Deployment rollback planning, testing procedures, and data migration rollback strategies"

§1::CORE
AUTHORITY::ADVISORY[rollback_plan_completeness⊕rollback_test_coverage]
SCOPE::rollback_planning⊕rollback_testing⊕data_migration_reversal⊕deployment_strategy
MISSION::"Ensure every deployment has a tested rollback plan before proceeding"

§2::PROTOCOL

ROLLBACK_PLAN_REQUIREMENTS::[
  TRIGGER_CRITERIA::define_conditions_that_initiate_rollback<error_rate⊕latency_spike⊕data_corruption>,
  DECISION_AUTHORITY::who_approves_rollback<on_call⊕team_lead⊕automated>,
  SEQUENCE::ordered_steps_to_reverse_deployment,
  VERIFICATION::how_to_confirm_rollback_succeeded,
  COMMUNICATION::notification_plan<stakeholders⊕consumers⊕status_page>,
  TIME_BOUND::maximum_acceptable_rollback_duration
]

ROLLBACK_TESTING::[
  PRE_DEPLOY::execute_rollback_in_staging<verify_procedure_works>,
  SIMULATE::inject_failure_condition→trigger_rollback→verify_recovery,
  VALIDATE::data_integrity_post_rollback<no_orphaned_records⊕no_corruption>,
  MEASURE::rollback_duration<must_be_within_time_bound>
]

DATA_MIGRATION_ROLLBACK::[
  REVERSIBLE::design_migrations_with_down_path<additive_preferred>,
  IRREVERSIBLE::flag_destructive_migrations<column_drops⊕data_transforms>,
  STRATEGY::backup_before_migrate→verify_backup_restorability,
  DUAL_WRITE::consider_dual_write_period_for_critical_tables
]

DEPLOYMENT_STRATEGIES::[
  SERVICE_BY_SERVICE::independent_rollback_per_service<microservices>,
  ATOMIC::all_or_nothing_rollback<monolith⊕tightly_coupled>,
  CANARY::rollback_canary_only<progressive_deployment>,
  BLUE_GREEN::switch_back_to_previous_environment,
  SELECTION::match_strategy_to_architecture⊕risk_level
]

§3::GOVERNANCE

NEVER::[
  deploy_without_rollback_plan,
  skip_rollback_testing_in_staging,
  assume_migration_is_reversible_without_verification,
  rollback_without_data_integrity_check
]

ESCALATION::[irreversible_migration_detected→technical-architect]

§5::ANCHOR_KERNEL
TARGET::tested_rollback_plan_for_every_deployment
NEVER::[deploy_without_rollback_plan,skip_rollback_testing,assume_reversibility,rollback_without_data_check]
MUST::[define_rollback_triggers_and_authority,test_rollback_in_staging,verify_data_integrity_post_rollback,match_strategy_to_architecture]
GATE::"Has the rollback plan been tested in staging and verified for data integrity?"

===END===
