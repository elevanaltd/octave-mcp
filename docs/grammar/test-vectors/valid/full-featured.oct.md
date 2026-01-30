OCTAVE::1.0.0
===FULL_FEATURED===
META:
  TYPE::TEST_VECTOR
  VERSION::"1.0.0"
  PURPOSE::"Demonstrates all OCTAVE token types and constructs"
  CONTRACT::HOLOGRAPHIC[JIT_GRAMMAR_COMPILATION]

---

// Section marker with number
// Source: parser.py parse_section_marker() lines 558-719
// Grammar: section_marker = section_operator, section_number, assign_operator, identifier
#1::LITERALS
  // String literals (double-quoted and bare)
  // Source: lexer.py TokenType.STRING line 52, patterns lines 308-309
  QUOTED_STRING::"Hello, World!"
  BARE_WORD::simple_value
  TRIPLE_QUOTED::"""
    Multi-line
    string content
  """

  // Number literals
  // Source: lexer.py TokenType.NUMBER line 53, pattern line 311
  INTEGER::42
  NEGATIVE::-17
  FLOAT::3.14
  SCIENTIFIC::1e10
  SCIENTIFIC_NEG::-2.5e-3

  // Boolean literals (lowercase only)
  // Source: lexer.py TokenType.BOOLEAN line 54, patterns lines 313-314
  BOOL_TRUE::true
  BOOL_FALSE::false

  // Null literal
  // Source: lexer.py TokenType.NULL line 55, pattern line 315
  NULL_VALUE::null

  // Version literals
  // Source: lexer.py TokenType.VERSION line 23, patterns lines 270-272
  SEMVER::1.2.3
  SEMVER_PRE::1.0.0-beta.1
  SEMVER_BUILD::2.0.0+build.123

  // Variable references
  // Source: lexer.py TokenType.VARIABLE line 26, pattern line 321
  VAR_SIMPLE::$MY_VAR
  VAR_NUMBERED::$1:role
  VAR_PATH::$CONFIG_PATH

// Section with named identifier
// Grammar: section_marker = section_operator, identifier, assign_operator, [identifier]
#OPERATORS::EXPRESSION_TYPES
  // Flow operator (-> normalized to U+2192)
  // Source: lexer.py TokenType.FLOW line 41, patterns lines 286-288
  FLOW_ASCII::[A->B->C]
  FLOW_UNICODE::[Input->Process->Output]

  // Synthesis operator (+ normalized to U+2295)
  // Source: lexer.py TokenType.SYNTHESIS line 37, patterns lines 289-290
  SYNTHESIS_ASCII::[Code+Tests]
  SYNTHESIS_UNICODE::[Design+Implementation]

  // Concatenation operator (~ normalized to U+29FA)
  // Source: lexer.py TokenType.CONCAT line 35, patterns lines 291-292
  CONCAT_ASCII::[First~Second]
  CONCAT_UNICODE::[Prefix~Suffix]

  // At operator (location/context)
  // Source: lexer.py TokenType.AT line 36, pattern line 293
  AT_LOCATION::[Function@Module]

  // Tension operator (vs/<-> normalized to U+21CC)
  // Source: lexer.py TokenType.TENSION line 38, patterns lines 287, 294-295
  TENSION_VS::[Speed vs Quality]
  TENSION_ASCII::[Fast<->Safe]
  TENSION_UNICODE::[Performance vs Security]

  // Constraint operator (& normalized to U+2227)
  // Source: lexer.py TokenType.CONSTRAINT line 39, patterns lines 298-299
  CONSTRAINT_ASCII::[Required&Validated]
  CONSTRAINT_UNICODE::[TypeA&TypeB&TypeC]

  // Alternative operator (| normalized to U+2228)
  // Source: lexer.py TokenType.ALTERNATIVE line 40, patterns lines 296-297
  ALTERNATIVE_ASCII::[OptionA|OptionB]
  ALTERNATIVE_UNICODE::[PathA|PathB|PathC]

#3::LISTS_AND_MAPS
  // Simple list
  // Source: parser.py parse_list() lines 1272-1406
  SIMPLE_LIST::[one, two, three]

  // Nested list
  NESTED_LIST::[[a, b], [c, d], [e, f]]

  // Inline map (key::value pairs within list)
  // Source: parser.py parse_list_item() lines 1408-1435
  INLINE_MAP::[name::Alice, age::30, active::true]

  // Mixed list
  MIXED_LIST::[42, "string", true, null, 1.5]

  // List with trailing comma (allowed)
  TRAILING_COMMA::[a, b, c,]

#4::BLOCKS_AND_NESTING
  // Block structure
  // Source: parser.py lines 784-883
  OUTER_BLOCK:
    INNER_KEY::inner_value
    NESTED_BLOCK:
      DEEP_KEY::deep_value
      DEEPER_BLOCK:
        DEEPEST_KEY::deepest_value

  // Block with target annotation [->TARGET]
  // Source: parser.py _parse_block_target_annotation() lines 333-384
  INHERITED_BLOCK[->PARENT]:
    CHILD_KEY::inherits_from_parent

#5::SECTION_REFERENCES
  // Section reference in value position
  // Source: parser.py lines 1227-1251
  TARGET_REF::#OPERATORS
  NUMBERED_REF::#1

#6::COLON_PATHS
  // Colon-separated path values
  // Source: parser.py lines 1134-1147
  MODULE_PATH::MODULE:SUBMODULE:COMPONENT
  NAMESPACE::HERMES:API_TIMEOUT

#7::COMMENTS
  // Leading comment for section
  KEY_WITH_COMMENT::value  // Trailing comment

// Multi-word bare values (coalesced per GH#66)
#8::MULTI_WORD
  MULTI_WORD_VALUE::Hello World Again
  MIXED_MULTI::Release 1.2.3 is ready

===END===
