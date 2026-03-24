===COGNITION_DEFINITION===
META:
  TYPE::SCHEMA
  VERSION::"1.2"
  STATUS::ACTIVE
  PURPOSE::"Schema for cognition master files (logos, ethos, pathos). Validates cognitive kernel structure with Wind/Wall/Door type system."
POLICY:
  VERSION::"1.2"
  UNKNOWN_FIELDS::WARN
  TARGETS::["§SELF"]
FIELDS:
  MODE::["CONVERGENT"∧REQ∧ENUM[CONVERGENT,VALIDATION,DIVERGENT]→§SELF]
  PRIME_DIRECTIVE::["Core cognitive instruction"∧REQ→§SELF]
  CRAFT::["Methodological stance"∧OPT→§SELF]
  THINK::[["Cognitive rules"]∧REQ∧TYPE[LIST]→§SELF]
  THINK_NEVER::[["Cognitive anti-patterns"]∧REQ∧TYPE[LIST]→§SELF]
  FORCE::["STRUCTURE"∧REQ∧ENUM[STRUCTURE,CONSTRAINT,POSSIBILITY]→§SELF]
  ESSENCE::["ARCHITECT"∧REQ→§SELF]
  ELEMENT::["DOOR"∧REQ∧ENUM[DOOR,WALL,WIND]→§SELF]
  EPISTEMOLOGY::["Epistemic tradition"∧OPT→§SELF]
USAGE_NOTES::[
  "FORCE: Cognitive force type - STRUCTURE (Door), CONSTRAINT (Wall), POSSIBILITY (Wind)",
  "ESSENCE: Archetype descriptor string - e.g. ARCHITECT, GUARDIAN, EXPLORER",
  "ELEMENT: Debate role - DOOR (integrator), WALL (validator), WIND (explorer)",
  "MODE: Reasoning approach - CONVERGENT (Door), VALIDATION (Wall), DIVERGENT (Wind)",
  "PRIME_DIRECTIVE: Single sentence capturing cognitive essence",
  "CRAFT: OPTIONAL. Single sentence describing methodological stance — bridges PRIME_DIRECTIVE (what to reveal) and THINK (how to reason)",
  "EPISTEMOLOGY: OPTIONAL. Named epistemic tradition (e.g. Aristotelian Logos) to activate pre-trained weight clusters as decoder key for reasoning style",
  "THINK: Positive cognitive patterns - how to approach problems",
  "THINK_NEVER: Hard cognitive boundaries - reasoning traps to avoid"
]
===END===
