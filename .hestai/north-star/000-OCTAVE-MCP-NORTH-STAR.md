---
project: OCTAVE-MCP
scope: system
phase: D1_03
version: 1.0.2
created: 2025-12-28
status: approved
approved_by: user
approved_date: 2025-12-28
updated: 2026-02-16
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

### Three-Layer Model: Normalizing DSL / Preserving Container / Explicit Literal Zones

The OCTAVE format operates in three distinct fidelity zones:

1. **Normalizing DSL** (core OCTAVE syntax)
   - Keys, values, operators, blocks follow normalization rules
   - ASCII↔Unicode operator conversion (logged via I4)
   - Whitespace standardization (2-space indent)
   - Subject to I1 syntactic fidelity (semantics preserved)

2. **Preserving Container** (YAML frontmatter in hybrid .oct.md files)
   - Container structure preserved byte-for-byte
   - No normalization applied to YAML content
   - Affects 100+ skills/patterns in .hestai-sys/library/
   - Honors I3 (reflects what is present without transformation)

3. **Explicit Literal Zones** (markdown fenced code blocks: \`\`\`)
   - First-class syntax for "do not touch" content
   - Exact formatting preserved (spaces, tabs, indentation, newlines)
   - Language tags preserved (\`\`\`python, \`\`\`json, etc.)
   - Empty blocks distinct from absent (I2)
   - Nested fences MUST error, not guess (I3)
   - Documents containing literal zones receive validation_status markers (I5)

**Philosophical Alignment**: Literal zones do not violate I1 (Syntactic Fidelity) - they fulfill it. The semantic intent of a literal zone is "preserve exactly as written." Normalizing its content would alter semantics. The exemption from normalization preserves the meaning.

---

## IMMUTABLE REQUIREMENTS

### I1: SYNTACTIC FIDELITY

**Statement**: Normalization shall alter syntax (representation) but never semantics (meaning). Every transformation preserving meaning is logged; every transformation altering meaning is FORBIDDEN.

**Rationale**: This is mathematical: `canon(x)` must be idempotent and bijective on semantic space. The distinction between TIER_NORMALIZATION (safe) and TIER_FORBIDDEN (never) creates a bright line that requires no inference.

**Interpretation for Literal Zones (Issue #235)**:
- Literal zones (markdown fenced code blocks) are EXEMPT from normalization
- This exemption does not violate I1 - it fulfills it
- The semantic intent of `"""python\n  code\n"""` is "preserve this exactly"
- Normalizing whitespace inside a literal zone would ALTER semantics
- The exemption preserves the meaning of "untouchable content"
- Transformation log must record: "literal_zone: preserved (no normalization applied)"

**Pressure Test**:
- Would you change this for faster/cheaper delivery? NO - violating this destroys trust
- Still true in 3 years with different technology? YES - any document processor must preserve meaning

**Current Enforcement**: ENFORCED
- W001-W005 correction codes logged
- RepairLog tracks `semantics_changed: bool`
- TIER_FORBIDDEN documented in architecture spec
- Literal zone exemption: planned for v1.3.0

**What Breaks If Not Honored**: System becomes a liar. Repairs transform dissent into agreement, nuance into binary. Code blocks lose exact formatting required for execution.

---

### I2: DETERMINISTIC ABSENCE

**Statement**: The system shall distinguish between "absent" (field not provided), "null" (explicitly empty), and "default" (schema-provided). Absence shall propagate as addressable state, never silently collapse to null or default.

**Rationale**: Downstream systems must know whether "tests section missing" means "no tests exist" vs "tests not checked." Any serialization format can distinguish these three states.

**Interpretation for Literal Zones (Issue #235)**:
- Empty code block `"""\n"""` is DISTINCT from absent (no code block)
- Parser must distinguish: no_literal_zone ≠ empty_literal_zone ≠ whitespace_only_literal_zone
- Empty literal zones have semantic meaning (placeholder, intentional blank)
- Collapsing empty to absent loses author intent

**Pressure Test**:
- Would you change this for faster/cheaper delivery? NO - collapsing states introduces semantic drift
- Still true in 3 years? YES - the distinction between absence and null is fundamental

**Current Enforcement**: PARTIAL → ENFORCED (for absent vs null)
- `Absent` sentinel type distinguishes from `null`
- Emitter skips Absent fields, emits null as `KEY::null`
- "default" state deferred to schema validation (P2.5)
- Literal zone absence handling: planned for v1.3.0

**What Breaks If Not Honored**: Lossy compression becomes misinformation. Cannot distinguish "didn't check" from "isn't there." Empty code blocks lose intentional placeholder semantics.

---

### I3: MIRROR CONSTRAINT

**Statement**: The system shall reflect only what is present, creating nothing. When input is ambiguous or invalid, the system shall ERROR with educational context rather than guess. The only exception is explicit, logged, reversible normalization.

**Rationale**: Non-reasoning is the core differentiator from LLM-based processing. "Helpful" guessing introduces security vulnerabilities and unpredictability.

**Interpretation for Literal Zones (Issue #235)**:
- Nested fences (``` inside ```) MUST error with clear message
- Parser MUST NOT guess which fence closes which block
- Error message: "E007: Nested literal zones detected. Escape inner fences or restructure content."
- No heuristics, no inference, no "helpful" fence matching
- Ambiguous fence boundaries = STOP, CITE, ESCALATE
- This preserves I3: reflect only what is unambiguous, error on ambiguity

**Pressure Test**:
- Would you change this for faster/cheaper delivery? NO - guessing creates attack surface
- Still true in 3 years? YES - deterministic systems require deterministic input handling

**Current Enforcement**: PARTIAL → ENFORCED
- TIER_FORBIDDEN documented
- E001-E006 error messages exist with rationale
- `validation_status` is always present in tool outputs (VISIBLE bypass surface)
- UNVALIDATED only when schema was not applied / not found; VALIDATED/INVALID when schema is available and checked
- Nested fence detection: planned for v1.3.0 with E007 error code

**What Breaks If Not Honored**: Attack surface for malicious instructions executed because system "helpfully" inferred intent. Nested fences create parsing ambiguity that enables injection attacks.

---

### I4: TRANSFORM AUDITABILITY

**Statement**: Every entropy-reducing transformation shall produce a recoverable audit record. The record shall include: rule_id, before, after, tier, and semantics_changed. Silent transformation is FORBIDDEN.

**Rationale**: If bits were lost, there must be a receipt. Tombstones for compression are future work, but transform logging is implementable now.

**Interpretation for Literal Zones (Issue #235)**:
- Literal zone preservation must be logged: "literal_zone: preserved (no normalization)"
- Container preservation must be logged: "yaml_frontmatter: preserved byte-for-byte"
- Transformation log distinguishes three zones: DSL (normalized), Container (preserved), Literal (preserved)
- RepairLog entries for documents with literal zones: `contains_literal_zones: true`
- Audit trail enables debugging: "why wasn't this normalized?" → "literal zone exemption applied"

**Pressure Test**:
- Would you change this for faster/cheaper delivery? NO - silent changes make debugging impossible
- Still true in 3 years? YES - audit requirements only increase as AI systems proliferate

**Current Enforcement**: ENFORCED for normalization, BLOCKED for compression
- RepairEntry dataclass enforces required fields
- W002 (ASCII→Unicode) logged
- Compression tier logging: NOT IMPLEMENTED
- Literal zone preservation logging: planned for v1.3.0

**What Breaks If Not Honored**: Compression engine becomes censorship engine. Validation passes while information is removed untraceably. Literal zone preservation becomes invisible, preventing diagnosis of formatting issues.

---

### I5: SCHEMA SOVEREIGNTY

**Statement**: A document processed without schema validation shall be marked as UNVALIDATED in its output metadata. Schema-validated documents shall record the schema name and version used. Schema bypass shall be visible, never silent.

**Rationale**: If you can't validate, you must say you can't. Traceability requirement is enforceable now even if full validation is future work.

**Interpretation for Literal Zones (Issue #235)**:
- Documents containing literal zones MUST include `contains_literal_zones: true` in validation_status
- Validation status must indicate if literal zone syntax was checked: `literal_zones_validated: true|false`
- Partial validation scenario: "DSL validated, literal zones unchecked" = UNVALIDATED
- Validation gap visibility: "We checked OCTAVE syntax but not code block internals"
- This prevents validation theater: can't claim VALIDATED if portions were skipped

**Pressure Test**:
- Would you change this for faster/cheaper delivery? NO - silent bypass creates false confidence
- Still true in 3 years? YES - schema versioning becomes more important as systems mature

**Current Enforcement**: PARTIAL (was BLOCKED)
- All tools include `validation_status` in output (VALIDATED | UNVALIDATED | INVALID)
- Schema bypass is visible, never silent (UNVALIDATED is an explicit state)
- When a schema is available and applied, tools record schema name/version and return VALIDATED/INVALID
- Holographic principle note: documents may declare their own validation law via META.CONTRACT / META.GRAMMAR; enforcement is planned, not fully implemented in v0.6.0
- Literal zone validation status: planned for v1.3.0

**What Breaks If Not Honored**: False sense of safety. Schema claims not enforced. Semantic drift through schema version mismatch. Literal zones become validation blind spots.

---

## CONSTRAINED VARIABLES

### Immutable (5)
- I1: Syntactic Fidelity
- I2: Deterministic Absence
- I3: Mirror Constraint
- I4: Transform Auditability
- I5: Schema Sovereignty

### Flexible (implementation decisions)
- Number of MCP tools (currently 3: octave_validate, octave_write, octave_eject)
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

### A3: 3-Tool Surface Is Stable
- **Confidence**: 95%
- **Impact**: MEDIUM
- **Validation**: Implemented (v0.6.x). Keep tool count stable; treat any new tool as a breaking design decision requiring explicit justification + migration story

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

### A8: Nested Fence Detection Is Tractable
- **Confidence**: 80%
- **Impact**: HIGH
- **Validation**: Implement nested fence detection in lexer phase with E007 error. Test with pathological inputs (deeply nested markdown, escaped backticks, mixed fence lengths).
- **Rationale**: Issue #235 requires parser to detect ``` inside ``` and error rather than guess. Lexer-level detection is more reliable than parser-level heuristics.

### A9: Migration to Literal Zones Is Non-Breaking
- **Confidence**: 75%
- **Impact**: HIGH
- **Validation**: Audit existing corpus for documents that might be misinterpreted as containing literal zones. Verify backward compatibility with existing .oct.md files.
- **Rationale**: Container preservation (YAML frontmatter) already exists. Literal zones add new syntax. Existing documents without ``` should parse identically.

### A10: Language Tags Are Preservation Metadata, Not Semantic
- **Confidence**: 70%
- **Impact**: MEDIUM
- **Validation**: Implement language tag preservation (\`\`\`python, \`\`\`json) without attempting syntax-specific validation. Language tags inform downstream processors but are not validated by OCTAVE parser.
- **Rationale**: Validating every possible language syntax (Python, JSON, YAML, etc.) is scope creep. OCTAVE preserves the tag and content; downstream tools interpret.

---

## RISKS

### R1: Spec Claims ≠ Implementation
- **Description**: Architecture spec claims features not yet implemented (schema validation, compression tiers)
- **Mitigation**: I5 makes gaps visible; enforcement status tracked per immutable

### R2: Validator Drift (Multiple Validators, Divergent Rules)
- **Description**: If repo tooling and runtime validation use different rule engines, documents can "pass" one validator and fail another
- **Mitigation**: Prefer core parser/validator as single source of truth; any extra lint rules must be explicitly labeled as style guidance, not validity

### R3: Lenient Parsing Edge Cases
- **Description**: Lenient parser may accept semantically invalid inputs
- **Mitigation**: I3 (Mirror Constraint) - errors rather than guesses; schema validation layer

---

## COMMITMENT CEREMONY
**Approved**: 2025-12-28
**Approved By**: User
This North Star document represents the immutable requirements for OCTAVE-MCP.
All work must align with these requirements.
Protection clause: if any work contradicts an immutable, STOP, CITE the violating I#, and ESCALATE.

## APPROVAL
**Status**: APPROVED

---

## EVIDENCE SUMMARY
- Total Immutables: 5 (within 5-9 range)
- Assumptions Tracked: 10 (A1-A7 original, A8-A10 for Issue #235 literal zones)
- Commitment Ceremony: Completed (2025-12-28), Updated (2026-02-16 for Issue #235)
- Current validator surface: core parser + core validator used by CLI/MCP tools; schema enforcement is partial and explicitly surfaced via validation_status
- Literal zones: planned for v1.3.0 with E007 error code, preservation logging, and validation status tracking

## SUMMARY
| Immutable | Name | Status |
|-----------|------|--------|
| I1 | Syntactic Fidelity | ENFORCED |
| I2 | Deterministic Absence | ENFORCED (absent≠null) |
| I3 | Mirror Constraint | ENFORCED |
| I4 | Transform Auditability | ENFORCED |
| I5 | Schema Sovereignty | PARTIAL |

**Total**: 5 immutables | 10 assumptions | 3 risks identified

**Update 2025-12-29**: I2, I3, I5 moved from PARTIAL/BLOCKED to ENFORCED/PARTIAL via commits implementing `Absent` sentinel, `validation_status` field, and visible schema bypass.

**Update 2026-02-16**: Added Issue #235 literal zones interpretation across all immutables (I1-I5). Added three new assumptions (A8-A10) for nested fence detection, migration safety, and language tag handling. Documented three-layer model: Normalizing DSL / Preserving Container / Explicit Literal Zones. No immutables changed; interpretations clarify how literal zones fulfill existing requirements.

---

*Document version: 1.0.2*
*Created: 2025-12-28*
*Updated: 2026-02-16 (Issue #235 literal zones)*
