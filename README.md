# OCTAVE MCP Server

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-1610%20passing-brightgreen.svg)]()
[![Coverage](https://img.shields.io/badge/coverage-90%25-brightgreen.svg)]()

Production-grade MCP server implementing the **OCTAVE v6** document protocol: **Generative Holographic Contracts**.

## Table of Contents

- [For AI Agents](#for-ai-agents)
- [What It Does](#what-it-does)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [MCP Tools](#mcp-tools)
- [When OCTAVE Helps](#when-octave-helps)
- [Documentation](#documentation)
- [Contributing](#contributing)

---

## For AI Agents

```octave
===AGENT_BOOTSTRAP===
META:
  TYPE::BOOTSTRAP
  VERSION::"6.0"
  CONTRACT::HOLOGRAPHIC[
    VALIDATION::JIT_GRAMMAR
    ANCHOR::HERMETIC
  ]

GUIDANCE::AGENTS.oct.md
QUALITY_GATES::[mypy,ruff,black,pytest]
DEV_SETUP::docs/guides/development-setup.md
SPECS::src/octave_mcp/resources/specs/
SKILLS::src/octave_mcp/resources/skills/
PRIMERS::src/octave_mcp/resources/primers/

// Five core immutables that define OCTAVE's behavior
IMMUTABLES::[
  I1::SYNTACTIC_FIDELITY,     // Preserve semantic meaning exactly
  I2::DETERMINISTIC_ABSENCE,  // Distinguish absent vs null vs default
  I3::MIRROR_CONSTRAINT,      // Reflect only what exists, create nothing
  I4::TRANSFORM_AUDITABILITY, // Log every transformation with IDs
  I5::SCHEMA_SOVEREIGNTY      // Make validation status visible
]
===END===
```

---

## What It Does

This repository ships the **OCTAVE MCP Server** (v1.0.0)—a Model Context Protocol implementation that transforms OCTAVE documents from passive text into **Generative Holographic Contracts**.

OCTAVE (Olympian Common Text And Vocabulary Engine) is a deterministic document format and control plane for LLM systems. It keeps meaning durable when text is compressed, routed between agents, or projected into different views.

**Core Philosophy: Validation Precedes Generation**
Instead of checking if an LLM wrote a valid document *after* the fact, OCTAVE v6 compiles the document's `META` block into a strict grammar (Regex/GBNF) that *constrains* the LLM's output generation. It is structurally impossible to generate invalid syntax.

- **Generative Constraints**: `META.CONTRACT` compiles to regex/grammar for LLM guidance.
- **Holographic Sovereignty**: The document defines its own schema laws inline.
- **Hermetic Anchoring**: No network calls in the hot path. Standards are frozen or local.
- **Auditable Loss**: Compression tiers declared in `META` (`LOSSLESS`, `AGGRESSIVE`).

### Language, operators, and readability

- **Syntax**: Unicode-first operators (`→`, `⊕`, `⧺`, `⇌`, `∨`, `∧`, `§`) with ASCII aliases.
- **Vocabulary**: Mythological terms as semantic compression shorthands.
- **Authoring**: Humans write in the lenient view; tools normalize to canonical Unicode.

See the [protocol specs in `src/octave_mcp/resources/specs/`](src/octave_mcp/resources/specs/) for v6.0.0 rules.

## What this server provides

`octave-mcp` bundles the OCTAVE tooling as MCP tools and a CLI.

- **3 MCP tools**: `octave_validate`, `octave_write`, `octave_eject`
- **Generative Engine**: Compiles constraints to grammars (`debug_grammar=True`).
- **Hermetic Hydrator**: Resolves standards without network dependency.

## When OCTAVE Helps

Use OCTAVE when documents must survive multiple agent/tool hops, repeated compression, or auditing:

- **Self-Validating Agents**: Agents that define their own output grammar.
- **Coordination Briefs**: Decision logs that circulate between agents.
- **Compressed Context**: Reusable prompts needing stable structure (54–68% token reduction).

## Installation

**PyPI:**
```bash
pip install octave-mcp
# or
uv pip install octave-mcp
```

**From source:**
```bash
git clone https://github.com/elevanaltd/octave-mcp.git
cd octave-mcp
uv pip install -e ".[dev]"
```

## Quick Start

### CLI

```bash
# Validate and normalize (v6 auto-detection)
octave validate document.oct.md

# Write with validation (from content)
echo "===DOC===\nMETA:\n  TYPE::LOG\n  CONTRACT::GRAMMAR[...]\n..." | octave write output.oct.md --stdin

# Project to a view/format
octave eject document.oct.md --mode executive --format markdown
```

### MCP Setup

Add to Claude Desktop (`claude_desktop_config.json`) or Claude Code (`~/.claude.json`):

```json
{
  "mcpServers": {
    "octave": {
      "command": "octave-mcp-server"
    }
  }
}
```

## MCP Tools

| Tool | Purpose |
|------|---------|
| `octave_validate` | Schema validation + repair suggestions + grammar compilation |
| `octave_write` | Unified file creation/modification with validation |
| `octave_eject` | Format projection and template generation |

### `octave_validate`

Validates OCTAVE content against a schema and returns normalized canonical output.

```python
# Parameters
content: str          # OCTAVE content to validate (or use file_path)
file_path: str        # Path to file (mutually exclusive with content)
schema: str           # Schema name (e.g., 'META', 'SESSION_LOG')
fix: bool = False     # Apply repairs (enum casefold, type coercion)
profile: str          # Validation strictness: STRICT, STANDARD, LENIENT, ULTRA
diff_only: bool       # Return diff instead of full canonical (saves tokens)
compact: bool         # Return counts instead of full error lists
debug_grammar: bool   # Include compiled regex/GBNF grammar in output
```

**Returns**: `{ status, canonical, repairs, warnings, errors, validation_status }`

### `octave_write`

Unified write operation for creating new files or modifying existing ones.

```python
# Parameters
target_path: str      # File path to write
content: str          # Full content for new files (mutually exclusive with changes)
changes: dict         # Delta updates for existing files (tri-state: absent=no-op, DELETE=remove, value=set)
mutations: dict       # META field overrides
base_hash: str        # Expected SHA-256 for consistency check (CAS)
schema: str           # Schema name for validation
lenient: bool         # Enable lenient parsing with auto-repairs
corrections_only: bool # Dry run - return corrections without writing
```

**Returns**: `{ status, mode, canonical, repairs, warnings, errors, validation_status, file_hash }`

### `octave_eject`

Projects OCTAVE content to different formats and views.

```python
# Parameters
content: str          # OCTAVE content to project (null for template generation)
schema: str           # Schema name for validation or template generation
mode: str             # Projection: canonical, authoring, executive, developer
format: str           # Output: octave, json, yaml, markdown, gbnf
```

**Returns**: `{ output, lossy, fields_omitted, validation_status }`

### Generative Holographic Contracts (v6)

OCTAVE v6 introduces the **Holographic Contract**:
1.  **Read META**: The parser reads the `META` block first.
2.  **Compile Grammar**: It compiles the constraints (`REQ`, `ENUM`, `REGEX`) into a generative grammar.
3.  **Generate/Validate**: The body is generated/validated against this bespoke grammar.

## Documentation

| Doc | Content |
|-----|---------|
| [Usage Guide](docs/usage.md) | CLI, MCP, and API examples |
| [API Reference](docs/api.md) | Python API documentation |
| [MCP Configuration](docs/mcp-configuration.md) | Client setup and integration |
| [Protocol Specs](src/octave_mcp/resources/specs/) | v6.0.0 Generative Holographic Specs |
| [EBNF Grammar](docs/grammar/octave-v1.0-grammar.ebnf) | Formal v1.0.0 grammar specification |
| [Development Setup](docs/guides/development-setup.md) | Dev environment, testing, quality gates |
| [Architecture Decisions](docs/adr/) | Architecture Decision Records (ADRs) |
| [Research](docs/research/) | Benchmarks and validation studies |

### Architecture Immutables

| ID | Principle |
|----|-----------|
| **I1** | Syntactic Fidelity — normalization alters syntax, never semantics |
| **I2** | Deterministic Absence — distinguish absent vs null vs default |
| **I3** | Mirror Constraint — reflect only what's present, create nothing |
| **I4** | Transform Auditability — log every transformation with stable IDs |
| **I5** | Schema Sovereignty — validation status visible in output |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and guidelines.

```bash
# Quick dev setup
git clone https://github.com/elevanaltd/octave-mcp.git
cd octave-mcp
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# Run tests
pytest

# Quality checks
ruff check src tests && mypy src && black --check src tests
```

## License

Apache-2.0 — Built with [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk).
