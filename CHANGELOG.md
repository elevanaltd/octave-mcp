# Changelog

All notable changes to OCTAVE-MCP will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Reading Primer** (#289) — New `octave-reading-primer.oct.md` for pure comprehension of OCTAVE documents without requiring output generation
- **Literal zones in literacy primer** (#289) — Teaching examples in the literacy primer now use literal zone fencing for clarity
- **OCTAVE vs LLMLingua-2 comparison** (#289) — Example documents and round-trip fidelity analysis comparing OCTAVE semantic compression against LLMLingua-2 extractive compression
- **Compression fidelity round-trip study** (#289) — Research documentation covering CONSERVATIVE-MYTH findings and prose-to-prose baseline measurements
- **Confirmation echo for SOURCE→STRICT compilations** (GH#287) — `octave_write` now returns a confirmation echo when compiling from SOURCE to STRICT mode

### Fixed
- **POSIX trailing newline in `emit()`** (GH#284) — `emit()` now ensures output ends with a trailing newline per POSIX text file convention
- **`%` character handling in values** (GH#287) — Lexer now accepts `%` in values when preceded by alphanumeric characters; restricted `%` handling to value context only; whitespace around `%` in key context correctly detected
- **Operator-rich value preservation in lenient mode** (GH#287) — Parser now preserves values containing multiple operators (e.g., `⊕`, `∧`, `→`) without splitting or reinterpreting them
- **META block parent-child association** (GH#287) — META blocks no longer absorb root-level keys that follow them; block parent-child association correctly preserved
- **Reading primer output format** (#289) — Reading primer now produces natural prose comprehension, not field-by-field translation

### Changed
- **Literacy primer updated** (#289) — Added reading context section for bidirectional OCTAVE literacy (read + write)
- **Skills simplified** (#289) — `SPEC_REFERENCE` in skills reduced to file-level references only
- **README quick-start rewritten** (#289) — Honest compression claims replacing overstated token savings

### Documentation
- **ADR-0005** (#290) — OCTAVE v1.5 Compiler Shift + Operator Evolution decision record, with cross-model validation study
- **Repo structure realigned** (#290) — Documentation structure aligned with visibility-rules v1.6

### Quality Gates
- 2301 tests passing (10 skipped), 0 failures
- Constitutional compliance verified: I1, I2, I3, I4, I5

## [1.6.0] - 2026-02-26 - "Validation Loop" Release

This release closes the Validation Precedes Generation loop: agents now receive INVALID status plus compiled GBNF grammar in a single round-trip, eliminating the need for a separate `octave_compile_grammar` call.

### Added
- **`grammar_hint` parameter for `octave_validate` and `octave_write`** (GH#278) — When `grammar_hint=true` and validation returns INVALID, the compiled GBNF grammar is included directly in the response. Closes the "Validation Precedes Generation" loop so agents can regenerate immediately without a second round-trip.

### Fixed
- **Stable `E_GRAMMAR_COMPILE` error code** (GH#278) — Grammar compilation failures now return a structured error code instead of leaking raw exceptions into tool responses.

### Documentation
- **README rewrite** — Three-audience structure (Engineers, Researchers, AI Agents) with prose-to-OCTAVE before/after example; removed stale v0.6.0 claims and unexplained jargon
- **Updated stale CRITICAL_GAPS** (GH#279) — Architecture and execution specs now reflect v1.5.0 reality; resolved gaps (grammar compilation, JIT grammar, unknown-fields policy) moved to `RESOLVED_GAPS` sections

### Quality Gates
- 2282 tests passing, 0 failures
- Constitutional compliance verified: I1, I2, I3, I4, I5

## [1.5.0] - 2026-02-24 - "Parser Resilience" Release

This release introduces the `octave_compile_grammar` MCP tool, Zone 2 frontmatter validation, multi-line array emission, and resolves a broad set of parser and emitter robustness issues surfaced through systematic GitHub issue review.

### Added
- **`octave_compile_grammar` MCP tool** (#228) — New fourth tool exposing the GBNF grammar compiler directly, with error-envelope hardening and native const type preservation
- **I5 Zone 2 frontmatter validation** (#244) — Opt-in YAML frontmatter validation extending Schema Sovereignty to Zone 2. New error codes: `E_FM_REQUIRED`, `E_FM_TYPE`, `E_FM_PARSE`. First use-case: SKILL schema validates both OCTAVE body and YAML frontmatter
- **`normalize` mode for `octave_write` tool** — Validates and normalizes a document without writing to the file system; useful for dry-run checks and CI pipelines
- **SKILL builtin schema** (`schemas/builtin/skill.oct.md`) — Validates both the OCTAVE body and YAML frontmatter of skill files
- **Multi-line emission for structured arrays** (GH#267) — Arrays with 3+ items now emit in multi-line format for readability; empty InlineMap guard prevents emission errors
- **Curly-brace repair candidate warning** (GH#263, GH#264) — Lexer emits `W_REPAIR_CANDIDATE` for curly-brace annotations; `octave_write` scopes repair to Zone 1 only, skipping quoted strings and literal zones

### Fixed
- **Constructor `NAME[args]` round-trip preservation** (GH#276) — Adjacency check, expanded token types, blacklist filtering of COMMENT/NEWLINE/INDENT tokens in bracket capture; fixes data loss for spaced brackets and multi-line constructors
- **Comments inside array brackets** (GH#272) — `//` comments inside array bracket context now correctly stripped during parsing
- **Annotated identifier coalescing** (GH#269) — Unified accumulator prevents multi-word coalescing of annotated identifiers
- **Duplicate key warnings in arrays** (GH#270) — False duplicate key warnings suppressed for repeated keys within array contexts
- **Canonicaliser numbered-key syntax inside list literals** (#246) — `1::"value"` patterns inside list literals no longer flattened to separate tokens; fixes round-trip fidelity for numbered keys
- **Emitter InlineMap bracket wrapping in lists** — Prevents nested list artifacts on re-parse when InlineMaps appear inside list values
- **Literal zone content in block body** (#259) — Literal zone content now preserved correctly when appearing inside block bodies
- **Bracket annotation after flow expressions** (#261) — Parser now consumes bracket annotations following flow expressions
- **Write tool robustness** (GH#263, GH#266) — Tightened structure detection to require `::` or `===` signals; graceful baseline parse failure handling; narrowed exception handling with audit receipts; escaped quote handling in curly-brace repair
- **Grammar compiler** — Preserved native const types and hardened error-envelope handling

### Documentation
- Archived mythology debate decisions from issue #110 review session
- Restored mythological compression principle across OCTAVE documentation (#110)
- Normalized all decision docs to OCTAVE canonical form
- Updated schema-spec to reflect all gaps implemented

### Quality Gates
- 2258 tests passing, 0 failures
- Constitutional compliance verified: I1, I2, I3, I4, I5

## [1.4.1] - 2026-02-22 - "Spec Hygiene" Patch

### Fixed
- **8 active .oct.md spec/primer parse failures** — All bundled specs and primers now parse cleanly
  - Primers spec: quoted bare `<`, `%`, `==` characters
  - Compression primer: quoted `§_names` value
  - Agents, patterns, skills specs: restructured nested inline maps to block format
  - Execution, rationale specs: closed unclosed lists, quoted `vs` boundary values
  - ADR-003: replaced bare backticks with quoted strings
- Cleared `KNOWN_ISSUES` in `test_spec_validation.py` — all specs pass validation

## [1.4.0] - 2026-02-22 - "Annotation Syntax" Release

This release introduces angle-bracket annotation syntax (`NAME<qualifier>`) as a new identifier feature, fixes bracket-depth-aware salvage in `octave_write`, and resolves spec parse failures blocking CI validation.

### Added
- **NAME\<qualifier\> Annotation Syntax** (#248) — New angle-bracket annotation syntax for identifiers
  - Lexer tokenizes `NAME<qualifier>` as a single IDENTIFIER token
  - Emitter preserves annotations in canonical output without quoting
  - Replaces `NAME{qualifier}` which conflicted with bracket parsing
  - Spec updates: core v6.0.0, rationale v6.0.0, agents v6.2.0

### Fixed
- **Bracket-depth-aware salvage** (#248) — `octave_write` salvage mode now correctly counts bracket depth
  - Previously could mis-count brackets inside quoted strings
  - Tightened emitter regex for quote-aware bracket matching
- **Primers spec parse failure** — Fixed bare `\n` in `FORMAT` value causing E005 lexer error
  - Restructured value to use quoted string representation
- **Compression primer parse failure** — Fixed bare `>` character causing E005 lexer error
  - Quoted the value containing the `>` to prevent angle-bracket ambiguity

### Documentation
- EBNF grammar updated with `angle_annotation` production rule and Appendix C note (Section 10, Note 9)
- Spec files updated for annotation syntax documentation

### Quality Gates
- 2080 tests passing, 0 failures
- Constitutional compliance verified: I1, I2, I3, I4, I5

## [1.3.0] - 2026-02-19 - "Three-Zone Model" Release

This release completes the Three-Zone Model architecture for OCTAVE documents, delivering Zone 3 (Explicit Literal Zones) as a new first-class language feature and fixing Zone 2 (Preserving Container) which was silently broken.

### Added

- **Literal Zones — Zone 3** (#235) - Fenced code blocks as first-class OCTAVE values
  - New `LiteralZoneValue` AST node with verbatim content preserved without normalization
  - Backtick fence syntax (`` ` `` `` ` `` `` ` ``) for literal zone values with optional language tags (e.g. `` ```python ``)
  - `FENCE_OPEN`, `FENCE_CLOSE`, `LITERAL_CONTENT` token types in lexer
  - NFC normalization bypass inside literal zones (I1 compliance — preserving meaning)
  - Tab bypass inside literal zones
  - Round-trip fidelity: `parse(emit(parse(D))) == parse(D)` for all literal zones
  - `LiteralZoneRepairLog` for I4 audit trail
  - `TYPE[LITERAL]` schema constraint for validating literal zone fields
  - `LANG[python]` schema constraint for requiring specific language tags
  - Zone reporting in all three MCP tools (`octave_validate`, `octave_write`, `octave_eject`)
  - `contains_literal_zones`, `literal_zone_count`, `literal_zones_validated` flags in all tool responses
  - A9 migration gate: existing documents unaffected (non-breaking)
  - LITERAL type documented in core spec and EBNF grammar

### Fixed

- **Zone 2 Container Preservation** (#234) - YAML frontmatter now preserved through `emit()` round-trips
  - Parser correctly stored `raw_frontmatter` on `Document` AST but emitter silently discarded it
  - `emit()` now prepends frontmatter byte-for-byte before grammar sentinel and envelope
  - Empty and whitespace-only frontmatter correctly treated as absent (prevents empty `---\n\n---` blocks)
  - All three MCP tools inherit preservation automatically via `emit()` pipeline
  - Skill files, pattern files, and agent files with YAML discovery headers now work correctly with `octave_write`
  - 9 new tests: round-trip, byte-for-byte fidelity, format options interaction, edge cases

### Architecture

- **Three-Zone Model** fully implemented:
  - Zone 1: Normalizing DSL — canonical operators, unicode normalization, deterministic emit (enforced since v1.0.0)
  - Zone 2: Preserving Container — YAML frontmatter byte-for-byte preservation (completed in this release)
  - Zone 3: Explicit Literal Zones — fenced code blocks with zero processing (new in this release)
- North Star updated to v1.2 reflecting Three-Zone Model as structural pattern

### Quality Gates

- All changes reviewed per tier requirements (CRS + CE dual gate)
- 2039 tests passing, 0 failures
- Constitutional compliance verified: I1, I2, I3, I4, I5

## [1.2.1] - 2026-02-15 - "Specification Refinement" (Re-release)

This is a re-release of v1.2.0 to fix a critical packaging issue where `__version__` in `__init__.py` was not synchronized with `pyproject.toml`.

### Fixed
- **Package Version Synchronization** (#231) - Critical fix for version reporting
  - Updated `__version__ = "1.2.1"` in `src/octave_mcp/__init__.py` to match `pyproject.toml`
  - v1.2.0 on PyPI contained incorrect version "0.6.1" in the package code
  - This caused installation verification failures and incorrect version reporting

**Note:** v1.2.0 should be considered broken and v1.2.1 should be used instead. The v1.2.0 release will be yanked on PyPI.

### All v1.2.x Changes

Same features and fixes as v1.2.0 (see below), but with correct version synchronization.

## [1.2.0] - 2026-02-15 - "Specification Refinement" Release (YANKED - use v1.2.1)

This release enhances the specification suite with improved skills and agents specs, and introduces Streamable HTTP transport for web-based client access.

### Added
- **Streamable HTTP Transport** (#218, #221) - Web-based clients can now access OCTAVE tools via HTTP
  - Single `/mcp` endpoint per MCP Streamable HTTP specification
  - DNS rebinding protection enabled by default via `TransportSecuritySettings`
  - Localhost binding (127.0.0.1) by default for security
  - CLI support: `--transport http --port 8080 --host 127.0.0.1`
  - Environment variables: `MCP_TRANSPORT`, `MCP_HOST`, `MCP_PORT`
  - Health check endpoint at `/health` for load balancers
  - Stateless mode support for serverless deployments (`--stateless`)
  - New optional `[http]` dependency group: `pip install octave-mcp[http]`
  - 31 new tests covering transport, security, CLI, and integration
- **Enhanced Skills Specification** (#225) - octave-skills-spec v8.0 with canonical structure requirements
  - Compression mandate for all skills (AGGRESSIVE tier minimum)
  - Standardized canonical sections: ESSENCE, SYNTAX, CONSTRAINTS, VALIDATE
  - Clarified that archetype vocabulary is open (extensible), not closed
- **Enhanced Agents Specification** (#225) - octave-agents-spec v6 improvements
  - Added `AUTHORITY` as optional field for agent role hierarchy
  - Enables explicit authority level declarations for agent coordination

### Changed
- **Documentation Clarity** (#229) - README improvements for generative constraints
  - Clarified implementation status of generative holographic contracts
  - Updated feature documentation to reflect current capabilities

### Fixed
- **Specification Syntax** (#227) - Fixed OCTAVE spec compliance issues
  - Fixed `MARKDOWN_EMBEDDING` value quoting to prevent lexer errors
  - Aligned specs and `octave_write` tool with markdown code fence syntax
  - Ensures all specifications parse correctly without syntax warnings

### Quality Gates
- All changes reviewed per tier requirements
- Constitutional compliance verified: I1, I3, I5
- HTTP transport includes comprehensive security testing

## [1.1.0] - 2026-02-02 - "Decision Scaffolding" Release

This release enhances OCTAVE Primers with decision scaffolding for semantic compression, corrects token budget specifications to match empirical measurements, and fixes parser comment preservation edge cases.

### Added
- **Compression Primer Decision Scaffolding** (#220) - Enhanced primer enables tier-based compression judgment
  - `§2::DECIDE` section with explicit tier selection (LOSSLESS/CONSERVATIVE/AGGRESSIVE/ULTRA)
  - `PRESERVE` and `DROP` rules per tier for semantic judgment
  - Concrete MAP section showing prose→OCTAVE transformations
  - Complex ONE_SHOT demonstrating hierarchy, flow, and tension operators together
  - `⊕` synthesis operator added to syntax reference
- **Universal LLM Onboarding Architecture** (#214, #215) - Research documentation for JIT literacy injection
  - Wind/Wall/Door debate transcript demonstrating synthesis methodology
  - Proof of concept for primer-based agent bootstrapping

### Changed
- **Primer Token Budget Corrected** (#220) - Spec updated to match empirical tiktoken measurements
  - `TOKEN_BUDGET::MAX[60]` → `MAX[300]_RECOMMENDED[200-260]`
  - Anti-pattern: "Exceeding_100_tokens" → "Exceeding_300_tokens"
  - Added note: OCTAVE syntax tokenizes ~5x word count due to `::`, `→`, `⊕`, `⇌`, `§` operators
  - Validation criteria: `tokens<60` → `tokens<300`
- **README Literacy Primer** (#215) - Embedded primer directly in README for instant LLM onboarding
- **Core Spec Token Count** (#216) - Corrected META.TOKENS from ~2500 to ~2650

### Fixed
- **Parser Comment Preservation** (#217, #219) - Leading comments inside sections now preserved before first child
  - Previously, comments at the start of a section block were dropped during parsing
  - Now correctly captured in AST and emitted in canonical output
  - Added regression tests to prevent future issues

### Quality Gates
- All changes reviewed per tier requirements
- Constitutional compliance verified: I1, I3, I4
- Primer changes maintain ULTRA compression tier

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

[Unreleased]: https://github.com/elevanaltd/octave-mcp/compare/v1.6.0...HEAD
[1.6.0]: https://github.com/elevanaltd/octave-mcp/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/elevanaltd/octave-mcp/compare/v1.4.1...v1.5.0
[1.4.1]: https://github.com/elevanaltd/octave-mcp/compare/v1.4.0...v1.4.1
[1.4.0]: https://github.com/elevanaltd/octave-mcp/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/elevanaltd/octave-mcp/compare/v1.2.1...v1.3.0
[1.2.1]: https://github.com/elevanaltd/octave-mcp/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/elevanaltd/octave-mcp/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/elevanaltd/octave-mcp/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/elevanaltd/octave-mcp/compare/v0.6.1...v1.0.0
[0.6.1]: https://github.com/elevanaltd/octave-mcp/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/elevanaltd/octave-mcp/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/elevanaltd/octave-mcp/compare/v0.4.1...v0.5.0
[0.4.1]: https://github.com/elevanaltd/octave-mcp/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/elevanaltd/octave-mcp/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/elevanaltd/octave-mcp/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/elevanaltd/octave-mcp/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/elevanaltd/octave-mcp/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/elevanaltd/octave-mcp/releases/tag/v0.1.0
