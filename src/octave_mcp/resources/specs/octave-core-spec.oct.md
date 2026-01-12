===OCTAVE_CORE===
META:
  TYPE::LLM_PROFILE
  VERSION::"6.0.0"
  STATUS::APPROVED

  TOKENS::"~280"
  REQUIRES::nothing
  ENABLES::[schema,data]
  TEACHES::[§skills/octave-literacy,§skills/octave-mastery]
  IMPLEMENTATION_NOTES::"Lexer (308 LOC), Parser (389 LOC), Emitter (140 LOC), AST (62 LOC) all production-ready. Full envelope, operators, types, structure complete. v6: Generative Holographic Contracts - adds CONTRACT and GRAMMAR blocks to META."
  IMPLEMENTATION_REF::[src/octave_mcp/core/lexer.py,src/octave_mcp/core/parser.py,src/octave_mcp/core/emitter.py,src/octave_mcp/core/ast_nodes.py]

  CONTRACT::HOLOGRAPHIC[
    PRINCIPLE::"Documents carry their own validation law",
    MECHANISM::JIT_GRAMMAR_COMPILATION[META→GBNF],
    ANCHORING::HERMETIC[frozen@sha256|latest@local],
    SELF_DESCRIBING::"META block defines how to parse the document itself"
  ]

  GRAMMAR::[
    GENERATOR::OCTAVE_GBNF_COMPILER[planned],
    INTEGRATION::[llama.cpp,Outlines,vLLM],
    BENEFIT::IMPOSSIBLE_TO_GENERATE_INVALID_SYNTAX,
    SELF_VALIDATION::"Document contains rules to validate itself"
  ]

  // HOLOGRAPHIC PRINCIPLE (v6.0 Core Feature):
  // OCTAVE documents are SELF-DESCRIBING. The META block can contain
  // CONTRACT and GRAMMAR fields that define validation rules for the
  // document itself. A parser reads META first, compiles the grammar,
  // then validates the document against its own rules.
  //
  // This enables:
  // - Documents that cannot be parsed incorrectly (constrained generation)
  // - Schema evolution without parser updates
  // - Domain-specific validation embedded in documents
  // - Hermetic reproducibility (frozen schema versions)

---

// OCTAVE CORE: The spine. Always inject this.
// Operators map to mythological domains for semantic density (see octave-mastery skill).
// Mythology = compression shorthand, not decoration (docs/research/mythology-evidence-synthesis.oct.md).

§1::ENVELOPE
FILE_EXTENSION::.oct.md[canonical][.octave.txt_deprecated]
START::===NAME===[first_line,exact_match]
META::required[TYPE,VERSION][immediately_after_start]
META_OPTIONAL::[CONTRACT,GRAMMAR][v6_holographic_contracts]
SEPARATOR::---[optional_for_discovery,signals_metadata_boundary]
END::===END===[last_line,exact_match,mandatory]
DUPLICATES::keys_must_be_unique_per_block
COMMENTS:://[line_start_or_after_value]

ASSEMBLY::when_profiles_concatenated[core+schema+data]→only_final_===END===_terminates
ASSEMBLY_RULE::omit_separator_in_assembled_profiles[only_standalone_documents]

// ASSEMBLY EXAMPLE (Issue #108):
// When injecting OCTAVE profiles into agent context, concatenate them.
// Each profile omits its ===END=== except the final one.
//
// STANDALONE (single file):
//   ===CORE===
//   META:
//     TYPE::LLM_PROFILE
//   ---
//   §1::CONTENT
//   ===END===
//
// ASSEMBLED (core+schema injected together):
//   ===CORE===
//   META:
//     TYPE::LLM_PROFILE
//   §1::CONTENT
//   ===SCHEMA===
//   META:
//     TYPE::LLM_PROFILE
//   §1::DEFINITIONS
//   ===END===
//
// USE_CASES::[
//   agent_context_injection[core+schema+data_profiles],
//   specification_layering[base_spec+extensions],
//   multi_part_documents[header+body+footer]
// ]

§2::OPERATORS

// LAYER 1: STRUCTURAL (statement/field level, not expressions)
STRUCTURAL:
  ::    assign      KEY::value[binding]
  :     block       KEY:[newline_then_indent]

// LAYER 2: EXPRESSION (inside values, precedence applies)
// Lower number = binds tighter
EXPRESSION:
  PREC::UNICODE::ASCII::SEMANTIC::USAGE::ASSOC
  1    []       []     container   [a,b,c]                   n/a
  2    ⧺        ~      concat      A⧺B[mechanical_join]      left
  3    ⊕        +      synthesis   A⊕B[emergent_whole]       left
  4    ⇌        vs     tension     A⇌B[binary_opposition]    none[binary_only]
  5    ∧        &      constraint  [A∧B∧C]                   left
  6    ∨        |      alternative A∨B                       left
  7    →        ->     flow        A→B→C                     right

// LAYER 3: PREFIX/SPECIAL
PREFIX:
  §     target      §INDEXER∨§./path
  //    comment     //text[to_end_of_line]

§2b::LEXER_RULES
LONGEST_MATCH::"::_recognized_before_:"
UNICODE_NORMALIZATION::NFC[canonical_composition]
ASCII_ALIASES::accepted_normalized_to_unicode

// ASCII alias boundary rules
vs::requires_word_boundaries[whitespace∨bracket∨paren∨start∨end]
VALID::"A vs B"∨"[Speed vs Quality]"
INVALID::"SpeedvsQuality"[no_boundaries]
RECOMMENDATION::prefer_canonical_unicode_in_emission

§2c::BRACKET_FORMS
CONTAINER::[a,b,c][bare_brackets_are_lists]
CONSTRUCTOR::NAME[args][e.g._REGEX[pattern]_ENUM[a,b]]
HOLOGRAPHIC::["value"∧CONSTRAINT→§TARGET][schema_mode]
RULE::NAME[...]_is_constructor|bare_[...]_is_container

§3::TYPES
STRING::bare_word|"quoted"[when:spaces,special,reserved]
NUMBER::42|3.14|-1e10[no_quotes]
BOOLEAN::true|false[lowercase_only]
NULL::null[lowercase_only]
LIST::[a,b,c]|[][empty_allowed]
ESCAPES::["quote","backslash","newline","tab"][inside_quotes_only]

§3b::QUOTING_RULES
// When to use quotes - critical for spec compliance
MUST_QUOTE::[
  spaces["hello world"],
  special_chars["~30%","coverage::87%","REGEX[\"^pattern$\"]"],
  operators_as_values["::","|","&","§"],
  curly_braces["{template}"],
  parentheses["(grouped)"],
  backslashes["path\\to\\file"],
  cross_references["see octave-core-spec §6"],
  section_markers_in_values["§SELF reference"]
]

QUOTE_GUIDELINES::
  IF[contains_non_alphanumeric]→quote_it
  IF[starts_with_§_but_not_anchor]→quote_it
  IF[contains_unicode_symbols_not_operators]→quote_it
  IF[ambiguous_parsing]→quote_it

SAFE_WITHOUT_QUOTES::[
  bare_identifiers[simple_name,STATUS,BUILD],
  numbers[42,3.14,-1e10],
  booleans[true,false],
  null[null],
  defined_operators_in_expressions[A→B,X∨Y,P∧Q]
]

§4::STRUCTURE
INDENT::2_spaces_per_level[no_tabs_ever]
KEYS::[A-Z,a-z,0-9,_][start_with_letter_or_underscore]
SECTION_NAMES::preserve_exactly[§1::NAME_not_§1::N][no_compression_allowed]
NESTING::indent_creates_child_relationship
BLANK_LINES::allowed_for_readability
EMPTY_BLOCK::KEY:[valid_with_no_children]

§5::MODES
DATA:
  PATTERN::KEY::value
  LEVELS::L1∨L2
  BRACKETS::lists[a,b,c]∨inline_maps[k::v,k2::v2]
  INLINE_MAP_NESTING::forbidden[values_must_be_atoms]
  USE::instances[sessions,configs,runtime_state]

SCHEMA:
  PATTERN::KEY::["example"∧CONSTRAINT→§TARGET]
  LEVELS::L3∨L4
  BRACKETS::holographic_container[value∧constraints→target]
  USE::definitions[types,validation_rules,extraction_routing]

§6::NEVER
ERRORS::[
  tabs,
  any_whitespace_around_::,
  newline_in_quoted_string,
  bare_flow[KEY→value],
  wrong_case[True,False,NULL],
  missing_final_===END===,
  ∧_outside_brackets,
  chained_tension[A⇌B⇌C],
  vs_without_boundaries[SpeedvsQuality]
]

§6b::VALIDATION_CHECKLIST
// Quick validation checklist for OCTAVE documents (Issue #107)
ENVELOPE::[
  starts_with_===NAME===,
  META_block_with_TYPE_and_VERSION,
  ends_with_===END===
]
STRUCTURE::[
  2_space_indent_per_level,
  no_tabs_anywhere,
  keys_unique_per_block,
  no_whitespace_around_double_colon
]
OPERATORS::[
  double_colon_for_assignment,
  single_colon_for_blocks,
  arrow_for_flow,
  tension_for_binary_opposition,
  constraint_only_inside_brackets
]
TYPES::[
  true_false_lowercase,
  null_lowercase,
  strings_quoted_if_special_chars,
  lists_use_square_brackets
]
SCHEMA_MODE::[
  holographic_pattern_in_brackets,
  constraints_before_target,
  target_uses_section_prefix
]

§7::CANONICAL_EXAMPLES
// Reference patterns only. Not standalone documents.

DATA_PATTERN:
  ID::sess_abc123
  STATUS::ACTIVE
  PHASE::B2
  TAGS::[api,auth]
  EMPTY_LIST::[]
  FLOW::[INIT→BUILD→TEST]
  BLOCKERS::issue_1∨issue_2
  QUALITY::[tests::5/5,lint::ok,coverage::"87%"]
  PATH::src⧺components⧺auth

// TENSION PATTERN (binary only, followed by resolution)
OPERATIONAL_TENSION::Speed⇌Quality→Balanced_Delivery
TRADE_OFF::[Latency⇌Accuracy,Cost⇌Quality]

// SYNTHESIS PATTERN (emergent combination)
APPROACH::Architecture⊕Implementation⊕Testing

// INLINE_MAP_NESTING (Forbidden pattern)
BAD::[config::[nested::value]]
GOOD:
  CONFIG:
    NESTED::value

SCHEMA_PATTERN:
  ID::["user_123"∧REQ∧REGEX["^user_\\w+$"]→§INDEXER]
  STATUS::["ACTIVE"∧REQ∧ENUM[ACTIVE,SUSPENDED]→§META]
  EMAIL::["user@example.com"∧REQ∧TYPE[STRING]→§INDEXER]
  ROLES::[["admin","viewer"]∧OPT∧TYPE[LIST]→§INDEXER]
  NOTES::["Optional context"∧OPT→§SELF]

BLOCK_INHERITANCE_PATTERN:
  RISKS[→§RISK_LOG]:
    CRITICAL::["auth_bypass"∧REQ]
    WARNING::["rate_limit"∧OPT→§SELF]

// PRECEDENCE EXAMPLES
PARSE_AS:
  A⊕B→C::"(A⊕B)→C"         // synthesis binds tighter
  A⇌B→C::"(A⇌B)→C"         // tension binds tighter
  A→B→C::"A→(B→C)"         // flow is right-associative
  [A∧B∧C]::"[(A∧B)∧C]"       // constraints chain left

===END===
