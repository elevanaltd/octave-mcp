# OCTAVE Holistic Review — Purpose, Triage & Forward Plan

**Date:** 2026-06-16 · **Author:** holistic-orchestrator (LOGOS) · **State:** v1.15.0, Production/Stable
**Inputs:** ADR audit (verified), 31-issue triage (verified), ho-liaison strategic consult
**Status:** ORCHESTRATION_DIRECTIVE — for operator approval

---

## 1. The diagnosis (what the rot actually is)

The operator sensed decay. It is **not** in the code (v1.15.0 stable, all 5 North Star immutables ENFORCED) and **not** in the vision (the three-zone / layered-fidelity North Star is still correct). The rot is **one structural gap in the governance stratum**:

> **OCTAVE is a loss-accounting system that gives every document a transform receipt (I4) — yet the project's own governance keeps no receipt.** There is no per-ADR `SHIPPED_IN` field and no single machine-readable CURRENT-STATE manifest declaring what is live. Headers are write-once and never reconciled against the CHANGELOG that implements them.

Every drift symptom is a child of that one gap. The fix is to **apply OCTAVE's own I4 discipline to OCTAVE.**

In a one-human + many-agent topology, the agents *are* the team. Prose ADR statuses fail because agents have no implicit temporal context — they cannot tell a frozen "Proposed" header from a live decision. A machine-readable current-state surface is therefore not over-engineering; it is the structural precondition for agents not to hallucinate project state. (ho-liaison: 90% recurrence probability without it.)

### 1b. The fix already exists and was never adopted (sharpened)

The recurrence fix is **not new infrastructure to build.** The HestAI `hestai-context` decision-record system already provides exactly the missing receipt:

- `submit_governance` — author a per-record decision (AGR) as validated OCTAVE, via prose or content, opened as a reviewed PR (no auto-merge). *This is OCTAVE applying its own I4 discipline to governance.*
- `list_decisions(status/tier/scope)` — the machine-readable **current-state surface** (replaces the "invent a CURRENT-STATE manifest" idea below).
- `lookup_decision(token)` + `trace_supersedure(token)` — resolve a decision and walk its supersession chain to terminal state.
- Schema (`decision_log.oct.md` v1.1) carries the exact fields whose absence caused the drift: **`STATUS`** lifecycle (BINDING/ACTIVE/SUPERSEDED_BY/DEPRECATED/ARCHIVED), **`SUPERSEDED_BY`/`SUPERSEDES`/`EXTENDS`/`AMENDS`** relationships, `ISSUE_REF`, `ENFORCEMENT_REF`, `CANONICAL` (pointer to long-form body), `EVIDENCE`, `DATE`.

**Verified:** this repo's own `CLAUDE.md §4` already *mandates* decision-lookup discipline against this system — yet `list_decisions` returns **0 records** and there is no `.hestai/decisions/` directory. OCTAVE-MCP's ADRs are orphaned plain-markdown in `docs/adr/`, entirely outside the governance system it tells its agents to consult. *That* is the root, stated precisely.

**What adopting it resolves:** status-lifecycle drift (no more frozen "Proposed"), supersession tracking (triage bucket B), and the queryable current-state anchor — all three, with no bespoke tooling.

**What it does NOT resolve (residual, handled separately):**
- *Release-version reconciliation* — the schema has no dedicated `SHIPPED_IN` field; STATUS is the live/dead proxy and the `EVIDENCE`/`ENFORCEMENT_REF` fields absorb "shipped in vX" informally. A structured `SHIPPED_IN` is a *nice-to-have* (queryable release-gating), **not** required — recommend deferring per MIP unless release automation needs it.
- *Capability / literacy live-state* (literacy §6: does `octave_fmt` exist? does `octave_write` canonicalise by default?) is runtime **capability** state, not a decision — needs its own small fix (see Wave 0.2), or a single CONVENTION-tier AGR anchoring it.
- *GitHub issue triage* — issues are not AGRs; that stays a GitHub workstream (§3b).

**Backfill discipline (`CLAUDE.md §4 PROMOTION`):** MIP — *no blanket backfill.* Do **not** mass-migrate all 11 ADRs. Adopt AGRs as the forward mechanism; backfill **only the hot/contested** decisions now (ADR-0005 genuinely-open, ADR-0001 partial). Shipped-and-settled ADRs just get their markdown `Status` header corrected (done in this commit) and are promoted to AGRs lazily, per-token, if/when they become load-bearing.

## 2. Purpose — the durable framing

Loss-accounting is the **mechanism**; cross-ecosystem interoperability is the **teleology**.

- **Mechanism (what it does today, keep enforcing):** OCTAVE is the *receipt layer for lossy LLM communication* — determinism + auditability of transforms. **Not "compression."** Compression is a side effect; the durable value is I1–I5.
- **Teleology (where it is going):** the EXPLORE cluster (epistemic operators, cross-ecosystem contract standard, multi-agent reconciliation) all point one direction — **a trust substrate for multi-agent semantic state.** If agents cannot account for semantic loss, they cannot trust each other's state. That is the larger purpose the organic growth has been groping toward.

This reframing changes nothing in v1.x scope — it clarifies *why* the HARDEN work matters (a trust substrate must be bulletproof before it can be a protocol) and *why* the EXPLORE cluster is real but premature.

## 3. Verified status tables

### 3a. ADRs (11 files, 8 logical decisions)

| ADR | Declared | Reality | Verdict | Action |
|---|---|---|---|---|
| 0001 Configurability | Proposed | Partial — operators hardcoded `lexer.py:135-169` | **GENUINELY_OPEN (partial)** | Scope-down-or-complete decision → tech-architect → operator |
| 0002 Schema validation | Accepted | Validator ships; holographic extraction partial | PARTIAL | Note residual gap; confirm Accepted |
| 0003 Generative contracts | Accepted | No impl evidence | UNKNOWN → verify | Confirm shipped-or-park |
| 0004 Tool consolidation | Accepted | Shipped v1.12.0 (3 tools) | MISSTATUSED | Mark Accepted + `SHIPPED_IN: v1.12.0` |
| **0005 Epistemic operators □◇⊥** | Proposed | **Never shipped** (grep: 0 hits); only #284 newline fix landed | **GENUINELY_OPEN** | **PARK under v2.0.0 gate (receipt, not limbo)** — see §5 |
| 0006 Writer/Reader Symmetry | Proposed | Shipped v1.12–v1.13.1 | MISSTATUSED | **Consolidate family → one Accepted ADR** |
| 0006-G3 META audit markers | Proposed | Shipped v1.13.0 (#419) | MISSTATUSED | Fold into 0006 as §G3 |
| 0006-SR1-T1 grammar core | Proposed | Shipped v1.12.0 | MISSTATUSED | Fold into 0006 as §SR1 |
| 0006-SR2-T2 span audit | Draft | Shipped v1.13.0–v1.13.1 (#418) | MISSTATUSED | Fold into 0006 as §SR2 |
| 0006-Sprint-2-Addendum | Proposed | Describes shipped v1.12–v1.14 plan | MISSTATUSED | **Archive** (coordination, not decision) |
| 0283 Chassis tiering | Approved | Format work done; impl belongs downstream | **CROSS_REPO** | Relocate to odyssean-anchor-mcp |

### 3b. Open issues (31) — triage

**(C) ALREADY-RESOLVED, verify & close (4):** #376 (format_style toggle, PR #378/#418), #384 (META admission, #419), #385 (HARD_SYMMETRY corpus, #419), #386 (W002 discriminant, #419).

**(B) SUPERSEDED:** none.

**(A) STILL-VALID — split by posture (27):**

*HARDEN / BUGFIX — bulletproof the v1.15 surface (priority order):*
- **Fidelity bugs (violate I1 round-trip):** #434 (emitter mangles backslash counts), #433 (lexer holographic recognition — target-only patterns mis-parse).
- **Writer safety:** #411 (surgical edits unsafe on inline-array top-level entries — defects 1 & 2 still open post-#418).
- **Validator fail-closed / parity (I5):** #480 (CLI resolves fewer schemas than API — false confidence), #441 (CI gate should use `octave_write --dry-run`), #435 (ENUM non-enforcement), #439 (SCHEMA_REQUIRED_EXCEPTIONS), #445 (section-bucket merging masks reqs), #448 (DECISION_LOG 68 conformance errors — calibration).
- **Integrity:** #365 (goose agents bypass octave_write via raw file-write).
- **Diff hygiene (cosmetic, lower):** #436 (diff wraps mid-content), #371 (single-key edits → whole-file diffs).
- **Evidence-gated:** #372 (W_DUPLICATE_TARGET migration sweep — scan first, close if 0 hits).
- **Epic:** #403 (annotation-content discipline — lint + calibration).
- **Deferred-but-valid build:** #377 (true preserve mode / deep changes-mode paths), #430 (#191 META schema into pre-parse pipeline).

*EXPLORE — future capability, gate on proven demand (v2.0.0 cluster):*
- #291 epistemic operators □◇⊥ (= ADR-0005), #260 scoped normalization, #153 stratified holography, #135 federation, #111 confidence scores, #318 cross-ecosystem contract standard, #317 multi-agent doc reconciliation.
- *Sprint-3-gated "DO NOT START" (keep gated):* #404, #405, #406 (reconciler-bridge graduation — depend on #377 default-flip).

*Cross-repo (not octave-mcp work):* #450 (odyssean-anchor anchor_commit CWD), #481 (`octave` console-script PATH collision — downstream tooling).

> **Seed correction:** the original review's "likely-resolved" list was unreliable — #365, #372, #377 are **still open**, not resolved. Only #376/#384/#385/#386 are genuinely resolved-but-open.

## 4. Posture: HARDEN now, EXPLORE later

v1.15 just landed a hard syntactic break (#487 changes-mode). Injecting language-level semantic evolution (epistemic operators) on top of an unsettled syntactic break risks adoption collapse (ho-liaison: 80% × critical). **Declare v1.x feature-complete for language semantics.** Route execution bandwidth to the HARDEN/BUGFIX cluster to make the I1–I5 foundation bug-free. Defer the entire EXPLORE cluster to a v2.0 line, gated on *proven ecosystem demand* — there is currently no evidence of practitioner pull for any of it.

## 5. Resolving the one real tension (ADR-0005)

The attached review wanted ADR-0005 sent to debate-hall for build-vs-abandon **now**. ho-liaison wanted **everything** v2.0 deferred. Both are half-right; the synthesis is the diagnosis itself:

> **PARK ADR-0005 under an explicit v2.0.0 gate with a recorded receipt — neither build nor abandon, and crucially not silent limbo.** "Parked, gated on demand" *is* a governance decision. Writing that receipt is the exact I4 discipline whose absence caused the drift. No debate-hall needed unless/until demand evidence arrives; then convene to decide build-vs-refine.

This honours the HARDEN posture (no v2.0 work now) while refusing the limbo the review correctly flagged.

## 6. Forward plan (waves, owners, lane)

> Lane note: this document is coordination. Decision records are authored via `submit_governance` (the correct tool for `.hestai/decisions/` records — not `octave_write`); plain-markdown ADR/doc reorg is done in-place directly.

**WAVE 0 — No-regrets governance cleanup (cheap, high-certainty, do first):**
1. **[DONE this commit]** Re-status the 5 misstatused ADR-0006-family headers (Proposed/Draft → Accepted + `Shipped:` line) so the human-readable layer matches reality. Long-form bodies stay in `docs/adr/`; no physical consolidation (the AGR `EXTENDS`/`SUPERSEDES` relationships model the family better than a merged file).
2. Fix `octave-literacy` §6: add a `LIVE_PHASE::TODAY` marker; correct the `AFTER_SR1_T4` row (it currently describes the unshipped SR3-T2 endstate; #407 shipped only a narrow byte-identity short-circuit). *Cross-repo — the skill is governed outside octave-mcp; route to the skills owner.*
3. **Adopt the existing `hestai-context` AGR decision store** as the forward source of truth (replaces the discarded "invent a manifest" idea). Per MIP/`CLAUDE.md §4` backfill **only** ADR-0005 and ADR-0001 now via `submit_governance`; settled ADRs promote lazily. `list_decisions(status=...)` becomes the queryable current-state surface. *This is the structural recurrence fix.*
4. Verify-close #376, #384, #385, #386. → implementation-lead (quick verify).
5. Relocate ADR-0283 → odyssean-anchor-mcp; file #450, #481 as cross-repo. → system-steward.

**WAVE 1 — HARDEN the v1.15 surface (the real engineering):**
- Fidelity first: #434, #433. Then writer safety: #411. Then validator fail-closed: #480, #441, #435, #439, #445, #448. Then integrity #365. Then diff hygiene #436, #371. Evidence-gate #372. → implementation-lead per issue, TDD mandatory, tier default/deep, quality gates per tier (T2: TMG⊕CRS⊕CE; T3 for security/MCP: +CIV).

**WAVE 2 — Decisions & parking (records, mostly):**
- Record ADR-0005 PARKED-v2.0.0 receipt (§5). → technical-architect → operator sign-off.
- ADR-0001 scope-down-or-complete decision. → technical-architect → operator.
- Stamp the v2.0.0 EXPLORE cluster (#291, #260, #153, #135, #111, #318, #317) with a uniform "parked: gated on demand" label and a one-line demand-trigger each. → system-steward.

**Recurrence guard (standing):** every release flips the `STATUS` of newly-shipped AGRs (and records supersessions) before tagging; `list_decisions(status=ACTIVE)` is the live-state read. I4 for governance.

## 7. One-line summary

> The code and vision are healthy; only the governance receipt-keeping drifted. The fix already exists and was never adopted: turn on the `hestai-context` AGR decision store (which this repo's CLAUDE.md already mandates), backfill only the hot decisions, correct the misstatused ADR headers, harden the v1.15 surface, and park — explicitly, with a receipt — all language-level evolution until ecosystem demand is proven.
