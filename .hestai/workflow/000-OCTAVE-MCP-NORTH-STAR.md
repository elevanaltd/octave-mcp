---
project: OCTAVE-MCP
version: 1.0.0
created: 2025-12-28
status: approved
approved_by: user
approved_date: 2025-12-28
---

# OCTAVE-MCP North Star

## Project Identity

**Name**: OCTAVE-MCP (Olympian Common Text And Vocabulary Engine - Model Context Protocol Server)

**Mission**: Provide a deterministic document format and control plane for LLM systems that keeps meaning durable when text is compressed, routed between agents, or projected into different views.

**Core Identity**: OCTAVE-MCP is a **loss accounting system** for LLM communication.

## The Layered Fidelity Principle

All immutable requirements derive from a single architectural pattern: **Layered Fidelity**

```
┌─────────────────────────────────────────────┐
│  INTENT LAYER (I3: Mirror Constraint)       │ ← NEVER TOUCH
│  "What did the author mean?"                │
├─────────────────────────────────────────────┤
│  VALUE LAYER (I1: Syntactic Fidelity)       │ ← LOG EVERYTHING
│  "What data was transformed?"               │
├─────────────────────────────────────────────┤
│  AUDIT LAYER (I4: Transform Auditability)   │ ← RECEIPTS REQUIRED
│  "What was lost and why?"                   │
├─────────────────────────────────────────────┤
│  SCHEMA LAYER (I5: Schema Sovereignty)      │ ← VALIDATION VISIBLE
│  "Was this checked against rules?"          │
├─────────────────────────────────────────────┤
│  ABSENCE LAYER (I2: Deterministic Absence)  │ ← PRESENCE ≠ NULL
│  "Is nothing the same as missing?"          │
└─────────────────────────────────────────────┘
```

Each layer answers one question about information fidelity. Together they form a complete audit surface.

---

## IMMUTABLE REQUIREMENTS

### I1: SYNTACTIC FIDELITY

**Statement**: Normalization shall alter syntax (representation) but never semantics (meaning). Every transformation preserving meaning is logged; every transformation altering meaning is FORBIDDEN.

**Rationale**: This is mathematical: `canon(x)` must be idempotent and bijective on semantic space. The distinction between TIER_NORMALIZATION (safe) and TIER_FORBIDDEN (never) creates a bright line that requires no inference.

**Pressure Test**:
- Would you change this for faster/cheaper delivery? NO - violating this destroys trust
- Still true in 3 years with different technology? YES - any document processor must preserve meaning

**Current Enforcement**: ENFORCED
- W001-W005 correction codes logged
- RepairLog tracks `semantics_changed: bool`
- TIER_FORBIDDEN documented in architecture spec

**What Breaks If Not Honored**: System becomes a liar. Repairs transform dissent into agreement, nuance into binary.

---

### I2: DETERMINISTIC ABSENCE

**Statement**: The system shall distinguish between "absent" (field not provided), "null" (explicitly empty), and "default" (schema-provided). Absence shall propagate as addressable state, never silently collapse to null or default.

**Rationale**: Downstream systems must know whether "tests section missing" means "no tests exist" vs "tests not checked." Any serialization format can distinguish these three states.

**Pressure Test**:
- Would you change this for faster/cheaper delivery? NO - collapsing states introduces semantic drift
- Still true in 3 years? YES - the distinction between absence and null is fundamental

**Current Enforcement**: PARTIAL
- `null` and `[]` supported per core types
- Absence-as-addressable-state not systematically enforced yet

**What Breaks If Not Honored**: Lossy compression becomes misinformation. Cannot distinguish "didn't check" from "isn't there."

---

### I3: MIRROR CONSTRAINT

**Statement**: The system shall reflect only what is present, creating nothing. When input is ambiguous or invalid, the system shall ERROR with educational context rather than guess. The only exception is explicit, logged, reversible normalization.

**Rationale**: Non-reasoning is the core differentiator from LLM-based processing. "Helpful" guessing introduces security vulnerabilities and unpredictability.

**Pressure Test**:
- Would you change this for faster/cheaper delivery? NO - guessing creates attack surface
- Still true in 3 years? YES - deterministic systems require deterministic input handling

**Current Enforcement**: PARTIAL
- TIER_FORBIDDEN documented
- E001-E006 error messages exist with rationale
- Schema validation currently allows bypass (`schema=None`)

**What Breaks If Not Honored**: Attack surface for malicious instructions executed because system "helpfully" inferred intent.

---

### I4: TRANSFORM AUDITABILITY

**Statement**: Every entropy-reducing transformation shall produce a recoverable audit record. The record shall include: rule_id, before, after, tier, and semantics_changed. Silent transformation is FORBIDDEN.

**Rationale**: If bits were lost, there must be a receipt. Tombstones for compression are future work, but transform logging is implementable now.

**Pressure Test**:
- Would you change this for faster/cheaper delivery? NO - silent changes make debugging impossible
- Still true in 3 years? YES - audit requirements only increase as AI systems proliferate

**Current Enforcement**: ENFORCED for normalization, BLOCKED for compression
- RepairEntry dataclass enforces required fields
- W002 (ASCII→Unicode) logged
- Compression tier logging: NOT IMPLEMENTED

**What Breaks If Not Honored**: Compression engine becomes censorship engine. Validation passes while information is removed untraceably.

---

### I5: SCHEMA SOVEREIGNTY

**Statement**: A document processed without schema validation shall be marked as UNVALIDATED in its output metadata. Schema-validated documents shall record the schema name and version used. Schema bypass shall be visible, never silent.

**Rationale**: If you can't validate, you must say you can't. Traceability requirement is enforceable now even if full validation is future work.

**Pressure Test**:
- Would you change this for faster/cheaper delivery? NO - silent bypass creates false confidence
- Still true in 3 years? YES - schema versioning becomes more important as systems mature

**Current Enforcement**: BLOCKED → convertible to PARTIAL
- Currently: `schema=None` silently bypasses validation
- Required: output should include `validation_status: UNVALIDATED | VALIDATED(schema, version)`

**What Breaks If Not Honored**: False sense of safety. Schema claims not enforced. Semantic drift through schema version mismatch.

---

## CONSTRAINED VARIABLES

### Immutable (5)
- I1: Syntactic Fidelity
- I2: Deterministic Absence
- I3: Mirror Constraint
- I4: Transform Auditability
- I5: Schema Sovereignty

### Flexible (implementation decisions)
- Number of MCP tools (currently 4, planned consolidation to 3)
- Specific error codes (E001-E006 pattern, content may evolve)
- Compression tier names (NORMALIZATION, REPAIR, FORBIDDEN)
- Specific schema formats (can add new schemas without changing immutables)

### Negotiable (business tradeoffs)
- Default strictness level (lenient vs strict parsing)
- Feature prioritization order
- Integration timeline with downstream consumers

---

## BOUNDARIES

### What OCTAVE-MCP IS
- A deterministic document format processor
- A loss accounting system for LLM communication
- A lenient-to-canonical normalizer
- A schema validation framework
- An audit trail generator for document transformations

### What OCTAVE-MCP IS NOT
- An LLM or reasoning engine (no inference)
- An agent orchestration system
- A database or persistence layer
- An identity/authentication system

---

## ASSUMPTIONS

### A1: Schema Validation Is Valuable
- **Confidence**: 85%
- **Impact**: HIGH
- **Validation**: Implement schema validation for 3 core schemas, measure adoption

### A2: Lenient Parsing Default Is Preferred
- **Confidence**: 90%
- **Impact**: HIGH
- **Validation**: User feedback (GH#56) indicates strong preference

### A3: 3-Tool Design Is Simpler Than 4
- **Confidence**: 75%
- **Impact**: MEDIUM
- **Validation**: Prototype consolidation, measure API complexity reduction

### A4: LLMs Comprehend OCTAVE Syntax
- **Confidence**: 92%
- **Impact**: CRITICAL
- **Validation**: Already validated - 90.7% zero-shot comprehension (see docs/research/)

### A5: Token Reduction Is Significant
- **Confidence**: 95%
- **Impact**: HIGH
- **Validation**: Already validated - 54-68% reduction vs JSON (see docs/research/)

### A6: RepairLog Structure Is Sufficient
- **Confidence**: 70%
- **Impact**: MEDIUM
- **Validation**: Stress test with bulk conversion use case

### A7: Parse Error Contract Can Be Formalized
- **Confidence**: 85%
- **Impact**: MEDIUM
- **Validation**: Define contract, implement, verify no regressions

---

## RISKS

### R1: Spec Claims ≠ Implementation
- **Description**: Architecture spec claims features not yet implemented (schema validation, compression tiers)
- **Mitigation**: I5 makes gaps visible; enforcement status tracked per immutable

### R2: Tool Consolidation Breaking Changes
- **Description**: 4→3 tool migration may break existing consumers
- **Mitigation**: Migration documentation, deprecation timeline, backward compatibility period

### R3: Lenient Parsing Edge Cases
- **Description**: Lenient parser may accept semantically invalid inputs
- **Mitigation**: I3 (Mirror Constraint) - errors rather than guesses; schema validation layer

---

## APPROVAL

**Status**: APPROVED

This North Star document represents the immutable requirements for OCTAVE-MCP.
All work must align with these requirements.

**Approved**: YES
**Approved By**: User
**Date**: 2025-12-28

---

## SUMMARY

| Immutable | Name | Status |
|-----------|------|--------|
| I1 | Syntactic Fidelity | ENFORCED |
| I2 | Deterministic Absence | PARTIAL |
| I3 | Mirror Constraint | PARTIAL |
| I4 | Transform Auditability | ENFORCED/BLOCKED |
| I5 | Schema Sovereignty | BLOCKED→PARTIAL |

**Total**: 5 immutables | 7 assumptions | 3 risks identified

---

*Document version: 1.0.0*
*Created: 2025-12-28*
