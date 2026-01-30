===UNBALANCED_BRACKETS===
META:
  TYPE::TEST_VECTOR
  PURPOSE::"Should fail with E_UNBALANCED_BRACKET - missing closing bracket"
  EXPECTED_ERROR::E_UNBALANCED_BRACKET

---

// This file has an unclosed bracket which should trigger E_UNBALANCED_BRACKET
// Source: lexer.py lines 720-728
// Error: "opening '[' at line X, column Y has no matching ']'"

UNCLOSED_LIST::[a, b, c

// The line above is missing the closing bracket
// Lexer should reject this with E_UNBALANCED_BRACKET

===END===
