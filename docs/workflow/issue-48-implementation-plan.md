# Issue 48: Vocabulary Snapshot Hydration - Implementation Plan

## Executive Summary

Issue 48 implements **vocabulary sharing via hydration at authoring time** through the "Living Scrolls" pattern - self-contained documents with embedded provenance that stand alone while maintaining full auditability.

This plan synthesizes 5 debate rounds (18 comments) from multi-model Wind/Wall/Door debates.

---

## Background

**Rejected Approach**: `INHERIT::` with runtime resolution (over-engineered "NPM for adjectives")

**Approved Approach**: `IMPORT→SNAPSHOT` hydration at authoring time with:
- Zero runtime dependencies
- Documents remain self-contained ("Sealed Books")
- Provenance via section annotations (already implemented in parser.py:172-223)
- No parser changes required for core hydration (§OCTAVE sentinel deferred to Phase 2)

---

## Approved Patterns from Debates

### 1. SNAPSHOT-WITH-MANIFEST (Debate Round 2)

```octave
§CONTEXT::SNAPSHOT[@mythos/greek,2025-12-25]
  ATHENA::"Strategic Wisdom"
  HERMES::"Communication Speed"

§SNAPSHOT.MANIFEST:
  SOURCE_URI::"../../shared/vocabulary.oct.md"
  SOURCE_HASH::"sha256:a1b2c3..."
  HYDRATION_TIME::"2026-01-02T10:30:00Z"
  HYDRATION_POLICY:
    DEPTH::1
    PRUNE::used_only
    COLLISION::error

§SNAPSHOT.PRUNED::[API_ENDPOINT,WEBHOOK,RATE_LIMIT]

§SNAPSHOT.FRESHNESS:
  STALE_AFTER::"2026-01-09T10:30:00Z"
  CHECK_URI::"../../shared/vocabulary.oct.md"
```

### 2. Living Scrolls with §SEAL (Debate Round 3)

```octave
§OCTAVE::6.0.0
===VOCABULARY_CAPSULE===
META:
  TYPE::CAPSULE
  NAME::"HestAI Constitutional Vocabulary"
  VERSION::"1.0.0"

§1::CORE_TERMS
  IMMUTABLE::"Requirement that survives all pressure tests"
  COGNITION::"Behavioral mode (ETHOS|LOGOS|PATHOS)"

§SEAL:
  SCOPE::LINES[1,N-1]
  ALGORITHM::SHA256
  HASH::"a1b2c3..."
  GRAMMAR::6.0.0
===END===
```

### 3. Companion Documents with Bidirectional Links (Debate Round 4)

```octave
# In spec (src/octave_mcp/resources/specs/octave-core-spec.oct.md):
META:
  TEACHES::[§skills/octave-literacy,§skills/octave-mastery]
```

```yaml
# In skill (skills/octave-literacy/SKILL.md):
---
implements: src/octave_mcp/resources/specs/octave-core-spec
coverage:
  §MAPS_TO::
    SKILL_§1::[SPEC_§1,SPEC_§4]
    SKILL_§3::[SPEC_§6]
    SKILL_§4::NOVEL
---
```

### 4. VOID MAPPER Output Format (Debate Round 5)

```
COVERAGE_RATIO::57%[4/7_spec_sections]
GAPS::[§3_TYPES,§5_MODES,§7_EXAMPLES]
NOVEL::[SKILL_§4]
```

### 5. ASSIST vs INVENT Symbol Convention (Debate Round 5)

| Symbol | Meaning | Rule |
|--------|---------|------|
| `→` | Transform (copy/filter) | PERMITTED |
| `⊕` | Synthesize (novel content) | REQUIRES EVIDENCE |

---

## Blocked Features

| Feature | Reason | Debate |
|---------|--------|--------|
| Ghost Links | No audit trail, violates I4/I5 | Round 2 |
| Implicit pruning without manifest | Violates I2 | Round 2 |
| Auto-update without user action | Violates Human Primacy | Round 2 |
| Runtime resolution | Violates standalone document principle | Round 1 |
| Layered Content Architecture (dir reorg) | 87 hard-coded path references | Round 4 |
| Holographic Capability Cartridges | I3 violation, skill discovery breakage | Round 4 |
| Pedagogy Tag `[skill::export]` | Requires grammar change | Round 5 |
| Holographic Scaffolder | Low value, de-prioritized | Round 5 |

---

## Vocabulary Storage Structure (Approved)

```
src/octave_mcp/resources/specs/
└── vocabularies/
    ├── registry.oct.md          # Machine-readable index
    ├── core/                     # Ships with octave-mcp
    │   ├── META.oct.md
    │   ├── SNAPSHOT.oct.md      # Issue #48
    │   ├── SESSION_LOG.oct.md
    │   └── NORTH_STAR.oct.md
    └── contrib/                  # Future community vocabs
```

---

## Immutable Compliance Matrix

| Immutable | Mechanism | Status |
|-----------|-----------|--------|
| **I1: Syntactic Fidelity** | Hydrated content uses canonical OCTAVE syntax; pre-seal normalization | ENFORCED |
| **I2: Deterministic Absence** | §SNAPSHOT.PRUNED explicitly lists available-but-unused terms | ENFORCED |
| **I3: Mirror Constraint** | No inference—collision policy is `error` by default | ENFORCED |
| **I4: Transform Auditability** | §SNAPSHOT.MANIFEST is the receipt; §SEAL provides verification | ENFORCED |
| **I5: Schema Sovereignty** | `validation_status` propagates from source | ENFORCED |

---

## Implementation Phases

### Phase 1: Foundation (NOW - MVP)

**Sequencing**: Contract-First Hydration (Schema → Tests → Core → CLI)

| Task | Description | Files | Priority |
|------|-------------|-------|----------|
| 1.1 | Create `src/octave_mcp/resources/specs/vocabularies/` directory structure | New directory | HIGH |
| 1.2 | Create `registry.oct.md` index | `src/octave_mcp/resources/specs/vocabularies/registry.oct.md` | HIGH |
| 1.3 | Define TYPE::CAPSULE schema | `src/octave_mcp/resources/specs/schemas/capsule.oct.md` | HIGH |
| 1.4 | Create golden-master test fixtures | `tests/fixtures/hydration/` | HIGH |
| 1.5 | Create hydration logic module with HydrationPolicy | `src/octave_mcp/core/hydrator.py` (new) | HIGH |
| 1.6 | Add §SNAPSHOT.MANIFEST generation | Part of hydrator | HIGH |
| 1.7 | Add §SNAPSHOT.PRUNED generation (tree shaking) | Part of hydrator | HIGH |
| 1.8 | Implement `octave hydrate` CLI command | `src/octave_mcp/cli/main.py` | HIGH |
| 1.9 | Unit tests for hydration | `tests/test_hydrator.py` | HIGH |
| 1.10 | Integration tests | `tests/integration/test_hydrate_cli.py` | HIGH |
| 1.11 | Add Companion Documents: `TEACHES::` to specs | `src/octave_mcp/resources/specs/octave-*-spec.oct.md` | MEDIUM |
| 1.12 | Add Companion Documents: `implements:` to skills | Skills YAML frontmatter | MEDIUM |
| 1.13 | Document ASSIST vs INVENT convention | `docs/CONTRIBUTING.md` or similar | MEDIUM |

### Phase 2: Verification & Tooling (SOON)

| Task | Description | Priority |
|------|-------------|----------|
| 2.1 | Add §OCTAVE grammar sentinel to parser | HIGH |
| 2.2 | Implement `octave normalize` CLI command | HIGH |
| 2.3 | Implement `§SEAL` computation | HIGH |
| 2.4 | Implement `octave seal` CLI command | HIGH |
| 2.5 | Add `§SEAL` verification to validate command | HIGH |
| 2.6 | Implement VOID MAPPER tool | HIGH |
| 2.7 | Add `octave coverage` CLI command | HIGH |
| 2.8 | Add `octave hydrate --check` for staleness detection | MEDIUM |
| 2.9 | Add `octave vocab list` command | MEDIUM |
| 2.10 | Implement PEDAGOGY DIFF tool | MEDIUM |
| 2.11 | PRUNE_MANIFEST policy options (hash/count/elide) | MEDIUM |
| 2.12 | Cycle detection for recursive imports | MEDIUM |

### Phase 3: Federation & Advanced (LATER)

| Task | Description | Priority |
|------|-------------|----------|
| 3.1 | Seal-Linked JSON-LD/RDF projection exports | MEDIUM |
| 3.2 | Remote vocabulary fetch (`oct-get` style) | LOW |
| 3.3 | Context Hydration on Demand (agent error → inject spec) | LOW |
| 3.4 | SchemaStore submission | LOW |

---

## Risk Matrix

| Risk | Description | Severity | Mitigation |
|------|-------------|----------|------------|
| R1 | Vocabulary Drift | Medium | `STALE_AFTER` + tooling warns |
| R2 | Circular Imports | High | `DEPTH::1` default; cycle detection |
| R3 | Hash Collisions | Negligible | SHA-256 (~2^128 operations) |
| R4 | Large Vocab Bloat | Medium | Tree shaking + PRUNE_MANIFEST |
| R5 | Breaking Changes | High | **Needs deprecation strategy** |
| R6 | Merge Conflicts | Medium | Accept as cost; or `--preserve-timestamp` |
| R7 | Namespace Collisions | High | `COLLISION::error` default |
| R8 | Tooling Required | Medium | By design (lenient→canonical) |

---

## Decided Defaults (Per 2026-01-03 Debate)

| Parameter | Decision | Rationale |
|-----------|----------|-----------|
| **PRUNE_MANIFEST** | `list` | Auditability for Phase 1 MVP; `hash` option added in Phase 2 |
| **COLLISION** | `error` | I3 compliance - no silent override; user must resolve conflicts explicitly |
| **Grammar Sentinel** | Phase 2 | Not required for core hydration; deferred to §SEAL verification phase |

## Remaining Open Questions

1. **Breaking changes strategy**: How should term renames/removals be handled?
2. **R5 Mitigation**: Need deprecation/migration strategy design

---

## Technical Notes

### Parser Infrastructure Already Exists
- Section annotations `[...]` implemented (`parser.py:172-223`)
- `@` location operator in lexer (`TokenType.AT`)
- No new syntax required - reuses existing patterns

### CLI Pattern
- Uses Click framework
- Follows existing `eject`/`validate`/`write` pattern
- New commands fit naturally: `hydrate`, `normalize`, `seal`, `coverage`

### Canonical Text Rules (Wall Condition C1)
- UTF-8 encoding
- LF-only line endings
- Trimmed trailing whitespace
- Normalized indentation (2 spaces)

---

## Debate Synthesis Tracker

| Debate | Topic | Final Verdict |
|--------|-------|---------------|
| Round 1 | Basic SNAPSHOT | APPROVED |
| Round 2 | Audited Capsule | APPROVED (§SNAPSHOT.* blocks) |
| Risk Analysis | PRUNE_MANIFEST options | DECIDED: `list` default |
| Round 3 | Living Scrolls | APPROVED (§SEAL, §OCTAVE sentinel → Phase 2) |
| Package Structure | Path 1.7 | APPROVED (`src/octave_mcp/resources/specs/vocabularies/`) |
| Project Structure | Layered Content | SUPERSEDED (no dir reorg) |
| Round 4 | Companion Documents | APPROVED (bidirectional links) |
| Round 5 | Spec-Skill Tooling | VOID MAPPER approved, Scaffolder de-prioritized |

---

## References

- Issue #48: https://github.com/elevanaltd/octave-mcp/issues/48
- Issue #32 (closed): Original §CONTEXT proposal
- PR #47: Phase 1 implementation
- Parser annotations: `src/octave_mcp/core/parser.py:172-223`

---

*Generated from 18 debate comments on Issue #48*
*Last updated: 2026-01-03*
*Decisions resolved: 2026-01-03 (debate-hall thread: 2026-01-03-issue48-phase1-scope)*
