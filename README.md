# OCTAVE MCP Server

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-178%20passing-brightgreen.svg)]()
[![Coverage](https://img.shields.io/badge/coverage-90%25-brightgreen.svg)]()

This repository ships the **OCTAVE MCP Server**—a Model Context Protocol implementation that exposes the OCTAVE document protocol as deterministic tools. The MCP layer is delivery plumbing; the value is the OCTAVE protocol itself.

OCTAVE (Olympian Common Text And Vocabulary Engine) is a deterministic document format and control plane for LLM systems. It keeps meaning durable when text is compressed, routed between agents, or projected into different views.

- **Non-reasoning**: OCTAVE never guesses intent; it only accepts, validates, and projects what you declare.
- **Lenient → canonical**: ASCII aliases and flexible whitespace are accepted on ingest, then normalized to canonical Unicode with a logged repair tier.
- **Schema-anchored**: Data and schema blocks travel together so routing and validation remain explicit.
- **Auditable loss**: Compression and projections must declare what was dropped; nothing is silently tightened or weakened.

### Language, operators, and readability

- **Syntax**: Unicode-first operators (`→`, `⊕`, `⧺`, `⇌`, `∨`, `∧`, `§`) with ASCII aliases (`->`, `+`, `~`, `vs`, `|`, `&`, `§`) keep documents compact while staying typable everywhere.
- **Vocabulary**: Mythological terms are deliberate compression shorthands (e.g., `ICARIAN`, `SISYPHEAN`, `HUBRIS→NEMESIS`) that pack multiple related concepts into single tokens for higher semantic density.
- **Authoring**: Humans typically write in the lenient view and rely on `octave ingest` to normalize into canonical Unicode; both views stay human-auditable.

See the [protocol specs in `specs/`](specs/README.oct.md) for the precise operators, envelopes, and schema rules (v5.1.0).

## What this server provides

`octave-mcp` bundles the OCTAVE tooling as MCP tools and a CLI.

### Available via CLI

- **`octave ingest`** - normalize lenient OCTAVE to canonical form, validate against schemas, and log every change.
- **`octave eject`** - project canonical OCTAVE into multiple views (canonical, authoring, executive, developer) and formats (OCTAVE, JSON, YAML, Markdown) with declared loss tiers.
- **`octave validate`** - validate OCTAVE against schemas without modifying files.

### Available via MCP (3 tools)

- **`octave_validate`** - schema validation and parsing of OCTAVE content
- **`octave_write`** - unified file creation and modification (content mode OR changes mode with optional hash-based consistency checking)
- **`octave_eject`** - format projection (octave, json, yaml, markdown) with declared loss tiers

These tools make it easy for LLMs to emit minimal intent while relying on deterministic mechanics for structure and safety. If the LLM were replaced by a plain text emitter, OCTAVE would still provide value.

## When OCTAVE helps

Use OCTAVE when documents must survive multiple agent/tool hops, repeated compression, or auditing:

- coordination briefs, decision logs, or policy/control artifacts that circulate between agents
- reusable prompts or RAG artifacts that need stable structure across context windows
- documents that mix prose with routing/targets (e.g., §targets for tools or indexes)

It is usually overkill for one-off chat replies, casual notes, or prose that will never be reused or validated.

### Proven efficiency

- **Token reduction**: Benchmarks show OCTAVE documents use **32–46% of the tokens** of equivalent JSON, a **54–68% reduction** that grows with document complexity while preserving fidelity (see `docs/research/README.md`).
- **Model comprehension**: Zero-shot tests across Claude, GPT-4o, and Gemini families show an **average 90.7% comprehension rate** (88–96% range) of OCTAVE syntax without fine-tuning, validating the readability of the language choices (see `docs/research/README.md`).
- **Behavior under compression**: In comparative studies, calibrated OCTAVE agents produced higher-quality outputs than verbose baselines (9.3/10 vs 8.3/10), demonstrating that explicit compression controls avoid semantic loss (see `docs/research/subagent-compression-study.md`).

## Installing

### From PyPI

```bash
pip install octave-mcp
```

### From source

```bash
git clone https://github.com/elevanaltd/octave-mcp.git
cd octave-mcp
pip install -e .
```

## Quick start

### CLI

```bash
# Normalize and validate lenient OCTAVE
octave ingest document.oct.md --schema DECISION_LOG

# Project to a view/format
octave eject document.oct.md --mode executive

# Validate only
octave validate document.oct.md --schema DECISION_LOG --strict
```

### MCP setup

Use the setup script to configure common MCP clients:

```bash
./setup-mcp.sh --claude-desktop   # Claude Desktop
./setup-mcp.sh --claude-code      # Claude Code CLI
./setup-mcp.sh --codex            # OpenAI Codex CLI
./setup-mcp.sh --gemini           # Google Gemini CLI
./setup-mcp.sh --all              # Configure all

# Show copy/paste configuration without writing files
./setup-mcp.sh --show-config
```

See [docs/mcp-configuration.md](docs/mcp-configuration.md) for details.

### Python API

```python
from octave_mcp.core.parser import parse
from octave_mcp.core.emitter import emit
from octave_mcp.core.validator import validate

doc = parse(content)                 # lenient → AST
errors = validate(doc, strict=True)  # schema checks
canonical = emit(doc)                # canonical OCTAVE
```

## How the control plane works

OCTAVE separates semantic decisions (LLM/human) from mechanical guarantees (syntax, validation, projection, routing). The control plane is deterministic and non-reasoning:

```
REASONING (LLM / human)
  decides meaning, compression intent, routing
          │
          ▼
OCTAVE CONTROL PLANE
  normalizes, validates, classifies changes, projects
          │
          ▼
CANONICAL OCTAVE + VIEW PROJECTIONS
```

### Repair and change tiers

- **NORMALIZATION (always)**: mechanical fixes only (ASCII → Unicode, whitespace). Semantics preserved.
- **REPAIR (opt-in)**: schema-bounded coercions (enum casefold, type conversions). May adjust values but not invent structure or targets.
- **FORBIDDEN (never automatic)**: semantic inference or structure invention (target guessing, missing field insertion, semantic rewrites).

Every change is logged so you can audit how meaning moved through the system.

## Documentation

- [Usage guide](docs/usage.md)
- [API reference](docs/api.md)
- [MCP configuration](docs/mcp-configuration.md)
- [Protocol specs](specs/README.oct.md) – canonical operator, envelope, schema, and data rules

## Development

```bash
python -m venv .venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows
pip install -e ".[dev]"

# Quality gates
mypy src
ruff check src tests
black --check src tests
pytest
```
