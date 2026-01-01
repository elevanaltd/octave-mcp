===ANNOTATION_TIERING_RUBRIC===
// Systematic approach to OCTAVE annotation density

META:
  NAME::"OCTAVE Annotation Tiering Rubric"
  VERSION::"5.1.0"
  TYPE::GUIDE
  PURPOSE::"Guide annotation depth based on code criticality"
  PRINCIPLE::"Annotate until marginal comprehension delta < 5%"

TIERS:
  HOTSPOT::"Full OCTAVE annotation"
  IMPORTANT::"Moderate OCTAVE annotation"
  PERIPHERAL::"Minimal or no OCTAVE"

HOTSPOT_CRITERIA:
  SECURITY_SURFACE::"Authentication, authorization, encryption"
  PERFORMANCE_CRITICAL::"O(N²) or worse algorithms"
  BUSINESS_LOGIC::"Core domain rules and calculations"
  SIDE_EFFECTS::"External API calls, database mutations"
  COMPLEX_FLOWS::"Multi-step state machines"

  ANNOTATION_DEPTH:
    PATTERNS::REQUIRED
    FORCES::REQUIRED
    TENSIONS::REQUIRED
    METRICS::REQUIRED
    RELATIONSHIPS::REQUIRED

IMPORTANT_CRITERIA:
  INTEGRATION_POINTS::"Service boundaries, adapters"
  ERROR_HANDLING::"Recovery strategies, fallbacks"
  CONFIGURATION::"System behavior controls"
  SHARED_UTILITIES::"Cross-domain helpers"

  ANNOTATION_DEPTH:
    PATTERNS::OPTIONAL
    FORCES::OPTIONAL
    TENSIONS::REQUIRED_IF_PRESENT
    METRICS::BASIC
    RELATIONSHIPS::BASIC

PERIPHERAL_CRITERIA:
  PURE_FUNCTIONS::"No side effects, deterministic"
  DATA_STRUCTURES::"Simple DTOs, value objects"
  GENERATED_CODE::"Auto-created by tools"
  OBVIOUS_HELPERS::"toString, simple getters"

  ANNOTATION_DEPTH:
    HEADLINE_ONLY::"Single line purpose if any"
    NO_PATTERNS::true
    NO_FORCES::true

DECISION_FLOW:
  STEP_1::"Does it have security implications?"
  STEP_2::"Is the runtime complexity > O(N)?"
  STEP_3::"Does it encode business rules?"
  STEP_4::"Does it cause side effects?"
  STEP_5::"Is the flow multi-step?"

  IF_ANY_YES::TIER::HOTSPOT
  ELSE_CHECK:
    INTEGRATION::"Service boundary?"
    ERROR_HANDLING::"Complex recovery?"
    CONFIGURATION::"Behavior control?"

  IF_ANY_YES::TIER::IMPORTANT
  ELSE::TIER::PERIPHERAL

EXAMPLES:
  HOTSPOT:
    FILE::"auth/jwt_validator.py"
    REASON::"Security surface + external API"
    ANNOTATION::"""
    PATTERN::GUARDIAN_GATEWAY
    FORCES::[SECURITY, PERFORMANCE]
    TENSION::THOROUGH_VALIDATION⇌LATENCY
    """

  IMPORTANT:
    FILE::"services/user_adapter.py"
    REASON::"Integration point"
    ANNOTATION::"""
    PURPOSE::Transform external user data
    TENSION::FLEXIBILITY⇌TYPE_SAFETY
    """

  PERIPHERAL:
    FILE::"models/user_dto.py"
    REASON::"Simple data structure"
    ANNOTATION::"// User data transfer object"

MEASUREMENT:
  COVERAGE_TARGET:
    HOTSPOT::"100% annotated"
    IMPORTANT::"60-80% annotated"
    PERIPHERAL::"0-20% annotated"

  COMPREHENSION_TEST::"Can new developer understand purpose and risks?"
  TOKEN_EFFICIENCY::"Annotation tokens / code tokens < 0.3"

===END===
