# OCTAVE-MCP Public API Reference (v0.3.0)

This document describes the public API exports available when importing `octave_mcp`.

## Installation

```bash
pip install octave-mcp
```

## Quick Start

```python
from octave_mcp import parse, emit, OP_TENSION, OP_FLOW

# Parse OCTAVE text
doc = parse("""===CONFIG===
META:
  TYPE::CONFIG
  VERSION::"1.0"
STATUS::ACTIVE
===END===""")

# Access parsed data
print(doc.name)  # "CONFIG"
print(doc.meta)  # {"TYPE": "CONFIG", "VERSION": "1.0"}

# Emit back to canonical form
canonical = emit(doc)
```

---

## Core Functions

### `parse(content: str) -> Document`

Parse OCTAVE text into an AST Document.

```python
from octave_mcp import parse

doc = parse("===DOC===\nKEY::value\n===END===")
```

### `emit(doc: Document) -> str`

Emit a Document AST back to canonical OCTAVE text.

```python
from octave_mcp import emit

canonical_text = emit(doc)
```

### `tokenize(content: str) -> tuple[list[Token], list[Any]]`

Tokenize raw OCTAVE text into a token stream.

```python
from octave_mcp import tokenize

tokens, warnings = tokenize("KEY::value")
for token in tokens:
    print(token.type, token.value)
```

### `repair(doc: Document, schema: SchemaDefinition, fix: bool = False) -> tuple[Document, RepairLog]`

Apply schema-driven repairs to a document.

```python
from octave_mcp import repair, parse, extract_schema_from_document

doc = parse(content)
schema = extract_schema_from_document(schema_doc)
repaired_doc, repair_log = repair(doc, schema, fix=True)
```

### `project(doc: Document, mode: str) -> ProjectionResult`

Project a document to a specific view mode.

```python
from octave_mcp import project

# Modes: "canonical", "authoring", "executive", "developer"
result = project(doc, mode="executive")
print(result.output)        # Filtered OCTAVE text
print(result.lossy)         # True (executive mode omits fields)
print(result.fields_omitted)  # List of omitted field names
```

---

## Core Classes

### `Parser`

Low-level parser class for advanced usage.

### `Validator`

Schema validator for OCTAVE documents.

```python
from octave_mcp import Validator, ValidationError

validator = Validator(schema)
errors = validator.validate(doc)
for err in errors:
    print(f"{err.code}: {err.message}")
```

### `TokenType` (Enum)

Token type enumeration used by the lexer.

```python
from octave_mcp import TokenType

if token.type == TokenType.TENSION:
    print("Found tension operator")
```

### `Token`

Token dataclass with `type`, `value`, `line`, `column` fields.

---

## AST Nodes

All AST nodes for representing parsed OCTAVE documents:

| Class | Description |
|-------|-------------|
| `Document` | Root document node with `name`, `meta`, `sections` |
| `Block` | Key with nested children (KEY: followed by indented content) |
| `Assignment` | Simple key-value pair (KEY::value) |
| `Section` | Section marker (e.g., META:, FIELDS:) |
| `ListValue` | List container [a, b, c] |
| `InlineMap` | Inline key-value pairs [k1::v1, k2::v2] |
| `Absent` | Sentinel for distinguishing absent vs null (I2 compliance) |

```python
from octave_mcp import Document, Block, Assignment, Absent

# Check if a value is absent (not provided) vs null (explicitly empty)
if isinstance(value, Absent):
    print("Field was not provided")
elif value is None:
    print("Field was explicitly set to null")
```

---

## Hydration (Vocabulary Import)

### `hydrate(doc: Document, registry: VocabularyRegistry, policy: HydrationPolicy) -> Document`

Hydrate vocabulary imports in a document.

```python
from octave_mcp import hydrate, VocabularyRegistry, HydrationPolicy
from pathlib import Path

registry = VocabularyRegistry.from_mappings({
    "@octave/core": Path("vocabs/core.oct.md")
})
policy = HydrationPolicy()

hydrated_doc = hydrate(doc, registry, policy)
```

### `HydrationPolicy`

Configuration for hydration behavior (collision handling, pruning strategy).

### `VocabularyRegistry`

Registry mapping namespace URIs to vocabulary file paths.

---

## Schema Introspection

### `extract_schema_from_document(doc: Document) -> SchemaDefinition`

Extract schema definition from a parsed schema document.

```python
from octave_mcp import parse, extract_schema_from_document

schema_doc = parse(schema_content)
schema = extract_schema_from_document(schema_doc)

for field_name, field_def in schema.fields.items():
    print(f"{field_name}: required={field_def.is_required}")
```

### `SchemaDefinition`

Complete schema with `name`, `version`, `policy`, `fields`.

### `FieldDefinition`

Single field definition with `name`, `pattern`, `is_required`.

---

## Audit Trail Types (I4 Compliance)

### Repair Audit

```python
from octave_mcp import RepairLog, RepairEntry, RepairTier

# RepairTier values:
# - NORMALIZATION: Always applied (whitespace, unicode)
# - REPAIR: Only when fix=True (enum casefold, type coercion)
# - FORBIDDEN: Never automatic

for entry in repair_log.repairs:
    print(f"{entry.rule_id}: {entry.before} -> {entry.after}")
    print(f"  tier={entry.tier}, safe={entry.safe}")
```

### Routing Audit

```python
from octave_mcp import RoutingLog, RoutingEntry

# Access routing log from validator
for entry in validator.routing_log.entries:
    print(f"{entry.source_path} -> {entry.target_name}")
    print(f"  hash={entry.value_hash[:8]}...")
```

---

## Document Sealing (Integrity)

### `seal_document(doc: Document) -> Document`

Add integrity seal to a document.

```python
from octave_mcp import seal_document

sealed_doc = seal_document(doc)
```

### `verify_seal(doc: Document) -> SealVerificationResult`

Verify document integrity seal.

```python
from octave_mcp import verify_seal

result = verify_seal(doc)
if result.valid:
    print("Document integrity verified")
else:
    print(f"Seal invalid: {result.reason}")
```

---

## Exceptions

| Exception | Description |
|-----------|-------------|
| `ParserError` | Syntax error during parsing |
| `LexerError` | Tokenization error |
| `ValidationError` | Schema validation failure |
| `VocabularyError` | Base class for hydration errors |
| `CollisionError` | Term collision during hydration |
| `VersionMismatchError` | Vocabulary version mismatch |
| `CycleDetectionError` | Circular vocabulary import detected |
| `SourceUriSecurityError` | Security violation in vocabulary URI |

```python
from octave_mcp import parse, ParserError

try:
    doc = parse(content)
except ParserError as e:
    print(f"Parse error at line {e.line}: {e.message}")
```

---

## Operators

Canonical OCTAVE operators for use in code that generates or manipulates OCTAVE text.

### Dictionary Access

```python
from octave_mcp import OCTAVE_OPERATORS

print(OCTAVE_OPERATORS["FLOW"])      # "→"
print(OCTAVE_OPERATORS["TENSION"])   # "⇌"
print(OCTAVE_OPERATORS["SYNTHESIS"]) # "⊕"
```

### Individual Constants

```python
from octave_mcp import OP_FLOW, OP_TENSION, OP_SYNTHESIS

# Build OCTAVE expressions programmatically
expr = f"A{OP_TENSION}B{OP_FLOW}C"  # "A⇌B→C"
```

### Complete Operator Reference

| Constant | Unicode | ASCII | Semantic |
|----------|---------|-------|----------|
| `OP_ASSIGN` | `::` | `::` | Key-value binding |
| `OP_BLOCK` | `:` | `:` | Block start |
| `OP_CONCAT` | `⧺` | `~` | Mechanical join |
| `OP_SYNTHESIS` | `⊕` | `+` | Emergent whole |
| `OP_TENSION` | `⇌` | `vs` | Binary opposition |
| `OP_CONSTRAINT` | `∧` | `&` | Logical AND |
| `OP_ALTERNATIVE` | `∨` | `\|` | Logical OR |
| `OP_FLOW` | `→` | `->` | Directional flow |
| `OP_SECTION` | `§` | `#` | Section marker |
| `OP_COMMENT` | `//` | `//` | Line comment |

---

## Version

```python
from octave_mcp import __version__

print(__version__)  # "0.3.0"
```

---

## See Also

- [OCTAVE Specification](../specs/octave-5-llm-core.oct.md)
- [Schema Mode](../specs/octave-5-llm-schema.oct.md)
- [Data Mode](../specs/octave-5-llm-data.oct.md)
