# ADR-002: Schema Validation Using OCTAVE Holographic Patterns

## Status
ACCEPTED

## Context

The OCTAVE MCP server currently has a validation stub (`Validator(schema=None)`) that was identified as a P0 enforcement gap in the external assessment (.hestai/reports/archive/assessment-validation-gaps-historical.md). The system can parse and emit OCTAVE syntax, but cannot validate document structure against schema requirements.

### The Problem
Without schema validation:
- Agents can write syntactically valid OCTAVE that violates semantic constraints
- Required fields can be omitted without error
- Type mismatches go undetected
- Enum violations are not caught
- "BLOCK not warn" gates cannot actually block

### The Discovery
During P2.5 planning, we initially considered inventing a schema format. However, **OCTAVE v6.0.0 already defines a schema language** using the holographic pattern:

```octave
KEY::["example"∧CONSTRAINT→§TARGET]
     ^^^^^^^^ ^^^^^^^^^^ ^^^^^^^^^
     example  constraints target
```

From `src/octave_mcp/resources/specs/octave-schema-spec.oct.md` §1:
> HOLOGRAPHIC_PATTERN
> SYNTAX::KEY::["example"∧CONSTRAINT→§TARGET]
> COMPONENTS::[EXAMPLE,CONSTRAINT,TARGET][all_required_for_L4]

This means:
1. ✅ Schema format already specified (no invention needed)
2. ✅ Schema documents are valid OCTAVE (can use existing parser)
3. ✅ Agents already understand the syntax (it's OCTAVE)
4. ✅ Modular by design (any document type can have a schema)

## Decision

### Use OCTAVE Holographic Patterns for Schema Definitions

**Schema documents will be OCTAVE documents** using the holographic pattern from the OCTAVE v6.0.0 specification. No new schema format will be invented.

### Example Schema
```octave
===SESSION_LOG===
META:
  TYPE::PROTOCOL_DEFINITION
  VERSION::"1.0"
  STATUS::DRAFT

POLICY:
  VERSION::"1.0"
  UNKNOWN_FIELDS::REJECT
  TARGETS::[§INDEXER,§DECISION_LOG]

FIELDS:
  AGENT::["implementation-lead"∧REQ∧REGEX[^[a-z-]+$]→§INDEXER]
  PHASE::["B2"∧REQ∧ENUM[D0,D1,D2,D3,B0,B1,B2,B3]→§INDEXER]
  WORK::[["Fixed bugs"]∧REQ∧TYPE(LIST)→§SELF]
  OUTCOMES::["5 tests passing"∧REQ→§SELF]
===END===
```

### Constraint Types (from spec §2)
- `REQ` - Required field (must exist)
- `OPT` - Optional field (may be omitted)
- `CONST[value]` - Must equal exact value
- `REGEX[pattern]` - Must match regex pattern
- `ENUM[A,B,C]` - Must be one of enumerated values
- `TYPE(STRING|NUMBER|BOOLEAN|LIST)` - Must be specific type
- `DIR` - Must be valid directory path
- `APPEND_ONLY` - Can only add items, not remove

### Constraint Chaining (from spec §2)
Constraints are chained with `∧` and evaluated left-to-right with fail-fast:
- `REQ∧ENUM[A,B]` - Required AND must be A or B
- `REQ∧REGEX[^user_\w+$]` - Required AND matches pattern
- `OPT∧TYPE(LIST)` - Optional but if present must be list

### Target Extraction (from spec §3)
Targets specify where validated fields are routed:
- `§SELF` - Keep in document
- `§META` - Extract to metadata
- `§INDEXER` - Send to indexing system
- `§DECISION_LOG` - Route to decision log
- `§./relative/path` - Write to file
- `§A∨§B∨§C` - Broadcast to multiple targets

### Block Inheritance (from spec §4)
```octave
RISKS[→§RISK_LOG]:
  CRITICAL::["auth_bypass"∧REQ]      # Inherits §RISK_LOG target
  WARNING::["rate_limit"∧OPT→§SELF]  # Overrides to §SELF
```

## Architecture

### Directory Structure
```
src/octave_mcp/resources/specs/schemas/              ← Schema definitions (pure OCTAVE)
├── builtin/               ← System schemas (always available)
│   ├── META.oct.md
│   ├── SESSION_LOG.oct.md
│   └── AGENT_OUTPUT.oct.md
├── agents/                ← Agent-specific output schemas
│   ├── implementation-lead/
│   │   └── OUTPUT.oct.md
│   └── critical-engineer/
│       └── OUTPUT.oct.md
└── skills/                ← Skill-specific schemas
    └── BUILD_EXECUTION/
        ├── INPUT.oct.md
        └── OUTPUT.oct.md
```

### Implementation Components

#### 1. Schema Extractor (NEW)
```python
# src/octave_mcp/core/schema_extractor.py

def extract_schema_rules(doc: dict) -> Schema:
    """
    Parse FIELDS block, extract holographic patterns.

    Example input:
        AGENT::["implementation-lead"∧REQ∧REGEX[^[a-z-]+$]→§INDEXER]

    Extraction:
        - Key: "AGENT"
        - Example: "implementation-lead"
        - Constraints: [REQ, REGEX[^[a-z-]+$]]
        - Target: §INDEXER
    """
    # 1. Parse FIELDS block from doc
    # 2. For each field, split value on ∧ to get constraint chain
    # 3. Parse each constraint type (REQ, ENUM[...], REGEX[...], etc.)
    # 4. Extract target (§ prefixed)
    # 5. Build Schema object with validation rules
```

#### 2. Schema Loader (NEW)
```python
# src/octave_mcp/core/schema_loader.py

def load_schema(schema_name: str) -> Schema:
    """
    Load schema from src/octave_mcp/resources/specs/schemas/{schema_name}.oct.md

    Search order:
    1. src/octave_mcp/resources/specs/schemas/builtin/{schema_name}.oct.md
    2. src/octave_mcp/resources/specs/schemas/agents/{schema_name}.oct.md
    3. src/octave_mcp/resources/specs/schemas/skills/{schema_name}.oct.md
    4. Custom paths from config
    """
    # 1. Find schema file in search paths
    # 2. Read file content
    # 3. Parse as OCTAVE (using existing parser!)
    # 4. Extract schema rules via schema_extractor
    # 5. Return Schema object
```

#### 3. Validator Enhancement (UPDATE)
```python
# src/octave_mcp/core/validator.py (enhance existing)

class Validator:
    def __init__(self, schema: Schema | None):
        self.schema = schema  # No longer always None!

    def validate(self, doc: dict, strict: bool) -> list[ValidationError]:
        """
        Validate document against schema rules.

        For each field in schema.fields:
        - REQ: Check field exists in doc
        - ENUM[values]: Check doc[field] in values
        - REGEX[pattern]: Check doc[field] matches pattern
        - TYPE(type): Check isinstance(doc[field], type)
        - CONST[value]: Check doc[field] == value

        Constraint chain evaluation: fail-fast on first violation
        """
        errors = []

        if not self.schema:
            return errors  # No schema, no validation

        for field_name, field_schema in self.schema.fields.items():
            # Evaluate constraint chain left-to-right
            for constraint in field_schema.constraints:
                if not self._check_constraint(doc, field_name, constraint):
                    errors.append(ValidationError(...))
                    break  # Fail-fast

        return errors
```

#### 4. `octave_validate` Tool Wiring (UPDATE)
```python
# src/octave_mcp/mcp/validate.py (update existing)

async def execute(self, **kwargs: Any) -> dict[str, Any]:
    # ... existing code ...

    schema_name = params["schema"]

    # BEFORE (P0 bug):
    # validator = Validator(schema=None)  # Stub

    # AFTER (P2.5 fix):
    try:
        schema = load_schema(schema_name)
        validator = Validator(schema=schema)
    except SchemaNotFoundError:
        result["warnings"].append({
            "code": "W001",
            "message": f"Schema '{schema_name}' not found, skipping validation"
        })
        validator = Validator(schema=None)

    # Now validation actually works!
    validation_errors = validator.validate(doc, strict=True)

    if validation_errors:
        # BLOCKING on errors (not just warnings)
        result["warnings"].extend([...])
```

## Implementation Plan (TDD)

### Phase 1: Schema Parsing (~2 hours)
```python
# RED: Test parsing FIELDS block from schema doc
def test_extract_fields_block():
    schema_doc = """
    ===TEST_SCHEMA===
    FIELDS:
      NAME::["example"∧REQ→§SELF]
    ===END===
    """
    doc = parse(schema_doc)
    fields = extract_fields_block(doc)
    assert "NAME" in fields

# GREEN: Implement extract_fields_block()

# RED: Test extracting holographic pattern
def test_extract_holographic_pattern():
    field_value = ["example"∧REQ→§SELF]
    pattern = extract_holographic_pattern(field_value)
    assert pattern.example == "example"
    assert REQ in pattern.constraints
    assert pattern.target == "§SELF"

# GREEN: Implement holographic pattern parser

# RED: Test constraint parsing
def test_parse_req_constraint():
    assert parse_constraint("REQ") == RequiredConstraint()

def test_parse_enum_constraint():
    constraint = parse_constraint("ENUM[A,B,C]")
    assert constraint.values == ["A", "B", "C"]

def test_parse_regex_constraint():
    constraint = parse_constraint("REGEX[^[a-z]+$]")
    assert constraint.pattern == "^[a-z]+$"

# GREEN: Implement constraint parsers

# REFACTOR: Clean up parser structure
```

### Phase 2: Validation Rules (~2 hours)
```python
# RED: Test REQ constraint blocks on missing field
def test_required_field_missing():
    schema = Schema(fields={"NAME": FieldSchema(constraints=[REQ])})
    doc = {}  # Missing NAME
    errors = validator.validate(doc, schema)
    assert any("NAME" in err.message for err in errors)

# GREEN: Implement required field validation

# RED: Test ENUM constraint blocks on invalid value
def test_enum_constraint_invalid():
    schema = Schema(fields={
        "STATUS": FieldSchema(constraints=[ENUM(["A", "B"])])
    })
    doc = {"STATUS": "C"}  # Not in enum
    errors = validator.validate(doc, schema)
    assert any("STATUS" in err.message for err in errors)

# GREEN: Implement enum validation

# RED: Test REGEX constraint validates pattern
def test_regex_constraint_invalid():
    schema = Schema(fields={
        "ID": FieldSchema(constraints=[REGEX("^user_\\w+$")])
    })
    doc = {"ID": "invalid"}  # Doesn't match pattern
    errors = validator.validate(doc, schema)
    assert any("ID" in err.message for err in errors)

# GREEN: Implement regex validation

# RED: Test constraint chaining with fail-fast
def test_constraint_chain_fail_fast():
    schema = Schema(fields={
        "EMAIL": FieldSchema(constraints=[REQ, REGEX("^.+@.+$")])
    })
    doc = {}  # Missing EMAIL
    errors = validator.validate(doc, schema)
    # Should fail on REQ, not reach REGEX
    assert len(errors) == 1
    assert "required" in errors[0].message.lower()

# GREEN: Implement constraint chaining

# REFACTOR: DRY constraint checkers
```

### Phase 3: Schema Loading (~1 hour)
```python
# RED: Test loading schema from file
def test_load_schema_from_builtin():
    schema = load_schema("SESSION_LOG")
    assert schema.name == "SESSION_LOG"
    assert "AGENT" in schema.fields

# GREEN: Implement load_schema()

# RED: Test schema not found error
def test_load_schema_not_found():
    with pytest.raises(SchemaNotFoundError):
        load_schema("NONEXISTENT")

# GREEN: Handle missing schema gracefully

# RED: Test schema search order
def test_schema_search_order():
    # Custom schemas override builtins
    create_custom_schema("src/octave_mcp/resources/specs/schemas/agents/TEST.oct.md")
    schema = load_schema("TEST")
    assert schema.version == "custom"

# GREEN: Implement search path logic

# REFACTOR: Add schema caching
```

### Phase 4: Wire into Ingest (~1 hour)
```python
# RED: Test ingest with schema validation
def test_ingest_with_schema():
    content = """
    ===SESSION_LOG===
    META:
      TYPE::"SESSION_LOG"
    AGENT::"implementation-lead"
    ===END===
    """
    result = ingest(content, schema="SESSION_LOG")
    # Missing PHASE, WORK, OUTCOMES (required fields)
    assert len(result["warnings"]) > 0
    assert any("PHASE" in w["message"] for w in result["warnings"])

# GREEN: Wire schema loading into IngestTool

# RED: Test validation BLOCKS on errors
def test_validation_blocking():
    content = """
    ===SESSION_LOG===
    AGENT::"INVALID_FORMAT"  # Doesn't match REGEX
    ===END===
    """
    result = ingest(content, schema="SESSION_LOG", strict=True)
    assert result["warnings"]  # Should have errors
    # In future: should reject document entirely in strict mode

# GREEN: Make validation blocking

# REFACTOR: Clean up error messages
```

## Consequences

### Positive
1. **No New Format**: Schemas are OCTAVE documents, using existing parser
2. **Self-Documenting**: Holographic pattern includes example values
3. **Modular by Design**: Any agent/skill can define schemas
4. **Already Specified**: Using OCTAVE v6.0.0 spec (§1-§4 of schema spec)
5. **Agent-Friendly**: Agents already know OCTAVE syntax
6. **Incremental Adoption**: Can add schemas gradually
7. **Type Safety**: Validation enforces structure at runtime
8. **Discoverable**: Schemas live in src/octave_mcp/resources/specs/schemas/ directory

### Negative
1. **Parsing Complexity**: Must parse nested holographic patterns (but spec defines this)
2. **Constraint Evaluation**: Need robust constraint checker (but bounded set of types)
3. **Error Messages**: Must provide clear feedback on validation failures
4. **Migration**: Existing code assumes schema=None (but migration is clean)

### Neutral
1. **Schema Complexity**: Holographic pattern is powerful but requires learning
   - Mitigation: Examples in schemas/ directory, generated templates
2. **Target Routing**: §TARGET extraction not implemented yet
   - Mitigation: Phase 1 focuses on validation, routing deferred to P3

## Validation Criteria

### Tests Required
```python
# Unit tests
tests/unit/test_schema_extractor.py      (~150 lines)
tests/unit/test_constraint_validation.py (~200 lines)
tests/unit/test_schema_loader.py         (~100 lines)

# Integration tests
tests/integration/test_schema_validation.py (~150 lines)
tests/integration/test_ingest_with_schema.py (~100 lines)

# E2E tests
tests/e2e/test_schema_enforcement.py (~50 lines)
```

### Property-Based Tests
```python
def test_schema_validation_idempotent():
    """Valid doc validates successfully multiple times."""
    assert validate(valid_doc, schema) == []
    assert validate(valid_doc, schema) == []

def test_schema_round_trip():
    """Schema doc can be parsed as OCTAVE."""
    schema_doc = load_schema_doc("SESSION_LOG")
    parsed = parse(schema_doc)
    emitted = emit(parsed)
    reparsed = parse(emitted)
    assert parsed == reparsed

def test_constraint_chain_fail_fast():
    """First constraint failure stops evaluation."""
    # REQ fails, REGEX never evaluated
    errors = validate({"STATUS": None}, schema_with_req_and_regex)
    assert len(errors) == 1
    assert "required" in errors[0].message.lower()
```

## Files to Create

### Schema Definitions (OCTAVE format)
```
src/octave_mcp/resources/specs/schemas/builtin/SESSION_LOG.oct.md    (~40 lines)
src/octave_mcp/resources/specs/schemas/builtin/META.oct.md           (~25 lines)
src/octave_mcp/resources/specs/schemas/builtin/AGENT_OUTPUT.oct.md   (~30 lines)
```

### Implementation
```
src/octave_mcp/core/schema_extractor.py     (~150 lines)
src/octave_mcp/core/schema_loader.py        (~100 lines)
src/octave_mcp/core/validator.py            (~80 lines UPDATE)
src/octave_mcp/mcp/validate.py              (~20 lines UPDATE)
```

### Tests
```
tests/unit/test_schema_extractor.py         (~150 lines)
tests/unit/test_constraint_validation.py    (~200 lines)
tests/unit/test_schema_loader.py            (~100 lines)
tests/integration/test_schema_validation.py (~150 lines)
tests/e2e/test_schema_enforcement.py        (~50 lines)
```

## Success Criteria

✅ `octave_validate(content, schema="SESSION_LOG")` loads schema from file
✅ Validation BLOCKS on missing required fields (REQ constraint)
✅ Validation BLOCKS on enum violations (ENUM[A,B] constraint)
✅ Validation BLOCKS on regex mismatches (REGEX[pattern] constraint)
✅ Validation BLOCKS on type mismatches (TYPE(LIST) constraint)
✅ Constraint chains evaluate left-to-right with fail-fast
✅ Templates can be generated from schema definitions (future)
✅ Custom schemas loadable from agents/skills/ directories
✅ All tests pass with TDD discipline (RED→GREEN→REFACTOR)

## References

### Specifications
- `src/octave_mcp/resources/specs/octave-schema-spec.oct.md` - Holographic pattern definition (§1-§7)
- `src/octave_mcp/resources/specs/octave-core-spec.oct.md` - Core OCTAVE syntax (§1-§7)

### Related ADRs
- ADR-001: Configurability and Modularity Architecture

### External Assessment
- `.hestai/reports/archive/assessment-validation-gaps-historical.md` - Identified validation stub as P0 gap

## Alignment with OCTAVE Specification

This ADR implements the schema validation system defined in OCTAVE v6.0.0 specification:

**From octave-schema-spec.oct.md §1**:
> HOLOGRAPHIC_PATTERN
> SYNTAX::KEY::["example"∧CONSTRAINT→§TARGET]
> COMPONENTS::[EXAMPLE,CONSTRAINT,TARGET][all_required_for_L4]

**From octave-schema-spec.oct.md §2**:
> CONSTRAINTS
> AVAILABLE::[REQ,OPT,CONST,REGEX,ENUM,TYPE,DIR,APPEND_ONLY]
> CHAIN::constraint∧constraint∧constraint[left_to_right]
> EVALUATION::fail_fast[stop_on_first_failure]

**From octave-schema-spec.oct.md §6**:
> SCHEMA_SKELETON
> TEMPLATE: [Minimal valid schema document structure provided]

This ADR translates the specification into a concrete implementation while maintaining 100% fidelity to the defined holographic pattern syntax.

## Recommendation Summary

**ACCEPTED**: Use OCTAVE holographic patterns for schema definitions.

**Rationale**:
- Format already specified in OCTAVE v6.0.0
- No new syntax to invent or learn
- Self-documenting with example values
- Modular and extensible by design
- Agents already understand OCTAVE

**Next Steps**:
1. Implement schema_extractor (parse holographic patterns)
2. Implement schema_loader (load from src/octave_mcp/resources/specs/schemas/)
3. Enhance validator (add constraint checking)
4. Wire into ingest tool
5. Create builtin schemas (SESSION_LOG, META, AGENT_OUTPUT)
6. Write comprehensive tests with TDD

**Estimated Effort**: ~6 hours with TDD discipline

This approach makes schema validation a first-class feature of OCTAVE MCP while staying 100% true to the OCTAVE v6.0.0 specification.
