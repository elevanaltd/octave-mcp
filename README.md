# OCTAVE MCP Server

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-2258%20passing-brightgreen.svg)]()
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

OCTAVE is a structured document format with an MCP server and CLI. Documents normalise to a single canonical form, validate against their own schema, and log every transformation. It's infrastructure for AI documents that need to survive compression, multi-agent handoffs, and auditing.

### Quick example

You write this (messy, lenient):
```octave
===CONFIG===
META:
  TYPE :: LOG
status  ::  active
flow :: A -> B -> C
tags:: [  alpha,  beta , gamma ]
===END===
```

Run `octave validate --stdin` and get back canonical form:
```octave
===CONFIG===
META:
  TYPE::LOG
status::active
flow::"A→B→C"
tags::[alpha,beta,gamma]
===END===
```
Whitespace normalised. `->` converted to `→`. List commas tightened. The warnings tell you exactly what changed:
```
normalization: '->' → '→' at line 5
normalization: '->' → '→' at line 5
```
Same input, same output, every time. That's the core promise.

### What you get

- **Canonical normalisation** — Same input, same output, always. Idempotent. Two agents independently producing the same document get a byte-for-byte match.

- **Schema validation with receipts** — Documents carry their schema inline. Validation returns specific field errors. Every repair is logged with stable IDs — you know exactly what changed and why.

- **Token compression (2–5x)** — Strips linguistic scaffolding, not content. Facts and relationships stay exactly as written.

- **Grammar compilation** — Schema constraints compile to GBNF grammars for llama.cpp-compatible backends. Constrain LLM generation at decode time.

- **YAML frontmatter + OCTAVE body in one pass** — Agent and skill files need YAML headers for tool discovery and structured bodies for behaviour. `octave_write` validates both in a single operation.

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
- Agent and skill files with YAML discovery headers + structured content
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

Two architectural ideas and one that sounds like it shouldn't work but does.

### Self-describing artifacts

Most structured output validates at a single point and then becomes a plain object. OCTAVE documents are different — the schema, compression tier, and transformation log travel *with* the document. A downstream agent doesn't infer integrity; it reads it.

This creates a property that JSON Schema or Pydantic don't give you: the validation receipt is part of the artifact, not external to it.

### Grammar compilation from inline constraints

A document's `META.CONTRACT` block compiles to a GBNF grammar that can constrain LLM generation at decode time. The schema doesn't just validate output after the fact — it can shape generation while it happens. This bridges the gap between "check if it's valid" and "make it valid by construction."

### Mythological compression

This is the part where we lose some of you. We know how it sounds. Just look at it from an inquisitive perspective and consider it for a moment.

OCTAVE is named **Olympian** Common Text And Vocabulary Engine. That's not branding — it's the hypothesis. Classical mythology seems to be so deeply represented in LLM training data that mythological terms function as a pre-compressed semantic vocabulary that's already in the weights.

| Term | What it encodes |
|------|----------------|
| `JOURNEY::ODYSSEAN` | Long, difficult, full of unforeseen obstacles |
| `CHALLENGE::SISYPHEAN` | Repetitive, frustrating, cyclical, futile |
| `CHOICE::SOLOMONIC` | Requires wisdom to divide fairly between competing claims |
| `STRATEGY::ATHENA` | Find a clever solution balancing competing constraints |

`SISYPHEAN::BUILD_FAILURES` — a single term that carries repetition, frustration, cyclicality, and futility. In prose, that's 10–15 tokens. Here, it's one.

In informal cross-model testing (GPT-4, Claude, Gemini, Llama, Mistral), these terms were consistently interpreted as expected without few-shot priming. No fine-tuning, no examples, no definitions provided. Personally, we've seen zero-shot comprehension in every model we've tried, but that's bias. Like every good hypothesis, we want to prove it wrong until we can't.

There's a paradox worth noting: when asked *theoretically* whether mythology works as compression, models hesitate and cite cultural concerns. When given `JOURNEY::ODYSSEAN` *practically*, they understand it instantly. We don't fully understand why that gap exists — but the practical result is consistent. So OCTAVE primers explicitly encourage operational use rather than meta-discussion.

This is exploratory. We're not claiming a universal law. We are claiming it works reliably in practice, across every model we've tested, and that it's worth investigating why.

If you're sceptical, fair enough. If you want to falsify this quickly, the guide includes a short replication protocol.

Evidence and methodology: [The Mythological Compression Principle](docs/guides/mythological-compression.md)

---

## For AI Agents

The ~200-token block below makes you OCTAVE-literate:

```octave
===OCTAVE_LITERACY_PRIMER===
META:
  TYPE::PRIMER
  VERSION::"6.0.0"

§1::ESSENCE
OCTAVE::"Semantic DSL for LLMs"
STRUCTURE::KEY::value,[list],indent_2

§2::SYNTAX
::::"assign"
→::"flow"
⊕::"synthesis"
⇌::"tension"

§3::ONE_SHOT
IN::"flow from A to B"
OUT::A→B

§4::VALIDATE
MUST::[valid_OCTAVE,preserve_§_names,"===END==="]
===END===
```

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
