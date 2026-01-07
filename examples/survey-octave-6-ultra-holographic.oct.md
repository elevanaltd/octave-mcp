===HOLOGRAPHIC_SURVEY===
META:
  TYPE::REFERENCE_INDEX
  VERSION::"6.0"
  SOURCE::survey-original-raw.oct.md
  COMPRESSION_TIER::ULTRA
  COMPRESSION_RATIO::~50%
  ORIGINAL_TOKENS::5600
  COMPRESSED_TOKENS::2800
  LOSS_PROFILE::narrative⊕reasoning|facts∧structure_preserved
  USE_CASE::embedding_generation,dense_indexing,lookup_tables,reference_only

  CONTRACT::HOLOGRAPHIC[
    SELF_VALIDATION::JIT_COMPILE
    GENERATIVE_CONSTRAINT::GRAMMAR_COMPILE[
      SECTION::SYSTEM_COMPARISON_FACT_TABLE REQUIRED::true
      SECTION::JSON_SCHEMA REQUIRED::true
      SECTION::OPENAPI REQUIRED::true
      SECTION::PROTOBUF REQUIRED::true
      SECTION::AVRO REQUIRED::true
      SECTION::CUE REQUIRED::true
      SECTION::JSON_LD REQUIRED::true
      SECTION::SHACL REQUIRED::true
      SECTION::ZOD REQUIRED::true
      SECTION::PYDANTIC REQUIRED::true
      SECTION::GUIDANCE REQUIRED::true
      SECTION::OUTLINES REQUIRED::true
      SECTION::GUARDRAILS REQUIRED::true
      SECTION::FUNCTION_CALLING REQUIRED::true
      SECTION::ATTRIBUTE_GRAMMARS REQUIRED::true
      SECTION::BDD_GHERKIN REQUIRED::true
      SECTION::COMPARATIVE_TEACH REQUIRED::true
      SECTION::COMPARATIVE_VALIDATE REQUIRED::true
      SECTION::COMPARATIVE_EXTRACT REQUIRED::true
      SECTION::HOLOGRAPHIC_NOVELTY REQUIRED::true
      SECTION::CLOSEST_ANALOGS REQUIRED::true
      SECTION::FAILURE_MODES REQUIRED::true
      SECTION::MINIMAL_EXECUTION REQUIRED::true
      SECTION::CONCLUSION REQUIRED::true
    ]
    LIVING_EVOLUTION::FORWARD_COMPATIBLE[
      DEPRECATION_WARNING::true
    ]
  ]

§1::SYSTEM_COMPARISON_FACT_TABLE
  SYSTEMS::[JSON_Schema,OpenAPI,Protobuf,Avro,CUE,JSON-LD,SHACL,Zod,Pydantic,Guidance,Outlines,Guardrails,Function_Calling,Attribute_Grammars,BDD_Gherkin]

§2::JSON_SCHEMA
  VALIDATES::[structure,types,ranges,patterns,formats]
  TEACHES::examples_in_docs|descriptions
  EXTRACTS::none|requires_external_code
  GAP::schema_separate_from_examples|no_runtime_binding

§3::OPENAPI
  VALIDATES::[structure,compliance]
  TEACHES::examples_in_docs
  EXTRACTS::codegen[generates_stubs]
  GAP::not_unified_executable|no_routing_semantics_standard

§4::PROTOBUF
  VALIDATES::[types,required,defaults]
  TEACHES::minimal|formal_not_legible
  EXTRACTS::codegen[native_bindings]
  GAP::no_inline_examples|no_execution_intent

§5::AVRO
  VALIDATES::[types,required,defaults]
  TEACHES::minimal|schema_with_data
  EXTRACTS::codegen|parse_to_objects
  GAP::no_execution_instructions|schema_evolution_only

§6::CUE
  VALIDATES::[types,ranges,patterns,enums,defaults]
  TEACHES::examples_inline|unified_schema_data
  EXTRACTS::partial|computes_output|no_side_effects_by_default
  STRENGTH::closest_non_LLM_analog
  GAP::no_execution_binding|learning_curve

§7::JSON_LD
  VALIDATES::via_SHACL[cardinalities,types,conditions,custom_code]
  TEACHES::semantic_context|not_format_examples
  EXTRACTS::semantic_categorization|manual_routing
  GAP::heavyweight|not_LLM_legible|niche_adoption

§8::SHACL
  VALIDATES::very_strong[cardinalities,types,complex_conditions,SPARQL]
  TEACHES::limited|RDF_graphs_not_readable
  EXTRACTS::pass_fail|categorization
  GAP::machine-oriented|separate_shapes|no_inline_examples

§9::ZOD
  VALIDATES::[types,ranges,patterns,enums]
  TEACHES::implicit|code_embedded
  EXTRACTS::native_objects
  GAP::developer-only|no_semantic_actions|manual_routing

§10::PYDANTIC
  VALIDATES::[types,constraints,custom_validators]
  TEACHES::field_metadata|examples_in_docs
  EXTRACTS::typed_objects|framework_integrated
  GAP::code_embedded|separate_examples|not_standalone_artifact

§11::GUIDANCE
  VALIDATES::[real_time|regex,types,choices]
  TEACHES::inline_examples|explicit_format
  EXTRACTS::captured_variables
  GAP::requires_coding|template_heavy|not_static

§12::OUTLINES
  VALIDATES::[guaranteed|grammar,regex_filtering]
  TEACHES::implicit|library_infers_from_schema
  EXTRACTS::automatic|Python_objects
  GAP::code_embedded|limited_nesting|Pydantic_tied

§13::GUARDRAILS
  VALIDATES::[schema,validators,semantic_checks,auto_correction]
  TEACHES::strong|YAML_spec,few_shot_examples
  EXTRACTS::parsed_objects|Python_dict_or_Pydantic
  GAP::verbose_YAML|after_fact_validation|retry_latency

§14::FUNCTION_CALLING
  VALIDATES::[structural|OpenAI_enforces_JSON_schema]
  TEACHES::schema_types_descriptions
  EXTRACTS::routing_implicit|function_call_direct
  GAP::no_explicit_examples|JSON_only|token_cost|narrow_use_case

§15::ATTRIBUTE_GRAMMARS
  VALIDATES::[strict|parsing_enforces_format]
  TEACHES::minimal|examples_separate
  EXTRACTS::semantic_actions|can_trigger_code
  STRENGTH::covers_all_three_axes
  GAP::verbose|specialized_skill|poor_error_messages|maintenance

§16::BDD_GHERKIN
  VALIDATES::via_tests|pass_fail_execution
  TEACHES::strong|readable_scenarios
  EXTRACTS::step_definitions|pattern_to_code
  GAP::test_specific|verbose|not_compact|ambiguity_risk

§17::COMPARATIVE_TEACH
  RANKING::strong>:[CUE,BDD,Guidance,Guardrails,JSON_LD]|moderate::[OpenAPI,Pydantic,Function_Calling]|weak::[Protobuf,JSON_Schema,Zod,Attribute_Grammars,Outlines]

§18::COMPARATIVE_VALIDATE
  RANKING::strong::[JSON_Schema,Pydantic,Protobuf,CUE,SHACL,Guardrails]|moderate::[OpenAPI,BDD,Guidance,Outlines]|weak::[JSON-LD,Function_Calling]

§19::COMPARATIVE_EXTRACT
  RANKING::strong::[Function_Calling,Guidance,BDD,Attribute_Grammars,Guardrails]|moderate::[Protobuf,Outlines,Pydantic_FastAPI]|weak::[CUE,JSON_Schema,OpenAPI,Zod,JSON-LD]

§20::HOLOGRAPHIC_NOVELTY
  UNIQUE::[example_rule_action_in_one_line,LLM_legible_syntax,self_referential_bootstrap]
  SYNTHESIS::[declarative_rigor,pedagogical_examples,spec_execution_binding]
  GAP::no_existing_system_unifies_all_three_seamlessly

§21::CLOSEST_ANALOGS
  SYSTEMS::[Guardrails,Outlines,CUE]

§22::FAILURE_MODES
  COMPLEXITY::balance_expressiveness_vs_simplicity|avoid_Turing_completeness
  DRIFT::spec_code_must_stay_unified|separate_specs_diverge
  MISINTERPRETATION::LLM_might_ignore_or_misunderstand|need_few_shot
  OVER_RELIANCE::models_not_100_percent_obedient|need_validator_layer
  PERFORMANCE::large_specs_token_costly|selective_injection_needed
  ADOPTION::wheel_reinvention_concern|need_clear_benefit

§23::MINIMAL_EXECUTION
  PARSER::read_holographic_lines→extract_[name,example,constraint,target]
  VALIDATOR::convert_spec→validation_rules|map_to_JSON_Schema_or_Pydantic
  TEACHING::include_spec_in_prompt|few_shot_examples
  ROUTING::dispatch_fields_to_targets|configuration_mapping

§24::CONCLUSION
  STATUS::meaningful_synthesis_not_reinvention
  COMPONENTS::schema_language_examples_execution_hooks_all_exist
  INTEGRATION::orchestrates_via_single_source
  BENEFIT::one_document_provides_documentation_validation_automation
  MARKET::gap_not_filled_by_existing_single_source
  CHALLENGE::keep_simple_not_burdensome|implement_robustly

===END===
