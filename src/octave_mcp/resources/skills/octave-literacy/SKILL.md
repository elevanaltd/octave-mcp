---
name: octave-literacy
description: "LLM-native structured communication format. Teaches OCTAVE syntax rules, canonical forms, the inner language, and warning prevention for zero-error .oct.md authoring."
allowed-tools: ["Read", "Write", "Edit"]
triggers: ["octave format", "write octave", "octave syntax", "structured output", "OCTAVE basics", "OCTAVE literacy", "OCTAVE structure", "key::value", "OCTAVE notation", "llm communication", "loss accounting"]
version: "5.1.0"
---

===OCTAVE_LITERACY===
META:
  TYPE::SKILL
  VERSION::"5.1.0"
  STATUS::ACTIVE
  PURPOSE::"Zero-error OCTAVE authoring: syntax rules, canonical forms, the inner language, warning prevention, governance-artefact grammar"
  OCTAVE::"Olympian Common Text And Vocabulary Engine: a loss accounting system for LLM communication"
  AUDIENCE::LLM<exclusively>
  SPEC_REFERENCE::octave-core-spec.oct.md
  NEXT_SKILLS::[octave-mastery,octave-compression]
  PATTERNS::[octave-tool-reference]
---
§0::CONSUMPTION_DIRECTIVE
  DIRECTIVE::"Write in note form, in plain words: tools read keys, not glyphs; structure lives in keys, sections and lists, meaning in quoted sentences (§4b)."
§1::CORE_SYNTAX
  ASSIGNMENT::"`KEY::value`: double colon, no spaces around it"
  BLOCK::"`KEY:`, newline, 2-space indented children; for a value with nested children"
  CHOICE::"scalar value: ASSIGNMENT; nested children: BLOCK; never mix"
  LIST::"`[a,b,c]`: square brackets; never YAML bullets"
  STRING::"bare word if no spaces or special characters, otherwise double-quoted; escape an inner double quote as `\"`"
  NUMBER::"`42`, `3.14` or `-1e10`; no quotes"
  BOOLEAN::"`true` or `false`, lowercase only"
  NULL_VALUE::"`null`, lowercase only"
  COMMENT::"`//` at line start or after a value; comments carry orientation, never a rule, because parsers drop them"
  §1b::BRACKET_FORMS
    CONTAINER::"`[a,b,c]`: bare brackets are a list"
    ANNOTATION::"`NAME<qualifier>`: a semantic facet on an identity; it qualifies what something IS"
    ANNOTATION_DISCIPLINE::"annotations are short qualifiers: 1 to 3 words, at most 32 characters, identifier only; multi-word reasoning goes in a sibling RATIONALE value as a quoted note-form sentence"
    CONSTRUCTOR::"`NAME[args]`: structured arguments on an identifier; it parameterizes what something DOES"
    INLINE_MAP::"`[key::val, key2::val2]`: dense key-value pairs; values must be atoms; no nesting"
    SEPARATE_FORMS::"separate forms; the lenient parser turns square into angle brackets only for annotation uses, genuine constructors keep square; in doubt: identity or archetype qualifier, angle; parameterized operation or schema, square"
    AUTHORING::"use `NAME<x>` or `NAME[x]` only where a schema field or parser expects them (archetypes, schema constraints); never inside a quoted value"
    REFERENCE:
      ```
      ATHENA<strategic_wisdom> // annotation: identity facet
      LLM<exclusively> // annotation
      REGEX[pattern] // constructor: validation arguments
      ENUM[a,b,c] // constructor
      JIT_GRAMMAR_COMPILATION[META→GBNF] // constructor
      ```
  §1c::LITERAL_ZONES
    SYNTAX::"KEY, then newline, then a fence of 3 or more backticks"
    RULES::[
      "zero processing between fences",
      "tabs allowed",
      "NFC bypass",
      "info tag preserved"
    ]
    USE_CASES::[
      "embedded code",
      "teaching examples",
      "verbatim content",
      "OCTAVE about OCTAVE"
    ]
    FENCE_SCALING::"wrap content holding N-backtick fences with N+1 backticks"
  §1d::BLOCK_CANONICAL_FORMS
    RULE::"a multi-field token (any key whose value is a map) takes BLOCK form; never an inline-array root; never flat prefix-scalars"
    THREE_SHAPES:
      ```
      ✓ BLOCK (canonical):         ✗ inline-array root:              ✗ flat prefix-scalars:
        PLATFORM:                    PLATFORM::[                        PLATFORM_TOKEN::HO-v1
          TOKEN::HO-v1                 TOKEN::HO-v1,                   PLATFORM_RUNTIME_FLOOR::"Node >=22"
          RUNTIME:                     RUNTIME::[FLOOR::"Node >=22"]]  PLATFORM_RUNTIME_BECAUSE::"…"
            FLOOR::"Node >=22"
            BECAUSE::"…"
      ```
    SCALAR_LIST_ONLY::"inline arrays `[a,b,c]` are for scalar lists only (`IMMUTABLES::[...]`, `CONSOLIDATES::[a,b]`), never for maps of maps"
    WHY:
      BLOCK::"indented children inherit parent context: fewer key tokens, better LLM attention, no `W_DUPLICATE_KEY` collisions"
      NOT_INLINE_ARRAY_ROOT::"inline map as token root: non-canonical for map tokens even with atomic values (§1b INLINE_MAP); gives `E_NESTED_INLINE_MAP` once a child needs nesting; restructuring later is waste; use BLOCK form from the start"
      NOT_FLAT_PREFIX::"`PARENT_CHILD1` and `PARENT_CHILD2` key proliferation destroys hierarchical grouping and LLM attention"
§2::OPERATORS
  AUTHORING::"write the relation in words (copied to, blocked by, versus, not equal to, at most); the operators below appear in documents you read, not in what you write"
  SCHEMA_EXCEPTION::"schema-definition files keep their holographic constraints, because the validator reads them (mastery §4)"
  READING_REFERENCE:
    ```
    CONTAINER::"[] — List [a,b,c]"
    CONCAT::"⧺ — Mechanical join A⧺B | ASCII: ~"
    SYNTHESIS::"⊕ — Emergent whole A⊕B | ASCII: +"
    TENSION::"⇌ — Binary opposition A⇌B | ASCII: vs (requires word boundaries: 'A vs B' valid, 'AvsB' invalid)"
    CONSTRAINT::"∧ — Inside brackets only [A∧B∧C]; bare A∧B invalid | ASCII: &"
    ALT::"∨ — Alternative A∨B | ASCII: |"
    FLOW::"→ — Right-associative A→B→C, often in lists [A→B→C] | ASCII: ->"
    TENSION_ARITY::"⇌ is binary only: A⇌B valid, chained A⇌B⇌C invalid"
    SECTION_REF::"§ — target anchor, e.g. §3c::ASSEMBLY_RULES"
    LINE_COMMENT::"// — line start or after value"
    ```
§3::CRITICAL_RULES
  RULES::[
    "Never put spaces around `::`: write `KEY::value`, not `KEY :: value`.",
    "Indent exactly 2 spaces per level; no tabs.",
    "Keys match `[A-Za-z_][A-Za-z0-9_]*`: they start with a letter or underscore.",
    "Envelopes: `===NAME===` opens and `===END===` closes; NAME matches `[A-Z_][A-Z0-9_]*`.",
    "`true`, `false` and `null` are lowercase only, not True, False or NULL.",
    "Quote any value that contains `§`, for example `\"see §3b\"`, never a bare `§3b`.",
    "The file extension `.oct.md` is canonical.",
    "A bare numeric key triggers `W_NUMERIC_KEY_DROPPED`: use a named key, or a list.",
    "An unkeyed prose line triggers `W_BARE_LINE_DROPPED`; `//` comments and list body lines are exempt.",
    "A section header carries no value: write `§N::NAME`, then children on the following lines; a value on the section header line is parsed as a bare header and silently dropped.",
    "An empty `KEY::` opens no block: it becomes a newline value, and the indented lines below hoist into the enclosing scope and collide with the next record's keys (`W_DUPLICATE_KEY`, last write wins); a block opener is `KEY:`, single colon.",
    "Indent section contents 2 spaces under the section header: column-0 keys are file scope, so a key repeated across sections collapses to the last copy.",
    "Address edits as section dot key (`§N.KEY`): changes mode mis-targets unaddressed keys (#517).",
    "Quotes carry no meaning: a single-token quoted value is dequoted on write (`TN_IDENTIFIER_DEQUOTE`).",
    "Escape an inner double quote as `\"`; a raw inner quote coalesces words (`W_LENIENT_MULTI_WORD_COALESCE`).",
    "VALIDATED is not a receipt: read `repairs[]` too; clean means empty errors, warnings and repairs."
  ]
  §3b::V6_ENVELOPE_STRUCTURE
    FILE_STRUCTURE::"`===NAME===`, then META, then an optional `---` separator, then the body, then `===END===`"
    SEPARATOR::"`---` after META marks the metadata boundary for discovery and indexing tools"
    META_REQUIRED::[TYPE,VERSION]
    META_OPTIONAL::[STATUS,UPDATED]
    STATUS_NOTE::"STATUS in META is the document lifecycle (ACTIVE, DRAFT); STATUS in the body is the subject's state; both are valid"
    SCHEMA_GAP::"under `schema=META` STRICT, every META key other than TYPE, VERSION, STATUS and ID gives `E007`, including PURPOSE, UPDATED, CANONICAL, SOURCE and TOKENS (#514)"
    POINTERS::"CONTRACT and GRAMMAR: mastery §4; COMPRESSION_TIER and LOSS_PROFILE on compressed artefacts: compression §2"
  §3c::ASSEMBLY_RULES
    RULE::"when concatenating profiles, omit the intermediate `===END===`; only the final one terminates"
    USE_CASES::[
      "agent context injection",
      "specification layering",
      "multi-part documents"
    ]
  §3d::SECTION_PATH_REFERENCES
    SYNTAX::"`§N::NAME` is a section reference; `§3b::V6_ENVELOPE_STRUCTURE` is a valid cross-reference"
    QUOTING::"quote `§` in a content value: `VALUE::\"see §3b\"`, not `VALUE::§3b`"
    NESTING::"`§3b` inside `§3` is a subsection; prefix digit tracks depth"
§4::WARNING_PREVENTION
  // Parser-drop codes: each is silent data loss at parse time.
  W_BARE_LINE_DROPPED::"cause: line with no `KEY::` prefix; fix: add a key or use a `//` comment"
  W_NUMERIC_KEY_DROPPED::"cause: bare integer key (`1::thing`); fix: use a named key, or a list"
  W_DUPLICATE_KEY::"cause: same key twice in one scope, last write wins; fix: BLOCK form per §1d or §7b; hidden causes (§3 rules): empty `KEY::` meant as `KEY:`, and column-0 keys across sections; STRICT still says VALIDATED, only `repairs[]` shows the loss"
  W_UNQUOTED_SECTION_IN_VALUE::"cause: bare `§` inside a value; fix: quote the value (§3 rules)"
  W_INLINE_ARRAY_ROOT::"cause: `TOKEN::[KEY::v,...]`, a map as inline root; fix: BLOCK form per §1d"
  W_FLAT_PREFIX_SCALAR::"cause: `PARENT_CHILD::v` key-prefix flattening; fix: BLOCK form per §1d"
  RECEIPTS::"`octave_write` returns `corrections[]` and `warnings[]`; `octave_validate`, `repairs[]`, `repair_log[]` and `warnings[]`; empty `warnings[]` does not prove no normalisation; read octave-tool-reference §3 before trusting either"
  §4b::INNER_LANGUAGE
    APPLIES::"PITH: every value, item, step and sentence you write, in any shape"
    RULES::[
      "Write in note form: fragments allowed; no articles or filler; every number, name, path and command kept.",
      "Identifiers (names, numbers, dates, paths, SHAs, tickets, PRs) copied exactly, in backticks, never shortened or merged.",
      "Hedges and conditions copied verbatim: if, could and unverified are facts.",
      "Relations in words (copied to, blocked by, versus); no operator glyphs in prose, values or items. Still allowed: holographic constraints in schema-definition files, which the validator reads.",
      "Never invent to fill a slot or field: write `none` or `not known`.",
      "No model-written ids, tags, counts or census on items or rules. Still allowed: identifiers copied from a source, and `STEP_n` keys in a runbook.",
      "A prohibition that can fire on its own carries one calibration sentence saying what is still allowed; not every rule needs one.",
      "Judgements are written as the review's or the finding's, never as 'Name: judgement'.",
      "Multi-line code or commands go in a fenced block under the slot or step that needs them.",
      "A source that contradicts itself is kept both ways and flagged.",
      "No snake_case blobs as prose; no mythology as instruction vocabulary. Still allowed: mythology as style where it fits exactly, and atoms in keys and enum values."
    ]
    RUNBOOK::"runbooks: numbered steps, no rule history, no forward references"
§5::ANCHOR_KERNEL
  TARGET::"parser-safe OCTAVE in PITH"
  NEVER::[
    "tab characters outside literal zones",
    "bare numeric keys",
    "markdown headings or bullets inside the envelope",
    "nested inline maps"
  ]
  MUST::[
    "Note form",
    "Exact identifiers (copied exactly, in backticks; never shortened or merged)",
    "Hedges verbatim",
    "Relations in words (no operators in prose or values)",
    "Nothing invented (none or not known)",
    "No writer-made ids, tags or counts",
    "One calibration sentence",
    "Judgement unattributed",
    "Code in fences",
    "Contradictions kept and flagged",
    "Plain vocabulary (no blobs, no mythology as instruction words)",
    "every line keyed, values with spaces or punctuation quoted",
    "no unkeyed lines",
    "no value on a section header",
    "contents indented under the header",
    "edits addressed as section dot key (§N.KEY)",
    "receipt fields read, not the status",
    "section signs quoted inside values",
    "KEY: opens a block, KEY:: never does",
    "envelope line, META with TYPE and VERSION, body, closing line",
    "lists in square brackets; true, false, null lowercase"
  ]
  GATE::"Is every line keyed, in PITH, identifiers exact, receipts clean?"
§6::WORKED_EXAMPLE
  SHOWS::"envelope, META, separator, note-form values, lists, BLOCK and ASSIGNMENT per §1"
  EXAMPLE:
    ```
    ===DECISION===
    META:
      TYPE::DECISION
      VERSION::"1.0.0"
      STATUS::ACTIVE
    ---
    CONTEXT::"API redesign; Q2 window closes `2026-06-30`"
    DECISION::"extract auth and payments into independent services"
    BECAUSE::"shared deploys block payments releases; auth outages take checkout down"
    PHASES:
      PLAN::["research","design"]
      BUILD::["code","test"]
    METRICS:
      LATENCY::"under 200 ms at p99"
      AVAILABILITY::"99.95 percent"
    RISKS::"not known; no load test yet"
    ===END===
    ```
§7::GOVERNANCE_AUTHORING
  UPOG::"Universal Parse-Only Governance: structure for governance artefacts (North Stars, ADRs, RFCs, project-context docs, agent definitions); builds on the §4b inner language and §3 rules; enforced by the strict parser, this skill and the octave-secretary write gate"
  §7a::ORGANIZING_PRINCIPLE
    PRINCIPLE::"the strict AST parse is the gate and this skill is the schema, so no per-doctype schema registration; governance bodies are schema-exempt by declaration, and the META envelope still validates"
    APPLIES_TO::[
      "North Star summaries",
      "architectural decision records",
      "requests for comments",
      "project-context documents",
      "agent definitions",
      "any repeated-entity governance artefact"
    ]
  §7b::BLOCK_FORM_FOR_REPEATED_ENTITIES
    WHY::"chained form `I1::NAME::[PRINCIPLE::v, WHY::v, STATUS::v]` reads as an assignment under the strict 1.13 lexer, hoisting inner pairs to file top level; across I1 to IN, PRINCIPLE, WHY and STATUS collide as `W_DUPLICATE_KEY`, 3 per record, last write wins"
    PATTERN::"`ID<LABEL>:` block opener plus indented children"
    SYNTAX::"the block opener uses the `ID<LABEL>:` form; the `NAME<facet>` annotation (§1b) carries the human-readable label; indented children scope keys per parent"
    WRONG_EXAMPLE::"`I1::PERSISTENT_COGNITIVE_CONTINUITY::[PRINCIPLE::v,WHY::v,STATUS::v]`"
    EXAMPLE_CANONICAL:
      ```
      §1::IMMUTABLES
        I1<PERSISTENT_COGNITIVE_CONTINUITY>:
          PRINCIPLE::"persist context, decisions and learnings across sessions"
          WHY::"amnesia causes system failure; prevents re-learning cost"
          STATUS::PENDING
          OWNER::implementation-lead
          GATE::B1
        I2<STRUCTURAL_INTEGRITY_PRIORITY>:
          PRINCIPLE::"correctness and compliance take precedence over velocity"
      ```
    GUARANTEE::"each `I<N>` block scopes its children, so no `W_DUPLICATE_KEY` across the section"
    APPLIES_ALSO_TO::[
      "assumptions A1 to AN",
      "ADR records",
      "RFC records",
      "constrained variables",
      "any homogeneous repeated record block"
    ]
  §7c::MARKDOWN_ERADICATION
    WHY::"markdown `##` headings inside an envelope fail `E_TOKENIZE` under the strict 1.13 lexer (the `(` in a heading such as `## IMMUTABLES (6 Total)` trips it); `§N::NAME` is structurally targetable"
    RULE::"governance `.oct.md`: no markdown headings inside the envelope"
    SCOPE::"active governance artefacts; generators still emitting legacy `##` headings (template files, the `/ns-summary-create` skill, the north-star-architect agent) are a follow-up, not retro-non-compliant, but MUST migrate before the next governance amendment cycle"
    TRANSFORM:
      FROM::"^## (.*)$"
      TO::"§N::SECTION_NAME"
    EXAMPLE_BEFORE::"## IMMUTABLES (6 Total)"
    EXAMPLE_AFTER:
      ```
      §1::IMMUTABLES
        STATUS::ACTIVE
      ```
  §7d::SCHEMA_EXEMPTION_VIA_CONTRACT
    RULE::"`CONTRACT::HOLOGRAPHIC<parse_only_governance>` in META: existing documents carry it; no consumer reads it; do not add it to new documents"
  §7e::CANONICAL_AND_SOURCE_META
    PURPOSE::"path-tracking META fields, enforced by the canonical-paths pre-commit hook"
    CANONICAL::"runtime delivery path (for example `.hestai/north-star/...` or `.hestai-sys/...`)"
    SOURCE::"git-committed source path (for example `src/<pkg>/_bundled_hub/...` or repo-local)"
    RULE::"every governance `.oct.md` requires both `META.CANONICAL` and `META.SOURCE`"
    PROJECT_LOCAL::"a file that lives only in the project tree has CANONICAL equal to SOURCE"
    BUNDLED_HUB::"source differs from canonical: CANONICAL points to `.hestai-sys/`, SOURCE points to `_bundled_hub/`"
  §7f::VALUE_FORM_DELEGATION
    RULE::"reasoning-field values (PRINCIPLE, WHY, RATIONALE, EVIDENCE and others) follow the note-form rule in the §4b rules list; never a bare snake_case blob (`W_SNAKE_CASE_BLOB`, octave-tool-reference §6::SNAKE_CASE_BLOB)"
  §7g::MIGRATION_CHECKLIST
    PURPOSE::"mechanical migration recipe; every legacy field kept verbatim, only the shape changes"
    STEP_1::"replace every `## Heading` with `§N::SECTION_NAME`"
    STEP_2::"replace every `I#::NAME::[KEY::v,...]` with an `I#<NAME>:` block and indented `KEY::v` children"
    STEP_3::"add `META.CANONICAL` and `META.SOURCE`"
    STEP_4::"run `octave_validate` STRICT and confirm empty warnings, errors and repairs"
    INVARIANT::"core structural field names kept (PRINCIPLE, WHY, STATUS, INHERITS, IS, IS_NOT, GATES, LOAD_FULL_NORTH_STAR_IF, THE_OATH and others); permitted splits where a legacy slot held several values: `ASSUMPTIONS::N[note]` into `ASSUMPTIONS_COUNT::N` and `ASSUMPTIONS_NOTE::note`; `RELATED::[issues]` or `[adrs]` into `RELATED_ISSUES::[...]` and `RELATED_ADRS::[...]`; `IF::trigger,THEN::[actions]` into `TRIGGER::trigger` and `ACTION::[actions]` (in a `PROTECTION_CLAUSE` block); splits mechanical and lossless"
  §7h::ENFORCEMENT_LOCI
    LOCI::[
      "This skill declares the pattern (vault delivery via `_bundled_hub`).",
      "The octave-secretary agent is the sole valid `.oct.md` write path and calls `octave_write` (procedure: octave-tool-reference).",
      "The octave-mcp 1.13 STRICT lexer refuses non-compliant grammar at parse."
    ]
    DRIFT_DETECTION::"a drift in any one locus is detectable: file hash on the bundled-hub skill source, and pre-commit OCTAVE validation"
===END===
