===DECISION_RECORD===
META:
  TYPE::DECISION_RECORD
  VERSION::"1.0"
  TOKEN::OCTAVE-MCP-ADR0006-SR2-T2-SPAN-AUDIT-20260617
  STATUS::RATIFIED
  TIER::TACTICAL
  AUTHORED_AT::"2026-06-17T00:00:00Z"
  RATIFIED_BY::"human:operator"
  RATIFIED_AT::"2026-06-17T00:00:00Z"
  ISSUE_REF::"repo:octave-mcp#377"
  HUMAN_ADR_REF::"docs/adr/adr-0006-sr2-t2-ast-span-coverage-audit.md"
  SCOPE::"octave-mcp"
  DECISION::"Adopt Strategy A (AST source-span coverage audit: per-key dirty tracking plus byte-splice emitter) for GH#377, so single-key edits preserve untouched bytes verbatim. Child of OCTAVE-MCP-ADR0006-WRITER-READER-SYMMETRY-20260617. Shipped across v1.13.0-v1.13.1 (PR #418). Dirty-path precision logging and reconciler-bridge graduation remain Sprint 3+ (issues #404/#405/#406)."
  BECAUSE::"Whole-document canonicalisation on minor edits violated I1 round-trip fidelity and harmed review/merge ergonomics; span-accurate splicing preserves bytes and the audit trail (I4). Backfilled as a RATIFIED AGR on 2026-06-17 with its DRAFT header corrected to shipped. Per the 2026-06-17 holistic review."
===END===