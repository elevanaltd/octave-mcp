===OCTAVE_DATA===
META:
  TYPE::LLM_PROFILE
  VERSION::"6.0.0"
  STATUS::APPROVED

  TOKENS::"~75"
  REQUIRES::octave-core-spec
  PURPOSE::compression_and_instances
  TEACHES::[§skills/octave-compression]
  IMPLEMENTATION_NOTES::"Compression tiers (LOSSLESS/CONSERVATIVE/AGGRESSIVE/ULTRA) are specified here for LLM compression behavior. OCTAVE-MCP v0.2.0 removed mcp/ingest.py during 3-tool consolidation; compression tier selection is not implemented in the server. v6: Holographic pattern - META self-declares compression tier for document generation."
  CRITICAL_GAPS::[compression_rules_enforcement,tier_specific_logic,loss_profile_tracking]

  CONTRACT::COMPRESSION_TIER[
    PRINCIPLE::"Documents self-validate compression target",
    MECHANISM::TIER_DECLARATION[COMPRESSION_TIER::LOSSLESS|CONSERVATIVE|AGGRESSIVE|ULTRA],
    BEHAVIOR::LLM_READS_TIER_FROM_META[replaces_text_description]
  ]

---

// OCTAVE DATA: Rules for compressing prose and writing instances. Inject WITH core.

§1::DATA_MODE
PATTERN::KEY::value[L1_simple_assignment]
LEVELS::L1∨L2[never_L3_L4]
BRACKETS::lists∨inline_maps[never_holographic]
FORBIDDEN::["example"∧CONSTRAINT→§TARGET][use_schema_mode]

COMPRESSION_INTENT::
  LOSSLESS_DOMAIN::[facts,numbers,names,operators,boundaries,code]
  LOSSY_DOMAIN::[prose_nuance,historical_context,explanatory_depth,edge_cases]
  ACCEPTABLE_LOSS::["~30%_at_70%_compression",nuance∨narrative_depth]
  UNACCEPTABLE_LOSS::[structural_mischaracterization,analytical_conclusions,core_thesis]

§1b::COMPRESSION_TIERS
TIER::LOSSLESS[target:"100%_fidelity",preserve:everything,drop:none]
  USE::critical_reasoning,legal_documents,safety_analysis,audit_trails
  METHOD::preserve_all_prose,keep_examples,document_tradeoffs
  OUTCOME::original_equals_compressed[except_whitespace∨formatting]

TIER::CONSERVATIVE[target:"85-90%_compression",preserve:explanatory_depth,drop:redundancy]
  USE::research_summaries,design_decisions,technical_analysis
  METHOD::drop_stopwords,compress_examples→inline,keep_tradeoff_narratives,remove_verbose_transitions
  LOSS::"~10-15%"[repetition,some_edge_cases,verbose_phrasing]
  EXAMPLE::5000_tokens→450-700_tokens[keep_depth,lose_redundancy]

TIER::AGGRESSIVE[target:"70%_compression",preserve:core_thesis∧conclusions,drop:nuance∨narrative]
  USE::context_window_scarcity,quick_reference,decision_support
  METHOD::drop_stopwords,compress_narratives→assertions,inline_all_examples,remove_historical_context
  LOSS::"~30%"[explanatory_depth,execution_tradeoff_narratives,edge_case_exploration,lineage]
  EXAMPLE::5600_tokens→1800_tokens[keep_landscape∧conclusions,lose_depth]

TIER::ULTRA[target:"50%_compression",preserve:facts∧structure,drop:all_narrative]
  USE::extreme_scarcity,embedding_generation,dense_reference
  METHOD::bare_assertions,minimal_lists,no_examples,no_prose
  LOSS::"~50%"[almost_all_explanatory_content,some_nuance,tradeoff_reasoning]
  OUTCOME::structure_∧_facts_only,poor_readability

TIER::ULTRA_MYTHIC[target:"60%_compression",preserve:soul∧constraints,drop:narrative]
  USE::agent_binding_passport,identity_transmission,high_density_communication
  METHOD::mythological_atoms,semantic_shorthand,constraint_preservation,list_compression
  REQUIRES::octave-mythology
  LOSS::"~40%"[prose,nuance]
  GAIN::semantic_density,constraint_clarity,identity_preservation
  OUTCOME::highly_compressed_identity_atoms

SELECTION_GUIDE::
  IF[critical_decision→safety_implications]→use_LOSSLESS
  IF[research_artifact→audience_needs_context]→use_CONSERVATIVE
  IF[context_token_budget→loss_acceptable]→use_AGGRESSIVE
  IF[embedding∨indexing∨lookup]→use_ULTRA
  IF[agent_binding∨identity_transfer]→use_ULTRA_MYTHIC

METADATA_REQUIREMENT::
  ALL_COMPRESSED_DOCS::include_TIER_in_META[enables_reader_expectations]
  EXAMPLE::COMPRESSION_TIER::CONSERVATIVE|LOSS_PROFILE::redundancy_removed|NARRATIVE_DEPTH::preserved

§2::COMPRESSION
PRESERVE::[
  numbers[exact],
  names[identifiers,proper_nouns],
  codes[error_codes,IDs,hashes],
  operators[all_OCTAVE_symbols],
  §anchors[targets,sections],
  "quoted"[verbatim_definitions]
]

DROP::[the,a,an,of,for,to,with,that,which,basically,essentially,simply]

REWRITE::verbose_phrase→minimal_token[preserve_meaning]

§3::ABBREVIATIONS
STATUS::[DONE,WIP,PENDING,BLOCKED,OPEN,CLOSED]
COMMON::[impl,config,env,auth,db,msg,req,res,fn,var,val]
CUSTOM::define_in_document_if_domain_specific

§4::LIST_FORMS
ALTERNATIVES::a∨b∨c[choose_one]
COLLECTION::[a,b,c][all_members]
SEQUENCE::[A→B→C][ordered_steps]
CONCAT::a⧺b⧺c[mechanical_join]
INLINE_MAP::[key::val,key2::val2][dense_key_value_pairs]
EMPTY::[][explicit_empty_state]

§5::ANCHORS
RULE::compress_around_anchors[never_rewrite_anchors]
VERBATIM::[code_blocks,example_strings,"quoted_canonical",numbers,enums]
BOUNDARIES::preserve_distinctions[A⇌B_must_remain_distinct]

§6::FORBIDDEN_REWRITES
NEVER::[
  introduce_absolutes[always,never,must][unless_in_source],
  collapse_boundaries[merge_distinct_concepts],
  strengthen_claims[change_hedging],
  drop_numbers[exact_values_required],
  rewrite_code[verbatim_only]
]

§7::REFERENCE
EXAMPLES::"see octave-core-spec §7 DATA_PATTERN"

WORKING_EXAMPLES::in_examples/post-octave-5-examples/
  LOSSLESS::survey-octave-5-lossless.oct.md
    FIDELITY::"100%"|TOKENS::5600|CONTENT::complete_original_research
  CONSERVATIVE::survey-octave-5-conservative.oct.md
    FIDELITY::"85-90%"|TOKENS::4800|CONTENT::explanatory_depth_preserved
  AGGRESSIVE::survey-octave-5-compressed.oct.md
    FIDELITY::"70%"|TOKENS::1800|CONTENT::analytical_truth_preserved
  ULTRA::survey-octave-5-ultra.oct.md
    FIDELITY::"50%"|TOKENS::2800|CONTENT::facts_and_structure_only

ASSESSMENTS::in_examples/post-octave-5-examples/
  MARKDOWN::assessment-survey.md[human_readable|publication_ready]
  OCTAVE::assessment-survey-llm.oct.md[LLM_optimized|"70%_compressed"|self_referential]

GUIDES::in_examples/post-octave-5-examples/compression-comparison/
  COMPARISON::README.oct.md[tier_selection_matrix|use_case_guide]

TIER_SELECTION::
  IF[one_off_document∨single_reader]→prose_better_than_LOSSLESS
  IF[critical_decision∨legal∨safety]→LOSSLESS_required
  IF[research_artifact∨audience_needs_reasoning]→CONSERVATIVE_recommended
  IF[prompt_injection∨context_window_tight]→AGGRESSIVE_standard
  IF[embedding∨indexing∨lookup]→ULTRA_appropriate

===END===
