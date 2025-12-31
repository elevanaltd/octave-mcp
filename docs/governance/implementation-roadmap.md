# OCTAVE Implementation Roadmap

**Status**: Current implementation ~45% complete by specification coverage (data processing) + reference specs
**Last Updated**: 2025-12-22
**Target**: Production-ready schema validation, semantic routing, and agent architecture support

---

## Executive Summary

The OCTAVE MCP server has **strong foundations** (lexer, parser, emitter, canonicalization) but **critical schema validation and routing features are unimplemented**. This roadmap prioritizes the work needed to move from "basic OCTAVE processing" to "production-grade semantic control surface."

**Recent Updates (2025-12-24)**:
- ✅ **Gap 2 Complete**: Constraint chain evaluation implemented with 12 constraint types
- ✅ **New constraints**: RANGE, MAX_LENGTH, MIN_LENGTH, DATE, ISO8601 added
- ✅ **§ section markers**: Parser now preserves § section markers (Issue #31)
- ✅ **Output formats implemented**: JSON, YAML, Markdown export now functional (eject.py)
- ⚠️ **Placeholder documentation**: All deferred items now have honest docstrings referencing roadmap gaps
- 📊 **Test coverage**: Improved from 43% to 82% overall project coverage
- 🔒 **Deferred with rationale**: Items 4, 5, 6, 7, 9 explicitly documented as requiring Phase 1-4 infrastructure

### Current State by Component

| Component | Status | Coverage | Priority |
|-----------|--------|----------|----------|
| **Lexer & Parser** | ✅ IMPLEMENTED | 100% | — |
| **Canonicalization** | ✅ IMPLEMENTED | 100% | — |
| **Projector (4 modes)** | ✅ IMPLEMENTED | 100% | — |
| **Output Formats (JSON/YAML/MD)** | ✅ IMPLEMENTED | 100% | — |
| **Constraint Evaluation** | ✅ IMPLEMENTED | 91% | — |
| **Schema Validation** | ❌ PLANNED | 0% | **HIGH** |
| **Target Routing** | ❌ PLANNED | 0% | **HIGH** |
| **Compression Tiers** | ❌ PLANNED | 0% | MEDIUM |
| **Repair Logic** | ⚠️ DEFERRED | 0% | MEDIUM |
| **Error Messages** | ❌ PLANNED | 0% | LOW |
| **Agent Architecture** | 📖 REFERENCE | N/A | N/A |

### Reference Specifications (No Code Implementation Required)

| Spec | Status | Purpose |
|------|--------|---------|
| **octave-5-llm-agents** | ✅ REFERENCE | Agent cognitive architecture patterns |
| **octave-5-llm-rationale** | ✅ REFERENCE | Design rationale and decision records |

---

## HIGH PRIORITY: Schema Validation

### Gap 1: Holographic Pattern Parsing

**Current State**: Schema class exists (35 LOC) but raises `NotImplementedError`

**What's Missing**:
- Parse holographic container syntax: `KEY::["example"∧CONSTRAINT→§TARGET]`
- Extract and validate three components:
  - **EXAMPLE**: Concrete value (teaches format)
  - **CONSTRAINT**: Validation chain (∧-separated)
  - **TARGET**: Extraction destination (§-prefixed)

**Specification Reference**: `octave-5-llm-schema.oct.md` § 1

**Implementation Tasks**:
1. Add holographic pattern regex/parser to lexer
2. Create `HolographicPattern` dataclass with example/constraint/target fields
3. Update parser to recognize holographic syntax in L4 context
4. Add AST node type for holographic values
5. Unit tests: valid/invalid holographic patterns, edge cases

**Implementation File**: `src/octave_mcp/core/schema.py`

**Est. Complexity**: Medium (1-2 days)

---

### Gap 2: Constraint Chain Evaluation ✅ COMPLETE

**Status**: Implemented (PR #35)

**Implementation**: `src/octave_mcp/core/constraints.py` (282 LOC, 91% coverage)

**Available Constraints** (12 total):
| Constraint | Syntax | Description |
|------------|--------|-------------|
| `REQ` | `REQ` | Required field |
| `OPT` | `OPT` | Optional field |
| `CONST` | `CONST[value]` | Constant value (immutable) |
| `ENUM` | `ENUM[a,b,c]` | Enumerated values with prefix matching |
| `TYPE` | `TYPE(STRING\|NUMBER\|LIST\|BOOLEAN)` | Type check |
| `REGEX` | `REGEX[pattern]` | Pattern matching |
| `DIR` | `DIR` | Directory path |
| `APPEND_ONLY` | `APPEND_ONLY` | List append semantics |
| `RANGE` | `RANGE[min,max]` | Numeric bounds (inclusive) |
| `MAX_LENGTH` | `MAX_LENGTH[N]` | Max string/list length |
| `MIN_LENGTH` | `MIN_LENGTH[N]` | Min string/list length |
| `DATE` | `DATE` | Strict YYYY-MM-DD |
| `ISO8601` | `ISO8601` | Full ISO8601 datetime |

**Features Implemented**:
- ✅ Constraint chain parsing (`REQ∧ENUM[A,B]∧RANGE[1,10]`)
- ✅ Left-to-right, fail-fast evaluation
- ✅ Conflict detection: `REQ∧OPT`, `ENUM∧CONST`, `CONST∧CONST`
- ✅ Structured validation errors (code, path, constraint, expected, got)
- ✅ Parse-time validation (malformed params raise ValueError)
- ✅ Type safety (RANGE/NUMBER reject booleans, LENGTH only accepts str/list)

**Tests**: 112 passing (91% coverage)

---

### Gap 3: Target Routing & Validation

**Current State**: Target enum exists (`§SELF`, `§META`, `§INDEXER`, etc.) but no routing logic

**What's Missing**:
- Validate target syntax: `→§TARGET`, `→§TARGET∨§TARGET2`
- Target existence validation (builtin vs. custom)
- Multi-target broadcasting: `→§A∨§B∨§C`
- Block inheritance: Children inherit parent target unless overridden
- Routing context (where does extracted data go?)

**Available Builtin Targets** (from spec):
- `§SELF` - Current field
- `§META` - Document metadata
- `§INDEXER` - Primary index destination
- `§DECISION_LOG` - Decision audit trail
- `§RISK_LOG` - Risk tracking
- `§KNOWLEDGE_BASE` - External knowledge storage

**Specification Reference**: `octave-5-llm-schema.oct.md` § 3, § 4

**Implementation Tasks**:
1. Create `Target` dataclass with path, type, broadcast_flag
2. Create `TargetRouter` class with routing logic
3. Implement target registry (builtin + custom from POLICY.TARGETS)
4. Implement block inheritance (children inherit unless overridden)
5. Implement broadcast routing (broadcast to multiple targets if `∨`)
6. Track routing decisions in audit log
7. Unit tests: single targets, multi-targets, inheritance, overrides, missing targets

**Implementation File**: `src/octave_mcp/core/schema.py` (new TargetRouter class)

**Est. Complexity**: Medium (1-2 days)

---

### Gap 4: Block Inheritance Semantics

**Current State**: Block structure parsed but no semantic nesting support

**What's Missing**:
- Semantic block inheritance: `BLOCK[→§TARGET]:`
- Children inherit parent target unless they specify own: `CHILD[→§OTHER]:`
- Unbounded semantic nesting (implementation caps at 100 levels)
- Target override detection and enforcement

**Specification Reference**: `octave-5-llm-schema.oct.md` § 4

**Implementation Tasks**:
1. Add semantic nesting tracking to Block AST node
2. Implement inheritance resolver (parent target → child inheritance)
3. Detect and apply overrides
4. Depth limit enforcement (max 100 levels)
5. Unit tests: single level, multi-level, overrides, depth limits

**Implementation File**: `src/octave_mcp/core/schema.py`

**Est. Complexity**: Low (0.5 days) - depends on Gap 3

---

### Gap 5: Policy Block & Schema Validation

**Current State**: Policy block structure exists but not validated

**What's Missing**:
- Validate required POLICY fields: VERSION, UNKNOWN_FIELDS, TARGETS
- UNKNOWN_FIELDS policy enforcement: REJECT | IGNORE | WARN
- Schema versioning and compatibility rules
- Unknown field detection in strict mode

**Specification Reference**: `octave-5-llm-schema.oct.md` § 5

**Implementation Tasks**:
1. Create `PolicyBlock` dataclass with VERSION, UNKNOWN_FIELDS, TARGETS
2. Implement policy validator
3. Enforce UNKNOWN_FIELDS policy during document validation
4. Track unknown fields with policy action (reject/ignore/warn)
5. Unit tests: valid policies, missing fields, enforcement modes

**Implementation File**: `src/octave_mcp/core/validator.py`

**Est. Complexity**: Low (0.5 days)

---

## MEDIUM PRIORITY: Compression & Repair

### Gap 6: Compression Tier Logic

**Current State**: Tier parameter accepted in octave_validate but ignored

**What's Missing**:
- Implement compression rules for each tier:
  - **LOSSLESS** (100% fidelity): Preserve all prose, keep examples, document tradeoffs
  - **CONSERVATIVE** (85-90%): Drop stopwords, compress examples→inline, keep narratives
  - **AGGRESSIVE** (70%): Drop narratives→assertions, remove context, inline all
  - **ULTRA** (50%): Bare assertions, minimal lists, no examples, no prose
- Track loss profile (what was dropped)
- Apply forbidden rewrites rules (never introduce absolutes, collapse boundaries, strengthen claims, etc.)
- Metadata requirement: Include COMPRESSION_TIER in output META

**Specification Reference**: `octave-5-llm-data.oct.md` § 1b, § 6

**Implementation Tasks**:
1. Create `CompressionStrategy` class per tier with rule definitions
2. Implement compression rule engine (find/replace patterns)
3. Apply forbidden rewrites validation before compression
4. Generate loss profile tracking
5. Add COMPRESSION_TIER to output META
6. Unit tests: all tiers, edge cases, forbidden rewrite prevention

**Implementation File**: `src/octave_mcp/core/compressor.py` (new)

**Est. Complexity**: High (3-4 days)

---

### Gap 7: Repair Logic (fix=true)

**Current State**: Repair tiers defined but no actual repair logic

**What's Missing**:
- **TIER_REPAIR** (opt-in via `fix=true`):
  - Enum casefold: `"active"→ACTIVE` (only if unique match)
  - Type coercion: `"42"→42` (if schema says NUMBER)
  - Never add missing fields or invent targets
- Repair classification: NORMALIZATION (always) vs. REPAIR (opt-in) vs. FORBIDDEN (never)
- Repair log generation with before/after snippets

**Specification Reference**: `octave-mcp-architecture.oct.md` § 5

**Implementation Tasks**:
1. Implement enum casefold logic (case-insensitive exact match, reject if ambiguous)
2. Implement type coercion logic (string→number, string→boolean)
3. Create repair entry structure (rule_id, before, after, tier, safe, semantics_changed)
4. Integrate with validator: if `fix=true`, attempt repairs, log all changes
5. Validate that repairs don't introduce forbidden changes
6. Unit tests: casefold unique/ambiguous, type coercion, repair logging

**Implementation File**: `src/octave_mcp/core/repair.py`

**Est. Complexity**: Medium (1-2 days)

---

## LOW PRIORITY: Error Messaging & Observability

### Gap 8: Formatted Error Messages

**Current State**: ValidationError dataclass exists but no formatted output

**What's Missing**:
- Educational error messages (E001-E006 from spec)
- Schema-aware error formatting with EXPECTED vs. GOT
- Rationale explanations for each error class
- Error codes and severity levels (ERROR, WARNING, INFO)
- Multi-error handling (return first, provide fix guidance)

**Available Error Classes**:
- `E001` - Single colon assignment (use `::`)
- `E002` - Schema selector required
- `E003` - Cannot auto-fill missing required field
- `E004` - Cannot infer routing target
- `E005` - Tabs not allowed (use 2 spaces)
- `E006` - Ambiguous enum match

**Specification Reference**: `octave-mcp-architecture.oct.md` § 8

**Implementation Tasks**:
1. Create `ErrorFormatter` class with message templates
2. Implement each error class with rationale
3. Add severity classification (ERROR/WARNING/INFO)
4. Implement error ordering (parse first, constraints, targets)
5. Add multi-error retry guidance
6. Unit tests: all error types, formatting, severity

**Implementation File**: `src/octave_mcp/core/errors.py` (new)

**Est. Complexity**: Low (1 day)

---

### Gap 9: Retry Protocol

**Current State**: Single-pass validation (no retry loop)

**What's Missing**:
- Implement `MAX_RETRIES::3` loop
- Strategy: one error at a time, fix then retry
- Feedback loop: generate→validate→error→fix→retry
- Guidance for common errors (tabs, spaces, syntax)

**Specification Reference**: `octave-5-llm-execution.oct.md` § 4

**Implementation Tasks**:
1. Wrap validator in retry loop (max 3 retries)
2. On error, return guidance (not just error message)
3. On fix, re-validate incrementally
4. Return final error or success state
5. Unit tests: successful retry, max retries exceeded, guidance clarity

**Implementation File**: `src/octave_mcp/core/validator.py`

**Est. Complexity**: Low (0.5 days)

---

## Implementation Sequence (Recommended)

### Phase 1: Foundation (3-4 weeks)
1. **Gap 2**: Constraint chain evaluation (foundation for all schema validation)
2. **Gap 1**: Holographic pattern parsing (depends on Gap 2)
3. **Gap 3**: Target routing (depends on Gap 2)
4. **Unit test suite**: 100+ tests covering all three

### Phase 2: Structure (1-2 weeks)
5. **Gap 4**: Block inheritance (depends on Gap 3)
6. **Gap 5**: Policy blocks (depends on Gap 2)
7. **Integration tests**: Schema validation end-to-end

### Phase 3: Polish (1-2 weeks)
8. **Gap 8**: Error messages (depends on all validation)
9. **Gap 9**: Retry protocol (depends on Gap 8)
10. **Gap 7**: Repair logic (depends on error messages)

### Phase 4: Compression (2-3 weeks)
11. **Gap 6**: Compression tiers (orthogonal to validation)

---

## Testing Strategy

### Unit Tests (Per Gap)
- Each gap should have 20-40 unit tests
- Cover: happy path, edge cases, error cases, conflicts
- Mock external dependencies (schema registry, file system)

### Integration Tests
- End-to-end schema validation workflows
- Multi-component interactions (parsing → validation → routing)
- Real schema files from `/specs/` directory

### Property Tests (Optional)
- Constraint chain evaluation is deterministic
- Canonicalization is idempotent
- Repair logic never adds new fields
- Compression preserves structure

### Performance Tests
- Large documents (>10K fields)
- Deep nesting (100 levels)
- Complex constraint chains (10+ constraints)
- Compression tier selection on large documents

---

## Critical Success Factors

1. **Determinism**: All validation must be deterministic (same input→same output)
2. **Auditability**: All repairs/changes must be logged (no silent drift)
3. **No Inference**: Never guess targets, add fields, or infer schema (spec §5)
4. **Spec Fidelity**: Implementation must match specification exactly
5. **Test Coverage**: Aim for >85% coverage on core validation logic

---

## File Structure Reference

```
src/octave_mcp/core/
  ├── lexer.py           ✅ DONE (308 LOC) - tokenization
  ├── parser.py          ✅ DONE (389 LOC) - lenient parsing
  ├── emitter.py         ✅ DONE (140 LOC) - canonical output
  ├── ast_nodes.py       ✅ DONE (62 LOC) - AST definitions
  ├── projector.py       ✅ DONE (89 LOC) - 4 projection modes
  ├── validator.py       ⚠️ PARTIAL (134 LOC) - needs constraints + policy
  ├── schema.py          ❌ TODO (35 LOC) - needs holographic + routing
  ├── repair.py          ⚠️ PARTIAL (39 LOC) - needs repair logic
  ├── repair_log.py      ✅ DONE (47 LOC) - repair log structure
  ├── errors.py          ❌ TODO - error message formatting
  └── compressor.py      ❌ TODO - compression tiers

src/octave_mcp/mcp/
  ├── ingest.py          ✅ DONE (200 LOC) - tool frontend (tier param deferred)
  ├── eject.py           ✅ DONE (242 LOC) - projection + JSON/YAML/MD formats
  └── base_tool.py       ✅ DONE (153 LOC) - MCP base class

tests/unit/
  ├── test_lexer.py      ✅ DONE
  ├── test_parser.py     ✅ DONE
  ├── test_emitter.py    ✅ DONE
  ├── test_validator.py  ⚠️ SPARSE - needs expansion
  ├── test_schema.py     ❌ TODO
  ├── test_constraints.py ❌ TODO
  ├── test_repair.py     ⚠️ PARTIAL
  └── test_compression.py ❌ TODO
```

---

## Specification Dependencies

```
octave-5-llm-core ✅ IMPLEMENTED
  ├── octave-5-llm-data ❌ PLANNED (Gap 6)
  ├── octave-5-llm-schema ❌ PLANNED (Gaps 1-5)
  │   └── octave-5-llm-execution ⚠️ PARTIAL (Gaps 8-9)
  ├── octave-mcp-architecture ⚠️ PARTIAL (Gap 7)
  └── octave-5-llm-agents 📖 REFERENCE (no code implementation)
      └── octave-5-llm-rationale 📖 REFERENCE (design decisions)
```

### Specification Coverage Summary

**Implemented Specs** (Ready for production use):
- `octave-5-llm-core`: Full syntax, operators, envelope, types (IMPLEMENTED)
- `octave-mcp-architecture`: MCP tools, canonicalization, normalization rules (PARTIAL - core done, validation deferred)

**Planned Specs** (Require implementation):
- `octave-5-llm-schema`: Holographic patterns, constraint validation, target routing (PLANNED)
- `octave-5-llm-data`: Compression tiers LOSSLESS→ULTRA (PLANNED)
- `octave-5-llm-execution`: Advanced validation, error formatting, retry protocol (PARTIAL)

**Reference Specs** (No code implementation required - reference only):
- `octave-5-llm-agents`: Agent architecture patterns, cognitive foundations, validation requirements (REFERENCE)
- `octave-5-llm-rationale`: Design philosophy, syntax decisions, token economics (REFERENCE)

---

## Success Metrics

- [ ] All CRITICAL_GAPS resolved
- [ ] 100+ new unit tests added
- [ ] >85% code coverage on validation modules
- [ ] All spec sections testable against real documents
- [ ] Error messages Educational and actionable
- [ ] No regressions in existing (lexer/parser/emitter) tests

---

## References

- **Specification**: `/specs/octave-*.oct.md`
- **Implementation**: `/src/octave_mcp/`
- **Tests**: `/tests/unit/`
- **Architecture**: `octave-mcp-architecture.oct.md` § 7-13
