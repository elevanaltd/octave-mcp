# Audit tables (companion to report). Measurements: tiktoken cl100k_base 0.14.0 over raw UTF-8 bytes; validator = octave-mcp ValidateTool (STRICT default, schema="").

See also: inventory.md (every file: TYPE/VERSION/STATUS/declared TOKENS/measured/lines/chars), validate_receipts.md (per-file receipts), validate.txt (CLI output).

## A. Operator table comparison

| Source | :: | → | ⊕ | ⇌ | ∧ | ∨ | ⧺ | ASCII forms stated | <> | [] | § | Gloss disagreements |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| core spec §2 | y | y (->) | y (+) | y (vs) | y (&) "constraint" | y (\|) | y (~) | all six + boundary rule for vs | §2c | §2c | y | precedence table; says "A→B" safe without quotes (§3b) but validator emits W_BARE_FLOW on `X::A→B` |
| mcp-architecture §3 | y | -> | + | vs | & | \| | ~ | all six + `#`→§ | – | – | # | only place `#` alias documented |
| literacy skill §2 | y | -> | + | vs | & "inside brackets only" | \| | ~ | all six; ASCII_RULE "emit unicode in files; ASCII acceptable on the wire" | §1b | §1b | y | – |
| chatter skill §3 | y | -> "causality ∨ sequence" | + | vs | & "inside brackets ∨ quoted values" | \| | ~ | all six | y | y | – | §4b::ASCII wire list is "-> + vs & \|" (omits ~); claims canonicaliser normalises on write (false for quoted values) |
| literacy primer §3 | y | "flow / sequence" | "synthesis / combine" | y | "conjunction / all-required" | "disjunction" | **absent** | **none** | – | – | – | – |
| compression primer §3 | y | y | y | y | y | y | **absent** | **none** | – | – | – | adds [,] |
| reading primer §2 | y | y | y | y | y | y | **absent** | **none** | – | – | – | – |
| mastery primer §3 | y | y | y | y | y | y | **absent** | **none** | y | y | y "target_reference" | – |
| mythology primer §3 | "atom-binding" | "becomes / maps to" | "unify atoms" | "opposing forces" | y | y | **absent** | **none** | – | – | – | three operators re-glossed |
| ultra-mythic primer §3 | "binds" | "flow / delegates to" | y | y | y | y | **absent** | **none** | y | y | – | adds NEVER[] |
| L3-AGENT-FORMAT §4 | y | y | y | y | y | y | absent | none | – | – | y | uses backtick-quoted operators (fails lexer E005) |

Lexer (src/octave_mcp/core/lexer.py ASCII_ALIASES, lines 147-156; TOKEN_PATTERNS 680-692; `+` special-case 1395-1416): normalises `->`→→, `<->`→⇌, `+`→⊕, `~`→⧺, `vs`(\bvs\b)→⇌, `|`→∨, `&`→∧, `#`→§. Probe result (bare positions): all 8 normalised, logged as repairs[type=normalization]. Probe result (inside quoted values): nothing normalised; `"fixture flake -> auth + payments vs runner fault?"` round-trips byte-identical. `<->` and `#` are accepted by the lexer but `<->` is documented nowhere in resources and `#` only in mcp-architecture §3. `vs` boundary check is also applied to identifiers/keys: `PRIMER_VS_SKILL` (primers-spec) and `enum_casefold_unique_vs_ambiguous` (mcp-arch) trigger W_BOUNDARY_MISSING false positives.

## B. octave-chatter rules vs wire-bench evidence

| # | Rule (location, quote) | Status | Evidence |
|---|---|---|---|
| 1 | §1 SPLIT_RULE "FORMAL ⇌ WIRE decided by WHO VALIDATES" | UNTESTED | definitional |
| 2 | §1 WHY_WIRE_EXISTS "45 facts, 0 wrong, 1 lost — every loss was an IDENTIFIER" | UNLOCATABLE / n=1 | only occurrence in repo is this line; baseline RESULTS Part 1: "Raw data not in the repo. n=1 relay, no prose control" |
| 3 | §2 KEYS "[A-Za-z_][A-Za-z0-9_]*" applied to wire | TESTED-HARMFUL | baseline Result 4: `R7-ROUNDING-PATTERN.md` mangled to key `R7_ROUNDING_PATTERN_MD::`, the only unpressured identifier loss; fixed by candidate rule 1 (e1/e1b: 109/109 survived) |
| 4 | §2 PROSE "unkeyed sentences are not OCTAVE" / §5 NEVER unkeyed_prose | TESTED-NEUTRAL | e1b: 0 unkeyed lines at every hop in W0/W1 when relays cued; baseline naive relay dropped the register at hop 1 but kept slots and facts (23-24/24) |
| 5 | §2 ENVELOPE optional | TESTED-NEUTRAL | envelope survived all hops; no fidelity effect measurable |
| 6 | §3 operator table / ASCII forms | PARTLY FALSE (code) | quoted-value ASCII never normalised (probe); contradicts §4b::ASCII, agrees with §4 header comment |
| 7 | §4 comment "Mythology = semantic zip… first use carries gloss" | UNTESTED | SPEC Experiment 2 not run; candidate rule 5 restricts to key labels |
| 8 | §4a LOSS "prose across hops -> facts merge + provenance lost" | TESTED-REFUTED (keyed prose), weakly supported (free prose) | baseline: free prose 70/72 lost one "who ruled"; keyed prose 72/72; e1/e1b all four registers 71-72/72 over 3 hops |
| 9 | §4a RISK "structure without hedges -> ICARIAN" | UNTESTED | no arm removed hedges |
| 10 | §4b RULE "quote the phrase & drop stopwords & operators carry connectives" (compression) | UNTESTED | relays copy verbatim (e1 similarity 0.90-1.00); baseline pressure arm n=1: wire 14/24 vs keyed 17/24, wire listed omissions fullest |
| 11 | §4b VERB "verb lives in the key, never in the arrow" / §5 NEVER verb_in_the_arrow | TESTED-CONFIRMED | arrow misread 12/12 (baseline 6/6 + e1 3/3 + e1b 3/3); COPIED_TO correct 6/6 |
| 12 | §4b TENSION "vs = genuine opposition only -> a mismatch gets words" / §5 NEVER tension_for_mismatch | TESTED-REFUTED as a needed rule | "served 13 lines vs actual 314" read as mismatch 6/6 at ~90 confidence; candidate drops it |
| 13 | §4b KEEP "numbers & IDs & SHAs & roles & hedges & reasons -> copied verbatim" / §5 NEVER paraphrase_an_id | TESTED-CONFIRMED but non-discriminating | 109/109 identifiers verbatim in every register; Haiku relays lose one filename per register (W1 and K alike) |
| 14 | §4b SUM "buckets total the whole" | UNTESTED | – |
| 15 | §4b COMPRESS "words vs claims" | UNTESTED | – |
| 16 | §4b ASCII "canonicaliser normalises to unicode on write" | REFUTED by code for quoted values | see A |
| 17 | §4c HEAD "FROM PROVENANCE" / §5 MUST HEAD+TAIL | TESTED-CONFIRMED (slots), shape NEUTRAL | slots are what free prose lacked when it lost provenance; e1b W0 (HEAD/TAIL shape) senders added keys beyond the slots (TO, STATUS, REPLY_TO) and relays added 3 keys; 8/9-slot W1 and K drifted 0 |
| 18 | §4c STATE_FIELD | UNTESTED / cautionary | e1b: Haiku relay invented a status sentence inside K's STATE slot; slot did not prevent invention |
| 19 | §4c TAIL "ASK::one question \| STATUS::OK\|BLOCKED\|DONE\|NEED_INPUT" | UNTESTED | STATUS enum never measured; ask-backs counted (wire 16 vs JSON 13 in e1b) but not judged |
| 20 | §4c ECHO "reply names UNCLEAR::[...]" (skill: "convention not rule; evidence 2 relay pairs, thin") | TESTED-MIXED | UNCLEAR held the self-weight doubt (receivers missed it twice: receiver miss); mandatory doubt slots manufactured 2 unverified items under pressure (keyed prose, baseline) |
| 21 | §4c ASK "reply in this register -> your SEA receipt…" | UNTESTED; SEA undefined in resources | – |
| 22 | §5 MUST "? marks unverified" / NEVER doubt_without_a_home | TESTED-REFUTED (weak) | W1 sender collapsed "fairly confident" to "checked once, no second reviewer" in 2/3 T1 runs; W0/J0/K kept gradation |
| 23 | §5 GATE "Could the receiver act without asking what any ID or arrow meant?" | TESTED-NEUTRAL | baseline calls it the best line; ask-backs not quality-scored |
| 24 | META PRIMER "canonical 554 tokens" | NOT REPRODUCIBLE | §4 (lines 50-71) = 506; §4a-c = 409; wire-bench harness primer (= §2-§6) = 1086; no v1.3 primer file exists in repo |
| 25 | META KERNEL "138 tokens" | CONFIRMED | lines 72-87 inclusive = 138 (131 without the §5 header line) |
| 26 | META "138-token kernel EFFICACY untested until W3" | STILL TRUE | every run primed senders with the full harness primer (1086 tok); kernel-only never run |
| 27 | META PRIOR_ART "RATIFIED across 3 models" | MODEL SELF-REPORT | docs/research/jit-literacy-injection-debate.oct.md: a debate transcript whose EVIDENCE_CLAIM is "This debate itself proves the solution" |
| 28 | META "v1.3 UNTESTED until W3; evidence base is v1.1 with 7 fewer rules" | SELF-LABELLED | candidate rule 8 drops the 7 v1.3 additions |

## C. Evidence claims in resources

| Claim | File:line | Traced to | Nature |
|---|---|---|---|
| "100% zero-shot comprehension, 60-70% token reduction, 10x semantic density" | AGENTS.oct.md:109 | docs/research/mythology-evidence-synthesis.oct.md:16-18, 56-61, 264-266 | synthesis doc; 100% = 35 hand-picked elements, "100% comprehension" judged by author; 60-70% = two hand-written example pairs (85→25, 95→35 tokens) where the OCTAVE side carries less content; 10x = asserted, no measurement |
| "60-70% token reduction vs natural language; 88-96% cross-model zero-shot comprehension; +17% structural sophistication in blind assessment; 4-model validation of Ares/Artemis" | mastery SKILL.md:60 | mythology-evidence-synthesis §3.1, §4.1, §5.1; cross-model-operator-validation-study.md | 88-96% = octave-benchmarking-evidence.md (30 evals, 0-5 rubric, doc itself notes "Self-Reporting Component"); +17% = one blind condition comparison C001 (4.67 vs 4.00 on /5, n unstated); 4-model = live multi-model dialogue relayed by a human, qualitative |
| "ATHENA<strategic_wisdom> = 1 token replacing 15" | literacy SKILL.md:26 | docs/research/02_benchmarking_and_generation/octave-write-test-outputs/literacy-v2-synthesised.oct.md:44 | comment in a generated test output; no measurement (ATHENA<strategic_wisdom> is ~7 cl100k tokens, not 1) |
| "11/11 decision-relevant facts preserved at 15% fewer tokens" | compression SKILL.md:158 | docs/research/compression-fidelity-round-trip-study.md:7,206,212 | n=1 passage, 1 reconstructing model, prose arm prompt "provide this in english" (doc's own Limitations §); baseline report calls prose arm handicapped |
| "measured relay test on v1.1: 45 facts, 0 wrong, 1 lost" | chatter SKILL.md:28 | nowhere in repo | unlocatable; n=1 anecdote |
| "RATIFIED across 3 models: ~200-token primer enabled native OCTAVE output" | chatter SKILL.md:20 | docs/research/jit-literacy-injection-debate.oct.md (STATUS::RATIFIED, MODELS 3) | debate transcript = model self-report; emission not fidelity |
| "canonical 554 tokens"; "138 tokens" | chatter SKILL.md:18-19 | this audit | 554 not reproducible; 138 confirmed |
| "OCTAVE syntax tokenizes ~5x word count" | primers-spec:17 | CHANGELOG.md:983 | assertion; test_gh453 docstring says whitespace proxies under-counted 2.7-4.4x |
| "60%/70%/80% higher probability of validation/pattern/implementation language (research evidence)" | cognitions/ethos:9, pathos:9, logos:9 | mythology-evidence-synthesis §2.3; docs/guides/cognitive-type-system.md:109 | asserted ("attention head pattern triggering"), no method, no data |
| "N=40 study: +20% improvement (C041, p=0.901 for labels alone)"; "M022 92% vs 54% adherence" | cognition-spec:793-794 | docs/guides/cognitive-type-system.md:107-108 only | guide restates the same numbers; study files in docs/research/03_cognitive_architecture do not contain C041/M022 (grep empty) → unlocatable |
| "Empirical testing across Claude, Codex, Gemini: all models immediately interpret <qualifier>… Zero disambiguation" | rationale-spec:648 | none | unlocatable |
| "'status::active' is as clear as 'the status is active' but 70% cheaper" | rationale-spec:693 | none | assertion (cl100k: 4 vs 5 tokens) |
| "60% token reduction while preserving soul" | ultra-mythic SKILL.md:22, primer:9, README:62 | compression tier definition | a target, presented as achieved in README ("Ultra-compress with 60% reduction") |

## D. Redundancy estimate (cl100k tokens)

| Content | Restated in | Tokens per copy | Copies | Duplicated (beyond one canonical) |
|---|---|---|---|---|
| Syntax kernel (KEY::value, KEY:, lists, key regex, literals, § headers, envelope) | core §1-§4 (~1260), literacy §1+§3 (606), chatter §2 (200), literacy primer §2-§3 (150), compression/reading/mastery/mythology/ultra primers §3 (~320), L3 §4 | | 9 | ≈1,300 |
| Operator legend | core §2+§2b (406), literacy §2 (298), chatter §3 (254), 6 primers (~410), mastery §7a (278), mcp-arch §3 | | 11 | ≈1,400 |
| Compression tiers | data-spec §1b (782), compression skill §1 (508), compression primer §2 (184) | | 3 | ≈690 |
| Telegraphic phrase rule | literacy §2 pointer, compression R3a, mastery §7a (278), compression primer, literacy primer, tool-ref §6 action | | 6 | ≈350 |
| Block-form / no inline-map rule | literacy §1d (334) + §7b (423), mastery §6 (239), core §5/§7 (362), tool-ref §6 STRUCTURAL_ADVISORY, compression AP3 | | 6 | ≈900 |
| Annotation ≤32-char discipline with identical I6<migration_on_moving_target…> example | literacy §1b, mastery §3, tool-ref §6, AGENTS.oct.md §12 | ~120 | 4 | ≈360 |
| Mythology pantheon/forces | mastery §1-§2 (1150), mythology primer (423), mastery primer §2, ultra-mythic §7, reading primer, compression §6, AGENTS §11, core §0 comments | | 8 | ≈700 |
| Anchor kernels (TARGET/NEVER/MUST/GATE) | every skill + tool-ref (6 × ~190) | | 6 | by design |
| **Total** | | | | **≈5,700 of 31,700 (18%) in primers+skills+specs** |
