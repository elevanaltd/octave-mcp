===DECISION_RECORD===
META:
  TYPE::DECISION_RECORD
  VERSION::"1.0"
  TOKEN::OCTAVE-MCP-ADR0004-TOOL-CONSOLIDATION-20260617
  STATUS::RATIFIED
  TIER::STRATEGIC
  AUTHORED_AT::"2026-06-17T00:00:00Z"
  RATIFIED_BY::"human:operator"
  RATIFIED_AT::"2026-06-17T00:00:00Z"
  ISSUE_REF::"repo:octave-mcp#51"
  HUMAN_ADR_REF::"docs/adr/adr-0004-tool-consolidation-design.md"
  SCOPE::"octave-mcp"
  DECISION::"Consolidate the OCTAVE-MCP tool surface from the original 4 tools (octave_ingest, octave_create, octave_amend, octave_eject) down to 3 (octave_validate, octave_write, octave_eject). Shipped in v1.12.0."
  BECAUSE::"The 4-tool suite created cognitive overhead and redundant functionality; the 3-tool API reduces cognitive load, enforces the North Star immutables through a smaller surface, and simplifies the developer experience. Backfilled as an AGR on 2026-06-17 to reconcile governance with shipped reality."
===END===