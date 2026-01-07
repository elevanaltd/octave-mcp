===OCTAVE_SKILLS===
META:
  TYPE::LLM_PROFILE
  VERSION::"6.0.0"
  STATUS::APPROVED
  TOKENS::"~180"
  REQUIRES::octave-6-llm-core
  PURPOSE::L5_skill_document_format[platform_agnostic]
  IMPLEMENTATION_NOTES::"v6: Holographic pattern - Skills are pure OCTAVE files where META.SKILL defines triggers and tools, replacing YAML frontmatter hybrid approach."

  CONTRACT::SKILL_DEFINITION[
    PRINCIPLE::"Skills self-declare triggers and tool constraints",
    MECHANISM::META_SKILL_BLOCK[TRIGGERS::[...], TOOLS::[...], DESCRIPTION::...],
    MIGRATION::YAML_FRONTMATTER_TO_META[backward_compatible_reader_support]
  ]

---

// OCTAVE SKILLS: Universal format for AI agent skill documents.
// v6: Pure OCTAVE files with META.SKILL block replacing YAML frontmatter hybrid.

§1::SKILL_DOCUMENT_STRUCTURE
ENVELOPE::===SKILL_NAME===[META,body,===END===]
META_REQUIRED::[TYPE::SKILL,VERSION,STATUS,SKILL]
META_SKILL::[NAME,DESCRIPTION,TRIGGERS,TOOLS][self_configuring]
BODY::octave_syntax[full_L1-L4_support]

DEPRECATED_V5::[
  yaml_frontmatter::replaced_by_META_SKILL,
  hybrid_octave_markdown::pure_octave_preferred,
  platform_specific_sections::unified_META_approach
]

META_SKILL_BLOCK::[
  NAME::skill_identifier[lowercase_hyphens_digits],
  DESCRIPTION::trigger_rich_summary[keywords_for_discovery],
  TRIGGERS::[action_verbs,domain_terms,problem_patterns],
  TOOLS::[tool_whitelist∨*_for_unrestricted][optional]
]

EXAMPLE_META::"
  META:
    TYPE::SKILL
    VERSION::\"1.0.0\"
    STATUS::ACTIVE
    SKILL::[
      NAME::stub-detection,
      DESCRIPTION::\"Systematic detection of placeholder implementations. Use when auditing codebases. Triggers on placeholder audit, stub detection, technical debt.\",
      TRIGGERS::[placeholder_audit,stub_detection,find_stubs,technical_debt],
      TOOLS::[Read,Grep,Glob,Bash]
    ]
"

§2::BODY_FORMAT

V6_STANDARD::pure_octave[full_L1-L4_syntax_support]
V5_DEPRECATED::[markdown_body,hybrid_body][backward_compatible_readers]

BENEFITS::[
  holographic_self_configuration::META_SKILL_declares_triggers_and_tools,
  semantic_compression::3-20x_token_efficiency,
  machine_parseable::structured_validation_and_projection,
  platform_agnostic::same_format_all_agents
]

§3::DOCUMENT_TEMPLATE

V6_TEMPLATE::"
===SKILL_NAME===
META:
  TYPE::SKILL
  VERSION::\"1.0.0\"
  STATUS::ACTIVE
  PURPOSE::skill_mission_statement
  SKILL::[
    NAME::skill-name,
    DESCRIPTION::\"Comprehensive description. Use when X. Triggers on Y, Z.\",
    TRIGGERS::[trigger1,trigger2,trigger3],
    TOOLS::[Read,Bash,Grep,Glob]
  ]

---

§1::SECTION_NAME
CONTENT::follows_octave_syntax[L1-L4]

§2::ANOTHER_SECTION
MORE_CONTENT::structured_data

===END===
"

V5_DEPRECATED_TEMPLATE::"
---
name: skill-name
description: Comprehensive description. Use when X. Triggers on Y, Z.
allowed-tools: Read, Bash, Grep, Glob
---

===SKILL_NAME===
VERSION::1.0.0
...
===END===
"

§4::SIZE_CONSTRAINTS
TARGET::<500_lines[all_skills]
MAX_BREACH::5_files>500[system_wide]
HARD_LIMIT::600_lines[NEVER_exceed]
OVERFLOW_STRATEGY::progressive_disclosure[main→resources]

§5::TRIGGER_DESIGN
DESCRIPTION_KEYWORDS::[action_verbs,domain_terms,problem_patterns]
DENSITY::3-5_keywords_per_trigger_category
PATTERN::"Use when [actions]. Triggers on [keywords]."
EXAMPLE::"Use when auditing codebases, finding stubs. Triggers on placeholder audit, stub detection, technical debt."

§6::RESOURCE_STRUCTURE

CLAUDE_CODE_RESOURCES::[
  PATH::.claude/skills/{skill-name}/,
  MAIN::SKILL.md,
  OVERFLOW::resources/[deep_dives,examples]
]

CODEX_RESOURCES::[
  PATH::.codex/skills/{skill-name}/,
  MAIN::SKILL.md,
  SCRIPTS::scripts/[executable_code],
  REFERENCES::references/[documentation],
  ASSETS::assets/[templates,images,fonts]
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

V6_VALIDATION::[
  META_REQUIRED::[TYPE::SKILL,VERSION,STATUS,SKILL],
  META_SKILL_REQUIRED::[NAME,DESCRIPTION,TRIGGERS],
  META_SKILL_OPTIONAL::[TOOLS],
  ENVELOPE::===NAME===[matches_META.SKILL.NAME],
  SYNTAX::passes_octave_validation,
  SIZE::under_constraint_limits
]

V5_VALIDATION_DEPRECATED::[
  frontmatter::valid_yaml,
  name::matches_directory,
  description::non_empty_with_triggers
]

HOLOGRAPHIC_VALIDATION::[
  SELF_DESCRIBING::META.SKILL.TRIGGERS_define_discovery,
  SELF_CONSTRAINING::META.SKILL.TOOLS_define_permissions,
  SELF_VALIDATING::TYPE::SKILL_triggers_schema_compilation
]

§9::FORBIDDEN

NEVER::[
  auxiliary_files::[README.md,CHANGELOG.md,INSTALLATION.md],
  deeply_nested_references::max_one_level,
  duplicate_information::SKILL.md_or_resources_not_both,
  table_of_contents::agents_scan_natively,
  line_number_references::stale_and_fragile
]

===END===
