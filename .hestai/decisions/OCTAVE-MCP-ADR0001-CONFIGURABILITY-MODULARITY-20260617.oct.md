===DECISION_RECORD===
META:
  TYPE::DECISION_RECORD
  VERSION::"1.0"
  TOKEN::OCTAVE-MCP-ADR0001-CONFIGURABILITY-MODULARITY-20260617
  STATUS::RATIFIED
  TIER::STRATEGIC
  AUTHORED_AT::"2026-06-17T00:00:00Z"
  RATIFIED_BY::"human:operator"
  RATIFIED_AT::"2026-06-17T00:00:00Z"
  HUMAN_ADR_REF::"docs/adr/adr-0001-configurability-and-modularity-architecture.md"
  SCOPE::"octave-mcp"
  DECISION::"Scope the configurability-and-modularity architecture to the CURRENT implementation. The hardcoded operators in src/octave_mcp/core/lexer.py are accepted as sufficient; no further configurability work (operator/schema/tier parameterisation) is pursued at this time. Resolved 2026-06-17 by operator: scope-down, do not complete the broader vision."
  BECAUSE::"The configurability vision was only partially realised and there is no current demand justifying the added complexity (MIP — subtract until it breaks). Closing the decision as scope-down keeps the system simple and removes the open-question overhang; re-open only if a concrete need for runtime configurability emerges. Per the 2026-06-17 holistic review."
===END===