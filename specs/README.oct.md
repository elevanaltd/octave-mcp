===OCTAVE_V6_SPECS===
META:
  TYPE::DOCUMENTATION
  VERSION::"6.0.0"
  STATUS::APPROVED
  MYTHOLOGY_INTEGRATED::true[domains_map_operators→archetypes_for_semantic_compression]
  EVIDENCE::docs/research/mythology-evidence-synthesis.oct.md[60-70%_compression,88-96%_comprehension]
  CHANGELOG::"v6.0: Generative Holographic Contracts - documents carry their own validation law (META.CONTRACT+META.GRAMMAR). Hermetic Anchoring for network-free standard resolution."

§1::CANONICAL_FILES
LLM_PROFILES::[
  octave-6-llm-core.oct.md["~280_tokens"][always_inject],
  octave-6-llm-schema.oct.md["~120_tokens"][for_L4_definitions+document_holography],
  octave-5-llm-data.oct.md["~75_tokens"][for_compression],
  octave-5-llm-execution.oct.md["~100_tokens"][for_debugging],
  octave-5-llm-rationale.oct.md["~160_tokens"][for_training_or_design]
]

LEGACY_V5::[
  octave-5-llm-core.oct.md[deprecated],
  octave-5-llm-schema.oct.md[deprecated]
]

ARCHIVE::_archive/[historical_development_artifacts]

§2::INJECTION_TABLE
TASK::INJECT::TOKENS::USE_CASE

RUNTIME:
  any_octave::core::"~250"::base_syntax_and_operators
  compress_prose::core⊕data::"~325"::telegram_style_compression
  define_schema::core⊕schema::"~340"::L4_holographic_definitions
  debug_errors::core⊕execution::"~350"::understanding_validator_feedback
  full_generation::core⊕schema⊕data::"~415"::complete_generation_capability

TRAINING:
  model_fine_tune::core⊕rationale::"~410"::teaching_OCTAVE_to_base_models
  complex_reasoning::core⊕schema⊕rationale::"~500"::designing_new_protocols
  full_with_debug::core⊕schema⊕data⊕execution::"~515"::complete_with_error_handling
  maximum::core⊕schema⊕data⊕execution⊕rationale::"~675"::everything

§3::COMPOSITION_RULES
CORE::always_required[base_syntax∧operators∧precedence]
SCHEMA::add_for[L4_holographic,constraint_chaining,targets,block_inheritance]
DATA::add_for[compression,abbreviations,inline_maps,forbidden_rewrites]
EXECUTION::add_for[error_formats,retry_protocol,validation_flow]
RATIONALE::add_for[design_philosophy,token_economics,training_context]

§4::VERSION_HISTORY
6.0.0::CURRENT
  changes::[generative_holographic_contracts,hermetic_anchoring,meta_contract_block,meta_grammar_block]
  additions::[META.CONTRACT,META.GRAMMAR,document_level_holography]
  impact::[jit_grammar_compilation,impossible_invalid_generation,network_free_standards]
5.1.0::DEPRECATED
  changes::[unicode_operators,precedence_rules,lexer_specification,tension_operator]
  operators::[→,⊕,⧺,⇌,∨,∧,§]
  ascii_aliases::[->|+|~|vs|||&|§]
5.0.3::LEGACY[supported_for_backward_compat]
  fixes::[empty_blocks,inline_map_nesting,broadcast_failure_semantics]
5.0.2::superseded
  fixes::[chaining_allowed,empty_lists,inline_maps,assembly_rule,error_ordering]
5.0.1::superseded[terminology_fixes]
5.0.0::superseded[initial_modular_split]

§5::SINGLE_SOURCE_OF_TRUTH
RULE::LLM_profiles_ARE_the_spec
MASTER_SPECS::archived[served_development_purpose]
DRIFT_PREVENTION::one_canonical_source_only

===END===
