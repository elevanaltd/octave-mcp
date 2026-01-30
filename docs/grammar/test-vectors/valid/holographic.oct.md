===HOLOGRAPHIC===
META:
  TYPE::TEST_VECTOR
  VERSION::"1.0.0"
  PURPOSE::"Validates holographic pattern syntax per parser.py _try_parse_holographic()"
  REFERENCE::"parser.py lines 1579-1632, holographic.py"
  CONTRACT::HOLOGRAPHIC[SELF_VALIDATING]

---

// Holographic patterns: ["example"&CONSTRAINT->#TARGET]
// Detection: CONSTRAINT token present, no commas at depth=1
// Source: parser.py _try_parse_holographic() lines 1579-1632

#1::BASIC_HOLOGRAPHIC
  // Simple required field
  REQUIRED_FIELD::["example_value"&REQ]

  // Optional field
  OPTIONAL_FIELD::["default"&OPT]

  // Constant field (immutable)
  CONSTANT_FIELD::["fixed_value"&CONST]

  // Directory field
  DIR_FIELD::["./path/to/dir"&DIR]

  // Append-only field
  APPEND_FIELD::["initial"&APPEND_ONLY]

#2::TYPED_CONSTRAINTS
  // Type constraint
  STRING_FIELD::["text"&TYPE[STRING]]
  NUMBER_FIELD::[42&TYPE[NUMBER]]
  BOOL_FIELD::[true&TYPE[BOOLEAN]]
  LIST_FIELD::[[a,b]&TYPE[LIST]]

#3::ENUM_CONSTRAINTS
  // Enumerated values
  STATUS::["PENDING"&ENUM[PENDING,ACTIVE,COMPLETE]]
  PRIORITY::["HIGH"&ENUM[LOW,MEDIUM,HIGH,CRITICAL]]
  COLOR::["RED"&ENUM[RED,GREEN,BLUE]]

#4::VALIDATION_CONSTRAINTS
  // Regex pattern
  EMAIL::["user@example.com"&REGEX["^[a-z]+@[a-z]+\\.[a-z]+$"]]

  // Range constraint (numeric bounds)
  PERCENTAGE::[50&RANGE[0,100]]
  RATING::[4&RANGE[1,5]]

  // Length constraints
  SHORT_TEXT::["Hi"&MAX_LENGTH[10]]
  LONG_TEXT::["Minimum content"&MIN_LENGTH[5]]

#5::DATE_CONSTRAINTS
  // Date format (YYYY-MM-DD)
  CREATED_DATE::["2026-01-30"&DATE]

  // ISO 8601 datetime
  TIMESTAMP::["2026-01-30T13:00:00Z"&ISO8601]

#6::COMBINED_CONSTRAINTS
  // Multiple constraints combined with &
  REQUIRED_STRING::["value"&REQ&TYPE[STRING]]
  BOUNDED_NUMBER::[50&REQ&RANGE[0,100]]
  ENUM_REQUIRED::["ACTIVE"&REQ&ENUM[ACTIVE,INACTIVE]]
  VALIDATED_TEXT::["email@test.com"&REQ&REGEX[".*@.*"]]

#7::TARGETED_HOLOGRAPHIC
  // Holographic with target section reference
  // Grammar: ["example"&CONSTRAINT->#TARGET]
  WITH_TARGET::["value"&REQ->#VALIDATION]
  CROSS_REF::["data"&TYPE[STRING]->#OUTPUT]
  NUMBERED_TARGET::[42&RANGE[0,100]->#1]

#8::NESTED_BRACKET_CONSTRAINTS
  // Constraints with brackets inside (ENUM, REGEX, TYPE, etc.)
  COMPLEX_ENUM::["A"&ENUM[A,B,C]&REQ]
  TYPED_RANGE::[100&TYPE[NUMBER]&RANGE[0,1000]]
  MULTI_VALIDATION::["test"&TYPE[STRING]&MAX_LENGTH[50]&MIN_LENGTH[1]]

#9::HOLOGRAPHIC_IN_CONTEXT
  // Holographic patterns within larger structures
  SCHEMA:
    ID::["uuid-here"&REQ&TYPE[STRING]]
    NAME::["Example"&REQ&MAX_LENGTH[100]]
    COUNT::[0&OPT&RANGE[0,999]]
    STATUS::["DRAFT"&ENUM[DRAFT,PUBLISHED,ARCHIVED]]
    CREATED::["2026-01-30"&REQ&DATE]

===END===
