# ADR-0006 SR2-T2 — AST Source-Span Coverage Audit (Strategy A for GH#377)

Status: DRAFT (advisory; pending HO commit)
Authors: ho-liaison (advisory)
Decision owner: holistic-orchestrator
Target release: v1.13.0
Predecessor: GH#376 PR-A (format_style toggle, Strategy C parse-equality short-circuit) — merged on `main` as v1.12.0
Successor task: GH#377 (Strategy A — per-key dirty tracking + byte-splice emitter)

> **Pre-flight citation remap.** The HO brief references file paths and line numbers that have drifted post-PR-401 (ADR-0006 SR1-T1 Step 6, validator collapse). This document uses canonical paths verified against the worktree:
> - `src/octave_mcp/core/ast_nodes.py` → **deprecation shim** (`ast_nodes.py:1-99`). Canonical: `src/octave_mcp/core/grammar/cst.py`.
> - `src/octave_mcp/tools/write.py` → **does not exist**. Canonical: `src/octave_mcp/mcp/write.py`.
> - `emitter.py:444 / 475` (comments) → actual: `emitter.py:422,441,486,537,561,629`.
> - `write.py:2076-2269` (_apply_changes) → actual: `mcp/write.py:2682-2900+`.
> - `write.py:413-505` ($op) → actual: `mcp/write.py:503-555` (_KNOWN_OPS + _extract_op_descriptor).
> - `write.py:596-602` (_normalize_value_for_ast) → actual: `mcp/write.py:645-680`.
> - `write.py:2716-2728` (frontmatter inheritance) → actual: `mcp/write.py:3370-3392`.

---

## Section 1 — AST node inventory

Source of truth: `src/octave_mcp/core/grammar/cst.py` (canonical post-ADR-0006 SR1-T1 Step 4) and `src/octave_mcp/core/lexer.py` (Token).

| # | Node | Subclass of | Current source-span coverage | Where parser sees the span | `changes`-mode target? | Strategy-A need |
|---|---|---|---|---|---|---|
| 1 | `ASTNode` (base) | — | `line:int`, `column:int` (cst.py:155-156); reserved (unpopulated) `leading_trivia`, `trailing_trivia`, `was_quoted` at cst.py:161-163 | All `Token`s carry `line`/`column` only (lexer.py:73-83). `tokenize()` tracks `pos` (byte offset) as a local at lexer.py:841 but **does not store it on `Token`** | n/a (abstract) | **Add `start_byte:int`, `end_byte:int` to base** so all subclasses inherit. |
| 2 | `Assignment` | `ASTNode` | line/col via base only (cst.py:172-178) | Constructed at `parser.py:1105-1106,1152-1153,1214-1215,1272-1273` from `identifier_token.line/column` | **Yes** — primary `_apply_changes` target (mcp/write.py:2719+) | **Per-key span required**. `(start_byte, end_byte)` covering the full `KEY::value\n` line(s), plus separately tracked `value_start_byte`, `value_end_byte` for value-only replacement (smaller diff footprint). |
| 3 | `Block` | `ASTNode` | line/col only (cst.py:181-200); has `target` field with no span | Built around `block_token` in parser block-parse (around parser.py:1125); children appended individually | **Yes** — `$op:MERGE` target (mcp/write.py:2793-2811) | `(start_byte, end_byte)` covering full block header line + indented children region. Header span and body span tracked separately so MERGE rewrites only the changed child while header bytes stay untouched. |
| 4 | `Section` | `ASTNode` | line/col only (cst.py:203-215); `annotation` field with no separate span | `section_token` at `parser.py:973-974` | **Yes** — section-prefixed change paths (`§N.KEY`) routed at mcp/write.py:2721-2727 | `(start_byte, end_byte)` covering full section incl. `===NAME===` style or `§N::` header line + body. Header byte-range separate from children byte-range for the same reason as Block. |
| 5 | `Document` | `ASTNode` | line/col (base); no document-level span. Carries `raw_frontmatter`, `grammar_version`, `meta`, `trailing_comments` (cst.py:218-242) | Whole-document construction post-parse loop | **Yes (indirect)** — `META.*` paths mutate `doc.meta` at mcp/write.py:2741,2764 | `meta_start_byte`, `meta_end_byte` covering the entire META block (critical for the largest single-key-edit class — META.STATUS, META.VERSION, META.UPDATED). `frontmatter_start_byte/end_byte` for `---...---` envelope. |
| 6 | `Comment` | `ASTNode` | line/col only (cst.py:245-250); `text` carries no separate span | Built whenever lexer emits a comment line | **No** (not directly addressable by changes API) | **Partial span needed.** `start_byte`/`end_byte` covers the comment line. Required because comments are *attached* to a parent (`leading_comments`/`trailing_comment`); when the parent is dirty, comments must be re-emitted; when the parent is clean, comments slice from baseline. |
| 7 | `ListValue` | **value type, NOT ASTNode** (cst.py:254-269) | Today: `tokens: list[Any] | None` for fidelity reconstruction (ADR-0012) — this is token-level provenance, not a contiguous byte span | `tokens` slice captured during list parse | Yes — APPEND/PREPEND target (mcp/write.py:_KNOWN_OPS:503) | **Add `start_byte`/`end_byte`** in addition to the existing `tokens` slice. Token slice is per-item; byte span is the literal `[...]` bracket extent needed for splice. |
| 8 | `InlineMap` | **value type, NOT ASTNode** (cst.py:272-279) | None | Constructed when parser sees inline-map shape | Yes — bare-dict MERGE (mcp/write.py:2793) | `start_byte`/`end_byte` covering `[k::v,k2::v2]`. |
| 9 | `HolographicValue` | **value type, NOT ASTNode** (cst.py:282-306) | Already carries `raw_pattern: str` (line 305) and `tokens: list[Any] | None` (line 306) | Holographic L4 detection | No — not a `_apply_changes` leaf | **Already covered for re-emit fidelity via `raw_pattern`.** Strategy A only needs a byte span IF the value sits beside a dirty sibling and the slice path needs an authoritative end point. Recommend: add span for symmetry; cost is negligible. |
| 10 | `LiteralZoneValue` | **value type, NOT ASTNode** (cst.py:309-339) | `content`, `info_tag`, `fence_marker` (verbatim per I1 spec) | Lexer fence-span detection (lexer.py:856+) — `span_start`/`span_end` are computed locally | No — content is byte-exact by I1 already | **Add `start_byte`/`end_byte`**. Trivially available — `_normalize_with_fence_detection()` already produces `fence_spans` as `(start, end, marker, tag)` tuples (lexer.py:820,857). Plumb the existing values onto the node. |
| 11 | `NodeKind` | enum, not a node | n/a | n/a | n/a | n/a — discriminator only (cst.py:62-79). |
| 12 | `Absent` / `ABSENT` | sentinel | n/a | n/a | n/a | n/a — singleton (cst.py:82-132). Absent values are skipped by emitter (emitter.py:838-841); no span possible by definition. |

### Notes
- Reserved fields `leading_trivia`/`trailing_trivia`/`was_quoted` (cst.py:161-163) are documented as "populated by Sprint 3+ / logical-Step 5". Strategy A piggybacks on the same schema-stability seam — adding two more `Optional[int]` fields to `ASTNode` is the same shape of change and incurs the same import-site exemption (zero call-site rewrite expected, per cst.py docstring).
- The audit log key under I4 (cst.py:67-68) is `NodeKind`. Strategy A's audit emission should key dirty-region records by `NodeKind` + `(start_byte, end_byte)` for stable receipts.

---

## Section 2 — Gap map

### Already covered (no span work needed)
- `HolographicValue.raw_pattern` (cst.py:305) — round-trip fidelity guaranteed for the value text. Span recommended for symmetry but not load-bearing.
- `ListValue.tokens` / `HolographicValue.tokens` — per-item provenance (cst.py:269,306) sufficient for in-place re-emission of unchanged items inside a dirty list.

### Need byte-range spans added (parser has line:col, not start/end byte offsets)
- `Assignment` — primary case. Two ranges: full line and value-only.
- `Block` — header + body, two ranges.
- `Section` — header + body, two ranges.
- `Document` — `meta_start/end`, `frontmatter_start/end`, `envelope_start/end`.
- `Comment` — single line range.
- `InlineMap` — bracket-bracket range.

### Need partial spans (only used when reachable from changes-mode)
- `ListValue` — bracket-bracket range; in practice always reachable through APPEND/PREPEND.
- `LiteralZoneValue` — fence-fence range; **already computed at lexer.py:820,857** but discarded. Cheapest win.

### Don't need spans
- `Absent`, `ABSENT` — by definition no source bytes.
- `NodeKind` — discriminator enum.
- `ASTNode` itself — abstract; covered transitively through subclasses.

### The single root cause
`Token` carries no byte offsets (lexer.py:73-83). `tokenize()` knows `pos` (lexer.py:841) at every emission point but does not store it. **One-line change to the dataclass + N call-site additions to `Token(...)` constructions inside `tokenize()`** unlocks every other span computation downstream.

---

## Section 3 — Comment, whitespace, frontmatter, repair handling

### Comments
Comments are attached to their owning node today via `leading_comments: list[str]` and `trailing_comment: str | None` on the **base** `ASTNode` (cst.py:157-158). Emitter consumes them on the parent (emitter.py:486-487, 537-538, 561-562, 629-630).

**Recommendation: spans live on the parent, comment *text* lives on the parent, but a dedicated `Comment` node IS retained for document-level orphans (`Document.trailing_comments`, emitter.py:850).**

Rationale:
1. Lifting comments into separate `Comment` nodes inside `Block.children` / `Section.children` would be a structural rewrite touching every visitor — out of scope for Strategy A.
2. Spans-on-parent matches the current emitter contract: `_emit_leading_comments` (emitter.py:422) consumes a `list[str]` keyed off the parent; under Strategy A, when the parent is clean, the parent's `start_byte` extends backwards to cover its leading comments, so the slice path captures them for free.
3. Add a single helper `node.comment_block_start_byte: int | None` on `ASTNode` to mark where the leading-comment band begins; `start_byte` itself remains the node's own first byte (post-comment). This separation lets the dirty-bit propagate independently: editing a comment marks the parent dirty (forced re-emit); editing the parent value with no comment change slices both bands from baseline.

### Whitespace between nodes (blank lines)
Currently invisible to the AST. Strategy A MUST decide ownership.

**Recommendation: trail-anchored to the preceding node.** A node's `end_byte` extends through its trailing blank lines up to (but not including) the first non-whitespace byte of the next node. Tie-breaker for the first node in a parent: leading blank lines after the parent's opening-line newline are attributed to the parent's *body-start* gap, owned by the parent.

Rationale:
1. Trail-anchoring matches the emitter's natural rhythm — `emit_assignment`/`emit_block`/`emit_section` return strings joined by `"\n"` (emitter.py:856); the blank lines are *after* a node, not before the next one.
2. Trail-anchoring composes cleanly with dirty propagation: when the dirty node is re-emitted, blank lines following it are regenerated by canonical rules; when it's clean, blank lines are sliced unmodified. No two nodes ever claim ownership of the same byte.
3. Lead-anchoring would interact badly with deletion: removing a node should remove its trailing blank line, not orphan it on the next node.

### Frontmatter inheritance
Today: `mcp/write.py:3370-3392` mutates `doc.raw_frontmatter` *after* parse when the new content omits frontmatter but the baseline had one (GH#302).

**Recommendation: force `dirty=True` on the Document for the frontmatter region whenever inheritance fires.**

Rationale:
1. Spans-before-mutation is structurally cleaner but requires moving the inheritance pass *before* span computation — that re-orders a non-trivial pipeline and breaks the inheritance audit-log point where the warning is emitted (write.py:3382).
2. Marking the inherited region dirty triggers re-emission of `raw_frontmatter` via the canonical `---\n{raw_frontmatter}\n---` path (emitter.py:812-816). Byte-identical to the original frontmatter source because the inherited string is the baseline bytes verbatim — so the "re-emit" is effectively a copy. I3 (Mirror Constraint) satisfied: nothing is fabricated, only the byte-source attribution shifts from "splice unchanged region" to "explicit raw copy".
3. The audit warning at write.py:3382 already records the inheritance event (I4 satisfied).

### Lenient-mode repairs (W002, numeric-coalesce, etc.)
Multi-word coalesce (parser.py:1283,1368,1427) and similar repairs mutate AST values during parse and emit warnings into `self.warnings` for the I4 audit trail (parser.py:241).

**Recommendation: add `repaired: bool = False` to `ASTNode` base; lenient repair paths set it; Strategy A treats `repaired=True` as an alias for `dirty=True`.**

Rationale:
1. Repaired values' source bytes do not represent the AST value any longer — splicing them back would re-introduce the lenient input that the parser just normalised away. **Splicing a repaired node is an I1 violation**: the canonical wire form differs from the source form by design.
2. A single `repaired` flag is cheaper than a per-repair-type tag (W002 vs. coalesce vs. quote-fix). The audit log via `self.warnings` retains the type breakdown.
3. `repaired=True` SHOULD be sticky through subsequent edits — once a node lost source fidelity at parse time, it can never reclaim it without a re-parse against the canonical re-emit.

---

## Section 4 — Dirty-bit propagation model

### Where the dirty flag lives
**Recommendation: `dirty: bool = False` field on `ASTNode` base, alongside the already-reserved fidelity fields at cst.py:161-163.**

Rejected alternative: `id()`-keyed side table.

Rationale (this is the highest-stakes recommendation in the audit):
1. PR_401 (PROJECT-CONTEXT.oct.md:112) just closed R2 (validator drift) by collapsing dual validator surfaces into a single canon. **A side-table dirty-state would reintroduce the same anti-pattern in a different module**: ownership of dirty-state would be split between the table and the node, and any future visitor that copies a subtree without copying its side-table entry silently loses dirty information.
2. The CST module already prepares schema-stability for exactly this shape of change. The docstring at cst.py:30 explicitly states reserved fields are added "so that the later population PRs do not need to re-touch every node class and every visitor signature". Strategy A is *the* population PR.
3. Visitor walks (`SymmetricVisitor[str]`, emitter.py:870-892) already pass nodes by reference; a node-attribute dirty bit is visited for free, no extra registry lookups.
4. Value types (`ListValue`, `InlineMap`, `HolographicValue`, `LiteralZoneValue`) are NOT `ASTNode` subclasses. For these, dirty is implied by their parent `Assignment` / `Block.children` element being dirty. **Value types do not need a separate dirty flag** — keep them as pure data carriers (modification_of_whole > addition_to_whole).

### Propagation rules for $op operations
Operators live at `_KNOWN_OPS = {"APPEND", "PREPEND", "MERGE", "DELETE"}` (mcp/write.py:503).

**Recommended rule: mark only the leaf node dirty; let the emitter walk decide re-emit scope from there.**

| Operation | Target node | Dirty marks |
|---|---|---|
| MERGE on Block (write.py:2793-2811) | Block + each modified child Assignment | Block stays *body-dirty* (rewrite children region); Block *header* clean (header bytes spliced); each modified Assignment fully dirty. |
| APPEND/PREPEND on ListValue parent Assignment | Assignment | Whole Assignment dirty (the value bracket extent changed length; partial splice of `[a,b]` → `[a,b,c]` is fragile under whitespace). |
| DELETE leaf | None (parent re-emits with the leaf removed) | Parent dirty (body-dirty for Block/Section; whole-dirty for Document.sections list). |
| META.FIELD update (write.py:2741) | Document | `meta_dirty: bool` on Document distinct from `dirty` (META is its own emission band — emitter.py:828). |
| Section-prefixed change (write.py:2725) | Section + child | Section body-dirty; child fully dirty. |

**Ancestors are NOT recursively marked dirty for full re-emit.** Body-dirty (children region changed) is distinct from whole-dirty (header + body both rewrite). This is what makes the 0.5% diff footprint achievable on a single-key edit: a deep Block hierarchy can have one dirty leaf and N clean ancestors, all of which slice their header bytes unmodified.

### `_normalize_value_for_ast` interaction (write.py:645-680)
Today the function silently coerces `dict → InlineMap`. This flips emission shape (`{...}` Python repr → `[k::v]` OCTAVE inline-map) — and *also* loses the option for a re-emit to produce the user's original `Block` shape if the user passed a dict thinking they were updating a Block.

**Recommendation: keep `_normalize_value_for_ast` semantics, but the caller `_apply_changes` must inspect the *existing* AST node before normalization. If the existing node at the target path is a `Block`, expand the incoming dict into per-child `Assignment` mutations instead of replacing the whole Block with an `InlineMap`.**

Already there is GH#369 plumbing for "PARENT.CHILD where PARENT is a Block" (write.py:2765-2782) doing exactly this. Strategy A's contribution: extend the same routing to the bare `key: dict` case when `_find_block(doc, key)` returns non-None. Mark only the modified children dirty.

When the existing node IS already an InlineMap (legitimate inline-map use), behaviour is unchanged: replace whole, mark Assignment dirty.

---

## Section 5 — Emitter integration

Two architectural options from the brief:
- **(A) Single emitter, span-aware** — `emit()` checks `node.dirty`; if False and span present, slice from `baseline_bytes`; else re-emit.
- **(B) Pre-pass replacement** — new `emit_with_preserve(doc, baseline_bytes, dirty_set)` lives outside `emit()`, calls `emit()` only on dirty subtrees, stitches via baseline.

### Recommendation: **Option A.**

Rationale:
1. **I1 Single-Canon Discipline** (the same principle PR-A's docstring at mcp/write.py:684-688 explicitly invokes: *"These helpers form AST normalisation pre-passes feeding the SAME emit() function used by today's canonical pipeline. They never fork the emitter."*). Option B forks the emitter; Option A does not.
2. The visitor seam `CanonicalEmitter(SymmetricVisitor[str])` (emitter.py:870-892) was landed at SR1-T1 Step 5 explicitly to be the single point that consumes per-node fidelity hints. The class docstring states: *"the seam Step 3 needs (a single point that consumes `assignment.was_quoted` from CST nodes)"*. Adding `node.dirty` + `node.start_byte` is the same shape of consumption — schematically already accommodated.
3. R2 (validator drift, closed by PR_401) is the precedent risk. Option B re-creates the dual-emitter shape that PR_401 just collapsed in the validator. ATHENA-weighted long-horizon view: **the validator collapse will be re-fought as an emitter collapse two sprints later if Option B ships.**
4. `FormatOptions` (emitter.py signatures, passim) is already the carrier for emission-shape parameters. Extending it with `baseline_bytes: bytes | None` and `enable_preserve: bool` is one signature change touched in `emit()`, `emit_meta`, `emit_block`, `emit_section`, `emit_assignment` — all of which already accept `format_options`.

### Integration sketch (illustrative; not implementation)
- `emit(doc, FormatOptions(baseline_bytes=..., enable_preserve=True))` enters the per-node loop.
- For each child of `doc.sections`: if `child.dirty` or `child.repaired` or `not child.start_byte`: call existing `emit_assignment/emit_block/emit_section`. Else: `lines.append(baseline_bytes[child.start_byte:child.end_byte].decode())`.
- `emit()` returns a single string just as today. **No parallel function. No emitter fork.**
- `mcp/write.py:_emit_with_format_style` (currently around mcp/write.py:1051-1095, today's PR-A short-circuit) becomes the single call site that passes `baseline_bytes`. The `"preserve"` branch's parse-equality scaffold (write.py:1081-1090) is **deleted** — Strategy A subsumes it.

### I1 implications
Option A keeps the canonical wire form as a function of (AST, FormatOptions). The slice path is logically `emit(parse(baseline_bytes), …)[node.start_byte:node.end_byte]` reduced to its byte-identical fixed point. **Provided spans are computed at parse time and dirty-tracking is correct, byte-slice and re-emit produce identical bytes on a clean node — the slice is just a faster path to the same answer.** This is the precise statement of I1 single-canon for Strategy A.

---

## Section 6 — Task breakdown (ready to file under GH#377)

Sequenced; each row is one paragraph of scope, plus LOC, risk, dependencies.

| # | Task | Scope | LOC | Risk | Depends on |
|---|---|---|---|---|---|
| **T1** | Token byte-offsets | Add `start_byte:int`, `end_byte:int` to `Token` (lexer.py:73-83). Populate at every token-emit site inside `tokenize()` from the already-tracked local `pos` (lexer.py:841). Update ~30 call sites. Tests: a new `test_lexer_byte_offsets.py` asserting `tokens[i].start_byte == content.encode().index(tokens[i].raw_or_value)` for representative inputs. | 80–120 | Low. Local change; no semantics shift. | — |
| **T2** | CST node span fields | Add `start_byte`, `end_byte`, `dirty:bool`, `repaired:bool` to `ASTNode` base (cst.py:135-169). Default `None`/`False`. Update `__post_init__` if it exists; otherwise dataclass defaults suffice. For value types (`ListValue`, `InlineMap`, `HolographicValue`, `LiteralZoneValue`), add `start_byte`/`end_byte` only. Document the new fields in cst.py module docstring §G3 (extending the §4.5 G1+G2 line). | 60–100 | Low. Reserved-field precedent (cst.py:30 docstring) lowers review friction. | T1 |
| **T3** | Parser span propagation | Wire `start_byte`/`end_byte` onto every node constructed by parser.py: `Assignment` (~5 sites at parser.py:1105,1152,1214,1272 and surrounds), `Block` (around parser.py:1125), `Section` (parser.py:973), `Document` (post-loop), `Comment`, `ListValue`, `InlineMap`, `HolographicValue`, `LiteralZoneValue` (use existing `fence_spans` at lexer.py:820,857). End byte for Block/Section MUST cover the body (last-child's end_byte → end). | 250–350 | Medium. Many sites; missed sites silently fall back to re-emit (no correctness loss, only perf loss). Add a test that asserts every node in a representative document has non-None spans. | T1, T2 |
| **T4** | Comment + whitespace span policy | Implement Section 3 policy: trail-anchored blank lines included in `end_byte`; `comment_block_start_byte` for the leading-comment band on each node that owns comments. Inherited frontmatter sets `doc.meta_dirty=True` for the frontmatter band; lenient repairs set `node.repaired=True`. | 200–250 | **Medium-High.** This is where I3 violations would slip in. Test matrix: (mixed `[X]`/`<X>` annotation forms) × (comment-before / comment-after / no-comment) × (blank-line-before / no-blank). | T3 |
| **T5** | Dirty-bit infrastructure | Implement dirty propagation rules from Section 4 inside `_apply_changes` and helpers (write.py:2682+). Each mutation point sets `node.dirty=True` and, for Block/Section bodies, distinguishes header-dirty from body-dirty via a second flag (`body_dirty:bool`). Add `doc.meta_dirty:bool`. No side tables. | 150–250 | Medium. Easy to under-mark (false-clean → I1 violation) or over-mark (false-dirty → bloated diff). Property-based tests recommended. | T2, T4 |
| **T6** | `_apply_changes` mark-touched integration | Touch every leaf of `_apply_changes` (mcp/write.py:2719+) and its sub-dispatchers `_apply_section_change`, `_apply_block_change`, MERGE/APPEND/PREPEND/DELETE branches (write.py:2783-2900+). Every assignment to a Python field on an AST node is paired with setting the owning node's `dirty=True`. | 200–300 | Medium. High site count; a linter/grep gate is recommended ("every `\.value\s*=` in write.py also touches `\.dirty\s*=`"). | T5 |
| **T7** | `_normalize_value_for_ast` rework | Extend the GH#369 routing (write.py:2765-2782) to the bare `key: dict` case when `_find_block(doc, key)` returns non-None: expand dict into per-child Assignment mutations against the existing Block. When the existing node is an InlineMap, behaviour unchanged. | 80–150 | Low-Medium. Existing tests cover GH#369 shape; extend. | T6 |
| **T8** | Emitter integration (Option A) | Extend `FormatOptions` with `baseline_bytes:bytes | None` and `enable_preserve:bool`. Modify `emit()` (emitter.py:795) and all `emit_*` helpers to: if a child node is clean (`not dirty and not repaired`) and has a span and `enable_preserve` is on, emit `baseline_bytes[start:end].decode()`; else fall through to existing emission. **Delete** the Strategy-C parse-equality short-circuit at mcp/write.py:1081-1090. | 200–300 | **High.** Emitter is load-bearing for every output path. Risks: missed branches re-emit unconditionally (perf regression only) vs. wrong-branch slices unchanged but stale bytes (I1 violation). Gate this PR with the existing 3003 tests passing PLUS the new fixture in T9. | T6, T7 |
| **T9** | Golden fixture + diff-footprint test | Pick an existing 100–150KB OCTAVE document from the worktree as the golden fixture. Candidates: `docs/research/02_benchmarking_and_generation/octave-write-test-outputs/literacy-rewrite-opus.oct.md` family or one of the agent definitions under `.hestai-sys/library/agents/`. Build a regression test: parse, apply a single META.STATUS change, assert diff footprint ≤ 0.5% of file size. Specifically assert that any byte ranges containing mixed `[X]`/`<X>` annotation forms outside the changed region are byte-identical to baseline. | 250–400 (mostly test) | Medium. Need to pick a fixture that genuinely exercises mixed annotation forms and section/block diversity. | T8 |
| **T10** | Default-flip task (separate PR, post-validation) | Change `format_style` default at `_emit_with_format_style` (mcp/write.py:1051) from `None` → `"preserve"`. Update the public MCP tool signature defaults. Update tests. **Ship in a separate PR from T1–T9** so any regression caught in the wild is bisectable to the default flip vs. the engine landing. | 30–60 | Medium. Default-flip is observable to every existing user. Recommend behind a single-version deprecation window or feature flag if HO prefers conservative rollout. | T8, T9 |
| **T11** | CHANGELOG + migration notes v1.13.0 | Update `CHANGELOG.md`, `docs/api.md`, `docs/usage.md`. Document Strategy A subsumes Strategy C; document that mixed `[X]`/`<X>` annotation forms are now stable across single-key edits; note the dirty-bit model is internal and not part of the public API. | 80–120 | Low. | T10 |

**Revised LOC envelope: 1,580–2,500 across T1–T11**, of which test code is ~250–450. The brief's "800–1200" estimate was optimistic by roughly 2×; the under-estimate concentrates in T3 (parser propagation) and T8 (emitter integration), both of which have larger surface than the headline node-count suggests.

---

## Section 7 — Risks specific to Strategy A

Format per `prophetic-intelligence` SKILL §4: SIGNAL → PROJECTION → PROBABILITY → MITIGATION.

[RISKS]

| Risk | Re-confirm/revise from PR-A diagnostic | Probability × Impact | SIGNAL | PROJECTION | MITIGATION |
|---|---|---|---|---|---|
| **R1 — Span/AST drift under post-parse mutation** | Revised: now central to Strategy A. | High × High | Inheritance at write.py:3370-3392; lenient repairs at parser.py:1283/1368/1427 mutate post-parse. | Splicing a "clean" node whose value was mutated post-parse — I1 violation, hard to detect without byte-diff testing. | `repaired:bool` flag + `dirty:bool` flag on every mutation site. Lint gate that fails CI if a `.value =` in write.py is unpaired with `.dirty = True`. (T5+T6) |
| **R2 — Side-table fragmentation** | New risk introduced by naive Strategy A. | Medium × High | Tempting to store dirty-state in `{id(node): bool}` map to avoid touching dataclass schema. | Same anti-pattern as R2 validator drift just closed by PR_401. Tree copies, subtree extraction, future visitors all need to thread the side table. | Section 4 recommendation: dirty bit on the dataclass. ATHENA-grade structural choice. (T2) |
| **R3 — Unicode byte-range mis-alignment** | New risk introduced by Strategy A. | Medium × High | OCTAVE corpus contains Unicode operators (→, ⊕, ∧, §, ⇌, ⊃, ⧺). Lexer applies NFC normalisation (lexer.py:818-820) BEFORE position tracking. | A `start_byte` computed against the post-NFC content sliced into the *pre-NFC* baseline would split a codepoint. | Strategy A operates on **post-NFC content as the canonical baseline**. The MCP write path already round-trips through NFC. If we ever expose Strategy A to a non-NFC input, slice indices MUST be re-mapped — document this in the API contract. (T8, T11) |
| **R4 — Emit-time span invalidation** | New risk introduced by Strategy A. | Medium × Medium | If upstream code mutates AST after spans are computed but before emit (e.g. a future normalize-pass), the span is stale. | Span points into baseline bytes that no longer represent the node. | Mark every post-parse pass that mutates AST as a `dirty=True` site by policy. Pre-emit assertion: `node.dirty or (node.start_byte is None) or canonical_emit(node) == baseline[start:end]` — gated behind a debug flag, not prod. (T8) |
| **R5 — Diff footprint regression under blank-line edits** | New risk. | Low × Medium | User edits a value that is followed by trailing blank lines; trail-anchored policy means the next node is unaffected. | None — this is the policy working as designed. Flag here to document the deliberate non-regression. | Section 3 trail-anchoring policy. Test in T9 includes blank-line cases. |
| **R6 — Default-flip user breakage** | Re-confirmed from PR-A R5. | Medium × Medium | Users on v1.12.0 who structured workflows around the existing canonical-rewrite default. | Diffs in CI artefacts shrink dramatically. Some downstream pipelines may rely on full-rewrite for normalization side-effects. | Ship T10 in a separate PR with explicit CHANGELOG flag and a feature toggle window. Consider a single-version `format_style: None` → `"preserve"` deprecation period if HO prefers. (T10, T11) |
| **R7 — Lenient-mode trip-wires** | Re-confirmed from PR-A R6. | Medium × High | W002 / multi_word_coalesce / curly-brace repair (parser.py:1283,1368,1427 plus tokenize at lexer.py:805) all mutate at parse. | If `repaired:bool` is forgotten on a repair site, that site silently violates I1 under Strategy A. | T4 explicit checklist over every entry in `parser.py:warnings.append({"type": "lenient_parse", …})` — every such site must set `repaired=True` on the affected node. CI grep gate. |

**New risks specific to Strategy A: R2, R3, R4, R5.** R1, R6, R7 are PR-A diagnostic risks confirmed/sharpened.

---

## Section 8 — Recommendation summary (for paste into GH#377)

**Verdict: GO_WITH_CONDITIONS.** Strategy A is the right structural fix and subsumes the GH#248 annotation-form drift problem as a free side-effect — no rule change needed, unchanged regions simply skip the emitter. The original 800–1200 LOC estimate is optimistic; revised envelope is **1,580–2,500 LOC across 11 sequenced tasks**, of which ~300 is test code, over an estimated 3–4 weeks (slightly over the original 2–3 week budget). **Recommended PR-split: stacked sequence of 4 PRs** — (PR-1) T1+T2+T3 [span infrastructure, no behaviour change]; (PR-2) T4+T5+T6+T7 [dirty-bit + apply_changes integration, behaviour-gated behind unused FormatOptions flag]; (PR-3) T8+T9 [emitter integration + golden-fixture regression test, flips the engine on]; (PR-4) T10+T11 [default flip + docs]. Single mega-PR is rejected because the emitter integration risk (R1/R3/R4) is too large to land alongside parser propagation review. The four conditions for GO are: (1) dirty-bit lives on the dataclass not in a side table — non-negotiable, see R2 and PR_401 precedent; (2) spans are computed at parse time only, with `repaired:bool` and `dirty:bool` carrying mutation provenance — non-negotiable, see I3 + R7; (3) Option A single-emitter-span-aware integration, NOT a parallel emit function — non-negotiable, see I1 single-canon and SR1-T1 Step 5 docstring; (4) default-flip ships in its own PR with explicit migration notes — non-negotiable for user trust.
