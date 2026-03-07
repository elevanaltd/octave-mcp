===OCTAVE_SKILLS===
META:
  TYPE::SKILL_DEFINITION
  VERSION::"9.0.0"
  STATUS::APPROVED
  TOKENS::"~250"
  REQUIRES::octave-core-spec
  PURPOSE::L5_skill_document_format[platform_agnostic]
  IMPLEMENTATION_NOTES::"v9: Fixes META type (SKILL_DEFINITION), standardizes §5::ANCHOR_KERNEL as section header, integrates canonical sections into template, isolates legacy compat into §11. Breaking change: ANCHOR_KERNEL::start syntax replaced by §5::ANCHOR_KERNEL section header. Grace period: parsers SHOULD accept both forms until v10."

  CONTRACT::SKILL_DEFINITION[
    PRINCIPLE::"Skills use YAML for external discovery and OCTAVE for internal definition",
    MECHANISM::[YAML_FRONTMATTER, OCTAVE_ENVELOPE[META, BODY, §5::ANCHOR_KERNEL]],
    COMPATIBILITY::universal_tool_support
  ]

---

// OCTAVE SKILLS: Universal format for AI agent skill documents.
// v9: YAML Frontmatter + OCTAVE Envelope + §5::ANCHOR_KERNEL + compression mandate + canonical sections + token budget.
// Breaking change from v8: ANCHOR_KERNEL must use §5 section header (not ANCHOR_KERNEL::start).
// Grace period: parsers SHOULD accept ANCHOR_KERNEL::start as fallback until v10 (see §11).

§1::SKILL_DOCUMENT_STRUCTURE
SEQUENCE::[YAML_FRONTMATTER, OCTAVE_ENVELOPE, §5::ANCHOR_KERNEL]
YAML_FRONTMATTER::[name, description, "allowed-tools", triggers, version]
ENVELOPE::===SKILL_NAME===[META, body_§1_to_§4, §5::ANCHOR_KERNEL, END]
META_REQUIRED::[TYPE::SKILL,VERSION,STATUS]
META_OPTIONAL::[PURPOSE,TIER,SPEC_REFERENCE]
BODY::octave_syntax[full_L1-L4_support]

DESCRIPTION_ROLE::retrieval_only[NOT_behavioral_constraint]
ENFORCEMENT_SOURCE::OCTAVE_body[§2::PROTOCOL⊕§3::GOVERNANCE]

// Note: No duplicate TRIGGERS/TOOLS in META. Source of truth is YAML.

§2::BODY_FORMAT

COMPRESSION::[
  BODY::AGGRESSIVE[dense_KEY::value⊕operators, preserve_1-2_examples⊕causal_chains, drop_narrative⊕stopwords⊕verbose_phrasing],
  YAML_FRONTMATTER::LOSSLESS[natural_language_for_BM25⊕embedding_retrieval],
  ANCHOR_KERNEL::ULTRA[atoms_only]
]

§2b::CANONICAL_SECTIONS
RECOMMENDED_SECTIONS::[
  §1::CORE[what_this_skill_IS⊕mission⊕authority⊕identity_in_2_to_5_lines],
  §2::PROTOCOL[what_agent_DOES⊕procedures⊕decision_trees⊕detection_checks],
  §3::GOVERNANCE[boundaries⊕MUST_NEVER⊕BLOCKED⊕ALLOWED⊕escalation],
  §4::EXAMPLES[1_to_2_concrete⊕1_anti⊕OPTIONAL_for_small_skills],
  §5::ANCHOR_KERNEL[high_density_atoms_only⊕server_extractable]
]
CATALOG_VARIANT::section_per_item[anti_patterns⊕failure_patterns⊕each_item_is_a_section]

§3::DOCUMENT_TEMPLATE

// V9 template: canonical sections explicitly mapped. LLMs should emit these exact headers.
V9_TEMPLATE_STRUCTURE:
  YAML_FRONTMATTER::[name, description, "allowed-tools", triggers, version]
  OCTAVE_ENVELOPE:
    META::[TYPE::SKILL, VERSION, STATUS]
    §1::CORE[mission, authority, identity]
    §2::PROTOCOL[procedures, decision_trees, detection_checks]
    §3::GOVERNANCE[boundaries, MUST_NEVER, BLOCKED, ALLOWED, escalation]
    §4::EXAMPLES[1_to_2_concrete, 1_anti_pattern, OPTIONAL_for_small_skills]
    §5::ANCHOR_KERNEL[TARGET, NEVER, MUST, GATE, LANE, DELEGATE, TEMPLATE, SIGNALS]
    END::marker

CASCADING_FALLBACK::[
  // Server extraction priority sequence for Anchor injection:
  PRIORITY_1::§5::ANCHOR_KERNEL[primary_source_if_present],
  PRIORITY_2::§3::GOVERNANCE[fallback_MUST_NEVER_and_ALLOWED],
  PRIORITY_3::SIGNALS_or_PATTERNS_blocks[fallback_for_detection_skills],
  PRIORITY_4::WARN_UNSTRUCTURED[emitted_if_no_kernel_or_governance_found]
]

§4::SIZE_CONSTRAINTS
TARGET::500_lines_max[all_skills]
MAX_BREACH::5_files_over_500[system_wide]
HARD_LIMIT::600_lines[NEVER_exceed]
OVERFLOW_STRATEGY::[progressive_disclosure[main→resources]]
TOKEN_TARGET::300-700[body_excluding_YAML_and_kernel]
EXAMPLE_DENSITY::1_per_200_tokens_of_abstraction
UNDERSIZED::below_200_tokens[skeleton_warning]
OVERSIZED::above_800_tokens[split_or_compress_warning]

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

UNIVERSAL_FORMAT::pure_octave_all_platforms
PACKAGING::directory_based[.claude∨.codex∨platform_agnostic]

§8::VALIDATION

V9_VALIDATION:
  META_REQUIRED::[TYPE::SKILL,VERSION,STATUS]
  ENVELOPE::"===NAME===[matches_YAML_NAME]"
  SYNTAX::passes_octave_validation
  SIZE::under_constraint_limits
  ANCHOR_KERNEL::recommended[warn_if_missing_for_anchor_enabled_skills]
  ANCHOR_KERNEL_SYNTAX::§5_section_header_required[not_ANCHOR_KERNEL::start]

KERNEL_VALIDATION::[
  SYNTAX::must_use_§5::ANCHOR_KERNEL_section_header,
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
  prose_in_anchor_kernel::high_density_atoms_only,
  ANCHOR_KERNEL_start_syntax::use_§5_section_header_instead
]

§10::ANCHOR_KERNEL_FORMAT

// §5::ANCHOR_KERNEL enables odyssean-anchor server to extract high-density
// capability atoms for automatic injection into agent anchors.
// This eliminates the need for agents to Read() skill files manually.

PURPOSE::[
  anchor_auto_injection::server_extracts_kernel_for_anchor_capability_loading,
  high_density::atoms_only_no_prose_no_rationale,
  cross_provider::works_via_anchor_print_to_any_LLM_context
]

ANCHOR_KERNEL_STRUCTURE::[
  // Base fields (align with patterns spec for consistency)
  TARGET::optional[single_line_purpose⊕what_this_skill_enforces],
  NEVER::required[list_of_forbidden_actions],
  MUST::required[list_of_mandatory_behaviors],
  GATE::optional[decision_question⊕the_one_question_this_skill_answers],
  // Skill-specific optional fields
  LANE::optional[role_type_for_coordination_skills],
  DELEGATE::optional[task_type_to_agent_mappings],
  TEMPLATE::optional[handoff_or_output_template],
  SIGNALS::optional[detection_patterns_for_detection_skills]
]

PLACEMENT::before_final_END_of_skill_envelope
SYNTAX::must_use_§5::ANCHOR_KERNEL[strict_section_header]

EXAMPLE_COORDINATION_SKILL:
  ```octave
  §5::ANCHOR_KERNEL
    LANE::COORDINATION_ONLY
    NEVER::[direct_code_implementation, bypass_delegation]
    MUST::[delegate_to_specialists, update_coordination_docs]
    DELEGATE:
      CODE_FIX::impl_lead
      TEST::ute
      ARCHITECTURE::tech_architect
  ===END===
  ```

EXAMPLE_DETECTION_SKILL:
  ```octave
  §5::ANCHOR_KERNEL
    NEVER::[ignore_signals, skip_analysis]
    MUST::[report_findings, cite_evidence]
    SIGNALS::[placeholder_patterns, stub_indicators, incomplete_implementations]
  ===END===
  ```

§11::LEGACY_COMPATIBILITY

// V5/V6/V7/V8 backward compatibility rules consolidated here.
// Keep the primary spec focused on current V9 standard.

V8_MIGRATION::[
  ANCHOR_KERNEL_start→§5::ANCHOR_KERNEL::section_header_migration,
  META_TYPE::LLM_PROFILE→SKILL_DEFINITION,
  BODY_SECTIONS→CANONICAL_§1_§4_MAPPED
]

TRANSITION_WINDOW::[
  GRACE_PERIOD::"v9.0 through v9.x — parsers SHOULD accept both §5::ANCHOR_KERNEL and ANCHOR_KERNEL::start",
  DEPRECATION_WARNING::"ANCHOR_KERNEL::start emits WARN[deprecated_kernel_syntax] during validation",
  HARD_REMOVAL::"v10.0 — ANCHOR_KERNEL::start no longer accepted, §5 section header required",
  RUNTIME_BEHAVIOR::"During grace period, cascading fallback (§3) applies: §5::ANCHOR_KERNEL takes priority over ANCHOR_KERNEL::start if both present"
]

V7_COMPAT::[
  V7_TEMPLATE::still_valid[kernel_omission_triggers_cascading_fallback],
  REQUIRED_V7::[yaml_frontmatter, octave_envelope, anchor_kernel_recommended, no_markdown_headers, description_role_retrieval_only]
]

V6_COMPAT::[
  V6_STANDARD::hybrid_format[yaml_header + octave_envelope],
  V6_READERS::can_read_v5_via_frontmatter_parsing,
  MIGRATION::opt_in_per_skill[no_forced_upgrade]
]

V5_DEPRECATED::[
  V5_FORMAT::[markdown_body, missing_envelope, duplicate_meta],
  V5_READERS::can_read_v6_via_META_projection,
  V5_VALIDATION::[frontmatter_valid_yaml, name_matches_directory, description_non_empty_with_triggers]
]

===END===
