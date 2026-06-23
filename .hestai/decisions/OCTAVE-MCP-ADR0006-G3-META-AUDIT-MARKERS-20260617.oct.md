===DECISION_RECORD===
META:
  TYPE::DECISION_RECORD
  VERSION::"1.0"
  TOKEN::OCTAVE-MCP-ADR0006-G3-META-AUDIT-MARKERS-20260617
  STATUS::RATIFIED
  TIER::TACTICAL
  AUTHORED_AT::"2026-06-17T00:00:00Z"
  RATIFIED_BY::"human:operator"
  RATIFIED_AT::"2026-06-17T00:00:00Z"
  ISSUE_REF::"repo:octave-mcp#365"
  HUMAN_ADR_REF::"docs/adr/adr-0006-g3-meta-audit-markers.md"
  SCOPE::"octave-mcp"
  DECISION::"Define a META envelope schema-admission policy for audit markers (META.NON_CANONICAL_DEGRADED, META.DEGRADED_REGIONS) via closed-set META_AUDIT_ADMIT_PATTERNS, emitting an informational W_META_AUDIT warning. Child of OCTAVE-MCP-ADR0006-WRITER-READER-SYMMETRY-20260617 (SR2-T3 blocker). Shipped in v1.13.0 (PR #419)."
  BECAUSE::"Raw-ingest escape valves needed a principled admission path so degraded-content markers are recognised rather than rejected or silently dropped, preserving I2 (deterministic absence) and I4. Backfilled as a RATIFIED AGR on 2026-06-17. Per the 2026-06-17 holistic review."
===END===