===CRS_REVIEW===
META:
  TYPE::SCHEMA
  VERSION::"1.1.0"
  STATUS::ACTIVE
  PURPOSE::"Schema for CRS_REVIEW code-review documents emitted by the HestAI review gate. WAVE_3 of pre-v1.13.0 Schema Sweep (GH-426) closes the §3::FINDINGS body-coverage gap left by v1.0.0 — only §1::VERDICT / §2::DISTRIBUTION / §4::SUMMARY had FIELDS coverage; §3::FINDINGS was silent. Reuses the POLICY+walker mechanism landed in PR #444 (REQUIRED_SECTION_IDS, SECTION_CONDITIONAL_REQUIRED) and the envelope-name canonicalisation precedent from PR #437 (envelope name matches META.TYPE)."
---
POLICY:
  VERSION::"1.0"
  UNKNOWN_FIELDS::WARN
  TARGETS::[
    "§VERDICT",
    "§DISTRIBUTION",
    "§FINDINGS",
    "§SUMMARY"
  ]
  REQUIRED_SECTION_IDS::["3"]
  SECTION_CONDITIONAL_REQUIRED:
    FINDINGS::["SEVERITY","FILE","ISSUE"]
FIELDS:
  // §1::VERDICT section fields
  ROLE::["CRS"∧REQ]
  PROVIDER::["claude-opus-4-6"∧OPT]
  VERDICT::["APPROVED"∧REQ∧ENUM[APPROVED,BLOCKED,CONDITIONAL]]
  SHA::["abc1234"∧REQ]
  TIER::["T2"∧REQ∧ENUM[T0,T1,T2,T3,T4]]
  // §2::DISTRIBUTION section fields
  TOTAL::[0∧REQ]
  BLOCKING::[0∧REQ]
  TRIAGED::[true∧REQ]
  OMITTED::[0∧OPT]
  P0::[0∧OPT]
  P1::[0∧OPT]
  P2::[0∧OPT]
  P3::[0∧OPT]
  P4::[0∧OPT]
  P5::[0∧OPT]
  // §3::FINDINGS section fields (GH-426)
  // The REQ triple (SEVERITY/FILE/ISSUE) is enforced via
  // POLICY.SECTION_CONDITIONAL_REQUIRED (per-finding-when-present semantic),
  // NOT via FIELDS-level REQ. FIELDS-level REQ would trigger
  // _check_required_field_coverage (mcp/validate.py) document-wide and would
  // falsely reject the legitimate APPROVED-review-with-zero-findings case
  // where §3 is present-but-empty. The SKILL schema follows the same
  // pattern: its ANCHOR_KERNEL quartet (TARGET/NEVER/MUST/GATE) is not
  // declared at FIELDS level either — only in POLICY.SECTION_CONDITIONAL_REQUIRED.
  //
  // SEVERITY ENUM[P0..P5] is documentary at the validator level until #435
  // lands (octave_validate ENUM enforcement PARTIAL); the constraint is
  // parsed and exposed via the GBNF compiler.
  SEVERITY::["P0"∧OPT∧ENUM[P0,P1,P2,P3,P4,P5]]
  FILE::["src/path/to/file"∧OPT]
  ISSUE::["Issue description"∧OPT]
  CONFIDENCE::["HIGH"∧OPT∧ENUM[CERTAIN,HIGH,MODERATE,LOW]]
  LINES::["10-20"∧OPT]
  TITLE::["Short title"∧OPT]
  EVIDENCE::["Evidence excerpt"∧OPT]
  IMPACT::["Impact description"∧OPT]
  // FIX / REQUIRED_FIX: validator-only alias per HO final-final AC (GH-426).
  // Both names accepted at OPT level; REQUIRED_FIX is the recommended canonical name.
  // No emit-time rewriting — see USAGE_NOTES.
  FIX::["Recommended fix"∧OPT]
  REQUIRED_FIX::["Recommended fix"∧OPT]
  // §4::SUMMARY section fields
  ASSESSMENT::["Summary assessment"∧REQ]
  TOP_RISKS::[["Risk description"]∧REQ∧TYPE[LIST]]
USAGE_NOTES::[
  "Vocabulary: §3::FINDINGS uses uppercase keys per WAVE_3 alignment with sibling schemas (DEBATE_TRANSCRIPT, AGENT_DEFINITION, DECISION_LOG, SKILL).",
  "REQ triple: every finding entry should carry SEVERITY, FILE, ISSUE. Missing members surface W_INCOMPLETE_SECTION_FIELDS naming the gap (PR #444 walker).",
  "FIX vs REQUIRED_FIX: both names are accepted as OPT fields. REQUIRED_FIX is the recommended canonical name. The alias is validator-only — octave_write does NOT rewrite FIX to REQUIRED_FIX at emit time (PROD::I1 bijective_on_semantic_space; HO final-final AC GH-426).",
  "REQUIRED_SECTION_IDS::[3]: documents omitting §3::FINDINGS entirely surface W_MISSING_REQUIRED_SECTION (PROD::I5 SCHEMA_SOVEREIGNTY; closes the WAVE_3 silent-gap defect).",
  "SEVERITY ENUM[P0..P5] is documentary until GH#435 (octave_validate ENUM enforcement PARTIAL) lands — the constraint is parsed and exposed via the GBNF compiler but is not yet a validator-level rejection axis.",
  "SCHEMA_REQUIRED_EXCEPTIONS (per GH#439) not yet consumed by the validator surface; declared empty here intentionally — the per-finding contract has no stub-pointer mode analogous to DECISION_LOG archived entries."
]
===END===
