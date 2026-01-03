===GAP_2_DEBATE_RESOLUTION===
META:
  TYPE::ARCHITECTURAL_DECISION_RECORD
  ADR_NUMBER::ADR-0012
  DATE::"2026-01-03"
  AUTHOR::holistic-orchestrator[claude-opus-4-5]
  DEBATE_METHOD::debate-hall[Wind+Wall+Door]
  PARTICIPANTS::[gemini-3-pro-preview[Wind],codex[Wall],claude-opus-4-5[Door]]
  STATUS::APPROVED

---

§1::DECISION_TITLE

TITLE::"Token-Witnessed Reconstruction for Holographic Pattern Parsing (Gap_2)"

---

§2::CONTEXT

PROBLEM::"Holographic patterns like `[\"example\"∧REQ→§SELF]` are parsed as generic ListValue. SchemaExtractor reconstructs strings from tokenized items to re-parse via HolographicParser. This reconstruction is fragile and loses information."

ROOT_CAUSE_ANALYSIS::[
  "Lexer strips quotes from string tokens (`\"∧\"` becomes bare `∧`)",
  "Parser returns token.value without type metadata",
  "ListValue.items contains values without token-type context",
  "Reconstruction cannot distinguish operator `∧` from quoted string `\"∧\"`",
  "This is an I1/I3 violation (guessing instead of mirroring)"
]

FRAGILITY_PROOF:
  CASE::"Operator Masquerade"
  INPUT::'FIELD::[\"∧\"∧REQ→§SELF]'
  EXPECTED::pattern.example == "∧" (quoted constraint symbol as value)
  ACTUAL::Reconstructor treats first `∧` as operator, corrupting pattern
  VERDICT::"Current heuristic approach CANNOT handle this edge case correctly"

---

§3::DECISION

DECISION::TOKEN_WITNESSED_RECONSTRUCTION

RATIONALE::[
  "Wind (PATHOS): Token preservation enables deterministic reconstruction without guessing",
  "Wall (ETHOS): Heuristics-only is IMPOSSIBLE for operator masquerade case; token witness is minimal viable fix",
  "Both agree this approach maintains v0.2.x scope constraints while fixing I1/I3 violations"
]

REJECTED_ALTERNATIVES::{
  STRENGTHEN_HEURISTICS::{
    PROPOSAL::"Improve _list_value_to_pattern_string() edge case handling",
    VERDICT::IMPOSSIBLE,
    REASON::"Information destroyed at lexer level; cannot reconstruct what was never preserved"
  },
  NATIVE_PARSER_SUPPORT::{
    PROPOSAL::"Add HolographicPatternValue AST node with new grammar rules",
    VERDICT::IMPOSSIBLE,
    REASON::"Violates v0.2.x scope constraint (no major parser grammar changes)"
  },
  SOURCE_SLICING::{
    PROPOSAL::"Track start/end indices for pixel-perfect substring extraction",
    VERDICT::DEFERRED_TO_V0.3.X,
    REASON::"Higher effort (lexer+parser+AST plumbing); token-witness sufficient for v0.2.x"
  }
}

---

§4::IMPLEMENTATION_SPECIFICATION

FILE_CHANGES::[
  {
    FILE::"src/octave_mcp/core/ast_nodes.py",
    CHANGE::"Extend ListValue dataclass with `tokens: list[Token] | None = None`",
    BACKWARDS_COMPAT::"Optional field with None default preserves existing behavior"
  },
  {
    FILE::"src/octave_mcp/core/parser.py",
    CHANGE::"In parse_list(), capture token slice: `list_value.tokens = self.tokens[start_pos:end_pos]`",
    LOCATION::"parse_list() method"
  },
  {
    FILE::"src/octave_mcp/core/schema_extractor.py",
    CHANGE::"Update _list_value_to_pattern_string() to prefer token-based reconstruction when tokens available",
    LOGIC::[
      "IF list_value.tokens: iterate tokens with type awareness",
      "TokenType.STRING → preserve as quoted value",
      "TokenType.CONSTRAINT → output as operator",
      "TokenType.SECTION → output as target marker",
      "ELSE: fall back to existing items-based logic (backwards compat)"
    ]
  }
]

REQUIRED_TESTS::[
  {
    TEST::"test_operator_masquerade_quoted_constraint",
    INPUT::'FIELD::[\"∧\"∧REQ→§SELF]',
    ASSERT::"pattern.example == '∧' AND pattern.constraints contains REQ"
  },
  {
    TEST::"test_operator_masquerade_quoted_flow",
    INPUT::'FIELD::[\"→\"∧REQ→§SELF]',
    ASSERT::"pattern.example == '→' AND pattern.target == 'SELF'"
  },
  {
    TEST::"test_quoted_section_marker_literal",
    INPUT::'FIELD::[\"§\"∧REQ→§SELF]',
    ASSERT::"pattern.example == '§' (not treated as routing marker)"
  }
]

---

§5::IMPACT_ANALYSIS

IMMUTABLE_ALIGNMENT::{
  I1_SYNTACTIC_FIDELITY::"Token witness preserves lexer's ground truth; no more guessing",
  I3_MIRROR_CONSTRAINT::"Reconstruction reflects what parser saw, creates nothing",
  I4_TRANSFORM_AUDITABILITY::"Token→reconstruction is deterministic and traceable"
}

RISK_ASSESSMENT::{
  RISK_LEVEL::LOW,
  BLAST_RADIUS::"3 files, ~50 lines of change",
  REGRESSION_MITIGATION::"Existing tests remain green; new tests prove correctness"
}

GAP_DEPENDENCY_RESOLUTION::{
  GAP_2::UNBLOCKED_BY_THIS_ADR,
  GAP_1::"Constraint validation can proceed once Gap_2 fix lands"
}

---

§6::VERIFICATION_GATES

PHASE_2_GAP_2_COMPLETE::[
  "All 3 operator masquerade tests pass",
  "Existing schema_extractor tests remain green",
  "pytest -k 'test_schema_extractor' passes",
  "CRS (Codex) signoff",
  "CE (Gemini) signoff"
]

---

§7::DEBATE_SYNTHESIS_EVIDENCE

WIND_CONTRIBUTION::[
  "Identified 4 creative approaches: Token-Witnessed, Holocron AST, Source Slicing, Edge Cases",
  "Surfaced operator masquerade as critical edge case",
  "Recommended Token-Witnessed for v0.2.x, Source Slicing for long-term"
]

WALL_CONTRIBUTION::[
  "Proved heuristics-only IMPOSSIBLE via I1/I3 violation evidence",
  "Confirmed Token-Witnessed POSSIBLE_WITH_CONDITIONS",
  "Identified exact file locations and minimal fix scope",
  "Specified 3 required test cases"
]

DOOR_SYNTHESIS::[
  "Recognized convergence: both cognitions point to Token-Witnessed",
  "Transcended false dichotomy of 'strengthen heuristics' vs 'native parser'",
  "Third way: preserve existing architecture + add fidelity layer"
]

EMERGENCE_VALIDATION::[
  "Wind alone: creative but needed constraint validation",
  "Wall alone: rigorous but needed creative alternatives surfaced",
  "Together: optimal solution emerged through dialectic"
]

===END===
