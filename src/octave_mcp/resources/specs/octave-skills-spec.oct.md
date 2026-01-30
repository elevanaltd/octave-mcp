===OCTAVE_SKILLS===
META:
  TYPE::LLM_PROFILE
  VERSION::"7.0.0"
  STATUS::ACTIVE
  TOKENS::"~220"
  REQUIRES::octave-core-spec
  PURPOSE::L5_skill_document_format[platform_agnostic]
  IMPLEMENTATION_NOTES::"v7: Adds optional ANCHOR_KERNEL for odyssean-anchor auto-injection. Skills can export high-density capability atoms for anchor binding. Backward compatible with v6."

  CONTRACT::SKILL_DEFINITION[
    PRINCIPLE::"Skills use YAML for external discovery and OCTAVE for internal definition",
    MECHANISM::[YAML_FRONTMATTER, OCTAVE_ENVELOPE[META, BODY, ANCHOR_KERNEL_OPTIONAL]],
    COMPATIBILITY::universal_tool_support
  ]

---

// OCTAVE SKILLS: Universal format for AI agent skill documents.
// v7: YAML Frontmatter + OCTAVE Envelope + optional ANCHOR_KERNEL for anchor injection.

§1::SKILL_DOCUMENT_STRUCTURE
SEQUENCE::[YAML_FRONTMATTER, OCTAVE_ENVELOPE, ANCHOR_KERNEL_OPTIONAL]
YAML_FRONTMATTER::[name, description, allowed-tools, triggers, version]
ENVELOPE::===SKILL_NAME===[META, body, ANCHOR_KERNEL_optional, END]
META_REQUIRED::[TYPE::SKILL,VERSION,STATUS]
META_OPTIONAL::[PURPOSE,TIER,SPEC_REFERENCE]
BODY::octave_syntax[full_L1-L4_support]
ANCHOR_KERNEL::recommended_for_anchor_injection

REQUIRED_V7::[
  yaml_frontmatter::required_for_discovery,
  octave_envelope::required_for_parsing,
  anchor_kernel::recommended_for_anchor_injection,
  no_markdown_headers::prevent_parser_errors
]

// Note: No duplicate TRIGGERS/TOOLS in META. Source of truth is YAML.

§2::BODY_FORMAT

V7_STANDARD::hybrid_format[yaml_header + octave_envelope + optional_kernel]
V6_STANDARD::hybrid_format[yaml_header + octave_envelope]
V5_DEPRECATED::[markdown_body, missing_envelope, duplicate_meta]

BENEFITS::[
  simplicity::no_redundant_data,
  compatibility::yaml_scanners_work,
  stability::no_markdown_headers_breaking_parsers,
  anchor_injection::kernel_enables_high_density_capability_loading
]

§3::DOCUMENT_TEMPLATE

// V7 template with optional ANCHOR_KERNEL for anchor auto-injection
V7_TEMPLATE_STRUCTURE::[
  YAML_FRONTMATTER::[name, description, allowed_tools, triggers, version],
  OCTAVE_ENVELOPE::[META, body_sections, ANCHOR_KERNEL_optional, END]
]

// Kernel structure aligns with patterns spec for consistency
KERNEL_FIELDS::[
  NEVER::[forbidden_actions],
  MUST::[required_behaviors],
  LANE::optional[role_type_for_coordination_skills],
  DELEGATE::optional[task_delegation_mappings]
]

V6_TEMPLATE::still_valid[kernel_omission_triggers_cascading_fallback]

CASCADING_FALLBACK::[
  // If ANCHOR_KERNEL missing, server extracts from these sections:
  PRIORITY_1::§ANCHOR_KERNEL[explicit_export_interface],
  PRIORITY_2::§BEHAVIOR.CONDUCT[MUST_NEVER + MUST_ALWAYS],
  PRIORITY_3::SIGNALS_or_PATTERNS_blocks[detection_skills],
  PRIORITY_4::WARN_UNSTRUCTURED[skill_name]
]

§4::SIZE_CONSTRAINTS
TARGET::500_lines_max[all_skills]
MAX_BREACH::5_files_over_500[system_wide]
HARD_LIMIT::600_lines[NEVER_exceed]
OVERFLOW_STRATEGY::[progressive_disclosure[main→resources]]

§5::TRIGGER_DESIGN
DESCRIPTION_KEYWORDS::[action_verbs,domain_terms,problem_patterns]
DENSITY::3-5_keywords_per_trigger_category
PATTERN::"Use when [actions]. Triggers on [keywords]."
EXAMPLE::Use_when_auditing_codebases_finding_stubs_Triggers_on_placeholder_audit_stub_detection_technical_debt

§6::RESOURCE_STRUCTURE

CLAUDE_CODE_RESOURCES::[
  PATH::".claude/skills/[skill-name]/",
  MAIN::SKILL.md,
  OVERFLOW::resources[deep_dives,examples]
]

CODEX_RESOURCES::[
  PATH::".codex/skills/[skill-name]/",
  MAIN::SKILL.md,
  SCRIPTS::scripts[executable_code],
  REFERENCES::references[documentation],
  ASSETS::assets[templates,images,fonts]
]

UNIVERSAL_PRINCIPLES::[
  one_level_deep::avoid_nested_references,
  progressive_disclosure::main_file_links_to_resources,
  no_auxiliary_docs::no_README_CHANGELOG_etc
]

§7::PLATFORM_ADAPTATION

V6_UNIFIED_FORMAT::pure_octave_all_platforms
V5_PLATFORM_DIFFERENCES::deprecated[maintained_for_backward_compatibility]

UNIVERSAL_V6::[
  BODY_FORMAT::pure_octave[META.SKILL_defines_all],
  TOOL_RESTRICTIONS::META.SKILL.TOOLS[declarative],
  DISCOVERY::META.SKILL.TRIGGERS[keyword_matching],
  PACKAGING::directory_based[.claude∨.codex∨platform_agnostic]
]

MIGRATION_PATH::[
  V5_YAML_FRONTMATTER→V6_META_SKILL::readers_support_both,
  V5_MARKDOWN_BODY→V6_OCTAVE_BODY::gradual_conversion,
  V5_PLATFORM_SPECIFIC→V6_UNIFIED::single_source_multiple_platforms
]

BACKWARD_COMPATIBILITY::[
  V5_READERS::can_read_v6_via_META_projection,
  V6_READERS::can_read_v5_via_frontmatter_parsing,
  MIGRATION::opt_in_per_skill[no_forced_upgrade]
]

§8::VALIDATION

V7_VALIDATION::[
  META_REQUIRED::[TYPE::SKILL,VERSION,STATUS],
  ENVELOPE::===NAME===[matches_YAML_NAME],
  SYNTAX::passes_octave_validation,
  SIZE::under_constraint_limits,
  ANCHOR_KERNEL::recommended[warn_if_missing_for_anchor_enabled_skills]
]

V6_VALIDATION::[
  META_REQUIRED::[TYPE::SKILL,VERSION,STATUS],
  ENVELOPE::===NAME===[matches_YAML_NAME],
  SYNTAX::passes_octave_validation,
  SIZE::under_constraint_limits
]

V5_VALIDATION_DEPRECATED::[
  frontmatter::valid_yaml,
  name::matches_directory,
  description::non_empty_with_triggers
]

KERNEL_VALIDATION::[
  IF_PRESENT::END_KERNEL_marker_required,
  CONTENT::atoms_only[no_prose_no_rationale],
  SIZE::kernel_50_lines_max
]

§9::FORBIDDEN

NEVER::[
  markdown_headers::breaks_octave_parser,
  auxiliary_files::[README.md,CHANGELOG.md,INSTALLATION.md],
  deeply_nested_references::max_one_level,
  duplicate_information::SKILL.md_or_resources_not_both,
  table_of_contents::agents_scan_natively,
  line_number_references::stale_and_fragile,
  prose_in_anchor_kernel::high_density_atoms_only
]

§10::ANCHOR_KERNEL_FORMAT

// §ANCHOR_KERNEL enables odyssean-anchor server to extract high-density
// capability atoms for automatic injection into agent anchors §5::CAPABILITY_KERNEL.
// This eliminates the need for agents to Read() skill files manually.

PURPOSE::[
  anchor_auto_injection::server_extracts_kernel_for_anchor_capability_loading,
  high_density::atoms_only_no_prose_no_rationale,
  cross_provider::works_via_anchor_print_to_any_LLM_context
]

ANCHOR_KERNEL_STRUCTURE::[
  // Base fields (align with patterns spec for consistency)
  NEVER::[list_of_forbidden_actions],
  MUST::[list_of_mandatory_behaviors],
  // Skill-specific optional fields
  LANE::optional[role_type_for_coordination_skills],
  DELEGATE::optional[task_type_to_agent_mappings],
  TEMPLATE::optional[handoff_or_output_template]
]

ANCHOR_KERNEL_TEMPLATE::"§ANCHOR_KERNEL NEVER::[{forbidden}] MUST::[{required}] LANE::{role_type} DELEGATE::[{mappings}] END_KERNEL"

PLACEMENT::before_final_END_of_skill_envelope

EXAMPLE_COORDINATION_SKILL::[
  §ANCHOR_KERNEL,
  LANE::COORDINATION_ONLY,
  NEVER::[direct_code_implementation, bypass_delegation],
  MUST::[delegate_to_specialists, update_coordination_docs],
  DELEGATE::[CODE_FIX::impl_lead, TEST::ute, ARCHITECTURE::tech_architect],
  END_KERNEL
]

EXAMPLE_DETECTION_SKILL::[
  §ANCHOR_KERNEL,
  NEVER::[ignore_signals, skip_analysis],
  MUST::[report_findings, cite_evidence],
  SIGNALS::[placeholder_patterns, stub_indicators, incomplete_implementations],
  END_KERNEL
]

===END===
