# PITH specification

Version `1.0`. Status: ratified rules (`LANG-ARCH-RECONCILIATION-RULINGS-20261031`), name (`INNER-LANGUAGE-NAMED-PITH-20261102`), calibrations (`PITH-SPEC-CALIBRATIONS-20261102`), home (`PITH-SPEC-HOME-OCTAVE-MCP-20261102`). Home: octave-mcp `src/octave_mcp/resources/specs/pith-spec.md`, shipped with the package; hestai-workbench points to it from `docs/agent-document-contract-v2.md`. Measured at hestai-workbench `e4305d53`, octave-mcp `1.16.0`, hestai-context-mcp `d8e2c6fc`, octave-wire-bench `1be10776`.

Evidence and check pointers outside octave-mcp refer to the HestAI repositories, not all of which are public.

## What PITH is

- The writing standard for every sentence, fragment, item, step, slot body and quoted value an agent writes, in any document shape.
- Job: carry facts, exact identifiers, hedges, provenance and calibrated prohibitions across model hops, compaction and parsers without silent loss or invention.
- Not a file format, not a container, not a schema, not a compression scheme. The outer shape belongs to the consumer (see Shapes). OCTAVE is one container PITH sits inside.
- Cite a rule by its name in words, never by a number.
- Evidence classes: MEASURED (bench experiment at `1be10776`), UNTESTED, OPERATOR-RULED (record). Check kinds: lint, parser receipt, review.

## Rules

### Note form
- Fragments and short clauses; drop articles and filler; keep every number, name, path, unit and command.
- Calibration: a full sentence where a fragment would drop a condition, hedge, decider or verb.
- Evidence: MEASURED `E8` (plus 1.28 facts per cell over sentences, p 0.001). Check: review; consumer word caps (`type_checker.py:143-155`, 40 words).
- Good: "Tests green at `cdfc963`; `3934` passed; `pytest -q`."
```text
Bad: I ran the full test suite and it seems that everything is passing now, which is great.
```

### Exact identifiers
- Names, numbers, dates, paths, SHAs, tickets, PRs copied as the source has them, in backticks; never shortened, rewritten or merged.
- Checker tolerance, not a writing licence: the `identifier_altered` flag accepts a SHA prefix of seven or more, a path basename, a number with or without thousands separators.
- Evidence: MEASURED `E1` to `E8` (identifiers at ceiling under slots), `E15b` L5 (13 altered by hyphen rewriting). Check: `identifier_altered` (`messageContract.ts:41,53`; `atoms/message.ts:372`) on bound dispatch replies; review elsewhere.
- Good: "`PR #532` merged at `cdfc963`; touches `supabase/config.toml`."
```text
Bad: PR 532/531 merged (cdfc9...) touching config_toml.
```

### Hedges verbatim
- Conditions and hedge words ("if", "could", "unless", "unverified") are facts; copy them, never resolve them. Topic-record VERBATIM fields stay byte-exact.
- Evidence: MEASURED, medium (closing report: dropped hedges are the one real register failure); OPERATOR-RULED for topic records (`HO-TOPIC-RECORDS-AND-APPEND-RULING-20261015`). Check: review.
- Good: "could be the lockfile; unverified this pass."
```text
Bad: The lockfile is the cause.
```

### Relations in words
- "copied to", "blocked by", "versus", "at most", "and", "or". No operator glyphs and no ASCII arrow or symbol forms as relations in prose, values or items; a converter from an OCTAVE source replaces every operator.
- Calibration: a schema-definition file (`TYPE::SCHEMA`) keeps the holographic constraints a validator reads; a fenced reading reference may show operators; a runbook's visual section marker and a quoted section-token citation are not relations.
- Evidence: MEASURED `E1`, `E1b`, `E4` (an arrow carrying a verb read as "moved" by 6 of 6 readers), `E15` C (operators copied through unless replaced), `E13` B (neutral in role files); OPERATOR-RULED for records (`HO-AGR-PLAIN-WORDS-REASONING-20261031`). Check: workbench lints catch the six Unicode glyphs (`validate-agent-rules.mjs:30-35`, `lint-runbook.mjs:13`); ASCII forms (spaced arrow, double arrow, plus, ampersand, tilde, pipe between word, backtick, quote or bracket characters) by `test_p2_8_bundled_skills_language.py` `A3` and review; in a container a bare arrow is a parse repair (`src/octave_mcp/core/parser.py:1418`).
- Good: "`DECISIONS.md` copied to `docs/`; original kept; `auth` blocked by `runner`."
```text
Bad: DECISIONS.md -> docs/ ∧ original ⇌ kept; auth ⊕ runner
```

### Nothing invented
- Never fill a slot or field; write `none` or `not known`. A decision with no decider in the source says "no decider named".
- Evidence: MEASURED `E8` (STATE and PROVENANCE slots drew fillers in every session), `E11` line 4 (slot-fills halved, 0.708 to 0.354, once fillers went). Check: `decided_no_decider` flag; review.
- Good: "UNCLEAR: none."
```text
Bad: UNCLEAR: minor risks around edge cases may exist.
```

### No writer-made ids
- No ids, tags, counts or census on items or rules; a tool derives any census out of band. Cite a rule by section and words.
- Calibration: a numbered runbook step, and a `STEP_n` key where a section is itself a runbook, order execution and are allowed.
- Evidence: MEASURED `E14` lines 2 and 3 (per-item ids minus 4.09 facts per cell; a census minus 0.71), `E15`, `E15b` L3 (5.6 and 5.77 tag fabrications per document, 20 invented deciders); OPERATOR-RULED (`PROGRAMME-DIRECTION-RULINGS-20261025`). Check: `validate-agent-rules.mjs`; in a container `numeric_key_dropped` (`src/octave_mcp/core/parser.py:1352`) and `W_FLAT_PREFIX_SCALAR` (`src/octave_mcp/mcp/write_detection.py:1246-1249`) are proxies.
- Good: `RULES::["Never put spaces around the double colon.","Quote multi-word values."]`
```text
Bad: R1 [tag:syntax] Never put spaces around ::   (2 of 13 rules)
```

### One calibration sentence
- A prohibition that can fire on its own carries one sentence saying what is still allowed; one that cannot over-fire carries none.
- Evidence: MEASURED `E13b` (false alarms 26 against 53; gates-decoy 7 against 26 of 36), `E13c` (insurance on Sonnet), `E13d`; OPERATOR-RULED (`PROCEDURE-COMMAND-SHAPE-PILOT-20261030`). Check: review; a runbook `Why:` line at most 30 words, one per step (`lint-runbook.mjs`).
- Good: "Never write production code. Reading and quoting existing code is allowed."
```text
Bad: Never write code. Never read code. Never quote code. Never think about code.
```

### Judgement unattributed
- A judgement is the review's or the finding's, never "Name: judgement". Naming the decider of a decision, or who reported a fact, inside the sentence is provenance and required.
- Evidence: OPERATOR-RULED (contract v2); MEASURED origin `E15` L3 (15 of 20 invented deciders named the operator). Check: `attribution_line` flag (`messageContract.ts:40,50`).
- Good: "The review judges the migration unsafe; `Mira` ruled the fallback in scope."
```text
Bad: Hughes: the migration is unsafe.
```

### Code in fences
- Multi-line code, commands, prompt templates and reference tables sit in a fenced block under the slot, step or key that needs them; a single command or path stays in backticks inline.
- Evidence: OPERATOR-RULED (contract v2); UNTESTED in isolation. Check: fenced lines are body text to the checker (`atoms/message.ts:98-117`); P2-8 `A12` validates fenced examples.
- Good: a step, then a three-backtick block holding the `gh api` call.
```text
Bad: Run gh api repos/x/pulls/1/comments --paginate --jq '[.[] | select(...)]' then gh pr view 1 ...
```

### Contradictions kept
- A source that contradicts itself is kept both ways and flagged; never resolved, averaged or halved silently.
- Evidence: OPERATOR-RULED (contract v2); UNTESTED in isolation. Check: review against the source.
- Good: "report says `3934` passed; `CHANGELOG.md` says `3936`; conflict."
```text
Bad: 3934 passed.
```

### Plain vocabulary
- Words separated by spaces; no snake_case blobs as prose; no mythology or HESTAI domain labels as instruction vocabulary or keys.
- Calibration: an established idiom ("Sisyphean", "Pyrrhic", "Gordian") may carry an evaluative judgement in prose where its dictionary sense fits exactly, never a fact, identifier, decision or ask (`E2b`: apt 14 of 14, none on mild passages). Archetype atoms (`ATLAS`, `HEPHAESTUS`, `DAEDALUS`) stay valid where a schema or parser names them, in archetype files and role bindings (`payloadCompiler.ts:123-155`), as does any uppercase key or enum atom a schema names.
- Evidence: MEASURED for mythology `E2` (escalates when misapplied), `E2b` (softened apt passages by 4 on Sonnet and 5 on Haiku), `E9` (plus 7 of 144 Haiku false alarms); UNTESTED for snake_case blobs. Check: `W_SNAKE_CASE_BLOB` (`src/octave_mcp/mcp/write_detection.py:42`, advisory, containers only); `validate-agent-rules.mjs`; review elsewhere.
- Good: "merge blocked until the lockfile is regenerated."
```text
Bad: STATUS::merge_blocked_until_lockfile_regenerated_SISYPHEAN
```

### Runbook steps
- Numbered steps; a `Why:` line only where it calibrates; no rule history; no step depends on a later section.
- Calibration: a template or table several stages use sits in an early section so later steps refer backward.
- Evidence: OPERATOR-RULED (`PROCEDURE-COMMAND-SHAPE-PILOT-20261030`); the `Why:` line MEASURED (`E13b` to `E13d`); numbering, history and forward references UNTESTED. Check: `lint-runbook.mjs` for mechanical bounds; history and forward references by review.
- Good: "1. PR required on current branch; none: stop. Why: gate reads PR comments."
```text
Bad: 3. Do what §7 says (we used to do it the other way before the 2026-09 rewrite).
```

## Shapes: only what differs

- Handoff. No envelope, no META. Seven slots in order: ASK, FROM, DECIDED, OUT_OF_SCOPE, DONE, UNCLEAR, LEFT_OUT; LEFT_OUT restates the ask in one clause; DECIDED holds standing rules and warnings; DONE says how each fact is known. Heading `## SLOT` or `SLOT::`. Only `missing_slot` blocks; flags persist in `egress_flags`. Bound roles: `implementation-lead`, `technical-architect`, `ideator`, `critical-engineer` (`messageContract.ts:84`); a bound dispatch is not sent its role's MUST_USE and keeps MUST_NOT (`payloadCompiler.ts:498,566,717`).
- Record. New records: quoted-YAML front matter in `.md` (`HO-RECORDS-YAML-DEFAULT-20261031`). DECISION and BECAUSE: plain words, one flat quoted string, at most 40 words, no newline. Existing OCTAVE records frozen; a list value stays on one line because the reader drops a multi-line list (hc `#224`). Body form is the writer's choice.
- Runbook. `.md`, never written or validated through octave tooling. The visual `===NAME===`, `META:` and numbered section skeleton stays so cross-references hold; it is not OCTAVE.
- Role file. `.oct.md`, the parser's keys (`agentFileParser.ts`). PITH acts on the bound tier: MUST_ALWAYS, MUST_NEVER, AUTHORITY BLOCKING, GATES (`payloadCompilerContentSource.ts:560-578`). The shown identity tier stays verbatim until a bench line says what it does. One quoted sentence per array item; nothing outside parsed keys, because the editor rebuilds the file from them (`agentFileWriter.ts:246-287`; `#649`).
- Standing context doc. HOLD for CTX-EXPERIMENT. `PHASE::`, the section 1 `CURRENT_STATE` keys and `I<n>` lines are load-bearing. PITH applies to values on the next refresh; no slot set is settled.

## Inside an OCTAVE container

- A file is `.oct.md` only where a named parser reads a named key or section; `SKILL.md` is the harness-fixed exception.
- Every content line outside fences is `KEY::"..."`, `KEY::["...","..."]` or a `KEY:` block with 2-space children. An unkeyed line is dropped while the file reports VALIDATED (`src/octave_mcp/core/parser.py:1702`). No rule or fact in a `//` comment.
- One `KEY::[...]` list per section for rules or items, never sibling keys sharing a prefix (`W_FLAT_PREFIX_SCALAR`). A list is edited by append or whole-list replace; changes mode cannot address a list item.
- Quote any value with spaces or punctuation; escape inner quotes as `\"`. A bare single token is dequoted on write (`src/octave_mcp/core/grammar/tier_normalize.py:71`), so quotes carry no meaning there.
- Backticks wrap identifiers inside a sentence value only; a standalone scalar or enum atom (`VERSION::"5.0.0"`, `STATUS::ACTIVE`) takes none.
- A section header carries no value. Indent section contents 2 spaces; address edits as section dot key, `§N.KEY` (`#517`).
- Inside a quoted value a section sign, a double colon and `===END===` are plain text. Unquoted under STRICT, a section sign in a scalar value is `E_PARSE` and UNVALIDATED (loud); in a list element it is VALIDATED with no repair and the element splits into several (silent). A double colon in a scalar value is VALIDATED with a `bare_line_dropped` repair and the rest of the value is lost; in a list element `a::b` is VALIDATED with no repair and the item becomes an inline pair (silent), while `a::b c`, with a space, gets a `multi_word_coalesce` repair. `===END===` in a scalar value is VALIDATED with no repair, the document ends there and later keys are lost (silent); in a list element it is VALIDATED with an `unclosed_list` repair, the document ends there and later keys are lost (`#533`, `#534`, `#535`). Write "double colon" in prose; a quoted cross-file citation keeps its section token because acceptance tests check citations by it.
- `ANCHOR_KERNEL` appears once per file, and no line inside the kernel starts with `===END===` or a section header: the odyssean-anchor extractor stops at either (`extraction.py:964-997`), as does the workbench regex (`payloadCompiler.ts:85`). Keep every key a schema or parser names.
- Read the receipt fields, never the status alone: `octave_validate` returns `repairs[]`, `validation_errors[]` and `warnings[]` (under LENIENT or ULTRA a schema failure lands in `warnings[]`, not `validation_errors[]`, `src/octave_mcp/mcp/validate.py:995-1004`); `octave_write` returns `corrections[]`, `warnings[]`, `validation_status` (`src/octave_mcp/mcp/write.py:2981`).
- Drop `COMPRESSION_TIER` and `LOSS_PROFILE` from new documents, except a compressed artefact, which keeps both as its loss receipt with a PITH sentence as the value (both E007 under META STRICT until `#514`).

## Skill kernels

- A kernel cites PITH in words on its `TARGET` line, never through a META key (E007 under STRICT).
- The standard kernel items are the compression of the rules above: Note form; Exact identifiers (copied exactly, in backticks; never shortened or merged); Hedges verbatim; Relations in words (no operators in prose or values); Nothing invented (`none` or `not known`); No writer-made ids, tags or counts; One calibration sentence; Judgement unattributed; Code in fences; Contradictions kept and flagged; Plain vocabulary (no blobs, no mythology as instruction words); and the container items (every line keyed, values with spaces or punctuation quoted; no unkeyed lines; no value on a section header; contents indented under the header; edits addressed as section dot key (`§N.KEY`); receipt fields read, not the status). Runbook steps has no kernel item.
- The drift test reads this list; each line is `tag: item`, the item being the exact kernel string.
```text
standard: Note form
standard: Exact identifiers (copied exactly, in backticks; never shortened or merged)
standard: Hedges verbatim
standard: Relations in words (no operators in prose or values)
standard: Nothing invented (none or not known)
standard: No writer-made ids, tags or counts
standard: One calibration sentence
standard: Judgement unattributed
standard: Code in fences
standard: Contradictions kept and flagged
standard: Plain vocabulary (no blobs, no mythology as instruction words)
container: every line keyed, values with spaces or punctuation quoted
container: no unkeyed lines
container: no value on a section header
container: contents indented under the header
container: edits addressed as section dot key (§N.KEY)
container: receipt fields read, not the status
```
- Two container items are worded here as recommended to the kernel owner ("values with spaces or punctuation quoted"; "receipt fields read, not the status"); the drift test reads the fenced list's exact strings, so whichever string the shipped kernel carries is the string the list carries.
- Drift test: parse each shipped kernel's `NEVER::[...]` and `MUST::[...]` arrays through the real workbench regex (`payloadCompiler.ts:85`, in Node) and the odyssean-anchor first-match rule; the standard items map both ways to this page and fail on an orphan; a skill's own extra items are checked against that skill's contract; a kernel over 300 cl100k tokens fails.
- Until the kernels are trimmed to a pointer plus own items, each kernel carries the standard items in full; compile-time de-duplication is not built.

## Amendment

- Rules change only by an operator-ratified record, filed in octave-mcp. Calibrations, examples, checks and file:line pointers change by PR with the drift test green and critical-engineer review. The drift test lives in octave-mcp beside the skill-kernel test. An evidence class moves up on a bench run after a model change; down only by record.
- Not established by this page: lint precision or recall for any regex; the effect of numbering, history or forward references in runbooks; any slot set for standing context docs; compliance by non-Claude senders.
