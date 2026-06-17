===DECISION_RECORD===
META:
  TYPE::DECISION_RECORD
  VERSION::"1.0"
  TOKEN::OCTAVE-MCP-ADOPTS-AGR-GOVERNANCE-20260617
  STATUS::RATIFIED
  TIER::STRATEGIC
  AUTHORED_AT::"2026-06-17T00:00:00Z"
  RATIFIED_BY::"human:operator"
  RATIFIED_AT::"2026-06-17T00:00:00Z"
  HUMAN_ADR_REF::"docs/2026-06-16-octave-holistic-review.md"
  SCOPE::"octave-mcp"
  DECISION::"OCTAVE-MCP adopts the hestai-context AGR DECISION_RECORD standard as its governance source of truth, stored under .hestai/decisions/ and authored via submit_governance. Historical ADRs in docs/adr/ are backfilled as DECISION_RECORD AGRs — RATIFIED for shipped decisions, PROPOSED for open ones — each linking to its long-form body via HUMAN_ADR_REF. Retroactive ratification of already-shipped ADRs by operator authority is an accepted governance norm for this one-time backfill."
  BECAUSE::"The repo CLAUDE.md section 4 already mandates decision-lookup discipline against this system, yet the decision store was empty and the ADRs were orphaned plain-markdown frozen at stale statuses (e.g. Proposed despite shipping in v1.12-v1.13). Adopting the AGR store applies OCTAVE's own I4 transform-auditability discipline to its own governance: STATUS lifecycle, supersession chains, and a queryable current-state surface via list_decisions. This formally establishes the backfill norm flagged by the semantic reviewer on the ADR-0004 pilot (PR #494). Per the 2026-06-17 holistic review."
===END===