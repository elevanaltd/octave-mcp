===DECISION_RECORD===
META:
  TYPE::DECISION_RECORD
  VERSION::"1.0"
  TOKEN::OCTAVE-MCP-ADR0001-CONFIGURABILITY-MODULARITY-20260617
  STATUS::PROPOSED
  TIER::STRATEGIC
  AUTHORED_AT::"2026-06-17T00:00:00Z"
  HUMAN_ADR_REF::"docs/adr/adr-0001-configurability-and-modularity-architecture.md"
  SCOPE::"octave-mcp"
  DECISION::"Adopt a configurability-and-modularity architecture so operators, schema formats, and tier behaviour are not hardcoded. Status PROPOSED: the principle is endorsed but only partially realised — operators remain hardcoded (src/octave_mcp/core/lexer.py ~135-169). Open decision: scope-down (accept current hardcoding as sufficient) or complete the configurability vision. Requires operator direction."
  BECAUSE::"The original assessment identified configurability as a structural goal, but implementation stopped partway. Recording it as a genuinely-open PROPOSED decision (not a frozen accepted one) makes the unfinished scope explicit and queryable rather than buried in a stale ADR header. Per the 2026-06-17 holistic review."
===END===