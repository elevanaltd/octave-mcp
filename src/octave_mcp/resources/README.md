# OCTAVE Package Resources

## Overview

These resources are distributed as part of the `octave-mcp` package for use by implementers and agents.

## Structure

### `/specs/`
Official OCTAVE v6.0.0 specifications defining the format, operators, and usage patterns.

- **octave-core-spec.oct.md** - Core syntax, operators, and type system
- **octave-agents-spec.oct.md** - Agent architecture patterns
- **octave-skills-spec.oct.md** - Skill document format and structure
- **octave-data-spec.oct.md** - Data compression tiers and patterns
- **octave-execution-spec.oct.md** - Execution flow and protocols
- **octave-schema-spec.oct.md** - Schema validation framework
- **octave-rationale-spec.oct.md** - Design rationale and philosophy
- **octave-primers-spec.oct.md** - Primer specification (v6.0.0)
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
Complete OCTAVE skills with full documentation and examples (~500-800 tokens).

- **octave-literacy/** - Basic OCTAVE syntax and structure
- **octave-compression/** - Compression workflows and tiers
- **octave-mastery/** - Advanced patterns and archetypes
- **octave-mythology/** - Mythological encoding patterns
- **octave-ultra-mythic/** - Ultra-high density compression

### `/primers/`
Ultra-compressed bootstrapping documents (30-60 tokens) for instant agent competence.

- **octave-literacy-primer.oct.md** - Write basic OCTAVE syntax
- **octave-compression-primer.oct.md** - Compress prose to OCTAVE
- **octave-mastery-primer.oct.md** - Master OCTAVE patterns
- **octave-mythology-primer.oct.md** - Map concepts to mythological atoms
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
# Agent can now compress prose to OCTAVE with ~50 token overhead
```

## Universal OCTAVE Definition

All primers use the standardized definition:
```
OCTAVE::"Semantic DSL for LLMs"
```

## Version Alignment

All resources are v6.0.0, part of the Universal Anchor release, ensuring consistency across the ecosystem.

## Implementation Notes

- Specs marked as APPROVED are normative
- Implementation status may vary; check individual specs for details
- Primers use the format they teach (self-referential compression)
- Token counts are approximate and may vary by tokenizer
