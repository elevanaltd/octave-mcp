===DECISION_RECORD===
META:
  TYPE::DECISION_RECORD
  VERSION::"1.0"
  TOKEN::OCTAVE-MCP-ADR0002-SCHEMA-VALIDATION-HOLOGRAPHIC-20260617
  STATUS::RATIFIED
  TIER::STRATEGIC
  AUTHORED_AT::"2026-06-17T00:00:00Z"
  RATIFIED_BY::"human:operator"
  RATIFIED_AT::"2026-06-17T00:00:00Z"
  HUMAN_ADR_REF::"docs/adr/adr-0002-schema-validation-using-octave-holographic-patterns.md"
  SCOPE::"octave-mcp"
  DECISION::"Implement schema validation using OCTAVE holographic patterns, replacing the prior validation stub (Validator(schema=None)) identified as a P0 enforcement gap. The validation machinery shipped in v1.12.0. Residual: holographic pattern extraction is not yet fully realised per the original design."
  BECAUSE::"The server could parse and emit OCTAVE but could not validate document structure against schema requirements, leaving I5 (schema sovereignty) unenforceable. Holographic patterns let schemas be expressed in OCTAVE itself. Backfilled as a RATIFIED AGR on 2026-06-17 with the residual extraction gap noted. Per the 2026-06-17 holistic review."
===END===