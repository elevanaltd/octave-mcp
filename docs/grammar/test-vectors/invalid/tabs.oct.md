===TABS_ERROR===
META:
  TYPE::TEST_VECTOR
  PURPOSE::"Should fail with E005 - tabs not allowed"
  EXPECTED_ERROR::E005

---

// This file contains a tab character which should trigger E005
// Source: lexer.py lines 435-438
// Error: "Tabs are not allowed. Use 2 spaces for indentation."

BLOCK:
	TAB_INDENTED::value

// The line above uses a tab character instead of spaces
// Parser should reject this with E005

===END===
