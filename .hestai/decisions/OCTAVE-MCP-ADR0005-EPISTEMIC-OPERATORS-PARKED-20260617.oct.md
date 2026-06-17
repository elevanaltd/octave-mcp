===DECISION_RECORD===
META:
  TYPE::DECISION_RECORD
  VERSION::"1.0"
  TOKEN::OCTAVE-MCP-ADR0005-EPISTEMIC-OPERATORS-PARKED-20260617
  STATUS::PROPOSED
  TIER::STRATEGIC
  AUTHORED_AT::"2026-06-17T00:00:00Z"
  ISSUE_REF::"repo:octave-mcp#291"
  HUMAN_ADR_REF::"docs/adr/adr-0005-octave-v1.5-compiler-shift-operator-evolution.md"
  SCOPE::"octave-mcp"
  DECISION::"Proposed OCTAVE v1.5+ epistemic operators (box / diamond / bottom for assertion, possibility, contradiction) plus a SOURCE-to-STRICT compilation model. PARKED under a v2.0.0 gate: not built, not abandoned, gated on proven ecosystem demand. Only the trailing-newline fix (#284) from the original ADR shipped; the operators never did (grep: zero hits in src). Re-open for build-vs-refine via debate-hall when demand evidence arrives."
  BECAUSE::"v1.15 just landed a hard syntactic break (#487); injecting language-level semantic evolution now risks adoption collapse before the I1-I5 foundation is bulletproof. Recording an explicit PARKED receipt (rather than a silent frozen Proposed header) is itself the I4 governance discipline whose absence caused the drift this review diagnosed. Per the 2026-06-17 holistic review."
===END===