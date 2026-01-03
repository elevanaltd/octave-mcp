# Contributing to OCTAVE MCP

Thank you for your interest in contributing!

## Development Setup

```bash
# Clone and install
git clone https://github.com/elevanaltd/octave-mcp.git
cd octave-mcp
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
```

See [docs/guides/development-setup.md](docs/guides/development-setup.md) for detailed setup instructions.

## Testing

```bash
# Run all tests (706 passing, 87% coverage required)
pytest

# Run with coverage report
pytest --cov=octave_mcp --cov-report=term-missing

# Run specific test categories
pytest tests/unit/           # Fast unit tests
pytest tests/integration/    # End-to-end tests
pytest tests/properties/     # Property-based (hypothesis)
```

## Quality Checks

All checks must pass before merging:

```bash
# Linting
ruff check src tests

# Type checking (strict mode)
mypy src

# Formatting
black --check src tests
```

Or run everything:

```bash
ruff check src tests && mypy src && black --check src tests
```

## Code Style

- **Python**: 3.11+, strict mypy, ruff + black formatting
- **Line length**: 120 characters
- **TDD workflow**: Write tests first, then implementation
- **Conventional commits**: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add new MCP tool for X
fix: correct turn validation logic
docs: update README quick start
test: add coverage for lenient parsing
refactor: simplify repair classification
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Make your changes with tests
4. Ensure all quality checks pass
5. Submit a PR with clear description

## Architecture Immutables

These principles are unchangeable — PRs that violate them will be rejected:

| ID | Principle | What It Means |
|----|-----------|---------------|
| **I1** | Syntactic Fidelity | Normalization alters syntax, never semantics |
| **I2** | Deterministic Absence | Distinguish absent vs null vs default |
| **I3** | Mirror Constraint | Reflect only what's present, create nothing |
| **I4** | Transform Auditability | Log every transformation with stable IDs |
| **I5** | Schema Sovereignty | Validation status visible in output |

## Project Structure

```
octave-mcp/
├── src/octave_mcp/
│   ├── core/         # Parsing, validation, emission
│   ├── cli/          # Command-line interface
│   ├── mcp/          # MCP server tools
│   └── schemas/      # Schema definitions
├── tests/
│   ├── unit/         # Fast isolated tests
│   ├── integration/  # End-to-end tests
│   └── properties/   # Property-based (hypothesis)
├── specs/            # OCTAVE protocol specifications (v5.1.0)
├── docs/             # Documentation
│   ├── guides/       # Usage and development guides
│   ├── architecture/ # Decision records
│   └── research/     # Benchmarks and studies
└── examples/         # Example OCTAVE documents
```

## What We're Looking For

- **Bug Fixes**: Issues in parser, validator, or MCP tools
- **Test Coverage**: Expand unit/integration/property tests
- **Documentation**: Clarify guides, add examples
- **Performance**: Optimize lexer, parser, or emitter
- **Examples**: Real-world OCTAVE document patterns

## Guidelines

- **No file variants** (`spec-v2.md`, `config-UPDATED.yaml`) — modify in-place, let Git handle history
- **No semantic inference** in parser/validator — OCTAVE is non-reasoning
- **All transformations logged** via RepairLog for auditability
- **Test everything** — TDD workflow required

## Questions?

Open an issue or start a Discussion on GitHub.

Thank you for helping make OCTAVE better!
