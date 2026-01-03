===GAP_9_INVESTIGATION===
META:
  TYPE::INVESTIGATION_REPORT
  AUTHOR::implementation-lead[claude-opus-4-5]
  DATE::"2026-01-02"
  STATUS::COMPLETE
  PHASE::B3_INTEGRATION

---

§1::EXECUTIVE_SUMMARY

FINDING::"Root cause confirmed. TokenType.SECTION not handled in parse_value()."
IMPACT::P0_CRITICAL[violates_I1_Syntactic_Fidelity]
COMPLEXITY::S[single_file_change,clear_fix_pattern]

§2::ROOT_CAUSE_CONFIRMED

FILE::src/octave_mcp/core/parser.py
FUNCTION::parse_value()
LINES::597-809

EVIDENCE:
  LEXER_BEHAVIOR::[
    INPUT::"TARGET::#INDEXER",
    TOKENS::[
      "IDENTIFIER(TARGET)",
      "ASSIGN(::)",
      "SECTION(§) normalized_from=#",
      "IDENTIFIER(INDEXER)",
      "EOF"
    ],
    REPAIRS::["normalization:#→§"],
    CONCLUSION::"Lexer correctly produces SECTION and IDENTIFIER as separate tokens"
  ]

  PARSER_BEHAVIOR::[
    CALL_CHAIN::"parse_document()->parse_section()->parse_value()",
    CURRENT_HANDLING::[
      "Line 601: if token.type == TokenType.STRING -> handled",
      "Line 605: elif token.type == TokenType.NUMBER -> handled",
      "Line 684: elif token.type == TokenType.BOOLEAN -> handled",
      "Line 688: elif token.type == TokenType.NULL -> handled",
      "Line 692: elif token.type == TokenType.LIST_START -> handled",
      "Line 695: elif token.type == TokenType.IDENTIFIER -> handled",
      "Line 801: elif token.type == TokenType.FLOW -> handled",
      "Line 805: else -> FALLTHROUGH (SECTION lands here)"
    ],
    FALLTHROUGH_CODE::[
      "805:        else:",
      "806:            # Try to consume as bare word",
      "807:            value = str(token.value)  # Returns '§' only",
      "808:            self.advance()            # Moves past SECTION",
      "809:            return value              # Returns '§' without INDEXER"
    ],
    CONSEQUENCE::"IDENTIFIER(INDEXER) left orphaned in token stream"
  ]

  PARSER_OUTPUT::[
    ACTUAL::[
      "Section 0: Assignment, key=TARGET, value='§'",
      "Warning: bare_line_dropped, original='INDEXER'"
    ],
    EXPECTED::[
      "Section 0: Assignment, key=TARGET, value='§INDEXER'"
    ]
  ]

SECONDARY_ISSUE:
  CONTEXT::LIST_PARSING
  DESCRIPTION::"Same bug affects list items"
  EVIDENCE::[
    INPUT::"TARGETS::[#INDEXER,#SELF]",
    ACTUAL::"value.items=['§','INDEXER','§','SELF']",
    EXPECTED::"value.items=['§INDEXER','§SELF']"
  ]

§3::BEHAVIOR_TRACE

DETAILED_FLOW:
  STEP_1::[
    ACTION::"Lexer tokenizes '#INDEXER'",
    RESULT::"[SECTION('§'), IDENTIFIER('INDEXER')]",
    STATUS::CORRECT
  ]
  STEP_2::[
    ACTION::"Parser calls parse_value() with current token = SECTION",
    RESULT::"parse_value() enters 'else' branch at line 805",
    STATUS::BUG_LOCATION
  ]
  STEP_3::[
    ACTION::"Fallthrough code: value = str(token.value)",
    RESULT::"value = '§'",
    STATUS::PARTIAL_CAPTURE
  ]
  STEP_4::[
    ACTION::"self.advance() moves past SECTION token",
    RESULT::"Current token now = IDENTIFIER('INDEXER')",
    STATUS::ORPHANED_IDENTIFIER
  ]
  STEP_5::[
    ACTION::"parse_value() returns '§'",
    RESULT::"Assignment created with value='§'",
    STATUS::INCOMPLETE
  ]
  STEP_6::[
    ACTION::"Parser continues, finds orphaned IDENTIFIER('INDEXER')",
    RESULT::"Treated as bare line, dropped with I4 audit warning",
    STATUS::DATA_LOSS
  ]

§4::FIX_RECOMMENDATION

APPROACH::ADD_SECTION_CASE_TO_PARSE_VALUE

LOCATION::parser.py::parse_value() around line 801 (before else clause)

LOGIC::[
  "1. Add 'elif token.type == TokenType.SECTION:' case",
  "2. Consume SECTION token (the § symbol)",
  "3. Check if next token is IDENTIFIER or NUMBER",
  "4. If yes: consume and concatenate '§' + identifier",
  "5. Return combined string (e.g., '§INDEXER')",
  "6. If no following identifier: return just '§' (edge case)"
]

PSEUDOCODE::[
  "elif token.type == TokenType.SECTION:",
  "    section_marker = token.value  # '§'",
  "    self.advance()  # consume SECTION",
  "    # Check for following identifier/number",
  "    if self.current().type in (TokenType.IDENTIFIER, TokenType.NUMBER):",
  "        target_name = str(self.current().value)",
  "        self.advance()  # consume identifier",
  "        return section_marker + target_name  # '§INDEXER'",
  "    # Bare section marker (rare but valid)",
  "    return section_marker"
]

AFFECTED_CODE_PATHS::[
  "Direct assignment value: TARGET::§INDEXER",
  "List items: TARGETS::[§INDEXER,§SELF]",
  "Flow expressions: data→§INDEXER (via parse_flow_expression)",
  "Holographic patterns: [\"value\"∧REQ→§INDEXER]"
]

ADDITIONAL_CONSIDERATION:
  CONTEXT::parse_flow_expression
  ISSUE::"parse_flow_expression() at line 868-891 also needs updating"
  FIX::"Include TokenType.SECTION in the expression loop"

§5::RISK_ASSESSMENT

RISK_LEVEL::LOW

FACTORS::[
  LOCALIZED_CHANGE::"Single function in single file",
  CLEAR_PATTERN::"Similar to existing IDENTIFIER handling",
  EXISTING_TESTS::"test_lexer.py verifies SECTION token creation (line 86-91)",
  BACKWARD_COMPATIBLE::"No existing code depends on broken behavior"
]

POTENTIAL_ISSUES::[
  ISSUE_1::[
    DESCRIPTION::"Conflict with parse_section_marker() at document level",
    MITIGATION::"parse_value() is only called in value position (after :: or in lists)",
    RISK::MINIMAL
  ],
  ISSUE_2::[
    DESCRIPTION::"Edge case of bare § without following identifier",
    MITIGATION::"Return just '§' - same as current fallthrough behavior",
    RISK::MINIMAL
  ],
  ISSUE_3::[
    DESCRIPTION::"Flow expressions need separate fix",
    MITIGATION::"parse_flow_expression() should include SECTION in token types",
    RISK::MEDIUM[requires_separate_code_path]
  ]
]

§6::TEST_LOCATIONS

EXISTING_TESTS::[
  FILE::tests/unit/test_lexer.py,
  TEST::test_normalize_section_marker[lines_86-91],
  COVERAGE::"Verifies lexer produces SECTION token with normalization"
]

NEW_TESTS_NEEDED::[
  FILE::tests/unit/test_parser.py,
  TESTS::[
    "test_parse_section_target_value::'TARGET::§INDEXER' -> value='§INDEXER'",
    "test_parse_section_target_ascii_alias::'TARGET::#INDEXER' -> value='§INDEXER'",
    "test_parse_section_in_list::'TARGETS::[§INDEXER,§SELF]' -> items=['§INDEXER','§SELF']",
    "test_parse_section_in_flow::'data→§INDEXER' -> value='data→§INDEXER'",
    "test_parse_bare_section_marker::'VALUE::§' -> value='§'"
  ]
]

REGRESSION_TESTS::[
  FILE::tests/unit/test_section_parsing.py,
  CONCERN::"Ensure document-level §1::OVERVIEW still works"
]

===END===
