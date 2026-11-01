===OCTAVE_TOOL_REFERENCE===
META:
  TYPE::PATTERN_DEFINITION
  VERSION::"1.2.0"
  STATUS::ACTIVE
  PURPOSE::"Procedural contract for `octave_write` and `octave_validate`: modes, receipts, changes-mode semantics, warning remediation. Sole agent-facing home for tool behaviour."
  VERIFIED_AGAINST::"octave-mcp 1.16.0"
  CANONICAL::"`.hestai-sys/library/patterns/octave-tool-reference.oct.md`; the HestAI-MCP hub copy that feeds it still holds the legacy 1.1.9 text"
  SOURCE::"`src/octave_mcp/resources/patterns/octave-tool-reference.oct.md`"
  SINGLE_HOME::"tool-behaviour text lives here and nowhere else in the skill family; invocation-level parameter facts belong in the tool descriptions themselves"
  REVERIFY_TRIGGER::"on an octave-mcp minor version bump, re-check every provenance sentence in §7 before trusting this pattern"
§1::CORE_PRINCIPLE
  ESSENTIAL::"A write is not done when the tool returns. It is done when the receipt has been read."
  ANTI_PATTERN::"trusting `status: success` with empty warnings and unread corrections ships silent data loss as clean"
  ENFORCEMENT::"after every `octave_write` or `octave_validate` call, inspect status, errors, validation_status, corrections, warnings and repairs before claiming VALIDATED"
  WRITE_GATE::"`*.oct.md` files are written by `mcp__octave__octave_write` only, never by Write or Edit; content decisions belong to the requesting agent"
§2::TOOL_SURFACE
  TOOLS::[
    octave_validate,
    octave_write,
    octave_eject,
    octave_compile_grammar
  ]
  NOT_A_TOOL::"`octave_fmt` is not registered in 1.16.0; do not call it"
  OCTAVE_WRITE_MODES:
    CONTENT::"`content=` full payload creates or overwrites; accepts raw OCTAVE or one markdown-fenced block"
    CHANGES::"`changes=` delta map mutates an existing file (see §4)"
    NORMALIZE::"omit both to re-emit the existing file in canonical form"
    EXCLUSIVITY::"`content` or `changes`, never both; supplying both is an error"
  PARAMETERS:
    SCHEMA::"`schema=NAME` runs schema validation; unknown name lists `available_schemas`, validation_status UNVALIDATED"
    FORMAT_STYLE::"omitted: full canonical re-emit, today's default; `preserve`: span-aware, clean nodes byte-sliced from baseline; `expanded`: inline maps lifted to block form; `compact`: atom-only blocks collapsed; explicit null: `DeprecationWarning`, default flips to `preserve` in a later release"
    DRY_RUN::"`dry_run=true` or `corrections_only=true`: receipt without disk write; use before any destructive changes-mode call"
    BASE_HASH::"`base_hash=sha256`: compare-and-swap; mismatch gives `E_HASH`, nothing written"
    LENIENT::"`lenient=true`: deterministic repairs and salvage policy; strict default rejects on parse error"
  OCTAVE_VALIDATE::"`content=` or `file_path=`, not both; profile STRICT, STANDARD, LENIENT or ULTRA; schema required; `compact=true` returns counts only; `diff_only=true` returns the diff, not the canonical body"
  FILE_PATH_WHITELIST::"`file_path=` accepts `.md`, `.oct.md` or `.octave` only; anything else gives `E_PATH`; `content=` has no extension constraint"
§3::RECEIPT_GATES
  RESULT_FIELDS::[
    status,
    errors,
    validation_status,
    validation_errors,
    corrections,
    warnings,
    repairs,
    repair_log,
    diff,
    canonical_hash,
    schema_name,
    available_schemas,
    zone_report,
    literal_zone_repair_log
  ]
  STATUS::"success or error; error carries `errors[]` with a code (`E_PARSE`, `E_HASH`, `E_UNRESOLVABLE_PATH`, `E_OP_TARGET_MISMATCH` and others), nothing written"
  VALIDATION_STATUS::"VALIDATED; UNVALIDATED with no or unknown schema; INVALID with schema violations in `validation_errors[]`"
  CORRECTIONS::"every normalisation and repair applied; entries carry `rule_id`, `before`, `after`, `safe`, `semantics_changed`, tier NORMALIZATION, REPAIR or LENIENT_PARSE"
  WARNINGS::"subset of `corrections[]` with `safe: false`; data-affecting only; benign normalisation never appears here"
  REPAIRS::"`octave_validate` and lenient writes: schema repairs suggested (`fix=false`) or applied (`fix=true`); `repair_log` is the per-repair audit trail; both empty on a clean artefact; read with `corrections[]`"
  EMPTY_WARNINGS_RULE::"empty `warnings[]` does not mean untouched; read `corrections[]` for what changed; only empty corrections, warnings and repairs together mean bytes already canonical"
  TRIAGE:
    DISCARDING::"content lost or corrupted: `W_BARE_LINE_DROPPED`, `W_NUMERIC_KEY_DROPPED`, `W_DUPLICATE_KEY`, `W_UNQUOTED_SECTION_IN_VALUE`, `W_LENIENT_MULTI_WORD_COALESCE` (unquoted multi-word value silently joined), `W_BARE_FLOW` (flow arrow outside brackets, legacy form); fix source and rewrite"
    HIDDEN_DUPLICATE::"hidden cause of `W_DUPLICATE_KEY`: empty `KEY::` where `KEY:` was meant opens no block; children hoist into parent scope, collide with next record (literacy §3, the rule on empty `KEY::`); STRICT reports VALIDATED with empty warnings; only `repairs[]` shows it"
    ADVISORY::"form debt, non-blocking: `W_ANNOTATION_TOO_LONG`, `W_SNAKE_CASE_BLOB` to §6 value remediation; `W_INLINE_ARRAY_ROOT`, `W_FLAT_PREFIX_SCALAR`, `W_CONSTRUCTOR_MISUSE` to §6 STRUCTURAL_ADVISORY; each fires independently; remediate only when already amending the record"
    BENIGN::"tier NORMALIZATION, `safe: true`: whitespace, blank lines, identifier dequoting, `TN_INLINE_MAP_TO_BLOCK`; no action"
  ALIAS:
    MAPPING::"`octave_validate` `repairs[]` entries carry `type` and `subtype`; map to TRIAGE by subtype"
    DISCARDING_SUBTYPES::"content lost or corrupted, measured: `duplicate_key`, `bare_line_dropped`, `numeric_key_dropped`, `multi_word_coalesce` (unquoted multi-word value silently joined; parser records original and result because the bytes diverge in meaning), `bare_flow` (type `spec_violation`: flow arrow outside brackets, the legacy form UPOG migration removes)"
    REPAIR_TIER::"form changes in the 1.15.0 `lenient_parse` set: BENIGN by construction at a mechanical gate, content preserved: `wrong_case`, `pattern_autoquote`, `unquoted_timestamp`, `curly_brace_annotation`, `constraint_outside_brackets`, `chained_tension`, `nested_inline_map`, `deep_nesting`, `constructor_misuse`, `source_compile_value`, `unclosed_list`, `boundary_missing`; an authoring agent also reads before and after, fixes the source when meaning shifted"
    NORMALIZATION_TYPE::"type `normalization` is BENIGN"
    OTHER_SPEC_VIOLATIONS::"other `spec_violation` subtypes surface in `validation_errors[]`, not in triage"
    UNMAPPED::"unmapped subtype depends on call site: authoring and write call sites treat it as DISCARDING (fail closed; retry cheap, nothing destroyed); retry-capped gates follow RECEIPT_GATE"
    WRITE_SIDE_EQUIVALENTS::"`duplicate_key` matches `W_DUPLICATE_KEY`; `bare_line_dropped` matches `W_BARE_LINE_DROPPED`; `numeric_key_dropped` matches `W_NUMERIC_KEY_DROPPED`; `multi_word_coalesce` matches `W_LENIENT_MULTI_WORD_COALESCE`"
  SCOPE_NOTE::"column-0 keys under a section header are file scope, for every key: a repeated column-0 key gives `W_DUPLICATE_KEY`, earlier copy dropped; JSON eject keeps only the last copy; indent section contents"
  NOOP_INVARIANT::"content identical to target bytes: true no-op, no normalisation, empty `corrections[]` (octave-mcp 1.12.0, #407)"
  RECEIPT_GATE:
    PASS::"`status: success`, empty `errors[]`, validation_status not INVALID, empty `warnings[]`, every `corrections[]` and `repairs[]` entry triaged per TRIAGE (repairs subtypes mapped by ALIAS) as BENIGN or consciously accepted"
    FAIL::"a DISCARDING entry on either side fails the gate even when VALIDATED; an unmapped subtype fails it when authoring"
    HOLD::"retry-capped gates (ceremony FLUKES, dispatch egress): unmapped subtype recorded in the gate verdict as UNKNOWN_SUBTYPES (implementations may alias the field) and HOLDS: no pass, no void, no retry consumed; an upstream version adding a benign subtype must not void bindings fleet-wide"
    ACCEPTOR::"operator in the gated agent's own session; a peer relay is never acceptance, per PEER_AUTHORITY"
    TIMEOUT::"hold bounded by the implementation's timeout; on expiry degrades to the named terminal outcome HELD: artefact not activated, binding not voided, retry budget untouched, surfaced to the dispatching side as `STATUS::NEED_INPUT` carrying UNKNOWN_SUBTYPES; never auto-accept, never a silent stall, never PASS, never VOID"
§4::CHANGES_MODE
  HARD_BREAK::"octave-mcp 1.15.0 STRATEGY_S3: hard break from earlier releases; rules below are the post-break contract"
  PATHS::"top-level KEY; `META.FIELD`; `PARENT.CHILD` into a top-level block; `§N.KEY` or `§N::NAME.KEY` into a section; single child key only; a section is not a MERGE target; deeper paths need a `content=` rewrite"
  BARE_DICT_AT_KEY::"`changes={PARENT: {CHILD: x}}` against an existing block: FULL REPLACE, unmentioned children DROPPED"
  PRESERVE_SIBLINGS::"add or change one child, keep the rest: `{PARENT: {$op: MERGE, value: {CHILD: x}}}`"
  NESTED_DICTS::"bare dict with nested dict values: synthesised as canonical block form (logged `TN_INLINE_MAP_TO_BLOCK`); flat dict: inline map; old coercion that re-parsed to `E_NESTED_INLINE_MAP` gone"
  MERGE_GUARD::"nested dict inside a `$op: MERGE` payload: `E_NESTED_DICT_IN_MERGE_PAYLOAD`; scalar over an existing child block via MERGE: `E_OP_TARGET_MISMATCH`; DELETE first or send a bare-dict REPLACE at the parent"
  SCALAR_OVER_BLOCK::"bare scalar at a KEY holding a block replaces it with one flat assignment; never emits duplicate keys"
  NO_AUTO_CREATE::"contract: changes cannot add a key at a path that does not exist (`E_UNRESOLVABLE_PATH`); new keys need a `content=` rewrite or MERGE into an existing block parent"
  KNOWN_DEFECT::"#517, measured on octave-mcp 1.16.0: absent top-level key created; `§N.NEW` created; `META.NEW` created; `BLOCK.NEW` and `NOPE.CHILD` give `E_UNRESOLVABLE_PATH`; `§2.STEP_1` against a column-0 key creates a duplicate; until fixed, the contract line is intent, not behaviour"
  ADDRESSING::"address edits as section dot key (`§N.KEY`), dry-run first, read the diff to confirm where the edit landed"
  RULE_LISTS::"no per-item edit of a rule list: `§N.RULES[0]` gives `E_UNRESOLVABLE_PATH`, a list value is replaced whole; edit with APPEND, or replace the whole list after a dry-run diff"
  OPS::[
    "`{$op: DELETE}` removes target",
    "`{$op: APPEND, value: x}` pushes onto array; nested list or dict items re-emitted as parseable OCTAVE",
    "`{$op: PREPEND, value: x}` unshifts onto array",
    "`{$op: MERGE, value: {...}}` deep-merges into block, unmentioned children kept; inner `$op: DELETE` removes"
  ]
  ERRORS::"`E_UNRESOLVABLE_PATH`: path absent or section as target; `E_INVALID_OP_DESCRIPTOR`: malformed `$op`; `E_AMBIGUOUS_PATH` or `W_AMBIGUOUS_PATH`: anchor the path with `§N`"
  LITERAL_ZONES::"changes value replacing a fenced child keeps fence form and info tag under `format_style=preserve`; content-only edits round-trip byte-identical"
  RULE_OF_THUMB::"scalar-array appends and single-key edits: changes mode; block-nested, structural or new key: `content=` with `format_style=preserve` after a dry run"
§5::ANCHOR_KERNEL
  TARGET::"verified OCTAVE writes with the receipt read"
  NEVER::[
    "unkeyed lines",
    "a value on a section header",
    "`.oct.md` files written with Write or Edit",
    "VALIDATED claimed without a read receipt",
    "empty warnings trusted alone",
    "a bare dict replace where siblings must survive",
    "a call to `octave_fmt`",
    "remediation of frozen archives"
  ]
  MUST::[
    "every line keyed, multi-word values quoted",
    "contents indented under the section header",
    "edits addressed as section dot key",
    "repairs read, not only the validation status",
    "`octave_write` only; `schema=` when one applies; dry run before a destructive change",
    "status, errors, validation status, corrections, warnings and repairs triaged as discarding, advisory or benign",
    "changes mode: MERGE to keep siblings; a bare dict is a full replace; nested or new keys through `content=` with preserve",
    "advisory warnings remediated only on the record already being amended"
  ]
  GATE::"Did I read the receipt, and can I name every correction and every repair the tool applied?"
§6::REMEDIATION
  POLICY::"remediate only when already amending the record that surfaced the warning"
  ANNOTATION_MIGRATION:
    POLICY::"refactor long annotations only when already amending that record"
    TRIGGER::"record amendment where an annotation exceeds 32 characters or 4 underscore-tokens (`W_ANNOTATION_TOO_LONG` in `corrections[]`)"
    ACTION::["Short qualifier instead: at most 32 characters, at most 4 underscore-tokens.","Full reasoning in a sibling RATIONALE (or PRINCIPLE, GUIDANCE) field as a quoted note-form sentence."]
    EXAMPLE_BEFORE::"`I6<migration_on_moving_target_is_anti_pattern_for_zero_warnings>`"
    EXAMPLE_AFTER::"`I6<production_grade_quality>`, sibling `RATIONALE::\"migration against a moving target makes strict typing an anti-pattern\"`"
    FROZEN_ARCHIVES::"archives (DECISIONS-ARCHIVE, `docs/research/`, benchmark docs) stay frozen; zero return on batch-rewriting historical records"
    DETECTION::"non-blocking, advisory only"
  SNAKE_CASE_BLOB:
    POLICY::"rewrite snake-fragmented prose only when amending a record whose `corrections[]` surfaces `W_SNAKE_CASE_BLOB`"
    TRIGGER::"record amendment where `octave_validate` or `octave_write` returns `W_SNAKE_CASE_BLOB` for a value or list element in a reasoning-field position (octave-mcp 1.13.0 advisory)"
    DETECTOR::"`_detect_snake_case_blob` in `src/octave_mcp/mcp/write_detection.py`: token over 40 characters with at least 4 underscores (bulk), or at least 2 stopwords across underscore-delimited parts (semantic); ALL-CAPS tokens of at most 16 characters excluded"
    REASONING_FIELDS::"key set `_W_SNAKE_CASE_BLOB_REASONING_FIELDS` in the same file (DECISION, BECAUSE, RATIONALE, WHY, NOTE, EVIDENCE and others)"
    ACTION::["Rewrite the value as a quoted note-form sentence, per the note-form rule in the literacy §4b rules list; relations in words.","Atoms belong in structural positions (keys, enum values), not in reasoning-field values."]
    EXAMPLE_BEFORE::"`BECAUSE::migration_on_moving_target_is_anti_pattern_for_zero_warnings_during_strict_typing`"
    EXAMPLE_AFTER::"`BECAUSE::\"migration against a moving target makes strict typing an anti-pattern\"`"
    DETECTION::"non-blocking, advisory only"
  STRUCTURAL_ADVISORY:
    POLICY::"reshape only the block being amended; never batch-restructure a file for shape warnings alone"
    W_INLINE_ARRAY_ROOT::"`TOKEN::[KEY::v,...]`, map as inline root: block form per octave-literacy §1d (`TOKEN:` plus indented children)"
    W_FLAT_PREFIX_SCALAR::"`PARENT_CHILD::v` siblings: group under a `PARENT:` block per octave-literacy §1d, except the named families the skills mandate (`STEP_n` runbooks, `W_*` code tables); accepted advisories, leave them"
    W_CONSTRUCTOR_MISUSE::"known constructor name (REGEX, PATTERN, ENUM and others) as an assignment key: use the constructor form `NAME[args]` or a different key; agent GRAMMAR blocks with a REGEX key are a known accepted case"
    DETECTION::"all three STRUCTURAL_CHECK tier, `safe: true`; never data loss"
§7::PROVENANCE
  RULE::"each sentence points at the source a claim was read from; paths under `src/octave_mcp/`; all re-checked on octave-mcp 1.16.0; re-verify on a version bump"
  PROVENANCE::[
    "Tool registry, no `octave_fmt`: tool table, `mcp/server.py`.",
    "Content, changes or neither: module docstring, `mcp/write.py`.",
    "Format styles and the omitted default: header comment and `FORMAT_STYLE_VALUES`, `mcp/write_format.py`; explicit None deprecated: CHANGELOG 1.13.0.",
    "Warnings are the corrections with `safe: false`: result warnings drain, `mcp/write.py`.",
    "Corrections drained from the TIER_NORMALIZATION log, entry shape: `log_repair`, `core/grammar/tier_normalize.py`.",
    "No-op invariant: CHANGELOG 1.12.0 (#407, SR1-T4).",
    "Changes-mode hard break: CHANGELOG 1.15.0 STRATEGY_S3 (#443, #440, #488, #484).",
    "Fence preservation under changes: CHANGELOG 1.14.0 (#460).",
    "Blob detector: `_detect_snake_case_blob`, `mcp/write_detection.py`.",
    "Column-0 keys are file scope: observed on 1.15.0 and 1.16.0.",
    "Section not a MERGE target; deeper paths `E_UNRESOLVABLE_PATH`: observed on 1.15.0 and 1.16.0; new-key creation contradicts the contract (#517, §4 KNOWN_DEFECT).",
    "Validate receipts carry `repairs[]` and `repair_log[]`; `E_PATH` on `.txt`: observed on 1.15.0 and 1.16.0."
  ]
§8::USED_BY
  AGENTS::[octave-secretary,octave-specialist]
  KERNEL_ONLY::"any agent that calls `octave_write` directly: north-star-architect, system-steward, agent-expert, skills-expert"
  CONTEXT::"document authoring, context maintenance, governance artefact amendment"
===END===
