===FLOW_EXPRESSIONS===
META:
  TYPE::TEST_VECTOR
  VERSION::"1.0.0"
  PURPOSE::"Validates all expression operator types per parser.py EXPRESSION_OPERATORS"
  REFERENCE::"parser.py parse_flow_expression() lines 1683-1787"

---

// EXPRESSION_OPERATORS frozenset (parser.py lines 110-120):
// FLOW, SYNTHESIS, AT, CONCAT, TENSION, CONSTRAINT, ALTERNATIVE

§1::FLOW_OPERATOR
  // TokenType.FLOW: -> (ASCII) or U+2192 (Unicode)
  // Source: lexer.py patterns lines 286-288
  // Right-associative, precedence 7
  SIMPLE_FLOW::[A->B]
  CHAIN_FLOW::[Input->Process->Transform->Output]
  UNICODE_FLOW::[Start→End]
  UNICODE_CHAIN::[Begin→Middle→Finish]
  MIXED_FLOW::[ASCII->Unicode→Back]

§2::SYNTHESIS_OPERATOR
  // TokenType.SYNTHESIS: + (ASCII) or U+2295 (Unicode)
  // Source: lexer.py patterns lines 289-290
  // Precedence 3, represents emergent whole
  SIMPLE_SYNTHESIS::[A+B]
  CHAIN_SYNTHESIS::[Code+Tests+Docs]
  UNICODE_SYNTHESIS::[Design⊕Build]
  UNICODE_CHAIN::[A⊕B⊕C]
  COMBINED::[Analysis⊕Design→Implementation]

§3::CONCAT_OPERATOR
  // TokenType.CONCAT: ~ (ASCII) or U+29FA (Unicode)
  // Source: lexer.py patterns lines 291-292
  // Precedence 2, mechanical join
  SIMPLE_CONCAT::[First~Second]
  CHAIN_CONCAT::[A~B~C~D]
  UNICODE_CONCAT::[Prefix⧺Suffix]
  UNICODE_CHAIN::[A⧺B⧺C⧺D]

§4::AT_OPERATOR
  // TokenType.AT: @
  // Source: lexer.py pattern line 293
  // Location/context indicator
  SIMPLE_AT::[Function@Module]
  CHAIN_AT::[Component@Layer@System]
  COMBINED_AT::[Handler@Route→Response]

§5::TENSION_OPERATOR
  // TokenType.TENSION: vs (with boundaries), <-> (ASCII), U+21CC (Unicode)
  // Source: lexer.py patterns lines 287, 294-295
  // Precedence 4, BINARY ONLY (no chaining)
  VS_BOUNDED::[Speed vs Quality]
  ASCII_TENSION::[Fast<->Safe]
  UNICODE_TENSION::[Performance⇌Security]
  IN_LIST::[A vs B, C⇌D]  // Multiple binary tensions in list

§6::CONSTRAINT_OPERATOR
  // TokenType.CONSTRAINT: & (ASCII) or U+2227 (Unicode)
  // Source: lexer.py patterns lines 298-299
  // Precedence 5, ONLY valid inside brackets
  SIMPLE_CONSTRAINT::[Required&Validated]
  CHAIN_CONSTRAINT::[TypeA&TypeB&TypeC&TypeD]
  UNICODE_CONSTRAINT::[Constraint1∧Constraint2]
  UNICODE_CHAIN::[A∧B∧C∧D]

§7::ALTERNATIVE_OPERATOR
  // TokenType.ALTERNATIVE: | (ASCII) or U+2228 (Unicode)
  // Source: lexer.py patterns lines 296-297
  // Precedence 6, logical or
  SIMPLE_ALTERNATIVE::[OptionA|OptionB]
  CHAIN_ALTERNATIVE::[Path1|Path2|Path3|Path4]
  UNICODE_ALTERNATIVE::[Choice1∨Choice2]
  UNICODE_CHAIN::[A∨B∨C∨D]

§8::COMPLEX_EXPRESSIONS
  // Mixed operators with varying precedence
  // Precedence (lower = tighter): [] (1), ~ (2), + (3), vs (4), & (5), | (6), -> (7)
  MIXED_OPERATORS::[A+B->C|D]
  PIPELINE::[Input->Transform+Validate->Output]
  SELECTION::[OptionA|OptionB->Process]
  CONSTRAINED_FLOW::[Source->Filter&Validate->Sink]
  // Full Unicode version
  UNICODE_PIPELINE::[Input→Transform⊕Validate→Output]
  UNICODE_SELECTION::[OptionA∨OptionB→Process]
  UNICODE_CONSTRAINED::[Source→Filter∧Validate→Sink]

§9::SECTION_REFERENCES_IN_FLOW
  // Section markers in flow expressions
  // Source: parser.py lines 1752-1763 (Gap 9 fix)
  SECTION_TARGET::[Start→§DESTINATION]
  NUMBERED_SECTION::[A→§1]
  FLOW_TO_SECTION::[Process→§OUTPUT]
  ASCII_SECTION::[Start->#DESTINATION]

§10::VARIABLES_IN_FLOW
  // Variable references in expressions
  // Source: parser.py lines 1253-1264, 1764-1767 (Issue #181)
  VAR_FLOW::[$INPUT→$OUTPUT]
  VAR_SYNTHESIS::[$A⊕$B]
  MIXED_VAR::[Prefix→$DYNAMIC→Suffix]
  ASCII_VAR::[Prefix->$DYNAMIC->Suffix]

===END===
