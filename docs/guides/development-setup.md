# OCTAVE MCP Server - Development Setup

## Project Status

This is the OCTAVE MCP Server (v0.6.1) - a lenient-to-canonical pipeline for structured AI communication using the OCTAVE protocol.

**Version**: 0.6.1
**Python**: >=3.11
**License**: Apache 2.0

## Quick Start

### 1. Activate Virtual Environment

The project uses `uv` for environment management. Activate the pre-configured venv:

```bash
source .venv/bin/activate
```

Verify the environment:
```bash
python --version  # Should be 3.11.x
which python      # Should point to .venv/bin/python
```

### 2. Install Package in Development Mode

```bash
pip install -e ".[dev]"
```

This installs:
- **Core**: `mcp>=1.0.0`, `click>=8.0.0`, `pydantic>=2.0.0`
- **Development**: `pytest`, `pytest-cov`, `mypy`, `ruff`, `black`, `hypothesis`

### 3. Verify Installation

```bash
# Check package
python -c "import octave_mcp; print(f'OCTAVE MCP {octave_mcp.__version__}')"

# Check CLI command
octave --version

# Check MCP server entrypoint
octave-mcp-server --help
```

### 4. Run Quality Checks

```bash
# Type checking (strict mode)
mypy src

# Linting
ruff check src tests

# Code formatting
black --check src tests

# Tests with coverage
pytest --cov=octave_mcp
```

## Project Structure

```
.
├── pyproject.toml              # Package configuration
├── setup-mcp.sh                # MCP server setup script for AI clients
├── src/octave_mcp/
│   ├── __init__.py             # Package root (version: 0.6.1)
│   ├── core/                   # Core parsing/validation
│   │   ├── lexer.py           # ASCII normalization → Unicode
│   │   ├── parser.py          # Lenient parser + envelope completion
│   │   ├── emitter.py         # Canonical OCTAVE emission
│   │   ├── schema.py          # Schema definitions
│   │   ├── validator.py       # Schema validation
│   │   ├── repair.py          # Tier-based repair classification
│   │   ├── projector.py       # Projection modes (executive/developer/etc)
│   │   ├── ast_nodes.py       # AST node definitions
│   │   └── repair_log.py      # Repair transformation logging
│   ├── cli/                    # Command-line interface
│   │   └── main.py            # `octave` CLI: ingest/eject/validate
│   ├── mcp/                    # MCP server implementation
│   │   ├── server.py          # MCP server entry point
│   │   ├── base_tool.py       # Base MCP tool class
│   │   ├── validate.py        # octave_validate tool
│   │   ├── write.py           # octave_write tool
│   │   └── eject.py           # octave_eject tool
│   └── schemas/                # Schema management
│       ├── loader.py          # Schema loading
│       ├── repository.py      # Schema repository
│       └── builtin/           # Built-in schemas (minimal)
├── tests/
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   └── properties/             # Property-based tests (hypothesis)
├── docs/
│   ├── adr/                    # Architecture Decision Records
│   ├── api.md                  # API documentation
│   ├── mcp-configuration.md    # MCP setup guide
│   ├── usage.md                # Usage examples
│   └── configurability-analysis.md  # Schema/projection architecture
├── src/octave_mcp/resources/specs/                      # OCTAVE protocol specifications
│   ├── octave-core-spec.oct.md
│   ├── octave-data-spec.oct.md
│   ├── octave-schema-spec.oct.md
│   ├── octave-execution-spec.oct.md
│   └── octave-mcp-architecture.oct.md
└── .venv/                      # Python 3.11 virtual environment (uv-managed)
```

## Running Tests

### Full Test Suite

```bash
# All tests with coverage
pytest

# Specific test category
pytest tests/unit/
pytest tests/integration/
pytest tests/properties/
```

### Test Configuration

Tests are configured in `pyproject.toml`:
- Coverage target: `octave_mcp` package
- Asyncio mode: auto
- Report format: term-missing

See `pytest.ini` section in `pyproject.toml` for details.

## Code Quality Standards

All code must pass these checks before commit:

```bash
# Type safety (mypy strict)
mypy src
✓ No errors allowed

# Linting (ruff)
ruff check src tests
✓ No violations allowed

# Formatting (black)
black --check src tests
✓ Must match project style (120 char line length)

# Testing
pytest
✓ All tests must pass
```

### Pre-commit Hooks

The project uses pre-commit hooks (see `.pre-commit-config.yaml`):
- Trailing whitespace
- End-of-file fixers
- YAML validation
- Large file detection

Hooks run automatically on `git commit`. Bypass with `git commit --no-verify` (not recommended).

## Development Workflow

### Adding New Code

Follow Test-Driven Development (TDD):

1. **RED**: Write failing test first
   ```bash
   pytest tests/unit/test_new_feature.py -v
   ```

2. **GREEN**: Implement minimal code to pass
   ```python
   # src/octave_mcp/core/new_feature.py
   def new_feature() -> str:
       return "implementation"
   ```

3. **REFACTOR**: Improve while tests still pass
   ```bash
   pytest tests/unit/test_new_feature.py -v
   mypy src
   ruff check src
   ```

4. **COMMIT**: Create conventional commit
   ```bash
   git commit -m "feat: Add new feature with tests"
   ```

### Conventional Commit Messages

- `feat:` - New feature
- `fix:` - Bug fix
- `test:` - Test additions/changes
- `refactor:` - Code reorganization (no functional change)
- `docs:` - Documentation updates
- `chore:` - Maintenance (deps, config, etc)

Example:
```
test: Add tests for lenient parser with edge cases
feat: Implement lenient parser with envelope completion
docs: Update API reference for parser module
```

## Dependencies

### Core Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| mcp | >=1.0.0 | Model Context Protocol SDK |
| click | >=8.0.0 | CLI framework |
| pydantic | >=2.0.0 | Data validation |
| python-dotenv | >=1.0.0 | Environment config |

### Development Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| pytest | >=7.0.0 | Test runner |
| pytest-cov | >=4.0.0 | Coverage reporting |
| pytest-asyncio | >=0.21.0 | Async test support |
| mypy | >=1.0.0 | Type checking (strict) |
| ruff | >=0.1.0 | Fast linting |
| black | >=23.0.0 | Code formatting |
| hypothesis | >=6.0.0 | Property-based testing |
| pre-commit | >=3.0.0 | Git hooks |

Install all development dependencies with `pip install -e ".[dev]"`.

## Entry Points

The package provides two CLI commands:

### 1. OCTAVE CLI Tool

```bash
octave ingest document.oct.md --schema DECISION_LOG
octave eject document.oct.md --mode executive --format markdown
octave validate document.oct.md --schema DECISION_LOG --strict
```

Implemented in: `src/octave_mcp/cli/main.py`

### 2. MCP Server

```bash
octave-mcp-server
```

Runs the MCP server for AI client integration.

**Automatic Setup (recommended):**

Use the setup script to automatically configure all supported AI clients:

```bash
./setup-mcp.sh              # Interactive setup
./setup-mcp.sh --all        # Configure all clients at once
./setup-mcp.sh --show-config # Show copy/paste configuration
```

**Supported clients:**
- Claude Desktop (macOS, Linux, Windows/WSL)
- Claude Code CLI
- OpenAI Codex CLI
- Google Gemini CLI

**Manual configuration:**

For Claude Desktop, add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "octave": {
      "command": "/path/to/octave/.venv/bin/python",
      "args": ["/path/to/octave/src/octave_mcp/mcp/server.py"]
    }
  }
}
```

Run `./setup-mcp.sh --show-config` to get the exact paths for your system.

Implemented in: `src/octave_mcp/mcp/server.py`

## Common Tasks

### Run a Single Test File

```bash
pytest tests/unit/test_lexer.py -v
```

### Run Tests Matching a Pattern

```bash
pytest -k "test_normalization" -v
```

### Generate Coverage Report

```bash
pytest --cov=octave_mcp --cov-report=html
# Open: htmlcov/index.html
```

### Format Code Automatically

```bash
black src tests
```

### Fix Linting Issues Automatically

```bash
ruff check src tests --fix
```

### Type Check a Single File

```bash
mypy src/octave_mcp/core/lexer.py
```

## Troubleshooting

### Import Error: "No module named 'octave_mcp'"

**Problem**: The package isn't installed in the venv.

**Solution**:
```bash
source .venv/bin/activate
pip install -e .
```

### pytest Not Finding Tests

**Problem**: pytest is using wrong Python interpreter.

**Solution**:
```bash
source .venv/bin/activate
which pytest  # Should be .venv/bin/pytest
pytest        # Should work now
```

### mypy "strict mode" Errors

**Problem**: Type hints missing or incorrect.

**Solution**:
- Add return type hints: `def func() -> str:`
- Add parameter types: `def func(x: int) -> str:`
- Import types: `from typing import Any, Optional`

See `mypy.ini` for strict configuration.

### Black/Ruff Conflicts

**Problem**: Code format disagreement.

**Solution**:
```bash
black src tests  # Format first
ruff check src tests --fix  # Then lint
```

Black's 120 character line length is configured in `pyproject.toml`.

## Architecture Notes

- **Core Pipeline**: ASCII input → Lenient parser → Canonical AST → Schema validation → Repair classification
- **Repair Tiers**: NORMALIZATION (always) → REPAIR (opt-in) → FORBIDDEN (never)
- **Projection Modes**: Schema-aware filtering for different stakeholders (executive, developer, authoring, canonical)
- **Type Safety**: Mypy strict mode enforced - all code is fully typed

See `docs/configurability-analysis.md` for detailed architectural decisions.

## Resources

- **Protocol Specs**: `src/octave_mcp/resources/specs/octave-core-spec.oct.md` (syntax and operators)
- **Architecture**: `src/octave_mcp/resources/specs/octave-mcp-architecture.oct.md` (MCP integration design)
- **API Guide**: `docs/api.md` (detailed API reference)
- **MCP Setup**: `docs/mcp-configuration.md` (Claude Desktop integration)
- **Usage**: `docs/usage.md` (practical examples)

## Support

- **Issues**: [GitHub Issues](https://github.com/elevanaltd/octave-mcp/issues)
- **Discussions**: [GitHub Discussions](https://github.com/elevanaltd/octave-mcp/discussions)
- **License**: [Apache 2.0](https://opensource.org/licenses/Apache-2.0)

---

*OCTAVE MCP Server - Deterministic, auditable, and efficient AI communication*
