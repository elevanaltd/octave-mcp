===OCTAVE_PRIMER_SPEC===
META:
  TYPE::SPECIFICATION
  VERSION::"1.0.0"
  STATUS::APPROVED
  PURPOSE::"Lightweight context injection for immediate capability activation"
  TIER::ULTRA
  TOKENS::~50

§1::DEFINITION
  PRIMER::"Minimal bootstrap for execution without understanding"
  SKILL::"Complete reference with rationale and examples"
  PRIMER_VS_SKILL::PRIMER[execution] ⇌ SKILL[comprehension] → PRIMER
  TOKEN_BUDGET::MAX[100]_RECOMMENDED[50-90]
  AUDIENCE::LLM_context_window[not_humans]

§2::MANDATORY_STRUCTURE
  SEQUENCE::===NAME_PRIMER===[META,§1::ESSENCE,§2::MAP,§3::SYNTAX,§4::ONE_SHOT,§5::VALIDATE,===END===]

  §2a::ESSENCE
    PURPOSE::"Core concept in <20 tokens"
    CONTENT::TARGET+METHOD+PRINCIPLE
    EXAMPLE::TARGET::60%_compression→preserve[soul,constraints]

  §2b::MAP
    PURPOSE::"Direct transformation rules"
    FORMAT::INPUT::[OUTPUT_PATTERN]
    NO::[explanations,rationale,why]
    YES::[equivalencies,arrows,brackets]

  §2c::SYNTAX
    PURPOSE::"Critical operators only"
    FORMAT::OPERATOR::usage_pattern
    TRUST::latent_LLM_knowledge

  §2d::ONE_SHOT
    PURPOSE::"Single perfect transformation"
    FORMAT::IN::"prose"\nOUT::octave_result
    DENSITY::maximum_compression_shown

  §2e::VALIDATE
    PURPOSE::"Success criteria"
    FORMAT::MUST::[criterion_list]
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
  TOKENS::50-90→500-800
  EXAMPLES::one→many
  RATIONALE::none→complete
  AUDIENCE::LLM→human+LLM
  METAPHOR::cheat_sheet→textbook

§5::VALIDATION_CRITERIA
  VALID_PRIMER::[
    tokens<100∧
    has_one_shot∧
    no_explanations∧
    executable_immediately∧
    self_referential[uses_format_it_teaches]
  ]

===END===
