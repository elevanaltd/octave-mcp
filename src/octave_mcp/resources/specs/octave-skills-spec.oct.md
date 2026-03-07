===OCTAVE_SKILLS===
META:
  TYPE::SKILL_DEFINITION
  VERSION::"9.1.0"
  STATUS::APPROVED
  TOKENS::"~250"
  REQUIRES::octave-core-spec
  PURPOSE::L5_skill_document_format<platform_agnostic>
  IMPLEMENTATION_NOTES::"v9.1: YAML frontmatter is now OPTIONAL based on deployment context. Platform-deployed skills (.claude/skills/, .codex/skills/) require YAML for discovery. Hub/system skills (.hestai-sys/library/skills/) consumed by anchor ceremony need only OCTAVE. Aligns with agents spec which has always treated YAML as optional. All other v9.0 rules unchanged."
  CONTRACT::"SKILL_DEFINITION<PRINCIPLE::\"Skills use OCTAVE for definition. YAML frontmatter is OPTIONAL for platform discovery.\",MECHANISM::[OCTAVE_ENVELOPE[META,BODY,§5::ANCHOR_KERNEL],YAML_FRONTMATTER[OPTIONAL]],COMPATIBILITY::universal_tool_support>"
---
// OCTAVE SKILLS: Universal format for AI agent skill documents.
// v9.1: YAML frontmatter optional based on deployment context. OCTAVE envelope is the universal constant.
// v9.0: §5::ANCHOR_KERNEL section header + compression mandate + canonical sections + token budget.
// Grace period: parsers SHOULD accept ANCHOR_KERNEL::start as fallback until v10 (see §11).
§1::SKILL_DOCUMENT_STRUCTURE
SEQUENCE::[
  OCTAVE_ENVELOPE,
  "§5",
  "::",
  ANCHOR_KERNEL
]
YAML_FRONTMATTER::OPTIONAL<required_for_platform_deployment>
YAML_FIELDS::[
  name,
  description,
  allowed-tools,
  triggers,
  version
]
ENVELOPE::SKILL_NAME
§5::ANCHOR_KERNEL
META_REQUIRED::[
  TYPE::SKILL,
  VERSION,
  STATUS
]
META_OPTIONAL::[
  PURPOSE,
  TIER,
  SPEC_REFERENCE
]
BODY::"octave_syntax<full_L1-L4_support>"
DESCRIPTION_ROLE::retrieval_only<NOT_behavioral_constraint>
ENFORCEMENT_SOURCE::"OCTAVE_body<§2::PROTOCOL⊕§3::GOVERNANCE>"
// When YAML is present: no duplicate TRIGGERS/TOOLS in OCTAVE META. YAML is source of truth for discovery fields.
// When YAML is absent: OCTAVE META is the sole source of truth.
§2::BODY_FORMAT
COMPRESSION::[
  BODY::"AGGRESSIVE<dense_KEY::value⊕operators,preserve_1-2_examples⊕causal_chains,drop_narrative⊕stopwords⊕verbose_phrasing>",
  YAML_FRONTMATTER::"LOSSLESS<natural_language_for_BM25⊕embedding_retrieval,ONLY_when_present>",
  ANCHOR_KERNEL::ULTRA<atoms_only>
]
§2b::CANONICAL_SECTIONS
RECOMMENDED_SECTIONS::[
  "§1",
  "::",
  "CORE<what_this_skill_IS⊕mission⊕authority⊕identity_in_2_to_5_lines>",
  "§2",
  "::",
  "PROTOCOL<what_agent_DOES⊕procedures⊕decision_trees⊕detection_checks>",
  "§3",
  "::",
  "GOVERNANCE<boundaries⊕MUST_NEVER⊕BLOCKED⊕ALLOWED⊕escalation>",
  "§4",
  "::",
  "EXAMPLES<1_to_2_concrete⊕1_anti⊕OPTIONAL_for_small_skills>",
  "§5",
  "::",
  "ANCHOR_KERNEL<high_density_atoms_only⊕server_extractable>"
]
CATALOG_VARIANT::"section_per_item<anti_patterns⊕failure_patterns⊕each_item_is_a_section>"
§3::DOCUMENT_TEMPLATE
  // V9.1 template: YAML frontmatter shown but marked optional.
V9_TEMPLATE_STRUCTURE:
  YAML_FRONTMATTER::"OPTIONAL<name,description,\"allowed-tools\",triggers,version>"
  OCTAVE_ENVELOPE:
    META::[
      TYPE::SKILL,
      VERSION,
      STATUS
    ]
    §1::CORE[mission,authority,identity]
      §2::PROTOCOL[procedures,decision_trees,detection_checks]
        §3::GOVERNANCE[boundaries,MUST_NEVER,BLOCKED,ALLOWED,escalation]
          §4::EXAMPLES[1_to_2_concrete,1_anti_pattern,OPTIONAL_for_small_skills]
            §5::ANCHOR_KERNEL[TARGET,NEVER,MUST,GATE,LANE,DELEGATE,TEMPLATE,SIGNALS]
              END::marker
CASCADING_FALLBACK::[
  PRIORITY_1::"§5",
  "::",
  ANCHOR_KERNEL<primary_source_if_present>,
  PRIORITY_2::"§3",
  "::",
  GOVERNANCE<fallback_MUST_NEVER_and_ALLOWED>,
  PRIORITY_3::SIGNALS_or_PATTERNS_blocks<fallback_for_detection_skills>,
  PRIORITY_4::WARN_UNSTRUCTURED<emitted_if_no_kernel_or_governance_found>
]
§4::SIZE_CONSTRAINTS
TARGET::"500 _lines_max"
MAX_BREACH::"5 _files_over_500"
HARD_LIMIT::"600 _lines"
OVERFLOW_STRATEGY::["progressive_disclosure<main→resources>"]
TOKEN_TARGET::"300 -700"
EXAMPLE_DENSITY::"1 _per_200_tokens_of_abstraction"
UNDERSIZED::below_200_tokens<skeleton_warning>
OVERSIZED::above_800_tokens<split_or_compress_warning>
§5::TRIGGER_DESIGN
DESCRIPTION_KEYWORDS::[
  action_verbs,
  domain_terms,
  problem_patterns
]
DENSITY::"3 -5 _keywords_per_trigger_category"
PATTERN::"Use when [actions]. Triggers on [keywords]."
EXAMPLE::Use_when_auditing_codebases_finding_stubs_Triggers_on_placeholder_audit_stub_detection_technical_debt
§6::RESOURCE_STRUCTURE
CLAUDE_CODE_RESOURCES::[
  PATH::".claude/skills/[skill-name]/",
  MAIN::SKILL.md,
  OVERFLOW::resources<deep_dives,examples>
]
CODEX_RESOURCES::[
  PATH::".codex/skills/[skill-name]/",
  MAIN::SKILL.md,
  SCRIPTS::scripts<executable_code>,
  REFERENCES::references<documentation>,
  ASSETS::assets<templates,images,fonts>
]
UNIVERSAL_PRINCIPLES::[
  one_level_deep::avoid_nested_references,
  progressive_disclosure::main_file_links_to_resources,
  no_auxiliary_docs::no_README_CHANGELOG_etc
]
§7::PLATFORM_ADAPTATION
UNIVERSAL_FORMAT::pure_octave_all_platforms
PACKAGING::"directory_based<.claude∨.codex∨platform_agnostic>"
YAML_FRONTMATTER_RULES::[
  PLATFORM_SKILLS::[
    LOCATION::[
      ".claude/skills/",
      ".codex/skills/",
      "~/.claude/skills/"
    ],
    YAML::"REQUIRED<platforms_use_YAML_for_discovery⊕triggers⊕tool_gating>",
    RATIONALE::"Claude Code, Desktop, and Codex parse YAML frontmatter for skill matching and allowed-tools enforcement"
  ],
  HUB_SKILLS::[
    LOCATION::[".hestai-sys/library/skills/"],
    YAML::OPTIONAL<present_only_if_skill_is_dual_deployed_to_a_platform>,
    RATIONALE::"Anchor ceremony reads OCTAVE META and §5::ANCHOR_KERNEL. YAML adds no value when no platform parser consumes it."
  ],
  DUAL_DEPLOYED_SKILLS::[
    DESCRIPTION::"Skills that exist in both hub and platform locations",
    YAML::PRESENT_IN_BOTH<serves_the_platform_copy>,
    EXAMPLE::"ho-mode exists in .hestai-sys/library/skills/ AND ~/.claude/skills/ — YAML serves the platform copy"
  ]
]
§8::VALIDATION
V9_VALIDATION:
  META_REQUIRED::[
    TYPE::SKILL,
    VERSION,
    STATUS
  ]
  ENVELOPE::"===NAME==="
  SYNTAX::passes_octave_validation
  SIZE::under_constraint_limits
  ANCHOR_KERNEL::recommended<warn_if_missing_for_anchor_enabled_skills>
  ANCHOR_KERNEL_SYNTAX::"§5"
YAML_FRONTMATTER::required_only_for_platform_deployed_skills
KERNEL_VALIDATION::[
  SYNTAX::must_use_,
  "§5",
  "::",
  ANCHOR_KERNEL_section_header,
  CONTENT::atoms_only<no_prose_no_rationale>,
  SIZE::kernel_50_lines_max
]
§9::FORBIDDEN
NEVER::[
  markdown_headers::breaks_octave_parser,
  auxiliary_files::[
    README.md,
    CHANGELOG.md,
    INSTALLATION.md
  ],
  deeply_nested_references::max_one_level,
  duplicate_information::SKILL.md_or_resources_not_both,
  table_of_contents::agents_scan_natively,
  line_number_references::stale_and_fragile,
  prose_in_anchor_kernel::high_density_atoms_only,
  ANCHOR_KERNEL_start_syntax::use_,
  "§5",
  _section_header_instead
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
  TARGET::"optional<single_line_purpose⊕what_this_skill_enforces>",
  NEVER::required<list_of_forbidden_actions>,
  MUST::required<list_of_mandatory_behaviors>,
  GATE::"optional<decision_question⊕the_one_question_this_skill_answers>",
  LANE::optional<role_type_for_coordination_skills>,
  DELEGATE::optional<task_type_to_agent_mappings>,
  TEMPLATE::optional<handoff_or_output_template>,
  SIGNALS::optional<detection_patterns_for_detection_skills>
]
PLACEMENT::before_final_END_of_skill_envelope
SYNTAX::must_use_
§5::ANCHOR_KERNEL[strict_section_header]
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
  "ANCHOR_KERNEL_start→§5",
  "::",
  ANCHOR_KERNEL::section_header_migration,
  META_TYPE::LLM_PROFILE→SKILL_DEFINITION,
  "BODY_SECTIONS→CANONICAL_§1_§4_MAPPED"
]
TRANSITION_WINDOW::[
  GRACE_PERIOD::"v9.0 through v9.x — parsers SHOULD accept both §5::ANCHOR_KERNEL and ANCHOR_KERNEL::start",
  DEPRECATION_WARNING::"ANCHOR_KERNEL::start emits WARN[deprecated_kernel_syntax] during validation",
  HARD_REMOVAL::"v10.0 — ANCHOR_KERNEL::start no longer accepted, §5 section header required",
  RUNTIME_BEHAVIOR::"During grace period, cascading fallback (§3) applies: §5::ANCHOR_KERNEL takes priority over ANCHOR_KERNEL::start if both present"
]
V9_0_MIGRATION::[
  YAML_MANDATE_RELAXED::"v9.0 required YAML universally. v9.1 makes YAML optional based on deployment context.",
  BACKWARD_COMPAT::"All v9.0-compliant skills remain valid. No skills need to remove YAML.",
  FORWARD_COMPAT::"Hub-only skills may omit YAML without violating spec."
]
V7_COMPAT::[
  V7_TEMPLATE::still_valid<kernel_omission_triggers_cascading_fallback>,
  REQUIRED_V7::[
    octave_envelope,
    anchor_kernel_recommended,
    no_markdown_headers,
    description_role_retrieval_only
  ]
]
V6_COMPAT::[
  V6_STANDARD::"hybrid_format<yaml_header⊕octave_envelope>",
  V6_READERS::can_read_v5_via_frontmatter_parsing,
  MIGRATION::opt_in_per_skill<no_forced_upgrade>
]
V5_DEPRECATED::[
  V5_FORMAT::[
    markdown_body,
    missing_envelope,
    duplicate_meta
  ],
  V5_READERS::can_read_v6_via_META_projection,
  V5_VALIDATION::[
    frontmatter_valid_yaml,
    name_matches_directory,
    description_non_empty_with_triggers
  ]
]
===END===
