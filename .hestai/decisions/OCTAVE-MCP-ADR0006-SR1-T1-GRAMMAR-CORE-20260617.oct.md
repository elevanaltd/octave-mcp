===DECISION_RECORD===
META:
  TYPE::DECISION_RECORD
  VERSION::"1.0"
  TOKEN::OCTAVE-MCP-ADR0006-SR1-T1-GRAMMAR-CORE-20260617
  STATUS::RATIFIED
  TIER::TACTICAL
  AUTHORED_AT::"2026-06-17T00:00:00Z"
  RATIFIED_BY::"human:operator"
  RATIFIED_AT::"2026-06-17T00:00:00Z"
  ISSUE_REF::"repo:octave-mcp#382"
  HUMAN_ADR_REF::"docs/adr/adr-0006-sr1-t1-grammar-core-design.md"
  SCOPE::"octave-mcp"
  DECISION::"Unify the grammar core so a single grammar drives both validate and write, removing divergent parse paths. Child of OCTAVE-MCP-ADR0006-WRITER-READER-SYMMETRY-20260617. Six migration steps shipped in v1.12.0 (PRs #393-#401). META-side was_quoted population explicitly deferred to Sprint 3+ (issues #404/#405/#406)."
  BECAUSE::"Multiple validators / parse paths were the root of writer-reader asymmetry and North Star Risk R2 (validator drift); a single grammar core retires that risk. Backfilled as a RATIFIED AGR on 2026-06-17 with its in-progress header corrected to shipped. Per the 2026-06-17 holistic review."
===END===