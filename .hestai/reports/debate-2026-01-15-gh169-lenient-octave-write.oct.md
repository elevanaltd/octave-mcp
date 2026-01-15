===DEBATE_TRANSCRIPT===

META:
  THREAD_ID::"2026-01-15-issue-169-lenient-octave-write"
  TOPIC::"GH#169: Design and implementation approach for `octave_write` lenient mode (Prettier-like auto-correction) with deterministic audit trail and diff-first output."
  MODE::fixed
  STATUS::synthesis

PARTICIPANTS::[Door,Wall,Wind]

TURNS::[
  T1::Wind[PATHOS]::"OPTIONS::[
  A_PRETTIFY_ONLY::\"lenient=true uses tolerant parse + canonical emit; still errors if parse fails\",
  B_PRETTIFY_PLUS_REPAIR::\"lenient=true also applies schema repair (enum casefold/type coercion) when schema provided\",
  C_ALWAYS_CANONICAL_SALVAGE::\"if parse fails, wrap raw text into a canonical carrier doc + log corrections; avoids catch-22\"
]

IDEAS::[
  DIFF_FIRST::\"Return unified diff + corrections log by default to save context; only return full canonical when requested\",
  CORRECTION_TIERS::[NORMALIZATION,LENIENT_PARSE,SCHEMA_REPAIR]→each_change_logged,
  FORBIDDEN::[semantic_inference,field_invention,target_invention]
]

QUESTIONS::[
  \"When lenient=true and parse fails, do we prefer error (Prettier) or salvage (always-canonical)?\",
  \"Should corrections_only return canonical preview, unified diff, or both?\",
  \"Do we want schema repair in octave_write, or keep it exclusive to octave_validate fix=true?\"
]",
  T2::Wall[ETHOS]::"VERDICT: Proceed with GH#169 only with deterministic + lossless guarantees and an explicit boundary between prettify/repair vs semantic translation.

[EVIDENCE]
- src/octave_mcp/mcp/write.py uses strict parse() and returns E_PARSE on failure.
- src/octave_mcp/mcp/validate.py uses parse_with_warnings() + repair() with audit surfaces.
- src/octave_mcp/resources/specs/octave-mcp-architecture.oct.md asserts lenient-in→canonical-out and “auditable not silent”.
- .hestai/context/context-negatives.oct.md forbids semantic inference.

YES_BUT:
1) Prettier analogy breaks at parse-failure: if we promise always-canonical, we must define a salvage carrier contract.
2) parse_with_warnings() may still drop bare/free-text lines (unexpected tokens). That is data loss unless we preserve bytes.
3) Issue #169’s semantic mapping examples must be opt-in, not default lenient.

GUARDS:
- lenient=true must pre-process would-be-dropped lines into deterministic STRING assignments under a known block BEFORE parsing.
- salvage carrier must embed original bytes verbatim and log a correction describing the wrap.
- corrections_only must be read-only (no mkdir/write side-effects).

QUESTIONS?
- Is salvage always-on for lenient=true, or a separate explicit mode?
- Does lenient imply schema repair, or keep repair exclusive to octave_validate fix=true?",
  T3::Door[LOGOS]::"1. DECISION: Implement GH#169 as deterministic canonicalization + optional schema repair + explicit salvage policy; keep semantic translation out of `octave_write` lenient by default.

2. API:
- Add `lenient: bool=false` and `corrections_only: bool=false` to `octave_write`.
- Return `diff_unified` (or upgrade `diff`), `corrections[]`, `canonical_hash`, `validation_status`.

3. PIPELINE:
- strict (default): tokenize repairs → parse() strict → emit() → validate (no repairs).
- lenient=true: tokenize repairs → preprocess free-text into deterministic RAW assignments → parse_with_warnings() → if schema: validate → repair(fix=True) → revalidate → emit().
- corrections_only=true: run pipeline but do not write.

4. SALVAGE POLICY:
- Trigger salvage only when parse fails OR tolerant parse would drop tokens.
- Canonical carrier: `===DOC===` + META(TYPE,VERSION defaults) + `BODY:` `RAW::<verbatim>` + `===END===`.
- Audit: always log wrap + all repairs into `corrections[]`.

5. PHASED IMPLEMENTATION:
- P1: Add flags + corrections_only no-write gate; add unified diff field.
- P2: Wire parse_with_warnings + map warnings into corrections.
- P3: Add RAW-preservation preprocessor to prevent silent drops.
- P4: Add optional schema repair in lenient (reuse `core/repair.py`) + tests.
- P5: Update docs (`docs/api.md`) to match real envelope + new flags.

6. TEST MATRIX:
- strict behavior unchanged.
- lenient quotes multiword values deterministically.
- lenient preserves free text as RAW (no loss).
- lenient schema enum casefold/type coercion logged.
- corrections_only does not write.
- diff_unified is compact and consistent.",
]

SYNTHESIS::"1. DECISION: Implement GH#169 by adding deterministic `lenient` + `corrections_only` to `octave_write`, keeping default strict behavior unchanged.
2. PRINCIPLE: Lenient mode = syntactic tolerance + schema repair (explicit), NOT semantic inference; any NL→OCTAVE translation is out-of-scope for `octave_write`.
3. CONTRACT: When parse would fail or drop tokens, use a canonical salvage carrier that embeds the original bytes verbatim and logs a correction (I4).
4. OUTPUT: Prefer diff-first (unified diff) + corrections log to minimize context; return full canonical only when requested.

===DEBATE_SYNTHESIS===
META:
  TYPE::DEBATE_SYNTHESIS
  ISSUE::GH_169
  TOPIC::\"octave_write lenient (Prettier-like)\"

RESOLUTION::[
  API::[
    octave_write_add_params::[lenient::bool=false,corrections_only::bool=false],
    response_add_fields::[diff_unified?],
    preserve_existing::[status,path,canonical_hash,corrections,diff,errors,validation_status]
  ],
  PIPELINE::[
    STRICT_DEFAULT::tokenize_repairs→parse_strict→emit→validate,
    LENIENT_TRUE::tokenize_repairs→preprocess_free_text_to_RAW_assignments→parse_with_warnings→(if schema: validate→repair→revalidate)→emit,
    CORRECTIONS_ONLY::no_write_side_effects
  ],
  SALVAGE_CONTRACT::[
    TRIGGER::parse_fail∨would_drop_tokens,
    CARRIER_DOC::\"===DOC=== + META defaults + BODY: RAW::<verbatim> + ===END===\",
    I4_AUDIT::\"wrap + every byte-change logged in corrections[]\"
  ],
  DIFF_FIRST::[
    DEFAULT_RETURN::unified_diff_when_small,
    FALLBACK::structural_summary_when_large
  ],
  NON_GOALS::[
    NEVER::semantic_inference_in_lenient_mode,
    NEVER::mythology_mapping_or_target_invention_as_autofix
  ]
]

FILES_RELEVANT::[
  specs::[src/octave_mcp/resources/specs/octave-mcp-architecture.oct.md,src/octave_mcp/resources/specs/octave-core-spec.oct.md,src/octave_mcp/resources/specs/octave-execution-spec.oct.md],
  constraints::[.hestai/context/context-negatives.oct.md],
  code::[src/octave_mcp/mcp/write.py,src/octave_mcp/mcp/validate.py,src/octave_mcp/core/parser.py,src/octave_mcp/core/repair.py]
]

NEXT_STEPS::[
  1::tests_red→green_for_lenient_and_corrections_only,
  2::implement_preprocessor_for_free_text_preservation,
  3::wire_schema_repair_in_lenient_path,
  4::update_docs_api_contract
]
===END==="

===END===
