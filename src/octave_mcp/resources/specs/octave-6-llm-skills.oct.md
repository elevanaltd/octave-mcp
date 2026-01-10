===OCTAVE_SKILLS===
META:
  TYPE::LLM_PROFILE
  VERSION::"6.0.0"
  STATUS::APPROVED
  TOKENS::"~180"
  REQUIRES::octave-6-llm-core
  PURPOSE::L5_skill_document_format[platform_agnostic]
  IMPLEMENTATION_NOTES::"v6: Hybrid pattern - Skills require YAML frontmatter for tool compatibility, followed by a pure OCTAVE envelope (META.SKILL) for internal consistency."

  CONTRACT::SKILL_DEFINITION[
    PRINCIPLE::"Skills use YAML for external discovery and OCTAVE for internal definition",
    MECHANISM::[YAML_FRONTMATTER, OCTAVE_ENVELOPE[META, BODY]],
    COMPATIBILITY::universal_tool_support
  ]

---

// OCTAVE SKILLS: Universal format for AI agent skill documents.
// v6: Simplified format: YAML Frontmatter + OCTAVE Envelope. No redundancy.

§1::SKILL_DOCUMENT_STRUCTURE
SEQUENCE::[YAML_FRONTMATTER, OCTAVE_ENVELOPE]
YAML_FRONTMATTER::[name, description, allowed-tools, triggers, version]
ENVELOPE::===SKILL_NAME===[META,body,===END===]
META_REQUIRED::[TYPE::SKILL,VERSION,STATUS]
META_OPTIONAL::[PURPOSE,TIER,SPEC_REFERENCE]
BODY::octave_syntax[full_L1-L4_support]

REQUIRED_V6::[
  yaml_frontmatter::required_for_discovery,
  octave_envelope::required_for_parsing,
  no_markdown_headers::prevent_parser_errors
]

// Note: No duplicate TRIGGERS/TOOLS in META. Source of truth is YAML.

§2::BODY_FORMAT

V6_STANDARD::hybrid_format[yaml_header + octave_envelope]
V5_DEPRECATED::[markdown_body, missing_envelope, duplicate_meta]

BENEFITS::[
  simplicity::no_redundant_data,
  compatibility::yaml_scanners_work,
  stability::no_markdown_headers_breaking_parsers
]

§3::DOCUMENT_TEMPLATE

V6_TEMPLATE::"
---
name: skill-name
description: Comprehensive description. Use when X. Triggers on Y, Z.
allowed-tools: [Read, Bash, Grep, Glob]
triggers: [trigger1, trigger2]
version: 1.0.0
---

===SKILL_NAME===
META:
  TYPE::SKILL
  VERSION::\"1.0.0\"
  STATUS::ACTIVE
  PURPOSE::skill_mission_statement

§1::SECTION_NAME
CONTENT::follows_octave_syntax[L1-L4]

===END===
"
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

HOLOGRAPHIC_VALIDATION::[
  DEPRECATED::"No longer required to mirror YAML in META.SKILL"
]

§9::FORBIDDEN

NEVER::[
  markdown_headers::breaks_octave_parser,
  auxiliary_files::[README.md,CHANGELOG.md,INSTALLATION.md],
  deeply_nested_references::max_one_level,
  duplicate_information::SKILL.md_or_resources_not_both,
  table_of_contents::agents_scan_natively,
  line_number_references::stale_and_fragile
]

===END===
