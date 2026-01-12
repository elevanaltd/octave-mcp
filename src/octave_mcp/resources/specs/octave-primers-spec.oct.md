===OCTAVE_PRIMERS===
META:
  TYPE::LLM_PROFILE
  VERSION::"6.0.0"
  STATUS::APPROVED
  TOKENS::"~80"
  REQUIRES::octave-core-spec
  PURPOSE::"Ultra-compressed context injection for immediate capability"
  COMPRESSION_TIER::ULTRA["50%_compression",facts∧structure_only]

§1::DEFINITION
  OCTAVE::"Semantic DSL for LLMs"  // Universal definition for all primers
  PRIMER::"Minimal bootstrap for execution without understanding"
  SKILL::"Complete reference with rationale and examples"
  PRIMER_VS_SKILL::PRIMER[execution] ⇌ SKILL[comprehension] → PRIMER
  TOKEN_BUDGET::MAX[60]_RECOMMENDED[30-50]
  AUDIENCE::LLM_context_window[not_humans]
  COMPRESSION_REF::skills/octave-compression[§1b::ULTRA_TIER]

§2::MANDATORY_STRUCTURE
  SEQUENCE::===NAME===[META,§1::ESSENCE,§2::MAP,§3::SYNTAX,§4::ONE_SHOT,§5::VALIDATE,===END===]

  §2a::ESSENCE
    PURPOSE::"Skill-specific action + OCTAVE definition"
    CONTENT::PURPOSE[action_verb]+OCTAVE[universal_def]+METHOD
    REQUIRED::[skill_action,OCTAVE_definition,method]
    EXAMPLE::"PURPOSE::Write_OCTAVE OCTAVE::Semantic_DSL_for_LLMs"
    UNIVERSAL::ALL_PRIMERS_USE_SAME_OCTAVE_DEF

  §2b::MAP
    PURPOSE::"Direct transformation rules"
    FORMAT::INPUT→OUTPUT[selection_hint]
    NO::[explanations,rationale,why]
    YES::[equivalencies,arrows,selection_hints]
    EXAMPLE::ARCHETYPE→ZEUS∨ATLAS[pick_by_intent]

  §2c::SYNTAX
    PURPOSE::"Operator legend with meanings"
    FORMAT::SYMBOL::meaning
    REQUIRED::minimum_4_operators_defined
    EXAMPLE::⊕::synthesis, →::transform, NEVER[]::constraint

  §2d::ONE_SHOT
    PURPOSE::"Single perfect transformation"
    FORMAT::IN::"prose"\nOUT::octave_result
    DENSITY::maximum_compression_shown

  §2e::VALIDATE
    PURPOSE::"Success criteria"
    FORMAT::MUST::[criterion_list]
    REQUIRED::[valid_OCTAVE,preserve_§_names_verbatim]
    TOKENS::<10

§3::ANTI_PATTERNS
  AVOID::[
    "Explaining_why[trust_latent_knowledge]",
    "Multiple_examples[one_perfect_shot]",
    "Human_readability[optimize_for_LLM]",
    "Exceeding_100_tokens[defeats_purpose]",
    "Teaching_theory[only_execution_matters]"
  ]

§4::COMPARISON_MATRIX
  ASPECT::PRIMER→SKILL
  PURPOSE::execution→understanding
  TOKENS::30-60→500-800
  EXAMPLES::one→many
  RATIONALE::none→complete
  AUDIENCE::LLM→human+LLM
  METAPHOR::cheat_sheet→textbook
  COMPRESSION::ULTRA[50%]→LOSSLESS[100%]

§5::VALIDATION_CRITERIA
  VALID_PRIMER::[
    tokens<60∧
    has_one_shot∧
    has_purpose_line∧
    has_operator_legend∧
    no_explanations∧
    executable_immediately∧
    self_referential[uses_format_it_teaches]∧
    compression_tier==ULTRA
  ]

===END===
