# OCTAVE MCP Server - API Reference

Complete API reference for the OCTAVE MCP server, including MCP tools, Python modules, and CLI commands.

## Table of Contents

- [MCP Tools](#mcp-tools)
  - [octave_validate](#octave_validate)
  - [octave_write](#octave_write)
  - [octave_eject](#octave_eject)
- [Python API](#python-api)
  - [Parser Module](#parser-module)
  - [Emitter Module](#emitter-module)
  - [Validator Module](#validator-module)
  - [Schema Module](#schema-module)
- [CLI Commands](#cli-commands)
  - [octave ingest](#octave-ingest)
  - [octave eject](#octave-eject)
  - [octave validate](#octave-validate)
- [Data Types](#data-types)

---

## MCP Tools

The OCTAVE MCP server exposes three tools for integration with MCP clients.

### octave_validate

Schema validation and parsing of OCTAVE content.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `content` | string | No | - | OCTAVE content to validate (mutually exclusive with `file_path`) |
| `file_path` | string | No | - | Path to OCTAVE file to validate (mutually exclusive with `content`) |
| `schema` | string | Yes | - | Schema name for validation (e.g., `"DECISION_LOG"`) |
| `fix` | boolean | No | `false` | If True, apply repairs to canonical output |

#### Returns

```typescript
{
  canonical: string;           // Normalized OCTAVE in strict format
  valid: boolean;              // Whether document passed validation
  validation_errors: ValidationError[];  // Schema violations found
  repair_log: RepairEntry[];   // List of all transformations applied
}
```

#### ValidationError Type

```typescript
{
  code: string;         // Error code (e.g., "UNKNOWN_FIELD", "TYPE_MISMATCH")
  message: string;      // Human-readable description
  path: string;         // Location in document (e.g., "DECISION.STATUS")
  severity: "ERROR" | "WARNING";  // Error severity
}
```

#### RepairEntry Type

```typescript
{
  tier: "NORMALIZATION" | "REPAIR";  // Classification
  location: string;                   // Position in document (e.g., "line 5")
  original: string;                   // Original text
  canonical: string;                  // Transformed text
  reason: string;                     // Explanation of transformation
}
```

#### Example

```python
import asyncio
from mcp import Client

async def validate_example():
    client = Client()
    await client.connect("octave-mcp-server")

    result = await client.call_tool(
        "octave_validate",
        {
            "content": 'DECISION:\n  ID::"DEC-001"\n  STATUS::"approved"',
            "schema": "DECISION_LOG"
        }
    )

    print("Valid:", result["valid"])
    print("Canonical:", result["canonical"])
    print("Errors:", len(result["validation_errors"]))

asyncio.run(validate_example())
```

#### Error Handling

The tool returns errors in the `validation_errors` array rather than throwing exceptions. Always check this array:

```python
result = await client.call_tool("octave_validate", {...})
if result["validation_errors"]:
    for error in result["validation_errors"]:
        print(f"{error['severity']}: {error['message']} at {error['path']}")
```

---

### octave_write

Unified entry point for writing OCTAVE files. Handles creation (new files) and modification (existing files).

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `target_path` | string | Yes | - | File path to write to |
| `content` | string | No | - | Full content for new files or overwrites (mutually exclusive with `changes`) |
| `changes` | object | No | - | Dictionary of field updates for existing files (mutually exclusive with `content`) |
| `schema` | string | No | - | Schema name for validation |
| `mutations` | object | No | - | META field overrides (applies to both modes) |
| `base_hash` | string | No | - | Expected SHA-256 hash of existing file for consistency check (CAS) |

#### Returns

```typescript
{
  success: boolean;            // Whether write succeeded
  path: string;                // Absolute path to written file
  diff: string;                // Summary of changes made
  canonical: string;           // Final canonical content
}
```

#### Example: Creating a new file

```python
result = await client.call_tool(
    "octave_write",
    {
        "target_path": "/path/to/decision.oct.md",
        "content": 'DECISION:\n  ID::"DEC-001"\n  STATUS::"approved"',
        "schema": "DECISION_LOG"
    }
)
```

#### Example: Modifying an existing file

```python
result = await client.call_tool(
    "octave_write",
    {
        "target_path": "/path/to/decision.oct.md",
        "changes": {"STATUS": "APPROVED", "REVIEWED_BY": "team-lead"}
    }
)
```

---

### octave_eject

Generate tailored views from canonical OCTAVE for different stakeholders.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `content` | string | No | `null` | Canonical OCTAVE (null generates template) |
| `schema` | string | Yes | - | Schema name for validation |
| `mode` | string | No | `"canonical"` | Projection mode: `"canonical"`, `"authoring"`, `"executive"`, `"developer"` |
| `format` | string | No | `"octave"` | Output format: `"octave"`, `"json"`, `"yaml"`, `"markdown"` |

#### Projection Modes

- **canonical**: Full document in strict OCTAVE (lossless)
- **authoring**: Lenient format for human/LLM editing (lossless)
- **executive**: High-level summary (status, risks, decisions; omits technical detail)
- **developer**: Implementation focus (tests, CI, dependencies; omits executive summaries)

#### Returns

```typescript
{
  output: string;              // Formatted output in requested format
  lossy: boolean;              // True if fields were omitted
  omitted_fields: string[];    // List of field paths omitted (if lossy)
}
```

#### Example

```python
import asyncio
from mcp import Client

async def eject_example():
    client = Client()
    await client.connect("octave-mcp-server")

    # Executive summary in Markdown
    result = await client.call_tool(
        "octave_eject",
        {
            "content": canonical_octave,
            "schema": "PROJECT_STATUS",
            "mode": "executive",
            "format": "markdown"
        }
    )

    print(result["output"])
    if result["lossy"]:
        print(f"\nNote: Following fields omitted: {', '.join(result['omitted_fields'])}")

asyncio.run(eject_example())
```

#### Template Generation

Pass `null` for `content` to generate a blank template:

```python
result = await client.call_tool(
    "octave_eject",
    {
        "content": None,
        "schema": "DECISION_LOG",
        "mode": "authoring",
        "format": "octave"
    }
)
# Returns a template with all required fields
```

---

## Python API

Direct Python API for programmatic integration without MCP.

### Public Exports

The octave-mcp package exposes the following public API exports for external use:

#### Core Functions
```python
from octave_mcp import parse, emit, tokenize, repair, project
```
- `parse(content: str) -> Document` - Parse OCTAVE text to document tree
- `emit(doc: Document, mode: str = "canonical") -> str` - Emit document as OCTAVE
- `tokenize(content: str) -> list[Token]` - Tokenize OCTAVE text
- `repair(doc: Document, schema: Schema) -> tuple[Document, RepairLog]` - Apply repairs
- `project(doc: Document, mode: str) -> Document` - Project document to view

#### Core Classes
```python
from octave_mcp import Parser, Validator, TokenType, Token
```

#### AST Nodes
```python
from octave_mcp.core.ast import (
    Document, Block, Assignment, Section,
    ListValue, InlineMap, Absent
)
```

#### Hydration System
```python
from octave_mcp import hydrate, HydrationPolicy, VocabularyRegistry
```
- `hydrate(doc: Document, policy: HydrationPolicy) -> Document` - Hydrate document
- `HydrationPolicy` - Configuration for hydration behavior
- `VocabularyRegistry` - Registry for vocabulary patterns

#### Schema System
```python
from octave_mcp import (
    SchemaDefinition, FieldDefinition,
    extract_schema_from_document
)
```
- `SchemaDefinition` - Schema structure definition
- `FieldDefinition` - Individual field definition
- `extract_schema_from_document(doc: Document) -> SchemaDefinition` - Extract schema

#### Repair System (I4)
```python
from octave_mcp import RepairLog, RepairEntry, RepairTier
```
- `RepairLog` - Collection of repair operations
- `RepairEntry` - Individual repair record
- `RepairTier` - Classification of repair type (NORMALIZATION or REPAIR)

#### Routing System (I4)
```python
from octave_mcp import RoutingLog, RoutingEntry
```
- `RoutingLog` - Transformation routing audit trail
- `RoutingEntry` - Individual routing record

#### Document Sealing
```python
from octave_mcp import seal_document, verify_seal, SealVerificationResult
```
- `seal_document(doc: Document) -> Document` - Add integrity seal
- `verify_seal(doc: Document) -> SealVerificationResult` - Verify seal
- `SealVerificationResult` - Verification outcome details

#### Exceptions
```python
from octave_mcp import (
    OctaveError, ParseError, ValidationError,
    SchemaError, RepairError, SealError,
    HydrationError, ProjectionError, EmitError
)
```

#### Operators
```python
from octave_mcp import (
    OCTAVE_OPERATORS,
    OP_ASSIGN, OP_BLOCK, OP_FLOW, OP_SYNTHESIS,
    OP_CONCAT, OP_TENSION, OP_ALTERNATIVE,
    OP_CONSTRAINT, OP_TARGET, OP_REFERENCE
)
```

### Parser Module

`octave_mcp.core.parser`

#### `parse(content: str) -> Document`

Parse lenient OCTAVE text into a document tree.

**Parameters:**
- `content` (str): Raw OCTAVE text (lenient or canonical)

**Returns:**
- `Document`: Parsed document tree

**Raises:**
- `SyntaxError`: If content has invalid syntax

**Example:**

```python
from octave_mcp.core.parser import parse

content = """
DECISION:
  ID::"DEC-001"
  STATUS::"approved"
"""

doc = parse(content)
print(doc.root)  # Access root node
```

#### Document Structure

```python
class Document:
    root: Node              # Root node of the document tree
    envelope: Envelope      # META envelope information

class Node:
    key: str                # Node key
    value: Any              # Node value (str, list, dict, or nested Node)
    children: list[Node]    # Child nodes (for block structures)
    line_number: int        # Source line number

class Envelope:
    meta: dict[str, Any]    # META fields (TYPE, VERSION, etc.)
```

---

### Emitter Module

`octave_mcp.core.emitter`

#### `emit(doc: Document, mode: str = "canonical") -> str`

Emit a document tree as formatted OCTAVE text.

**Parameters:**
- `doc` (Document): Parsed document tree
- `mode` (str): Output mode - `"canonical"` or `"authoring"`

**Returns:**
- `str`: Formatted OCTAVE text

**Example:**

```python
from octave_mcp.core.parser import parse
from octave_mcp.core.emitter import emit

doc = parse(content)
canonical = emit(doc, mode="canonical")
print(canonical)
```

#### Normalization Rules

When `mode="canonical"`:
- ASCII operators → Unicode (`->` → `→`)
- Whitespace normalized (2-space indents)
- Quotes normalized (`'` → `"`)
- Envelopes completed (META added if missing)

When `mode="authoring"`:
- ASCII operators preserved
- Flexible whitespace preserved
- Human-friendly formatting

---

### Validator Module

`octave_mcp.core.validator`

#### `validate(doc: Document, schema_name: str | None = None, strict: bool = False) -> list[ValidationError]`

Validate a document against schema requirements.

**Parameters:**
- `doc` (Document): Parsed document to validate
- `schema_name` (str | None): Schema name (or None to skip schema validation)
- `strict` (bool): If True, unknown fields are errors; if False, warnings

**Returns:**
- `list[ValidationError]`: List of validation errors (empty if valid)

**Example:**

```python
from octave_mcp.core.parser import parse
from octave_mcp.core.validator import validate

doc = parse(content)
errors = validate(doc, schema_name="DECISION_LOG", strict=True)

if errors:
    for error in errors:
        print(f"{error.code}: {error.message} at {error.path}")
else:
    print("Valid")
```

#### ValidationError Structure

```python
class ValidationError:
    code: str               # Error code (e.g., "UNKNOWN_FIELD")
    message: str            # Human-readable description
    path: str               # Location in document (e.g., "DECISION.STATUS")
    severity: str           # "ERROR" or "WARNING"
    line_number: int | None # Source line number (if available)
```

#### Common Error Codes

- `UNKNOWN_FIELD`: Field not in schema (warning in non-strict, error in strict)
- `MISSING_REQUIRED`: Required field is absent
- `TYPE_MISMATCH`: Field value doesn't match expected type
- `ENUM_VIOLATION`: Value not in allowed enum set
- `INVALID_STRUCTURE`: Nested structure doesn't match schema

---

### Schema Module

`octave_mcp.core.schema`

#### `load_schema(name: str) -> Schema`

Load a builtin or custom schema by name.

**Parameters:**
- `name` (str): Schema name (e.g., `"DECISION_LOG"`, `"META"`)

**Returns:**
- `Schema`: Schema definition

**Raises:**
- `ValueError`: If schema not found

**Example:**

```python
from octave_mcp.core.schema import load_schema

schema = load_schema("DECISION_LOG")
print("Required fields:", schema.required_fields)
print("Field types:", schema.field_types)
```

#### Schema Structure

```python
class Schema:
    name: str                       # Schema name
    version: str                    # Schema version
    required_fields: set[str]       # Set of required field names
    field_types: dict[str, Type]    # Field name → expected type
    enums: dict[str, set[str]]      # Field name → allowed values
    nested_schemas: dict[str, str]  # Field name → nested schema name
```

#### Builtin Schemas

The following schemas are included:

- `META`: OCTAVE document envelope
- `DECISION_LOG`: Decision records
- `TASK`: Task definitions
- `TASK_RESULT`: Task completion records

Custom schemas can be added to `src/octave_mcp/schemas/`.

---

## CLI Commands

Command-line interface for OCTAVE processing.

### octave ingest

Ingest lenient OCTAVE and emit canonical output.

#### Syntax

```bash
octave ingest FILE [OPTIONS]
```

#### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--schema` | string | None | Schema name for validation |
| `--fix` | flag | False | Apply TIER_REPAIR fixes |
| `--verbose` | flag | False | Show pipeline stages |

#### Examples

```bash
# Basic ingestion
octave ingest document.oct.md

# With validation
octave ingest document.oct.md --schema DECISION_LOG

# With auto-repair
octave ingest document.oct.md --schema DECISION_LOG --fix

# Verbose mode
octave ingest document.oct.md --verbose
```

#### Exit Codes

- `0`: Success
- `1`: Syntax error or validation failure

---

### octave eject

Eject OCTAVE to projected format.

#### Syntax

```bash
octave eject FILE [OPTIONS]
```

#### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--schema` | string | None | Schema name for validation |
| `--mode` | string | `canonical` | Projection mode: `canonical`, `authoring`, `executive`, `developer` |
| `--format` | string | `octave` | Output format: `octave`, `json`, `yaml`, `markdown` |

#### Examples

```bash
# Canonical output (default)
octave eject document.oct.md

# Executive summary in Markdown
octave eject document.oct.md --mode executive --format markdown

# Developer view in JSON
octave eject document.oct.md --mode developer --format json

# Authoring format for editing
octave eject document.oct.md --mode authoring
```

#### Exit Codes

- `0`: Success
- `1`: File not found or processing error

---

### octave validate

Validate OCTAVE against schema.

#### Syntax

```bash
octave validate FILE [OPTIONS]
```

#### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--schema` | string | None | Schema name for validation |
| `--strict` | flag | False | Strict mode (unknown fields are errors) |

#### Examples

```bash
# Basic validation
octave validate document.oct.md --schema DECISION_LOG

# Strict mode
octave validate document.oct.md --schema DECISION_LOG --strict
```

#### Exit Codes

- `0`: Valid (no errors)
- `1`: Invalid (validation errors found)

---

## Data Types

### Type System

OCTAVE supports the following value types:

| Type | OCTAVE Syntax | Python Type | Example |
|------|---------------|-------------|---------|
| String | `"value"` | `str` | `ID::"DEC-001"` |
| Identifier | `value` | `str` | `STATUS::APPROVED` |
| Integer | `42` | `int` | `COUNT::42` |
| Float | `3.14` | `float` | `RATIO::3.14` |
| Boolean | `true`, `false` | `bool` | `ENABLED::true` |
| List | `[A, B, C]` | `list` | `TAGS::[urgent, security]` |
| Flow | `[A→B→C]` | `list` | `PIPELINE::[parse→validate→emit]` |
| Dict | Block structure | `dict` | See below |

### Dictionary Structure

```octave
PARENT:
  CHILD_1::"value"
  CHILD_2::42
  NESTED:
    GRANDCHILD::"value"
```

Equivalent Python:
```python
{
  "PARENT": {
    "CHILD_1": "value",
    "CHILD_2": 42,
    "NESTED": {
      "GRANDCHILD": "value"
    }
  }
}
```

### Operators

| Operator | Unicode | ASCII | Meaning | Example |
|----------|---------|-------|---------|---------|
| Assignment | `::` | `::` | Key-value binding | `KEY::VALUE` |
| Block | `:` | `:` | Nested structure | `KEY:\n  CHILD::VALUE` |
| Flow | `→` | `->` | Sequence | `A→B→C` |
| Synthesis | `⊕` | `+` | Emergent combination | `A⊕B⊕C` |
| Concatenation | `⧺` | `~` | Mechanical join | `path⧺to⧺file` |
| Tension | `⇌` | `vs` | Binary opposition | `Speed⇌Quality` |
| Alternative | `∨` | `\|` | Choice | `A∨B∨C` |
| Constraint | `∧` | `&` | All required | `A∧B∧C` |
| Target | `§` | `§` | Section reference | `§3::DEFINITIONS` |

---

## See Also

- [Usage Guide](usage.md) - Detailed usage examples and workflows
- [MCP Configuration](mcp-configuration.md) - Setup guide for MCP clients
- [OCTAVE Specification](https://github.com/elevanaltd/octave-mcp/tree/main/src/octave_mcp/resources/specs) - Full protocol specification
