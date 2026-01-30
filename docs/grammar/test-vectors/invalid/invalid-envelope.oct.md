===my-document===
META:
  TYPE::TEST_VECTOR
  PURPOSE::"Should fail with E_INVALID_ENVELOPE_ID - hyphen in envelope identifier"
  EXPECTED_ERROR::E_INVALID_ENVELOPE_ID

---

// This file has an invalid envelope identifier (contains hyphen)
// Source: lexer.py _check_invalid_envelope() lines 337-414
// Valid pattern: [A-Za-z_][A-Za-z0-9_]*
// Error: "Envelope identifier 'my-document' contains invalid character hyphen '-'.
//         Use underscores or CamelCase instead"

CONTENT::value

===END===
