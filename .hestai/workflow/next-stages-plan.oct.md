===NEXT_STAGES_PLAN===
// Phase-gated implementation plan synthesized from GitHub issues
// Generated: 2025-12-28 by holistic-orchestrator

META:
  TYPE::"ORCHESTRATION_PLAN"
  VERSION::"1.0.0"
  SESSION::d3ab0393
  SYNTHESIZED_FROM::[
    gh_issues::[25,48,51,52,55,56],
    context::[PROJECT-CONTEXT,PROJECT-ROADMAP,PROJECT-CHECKLIST]
  ]

SUMMARY::"6 open GitHub issues mapped to HestAI phase gates. Critical path: D0 completion -> D1 requirements -> D2 tool consolidation design -> B1 core fixes"

ISSUE_INVENTORY:
  OPEN_ISSUES::6
  MAPPING::[
    GH_56::B1[P0-P4_ingest_blockers,bug],
    GH_55::B1[duplicate_of_56],
    GH_52::B2[debate_transcript_helpers,feature],
    GH_51::D2[tool_consolidation_4_to_3,architecture],
    GH_48::B2[vocabulary_snapshot_hydration,feature],
    GH_25::D1[spec_clarification_arrow_misuse,docs]
  ]

PHASE_STRUCTURE:

  D0::DISCOVERY[current]:
    STATUS::95%_COMPLETE
    REMAINING::[
      create_north_star_document[BLOCKING]
    ]
    GATE::"North star defined with OCTAVE protocol immutables"
    OWNER::requirements-steward

  D1::REQUIREMENTS:
    STATUS::PENDING
    WORK_ITEMS::[
      define_octave_immutables[
        lenient_parsing_as_default,
        canonical_output_as_option,
        round_trip_fidelity_guarantee
      ],
      GH_25::spec_clarification[
        add_SEMANTIC_NEVER_section,
        clarify_arrow_operator_semantics,
        document_correct_mapping_patterns
      ],
      tool_interface_decision[
        resolve_2_vs_3_vs_4_tools,
        define_orthogonal_concerns
      ]
    ]
    GATE::"Immutables defined, tool count decided"
    OWNER::north-star-architect

  D2::ARCHITECTURE_DESIGN:
    STATUS::PENDING
    DEPENDS_ON::D1[tool_interface_decision]
    WORK_ITEMS::[
      GH_51::tool_consolidation[
        IF[3_tools_chosen]::design[
          octave_validate[schema_check+repair_suggestions,read_only],
          octave_write[normalize+write+auto_detect_new_vs_existing,write],
          octave_eject[format_conversion+projection,none]
        ],
        migration_path_from_current_4_tools,
        deprecation_timeline
      ]
    ]
    GATE::"Tool specs complete, migration documented"
    OWNER::technical-architect

  B0::WORKSPACE_SETUP:
    STATUS::PENDING
    WORK_ITEMS::[
      validate_quality_gates[mypy,ruff,black,pytest],
      confirm_CI_pipeline,
      verify_test_infrastructure
    ]
    GATE::"All quality gates green"
    OWNER::workspace-architect

  B1::FOUNDATION_FIXES:
    STATUS::PENDING
    DEPENDS_ON::[D2,B0]
    WORK_ITEMS::[
      GH_56::core_ingest_fixes[
        P0::lenient_syntax_parsing[accept_unquoted_dotted_paths],
        P1::metadata_mutation[mutations_parameter],
        P2::structure_preservation[preserve_structure_flag],
        P3::round_trip_validation[document_behavior+validate_function],
        P4::error_recovery[lenient_mode+partial_output]
      ]
    ]
    GATE::"All P0-P2 fixes verified, tests passing"
    OWNER::implementation-lead

  B2::FEATURE_IMPLEMENTATION:
    STATUS::PENDING
    DEPENDS_ON::B1
    WORK_ITEMS::[
      GH_52::debate_transcript_helpers[
        schema_validation[DEBATE_TRANSCRIPT_structure],
        json_to_octave_converter,
        compression_metrics_tracking
      ],
      GH_48::vocabulary_snapshot[
        define_vocab_file_format,
        implement_hydrate_cli_command,
        handle_snapshot_import_roundtrip
      ]
    ]
    GATE::"Features tested, documented"
    OWNER::implementation-lead

CRITICAL_PATH::[
  D0::north_star_creation->BLOCKING[all_subsequent_phases],
  D1::tool_decision->BLOCKING[D2_design],
  D2::tool_specs->BLOCKING[B1_implementation],
  B1::core_fixes->BLOCKING[B2_features]
]

RECOMMENDATIONS:

  IMMEDIATE::[
    1::complete_D0[create_north_star_document],
    2::close_GH_55[duplicate_of_GH_56],
    3::validate_GH_51_against_D1_decision[ensure_alignment]
  ]

  SEQUENCING::[
    GH_25::can_proceed_in_D1[no_dependencies],
    GH_51::requires_D1_completion[tool_decision_needed],
    GH_56::requires_D2_completion[design_needed_before_implementation],
    GH_52_and_GH_48::queue_for_B2[after_core_stable]
  ]

  DEFERRED::[
    HestAI-MCP_integration::after_B1[stable_tools_needed],
    debate-hall-mcp_validation::after_B2[debate_helpers_needed]
  ]

GAP_ANALYSIS:

  DISCOVERED_GAPS::[
    roadmap_says_2_tools_issue_51_says_3_tools[RECONCILE_IN_D1],
    no_workflow_dir_created_yet[CREATED_WITH_THIS_ARTIFACT],
    checklist_not_updated_with_issues[SEPARATE_TASK]
  ]

  OWNERSHIP::[
    D0_completion::requirements-steward,
    tool_decision::north-star-architect+technical-architect,
    issue_triage::holistic-orchestrator[CURRENT_SESSION],
    implementation::implementation-lead[DELEGATED]
  ]

NEXT_SESSION_HANDOFF::[
  1::review_this_plan_with_user,
  2::initiate_D0_completion[north_star_creation],
  3::update_PROJECT-CHECKLIST_with_issue_links,
  4::close_duplicate_issue_GH_55
]

===END===
