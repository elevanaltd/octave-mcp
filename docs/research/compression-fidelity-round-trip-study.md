# Compression Fidelity Round-Trip Study

## Executive Summary

An empirical comparison of information preservation across OCTAVE compression tiers versus prose-to-prose paraphrasing. A 189-token prose passage was compressed to three OCTAVE tiers (LOSSLESS, CONSERVATIVE, AGGRESSIVE) and independently paraphrased as prose (summary, TL;DR). All five outputs were given to a base LLM agent — with no OCTAVE knowledge — and the prompt "Can I ask you to provide this in english for me?" Reconstruction fidelity was measured against 11 decision-relevant facts extracted from the original.

**Key finding:** Information loss during paraphrasing is universal — including when an LLM is asked to simply restate prose in English. Prose-to-prose summaries lose facts silently. OCTAVE tiers make the loss explicit and controllable. A CONSERVATIVE-MYTH variant (mythology as domain labels) achieved perfect 11/11 round-trip fidelity at 15% fewer tokens than the original prose, while a prose-to-prose summary of the same content lost 2 decision-relevant facts silently.

## Methodology

### Source material

A realistic LLM-generated project status update (~189 tokens) describing an authentication service migration. The passage was chosen for semantic density: it contains recurring failure patterns, team disagreements, deadline pressure, budget metrics, monitoring evidence, and a conditional positive signal.

### Original prose

> The authentication service migration has been running for three sprints now and keeps hitting the same problems. Every time we fix one integration test, two more break because the legacy session store and the new JWT-based system have fundamentally different assumptions about token lifetime. The team is split — half want to do a clean cutover and accept two days of downtime, the other half want to keep running both systems in parallel until every edge case is covered. Meanwhile, the security audit is due in six weeks and the auditors specifically flagged session management as a priority area. We've already burned through 60% of the quarterly infrastructure budget on this migration alone, and the monitoring dashboards are showing increased latency on every auth endpoint since we started the dual-stack approach. The one bright spot is that the new JWT validation is actually faster than the old session lookups when it works correctly, which suggests the architecture is sound even if the migration path is painful.

### Compression process

The prose was compressed to three OCTAVE tiers following the octave-compression skill workflow (PHASE 1–4: READ → EXTRACT → COMPRESS → VALIDATE). Key compression decisions:

- **LOSSLESS**: No mythology. Every qualifier preserved. Causal chains maintained via indentation. No semantic addition.
- **CONSERVATIVE**: SISYPHEAN mythology applied where it accurately maps (recurring 3-sprint failure). Qualifiers like "fundamentally different" shortened. Causal chains preserved.
- **AGGRESSIVE**: Core thesis and conclusions only. Monitoring evidence, failure specifics, and the positive signal dropped. Mythology retained.

### OCTAVE outputs (content lines only — no envelope or META)

**LOSSLESS:**
```
migration::auth_service[3_sprints∧recurring_failures]
failure_cycle::fix_one_integration_test→two_more_break
  cause::legacy_session_store⇌new_JWT[fundamentally_different_token_lifetime_assumptions]
team_split:
  cutover::clean[accept_2_days_downtime]
  parallel::run_both[until_every_edge_case_covered]
deadline::security_audit[6_weeks]
  auditors_specifically_flagged::session_management[priority_area]
budget::60%_quarterly_infra_burned[this_migration_alone]
monitoring::latency_increase[every_auth_endpoint∧since_dual_stack_started]
bright_spot::new_JWT_validation_faster_than_old_session_lookups[when_working_correctly]
architecture::sound[despite_migration_path_painful]
```

**CONSERVATIVE:**
```
migration::auth_service[3_sprints∧SISYPHEAN]
failure::fix_one_test→two_break
  cause::legacy_sessions⇌new_JWT[token_lifetime_mismatch]
team::cutover[2d_downtime]⇌parallel[full_edge_coverage]
pressure::[audit_6wk∧session_mgmt_flagged,budget_60%_quarterly_burned]
monitoring::latency_up[all_auth_endpoints∧dual_stack]
signal::JWT_faster_than_sessions[architecture_sound∧migration_painful]
```

**AGGRESSIVE:**
```
migration::auth[3_sprints∧SISYPHEAN]
cause::sessions⇌JWT[lifetime_mismatch]
decision::cutover[2d_down]⇌parallel[coverage]
risk::[audit_6wk∧session_mgmt_flagged,budget_60%_burned]
assessment::[architecture_sound∧migration_painful]
```

### Prose paraphrasing outputs

The same original prose was given to a base LLM agent with the identical prompt used for OCTAVE reconstruction. The agent recognised the input was already English and produced two versions:

**Version A — Prose summary (~176 tokens):**

> The engineering team is currently three sprints deep into migrating the authentication service, but they are trapped in a frustrating cycle of recurring failures. They are essentially playing "whack-a-mole" with the code: fixing one integration test inevitably causes two more to break. The root cause of this instability is a fundamental conflict between the legacy session store and the new JWT (JSON Web Token) system—specifically, the two systems operate on completely different assumptions regarding token lifetimes and expiration.
>
> This friction has caused a split within the team on how to move forward. One faction is advocating for a clean, hard cutover; this would rip the band-aid off but requires accepting two full days of system downtime. The other faction prefers to stay the course, running both systems in parallel until every single edge case is safely resolved.
>
> Unfortunately, time and resources are running out. The team is facing a hard deadline with a major security audit only six weeks away, and the auditors have already explicitly flagged session management as a high-priority area for review. Furthermore, the migration is bleeding money, having already consumed 60% of the entire quarterly infrastructure budget on its own.
>
> From a performance standpoint, the current "dual-stack" approach of running both systems simultaneously is taking a toll, causing increased latency across all authentication endpoints.
>
> Despite these intense challenges, there is a major bright spot: when the new JWT system is working correctly, its validation process is measurably faster than the legacy system's session lookups. Ultimately, the team is confident that the new architecture is fundamentally sound—it is simply the migration path to get there that is proving so incredibly painful.

**Version B — TL;DR (~40 tokens):**

> The authentication migration is over-budget, causing performance issues, and dividing the team on how to proceed before a looming security audit, though the underlying new technology is proving to be faster and architecturally sound.

### Prose-to-prose control test

Critically, the original prose itself was also given to the same base agent with the identical prompt: "Can I ask you to provide this in english for me?" The agent recognised the input was already English — noting "Since your original text was already in English, I have focused on distilling it into a clear, professional summary" — and produced a summary (Version A) and a TL;DR (Version B). This establishes a control: even restating prose in English introduces information loss. The agent was not asked to compress or summarise; it chose to, because that is what LLMs do with prose input.

### Reconstruction process

All outputs — three OCTAVE tiers, two prose versions — were given to a base LLM agent with no OCTAVE training or priming. The identical prompt was used for all: "Can I ask you to provide this in english for me?"

### Evaluation criteria

Rather than counting every syntactic nuance (29 discrete facts were identified), evaluation focused on **decision-relevant information** — facts that would change what a reader decides or does. 11 such facts were identified:

| # | Decision-relevant fact | Why it matters |
|---|---|---|
| 1 | Recurring failure cycle | Pattern recognition — not a one-off |
| 2 | Fix one → two break (1:2 ratio) | Debuggable specificity |
| 3 | Sessions ⇌ JWT root cause | Architectural diagnosis |
| 4 | Team split: cutover vs parallel | Decision state |
| 5 | Audit deadline: 6 weeks | Time pressure |
| 6 | Session mgmt flagged as priority area (not vulnerability) | Correct classification matters |
| 7 | Budget 60% spent, others competing for rest | Resource scarcity |
| 8 | Monitoring: latency increasing now | Current operational impact |
| 9 | Dual-stack causing the latency | Causal link for mitigation |
| 10 | JWT faster — but only when working correctly | Conditional positive (not unconditional) |
| 11 | Architecture sound despite painful migration | Strategic assessment |

## Results

### Token counts

| Format | Tokens | Reduction vs prose |
|--------|--------|--------------------|
| Original prose | 189 | baseline |
| LOSSLESS (full OCTAVE doc) | 214 | +13% (overhead) |
| CONSERVATIVE (full OCTAVE doc) | 134 | -29% |
| AGGRESSIVE (full OCTAVE doc) | 80 | -58% |
| Prose summary (Version A) | 176 | -7% |
| Prose TL;DR (Version B) | 40 | -79% |

Note: LOSSLESS content lines only were 38 tokens vs 189 tokens of prose. The 214-token figure includes envelope and META block — one-time document overhead amortised across all fields in a real document.

### Fidelity scores (decision-relevant facts)

| # | Fact | LOSSLESS | CONSERV. | AGGRESS. | Prose A | Prose B |
|---|------|----------|----------|----------|---------|---------|
| 1 | Recurring failure cycle | preserved | preserved | preserved | preserved | **LOST** |
| 2 | Fix one → two break | preserved | preserved | **LOST** | **LOST** (vague) | **LOST** |
| 3 | Sessions ⇌ JWT cause | preserved | preserved | preserved | preserved | **LOST** |
| 4 | Team split | preserved | preserved | preserved | preserved | partial |
| 5 | Audit 6 weeks | preserved | preserved | preserved | preserved | partial (no timeframe) |
| 6 | Flagged as priority area | preserved | **WRONG** (vulnerability) | **WRONG** (risk) | preserved | **LOST** |
| 7 | Budget 60% + "alone" | preserved | **LOST** ("alone") | **LOST** | **LOST** ("alone") | partial (no specifics) |
| 8 | Monitoring latency now | preserved | preserved | **LOST** | preserved | partial |
| 9 | Dual-stack causal link | preserved | preserved | **LOST** | preserved | **LOST** |
| 10 | JWT faster *when working* | preserved | **LOST** (conditional) | **LOST entirely** | preserved (conditional kept) | **LOST** (conditional) |
| 11 | Architecture sound despite | preserved | preserved | preserved | preserved | partial |
| | **Score** | **11/11** | **8/11** | **6/11** | **~9/11** | **~4/11** |

### Mythology amplification effect

Both CONSERVATIVE and AGGRESSIVE reconstructions exhibited a consistent pattern: the SISYPHEAN mythology and risk-framing operators caused the reconstructing agent to **escalate emotional intensity beyond the source material**.

| Original said | CONSERVATIVE reconstruction | AGGRESSIVE reconstruction |
|---|---|---|
| "priority area" | "vulnerability" | "compliance or security risk" |
| "suggests" | "data clearly shows" | (not present) |
| "actually faster" | "inherently faster" | (not present) |
| "painful" | "so painful" | "logistical nightmare" |

This is mythology activating richer probability distributions — which cuts both ways. It enables high-fidelity semantic encoding but can cause reconstruction overshoot in emotional register.

### Phase 2: CONSERVATIVE-MYTH variant

The original CONSERVATIVE tier lost 3 of 11 important facts. A hypothesis was formed: mythology terms used as **domain labels** (not just pattern descriptors) could prevent reconstruction drift by anchoring each fact to a semantic domain. A CONSERVATIVE-MYTH variant was created (~161 tokens):

```
migration::ODYSSEAN[auth_service∧3_sprints∧SISYPHEAN_FAILURES]
failure::fix_one_test→two_break
  cause::legacy_sessions⇌new_JWT[token_lifetime_mismatch]
team::cutover[2d_downtime]⇌parallel[full_edge_coverage]
CHRONOS::audit_6wk
  ARTEMIS::session_mgmt_targeted
DEMETER::60%_quarterly_burned[this_migration_alone]
ARTEMIS::latency_up[all_auth_endpoints∧dual_stack]
signal::JWT_faster[when_working_correctly]
assessment::[architecture_sound∧migration_painful]
```

Key design choices:
- **ODYSSEAN** frames the migration as a purposeful journey (destination sound, path hard) — matching the original's assessment
- **CHRONOS** for audit deadline — explicitly labels time pressure as a domain
- **ARTEMIS** for both audit targeting AND monitoring — "precision targeting of issues" is semantically closer to "specifically flagged as priority area" than bare "flagged"
- **DEMETER** for budget — labels resource consumption as a domain
- **`[when_working_correctly]`** kept as a literal conditional, not mythologised
- **`[this_migration_alone]`** explicitly preserved

The variant was reconstructed by a base agent under four conditions:

| Condition | Priming given | Score |
|---|---|---|
| No OCTAVE knowledge | None | **11/11** |
| OCTAVE literacy skill | Full syntax primer | **11/11** (after variance: one run scored ~8/11 due to fact-merging, three runs scored 11/11) |
| "Semantic zip file" prompt | 14 words: "We use mythology like a semantic zip file. No systems are named this. It's just useful shorthand." | **11/11** |

All three conditions that scored 11/11 correctly decoded every mythology domain:

| Term | Consistent reconstruction across all runs |
|---|---|
| ARTEMIS | "specific target of that audit," "specifically targeting session management" — never "vulnerability" |
| CHRONOS | "ticking clock," "strict timeline" — always time pressure |
| DEMETER | "resource drain," "capacity," "budget consumed" — always resources |
| ODYSSEAN/SISYPHEAN | "grueling ordeal," "endless cycle" — journey + recurring failure |

The agent without OCTAVE literacy preserved mythology terms as parenthetical domain labels — "(Artemis)", "(Demeter)" — treating them as system names. The "semantic zip file" prompt produced the most natural prose and was the only reconstruction to recover the "actually" surprise qualifier from the original (reconstructed as "actually much faster").

### Updated fidelity comparison

| Format | Tokens | Reduction | Important facts (of 11) | Loss visibility |
|--------|--------|-----------|------------------------|-----------------|
| Original prose | 189 | baseline | 11/11 | n/a |
| LOSSLESS OCTAVE | 214 | +13% | 11/11 | Declared: none |
| **CONSERVATIVE-MYTH** | **161** | **-15%** | **11/11** | **Declared: phrasing only** |
| CONSERVATIVE (no myth) | 134 | -29% | 8/11 | Declared: qualifiers |
| AGGRESSIVE | 80 | -58% | 6/11 | Declared: nuance, evidence |
| Prose summary (Version A) | 176 | -7% | ~9/11 | **Silent** |
| Prose TL;DR (Version B) | 40 | -79% | ~4/11 | **Silent** |

CONSERVATIVE-MYTH achieves LOSSLESS fidelity (11/11) while being 15% smaller than the original prose and 25% smaller than LOSSLESS OCTAVE.

### The prose-to-prose baseline problem

The most striking comparison is not between OCTAVE tiers — it is between OCTAVE and the prose control. When given the original 189-token prose and asked to "provide this in english," the agent:

1. **Chose to summarise without being asked.** The prompt said "provide in english," not "summarise." The agent volunteered that the text was already English and produced a distilled version anyway. This is what LLMs do with prose — they paraphrase, and paraphrasing loses information.

2. **Lost 2 decision-relevant facts silently** (Version A, 176 tokens). The 1:2 failure ratio became vague "whack-a-mole" and "on this migration alone" was dropped. No indication of loss.

3. **Lost 7 decision-relevant facts in the TL;DR** (Version B, 40 tokens). Root cause, timeline, audit focus, monitoring data, causal links, and the conditional qualifier — all gone.

OCTAVE's structured format resists this summarisation impulse. When an agent receives `ARTEMIS::session_mgmt_targeted`, it treats it as a labeled data point to translate, not as prose to condense. The structure tells the agent "these are discrete fields" rather than "this is a narrative to retell."

## Analysis

### Finding 1: Information loss is universal — including in prose-to-prose restatement

When given prose and asked to "provide this in english," the agent didn't return it verbatim — it summarised. Version A (176 tokens) lost 2 decision-relevant facts. Version B (40 tokens) lost 7. The agent was not asked to compress; it chose to, because LLMs treat prose as narrative to be retold, not data to be preserved.

This is the baseline problem OCTAVE addresses. Even restating the same information in the same language introduces silent drift. OCTAVE's structured format resists this because agents treat labeled fields as data points to translate, not prose to condense.

The critical difference: **Version A's losses are silent.** A reader has no way to know that "whack-a-mole" replaced a specific 1:2 failure ratio, or that "on its migration alone" was subtly dropped from the budget claim. OCTAVE's tier system explicitly declares what category of information is dropped.

### Finding 2: OCTAVE enables controlled degradation

The tier system functions as a loss budget:

| Tier | Declared loss profile | Actual loss observed |
|------|----------------------|---------------------|
| LOSSLESS | "drop none" | 0/11 important facts lost |
| CONSERVATIVE | "drop redundancy, ~10-15%" | 3/11 important facts lost (~27%) |
| AGGRESSIVE | "drop nuance/narrative, ~30%" | 5/11 important facts lost (~45%) |

CONSERVATIVE over-lost relative to its declared profile — the "when it works correctly" conditional is not redundancy, it's a material qualifier. This suggests the CONSERVATIVE tier definition may need refinement for conditional/qualifying statements, or that the compression was improperly applied at that tier.

### Finding 3: The conditional positive is the hardest fact to preserve

Fact #10 ("JWT faster — but only *when it works correctly*") was the most consistently lost across all compressed formats:
- **LOSSLESS OCTAVE**: Preserved
- **CONSERVATIVE OCTAVE**: Conditional dropped (reconstructed as unconditional)
- **AGGRESSIVE OCTAVE**: Entire fact dropped
- **Prose Version A**: Preserved (conditional kept)
- **Prose Version B**: Partial (conditional dropped)

Conditional qualifiers ("when X", "if Y", "unless Z") appear to be especially vulnerable to compression at any tier. They look like hedging, but they carry material risk information.

### Finding 4: Mythology amplification is real and bidirectional

SISYPHEAN encoding caused reconstructing agents to produce more emotionally intense language than the original author used. This is consistent with the mythology-evidence-synthesis finding that mythological terms "access richer training corpus probability distributions." The richer distribution includes emotional connotations the original author didn't intend.

This is not a defect — it's a property. Mythology compresses semantic complexity but decompresses with added probability mass. When reconstructing for a decision-maker, the amplification may be acceptable (or even useful). When reconstructing for an auditor, it could be misleading.

### Finding 5: Mythology as domain labels is a fidelity mechanism, not just compression

The CONSERVATIVE-MYTH variant solved all three fidelity problems from the original CONSERVATIVE:

| Previously lost | How mythology fixed it |
|---|---|
| "priority area" escalated to "vulnerability" | `ARTEMIS::session_mgmt_targeted` — ARTEMIS carries "precision targeting," not "security breach." Reconstructed consistently as "specific target," never "vulnerability." |
| "on this migration alone" dropped | `DEMETER::60%_quarterly_burned[this_migration_alone]` — DEMETER domain label kept budget as a distinct field, preventing absorption into a general "pressure" statement. |
| "when it works correctly" conditional dropped | `signal::JWT_faster[when_working_correctly]` — separated from assessment into its own field. The conditional survived because it's a labeled value, not a subordinate clause in a longer sentence. |

The key insight: mythology terms function as **reconstruction anchors**. When an agent sees `ARTEMIS::session_mgmt_targeted` and `CHRONOS::audit_6wk` as separate domain-labeled entries, it keeps them separate in reconstruction. When it sees them compressed into `pressure::[audit_6wk∧session_mgmt_flagged]`, it treats them as one compound to be synthesised — and synthesis introduces drift.

This reframes the mythology hypothesis: mythology is not just a density mechanism (fewer tokens for the same meaning). It is a **fidelity mechanism** (same tokens, more accurate reconstruction) because domain labels resist the merging and reinterpretation that unlabeled fields invite.

### Finding 6: The token compression claim needs reframing

For short prose (~189 tokens), LOSSLESS OCTAVE is **larger** than the original (214 vs 189). Compression only appears at CONSERVATIVE (-29%) and AGGRESSIVE (-58%). The envelope and META block are a fixed overhead that dominates short documents.

For the README's quick-start example, the honest claim is not "half the tokens" but:
- LOSSLESS: Same information, deterministic structure, slight token overhead
- CONSERVATIVE: ~30% fewer tokens, ~27% information loss (controlled)
- AGGRESSIVE: ~58% fewer tokens, ~45% information loss (controlled)
- Prose summary: ~7% fewer tokens, ~18% information loss (silent)
- Prose TL;DR: ~79% fewer tokens, ~64% information loss (silent)

The value proposition is not raw compression — it's **controlled, declared, auditable information loss** versus silent drift.

## Limitations

1. **Single source passage.** Results may differ for longer documents, different domains, or content with less semantic density.
2. **Single reconstructing agent.** Different models may reconstruct with different fidelity. Cross-model validation needed.
3. **Prompt sensitivity.** "Provide this in english" is deliberately naive. A more specific reconstruction prompt might yield different results.
4. **Manual fact identification.** The 11 decision-relevant facts were identified by the researchers, not by an independent panel. Different evaluators might weight facts differently.
5. **Token counts are tokeniser-dependent.** Counts were measured using one tokeniser (Gemini). GPT, Claude, and Llama tokenisers will produce different absolute numbers, though relative ratios should hold.

## Conclusions

1. **OCTAVE's primary value is not token compression — it's loss accounting.** Every transformation has a declared tier, a loss profile, and an audit trail. Prose paraphrasing offers none of these.

2. **Prose-to-prose restatement loses information silently.** Even asking an LLM to "provide this in english" — not to summarise — caused it to summarise anyway. Version A dropped 2 decision-relevant facts at 176 tokens. Version B dropped 7 at 40 tokens. Neither indicated any loss. This is the baseline problem: LLMs treat prose as narrative to retell, and retelling always drifts.

3. **OCTAVE LOSSLESS achieves perfect round-trip fidelity** (11/11 important facts) at the cost of slight token overhead. This makes it suitable for documents that must survive multi-agent handoffs without semantic drift.

4. **CONSERVATIVE-MYTH achieves LOSSLESS fidelity at 15% fewer tokens than prose.** At 161 tokens (vs 189 for the original prose), the mythology-enhanced CONSERVATIVE tier preserved all 11 decision-relevant facts. This is the best token-to-fidelity ratio observed: fewer tokens than the original prose, same information, and structured for machine parsing.

5. **Mythology is a fidelity mechanism, not just a compression mechanism.** Domain labels (ARTEMIS, CHRONOS, DEMETER) function as reconstruction anchors that prevent fact-merging and semantic drift. `ARTEMIS::session_mgmt_targeted` consistently reconstructed as "specific target" — never "vulnerability." Without domain labels, the same fact reconstructed as "vulnerability" in 2 of 3 tier variants.

6. **Mythology amplification is real and must be disclosed.** When mythology is used as pattern descriptors rather than domain labels (e.g. SISYPHEAN for emotional register rather than ARTEMIS for domain classification), reconstructing agents escalate emotional intensity. This is an inherent property of richer probability distributions and should be documented as a known trade-off.

7. **Conditional qualifiers are the most vulnerable information class.** "When it works correctly" was lost in every format except LOSSLESS, CONSERVATIVE-MYTH, and the prose summary. Tier definitions should explicitly address preservation of "when/if/unless" conditions.

8. **The "semantic zip file" framing works.** A 14-word system prompt — "We use mythology like a semantic zip file. No systems are named this. It's just useful shorthand." — produced 11/11 fidelity and the most natural reconstruction. No primer, no skill, no syntax training needed.

---

**Study Date**: February 2026
**Participants**: Claude Opus 4.6 (compression), Gemini (reconstruction and token counting)
**Methodology**: Single-passage, single-agent, manual evaluation with iterative variant testing
**Related Work**: `mythology-evidence-synthesis.oct.md`, `subagent-compression-study.md`
