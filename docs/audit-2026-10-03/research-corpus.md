# docs/research/** corpus table (one line per file)

| File | Date | Method | n | Models | Superseded by |
|---|---|---|---|---|---|
| 01/asterisk-validation-report.md | 2025-06-16 | zero-shot prompt test, qualitative grading | 10 models x 1 prompt | 10 unnamed | partially by comprehension-test (same week), both frozen |
| 01/octave-evaluation-bias-report.md | 2025-07-15 | anecdote (single incident, 2 framings) | 1 | Sonnet-4 | none; cited by guide as "documented paradox" |
| 01/octave-mythological-semantics-comprehension-test-2025-06-19.md | 2025-06-19 | anecdote via zen MCP tools, qualitative quotes; 2 hand-built token examples | 4 elements, 2 examples | Gemini 2.0 Pro, 2.5 Flash | source of 100%/60-70%/10x — never superseded |
| 01/octave-validation-summary.md | undated (refs v5.4→6.0, LangChain prototype) | synthesis + model self-report table | 8 models self-report | 4o-mini..Mistral 7B | synthesis of benchmarking-evidence |
| 02/octave-benchmarking-evidence.md | undated (2025) | semi-controlled rubric (0-5, 5 dims), admits self-report & small n | 30 evals (5x3x2) | Sonnet 3.7, Haiku 3.5, 4o, o3, Gemini 2.5 Pro | none — carries the "88-96%" claim |
| 02/octave-generation-analysis-2025.md | 2025-01-19 | anecdote (2 prompts) | 2 | unnamed | none |
| 02/octave-specialist-model-comparison-2026-04-06.md | 2026-04-06 | controlled-ish tooling bake-off, 3 prompts | 6 agents x 3 | Sonnet 4.6, Gemini 3.1, o4-mini, minimax, mimo, kimi | r3/r4/r5, secretary-conclusions |
| 02/octave-specialist-octave-write-benchmark-2026-04-06.md | 2026-04-06 | tooling bake-off round 2 | 6x3 | as above + qwen | secretary-conclusions |
| 02/octave-specialist-stress-test-2026-04-06.md | 2026-04-06 | platform comparison, multi-turn | 2 | Sonnet 4.6 | r3 (admits model mismatch confound) |
| 02/octave-specialist-r3-controlled-comparison-2026-04-08.md | 2026-04-08 | controlled (matched skills/prompt) | 4 agents x 1 task | Haiku 4.5, Sonnet 4.6, Opus 4.6 | r4 |
| 02/octave-specialist-r4-skill-pruning-2026-04-09.md | 2026-04-09 | ablation, 1 model | 3 variants x 1 | Haiku 4.5 | secretary-conclusions |
| 02/octave-specialist-r5-llm-framing-benchmark-2026-04-09.md | 2026-04-09 | qualitative rewrite comparison | 5 agents | Gemini 3.1, Haiku/Sonnet/Opus 4.6 | secretary-conclusions |
| 02/octave-secretary-conclusions-2026-04-09.md | 2026-04-09 | synthesis of rounds 1-5 | — | — | terminal for that thread (about tooling/agent design, not OCTAVE-vs-X) |
| 02/octave-write-test-outputs/* (31 files) | 2026-04 | raw outputs | — | — | artefacts of the above |
| 03/archetype-interference-study.md | 2025-07-16 | rubric comparison, status ARCHIVE | 6 conditions, score /50 | unnamed | self-marked ARCHIVE; about cognition archetypes, not OCTAVE notation |
| 03/specialist-agent-performance-report.md | 2025-06-29 | rubric comparison, ARCHIVE | 5 personas x 4 runs | unnamed | self-marked ARCHIVE |
| comparitive-analysis-multi-agent-comms.md | 2026-03-02 | external LLM deep-research output (contains `citeturnNviewM` artefacts), literature comparison | — | — | .oct.md twin (same date, 123 vs 176 lines) |
| comparitive-analysis-multi-agent-comms.oct.md | 2026-03-02 | OCTAVE transcription of above | — | — | — |
| compression-fidelity-round-trip-study.md | 2026-02 | single-passage round-trip, manual 11-fact scoring, no blinding | 1 passage; 1 run/arm; 3-4 runs for CONSERVATIVE-MYTH | Opus 4.6 (compress), Gemini (reconstruct+count) | wire-bench 2026-10-02 (multi-hop, pre-registered, n=72/arm) for the structure claim; myth-placement (Exp 2) not yet run |
| cross-model-operator-validation-study.md | 2026-02/03 (undated; v1.5 context) | go-between dialogue, zero-shot reconstruction of 1 compound expression | 1-2 expressions x 4 models | Opus 4.6, Gemini 3.1, ChatGPT 5.2, Sonnet 4.6 | ADR-0005 parked (AGR 20260617); operators never shipped |
| jit-literacy-injection-debate.oct.md | 2026-01-30 | debate transcript | 3 | Opus 4.5, o3, Gemini 3 Pro | universal-llm-onboarding (proposal) |
| llm-native-encoding-patterns-research.oct.md | undated ("VERSION 6.0.0") | literature meta-summary (LLMLingua, 500xCompressor etc.) | 0 own | — | none |
| mythology-evidence-synthesis.oct.md | 2025-12 | synthesis of comprehension-test + benchmarking-evidence + unpublished C001/M005 | 0 own | — | none; cited as "30+ studies" |
| subagent-compression-study.md | 2025-01 | blind-rated comparison (C019/C020), raw data not in repo | 6 scenarios x 3 raters | Gemini, o3, Opus-4 raters | none |
| universal-llm-onboarding-architecture.oct.md | 2026-01-30 | architecture proposal | — | — | partly shipped (MCP prompts? unverified) |
| README.md | rolling | synthesis of all above | — | — | — |

Evidential weight (actual data, >n=1, some control): 1) octave-wire-bench e1b (external, pre-registered, 89 agents) ; 2) compression-fidelity-round-trip-study (n=1 but concrete, reproducible passage); 3) cross-model-operator-validation-study (4 models, zero-context); 4) octave-benchmarking-evidence (30 evals, honest caveats); 5) specialist r3 controlled comparison (matched conditions, but about agent tooling).
Circular: mythology-evidence-synthesis -> comprehension-test + benchmarking-evidence; research/README -> synthesis + validation-summary -> benchmarking-evidence; guides/mythological-compression.md -> synthesis ("30+ studies"); AGENTS.oct.md §11 -> guide -> synthesis -> comprehension-test (n=4 quotes, 2 Gemini models). The "100% / 60-70% / 10x" triple is one 2025-06-19 anecdote doc quoted four layers deep.
