# ADR-0006 SR1-T1: Unified Grammar Core — Design Pass

**Status:** Proposed (design-only; implementation in progress — Steps 1, 2 merged)
**Date:** 2026-05-09 (original) · **Updated:** 2026-05-11 (cubic P2 resolution — see §3a "Reconciler bridge pattern")
**Version:** 1.2 (semver: patch — clarifies internal inconsistency between §3a class-2 dependency schedule and §4.3 xfail-flip schedule; no architectural change)
**Parent:** [ADR-0006 Writer/Reader Symmetry](./adr-0006-writer-reader-symmetry.md) §70-84
**Tracks:** GH#382 (SR1-T1)
**Retires:** North Star Risk **R2** — `validator_drift_multiple_validators`
**Out of scope (separate IL agents):** SR1-T2 (#372 W_DUPLICATE_TARGET hard-fail), SR1-T3 (#369 path-resolver), SR1-T4 (no-op normalize default), Sprint 3 cursor-CST.

**Changelog:**
- **1.2 (2026-05-11):** Resolve internal inconsistency identified by cubic AI (PR #396 review id `4263620972`): the §3a class-2 (blank-line stripping) and class-3 (triple-quote collapse) rows say structural support is not delivered until Sprint 3+ / future lexer W-code, yet §4.3 claimed all 10 xfails flip at logical-Step 3. Clarified that 8 fixtures flip via **precise `was_quoted`-based instrumentation** enabled by logical-Step 5, and 2 fixtures (`spec_full.oct.md`, `empty_triple_quoted.oct.md`) flip via a **reconciler bridge** in `mcp/write.py` — a temporary, self-deprecating mechanism that goes dormant when trivia population (Sprint 3+) and a new triple-quote lexer W-code (separate task) land.
- **1.1 (2026-05-11):** Re-sequence migration steps after IL empirical audit (permit SID `4fa2f2f1-85ff-4cfc-89c6-206ab9f8b048`) surfaced that the original Step 3 (TIER_NORMALIZATION centralisation) could not flip the 10 audit-cardinality xfails until structural fields reserved by the original Step 4 (CST promotion) and populated by the original Step 5 (emitter rewrite + `was_quoted`) had landed. Step IDs remain stable; execution order becomes 1 → 2 → 4 → 5 → 3 → 6. See new §3a for full rationale.
- **1.0 (2026-05-09):** Original design pass.

---

## 1. Problem statement

ADR-0006 §23 named the proximate defect: `octave_validate` and `octave_write` execute *different* normalisation paths. Sprint 0 (PR #383) made the asymmetry observable via the HARD_SYMMETRY suite and patched the worst W002 case, but the underlying drift remains: grammar knowledge is **distributed across at least five modules**, each with its own implicit grammar contract. SR1-T1 must collapse this into a single source of truth so the third HARD_SYMMETRY conjunct (`corrections non-empty IFF diff_unified non-empty`) holds without per-fixture xfails.

### 1.1 Where grammar knowledge lives today

Catalogue with `file:line` evidence (verified against branch `octave-format-optimization` at HEAD `22df280`):

| # | Module | Grammar concern | Evidence |
|---|--------|-----------------|----------|
| 1 | `src/octave_mcp/core/lexer.py` | Token rules, ASCII→Unicode aliases, W002 destructive-repair guard, identifier regex with embedded `#` and `://` carve-outs | `lexer.py:99-108` `ASCII_ALIASES`; `lexer.py:1003,1023,1193-1203` context-aware `#` and URL-scheme handling; `lexer.py:805` `tokenize(content, lenient=False)` |
| 2 | `src/octave_mcp/core/parser.py` | Envelope inference, whitespace tolerance around `::`, indent-block discipline, deep-nesting thresholds, YAML frontmatter strip, holographic context | `parser.py:32-34` `DEFAULT_DEEP_NESTING_THRESHOLD=5`, `MAX_NESTING_DEPTH=100`; `parser.py:37-100` `_strip_yaml_frontmatter`; `parser.py:512` `parse_document`; `parser.py:823` "Expected `::` after §" |
| 3 | `src/octave_mcp/core/emitter.py` | Identifier-shape regex (re-derived, not reused from lexer), expression-pattern regex, always-quote keys, FormatOptions normalisation switches | `emitter.py:74` `IDENTIFIER_PATTERN` *(re-derived from lexer rules — drift surface)*; `emitter.py:80` `ANNOTATION_PATTERN`; `emitter.py:86` `_ALWAYS_QUOTE_KEYS`; `emitter.py:97-100` `EXPRESSION_PATTERN`; `emitter.py:42-69` `FormatOptions` (indent/blank/whitespace/sort/strip-comments) |
| 4 | `src/octave_mcp/core/validator.py` | Schema-vs-AST rules, target routing, policy enforcement, `_count_literal_zones`, module-level `validate()` AND class `Validator.validate()` | `validator.py:73` `class Validator`; `validator.py:104` `Validator.validate`; `validator.py:578` module-level `validate()`; `validator.py:599` `validate_frontmatter()` |
| 5 | `src/octave_mcp/core/repair.py` | Tier classification (NORMALIZATION/REPAIR/FORBIDDEN), enum-casefold, type-coercion, schema-driven AST mutation | `repair.py:29` `repair_value`; `repair.py:233` `repair`; `repair.py:255-257` *"TIER_NORMALIZATION: Always applied (already handled by lexer/parser)"* — comment admits the tier lives in two places |
| 6 | `src/octave_mcp/core/schema.py` | Thin delegator wrapping `validator.py:578` | `schema.py:29-45` `validate(...)` → `validate_impl` *(low drift risk — included for completeness)* |
| 7 | `src/octave_mcp/core/grammar.py` | **Name collision.** Currently the GBNF compiler entry, NOT a parse front-door. ADR §72 prescribes `core/grammar.py` `parse(source, *, lenient=False) -> CST` — this name is already taken. | `grammar.py:16-34` `compile_document_grammar`; `grammar.py:37-51` `emit_grammar_for_schema` |
| 8 | `src/octave_mcp/core/repair_log.py` | `is_destructive_normalization_repair()` discriminant — recently centralised by PR #383 follow-up `e16a728` | `repair_log.py:8` |
| 9 | `docs/grammar/octave-v1.0-grammar.ebnf` | Spec-of-record EBNF — informational, not consulted at runtime | exists; not imported by any `core/` module (verified by grep) |

### 1.2 Concrete drift evidence

Three drift surfaces, in increasing severity:

**D1 — Identifier-shape drift (silent).** `emitter.py:74` `IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-]*(?<!-)\Z")` is re-derived from lexer rules; the inline GH#299 comment admits "Include hyphens to match lexer's `_is_valid_identifier_char` which allows `-`." The lexer extends identifiers with mid-value `#` (`lexer.py:497,1003,1371`) and `://` carve-outs (`lexer.py:1023`); the emitter's regex does not encode those carve-outs. A token tokenised as one identifier may fail the emitter's `IDENTIFIER_PATTERN` round-trip and be requoted on emit, producing a parse-equal but byte-different output that the corrections log does NOT record (this is the audit-cardinality breach behind the nine xfails in `tests/unit/test_writer_reader_symmetry.py:71-83`).

**D2 — Tier-NORMALIZATION ownership ambiguity (audit hole).** `repair.py:255-257` declares "TIER_NORMALIZATION: Always applied (already handled by lexer/parser). These are logged during parsing." But ASCII→Unicode logging happens in `lexer.py` (W002 path); whitespace-around-`::` normalisation happens in `parser.py` (per docstring `parser.py:7`); `emitter.py` re-applies blank-line + trailing-whitespace normalisation via `FormatOptions` (`emitter.py:691-696`) without writing to any `RepairLog`. Three modules touch TIER_NORMALIZATION; only one logs. This directly violates I4 (TRANSFORM_AUDITABILITY) and is the structural cause of the SR1-T4 xfail set.

**D3 — Validator surface duplication (R2 named risk).** `validator.py` exposes both `class Validator` (stateful) and a module-level `validate()` function (stateless); `schema.py:29` adds a third call signature; `mcp/validate.py:25` and `mcp/write.py:45` import different subsets. Each call site has subtly different default behaviour (e.g. `mcp/validate.py:10` describes pipeline `PARSE -> NORMALIZE -> VALIDATE -> REPAIR(if fix) -> EMIT` while `mcp/write.py` always re-emits canonical bytes regardless). PR #383's HARD_SYMMETRY suite quantifies the gap as 9 xfailed fixtures.

### 1.3 Why this is now actionable

PR #383 delivered (a) the HARD_SYMMETRY suite as a fence, (b) the W002 destructive-repair guard centralised in `repair_log.py:8`, and (c) the xfail set as a closed enumeration of remaining drift. The xfails are the test-side proof that the design proposed below is necessary and sufficient.

---

## 2. Recommended architecture

**Recommendation: Option (C) — Concrete Syntax Tree with shared visitor interfaces, fronted by a single `parse()` entry.**

### 2.1 Rationale (keyed to ADR-0006 invariants and Sprint 3 trajectory)

| Concern | Option (A) EBNF→combinators | Option (B) schema-codegen | **Option (C) shared CST + visitors** | Option (D) other |
|---------|------------------------------|---------------------------|---------------------------------------|------------------|
| I1 SYNTACTIC_FIDELITY (idempotent ⊕ bijective canon) | Forces a rewrite of lexer hand-tuned `#`/`://` carve-outs (D1 risk) | Codegen brittle against literal-zone `LiteralZoneValue` exemptions | Reuses existing lexer; bijectivity gained by single tree representation | n/a |
| I3 MIRROR_CONSTRAINT (reflect only present) | n/a — combinators are neutral | Risk: codegen may "helpfully" emit defaulted fields | CST nodes carry `Absent` sentinel directly (`ast_nodes.py:16-66`) | n/a |
| I4 TRANSFORM_AUDITABILITY | Logging must be re-bolted onto every combinator | Codegen would have to thread `RepairLog` through every emitted method | Visitors take `RepairLog` as constructor arg → single audit surface | n/a |
| Sprint 3 cursor-CST trajectory (ADR §96-104) | Combinators don't carry source spans naturally | Codegen unrelated to span tracking | **Direct foreshadowing — Sprint 3 just adds `(start_offset, end_offset, source_hash)` to existing CST nodes** | n/a |
| HEPHAESTUS forge-cost (mip-architecture SIMPLIFICATION_TEST) | High — ~6.5kloc rewrite | Highest — toolchain + codegen + new build step | **Lowest — promote `ast_nodes.py` to CST status, write three visitor protocols, retarget call sites** | n/a |
| ATLAS coherence across 7-module core | Combinators silo lexer concerns | Codegen forks runtime from spec | One tree consumed by all four pipelines | n/a |

Option (C) is the only choice that **subtracts** rather than adds: it deletes the duplicate validate signatures (D3), centralises tier-NORMALIZATION logging (D2), and makes the emitter's regex re-derivation (D1) impossible by construction (the emitter walks the same tree the lexer produced, so identifier shape is a property of the node, not a re-checked regex).

### 2.2 Module boundaries (post-unification)

```
src/octave_mcp/core/
├── grammar/                          # NEW PACKAGE (resolves naming collision)
│   ├── __init__.py                   # Re-exports parse, emit, validate, repair
│   ├── entry.py                      # parse(source, *, lenient=False) -> CST
│   │                                 #   Single front-door used by mcp/validate.py
│   │                                 #   AND mcp/write.py. Owns RepairLog lifecycle.
│   ├── cst.py                        # Promoted ast_nodes.py — adds NodeKind enum,
│   │                                 #   visitor protocol, Absent sentinel, optional
│   │                                 #   span fields (None until Sprint 3 lands them).
│   ├── visitor.py                    # Visitor[T] protocol; SymmetricVisitor mixin
│   │                                 #   that asserts emit-after-parse round-trip in
│   │                                 #   debug builds.
│   └── tier_normalize.py             # Centralised TIER_NORMALIZATION logger.
│                                     #   ALL ascii→unicode, whitespace, blank-line,
│                                     #   identifier-quoting decisions log here.
│                                     #   Lexer + parser + emitter import & call.
├── lexer.py                          # Unchanged tokeniser; gains a thin shim that
│                                     #   routes its repair events through
│                                     #   tier_normalize.log_repair() instead of a
│                                     #   private list.
├── parser.py                         # Unchanged AST construction; same shim.
├── emitter.py                        # Loses IDENTIFIER_PATTERN, ANNOTATION_PATTERN,
│                                     #   EXPRESSION_PATTERN re-derivations. Becomes
│                                     #   a CST visitor whose dispatch matches the
│                                     #   NodeKind discriminant from cst.py.
├── validator.py                      # Loses module-level validate(); only
│                                     #   class Validator(visitor.Visitor[None])
│                                     #   remains. validate_frontmatter() moves to
│                                     #   grammar/entry.py as a parse stage.
├── repair.py                         # Unchanged TIER_REPAIR semantics; binds to
│                                     #   tier_normalize.log_repair() for audit.
├── repair_log.py                     # Unchanged. is_destructive_normalization_repair
│                                     #   becomes the CST emitter's veto predicate.
├── schema.py                         # DELETED — was thin delegator (schema.py:29-45);
│                                     #   single canonical validate() in validator.py.
└── grammar_compiler/                 # RENAMED from grammar.py (resolves collision).
    ├── __init__.py
    └── gbnf.py                       # The existing GBNF compiler entry points.

src/octave_mcp/mcp/
├── validate.py                       # Imports octave_mcp.core.grammar.parse
│                                     #   and octave_mcp.core.grammar.validate.
│                                     #   No direct lexer/parser imports.
└── write.py                          # Same. Loses its private import set
                                     #   (write.py:36-46 — six core imports → one).
```

### 2.3 Why a `grammar/` package, not a flat `grammar.py`

ADR §72 specified `core/grammar.py`, but `core/grammar.py` already exists as the GBNF compiler entry (`grammar.py:16-51`). Two equally bad options:

- **Rename existing grammar.py to gbnf.py** — touches all GBNF callers (~12 import sites surveyed via grep), high blast radius, breaches AUTHORITY_BLOCKING[Production_impact_decisions] for an SR1 deliverable.
- **Use grammar/ as a package** — preserves `from octave_mcp.core.grammar import parse` per ADR §73, sequesters the existing GBNF compiler under `grammar_compiler/` (a more accurate name), and lets the package boundary make the visitor protocol the single export surface.

The package option is the SIMPLIFICATION_TEST winner: the GBNF compiler was always misnamed (it doesn't define grammar; it compiles META schemas to llama.cpp's GBNF format), and renaming it `grammar_compiler/` is a documentation fix, not an architectural one.

---

## 3. Migration plan

Each step is a bounded PR. None of them require touching SR1-T2 (#372), SR1-T3 (#369), or SR1-T4 (no-op default) — those land in parallel under separate IL delegations.

| # | PR scope | Touches | Risk | HARD_SYMMETRY effect |
|---|----------|---------|------|----------------------|
| 1 | **Rename `core/grammar.py` → `core/grammar_compiler/gbnf.py`** with re-export shim. Pure refactor; no behaviour change. | ~12 import sites (`mcp/compile_grammar.py`, `mcp/grammar_resources.py`, tests) | Low — covered by import-graph tests. | No effect (no parse path touched). |
| 2 | **Create `core/grammar/` package** with `entry.py::parse()` as a thin wrapper that calls `lexer.tokenize()` then `parser.parse()` and returns the existing AST cast as CST. | New package only; `mcp/validate.py` and `mcp/write.py` switch their `from octave_mcp.core.parser import parse` to `from octave_mcp.core.grammar import parse`. | Low — wrapper is identity. | No effect (same pipeline). |
| 3 | **Centralise TIER_NORMALIZATION logging in `core/grammar/tier_normalize.py`**. Lexer's W002 path + parser's whitespace normalisation + emitter's `FormatOptions` strip/blank-line repairs all emit through one `log_repair()` call. **Per 2026-05-11 re-sequence (§3a), this step now executes AFTER Steps 4 and 5** so the emitter has access to `was_quoted` and reserved trivia fields for precise instrumentation. | `core/grammar/tier_normalize.py` (new), `lexer.py`, `parser.py`, `emitter.py`, `repair.py`, **plus additive wiring in `src/octave_mcp/mcp/write.py` to consume `RepairLog` tier_normalize entries into the `corrections` list (pre-authorised scope expansion per 2026-05-11 user decision; mirrors the existing schema-repair loop at `write.py:3640`)**. | Medium — every TIER_NORMALIZATION event now appears in `RepairLog`. **This is the step that flips the audit-cardinality xfails (10 total: 9 original + 1 added by #385).** | Flips xfail set 1 (see §4). |
| 4 | **Promote `ast_nodes.py` to `core/grammar/cst.py`** with `NodeKind` enum and visitor protocol. Existing dataclasses unchanged; Section/Block/Assignment/Document gain `kind: NodeKind` field defaulted from `__class_getitem__`. **Reserve fidelity-preservation field shapes on the base node (defaulted `None`):** `leading_trivia: Optional[str] = None`, `trailing_trivia: Optional[str] = None`, `was_quoted: Optional[bool] = None`. Population is deferred to Sprint 3 / future steps; reserving the slots now prevents a second schema migration touching every node and every visitor signature. See §4.5 for rationale. | `ast_nodes.py` → moved; ~30 import sites rewritten by ruff codemod. | Medium — broad import churn; mypy gates catch breakage. | No effect (structural only). |
| 5 | **Rewrite emitter as CST visitor**. Transition identifier/annotation/expression shape handling from `IDENTIFIER_PATTERN`, `ANNOTATION_PATTERN`, and `EXPRESSION_PATTERN` to CST metadata (`node.kind` + `node.was_quoted`). `node.kind` is a structural marker (Assignment/Block/String/Identifier), NOT a presentation-aware quoting decision; `was_quoted` is what prevents `KEY::"42"` (string) from re-emitting as `KEY::42` (integer) on round-trip — direct I1 type-fidelity guard. Keep a temporary regex fallback ONLY while `was_quoted` may be `None`, and delete the heuristic in the same PR that guarantees lexer/parser population (either folded into Step 5 scope, or sequenced as Step 4.5 if scope dictates separation). Identifier-shape decisions become single-sourced once fallback is removed. See §4.5. | `emitter.py` only (plus lexer/parser instrumentation if folded in). | Medium-high — emitter is hot path; rely on existing 2788-test gate + HARD_SYMMETRY. | Should not regress; may flip 1-2 additional fixtures. |
| 6 | **Collapse validator surface**. Delete `core/schema.py`; delete module-level `validate()` in `validator.py`; promote `class Validator` to `visitor.Visitor[None]`; move `validate_frontmatter()` into `grammar/entry.py` as a parse-stage hook. | `validator.py`, `schema.py` (delete), `mcp/validate.py`, `mcp/write.py`, ~8 internal call sites. | High — biggest blast radius. Land last. CE review mandatory per AUTHORITY_MANDATE. | Closes R2 (named risk). |

**Sequencing rationale (amended 2026-05-11; superseded by §3a):**

> **Original (1.0) rationale, preserved for audit trail:** Steps 1-2 are pure refactor (no semantics change) — land first to establish the package skeleton. Step 3 is the **load-bearing audit-completeness fix** that flips the xfail set; it must land before SR1-T4 because T4 (no-op normalize default) depends on knowing what "no repairs occurred" actually means. Steps 4-5 are structural simplifications enabled by step 3. Step 6 is the R2-retiring change and absorbs CE review per the design integrity gate.

> **Revised (1.1) rationale:** Steps 1-2 remain pure refactor and land first (both merged at PR #393 and PR #394). The **execution order then becomes 4 → 5 → 3 → 6** rather than 3 → 4 → 5 → 6. The reason: precise emit-time audit instrumentation for the three normalisation classes (identifier dequoting, blank-line stripping, triple-quote collapse) requires structural fields (`was_quoted`, `leading_trivia`, `trailing_trivia`) that Step 4 reserves and Step 5 populates. Without those fields landed first, the original Step 3 could only flip xfails via post-hoc baseline-vs-canonical reconciliation — a coarse-grained workaround that constitutes design drift from I4 (TRANSFORM_AUDITABILITY: every transformation logged with stable IDs). Landing CST + populated fields first allows the now-final Step 3 (executed as the 5th step) to do precise instrumentation as originally designed. Step IDs are retained for traceability with already-merged work (#393, #394, #395 and the xfail reasons in `tests/unit/test_writer_reader_symmetry.py`); only the execution order changes. Step 6 (validator collapse) remains last, unchanged. Step 3 still lands before SR1-T4 in the cross-task timeline, satisfying T4's "no repairs occurred" precondition.

### 3a. 2026-05-11 Re-sequencing Note

**Trigger.** During implementation-lead (IL) preparation for the original Step 3, an empirical audit (anchor permit SID `4fa2f2f1-85ff-4cfc-89c6-206ab9f8b048`) of the 10 audit-cardinality xfailing fixtures in `tests/unit/test_writer_reader_symmetry.py` surfaced a structural gap: every one of the three normalisation classes that the original Step 3 promised to flip originates at the emitter but the emitter lacks the upstream information needed to log them precisely.

**Empirical finding (three normalisation classes, structural dependencies, and Step-3 flip mechanism):**

| # | Normalisation class | Example | Where information is lost | Required structural field | Reserved by | Populated by (precise) | Flip mechanism at logical-Step 3 (executes 5th) |
|---|---------------------|---------|---------------------------|---------------------------|-------------|------------------------|--------------------------------------------------|
| 1 | **Identifier dequoting** | `TYPE::"SPEC"` → `TYPE::SPEC` | `emitter.py:326` `needs_quotes()` has no knowledge the value was originally quoted | `was_quoted: Optional[bool]` on Identifier/String nodes | Step 4 (CST promotion — see §4.5 G2) | Step 5 (emitter rewrite + lexer/parser instrumentation) | **Precise (was_quoted)** — emitter consults `node.was_quoted`; `tier_normalize.log_repair()` records each dequoting decision. |
| 2 | **Blank-line stripping** | extra blank line → single blank | Blank lines are parser-discarded; never present in AST; `emit()` cannot re-emit them | `leading_trivia: Optional[str]`, `trailing_trivia: Optional[str]` on every node | Step 4 (CST promotion — see §4.5 G1) | **Sprint 3+** (SR3-T1 cursor-CST populates trivia alongside spans) | **Reconciler bridge** — precise logging not yet available; logical-Step 3 bridges via the reconciler in `mcp/write.py` (see "Reconciler bridge pattern" below) until Sprint 3+ trivia population enables precise emit-time logging. |
| 3 | **Triple-quote collapse** | `""""""` → `""` | Lexer-side information loss before tokens reach the AST | New lexer W-code for triple-quote-collapse preservation (separate Sprint task; out of immediate SR1-T1 scope) | **Separate task** (not delivered by logical-Step 5) | **Separate task** (not delivered by logical-Step 5) | **Reconciler bridge** — precise logging not yet available; logical-Step 3 bridges via the reconciler in `mcp/write.py` until the new lexer W-code lands. |

**Summary of the 8/2 split.** Of the 10 audit-cardinality xfails, **8 fixtures (the hydration/identifier-dequoting cluster + `deeply_nested_keys`)** flip via precise was_quoted-based instrumentation at logical-Step 3. **2 fixtures (`coverage/spec_full.oct.md` blank-line stripping, `symmetry/empty_triple_quoted.oct.md` triple-quote collapse)** flip via the reconciler bridge at the same logical-Step 3. The reconciler is a temporary, self-deprecating mechanism — see "Reconciler bridge pattern" immediately below.

### Reconciler bridge pattern (logical-Step 3, executes 5th)

**Mechanism.** Post-emit (inside `mcp/write.py`, after the canonical bytes have been produced), if `baseline != canonical` AND no `TIER_NORMALIZATION` entries in the current `RepairLog` account for the diff, a single coarse-grained `TIER_NORMALIZATION` entry is appended to `RepairLog` with the diff (or a stable summary of it) as receipt. That entry then flows through the same additive wiring at `write.py:3640`-style consumer loop into the `corrections` list returned to callers. The reconciler runs after all precise loggers have had their chance; it does not preempt them.

**Scope.** Applies at the renumbered logical-Step 3 (5th execution per §3a). It is part of the pre-authorised `mcp/write.py` additive scope expansion documented in §3 migration table's Step 3 "Touches" column. It is purely additive (~10-20 lines of post-emit comparison + RepairLog append) and does not change the `octave_write` contract — callers see one more `corrections` entry when the underlying transformation would otherwise be silent, which is exactly the I4 (TRANSFORM_AUDITABILITY) requirement.

**Self-deprecation (no code change required to retire).**
- When **Sprint 3+ trivia population** lands (`leading_trivia` / `trailing_trivia` populated by SR3-T1 cursor-CST), the emitter visitor will log blank-line stripping as a precise `TIER_NORMALIZATION` entry via `tier_normalize.log_repair()`. The reconciler's "no `TIER_NORMALIZATION` entries account for the diff" precondition fails → reconciler no-ops for `spec_full.oct.md`.
- When the **new lexer W-code for triple-quote-collapse preservation** lands (separate Sprint task), the lexer will emit a precise `TIER_NORMALIZATION` entry on collapse. The reconciler's precondition fails → reconciler no-ops for `empty_triple_quoted.oct.md`.
- The reconciler does not need to be deleted at that point. It remains dormant for any remaining edge case where post-emit diff exists but no precise log entry has been produced — a safety net consistent with I4.

**Not design drift.** The reconciler bridge is the same coarse-grained baseline-vs-canonical mechanism that the §3 "Revised (1.1) rationale" paragraph identified as the workaround originally rejected as drift. The difference: under v1.1's re-sequence, it operates as a documented **bridge for 2 of 10 fixtures only**, with explicit self-deprecation paths via Sprint 3+ trivia and a new lexer W-code. Under v1.0's original sequencing it would have been the **sole mechanism for all 10**, with no documented self-deprecation. The v1.2 framing honours the user's 2026-05-11 authorisation ("additive non-contract-breaking edits to `mcp/write.py` permitted") by deploying the reconciler as a narrow, time-bounded bridge rather than a permanent emit-time substitute.

**Consumer-side gap.** During the same audit, IL identified that `src/octave_mcp/mcp/write.py` is the only surface that builds the `corrections` list consumed by `octave_write` callers. The original Step 3 scope fence — written before the audit — forbade touching `write.py`. That fence was over-tight: a purely additive ~15-line wiring edit (read from `tier_normalize` `RepairLog` entries; append to `corrections`; mirror the existing schema-repair loop at `write.py:3640`) is not a contract change and is required for the audit-cardinality xfails to actually flip end-to-end (the data must reach the consumer, not just exist in the log).

**User decision (Option C — re-sequence).** Pause original Step 3. Proceed immediately with original Step 4 (CST + reserved fields) and original Step 5 (emitter rewrite + populate `was_quoted`). Once the data structurally exists, return to original Step 3 to wire up the logging and flip the 10 xfails. The pre-authorised scope expansion for `mcp/write.py` applies when original Step 3 returns. **Clarified at v1.2 (per cubic P2 review):** the "data exists" precondition is partially met by logical-Step 5 — `was_quoted` covers 8 of 10 fixtures via precise instrumentation. The remaining 2 (`spec_full.oct.md` blank-line stripping, `empty_triple_quoted.oct.md` triple-quote collapse) are bridged at logical-Step 3 by the reconciler in `mcp/write.py` (see "Reconciler bridge pattern" above). Full precision (all 10 via precise emit-time instrumentation) arrives when Sprint 3+ trivia population and the new triple-quote-collapse lexer W-code land; at that point the reconciler self-deprecates without code change.

**Renumbering convention chosen.** Stable Step IDs with explicit execution-order annotation (HO-recommended option (b)). Rationale: already-merged PRs (#393, #394, #395) and the xfail-reason strings inside `tests/unit/test_writer_reader_symmetry.py` reference "SR1-T1 Step 3" as a stable identifier. Renumbering the IDs (strict-renumber option (a)) would orphan those references and trigger an audit-trail break that violates ATLAS<historical_burden> discipline and I3 (SOURCE_FIDELITY: modify in-place, no versioned copies of meaning). Option (b) preserves the IDs and adds the execution-order disambiguation everywhere references occur.

**New execution order (step-by-step rationale):**

| Execution # | Step ID | Status | Rationale for position |
|-------------|---------|--------|------------------------|
| 1 | Step 1 | Merged at PR #393 | Pure refactor; no dependency. |
| 2 | Step 2 | Merged at PR #394 | Pure refactor; depends only on Step 1. |
| 3 | Step 4 | **NEXT** | Reserves `was_quoted`, `leading_trivia`, `trailing_trivia` field shapes on CST nodes. Must precede emitter rewrite so visitor signatures land once. |
| 4 | Step 5 | After Step 4 | Rewrites emitter as CST visitor; populates `was_quoted` via lexer/parser instrumentation (or via Step 4.5 if scope dictates separation per §4.5 fallback discipline). After this step, the emitter has the structural information needed for precise audit logging. |
| 5 | Step 3 | After Step 5 | Centralises TIER_NORMALIZATION logging in `core/grammar/tier_normalize.py`; instruments lexer + parser + the now-rewritten emitter; consumes log into `corrections` via the pre-authorised `mcp/write.py` additive wiring. **This is the step that flips the 10 audit-cardinality xfails.** |
| 6 | Step 6 | Last (unchanged) | Validator surface collapse; closes R2. Highest blast radius; lands last with mandatory CE review per AUTHORITY_MANDATE. |

**Traceability.** This re-sequencing was recorded in commit SHA (to be filled by the merging PR; see `docs/adr-0006-resequence-design-doc` branch) and the corresponding PR. The IL audit that surfaced the gap is bound to anchor permit SID `4fa2f2f1-85ff-4cfc-89c6-206ab9f8b048`. Predecessor merged work: PR #393 (Step 1), PR #394 (Step 2), PR #395 (issue #385 HARD_SYMMETRY corpus expansion adding the 10th xfail `deeply_nested_keys`).

---

## 4. Acceptance criteria

### 4.1 Quality gates (BLOCKING per CLAUDE.md)
- `pytest` — full suite green (currently 2788 passing per `current-state.oct.md:43`).
- `mypy --strict` — clean (per PROJECT-CONTEXT `QUALITY_GATES`).
- `ruff check` + `black --check` — clean.
- Coverage ≥ 90% (current floor).

### 4.2 HARD_SYMMETRY invariant (PR #383 fence)
- The `_AUDIT_CARDINALITY_XFAILS` set in `tests/unit/test_writer_reader_symmetry.py:71-83` shrinks per the table below.
- No new `strict=True` xfail markers added.
- The targeted regression fixture `tests/fixtures/symmetry/empty_triple_quoted.oct.md` continues to pass (SR0-T2 fence).

### 4.3 Expected xfail flips

The ten xfails (`#382` original set of 9 + `#385` corpus expansion adding `deeply_nested_keys`) all flip when **Step 3** lands. Per the 2026-05-11 re-sequence (§3a), Step 3 is now the **5th step executed**, after Steps 1, 2, 4, 5. The fixture-to-step mapping below uses **Step IDs (stable)**; for execution order see §3a. Per v1.2 (cubic P2 resolution), the table now includes an explicit **flip-mechanism column** that distinguishes precise was_quoted-based instrumentation (8 fixtures) from the reconciler bridge (2 fixtures); see §3a "Reconciler bridge pattern" for the bridge mechanism.

| Fixture | Flips at Step ID (executes 5th per §3a) | Flip mechanism at Step 3 | Why |
|---------|------------------------------------------|--------------------------|-----|
| `tests/fixtures/symmetry/empty_triple_quoted.oct.md` | Step 3 (legacy ID — executes 5th) | **Reconciler bridge** (until new triple-quote-collapse lexer W-code lands) | Triple-quote collapse is lexer-side info loss; logical-Step 5 does not deliver a lexer hook for it. Reconciler in `mcp/write.py` records a single coarse-grained `TIER_NORMALIZATION` entry sourced from baseline-vs-canonical diff. Self-deprecates when the new lexer W-code lands. |
| `tests/fixtures/coverage/spec_full.oct.md` | Step 3 (legacy ID — executes 5th) | **Reconciler bridge** (until Sprint 3+ trivia population) | Blank-line stripping requires `leading_trivia` / `trailing_trivia` populated; logical-Step 5 reserves the field shapes (via Step 4) but population is deferred to Sprint 3+ SR3-T1. Reconciler in `mcp/write.py` until trivia population enables precise emit-time logging. Self-deprecates when Sprint 3+ lands. |
| `tests/fixtures/hydration/collision_source.oct.md` | Step 3 (legacy ID — executes 5th) | **Precise (was_quoted)** | Identifier dequoting; emitter visitor consults `node.was_quoted` populated by logical-Step 5 lexer/parser instrumentation. |
| `tests/fixtures/hydration/expected.oct.md` | Step 3 (legacy ID — executes 5th) | **Precise (was_quoted)** | Same. |
| `tests/fixtures/hydration/source.oct.md` | Step 3 (legacy ID — executes 5th) | **Precise (was_quoted)** | Same. |
| `tests/fixtures/hydration/source_all_terms.oct.md` | Step 3 (legacy ID — executes 5th) | **Precise (was_quoted)** | Same. |
| `tests/fixtures/hydration/source_with_version.oct.md` | Step 3 (legacy ID — executes 5th) | **Precise (was_quoted)** | Same. |
| `tests/fixtures/hydration/source_with_wrong_version.oct.md` | Step 3 (legacy ID — executes 5th) | **Precise (was_quoted)** | Same. |
| `tests/fixtures/hydration/vocabulary.oct.md` | Step 3 (legacy ID — executes 5th) | **Precise (was_quoted)** | Same. |
| `tests/fixtures/symmetry/deeply_nested_keys.oct.md` (added by #385) | Step 3 (legacy ID — executes 5th) | **Precise (was_quoted)** | Identifier dequoting across deeply-nested keys; depends on `was_quoted` from Step 5. |

**All ten flip at Step 3 (legacy ID — executes 5th per §3a re-sequence): 8 via precise `was_quoted`-based instrumentation, 2 via the reconciler bridge documented in §3a.** The reconciler becomes dormant when Sprint 3+ trivia population and a new lexer W-code (separate task) land; at that point all 10 flip via precise instrumentation and the reconciler self-deprecates without code change. Steps 4 and 5 (executed 3rd and 4th) supply the structural dependencies — CST reserved fields and emitter `was_quoted` population respectively — that make precise emit-time audit logging possible for the 8 fixtures at Step 3. Steps 4 and 5 are not themselves expected to flip xfails — they are enablers. The xfail-reason strings in `tests/unit/test_writer_reader_symmetry.py` (currently "#382 SR1-T4" and "SR1-T1 Step 3") will be updated inside the future Step 3 PR (legacy ID), not by this design-doc amendment.

**No fixtures require SR1-T4** to flip — SR1-T4 (no-op normalize default) is a separate quality-of-life change that prevents the writer from running normalisation when no edit was requested. The HARD_SYMMETRY suite asserts symmetry *given* normalisation; it does not require normalisation to be skipped.

### 4.4 Drift-elimination evidence
- `validator.py` exports exactly one public `validate` symbol (the class method).
- `core/schema.py` deleted; no consumers remain.
- `emitter.py` defines no identifier/annotation/expression regex — all shape decisions consult `cst.NodeKind` AND `node.was_quoted` per §4.5.
- A new test `tests/unit/test_grammar_core_single_source.py` asserts (via AST inspection of `core/`) that no module besides `core/grammar/tier_normalize.py` writes to a `RepairLog` for TIER_NORMALIZATION events.

### 4.5 Fidelity guardrails (HO addendum)

Two fidelity-preservation gaps were identified in the original design after technical-architect handoff. Both must be honoured when Steps 4 and 5 land.

**G1 — Trivia field reservation (Step 4).** ADR-0006 reserves `(start_offset, end_offset, source_hash)` for SR3-T1 cursor-CST. That is necessary but not sufficient: lexer at `core/lexer.py:928-946` discards inter-token whitespace and produces non-contiguous spans, so SR3-T1's `emit_bytes(source[start:end])` strategy will NOT preserve whitespace unless tokens additionally carry `leading_trivia` / `trailing_trivia`. Reserving `Optional[str] = None` slots at Step 4 is trivial; retrofitting later requires a second schema migration touching every node and every visitor signature. Step 4 reserves the shape; Sprint 3 SR3-T1 populates it; Step 5 emitter and Sprint 2 preserve-default visitor consult it.

**G2 — `was_quoted` metadata preservation (Step 5).** The current emitter's `IDENTIFIER_PATTERN`, `ANNOTATION_PATTERN`, and `EXPRESSION_PATTERN` regexes implicitly encode "did the user originally use quotes?" by re-deriving from value content. Step 5 deletes those regexes. `node.kind` (Assignment/Block/String/Identifier) is structural, NOT presentation-aware. Without `was_quoted` on Identifier and String nodes:
- A user who wrote `KEY::"42"` (explicit string) gets `KEY::42` (integer) back on round-trip → I1 violation, silent type change.
- A user who wrote `KEY::"identifier_looking"` (explicit string) gets `KEY::identifier_looking` (bare identifier) back → I1 violation.

These bugs would not be caught by the HARD_SYMMETRY suite's audit-cardinality conjunct alone — they pass through type and round-trip parse-equally despite changing semantics. The lexer/parser must record `was_quoted: bool` on Identifier and String nodes (Step 4 reserves the field shape; Step 5 emitter visitor consults it; lexer/parser instrumentation lands in Step 5 as part of the emitter rewrite scope, OR as an explicit Step 4.5 if scope dictates separation).

**Fallback discipline during transition.** Step 5 keeps a temporary regex fallback ONLY while `was_quoted` may be `None`. The fallback and the regex constants must be deleted in the SAME PR that guarantees lexer/parser populate the field — there is no release where both the regex constants AND the `was_quoted`-driven path coexist as live decision sources. Two acceptable shapes for Step 5: (a) fold lexer/parser instrumentation into Step 5 scope so the deletion is atomic; (b) sequence as a Step 4.5 (lexer/parser instrumentation) followed by Step 5 (visitor switch + regex deletion). Step 5 PR reviewer chain (CE + CRS) MUST verify the chosen shape: no PR ships a "deleted regex" claim while a `was_quoted is None` fallback path remains in the visitor.

**Clarification (2026-05-11 amendment).** The original §4.5 wording "Population is deferred to Sprint 3 / future steps" (G1) and "Step 4 reserves the field shape; Step 5 emitter visitor consults it" (G2) was technically correct as a field-population schedule but was misread during early IL planning of the original Step 3 as "Step 3 can still flip the audit-cardinality xfails through alternative means." It cannot. **Emit-time precise audit instrumentation depends on Step 5's `was_quoted` population (G2) and on the reserved trivia fields (G1).** Until Step 4 and Step 5 land, audit completion for the three normalisation classes (identifier dequoting, blank-line stripping, triple-quote collapse) is structurally impossible without resort to post-hoc baseline-vs-canonical reconciliation — an approach that was considered and rejected as design drift from I4 (TRANSFORM_AUDITABILITY) during the 2026-05-11 user-decision review. The re-sequence in §3a is the principled response: land the structural prerequisites first, then do precise instrumentation as originally designed.

---

## 5. Out of scope

- **Span tracking / cursor CST.** Sprint 3 (#377, ADR §96-104) adds `(start_offset, end_offset, source_hash)` to every CST node; this design only reserves the field shape, does not populate it.
- **EBNF → runtime grammar codegen.** Option (B) is rejected; `docs/grammar/octave-v1.0-grammar.ebnf` remains the spec-of-record for human readers, not a runtime artefact.
- **GBNF compiler refactor.** The existing `core/grammar.py` (renamed to `core/grammar_compiler/gbnf.py` in step 1) is functionally untouched.
- **MCP tool surface changes.** `octave_validate`, `octave_write`, `octave_eject` keep their public envelopes. Internal import lists shrink; external schemas do not.
- **SR1-T2 / SR1-T3 / SR1-T4 work.** Each has a separate IL delegation. This design must be migration-step-orderable around their landing (the migration table assumes T2/T3 land independently before or after any of steps 1-6).

---

## 6. References

- Parent: [`docs/adr/adr-0006-writer-reader-symmetry.md`](./adr-0006-writer-reader-symmetry.md) §70-84 (SR1-T1 task definition)
- Sprint 0 PR: [#383 (merged at `22df280`)](https://github.com/elevanaltd/octave-mcp/pull/383)
- HARD_SYMMETRY suite: `tests/unit/test_writer_reader_symmetry.py` (xfail set at lines 71-83)
- North Star: [`.hestai/north-star/000-OCTAVE-MCP-NORTH-STAR-SUMMARY.oct.md`](../../.hestai/north-star/000-OCTAVE-MCP-NORTH-STAR-SUMMARY.oct.md) (R2 risk; I1/I3/I4 invariants)
- W002 centralisation: commits `e16a728` (CE follow-up), `5a9d9af` (P2 follow-up), `repair_log.py:8`
- Grammar spec-of-record: `docs/grammar/octave-v1.0-grammar.ebnf`
- Tracking issue: GH#382 (remains open after this design lands; closes when migration step 6 merges)
