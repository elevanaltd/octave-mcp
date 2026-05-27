# OCTAVE MCP Server - Usage Guide

This guide provides detailed examples and workflows for using the OCTAVE MCP server in production.

## Table of Contents

- [Installation & Setup](#installation--setup)
- [Command-Line Interface](#command-line-interface)
- [MCP Server Usage](#mcp-server-usage)
- [Python API](#python-api)
- [Common Workflows](#common-workflows)
- [Troubleshooting](#troubleshooting)

## Installation & Setup

### Prerequisites

- Python 3.11 or higher
- pip package manager

### Installation

#### From PyPI

```bash
pip install octave-mcp
```

#### From Source

```bash
git clone https://github.com/elevanaltd/octave-mcp.git
cd octave-mcp
pip install -e .
```

#### Verify Installation

```bash
octave --version
octave-mcp-server --help
```

## Command-Line Interface

The OCTAVE CLI provides three main commands: `ingest`, `eject`, and `validate`.

### `octave ingest` - Normalize lenient to canonical

The `ingest` command accepts lenient OCTAVE syntax and produces canonical output.

#### Basic Usage

```bash
octave ingest document.oct.md
```

#### With Schema Validation

```bash
octave ingest document.oct.md --schema DECISION_LOG
```

This validates the document against the `DECISION_LOG` schema and reports any violations.

#### With Automatic Repairs

```bash
octave ingest document.oct.md --schema DECISION_LOG --fix
```

The `--fix` flag enables TIER_REPAIR transformations:
- Enum casefolding (e.g., `"active"` → `ACTIVE`)
- Type coercion (e.g., `"42"` → `42`)
- Value normalization within schema bounds

#### Verbose Mode

```bash
octave ingest document.oct.md --verbose
```

Shows detailed pipeline stages:
1. Lexical analysis
2. Parsing
3. Normalization
4. Validation
5. Repair log

### `octave eject` - Generate projected views

The `eject` command transforms canonical OCTAVE into different formats and projection modes.

#### Projection Modes

```bash
# Canonical (default) - Full document, strict OCTAVE
octave eject document.oct.md --mode canonical

# Authoring - Lenient format for editing
octave eject document.oct.md --mode authoring

# Executive - High-level summary (status, risks, decisions)
octave eject document.oct.md --mode executive

# Developer - Implementation focus (tests, CI, dependencies)
octave eject document.oct.md --mode developer
```

#### Output Formats

```bash
# OCTAVE format (default)
octave eject document.oct.md --format octave

# JSON
octave eject document.oct.md --format json

# YAML
octave eject document.oct.md --format yaml

# Markdown
octave eject document.oct.md --format markdown
```

#### Combined Options

```bash
# Executive summary in Markdown
octave eject document.oct.md --mode executive --format markdown

# Developer view in JSON
octave eject document.oct.md --mode developer --format json
```

### `octave validate` - Schema validation

The `validate` command checks documents against schema requirements.

#### Basic Validation

```bash
octave validate document.oct.md --schema DECISION_LOG
```

#### Strict Mode

```bash
octave validate document.oct.md --schema DECISION_LOG --strict
```

In strict mode:
- Unknown fields trigger errors (not warnings)
- All required fields must be present
- All type constraints enforced

#### Validation Output

```bash
# Success
$ octave validate document.oct.md --schema DECISION_LOG
Valid

# Failure
$ octave validate document.oct.md --schema DECISION_LOG --strict
UNKNOWN_FIELD: Field 'EXTRA_DATA' not in schema
MISSING_REQUIRED: Field 'STATUS' is required
TYPE_MISMATCH: Field 'ID' must be string, got integer
```

## MCP Server Usage

The OCTAVE MCP server integrates with any MCP-compatible client (e.g., Claude Desktop, custom applications).

### Starting the Server

#### Standalone Mode

```bash
octave-mcp-server
```

The server runs on stdio and waits for MCP protocol messages.

#### From Configuration

Most MCP clients (like Claude Desktop) start the server automatically based on configuration.

### Available MCP Tools

The server exposes three tools: `octave_validate`, `octave_write`, and `octave_eject`.

#### `octave_validate` Tool

**Purpose:** Schema validation and parsing of OCTAVE content.

**Parameters:**
- `content` (optional): OCTAVE content to validate (mutually exclusive with `file_path`)
- `file_path` (optional): Path to OCTAVE file to validate (mutually exclusive with `content`)
- `schema` (required): Schema name for validation (e.g., `"DECISION_LOG"`)
- `fix` (optional): Apply repairs to canonical output - `true` or `false`

**Returns:**
```json
{
  "canonical": "DECISION:\n  ID::\"DEC-001\"\n  STATUS::APPROVED\n",
  "valid": true,
  "validation_errors": [],
  "repair_log": [
    {
      "tier": "NORMALIZATION",
      "location": "line 2",
      "original": "STATUS::\"approved\"",
      "canonical": "STATUS::APPROVED",
      "reason": "Enum casefold"
    }
  ]
}
```

**Example via Python MCP Client:**

```python
import asyncio
from mcp import Client

async def main():
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

asyncio.run(main())
```

#### `octave_write` Tool

**Purpose:** Unified entry point for writing OCTAVE files. Handles creation and modification.

**Parameters:**
- `target_path` (required): File path to write to
- `content` (optional): Full content for new files or overwrites
- `changes` (optional): Dictionary of field updates for existing files
- `schema` (optional): Schema name for validation
- `mutations` (optional): META field overrides
- `format_style` (optional, GH#376 PR-A): Output projection — `"preserve"`, `"expanded"`, or `"compact"`. Unset preserves today's canonical behaviour. See [API reference](api.md#format-style-modes-gh376-pr-a) for full mode semantics and the `W_COMPACT_REFUSED` audit record.

**Example:**

```python
# Create new file
result = await client.call_tool(
    "octave_write",
    {
        "target_path": "/path/to/decision.oct.md",
        "content": 'DECISION:\n  ID::"DEC-001"\n  STATUS::"approved"',
        "schema": "DECISION_LOG"
    }
)

# Modify existing file
result = await client.call_tool(
    "octave_write",
    {
        "target_path": "/path/to/decision.oct.md",
        "changes": {"STATUS": "APPROVED"}
    }
)
```

#### `octave_eject` Tool

**Purpose:** Generate tailored views from canonical OCTAVE.

**Parameters:**
- `content` (optional): Canonical OCTAVE (null for template generation)
- `schema` (required): Schema name for validation
- `mode` (optional): Projection mode - `"canonical"`, `"authoring"`, `"executive"`, `"developer"`
- `format` (optional): Output format - `"octave"`, `"json"`, `"yaml"`, `"markdown"`

**Returns:**
```json
{
  "output": "# Decision Summary\n\nID: DEC-001\nStatus: APPROVED\n",
  "lossy": true,
  "omitted_fields": ["RATIONALE", "ALTERNATIVES"]
}
```

**Example via Python MCP Client:**

```python
result = await client.call_tool(
    "octave_eject",
    {
        "content": canonical_octave,
        "schema": "DECISION_LOG",
        "mode": "executive",
        "format": "markdown"
    }
)

print(result["output"])
if result["lossy"]:
    print(f"Note: Omitted fields: {result['omitted_fields']}")
```

## Python API

For programmatic integration, use the Python API directly.

### Parsing

```python
from octave_mcp.core.parser import parse

content = """
DECISION:
  ID::"DEC-001"
  STATUS::"approved"
"""

doc = parse(content)
print(doc.root)  # Access parsed document tree
```

### Emitting

```python
from octave_mcp.core.emitter import emit

canonical = emit(doc)
print(canonical)
```

### Validation

> **ADR-0006 SR1-T1 Step 6 (v1.12.0+):** the canonical validation surface is the
> class `Validator`. The module-level `validate()` function has been removed —
> instantiate `Validator(schema)` and call `.validate(doc, ...)`.

```python
from octave_mcp.core.validator import Validator

errors = Validator(schema=None).validate(doc, strict=True)
if errors:
    for error in errors:
        print(f"{error.code}: {error.message}")
else:
    print("Valid")
```

### Full Pipeline

```python
from octave_mcp.core.parser import parse
from octave_mcp.core.validator import Validator
from octave_mcp.core.emitter import emit

# Input
lenient_content = """
DECISION:
  ID::"DEC-001"
  STATUS::"approved"
"""

# Parse
doc = parse(lenient_content)

# Validate (use Validator class API; v1.12.0+)
errors = Validator(schema=None).validate(doc, strict=False)
if errors:
    print(f"Validation errors: {errors}")

# Emit canonical
canonical = emit(doc)
print(canonical)
```

## Common Workflows

### Workflow 1: Document Creation

**Goal:** Create a new OCTAVE document from scratch.

```bash
# Step 1: Generate template
octave eject --schema DECISION_LOG --format authoring > decision.oct.md

# Step 2: Edit in your favorite editor
vim decision.oct.md

# Step 3: Validate
octave validate decision.oct.md --schema DECISION_LOG

# Step 4: Normalize to canonical
octave ingest decision.oct.md --schema DECISION_LOG > decision-canonical.oct.md
```

### Workflow 2: Document Review

**Goal:** Review a complex document with different stakeholders.

```bash
# For executive review
octave eject document.oct.md --mode executive --format markdown > executive-summary.md

# For developer review
octave eject document.oct.md --mode developer --format markdown > developer-detail.md

# For editing
octave eject document.oct.md --mode authoring > editable-version.oct.md
```

### Workflow 3: Automated Processing

**Goal:** Integrate OCTAVE processing into a CI/CD pipeline.

```bash
#!/bin/bash
set -e

# Validate all OCTAVE documents
find . -name "*.oct.md" | while read file; do
  echo "Validating $file..."
  octave validate "$file" --schema AUTO_DETECT --strict
done

# Normalize all documents
find . -name "*.oct.md" | while read file; do
  echo "Normalizing $file..."
  octave ingest "$file" --fix > "$file.canonical"
  mv "$file.canonical" "$file"
done

echo "All documents validated and normalized"
```

### Workflow 4: Multi-Agent Communication

**Goal:** Use OCTAVE for structured communication between AI agents.

```python
from octave_mcp.mcp.validate import ValidateTool
from octave_mcp.mcp.eject import EjectTool

async def agent_communication():
    validate = ValidateTool()
    eject = EjectTool()

    # Agent A creates a task
    task = """
    TASK:
      ID::"TASK-001"
      ASSIGNEE::"agent-b"
      PRIORITY::"high"
      DESCRIPTION::"Analyze performance metrics"
    """

    # Normalize and validate
    result = await validate.execute(
        content=task,
        schema="TASK",
        fix=True
    )

    canonical = result["canonical"]

    # Agent B receives and processes
    # ... work done ...

    # Agent B responds
    response = """
    TASK_RESULT:
      TASK_ID::"TASK-001"
      STATUS::"completed"
      FINDINGS::"Performance within acceptable range"
    """

    # Normalize response
    result = await validate.execute(
        content=response,
        schema="TASK_RESULT",
        fix=True
    )

    return result["canonical"]
```

### Workflow 5: Multi-envelope documents (v1.13.0)

**Goal:** Edit a single field inside a FRAME_CARD-style document that
contains multiple top-level envelopes, without disturbing sibling
envelopes.

A *multi-envelope document* is a single `.oct.md` file with two or more
top-level `===NAME===…===END===` envelopes — common for FRAME_CARDs,
decision packets, and other artifacts that group related-but-distinct
sections under one file. As of v1.13.0 (PR #451, closes #420),
multi-envelope documents round-trip byte-stable under
`format_style="preserve"`.

Worked example — a three-envelope FRAME_CARD with a status field flip:

```octave
===META===
TYPE::FRAME_CARD
ID::"FRAME-001"
STATUS::proposed
===END===

===FRAME===
TITLE::"Multi-envelope worked example"
SCOPE::"3-envelope demonstration document"
===END===

===NOTES===
NOTE_1::"Each top-level envelope is parsed as a sibling"
NOTE_2::"Unchanged envelopes slice verbatim under preserve mode"
===END===
```

Mutate `META.STATUS` in place:

```python
result = await client.call_tool("octave_write", {
    "target_path": "/path/to/frame-001.oct.md",
    "changes": {"META.STATUS": "ratified"},
    "format_style": "preserve",
})
```

Expected behaviour (empirically verified — input 321 bytes → output
321 bytes):

- A single-line surgical edit: `STATUS::proposed` → `STATUS::ratified`.
- The `===FRAME===` and `===NOTES===` sibling envelopes (and the blank
  lines between envelopes) are byte-identical to the input.
- Diff footprint matches `octave_write`'s Strategy A contract
  (≤0.5% of file size on representative documents).

**Mutate-in-place on flat `===META===` atoms (PR #449, closes #447).**
When the existing META envelope contains a flat-form atom like
`STATUS::proposed`, `changes={"META.STATUS": "ratified"}` mutates that
atom *in place* rather than injecting a duplicate nested-block atom
alongside it. This applies across `format_style ∈ {preserve, expanded,
compact, omitted}` and keeps change diffs minimal. The flat-atom scan
is gated on `doc.name == "META"`, so non-META envelopes containing
same-named atoms are unaffected.

**Deferred to v1.14+.** Per-envelope `META` scope in change-path
resolution (e.g. `FRAME.META.X`) and `changes`-mode atom mutation on
additional envelopes (#2..N) are intentionally **not** in v1.13.0 —
the `META.<field>` resolver targets envelope #1's META by construction.
Tracked under v1.14+ in [#420 follow-ups](https://github.com/elevanaltd/octave-mcp/issues/420).
For today, mutate additional envelopes via content-mode rewrite or by
serialising the parsed `Document.additional_envelopes` list yourself.

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'octave_mcp'"

**Cause:** Package not installed or virtual environment not activated.

**Solution:**
```bash
# Ensure package is installed
pip install octave-mcp

# Or install from source
pip install -e .
```

### Issue: "Unknown tool: octave_validate"

**Cause:** MCP server not properly configured in client.

**Solution:** Check your MCP client configuration (see [MCP Configuration Guide](mcp-configuration.md)).

### Issue: Validation errors with strict mode

**Cause:** Document has unknown fields or missing required fields.

**Solution:**
```bash
# Check what's wrong (non-strict mode shows warnings)
octave validate document.oct.md --schema DECISION_LOG

# Fix automatically if possible
octave ingest document.oct.md --schema DECISION_LOG --fix --verbose
```

### Issue: ASCII aliases not converting

**Cause:** Not using the `ingest` command (only `ingest` normalizes).

**Solution:**
```bash
# Wrong: validate doesn't normalize
octave validate document.oct.md

# Right: ingest normalizes first
octave ingest document.oct.md | octave validate --schema DECISION_LOG
```

### Issue: MCP server not starting

**Cause:** Missing dependencies or incorrect command.

**Solution:**
```bash
# Check installation
which octave-mcp-server

# Install with dependencies
pip install octave-mcp

# Check for errors
octave-mcp-server 2>&1 | tee server-log.txt
```

### Issue: Performance slow for large documents

**Cause:** Large documents may require optimization.

**Solution:**
- Use `--verbose` to identify bottlenecks
- Consider splitting large documents into smaller schemas
- Use projection modes (`executive`, `developer`) to work with subsets

### Getting Help

- **Documentation:** [docs/](.)
- **Issues:** [GitHub Issues](https://github.com/elevanaltd/octave-mcp/issues)
- **Discussions:** [GitHub Discussions](https://github.com/elevanaltd/octave-mcp/discussions)

---

## Migration: `format_style` across versions (v1.12 → v1.13 → v1.14)

`octave_write`'s `format_style` parameter is being rolled out in three stages
across v1.12.0, v1.13.0, and v1.14.0. This section documents the behaviour
matrix and the recommended upgrade path for callers.

### Behaviour matrix

| `format_style` value | v1.12.0 behaviour | v1.13.0 behaviour | v1.14.0 behaviour (planned) |
|---|---|---|---|
| _(parameter omitted)_ | Full canonical re-emit. Today's default. | **Unchanged** — full canonical re-emit. No warning. | **Flips to `"preserve"`** — span-aware preserve mode. No warning. |
| `None` *(explicit)* | Full canonical re-emit (same as omitted). | **Deprecated** — same full canonical re-emit behaviour, but emits a `DeprecationWarning` announcing the v1.14.0 flip. | Behaviour TBD; treat as removed. Pin an explicit string value. |
| `"preserve"` | Strategy C narrow short-circuit (`parse∘emit` identity). | **Strategy A span-aware preserve mode (#418).** Single-region slice-and-replace; clean nodes byte-identical to baseline. | Same as v1.13.0 (the new default). |
| `"expanded"` | AST lift `InlineMap` → `Block` form. | Unchanged. | Unchanged. |
| `"compact"` | AST collapse atom-only Blocks → inline-list; veto + `W_COMPACT_REFUSED` on comment-bearing subtrees. | Unchanged. | Unchanged. |
| unknown string | `E_INVALID_FORMAT_STYLE` | `E_INVALID_FORMAT_STYLE` | `E_INVALID_FORMAT_STYLE` |

### Recommended upgrade path

| If you are on v1.12.0 and you… | …recommended action for v1.13.0 |
|---|---|
| omit `format_style` and DO NOT care about the v1.14.0 default flip | No change required. Keep omitting. You will silently accept Strategy A preserve mode in v1.14.0. |
| omit `format_style` and DO care about byte-shape stability across the v1.14.0 flip | Pin an explicit value now. Pass `format_style="expanded"` if you want to keep v1.12.0 canonical re-emit behaviour, or `format_style="preserve"` if you want the future default. |
| pass `format_style=None` explicitly (e.g. from a wrapper that always sets it) | Replace with `format_style="expanded"` (keep current behaviour) **or** drop the explicit None (accept the future default silently). The explicit-None path will emit a `DeprecationWarning` in v1.13.0. |
| pass `format_style="preserve"` explicitly | No change. You will now benefit from Strategy A's single-region diffs (≤0.5% diff footprint) instead of Strategy C's narrow short-circuit. |
| pass `format_style="expanded"` or `format_style="compact"` explicitly | No change. Behaviour is preserved across the flip. |

### Silencing the `DeprecationWarning`

The v1.13.0 `DeprecationWarning` fires only when `format_style=None` is
passed *explicitly*. The cleanest way to silence it is to replace the
explicit `None` with the value that captures your intent:

```python
# Before — emits DeprecationWarning in v1.13.0:
result = await write_tool.execute(target_path=path, changes=changes, format_style=None)

# After — explicit pin, no warning, byte-shape stable across v1.14.0:
result = await write_tool.execute(target_path=path, changes=changes, format_style="expanded")
```

If you need to suppress the warning at the consumer level instead (e.g. a
library that wraps `octave_write` and cannot change its caller's code),
use the standard `warnings` filter:

```python
import warnings

with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="octave_mcp")
    result = await write_tool.execute(target_path=path, changes=changes, format_style=None)
```

This is **not recommended** as a long-term strategy — the underlying
behavioural flip still lands in v1.14.0. Use the explicit-pin upgrade
above as a permanent fix.

### CLI equivalent

The CLI surface mirrors the same contract. `octave write --format-style none`
is the explicit-None analogue and emits the deprecation warning; omitting
`--format-style` is silent. The behaviour matrix above applies identically.

---

For MCP configuration details, see [MCP Configuration Guide](mcp-configuration.md).
For API reference, see [API Reference](api.md).
