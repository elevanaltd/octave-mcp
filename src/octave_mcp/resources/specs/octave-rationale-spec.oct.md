===OCTAVE_RATIONALE===
META:
  TYPE::LLM_PROFILE
  VERSION::"6.0.0"
  STATUS::APPROVED

  TOKENS::"~200"
  REQUIRES::octave-core-spec
  PURPOSE::architectural_decision_record
  IMPLEMENTATION_NOTES::"Design rationale document only. No code implementation. Referenced by core, data, schema, execution profiles."

---

// OCTAVE RATIONALE: The "Why" behind the syntax. Inject for training or advanced reasoning.

§1::DESIGN_PHILOSOPHY
CORE_TENET::generative_holographic_contracts
TARGET_AUDIENCE::[LLMs_with_high_reasoning,Prompt_Engineers,System_Architects]

PARADIGM_SHIFT::"Validation precedes generation - schemas are executable contracts, not post-hoc checks"
HOLOGRAPHIC_PRINCIPLE::"Value, constraint, and routing encoded in single line - teaching by example"

GOALS:
  1::ELIMINATE_AMBIGUITY::prose_is_probabilistic|OCTAVE_is_deterministic
  2::OPTIMIZE_CONTEXT::reduce_token_usage_by_30_percent_vs_JSON
  3::PREVENT_HALLUCINATION::strong_syntax_anchors_reduce_drift
  4::ENABLE_GENERATION::schemas_define_valid_output_space_before_emission

§2::SYNTAX_DECISIONS
NO_CURLY_BRACES:
  REASON::avoids_json_bias
  EXPLANATION::"The moment an LLM sees '{', it biases towards valid JSON, requiring quoted keys and trailing commas. OCTAVE uses indentation for hierarchy."
  BENEFIT::[template_safety_for_jinja,token_savings,no_escaping_needed]

DOUBLE_COLON__::__:
  REASON::strong_binding
  EXPLANATION::"Standard colons ':' are ambiguous in text (time, ratios, grammar). '::' creates a unique token that signifies a hard Data assignment."
  RULE::no_spaces_around_::[maximizes_density]

SYMBOLS__§_&_->_+_~:
  REASON::token_anchors
  EXPLANATION::"Rare tokens act as 'cognitive speed bumps' for the LLM, forcing it to switch from prose-generation mode to logic-processing mode."
  USAGE::[
    §::target_reference,
    &::constraint_chain,
    ->::directional_flow,
    +::synthesis,
    ~::concatenation
  ]

§3::GENERATIVE_THEORY
VALIDATION_FIRST_PRINCIPLE::"Schemas must be compiled BEFORE generation to define valid output space"

WHY_VALIDATION_MUST_PRECEDE:
  PROBLEM::"Post-hoc validation creates formatting theater - LLM generates, validator rejects, retry loop wastes tokens"
  SOLUTION::"Compile schema into grammar constraints, LLM generates within valid space from start"
  BENEFIT::[zero_retry_loops,predictable_token_cost,guaranteed_valid_output]

HOLOGRAPHIC_ENCODING:
  CONCEPT::L4_schema_density
  PROBLEM::"Schemas are usually verbose (OpenAPI/JSONSchema)."
  SOLUTION::"Encode the value, validation, and routing in a single line."
  PATTERN::KEY::["example_value"∧CONSTRAINT→§TARGET]
  RESULT::"The example teaches the format. The constraint enforces it. The target routes it. 3-in-1."

GENERATIVE_WORKFLOW:
  SEQUENCE::[READ_META→COMPILE_GRAMMAR→GENERATE_WITHIN_CONSTRAINTS]
  CONTRAST_OLD::[GENERATE→VALIDATE→RETRY_IF_INVALID]
  ADVANTAGE::"Single-pass generation with structural guarantees"

§4::TOKEN_ECONOMICS
WHITESPACE_POLICY:
  RULE::indentation_only
  REASON::"Spaces around operators (e.g., ' :: ') cost tokens without adding meaning. Indentation conveys hierarchy cheaper than brackets."

STOPWORDS_IN_DATA:
  RULE::drop_[the,a,is,of]
  REASON::"LLMs can reconstruct meaning without connecting words. 'status::active' is as clear as 'the status is active' but 70% cheaper."

§5::OPERATIONAL_SAFETY
STRICT_ENVELOPES:
  START_END::[===NAME===...===END===]
  REASON::"Prevents 'run-on' generation. Gives the parser definitive start/stop signals."

VERSIONING:
  STRATEGY::semantic_lockstep
  REASON::"Core defines the physics. Data/Schema define the chemistry. Versions must match to ensure the reaction is stable."

===END===
