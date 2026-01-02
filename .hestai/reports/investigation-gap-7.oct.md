===GAP_7_INVESTIGATION===
META:
  TYPE::INVESTIGATION_REPORT
  AUTHOR::implementation-lead[claude-opus-4-5]
  DATE::"2026-01-02"
  TARGET::Gap_7_RESPONSE_STRUCTURE
  STATUS::COMPLETE
  PHASE::B3_INTEGRATION

---

§1::EXECUTIVE_SUMMARY

FINDING::"Response structure mismatch between spec and implementation confirmed."
IMPACT::P0_CRITICAL[violates_I5_Schema_Sovereignty]
COMPLEXITY::S[field_additions_and_renames]

---

§2::SPEC_REQUIREMENTS

SOURCE::specs/octave-mcp-architecture.oct.md[§7::MCP_TOOL_SURFACE]

TOOL_VALIDATE_RETURNS:
  CANONICAL::["===DOC===\n..."∧REQ→validated_OCTAVE]
  VALID::[true∧REQ∧BOOLEAN→whether_document_passed_validation]
  VALIDATION_ERRORS::[[...]∧REQ→schema_violations_found]
  REPAIR_LOG::[[...]∧REQ→transformation_log_always_present]

SPEC_MANDATED_FIELDS::[
  {FIELD::"canonical", TYPE::string, REQUIRED::YES, DESC::"Validated OCTAVE output"},
  {FIELD::"valid", TYPE::boolean, REQUIRED::YES, DESC::"Whether document passed validation"},
  {FIELD::"validation_errors", TYPE::array, REQUIRED::YES, DESC::"Schema violations found"},
  {FIELD::"repair_log", TYPE::array, REQUIRED::YES, DESC::"Transformation log"}
]

---

§3::CURRENT_IMPLEMENTATION

SOURCE::src/octave_mcp/mcp/validate.py

SUCCESS_ENVELOPE[lines_240-248]:
  status::"success"
  canonical::""
  repairs::[]  # MISNAMED - spec says "repair_log"
  warnings::[]
  errors::[]
  validation_status::"UNVALIDATED"
  routing_log::[]

IMPLEMENTATION_FIELDS::[
  {FIELD::"status", TYPE::string, PRESENT::YES, NOTES::"NOT in spec"},
  {FIELD::"canonical", TYPE::string, PRESENT::YES, NOTES::"Matches spec"},
  {FIELD::"valid", TYPE::boolean, PRESENT::NO, NOTES::"MISSING - Spec requires"},
  {FIELD::"repairs", TYPE::array, PRESENT::YES, NOTES::"MISNAMED - Spec says repair_log"},
  {FIELD::"warnings", TYPE::array, PRESENT::YES, NOTES::"Not in spec but useful"},
  {FIELD::"errors", TYPE::array, PRESENT::YES, NOTES::"Used for parse/input errors"},
  {FIELD::"validation_status", TYPE::string, PRESENT::YES, NOTES::"VALIDATED|UNVALIDATED|INVALID"},
  {FIELD::"validation_errors", TYPE::array, PRESENT::CONDITIONAL, NOTES::"Only when INVALID"},
  {FIELD::"schema_name", TYPE::string, PRESENT::CONDITIONAL, NOTES::"When schema found"},
  {FIELD::"schema_version", TYPE::string, PRESENT::CONDITIONAL, NOTES::"When schema found"},
  {FIELD::"routing_log", TYPE::array, PRESENT::YES, NOTES::"I4 compliance"}
]

---

§4::GAP_ANALYSIS

DISCREPANCIES::[
  {ISSUE::"Missing valid boolean", SPEC::"VALID::[true∧REQ∧BOOLEAN]", IMPL::"Not present", IMPACT::"API CONTRACT BROKEN"},
  {ISSUE::"Field name mismatch", SPEC::"REPAIR_LOG", IMPL::"Uses repairs", IMPACT::"API CONTRACT BROKEN"},
  {ISSUE::"Error code format", SPEC::"Granular E001-E007", IMPL::"Uses E_PARSE, E_TOKENIZE, E_INPUT, etc.", IMPACT::"INCONSISTENT"},
  {ISSUE::"Extra fields", SPEC::"Not specified", IMPL::"status, warnings, validation_status, routing_log, schema_name, schema_version", IMPACT::"ENHANCEMENT"}
]

VIOLATIONS::[
  I5_SCHEMA_SOVEREIGNTY::"API contract as documented cannot be fulfilled",
  BACKWARD_COMPATIBILITY::"docs/api.md documents spec format, creating inconsistency"
]

---

§5::ENVELOPE_CONSTRUCTION_LOCATIONS

FILE::src/octave_mcp/mcp/validate.py
LOCATIONS::[
  {LINES::"165-173", CONTEXT::"_error_envelope() method"},
  {LINES::"240-248", CONTEXT::"Main result dict initialization in execute()"},
  {LINES::"206-216", CONTEXT::"Error returns for XOR violations"},
  {LINES::"222-232", CONTEXT::"Error returns for file operations"},
  {LINES::"260-269", CONTEXT::"Parse error handling"},
  {LINES::"347-350", CONTEXT::"Emit error handling"}
]

---

§6::FIX_RECOMMENDATION

STEP_1::ADD_VALID_BOOLEAN
  LOGIC::'result["valid"] = result["validation_status"] == "VALIDATED"'
  EFFORT::S[1_line]
  RISK::LOW

STEP_2::RENAME_REPAIRS_TO_REPAIR_LOG
  OPTIONS::[
    OPTION_A::{NAME::"Breaking", DESC::"Rename globally", EFFORT::S, RISK::MEDIUM},
    OPTION_B::{NAME::"Backward Compatible", DESC::"Return BOTH repairs and repair_log, deprecate repairs", EFFORT::S, RISK::LOW}
  ]
  RECOMMENDATION::OPTION_A_with_semver_bump_to_0.3.0_OR_OPTION_B_for_0.2.x

STEP_3::ENSURE_VALIDATION_ERRORS_ALWAYS_PRESENT
  CURRENT::"Only present when validation_status == INVALID"
  SPEC::"REQ (always present)"
  FIX::"Return empty array when no errors"

STEP_4::ENSURE_CANONICAL_ALWAYS_PRESENT
  STATUS::ALREADY_IMPLEMENTED_CORRECTLY

STEP_5::CONSIDER_SPEC_UPDATE
  RECOMMENDATION::"Update spec to adopt validation_status, routing_log (higher fidelity)"

---

§7::TEST_LOCATIONS

EXISTING_TESTS::[
  FILE::tests/unit/test_validate_tool.py,
  COVERAGE::"Tests unified envelope but NOT valid boolean or repair_log field name"
]

NEW_TESTS_NEEDED::[
  "test_validate_returns_valid_boolean",
  "test_validate_returns_repair_log_field",
  "test_validate_returns_validation_errors_always",
  "test_validate_error_codes_match_spec"
]

INTEGRATION_TESTS::[
  FILE::tests/integration/test_e2e.py,
  LINES::"224-232"
]

---

§8::COMPLEXITY_ASSESSMENT

CHANGES::[
  {CHANGE::"Add valid boolean", EFFORT::S, RISK::LOW},
  {CHANGE::"Rename repairs to repair_log", EFFORT::S, RISK::MEDIUM[breaking]},
  {CHANGE::"Propagate error codes", EFFORT::M, RISK::LOW},
  {CHANGE::"Update tests", EFFORT::S, RISK::LOW},
  {CHANGE::"Update docs/api.md", EFFORT::S, RISK::LOW}
]

TOTAL_EFFORT::S[1-2_hours_including_tests]

---

§9::DEPENDENCY_ANALYSIS

DEPENDENCIES::[
  {GAP::"Gap_9 (Alias Bug)", STATUS::INDEPENDENT},
  {GAP::"Gap_6 (Error Messages)", STATUS::CAN_BE_COMBINED}
]

RECOMMENDATION::"Fix Gap_7 and Gap_6 together in same PR"

===END===
