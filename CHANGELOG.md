# Changelog

All notable changes to OCTAVE-MCP will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### ⚠️ BREAKING — `octave_write` `changes` mode value semantics (GH#487, v1.15.0)

> **Migration in one line:** a **bare dict** at a `changes` KEY now **fully replaces** that key (unmentioned children are **dropped**). To merge into an existing block, you **MUST** now send an explicit `{"$op": "MERGE", "value": {…}}`.

This is the STRATEGY_S3 `DocumentMutator` extraction implementing the operator-ratified, debate-hall-settled (`decision_hash a8837c80…`) + CDV CONDITIONAL-GO contract. Transition logic and structural AST synthesis are now owned by a single `DocumentMutator` layer (`src/octave_mcp/mcp/document_mutator.py`); the emitter remains the sole canonicalizer-to-bytes (R2: one mutation path, no serialization-policy split, no node indentation metadata added).

- **Q1 — bare-dict at a top-level KEY = FULL REPLACE (#443a, HARD BREAK).** `changes={"PARENT": {"NEW_CHILD": "x"}}` against an existing `PARENT` block now **replaces** the block's children with the payload: **unmentioned children are DROPPED** (honours PROD::I3 — reflect only what's present). The previous silent implicit-MERGE (unmentioned children preserved + new child appended) is removed. **No** `$op:REPLACE` op is introduced — bare-dict carries replace semantics directly.
  - **Key-wise reconciliation (CDV BLOCKING-1):** a key present in BOTH payload and target is **form-preserved** — routed through the #460 fence-preserving path, so a re-mentioned literal-zone (fenced ```` ``` ````) child keeps its fence FORM while unmentioned siblings are dropped (PROD::I1 intact).
  - **Migration:** callers that relied on bare-dict merging **MUST** switch to `changes={"PARENT": {"$op": "MERGE", "value": {"NEW_CHILD": "x"}}}` to preserve unmentioned children. Blast radius is small at current usage; accepted by operator as a hard break.
- **Q1 — bare-scalar over a nested BLOCK = FULL REPLACE (#443 Defect 2).** A bare scalar assigned to a KEY that holds a block now **replaces the block in place** with a single flat assignment (exactly one key emitted), curing the prior duplicate-keys footgun (block left in place AND a flat scalar of the same name appended at the same scope).
- **Defect 2 — scalar-over-nested-BLOCK via `$op:MERGE` = REJECT (#443).** A `$op:MERGE` whose payload would replace an existing **child block** with a **scalar** is now **rejected with `E_OP_TARGET_MISMATCH`** (CDV firmed the scalar↔BLOCK transition to REJECT-only, never silently honour). To replace a block with a scalar, DELETE it first or send a bare-dict REPLACE at the parent. **Never emits duplicate keys.** Surfaced pre-apply by `octave_validate` and defended apply-side.
- **Q2 — deferred canonicalization: nested dicts emit BLOCK form (#440).** A bare dict with a **nested** dict value is now synthesized as canonical **BLOCK** form (the sole canonical nested form) instead of the legacy `dict→InlineMap` coercion (which re-parsed to `E_NESTED_INLINE_MAP`). The `dict→InlineMap` coercion is **abolished** for nested dicts. Every such conversion is logged to the I4 audit channel as `TRANSFORM::INLINE_MAP_TO_BLOCK` (stable rule id `TN_INLINE_MAP_TO_BLOCK`) with the key as the stable structural id (PROD::I4). A **flat** dict (all scalar/list values) is unchanged — it still emits as a re-parseable inline map.
- **#488 — APPEND/PREPEND of nested list/dict elements now re-parseable.** `$op:APPEND`/`$op:PREPEND` of a nested list (`[["PR::x"]]`) or dict (`[{"K": "v"}]`) element previously emitted a Python repr (`['PR::x']` single-quoted, or `{'K': 'v'}` with braces) that failed strict re-parse (E005) while reporting `status:success` — an I1 round-trip false-green. New list items are now normalized at the mutation seam so they emit as re-parseable OCTAVE (double-quoted strings; bare `k::v` pairs in multi-line lists).
- **#484 guard retained.** The `E_NESTED_DICT_IN_MERGE_PAYLOAD` guard for nested dicts in `$op:MERGE` payloads is **unchanged** and continues to fire **only** under explicit `$op:MERGE`; the new bare-dict REPLACE path emits BLOCK form instead and is never blocked by the guard.

`octave_validate` (read path) is unchanged: it continues to ACCEPT inline maps and report `W_INLINE_ARRAY_ROOT` without mutating the source (PROD::I5).

## [1.14.0] - 2026-05-30 - "octave_write changes-mode hybrid fix (anchored paths + literal-zone fidelity)"

### Added
- **`octave_write` `changes` mode: `ANCHOR/KEY` anchored-path syntax (#460).** Disambiguates duplicate sibling keys — e.g. five sibling `RATIONALE` keys, one per immutable — by targeting *"the `KEY` assignment following the `ANCHOR` key in document order"* (`changes={"I2/RATIONALE": …}` updates the `RATIONALE` after `I2`, not the first sibling). Resolution is local to a sibling list (top-level, or one level inside a Block/Section) and never crosses a container boundary. **Resolve-literal-first**: a real assignment whose key literally contains `/` is still mutated in place (backward-compatible, since `/` is a valid OCTAVE identifier character); bare `KEY`, `META.FIELD`, `PARENT.CHILD`, and `§N.KEY` paths are unchanged. Indexed `KEY[N]` addressing is **not** introduced and stays rejected with `E_UNRESOLVABLE_PATH` (PROD::I4 audit-stability + PROD::I3 real-keys-not-invented-indices). An unresolvable anchored path fails with `E_UNRESOLVABLE_PATH` rather than fabricating an `ANCHOR/KEY` assignment (PROD::I3). New pure resolvers live in `write_mutation.py` (`_parse_anchored_path`, `_resolve_anchored_assignment`); orchestration in `write.py` (`WriteTool._resolve_anchored_change`). Closes the PR #457 surgical-Edit workaround for duplicate-sibling targeting. Anchored paths also accept the full `$op` surface (`MERGE`/`APPEND`/`PREPEND`/`DELETE`) with the same target-type validation as bare keys — `$op MERGE` on an anchored scalar leaf fails loudly with `E_OP_TARGET_MISMATCH` rather than persisting the descriptor as literal data. `docs/api.md` updated.

### Fixed
- **`octave_write` `changes` mode: literal-zone fence form preserved on content edits and `$op MERGE` (#460).** When a `changes` value replaces a child whose existing value is a literal zone (fenced ```` ``` ```` block), the new content is re-wrapped to preserve the fence form — original fence marker (```` ``` ```` vs ```` ```` ````) and info tag retained, only the inner content changed. A content-only edit now round-trips to a **byte-identical fence form** under `format_style="preserve"` instead of being downgraded to a quoted scalar (`KEY::"…"`). Restores PROD::I1 (Syntactic Fidelity) and mirrors PR #449 mutate-in-place. New `write_mutation._normalize_value_for_ast_preserving` applied at every in-place replacement site in `write.py`. Closes the PR #455 full-content workaround for primer operator-legend updates. The preserving re-wrap is applied at every in-place replacement site, including `$op MERGE` into an existing fenced Block/Section child.
- **`octave_write` `changes` mode: anchored-path `$op` descriptors are executed, not written as data (#460).** An `ANCHOR/KEY` path carrying a `$op` descriptor now dispatches through the op machinery rather than being normalised into the target as literal content: `$op DELETE` removes the resolved sibling (previously a silent-success no-op — a PROD::I3/I4 violation where the tool reported success but performed no mutation), and `$op APPEND`/`PREPEND`/`MERGE` are applied with the same target-type validation as bare-key ops (loud `E_OP_TARGET_MISMATCH` on a type mismatch). A single `_is_anchored_change` predicate gates the bare-DELETE suppression and the anchored handler in lock-step so no `(key, value)` combination is stranded between branches.
- **Worktree `.venv` reliably gets the dev toolchain after sync (#462).** Added a PEP-735 `[dependency-groups]` `dev` group to `pyproject.toml` mirroring the existing `[project.optional-dependencies]` `dev` extra. `uv sync` installs the `dev` dependency-group **by default** (no flag required), so `.venv/bin/ruff`, `.venv/bin/black`, `.venv/bin/coverage`, `.venv/bin/mypy`, and the coverage HTML toolchain (`coverage/htmlfiles/`) land in the venv even if a sync invocation omits `--all-extras` — the root of the reported symptom where a worktree `.venv` held only runtime + `http`-extra packages and quality gates fell back to system `ruff`/`black`. The `dev` extra is retained for the `pip install -e ".[dev]"` fallback path, and `uv sync --all-extras` continues to work unchanged. `uv.lock` regenerated to resolve the new group. Empirically verified: a bare `uv sync` into a clean venv now installs all 13 dev packages, and `pytest --cov-report=html` generates `htmlcov/` with no INTERNALERROR. Developer docs (`docs/guides/development-setup.md`, `CONTRIBUTING.md`) updated with the canonical sync command and a verify/repair recipe.

### Changed
- **Canonical dev-setup command documented as `uv sync --all-extras` (#462).** `CONTRIBUTING.md` and `docs/guides/development-setup.md` now present `uv sync --all-extras` (rather than `uv pip install -e ".[dev]"`) as the canonical install step, and direct quality-gate invocation through `.venv/bin/...` so the project venv is exercised rather than system-installed `ruff`/`black`.

## [1.13.1] - 2026-05-28 - "write.py STRATEGY_S1 refactor (god-object decomposition)"

### Changed
- **STRATEGY_S1 incremental refactor of `src/octave_mcp/mcp/write.py` god object (#459).** The 4887-LOC mutation entrypoint module is decomposed into five cohesive peer modules with **zero behaviour change** and **byte-identical output** on all 3614 baseline tests preserved throughout the four-PR sequence:
  - **CLUSTER_A** (#463, PR #467) — `write_detection.py` (946 LOC): pure-text detection helpers and W-code warning emitters (`_detect_annotation_too_long`, `_detect_snake_case_blob`, literal-zone/holographic span scanners, lenient repair).
  - **CLUSTER_B** (#464, PR #469) — `write_metrics.py` (55 LOC): AST `StructuralMetrics` dataclass + `extract_structural_metrics`.
  - **CLUSTER_D** (#465, PR #471) — `write_format.py` (537 LOC): format-style pipeline (`_emit_with_style`, `_compact_pass`, `_expand_pass`, NFC byte threading, baseline span dispatch) — the Strategy A preserve-mode home.
  - **CLUSTER_C** (#466, PR #473) — `write_mutation.py` (240 LOC): op-dispatch + AST mutation primitives (`_normalize_value_for_ast`, `_mark_dirty`, `$op` envelope, dirty-flag bookkeeping) — the v1.14.0 hybrid-fix home.
- After the sequence, `write.py` is **3197 LOC** (down 1690, or 35%). WriteTool external API unchanged. Test counts unchanged (3614 passing, 11 skipped, 3 xfailed). Root architectural pattern `ABSENT_DOMAIN_MUTATION_LAYER` identified in the diagnostic remains; STRATEGY_S3 DocumentMutator extraction deferred to v1.15.0+ pending v1.14.0 evidence (#460).
- **CI coverage tracer forced to `sysmon` on Python 3.12 (#475, commit `b09f2f1`).** `.github/workflows/ci.yml` sets `COVERAGE_CORE=sysmon` only on the 3.12 matrix row to bypass the CPython 3.12 `sys.settrace` performance regression in coverage.py's default CTracer (empirically ~8min → ~14s locally on Python 3.12.12 + coverage 7.14.1; coverage numbers unchanged at 89% and the `--cov-fail-under=85` gate unaffected). Python 3.11 and 3.13 matrix rows are untouched and keep the coverage.py default. CI-only change; no user-visible runtime effect on the published package.

### Added
- **Skills now name `TELEGRAPHIC_PHRASE` (follow-up to #453).** Added the atom + canonical contrast example to `octave-compression/SKILL.md` §4 (R3a) and a cross-ref in `octave-literacy/SKILL.md` §2. Closes the primer-vs-skill gap so agents loading skills-only see the same positive value-form example primers carry.

## [1.13.0] - 2026-05-27 - "Strategy A Span-Aware Preserve" (ADR-0006 SR2)

This release lands the Strategy A span-aware preserve-mode engine (#418), the META audit-marker admission policy (#419, GH#384), and the Shape B `format_style` deprecation rollout (PR-4 / addendum §5). The default `format_style` does **not** flip in this release — see "Deprecated" below for the v1.14.0 plan.

### Added
- **Strategy A span-aware preserve mode engine (#418).** When `format_style="preserve"` is passed, `octave_write` returns single-region slice-and-replace output: clean nodes are sliced verbatim from the post-NFC baseline bytes, only mutated subtrees are re-emitted canonically. Diff footprint ≤0.5% of file size on representative documents (≈162KB governance fixture). Subsumes **GH#248** mixed `[X]`/`<X>` annotation form drift — annotations in unchanged regions are byte-identical to baseline. Implemented across the lexer (post-NFC `normalize_content()` public utility), emitter (`FormatOptions.baseline_bytes` + `enable_preserve` span-aware dispatch in the single `emit()` codepath, no parallel emitters), and write pipeline (NFC threading at all three `_emit_with_style` call sites, `spans_valid_for_baseline` discriminator for content-mode vs. changes-mode docs).
- **Paired-write discipline across four mutation surfaces.** The Strategy A slice path requires that every AST mutation be paired with the appropriate `dirty` / `body_dirty` / `meta_dirty` flag, or the emitter would splice stale baseline bytes. PR-3 of #418 installed this contract on `mcp/write.py` (PR-2 carryover), `cli/main.py` (CE BLOCKER cycle 4), `core/repair.py` (CE BLOCKER cycle 3), and `core/parser.py` (CE BLOCKER cycle 5). A structural lint gate (`tests/unit/test_dirty_paired_write_lint.py`) enforces both proximity-based pairing (write/repair/cli) and AST-scoped function-body checks (repair propagation, parser post-pass invocation) so the bug class cannot recur.
- **META audit-marker admission via Option C (#419, GH#384).** Closed-set `META_AUDIT_ADMIT_PATTERNS` matches audit markers (e.g. `AUDIT_*::`, `EVIDENCE::`) in META blocks and emits informational `W_META_AUDIT` warnings rather than rejecting them; non-matching patterns still fall through to the regular admission rules.
- **`octave_mcp.core.lexer.normalize_content(content: str) -> str`** — public utility exposing the fence-aware NFC normalisation that `tokenize()` applies internally. Callers feeding `baseline_bytes` to `_emit_with_style` must use this (or `mcp.write._to_baseline_bytes`) so byte spans index the same bytes the parser saw. See `docs/api.md` for the NFC contract.
- **`W_SNAKE_CASE_BLOB` advisory warning for snake-case prose blobs in reasoning fields (#452).** New non-blocking advisory warning emitted by `octave_write` and `octave_validate` when a value (or list-element) appearing in the position of an OCTAVE reasoning field (`DECISION`, `BECAUSE`, `RATIONALE`, `RETAINS`, `GUIDANCE`, `WHY`, `NOTE`, `PRINCIPLE`, `ESCAPE_HATCH`, `CONTEXT`, `EVIDENCE`, `OBSERVATION`, `FINDING`, `CONSEQUENCES`, `TRADEOFFS`, `NEXT_STEPS`, `CAVEAT`, `ASSUMPTION` — 18 fields per refined contract) carries a snake_case token that satisfies the bulk (`length>40 ∧ underscores≥4`) **or** semantic (`stopword_count≥2`, stopwords: `{and, or, of, to, the, with, is, are, via, for, from, at, by, on, in, into, when, if, not, no, plus, as, then}`) content trigger. Three exclusions suppress false positives: tokens containing `-` or `.`, tokens matching `^[A-Z][A-Z0-9_]{0,15}$` (short ALL-CAPS idioms like `SUPERSEDED_BY`), and tokens with zero underscores. Mirrors the `W_ANNOTATION_TOO_LONG` architecture (file:line provenance, `tier="STRUCTURAL_CHECK"`, routed through the existing `warnings[]`/`corrections[]` audit path). Cross-references the canonical `TELEGRAPHIC_PHRASE` pattern landed in primers via #453. v1 is **advisory only**; v2 blocking severity is deferred to a separate PR ~30 days out. Skill propagation to `octave-literacy` §1b `VALUE_CLASS_DISCIPLINE` and `octave-mastery` anti-pattern reference is tracked separately as a downstream HestAI-MCP issue (those skill files live under `.hestai-sys/library/skills/`, system-owned territory). Refined contract source: operator comment [4549996376](https://github.com/elevanaltd/octave-mcp/issues/452#issuecomment-4549996376) on issue #452.
- **Primer authoring discipline: canonical operator legends + `TELEGRAPHIC_PHRASE` naming (#453).** All six primers under `src/octave_mcp/resources/primers/` now legend the canonical operator set `[::, →, ⊕, ⇌, ∧, ∨]` (exceeds the §2c::SYNTAX minimum of 4). Previously `∧` and `∨` appeared in primer examples (e.g. `noise→DROP[stopwords∧redundancy]`, `ARCHETYPE→EXECUTOR∨VALIDATOR∨SYNTHESIZER`) without being legended, forcing downstream agents to infer their meaning or escalate to `octave-core-spec`. The mastery primer's mastery-specific operators (`§`, `CONTRACT[]`) remain alongside the canonical set. The compression primer now names the operator-bearing-quoted-value form as `TELEGRAPHIC_PHRASE::"quoted value, stopwords dropped, operators carry English connectives — e.g. 'security ⇌ usability' not 'security at odds with usability'"` in §1::ESSENCE, and the literacy primer cross-references it from §3::SYNTAX. A new regression test (`tests/unit/test_gh453_primer_token_budgets.py`) guards both the canonical-legend invariant and the spec ceiling `TOKEN_BUDGET::MAX[300]` (primers-spec §1) via two complementary proxies: the author-declared `META.TOKENS` field and a conservative whitespace-token count. No schema/validator changes; primers remain `VALIDATED` under `mcp__octave__octave_validate` (schema=META).
- **Multi-envelope parsing and emission (#420, PR #451).** OCTAVE documents with two or more sibling top-level `===NAME===…===END===` envelopes now round-trip without data loss. Implemented via Option D: an additive `Envelope` AST node and `Document.additional_envelopes: list[Envelope]` field. Envelope #1 continues to populate `Document.name/meta/sections` exactly as before; sibling envelopes (#2..N) become `Envelope` nodes appended to the new field, each with independent `dirty` flag, baseline span tracking, and `pre_trivia` byte-range fields for verbatim inter-envelope whitespace preservation under `format_style="preserve"`. Strategy A applies per envelope: unchanged sibling envelopes (including their pre_trivia) slice verbatim from the baseline; only mutated envelopes re-emit canonically. Bijection verified across boundary widths {zero-byte adjacency, single newline, double newline, three-newline, trailing-whitespace} — distinct inputs produce distinct outputs and all round-trip byte-identical under preserve. `META.<field>` change-path resolver (from #449) continues to mean "envelope #1's META" by construction; per-envelope `META` scoping and atom mutation on additional envelopes are deferred to v1.14+. Idempotency CI gate widened to include a multi-envelope fixture so future regressions are caught structurally.

### Deprecated
- **Passing `format_style=None` *explicitly* now emits a `DeprecationWarning`** at both the MCP `octave_write` tool surface and the CLI `octave write` command (via the new `--format-style none` literal choice). In **v1.14.0** the default will change from full canonical re-emit to span-aware `"preserve"` mode. To keep the current canonical re-emit behaviour across the flip, pass `format_style="expanded"` explicitly. To opt in to preserve mode now, pass `format_style="preserve"`. **OMITTING the parameter does NOT emit a warning** — that is the supported way to accept the future default silently. See ADR-0006 Sprint 2 addendum §5 Shape B for the rationale.
- **Notice.** v1.14.0 will flip the `format_style` default. Callers asserting byte-shape of `octave_write` outputs SHOULD review their integration and pin a `format_style` value explicitly before the v1.14.0 upgrade.

### Fixed
- **North Star summary I2 `RATIONALE` self-application cleanup (#457).** The sole project-owned offender surfaced by the new `W_SNAKE_CASE_BLOB` advisory (in `.hestai/north-star/000-OCTAVE-MCP-NORTH-STAR-SUMMARY.oct.md:29`) is rewritten from snake-blob to quoted English prose (`"downstream must know — didn't check vs. not there"`), bringing octave-mcp's own `.oct.md` corpus to zero `W_SNAKE_CASE_BLOB` warnings.
- **`octave_write` changes_mode mutate-in-place on flat `===META===` atoms (#447, PR #449).** When `changes={"META.<field>": <value>}` targets a flat-form atom inside a `===META===` envelope (e.g. existing `STATUS::proposed`), the resolver now mutates that atom in-place instead of injecting a duplicate nested-block atom alongside it. Behaviour verified across `format_style ∈ {preserve, expanded, compact, omitted}`. The flat-atom scan is strictly gated on `doc.name == "META"`, so non-META envelopes with same-named flat atoms (e.g. `===DOC===\nSTATUS::content\n===END===`) are not affected and continue to route via the existing `doc.meta` create path. `$op DELETE` against flat META atoms is covered by the same code path and pinned by regression tests.

### Migration
- No code changes required to upgrade from v1.12.0 to v1.13.0. Behaviour on the default path (`format_style` omitted) is byte-identical to v1.12.0.
- To silence the new `DeprecationWarning` while intentionally keeping v1.12.0 behaviour, replace any `format_style=None` explicit pass with `format_style="expanded"`.
- See `docs/usage.md` for the v1.12.0 → v1.13.0 → v1.14.0 behaviour matrix per `format_style` value.

### Status of v1.12.0 known issues (#411)
PR #418 (Strategy A engine) explicitly does NOT subsume #411 defects 1 and 2 (`$op:APPEND` Python-dict emission; `format_style:"expanded"` lifter dropping outer `]`); those remain open for a follow-up sprint. PR #418 partially subsumes #411 defects 3 and 4 — preserve mode now surfaces nested-merge errors structurally (no longer silently invalid output) although MERGE on inline-array top-level targets is still rejected and the validator's false-green on inline-array writer output remains tracked separately. See ADR-0006 Sprint 2 addendum EC-4 / EC-4b for the subsumption retriage record.

### Related PRs
- **#418** — Strategy A span-aware preserve mode engine (PR-3 / T8 + T9 + reviewer rework cycles 1–5).
- **#419** — META audit-marker admission (GH#384 / SR2-T3).
- **#421** — Sprint 2 EC coordination (EC-1 + EC-2 SATISFIED).
- **PR-4 (this release)** — Shape B `format_style` deprecation warning + v1.13.0 documentation (T10 + T11).
- **#449** — `octave_write` changes_mode mutate-in-place on flat `===META===` atoms (closes #447, PR-A of two pre-v1.13.0 release blockers; PR-B = #420 multi-envelope parsing/emission follows separately).
- **#451** — multi-envelope parsing and emission via additive `Envelope` AST nodes (closes #420, PR-B of two pre-v1.13.0 release blockers). Option D scope-locked by HO; two CE rework cycles (inter-envelope whitespace capture + verbatim emission via direct-concat byte assembly) before APPROVE.

## [1.12.0] - 2026-05-11 - "Writer/Reader Symmetry" Release (ADR-0006 SR0 + SR1-T1)

This release completes the ADR-0006 writer/reader symmetry programme: the SR0 corpus + W002 destructive-correction work (#383) and all six SR1-T1 steps (#393, #394, #395, #396, #397, #398, #399, #400, #401). It single-sources the validator surface (closing North Star Risk **R2**) and enforces I4 (TRANSFORM_AUDITABILITY) at boundary cases by routing every canonical re-emit transformation through a `TIER_NORMALIZATION` receipt.

### Shipped in v1.12.0
- **`octave_validate` and `octave_write` share a unified grammar core** — validator surface single-sourced on `class Validator` (now a `Visitor[None]`); `core/schema.py` deleted; `core/grammar/entry.py` is the parse-stage seam. Closes **R2 — `validator_drift_multiple_validators`**. (#393, #394, #396, #397, #398, #399, #400, #401)
- **W002 destructive empty-`after` corrections eliminated** — pre-1.12.0 the W002 normalization repair could emit `after=""` corrections that silently destroyed source content. The discriminant is now centralised and the destructive variant is rejected at write + lexer. (#383)
- **Ambiguous `Block.child` paths surface as `W_AMBIGUOUS_PATH` warning** — `octave_write` now drains an `E_AMBIGUOUS_PATH`-scaffolded warning into emit error envelopes when a `changes` path is structurally ambiguous (e.g. duplicate child key target). Warning-only in v1.12.0 — does **not** yet hard-fail. (#391, #392)
- **HARD_SYMMETRY roundtrip suite enforced in CI** — corner-case fixtures (deeply nested keys, trailing whitespace, multi-byte identifiers, blank-line stripping, triple-quote collapse, identifier dequoting) all enforce writer/reader symmetry; 10 corner-case fixtures (deeply nested keys, blank-line stripping, triple-quote collapse, etc.) now enforced as expected-pass rather than skipped, via the reconciler bridge. (#385, #395, #399)
- **SR1-T4 — Explicit `octave_write` no-op invariant assertion**: when supplied content already matches target bytes, the write tool is a true no-op (no normalisation, no corrections emitted). Closes the symmetry programme's writer contract. (#407)
- **GH-386 / W002 discriminant** — W002 destructive-normalization guard now uses a discriminant against a closed `SUPPRESSIBLE_NORMALIZATION_CODES` set; future W003+ codes require explicit admission policy. Prevents accidental warning suppression as new normalisation codes are added. (#408)

### NOT YET in this release (coming in v1.13.0)
> These are intentional deferrals with named dependencies. They will land **after** ADR-0006 Sprint 2 exit criteria are written.
- **`format_style="preserve"` as default** — currently opt-in only. Default flip is pending Strategy A (per-key dirty tracking) per **#376** + **#377**. Triggering the default on today's Strategy C narrow short-circuit would cause unsafe writes on byte-identical-but-AST-different inputs.
- **Single-region diffs on edits** — currently `octave_write` produces full-document canonical re-emits even for one-line edits. Cursor-backed CST + per-key dirty tracking is pending **#377**.
- **Full hard-fail on ambiguous paths** — currently warning-only via `W_AMBIGUOUS_PATH` (see Shipped). Hard-fail with `E_AMBIGUOUS_PATH` is pending **#369** (Block.child path corruption hard-fail) and downstream consumer migration.

### ⚠️ Known Issues (filed for v1.13.0)

These pre-existing defects in `octave_write` changes-mode primitives are
not fixed in v1.12.0. They are confirmed in #411 and will be addressed
alongside Strategy A in v1.13.0.

- **#411 defect 1 — `$op:APPEND` emits Python dict syntax inside OCTAVE
  arrays.** Calling `octave_write` with `{"$op":"APPEND","value":{"K":"V"}}`
  on a list-valued target produces `{'K': 'V'}` (Python repr) in the
  output. The tool returns `validation_status: VALIDATED` because the
  lexer accepts the form, but the output is semantically invalid OCTAVE.
  **Workaround:** pass APPEND values as a list of K::V strings, not a
  dict; or use content-mode rewrite.

- **#411 defect 2 — `format_style:"expanded"` over-eagerly lifts inner
  list-of-atoms.** The lifter cannot distinguish a structured record
  (`KEY::[TOKEN::X, STATUS::Y]`) from a list of K::V data points
  (`FACTS::[a::1, b::2]`). Both lift to Block form. The lift is
  semantically wrong on the second case and drops the outer `]` causing
  document boundary loss. **Workaround:** do not run `expanded` on
  documents containing inner list-of-atoms; pre-canonicalise block-form
  entries only.

- **#411 defect 3 — `$op:MERGE` rejects inline-array top-level targets.**
  Feature gap, not corruption. MERGE only supports Block/Section/META
  targets. **Workaround:** content-mode rewrite for inline-array
  records.

- **#411 defect 4 — Validator false-green on writer output.** All three
  defects above produce output that `octave_validate` accepts. This
  violates HARD_SYMMETRY in the *output* direction (the validator
  cannot be used to verify that `octave_write` output is semantically
  correct). Tracked separately as a lexer-level investigation.

Until v1.13.0 ships, callers should spot-check `octave_write` diffs
visually rather than relying on `validation_status: VALIDATED` alone
for changes-mode operations on inline-array top-level entries.

### Related work tracked separately

- **#403 — annotation-content discipline epic** — broader programme on
  annotation hygiene across the writer/reader surface. Not a v1.12.0
  blocker; tracked for visibility and future sprint planning.

### ⚠️ Breaking Changes — direct importers of internal API

The MCP tool surface (`octave_validate`, `octave_write`, `octave_eject`, `octave_compile_grammar`) and the CLI are **unchanged**. The break is for Python code that imported internal validator symbols directly.

| Old (≤ 1.11.0) | New (1.12.0+) |
|---|---|
| `from octave_mcp.core.schema import validate` | **deleted** — use `Validator(schema).validate(doc)` |
| `from octave_mcp.core.schema import Schema` | `from octave_mcp.schemas.repository import Schema` |
| `from octave_mcp.core.validator import validate` *(module-level)* | `Validator(schema).validate(doc, strict=...)` |
| `from octave_mcp.core.validator import validate_frontmatter` | `from octave_mcp.core.grammar.entry import validate_frontmatter` *(also re-exported from `octave_mcp.core.grammar`)* |
| `from octave_mcp.core.grammar import compile_grammar` *(legacy module)* | unchanged shim retained — grammar compiler now lives at `octave_mcp.core.grammar_compiler.gbnf`; the old import path emits a DeprecationWarning |
| `from octave_mcp.core.ast_nodes import …` *(internal node types)* | `from octave_mcp.core.grammar.cst import …` — new `NodeKind`, `Visitor[T]`, and reserved fields (`was_quoted`, `leading_trivia`, `trailing_trivia`) |

Code example:

```python
# Before (≤ 1.11.0)
from octave_mcp.core.validator import validate
errors = validate(doc, schema, strict=True)

# After (1.12.0+)
from octave_mcp.core.validator import Validator
errors = Validator(schema).validate(doc, strict=True)
```

### ⚠️ Breaking Behaviour — RepairLog volume shift (I4 enforcement)

`RepairLog` now records all TIER_NORMALIZATION events. Documents containing trivia normalisation (blank-line stripping, triple-quote collapse, identifier dequoting) that previously produced an empty repair log now produce one or more entries. **This reflects correct behaviour per I4 — pre-1.12.0 silent canonical mutation was an under-reporting bug.**

If your tests or downstream consumers assert `len(repair_log.entries) == 0` (or `len(corrections) == 0`) on such documents, they will now fail. Migration:

- To detect **content normalisation**, filter `corrections` by `tier == "NORMALIZATION"`.
- To detect **schema repairs**, filter by `tier == "REPAIR"`.

See `docs/adr/adr-0006-sr1-t1-grammar-core-design.md` §3 row 6 + §2.2 (module boundaries) + §3a (Reconciler bridge pattern) + §4.4 (drift-elimination evidence).

### Added — ADR-0006 SR1-T1 Step 6 (validator surface collapse; closes R2) — #401
- **`core/grammar/entry.py`** now hosts `validate_frontmatter()` as a parse-stage hook. The legacy location `octave_mcp.core.validator.validate_frontmatter` is intentionally absent — no shim retained (design §3 row 6, §2.2).
- **`octave_mcp.core.grammar` package** re-exports `validate_frontmatter` for convenience (`from octave_mcp.core.grammar import validate_frontmatter`).
- **`class Validator`** is now a structural `visitor.Visitor[None]` — it exposes `visit_document`, `visit_section`, `visit_block`, `visit_assignment`, and the `visit` dispatcher. The orchestrating `Validator.validate(doc, ...)` method remains the canonical entry point; the visit methods are the protocol surface that future visitors compose against.
- **`tests/unit/test_validator_surface_collapse.py`** — R2 closure witness asserting schema.py is unimportable, module-level `validate()` is gone, `validate_frontmatter` lives at the new location, and `Validator` satisfies `Visitor[None]` structurally.

### Added — ADR-0006 SR1-T1 Step 3 (audit-completeness closure) — #399, #400
- **`core/grammar/tier_normalize.py`** — Centralised TIER_NORMALIZATION audit channel. Public surface:
  - `log_repair(log, rule_id, before, after, *, safe=True, semantics_changed=False)` — single precise entry point for normalisation receipts.
  - `active(log)` context manager — ContextVar-scoped sink so pipeline-internal sites (notably emitter identifier-dequoting) can record receipts without RepairLog threading through `emit()`'s public signature.
  - `reconcile_canonical_emission(log, baseline_bytes, canonical_bytes)` — reconciler bridge (per design doc v1.2 §3a) that closes audit-cardinality gaps for diffs upstream precise loggers do not yet cover (blank-line stripping, triple-quote collapse).
  - Stable rule IDs: `TN_IDENTIFIER_DEQUOTE` (precise was_quoted-driven), `TN_RECONCILE_CANONICAL` (reconciler bridge).
- **Precise instrumentation in `core/emitter.py`** — `emit_assignment` now logs `TN_IDENTIFIER_DEQUOTE` via `tier_normalize.log_repair_if_active` whenever `assignment.was_quoted is True` AND the emitter chose to emit bare. The hook is no-op outside the active context (preserves today's behaviour for callers that do not opt in).
- **Additive consumer wiring in `mcp/write.py`** — Each `_emit_with_style` invocation is now wrapped with `tier_normalize.active(tier_normalize_log)`. After final emit, `reconcile_canonical_emission` runs and the log drains into `result["corrections"]` mirroring the existing schema-repair loop. The edit is purely additive (~30 lines including comments; no envelope / public API change).

### Added — ADR-0006 SR0 (writer/reader symmetry foundation) — #383
- **SR0-T1 HARD_SYMMETRY roundtrip suite** — `tests/unit/test_writer_reader_symmetry.py` establishes the writer/reader symmetry contract as enforced CI baseline. The suite asserts the three HARD_SYMMETRY conjuncts (parse-equivalence, byte-equivalence under canonical, repair-cardinality correctness).
- **SR0-T2 W002 destructive-correction elimination** — the W002 normalization repair previously could emit `after=""` corrections that destroyed source content during canonical re-emit. The discriminant for destructive variants is now centralised in the lexer + write path, and destructive variants are rejected before they reach the RepairLog. Follow-up hardening landed via `e16a728` (CE: discriminant centralisation) and `5a9d9af` (cubic P2: defensive guard for malformed normalization repairs).

### Added — ADR-0006 SR1-T3a (ambiguous path warning surface) — #391, #392
- **`W_AMBIGUOUS_PATH` deprecation warning + `E_AMBIGUOUS_PATH` scaffolding** — `octave_write` now detects structurally ambiguous `changes` paths (e.g. duplicate child-key targets in a Block) and surfaces a `W_AMBIGUOUS_PATH` warning into the emit error envelope. The `E_AMBIGUOUS_PATH` error symbol is scaffolded but not yet emitted — the hard-fail transition is gated behind #369 and downstream consumer migration in v1.13.0+. Follow-up hardening landed via `e360827` (CRS+CE: verify $op behaviour on ambiguous paths + remove singleton race in warning buffer) and `70d5016` (CE: drain `W_AMBIGUOUS_PATH` into emit error envelopes).

### Added — ADR-0006 SR1-T1 Steps 1, 2, 4, 5 (grammar core seams) — #393, #394, #396, #397, #398
- **Step 1 (#393)** — `core/grammar.py` renamed to `core/grammar_compiler/gbnf.py`; a deprecation shim retained at `core/grammar.py` re-exports the public surface and emits a DeprecationWarning. Internal call sites switched to the new path.
- **Step 2 (#394)** — `core/grammar/` package installed as the parse-stage seam. `core/grammar/entry.py::parse()` is currently an identity wrapper around `core/parser.py::parse`, ready to host CST construction in Sprint 2.
- **Step 4 (#397)** — `core/ast_nodes` promoted to `core/grammar/cst.py`. Introduces `NodeKind` discriminator, `Visitor[T]` protocol, and reserved fields (`was_quoted`, `leading_trivia`, `trailing_trivia`) on CST nodes. Internal import sites switched (#396).
- **Step 5 (#398)** — `core/emitter.py` rewritten as a CST visitor. `was_quoted` is populated on `Assignment` nodes during parsing and consumed at emit time. META-dict values are not yet covered by `was_quoted` propagation — deferred to Sprint 3+ work (see Implementation note below).
- **Test corpus expansion (#395)** — HARD_SYMMETRY corpus extended with corner-case fixtures (deeply nested keys, trailing whitespace, multi-byte identifiers).

### Changed
- **`tests/unit/test_writer_reader_symmetry.py`** — `_AUDIT_CARDINALITY_XFAILS` and `_GH385_DEEP_NESTING_XFAILS` are now empty frozensets. The 10 previously strict-xfailed fixtures flip to expected pass:
  - `tests/fixtures/coverage/spec_full.oct.md` (reconciler bridge: blank-line stripping)
  - `tests/fixtures/hydration/collision_source.oct.md`
  - `tests/fixtures/hydration/expected.oct.md`
  - `tests/fixtures/hydration/source.oct.md`
  - `tests/fixtures/hydration/source_all_terms.oct.md`
  - `tests/fixtures/hydration/source_with_version.oct.md`
  - `tests/fixtures/hydration/source_with_wrong_version.oct.md`
  - `tests/fixtures/hydration/vocabulary.oct.md`
  - `tests/fixtures/symmetry/empty_triple_quoted.oct.md` (reconciler bridge: triple-quote collapse)
  - `tests/fixtures/symmetry/deeply_nested_keys.oct.md` (GH#385 corpus expansion)
- **`octave-literacy` and `octave-mastery` skills** — New §7 sections document the `tier_normalize` audit channel, RepairLog completeness semantics, and reconciler-bridge self-deprecation pattern.

### Changed — internal API migration map (test files updated)
- Test files that imported the module-level `validate()` were migrated to the class-based API (`tests/unit/test_schema.py`, `tests/integration/test_e2e.py`, `tests/vectors/test_vectors.py`, `tests/unit/test_unknown_fields.py`, `tests/unit/test_repair.py`, `tests/unit/test_crs_review_schema.py`, `tests/unit/test_forbidden_repairs.py`, `tests/unit/test_gh344_meta_field_false_positive.py`, `tests/unit/test_gh358_meta_id_field.py`). Tests using `validate_frontmatter` (`tests/unit/test_frontmatter_validation.py`) and the `Schema` container (`tests/unit/test_schema_repository.py`) were updated to the new import paths. No test assertions were weakened. The MCP and CLI call sites (`mcp/validate.py`, `mcp/write.py`, `cli/main.py`) already used the class-based `Validator(schema).validate(doc, ...)` surface and required no change.

### Risk closure
This release retires **R2 — `validator_drift_multiple_validators`** from the OCTAVE-MCP North Star Risks. Validator surface is now single-sourced on `class Validator`; there is no second validation path. **SR1-T1 is complete** — all six steps (1 → 2 → 4 → 5 → 3 → 6 per design v1.3 §3a execution order) are now merged.

### Implementation note (reconciler self-deprecation, design §3a)
- The reconciler bridge is a **temporary, self-deprecating mechanism**. The 8 hydration / `deeply_nested_keys` fixtures and the 2 (`spec_full`, `empty_triple_quoted`) fixtures are currently all covered by the bridge because META-side dequoting is not threaded through `was_quoted` (META values live in `Document.meta: dict[str, Any]`, not Assignment nodes). When Sprint 3+ populates `leading_trivia` / `trailing_trivia` (per design §4.5 G1) and the new triple-quote-collapse lexer W-code lands, precise upstream loggers will cover their respective diffs, the de-duplication precondition will fail, and the reconciler will no-op — **no code change required**. See `docs/adr/adr-0006-sr1-t1-grammar-core-design.md` §3a ("Reconciler bridge pattern") for the full rationale.

### Deviation from HO 8/2 split directive
- The HO directive anticipated 8 fixtures flipping via precise `was_quoted` instrumentation and 2 via the reconciler bridge. Empirically, all 10 flip via the reconciler bridge because META-key dequoting (where `TYPE::"SPEC"` → `TYPE::SPEC` happens) operates on `Document.meta: dict[str, Any]` values, not on `Assignment` nodes — the parser does not currently carry `was_quoted` for META values. The precise `TN_IDENTIFIER_DEQUOTE` hook is wired and active for Assignment-shaped values (`§N::CONTENT` body assignments); it simply does not fire on these specific fixtures because their dequoting targets are in META. The reconciler bridge correctly absorbs the gap and self-deprecates the same way once META-side `was_quoted` (or trivia population) lands.

### Quality Gates (at v1.12.0 release HEAD)
- pytest: **3003 passing, 11 skipped, 0 xfailed, 0 failures** (Python 3.11/3.12/3.13 matrix; CI run 25699798578 on c7660ac).
- Property-based tests: 14 passing.
- mypy --strict: clean.
- ruff check / black --check: clean.
- Smoke parity: `canonical_hash` unchanged for both ground-truth fixtures (`3f680a6b…` for `hydration/source.oct.md`; `fc758a43…` for `symmetry/empty_triple_quoted.oct.md`).
- Constitutional compliance: I1, I2, I3, I4 (now fully enforced at boundary cases), I5.

### Added — `format_style` parameter on `octave_write` — #376 PR-A
- **`format_style` parameter on `octave_write`** — New optional parameter on the MCP tool (`format_style`) and CLI command (`--format-style`) accepting `"preserve"`, `"expanded"`, or `"compact"`. The three modes are AST-level pre-passes that funnel into the single canonical `emit()` (I1 Single-Canon Discipline), not parallel emitters:
  - `"preserve"` — Strategy C narrow short-circuit: when `parse(new_content) == parse(baseline_content)`, write baseline bytes verbatim and skip canonical re-emission.
  - `"expanded"` — Lift `InlineMap` (and `ListValue` items that are `InlineMap`) into `Block` form before `emit()`.
  - `"compact"` — Collapse atom-only Blocks (no comments anywhere in subtree, arity ≤ 8) into `inline-list-of-InlineMap` form. Comment-bearing subtrees are vetoed and a new `W_COMPACT_REFUSED` correction is appended to the repair log (I3 Mirror Constraint + I4 Auditability). The CLI surfaces these records on stderr.
  - Unknown values are rejected with `E_INVALID_FORMAT_STYLE` (I5 Schema Sovereignty).

  This is **purely additive**: when the parameter is omitted, today's canonical behaviour is preserved byte-for-byte and all baseline tests pass unchanged. Default behaviour is **not** changed in this release. Richer per-key dirty tracking (Strategy A), deep changes-mode paths, and the SemVer-staged default flip are deferred to [#377](https://github.com/elevanaltd/octave-mcp/issues/377).

## [1.11.0] - 2026-04-17 - "Lexer Safety & Skill Upgrades" Release

This release fixes silent data loss from `#` characters in values and `://` in URLs (W002 warning), hardens the lexer against trailing `#` edge cases, and fixes E005 false positives on digit-prefix hash values. On the skills side, three major version upgrades ship: `octave-literacy` v3.0 (LLM-consumption paradigm), `octave-mastery` v3.0, and `octave-compression` v3.0 with the new ULTRA_MYTHIC compression tier.

### Added
- **`octave-literacy` v3.0** — Upgraded to LLM-consumption paradigm with `NAME<args>` as canonical primary form
- **`octave-mastery` v3.0** — Major skill version upgrade
- **`octave-compression` v3.0** — Major skill version upgrade with ULTRA_MYTHIC compression tier
- **All 3 secretary skills synced to v3.0** — Governance-aligned skill versions across the secretary skill set

### Fixed
- **Silent data loss from `#` in values and `://` in URLs** (W002) — Parser now detects and warns when `#` characters in values or `://` URL patterns would be silently lost during normalization, preventing I1 (Syntactic Fidelity) violations
- **Trailing `#` edge case in lexer** — Lexer now correctly handles trailing `#` characters without misinterpreting them as comment delimiters; also fixes LOSS_PROFILE syntax consistency
- **E005 false positive on digit-prefix hash values** — Lexer no longer raises E005 for values starting with digits followed by hash characters (e.g., `6#abc`)
- **Accidental `dependency-groups` in pyproject.toml** — Removed spurious dependency group added during PR#366; bare operators in SKILL.md wrapped in brackets per spec

### Quality Gates
- All tests passing, 0 failures
- Constitutional compliance verified: I1, I2, I3, I4, I5

## [1.10.0] - 2026-04-08 - "Typed Envelopes & Section-Aware Export" Release

This release delivers typed envelope identifiers, section-aware JSON export, and a batch of 15 parser/lexer/validator improvements resolved in PR#361. Key additions include MCP resource endpoints for GBNF grammars, dynamic FIELDS_OMITTED for projection modes, and section-prefixed path resolution in `octave_write`. The lexer gains unquoted ISO timestamp detection and number+identifier token coalescing, while the validator eliminates false positives for TYPE/VERSION in META blocks.

### Added
- **Typed envelope identifiers (`TYPE:NAME`)** — Parser now supports typed envelope syntax for multi-envelope documents with explicit type discrimination
- **Section-aware JSON export in `octave_eject`** (#341) — New `sections` parameter allows extracting specific sections by ID (e.g., `§3`, `3`, `§3::CAPABILITIES`) with META always included
- **MCP resource endpoints for GBNF grammars** (#280) — New `octave://grammars/{schema_name}` resource URI for pre-compiled grammar access
- **Dynamic `FIELDS_OMITTED` for executive/developer projection** (#281) — Projection modes now include a `FIELDS_OMITTED` marker listing which fields were filtered, improving auditability of lossy projections
- **`ID` as optional first-class META schema field** (#358) — META blocks can now include an `ID` field validated by the schema system
- **`W_NUMERIC_KEY_DROPPED` warning** (#348) — Parser now emits a warning when numeric keys are dropped during normalization, preventing silent data loss
- **`bare_line_dropped` surfaced as top-level warning** (#349) — `octave_write` response now includes `bare_line_dropped` warnings at the top level for immediate visibility
- **DX guidance hints for `E005` and `UNVALIDATED`** (#351, #352) — Error and status messages now include actionable guidance for common developer pain points

### Fixed
- **Validator false positive for `TYPE`/`VERSION` in META** (#344) — META block validator no longer falsely rejects valid TYPE and VERSION fields
- **Literal zone closing fence indentation** (#346) — Emitter now preserves indentation of closing fences in literal zones
- **Auto-quote compound `§` references in `octave_write`** (#334) — Values containing compound section references are now automatically quoted to prevent parser misinterpretation
- **Array-index path rejection in `octave_write` changes** (#335) — Unresolvable array-index paths in the `changes` parameter now raise clear errors instead of silently failing
- **Unquoted ISO timestamp detection in lexer** (#350) — Lexer now detects unquoted ISO timestamps to prevent silent fragmentation of date values
- **Number+identifier token coalescing in lexer** (#356) — Lexer now merges adjacent number and identifier tokens to prevent spurious space insertion in canonical output
- **Section-prefixed path resolution in `octave_write` changes** (#353) — Paths like `§3::SKILLS` now correctly resolve to the target section
- **Uppercase section ID suffixes in `_SECTION_PATH_RE`** (#361) — Section path regex now accepts uppercase suffixes
- **`_SECTION_CONTAINING_TOKEN_RE` swallowing `//` comments** (#361) — Section-containing token regex no longer consumes comment delimiters
- **Slash included in `_SECTION_CONTAINING_TOKEN_RE` character class** (#361) — Fixes regex to include forward slash in the character class
- **Backslash parity in escape-aware auto-quote scanner** (#361) — Auto-quote scanner now correctly handles backslash escape sequences
- **Colon-aware diagnostics for malformed typed envelope identifiers** — Improved error messages when typed envelope syntax is malformed
- **Review findings: dotted key regression, bare flow example, section filter** (#347) — Batch fix for issues discovered during code review
- **Deeply nested section indentation regression tests** (#357) — Added regression tests ensuring correct indentation at deep nesting levels

### Documentation
- **Bare flow operators wrapped in brackets per spec §6** (#345) — Documentation examples updated to use bracket notation for bare flow operators

### Quality Gates
- 2788 tests passing, 0 failures
- Constitutional compliance verified: I1, I2, I3, I4, I5

## [1.9.6] - 2026-03-30 - "CRS_REVIEW Schema" Patch

This patch adds the CRS_REVIEW builtin schema for structured code review artifacts (Issue #342). Replaces verbose 900-line markdown PR comments with compact, machine-parseable OCTAVE output for the HestAI review gate system. Token economy: 30-50% size reduction vs markdown equivalent.

### Schema
- **CRS_REVIEW v1.0.0** — New builtin schema at `schemas/builtin/crs_review.oct.md`
  - `§1::VERDICT` — ROLE (REQ), PROVIDER (OPT), VERDICT (REQ, ENUM[APPROVED,BLOCKED,CONDITIONAL]), SHA (REQ), TIER (REQ, ENUM[T0-T4])
  - `§2::DISTRIBUTION` — TOTAL (REQ), BLOCKING (REQ), TRIAGED (REQ), OMITTED/P0-P5 (OPT)
  - `§3::FINDINGS` — flat sequential inline-map records (no field-level schema validation; content is structural)
  - `§4::SUMMARY` — ASSESSMENT (REQ), TOP_RISKS (REQ, TYPE[LIST])
  - POLICY: UNKNOWN_FIELDS WARN, targets all 4 sections
  - Section-level fields validated via `_build_deep_section_schemas()` (document-type schema pattern, same as COGNITION_DEFINITION)
  - META fields (TYPE, VERSION, SCHEMA_VERSION) validated separately by META block validator, not in FIELDS block

### Design Decisions
- No evidence field — `file` + `line` sufficient; CE reads files independently
- No escalation section — workflow logic stays in agent definition, not data format
- Single string `line` field — `"27"` or `"27-58"` range format
- Flat sequential finding records — no indexed sub-records (F1, F2, etc.)
- UNKNOWN_FIELDS::WARN (not REJECT) — fields are distributed across sections; per-section validation only sees its own subset, so other sections' fields would be false-positive unknowns under REJECT
- No FINDINGS section field constraints — findings are inline maps `[tier::P0,...]` which are structural content, not assignments the schema extractor can constrain

### Tests
- 37 tests across 8 test classes covering schema loading, field definitions, policy, document parsing, validator integration, and negative validation
- Integration tests call `validate()` with `_build_deep_section_schemas()` end-to-end
- Negative tests verify ENUM rejection (invalid VERDICT, invalid TIER) and required field detection (missing VERDICT, missing ASSESSMENT)

### Quality Gates
- All tests passing, 0 failures
- ruff, mypy, black clean

## [1.9.5] - 2026-03-25 - "OCTAVE Acronym Expansion" Patch

This patch adds the full OCTAVE acronym expansion (Olympian Common Text And Vocabulary Engine) across all bundled resource files — primers, specs, skills, and README. Previously the acronym was only defined in archived specs and docs guides, meaning agents loading active resources never learned the full name.

### Documentation
- **Primers** — Updated universal OCTAVE definition from `"Semantic DSL for LLMs"` to `"Olympian Common Text And Vocabulary Engine — Semantic DSL for LLMs"` across all 6 primers
- **Specs** — Added `NAME::"OCTAVE (Olympian Common Text And Vocabulary Engine)"` to core-spec and architecture-spec META; expanded acronym in primers-spec universal definition, skills-spec header, and patterns-spec header
- **Skills** — Added acronym parenthetical to all 5 SKILL.md YAML descriptions
- **Resources README** — Added full name to title and universal definition section

### Changed
- **Primer literal zones** — Mastery, compression, and ultra-mythic primers now use literal zones (fenced code blocks) for teaching examples, preventing normalizer restructuring of pedagogical pseudo-OCTAVE content

## [1.9.4] - 2026-03-24 - "Cognition Spec EPISTEMOLOGY Field" Patch

This patch evolves the cognition spec to v1.2.0, adding an optional EPISTEMOLOGY field to §1::COGNITIVE_IDENTITY NATURE block. EPISTEMOLOGY invokes a named epistemic tradition (e.g. "Aristotelian Logos") to activate pre-trained weight clusters as a decoder key for cognition reasoning style. No functional code changes — spec and schema evolution only.

### Spec Evolution
- **Cognition Spec v1.2.0 — EPISTEMOLOGY Field** — Added optional EPISTEMOLOGY field to §1::COGNITIVE_IDENTITY NATURE block
  - Invokes named epistemic tradition to activate high-quality academic/philosophical clusters in LLM pre-training data
  - Acts as a decoder key for the cognition type's reasoning style
  - Updated FIELD CONTRACT: `NATURE (FORCE/ESSENCE/ELEMENT/EPISTEMOLOGY (OPT)), MODE, PRIME_DIRECTIVE, CRAFT (OPT), THINK, THINK_NEVER`
- **COGNITION_DEFINITION Schema v1.2** — Added `EPISTEMOLOGY::["Epistemic tradition"∧OPT→§SELF]` to FIELDS
  - USAGE_NOTES updated with EPISTEMOLOGY description

### Tests
- Updated schema version assertion from "1.1" to "1.2"
- Added `test_cognition_with_epistemology_validates` — validates cognition file with EPISTEMOLOGY passes
- Added `test_cognition_without_epistemology_validates` — backward compatibility with v1.0.0/v1.1.0 files

### Quality Gates
- 2492 tests passing, 0 failures
- Backward compatible: all existing cognition files validate against updated schema

## [1.9.3] - 2026-03-24 - "Cognition Spec CRAFT Field" Patch

This patch evolves the cognition spec to v1.1.0, adding an optional CRAFT field to §2::COGNITIVE_RULES. CRAFT provides a methodological stance bridging PRIME_DIRECTIVE (existential orientation) and THINK (operational rules). No functional code changes — spec and schema evolution only.

### Spec Evolution
- **Cognition Spec v1.1.0 — CRAFT Field** — Added optional CRAFT field to §2::COGNITIVE_RULES
  - Positioned between PRIME_DIRECTIVE and THINK in the field contract
  - CRAFT provides a "discipline of practice" — semantically distinct from PRIME_DIRECTIVE (perceptual lens) and THINK (operational rules)
  - Updated FIELD CONTRACT comment: `NATURE (FORCE/ESSENCE/ELEMENT), MODE, PRIME_DIRECTIVE, CRAFT (OPT), THINK, THINK_NEVER`
  - v1.1.0 changelog comments documenting the addition and backward compatibility
- **COGNITION_DEFINITION Schema v1.1** — Added `CRAFT::["Methodological stance"∧OPT→§SELF]` to FIELDS
  - USAGE_NOTES updated with CRAFT description
  - POLICY VERSION bumped to 1.1

### Tests
- Updated schema version assertion from "1.0" to "1.1"
- Added `test_cognition_with_craft_validates` — validates cognition file with CRAFT passes
- Added `test_cognition_without_craft_validates` — backward compatibility with v1.0.0 cognition files

### Quality Gates
- 2490 tests passing, 0 failures
- Backward compatible: all three v1.0.0 cognition files (logos, ethos, pathos) validate against updated schema
- Constitutional compliance verified: I1, I2, I5

## [1.9.2] - 2026-03-14 - "Downstream Portability" Patch

This patch fixes skill file portability issues flagged by downstream consumers (HestAI-MCP PR #321). All changes are to bundled skill resources — no functional code changes.

### Fixed
- **`Artemis_Scrape` expression inconsistency** (#336) — Unified `⟨Hidden⟩` (non-OCTAVE syntax) to `Hidden` across octave-mythology §2, §5, §6; quoted THREAT values in §6 for lexer safety
- **Archetype validation regex scope** (#336) — Clarified in §10 that `[A-Z][A-Z_]*` applies to standalone archetypes; compound behavioral expressions (e.g., `Artemis_Scrape`) use Title\_Case prefix
- **Dead file references trimmed** (#336) — Removed ADR-0005 references (evidence already inlined), collapsed §11 RESEARCH\_BACKING to findings-only (stripped 5 file paths agents never follow)
- **Cross-repo reference portability** (#336) — Changed remaining SOURCE/GUIDE/EVIDENCE paths from string literals to constructor syntax (`octave-mcp[path]`), clearly marking them as source-repo references

### Changed
- **Skill versions bumped**: octave-mythology 1.2.0→1.2.1, octave-ultra-mythic 1.2.0→1.2.1, octave-compression 2.5.0→2.5.1

### Quality Gates
- 2488 tests passing, 0 failures
- Constitutional compliance verified: I1, I3, I4, I5

## [1.9.1] - 2026-03-07 - "YAML-Optional Alignment" Patch

This patch aligns the skills and agents specs on a consistent YAML frontmatter contract: YAML is OPTIONAL, required only for platform-deployed files (`.claude/skills/`, `.codex/skills/`), not for hub/system files consumed by the anchor ceremony.

### Spec Evolution
- **Skills Spec v9.1.0 — YAML Optional** — YAML frontmatter changed from mandatory to optional based on deployment context
  - Added `§7::YAML_FRONTMATTER_RULES` documenting three deployment contexts: platform skills (YAML required), hub skills (YAML optional), dual-deployed skills (YAML present in both)
  - `§1::SEQUENCE` updated: OCTAVE envelope is the universal constant, YAML serves platform discovery only
  - `§8::VALIDATION` updated: YAML required only for platform-deployed skills
  - `§11::V9_0_MIGRATION` added: backward compatible — all v9.0 skills remain valid
- **Agents Spec v8.1.0 — YAML Frontmatter Section** — Added `§6::YAML_FRONTMATTER` with matching optional contract
  - Documents existing reality: hub agents have never used YAML and work correctly
  - Provides schema for platform agents (`.claude/agents/`, `.codex/agents/`) if needed
  - Same deployment context structure as skills spec for consistency

### Documentation
- Both specs now follow the same principle: YAML serves platform discovery, OCTAVE serves definition
- Eliminates inconsistency where skills mandated YAML universally while agents never required it

## [1.9.0] - 2026-03-07 - "Cognitive Architecture & Chassis-Profile" Release

This release introduces the cognitive type system — three cognition master files (LOGOS, ETHOS, PATHOS) with a formal spec and schema validation — alongside agents-spec v8.0.0 with chassis-profile capability tiering (ADR-0283), and fixes for angle bracket annotations, deep section schema validation, and `§` quoting false positives.

### Added
- **ADR-0283: Chassis-Profile Capability Tiering** (#283, #330, #331) — Schema-level capability boundaries for agent definitions
  - Two-tier architecture: CHASSIS (invariant skills) + PROFILES (context-specific skill sets)
  - Each profile declares: `match` (documentation-as-schema), `skills`, `patterns`, `kernel_only`
  - Profile selection via explicit `capability_mode` parameter — no filesystem analysis
  - `kernel_only` loads `§5::ANCHOR_KERNEL` extraction only (safety constraints without procedural weight)
  - Backward compatible: flat `SKILLS::[]/PATTERNS::[]` remains valid (v7 format)
  - Version detection: presence of CHASSIS or PROFILES keys triggers structured mode
  - Overlap rules defined for downstream validation: CHASSIS∩profile.skills → error, CHASSIS∩kernel_only → error, duplicate profile names → error, `default` mixed with `context::` → error, 4+ profiles → warning
  - EBNF grammar Section 13 with formal rules for chassis-profile structure
- **`W_UNQUOTED_SECTION_IN_VALUE` warning** (#329) — `octave_write` now warns when unquoted `§` in values is parsed as a section operator, with guidance to quote the value (e.g., `KEY::"value_with_§"`)
- **Cognition Type System** (#322, #324) — Cognitive kernel architecture for Wind/Wall/Door agent archetypes
  - New `octave-cognition-spec.oct.md` schema contract defining `COGNITION_DEFINITION` type with `§1::COGNITIVE_IDENTITY` (NATURE: FORCE/ESSENCE/ELEMENT) and `§2::COGNITIVE_RULES` (MODE, PRIME_DIRECTIVE, THINK, THINK_NEVER)
  - Three cognition master files: `logos.oct.md` (LOGOS/STRUCTURE/DOOR), `ethos.oct.md` (ETHOS/CONSTRAINT/WALL), `pathos.oct.md` (PATHOS/POSSIBILITY/WIND)
  - PRIME_DIRECTIVE triad: "Reveal what connects" / "Reveal what breaks" / "Reveal what could be"
  - Cognitive type system guide with Wind/Wall/Door metaphor (`docs/guides/cognitive-type-system.md`)
- **COGNITION_DEFINITION Schema Registration** (#325, #326) — Schema validation for cognition files
  - New `cognition_definition.oct.md` schema with 7 holographic field constraints (FORCE/ELEMENT/MODE enums, REQ fields)
  - Auto-discovered via existing schema loader — no manual registration code
  - `octave_validate --schema COGNITION_DEFINITION` now returns `VALIDATED` instead of `UNVALIDATED`
  - TYPE-based section matching for multi-envelope documents (COGNITION_LOGOS, COGNITION_ETHOS, COGNITION_PATHOS all validate against single schema)
  - Deep section walking for nested block validation (e.g., NATURE: block inside §1)
  - 14 new tests: schema loading, happy path for all 3 cognition files, 5 negative cases, 3 envelope regression tests

### Fixed
- **`W_UNQUOTED_SECTION_IN_VALUE` false positives** (#329) — Four fixes for the § quoting warning:
  - Array values containing `§` no longer trigger false warnings
  - Unicode operator characters adjacent to `§` no longer misdetected
  - Comments containing `§` no longer trigger warnings
  - Detection now runs on unwrapped content to avoid markdown false positives
- **Comma-separated angle bracket qualifiers** (#320, #321) — `NEVER<PEDANTIC,DISMISSIVE,VAGUE>` constructor syntax inside `::[]` arrays no longer triggers E005 lexer error. Extended `_match_unicode_identifier()` qualifier loop to consume commas between valid identifier segments
- **Envelope-level assignments in deep section schemas** (#326) — Valid envelope-style documents (e.g., DEBATE_TRANSCRIPT with root-level fields) no longer falsely marked INVALID when `META.TYPE` triggers deep section schema path. Added pre-walk pass collecting envelope-level assignments
- **Lite instruction cross-model feedback** (#316) — Tightened guide from zero-shot reviews by Gemini, ChatGPT, Claude Sonnet, and Claude Haiku: defined `NAME[args]` constructor and `---` separator in FORMAT, added quote usage rule, replaced subjective conversion gate with deterministic threshold, added provenance marker to example

### Spec Evolution
- **Agents Spec v8.0.0 — Chassis-Profile** (#283, #314, #319) — Two-release evolution of agent architecture
  - v7.0.0 (Cognitive Separation): Removed ACTIVATION and MODE from §1 → cognition master files; renamed §2 to OPERATIONAL_BEHAVIOR; flattened §1 structure and AUTHORITY fields
  - v8.0.0 (Chassis-Profile): Extended §3::CAPABILITIES with CHASSIS/PROFILES structure for context-aware skill loading; comprehensive documentation of overlap rules, loading semantics, and backward compatibility
- **Skills Spec v9.0.0 — Structural Cleanup** — Evolved from v8.0.0 based on cross-model assessment
  - Fixed META TYPE from `LLM_PROFILE` (copy-paste error) to `SKILL_DEFINITION`
  - Standardized `§5::ANCHOR_KERNEL` as strict section header (replaces inconsistent `ANCHOR_KERNEL::start` syntax)
  - Integrated §2b canonical sections into §3 document template — LLMs now see exact headers to emit
  - Consolidated V5/V6/V7/V8 legacy compatibility into §11::LEGACY_COMPATIBILITY
  - Added SIGNALS and TEMPLATE to kernel field contract; marked NEVER/MUST as required
  - Explicit v8→v9 transition window with grace period through v9.x, hard removal at v10
  - Examples wrapped in literal zones for safe `===END===` inclusion
  - Cascading fallback reworded as extraction priority sequence (resolved logical contradiction)
- **Patterns Spec v2.0.0 — Chassis-Profile Alignment** (#331) — Structural alignment with skills spec v9 and ADR-0283
  - META TYPE: `LLM_PROFILE` → `PATTERN_DEFINITION`
  - Anchor kernel: `§ANCHOR_KERNEL` → `§5::ANCHOR_KERNEL` section header syntax
  - New §8::CHASSIS_PROFILE_LOADING: patterns participate in chassis-profile tiering
  - New §11::LEGACY_COMPATIBILITY: v1→v2 migration with grace period

### Documentation
- **ADR-0283** — Chassis-Profile Schema for Agent Capability Tiering: full design document covering two-tier architecture, loading semantics, overlap rules, Safety-Invariant Loader Contract, and risk mitigations. Approved with ratification debate artifacts
- **`octave-literacy` skill** — Added rule 8 (quote `§` in values) with WRONG/RIGHT example; renumbered file extension rule to 9
- Cognitive type system guide with Wind/Wall/Door metaphor, separation of concerns diagram, evidence basis (#324)
- Repository structure realigned with visibility-rules v1.6 and v1.7 (#323) — debate synthesis files relocated from `.hestai/decisions/` to `debates/`
- CRS review findings resolved: clarified §0 and COGNITION comments in agents spec (#319)
- EBNF grammar extended with Section 13 for chassis-profile capability tiering rules

### Quality Gates
- 2498 tests passing, 0 failures
- Constitutional compliance verified: I1, I2, I3, I4, I5

## [1.8.0] - 2026-03-02 - "Lexical Fidelity" Release

This release enforces quote preservation for PATTERN and REGEX values across all emission paths, adds three new lint warnings for better authoring feedback, and fixes multiple parser/emitter edge cases discovered during agent definition audits.

### Added
- **`W_CONSTRUCTOR_MISUSE` lint warning** (#305) — Known constructor names (`PATTERN`, `REGEX`, `ENUM`, `TYPE`, `NEVER`, `ALWAYS`) used as inline-map assignment keys now emit an advisory warning suggesting constructor form
- **`W_DUPLICATE_KEY` warning for silent key deduplication** (#306) — Parser now warns when duplicate keys appear in the same block, preventing silent last-value-wins data loss
- **`W_PATTERN_AUTOQUOTE` warning** (#310) — Bare `PATTERN`/`REGEX` values are flagged with an I4-compliant audit trail when auto-quoted for lexical matching fidelity

### Fixed
- **PATTERN/REGEX quote preservation** (#310, #311) — Normalizer now always quotes `PATTERN::` and `REGEX::` values, even single bare words, across both assignment and inline-map emission paths. Previously `PATTERN::"Workaround"` was silently stripped to `PATTERN::Workaround`, violating I1 (SYNTACTIC_FIDELITY)
- **Emitter quoting and multiline bugs** (#306) — Resolved 4 issues in `needs_quotes()` and `_needs_multiline()`: expression patterns, annotation patterns, and edge cases in value emission
- **META block comment nesting** (#306) — Keys inside META blocks no longer escape to root level when comments are present
- **META nested block duplicate key tracking** (#306, #307) — Duplicate key detection now works correctly inside nested META blocks
- **Literal zones in `octave_validate`** (#306) — Validation tool now matches `octave_write` parser path for literal zone support
- **YAML frontmatter and CONTRACT field preservation** (#308) — `octave_write` round-trips now preserve YAML frontmatter and META CONTRACT fields
- **Frontmatter inheritance audit trail** (#309) — Skipped frontmatter inheritance now logged for I4 compliance

### Changed
- **Agents spec GATES syntax** (#312) — Updated `octave-agents-spec` line 85 from `GATES::NEVER[prohibited] ALWAYS[required]` to `GATES::[NEVER<prohibited>, ALWAYS<required>]` to match normalizer canonical output and improve LLM comprehension
- **Agents spec block notation** (#309) — Clarified nested structure guidance in agent definition documentation

### Quality Gates
- 26 new tests for PATTERN/REGEX quote preservation (assignment + inline-map paths)
- Constitutional compliance verified: I1, I2, I3, I4, I5

## [1.7.0] - 2026-02-28 - "Parser Resilience" Release

This release hardens the parser and lexer against real-world OCTAVE documents containing operator-rich values, `%` characters, and deeply nested META blocks. It also introduces a reading primer for comprehension-only workflows and documents the OCTAVE vs LLMLingua-2 comparison study.

### Added
- **Reading Primer** (#289) — New `octave-reading-primer.oct.md` for pure comprehension of OCTAVE documents without requiring output generation
- **Literal zones in literacy primer** (#289) — Teaching examples in the literacy primer now use literal zone fencing for clarity
- **OCTAVE vs LLMLingua-2 comparison** (#289) — Example documents and round-trip fidelity analysis comparing OCTAVE semantic compression against LLMLingua-2 extractive compression
- **Compression fidelity round-trip study** (#289) — Research documentation covering CONSERVATIVE-MYTH findings and prose-to-prose baseline measurements
- **Confirmation echo for SOURCE→STRICT compilations** (#287) — `octave_write` now returns a confirmation echo when compiling from SOURCE to STRICT mode

### Fixed
- **POSIX trailing newline in `emit()`** (#284) — `emit()` now ensures output ends with a trailing newline per POSIX text file convention
- **`%` character handling in values** (#287) — Lexer now accepts `%` in values when preceded by alphanumeric characters; restricted `%` handling to value context only; whitespace around `%` in key context correctly detected
- **Operator-rich value preservation in lenient mode** (#287) — Parser now preserves values containing multiple operators (e.g., `⊕`, `∧`, `→`) without splitting or reinterpreting them
- **META block parent-child association** (#287) — META blocks no longer absorb root-level keys that follow them; block parent-child association correctly preserved
- **Reading primer output format** (#289) — Reading primer now produces natural prose comprehension, not field-by-field translation

### Changed
- **Literacy primer updated** (#289) — Added reading context section for bidirectional OCTAVE literacy (read + write)
- **Skills simplified** (#289) — `SPEC_REFERENCE` in skills reduced to file-level references only
- **README quick-start rewritten** (#289) — Honest compression claims replacing overstated token savings

### Documentation
- **ADR-0005** (#290, #292) — OCTAVE v1.5 Compiler Shift + Operator Evolution decision record, with cross-model validation study
- **Repo structure realigned** (#290) — Documentation structure aligned with visibility-rules v1.6

### Quality Gates
- 2301 tests passing (10 skipped), 0 failures
- Constitutional compliance verified: I1, I2, I3, I4, I5

## [1.6.0] - 2026-02-26 - "Validation Loop" Release

This release closes the Validation Precedes Generation loop: agents now receive INVALID status plus compiled GBNF grammar in a single round-trip, eliminating the need for a separate `octave_compile_grammar` call.

### Added
- **`grammar_hint` parameter for `octave_validate` and `octave_write`** (GH#278) — When `grammar_hint=true` and validation returns INVALID, the compiled GBNF grammar is included directly in the response. Closes the "Validation Precedes Generation" loop so agents can regenerate immediately without a second round-trip.

### Fixed
- **Stable `E_GRAMMAR_COMPILE` error code** (GH#278) — Grammar compilation failures now return a structured error code instead of leaking raw exceptions into tool responses.

### Documentation
- **README rewrite** — Three-audience structure (Engineers, Researchers, AI Agents) with prose-to-OCTAVE before/after example; removed stale v0.6.0 claims and unexplained jargon
- **Updated stale CRITICAL_GAPS** (GH#279) — Architecture and execution specs now reflect v1.5.0 reality; resolved gaps (grammar compilation, JIT grammar, unknown-fields policy) moved to `RESOLVED_GAPS` sections

### Quality Gates
- 2282 tests passing, 0 failures
- Constitutional compliance verified: I1, I2, I3, I4, I5

## [1.5.0] - 2026-02-24 - "Parser Resilience" Release

This release introduces the `octave_compile_grammar` MCP tool, Zone 2 frontmatter validation, multi-line array emission, and resolves a broad set of parser and emitter robustness issues surfaced through systematic GitHub issue review.

### Added
- **`octave_compile_grammar` MCP tool** (#228) — New fourth tool exposing the GBNF grammar compiler directly, with error-envelope hardening and native const type preservation
- **I5 Zone 2 frontmatter validation** (#244) — Opt-in YAML frontmatter validation extending Schema Sovereignty to Zone 2. New error codes: `E_FM_REQUIRED`, `E_FM_TYPE`, `E_FM_PARSE`. First use-case: SKILL schema validates both OCTAVE body and YAML frontmatter
- **`normalize` mode for `octave_write` tool** — Validates and normalizes a document without writing to the file system; useful for dry-run checks and CI pipelines
- **SKILL builtin schema** (`schemas/builtin/skill.oct.md`) — Validates both the OCTAVE body and YAML frontmatter of skill files
- **Multi-line emission for structured arrays** (GH#267) — Arrays with 3+ items now emit in multi-line format for readability; empty InlineMap guard prevents emission errors
- **Curly-brace repair candidate warning** (GH#263, GH#264) — Lexer emits `W_REPAIR_CANDIDATE` for curly-brace annotations; `octave_write` scopes repair to Zone 1 only, skipping quoted strings and literal zones

### Fixed
- **Constructor `NAME[args]` round-trip preservation** (GH#276) — Adjacency check, expanded token types, blacklist filtering of COMMENT/NEWLINE/INDENT tokens in bracket capture; fixes data loss for spaced brackets and multi-line constructors
- **Comments inside array brackets** (GH#272) — `//` comments inside array bracket context now correctly stripped during parsing
- **Annotated identifier coalescing** (GH#269) — Unified accumulator prevents multi-word coalescing of annotated identifiers
- **Duplicate key warnings in arrays** (GH#270) — False duplicate key warnings suppressed for repeated keys within array contexts
- **Canonicaliser numbered-key syntax inside list literals** (#246) — `1::"value"` patterns inside list literals no longer flattened to separate tokens; fixes round-trip fidelity for numbered keys
- **Emitter InlineMap bracket wrapping in lists** — Prevents nested list artifacts on re-parse when InlineMaps appear inside list values
- **Literal zone content in block body** (#259) — Literal zone content now preserved correctly when appearing inside block bodies
- **Bracket annotation after flow expressions** (#261) — Parser now consumes bracket annotations following flow expressions
- **Write tool robustness** (GH#263, GH#266) — Tightened structure detection to require `::` or `===` signals; graceful baseline parse failure handling; narrowed exception handling with audit receipts; escaped quote handling in curly-brace repair
- **Grammar compiler** — Preserved native const types and hardened error-envelope handling

### Documentation
- Archived mythology debate decisions from issue #110 review session
- Restored mythological compression principle across OCTAVE documentation (#110)
- Normalized all decision docs to OCTAVE canonical form
- Updated schema-spec to reflect all gaps implemented

### Quality Gates
- 2258 tests passing, 0 failures
- Constitutional compliance verified: I1, I2, I3, I4, I5

## [1.4.1] - 2026-02-22 - "Spec Hygiene" Patch

### Fixed
- **8 active .oct.md spec/primer parse failures** — All bundled specs and primers now parse cleanly
  - Primers spec: quoted bare `<`, `%`, `==` characters
  - Compression primer: quoted `§_names` value
  - Agents, patterns, skills specs: restructured nested inline maps to block format
  - Execution, rationale specs: closed unclosed lists, quoted `vs` boundary values
  - ADR-003: replaced bare backticks with quoted strings
- Cleared `KNOWN_ISSUES` in `test_spec_validation.py` — all specs pass validation

## [1.4.0] - 2026-02-22 - "Annotation Syntax" Release

This release introduces angle-bracket annotation syntax (`NAME<qualifier>`) as a new identifier feature, fixes bracket-depth-aware salvage in `octave_write`, and resolves spec parse failures blocking CI validation.

### Added
- **NAME\<qualifier\> Annotation Syntax** (#248) — New angle-bracket annotation syntax for identifiers
  - Lexer tokenizes `NAME<qualifier>` as a single IDENTIFIER token
  - Emitter preserves annotations in canonical output without quoting
  - Replaces `NAME{qualifier}` which conflicted with bracket parsing
  - Spec updates: core v6.0.0, rationale v6.0.0, agents v6.2.0

### Fixed
- **Bracket-depth-aware salvage** (#248) — `octave_write` salvage mode now correctly counts bracket depth
  - Previously could mis-count brackets inside quoted strings
  - Tightened emitter regex for quote-aware bracket matching
- **Primers spec parse failure** — Fixed bare `\n` in `FORMAT` value causing E005 lexer error
  - Restructured value to use quoted string representation
- **Compression primer parse failure** — Fixed bare `>` character causing E005 lexer error
  - Quoted the value containing the `>` to prevent angle-bracket ambiguity

### Documentation
- EBNF grammar updated with `angle_annotation` production rule and Appendix C note (Section 10, Note 9)
- Spec files updated for annotation syntax documentation

### Quality Gates
- 2080 tests passing, 0 failures
- Constitutional compliance verified: I1, I2, I3, I4, I5

## [1.3.0] - 2026-02-19 - "Three-Zone Model" Release

This release completes the Three-Zone Model architecture for OCTAVE documents, delivering Zone 3 (Explicit Literal Zones) as a new first-class language feature and fixing Zone 2 (Preserving Container) which was silently broken.

### Added

- **Literal Zones — Zone 3** (#235) - Fenced code blocks as first-class OCTAVE values
  - New `LiteralZoneValue` AST node with verbatim content preserved without normalization
  - Backtick fence syntax (`` ` `` `` ` `` `` ` ``) for literal zone values with optional language tags (e.g. `` ```python ``)
  - `FENCE_OPEN`, `FENCE_CLOSE`, `LITERAL_CONTENT` token types in lexer
  - NFC normalization bypass inside literal zones (I1 compliance — preserving meaning)
  - Tab bypass inside literal zones
  - Round-trip fidelity: `parse(emit(parse(D))) == parse(D)` for all literal zones
  - `LiteralZoneRepairLog` for I4 audit trail
  - `TYPE[LITERAL]` schema constraint for validating literal zone fields
  - `LANG[python]` schema constraint for requiring specific language tags
  - Zone reporting in all three MCP tools (`octave_validate`, `octave_write`, `octave_eject`)
  - `contains_literal_zones`, `literal_zone_count`, `literal_zones_validated` flags in all tool responses
  - A9 migration gate: existing documents unaffected (non-breaking)
  - LITERAL type documented in core spec and EBNF grammar

### Fixed

- **Zone 2 Container Preservation** (#234) - YAML frontmatter now preserved through `emit()` round-trips
  - Parser correctly stored `raw_frontmatter` on `Document` AST but emitter silently discarded it
  - `emit()` now prepends frontmatter byte-for-byte before grammar sentinel and envelope
  - Empty and whitespace-only frontmatter correctly treated as absent (prevents empty `---\n\n---` blocks)
  - All three MCP tools inherit preservation automatically via `emit()` pipeline
  - Skill files, pattern files, and agent files with YAML discovery headers now work correctly with `octave_write`
  - 9 new tests: round-trip, byte-for-byte fidelity, format options interaction, edge cases

### Architecture

- **Three-Zone Model** fully implemented:
  - Zone 1: Normalizing DSL — canonical operators, unicode normalization, deterministic emit (enforced since v1.0.0)
  - Zone 2: Preserving Container — YAML frontmatter byte-for-byte preservation (completed in this release)
  - Zone 3: Explicit Literal Zones — fenced code blocks with zero processing (new in this release)
- North Star updated to v1.2 reflecting Three-Zone Model as structural pattern

### Quality Gates

- All changes reviewed per tier requirements (CRS + CE dual gate)
- 2039 tests passing, 0 failures
- Constitutional compliance verified: I1, I2, I3, I4, I5

## [1.2.1] - 2026-02-15 - "Specification Refinement" (Re-release)

This is a re-release of v1.2.0 to fix a critical packaging issue where `__version__` in `__init__.py` was not synchronized with `pyproject.toml`.

### Fixed
- **Package Version Synchronization** (#231) - Critical fix for version reporting
  - Updated `__version__ = "1.2.1"` in `src/octave_mcp/__init__.py` to match `pyproject.toml`
  - v1.2.0 on PyPI contained incorrect version "0.6.1" in the package code
  - This caused installation verification failures and incorrect version reporting

**Note:** v1.2.0 should be considered broken and v1.2.1 should be used instead. The v1.2.0 release will be yanked on PyPI.

### All v1.2.x Changes

Same features and fixes as v1.2.0 (see below), but with correct version synchronization.

## [1.2.0] - 2026-02-15 - "Specification Refinement" Release (YANKED - use v1.2.1)

This release enhances the specification suite with improved skills and agents specs, and introduces Streamable HTTP transport for web-based client access.

### Added
- **Streamable HTTP Transport** (#218, #221) - Web-based clients can now access OCTAVE tools via HTTP
  - Single `/mcp` endpoint per MCP Streamable HTTP specification
  - DNS rebinding protection enabled by default via `TransportSecuritySettings`
  - Localhost binding (127.0.0.1) by default for security
  - CLI support: `--transport http --port 8080 --host 127.0.0.1`
  - Environment variables: `MCP_TRANSPORT`, `MCP_HOST`, `MCP_PORT`
  - Health check endpoint at `/health` for load balancers
  - Stateless mode support for serverless deployments (`--stateless`)
  - New optional `[http]` dependency group: `pip install octave-mcp[http]`
  - 31 new tests covering transport, security, CLI, and integration
- **Enhanced Skills Specification** (#225) - octave-skills-spec v8.0 with canonical structure requirements
  - Compression mandate for all skills (AGGRESSIVE tier minimum)
  - Standardized canonical sections: ESSENCE, SYNTAX, CONSTRAINTS, VALIDATE
  - Clarified that archetype vocabulary is open (extensible), not closed
- **Enhanced Agents Specification** (#225) - octave-agents-spec v6 improvements
  - Added `AUTHORITY` as optional field for agent role hierarchy
  - Enables explicit authority level declarations for agent coordination

### Changed
- **Documentation Clarity** (#229) - README improvements for generative constraints
  - Clarified implementation status of generative holographic contracts
  - Updated feature documentation to reflect current capabilities

### Fixed
- **Specification Syntax** (#227) - Fixed OCTAVE spec compliance issues
  - Fixed `MARKDOWN_EMBEDDING` value quoting to prevent lexer errors
  - Aligned specs and `octave_write` tool with markdown code fence syntax
  - Ensures all specifications parse correctly without syntax warnings

### Quality Gates
- All changes reviewed per tier requirements
- Constitutional compliance verified: I1, I3, I5
- HTTP transport includes comprehensive security testing

## [1.1.0] - 2026-02-02 - "Decision Scaffolding" Release

This release enhances OCTAVE Primers with decision scaffolding for semantic compression, corrects token budget specifications to match empirical measurements, and fixes parser comment preservation edge cases.

### Added
- **Compression Primer Decision Scaffolding** (#220) - Enhanced primer enables tier-based compression judgment
  - `§2::DECIDE` section with explicit tier selection (LOSSLESS/CONSERVATIVE/AGGRESSIVE/ULTRA)
  - `PRESERVE` and `DROP` rules per tier for semantic judgment
  - Concrete MAP section showing prose→OCTAVE transformations
  - Complex ONE_SHOT demonstrating hierarchy, flow, and tension operators together
  - `⊕` synthesis operator added to syntax reference
- **Universal LLM Onboarding Architecture** (#214, #215) - Research documentation for JIT literacy injection
  - Wind/Wall/Door debate transcript demonstrating synthesis methodology
  - Proof of concept for primer-based agent bootstrapping

### Changed
- **Primer Token Budget Corrected** (#220) - Spec updated to match empirical tiktoken measurements
  - `TOKEN_BUDGET::MAX[60]` → `MAX[300]_RECOMMENDED[200-260]`
  - Anti-pattern: "Exceeding_100_tokens" → "Exceeding_300_tokens"
  - Added note: OCTAVE syntax tokenizes ~5x word count due to `::`, `→`, `⊕`, `⇌`, `§` operators
  - Validation criteria: `tokens<60` → `tokens<300`
- **README Literacy Primer** (#215) - Embedded primer directly in README for instant LLM onboarding
- **Core Spec Token Count** (#216) - Corrected META.TOKENS from ~2500 to ~2650

### Fixed
- **Parser Comment Preservation** (#217, #219) - Leading comments inside sections now preserved before first child
  - Previously, comments at the start of a section block were dropped during parsing
  - Now correctly captured in AST and emitted in canonical output
  - Added regression tests to prevent future issues

### Quality Gates
- All changes reviewed per tier requirements
- Constitutional compliance verified: I1, I3, I4
- Primer changes maintain ULTRA compression tier

## [1.0.0] - 2026-01-30 - "Generative Holographic Contracts" Release

This release marks the stable v1.0.0 of OCTAVE-MCP, completing four internal milestones (M1-M4) with full OCTAVE v6 specification compliance. OCTAVE-MCP is now production-ready for LLM communication with generative holographic contracts.

### Added

#### M1: Parser Hardening (v0.7.0-internal) - #194
- **Duplicate Key Detection** (#179) - Parser now detects and warns on duplicate keys within the same block
- **Unbalanced Bracket Detection** (#180) - Improved error messages for unclosed `[` brackets with position tracking
- **Spec Compliance Warnings** (#184) - Added warnings for NEVER rules from octave-core-spec (e.g., trailing commas)
- **Inline Map Nesting Validation** (#185) - Validates inline map nesting depth with configurable limits

#### M2: Developer Experience (v0.8.0-internal) - #198
- **Variable Syntax Support** (#181) - Added `$VAR` and `${VAR}` variable reference syntax in OCTAVE documents
- **Comment Preservation** (#182) - Comments are now preserved during normalization and round-trip parsing
- **Validation Profiles** (#183, #197) - Four profiles: `STRICT`, `STANDARD`, `LENIENT`, `ULTRA` for flexible validation
- **Token-Efficient Response Modes** (#195, #196) - Added `diff_only` and `compact` modes to reduce MCP response size
- **Deep Nesting Warning** (#192) - Configurable warning threshold for deeply nested structures
- **Auto-Format Options** (#193) - Formatting options for canonical emission (indentation, line width)

#### M3: Schema Foundation (v0.9.0-internal) - #199
- **Holographic Pattern Parsing** (#187) - Full support for `["example"^CONSTRAINT->TARGET]` syntax with registry
- **Target Routing System** (#188) - Block-level routing with `TargetRegistry` and `TargetRouter` for `->TARGET` directives
- **Block Inheritance** (#189) - `BLOCK[->TARGET]:` syntax for inheriting parent constraints
- **POLICY Block Enforcement** (#190) - New `POLICY::` block type for governance declarations

#### M4: Generative Contracts (v1.0.0) - #204, #205, #207
- **Complete GBNF Integration** (#171, #204) - Full llama.cpp GBNF grammar generation for LLM backend constrained decoding
- **Emoji and Unicode Symbol Support** (#186, #204) - Keys can now contain emoji and extended Unicode symbols
- **META Schema Compilation** (#191, #205) - Self-describing documents with `META.CONTRACT::HOLOGRAPHIC[...]` compilation
- **META.CONTRACT in GBNF Export** (#207) - `octave_eject` now includes META.CONTRACT field in GBNF output

#### Documentation - #202, #208
- **Formal EBNF Grammar Specification** (#113, #208) - Complete formal grammar at `docs/grammar/octave-v1.0-grammar.ebnf`
- **Patterns Specification** (#202) - New `octave-patterns-spec.oct.md` with `ANCHOR_KERNEL` support
- **Grammar Test Vectors** - Valid and invalid example files for grammar testing

#### Infrastructure - #203, #206
- **Context File Synchronization** (#203) - Updated `.hestai/context/` files to reflect M1-M3 completion
- **Startup Dependency Sync** (#206) - MCP server now validates venv dependencies on startup to prevent stale environments

### Changed
- **Emitter Improvements** (#200, #201) - Block target annotations (`[->TARGET]`) and `HolographicValue` emission using `raw_pattern`
- **Test Infrastructure** - Test count increased from 706 to ~1610 passing tests
- **Quality Gates** - All changes validated against mypy, ruff, black, pytest with 90%+ coverage

### Fixed
- **Critical octave_write Issues** (#176, #177, #178) - Fixed file writing edge cases and validation errors
- **Emitter Target Annotations** (#201) - Correctly emit block target annotations in canonical output
- **HolographicValue Emission** (#200) - Fixed raw pattern preservation in holographic value emission

### Quality Gates
- All milestones reviewed by Critical Review Specialist (Gemini/LOGOS)
- Constitutional compliance verified: I1, I2, I3, I4, I5
- Parser hardening prevents silent data loss (I3 compliance)
- All changes include comprehensive test coverage

## [0.6.1] - 2026-01-12

### Added
- **Validator Frontmatter Support** - Added `--require-frontmatter` flag to `octave-validator` tool
  - Aligns repo validator with core parser/validator behavior
  - Broadens spec parsing coverage for documents with frontmatter
  - Backward compatible - flag is optional

### Fixed
- **Template Generation** - Fixed `octave_eject` template to produce valid OCTAVE
  - Replaced markdown-style `#` comments with OCTAVE `//` syntax
  - Templates now parse correctly without syntax errors
  - Added regression test to prevent future template syntax issues

## [0.6.0] - 2026-01-12 - "Structural Integrity" Release

This release strengthens OCTAVE's structural validation, fixes critical parser issues, and refines the specification suite through dogfooding and systematic cleanup.

### Added
- **Section Name Preservation Rule** - Three-layer defense preventing compression of section identifiers
  - Core spec: `SECTION_NAMES::preserve_exactly` in §4::STRUCTURE
  - Primers spec: Required validation items in §2e::VALIDATE
  - All primers: `preserve_§_names_verbatim` in §5::VALIDATE sections
  - Prevents §1::ESSENCE → §1::ESS compression that breaks parsers
- **Strict Structural Validation** - Parser now has `strict_structure` mode
  - `parse()` uses strict mode by default (fail fast on malformed documents)
  - `parse_with_warnings()` remains lenient for recovery workflows
  - Exported `parse_with_warnings()` for discoverability
- **CI Specification Validation** - All OCTAVE spec files now validated in CI pipeline
  - Ensures specs comply with their own syntax rules (dogfooding)
  - Catches regressions in specification quality

### Changed
- **Specification Naming Convention** - Renamed all spec files for clarity
  - `octave-6-llm-*` → `octave-*-spec` (e.g., `octave-core-spec.oct.md`)
  - Updated all REQUIRES references across specification suite
  - Cleaner, more intuitive naming pattern
- **Primer Structural Alignment** - Ultra-mythic primer updated to v6.1.0
  - §2::TEMPLATE → §2::MAP (matches spec structure)
  - §4::EXAMPLE → §4::ONE_SHOT (matches spec structure)
  - Simplified primer naming: `===NAME===` instead of `===NAME_PRIMER===`
- **Enhanced Core Specification** - Comprehensive quoting rules and holographic principle documentation
  - Added §3b::QUOTING_RULES with explicit guidance
  - Enhanced §6b::VALIDATION_CHECKLIST
  - Clarified holographic contract principles

### Fixed
- **Parser Silent Data Loss** (Issue #162) - Critical fix for unclosed lists at EOF
  - Parser now raises E007 error in strict mode for unclosed lists
  - Lenient mode emits I4 warning with audit trail
  - Prevents silent acceptance of malformed documents
  - Constitutional compliance: I3 (Mirror Constraint), I4 (Transform Auditability)
- **Specification Dogfooding** - Fixed syntax violations in 10+ spec files
  - All specs now comply with octave-core-spec rules
  - Systematic cleanup of quoting, spacing, structure issues
  - Validates OCTAVE's ability to describe itself correctly
- **Test Infrastructure** - Added timeout protection to spec validation tests
  - Prevents CI hangs on malformed specifications
  - 1221 tests passing, 9 skipped

### Quality Gates
- All changes reviewed by Critical Review Specialist (Gemini/LOGOS)
- Critical Engineer approval on parser fixes
- Constitutional compliance verified: I1, I3, I4, I5
- Strict mode prevents I3 violations (accepting incomplete structures)

## [0.5.0] - 2026-01-11 - "Universal Anchor" Release

This release introduces OCTAVE Primers for ultra-efficient agent bootstrapping and completes
the architectural separation of the OCTAVE language specification from implementation details.

### Added
- **OCTAVE Primers** - Ultra-compressed bootstrapping documents (40-60 tokens vs 500-800 for full skills)
  - Universal OCTAVE definition: "Semantic DSL for LLMs"
  - Complete primer set: literacy, compression, mastery, mythology, ultra-mythic
  - Primer Specification v3.0.0 with 5-section structure (ESSENCE, MAP, SYNTAX, ONE_SHOT, VALIDATE)
  - Self-referential compression (primers use the format they teach)
  - 93.75% token savings for agent initialization
- **Octave v6 "Dual-Lock" Schema Specification**
  - Defines strict separation of Identity (Shank) and Behavior (Conduct)
  - Supports `MODEL_TIER` (Premium/Standard/Basic) and `ACTIVATION` (Force/Essence/Element)
  - Enables "Holographic Contract" self-validation within agent files
- **Patterns Support**: Updated Spec to include `PATTERNS::[...]` in Capabilities manifest
- **Resource Consolidation**: All specs, primers, and skills now distributed as package resources
  - Accessible via `importlib.resources` API
  - JSON Schema documentation restored to `resources/specs/schemas/json/`
  - Complete Python package structure with proper `__init__.py` files
- **Comprehensive Test Coverage**: Added tests for resource accessibility and structure validation

### Changed
- **Architectural Separation**: Removed specific HestAI agent implementations (Holistic Orchestrator, etc.) from `octave-mcp` repo
  - Moved agent/skill/pattern content to `hestai-mcp/_bundled_hub` as the reference library
  - `octave-mcp` now serves as the pure Language Specification and Parser
- **Spec Purification**:
  - Renamed `BIND` -> `CORE` in Identity spec to correct semantic verb/noun mismatch
  - Removed `UNIVERSAL_LAWS` from spec to prevent polluting the language with system-specific business logic
- **Vocabulary Alignment**: Updated Spec Activation block to use Debate Hall metaphors (`GUARDIAN`/`EXPLORER`/`ARCHITECT`) instead of generic text
- **Resource Organization**: Consolidated all documentation into `src/octave_mcp/resources/` for single source of truth
  - Removed duplicate `specs/`, `primers/`, and `skills/` folders at root
  - Updated all import paths and references

### Fixed
- Removed non-existent `SESSION_LOG` vocabulary from registry that would cause `FileNotFoundError`
- Updated test paths to use consolidated resource locations
- Fixed package data configuration to include all resource subdirectories

## [0.4.1] - 2026-01-07

### Fixed
- Hermetic schema resolution in `octave_write` tool - now uses `resolve_hermetic_standard` for `frozen@` and `latest` schema references (Issue #150)

### Added
- Type hints and improved documentation in write tool hermetic resolution path

## [0.4.0] - 2026-01-07

### Added
- **Generative Holographic Contracts** (ADR-003): Multi-dimensional validation with incremental integrity enforcement
  - Hermetic Anchoring: Contextual identity binding via `odyssean_anchor` tool with RAPH vectors (Request, Assignment, Permit, Hash)
  - v6 OCTAVE specification support with pattern-based validation and regex compilation
  - `debug_grammar` parameter in `octave_validate` for grammar debugging output
  - Progressive integrity model: v4 (Structural) → v5 (Syntactic) → v6 (Semantic+Hermetic)

### Changed
- Enhanced validation architecture with tier-based approach (quick/default/deep)
- Improved schema sovereignty with regex pattern compilation

## [0.3.1] - 2026-01-04

### Added
- `list_exports()` helper function for API discovery - easily explore all 52 public exports by category
- Regression tests covering semantic version strings (`VERSION` token) and multi-word value handling

### Fixed
- Handle semantic version strings (e.g., `1.2.3`, prerelease/build forms) via `VERSION` tokenization (#140, #141, #142)
- Prevent `VALUE_TOKENS` data loss in multi-word values; unify value token handling in parser/lexer (#140, #141, #142)
- Restrict `GRAMMAR_SENTINEL` matching to document start only (#142)

## [0.3.0] - 2026-01-04

### Added
- **51 public API exports** enabling external packages to import OCTAVE functionality
  - Core functions: `parse()`, `emit()`, `tokenize()`, `repair()`, `project()`
  - Core classes: `Parser`, `Validator`, `TokenType`, `Token`
  - AST nodes: `Document`, `Block`, `Assignment`, `Section`, `ListValue`, `InlineMap`, `Absent`
  - Hydration: `hydrate()`, `HydrationPolicy`, `VocabularyRegistry`
  - Schema: `SchemaDefinition`, `FieldDefinition`, `extract_schema_from_document()`
  - Repair (I4): `RepairLog`, `RepairEntry`, `RepairTier`
  - Routing (I4): `RoutingLog`, `RoutingEntry`
  - Sealing: `seal_document()`, `verify_seal()`, `SealVerificationResult`
  - Exceptions: 9 exception types for granular error handling
  - Operators: `OCTAVE_OPERATORS` dict + 10 `OP_*` constants
- Comprehensive API documentation in `docs/api.md`
- PyPI package distribution

### Fixed
- CLI version reporting now uses package version instead of hardcoded value
- Version alignment across all components (pyproject.toml, __init__.py, CLI)

### Changed
- Package version updated from 0.2.0 to 0.3.0

## [0.2.0] - 2025-12-28

### Added
- MCP (Model Context Protocol) server implementation
  - `octave_validate` tool - Schema validation with repair suggestions
  - `octave_write` tool - Unified file writing with CAS support
  - `octave_eject` tool - Multiple projection modes (canonical, authoring, executive, developer)
- Comprehensive schema validation system (I5 - Schema Sovereignty)
- Repair log functionality for audit trail (I4 - Transform Auditability)
- Routing log for transformation tracking
- Document sealing for integrity verification
- Hydration system with vocabulary registry
- Support for holographic patterns

### Changed
- Consolidated from multiple tools to three core MCP tools
- Improved error handling and validation messages
- Enhanced lenient parsing with better error recovery

### Fixed
- Parse error handling for edge cases
- Idempotency issues in canonical emission

## [0.1.0] - 2025-12-15

### Added
- Initial OCTAVE specification implementation
- Core parser and lexer
- AST (Abstract Syntax Tree) nodes
- Basic emit functionality for canonical output
- Support for OCTAVE operators (both Unicode and ASCII)
- Command-line interface (`octave` command)
- Test suite with >1000 tests
- Five core immutables:
  - I1: Syntactic Fidelity
  - I2: Deterministic Absence
  - I3: Mirror Constraint
  - I4: Transform Auditability
  - I5: Schema Sovereignty

### Features
- Lenient-to-canonical transformation pipeline
- Loss accounting for LLM communication
- Non-reasoning document processing
- Deterministic, idempotent transformations

[Unreleased]: https://github.com/elevanaltd/octave-mcp/compare/v1.14.0...HEAD
[1.14.0]: https://github.com/elevanaltd/octave-mcp/compare/v1.13.1...v1.14.0
[1.13.1]: https://github.com/elevanaltd/octave-mcp/compare/v1.13.0...v1.13.1
[1.13.0]: https://github.com/elevanaltd/octave-mcp/compare/v1.12.0...v1.13.0
[1.12.0]: https://github.com/elevanaltd/octave-mcp/compare/v1.11.0...v1.12.0
[1.11.0]: https://github.com/elevanaltd/octave-mcp/compare/v1.10.0...v1.11.0
[1.10.0]: https://github.com/elevanaltd/octave-mcp/compare/v1.9.6...v1.10.0
[1.9.6]: https://github.com/elevanaltd/octave-mcp/compare/v1.9.5...v1.9.6
[1.9.5]: https://github.com/elevanaltd/octave-mcp/compare/v1.9.4...v1.9.5
[1.9.4]: https://github.com/elevanaltd/octave-mcp/compare/v1.9.3...v1.9.4
[1.9.3]: https://github.com/elevanaltd/octave-mcp/compare/v1.9.2...v1.9.3
[1.9.2]: https://github.com/elevanaltd/octave-mcp/compare/v1.9.1...v1.9.2
[1.9.1]: https://github.com/elevanaltd/octave-mcp/compare/v1.9.0...v1.9.1
[1.9.0]: https://github.com/elevanaltd/octave-mcp/compare/v1.8.0...v1.9.0
[1.8.0]: https://github.com/elevanaltd/octave-mcp/compare/v1.7.0...v1.8.0
[1.7.0]: https://github.com/elevanaltd/octave-mcp/compare/v1.6.0...v1.7.0
[1.6.0]: https://github.com/elevanaltd/octave-mcp/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/elevanaltd/octave-mcp/compare/v1.4.1...v1.5.0
[1.4.1]: https://github.com/elevanaltd/octave-mcp/compare/v1.4.0...v1.4.1
[1.4.0]: https://github.com/elevanaltd/octave-mcp/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/elevanaltd/octave-mcp/compare/v1.2.1...v1.3.0
[1.2.1]: https://github.com/elevanaltd/octave-mcp/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/elevanaltd/octave-mcp/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/elevanaltd/octave-mcp/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/elevanaltd/octave-mcp/compare/v0.6.1...v1.0.0
[0.6.1]: https://github.com/elevanaltd/octave-mcp/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/elevanaltd/octave-mcp/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/elevanaltd/octave-mcp/compare/v0.4.1...v0.5.0
[0.4.1]: https://github.com/elevanaltd/octave-mcp/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/elevanaltd/octave-mcp/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/elevanaltd/octave-mcp/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/elevanaltd/octave-mcp/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/elevanaltd/octave-mcp/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/elevanaltd/octave-mcp/releases/tag/v0.1.0
