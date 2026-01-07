===OCTAVE_MCP_ARCHITECTURE===
META:
  TYPE::SPECIFICATION
  VERSION::"2.0.0"
  STATUS::APPROVED
  IMPLEMENTATION::PARTIAL
  DATE::"2026-01-06"
  OCTAVE_VERSION::"6.0.0"
  PURPOSE::MCP_server_architecture_for_OCTAVE_productization+generative_holographic_contracts
  IMPLEMENTATION_NOTES::"MCP tools (octave_validate, octave_write, octave_eject), canonicalization rules, and projection modes IMPLEMENTED. Constraint validation, repair logic (fix=true), target routing, and schema policy PLANNED. v2.0: Generative Constraints (JIT Grammar Compilation) and Hermetic Anchoring added."
  IMPLEMENTATION_REF::[src/octave_mcp/mcp/validate.py,src/octave_mcp/mcp/write.py,src/octave_mcp/mcp/eject.py,src/octave_mcp/core/lexer.py,src/octave_mcp/core/projector.py,src/octave_mcp/core/hydrator.py]
  CRITICAL_GAPS::[constraint_validation,target_routing,repair_logic,builtin_schema_loading,error_message_formatting,jit_grammar_compilation,hermetic_standard_resolution]

---

// OCTAVE MCP: A deterministic semantic ingress/egress layer for LLM systems
// with explicit loss control and schema-bound execution constraints.

§1::PHILOSOPHY

CORE_PRINCIPLE::one_language_disciplined_tolerance

DEFINITION::[
  ONE_LANGUAGE::OCTAVE[single_spec,single_canonical_form],
  DISCIPLINED_TOLERANCE::finite_rewrite_system[not_inference],
  CONTROL_PLANE::documents_drive_behavior[not_just_formatting]
]

WHAT_THIS_IS::[
  semantic_control_surface,
  deterministic_canonicalization,
  schema_bound_validation,
  explicit_loss_tracking,
  auditable_transformation
]

WHAT_THIS_IS_NOT::[
  babel_fish[accept_anything_guess_intent],
  semantic_inference_engine,
  two_separate_languages,
  opinionated_assistant
]

LITMUS_TEST::"If you removed the LLM and replaced it with a dumb text emitter, would this system still add value?"→YES

§2::TWO_TOLERANCES

STRICT_MODE[canonical]:
  PURPOSE::storage_and_execution
  TOLERANCE::zero
  OPERATORS::unicode[→,⊕,⧺,⇌,∨,∧,§]
  ENVELOPE::explicit[===NAME===...===END===]
  WHITESPACE::no_spaces_around_::
  QUOTING::explicit_where_required

LENIENT_MODE[authoring]:
  PURPOSE::human_and_LLM_input
  TOLERANCE::syntactic_only
  OPERATORS::ascii_aliases_accepted[normalized_to_unicode]
  ENVELOPE::inferred_for_single_doc[always_emitted_canonical]
  WHITESPACE::flexible_around_::[normalized_away]
  QUOTING::auto_inserted_where_safe

CRITICAL_BOUNDARY::tolerance_is_syntactic_not_semantic

§3::LENIENT_GRAMMAR

ACCEPTED:
  SCHEMA_SELECTOR::@<schema_id>[@<version>][required_if_no_envelope]
  ENVELOPE::===<NAME>===[optional_if_schema_selector]
  ASSIGNMENT::KEY::value[double_colon_required]
  FLEXIBLE_ASSIGNMENT::KEY :: value[whitespace_tolerated]
  ASCII_FLOW::A -> B[normalized_to→]
  ASCII_SYNTHESIS::A + B[normalized_to⊕]
  ASCII_CONCAT::A ~ B[normalized_to⧺]
  ASCII_TENSION::A vs B[normalized_to⇌,requires_word_boundaries]
  ASCII_ALTERNATIVE::A | B[normalized_to∨]
  ASCII_CONSTRAINT::A & B[normalized_to∧]
  ASCII_TARGET_SELECTOR::#TARGET[normalized_to§TARGET]
  ASCII_FLOW_TARGET::A -> #TARGET[normalized_to→§TARGET]

REJECTED[errors_not_repairs]:
  SINGLE_COLON::key: value[ERROR::ambiguous_with_block_operator]
  EQUALS::key = value[ERROR::not_OCTAVE_syntax]
  TABS::any_tab_character[ERROR::indent_must_be_2_spaces]
  MISSING_SCHEMA::no_@selector_and_no_envelope[ERROR::type_unknown]

§4::CANONICALIZATION_RULES

// Finite, deterministic, spec'd rewrites. Not inference.

RULE_TABLE:
  ID::INPUT::OUTPUT::SEMANTICS_CHANGE
  R01::"->"::→::no
  R02::"+"::⊕::no
  R03::"~"::⧺::no
  R04::"vs"[word_bounded]::⇌::no
  R05::"|"::∨::no
  R06::"&"::∧::no
  R07::"KEY :: value"::"KEY::value"::no[whitespace_removal]
  R08::bare_string_with_spaces::"quoted string"::no[quote_insertion]
  R09::missing_envelope[single_doc]::===INFERRED===...===END===::no
  R10::NFC_normalization::canonical_unicode::no

PROPERTIES:
  IDEMPOTENT::canon(canon(x))==canon(x)
  DETERMINISTIC::same_input→same_output_always
  TOTAL::every_valid_lenient_input_has_exactly_one_canonical_form

§5::REPAIR_CLASSIFICATION

// The keystone: every transformation is classified and logged.

TIER_NORMALIZATION[always_on]:
  SCOPE::syntactic_and_lexical_only
  SEMANTICS::preserved
  LOGGING::included_in_repairs[]
  EXAMPLES::[
    ascii_to_unicode,
    whitespace_normalization,
    quote_insertion,
    envelope_completion
  ]

TIER_REPAIR[opt_in_via_fix=true]:
  SCOPE::schema_bounded_value_transforms
  SEMANTICS::may_change_value[not_structure]
  LOGGING::required_with_before_after
  REQUIRES::unique_schema_match
  EXAMPLES::[
    enum_casefold["active"→ACTIVE,only_if_unique_match],
    type_coercion["42"→42,if_schema_says_NUMBER]
  ]

TIER_FORBIDDEN[never_automatic]:
  SCOPE::semantic_intent_and_structure
  SEMANTICS::would_change_meaning
  RATIONALE::author_intent_unknown
  EXAMPLES::[
    target_inference[never_guess→§TARGET],
    field_insertion[never_add_missing_REQ_fields],
    structure_repair[never_reparent_blocks],
    semantic_rewrite[never_change_meaning],
    schema_inference[never_guess_document_type],
    routing_guess[never_invent_destinations]
  ]

FORBIDDEN_RATIONALE::[
  "Schema constraints tell you what values are allowed and what shape is required",
  "Schema constraints cannot tell you which missing field the author intended",
  "Schema constraints cannot tell you whether a target was malicious or mistaken",
  "Schema constraints cannot tell you whether dropping/adding a field changes downstream meaning",
  "Autocorrect is safe for syntax, bounded for values, dangerous for intent"
]

§6::REPAIR_LOG_FORMAT

// Mandatory. No silent drift.

STRUCTURE:
  REPAIRS::[
    {
      RULE_ID::"R01",
      BEFORE::"->" ,
      AFTER::"→",
      TIER::NORMALIZATION,
      SAFE::true,
      SEMANTICS_CHANGED::false
    }
  ]

REQUIREMENTS::[
  every_change_logged,
  tier_classification_required,
  before_after_snippets_required,
  safe_classification_required
]

§7::MCP_TOOL_SURFACE

// Three tools: validate, write, eject. Orthogonal concerns.

TOOL_VALIDATE:
  NAME::octave_validate
  PURPOSE::schema_validation_and_parsing_of_OCTAVE_content

  PARAMETERS:
    CONTENT::["OCTAVE content to validate"∧OPT∧mutually_exclusive_with_FILE_PATH]
    FILE_PATH::["path to OCTAVE file to validate"∧OPT∧mutually_exclusive_with_CONTENT]
    SCHEMA::["DECISION_LOG"∧REQ∧validates_against_schema_repo]
    FIX::[false∧OPT∧BOOLEAN→apply_repairs_to_canonical_output]

  RETURNS:
    CANONICAL::["===DOC===\n..."∧REQ→validated_OCTAVE]
    VALID::[true∧REQ∧BOOLEAN→whether_document_passed_validation]
    VALIDATION_ERRORS::[[...]∧REQ→schema_violations_found]
    REPAIR_LOG::[[...]∧REQ→transformation_log_always_present]

  PIPELINE::[PREPARSE→PARSE→NORMALIZE→VALIDATE→REPAIR(if_fix)→VALIDATE]

TOOL_WRITE:
  NAME::octave_write
  PURPOSE::unified_file_creation_and_modification

  PARAMETERS:
    TARGET_PATH::["file path to write to"∧REQ]
    CONTENT::["full content for new files or overwrites"∧OPT∧mutually_exclusive_with_CHANGES]
    CHANGES::["dictionary of field updates for existing files"∧OPT∧mutually_exclusive_with_CONTENT]
    SCHEMA::["DECISION_LOG"∧OPT∧for_validation]
    MUTATIONS::["META field overrides"∧OPT∧applies_to_both_modes]
    BASE_HASH::["SHA-256 hash for consistency check (CAS)"∧OPT]

  RETURNS:
    SUCCESS::[true∧REQ∧BOOLEAN→whether_write_succeeded]
    PATH::["absolute path to written file"∧REQ]
    DIFF::["summary of changes made"∧REQ]
    CANONICAL::["final canonical content"∧REQ]

TOOL_EJECT:
  NAME::octave_eject
  PURPOSE::format_projection_with_declared_loss_tiers

  PARAMETERS:
    CONTENT::["canonical OCTAVE"∧OPT→null_for_template_generation]
    SCHEMA::["DECISION_LOG"∧REQ∧for_validation_or_template]
    MODE::["authoring"∧OPT∧ENUM[canonical,authoring,executive,developer]]
    FORMAT::["octave"∧OPT∧ENUM[octave,json,yaml,markdown]]

  RETURNS:
    OUTPUT::["@DECISION_LOG\n..."∧REQ→formatted_content]
    LOSSY::[true∧REQ∧BOOLEAN→true_if_mode_discards_fields]
    FIELDS_OMITTED::[[...]∧OPT→list_of_dropped_fields_if_lossy]

§8::ERROR_MESSAGES

// Educational, not just informative. Defends against forbidden repair pressure.

PATTERN::ERROR_ID::MESSAGE::RATIONALE

ERRORS:
  E001::"Single colon assignment not allowed. Use KEY::value (double colon)."::
    "OCTAVE uses :: for assignment because : is the block operator. This prevents ambiguity."

  E002::"Schema selector required. Add @SCHEMA_NAME or explicit ===ENVELOPE===."::
    "OCTAVE cannot infer document type. Schema selection must be explicit for safety."

  E003::"Cannot auto-fill missing required field '{field}'. Author must provide value."::
    "Required fields represent author intent. The system cannot guess what you meant."

  E004::"Cannot infer routing target. Specify →§TARGET explicitly."::
    "Routing determines where data flows. Guessing targets would violate trust boundaries."

  E005::"Tabs not allowed. Use 2 spaces for indentation."::
    "OCTAVE requires consistent indentation for deterministic hierarchy parsing."

  E006::"Ambiguous enum match for '{value}'. Multiple options: {options}. Be explicit."::
    "Schema-driven repair only works when there's exactly one valid correction."

§9::PROJECTION_MODES

// eject() can return different views for different stakeholders.

MODE_CANONICAL:
  RETURNS::full_document_in_strict_OCTAVE
  LOSSY::false
  USE::storage_diffing_hashing

MODE_AUTHORING:
  RETURNS::lenient_format_for_editing
  LOSSY::false[structure_preserved]
  USE::human_or_LLM_editing

MODE_EXECUTIVE:
  RETURNS::STATUS_RISKS_DECISIONS_only
  LOSSY::true
  FIELDS_OMITTED::[TESTS,CI,DEPS,technical_detail]
  USE::high_level_review

MODE_DEVELOPER:
  RETURNS::TESTS_CI_DEPS_technical_fields
  LOSSY::true
  FIELDS_OMITTED::[executive_summary_fields]
  USE::implementation_focus

MERGE_BACK::DEFERRED[requires_patch_protocol_not_in_v1]

§10::SCOPE_EXCLUSIONS

// Intentionally not building. Restraint is a feature.

EXCLUDED:
  SEMANTIC_INFERENCE::never_guess_meaning
  AUTO_FILL_INTENT::never_invent_missing_fields
  PROJECTION_MERGE::deferred[big_product_on_its_own]
  ROUTING_GUESS::never_invent_targets
  BABEL_FISH::never_accept_anything

RATIONALE::[
  determinism,
  trust_boundaries,
  explainability,
  testability
]

§11::IMPLEMENTATION_PHASES

PHASE_1[core_library]:
  LANGUAGE::Python
  COMPONENTS::[
    lenient_parser_with_normalization,
    canonical_emitter,
    validator_with_schema_support,
    repair_log_generation
  ]
  CLI::[octave ingest,octave eject,octave validate]
  DELIVERABLE::pip_installable_package

PHASE_2[mcp_server]:
  COMPONENTS::[
    wrap_library_as_MCP_tools,
    octave_validate_tool,
    octave_write_tool,
    octave_eject_tool,
    schema_repository[builtin+custom]
  ]
  DELIVERABLE::MCP_server_package

PHASE_3[ecosystem]:
  COMPONENTS::[
    vscode_extension[syntax_highlighting,inline_validation],
    github_action[octave-validate],
    npm_package[@octave/types]
  ]
  DELIVERABLE::ecosystem_tools

§12::VALIDATION_CRITERIA

PROPERTIES_TO_TEST::[
  canonicalize_is_idempotent,
  parse_AST_is_unique[no_ambiguity],
  lenient_round_trip[ingest(eject(doc,canonical))==doc],
  fix_true_never_adds_new_fields,
  forbidden_repairs_always_error,
  repair_log_always_present,
  unknown_fields_policy_enforced
]

TEST_VECTORS_REQUIRED::[
  lenient_inputs_with_ascii_aliases,
  whitespace_variations,
  enum_casefold_unique_vs_ambiguous,
  missing_envelope_single_doc,
  forbidden_repair_attempts,
  projection_mode_field_omission
]

§12A::UNKNOWN_FIELDS_POLICY

POLICY::[
  STRICT_MODE::reject_unknown_fields[error_with_path],
  LENIENT_MODE::warn_unknown_fields[logged_only]
]

SCOPE::initial_META_only[v1];_document_body_in_v1.1

ERROR::
  E007::"Unknown field '{field}' not allowed in STRICT mode."::
    "Avoids schema surface drift compromising downstream contracts."

§13::SUMMARY

ARCHITECTURE::"One language, disciplined tolerance"

KEY_PROPERTIES::[
  deterministic_not_probabilistic,
  auditable_not_silent,
  syntactic_tolerance_not_semantic_inference,
  control_plane_not_formatter
]

PRODUCT_STATEMENT::[
  "OCTAVE is a semantic compression format for LLM communication.",
  "The OCTAVE MCP server accepts lenient input and always returns canonical OCTAVE.",
  "Lenience is deterministic normalization, not semantic inference.",
  "Every repair is logged; nothing changes silently.",
  "Schema-driven validation ensures structural correctness.",
  "Authors provide meaning; tools provide formatting."
]

§14::VERSIONING_AND_COMPATIBILITY

POLICY::semver

SURFACES::[
  SPEC_VERSION::"2.0.0"[breaking_changes_only_on_major],
  OCTAVE_VERSION::"6.0.0"[grammar_features+generative_constraints+hermetic_anchoring],
  VALIDATOR_DEFAULT::"6.0.0"[full_v6_feature_support],
  VALIDATOR_FLAGS::["--version 6.0.0"→enable_new_rules]
]

COMPATIBILITY_MATRIX::[
  lenient_ascii_aliases::stable_across_6.x,
  canonicalization_rules::stable_across_2.x,
  forbidden_repairs::strict_no_change,
  generative_constraints::new_in_6.0,
  hermetic_anchoring::new_in_6.0
]

LEGACY_SUPPORT::[
  v5.x_documents::parsed_correctly[backward_compatible_grammar],
  v5.x_schemas::supported_via_compatibility_layer,
  migration_path::automated_upgrade_available
]

MIGRATION::[
  add_tests_for_6.0.0_rules,
  bump_default_once_tests_green,
  publish_release_notes,
  document_v5_to_v6_upgrade_path
]

§15::HESTAI_INTEGRATION

ALIGNMENT::[
  DUAL_LAYER_CONTEXT::compatible[documents_in_.hestai/context, sessions_in_.hestai/sessions],
  SINGLE_WRITER_RULE::supported_via_MCP_tools[use_document_submit|context_update_when_embedded],
  ODYSSEAN_ANCHOR::recommended_precondition[bind_agent_identity_before_ingest]
]

MAPPING::[
  OCTAVE_MCP::octave_validate|octave_write|octave_eject,
  HESTAI_MCP::document_submit|context_update
]

NOTE::"When embedded in HestAI-MCP, map tool names to the HestAI equivalents without altering semantics."

§16::GENERATIVE_CONSTRAINTS

// v2.0: JIT Grammar Compilation from META.CONTRACT→GBNF/Outlines

PRINCIPLE::"Validation precedes generation - impossible to generate invalid syntax"

MECHANISM:
  INPUT::META.CONTRACT∧META.GRAMMAR[document_schema]
  COMPILATION::JIT_COMPILER[OCTAVE→GBNF∨Outlines∨JSON_Schema]
  OUTPUT::constrained_grammar[llama.cpp,vLLM,Outlines]

SECURITY::HERMETIC[no_network_fetch_in_hot_path]

PHASES::[
  PARSE::extract_CONTRACT_and_GRAMMAR_from_META,
  COMPILE::transform_constraints_to_target_grammar,
  GENERATE::apply_grammar_to_inference_engine,
  VALIDATE::post_generation_hash_verification
]

BENEFITS::[
  impossible_to_generate_invalid_syntax,
  no_post_hoc_validation_theater,
  deterministic_output_structure,
  self_describing_documents
]

§17::HERMETIC_ANCHORING

// v2.0: Network-free standard resolution with cryptographic guarantees

PRINCIPLE::"Frozen Standards - no runtime dependency resolution"

MODES:
  DEV::standard_latest[local_filesystem_only,no_network]
  PROD::standard_frozen@sha256[immutable_pinned_resources]

RESOLUTION:
  CACHE::local_cache[~/.octave/standards/]
  PINNED::frozen@sha256_abc123[verified_against_hash]
  LATEST::latest[local_toolchain_defaults,dev_only]

FORBIDDEN::[
  network_fetch_in_hot_path,
  dynamic_registry_resolution,
  runtime_schema_download,
  unverified_remote_resources
]

IMPLEMENTATION::streamlined_hydrator[remove_living_scrolls_complexity]

§18::ORCHESTRA_MAP_INTEROP

PURPOSE::"Concepts claim Code via imports"

OPTIONAL_FIELDS::[
  CLAIMS::["import paths or module IDs claimed by this spec"],
  STALENESS_RULE::"LastCommit(Spec) < LastCommit(Impl) == STALE"
]

OUTPUTS::[
  GRAPH::edges[concept→code],
  STALE_MODULES::[[...]]
]

INTEGRATION::"Expose GRAPH via eject(mode=developer, format=json) for CI consumption."

===END===
