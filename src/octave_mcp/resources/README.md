# OCTAVE (Olympian Common Text And Vocabulary Engine) Package Resources

## Overview

These resources are distributed as part of the `octave-mcp` package for use by implementers and agents.

## Structure

### `/specs/`
Official OCTAVE v6 specifications defining the format, operators, and usage patterns.

- **octave-core-spec.oct.md** - Core syntax, operators, and type system
- **octave-agents-spec.oct.md** - Agent architecture patterns
- **octave-skills-spec.oct.md** - Skill document format and structure
- **octave-data-spec.oct.md** - Data compression tiers and patterns
- **octave-execution-spec.oct.md** - Execution flow and protocols
- **octave-schema-spec.oct.md** - Schema validation framework
- **octave-rationale-spec.oct.md** - Design rationale and philosophy
- **octave-primers-spec.oct.md** - Primer specification (token budget: 500 `cl100k_base` tokens per primer)
- **octave-mcp-architecture.oct.md** - MCP implementation architecture

#### `/specs/schemas/`
Schema definitions and templates.

- **debate_transcript.oct.md** - Schema for debate hall transcripts
- **json/** - JSON Schema for OCTAVE (see [JSON Schema README](specs/schemas/json/README.md))

#### `/specs/vocabularies/`
OCTAVE vocabulary definitions.

- **registry.oct.md** - Vocabulary registry index
- **core/** - Core vocabulary definitions
  - **META.oct.md** - META vocabulary specification
  - **SNAPSHOT.oct.md** - SNAPSHOT vocabulary specification

### `/skills/`
Complete OCTAVE skills with full documentation and examples (roughly 1,600-5,100 `cl100k_base` tokens each).

- **octave-literacy/** - Basic OCTAVE syntax, canonical forms, and governance-artefact grammar
- **octave-compression/** - Compression workflows and tiers
- **octave-mastery/** - Advanced patterns, archetypes, and the mythology vocabulary
- **octave-chatter/** - OCTAVE on the wire: reading and emitting OCTAVE in agent-to-agent messages
- **octave-ultra-mythic/** - Ultra-high density compression

The **octave-mythology** skill was retired; its vocabulary, usage law, and
anti-patterns are absorbed into **octave-mastery** (see its `ABSORBS` META field).

### `/patterns/`
Procedural patterns that compose with the skills.

- **octave-tool-reference.oct.md** - Contract for `octave_write` / `octave_validate`:
  modes, receipt gates, changes-mode semantics, and warning remediation

### `/primers/`
Compact bootstrapping documents (each within the 500-token `cl100k_base` budget; the exact count is declared as `TOKENS` in each primer's `META`) for instant agent competence.

- **octave-literacy-primer.oct.md** - Write basic OCTAVE syntax
- **octave-compression-primer.oct.md** - Compress prose to OCTAVE
- **octave-mastery-primer.oct.md** - Master OCTAVE patterns
- **octave-mythology-primer.oct.md** - Map concepts to mythological atoms
- **octave-reading-primer.oct.md** - Understand OCTAVE format on receipt (read-only register)
- **octave-ultra-mythic-primer.oct.md** - Ultra-compress with 60% reduction

## Usage

### From Python Package

```python
from importlib.resources import files, as_file

# Read a primer
primer_file = files('octave_mcp.resources.primers').joinpath('octave-literacy-primer.oct.md')
with as_file(primer_file) as path:
    primer_content = path.read_text()

# Read a spec
spec_file = files('octave_mcp.resources.specs').joinpath('octave-core-spec.oct.md')
with as_file(spec_file) as path:
    spec_content = path.read_text()

# Read JSON Schema documentation
json_schema_file = files('octave_mcp.resources.specs.schemas.json').joinpath('json-schema.md')
with as_file(json_schema_file) as path:
    json_schema_content = path.read_text()

# Read vocabulary files
meta_vocab_file = files('octave_mcp.resources.specs.vocabularies.core').joinpath('META.oct.md')
with as_file(meta_vocab_file) as path:
    meta_vocab_content = path.read_text()
```

### For Agents

Primers are designed for direct injection into agent context:

```python
# Load primer for instant OCTAVE competence
primer = load_resource('primers/octave-compression-primer.oct.md')
# Agent can now compress prose to OCTAVE at a cost of ~500 tokens of context
```

## Universal OCTAVE Definition

OCTAVE stands for **Olympian Common Text And Vocabulary Engine**.

All primers use the standardized definition:
```
OCTAVE::"Olympian Common Text And Vocabulary Engine — Semantic DSL for LLMs"
```

## Version Alignment

Resources target the OCTAVE v6 protocol. Each file carries its own `VERSION` in `META`; versions differ per file (e.g. `octave-core-spec` 6.0.1, `octave-primers-spec` 6.3.2, `octave-skills-spec` 9.1.0), so check the file rather than assuming a shared version.

## Implementation Notes

- Specs marked as APPROVED are normative
- Implementation status may vary; check individual specs for details
- Primers use the format they teach (self-referential compression)
- Primer `TOKENS` values are exact `cl100k_base` counts (enforced by `tests/unit/test_gh453_primer_token_budgets.py`); other token figures are approximate and vary by tokenizer
