# OCTAVE Package Resources

## Overview

These resources are distributed as part of the `octave-mcp` package for use by implementers and agents.

## Structure

### `/specs/`
Official OCTAVE v6.0.0 specifications defining the format, operators, and usage patterns.

- **octave-6-llm-core.oct.md** - Core syntax, operators, and type system
- **octave-6-llm-skills.oct.md** - Skill document format and structure
- **octave-6-llm-data.oct.md** - Data compression tiers and patterns
- **octave-primer-spec.oct.md** - Primer specification (v3.0.0)

### `/primers/`
Ultra-compressed bootstrapping documents (~40-60 tokens) for instant agent competence.

- **octave-literacy-primer.oct.md** - Write basic OCTAVE syntax
- **octave-compression-primer.oct.md** - Compress prose to OCTAVE
- **octave-mastery-primer.oct.md** - Master OCTAVE patterns
- **octave-mythology-primer.oct.md** - Map concepts to mythological atoms
- **octave-ultra-mythic-primer.oct.md** - Ultra-compress with 60% reduction

## Usage

### From Python Package

```python
from importlib import resources
import octave_mcp.resources

# Read a primer
with resources.files(octave_mcp.resources).joinpath('primers/octave-literacy-primer.oct.md').open() as f:
    primer_content = f.read()

# Read a spec
with resources.files(octave_mcp.resources).joinpath('specs/octave-6-llm-core.oct.md').open() as f:
    spec_content = f.read()
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

All primers are v3.0.0, part of the Universal Anchor release, ensuring consistency across the ecosystem.

## Implementation Notes

- Specs marked as APPROVED are normative
- Implementation status may vary; check individual specs for details
- Primers use the format they teach (self-referential compression)
- Token counts are approximate and may vary by tokenizer
