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

Wire-envelope shape emitted by the MCP `octave_validate` tool:

```typescript
{
  code: string;         // Error code (e.g., "UNKNOWN_FIELD", "TYPE_MISMATCH")
  message: string;      // Human-readable description
  field: string;        // Location in document (e.g., "DECISION.STATUS")
}
```

> The Python `ValidationError` dataclass (returned by direct `Validator`
> usage) carries additional fields (`field_path`, `line`, `severity`);
> see the [ValidationError Structure](#validationerror-structure) block
> below for the Python-API surface.

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
        print(f"{error['code']}: {error['message']} at {error['field']}")
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
| `format_style` | string | No | _(unset)_ | Output formatting projection — one of `"preserve"`, `"expanded"`, `"compact"`. When omitted, today's canonical emit behaviour is preserved exactly. See [Format-style modes](#format-style-modes-gh376-pr-a) below. |

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

#### Op-aware mutation in `changes` (GH#373)

Each value in `changes` is either a **bare value** (full replacement, default
behaviour) or a **`$op` descriptor** that targets a specific operation:

| `$op` | Target type | Semantics |
|---|---|---|
| `APPEND` | array | push `value` (or each item of list `value`) onto the end |
| `PREPEND` | array | unshift `value` (or each item of list `value`) onto the front |
| `MERGE` | block (dict) | deep-merge `value` into the block; unmentioned keys preserved |
| `DELETE` | any | remove the target (key or assignment) |
| _(none)_ | any | full-value replacement (legacy behaviour) |

Paths support: top-level `KEY`, `META.FIELD`, `PARENT.CHILD` into a top-level
Block, `§N.KEY` / `§N::NAME.KEY` into Sections, and `ANCHOR/KEY` anchored paths
for disambiguating duplicate sibling keys (see below).

```python
# Append a new token to a nested array (no read-modify-write of the whole array).
await client.call_tool("octave_write", {
    "target_path": path,
    "changes": {"NAV.OPERATIONAL_CONVENTIONS": {"$op": "APPEND", "value": "NEW_TOKEN"}}
})

# Bulk-append multiple elements in caller order.
await client.call_tool("octave_write", {
    "target_path": path,
    "changes": {"NAV.OPERATIONAL_CONVENTIONS": {"$op": "APPEND", "value": ["A", "B"]}}
})

# Merge into a top-level Block, preserving unmentioned children.
await client.call_tool("octave_write", {
    "target_path": path,
    "changes": {"NAV": {"$op": "MERGE", "value": {"NEW_KEY": "x"}}}
})

# Remove a nested child.
await client.call_tool("octave_write", {
    "target_path": path,
    "changes": {"NAV.DEPRECATED": {"$op": "DELETE"}}
})
```

#### Anchored-path disambiguation `ANCHOR/KEY` (GH#460, v1.14.0)

When a document contains **duplicate sibling keys** — e.g. five sibling
`RATIONALE` keys, one following each `I1`…`I5` immutable — a bare-key change
(`{"RATIONALE": …}`) resolves only the **first** match. The `ANCHOR/KEY` form
disambiguates: it targets *"the `KEY` assignment that follows the `ANCHOR` key
in document order"*.

```python
# Update only the RATIONALE that follows the I2 key; siblings untouched.
await client.call_tool("octave_write", {
    "target_path": path,
    "changes": {"I2/RATIONALE": "new rationale for I2"}
})
```

Semantics and guarantees:

- **Document order.** `ANCHOR/KEY` resolves the first `KEY` assignment that
  appears *after* the `ANCHOR` assignment within the **same sibling list**
  (top-level, or one level inside a Block/Section). The anchor never crosses a
  container boundary.
- **Resolve-literal-first (backward-compat).** `/` is a valid OCTAVE identifier
  character, so a key may literally contain it. If a real assignment whose key
  is exactly `ANCHOR/KEY` exists, it is mutated in place; the anchored-path
  interpretation only applies when no such literal key is present. Bare `KEY`,
  `META.FIELD`, `PARENT.CHILD`, and `§N.KEY` paths are unchanged.
- **Real keys, not indices.** Indexed addressing (`KEY[N]`) is deliberately
  **not** supported and remains rejected with `E_UNRESOLVABLE_PATH`. Stable
  real-key anchors honour PROD::I4 (Transform Auditability — deleting a sibling
  does not shift which node a path resolves to) and PROD::I3 (Mirror Constraint
  — reflect real structure, never invented indices).
- **No auto-create.** An anchored path that does not resolve (anchor absent, or
  no `KEY` following the anchor) fails with `E_UNRESOLVABLE_PATH` rather than
  appending a fabricated `ANCHOR/KEY` assignment (PROD::I3).

#### Literal-zone form preservation (GH#460, v1.14.0)

When a `changes` value replaces a child whose existing value is a **literal
zone** (a fenced ```` ``` ```` block), the new content is re-wrapped to preserve
the fence form — the original fence marker (e.g. ```` ``` ```` vs ```` ```` ````)
and info tag are kept, and only the inner content changes. A content-only edit
therefore round-trips to a **byte-identical fence form** under
`format_style="preserve"`, instead of being downgraded to a quoted scalar
(`KEY::"…"`). This restores PROD::I1 (Syntactic Fidelity:
*normalization_alters_syntax_never_semantics*) and mirrors the PR #449
mutate-in-place philosophy.

```python
# A fenced OPERATOR_LEGEND block: only the content changes; the ``` fence
# framing is preserved byte-for-byte.
await client.call_tool("octave_write", {
    "target_path": path,
    "changes": {"OPERATOR_LEGEND": "A -> B (new)\nC -> D (new)"},
    "format_style": "preserve",
})
```

> Passing an explicit `LiteralZoneValue`, a list, or a `$op` descriptor is taken
> at face value; form preservation only re-wraps a plain string replacement
> aimed at an existing literal-zone child.

**Validation contract.** Op/target-type mismatches and missing paths surface as
explicit error codes; they are never silently coerced (I3 Mirror Constraint,
I5 Schema Sovereignty). All descriptors in a batch are validated up-front:
if any descriptor is invalid, none are applied (fail-fast atomicity).

| Error code | Cause |
|---|---|
| `E_OP_TARGET_MISMATCH` | `APPEND`/`PREPEND` on a non-array, or `MERGE` on a non-block |
| `E_UNRESOLVABLE_PATH` | path does not resolve in the AST (auto-create is forbidden) |
| `E_INVALID_OP_DESCRIPTOR` | unknown `$op`, missing `value` for `APPEND`/`PREPEND`/`MERGE` (not `DELETE`), or `MERGE` with non-dict `value` |

> **Diff-locality note.** `$op` descriptors give you correct, targeted *semantics*
> (e.g. APPEND mutates only the array's contents in the AST), but the rendered
> diff is not yet guaranteed to be byte-stable outside the changed region — the
> renderer canonicalises the whole document. Renderer stability is tracked
> separately in [GH#371](https://github.com/elevanaltd/octave-mcp/issues/371).

#### Format-style modes (GH#376 PR-A)

`format_style` is an optional output-formatting projection. The three accepted
values are **AST-level pre-passes that all funnel into the single canonical
`emit()`** — they are projections of one canon, not parallel emitters
(I1 Single-Canon Discipline). Unknown values are rejected with
`E_INVALID_FORMAT_STYLE` (I5 Schema Sovereignty).

| Mode | Semantics | When to use |
|---|---|---|
| _(unset / omitted)_ | Today's canonical behaviour byte-for-byte. No pre-pass, no short-circuit. | Default — preserves existing call-site behaviour. **Note:** in **v1.14.0** this default will flip to `"preserve"`; pin a value explicitly if byte-shape stability across versions matters. |
| _(explicit `null` / `None`)_ | **Deprecated in v1.13.0.** Same byte-for-byte behaviour as omission today, but emits a `DeprecationWarning` to announce the v1.14.0 default flip. | Avoid — either omit the parameter (accept the future default) or pin an explicit string value. |
| `"preserve"` | **Strategy A span-aware preserve mode (#418).** Single-region slice-and-replace: clean nodes are sliced verbatim from the post-NFC baseline bytes; only mutated subtrees (`dirty`, `body_dirty`, `repaired`, `meta_dirty[k]=True`) are re-emitted canonically. Diff footprint ≤0.5% of file size on representative documents. Subsumes GH#248 mixed annotation form drift. Falls through to canonical `emit()` when the doc was parsed from user-supplied new content (content mode — spans index the new content, not the baseline file). | The recommended mode for changes-mode edits where unchanged regions should produce zero-byte diff. |
| `"expanded"` | AST normalisation pre-pass that lifts `InlineMap` (and `ListValue` items that are `InlineMap`) into `Block` form before `emit()`. Materially changes on-disk shape vs default. | Canonicalisation pipelines where compact inline shapes must be normalised to multi-line Blocks for diff stability or downstream tooling. ALSO the recommended pin if you want to keep v1.12.0 canonical re-emit behaviour past the v1.14.0 default flip. |
| `"compact"` | AST pre-pass that collapses atom-only Blocks (no `Comment` anywhere in subtree, arity ≤ 8) into `Assignment(value=ListValue([InlineMap{...}, ...]))` form. Subtrees containing **any** `Comment` are vetoed and a `W_COMPACT_REFUSED` correction is appended to the repair log. | Token-minimised outputs for LLM consumption — but mind the comment veto. |

##### `W_COMPACT_REFUSED` repair record

When `format_style="compact"` encounters a Block whose subtree contains any
`Comment` node, the collapse is **refused for that subtree** (the Block is
left in its multi-line form) and a structured correction is appended to the
response's repair log:

```typescript
{
  code: "W_COMPACT_REFUSED",
  field: "<dotted.path.to.block>",
  message: "Compact projection refused: comment(s) present in subtree (I3 Mirror Constraint)."
}
```

This record IS the I4 Auditability expression of compact-mode — every
attempted-and-refused collapse leaves a receipt. The MCP tool surfaces it in
the `corrections` field of the standard response; the CLI surfaces each entry
on **stderr** after the write completes:

```
correction: W_COMPACT_REFUSED <field> -- <message>
```

Rationale: comments are I3 first-class content. Collapsing a Block to inline
form would silently drop them. The veto + audit-log pattern preserves both
the source content and a transparent record of where compact-mode could not
be applied.

##### Strategy A NFC contract for `baseline_bytes` (#377, #418)

When `format_style="preserve"` is engaged, the span-aware emitter slices
unchanged regions verbatim from a `baseline_bytes: bytes` value supplied
via `FormatOptions`. The slice path is only correct if `baseline_bytes`
satisfies the **post-NFC byte equality contract**:

> `baseline_bytes == octave_mcp.core.lexer.normalize_content(raw).encode("utf-8")`

where `raw` is the original file content. The reason is structural —
`tokenize()` applies fence-aware NFC normalisation via the internal
`_normalize_with_fence_detection` pass, and every `Token.start_byte` /
`Token.end_byte` (and the AST node spans derived from them) indexes the
NFC-normalised byte stream, **not** the raw on-disk bytes. A plain
`unicodedata.normalize("NFC", raw)` is **not equivalent** because the
fence-aware pass deliberately exempts literal-zone (fenced) content from
NFC. Passing un-normalised `baseline_bytes` would corrupt the slice
output for any document containing pre-NFC Unicode outside literal
zones.

The MCP `WriteTool` and CLI `write` command thread this contract
automatically via the internal `mcp.write._to_baseline_bytes()` helper.
**Python callers using `mcp.write._emit_with_style` directly** must
either:

* prefer `_to_baseline_bytes(raw_str)` (recommended — single source of
  truth, returns `None` on malformed baselines so the slice path
  degrades safely), OR
* call `from octave_mcp.core.lexer import normalize_content; baseline_bytes = normalize_content(raw).encode("utf-8")`.

The CE-identified hard constraints behind this contract are documented
in PR #418's commit history as **HC-1** (don't pass pre-NFC `str` to the
slice path), **HC-2** (`baseline_bytes` type is `bytes | None`, not
`str | None`), and **HC-3** (expose `normalize_content()` as a public
utility for write-pipeline callers).

##### `spans_valid_for_baseline` discriminator

`_emit_with_style(spans_valid_for_baseline=...)` is a structural
discriminator that must be `True` only when the parsed `Document` was
built from the same content that `baseline_bytes` represents — i.e.
changes-mode or normalize-mode where `doc = parse(baseline_content)`.
It must be `False` in content-mode where the caller supplied entirely
new content, because the doc's `start_byte`/`end_byte` values index the
NEW content's bytes, not the old baseline. Slicing the old baseline
with new-content spans would produce garbage; the discriminator forces
fall-through to canonical `emit()` in that case.

##### Multi-envelope documents (#420, PR #451)

As of **v1.13.0**, OCTAVE documents containing two or more sibling
top-level `===NAME===…===END===` envelopes round-trip without data loss.
Under `format_style="preserve"`, unchanged sibling envelopes (including
inter-envelope whitespace) slice verbatim from the baseline; only the
mutated envelope re-emits canonically. The `META.<field>` change-path
resolver targets envelope #1's META by construction — per-envelope
`META` scoping and atom mutation on additional envelopes are deferred
to v1.14+. See the [Multi-envelope documents](usage.md#workflow-5-multi-envelope-documents-v1130)
walkthrough in the Usage Guide for a worked example.

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

#### Multi-envelope documents (#420, PR #451 — v1.13.0)

Documents with two or more sibling top-level `===NAME===…===END===`
envelopes are parsed via the additive `Envelope` AST node introduced in
v1.13.0. Envelope #1 continues to populate `Document.name`,
`Document.meta`, and `Document.sections` exactly as before; sibling
envelopes (#2..N) become `Envelope` nodes appended to
`Document.additional_envelopes: list[Envelope]`. Each `Envelope` carries
its own name, sections, meta, independent `dirty` flag, baseline span
tracking, and `pre_trivia` byte-range fields used to preserve verbatim
inter-envelope whitespace under `format_style="preserve"`.

```python
from octave_mcp.core.parser import parse

content = (
    "===META===\nTYPE::FRAME_CARD\nSTATUS::proposed\n===END===\n\n"
    "===FRAME===\nTITLE::\"Worked example\"\n===END===\n"
)
doc = parse(content)
assert doc.name == "META"
assert len(doc.additional_envelopes) == 1
assert doc.additional_envelopes[0].name == "FRAME"
```

**v1.13.0 support surface:** parse + emit (round-trip byte-stable under
`format_style="preserve"`). **Deferred to v1.14+:** per-envelope `META`
scope in change-path resolution, and `changes`-mode atom mutation on
additional envelopes. The `META.<field>` change-path continues to mean
"envelope #1's META" by construction (see #449).

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

> **ADR-0006 SR1-T1 Step 6 (v1.12.0+):** The canonical validation surface is the class
> `Validator`. The historical module-level `validate()` function and `core.schema`
> delegator have been removed. See `docs/adr/adr-0006-sr1-t1-grammar-core-design.md`
> §3 row 6 + §2.2 module boundaries. The class API has been the supported pattern
> since v1.11.0.

#### `class Validator`

```python
class Validator:
    def __init__(self, schema: dict | None = None): ...
    def validate(
        self,
        doc: Document,
        strict: bool = False,
        section_schemas: dict[str, SchemaDefinition] | None = None,
    ) -> list[ValidationError]: ...
```

Validate a document against schema requirements.

**Constructor parameters:**
- `schema` (dict | None): Top-level schema dict (e.g. `{"META": {...}}`). May be omitted to skip schema-aware META validation.

**`validate()` parameters:**
- `doc` (Document): Parsed document to validate.
- `strict` (bool): If True, unknown META fields are errors; if False, warnings.
- `section_schemas` (dict | None): Optional dict mapping section names to `SchemaDefinition`. When provided, sections with matching keys are validated against their schema's constraints.

**Returns:**
- `list[ValidationError]`: List of validation errors (empty if valid)

**Example:**

```python
from octave_mcp.core.parser import parse
from octave_mcp.core.validator import Validator

schema = {"META": {"required": ["TYPE", "VERSION"], "fields": {...}}}
doc = parse(content)
errors = Validator(schema).validate(doc, strict=True)

if errors:
    for error in errors:
        print(f"{error.code}: {error.message} at {error.field_path}")
else:
    print("Valid")
```

#### `validate_frontmatter(raw_frontmatter, schema)` — parse-stage hook

Lives at `octave_mcp.core.grammar.entry` (re-exported from
`octave_mcp.core.grammar`). Validates YAML frontmatter against a
`SchemaDefinition`'s frontmatter field definitions.

```python
from octave_mcp.core.grammar.entry import validate_frontmatter
errors = validate_frontmatter(doc.raw_frontmatter, schema_def)
```

#### ValidationError Structure

```python
class ValidationError:
    code: str         # Error code (e.g., "UNKNOWN_FIELD")
    message: str      # Human-readable description
    field_path: str   # Location in document (e.g., "DECISION.STATUS")
    line: int         # Source line number (0 if not available)
    severity: str     # "error" or "warning" (default: "error")
```

#### Common Error Codes

- `UNKNOWN_FIELD`: Field not in schema (warning in non-strict, error in strict)
- `MISSING_REQUIRED`: Required field is absent
- `TYPE_MISMATCH`: Field value doesn't match expected type
- `ENUM_VIOLATION`: Value not in allowed enum set
- `INVALID_STRUCTURE`: Nested structure doesn't match schema

---

### Schema Module

> **ADR-0006 SR1-T1 Step 6 (v1.12.0+):** `octave_mcp.core.schema` has been
> **deleted**. The `Schema` container class has been relocated to
> `octave_mcp.schemas.repository` (co-located with its sole consumer
> `SchemaRepository`). The thin `validate()` delegator that lived in this
> module has been removed; use the class-based `Validator` API (above).

`octave_mcp.schemas.repository`

#### `class Schema`

A lightweight container for schema metadata used by `SchemaRepository`.
Validation is performed by `octave_mcp.core.validator.Validator`, which
accepts the schema as a dict.

```python
from octave_mcp.schemas.repository import Schema, SchemaRepository

schema = Schema(name="DECISION_LOG", version="1.0", fields={})
repo = SchemaRepository()
repo.register("DECISION_LOG", schema)
retrieved = repo.get("DECISION_LOG")
```

#### Schema field-definition shapes

The rich schema shapes consumed by `Validator` and `validate_frontmatter`
live in `octave_mcp.core.schema_extractor`:

- `SchemaDefinition` — full schema with fields, frontmatter, policies, targets.
- `FieldDefinition` — single field's pattern + constraints + target.
- `FrontmatterFieldDef` — YAML-frontmatter field definition.
- `extract_schema_from_document(doc) -> SchemaDefinition` — parse an
  OCTAVE schema document into the runtime shape.

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

### octave write — `--format-style` flag (GH#376 PR-A)

The `octave write` CLI command (which mirrors the `octave_write` MCP tool)
accepts a `--format-style` option with the same three modes documented in
[Format-style modes](#format-style-modes-gh376-pr-a) above:

```bash
octave write FILE --content '...' [--format-style {preserve|expanded|compact}]
octave write FILE --changes '{...}' [--format-style {preserve|expanded|compact}]
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--format-style` | choice | _(unset)_ | One of `preserve`, `expanded`, `compact`. Unset preserves today's canonical behaviour. See [Format-style modes](#format-style-modes-gh376-pr-a). |

When `--format-style=compact` is used, any `W_COMPACT_REFUSED` records are
surfaced on **stderr** (one line per refused collapse), in addition to the
normal stdout success information:

```
correction: W_COMPACT_REFUSED <field> -- <message>
```

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
