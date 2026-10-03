# OCTAVE-MCP holistic audit, 3 October 2026

**State audited:** `main` at `cdfc963` (v1.16.0). **Companion evidence:** `elevanaltd/octave-wire-bench` at `38e3d21` (runs baseline, e1, e1b; spec branches for Experiments 5 and 6).
**Audience:** the operator, and the agents running the wire-bench experiments.
**Method:** every quality gate run locally; every open parser issue reproduced; five independent area audits (core pipeline, MCP/CLI layer, shipped resources, documentation and evidence, tests/CI/packaging) with file:line evidence; both wire-bench RESULTS files and the baseline report read in full. Nothing in either repo was modified. Scratch scripts and full tables are referenced where they exist.

---

## 0. The answer in one page

**The code is a working, well-tested canonicaliser with a receipt problem.** All gates pass (ruff, black, mypy, 3608 tests, 89% coverage). The shipped corpus round-trips to a fixed point (40 of 40 parseable files). But the parser and emitter still silently drop or rewrite content in a dozen reproducible cases, including three open issues that reproduce on `main` today (#509 path replaced by a single glyph, #533 document truncated after a bare `===END===` inside a value, #510 canonical output not a fixed point for quoted `→`). None of these produce a RepairLog entry, and the CLI exits 0 on all of them. I4 (every transform logged) is the invariant the project is named for and the one it least upholds.

**The shipped primers are the one clean, measured, enforced part of the resource family.** The skills around them are 2 to 7 times over their own spec's budget, 18% of the resource text is restatement, five specs lose their own content under STRICT canonicalisation, and the chatter skill carries three rules the bench has refuted plus an ASCII-normalisation claim the lexer contradicts.

**The documentation is larger than the product and much of it is stale or circular.** Tool count is wrong in four documents, the test badge is wrong, the "100% zero-shot, 60-70% reduction, 10x density" triple rests on four quotes from two Gemini models quoted four layers deep, the README's central handoff narrative is now contradicted at the ceiling by the wire-bench, and 12 of 16 shipped examples do not parse with the shipped parser. Roughly 450 KB of archive, build plans, debates and duplicated instruction variants sit in the repo with zero inbound references.

**The MCP server has two startup and deployment hazards nobody intended.** It runs `uv sync` against whatever project contains the package on every start, and the HTTP transport has no authentication while `octave_write` has no root confinement and accepts bare `.md` paths.

**On the wire-bench question (where to spend, where to stop):** stop maintaining the glyph layer and the frozen kernel; keep the slot contract and the verbatim-identifier rule; run Experiment 6 (compression-forced relay) with the added-facts judge as the one experiment that can still change a decision; do not run Experiment 2 (mythology placement) or Experiment 7 (orchestrator brief register) on the current budget; run Experiment 5 only in its reduced form. Detail in §8.

---

## 1. Measured ground truth

| Measure | Value | Source |
|---|---|---|
| Tests collected / passed / skipped / xfailed | 3637 / 3608 / 26 / 3 | `pytest` this session, 93.8 s |
| Coverage | 89% (CI gate 85%) | same run |
| ruff, black, mypy | all clean | same run (mypy runs non-strict, see §6) |
| Source lines: core / mcp / cli / schemas / integrations | 15,251 / 9,116 / 1,277 / 317 / 333 | `wc -l` |
| Shipped resources (.md under `src/.../resources`) | 5,528 lines | |
| Tests | 67,316 lines, 164 files, 26% inside string literals | |
| Docs / `_archive` / `debates` / CHANGELOG | 16,124 / 5,265 / 177 / 1,298 lines | |
| Open GitHub issues | 52 (18 labelled bug) | GitHub API |
| Open PRs | 0 | |
| Commits by month | Dec 25 to Feb 26: 292, 338, 224; May 26: 293; Jun 26: 28; Sep 26: 20 | `git log` |
| Most-churned files | `mcp/write.py` 108 commits, `core/parser.py` 84, `CHANGELOG.md` 69, `pyproject.toml` 61, `README.md` 52 | |

Two claims that hold: "DNS rebinding protection" (`http_transport.py:41-58`, verified against the mcp 1.27 middleware and covered by `tests/unit/test_http_transport.py:336`) and canonical idempotency on the shipped corpus.

Two claims that do not: README badge "3003 passing" (actual 3608; `AGENTS.oct.md:69` says 1610) and `AGENTS.oct.md:69-72` "90% coverage" and "TOOLS::3" (actual 89% and 4).

---

## 2. Core pipeline (lexer, parser, emitter, validator, hydrator)

Scratch: `docs/audit-2026-10-03/idempotency.py`, `idempotency_output.txt`, `fuzz_notes.txt`.

### 2.1 Architecture

One hand-written recursive-descent parser (`core/parser.py`, 3,282 lines) producing `core/grammar/cst.py` dataclasses. `grammar/entry.py` and `grammar/__init__.py` are re-export fronts; `ast_nodes.py` is a deprecation shim; `grammar_compiler/gbnf.py` is a two-function shim over `gbnf_compiler.py`. There is no parallel parser. `CanonicalEmitter` and `SymmetricVisitor.assert_round_trip` are reachable only from tests.

Every MCP tool and CLI command funnels through the same `parse()` / `parse_with_warnings()`. "Strict" governs only unclosed lists and nested inline maps (`parser.py:2489, 2695`); every silent drop below happens in strict mode too.

### 2.2 Invariants (AGENTS.oct.md §3)

| Invariant | Verdict | Evidence |
|---|---|---|
| I1 syntactic fidelity, idempotent canon | Holds on corpus, fails on constructed input | 40/40 shipped files reach a fixed point. `K::FOO[]` emits `FOO<>` which the lexer rejects (`parser.py:458`, `lexer.py:582`). `1e999`→`inf`, `+5`→`"⊕"`, `~30%`→`"⧺"`, `[,]`→`[","]` alter semantics. #510 (`"A→B"` dequoted to bare flow) reproduced. |
| I2 Absent ≠ null | Emitter yes, validator no | `NAME::null` with `REQ` yields E003 "required but missing" (`validator.py:876-896`). `K::` with nothing after it becomes the string `"\n"` (`parser.py:2403-2407`). |
| I3 mirror, no inference | Mostly | `§CONTEXT::` re-emitted as `§CONTEXT::CONTEXT` (`parser.py:1152`); constructor `ENUM[A,B]` rewritten to annotation `ENUM<A,B>` (`parser.py:2122`) although the spec defines them as distinct. |
| I4 every transform logged | **Weakest** | Silent drops at eight `capture=False` sites (`parser.py:1802, 1981, 2023, 2065, 2222, 2254, 2339, 3064`); block-header comments (`parser.py:1516`); all META comments (`parser.py:975`); non-identifier tokens at section level advanced without receipt (`parser.py:611-614, 832-833`); `hydrate()` and `seal_document` drop `trailing_comments`/`additional_envelopes` (`hydrator.py:877`, `sealer.py:111`). TIER_NORMALIZATION receipts are only wired when `mcp/write.py` binds the ContextVar, so CLI and validate paths never emit them. |
| I5 validation visible | Holds at tool layer | `loader.load_builtin_schemas` swallows every exception (`loader.py:215`). |

### 2.3 Reproduced defects (all on `main`, inputs in `docs/audit-2026-10-03/fuzz_notes.txt` and `docs/audit-2026-10-03/repro/`)

| # | Input → actual | Where | Severity |
|---|---|---|---|
| B1 | Three-level META nesting ejects `C::1 D::2 E::3` to document root, loses `B`, no warning | `parser.py:1063` | High |
| B2 | `K::1→2→3` → `K::1`; `K::A→1→B` → `"A→"` | `parser.py:2949`, `1815-1950` | High |
| B3 | `K::FOO[]` → `FOO<>` → reparse E005 | `parser.py:458`, `lexer.py:582` | High |
| #533 | `SEQUENCE::===NAME===[…,===END===]` truncates the rest of the document, result VALIDATED | lexer envelope detection | High |
| #509 | `LOCATION::~/.claude/hooks/x.sh` → `LOCATION::"⧺"`; spaces inside `FUTURE[Will require …]` stripped and `[]`→`<>` | lexer/emitter | High |
| B4 | `K::` + newline → `K::"\n"` | `parser.py:2403` | Med-High |
| B5 | `K::"a" [x,y]` → `K::a` plus two misleading `bare_line_dropped` | `parser.py:1811` | Med |
| B6 | `K::+5` → `K::"⊕"`, `5` gone | `parser.py:2403`, `611` | Med |
| B7 | `[a,,b]` → `[a,",",b]`; `[1→2]` → `[1,"→",2]` | `parse_list` | Med |
| B8 | validator treats null as absent | `validator.py:876` | Med |
| B9 | executive projection keeps every `§` section wholesale; `fields_omitted` lists only top-level keys | `projector.py:80-104` | Med |
| B11 / #510 | emitter emits spec-forbidden bare `→` and `∧`; four shipped spec files trip their own §6 NEVER on reparse | `emitter.py:197`, `visitor.py:95` | Med |
| B12 | block-header and META comments dropped | `parser.py:1516, 975` | Med |
| B14 | CRLF input → `E005 Unexpected character: ''` | `lexer.py:1632` | Low |
| B18 | `schemas/builtin/meta.oct.md` yields zero fields (block-form FIELDS unsupported); the real META schema is a hard-coded dict in `loader.py:30` | `schema_extractor.py:599` | Low |

Also open and still reproducing per the issue tracker: #511 (META comments reparented), #534 (chained `KEY::VALUE::extra`), #535 (`§` splits an unquoted list element).

### 2.4 Spec drift

Spec §6 forbids bare flow and bare `∧`; the emitter produces both by design. Spec §2c distinguishes constructor from annotation; the parser conflates them. Spec §4 key charset is `[A-Za-z0-9_]`; the parser accepts `my-key`, `a.b`, `./x`, `A#B`, `1abc`. Spec §2 operator precedence is not implemented (expressions flatten to strings). Unquoted ISO timestamps are a hard lexer error not in the spec. `MARKDOWN_EMBEDDING::[outer_single_code_fence_allowed→strip_fence_then_parse]` is not implemented in core. Literal-zone rules are implemented faithfully.

### 2.5 Complexity

`lexer.tokenize` 776 lines (rough cyclomatic 130); `parser.parse_value` 639 (119); `parser.parse_section` 341; `emitter.emit` 281. `parse_value` repeats a 35-line multi-word-coalesce block five times; `parse_additional_envelope` copies `parse_document`; the block-children and section-children loops are near-identical; string escaping is copy-pasted four times in the emitter. Dead code: `lexer.py:1298-1340` unreachable; `Parser.collect_leading_comments`, `hydrator._extract_namespace_from_snapshot_key`, `tier_normalize.get_active_log`, `schemas/repository.py` stub, two schema_extractor back-compat wrappers. Zero TODO/FIXME; zero bare `except:`.

---

## 3. MCP server, tools, transport, CLI

### 3.1 Surface vs documentation

Four tools are registered on stdio (`server.py:161-166`); the HTTP transport registers three (`http_transport.py:61-120` is a copy of `create_server` missing `CompileGrammarTool` and the grammar resources). The only document that describes the surface accurately is `resources/patterns/octave-tool-reference.oct.md`, and it is stamped `VERIFIED_AGAINST 1.15.0`.

Wrong in: `AGENTS.oct.md:72` (3 tools), `.env.example:6`, `README.md:107` (phantom `mode: normalize`), `docs/api.md` (3 tools, 4 of 9 validate params, missing `lenient`/`dry_run`/`parse_error_policy`, phantom `octave ingest`, `--verbose`, `--strict`), `docs/usage.md` (same), `docs/mcp-configuration.md` (four env vars that do not exist: `OCTAVE_SCHEMA_PATH`, `OCTAVE_LOG_LEVEL`, `OCTAVE_LOG_FILE`, `OCTAVE_STRICT_MODE`; never mentions HTTP), `octave-mcp-architecture.oct.md §7`. Real env vars are `DISABLED_TOOLS`, `OCTAVE_MCP_SKIP_SYNC`, `MCP_TRANSPORT`, `MCP_HOST`, `MCP_PORT`.

### 3.2 Security and deployment

| Finding | Where | Severity |
|---|---|---|
| `ensure_dependencies_synced()` runs `uv sync --quiet` on every server start, walking up from `__file__` to the first `pyproject.toml`+`uv.lock`. For a pip-installed package inside a user's project venv that is the user's project, and `uv sync` prunes the venv to that lockfile. Opt-out only via `OCTAVE_MCP_SKIP_SYNC=1`. | `server.py:61-118`, called at 364 | High |
| HTTP transport has no authentication. Anyone reaching the port gets `octave_write`. | `http_transport.py` | High for any non-loopback deployment |
| `octave_write` has no root confinement; `_validate_path` rejects `..` and symlinks but accepts any absolute path and `mkdir -p`s parents; `.md` is an allowed extension, so a prompt-injected agent can overwrite `~/.claude/CLAUDE.md` or any README. | `write.py:931-1004, 3011`, `file_ops.py:15` | High |
| `--host 0.0.0.0 --stateless` is documented but `run_http` never widens the host allowlist, so every non-localhost request gets 421. The serverless mode is non-functional as shipped. | `server.py:24-27, 281` | Med |
| Files created by the server are mode 0600 (`mkstemp`; `fchmod` only when the file pre-existed). | `write.py:3033`, `file_ops.py:172` | Low |
| `setup-mcp.sh` replaces `~/.claude.json` with an empty file if its Python heredoc fails (temp file is `mv`ed unvalidated; `set -e` suppressed inside `&&`). | `setup-mcp.sh:455-480, 316-332` | Med |
| Symlink check hardcodes a macOS `/private/` allowance. | `write.py:966-1000` | Low |

No `eval`/`exec`; YAML via `safe_load` only; no `shell=True`.

### 3.3 write.py anatomy

3,092 lines; `execute()` is a single 1,015-line method (`write.py:2077-3092`). Path validation, hash, and atomic write are triplicated across `write.py`, `validate.py:472-518` and `core/file_ops.py` (only the CLI uses `file_ops`, which is the one with tests). `_apply_block_change`/`_apply_section_change` are the same algorithm; so are the MERGE paths in `document_mutator.py:331-411`. `DocumentMutator` delegates back to `WriteTool` for three helpers (circular seam).

Dead: `DELETE_SENTINEL` (`write.py:84`, zero refs); `E_AMBIGUOUS_PATH` (defined, never raised); first two params of `_track_corrections` ignored.

`_auto_quote_section_refs_in_values` (`write_detection.py:349-485`) mutates input bytes in strict mode (`write.py:2443`); it is logged, but it is the one detector that crosses the "syntactic tolerance, never semantic inference" line the architecture spec draws. The other five detectors are advisory regex linters that re-implement quote/fence/comment tracking four times instead of using the AST they already hold.

The file is written even when `validation_status == "INVALID"` with `status: "success"` (`write.py:2900`, `3008`). `octave_eject` returns a parse failure as a success-shaped result with `output: "// Parse error: …"` and no `status` key (`eject.py:411-420`). `except: pass` at `write.py:2896` and `validate.py:921`. Unknown kwargs are silently ignored (`dry-run` typo → file written).

### 3.4 CLI

`octave write --changes` applies changes with its own 40-line loop that bypasses `_validate_change_paths`, `$op` descriptors and `DocumentMutator`, so `{"NEW.KEY": 1}` appends a literal dotted key, which the MCP tool rejects (`cli/main.py:564-608`). `write --schema X` prints INVALID and exits 0 (`cli/main.py:617-633`). CLI validation uses only the hard-coded builtin dict schemas, so CLI "VALIDATED" is weaker than MCP "VALIDATED". Docs describe `ingest` (removed) and omit `hydrate`, `normalize`, `seal`, `coverage`, `vocab`.

### 3.5 Dependencies and integrations

`PyJWT`, `python-multipart`, `cryptography`, `filelock` are declared as runtime dependencies "for CVE reasons" (`pyproject.toml:38-41`); the package imports none of them. Three are transitive via `mcp`; `filelock` is needed by nothing at runtime. They belong in a constraints section or the dev group. The `mcp<2` pin is justified and the code uses no deprecated 1.x API.

`integrations/` is scaffolding: `format_for_llama_cpp` and `format_for_vllm` are byte-identical; `create_vllm_sampling_params` returns a dict shape vLLM does not accept; five of eight functions have zero tests and zero callers. Coverage 20 to 68%.

---

## 4. Shipped resources (primers, skills, specs)

Scratch: `docs/audit-2026-10-03/inventory.md`, `tables.md` (operator matrix, chatter rule-by-rule table, evidence trace, redundancy), `validate_receipts.md`.

### 4.1 Inventory

40 files, 5,226 lines, about 31,700 cl100k tokens across primers, skills and the core spec family.

- **Primers (6):** literacy 424, compression 498, mastery 462, mythology 423, reading 330, ultra-mythic 448 tokens. All within the 500 budget; every declared `TOKENS` equals the measured count exactly, and `tests/unit/test_gh453_primer_token_budgets.py` enforces it. This is the one part of the resource family that is measured, enforced and clean. Compression sits at 498 of 500.
- **Skills (5):** literacy 5,065, mastery 3,885, compression 2,106, chatter 1,975, ultra-mythic 1,635 tokens. `octave-skills-spec §4` sets `TOKEN_TARGET 300-700` and `OVERSIZED above 800`; every shipped skill is 2 to 7 times over its own governing spec (#538).
- **Specs:** declared `TOKENS` are 12 to 28 times off measured (`primers-spec ~80` → 973; `data-spec ~75` → 2,080; `skills-spec ~250` → 2,874; `core ~2500` → 3,866). No test covers them.
- `standards/L3-AGENT-FORMAT.oct.md`: "Strict OCTAVE 5.1.0", DRAFT, does not tokenize (E005 on a backtick at line 44), and its section layout contradicts `octave-agents-spec` 8.1.0 and the `agent_definition` schema.

### 4.2 Consistency

Cross-references between skills, primers and specs resolve, with four exceptions: `primers-spec:20` points at `octave-compression[§1b::ULTRA_TIER]` (no §1b in that skill); `AGENTS.oct.md:21` `specs/README.oct.md` (no such file); `tool-reference` META `SOURCE`/`CANONICAL` point outside this repo; chatter §4c refers to "your SEA receipt" and SEA is defined nowhere in resources. The README says the mythology skill was retired into mastery, yet `octave-mythology-primer.oct.md` still ships with no parent skill. The README says "specs marked APPROVED are normative"; no spec is APPROVED.

**Operators.** The six-operator table with ASCII forms appears in four places (core §2, mcp-architecture §3, literacy §2, chatter §3) and they agree. None of the six primers lists any ASCII form or `⧺`. The mythology and ultra-mythic primers re-gloss `→` and `⊕` differently from the core spec. `∧` is "constraint", "conjunction" or "joint condition" depending on the file.

**The lexer vs the chatter skill.** `lexer.py:147-156` normalises `->`, `<->`, `+`, `~`, `vs`, `|`, `&`, `#` in bare positions, with a repair record. Inside quoted values nothing is normalised: `X::"fixture flake -> auth + payments vs runner fault?"` round-trips byte-identical. The chatter skill's §4b::ASCII line, "the canonicaliser normalises to unicode on write", is therefore false for exactly the quoted telegraphic form the primer teaches; the skill's own §4 header comment says the opposite and is correct. `<->` is accepted but documented nowhere. The `vs` boundary check fires on keys (`PRIMER_VS_SKILL` → `W_BOUNDARY_MISSING`). Core §3b lists `A→B` as safe unquoted; the validator flags it `W_BARE_FLOW`. The chatter §6 example's `FROM::octave-secretary[align-octave-skills]` canonicalises to `FROM::"octave-secretary<align-octave-skills>"`, so the `who[role]` slot survives the parser only inside quotes.

### 4.3 The octave-chatter skill, rule by rule, against the bench

| Status | Rules |
|---|---|
| Confirmed | `VERB` / NEVER `verb_in_the_arrow` (arrow misread 12/12; `COPIED_TO` 6/6). `KEEP … verbatim` / NEVER `paraphrase_an_id` (confirmed but non-discriminating: 109/109 in every register). HEAD slots FROM/PROVENANCE (free prose, the one register without them, is the only one that lost an attribution). |
| Refuted | `TENSION::"vs = genuine opposition only"` / NEVER `tension_for_mismatch` (read correctly 6/6 at ~90 confidence; defends against a misreading nobody made). §4a `LOSS::"prose across hops -> facts merge"` (keyed prose 72/72 and all four registers 71-72/72). MUST `"? marks unverified"` (flattened graded confidence 2/3). §4b ASCII normalisation claim (false in code). §2 KEYS regex applied to the wire (caused the only unpressured identifier loss). |
| Neutral | NEVER `unkeyed_prose`, ENVELOPE (register survives when cued; facts survive either way). HEAD/TAIL shape (W0 senders added `TO`, `STATUS`, `REPLY_TO`; relays added 3 keys; the fixed 8-slot W1 and K shapes drifted 0). ECHO UNCLEAR (self-labelled "convention not rule; evidence thin"; mandatory doubt slots manufactured two items under pressure in the baseline). GATE question (unmeasured, praised). |
| Untested | `RULE` quote-the-phrase/drop-stopwords, `SUM`, `COMPRESS` (relays copied at 0.90 to 1.00 similarity; only the baseline n=1 pressure arm stressed compression: wire 14/24 vs keyed 17/24). `RISK::ICARIAN`. `STATE_FIELD` (a Haiku relay invented status inside K's STATE slot). `TAIL STATUS` enum. `ASK "reply in this register"`. Mythology-as-zip (Experiment 2 unrun). |

**META claims.** `"canonical 554 tokens"` matches nothing shipped: §4 is 506, §4a-c 409, and the harness primer the W0 senders actually received (§2 to §6) is 1,086. `"138 tokens"` is correct for §5 inclusive of its header (131 without). `"EFFICACY untested until W3"` is still true: no run has ever sent the kernel alone. `"RATIFIED across 3 models"` resolves to a debate transcript whose `EVIDENCE_CLAIM` is "this debate itself proves the solution". `"45 facts, 0 wrong, 1 lost"` is unlocatable in either repo. The skill honestly self-labels v1.3 UNTESTED and ECHO thin; the candidate's rule 8 drops the seven v1.3 additions.

### 4.4 Evidence claims embedded in resources

`AGENTS.oct.md:109` "100% zero-shot, 60-70%, 10x" → `mythology-evidence-synthesis.oct.md`: 100% is 35 author-chosen elements judged by the author; 60-70% is two hand-written example pairs where the OCTAVE side carries less content; 10x is asserted with no measurement. `mastery:60` "88-96%, +17%" → `octave-benchmarking-evidence.md`, which itself warns that comprehension metrics are partly LLM self-report; +17% is one blind condition at n unstated. `literacy:26` "ATHENA<strategic_wisdom> = 1 token replacing 15" → a comment in a generated test output; cl100k tokenises it as about 7. `compression:158` "11/11, 15% fewer tokens" → the n=1 round-trip study. Cognitions' "60%/70%/80% higher probability (research evidence)" and cognition-spec's "N=40 study, C041 p=0.901, M022 92% vs 54%" → unlocatable anywhere in `docs/research`. `rationale-spec:648,693` "empirical testing across Claude, Codex, Gemini", "70% cheaper" → assertion. The "60% reduction" in ultra-mythic and README:62 is a tier target presented as achieved.

### 4.5 Mythology layer

Mythology-bearing lines account for 4,289 of 31,709 tokens (14%) across primers, skills and the core-spec family, and 22% of the five skills alone (mastery 49%, ultra-mythic 32%, chatter 9%, core 4%). Syntax proper is about 5,500 tokens across the same files.

The candidate's rule 5 (domain labels in keys only, glossed once, never descriptors in values) is already the rule in compression R5, the mythology primer §3b, the reading primer and mastery §1a. It is contradicted by compression R6 (the very next line: "use mythology as PATTERN DESCRIPTORS (SISYPHEAN, ODYSSEAN)"), mastery §2 `HEALTH::[GREEN→YELLOW→ICARIAN]`, the mastery primer, all of ultra-mythic, and **the chatter skill itself** (§4a `SISYPHEAN<endless re-explaining>`, `ICARIAN<confident + wrong>` as descriptors inside values). The chatter §6 example uses no mythology, and every W0 message in e1/e1b scored at ceiling without it.

### 4.6 Redundancy and self-compliance

About 5,700 of 31,700 tokens (18%) are duplicated: the syntax kernel is restated 9 times, the operator legend 11, the block-form rule 6, the compression tier table 3, the identical `I6<migration_on_moving_target…>` example 4 times (literacy §1b, mastery §3, tool-ref §6, AGENTS §12).

"Primers use the format they teach." Under STRICT: all six primers, chatter, compression, cognitions, vocabularies and the core/data/execution specs are clean. Literacy, mastery, skills-spec and others carry advisory warnings only. Five specs lose their own content silently on canonicalisation (DISCARDING tier per tool-reference §3): mcp-architecture 16 `bare_line_dropped` plus a duplicate key and 2 bare flows; patterns-spec 13 bare lines; rationale-spec 5 bare lines, 2 duplicate keys and a dropped numeric key; primers-spec 5 bare flows and a `W_META_001`; schema-spec a duplicate key. L3-AGENT-FORMAT does not parse. The CLI shows none of this (`octave validate` prints only `validation_status: UNVALIDATED`); the receipts above came from the Python tool.

### 4.7 Ranked, resources only

1. Chatter §4b::ASCII contradicts the lexer and its own §4 comment. Rewrite.
2. Rules the bench refuted still sit in the frozen kernel (`tension_for_mismatch`, `? marks unverified`, the KEYS regex). Rewrite §5 around the measured contract and re-count; the frozen 138 is re-opened anyway.
3. Unlocatable or self-reported evidence presented as measured (chatter 45-facts and RATIFIED; AGENTS triple; cognitions; cognition-spec C041/M022; literacy 1-for-15). Name source and n, or delete; point wire claims at `octave-wire-bench/runs`.
4. "554 tokens" and the 1,086-token harness primer: decide which artefact is "the primer", stamp its real count, enforce it like the primers.
5. Kernel efficacy never tested while being stamped into dispatch envelopes.
6. Mythology-in-values contradiction across the family; drop the two descriptor glosses from chatter §4a now.
7. Five specs that lose their own content under STRICT: rewrite via `octave_write` with receipts, and add a CI gate for every resource file like the primer one.
8. Delete `standards/L3-AGENT-FORMAT.oct.md`.
9. 18% redundancy: make core §2/§4 the single legend, cite by section elsewhere; re-parent or delete the orphan mythology primer.
10. Fix declared `TOKENS` on specs or drop the field; fix the four broken references; raise the skills-spec budget to what ships or split the skills. Leave the primers alone.

---

## 5. Documentation and evidence

Scratch: `docs/audit-2026-10-03/claim-ledger.md` (23 claims), `research-corpus.md`, `linkcheck.tsv`.

### 5.1 Claim ledger (condensed)

| Claim | Where | Rests on | Verdict |
|---|---|---|---|
| "3003 passing" badge; `TESTS_PASSING::1610`; "90% coverage"; `TOOLS::3` | README:6; AGENTS:69-72 | nothing current | Stale |
| "OCTAVE protocol v6.0.0" | AGENTS:62, CONTRIBUTING:109, architecture spec | specs are 6.0.1, 8.1.0, 6.3.2, 6.4.1 | Stale |
| "~140-token block" | README:186 | measured 141, but it is an unlabelled abridged copy of the 424-token shipped primer (#540) | Misleading |
| "Same input, same output, every time" | README:62 | property tests, corpus fixed point | Supported, with §2.3 exceptions |
| Loss accounting "[Evidence]" | README:70 → round-trip study | n=1 passage, 1 reconstructor, unblinded, author-chosen facts | Weak |
| ARTEMIS "never vulnerability"; domain labels "consistently prevented" misreading | README:52, 170 | one reconstruction of one line; the study's own Finding 5 credits both the label and splitting a compound field, confound unresolved | Weak; this is exactly wire-bench Experiment 2, unrun |
| "In prose 10-15 tokens, here one" | README:168 | none; `SISYPHEAN_FAILURES` is 4-5 cl100k tokens | Unsupported |
| "informal cross-model testing (GPT-4, Claude, Gemini, Llama, Mistral)" | README:174 | no Llama anywhere in the repo; Mistral appears once as a self-report | Weak; Llama unsupported |
| "100% zero-shot comprehension, 60-70% token reduction, 10x semantic density" | AGENTS:88; mythological-compression.md:33-35 | 4 qualitative quotes from 2 Gemini models (2025-06-19) and two author-written token examples; "10x" asserted over a table whose arithmetic gives 3-4x | Unsupported; contradicted by the sibling asterisk report (10 models, 40% strong) and by the round-trip study (LOSSLESS is 13% larger) |
| "+17% structural sophistication"; "88-96% (5 models, 30 evals)"; "30+ study synthesis" | guide:36-39 | synthesis with no raw data; benchmarking-evidence (self-admitted self-report, small n); ~13 items, not 30 | Weak / Weak / Unsupported |
| Structure resists summarisation across handoffs | README:40-52 | round-trip n=1 | Contradicted at the ceiling by wire-bench e1/e1b: JSON, wire and keyed prose all 71-72/72 over three hops |
| examples/README ratios "12.2x", "12x", LOSSLESS ~14,900 | examples/README.md:13-79 | none | Wrong by ~6x (measured 2.1x, 1.8x); ULTRA is smaller than AGGRESSIVE, the README says the reverse |
| "Production/Stable" | pyproject:24 | 1.15.0 shipped a self-labelled HARD BREAK in a minor under a SemVer banner; 18 open bugs incl. I1/I4 | Contested |

### 5.2 Research corpus

Documents that carry evidential weight, in order: wire-bench e1b (external, pre-registered, 89 agents, hand-checked); `compression-fidelity-round-trip-study.md` (n=1 but reproducible); `cross-model-operator-validation-study.md` (4 models, but validates operators that were never shipped); `02/octave-benchmarking-evidence.md` (30 evals, honest caveats, Sonnet-3.7 era); `02/octave-specialist-r3-controlled-comparison` (about secretary tooling, not notation).

The circular chain: `AGENTS.oct.md §11` → `guides/mythological-compression.md` → `mythology-evidence-synthesis.oct.md` (zero own data) → `comprehension-test-2025-06-19.md` (4 quotes). `docs/research/README.md §6` cites `operator_selection_suite/03_validation/final-recommendation.md`, which does not exist. `comparitive-analysis-multi-agent-comms.md` is an external LLM deep-research dump with raw `citeturn2view0` artefacts at lines 7-13. Both `03_cognitive_architecture` docs self-mark ARCHIVE.

### 5.3 Stale, broken, duplicated

- Broken refs: `AGENTS.oct.md:21` `specs/README.oct.md` (no such file); `AGENTS:20` `README.md§Quick_Start` (no such heading); `examples/README.md:13` wrong extension; `CONTRIBUTING.md:111` `docs/architecture/` (actual `docs/adr/`); research README §6 as above.
- 12 of 16 `examples/**/*.oct.md` fail `octave validate` (E005). All 5 grammar test vectors pass.
- Three hand-maintained variants of one custom instruction (`octave-custom-instruction.md`, `-lite.md`, `.oct.md`; diffs 291 and 343 lines). `.md`/`.oct.md` twins for philosophy and the multi-agent comparison.
- `docs/octave-spec-historical-review.md` says "no formal grammar, no test vectors"; both exist.
- ADR-0004 headline "3-tool API" never amended for the fourth tool (shipped v1.5.0); downstream docs copied the 3. ADR-0001/0005 markdown headers still PROPOSED although AGR records were cut 2026-06-17. ADR-0283 was to be relocated to odyssean-anchor; still here.
- CHANGELOG: top entry matches pyproject; `[Unreleased]` is accurate; five sampled entries verified in code. 1.15.0 carries a "HARD BREAK" in a minor.

### 5.4 Holistic review (2026-06-16) follow-through

Done: ADR-0006 re-status, AGR store adopted (11 records next day), #433/#434 fixed in v1.16.0. Not done: Wave 0.4 verify-close (#376, #384, #385, #386 all open); ADR-0283 relocation; Wave 1 remainder (#411, #480, #441, #435, #439, #445, #448, #365, #436, #371, #372, #377, #430 all open); #291 unparked. Since 2026-06-23 every commit is skill/primer/governance docs plus the `mcp<2` pin. No HARDEN engineering has landed in 3.5 months, while 7 new parser/emitter bugs were filed in September.

### 5.5 Repo weight that is not product

| Dir | Size | Inbound refs | Recommendation |
|---|---|---|---|
| `_archive/` | 240 KB | 2 historical | Move to a tag or history repo |
| `.hestai/rules/specs/` | 164 KB | 0 | Delete (completed build plans) |
| `debates/` | 32 KB | 1 (CHANGELOG note) | Move into governance or history |
| `standards/L3-AGENT-FORMAT.oct.md` | 8 KB | 0; says "OCTAVE 5.1.0", DRAFT | Delete |
| `tools/` | 84 KB | tools/README | Keep `octave-validator.py` (move its tests under `tests/`); delete `lint-octave.py`, `octave-to-json.py`, `json-to-octave.py` (untested regex reimplementations) |
| Custom-instruction triplet, `.md`/`.oct.md` twins | | | Collapse to one source plus one generated rendering |

`.hestai/decisions/`, `north-star/`, `MANIFEST.md` are live governance and should stay.

---

## 6. Tests, CI, packaging

Scratch: `docs/audit-2026-10-03/` (`quality.txt`, `module_map.txt`, `wheel_contents.txt`, `coverage_table.txt`).

### 6.1 Suite

3,637 tests, 164 files. `tests/unit/test_write_tool.py` alone is 5,912 lines / 209 tests. 28 files are named after issue numbers; they are regression pins written at fix time, several of which (`test_gh420_*` 1,111 lines, `test_gh452_*` 56 tests) have become de-facto feature suites. 29 tests have no assertion of any kind, including eight in `test_meta_audit_admission.py` whose names claim rejection, and five `test_round_trip_*` in `test_literal_zones_emitter.py`. 9 skips are pinned to files no longer on disk; 3 parametrize sets are empty; 5 tests depend on the gitignored `.hestai-sys` and never run in CI (#523 confirmed); 2 are unconditional `pytest.skip`. `tests/repro_issue.py` and `tools/test_octave_validator.py` are never collected.

Side effects: `unit/test_mcp_server.py:19` runs a real `uv sync` against `.venv` mid-suite with no assertion; `unit/test_gh453_primer_token_budgets.py:115` downloads the tiktoken BPE on a cold cache (#536).

### 6.2 Configuration that is not doing what it says

- **mypy strict is dead.** Both `mypy.ini` and `[tool.mypy] strict = true` exist; mypy reads `mypy.ini` first (confirmed with `--verbose`; gates.log prints "mypy.ini: note: unused section"). `mypy.ini` is non-strict. `mypy src --config-file pyproject.toml` yields 73 errors in 13 files. `AGENTS.oct.md:43` promises "mypy strict mode (no Any, full hints)".
- **Hypothesis config is inert.** Hypothesis does not read `[tool.hypothesis]` from pyproject. The `ci` profile that `ci.yml:189` requests is Hypothesis's built-in one (derandomize=True, 100 examples), and `tests/properties/test_canonicalization.py:83,120` hard-code 50 and 30. CI never explores new examples; the "increased iterations" comment is false. Only 14 property tests exist.
- **pre-commit disagrees with CI.** `ruff-format` would reformat 89 of 224 files that `black --check` passes; ruff pinned at 0.8.4 below the 0.9 floor; no mypy hook. The hooks are evidently not in use.

### 6.3 CI holes

- `integration-from-wheel` (`ci.yml:283-333`) runs no tests; it installs pytest and never calls it, and `timeout 5s octave-mcp-server || true` cannot fail. The comment at line 164 says integration tests run here.
- Docs-only fast path treats `src/**/*.md` that is not `.oct.md` as docs (`ci.yml:51,70`), so changes to the five shipped `SKILL.md` files skip tests, build and wheel checks. Any `docs/**` change skips tests although `tests/test_spec_validation.py:176` reads `docs/grammar/*.ebnf`. `git diff HEAD^ HEAD` classifies only the tip commit of a multi-commit push. The `specs/` rule at line 68 matches nothing.
- Codecov upload is best-effort; markdownlint is `continue-on-error`.
- `publish.yml` uses trusted publishing (good) but never checks tag == `project.version` before upload, and the release wheel smoke omits 3.11.

### 6.4 Packaging

Wheel built this session contains all 42 non-Python files; nothing missing. But `build-system.requires = ["setuptools>=45"]` permits versions that silently drop the recursive `resources/**` globs (need ≥62.3), and `artifact-validate` checks only one file. The `dev` extra duplicates the `dev` dependency group verbatim; the `http` extra is redundant (mcp pulls starlette/uvicorn).

---

## 7. Ranked list across the whole repo

| # | Issue | Area | Severity | Effort |
|---|---|---|---|---|
| 1 | Startup `uv sync` mutates the host project's venv (`server.py:61-118`) | MCP | High | Trivial: delete or gate behind `OCTAVE_MCP_DEV_SYNC=1` |
| 2 | Silent content loss without receipts: #509, #533, B1, B2, B3, B4, the eight `capture=False` sites, META/block comments | Core | High | Small per site; one helper that always returns-or-logs fixes most |
| 3 | Unauthenticated HTTP + unconfined `octave_write` accepting bare `.md` | MCP | High (deployment) | Medium: token auth, `OCTAVE_WRITE_ROOT`, drop `.md` from allowlist |
| 4 | Canonical output not a fixed point / spec-forbidden shapes emitted (#510, B3, B11); four shipped specs fail their own NEVER | Core + specs | Med-High | Policy decision then small code change |
| 5 | README and AGENTS make claims the repo cannot support (100%/60-70%/10x, 10-15 tokens, Llama, "consistently prevented", 12x examples) and one the wire-bench contradicts | Docs | High (credibility) | Small: rewrite §§ README:40-54, 168-182; delete the triple |
| 6 | mypy strict shadowed by `mypy.ini` (73 hidden errors); Hypothesis never randomises | Tests | Med | Small |
| 7 | `integration-from-wheel` runs nothing; docs-only path skips tests for shipped `SKILL.md` | CI | Med | Small |
| 8 | Four docs wrong on tool count/params/env vars/CLI; HTTP registers 3 tools vs stdio 4 | Docs + MCP | Med | Small: generate from `get_input_schema()`; one `create_server()` |
| 9 | 12/16 examples fail the shipped parser; examples/README ratios off ~6x | Docs | Med | Small: fix or archive, add a CI test |
| 10 | write.py 3,092 lines / 1,015-line `execute()`, triplicated path/hash/write code; CLI `write --changes` bypasses the contract and exits 0 on INVALID | MCP + CLI | Med | Medium |
| 11 | Validator collapses null into absent (I2); `KEY::` becomes `"\n"` | Core | Med | Small |
| 12 | ~450 KB of archive/build plans/debates/duplicate instruction variants with zero inbound refs; three untested `tools/` reimplementations | Repo | Low | Trivial |
| 13 | 29 assertion-less tests, 9 skips to deleted files, 5 `.hestai-sys` vacuous tests, `uv sync` inside a test | Tests | Low-Med | Small |
| 14 | Four unused runtime deps; `integrations/` scaffolding with a wrong vLLM shape | Packaging | Low | Trivial |
| 15 | Holistic-review Wave 0/1 commitments stalled since June (17 issues untouched) | Governance | Med | Decision: do them or retract |
| 16 | Chatter skill: §4b ASCII claim false in code; three bench-refuted rules still in the frozen kernel; "554 tokens" matches nothing shipped; two mythology descriptors in values in the one primer that bans them | Resources | Med | Small, but must follow the §8 decision on the kernel |
| 17 | Five shipped specs lose their own content under STRICT canonicalisation; spec `TOKENS` declarations 12-28x off; skills 2-7x over their own spec | Resources | Med | Small: extend the primer CI gate to every resource file |

A one-line summary of the pattern: **the project ships a receipt-based integrity story, and the places where it fails are exactly the places where no receipt is produced.** Fixing #2 and #4 is what would make the README's determinism claim true.

---

## 8. Guidance for the wire-bench agents

This section is written from the vantage point of having read both repos end to end. It is advice, not a spec amendment; anything adopted should go through the SPEC "Amendments" discipline.

### 8.1 What the evidence already settles

1. **Fidelity cannot rank registers on this content with Sonnet relays.** Three runs (baseline, e1, e1b), four registers, all at 71-72 of 72. Any further unpressured Sonnet relay run is spending budget to re-measure a ceiling.
2. **The glyph layer is not what carries facts.** The baseline naive relay dropped `::` entirely and still scored 23-24/24. The measured value is the eight slots, the verbatim-identifier rule, and the relay instruction "forward everything the replacement needs to act; name what you left out".
3. **The two rules that are confirmed:** verb in the key, never in the arrow (12/12 wrong on the arrow, 6/6 right on `COPIED_TO`); identifiers quoted inside values, never keyed (the only unpressured identifier loss in three runs was the baseline's key-grammar mangle).
4. **One rule is refuted as written:** `? marks unverified` flattened "fairly confident" to a bare flag in 2 of 3 W1 T1 senders. The candidate revision 2 (hedges verbatim, `?` appends never replaces) is the right fix and is already on `spec/experiment-6`.
5. **Wire is cheaper, by a bounded amount:** about 25% fewer tokens than free-key JSON and about 10% fewer than headed prose at hop 3. That is a real but small saving; it is not "60-70%".
6. **Haiku relays lose and invent, register-neutrally.** Both W1 and K lost the same filename once each; a Haiku relay invented a status sentence in K. In the e3 T1 re-run K hop-3 message the relay also wrote "the calculation pack reports 1.9 Hz, not 2.3 Hz as initially thought", inverting the source, and promoted a decision into an OUT_OF_SCOPE item. No scored question probed either. **This is the strongest argument for the added-facts judge in Experiment 6, and it is also evidence that the wire form's copy-verbatim bias has value under weaker relays.** Not provable at n=3.

### 8.2 Where to focus

**Run Experiment 6 next, as specced, with two changes worth an amendment.** It is the only queued experiment that can still change a decision (is the declared-loss rule worth its words; does any register degrade more gracefully). Two suggestions:

- Add a **K+ arm**: headed prose with the candidate's BUDGET and LEFT_OUT lines appended to the heading list. Without it, a W1v2 win on declared-loss recall cannot be separated from "W1v2 was the only arm told to declare". The pre-stated prediction "W1v2 declares with the highest recall; J0 the lowest" is otherwise close to tautological.
- Score the **added-facts judge on every hop-1 message too** (a sender-level false-positive rate), so the judge's precision is known before its counts are used to rank arms.

**Fold the hedge fix (candidate row 9) and the `none`-for-empty-slots rule into the skill now**, ahead of Experiment 6, because they are the only candidate changes with evidence behind them that is not also evidence for the headings arm. Everything else in the candidate (slots, verbatim IDs, verb-in-key) is already shown; the drop-order rule is what Experiment 6 tests.

**Spend remaining budget on scenario count, not on arms.** Experiment 3 flipped order between runs at a 3-question noise level with three scenarios. Six scenarios per arm with one relay model is worth more than three scenarios across two relay models. If Experiment 6 must be cut, cut the Haiku grid before cutting scenarios.

### 8.3 Where to stop

**Stop maintaining the frozen 138-token kernel and the glyph mandate.** Measured: kernel §5 is 138 cl100k tokens with its header (131 without), the §4 primer 506, the whole skill 1,975, the harness W0 primer that senders actually received 1,086, the candidate W1 primer 558. Nothing in three runs shows the glyphs doing work the slot names do not. The skill's own `WHY_WIRE_EXISTS` line ("syntax was never the failure") agrees. The contract (five lines in the baseline report's Part 4) replaces four artefacts with one. One caveat: the kernel is stamped into workbench dispatch envelopes today and has never been sent alone to any sender. If the envelopes keep it, a kernel-only sender arm (3 senders, 6 relays, 3 receivers) bolted onto Experiment 6 is the cheapest way to learn whether the deployed artefact does anything. If the envelopes drop it, skip the arm.

**Do not run Experiment 2 (mythology placement) on this budget.** The README's ARTEMIS anecdote is n=1 with a field-splitting confound, so the question is real, but it is a question about compression of evaluative prose, not about the wire register, and the candidate already restricts mythology to glossed domain labels in keys. Three passages at 48 agents would produce another n=3 result. If it is ever run, it needs a plain-key-with-gloss control (`AUDIT::"6wk" // time pressure`) or it cannot separate the mythology from the gloss.

**Do not run Experiment 7 (OCTAVE vs prose orchestrator brief).** Six full Experiment 6 sessions at about 150 agents each is roughly 900 agents, nine times the budget, to answer a question whose pre-stated prediction is the null. The deviations it would count (amendments filed, steps skipped) were already small and mostly forced in e1 and e1b.

**Run Experiment 5 only in reduced form, and only after Experiment 6.** Its question (does an OCTAVE role instruction persist under noise) is the one Shaun reports seeing in practice and the mechanism split (format vs re-injection vs file durability) is well designed. But four 35-60k-token scripts across six arms and two models is 32-36 long-context agents at several times the per-agent cost of a relay agent, and the scoring is hand-done against twelve rules times three probes. A2 vs A1 vs A4 on two scripts, Sonnet only (6 agents), answers "does format do anything A4's re-injection does not" and is the result that decides whether the rest is worth buying.

**Stop citing octave-mcp's research corpus as support for wire claims.** The baseline report's Part 1 table already said this; this audit confirms the chain is circular and the headline triple is unsupported. The wire-bench runs are now the evidence base; the skill's `PRIOR_ART`, `WHY_WIRE_EXISTS` and `PRIMER` META lines should point at `runs/` and nothing else.

### 8.4 Two things the bench should take back to octave-mcp

1. The relay scenario files (`T1.md` etc.) contain real-looking handoff content with `FUTURE[Will require …]`-style annotations and paths. Before any wire message is ever passed through `octave_write` (for example to canonicalise a dispatch envelope), note that #509 and #533 reproduce on `main` today and would corrupt exactly that content silently. The bench's "validated by the receiving model, never by octave_validate" split is currently a safety feature, not just a design choice.
2. The harness `score.py` `contains_any` reads `a` not `tokens`; the e1b run found it after senders ran and hand-reclassified 27 answers. The fix is a two-line change plus the self-test feeding `tokens` not `a[0]`. It should land on `main` before Experiment 6 so the run does not inherit it.

---

## 9. What this audit did not do

Did not exercise Strategy-A preserve-mode byte slicing or validate GBNF output against llama.cpp. Did not read the 117 KB CHANGELOG below the last 15 releases. Did not audit the hydrator's vocabulary semantics or the sealer's crypto beyond I4. Did not run the wire-bench harness itself. Did not read any agent transcript from the runs. Issue descriptions from GitHub were treated as claims and reproduced where cited; issues not reproduced here are reported as open, not confirmed.
