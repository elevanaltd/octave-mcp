===GAP_6_INVESTIGATION===
META:
  TYPE::INVESTIGATION_REPORT
  AUTHOR::implementation-lead[claude-opus-4-5]
  DATE::"2026-01-02"
  TARGET::Gap_6_ERROR_MESSAGES
  STATUS::COMPLETE
  PHASE::B3_INTEGRATION

---

§1::SPEC_ERROR_CODES

SOURCE::specs/octave-mcp-architecture.oct.md[§8::ERROR_MESSAGES]
PATTERN::"ERROR_ID::MESSAGE::RATIONALE"

SPEC_ERRORS::[
  E001::{
    MESSAGE::"Single colon assignment not allowed. Use KEY::value (double colon).",
    RATIONALE::"OCTAVE uses :: for assignment because : is the block operator.",
    CATEGORY::SYNTAX
  },
  E002::{
    MESSAGE::"Schema selector required. Add @SCHEMA_NAME or explicit ===ENVELOPE===.",
    RATIONALE::"OCTAVE cannot infer document type.",
    CATEGORY::SCHEMA
  },
  E003::{
    MESSAGE::"Cannot auto-fill missing required field '{field}'.",
    RATIONALE::"Required fields represent author intent.",
    CATEGORY::VALIDATION
  },
  E004::{
    MESSAGE::"Cannot infer routing target. Specify →§TARGET explicitly.",
    RATIONALE::"Routing determines where data flows.",
    CATEGORY::ROUTING
  },
  E005::{
    MESSAGE::"Tabs not allowed. Use 2 spaces for indentation.",
    RATIONALE::"OCTAVE requires consistent indentation.",
    CATEGORY::SYNTAX
  },
  E006::{
    MESSAGE::"Ambiguous enum match for '{value}'.",
    RATIONALE::"Schema-driven repair only works when there's exactly one valid correction.",
    CATEGORY::VALIDATION
  },
  E007::{
    MESSAGE::"Unknown field '{field}' not allowed in STRICT mode.",
    RATIONALE::"Avoids schema surface drift.",
    CATEGORY::SCHEMA
  }
]

---

§2::IMPLEMENTATION_ERROR_CODES

LAYER_1_MCP_TOOL_ERRORS::[
  LOCATION::"src/octave_mcp/mcp/write.py, validate.py",
  CODES::{
    E_INPUT::{MSG::"Mutual exclusion/parameter validation", LINES::[write:518-527, validate:209-216]},
    E_PATH::{MSG::"Invalid file path", LINES::[write:509, validate:223]},
    E_FILE::{MSG::"File not found", LINES::[write:544, validate:227]},
    E_READ::{MSG::"Error reading file", LINES::[write:554,632, validate:232]},
    E_HASH::{MSG::"Hash mismatch - CAS guard", LINES::[write:565,624,747]},
    E_TOKENIZE::{MSG::"Tokenization error", LINES::[write:641, validate:265]},
    E_PARSE::{MSG::"Parse error", LINES::[write:579,653, validate:267]},
    E_APPLY::{MSG::"Apply changes error", LINES::[write:588]},
    E_EMIT::{MSG::"Emit error", LINES::[write:599,665, validate:349]},
    E_WRITE::{MSG::"Write error", LINES::[write:715,765]}
  }
]

LAYER_2_CORE_ERRORS::[
  LOCATION::"src/octave_mcp/core/lexer.py, parser.py, validator.py, constraints.py",
  CODES::{
    E001::{IMPL::"Single colon on same line as block operator value", LOCATIONS::[parser:120,517], MATCH::PARTIAL},
    E003::{IMPL::"Cannot auto-fill missing required field", LOCATIONS::[validator:89, constraints:94], MATCH::YES},
    E004::{IMPL::"CONST constraint mismatch", LOCATIONS::[constraints:134], MATCH::PARTIAL[spec_says_routing]},
    E005::{IMPL::"Tabs/unexpected chars/enum no match", LOCATIONS::[lexer:72,167,314, constraints:175], MATCH::PARTIAL[overloaded]},
    E006::{IMPL::"Ambiguous enum match", LOCATIONS::[parser:379,387,404, constraints:190], MATCH::YES},
    E007::{IMPL::"Unknown field/type violation", LOCATIONS::[validator:102,229,238,256, constraints:248,263], MATCH::PARTIAL[overloaded]}
  }
]

---

§3::GAP_ANALYSIS

DISCREPANCIES::[
  GAP_A::{
    ISSUE::"MCP tools use E_* prefix codes",
    SPEC::"Spec defines E001-E007 numeric codes",
    IMPACT::"API consumers receive different error codes than documented",
    SEVERITY::MEDIUM
  },
  GAP_B::{
    ISSUE::"E002 (Schema selector required) not implemented",
    SPEC::"E002 defined for missing schema selector",
    IMPACT::"Users get generic parse errors instead of educational E002",
    SEVERITY::LOW
  },
  GAP_C::{
    ISSUE::"E004 used for CONST constraint violations",
    SPEC::"E004 defined for routing target inference",
    IMPACT::"Semantic mismatch",
    SEVERITY::LOW
  },
  GAP_D::{
    ISSUE::"E005 overloaded (tabs, unexpected chars, enum no-match)",
    SPEC::"E005 specifically for tabs",
    IMPACT::"Educational rationale diluted",
    SEVERITY::LOW
  },
  GAP_E::{
    ISSUE::"E007 overloaded (unknown fields AND type violations)",
    SPEC::"E007 specifically for unknown fields in strict mode",
    IMPACT::"Educational rationale diluted",
    SEVERITY::LOW
  }
]

---

§4::ERROR_FLOW_ANALYSIS

MCP_OUTPUT_PATH::[
  "1. MCP_tool_execute() catches exceptions, wraps in envelope",
  "2. Core errors (E001-E007) propagate via exception, MCP catches, wraps as E_TOKENIZE/E_PARSE",
  "3. Validation errors returned in validation_errors array, codes preserved",
  "4. Final output: {status, errors[], validation_errors[]}"
]

CODE_PRESERVATION::[
  CORE_ERRORS::"E001-E007 embedded in error messages but wrapped in E_TOKENIZE/E_PARSE",
  VALIDATION_ERRORS::"E003-E007 preserved in validation_errors array",
  MCP_TOOL_ERRORS::"E_* codes used in errors array"
]

---

§5::LOCATIONS_SUMMARY

ERROR_DEFINITIONS::[
  {FILE::"src/octave_mcp/core/lexer.py", LINES::[72-77,167,314], CODES::[E005]},
  {FILE::"src/octave_mcp/core/parser.py", LINES::[120-127,379,387,404,517], CODES::[E001,E006]},
  {FILE::"src/octave_mcp/core/validator.py", LINES::[89,102,159,229,238,256], CODES::[E003,E007]},
  {FILE::"src/octave_mcp/core/constraints.py", LINES::[94,134,175,190,248,263], CODES::[E003,E004,E005,E006,E007]},
  {FILE::"src/octave_mcp/mcp/write.py", LINES::[509-765], CODES::[E_PATH,E_INPUT,E_FILE,E_READ,E_HASH,E_TOKENIZE,E_PARSE,E_APPLY,E_EMIT,E_WRITE]},
  {FILE::"src/octave_mcp/mcp/validate.py", LINES::[209-349], CODES::[E_INPUT,E_PATH,E_FILE,E_READ,E_TOKENIZE,E_PARSE,E_EMIT]}
]

---

§6::FIX_RECOMMENDATION

APPROACH::HYBRID_ERROR_CODE_UNIFICATION

RECOMMENDED_OPTION::LAYERED_ERROR_CODES
  DESCRIPTION::"Keep E_* for MCP tool layer, preserve E001-E007 for core layer, add mapping"
  PROS::[Non-breaking, clear layer separation, both code sets meaningful]
  CONS::[Two code systems to maintain]

IMPLEMENTATION_STEPS::[
  "1. Create src/octave_mcp/core/error_codes.py with canonical definitions",
  "2. Define ErrorCode enum with all E001-E007 plus E_* codes",
  "3. Add educational rationale strings from spec §8",
  "4. Update core layer to import from enum",
  "5. Update MCP tools to use consistent codes from enum",
  "6. Add error code documentation to MCP tool responses",
  "7. Consider adding 'spec_code' field mapping E_* to E00x for API clarity"
]

ESTIMATED_EFFORT::[
  FILES_TO_MODIFY::6,
  NEW_FILES::1,
  RISK::LOW,
  COMPLEXITY::MEDIUM
]

---

§7::WARNINGS_CODES

STRUCTURAL_WARNINGS::[
  W_STRUCT_001::"Section marker loss" (write.py:33),
  W_STRUCT_002::"Block count reduction" (write.py:34),
  W_STRUCT_003::"Assignment count reduction" (write.py:35),
  W002::"ASCII operator -> Unicode correction" (write.py:305)
]

NOTE::"W001-W005 mentioned in comment (write.py:297) but only W002 implemented"

===END===
