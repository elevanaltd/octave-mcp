===DECISION_RECORD===
META:
  TYPE::DECISION_RECORD
  VERSION::"1.0"
  THREAD_ID::"2026-02-16-issue-235-design-decisions"
  TOPIC::"Issue #235: 6 Design Decisions for Literal Zones in OCTAVE-MCP"
  DECIDED_AT::"2026-02-16"
  STATUS::APPROVED
  COMPRESSION_TIER::AGGRESSIVE
  SOURCES::["debate-hall_standard","ideator_oa-router",validator_codex_clink,synthesizer_gemini_clink]
  REFERS_TO::["Issue-235","ADR-005"]
§1::DECISIONS
D1::AST_REPRESENTATION
VERDICT::NEW_LITERALZONEVALUE_VALUE_TYPE
RATIONALE::"Distinct dataclass (not ASTNode subclass). Follows HolographicValue⊕ListValue precedent. Fields: content, info_tag, fence_marker."
CONSENSUS::UNANIMOUS
KEY_INSIGHT::"Type safety prevents silent normalization through string paths. Exhaustive pattern matching."
D2::SYNTAX
VERDICT::BACKTICKS_ONLY
RATIONALE::"Triple-backtick fences for block literals. Triple-quotes remain normalizing strings (unchanged). Fence-length scaling per CommonMark."
CONSENSUS::UNANIMOUS
KEY_INSIGHT::"Clear semantic split: backticks='preserve exactly', triple-quotes='multi-line string'. No ambiguity. No backward compatibility break."
D3::ESCAPE_HANDLING
VERDICT::ZERO_PROCESSING
RATIONALE::"Content between fences absolutely raw. No escape processing, no operator normalization, no variable substitution. NFC normalization bypassed for literal spans."
CONSENSUS::UNANIMOUS
KEY_INSIGHT::"Simplest mental model. Matches Markdown⊕CDATA⊕Python_raw_strings. I1 compliance: normalization would alter semantics."
D4::SCHEMA_CONSTRAINTS
VERDICT::ENVELOPE_BOUNDARY_ONLY
RATIONALE::"Schema validates: presence(REQ/OPT), language_tag(LANG[python]), non-empty. Content opaque. validation_status reports literal_zones_validated:false."
CONSENSUS::UNANIMOUS
KEY_INSIGHT::"I5: honest about what is/isn't validated. Prevents validation theater. No REGEX on content (ReDoS risk)."
D5::CONTAINER_SCOPE
VERDICT::YAML_FRONTMATTER_ONLY
RATIONALE::"Container preservation scoped to ---...--- YAML frontmatter. Markdown outer fence remains transport wrapper. No generic envelope detection."
CONSENSUS::STRONG
KEY_INSIGHT::"100+ files use YAML frontmatter. Zero use other formats. SUBTRACTION principle. I3: no heuristic detection."
DIVERGENCE::"Debate proposed unifying frontmatter⊕code_blocks into one node. HO overruled: they serve different purposes."
D6::MCP_TOOL_BEHAVIOR
VERDICT::PRESERVE_ALWAYS_PLUS_AUDIT
RATIONALE::"Literal zones always preserved (non-configurable). All three MCP tools report per-zone status. Stripping requires explicit flag with I4 audit receipt."
CONSENSUS::STRONG
KEY_INSIGHT::"I1/I4 compliance. Zone determines behavior, not flags. Zone-aware reporting eliminates need for configuration."
§2::IMPLEMENTATION_CRITICAL_NOTES
NFC_BYPASS::"Lexer must detect fence boundaries BEFORE applying NFC normalization (lexer.py:429)"
TAB_BYPASS::"Literal zones containing tabs must bypass global tab rejection (lexer.py:435)"
E007_DISCIPLINE::"E007 already overloaded; need subtype/message discipline for nested-fence detection"
EMITTER_PASSTHROUGH::"Emitter canonicalizes via emit() in all tool paths; must be updated for literal zone passthrough"
§3::PROVENANCE
DEBATE_THREAD::"debates/2026-02-16-issue-235-design-decisions.json"
WIND_MODEL::"claude-opus-4-6"
WALL_MODEL::codex
DOOR_MODEL::"gemini-3-pro-preview"
TURN_COUNT::6
PATTERN::"The Sovereign Container Protocol"
===END===
