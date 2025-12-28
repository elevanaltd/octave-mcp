---
project: OCTAVE-MCP
scope: standalone
phase: D1_03
created: 2025-12-28
status: pending_approval
approved_by: null
approved_date: null
parent_north_star: null
debate_synthesis: octave-mcp-north-star-2025-12-28
---

# 000-OCTAVE-MCP-NORTH-STAR

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

**Rationale**: This survives any platform change because it is mathematical: `canon(x)` must be idempotent and bijective on semantic space. The distinction between TIER_NORMALIZATION (safe) and TIER_FORBIDDEN (never) creates a bright line that requires no inference.

**Evidence (Immutability Oath)**:
- Q1 "Willing to commit as IMMUTABLE?": YES - semantic preservation is the core value proposition
- Q2 "Would you change this for faster/cheaper delivery?": NO - violating this destroys trust in the system
- Q3 "Still true in 3 years?": YES - any document processing system must preserve meaning

**Current Enforcement**: ENFORCED
- W001-W005 correction codes logged in create/amend tools
- RepairLog tracks `semantics_changed: bool`
- TIER_FORBIDDEN documented in architecture spec

**What Breaks If Not Honored**: System becomes a liar. Repairs transform dissent into agreement, nuance into binary. Audit log shows "success" where truth was lost.

---

### I2: DETERMINISTIC ABSENCE

**Statement**: The system shall distinguish between "absent" (field not provided), "null" (explicitly empty), and "default" (schema-provided). Absence shall propagate as addressable state, never silently collapse to null or default.

**Rationale**: This prevents misinformation: downstream systems must know whether "tests section missing" means "no tests exist" vs "tests not checked." Technology-agnostic—any serialization format can distinguish these three states.

**Evidence (Immutability Oath)**:
- Q1: YES - data integrity requires knowing what we don't know
- Q2: NO - collapsing states introduces semantic drift
- Q3: YES - the distinction between absence and null is fundamental to computing

**Current Enforcement**: PARTIAL
- `null` and `[]` supported per core types (specs/octave-5-llm-core.oct.md)
- Absence-as-addressable-state not systematically enforced yet
- Tombstones for missing fields require compression tier infrastructure

**What Breaks If Not Honored**: Lossy compression becomes misinformation. Cannot distinguish "didn't check" from "isn't there."

---

### I3: MIRROR CONSTRAINT

**Statement**: The system shall reflect only what is present, creating nothing. When input is ambiguous or invalid, the system shall ERROR with educational context rather than guess. The only exception is explicit, logged, reversible normalization.

**Rationale**: Prevents "prompt injection by typo" attack surface. Platform-agnostic because it's a policy, not a mechanism. Any implementation that guesses violates the mirror.

**Evidence (Immutability Oath)**:
- Q1: YES - non-reasoning is the core differentiator from LLM-based processing
- Q2: NO - "helpful" guessing introduces security vulnerabilities and unpredictability
- Q3: YES - deterministic systems require deterministic input handling

**Current Enforcement**: PARTIAL
- TIER_FORBIDDEN documented (architecture spec §5)
- E001-E006 error messages exist with rationale
- Schema validation currently bypassed (`schema=None` allowed)
- Parse error contract not yet formalized

**What Breaks If Not Honored**: System trains users to be careless. Attack surface for malicious instructions executed because system "helpfully" inferred intent.

---

### I4: TRANSFORM AUDITABILITY

**Statement**: Every entropy-reducing transformation shall produce a recoverable audit record. The record shall include: rule_id, before, after, tier, and semantics_changed. Silent transformation is FORBIDDEN.

**Rationale**: If bits were lost, there must be a receipt. Wall's key insight operationalized: tombstones for compression are future work, but transform logging is implementable now.

**Evidence (Immutability Oath)**:
- Q1: YES - auditability is essential for trust in AI-assisted workflows
- Q2: NO - silent changes make debugging impossible and violate transparency
- Q3: YES - audit requirements only increase as AI systems proliferate

**Current Enforcement**: ENFORCED for normalization, BLOCKED for compression
- RepairEntry dataclass enforces required fields
- W002 (ASCII→Unicode) logged in create/amend tools
- Compression tier logging: NOT IMPLEMENTED (tier parameter ignored)

**What Breaks If Not Honored**: Compression engine becomes censorship engine. Validation passes while information is removed untraceably.

---

### I5: SCHEMA SOVEREIGNTY

**Statement**: A document processed without schema validation shall be marked as UNVALIDATED in its output metadata. Schema-validated documents shall record the schema name and version used. Schema bypass shall be visible, never silent.

**Rationale**: Acknowledges implementation gaps honestly. If you can't validate, you must say you can't. Traceability requirement is enforceable now even if full validation is future work.

**Evidence (Immutability Oath)**:
- Q1: YES - knowing validation state is essential for downstream trust decisions
- Q2: NO - silent bypass creates false confidence
- Q3: YES - schema versioning becomes more important as systems mature

**Current Enforcement**: BLOCKED → convertible to PARTIAL
- Currently: `schema=None` silently bypasses validation
- Required: output should include `validation_status: UNVALIDATED | VALIDATED(schema, version)`
- This is a minimal change that makes the gap visible

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
- Integration timeline with dependent systems (HestAI-MCP, debate-hall-mcp)

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
- An agent orchestration system (that's HestAI-MCP)
- A database or persistence layer
- A debate management system (that's debate-hall-mcp)
- An identity/authentication system

---

## ASSUMPTIONS REGISTER

### A1: Schema Validation Is Valuable
- **Confidence**: 85%
- **Impact**: HIGH
- **Validation Cost**: Moderate
- **Validation Plan**: Implement schema validation for 3 core schemas, measure adoption and error reduction
- **Owner**: implementation-lead
- **Validation Timing**: Before B1 (blocking)

### A2: Lenient Parsing Default Is Preferred
- **Confidence**: 90%
- **Impact**: HIGH
- **Validation Plan**: User feedback on GH#56 indicates strong preference for lenient-by-default
- **Owner**: technical-architect
- **Validation Timing**: Document only (validated by production feedback)

### A3: 3-Tool Design Is Simpler Than 4
- **Confidence**: 75%
- **Impact**: MEDIUM
- **Validation Plan**: Prototype consolidation, measure API complexity reduction
- **Owner**: technical-architect
- **Validation Timing**: During D2 (design validation)

### A4: LLMs Comprehend OCTAVE Syntax
- **Confidence**: 92%
- **Impact**: CRITICAL
- **Validation Plan**: Already validated - 90.7% zero-shot comprehension across Claude/GPT-4o/Gemini
- **Owner**: N/A
- **Validation Timing**: Validated (see docs/research/README.md)

### A5: Token Reduction Is Significant
- **Confidence**: 95%
- **Impact**: HIGH
- **Validation Plan**: Already validated - 32-46% of JSON tokens (54-68% reduction)
- **Owner**: N/A
- **Validation Timing**: Validated (see docs/research/README.md)

### A6: HestAI-MCP Needs Stable OCTAVE Tools
- **Confidence**: 80%
- **Impact**: HIGH
- **Validation Plan**: Coordinate with HestAI-MCP team on integration requirements
- **Owner**: holistic-orchestrator
- **Validation Timing**: Before B1 (integration contract needed)

### A7: RepairLog Structure Is Sufficient
- **Confidence**: 70%
- **Impact**: MEDIUM
- **Validation Plan**: Stress test with bulk conversion (GH#56 use case)
- **Owner**: implementation-lead
- **Validation Timing**: During B1

### A8: Parse Error Contract Can Be Formalized
- **Confidence**: 85%
- **Impact**: MEDIUM
- **Validation Plan**: Define contract, implement, verify no regressions
- **Owner**: implementation-lead
- **Validation Timing**: Before B2

---

## INTEGRATION REQUIREMENTS

### Upstream Dependencies
- Python 3.12+ runtime environment
- MCP protocol specification compliance

### Downstream Consumers
- **HestAI-MCP**: Needs stable octave tools for clock_out compression
- **debate-hall-mcp**: Declares OCTAVE binding for debate artifacts
- **Claude Code CLI**: Uses MCP tools for document processing

### Integration Contracts (to be defined)
- Tool API stability guarantees
- Schema versioning convention
- Error code stability

---

## RISK ASSESSMENT

### R1: Spec Claims ≠ Implementation
- **Description**: Architecture spec claims features not yet implemented (schema validation, compression tiers)
- **Mitigation**: I5 (Schema Sovereignty) makes gaps visible; enforcement status tracked per immutable
- **Owner**: critical-engineer

### R2: Tool Consolidation Breaking Changes
- **Description**: 4→3 tool migration may break existing consumers
- **Mitigation**: Migration documentation, deprecation timeline, backward compatibility period
- **Owner**: technical-architect

### R3: Lenient Parsing Edge Cases
- **Description**: Lenient parser may accept inputs that are semantically invalid
- **Mitigation**: I3 (Mirror Constraint) - errors rather than guesses; schema validation layer
- **Owner**: implementation-lead

---

## COMMITMENT CEREMONY

**Status**: PENDING_APPROVAL

> "These are your North Star. If you approve, I commit to defending them throughout this project. Future-you may want to change these, but present-you is making a commitment to future-you. Do you approve?"

**Approved**: [PENDING USER APPROVAL]
**Approved By**: [PENDING]

**Commitment Statement**:
This North Star document represents the immutable requirements for OCTAVE-MCP.
All work must align with these requirements. Any detected misalignment will trigger escalation.
Changes to immutables require formal amendment process via requirements-steward.

**Protection Clause**:
If ANY agent detects misalignment between work and North Star (phases B0-B4):
1. STOP current work immediately
2. CITE specific North Star requirement being violated
3. ESCALATE to requirements-steward for resolution
Options: CONFORM to North Star | USER AMENDS (rare) | ABANDON incompatible path

---

## EVIDENCE SUMMARY

### Constitutional Compliance
- **Total Immutables**: 5 (within 5-9 range)
- **Pressure Tested**: 5/5 passed Immutability Oath (Q1, Q2, Q3)
- **System-Agnostic**: 5/5 passed Technology Change Test
- **Assumptions Tracked**: 8 (6+ required)
- **Critical Assumptions**: 2 requiring pre-B1 validation (A1, A6)
- **Commitment Ceremony**: PENDING

### Quality Gates
- **YAML Front-Matter**: Present
- **Inheritance Chain**: N/A (standalone project)
- **Miller's Law**: 5 immutables
- **PROPHETIC_VIGILANCE**: 8 assumptions
- **Technology-Neutral**: All translated
- **Evidence Trail**: All Oath passages documented

### Readiness Status
- **D1_04 Gate**: Ready for requirements-steward validation
- **Critical Blockers**: None (awaiting user approval for Commitment Ceremony)

---

## DEBATE PROVENANCE

This North Star was synthesized through Wind/Wall/Door debate:

- **Thread ID**: octave-mcp-north-star-2025-12-28
- **Wind (PATHOS)**: edge-optimizer via gemini-3-pro-preview - 7 candidate provocations
- **Wall (ETHOS)**: critical-engineer via o3 - ALLOW:2, MODIFY:4, BLOCK:1 verdicts
- **Door (LOGOS)**: synthesizer via claude-opus-4-5-20251101 - Layered Fidelity synthesis

**Key Transformations**:
- Wind's C3 "Holographic Entanglement" → I5 "Schema Sovereignty" (narrowed to achievable)
- Wind's C5 "Cognitive Ergonomics" → Quality heuristic (not immutable)
- Wind's C7 "Anchor Immutability" → Out of scope (orchestration layer)

---

*Document version: 1.0.0*
*Generated by: holistic-orchestrator*
*Session: d3ab0393*
