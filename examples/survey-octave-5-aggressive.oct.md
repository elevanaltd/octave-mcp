===HOLOGRAPHIC_SURVEY===
META:
  TYPE::RESEARCH_SUMMARY
  VERSION::"5.1.0"
  SOURCE::survey-original-raw.oct.md
  COMPRESSION_TIER::AGGRESSIVE
  COMPRESSION_RATIO::~70%
  ORIGINAL_TOKENS::5600
  COMPRESSED_TOKENS::~1800
  LOSS_PROFILE::explanatory_depth⊕execution_narratives|core_thesis∧landscape_preserved
  NARRATIVE_DEPTH::compressed[execution_tradeoffs_implicit,lineage_omitted,edge_cases_summarized]

---

NOTE::AGGRESSIVE tier: preserves comparative conclusions and system coverage;
      explanatory_depth, historical_context, execution_tradeoff_narratives are intentionally compressed.
      For LOSSLESS or CONSERVATIVE tiers, see OCTAVE_DATA.§1b.COMPRESSION_TIERS

// Holographic Document Language: Survey Related Systems
// Compressed using OCTAVE 5.1.0 rules (core + data profiles)

OVERVIEW::
  CONCEPT::single declarative spec→teaches_format⊕validates_rules⊕routes_data
  EXAMPLE::ID::[`sess_123`∧REQ→INDEXER]
  BENEFIT::LLM-legible⊕machine-executable⊕single-source_truth
  SURVEY_AXIS::[teach_format,validate_structure,extract_routing]

SCHEMA_LANGUAGES:
  JSON_SCHEMA:
    SOLVES::[format_grammar,validation,structure_definition]
    TEACH::annotations[title,description,examples]|indirect
    VALIDATE::strong[types,required,ranges,patterns]
    EXTRACT::none[requires_external_code]
    GAP::schema∨examples_separate|no_runtime_binding|no_routing

  OPENAPI:
    SOLVES::[API_contracts,endpoints,request-response]
    TEACH::moderate[examples∨descriptions_in_docs]
    VALIDATE::via_schema[requests,responses,compliance]
    EXTRACT::codegen[generates_stubs∨SDK]
    GAP::no_execution_semantics|→INDEXER_not_standard|spec≠execution_plan

  PROTOBUF_AVRO:
    SOLVES::[binary_serialization,cross-language_data]
    TEACH::minimal[no_inline_examples|formal_not_LLM-legible]
    VALIDATE::strong[type_checking,required_fields,defaults]
    EXTRACT::via_codegen[native_bindings]
    GAP::no_execution_intent|schema≠action|codegen-heavy

UNIFIED_LANGUAGES:
  CUE:
    SOLVES::[unify_schema⊕data⊕constraints]
    TEACH::strong[examples_inline|self-demonstrating]
    VALIDATE::extensive[optional,ranges,regex,enums,defaults]
    EXTRACT::partial[executes_queries|no_external_routing]
    STRENGTH::teaches⊕validates_in_one_place
    GAP::no_inherent_routing|complexity→learning_curve

  JSON_LD_SHACL:
    SOLVES::[semantic_annotation,RDF_constraints]
    TEACH::semantic[ontology_mapping|not_format_examples]
    VALIDATE::very_strong[cardinality,types,conditions,SPARQL]
    EXTRACT::semantic[categorize_validate|not_imperative]
    GAP::heavyweight|not_LLM-legible|separate_shapes|niche_adoption

CODE_LIBRARIES:
  ZOD:
    SOLVES::[runtime_schema_validation]
    TEACH::implicit[developer_intuition|separate_tests]
    VALIDATE::strong[types,ranges,regex,enums]
    EXTRACT::native_objects[typed_JS_objects]
    GAP::code-embedded|no_semantic_actions|manual_routing

  PYDANTIC:
    SOLVES::[data_parsing⊕validation_via_types]
    TEACH::moderate[Field(example=)|separate_docs]
    VALIDATE::strong[types,constraints,custom_validators]
    EXTRACT::framework_coupled[FastAPI_integration]
    GAP::code-embedded|no_unified_spec|framework-dependent

GRAMMARS_EXECUTABLE:
  ATTRIBUTE_GRAMMARS:
    SOLVES::[syntax_validation⊕semantic_execution]
    TEACH::implicit[examples_separate|not_self-evident]
    VALIDATE::strict[parse→only_conforming_valid]
    EXTRACT::semantic_actions[can_trigger_code]
    STRENGTH::covers_all_three_axes
    GAP::verbose|specialized_skill|poor_error_messages|maintenance_burden

  BDD_GHERKIN:
    SOLVES::[behavior_examples⊕executable_tests]
    TEACH::strong[readable_scenarios|natural_language]
    VALIDATE::via_tests[pass-fail_enforcement]
    EXTRACT::step_definitions[pattern→code_binding]
    GAP::test-specific|verbose|not_compact|ambiguity_risk

LLM_STRUCTURED_OUTPUT:
  FUNCTION_CALLING:
    SOLVES::[structured_JSON_generation⊕function_routing]
    TEACH::via_schema[types,descriptions,fields→inferred_format]
    VALIDATE::structural[OpenAI_enforces_JSON|schema_compliant]
    EXTRACT::routing_implicit[function_name⊕args]
    STRENGTH::built-in_execution|schema→action
    GAP::minimal_examples|JSON-only|no_long_form|token_cost

  GUIDANCE:
    SOLVES::[template_prompts⊕token-level_steering]
    TEACH::strong[inline_examples⊕explicit_format]
    VALIDATE::real-time[regex∨type∨choice_enforcement]
    EXTRACT::immediate[captured→variables]
    STRENGTH::guarantees_structure|during_generation
    GAP::not_declarative|requires_coding|template-heavy|model-specific

  OUTLINES:
    SOLVES::[simplified_structured_generation]
    TEACH::implicit[library_infers_from_schema]
    VALIDATE::guaranteed[grammar∨regex_filtering]
    EXTRACT::automatic[Pydantic_parsing]
    STRENGTH::high-level|abstracts_complexity
    GAP::code-embedded|not_static_artifact|limited_nesting

  GUARDRAILS:
    SOLVES::[validation⊕correction⊕schema_compliance]
    TEACH::via_RAIL_spec[YAML_format|examples_in_doc]
    VALIDATE::comprehensive[schema∧validators∧semantic_checks]
    EXTRACT::parsed_objects[Python_dict∨Pydantic]
    STRENGTH::single_source|retry_loop|after-fact_correction
    GAP::verbose_YAML|no_token_steering|content_validation_separate

COMPARATIVE_MATRIX:
  TEACH::
    strong::[CUE,BDD,Guidance,Guardrails,JSON_LD_semantic]
    moderate::[OpenAPI,Pydantic,Function_Calling]
    weak::[Protobuf,JSON_Schema,Zod,Attribute_Grammars,Outlines]

  VALIDATE::
    strong::[JSON_Schema,Pydantic,Protobuf,CUE,SHACL,Guardrails]
    moderate::[OpenAPI,BDD,Guidance,Outlines]
    weak::[JSON-LD,Function_Calling]

  EXTRACT::
    strong::[Function_Calling,Guidance,BDD,Attribute_Grammars,Guardrails]
    moderate::[Protobuf,Outlines,Pydantic⊕FastAPI]
    weak::[CUE,JSON_Schema,OpenAPI,Zod,JSON-LD]

NOVELTY::
  HOLOGRAPHIC_APPROACH::
    UNIQUE::[example∧rule→action_in_one_line|LLM-legible_syntax|self-referential_bootstrap]
    SYNTHESIS::combines[declarative_rigor+pedagogical_examples+spec→execution_binding]
    GAP::no_existing_system_unifies_all_three_seamlessly
    ANALOG_CLOSEST::[Guardrails⊕Outlines+CUE]

FAILURE_MODES:
  COMPLEXITY_RISK::balance_expressiveness↔simplicity|avoid_Turing-completeness
  DRIFT_RISK::must_treat_spec∧code_as_unified_source|cultural_discipline_required
  LLM_MISINTERPRETATION::need_few-shot⊕meta-spec_explanation
  OVER_RELIANCE::require_validation_layer⊕fallback_logic
  PERFORMANCE::large_specs→selective_injection|two-pass_validation|fine-tuning

MINIMAL_EXECUTION_LAYER:
  PARSER::spec_text→[field_name,example,constraint,target]|simple_PEG∨string_parsing
  VALIDATOR::map_REQ→JSON_Schema|REGEX→pattern|ENUM→set|compile_to_existing_tools
  LLM_TEACHING::[include_spec_in_prompt|few-shot_examples|system_message]
  ROUTING::map_TARGET_labels→handlers|function∨API_calls|plugin_architecture

CONCLUSION::
  GAP_FILLED::documents_unified_for[humans_read⊕LLMs_generate⊕machines_execute]
  RISK::wheel_reinvention_unless_synthesis_is_seamless⊕clear_benefit
  SOLUTION::leverage_existing[JSON_Schema_for_validation,function_calling_for_generation,routing_config]
  FEASIBILITY::meaningful_gap_fills_market|achievable_via_pragmatic_architecture

===END===
