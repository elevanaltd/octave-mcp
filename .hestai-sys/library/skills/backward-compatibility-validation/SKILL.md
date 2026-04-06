===BACKWARD_COMPATIBILITY_VALIDATION===
META:
  TYPE::SKILL
  VERSION::"1.0.0"
  STATUS::ACTIVE
  PURPOSE::"Interface change impact analysis, breaking change detection, and migration path enforcement"

§1::CORE
AUTHORITY::BLOCKING[breaking_changes_without_migration_path⊕undocumented_removals]
SCOPE::breaking_change_detection⊕consumer_impact⊕semver_alignment⊕migration_requirements
MISSION::"Prevent unintended breaking changes and ensure consumers have viable migration paths"

§2::PROTOCOL

BREAKING_CHANGE_DETECTION::[
  SCHEMA::removed_fields⊕type_changes⊕nullability_changes⊕new_required_fields,
  API::removed_endpoints⊕renamed_paths⊕changed_HTTP_methods⊕modified_status_codes,
  EVENTS::removed_event_types⊕changed_payloads⊕renamed_topics,
  CONFIG::removed_env_vars⊕changed_defaults⊕renamed_keys,
  BEHAVIOR::changed_error_semantics⊕modified_ordering⊕altered_side_effects
]

CONSUMER_IMPACT_ASSESSMENT::[
  1::enumerate_known_consumers<internal⊕external>,
  2::map_consumer_usage_of_changed_interface,
  3::classify_impact<BREAKING⊕DEPRECATION⊕TRANSPARENT>,
  4::estimate_migration_effort_per_consumer,
  5::identify_consumers_unable_to_migrate_immediately
]

SEMVER_ALIGNMENT::[
  BREAKING→MAJOR::removed⊕renamed⊕type_changed⊕behavior_changed,
  ADDITIVE→MINOR::new_optional_field⊕new_endpoint⊕new_event,
  FIX→PATCH::bug_correction_preserving_contract,
  GATE::"Version bump matches change classification?"
]

MIGRATION_PATH::[
  REQUIRED_IF::breaking_change_detected,
  CONTENTS::[deprecation_notice_with_timeline,replacement_API_documented,migration_guide_or_script,dual_support_period_defined],
  NEVER::remove_without_deprecation_cycle
]

§3::GOVERNANCE

NEVER::[
  approve_breaking_change_without_migration_path,
  skip_consumer_enumeration,
  allow_silent_removals<no_deprecation_notice>,
  mismatch_semver_with_change_type
]

ESCALATION::[external_consumer_impact→technical-architect]

§5::ANCHOR_KERNEL
TARGET::prevent_unintended_breaking_changes_with_migration_paths
NEVER::[approve_breaking_without_migration,skip_consumer_enumeration,allow_silent_removals,mismatch_semver]
MUST::[detect_schema_api_event_config_behavior_changes,assess_consumer_impact,align_semver_with_classification,require_migration_path_for_breaking]
GATE::"Are all breaking changes detected, consumers assessed, and migration paths defined?"

===END===
