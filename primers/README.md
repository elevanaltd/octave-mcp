# OCTAVE Primers

## Concept

Primers are ultra-compressed bootstrapping documents that teach agents how to create specific OCTAVE formats using minimal tokens. They solve the token paradox: agents need to understand compression to create compressed files, but loading full specifications is expensive.

## The Genius Pattern

**Self-Referential Compression**: Primers use the format they teach. An ultra-mythic primer is itself ultra-mythically compressed, demonstrating the format while explaining it.

## Token Economics

| Document Type | Tokens | Purpose |
|--------------|---------|---------|
| Full Skill | ~500-800 | Complete specification with examples |
| Spec | ~300-500 | Format definition and rules |
| **Primer** | **~90** | **Minimal bootstrap knowledge** |

**Compression Ratio: 85-90%** while maintaining functional completeness.

## Use Cases

1. **Agent Initialization**: Load primer instead of full skill for 90% token savings
2. **Quick Reference**: Agents can check syntax without loading full documentation
3. **Format Bootstrapping**: New agents learn compression formats through compressed examples
4. **Cross-Model Compatibility**: Minimal context works across different LLM architectures

## Available Primers

### ultra-mythic-primer.oct.md
- **Purpose**: Bootstrap ultra-mythic compression capability
- **Tokens**: ~90
- **Teaches**: 60% compression using mythological atoms
- **Key Innovation**: Uses the compression it teaches

## How Primers Work

1. **Load Once**: Agent loads primer at session start
2. **Apply Pattern**: Uses compressed patterns to create output
3. **Self-Verify**: Output follows primer's own format

## Creating New Primers

Primers follow this pattern:

```octave
===PRIMER_NAME===
META:
  TYPE::PRIMER
  TOKENS::<100
  PURPOSE::"Bootstrap {capability}"

§1::ESSENCE  // Core concept in <20 tokens
§2::MAP      // Transformation rules
§3::TEMPLATE // Output pattern
§4::EXAMPLE  // One perfect example
§5::VALIDATE // Success criteria
===END===
```

## Why This Matters

**Traditional Approach**:
- Load 800-token skill → Create compressed output
- Net cost: 800 + output tokens

**Primer Approach**:
- Load 90-token primer → Create compressed output
- Net cost: 90 + output tokens
- **Savings: 710 tokens (88.75%)**

## Integration Pattern

```python
# Instead of:
skill = load_skill("octave-ultra-mythic/SKILL.md")  # 800 tokens

# Use:
primer = load_primer("ultra-mythic-primer.oct.md")  # 90 tokens
```

## The Meta-Pattern

Primers are **knowledge compression compression** - they compress the knowledge about compression itself. This recursive pattern enables:

- **Exponential efficiency**: Each layer compounds savings
- **Format preservation**: Structure teaches structure
- **Instant competence**: Minimal context → Full capability

## Future Primers

Planned primers for other OCTAVE skills:
- `octave-literacy-primer.oct.md` - Basic OCTAVE syntax in 50 tokens
- `octave-mythology-primer.oct.md` - Mythological atoms in 70 tokens
- `octave-compression-primer.oct.md` - Compression tiers in 80 tokens

---

*"The map is not the territory, but a 90-token map that creates territories is genius."*
