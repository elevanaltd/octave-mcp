===NEXT_STAGES_PLAN===
// Phase-gated implementation plan synthesized from GitHub issues
// Generated: 2025-12-28 by holistic-orchestrator

META:
  TYPE::"ORCHESTRATION_PLAN"
  VERSION::"1.1.0"
  SESSION::3fecf983
  UPDATED::"2025-12-28"
  SYNTHESIZED_FROM::[
    gh_issues::[25,48,51,52,55,56],
    context::[PROJECT-CONTEXT,PROJECT-ROADMAP,PROJECT-CHECKLIST]
  ]

SUMMARY::"D2 COMPLETE. 3-tool design approved by quality gates. Next: B0 workspace setup, B1 implementation."

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

  D0::DISCOVERY:
    STATUS::COMPLETE
    ARTIFACT::.hestai/workflow/000-OCTAVE-MCP-NORTH-STAR.md
    GATE::"North star defined with OCTAVE protocol immutables"
    OWNER::requirements-steward

  D1::REQUIREMENTS:
    STATUS::COMPLETE
    ARTIFACTS::[
      north_star::".hestai/workflow/000-OCTAVE-MCP-NORTH-STAR.md",
      immutables::[I1_syntactic_fidelity,I2_deterministic_absence,I3_mirror_constraint,I4_transform_auditability,I5_schema_sovereignty],
      tool_decision::3_tools[validate,write,eject]
    ]
    GATE::"Immutables defined, tool count decided"
    OWNER::north-star-architect

  D2::ARCHITECTURE_DESIGN:
    STATUS::COMPLETE
    ARTIFACT::"docs/architecture/tool-consolidation-design.md"
    QUALITY_GATES_PASSED::[
      CE_gemini::PASS[I1-I5_compliance],
      CRS_codex::PASS[API_design,DELETE_encoding,error_envelope],
      PE_claude::CONDITIONAL_GO[strategic_viability]
    ]
    WORK_ITEMS_COMPLETED::[
      GH_51::tool_consolidation[
        octave_validate[schema_check+repair_suggestions,read_only],
        octave_write[unified_create_amend+tri_state_semantics+schema_param],
        octave_eject[format_conversion+projection,unchanged]
      ],
      migration_path[12_week_deprecation],
      i2_compliance[DELETE_sentinel_as_JSON_object],
      i5_compliance[validation_status_always_returned]
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
  D0::COMPLETE,
  D1::COMPLETE,
  D2::COMPLETE,
  B0::workspace_setup->NEXT[ready_for_implementation],
  B1::core_fixes->BLOCKING[B2_features]
]

RECOMMENDATIONS:

  IMMEDIATE::[
    1::B0_workspace_setup[validate_quality_gates],
    2::close_GH_55[duplicate_of_GH_56],
    3::begin_B1_implementation[GH_56_core_fixes]
  ]

  SEQUENCING::[
    GH_25::can_proceed_in_parallel[spec_clarification],
    GH_51::COMPLETE[design_approved],
    GH_56::ready_for_B1[design_complete],
    GH_52_and_GH_48::queue_for_B2[after_core_stable]
  ]

  DEFERRED::[
    HestAI-MCP_integration::after_B1[stable_tools_needed],
    debate-hall-mcp_validation::after_B2[debate_helpers_needed]
  ]

GAP_ANALYSIS:

  RESOLVED_GAPS::[
    tool_count_decision::3_tools_chosen[validate,write,eject],
    workflow_dir::CREATED,
    D2_design::COMPLETE_WITH_QUALITY_GATES
  ]

  REMAINING_GAPS::[
    mutations_stub::needs_implementation_before_B1,
    schema_validation_infrastructure::P2.5_work,
    checklist_not_updated_with_issues[SEPARATE_TASK]
  ]

  OWNERSHIP::[
    B0_setup::workspace-architect,
    B1_implementation::implementation-lead[DELEGATED],
    issue_triage::holistic-orchestrator[CURRENT_SESSION]
  ]

NEXT_SESSION_HANDOFF::[
  1::approve_D2_design[tool-consolidation-design.md],
  2::initiate_B0_workspace_setup,
  3::delegate_B1_implementation_to_IL,
  4::close_duplicate_issue_GH_55
]

===END===
