# OCTAVE MCP Server

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-3003%20passing-brightgreen.svg)]()
[![PyPI](https://img.shields.io/pypi/v/octave-mcp.svg)](https://pypi.org/project/octave-mcp/)

**Deterministic document infrastructure for LLM pipelines.** Canonicalization, schema validation, grammar compilation, and MCP tools for durable AI artifacts.

```bash
pip install octave-mcp
```

---

This README serves three audiences. We know that's unusual, and we're being upfront about it — because the project itself sits at the intersection of all three.

| If you are... | Jump to |
|---------------|---------|
| An engineer evaluating this for production | [For Engineers](#for-engineers) |
| A researcher interested in what's novel here | [For Researchers](#for-researchers) |
| An AI agent that needs to read/write OCTAVE | [For AI Agents](#for-ai-agents) |

---

## For Engineers

OCTAVE is a structured document format with an MCP server and CLI. Documents normalise to a single canonical form, validate against their own schema, and log every transformation. It's infrastructure for AI documents that need to survive compression, multi-agent handoffs, and auditing. The writing standard inside the container is [PITH](src/octave_mcp/resources/specs/pith-spec.md): plain words, exact identifiers, hedges kept. OCTAVE is the strict container around it: schema validation, a repair log and loss receipts.

### Quick example: what changes

Ask an LLM to summarise a project status and you get prose:

```text
The auth migration has been running for three sprints and keeps hitting
the same problems. There's a security audit in six weeks — the auditors
specifically flagged session management as a priority area. We've burned
through 60% of the quarterly budget on this migration alone.
```

Ask another LLM to restate that in English and it will paraphrase — silently dropping facts, merging details, escalating "priority area" to "vulnerability." That's not a bug in the LLM. It's what prose invites: retelling.

OCTAVE structures the same information as labelled fields, written in PITH:

```octave
MIGRATION::"auth migration running for three sprints"
PROBLEMS::"keeps hitting the same problems"
AUDIT::"security audit in six weeks"
FLAGGED::"auditors specifically flagged session management as a priority area"
BUDGET::"`60%` of the quarterly budget burned on this migration alone"
```

Each fact sits in its own labelled field, in plain words, with its numbers and its hedges copied exactly. There is no narrative to retell, so there is less for a later reader to merge or escalate. See the [PITH specification](src/octave_mcp/resources/specs/pith-spec.md) for the rules and the evidence behind each one.

Documents written earlier with operators or mythology terms stay readable: the parser still reads them, and normalisation changes syntax, never meaning (North Star I1 and I3). New documents are written in plain words instead. [Why](#pith-the-writing-standard).

If an LLM writes it slightly wrong (extra spaces, or an ASCII operator where the Unicode form is canonical), the normaliser autocorrects and gives you a receipt:

```
normalization: '->' → '→' at line 3
```

Same input, same output, every time. That's what deterministic means.

### What you get

- **Canonical normalisation** — Same input, same output, always. Idempotent. Two agents independently producing the same document get a byte-for-byte match.

- **Schema validation with receipts** — Documents carry their schema inline. Validation returns specific field errors. Every repair is logged with stable IDs — you know exactly what changed and why.

- **Controlled compression with loss accounting** — Choose a tier (LOSSLESS, CONSERVATIVE, AGGRESSIVE) and the system declares what's preserved and what's dropped. Prose paraphrasing loses facts silently; OCTAVE makes every trade-off explicit. [Evidence](docs/research/compression-fidelity-round-trip-study.md).

- **Grammar compilation** — Schema constraints compile to GBNF grammars for llama.cpp-compatible backends. Constrain LLM generation at decode time.

- **Optional YAML frontmatter + OCTAVE body in one pass** — Platform-deployed skill and agent files can include YAML headers for tool discovery alongside structured OCTAVE bodies. `octave_write` validates both in a single operation. YAML is optional for hub/system files consumed by the anchor ceremony.

- **Literal zones** — Fenced code blocks pass through with zero processing. No normalisation, no escaping.

- **HTTP + stdio transport** — Stdio by default, Streamable HTTP with DNS rebinding protection and health checks for web deployments.

### Install

```bash
pip install octave-mcp
```

**Claude Code** (`~/.claude.json`) or **Claude Desktop** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "octave": {
      "command": "octave-mcp-server"
    }
  }
}
```

**HTTP:**
```bash
octave-mcp-server --transport http --port 8080
```

### MCP Tools

| Tool | What it does |
|------|-------------|
| `octave_validate` | Validate against schema. Field errors, repair suggestions, zone coverage |
| `octave_write` | Write files through the full validation pipeline. `mode: normalize` for dry-run |
| `octave_eject` | Project to different views — canonical, executive summary, developer, template |
| `octave_compile_grammar` | Compile schema constraints to GBNF grammar for constrained generation |

### CLI

```bash
octave validate document.oct.md
octave write output.oct.md --stdin
octave eject document.oct.md --mode executive --format markdown
```

### When to use it

- Documents passing through multiple agents, tools, or compression steps
- Agent and skill files with optional YAML discovery headers + structured content
- Decision logs, coordination briefs, audit trails
- System prompts and reference docs where token cost matters

**Not the right tool** for single-step prompts, freeform prose, or code output.

### Docs

| Doc | Content |
|-----|---------|
| [Usage Guide](docs/usage.md) | CLI, MCP, and API examples |
| [API Reference](docs/api.md) | Python API |
| [MCP Configuration](docs/mcp-configuration.md) | Client setup and integration |
| [Development Setup](docs/guides/development-setup.md) | Testing, quality gates, contributing |
| [EBNF Grammar](docs/grammar/octave-v1.0-grammar.ebnf) | Formal grammar spec |
| [Architecture Decisions](docs/adr/) | ADRs |

---

## For Researchers

### Self-describing artifacts

Most structured output validates at a single point and then becomes a plain object. OCTAVE documents are different — the schema, compression tier, and transformation log travel *with* the document. A downstream agent doesn't infer integrity; it reads it.

This creates a property that JSON Schema or Pydantic don't give you: the validation receipt is part of the artifact, not external to it.

### Grammar compilation from inline constraints

A document's `META.CONTRACT` block compiles to a GBNF grammar that can constrain LLM generation at decode time. The schema doesn't just validate output after the fact — it can shape generation while it happens. This bridges the gap between "check if it's valid" and "make it valid by construction."

### PITH: the writing standard

Two architectural ideas, and one decision about language.

OCTAVE once leaned on operators and mythology terms as a compression vocabulary. Bench results recorded in the [PITH specification](src/octave_mcp/resources/specs/pith-spec.md) (Plain vocabulary) reported that mythology used as writing escalated when misapplied, and allows an established idiom only where its dictionary sense fits exactly. So the project retires mythology as instruction vocabulary and as keys. The project keeps the container and replaces the writing standard.

PITH is the standard for every sentence, item, step and quoted value an agent writes, in any document shape:

- Note form in plain words, one fact per line.
- Identifiers, numbers and SHAs copied exactly, in backticks.
- Hedges copied verbatim; `none` or `not known` for an empty slot, never an invented value.
- Relations written in words, not with operators.
- Contradictions kept and flagged.

PITH is not a file format or a compression scheme. OCTAVE is one container it sits inside; the container adds the schema, the repair log and the loss receipts. Existing documents that use operators or mythology stay readable under the parser, which is the point of the mirror constraint (I3): it reflects what is present and creates nothing.

Evidence, evidence classes and the checks for each rule: [PITH specification](src/octave_mcp/resources/specs/pith-spec.md). The earlier study is kept for the record: [mythology study (superseded)](docs/guides/mythological-compression.md) | [Compression Fidelity Study](docs/research/compression-fidelity-round-trip-study.md).

---

## For AI Agents

Write in PITH: note form in plain words, identifiers copied exactly in backticks, hedges kept, relations in words, `none` or `not known` for an empty slot. The rules are in the [PITH specification](src/octave_mcp/resources/specs/pith-spec.md). The syntax primer is `src/octave_mcp/resources/primers/octave-literacy-primer.oct.md`.

A value in PITH:

```octave
STATUS::"blocked; the lockfile change is not confirmed"
EVIDENCE::"measured at `9c58708f`: `195` tests pass"
```

Documents you receive may still use operators or mythology terms. Read them by their plain meaning; do not write operators and mythology as instruction vocabulary or keys.

**Working on this codebase:**
```octave
===AGENT_BOOTSTRAP===
QUALITY_GATES::[mypy,ruff,black,pytest]
SPECS::src/octave_mcp/resources/specs/
PRIMERS::src/octave_mcp/resources/primers/
===END===
```

---

## Contributing

```bash
git clone https://github.com/elevanaltd/octave-mcp.git
cd octave-mcp
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
pytest
ruff check src tests && mypy src && black --check src tests
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

Apache-2.0 — Built with [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk).
