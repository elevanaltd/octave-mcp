===OCTAVE_MCP_GAP_ANALYSIS===
META:
  TYPE::ARCHITECTURAL_ASSESSMENT
  TARGET::OCTAVE_MCP_IMPLEMENTATION
  AUTHOR::TECHNICAL_ARCHITECT[gemini-3-pro-preview]
  REVIEWER::STRESS_TEST_AGENT[claude-opus-4-5]
  DATE::"2026-01-02"
  VERSION::"0.2.0"
  STATUS::APPROVED
  METHODOLOGY::stress_test→gap_identification→architectural_review

---

§1::EXECUTIVE_SUMMARY

CONTEXT::"Comprehensive stress test of OCTAVE-MCP 3-tool surface (octave_validate, octave_write, octave_eject) against specifications in specs/ directory"

FINDINGS:
  TOTAL_GAPS::9
  CRITICAL::[Gap_9_ALIAS_BUG, Gap_7_RESPONSE_MISMATCH]
  HIGH::[Gap_1_CONSTRAINTS, Gap_2_HOLOGRAPHIC]
  MEDIUM::[Gap_3_TARGET_ROUTING, Gap_5_REPAIR_LOGIC, Gap_6_ERROR_MESSAGES]
  DEFERRABLE::[Gap_4_BLOCK_INHERITANCE, Gap_8_PROJECTION_MODES]

IMMUTABLE_VIOLATIONS:
  I1_SYNTACTIC_FIDELITY::Gap_9[parser_corrupts_#TARGET_syntax]
  I5_SCHEMA_SOVEREIGNTY::Gap_7[API_contract_broken]

§2::PRIORITY_RANKING

RANKING:
  P0_CRITICAL::[Gap_9, Gap_7]
  P1_HIGH::[Gap_1, Gap_2]
  P2_MEDIUM::[Gap_3, Gap_5, Gap_6]
  P3_DEFERRABLE::[Gap_4, Gap_8]

RATIONALE:
  Gap_9_ALIAS_BUG::"Violates I1 (Syntactic Fidelity). Parser breaks on valid #TARGET syntax, corrupting document structure. Must be fixed immediately."
  Gap_7_RESPONSE_MISMATCH::"Violates I5 (Schema Sovereignty). API contract broken; clients cannot reliably consume validation results. Blocking integration."
  Gap_2_HOLOGRAPHIC::"Blocker for Gap 1. Current 'parse-then-reconstruct' strategy in SchemaExtractor is fragile. Needs robust AST support."
  Gap_1_CONSTRAINTS::"Core value proposition. Logic exists in constraints.py but integration depends on Gap 2 fix."

§3::GAP_DETAILS

GAP_1_CONSTRAINT_VALIDATION:
  DESCRIPTION::"Spec defines 12 constraints (REQ, OPT, CONST, REGEX, ENUM, TYPE, DIR, APPEND_ONLY, RANGE, MAX_LENGTH, MIN_LENGTH, DATE, ISO8601). Only structural parsing implemented."
  SPEC_REF::octave-5-llm-schema.oct.md[§2::CONSTRAINTS]
  IMPL_STATUS::PARTIAL[constraints.py_exists_but_not_integrated]
  PRIORITY::P1_HIGH
  DEPENDENCY::Gap_2

GAP_2_HOLOGRAPHIC_PARSING:
  DESCRIPTION::"Spec pattern KEY::[\"example\"∧CONSTRAINT→§TARGET] not parsed correctly. Lexer/parser don't handle L4 schema mode."
  SPEC_REF::octave-5-llm-schema.oct.md[§1::HOLOGRAPHIC_PATTERN]
  IMPL_STATUS::NOT_IMPLEMENTED
  PRIORITY::P1_HIGH
  ROOT_CAUSE::"Parser treats pattern as ListValue. SchemaExtractor reconstructs string to re-parse - fragile approach."

GAP_3_TARGET_ROUTING:
  DESCRIPTION::"Targets (§SELF, §META, §INDEXER, etc.) parsed but not routed/validated."
  SPEC_REF::octave-5-llm-schema.oct.md[§3::TARGETS]
  IMPL_STATUS::PARTIAL[parsing_yes_routing_no]
  PRIORITY::P2_MEDIUM
  DEPENDENCY::Gap_9

GAP_4_BLOCK_INHERITANCE:
  DESCRIPTION::"BLOCK[→§TARGET]: children inherit parent target unless override. Not implemented."
  SPEC_REF::octave-5-llm-schema.oct.md[§4::BLOCK_INHERITANCE]
  IMPL_STATUS::NOT_IMPLEMENTED
  PRIORITY::P3_DEFERRABLE

GAP_5_REPAIR_LOGIC:
  DESCRIPTION::"fix=true should do enum casefold and type coercion. Only normalization (ASCII→Unicode) implemented."
  SPEC_REF::octave-mcp-architecture.oct.md[§5::TIER_REPAIR]
  IMPL_STATUS::PARTIAL[normalization_only]
  PRIORITY::P2_MEDIUM

GAP_6_ERROR_MESSAGES:
  DESCRIPTION::"Spec defines E001-E007 with educational rationale. Implementation uses E_PARSE, E_TOKENIZE, E_INPUT codes."
  SPEC_REF::octave-mcp-architecture.oct.md[§8::ERROR_MESSAGES]
  IMPL_STATUS::MISMATCH
  PRIORITY::P2_MEDIUM

GAP_7_RESPONSE_STRUCTURE:
  DESCRIPTION::"validate missing VALID boolean, different field names. write returns hash not content. eject modes incomplete."
  SPEC_REF::octave-mcp-architecture.oct.md[§7::MCP_TOOL_SURFACE]
  IMPL_STATUS::MISMATCH
  PRIORITY::P0_CRITICAL

GAP_8_PROJECTION_MODES:
  DESCRIPTION::"authoring mode same as canonical. executive/developer strip ALL content not category-specific."
  SPEC_REF::octave-mcp-architecture.oct.md[§9::PROJECTION_MODES]
  IMPL_STATUS::PARTIAL
  PRIORITY::P3_DEFERRABLE

GAP_9_TARGET_ALIAS_BUG:
  DESCRIPTION::"#INDEXER should become §INDEXER but parser drops identifier after # symbol."
  SPEC_REF::octave-mcp-architecture.oct.md[§3::LENIENT_GRAMMAR]
  IMPL_STATUS::BUG
  PRIORITY::P0_CRITICAL
  ROOT_CAUSE::"parser.py::parse_value() does not handle TokenType.SECTION (#/§). Falls through to bare word logic."

§4::IMPLEMENTATION_STRATEGY

STRATEGY_GAP_9_ALIAS_BUG:
  GOAL::"Correctly parse #TARGET and §TARGET as values"
  ROOT_CAUSE::"parser.py::parse_value() does not handle TokenType.SECTION (#/§). Falls through to 'bare word' logic, consuming only the marker and leaving identifier orphaned."
  FIX:
    FILE::src/octave_mcp/core/parser.py
    LOGIC::"Add TokenType.SECTION case to parse_value(). Consume marker + following Identifier/Number. Return combined string."
  RISK::LOW
  COMPLEXITY::S

STRATEGY_GAP_7_RESPONSE_STRUCTURE:
  GOAL::"Align MCP tool output with Spec §7"
  ROOT_CAUSE::"mcp/validate.py constructs ad-hoc response envelope."
  FIX:
    FILE::src/octave_mcp/mcp/validate.py
    LOGIC::[
      "Add 'valid' boolean field (derived from validation_status == VALIDATED)",
      "Rename 'repairs' to 'repair_log' to match Spec §7",
      "Ensure 'validation_errors' uses granular codes (E00x) not generic wrappers",
      "Ensure 'canonical' is always present"
    ]
  RISK::LOW
  COMPLEXITY::S

STRATEGY_GAP_2_HOLOGRAPHIC:
  GOAL::"Robust parsing of schema patterns"
  ROOT_CAUSE::"Parser treats pattern as ListValue. SchemaExtractor attempts to reconstruct string from AST to re-parse. Fragile."
  FIX:
    FILE::src/octave_mcp/core/schema_extractor.py
    APPROACH::"Strengthen _list_value_to_pattern_string to handle all holographic tokens (operators, section markers) correctly. Add comprehensive tests for pattern reconstruction."
    ALTERNATIVE::"Modify parser.py to natively recognize holographic patterns (High effort/risk). Stick to reconstruction for v0.2.0 but verify it."
  RISK::MEDIUM
  COMPLEXITY::M

§5::DEFER_ACCEPT_DECISIONS

DECISIONS:
  Gap_3_TARGET_ROUTING::PARTIAL_ACCEPT[Logic exists in validator.py; verify §TARGET parsing fix (Gap 9) enables it. Full implementation can wait for v0.3.0.]
  Gap_4_BLOCK_INHERITANCE::DEFER[v0.3.0. Not blocking core validation.]
  Gap_5_REPAIR_LOGIC::DEFER[v0.3.0. 'fix=true' currently does normalization (I1). Schema-driven repair (I4) is complex.]
  Gap_8_PROJECTION_MODES::DEFER[v0.3.0. Canonical mode is sufficient for now.]
  Gap_6_ERROR_MESSAGES::ACCEPT_FIX[Easy to fix alongside Gap 7. Pass through granular codes.]

§6::SPEC_ALIGNMENT_RECOMMENDATIONS

RECOMMENDATIONS:
  UPDATE_SPEC_1:
    SECTION::§7_MCP_TOOL_SURFACE
    CHANGE::"Adopt 'validation_status' (VALIDATED|UNVALIDATED|INVALID) from implementation. It offers higher fidelity than boolean 'valid'. Keep 'valid' for backward compat."
  UPDATE_SPEC_2:
    SECTION::§7_MCP_TOOL_SURFACE
    CHANGE::"Clarify 'repair_log' vs 'repairs'. Implementation uses 'repairs'. Spec should align to 'repairs' or implementation to 'repair_log'."

§7::STRESS_TEST_OBSERVATIONS

WORKING_WELL:
  ASCII_UNICODE_NORMALIZATION::"-> → ⊕, + → ⊕, vs → ⇌, | → ∨, & → ∧"
  AUTO_QUOTING::"Multi-word bare values correctly quoted"
  ENVELOPE_HANDLING::"===NAME===...===END=== correctly parsed/emitted"
  FORMAT_EXPORT::"JSON, YAML, Markdown all produce valid output"
  TEMPLATE_GENERATION::"content=null correctly generates schema templates"
  IDEMPOTENT_CANONICALIZATION::"canon(canon(x)) == canon(x) verified"
  CAS_SUPPORT::"base_hash parameter accepted for consistency checks"
  PARSE_ERROR_DETECTION::"Single colon assignment, tabs correctly rejected"

ISSUES_FOUND:
  SLASH_IN_PATHS::"docs/research/file.md causes E_TOKENIZE - paths must be quoted"
  WHITESPACE_NOT_LOGGED::"KEY :: value normalized but not in repairs[]"
  CHANGES_FIELD_PLACEMENT::"Adds to root not contextually to blocks"
  MUTATIONS_NOT_WORKING::"META field overrides had no effect"

§8::RECOMMENDED_ACTION_PLAN

PHASE_1_IMMEDIATE[v0.2.1]:
  FIX_GAP_9::"Parser #TARGET alias bug"
  FIX_GAP_7::"Response structure alignment"
  FIX_GAP_6::"Error message codes"
  EFFORT::S+S+S=3_story_points

PHASE_2_NEXT[v0.2.2]:
  FIX_GAP_2::"Holographic pattern parsing"
  FIX_GAP_1::"Constraint validation integration"
  EFFORT::M+M=6_story_points

PHASE_3_DEFERRED[v0.3.0]:
  FIX_GAP_3::"Full target routing"
  FIX_GAP_4::"Block inheritance"
  FIX_GAP_5::"Schema-driven repair logic"
  FIX_GAP_8::"Projection mode field filtering"
  EFFORT::L+M+L+M=12_story_points

===END===
