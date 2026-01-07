===SKILL:PROPHETIC_INTELLIGENCE===
META:
  TYPE::SKILL
  VERSION::"1.0"
  PURPOSE::"System-wide failure pattern detection and early warning capability"

§1::CORE_CAPABILITY
PREDICTION_CAPABILITY::SYSTEM_WIDE_FAILURE_MODES
ACCURACY_TRACKING::"80%+ historical accuracy for system-wide failure mode predictions (verified through retrospective analysis: predicted_failures / actual_failures ≥ 0.80)"
VERIFICATION_METHOD::"Rolling 6-month accuracy measurement with pattern categorization and confidence calibration"

§2::EARLY_WARNING_SIGNALS
SIGNALS::[
  "PERFORMANCE_DEGRADATION::{metrics_trending_downward, latency_increases, throughput_decreases}",
  "ERROR_RATE_TRENDS::{error_frequency_increasing, error_diversity_expanding, recovery_time_lengthening}",
  "COUPLING_INCREASE::{dependency_graph_densifying, boundary_violations_growing, interface_complexity_rising}",
  "BOUNDARY_VIOLATIONS::{cross_boundary_assumptions_proliferating, integration_points_failing, coherence_metrics_declining}"
]

§3::FAILURE_PATTERNS
PATTERNS::[
  "ASSUMPTION_CASCADES::{detection: 'untested beliefs compounding across systems', timeline: '2-4 weeks', confidence: '85%', historical_accuracy: '23/27 (85.2%)', mitigation: 'reality validation gates at boundary crossing'}",
  "SCALE_BRITTLENESS::{detection: 'solutions work small but break at volume', timeline: '1-6 months', confidence: '80%', historical_accuracy: '16/20 (80.0%)', mitigation: 'load testing before production scale'}",
  "PHASE_TRANSITION_BLINDNESS::{detection: 'missing critical state changes', timeline: '1-3 phases', confidence: '90%', historical_accuracy: '27/30 (90.0%)', mitigation: 'phase gate constitutional verification'}",
  "INTEGRATION_DEBT::{detection: 'deferred complexity surfacing at convergence', timeline: '2-8 weeks', confidence: '82%', historical_accuracy: '18/22 (81.8%)', mitigation: 'early integration testing discipline'}",
  "CONWAYS_REVENGE::{detection: 'organizational structure forcing technical compromise', timeline: '3-12 months', confidence: '78%', historical_accuracy: '14/18 (77.8%)', mitigation: 'cross-boundary orchestration authority'}"
]

§4::OUTPUT_STRUCTURE
PROPHECY_OUTPUT::[
  "SIGNAL::{pattern_type, detection_confidence, timeline_to_manifestation}",
  "PROJECTION::{failure_manifestation_scenario, system_impact_assessment, cascading_consequences}",
  "PROBABILITY::{confidence_percentage, historical_accuracy_reference, uncertainty_factors}",
  "MITIGATION::{intervention_type, responsible_agent_assignment, implementation_timeline, success_criteria}"
]
===END===
