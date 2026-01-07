===SKILL:CONSTITUTIONAL_ENFORCEMENT===
META:
  TYPE::SKILL
  VERSION::"1.0"
  PURPOSE::"Enforcement of system-wide constitutional gates and boundaries"

§1::CONSTITUTIONAL_ESSENTIALS
PHASE_GATES::"D1(NORTH-STAR)→D2(DESIGN)→D3(BLUEPRINT)→B0(VALIDATION)→B1(BUILD-PLAN+STOP)→B2(TDD)→B3(INTEGRATION)→B4(HANDOFF)"
QUALITY_GATES::"TDD(failing_test_first)→CodeReview(every_change)→Tests(must_pass)→Security(scan_required)"
RACI_CONSULTATIONS::"critical-engineer(tactical)→principal-engineer(strategic)→security-specialist(security)→requirements-steward(alignment)→test-methodology-guardian(discipline)"

§2::ENFORCEMENT_PROTOCOL
BLOCKING_AUTHORITY::[
  "Production risk exposure above organizational threshold",
  "Constitutional principle violations requiring intervention",
  "System coherence threats endangering overall stability",
  "Gap ownership abandonment creating accountability voids",
  "Quality gate bypassing attempts",
  "RACI consultation avoidance",
  "Phase progression with missing essential artifacts or failed quality gates"
]

§3::ESCALATION
ESCALATION_CRITERIA::[
  CONSTITUTIONAL_BOUNDARY::"New principle conflicts, force reinterpretation, authority scope expansion, fundamental structure change → HUMAN",
  DUAL_KEY_GOVERNANCE::"Major scope changes, GO/NO-GO decisions, production deployment → critical-engineer(tactical) + principal-engineer(strategic) + requirements-steward (+ HUMAN)"
]

===END===
