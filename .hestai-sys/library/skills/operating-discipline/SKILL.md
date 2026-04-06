===SKILL:OPERATING_DISCIPLINE===
META:
  TYPE::SKILL
  VERSION::"1.0"
  PURPOSE::"Enforcement of system-wide operating discipline gates and boundaries"

§1::OPERATING_ESSENTIALS
PHASE_GATES::"D1(NORTH-STAR)→D2(DESIGN)→D3(BLUEPRINT)→B0(VALIDATION)→B1(BUILD-PLAN+STOP)→B2(TDD)→B3(INTEGRATION)→B4(HANDOFF)"
QUALITY_GATES::"TDD(failing_test_first)→TMG_CHECKPOINT(T2+:load_review-red_skill)→CodeReview(every_change)→Tests(must_pass)→Security(scan_required)"
RACI_CONSULTATIONS::"critical-engineer(tactical)→principal-engineer(strategic)→security-specialist(security)→requirements-steward(alignment)→test-methodology-guardian(discipline)"

§2::ENFORCEMENT_PROTOCOL
BLOCKING_AUTHORITY::[
  "Production risk exposure above organizational threshold",
  "System standard violations requiring intervention",
  "System coherence threats endangering overall stability",
  "Gap ownership abandonment creating accountability voids",
  "Quality gate bypassing attempts",
  "RACI consultation avoidance",
  "Phase progression with missing essential artifacts or failed quality gates"
]

§3::ESCALATION
ESCALATION_CRITERIA::[
  SYSTEM_STANDARD_BOUNDARY::"New principle conflicts, force reinterpretation, authority scope expansion, fundamental structure change → HUMAN",
  DUAL_KEY_GOVERNANCE::"Major scope changes, GO/NO-GO decisions, production deployment → critical-engineer(tactical) + principal-engineer(strategic) + requirements-steward (+ HUMAN)"
]

§5::ANCHOR_KERNEL
TARGET::enforce_operating_discipline_gates_and_boundaries
PHASE_GATES::[D1→D2→D3→B0→B1→B2→B3→B4]
QUALITY_GATES::[TDD[failing_test_first]→TMG[T2+_load_review-red_skill]→CodeReview[every_change]→Tests[must_pass]→Security[scan_required]]
RACI::[CE[tactical], PE[strategic], SecSpec[security], ReqSteward[alignment], TMG[discipline]]
BLOCKING::[production_risk, system_standard_misalignment, coherence_threats, gap_abandonment, gate_bypass, RACI_avoidance, phase_progression_without_artifacts]
ESCALATE_TO_HUMAN::[new_principle_conflicts, authority_scope_expansion, fundamental_structure_change]
DUAL_KEY::[[major_scope_changes, GO_NO_GO, production_deploy]→CE+PE+ReqSteward+HUMAN]
GATE::"Phase gate requirements met, quality gates passed, RACI consulted?"
===END===
