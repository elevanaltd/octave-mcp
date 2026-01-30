===OCTAVE_PATTERNS===
META:
  TYPE::LLM_PROFILE
  VERSION::"1.0.0"
  STATUS::ACTIVE
  TOKENS::"~120"
  REQUIRES::octave-core-spec
  PURPOSE::L5_pattern_document_format[reusable_decision_frameworks]
  IMPLEMENTATION_NOTES::"v1: Patterns are lightweight skills - decision frameworks without behavior. Pure OCTAVE envelope, no YAML frontmatter required."

  CONTRACT::PATTERN_DEFINITION[
    PRINCIPLE::"Patterns encode reusable decision logic for consistent agent behavior",
    MECHANISM::[OCTAVE_ENVELOPE[META, BODY, ANCHOR_KERNEL]],
    DISTINCTION::"Skills define WHAT agents do; Patterns define HOW agents decide"
  ]

---

// OCTAVE PATTERNS: Universal format for reusable decision frameworks.
// v1: Pure OCTAVE envelope. Lighter than skills - no YAML frontmatter.

§1::PATTERN_DOCUMENT_STRUCTURE
ENVELOPE::PATTERN_NAME[META,body,§ANCHOR_KERNEL,END]
ENVELOPE_FORMAT::"Three-equals delimiters: ===PATTERN_NAME=== and ===END==="
META_REQUIRED::[TYPE::PATTERN,VERSION,PURPOSE]
META_OPTIONAL::[REPLACES,TIER,SPEC_REFERENCE]
BODY::octave_syntax[L1-L4_support]
ANCHOR_KERNEL::required_for_auto_loading

REQUIRED_V1::[
  octave_envelope::required_for_parsing,
  anchor_kernel::required_for_anchor_injection,
  no_yaml_frontmatter::patterns_are_not_discoverable_skills,
  no_markdown_headers::prevent_parser_errors
]

§2::BODY_FORMAT

RECOMMENDED_SECTIONS::[
  §1::CORE_PRINCIPLE::"What this pattern optimizes for and prevents",
  §2::METRICS_OR_TARGETS::"Measurable goals (optional)",
  §3::DECISION_FRAMEWORK::"Questions to ask before/during application",
  §4::USED_BY::"Agents and contexts where pattern applies"
]

MINIMAL_VALID_PATTERN::[
  META::[TYPE::PATTERN,VERSION,PURPOSE],
  §1::CORE_PRINCIPLE,
  §ANCHOR_KERNEL
]

§3::ANCHOR_KERNEL_FORMAT

// §ANCHOR_KERNEL is the "export interface" for anchor auto-injection
// Server extracts ONLY this block for high-density capability loading

ANCHOR_KERNEL_STRUCTURE::[
  TARGET::"metric or optimization goal",
  NEVER::[forbidden_actions_or_anti_patterns],
  MUST::[required_behaviors_or_checks],
  GATE::"quality check question before application"
]

ANCHOR_KERNEL_TEMPLATE::"§ANCHOR_KERNEL TARGET::{metric} NEVER::[{anti_patterns}] MUST::[{behaviors}] GATE::{question} END_KERNEL"

PLACEMENT::before_final_END_terminator

§4::SIZE_CONSTRAINTS
TARGET::100_lines_max[all_patterns]
HARD_LIMIT::150_lines[NEVER_exceed]
REASON::patterns_are_decision_aids_not_documentation
OVERFLOW_STRATEGY::[if_pattern_exceeds_limit→consider_splitting_or_promoting_to_skill]

§5::VALIDATION

VALIDATION_RULES::[
  META_REQUIRED::[TYPE::PATTERN,VERSION,PURPOSE],
  ENVELOPE::PATTERN_NAME[must_match_filename],
  ANCHOR_KERNEL::required[§ANCHOR_KERNEL...END_KERNEL],
  SYNTAX::passes_octave_validation,
  SIZE::under_constraint_limits
]

VALIDATION_ERRORS::[
  MISSING_ANCHOR_KERNEL::"Pattern requires §ANCHOR_KERNEL for anchor injection",
  MALFORMED_ENVELOPE::"Pattern envelope must be PATTERN_NAME in three-equals delimiters",
  EXCEEDS_SIZE_LIMIT::"Pattern exceeds 150 lines - consider splitting"
]

§6::DOCUMENT_TEMPLATE

// See .hestai-sys/library/patterns/ for concrete examples
// Template structure (envelope delimiters shown as placeholders):

V1_TEMPLATE_STRUCTURE::[
  ENVELOPE_START::PATTERN_NAME[three_equals_delimiters],
  META::[TYPE::PATTERN,VERSION,PURPOSE],
  BODY_SECTIONS::§1_through_§4,
  ANCHOR_KERNEL_SECTION::§ANCHOR_KERNEL,
  KERNEL_TERMINATOR::END_KERNEL[three_equals],
  ENVELOPE_END::END[three_equals_delimiter]
]

SECTION_PATTERN::[
  §1::CORE_PRINCIPLE::[ESSENTIAL,ANTI_PATTERN,ENFORCEMENT],
  §2::DECISION_FRAMEWORK::[BEFORE_ACTION,QUALITY_GATE],
  §3::USED_BY::[AGENTS,CONTEXT],
  §ANCHOR_KERNEL::[TARGET,NEVER,MUST,GATE]
]

§7::EXAMPLE_PATTERNS

// Reference: .hestai-sys/library/patterns/mip-orchestration.oct.md

MIP_ORCHESTRATION_SUMMARY::[
  ENVELOPE::MIP_ORCHESTRATION,
  META::[TYPE::PATTERN,VERSION::1.0,PURPOSE::minimal_intervention_orchestration],
  §1::CORE_PRINCIPLE[ESSENTIAL::system_coherence,ANTI_PATTERN::coordination_theater],
  §2::METRICS[TARGET::62_percent_essential_38_coordination_max],
  §3::DECISION_FRAMEWORK[BEFORE::coherence_question,GATE::value_or_theater],
  §4::USED_BY[AGENTS::[holistic_orchestrator,system_orchestrator]],
  §ANCHOR_KERNEL::[TARGET,NEVER,MUST,GATE]
]

TDD_DISCIPLINE_SUMMARY::[
  ENVELOPE::TDD_DISCIPLINE,
  META::[TYPE::PATTERN,VERSION::1.0,PURPOSE::red_green_refactor_enforcement],
  §1::CORE_PROTOCOL[CYCLE::[RED,GREEN,REFACTOR]],
  §2::GIT_WORKFLOW[PATTERN::[test_commit,feat_commit,refactor_commit]],
  §3::ANTI_PATTERNS[AVOID::[TEST_AFTER,SINGLE_COMMIT,MOCKING_EVERYTHING]]
]

§8::FORBIDDEN

NEVER::[
  yaml_frontmatter::patterns_are_not_discoverable_like_skills,
  markdown_headers::breaks_octave_parser,
  missing_anchor_kernel::required_for_anchor_injection,
  prose_in_anchor_kernel::high_density_atoms_only,
  exceeding_150_lines::patterns_must_stay_lightweight
]

§9::DISTINCTION_FROM_SKILLS

PATTERNS_COMPARED_TO_SKILLS::[
  DISCOVERY::[
    SKILLS::yaml_frontmatter_enables_trigger_based_discovery,
    PATTERNS::referenced_by_agent_definitions_not_auto_discovered
  ],
  PURPOSE::[
    SKILLS::define_agent_behavior_and_tool_restrictions,
    PATTERNS::encode_reusable_decision_frameworks
  ],
  STRUCTURE::[
    SKILLS::yaml_frontmatter+octave_envelope,
    PATTERNS::octave_envelope_only
  ],
  SIZE::[
    SKILLS::up_to_500_lines,
    PATTERNS::up_to_150_lines
  ],
  ANCHOR_KERNEL::[
    SKILLS::recommended_for_anchor_injection,
    PATTERNS::required_for_anchor_injection
  ]
]

===END===
