# OCTAVE Quick Start Guide

OCTAVE is a structured notation format optimized for LLM communication and agent-to-agent data exchange. It provides predictable parsing, semantic compression, and machine validation.

## When to Use OCTAVE

- Agent-to-agent communication requiring structured data
- Configuration and state documents that need validation
- Knowledge compression for context window efficiency
- Audit trails and decision logs requiring machine parsing
- Schema definitions for document types

## When NOT to Use OCTAVE

- Simple tasks with minimal structured data (use prose)
- Frequent human editing without tooling support
- One-off documents with a single reader (prose is fine)
- Environments requiring strict JSON/YAML interoperability

---

## DATA Mode Example

DATA mode is for instances: sessions, configs, runtime state. Uses simple `KEY::value` assignments.

```octave
===MY_SESSION===
META:
  TYPE::SESSION_LOG
  VERSION::"1.0"

---

SESSION:
  ID::sess_abc123
  STATUS::ACTIVE
  PHASE::B2
  STARTED::"2026-01-02T10:00:00Z"

CONTEXT:
  BRANCH::"feature/auth-flow"
  TAGS::[api,auth,security]
  BLOCKERS::[]

PROGRESS:
  COMPLETED::[design,scaffolding]
  CURRENT::implementation
  NEXT::[BUILD,TEST,DEPLOY]

METRICS:
  TESTS_PASSED::12
  TESTS_FAILED::0
  COVERAGE::"87%"
  LINT::ok

===END===
```

**Key Points:**
- Envelope: `===NAME===` at start, `===END===` at end
- META block required: at minimum `TYPE` and `VERSION`
- `---` separator is optional (for readability)
- `::` assigns values (no spaces around it)
- Lists use brackets: `[a,b,c]`
- Inline maps: `[key::value,key2::value2]`
- Flow sequences: `[A->B->C]`
- Empty lists: `[]`

---

## SCHEMA Mode Example

SCHEMA mode defines document types with validation rules. Uses holographic patterns with constraints and routing targets.

```octave
===USER_SCHEMA===
META:
  TYPE::PROTOCOL_DEFINITION
  VERSION::"1.0"
  STATUS::DRAFT

---

POLICY:
  VERSION::"1.0"
  UNKNOWN_FIELDS::REJECT
  TARGETS::[INDEXER,META]

FIELDS:
  ID::["user_123"&REQ->INDEXER]
  EMAIL::["user@example.com"&REQ->INDEXER]
  STATUS::["ACTIVE"&REQ&ENUM[ACTIVE,SUSPENDED,DELETED]->META]
  CREATED::["2026-01-02"&REQ&DATE->META]
  NOTES::["Optional context"&OPT->SELF]

===END===
```

**Key Points:**
- Holographic pattern: `["example"&CONSTRAINT->TARGET]`
- Example value teaches expected format
- Constraints chain with `&`: `REQ&ENUM[A,B,C]`
- Target routes data: `->INDEXER`, `->META`, `->SELF`
- Available constraints: `REQ`, `OPT`, `CONST`, `REGEX`, `ENUM`, `DATE`, `RANGE`, `MAX_LENGTH`, `MIN_LENGTH`
- POLICY block defines validation behavior

**Note:** Full holographic pattern parsing (including TYPE constraints) is under active development. See the schema spec for the complete syntax.

---

## Step-by-Step: Creating Your First OCTAVE Document

### Step 1: Choose Your Mode

- **DATA mode**: You have data instances to store (configs, sessions, state)
- **SCHEMA mode**: You need to define validation rules for a document type

### Step 2: Create the Envelope

Every OCTAVE document starts and ends the same way:

```octave
===DOCUMENT_NAME===
META:
  TYPE::YOUR_TYPE
  VERSION::"1.0"

---

CONTENT:
  KEY::value

===END===
```

### Step 3: Add Your Content

**For DATA mode**, use simple assignments:

```octave
SECTION:
  KEY::value
  LIST::[item1,item2]
  MAP::[k1::v1,k2::v2]
```

**For SCHEMA mode**, use holographic patterns:

```octave
FIELDS:
  FIELD_NAME::["example"&CONSTRAINT->TARGET]
```

### Step 4: Validate Your Document

Use the `octave_validate` MCP tool:

```
octave_validate(schema="META", content="your document here")
```

The tool returns:
- `status`: success or error
- `canonical`: normalized version of your document
- `repairs`: any automatic fixes applied
- `warnings`: potential issues
- `errors`: validation failures

---

## Common Operators

| Operator | ASCII | Meaning | Example |
|----------|-------|---------|---------|
| `::` | `::` | Assignment | `KEY::value` |
| `->` | `->` | Flow/sequence | `A->B->C` |
| `&` | `&` | Constraint chain | `REQ&TYPE(STRING)` |
| `\|` | `\|` | Alternative | `A\|B` |
| `[]` | `[]` | Container/list | `[a,b,c]` |

---

## Common Mistakes to Avoid

1. **Tabs instead of spaces**: Use 2-space indentation only
2. **Spaces around `::`**: Write `KEY::value` not `KEY :: value`
3. **Missing `===END===`**: Every document must end with this
4. **Wrong case for booleans**: Use `true`/`false` not `True`/`FALSE`
5. **Nested inline maps**: `[a::[b::c]]` is forbidden; use proper nesting instead

---

## Full Specification

For complete details:

- **Core syntax**: [specs/octave-5-llm-core.oct.md](../specs/octave-5-llm-core.oct.md)
- **DATA mode**: [specs/octave-5-llm-data.oct.md](../specs/octave-5-llm-data.oct.md)
- **SCHEMA mode**: [specs/octave-5-llm-schema.oct.md](../specs/octave-5-llm-schema.oct.md)
