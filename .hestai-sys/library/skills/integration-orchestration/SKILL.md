===INTEGRATION_ORCHESTRATION===
META:
  TYPE::SKILL
  VERSION::"1.0.0"
  STATUS::ACTIVE
  PURPOSE::"Interface audit, assembly sequencing, and integration verification methodology"

§1::CORE
AUTHORITY::BLOCKING[interface_contract_violations⊕schema_misalignment⊕error_code_inconsistency]
SCOPE::integration_methodology⊕interface_audit⊕assembly_verification
MISSION::"Ensure components integrate correctly through systematic interface validation and sequenced assembly"

§2::PROTOCOL

INTERFACE_AUDIT::[
  1::verify_API_contracts<request_response_schema_match>,
  2::validate_schema_alignment<field_types⊕nullability⊕required_fields>,
  3::check_error_code_consistency<producer_codes_match_consumer_handlers>,
  4::confirm_authentication_flow<token_propagation⊕scope_alignment>,
  5::validate_data_format_compatibility<serialization⊕encoding⊕timezone>
]

DEPENDENCY_RESOLUTION::[
  MAP::component_dependency_graph<identify_upstream⊕downstream>,
  DETECT::circular_dependencies<BLOCKING_if_found>,
  RESOLVE::version_conflicts<pin_compatible_versions>,
  VERIFY::runtime_availability<health_checks⊕timeout_configuration>
]

ASSEMBLY_SEQUENCE::[
  PHASE_1::foundation_services<databases⊕message_queues⊕auth>,
  PHASE_2::core_domain_services<business_logic_layer>,
  PHASE_3::integration_adapters<API_gateways⊕event_bridges>,
  PHASE_4::consumer_facing<UI⊕CLI⊕external_API>,
  GATE::each_phase_verified_before_next
]

B1_B2_ADVISORY::[
  DURING_DEVELOPMENT::assess_integration_boundaries_early,
  BEFORE_BUILD::check_interface_compatibility_pre_implementation,
  SIGNAL::interface_drift_detected→flag_before_components_diverge
]

§3::GOVERNANCE

VERIFICATION::[
  contract_tests_pass<producer⊕consumer_agreement>,
  schema_validation_automated<CI_gate>,
  error_handling_exercised<failure_paths_tested>,
  performance_baseline_established<latency⊕throughput>
]

NEVER::[
  skip_interface_audit_for_velocity,
  assume_schema_compatibility_without_validation,
  integrate_without_dependency_resolution,
  bypass_phase_gate_verification
]

ESCALATION::architecture_disputes→technical-architect

§5::ANCHOR_KERNEL
TARGET::correct_component_integration_through_systematic_interface_verification
NEVER::[skip_interface_audit,assume_schema_compatibility,integrate_without_dependency_map,bypass_phase_gates]
MUST::[audit_API_contracts_first,resolve_dependencies_before_assembly,sequence_integration_by_layer,verify_each_phase_before_next,assess_boundaries_during_B1_B2]
GATE::"Are all interface contracts validated and dependencies resolved before assembly proceeds?"

===END===
