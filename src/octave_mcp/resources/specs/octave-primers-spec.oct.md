===OCTAVE_PRIMERS===
META:
  TYPE::LLM_PROFILE
  VERSION::"6.5.0"
  STATUS::ACTIVE
  TOKENS::"~80"
  REQUIRES::octave-core-spec
  PURPOSE::"Ultra-compressed context injection for immediate capability"
  COMPRESSION_TIER::"ULTRA: 50 percent compression, facts and structure only"
§1::DEFINITION
  OCTAVE::"Olympian Common Text And Vocabulary Engine — Semantic DSL for LLMs" // Universal definition for all primers
  PRIMER::"Minimal bootstrap for a single workflow — execution OR comprehension; written in PITH (pith-spec.md)"
  PRIMER_MODES::["execution: write without deep understanding","reading: comprehend without generating output"]
  SKILL::"Complete reference with rationale and examples"
  PRIMER_VS_SKILL::"a primer covers a single workflow; a skill is the full reference; load the primer when one workflow is needed"
  TOKEN_BUDGET::"MAX[500]_RECOMMENDED[300-450]"
  // Note: OCTAVE syntax tokenizes about five times the word count because of double colons, operators and section signs
  MEASURE::"cl100k_base[tiktoken]_over_canonical_file_bytes[utf-8]"
  AUDIENCE::"LLM_context_window[not_humans]"
  COMPRESSION_REF::"skills/octave-compression[§1b::ULTRA_TIER]"
§2::MANDATORY_STRUCTURE
  SEQUENCE::"===NAME===[META,§1::ESSENCE,§2::MAP,§3::SYNTAX,§4::ONE_SHOT,§5::VALIDATE,===END===]"
  §2a::ESSENCE
    PURPOSE::"Skill-specific action and OCTAVE definition"
    CONTENT::"the purpose as an action verb, the universal OCTAVE definition, and the method"
    REQUIRED::[
      skill_action,
      OCTAVE_definition,
      method
    ]
    EXAMPLE::"PURPOSE::\"Write OCTAVE\" OCTAVE::\"Olympian Common Text And Vocabulary Engine — Semantic DSL for LLMs\""
    UNIVERSAL::ALL_PRIMERS_USE_SAME_OCTAVE_DEF
  §2b::MAP
    PURPOSE::"Direct transformation rules"
    FORMAT::"input and output as plain-word rows with the selection hint in words"
    NO::[
      explanations,
      rationale,
      why
    ]
    YES::[
      equivalencies,
      plain_word_rows,
      selection_hints
    ]
    EXAMPLE::"audit or critical work: use the LOSSLESS tier"
  §2c::SYNTAX
    PURPOSE::"Reading legend: the operators a reader meets in documents it receives; never an authoring instruction, relations are written in words (pith-spec.md). The legend is a fenced READING_LEGEND block; no operator glyph appears outside that fence."
    FORMAT::"SYMBOL then meaning, one row per operator, inside the fence"
    REQUIRED::minimum_4_operators_defined
    READING_LEGEND:
      ```
      ⊕         synthesis
      →         transform
      NEVER[]   constraint
      ```
  §2d::ONE_SHOT
    PURPOSE::"Single perfect transformation"
    FORMAT::"IN::prose / OUT::octave_result"
    DENSITY::maximum_compression_shown
  §2e::VALIDATE
    PURPOSE::"Success criteria"
    FORMAT::"MUST::[criterion_list]"
    REQUIRED::["valid OCTAVE","section names kept verbatim"]
    TOKENS::"<10"
§3::ANTI_PATTERNS
  AVOID::[
    "Explaining_why[trust_latent_knowledge]",
    "Multiple_examples[one_perfect_shot]",
    "Human_readability[optimize_for_LLM]",
    "Exceeding_500_tokens[defeats_purpose]",
    "Teaching_theory[only_workflow_activation_matters]",
    "Teaching mythology or operators as authoring vocabulary: write in PITH (pith-spec.md)"
  ]
§4::COMPARISON_MATRIX
  ASPECT::"primer versus skill"
  PURPOSE::"primer: single workflow; skill: full understanding"
  TOKENS::"primer: 300 to 500; skill: per octave-skills-spec TOKEN_TARGET"
  EXAMPLES::"primer: one; skill: many"
  RATIONALE::"primer: none; skill: complete"
  AUDIENCE::"primer: LLM; skill: human and LLM"
  METAPHOR::"primer: cheat sheet; skill: textbook"
  COMPRESSION::"primer: its META records its own tier, ULTRA, as a loss receipt (a tier frozen for reading); skill: LOSSLESS, the full reference"
§5::VALIDATION_CRITERIA
  VALID_PRIMER::[
    "tokens<=500",
    has_one_shot,
    has_purpose_line,
    has_reading_legend,
    reading_legend_in_a_fenced_READING_LEGEND_block,
    "written_in_PITH[pith-spec.md]",
    no_explanations,
    executable_immediately,
    "self_referential[uses_format_it_teaches]",
    META_records_its_own_tier_and_loss_profile_as_a_loss_receipt
  ]
===END===
