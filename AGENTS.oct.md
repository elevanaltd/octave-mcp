===OCTAVE_MCP_AGENT_GUIDANCE===
META:
  TYPE::AGENT_GUIDANCE
  VERSION::"1.0"
  PURPOSE::"AI assistant bootstrap for OCTAVE MCP development"
  AUDIENCE::AI_AGENTS

§1::IDENTITY
  PROJECT::"OCTAVE MCP Server"
  ESSENCE::"Deterministic document protocol with loss accounting"
  VALUE::"OCTAVE→MCP tools make structured AI communication auditable"

§2::BOOTSTRAP
  QUALITY_GATES::[
    "mypy src",
    "ruff check src tests",
    "black --check src tests",
    "pytest"
  ]
  DEV_SETUP::"docs/guides/development-setup.md"
  QUICK_START::"README.md§Quick_Start"
  ARCHITECTURE::"specs/README.oct.md"

§3::CORE_CONSTRAINTS
  I1::SYNTACTIC_FIDELITY
    RULE::"Normalization alters syntax, never semantics"
    IMPLEMENTATION::"Canonical form must be idempotent"
  I2::DETERMINISTIC_ABSENCE
    RULE::"Distinguish absent vs null vs default"
    IMPLEMENTATION::"Use Absent sentinel type"
  I3::MIRROR_CONSTRAINT
    RULE::"Reflect only what's present, create nothing"
    IMPLEMENTATION::"No semantic inference or guessing"
  I4::TRANSFORM_AUDITABILITY
    RULE::"Every transformation logged with stable IDs"
    IMPLEMENTATION::"RepairLog tracks all changes"
  I5::SCHEMA_SOVEREIGNTY
    RULE::"Validation status visible in output"
    IMPLEMENTATION::"Validation field in canonical output"

§4::CODE_STYLE
  PYTHON::"3.11+"
  TYPE_SAFETY::"mypy strict mode (no Any, full hints)"
  LINE_LENGTH::120
  WORKFLOW::"TDD (test → implement → refactor)"
  COMMITS::[feat,fix,docs,test,refactor,chore]

§5::ANTI_PATTERNS
  FORBIDDEN::[
    "File variants (spec-v2.md, config-UPDATED.yaml)",
    "Personal info, API keys, credentials",
    "Machine-specific paths (use relative)",
    "Semantic inference in parser/validator",
    "Silent normalization without RepairLog"
  ]

§6::STRUCTURE
  SRC::"src/octave_mcp/[core|cli|mcp|schemas]"
  TESTS::"tests/[unit|integration|properties]"
  SPECS::"specs/*.oct.md (OCTAVE protocol v5.1.0)"
  DOCS::"docs/[guides|architecture|adr|research]"
  TOOLS::[octave,octave-mcp-server]

§7::TESTING
  UNIT::"pytest tests/unit/ (fast, isolated)"
  INTEGRATION::"pytest tests/integration/ (end-to-end)"
  PROPERTIES::"pytest tests/properties/ (hypothesis)"
  COVERAGE::"90% minimum (current: 90%)"
  TESTS_PASSING::1610

§8::MCP_TOOLS
  TOOLS::3
  octave_validate::"Schema validation + canonical form"
  octave_write::"Unified create/modify (content OR changes mode)"
  octave_eject::"Format projection (octave|json|yaml|markdown)"

§9::WORKFLOW_PATTERN
  FEATURE::[
    "Write failing test → tests/unit/",
    "Implement → src/octave_mcp/",
    "Pass quality gates",
    "Commit → feat: description"
  ]
  BUG_FIX::[
    "Test reproducing bug",
    "Fix implementation",
    "Verify test passes",
    "Commit → fix: description"
  ]

§10::RESOURCES
  PHILOSOPHY::"docs/guides/octave-philosophy.md"
  CORE_SPEC::"src/octave_mcp/resources/specs/octave-core-spec.oct.md"
  GRAMMAR::"docs/grammar/octave-v1.0-grammar.ebnf"
  API_DOCS::"docs/api.md"
  MCP_SETUP::"docs/mcp-configuration.md"
  DEVELOPMENT::"docs/guides/development-setup.md"

===END===
