===DECISION_LOG===
META:
  TYPE::SCHEMA
  VERSION::"1.0"
  STATUS::ACTIVE
  PURPOSE::"Schema for DECISIONS_OCTAVE_v20260417 decision-log documents. Codifies the self-declared per-entry schema (TOKEN/TIER/STATUS/DECISION/BECAUSE plus tier-conditional fields) into a validator-recognised contract. Ratified per HO_DECISION_GOVERNANCE_GRAVITY_TIERED_20260428 extending HestAI-MCP ADR-0060."
POLICY:
  VERSION::"1.0"
  UNKNOWN_FIELDS::WARN
  TARGETS::["§INDEXER","§SELF"]
FIELDS:
  TOKEN::["HO-MONOREPO-GOVERNANCE-20251107"∧REQ→§INDEXER]
  TIER::["ARCHITECTURAL"∧REQ∧ENUM[ARCHITECTURAL,CONVENTION,MICRO]→§SELF]
  STATUS::["BINDING"∧REQ→§SELF]
  DECISION::["The decision essence"∧REQ→§SELF]
  BECAUSE::[["rationale"]∧REQ→§SELF]
  ISSUE_REF::["#751"∧OPT→§SELF]
  ENFORCEMENT_REF::["src/path/to/enforcer.py"∧OPT→§SELF]
  CANONICAL::["DECISIONS-ARCHIVE.oct.md#TOKEN"∧OPT→§SELF]
  SUPERSEDED_BY::["NEW-TOKEN-DATE"∧OPT→§SELF]
  SUPERSEDES::["OLD-TOKEN-DATE"∧OPT→§SELF]
  EXTENDS::["OTHER-TOKEN-DATE"∧OPT→§SELF]
  AMENDS::["OTHER-TOKEN-DATE"∧OPT→§SELF]
  EVIDENCE::[["citation"]∧OPT→§SELF]
  AMENDMENTS::[["dated_amendment"]∧OPT→§SELF]
  IMPLEMENTATION_HANDOFF::["agent_or_owner"∧OPT→§SELF]
  CONSTRAINTS::[["constraint"]∧OPT→§SELF]
  AUTHORITY::[["NorthStar_I12"]∧OPT→§SELF]
TIER_DEFINITIONS::[
  ARCHITECTURAL::issue_required_plus_ISSUE_REF_field,
  CONVENTION::no_issue_inline_only,
  MICRO::no_doc_encode_in_tooling_with_ENFORCEMENT_REF_to_linter_or_ci_or_schema
]
SCHEMA_REQUIRED_BY_TIER::[
  ARCHITECTURAL_REQUIRES::[ISSUE_REF,EXTENDS_or_AMENDS_or_SUPERSEDES_when_applicable],
  CONVENTION_REQUIRES::[],
  MICRO_REQUIRES::[ENFORCEMENT_REF_pointing_to_commit_or_file_implementing_mechanism]
]
SCHEMA_REQUIRED_EXCEPTIONS::[
  ARCHIVED_FULL_ENTRY_stubs_exempt_from_BECAUSE_and_DECISION,
  STUB_entries_carry_FULL_BODY_AT_pointer_instead_of_BECAUSE_and_DECISION_substance,
  STATUS_SUPERSEDED_BY_entries_carry_only_TOKEN_plus_STATUS_plus_SUPERSEDED_BY_plus_CANONICAL
]
WRITE_DISCIPLINE::[
  RULE_1::new_top_level_entries_via_octave_write_changes_mode_only_never_content_mode_to_avoid_format_drift,
  RULE_2::amendments_appended_to_AMENDMENTS_array_dated_entries_never_inline_rewrite_of_existing_BECAUSE_or_CANONICAL_or_DECISION_fields,
  RULE_3::pre_merge_octave_validate_in_CI_catches_format_drift_before_merge,
  RULE_4::META_UPDATED_conflict_resolution_take_latest_date_no_human_review_needed,
  RULE_5::amendment_collision_on_same_token_requires_human_reconciliation_semantic_conflict_not_tooling_failure,
  RULE_6::supersedure_workflow_writes_new_active_entry_collapses_old_to_stub_pointer_moves_old_body_to_archive_all_in_same_PR
]
USAGE_NOTES::[
  "TOKEN: Stable identifier with date suffix (e.g., HO-MONOREPO-GOVERNANCE-20251107). Indexer key.",
  "TIER: Decision-gravity tier. ARCHITECTURAL requires ISSUE_REF; MICRO requires ENFORCEMENT_REF; CONVENTION is inline-only.",
  "STATUS: Lifecycle state. Common values: BINDING, ACTIVE, SUPERSEDED_BY_<TOKEN>, DEPRECATED, ARCHIVED. Enforced by document convention, not by enum at schema level.",
  "DECISION: One-line essence of the decision. Required except for stub-pointer entries (see SCHEMA_REQUIRED_EXCEPTIONS).",
  "BECAUSE: Rationale list. Required except for stub-pointer entries.",
  "ISSUE_REF: GitHub issue reference. REQUIRED when TIER::ARCHITECTURAL; enforcement of tier-conditional requirement is via document convention plus CI octave_validate, not via schema-level conditional constraints.",
  "ENFORCEMENT_REF: Path to commit or file implementing the mechanism. REQUIRED when TIER::MICRO.",
  "SUPERSEDED_BY / SUPERSEDES / EXTENDS / AMENDS: Decision-relationship references. Targets are TOKEN values of other entries.",
  "CANONICAL: When a decision has been moved to the archive, CANONICAL points to the archive section retaining the full body.",
  "WRITE_DISCIPLINE: Advisory rules surfacing the operational contract — pre-merge octave_validate catches structural drift; semantic collisions still require human reconciliation."
]
===END===
