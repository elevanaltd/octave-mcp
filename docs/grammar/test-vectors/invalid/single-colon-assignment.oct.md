===SINGLE_COLON===
META:
  TYPE::TEST_VECTOR
  PURPOSE::"Should fail with E001 - single colon used for assignment"
  EXPECTED_ERROR::E001

---

// This file uses single colon for assignment which should trigger E001
// Source: parser.py lines 788-798
// Error: "Single colon assignment detected: 'KEY: value'.
//         OCTAVE REQUIREMENT: Use 'KEY::value' (double colon) for assignments.
//         Single colon ':' is reserved for block definitions only."

WRONG_ASSIGNMENT: value

// The line above uses single colon instead of double colon
// Parser should reject this with E001

===END===
