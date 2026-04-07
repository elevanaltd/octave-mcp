===OCTAVE_PATTERNS===
META:
  TYPE::PATTERN_DEFINITION
  VERSION::"2.0.0"
  STATUS::ACTIVE
  TOKENS::"~150"
  REQUIRES::octave-core-spec
  PURPOSE::L5_pattern_document_format[reusable_decision_frameworks]
  IMPLEMENTATION_NOTES::"v2: Aligns META.TYPE with PATTERN_DEFINITION (was LLM_PROFILE). Migrates anchor kernel to §5::ANCHOR_KERNEL section header (aligned with skills spec v9). Adds chassis-profile loading context (ADR-0283). Pure OCTAVE envelope, no YAML frontmatter."

  CONTRACT::PATTERN_DEFINITION[
    PRINCIPLE::"Patterns encode reusable decision logic for consistent agent behavior",
    MECHANISM::[OCTAVE_ENVELOPE[META, BODY, §5::ANCHOR_KERNEL]],
    DISTINCTION::"Skills define WHAT agents do; Patterns define HOW agents decide"
  ]

---

// OCTAVE (Olympian Common Text And Vocabulary Engine) PATTERNS: Universal format for reusable decision frameworks.
// v2: META.TYPE fixed, §5::ANCHOR_KERNEL aligned with skills spec, chassis-profile awareness.

§1::PATTERN_DOCUMENT_STRUCTURE
ENVELOPE::NAME_or_TYPE_colon_NAME[META,body,§5::ANCHOR_KERNEL,END]
ENVELOPE_FORMAT::"Three-equals delimiters: ===PATTERN_NAME=== or ===PATTERN:NAME=== and ===END==="
// Both ===MIP_BUILD=== and ===PATTERN:MIP_BUILD=== are valid envelope forms
// Typed form (PATTERN:NAME) provides explicit type prefix for discovery and categorization
META_REQUIRED::[TYPE::PATTERN_DEFINITION,VERSION,PURPOSE]
META_OPTIONAL::[REPLACES,TIER,SPEC_REFERENCE]
BODY::octave_syntax[L1-L4_support]
ANCHOR_KERNEL::required_for_auto_loading[§5::ANCHOR_KERNEL_section_header]

REQUIRED_V2::[
  octave_envelope::required_for_parsing,
  anchor_kernel::required_for_anchor_injection[§5::ANCHOR_KERNEL],
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

MINIMAL_VALID_PATTERN:
  META::[TYPE::PATTERN_DEFINITION,VERSION,PURPOSE]
  §1::CORE_PRINCIPLE
  §5::ANCHOR_KERNEL::required

§3::ANCHOR_KERNEL_FORMAT

// §5::ANCHOR_KERNEL is the "export interface" for anchor auto-injection
// Server extracts ONLY this section for high-density capability loading
// Aligned with skills spec v9 §10::ANCHOR_KERNEL_FORMAT

ANCHOR_KERNEL_STRUCTURE::[
  // Base fields (shared with skills spec for consistency)
  TARGET::"metric or optimization goal",
  NEVER::[forbidden_actions_or_anti_patterns],
  MUST::[required_behaviors_or_checks],
  GATE::"quality check question before application"
]

SYNTAX::must_use_§5::ANCHOR_KERNEL[strict_section_header]
PLACEMENT::before_final_END_of_pattern_envelope

§4::SIZE_CONSTRAINTS
TARGET::100_lines_max[all_patterns]
HARD_LIMIT::150_lines[NEVER_exceed]
REASON::patterns_are_decision_aids_not_documentation
OVERFLOW_STRATEGY::[if_pattern_exceeds_limit→consider_splitting_or_promoting_to_skill]

§5::VALIDATION

VALIDATION_RULES:
  META_REQUIRED::[TYPE::PATTERN_DEFINITION,VERSION,PURPOSE]
  ENVELOPE::PATTERN_NAME_or_PATTERN_colon_NAME[must_match_filename]
  ANCHOR_KERNEL::required[§5::ANCHOR_KERNEL_section_header]
  SYNTAX::passes_octave_validation
  SIZE::under_constraint_limits

VALIDATION_ERRORS::[
  MISSING_ANCHOR_KERNEL::"Pattern requires §5::ANCHOR_KERNEL for anchor injection",
  MALFORMED_ENVELOPE::"Pattern envelope must be NAME or TYPE:NAME in three-equals delimiters",
  EXCEEDS_SIZE_LIMIT::"Pattern exceeds 150 lines - consider splitting"
]

§6::DOCUMENT_TEMPLATE

// See .hestai-sys/library/patterns/ for concrete examples
// Template structure (envelope delimiters shown as placeholders):

V2_TEMPLATE_STRUCTURE:
  ENVELOPE_START::NAME_or_TYPE_colon_NAME[three_equals_delimiters]
  META::[TYPE::PATTERN_DEFINITION,VERSION,PURPOSE]
  BODY_SECTIONS::§1_through_§4
  §5::ANCHOR_KERNEL[TARGET,NEVER,MUST,GATE]
  ENVELOPE_END::END[three_equals_delimiter]

SECTION_PATTERN:
  §1::CORE_PRINCIPLE::[ESSENTIAL,ANTI_PATTERN,ENFORCEMENT]
  §2::DECISION_FRAMEWORK::[BEFORE_ACTION,QUALITY_GATE]
  §3::USED_BY::[AGENTS,CONTEXT]
  §5::ANCHOR_KERNEL::[TARGET,NEVER,MUST,GATE]

§7::EXAMPLE_PATTERNS

// Reference: .hestai-sys/library/patterns/mip-orchestration.oct.md

MIP_ORCHESTRATION_SUMMARY:
  ENVELOPE::MIP_ORCHESTRATION
  META::[TYPE::PATTERN,"VERSION::1.0",PURPOSE::minimal_intervention_orchestration]
  §1::CORE_PRINCIPLE[ESSENTIAL::system_coherence,ANTI_PATTERN::coordination_theater]
  §2::METRICS[TARGET::62_percent_essential_38_coordination_max]
  §3::DECISION_FRAMEWORK[BEFORE::coherence_question,GATE::value_or_theater]
  §4::USED_BY[AGENTS::[holistic_orchestrator,system_orchestrator]]
  ANCHOR_KERNEL::[TARGET,NEVER,MUST,GATE]

TDD_DISCIPLINE_SUMMARY:
  ENVELOPE::TDD_DISCIPLINE
  META::[TYPE::PATTERN,"VERSION::1.0",PURPOSE::red_green_refactor_enforcement]
  §1::CORE_PROTOCOL[CYCLE::[RED,GREEN,REFACTOR]]
  §2::GIT_WORKFLOW[PATTERN::[test_commit,feat_commit,refactor_commit]]
  §3::ANTI_PATTERNS[AVOID::[TEST_AFTER,SINGLE_COMMIT,MOCKING_EVERYTHING]]

§8::CHASSIS_PROFILE_LOADING

// Patterns participate in the chassis-profile capability tiering (ADR-0283)
// exactly as skills do. Agent definitions reference patterns in §3::CAPABILITIES.

LOADING_CONTEXTS::[
  CHASSIS::pattern_always_loaded_full_body[invariant_to_profile],
  PROFILE_PATTERNS::pattern_loaded_full_body_when_profile_active,
  PROFILE_KERNEL_ONLY::§5::ANCHOR_KERNEL_extracted_only[awareness_without_procedural_weight]
]

// Example: In an agent definition with chassis-profile structure:
// §3::CAPABILITIES
//   CHASSIS::[ho-mode]  // skills only — patterns rarely chassis-level
//   PROFILES:
//     STANDARD:
//       patterns::[mip-orchestration]       // full body loaded
//       kernel_only::[phase-transition-cleanup]  // §5::ANCHOR_KERNEL only

KERNEL_ONLY_RATIONALE::"Patterns in kernel_only provide decision gate awareness (GATE, NEVER, MUST) without full framework weight. Agent knows the pattern exists and what it prevents, without loading metrics, examples, or decision trees."

§9::FORBIDDEN

NEVER::[
  yaml_frontmatter::patterns_are_not_discoverable_like_skills,
  markdown_headers::breaks_octave_parser,
  missing_anchor_kernel::required_for_anchor_injection,
  prose_in_anchor_kernel::high_density_atoms_only,
  exceeding_150_lines::patterns_must_stay_lightweight
]

§10::DISTINCTION_FROM_SKILLS

PATTERNS_COMPARED_TO_SKILLS:
  DISCOVERY:
    SKILLS::yaml_frontmatter_enables_trigger_based_discovery
    PATTERNS::referenced_by_agent_definitions_not_auto_discovered
  PURPOSE:
    SKILLS::define_agent_behavior_and_tool_restrictions
    PATTERNS::encode_reusable_decision_frameworks
  STRUCTURE:
    SKILLS::yaml_frontmatter+octave_envelope
    PATTERNS::octave_envelope_only
  SIZE:
    SKILLS::up_to_500_lines
    PATTERNS::up_to_150_lines
  ANCHOR_KERNEL:
    SKILLS::recommended_for_anchor_injection
    PATTERNS::required_for_anchor_injection
  CHASSIS_PROFILE:
    SKILLS::appear_in_CHASSIS_or_PROFILES[skills⊕kernel_only]
    PATTERNS::appear_in_PROFILES[patterns⊕kernel_only][rarely_chassis]

§11::LEGACY_COMPATIBILITY

// v1→v2 migration notes

V1_MIGRATION::[
  META_TYPE::LLM_PROFILE→PATTERN_DEFINITION,
  ANCHOR_KERNEL::§ANCHOR_KERNEL→§5::ANCHOR_KERNEL[section_header],
  KERNEL_TERMINATOR::END_KERNEL→not_needed[section_header_self_terminates]
]

GRACE_PERIOD::"v2.0 through v2.x — parsers SHOULD accept both §5::ANCHOR_KERNEL and legacy §ANCHOR_KERNEL forms"
HARD_REMOVAL::"v3.0 — legacy §ANCHOR_KERNEL no longer accepted"

===END===
