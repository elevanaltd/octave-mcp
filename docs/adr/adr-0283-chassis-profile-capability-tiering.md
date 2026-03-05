# ADR-0283: Chassis-Profile Schema for Agent Capability Tiering

## Status
APPROVED

Ratification debate: `2026-03-05-ratification-debate-adr-0283-c-01kjygse`
Ratification conditions: Three strengthening artifacts incorporated (Safety-Invariant Loader Contract, Holographic Overlap Matrix, Risk Mitigation Traceability)
Approved: 2026-03-05 (human approval)

## Context

### The Problem

Agent definitions declare 6-8 skills in `§3::CAPABILITIES`, but most operational contexts only need 2-3 at full fidelity. Currently, the anchor ceremony's FLUKES stage loads all declared skills with equal treatment — either full content or kernel extraction via cascading fallback. There is no mechanism for an agent definition to declare *which skills matter more in which context*.

This creates two failure modes:
1. **Token waste**: Loading 8 full skill bodies (~3000+ tokens) when only 2-3 are actively needed
2. **Capability drift**: A single flat skill list provides no structural boundary between "this agent can always do X" and "this agent can do Y only in context Z"

### The Origin

Wind/Wall/Door debate (`2026-02-25-should-we-create-a-specialized-01kj9rf7`) during Project 15 ecosystem coordination explored whether to fork the HO agent for cross-repo work. Three approaches were rejected:

- **Forking the agent**: Creates agent rot — two definitions diverge over time
- **Code-level `capability_mode`**: The anchor's `capability_mode` parameter exists but is opaque — no schema-level visibility into what each mode actually loads
- **Loading everything**: Burns context tokens; no structural boundary prevents capability drift

A subsequent debate (`2026-03-05-how-should-the-chassis-profile-01kjy02r`) explored the token efficiency dimension: even within a selected profile, not all skills need full body loading. The synthesis produced a "Holographic Kernel Architecture" concept — always load safety constraints and capability signatures (kernels), inflate full bodies only when needed.

### The Existing Infrastructure

The solution builds on infrastructure that already exists:

1. **`§5::ANCHOR_KERNEL`** (skills spec v9): Skills already define a high-density extraction section (~50 lines max, atoms only) containing `NEVER`, `MUST`, `GATE`, `LANE`, `DELEGATE`, `TEMPLATE`, `SIGNALS`. The anchor ceremony already extracts these via cascading fallback.

2. **`capability_mode` parameter**: `anchor_request` already accepts this parameter. The FLUKES loader just doesn't use it to differentiate skill loading.

3. **Cascading fallback** (skills spec §3): The anchor already has extraction priority: `§5::ANCHOR_KERNEL` → `§3::GOVERNANCE` → `SIGNALS` blocks → `WARN_UNSTRUCTURED`. The infrastructure for "load less than the full file" is built.

### What's Missing

The agent definition file has no way to declare:
- Which skills are invariant to identity (always needed regardless of context)
- Which skills belong to which operational context
- Which skills in a given context need full body vs. kernel-only loading

## Decision

### Extend `§3::CAPABILITIES` with Chassis-Profile Structure

Replace the current flat skill/pattern lists with a two-tier architecture:

```octave
§3::CAPABILITIES
  CHASSIS::[ho-mode, prophetic-intelligence, gap-ownership]
  PROFILES::[
    STANDARD::{
      match::[default],
      skills::[ho-orchestrate, subagent-rules, constitutional-enforcement],
      patterns::[mip-orchestration],
      kernel_only::[system-orchestration, decision-record-authoring]
    },
    ECOSYSTEM::{
      match::[context::p15, context::ecosystem],
      skills::[ho-ecosystem],
      patterns::[dependency-graph-map],
      kernel_only::[constitutional-enforcement]
    }
  ]
```

### Loading Semantics

The FLUKES stage skill loader follows deterministic rules:

| Category | What loads | When |
|----------|-----------|------|
| **CHASSIS** skills | Full body, always | Every ceremony, regardless of profile |
| **Profile `skills`** | Full body | When that profile is active |
| **Profile `patterns`** | Full body | When that profile is active |
| **Profile `kernel_only`** | `§5::ANCHOR_KERNEL` extraction only | When that profile is active |
| **Unlisted skills** | Nothing | Not loaded at all |

**Token budget example** (HO agent):
- Current: 8 full skills = ~3000+ tokens
- With Chassis-Profile: 3 chassis (~1200) + 3 profile skills (~900) + 2 kernels (~160) = ~2260 tokens
- Savings: ~25-30% reduction, with structural guarantees about what's loaded and why

### Profile Selection

Profile selection is deterministic, not LLM-reasoned:

1. **Explicit selection** (primary and only runtime mechanism): The `capability_mode` parameter in `anchor_request` maps directly to a profile name. `capability_mode="ECOSYSTEM"` loads the ECOSYSTEM profile. The caller (human or orchestrating agent) is responsible for choosing the correct mode.
2. **Default fallback**: If no `capability_mode` is specified, the profile with `match::[default]` is selected.
3. **No default**: If no `capability_mode` is specified and no profile has `match::[default]`, only CHASSIS skills load. The agent operates in a minimal but safe mode.
4. **Unknown profile error**: If `capability_mode` specifies a profile name that doesn't exist in the agent definition, the ceremony MUST emit a warning in the permit metadata and fall back to `default` or chassis-only. Silent degradation to a different capability set than intended is a debuggability trap.

#### The `match` Field: Declared Intent, Not Runtime Logic

The `match` field in a profile declaration serves as **documentation-as-schema** — it declares the contexts a profile is *designed for*, not a runtime matching engine. The `context::` values are human-readable descriptors:

```octave
ECOSYSTEM::{
  match::[context::p15, context::ecosystem],  // "This profile is for P15 and ecosystem work"
  skills::[ho-ecosystem],
  ...
}
```

**The Anchor does not do filesystem analysis.** It does not inspect `pnpm-workspace.yaml`, parse `package.json`, or scan git branches to determine context. The Anchor is a text compiler, not a filesystem analyzer. Profile selection is always explicit via `capability_mode`.

**Future consideration**: A higher-level orchestrator (Workbench, HO, or a dedicated context resolver) could eventually do environment detection and pass the result as `capability_mode`. This keeps the Anchor simple and pushes context intelligence to the layer that has the right information. But this is not in scope for this ADR.

**Design constraint**: `default` is a reserved keyword that may only appear as the sole condition in a match list: `match::[default]`. It may not be mixed with `context::` conditions.

### Design Properties

#### 1. Mutual Exclusivity
Only one profile is active at a time. The ECOSYSTEM profile structurally cannot access `ho-orchestrate` — there is no code path that loads it. This is a schema-level guarantee, not a runtime convention.

#### 2. Declarative Auditability (I4)
All valid configurations are visible in the `.oct.md` file. A reviewer can read the agent definition and enumerate every possible capability set. No hidden code logic determines what loads.

#### 3. Chassis Invariance
CHASSIS skills define identity — lane discipline, cognition, philosophy. Profiles cannot override or exclude chassis skills. The chassis is the answer to "who is this agent regardless of context?"

#### 4. Kernel-Only as Awareness Without Cost
`kernel_only` skills provide:
- **Safety constraints** (`NEVER` rules are always active)
- **Capability awareness** (the agent knows the skill exists and what it does)
- **No procedural weight** (templates, guides, and execution steps stay unloaded)

This means an agent in ECOSYSTEM mode still knows `constitutional-enforcement` exists and what it forbids — but doesn't burn ~400 tokens on its full procedural content.

**Important constraint**: `kernel_only` is a ceremony-time commitment, irrevocable for the session. An agent loaded with kernel-only skills cannot access the full procedural content of those skills within the same ceremony. If full procedural access is required, a new ceremony with the skill promoted to the `skills` list is needed. Profile designers should be conservative — when in doubt, put a skill in `skills` rather than `kernel_only`. The token savings of kernel_only (~200-400 tokens per skill) are not worth the cost of a mid-session capability gap.

#### 5. Backward Compatibility
Agents with flat `SKILLS::[]` / `PATTERNS::[]` continue to work. The FLUKES loader treats a flat list as equivalent to a single profile named `DEFAULT` with all skills as full-body. Migration is opt-in per agent.

### Design Decisions on Open Questions

#### Match semantics: OR-only
`match` conditions use OR semantics. If any condition matches, the profile activates. AND semantics create combinatorial explosion with no current use case. If AND is needed later, it can be added as `match_all::[]` without breaking OR behavior.

#### No profile inheritance
Profiles do not inherit from each other. If ECOSYSTEM needs a skill that STANDARD also has, it must list it explicitly. This is intentional:
- Inheritance makes mutual exclusivity fuzzy ("does ECOSYSTEM include STANDARD's skills?")
- Explicit duplication is auditable; implicit inheritance requires tracing resolution chains
- The cost of listing 3-5 extra skill names is negligible vs. the debugging cost of inheritance surprises

#### No `required` flag in skill files
Skills should not know they are "chassis" — that's an agent-level concept. A skill like `ho-mode` is chassis for the HO agent but irrelevant to an implementation-lead. The agent definition declares what's invariant, not the skill file.

#### Grammar validation
Mutual exclusivity (one active profile) is enforced by the anchor ceremony at runtime, not by the OCTAVE grammar at parse time. The grammar validates structural correctness (CHASSIS is a list, PROFILES contains named blocks with required fields). The ceremony validates semantic correctness (exactly one profile selected).

#### Overlap rules and collision resolution

The following overlap conditions are explicitly defined for **static validation** (parse-time):

| Condition | Verdict | Rationale |
|-----------|---------|-----------|
| CHASSIS skill also in a profile's `skills` | Validator error | Redundant — chassis always loads full body |
| CHASSIS skill also in a profile's `kernel_only` | Validator error | Contradictory — chassis loads full body, kernel_only loads less |
| Same skill in `skills` for Profile A and `kernel_only` for Profile B | Valid | Profiles are mutually exclusive; the skill loads at different fidelity depending on active profile |
| Same skill in `skills` for both Profile A and Profile B | Valid | Explicit duplication across profiles is expected (no inheritance) |
| `default` mixed with `context::` conditions in same `match` list | Validator error | `default` absorbs all contexts, making other conditions meaningless |
| `default` as sole match condition | Valid | Designates the fallback profile |
| Duplicate profile names in PROFILES | Validator error | Ambiguous resolution |

The following **runtime collision resolution rules** govern the FLUKES loader when edge cases arise:

1. **Identity Supremacy**: If a skill appears in both CHASSIS and a profile (should be caught by validator, but as a safety invariant): load full body via CHASSIS. Identity cannot be degraded by context.
2. **Procedural Necessity**: If a skill somehow appears in both `skills` and `kernel_only` within the same profile: load full body. Explicit need for full body overrides the efficiency request.
3. **Context Specificity**: If a specific context match fires, it suppresses the `default` profile. Specific context always overrides generic default.
4. **Exclusivity Violation**: If more than one non-default profile matches the current context, the ceremony MUST halt with an error (`AMBIGUOUS_PROFILE_MATCH`). No implicit merging of profiles.

### Agents-Spec Versioning

This ADR targets **agents-spec v8.0.0**. The version transition:

- **v7.x (current)**: Flat `SKILLS::[]` / `PATTERNS::[]` in §3
- **v8.0 (this ADR)**: Introduces `CHASSIS` / `PROFILES` structure. Flat lists remain valid and are treated as equivalent to a single `DEFAULT` profile with all skills as full-body
- **v9.0 (future, not this ADR)**: Flat `SKILLS::[]` deprecated. All agent definitions must use chassis-profile structure

The FLUKES loader must handle both formats during the v8.x window. Version detection is based on the presence of `CHASSIS` or `PROFILES` keys — if present, use structured loading; if absent, use legacy flat loading.

### Cognition Files — Out of Scope

Cognition files (`logos.oct.md`, `ethos.oct.md`, `pathos.oct.md`) are explicitly out of scope for capability tiering. Cognition defines cognitive identity (§1::IDENTITY::COGNITION) and is always loaded at full body. This is justified by the same principle as CHASSIS: cognition is invariant to operational context. An agent's thinking style does not change based on which profile is active.

## Implementation Surface

### octave-mcp (this repository)

1. **Agent spec update**: Add `CHASSIS`, `PROFILES`, `match`, `skills`, `patterns`, `kernel_only` to `octave-agents-spec.oct.md` §3. Target version: v8.0.0
2. **Grammar rules**: EBNF/GBNF rules for the new nested structure
3. **Validator**: Structural validation — CHASSIS is list, each profile has required fields, overlap rules enforced per the table in "Overlap rules" above
4. **Backward compatibility**: Parser accepts both flat `SKILLS::[]` and new `CHASSIS`/`PROFILES` structure
5. **Test vectors**: Valid and invalid test cases covering: chassis-profile document, profile with kernel_only, flat backward-compatible list, CHASSIS overlap with profile skill (invalid), CHASSIS overlap with kernel_only (invalid), duplicate profile names (invalid), `default` mixed with context conditions (invalid), `default` as sole match (valid)

### odyssean-anchor-mcp (downstream — HestAI-MCP#284)

1. **FLUKES loader**: Read `§3::CAPABILITIES`, detect flat vs. structured format
2. **Profile resolver**: Match `capability_mode` parameter to profile name, fall back to `default` profile if no `capability_mode` specified. No filesystem analysis — profile selection is purely based on the explicit parameter
3. **Differentiated loading**: Full body for chassis + profile `skills`, kernel extraction for `kernel_only` via the Safety-Invariant Loader Contract (see below)
4. **Permit metadata**: Include active profile name and loading manifest (which skills loaded at what fidelity) in the permit for auditability
5. **Error handling**: Unknown `capability_mode` → warn + fallback to default or chassis-only; no `capability_mode` and no default profile → chassis-only with warning

### hestai-mcp (downstream — agent definitions)

1. **Agent file migration**: Convert flat skill lists to chassis-profile structure
2. **Profile design**: Determine which skills belong to which profiles per agent

### Safety-Invariant Loader Contract

The `kernel_only` loading mode follows a cascading extraction protocol that guarantees safety constraints are always present, even for skills with incomplete or missing `§5::ANCHOR_KERNEL` sections:

```
STEP 1: Check §5::ANCHOR_KERNEL exists?
  → YES: Extract §5 content. DONE.
  → NO:  Go to Step 2.

STEP 2: Check §3::GOVERNANCE exists?
  → YES: Extract §3 (truncate to 300 tokens). Tag output with SOURCE::FALLBACK_GOVERNANCE. DONE.
  → NO:  Go to Step 3.

STEP 3: Identity Fallback
  → Extract §1::CORE. Tag output with WARN::UNCONSTRAINED_CAPABILITY_LOADED.
  → Log permit warning: "Safety kernel missing for skill X"
```

This contract ensures that `kernel_only` never produces a silent empty result. The cascading fallback aligns with the existing skills spec v9 §3 extraction priority but makes the algorithm explicit and mandatory for the FLUKES loader implementation.

### Risk Mitigation Traceability

| Risk | Mitigation | Status |
|------|-----------|--------|
| R1: Safety regression in legacy skills (missing §5) | Cascading Safety Extraction Protocol (loader contract above) | Resolved by design |
| R2: Profile proliferation / capability drift | Mutual exclusivity + no inheritance + validator warning at 4+ profiles | Controlled |
| R3: Operational friction (kernel_only irrevocability) | Accepted tradeoff — restart cost buys auditability. Future JIT inflation path preserved | Accepted tradeoff |
| R4: Ambiguous overlap resolution | Holographic Overlap Matrix (static + runtime rules above) | Resolved by spec |
| R5: Scope creep into filesystem analysis | Anchor constrained to text compilation; `capability_mode` is explicit parameter only; filesystem detection deferred to future orchestrator layer | Eliminated by design |

## Consequences

### Positive
- Schema-level capability boundaries prevent drift between operational modes — the enduring structural guarantee
- Structural token savings (~25-30%) without losing capability awareness
- Existing `§5::ANCHOR_KERNEL` infrastructure means skill files need no changes
- `capability_mode` parameter gains schema-visible meaning
- Backward compatible — no forced migration

### Negative
- Agent definitions become more complex (nested structure vs. flat list)
- Profile design requires upfront thought about operational contexts
- The anchor ceremony's FLUKES loader becomes more complex (but deterministically so)

### Risks
- **R1: Profile proliferation**: Agents could accumulate many profiles. Mitigation: validator emits a warning (not error) at 4+ profiles, requiring a justification comment. This makes the convention visible without blocking legitimate use cases.
- **R2: Match ambiguity**: Multiple profiles could match the same context. Mitigation: profiles are evaluated in declaration order; first match wins. `default` must be the last profile and may only appear as a sole match condition.
- **R3: Kernel insufficiency**: `kernel_only` is a ceremony-time commitment — the agent cannot access full procedural content mid-session. Mitigation: the `§5::ANCHOR_KERNEL` spec requires `NEVER` and `MUST` fields, covering safety. Profile designers should default to `skills` and only demote to `kernel_only` when they are confident the procedural content is not needed in that context. When in doubt, use `skills`.
- **R4: Schema version fragmentation**: The agents-spec v8 introduces a new structure while v7 flat lists must remain valid. Mitigation: version detection is structural (presence of CHASSIS/PROFILES keys), not META-based. The FLUKES loader handles both formats during the v8.x transition window. See "Agents-Spec Versioning" above.
- **R5: Scope creep into filesystem analysis**: The `match` field could tempt future implementations to make the Anchor inspect the filesystem for context signals. Mitigation: this ADR explicitly constrains the Anchor to text compilation — profile selection is via explicit `capability_mode` parameter only. Filesystem-based context detection is deferred to a future higher-level orchestrator layer.

## Future Considerations

### On-Demand Inflation (Not in This ADR — tracked as separate issue)
The debate explored "Vector B" — an agent seeing a kernel and requesting full body loading mid-session via `Skill(inflate::"skill-id")` or a dedicated `inflate_skill` MCP tool. This is the natural escape hatch for the kernel_only irrevocability trap (Dragon 1): an agent hits a capability gap, realizes it only has the kernel, and calls the tool to fetch the full body. This is architecturally compatible with the chassis-profile model and should be prioritized early in the v9 roadmap. See HestAI-MCP#307 for tracking.

### INFLATE_ON Triggers (Not in This ADR)
The debate proposed file-pattern and tag-based triggers for automatic skill inflation. This overlaps with the `match` field but operates at the individual skill level rather than the profile level. Deferred until there's a concrete use case that profiles don't satisfy.

## References

- Issue #283: RFC for Chassis-Profile schema
- Debate: `2026-02-25-should-we-create-a-specialized-01kj9rf7` (fork vs. dynamism)
- Debate: `2026-03-05-how-should-the-chassis-profile-01kjy02r` (skill loading efficiency)
- Debate: `2026-03-05-ratification-debate-adr-0283-c-01kjygse` (ratification — approved with conditions)
- Issue #222: AUTHORITY field formalization (precedent for evolving agent spec)
- Skills spec v9: `§5::ANCHOR_KERNEL` and cascading fallback
- HestAI-MCP#284: Capability tiers implementation (downstream)
- HestAI-MCP#285: Tiered permit model (downstream)
