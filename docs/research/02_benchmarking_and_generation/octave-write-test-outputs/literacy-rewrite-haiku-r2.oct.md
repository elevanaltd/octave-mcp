===OCTAVE_LITERACY===
META:
  TYPE::SKILL
  VERSION::"2.0.0"
  STATUS::ACTIVE
  PURPOSE::"Foundational OCTAVE competence: Why structured data, who consumes it, how syntax enables semantic density"
  OCTAVE::"Olympian Common Text And Vocabulary Engine — Semantic DSL for LLMs"
  AUDIENCE::"LLMs exclusively (not humans). North Star: loss accounting system for LLM communication"
  TIER::LOSSLESS
  SPEC_REFERENCE::octave-core-spec.oct.md
  V6_FEATURES::"CONTRACT/GRAMMAR blocks, assembly rules, .oct.md extension"
  NEXT_SKILLS::[octave-mastery, octave-mythology]

§0::LLM_CONSUMPTION_PARADIGM
  // ===FOUNDATIONAL_FRAMING===
  // OCTAVE is designed for LLM consumption exclusively. This is not arbitrary.
  // Every design choice optimizes for how LLMs parse and emit structured information.

  THE_PROBLEM:
    NATURAL_LANGUAGE::"Ambiguous, redundant, parse-expensive for LLMs"
    TOKEN_WASTE::"Prose explanation consumes tokens that could carry semantic payload"
    RECONSTRUCTION_DRIFT::"Human-written explanations rebuild knowledge imperfectly"
    SOLUTION::"Structured data native to LLM tokenization + probability distributions"

  WHAT_THIS_MEANS:
    EFFICIENCY::"Structured data tokenizes into fewer, more meaningful units than prose"
    PRECISION::"Syntax constraints eliminate ambiguity — LLM can reliably extract intent"
    MYTHOLOGICAL_ACTIVATION::"Archetypes activate pre-trained probability clusters — semantic compression via existing embeddings"
    ZERO_AMBIGUITY::"Grammar constraints make invalid syntax impossible to generate — deterministic parsing"

  WHY_SYNTAX_CHOICES_MATTER:
    DOUBLE_COLON_NO_SPACES::"KEY::value tokenizes as distinct units, not KEY :: value with spaces"
      EFFECT::"Fewer tokens, tighter semantic units, LLM attention more focused"
    INDENT_EXACTLY_2_SPACES::"Consistent tokenization depth → LLM learns positional semantics"
      EFFECT::"Parser doesn't waste inference on tab-vs-space ambiguity, nesting is unambiguous"
    OPERATORS_WITH_PRECEDENCE::"Container, Concatenation, Synthesis, Tension, Constraint, Alternative, Flow"
      EFFECT::"LLM can predict operator binding without backtracking"
    ENVELOPE_MARKERS_===NAME===::"Clear document boundaries → LLM knows scope precisely"
      EFFECT::"Prevents context bleeding, enables parallel document processing"

  THE_NORTH_STAR:
    GOAL::"Maximum information density with zero ambiguity"
    CONSTRAINT::"Every token must carry semantic payload"
    METHOD::"Structure > Prose, Operators > Explanation, Mythology > Generic Terms"
    PROOF::"octave-compression achieves 60-80% compression vs 15-20% for prose documentation"

§1::CORE_SYNTAX
  // Why each rule exists: optimized for LLM tokenization and probability flow

  ASSIGNMENT::KEY::value
    // RULE: No spaces around ::
    // WHY: Double colon without spaces is a distinct token boundary. With spaces, LLM tokenizer adds extra tokens.
    // EFFECT: Information density per token increases

  BLOCK::KEY:[newline_then_2_spaces]
    // RULE: Single colon, newline, exactly 2 spaces for nesting
    // WHY: LLM attention tracks indentation depth as positional encoding. 2 spaces is minimum unambiguous increment.
    // EFFECT: Parser learns colon-plus-newline signals new context level

  LIST::[item1,item2,item3]
    // Brackets signal collection to LLM. Commas with no spaces minimize tokens.
    // LLM recognizes [item1,item2] as single semantic unit

  STRING::"value_with_spaces"∨bare_word
    // RULE: Quotes required only if value contains spaces or special chars
    // WHY: Bare words tokenize more efficiently. Quotes add overhead only when necessary.

  NUMBER::42∨3.14∨-1e10
    // LLM tokenizes numbers as numeric tokens, not word tokens. No quotes needed.
    // Numeric tokens are single-token units regardless of magnitude

  BOOLEAN::true∨false
    // RULE: Lowercase only
    // WHY: LLM probability distribution for booleans is tuned to lowercase. Uppercase adds confusion.

  NULL::null
    // RULE: Lowercase only (matching boolean principle)

  COMMENT:://
    // Comments preserved for human reading during LLM debugging/auditing
    // LLM skips comment tokens during inference but respects them during parsing

  §1b::LITERAL_ZONES
    // Fenced code blocks pass through with ZERO processing
    // WHY: LLM must respect embedded syntax without reinterpretation
    // MECHANISM: Three or more backticks creates zone where OCTAVE parsing suspends

    SYNTAX::"KEY, newline, fence_marker, content, fence_marker"
    RULES::[zero_processing_between_fences,tabs_allowed,NFC_bypass,info_tag_preserved]
    EFFECT::"Content is opaque to OCTAVE parser, transparent to LLM consumption"

  §1c::BRACKET_FORMS
    // LLM recognizes bracket patterns as semantic categories

    CONTAINER::[a,b,c]
      // Bare brackets = unordered collection. LLM treats as set/list.

    CONSTRUCTOR::NAME[args]
      // NAME[...] signals specialized container type. LLM learns: NAME defines the semantics.
      // EXAMPLES::[REGEX_pattern, ENUM_options, RANGE_bounds]
      // EFFECT: Extensible type system without explicit schema bloat

    INLINE_MAP::[key::val,key2::val2]
      // Dense key-value pairs in single bracket. LLM parses as homogeneous structure.
      // Values must be atoms (no nested structures) for efficient tokenization.

    HOLOGRAPHIC::"schema_mode_combines_data_constraint_and_reference"
      // Single token stream for validation and routing.
      // LLM can validate and route in one forward pass.

§2::OPERATORS
  // Operators are semantic compression. Each one encodes a relationship that would require prose explanation.
  // Operators activate LLM's pre-trained knowledge of mathematical/logical relationships.

  EXPRESSION_OPERATORS::[precedence_order_tight_to_loose_binding]

    CONTAINER_PRECEDENCE_1::[a,b,c]
      // Tightest binding. Creates semantic unit.

    CONCATENATION_PRECEDENCE_2::A⧺B
      // Mechanical join. Stick these together as-is. No synthesis, just assembly.
      // ASCII_ALIAS::" ~ "
      // EXAMPLE:: module_a⧺module_b
      // WHY: Single token encodes combine without interpretation

    SYNTHESIS_PRECEDENCE_3::A⊕B
      // Emergent whole. Combine these and produce something new.
      // ASCII_ALIAS::" + "
      // EXAMPLE:: Code⊕Tests → Verified_System
      // WHY: Activates LLM's synthesis probability cluster — richer than mechanical join

    TENSION_PRECEDENCE_4::A⇌B
      // Binary opposition. These are in tension; trade-off exists.
      // ASCII_ALIAS::" vs "
      // RULE: Requires word boundaries
      // VALID::"Speed vs Quality"
      // INVALID::"SpeedvsQuality"
      // WHY: Encodes optimization frontier exists here — single token, rich semantics

    CONSTRAINT_PRECEDENCE_5::[A∧B∧C]
      // All must be true. Logical AND.
      // ASCII_ALIAS::" & "
      // RULE: Only appears inside brackets, never bare
      // VALID::[A∧B∧C]
      // INVALID::A∧B
      // WHY: Bracket scope prevents ambiguous precedence

    ALTERNATIVE_PRECEDENCE_6::A∨B
      // One or both can be true. Logical OR.
      // ASCII_ALIAS::" | "
      // EXAMPLE:: Production∨Development
      // WHY: Activates LLM's choice semantics

    FLOW_PRECEDENCE_7::[A→B→C]
      // Causal sequence. A leads to B leads to C.
      // ASCII_ALIAS::" -> "
      // RIGHT_ASSOCIATIVE:: A→B→C means A→(B→C)
      // WHY: Encodes narrative/dependency flow in single token stream

  PREFIX_AND_SPECIAL:
    SECTION_TARGET::→§DECISION_LOG
      // Section reference. Links to document location. LLM can jump scope.

    COMMENT_MARKER:://
      // Line-start or post-value. LLM parser skips; humans read during debugging.

§3::CRITICAL_RULES
  // Each rule optimizes either tokenization efficiency, parsing determinism, or LLM probability alignment

  RULE_1::No_spaces_around_assignment_::
    WRONG::"KEY :: value"
    RIGHT::"KEY::value"
    WHY::"Spaces add tokens. No spaces = 1 token boundary instead of 3."
    EFFECT:: "3x token efficiency for assignments"

  RULE_2::Indent_exactly_2_spaces_per_level
    CONSTRAINT::"NO TABS. Always 2 spaces."
    WHY::"LLM tokenizer learns positional semantics from consistent indentation."
    EFFECT::"Nesting depth is unambiguous to parser"

  RULE_3::Keys_follow_identifier_rules
    PATTERN::"[A-Z, a-z, 0-9, _] start with letter or underscore"
    WHY::"Matches LLM tokenizer's identifier patterns. Prevents collision with operators."

  RULE_4::Envelopes_delimit_document_scope
    SYNTAX::"===NAME=== at start, ===END=== at finish"
    CONSTRAINT::"NAME must be [A-Z_][A-Z0-9_]*"
    WHY::"Clear boundaries enable LLM to process in parallel or cache context."
    EFFECT::"Prevents context bleeding between documents"

  RULE_5::Lowercase_for_true_false_null
    WRONG::"True, False, NULL"
    RIGHT::"true, false, null"
    WHY::"LLM's probability distribution is tuned to lowercase boolean constants."

  RULE_6::Constraint_∧_only_inside_brackets
    WRONG::"A∧B"
    RIGHT::"[A∧B∧C]"
    WHY::"Bracket scope prevents precedence ambiguity"

  RULE_7::Tension_⇌_is_binary_only
    WRONG::"A⇌B⇌C"
    RIGHT::"A⇌B"
    WHY::"Tension implies tradeoff. Multiple simultaneous tensions are ambiguous."

  RULE_8::Quote_section_anchors_when_used_as_values
    WRONG::"REFERENCE::§2_BEHAVIOR"
    RIGHT::"REFERENCE::\"§2_BEHAVIOR\""
    WHY::"Prevents § from being parsed as section marker instead of literal string"

  RULE_9::File_extension_is_.oct.md
    CANONICAL::.oct.md
    DEPRECATED::.octave.txt
    WHY::"md signals human-readable wrapper; oct signals OCTAVE payload"

  §3b::V6_ENVELOPE_STRUCTURE
    FILE_STRUCTURE::[===NAME===,META_BLOCK,SEPARATOR_OPTIONAL,BODY,===END===]
    META_REQUIRED::[TYPE,VERSION]
    META_V6_OPTIONAL::[CONTRACT,GRAMMAR]

  §3c::ASSEMBLY_RULES
    WHEN_CONCATENATING::"Omit intermediate ===END=== markers (only final ===END=== terminates)"
    USE_CASES::[agent_context_injection,specification_layering,multi_part_documents]
    WHY::"Enables documents to stack specifications without duplication. LLM parses single coherent scope."

§4::EXAMPLE_BLOCK
  ===EXAMPLE===
  STATUS::ACTIVE
  PHASES:
    PLAN::[Research→Design]
    BUILD::[Code⊕Test]
  METRICS:
    SPEED::"High"
    QUALITY::"Verified"
  ===END===

§5::NEXT_STEPS
  AFTER_MASTERING_THIS_SKILL:
    LOAD_OCTAVE_MASTERY::"Advanced semantic vocabulary, archetype patterns, holographic contracts"
    LOAD_OCTAVE_MYTHOLOGY::"Mythological compression, semantic shorthand for LLM audiences"
    LOAD_OCTAVE_COMPRESSION::"Transform prose to OCTAVE with fidelity guarantees"

===END===
