# AGENTS.md

This file provides guidance to AI coding assistants (Claude, Codex, Gemini, etc.) when working with this repository.

## Project Overview

**OCTAVE MCP Server** - A production-ready MCP (Model Context Protocol) server implementing the OCTAVE protocol for structured AI communication.

**OCTAVE** (Olympian Common Text And Vocabulary Engine) is a protocol that achieves 3-20x token reduction while maintaining clarity through structured syntax and mythological vocabulary.

## Repository Structure

```
.
├── src/octave_mcp/          # Python package (the MCP server)
│   ├── core/                # Parsing, validation, emission
│   ├── cli/                 # Command-line interface
│   ├── mcp/                 # MCP server tools (ingest, eject)
│   └── schemas/             # Schema definitions
├── specs/                   # OCTAVE protocol specifications (v5.1.0)
├── guides/                  # Usage documentation
├── tests/                   # Unit, integration, property tests
├── docs/                    # API docs, ADRs, configuration guides
├── examples/                # Example OCTAVE documents
├── evidence/                # Compression benchmarks, validation data
└── tools/                   # Python utilities
```

## Key Files

| File | Purpose |
|------|---------|
| `pyproject.toml` | Package configuration, dependencies |
| `setup-mcp.sh` | MCP server setup for AI clients |
| `README.md` | User-facing documentation |
| `SETUP.md` | Developer setup guide |
| `specs/octave-5-llm-core.oct.md` | Core OCTAVE syntax specification |
| `specs/octave-mcp-architecture.oct.md` | MCP server architecture |

## Development Commands

```bash
# Setup
source .venv/bin/activate
pip install -e ".[dev]"

# Quality gates (all must pass)
mypy src                    # Type checking (strict)
ruff check src tests        # Linting
black --check src tests     # Formatting
pytest                      # Tests with coverage

# CLI tools
octave ingest FILE          # Normalize OCTAVE document
octave eject FILE           # Project to different formats
octave validate FILE        # Validate against schema
```

## Code Style

- **Python 3.11+** with full type hints (mypy strict mode)
- **120 character** line length (black/ruff configured)
- **TDD workflow**: Write tests first, then implementation
- **Conventional commits**: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`

## Architecture Principles

### Spec-Static, Schema-Dynamic

- **Hardcoded (never configure)**: Core grammar, operators, repair tiers, error codes
- **Configurable**: Schema definitions, projection modes, validation rules

### Three-Tier Repair Classification

1. **NORMALIZATION** (always): ASCII→Unicode, whitespace fixes
2. **REPAIR** (opt-in): Enum casefold, type coercion
3. **FORBIDDEN** (never): Semantic inference, missing field insertion

## Version Control Rules

### Single Source of Truth
- **NEVER** create file variants (`spec-v2.md`, `config-UPDATED.yaml`)
- **ALWAYS** modify files in-place; update VERSION field inside document
- Let Git handle version history

### Public Repository Guidelines
- No personal information, API keys, or credentials
- No machine-specific paths (use relative paths)
- No internal/proprietary references
- Professional commit messages focused on OCTAVE/MCP development

## Testing

```bash
pytest tests/unit/           # Fast unit tests
pytest tests/integration/    # End-to-end tests
pytest tests/properties/     # Property-based (hypothesis)
pytest -k "test_lexer"       # Run specific tests
pytest --cov-report=html     # Generate coverage report
```

## Common Tasks

### Adding a New Feature
1. Write failing test in `tests/unit/`
2. Implement in `src/octave_mcp/`
3. Ensure `mypy src && ruff check src && pytest` pass
4. Commit with `feat: description`

### Fixing a Bug
1. Write test that reproduces the bug
2. Fix the code
3. Verify test passes
4. Commit with `fix: description`

### Modifying OCTAVE Syntax
1. Update specification in `specs/`
2. Update lexer/parser in `src/octave_mcp/core/`
3. Add test cases
4. Update documentation

## MCP Server Integration

The package provides three MCP tools:

- **octave_validate**: Schema validation and parsing of OCTAVE content
- **octave_write**: Unified file creation and modification (content mode OR changes mode)
- **octave_eject**: Format projection (octave, json, yaml, markdown)

Configure with `./setup-mcp.sh` for Claude Desktop, Claude Code, Codex, or Gemini.

## Claude Code Skills

Three specialized skills enhance Claude Code's capabilities for OCTAVE work:

### 1. **octave-literacy** (Foundation)
**Purpose**: Fundamental reading and writing capability for the OCTAVE format.

Provides:
- Core syntax and operators
- Critical formatting rules
- Basic structural competence

**Triggers**: `octave format`, `write octave`, `octave syntax`, `structured output`

**When to use**: Agents need basic OCTAVE competence without architectural overhead

### 2. **octave-compression** (Workflow)
**Purpose**: Specialized workflow for transforming verbose prose into semantic OCTAVE structures.

Provides:
- 4-phase compression transformation
- Token reduction strategies (60-80% target)
- Fidelity preservation rules
- Anti-patterns to avoid

**Requires**: Load `octave-literacy` first

**Triggers**: `compress to octave`, `semantic compression`, `documentation refactoring`

**When to use**: Refactoring documentation or generating compressed knowledge artifacts

### 3. **octave-mastery** (Advanced)
**Purpose**: Advanced semantic vocabulary and architectural patterns.

Provides:
- Semantic Pantheon (mythological vocabulary)
- Narrative dynamics patterns
- System forces and dynamics
- Advanced syntax (holographic, inline objects)
- Anti-patterns and smells

**Requires**: Load `octave-literacy` first

**Triggers**: `octave architecture`, `agent design`, `semantic pantheon`, `advanced octave`

**When to use**: Designing agents, crafting high-density specifications, system architecture

### Skill Usage Pattern

```bash
# Load foundation skill
octave-literacy

# Then load either/both specialized skills
octave-compression  # For document refactoring
octave-mastery      # For advanced design
```

For Claude Code users, these skills integrate into your workspace and activate via keyword triggers automatically.

## Architectural Layers & Ownership

The system is organized into three layers with clear responsibility boundaries:

- **L1 (OCTAVE Repository)**: Owns language specification, syntax, operators, and profiles
- **L2 (Orchestration Layer)**: Owns governance tooling, prompt assembly, context injection (e.g., HestAI-MCP)
- **L3 (Project Layer)**: Owns role definitions, local policies, success criteria

See **`specs/octave-5-llm-agents.oct.md` (§0::OWNERSHIP_AND_BOUNDARIES)** for the complete architectural breakdown and responsibility allocation.

## Resources

- **Quick Reference**: `guides/llm-octave-quick-reference.oct.md`
- **Core Spec**: `specs/octave-5-llm-core.oct.md`
- **Architecture**: `specs/octave-5-llm-agents.oct.md` (layer ownership and boundaries)
- **API Docs**: `docs/api.md`
- **MCP Setup**: `docs/mcp-configuration.md`
