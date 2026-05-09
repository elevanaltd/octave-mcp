# ADR-0006 SR1-T1: Unified Grammar Core — Design Pass

**Status:** Proposed (design-only; implementation deferred to follow-up IL delegation)
**Date:** 2026-05-09
**Parent:** [ADR-0006 Writer/Reader Symmetry](./adr-0006-writer-reader-symmetry.md) §70-84
**Tracks:** GH#382 (SR1-T1)
**Retires:** North Star Risk **R2** — `validator_drift_multiple_validators`
**Out of scope (separate IL agents):** SR1-T2 (#372 W_DUPLICATE_TARGET hard-fail), SR1-T3 (#369 path-resolver), SR1-T4 (no-op normalize default), Sprint 3 cursor-CST.

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
| 3 | **Centralise TIER_NORMALIZATION logging in `core/grammar/tier_normalize.py`**. Lexer's W002 path + parser's whitespace normalisation + emitter's `FormatOptions` strip/blank-line repairs all emit through one `log_repair()` call. | `lexer.py`, `parser.py`, `emitter.py` — additive instrumentation only. | Medium — every TIER_NORMALIZATION event now appears in `RepairLog`. **This is the step that flips the audit-cardinality xfails.** | Flips xfail set 1 (see §4). |
| 4 | **Promote `ast_nodes.py` to `core/grammar/cst.py`** with `NodeKind` enum and visitor protocol. Existing dataclasses unchanged; Section/Block/Assignment/Document gain `kind: NodeKind` field defaulted from `__class_getitem__`. | `ast_nodes.py` → moved; ~30 import sites rewritten by ruff codemod. | Medium — broad import churn; mypy gates catch breakage. | No effect (structural only). |
| 5 | **Rewrite emitter as CST visitor**. Delete `IDENTIFIER_PATTERN`, `ANNOTATION_PATTERN`, `EXPRESSION_PATTERN` re-derivations; consult `node.kind` instead. Identifier-shape decisions become single-sourced. | `emitter.py` only. | Medium-high — emitter is hot path; rely on existing 2788-test gate + HARD_SYMMETRY. | Should not regress; may flip 1-2 additional fixtures. |
| 6 | **Collapse validator surface**. Delete `core/schema.py`; delete module-level `validate()` in `validator.py`; promote `class Validator` to `visitor.Visitor[None]`; move `validate_frontmatter()` into `grammar/entry.py` as a parse-stage hook. | `validator.py`, `schema.py` (delete), `mcp/validate.py`, `mcp/write.py`, ~8 internal call sites. | High — biggest blast radius. Land last. CE review mandatory per AUTHORITY_MANDATE. | Closes R2 (named risk). |

**Sequencing rationale:** Steps 1-2 are pure refactor (no semantics change) — land first to establish the package skeleton. Step 3 is the **load-bearing audit-completeness fix** that flips the xfail set; it must land before SR1-T4 because T4 (no-op normalize default) depends on knowing what "no repairs occurred" actually means. Steps 4-5 are structural simplifications enabled by step 3. Step 6 is the R2-retiring change and absorbs CE review per the design integrity gate.

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

The nine xfails (`#382` set) split by which migration step flips them:

| Fixture | Flips at | Why |
|---------|----------|-----|
| `tests/fixtures/symmetry/empty_triple_quoted.oct.md` | Step 3 | Triple-quote collapse currently invisible to repair log; centralised logger captures it. |
| `tests/fixtures/coverage/spec_full.oct.md` | Step 3 | Blank-line stripping by emitter `FormatOptions` becomes a logged repair. |
| `tests/fixtures/hydration/collision_source.oct.md` | Step 3 | Identifier dequoting by emitter regex becomes a logged repair. |
| `tests/fixtures/hydration/expected.oct.md` | Step 3 | Same. |
| `tests/fixtures/hydration/source.oct.md` | Step 3 | Same. |
| `tests/fixtures/hydration/source_all_terms.oct.md` | Step 3 | Same. |
| `tests/fixtures/hydration/source_with_version.oct.md` | Step 3 | Same. |
| `tests/fixtures/hydration/source_with_wrong_version.oct.md` | Step 3 | Same. |
| `tests/fixtures/hydration/vocabulary.oct.md` | Step 3 | Same. |

**All nine flip at step 3** (audit-completeness fix). Step 5 (emitter as visitor) may reduce the *frequency* of repairs (single-sourced identifier rules → fewer requote events) but does not change the audit-cardinality-conjunct logic.

**No fixtures require SR1-T4** to flip — SR1-T4 (no-op normalize default) is a separate quality-of-life change that prevents the writer from running normalisation when no edit was requested. The HARD_SYMMETRY suite asserts symmetry *given* normalisation; it does not require normalisation to be skipped.

### 4.4 Drift-elimination evidence
- `validator.py` exports exactly one public `validate` symbol (the class method).
- `core/schema.py` deleted; no consumers remain.
- `emitter.py` defines no identifier/annotation/expression regex — all shape decisions consult `cst.NodeKind`.
- A new test `tests/unit/test_grammar_core_single_source.py` asserts (via AST inspection of `core/`) that no module besides `core/grammar/tier_normalize.py` writes to a `RepairLog` for TIER_NORMALIZATION events.

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
