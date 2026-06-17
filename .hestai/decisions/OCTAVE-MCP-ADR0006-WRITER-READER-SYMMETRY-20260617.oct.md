===DECISION_RECORD===
META:
  TYPE::DECISION_RECORD
  VERSION::"1.0"
  TOKEN::OCTAVE-MCP-ADR0006-WRITER-READER-SYMMETRY-20260617
  STATUS::RATIFIED
  TIER::STRATEGIC
  AUTHORED_AT::"2026-06-17T00:00:00Z"
  RATIFIED_BY::"human:operator"
  RATIFIED_AT::"2026-06-17T00:00:00Z"
  ISSUE_REF::"repo:octave-mcp#369"
  HUMAN_ADR_REF::"docs/adr/adr-0006-writer-reader-symmetry.md"
  SCOPE::"octave-mcp"
  DECISION::"Establish writer/reader symmetry: eliminate the octave_validate / octave_write asymmetry where content reported valid was then mangled or destructively canonicalised on write. Parent decision for the SR0/SR1/SR2 task family; shipped across v1.12.0-v1.13.1. Child tasks recorded as separate TACTICAL AGRs (SR1-T1 grammar core, SR2-T2 span audit, G3 META audit markers)."
  BECAUSE::"The asymmetry violated I1 (idempotent, bijective canon), I3 (mirror constraint) and I4 (transform auditability), forcing repeated repair cycles. Unifying the writer and reader retired North Star Risk R2 (validator drift). Backfilled as a RATIFIED AGR on 2026-06-17 with its previously-Proposed header corrected to match shipped reality. Per the 2026-06-17 holistic review."
===END===