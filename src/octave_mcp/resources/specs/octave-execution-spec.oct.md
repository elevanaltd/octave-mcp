===OCTAVE_EXECUTION===
META:
  TYPE::LLM_PROFILE
  VERSION::"6.0.0"
  STATUS::ACTIVE
  TOKENS::"~130"
  REQUIRES::"octave-core-spec"
  PURPOSE::validation_and_error_handling
  IMPLEMENTATION_NOTES::"Validator handles META validation, structure validation, and schema-driven constraint validation (15+ constraint types including Type, Regex, Enum, Range, MinLength, MaxLength, Date, Iso8601). Unknown fields policy (E007) with STRICT/LENIENT/WARN modes implemented. Retry protocol not yet implemented as tool-level feature."
  IMPLEMENTATION_REF::["src/octave_mcp/core/validator.py","src/octave_mcp/core/constraints.py"]
  CRITICAL_GAPS::[retry_protocol]
  RESOLVED_GAPS::[
    constraint_validation,
    type_checking,
    regex_validation,
    error_message_formatting,
    grammar_hints_on_validation_failure
  ]
---
// OCTAVE EXECUTION: Understanding validation feedback. Inject when debugging/iterating.
§1::VALIDATION_FLOW
GENERATIVE_WORKFLOW::["READ_META→COMPILE_GRAMMAR→GENERATE"]
READ_META:
  PURPOSE::"Extract schema constraints before generation"
  CHECKS::[
    envelope,
    syntax,
    structure,
    indent,
    META_presence
  ]
  FAILURE::unparseable<no_recovery>
COMPILE_GRAMMAR:
  PURPOSE::"Build constraint graph defining valid output space"
  PROCESS::["parse_constraints→resolve_targets→build_grammar_rules"]
  OUTPUT::executable_schema<guides_generation>
  FAILURE::schema_error<fix_schema>
GENERATE:
  PURPOSE::"Emit content within constraint boundaries"
  MODE::constrained_decoding<uses_compiled_grammar>
  GUARANTEE::output_is_valid_by_construction
  CONTRAST_OLD::generate_then_validate_then_retry
LEGACY_STAGES::["PARSE→VALIDATE→ROUTE"]
§2::COMPILE_ERRORS
GRAMMAR_COMPILATION_FAILURES::[
  regex_bombs,
  recursion_limits,
  circular_dependencies
]
REGEX_BOMB:
  PATTERN::"REGEX with catastrophic backtracking"
  EXAMPLE::"REGEX[(a+)+b]"
  DETECTION::compile_time_complexity_analysis
  ERROR::"REGEX_COMPLEXITY_EXCEEDED::{pattern}|LIMIT::O(n^2)"
  FIX::"Simplify regex or use explicit length constraints"
RECURSION_LIMIT:
  PATTERN::"Schema references creating infinite loop"
  EXAMPLE::"FIELD→§SELF,TARGET→§FIELD"
  DETECTION::dependency_graph_cycle_check
  ERROR::"CIRCULAR_DEPENDENCY::{chain}|DEPTH::{level}"
  FIX::"Break cycle or add explicit termination condition"
CONSTRAINT_CONFLICT:
  PATTERN::"Mutually exclusive constraints on same field"
  EXAMPLE::"[REQ∧OPT],[CONST[5]∧ENUM[1,2,3]]"
  DETECTION::constraint_compatibility_matrix
  ERROR::"CONFLICT::{constraint_a}∧{constraint_b}|REASON::{explanation}"
  FIX::"Remove conflicting constraint or restructure schema"
§3::ERROR_FORMATS
CONSTRAINT_ERROR::"FIELD::{name}|EXPECTED::{rule}|GOT::{value}"
CHAIN_ERROR::"CONSTRAINT_CHAIN::{index}|{constraint}|EXPECTED::{rule}|GOT::{value}"
TARGET_ERROR::"TARGET_MISSING::{target_id}|ALLOWED::[§SELF,§META,§INDEXER,§*_LOG,§KNOWLEDGE_BASE,POLICY.TARGETS]"
CONFLICT_ERROR::"CONFLICT::{constraint_a}∧{constraint_b}|{reason}"
DEPTH_ERROR::"DEPTH_EXCEEDED::{level}|MAX::100"
PARSE_ERROR::"SYNTAX::line_{n}[1_indexed]|{reason}"
UNKNOWN_FIELD::"UNKNOWN_KEY::{key}|POLICY::REJECT|IGNORE|WARN"
COMPILE_ERROR::"GRAMMAR_COMPILE_FAILED::{component}|{reason}"
ERROR_ORDERING::"parse_errors_first→compile_errors_second→constraint_errors_top_down→target_errors_last"
MULTI_ERROR::returns_first_only<fix_one_retry>
§4::VALIDATOR_CATCHES
ALWAYS_CHECKED::[
  "constraint_conflicts<REQ∧OPT,ENUM∧CONST>",
  target_existence<must_be_declared_or_builtin>,
  "type_mismatches[STRING_vs_NUMBER]",
  regex_validity<pattern_must_compile>,
  "depth_limits<100_levels_max>",
  grammar_compilability<schema_can_generate_valid_output>
]
NOT_CHECKED::[
  semantic_correctness<validator_only_checks_structure>,
  business_logic<your_responsibility>,
  broadcast_rollback<handler_manages_partial_failure>
]
§5::RETRY_PROTOCOL
STRATEGY::one_error_at_a_time<fix_then_retry>
MAX_RETRIES::3
FEEDBACK_LOOP::["compile_schema→generate_within_constraints→verify"]
V6_PARADIGM::"Compilation failures prevent generation - fix schema before emit"
V5_LEGACY::["generate→validate→error→fix→retry"]
ON_PARSE_ERROR:
  ACTION::check_envelope_and_indent_first
  COMMON::[
    tabs,
    "missing_===END===",
    "space_around_::"
  ]
ON_COMPILE_ERROR:
  ACTION::fix_schema_before_generation
  COMMON::[
    regex_bombs,
    circular_refs,
    constraint_conflicts
  ]
ON_CONSTRAINT_ERROR:
  ACTION::read_EXPECTED_and_GOT_carefully
  COMMON::[
    wrong_type,
    invalid_enum_value,
    regex_mismatch
  ]
ON_TARGET_ERROR:
  ACTION::use_builtin_or_declare_in_POLICY.TARGETS
  BUILTIN::[
    "§SELF",
    "§META",
    "§INDEXER",
    "§DECISION_LOG",
    "§RISK_LOG",
    "§KNOWLEDGE_BASE"
  ]
§6::SEVERITY
ERROR::must_fix<blocks_processing>
WARNING::should_fix<processing_continues>
INFO::suggestion<optional_improvement>
§7::INTEGRATION_HINTS
CONSTRAINED_DECODING::[Guidance,Outlines]
VALIDATE_REPAIR::[Pydantic,Guardrails]
RECOMMENDED_V6::"compile_first<schema_to_grammar→constrained_generation>"
LEGACY_V5::"hybrid<minimal_constraints⊕full_validation>"
§8::REFERENCE
CORE_ERRORS::"see octave-core-spec §6 NEVER"
CONSTRAINT_RULES::"see octave-schema-spec §2 CONSTRAINTS"
COMPRESSION_RULES::"see octave-data-spec §6 FORBIDDEN_REWRITES"
GENERATIVE_PHILOSOPHY::"see octave-rationale-spec §3 GENERATIVE_THEORY"
===END===
