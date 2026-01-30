# Changelog

All notable changes to OCTAVE-MCP will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-01-30 - "Generative Holographic Contracts" Release

This release marks the stable v1.0.0 of OCTAVE-MCP, completing four internal milestones (M1-M4) with full OCTAVE v6 specification compliance. OCTAVE-MCP is now production-ready for LLM communication with generative holographic contracts.

### Added

#### M1: Parser Hardening (v0.7.0-internal) - #194
- **Duplicate Key Detection** (#179) - Parser now detects and warns on duplicate keys within the same block
- **Unbalanced Bracket Detection** (#180) - Improved error messages for unclosed `[` brackets with position tracking
- **Spec Compliance Warnings** (#184) - Added warnings for NEVER rules from octave-core-spec (e.g., trailing commas)
- **Inline Map Nesting Validation** (#185) - Validates inline map nesting depth with configurable limits

#### M2: Developer Experience (v0.8.0-internal) - #198
- **Variable Syntax Support** (#181) - Added `$VAR` and `${VAR}` variable reference syntax in OCTAVE documents
- **Comment Preservation** (#182) - Comments are now preserved during normalization and round-trip parsing
- **Validation Profiles** (#183, #197) - Four profiles: `STRICT`, `STANDARD`, `LENIENT`, `ULTRA` for flexible validation
- **Token-Efficient Response Modes** (#195, #196) - Added `diff_only` and `compact` modes to reduce MCP response size
- **Deep Nesting Warning** (#192) - Configurable warning threshold for deeply nested structures
- **Auto-Format Options** (#193) - Formatting options for canonical emission (indentation, line width)

#### M3: Schema Foundation (v0.9.0-internal) - #199
- **Holographic Pattern Parsing** (#187) - Full support for `["example"^CONSTRAINT->TARGET]` syntax with registry
- **Target Routing System** (#188) - Block-level routing with `TargetRegistry` and `TargetRouter` for `->TARGET` directives
- **Block Inheritance** (#189) - `BLOCK[->TARGET]:` syntax for inheriting parent constraints
- **POLICY Block Enforcement** (#190) - New `POLICY::` block type for governance declarations

#### M4: Generative Contracts (v1.0.0) - #204, #205, #207
- **Complete GBNF Integration** (#171, #204) - Full llama.cpp GBNF grammar generation for LLM backend constrained decoding
- **Emoji and Unicode Symbol Support** (#186, #204) - Keys can now contain emoji and extended Unicode symbols
- **META Schema Compilation** (#191, #205) - Self-describing documents with `META.CONTRACT::HOLOGRAPHIC[...]` compilation
- **META.CONTRACT in GBNF Export** (#207) - `octave_eject` now includes META.CONTRACT field in GBNF output

#### Documentation - #202, #208
- **Formal EBNF Grammar Specification** (#113, #208) - Complete formal grammar at `docs/grammar/octave-v1.0-grammar.ebnf`
- **Patterns Specification** (#202) - New `octave-patterns-spec.oct.md` with `ANCHOR_KERNEL` support
- **Grammar Test Vectors** - Valid and invalid example files for grammar testing

#### Infrastructure - #203, #206
- **Context File Synchronization** (#203) - Updated `.hestai/context/` files to reflect M1-M3 completion
- **Startup Dependency Sync** (#206) - MCP server now validates venv dependencies on startup to prevent stale environments

### Changed
- **Emitter Improvements** (#200, #201) - Block target annotations (`[->TARGET]`) and `HolographicValue` emission using `raw_pattern`
- **Test Infrastructure** - Test count increased from 706 to ~1610 passing tests
- **Quality Gates** - All changes validated against mypy, ruff, black, pytest with 90%+ coverage

### Fixed
- **Critical octave_write Issues** (#176, #177, #178) - Fixed file writing edge cases and validation errors
- **Emitter Target Annotations** (#201) - Correctly emit block target annotations in canonical output
- **HolographicValue Emission** (#200) - Fixed raw pattern preservation in holographic value emission

### Quality Gates
- All milestones reviewed by Critical Review Specialist (Gemini/LOGOS)
- Constitutional compliance verified: I1, I2, I3, I4, I5
- Parser hardening prevents silent data loss (I3 compliance)
- All changes include comprehensive test coverage

## [0.6.1] - 2026-01-12

### Added
- **Validator Frontmatter Support** - Added `--require-frontmatter` flag to `octave-validator` tool
  - Aligns repo validator with core parser/validator behavior
  - Broadens spec parsing coverage for documents with frontmatter
  - Backward compatible - flag is optional

### Fixed
- **Template Generation** - Fixed `octave_eject` template to produce valid OCTAVE
  - Replaced markdown-style `#` comments with OCTAVE `//` syntax
  - Templates now parse correctly without syntax errors
  - Added regression test to prevent future template syntax issues

## [0.6.0] - 2026-01-12 - "Structural Integrity" Release

This release strengthens OCTAVE's structural validation, fixes critical parser issues, and refines the specification suite through dogfooding and systematic cleanup.

### Added
- **Section Name Preservation Rule** - Three-layer defense preventing compression of section identifiers
  - Core spec: `SECTION_NAMES::preserve_exactly` in §4::STRUCTURE
  - Primers spec: Required validation items in §2e::VALIDATE
  - All primers: `preserve_§_names_verbatim` in §5::VALIDATE sections
  - Prevents §1::ESSENCE → §1::ESS compression that breaks parsers
- **Strict Structural Validation** - Parser now has `strict_structure` mode
  - `parse()` uses strict mode by default (fail fast on malformed documents)
  - `parse_with_warnings()` remains lenient for recovery workflows
  - Exported `parse_with_warnings()` for discoverability
- **CI Specification Validation** - All OCTAVE spec files now validated in CI pipeline
  - Ensures specs comply with their own syntax rules (dogfooding)
  - Catches regressions in specification quality

### Changed
- **Specification Naming Convention** - Renamed all spec files for clarity
  - `octave-6-llm-*` → `octave-*-spec` (e.g., `octave-core-spec.oct.md`)
  - Updated all REQUIRES references across specification suite
  - Cleaner, more intuitive naming pattern
- **Primer Structural Alignment** - Ultra-mythic primer updated to v6.1.0
  - §2::TEMPLATE → §2::MAP (matches spec structure)
  - §4::EXAMPLE → §4::ONE_SHOT (matches spec structure)
  - Simplified primer naming: `===NAME===` instead of `===NAME_PRIMER===`
- **Enhanced Core Specification** - Comprehensive quoting rules and holographic principle documentation
  - Added §3b::QUOTING_RULES with explicit guidance
  - Enhanced §6b::VALIDATION_CHECKLIST
  - Clarified holographic contract principles

### Fixed
- **Parser Silent Data Loss** (Issue #162) - Critical fix for unclosed lists at EOF
  - Parser now raises E007 error in strict mode for unclosed lists
  - Lenient mode emits I4 warning with audit trail
  - Prevents silent acceptance of malformed documents
  - Constitutional compliance: I3 (Mirror Constraint), I4 (Transform Auditability)
- **Specification Dogfooding** - Fixed syntax violations in 10+ spec files
  - All specs now comply with octave-core-spec rules
  - Systematic cleanup of quoting, spacing, structure issues
  - Validates OCTAVE's ability to describe itself correctly
- **Test Infrastructure** - Added timeout protection to spec validation tests
  - Prevents CI hangs on malformed specifications
  - 1221 tests passing, 9 skipped

### Quality Gates
- All changes reviewed by Critical Review Specialist (Gemini/LOGOS)
- Critical Engineer approval on parser fixes
- Constitutional compliance verified: I1, I3, I4, I5
- Strict mode prevents I3 violations (accepting incomplete structures)

## [0.5.0] - 2026-01-11 - "Universal Anchor" Release

This release introduces OCTAVE Primers for ultra-efficient agent bootstrapping and completes
the architectural separation of the OCTAVE language specification from implementation details.

### Added
- **OCTAVE Primers** - Ultra-compressed bootstrapping documents (40-60 tokens vs 500-800 for full skills)
  - Universal OCTAVE definition: "Semantic DSL for LLMs"
  - Complete primer set: literacy, compression, mastery, mythology, ultra-mythic
  - Primer Specification v3.0.0 with 5-section structure (ESSENCE, MAP, SYNTAX, ONE_SHOT, VALIDATE)
  - Self-referential compression (primers use the format they teach)
  - 93.75% token savings for agent initialization
- **Octave v6 "Dual-Lock" Schema Specification**
  - Defines strict separation of Identity (Shank) and Behavior (Conduct)
  - Supports `MODEL_TIER` (Premium/Standard/Basic) and `ACTIVATION` (Force/Essence/Element)
  - Enables "Holographic Contract" self-validation within agent files
- **Patterns Support**: Updated Spec to include `PATTERNS::[...]` in Capabilities manifest
- **Resource Consolidation**: All specs, primers, and skills now distributed as package resources
  - Accessible via `importlib.resources` API
  - JSON Schema documentation restored to `resources/specs/schemas/json/`
  - Complete Python package structure with proper `__init__.py` files
- **Comprehensive Test Coverage**: Added tests for resource accessibility and structure validation

### Changed
- **Architectural Separation**: Removed specific HestAI agent implementations (Holistic Orchestrator, etc.) from `octave-mcp` repo
  - Moved agent/skill/pattern content to `hestai-mcp/_bundled_hub` as the reference library
  - `octave-mcp` now serves as the pure Language Specification and Parser
- **Spec Purification**:
  - Renamed `BIND` -> `CORE` in Identity spec to correct semantic verb/noun mismatch
  - Removed `UNIVERSAL_LAWS` from spec to prevent polluting the language with system-specific business logic
- **Vocabulary Alignment**: Updated Spec Activation block to use Debate Hall metaphors (`GUARDIAN`/`EXPLORER`/`ARCHITECT`) instead of generic text
- **Resource Organization**: Consolidated all documentation into `src/octave_mcp/resources/` for single source of truth
  - Removed duplicate `specs/`, `primers/`, and `skills/` folders at root
  - Updated all import paths and references

### Fixed
- Removed non-existent `SESSION_LOG` vocabulary from registry that would cause `FileNotFoundError`
- Updated test paths to use consolidated resource locations
- Fixed package data configuration to include all resource subdirectories

## [0.4.1] - 2026-01-07

### Fixed
- Hermetic schema resolution in `octave_write` tool - now uses `resolve_hermetic_standard` for `frozen@` and `latest` schema references (Issue #150)

### Added
- Type hints and improved documentation in write tool hermetic resolution path

## [0.4.0] - 2026-01-07

### Added
- **Generative Holographic Contracts** (ADR-003): Multi-dimensional validation with incremental integrity enforcement
  - Hermetic Anchoring: Contextual identity binding via `odyssean_anchor` tool with RAPH vectors (Request, Assignment, Permit, Hash)
  - v6 OCTAVE specification support with pattern-based validation and regex compilation
  - `debug_grammar` parameter in `octave_validate` for grammar debugging output
  - Progressive integrity model: v4 (Structural) → v5 (Syntactic) → v6 (Semantic+Hermetic)

### Changed
- Enhanced validation architecture with tier-based approach (quick/default/deep)
- Improved schema sovereignty with regex pattern compilation

## [0.3.1] - 2026-01-04

### Added
- `list_exports()` helper function for API discovery - easily explore all 52 public exports by category
- Regression tests covering semantic version strings (`VERSION` token) and multi-word value handling

### Fixed
- Handle semantic version strings (e.g., `1.2.3`, prerelease/build forms) via `VERSION` tokenization (#140, #141, #142)
- Prevent `VALUE_TOKENS` data loss in multi-word values; unify value token handling in parser/lexer (#140, #141, #142)
- Restrict `GRAMMAR_SENTINEL` matching to document start only (#142)

## [0.3.0] - 2026-01-04

### Added
- **51 public API exports** enabling external packages to import OCTAVE functionality
  - Core functions: `parse()`, `emit()`, `tokenize()`, `repair()`, `project()`
  - Core classes: `Parser`, `Validator`, `TokenType`, `Token`
  - AST nodes: `Document`, `Block`, `Assignment`, `Section`, `ListValue`, `InlineMap`, `Absent`
  - Hydration: `hydrate()`, `HydrationPolicy`, `VocabularyRegistry`
  - Schema: `SchemaDefinition`, `FieldDefinition`, `extract_schema_from_document()`
  - Repair (I4): `RepairLog`, `RepairEntry`, `RepairTier`
  - Routing (I4): `RoutingLog`, `RoutingEntry`
  - Sealing: `seal_document()`, `verify_seal()`, `SealVerificationResult`
  - Exceptions: 9 exception types for granular error handling
  - Operators: `OCTAVE_OPERATORS` dict + 10 `OP_*` constants
- Comprehensive API documentation in `docs/api.md`
- PyPI package distribution

### Fixed
- CLI version reporting now uses package version instead of hardcoded value
- Version alignment across all components (pyproject.toml, __init__.py, CLI)

### Changed
- Package version updated from 0.2.0 to 0.3.0

## [0.2.0] - 2025-12-28

### Added
- MCP (Model Context Protocol) server implementation
  - `octave_validate` tool - Schema validation with repair suggestions
  - `octave_write` tool - Unified file writing with CAS support
  - `octave_eject` tool - Multiple projection modes (canonical, authoring, executive, developer)
- Comprehensive schema validation system (I5 - Schema Sovereignty)
- Repair log functionality for audit trail (I4 - Transform Auditability)
- Routing log for transformation tracking
- Document sealing for integrity verification
- Hydration system with vocabulary registry
- Support for holographic patterns

### Changed
- Consolidated from multiple tools to three core MCP tools
- Improved error handling and validation messages
- Enhanced lenient parsing with better error recovery

### Fixed
- Parse error handling for edge cases
- Idempotency issues in canonical emission

## [0.1.0] - 2025-12-15

### Added
- Initial OCTAVE specification implementation
- Core parser and lexer
- AST (Abstract Syntax Tree) nodes
- Basic emit functionality for canonical output
- Support for OCTAVE operators (both Unicode and ASCII)
- Command-line interface (`octave` command)
- Test suite with >1000 tests
- Five core immutables:
  - I1: Syntactic Fidelity
  - I2: Deterministic Absence
  - I3: Mirror Constraint
  - I4: Transform Auditability
  - I5: Schema Sovereignty

### Features
- Lenient-to-canonical transformation pipeline
- Loss accounting for LLM communication
- Non-reasoning document processing
- Deterministic, idempotent transformations

[Unreleased]: https://github.com/elevanaltd/octave-mcp/compare/v0.6.1...HEAD
[0.6.1]: https://github.com/elevanaltd/octave-mcp/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/elevanaltd/octave-mcp/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/elevanaltd/octave-mcp/compare/v0.4.1...v0.5.0
[0.4.1]: https://github.com/elevanaltd/octave-mcp/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/elevanaltd/octave-mcp/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/elevanaltd/octave-mcp/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/elevanaltd/octave-mcp/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/elevanaltd/octave-mcp/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/elevanaltd/octave-mcp/releases/tag/v0.1.0
