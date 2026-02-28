# OCTAVE Guides

This directory contains conceptual documentation for **OCTAVE** (Olympian Common Text And Vocabulary Engine).

## For LLMs: Use the Skills

Claude Code skills provide OCTAVE capabilities directly:

| Skill | Purpose | Triggers |
|-------|---------|----------|
| **octave-literacy** | Core syntax and operators | `octave format`, `write octave` |
| **octave-compression** | Transform prose to OCTAVE | `compress to octave`, `semantic compression` |
| **octave-mastery** | Semantic Pantheon and advanced patterns | `octave architecture`, `agent design` |

## Custom Instructions

| File | Audience | Purpose |
|------|----------|---------|
| [octave-custom-instruction.md](octave-custom-instruction.md) | Any LLM (no tooling) | Drop-in system prompt for Claude Projects, ChatGPT, or any LLM — enables OCTAVE conversion without the MCP toolchain |
| [octave-custom-instruction.oct.md](octave-custom-instruction.oct.md) | Any LLM (no tooling) | Same as above, in OCTAVE format for direct context injection |
| [octave-expert-mcp-aware.oct.md](octave-expert-mcp-aware.oct.md) | MCP-equipped agents | Expert layer for agents WITH the MCP toolchain — tools handle syntax, instruction handles editorial judgment (compression craft, naming, operator semantics) |

## Philosophy (Dual Format)

The philosophy document exists in two formats for different audiences:

| File | Audience | Purpose |
|------|----------|---------|
| [octave-philosophy.md](octave-philosophy.md) | Humans | Narrative explanation with context |
| [octave-philosophy.oct.md](octave-philosophy.oct.md) | LLMs | Compressed OCTAVE for injection |

Both contain identical information - the Golden Rule and Seven Deadly Smells.

## Examples

See [`examples/`](../../examples/) for comprehensive OCTAVE examples including:
- Compression tier comparisons (lossless → ultra)
- Assessment survey transformations
- Templates for common patterns

## Development Setup

See [development-setup.md](development-setup.md) for environment configuration and testing.

## Protocol Specifications

For the authoritative OCTAVE specification, see [`src/octave_mcp/resources/specs/`](../../src/octave_mcp/resources/specs/):

- `octave-core-spec.oct.md` - Core syntax and operators
- `octave-agents-spec.oct.md` - Agent architecture
- `octave-skills-spec.oct.md` - Skills specification
- `octave-patterns-spec.oct.md` - Patterns specification

## The Golden Rule

> "If your OCTAVE document were a database schema, would it have foreign keys?
> If not, you've written a list, not a system."

Focus on **relationships**, not just data.
