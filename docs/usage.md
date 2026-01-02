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

```python
from octave_mcp.core.validator import validate

errors = validate(doc, strict=True)
if errors:
    for error in errors:
        print(f"{error.code}: {error.message}")
else:
    print("Valid")
```

### Full Pipeline

```python
from octave_mcp.core.parser import parse
from octave_mcp.core.validator import validate
from octave_mcp.core.emitter import emit

# Input
lenient_content = """
DECISION:
  ID::"DEC-001"
  STATUS::"approved"
"""

# Parse
doc = parse(lenient_content)

# Validate
errors = validate(doc, strict=False)
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

For MCP configuration details, see [MCP Configuration Guide](mcp-configuration.md).
For API reference, see [API Reference](api.md).
