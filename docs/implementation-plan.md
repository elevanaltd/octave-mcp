---
title: OCTAVE v1.0.0 Implementation Plan
version: 1.0.0
status: active
created: 2026-01-02
orchestrator: holistic-orchestrator
session: b0a04015-de06-4331-9489-649d7fda1567
---

# OCTAVE v1.0.0 Implementation Plan

## Summary

v1.0.0 = **"The Honest Minimum"**

Immutables Enforced + Schema Sovereignty Complete + Honest Gaps Documented

## Phased Implementation

### Phase 1: Core Validation Wiring (Issues #102, #105)

| Issue | Task | Dependencies | Status |
|-------|------|--------------|--------|
| #102 | Wire `_validate_section` to ConstraintChain | None | PENDING |
| #105 | Canonicalize `.oct.md` file extension | None | PENDING |

**#102 Design Decision** (via debate-hall 2026-01-02-wire-validate-section):

```
RESOLUTION:
1. Add optional `section_schema: SchemaDefinition | None` to _validate_section
2. Keep dict compatibility for existing Validator API
3. Schema-less sections: skip content validation, track as UNVALIDATED (I5)
4. Wire ConstraintChain.evaluate() for fields with holographic patterns
5. DO NOT validate targets - defer to #103

NO-GO:
- No SchemaDefinition injection into Validator constructor
- No E007 for schema-less sections (scope jump, high false positive risk)
- No target routing validation (scope creep per release plan)
```

**TDD Requirements**:
- RED: Test `_validate_section` with SchemaDefinition returns constraint errors
- GREEN: Implement minimal wiring
- REFACTOR: Clean up after tests pass

### Phase 2: Target Routing (Issues #103, #109)

| Issue | Task | Dependencies | Status |
|-------|------|--------------|--------|
| #103 | Implement target routing for `→§TARGET` | #102 | PENDING |
| #109 | Implement block inheritance | #103 | PENDING |

**Debate Required**: Before implementation, resolve via debate-hall:
- Audit trail format for `→§TARGET` routing
- How block inheritance interacts with explicit child targets

### Phase 3: I5 Completion (Issue #106)

| Issue | Task | Dependencies | Status |
|-------|------|--------------|--------|
| #106 | Complete I5 Schema Sovereignty enforcement | #102, #103 | PENDING |

**Success Criteria**:
- I5 status in PROJECT-CONTEXT.oct.md: PARTIAL → ENFORCED
- Validation status visible in all tool outputs

### Phase 4: Documentation (Issues #104, #107, #108)

| Issue | Task | Dependencies | Status |
|-------|------|--------------|--------|
| #104 | Quick-start guide with 2 examples | None | PENDING |
| #107 | Add validation checklist to spec | None | PENDING |
| #108 | Clarify ASSEMBLY rules with example | None | PENDING |

**Debate Required**: Before #104, resolve via debate-hall:
- Minimal DATA mode example that demonstrates value
- Minimal SCHEMA mode example that demonstrates value

## Quality Gates

All implementations must pass:
- `python -m pytest` - All tests passing
- `python -m mypy src` - No type errors
- `python -m ruff check src tests scripts` - No lint errors
- `python -m black --check src tests scripts` - Formatting compliant
- Coverage >= 85%

## Deferred (v1.1.0+)

| Issue | Description | Rationale |
|-------|-------------|-----------|
| #110 | Mythological pattern library | Nice-to-have, not trust-critical |
| #111 | Confidence scores | Design decision needed |
| #112 | Delta updates | Adds state complexity |
| #113 | Formal grammar (BNF/EBNF) | For tool builders, not adopters |

## Delegation Protocol

Per ho-orchestrate skill:
1. HO delegates to implementation-lead (IL) with TDD mandate
2. IL must load build-execution skill
3. After IL completion: CRS review (Codex) -> CE review (Gemini)
4. On blocking feedback -> rework loop with IL
5. All gates pass -> merge

## Current State

```
BRANCH: octave-v1-implementation (0↑0↓ with main)
COVERAGE: 91%
TESTS: 516 passing
I5: PARTIAL (target: ENFORCED)
```
