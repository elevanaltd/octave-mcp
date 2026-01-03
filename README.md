# OCTAVE MCP Server

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-706%20passing-brightgreen.svg)]()
[![Coverage](https://img.shields.io/badge/coverage-87%25-brightgreen.svg)]()

Production-grade MCP server implementing the OCTAVE document protocol for deterministic, auditable AI communication.

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
GUIDANCE::AGENTS.oct.md
QUALITY_GATES::[mypy,ruff,black,pytest]
DEV_SETUP::docs/guides/development-setup.md
SPECS::specs/README.oct.md
IMMUTABLES::[I1,I2,I3,I4,I5]
===END===
```

---

## What It Does

This repository ships the **OCTAVE MCP Server**—a Model Context Protocol implementation that exposes the OCTAVE document protocol as deterministic tools. The MCP layer is delivery plumbing; the value is the OCTAVE protocol itself.

OCTAVE (Olympian Common Text And Vocabulary Engine) is a deterministic document format and control plane for LLM systems. It keeps meaning durable when text is compressed, routed between agents, or projected into different views.

- **Non-reasoning**: OCTAVE never guesses intent; it only accepts, validates, and projects what you declare.
- **Lenient → canonical**: ASCII aliases and flexible whitespace are accepted on ingest, then normalized to canonical Unicode with a logged repair tier.
- **Schema-anchored**: Data and schema blocks travel together so routing and validation remain explicit.
- **Auditable loss**: Compression and projections must declare what was dropped; nothing is silently tightened or weakened.

### Language, operators, and readability

- **Syntax**: Unicode-first operators (`→`, `⊕`, `⧺`, `⇌`, `∨`, `∧`, `§`) with ASCII aliases (`->`, `+`, `~`, `vs`, `|`, `&`, `§`) keep documents compact while staying typable everywhere.
- **Vocabulary**: Mythological terms are deliberate compression shorthands (e.g., `ICARIAN`, `SISYPHEAN`, `HUBRIS→NEMESIS`) that pack multiple related concepts into single tokens for higher semantic density.
- **Authoring**: Humans typically write in the lenient view and rely on `octave validate` to normalize into canonical Unicode; both views stay human-auditable.

See the [protocol specs in `specs/`](specs/README.oct.md) for the precise operators, envelopes, and schema rules (v5.1.0).

## What this server provides

`octave-mcp` bundles the OCTAVE tooling as MCP tools and a CLI.

- **3 MCP tools**: `octave_validate`, `octave_write`, `octave_eject`
- **CLI commands**: `octave validate`, `octave write`, `octave eject`
- **Deterministic**: Non-reasoning control plane for syntax, validation, projection
- **Loss accounting**: Every transformation logged with audit trails
- **Schema-anchored**: Validation travels with documents

## When OCTAVE Helps

Use OCTAVE when documents must survive multiple agent/tool hops, repeated compression, or auditing:

- Coordination briefs, decision logs, policy artifacts that circulate between agents
- Reusable prompts or RAG artifacts needing stable structure across context windows
- Documents mixing prose with routing/targets (e.g., §targets for tools or indexes)

**Proven efficiency:**
- **54–68% token reduction** vs equivalent JSON while preserving fidelity
- **90.7% comprehension rate** (zero-shot across Claude, GPT-4o, Gemini)
- **Higher quality outputs** (9.3/10 vs 8.3/10) when compression is explicit

See [docs/research/](docs/research/) for benchmarks and validation studies.

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
# Validate and normalize to canonical form
octave validate document.oct.md --schema DECISION_LOG

# Write with validation (from content)
echo "===DOC===\nKEY::value" | octave write output.oct.md --stdin --schema META

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

**Or use the setup script:**
```bash
./setup-mcp.sh --all              # Configure all clients
./setup-mcp.sh --show-config      # Show config for copy/paste
```

See [docs/mcp-configuration.md](docs/mcp-configuration.md) for advanced configuration.

## MCP Tools

| Tool | Purpose |
|------|---------|
| `octave_validate` | Schema validation + canonical normalization |
| `octave_write` | Unified file creation/modification (content OR delta changes) |
| `octave_eject` | Format projection (octave, json, yaml, markdown) |

### Repair Tiers

OCTAVE separates semantic decisions from mechanical guarantees through three repair tiers:

- **NORMALIZATION (always)**: ASCII→Unicode, whitespace (semantics preserved)
- **REPAIR (opt-in)**: Schema-bounded coercions (enum casefold, type conversion)
- **FORBIDDEN (never)**: Semantic inference, structure invention, target guessing

Every transformation is logged for auditability.

## Documentation

| Doc | Content |
|-----|---------|
| [Usage Guide](docs/usage.md) | CLI, MCP, and API examples |
| [API Reference](docs/api.md) | Python API documentation |
| [MCP Configuration](docs/mcp-configuration.md) | Client setup and integration |
| [Protocol Specs](specs/README.oct.md) | Canonical operators, envelopes, schema rules (v5.1.0) |
| [Development Setup](docs/guides/development-setup.md) | Dev environment, testing, quality gates |
| [Architecture](docs/architecture/) | Decision records and design docs |
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

# Run tests (706 passing, 87% coverage)
pytest

# Quality checks
ruff check src tests && mypy src && black --check src tests
```

## License

Apache-2.0 — Built with [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk).
