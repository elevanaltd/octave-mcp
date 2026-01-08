# Changelog

All notable changes to OCTAVE-MCP will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Octave v6 "Dual-Lock" Schema Specification**
  - Defines strict separation of Identity (Shank) and Behavior (Conduct)
  - Supports `MODEL_TIER` (Premium/Standard/Basic) and `ACTIVATION` (Force/Essence/Element)
  - Enables "Holographic Contract" self-validation within agent files
- **Patterns Support**: Updated Spec to include `PATTERNS::[...]` in Capabilities manifest

### Changed
- **Architectural Separation**: Removed specific HestAI agent implementations (Holistic Orchestrator, etc.) from `octave-mcp` repo.
  - Moved agent/skill/pattern content to `hestai-mcp/_bundled_hub` as the reference library.
  - `octave-mcp` now serves as the pure Language Specification and Parser.
- **Spec Purification**:
  - Renamed `BIND` -> `CORE` in Identity spec to correct semantic verb/noun mismatch.
  - Removed `UNIVERSAL_LAWS` from spec to prevent polluting the language with system-specific business logic.
- **Vocabulary Alignment**: Updated Spec Activation block to use Debate Hall metaphors (`GUARDIAN`/`EXPLORER`/`ARCHITECT`) instead of generic text.

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
- Comprehensive API documentation in `docs/public-api-reference.md`
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

[Unreleased]: https://github.com/elevanaltd/octave-mcp/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/elevanaltd/octave-mcp/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/elevanaltd/octave-mcp/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/elevanaltd/octave-mcp/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/elevanaltd/octave-mcp/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/elevanaltd/octave-mcp/releases/tag/v0.1.0
