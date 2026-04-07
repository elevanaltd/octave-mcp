===SKILL:REVIEW_PRIORITIZATION===
META:
  TYPE::SKILL
  VERSION::"2.0.0"
  STATUS::ACTIVE
  PURPOSE::"Severity-ordered finding triage for CRS reviews. Context-adaptive: PR reviews get display budget, standalone/audit reviews report all findings."

§1::CORE
AUTHORITY::ADVISORY[finding_ordering⊕batch_triage]
COMPLEMENTS::[review-discipline<confidence_levels>,constructive-feedback<presentation>]

§2::PRIORITY_TIERS
// Order: P0→P5. Within each tier: CERTAIN→HIGH→MODERATE.
P0_SECURITY::injection⊕auth_bypass⊕secrets⊕XSS⊕CSRF⊕privilege_escalation[FLOOR::MODERATE]
P1_CORRECTNESS::logic_errors⊕data_loss⊕race_conditions⊕null_deref⊕unchecked_errors[FLOOR::HIGH]
P2_RELIABILITY::missing_tests⊕error_handling_gaps⊕unvalidated_input⊕resource_leaks[FLOOR::HIGH]
P3_ARCHITECTURE::coupling⊕cohesion⊕abstraction_violations⊕API_design⊕scope_creep[FLOOR::HIGH]
P4_PERFORMANCE::algorithmic_complexity⊕N_plus_1⊕memory⊕caching[FLOOR::HIGH]
P5_STYLE::naming⊕formatting⊕documentation⊕conventions[FLOOR::CERTAIN]

§3::BUDGET
// Context-adaptive: detect review mode from task description
PR_REVIEW::[BUDGET::15,P0_P1::uncapped,P2::up_to_remaining,P3_P5::if_budget_remains,over_budget::append_"+N omitted"]
STANDALONE::[BUDGET::none,report_all_findings_at_or_above_confidence_floor]
AUDIT::[BUDGET::none,report_all_findings_at_or_above_confidence_floor]
DEFAULT::PR_REVIEW
// P5: consolidate into single note when count exceeds 5 (any mode)

§4::OUTPUT
SUMMARY::include_tier_distribution["P0:N P1:N P2:N P3:N P4:N P5:N"]
STRUCTURE::P0_P1_first→P2_P4_next→P5_last
// PR metadata fields (priority_distribution, findings_omitted) defined in review-handoff pattern

§5::ANCHOR_KERNEL
TARGET::severity_ordered_finding_triage
NEVER::[report_P5_before_P0,omit_P0_findings,consolidate_P0_or_P1,report_speculative_P5]
MUST::[classify_P0_through_P5,sort_by_confidence_within_tier,apply_context_budget,emit_tier_distribution]
GATE::"Are findings severity-ordered, confidence-sorted, and budget-appropriate for the review context?"

===END===
