# ADR-001: Configurability and Modularity Architecture

## Status
PROPOSED

## Context
The OCTAVE MCP Server implements the OCTAVE v6.0.0 specification, which defines:
- Core grammar (operators, syntax, structure)
- Repair tiers (NORMALIZATION, REPAIR, FORBIDDEN)
- Error codes and validation rules
- Projection modes
- Schema validation framework

The current implementation hardcodes most of these rules directly in Python code:
- `lexer.py`: Operators and ASCII_ALIASES dictionary (lines 79-87)
- `parser.py`: Grammar rules for parsing structure
- `repair.py`: Repair tier classification logic
- `validator.py`: Error code definitions and validation logic
- `schemas/loader.py`: Schema loading mechanism (minimal implementation)

### Key Question
**"If changing the rules in core means changing the code, is that correct?"**

This question requires distinguishing between:
1. **OCTAVE Specification Elements** - The formal grammar, operators, and syntax rules that define OCTAVE itself
2. **Implementation Configuration** - Schema repositories, projection modes, repair strategies, error messages
3. **Extension Points** - Where users/applications should be able to customize behavior

## Decision

### ARCHITECTURAL PRINCIPLE: "Spec-Static, Schema-Dynamic"

The OCTAVE grammar and core operators are **intentionally static** and should remain hardcoded in the implementation. Schemas, projection modes, and certain validation behaviors should be **dynamic and configurable**.

### What MUST Remain Hardcoded (CORRECT AS-IS)

#### 1. Core Grammar and Operators
**RATIONALE**: These are part of the OCTAVE language specification itself, not configuration.

**HARDCODED IN CODE** (src/octave_mcp/resources/specs/octave-core-spec.oct.md §2):
```python
# lexer.py lines 79-87
ASCII_ALIASES = {
    "->": "→",
    "+": "⊕",
    "~": "⧺",
    "vs": "⇌",
    "|": "∨",
    "&": "∧",
    "#": "§",
}
```

**WHY THIS IS CORRECT**:
- Operators are part of the language syntax definition (OCTAVE v6.0.0)
- Changing operators would create incompatible OCTAVE dialects
- These map directly to spec §2::OPERATORS which is versioned with the spec
- ASCII aliases are canonicalization rules (spec §4::CANONICALIZATION_RULES)
- All implementations must agree on operator semantics for interoperability

**SPEC REFERENCE**:
- `octave-core-spec.oct.md` §2::OPERATORS defines precedence and semantics
- `octave-mcp-architecture.oct.md` §4::CANONICALIZATION_RULES (R01-R10)

**LITMUS TEST**: "If two systems disagree on what → means, they cannot exchange OCTAVE documents reliably."

#### 2. Repair Tier Classification
**RATIONALE**: The three-tier system (NORMALIZATION/REPAIR/FORBIDDEN) is a core architectural principle.

**HARDCODED IN CODE** (src/octave_mcp/resources/specs/octave-mcp-architecture.oct.md §5):
```python
# repair.py classification logic
TIER_NORMALIZATION = always_on    # ASCII→unicode, whitespace, quotes
TIER_REPAIR = opt_in_via_fix      # Enum casefold, type coercion
TIER_FORBIDDEN = never_automatic  # Target inference, field insertion
```

**WHY THIS IS CORRECT**:
- The tier system prevents semantic drift (spec §5::REPAIR_CLASSIFICATION)
- FORBIDDEN tier protects against dangerous autocorrect (spec §5::FORBIDDEN_RATIONALE)
- This is a safety boundary, not a preference
- "Autocorrect is safe for syntax, bounded for values, dangerous for intent"

**SPEC REFERENCE**: `octave-mcp-architecture.oct.md` §5::REPAIR_CLASSIFICATION

**LITMUS TEST**: "If repair tiers were configurable, malicious config could bypass safety boundaries."

#### 3. Error Codes and Core Validation Rules
**RATIONALE**: Standard error codes enable cross-implementation tooling.

**HARDCODED IN CODE** (src/octave_mcp/resources/specs/octave-mcp-architecture.oct.md §8):
```python
# validator.py error definitions
E001 = "Single colon assignment not allowed. Use KEY::value (double colon)."
E002 = "Schema selector required. Add @SCHEMA_NAME or explicit ===ENVELOPE===."
E003 = "Cannot auto-fill missing required field '{field}'. Author must provide value."
E005 = "Tabs not allowed. Use 2 spaces for indentation."
```

**WHY THIS IS CORRECT**:
- Standard error codes enable IDE integration, GitHub Actions, CI/CD tooling
- Error messages include educational rationale (spec §8::ERROR_MESSAGES)
- These defend against forbidden repair pressure
- Consistency across implementations reduces cognitive load

**SPEC REFERENCE**: `octave-mcp-architecture.oct.md` §8::ERROR_MESSAGES

**LITMUS TEST**: "If error codes vary by installation, shared tooling breaks."

#### 4. Envelope Format and Structural Rules
**RATIONALE**: Document structure is part of the OCTAVE format specification.

**HARDCODED IN CODE** (src/octave_mcp/resources/specs/octave-core-spec.oct.md §1):
```python
# parser.py envelope handling
ENVELOPE_START = "===NAME==="
ENVELOPE_END = "===END==="
META_BLOCK = required_immediately_after_start
SEPARATOR = "---"  # optional
```

**WHY THIS IS CORRECT**:
- These are OCTAVE format markers, not preferences
- Envelope format enables file discovery and concatenation
- Meta block placement is spec'd for parsability
- Changing these would create format incompatibility

**SPEC REFERENCE**: `octave-core-spec.oct.md` §1::ENVELOPE

### What SHOULD Be Configurable (NEEDS IMPROVEMENT)

#### 1. Schema Repository - **HIGHEST PRIORITY**
**CURRENT STATE**: Minimal implementation in `schemas/loader.py` and `schemas/repository.py`

**REQUIRED CAPABILITIES**:
```python
# Configuration-driven schema loading
class SchemaRepository:
    def __init__(self, config: SchemaConfig):
        self.builtin_schemas = self._load_builtin()
        self.custom_schema_paths = config.custom_paths
        self.remote_registries = config.remote_urls

    def load_from_file(self, path: Path) -> Schema
    def load_from_url(self, url: str) -> Schema
    def register_custom_schema(self, name: str, schema: Schema)
    def list_available_schemas(self) -> list[str]
```

**CONFIGURATION FORMAT** (example):
```yaml
# octave-mcp-config.yaml
schema:
  builtin_path: "src/octave_mcp/schemas/builtin"
  custom_paths:
    - "/path/to/project/schemas"
    - "$HOME/.octave/schemas"
  remote_registries:
    - "https://octave-schemas.example.com/registry"
  cache_dir: "$HOME/.octave/cache/schemas"
  validate_on_load: true
```

**WHY THIS IS ESSENTIAL**:
- Different applications need different schemas (SESSION_LOG, DECISION_LOG, etc.)
- Schema definitions should not require code changes
- Users should be able to define domain-specific schemas
- Schema versioning enables evolution (e.g., SESSION_LOG v2.0)

**SPEC REFERENCE**: `octave-schema-spec.oct.md` §6::SCHEMA_SKELETON

**IMPLEMENTATION PRIORITY**: P0 (blocking for real-world use)

#### 2. Projection Mode Definitions - **MEDIUM PRIORITY**
**CURRENT STATE**: Hardcoded in `projector.py` (lines 45-54)

**REQUIRED CAPABILITIES**:
```python
# Schema-driven projection modes
class ProjectionMode:
    name: str
    include_fields: list[str] | Literal["*"]
    exclude_fields: list[str]
    lossy: bool
    description: str

# Defined in schema or config
projection_modes:
  executive:
    include: ["STATUS", "RISKS", "DECISIONS"]
    exclude: ["TESTS", "CI", "DEPS"]
    lossy: true
  developer:
    include: ["TESTS", "CI", "DEPS"]
    exclude: ["STATUS", "RISKS"]
    lossy: true
```

**WHY THIS MATTERS**:
- Different stakeholders need different views
- Projection modes vary by document schema
- Executive view for SESSION_LOG differs from DECISION_LOG

**SPEC REFERENCE**: `octave-mcp-architecture.oct.md` §9::PROJECTION_MODES

**IMPLEMENTATION PRIORITY**: P1 (important for usability)

#### 3. Compression Tier Behavior - **LOW PRIORITY**
**CURRENT STATE**: Not implemented (reserved in `ingest.py` line 82)

**REQUIRED CAPABILITIES**:
```python
# Compression tier configuration
compression_tiers:
  LOSSLESS:
    target_fidelity: 100
    preserve: ["everything"]
    drop: []
  AGGRESSIVE:
    target_compression: 70
    preserve: ["core_thesis", "conclusions"]
    drop: ["nuance", "narrative", "examples"]
```

**WHY THIS IS LOWER PRIORITY**:
- Compression is primarily about presentation, not correctness
- Current hardcoded tiers match spec exactly
- Less critical for MVP functionality

**SPEC REFERENCE**: `octave-data-spec.oct.md` §1b::COMPRESSION_TIERS

**IMPLEMENTATION PRIORITY**: P2 (enhancement)

### What Should NEVER Be Configurable

#### 1. Forbidden Repair Rules
**NEVER ALLOW**:
- Disabling TIER_FORBIDDEN restrictions
- Enabling target inference
- Allowing field insertion for missing required fields
- Bypassing semantic intent protection

**RATIONALE**: These are safety boundaries that protect against data corruption and security issues.

**SPEC REFERENCE**: `octave-mcp-architecture.oct.md` §5::TIER_FORBIDDEN

#### 2. Core Grammar Precedence
**NEVER ALLOW**:
- Changing operator precedence (e.g., making → bind tighter than ⊕)
- Modifying associativity rules
- Altering bracket semantics

**RATIONALE**: These would create incompatible OCTAVE dialects.

#### 3. Envelope Structure
**NEVER ALLOW**:
- Custom envelope markers (beyond ===NAME=== ... ===END===)
- Optional ===END=== marker
- Different META block placement

**RATIONALE**: File discovery, concatenation, and tooling depend on standard structure.

## Consequences

### Positive
1. **Clear Separation**: Spec-static vs Schema-dynamic principle provides architectural clarity
2. **Interoperability**: Hardcoded grammar ensures all OCTAVE implementations agree
3. **Safety**: Forbidden repairs remain non-configurable, preventing security issues
4. **Extensibility**: Schema repository enables domain-specific extensions without code changes
5. **Evolution**: Spec versioning (5.0.3 → 6.0.0) handled through code updates, not config drift

### Negative
1. **Grammar Changes Require Code Updates**: True, but this is correct - grammar changes are spec changes
2. **Schema Limitation**: Current minimal schema implementation blocks real-world usage
3. **Projection Rigidity**: Hardcoded projection modes limit stakeholder-specific views

### Migration Path
1. **Phase 1 (P0)**: Implement full schema repository with file/URL loading
2. **Phase 2 (P1)**: Make projection modes schema-driven
3. **Phase 3 (P2)**: Implement compression tier behavior (if needed)
4. **Phase 4 (P3)**: Build ecosystem tools (VSCode extension, GitHub Action) that depend on stable core

## Architectural Recommendation

### Configuration File Structure
```yaml
# ~/.octave/config.yaml (user-level)
# or .octave-mcp.yaml (project-level)

version: "1.0"

# Schema configuration (DYNAMIC)
schemas:
  builtin: true
  paths:
    - "./schemas"
    - "$HOME/.octave/schemas"
  registries:
    - url: "https://octave-schemas.example.com"
      cache: true

# Projection modes (DYNAMIC, schema-specific)
projections:
  # Can be defined per-schema or globally
  default_mode: "canonical"

# Validation behavior (CONFIGURABLE WITHIN BOUNDS)
validation:
  strict_mode: true  # Reject unknown fields
  unknown_field_policy: "REJECT"  # or WARN, IGNORE

# Pipeline behavior (CONFIGURABLE)
pipeline:
  default_fix: false  # Don't enable TIER_REPAIR by default
  verbose_logging: false

# FORBIDDEN (never configurable via user config)
# - Core grammar
# - Operator precedence
# - Repair tier classification
# - Error code definitions
# - Envelope structure
```

### Implementation Design

#### Schema Repository Architecture
```python
# src/octave_mcp/schemas/repository.py (enhanced)

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

class SchemaLoader(Protocol):
    """Protocol for schema loading strategies."""
    def load(self, identifier: str) -> Schema: ...

class FileSchemaLoader:
    """Load schemas from filesystem."""
    def __init__(self, base_paths: list[Path]):
        self.base_paths = base_paths

    def load(self, identifier: str) -> Schema:
        # Search base_paths for {identifier}.oct.md
        ...

class URLSchemaLoader:
    """Load schemas from remote registry."""
    def __init__(self, registry_url: str, cache_dir: Path):
        self.registry_url = registry_url
        self.cache_dir = cache_dir

    def load(self, identifier: str) -> Schema:
        # Fetch from registry, cache locally
        ...

class SchemaRepository:
    """Centralized schema management with multiple loaders."""

    def __init__(self, config: SchemaConfig):
        self.loaders: list[SchemaLoader] = []
        self.cache: dict[str, Schema] = {}

        # Always include builtin schemas
        builtin_path = Path(__file__).parent / "builtin"
        self.loaders.append(FileSchemaLoader([builtin_path]))

        # Add custom paths from config
        if config.custom_paths:
            self.loaders.append(FileSchemaLoader(config.custom_paths))

        # Add remote registries
        for registry in config.registries:
            self.loaders.append(URLSchemaLoader(registry.url, config.cache_dir))

    def get(self, name: str) -> Schema:
        """Get schema by name, trying loaders in order."""
        if name in self.cache:
            return self.cache[name]

        for loader in self.loaders:
            try:
                schema = loader.load(name)
                self.cache[name] = schema
                return schema
            except SchemaNotFoundError:
                continue

        raise SchemaNotFoundError(f"Schema '{name}' not found in any loader")

    def register(self, name: str, schema: Schema):
        """Register schema directly (for testing, programmatic use)."""
        self.cache[name] = schema

    def list_available(self) -> list[str]:
        """List all available schemas across all loaders."""
        schemas = set()
        for loader in self.loaders:
            schemas.update(loader.list_schemas())
        return sorted(schemas)
```

#### Configuration Loading
```python
# src/octave_mcp/config.py (new)

from dataclasses import dataclass
from pathlib import Path
import yaml

@dataclass
class SchemaConfig:
    builtin: bool = True
    custom_paths: list[Path] = None
    registries: list[RegistryConfig] = None
    cache_dir: Path = Path.home() / ".octave" / "cache"

@dataclass
class RegistryConfig:
    url: str
    cache: bool = True
    verify_ssl: bool = True

@dataclass
class ValidationConfig:
    strict_mode: bool = True
    unknown_field_policy: str = "REJECT"

@dataclass
class OctaveMCPConfig:
    schemas: SchemaConfig
    validation: ValidationConfig

    @classmethod
    def load(cls, config_path: Path | None = None) -> "OctaveMCPConfig":
        """Load configuration from file or use defaults."""
        if config_path is None:
            # Search for config in standard locations
            config_path = cls._find_config()

        if config_path and config_path.exists():
            with open(config_path) as f:
                data = yaml.safe_load(f)
            return cls.from_dict(data)
        else:
            return cls.default()

    @classmethod
    def default(cls) -> "OctaveMCPConfig":
        """Return default configuration."""
        return cls(
            schemas=SchemaConfig(),
            validation=ValidationConfig(),
        )
```

## Validation Criteria

### Property-Based Tests Required
1. **Spec-Static Invariants**:
   - `canonicalize(doc) == canonicalize(canonicalize(doc))` (idempotent)
   - `parse(emit(ast)) == ast` (round-trip for canonical)
   - Operator precedence matches spec exactly
   - Repair tier classification never violates FORBIDDEN boundary

2. **Schema-Dynamic Invariants**:
   - `repository.get(name)` returns same schema regardless of loader order
   - Schema cache invalidation works correctly
   - Unknown schema errors provide helpful messages
   - Custom schemas override builtins when explicitly configured

3. **Configuration Invariants**:
   - Invalid config fails loudly at startup, not runtime
   - Config changes don't affect core grammar behavior
   - Default config enables immediate usage (no setup required)

### Test Coverage Required
```python
# tests/test_configurability.py

def test_operators_not_configurable():
    """Verify core operators cannot be changed via config."""
    # Even with custom config, → always means FLOW
    ...

def test_forbidden_repairs_never_configurable():
    """Verify TIER_FORBIDDEN cannot be disabled."""
    # No config should allow target inference
    ...

def test_schema_loading_from_file():
    """Custom schemas load from configured paths."""
    ...

def test_schema_loading_from_url():
    """Remote schemas load and cache correctly."""
    ...

def test_projection_modes_schema_specific():
    """Projection modes vary by schema."""
    ...
```

## References

### Specifications
- `src/octave_mcp/resources/specs/octave-core-spec.oct.md` - Core grammar, operators, structure
- `src/octave_mcp/resources/specs/octave-schema-spec.oct.md` - Schema definition patterns
- `src/octave_mcp/resources/specs/octave-mcp-architecture.oct.md` - MCP server architecture, repair tiers

### Implementation Files
- `src/octave_mcp/core/lexer.py` - Operators and ASCII aliases (lines 79-87)
- `src/octave_mcp/core/parser.py` - Grammar rules
- `src/octave_mcp/core/repair.py` - Repair tier classification
- `src/octave_mcp/core/validator.py` - Error codes and validation
- `src/octave_mcp/schemas/loader.py` - Schema loading (minimal)
- `src/octave_mcp/schemas/repository.py` - Schema repository (minimal)

### Alignment with OCTAVE MCP Architecture Spec
This ADR directly implements the architectural philosophy from `octave-mcp-architecture.oct.md`:

**§1::PHILOSOPHY**:
> CORE_PRINCIPLE::one_language_disciplined_tolerance

This ADR distinguishes:
- ONE_LANGUAGE: Core grammar is static (hardcoded)
- DISCIPLINED_TOLERANCE: Schemas and projections are dynamic (configurable)

**§5::REPAIR_CLASSIFICATION**:
> TIER_FORBIDDEN[never_automatic]: semantic_intent_and_structure

This ADR mandates that forbidden repairs remain non-configurable for safety.

**§10::SCOPE_EXCLUSIONS**:
> EXCLUDED: SEMANTIC_INFERENCE::never_guess_meaning

This ADR ensures no configuration can bypass semantic safety boundaries.

## Recommendation Summary

### ✅ CORRECT AS-IS (Keep Hardcoded)
1. Core grammar and operators (`ASCII_ALIASES` dict)
2. Repair tier classification system
3. Error codes and validation rules
4. Envelope format and structural rules

### 🔧 NEEDS IMPROVEMENT (Make Configurable)
1. **P0**: Schema repository with file/URL loading
2. **P1**: Projection mode definitions (schema-driven)
3. **P2**: Compression tier behavior (if needed)

### ❌ NEVER CONFIGURABLE (Safety Boundaries)
1. Forbidden repair rules
2. Core grammar precedence
3. Envelope structure requirements

### Implementation Roadmap
1. Create configuration file format (YAML)
2. Implement `SchemaConfig` and `OctaveMCPConfig` classes
3. Enhance `SchemaRepository` with multiple loaders
4. Add configuration loading to MCP server initialization
5. Write comprehensive tests for configurability boundaries
6. Document configuration options in user guide

This architecture achieves the right balance: **spec-defined elements remain stable and interoperable, while domain-specific extensions are flexible and configurable**.
