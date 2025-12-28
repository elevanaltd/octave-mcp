===STRESS_TEST_REPORT===
META:
  TYPE::TEST_REPORT
  VERSION::"1.0"
  DATE::"2025-12-28"
  TESTER::claude-opus-4-5
  SCOPE::consolidated_tools_gh51

SUMMARY:
  TOOLS_TESTED::[octave_validate, octave_write, octave_eject]
  DEPRECATED_TESTED::[octave_ingest, octave_create, octave_amend]
  TOTAL_TESTS::32
  ISSUES_FOUND::7
  SEVERITY::[CRITICAL::2, MEDIUM::3, LOW::2]

CRITICAL_ISSUES:

  ISSUE_1:
    ID::OCTAVE-BUG-001
    GITHUB::"https://github.com/elevanaltd/octave-mcp/issues/62"
    TOOL::octave_validate
    SEVERITY::CRITICAL
    TITLE::"Unicode tension operator causes silent value truncation"
    DESCRIPTION::"Input with tension operator truncates value after operator"
    INPUT::"TENSION::Speed ⇌ Quality"
    OUTPUT::"TENSION::Speed"
    EXPECTED::"TENSION::\"Speed ⇌ Quality\""
    IMPACT::"Silent data loss - violates I1 (Syntactic Fidelity)"
    REPRODUCIBLE::true

  ISSUE_2:
    ID::OCTAVE-BUG-002
    GITHUB::"https://github.com/elevanaltd/octave-mcp/issues/63"
    TOOL::octave_validate
    SEVERITY::CRITICAL
    TITLE::"Triple quotes cause complete value loss"
    DESCRIPTION::"Triple-quoted strings lose all content"
    INPUT::"QUOTES::\"\"\"Triple quotes test\"\"\""
    OUTPUT::"QUOTES::\"\""
    EXPECTED::"QUOTES::\"Triple quotes test\""
    IMPACT::"Silent data loss - violates I1 (Syntactic Fidelity)"
    REPRODUCIBLE::true

MEDIUM_ISSUES:

  ISSUE_3:
    ID::OCTAVE-BUG-003
    GITHUB::"https://github.com/elevanaltd/octave-mcp/issues/65"
    TOOL::octave_validate
    SEVERITY::MEDIUM
    TITLE::"ASCII tension operator <-> not recognized"
    DESCRIPTION::"Tokenizer rejects <-> as unexpected character"
    INPUT::"TENSION::Speed <-> Quality"
    OUTPUT::E_TOKENIZE
    EXPECTED::"Should parse or normalize to ⇌"
    IMPACT::"Lenient parsing claim incomplete"
    REPRODUCIBLE::true

  ISSUE_4:
    ID::OCTAVE-BUG-004
    GITHUB::"https://github.com/elevanaltd/octave-mcp/issues/64"
    TOOL::octave_validate
    SEVERITY::MEDIUM
    TITLE::"Bare lines silently dropped without warning"
    DESCRIPTION::"Lines without :: assignment silently removed"
    INPUT::"MISSING_END (bare line after STATUS::ACTIVE)"
    OUTPUT::"Line removed, no warning"
    EXPECTED::"Warning about unparseable line"
    IMPACT::"Silent data loss without audit trail - violates I4"
    REPRODUCIBLE::true

  ISSUE_5:
    ID::OCTAVE-BUG-005
    GITHUB::"https://github.com/elevanaltd/octave-mcp/issues/66"
    TOOL::octave_eject
    SEVERITY::MEDIUM
    TITLE::"Markdown format truncates and malforms output"
    DESCRIPTION::"Multi-word values truncated, formatting broken"
    INPUT::"BODY::Main content"
    OUTPUT::"**BODY**: Main"
    EXPECTED::"**BODY**: Main content"
    IMPACT::"Data loss in markdown projection"
    REPRODUCIBLE::true

LOW_ISSUES:

  ISSUE_6:
    ID::OCTAVE-BUG-006
    TOOL::octave_validate
    SEVERITY::LOW
    TITLE::"Inline object syntax {{}} not supported"
    DESCRIPTION::"Double braces cause tokenization error"
    INPUT::"OBJ::{{key:value}}"
    OUTPUT::E_TOKENIZE
    EXPECTED::"Parse inline object or clear error message"
    IMPACT::"Feature gap vs octave-mastery skill documentation"
    REPRODUCIBLE::true

  ISSUE_7:
    ID::OCTAVE-BUG-007
    TOOL::octave_ingest
    SEVERITY::LOW
    TITLE::"Response envelope differs from octave_validate"
    DESCRIPTION::"Deprecated tool lacks status, errors, validation_status fields"
    MIGRATION_CONCERN::"Clients upgrading must handle different envelope shape"
    IMPACT::"Migration friction"
    REPRODUCIBLE::true

WORKING_CORRECTLY:

  OCTAVE_VALIDATE:
    PASSING::[
      "Simple documents parse correctly",
      "Lists parse and normalize correctly",
      "Deep nesting (5 levels) works",
      "Large lists (20 items) work",
      "Numeric types preserved (int, float, negative)",
      "Boolean case preserved",
      "Scientific notation converted to float",
      "Empty content creates INFERRED envelope",
      "Tabs correctly rejected with clear error",
      "No-envelope documents get envelope added",
      "ASCII -> operator normalized to unicode"
    ]

  OCTAVE_WRITE:
    PASSING::[
      "Content mode creates files correctly",
      "Changes mode updates existing files",
      "XOR validation rejects content+changes",
      "Path traversal (..) rejected",
      "Invalid extensions rejected",
      "CAS guard (base_hash) works",
      "Tri-state DELETE sentinel works",
      "Tri-state null value works",
      "Nonexistent file in changes mode rejected",
      "Atomic writes work correctly"
    ]

  OCTAVE_EJECT:
    PASSING::[
      "Canonical mode preserves all fields",
      "Executive mode filters to STATUS/RISKS/DECISIONS",
      "Developer mode filters to TESTS/CI/DEPS",
      "JSON format conversion works",
      "YAML format conversion works",
      "Template generation works",
      "Lossy flag correctly set",
      "Fields_omitted correctly reported",
      "Authoring mode normalizes whitespace"
    ]

  DEPRECATED_TOOLS:
    PASSING::[
      "octave_ingest parses correctly",
      "octave_create writes files",
      "octave_amend updates files"
    ]

SECURITY_VERIFICATION:
  PATH_TRAVERSAL::BLOCKED
  INVALID_EXTENSIONS::BLOCKED
  SYMLINKS::NOT_TESTED
  CAS_GUARD::WORKING
  TOCTOU::IMPLEMENTED

RECOMMENDATIONS:
  PRIORITY_1::"Fix silent data loss bugs (ISSUE_1, ISSUE_2, ISSUE_4, ISSUE_5)"
  PRIORITY_2::"Add <-> ASCII alias support (ISSUE_3)"
  PRIORITY_3::"Document response envelope changes for migration (ISSUE_7)"
  PRIORITY_4::"Consider inline object support or update skill docs (ISSUE_6)"

===END===
