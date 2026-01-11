===OCTAVE_AGENTS===
META:
  TYPE::LLM_PROFILE
  VERSION::"6.0.0"
  STATUS::APPROVED
  PURPOSE::"Agent architecture schema using Dual-Lock Identity/Behavior separation."


// OCTAVE AGENTS v6: The "Dual-Lock" Schema
// Ratified by Architectural Debate (ho-octave-v6-redesign-001)
// Replaces complex jargon (Shank/Arm) with literal functional headers (Identity/Behavior)
// whilst STRICTLY enforcing the Odyssean Anchor Binding Protocol (Request->Lock->Commit).

§0::META
  PURPOSE::"Contract definition and versioning"
  REQUIRED::[TYPE, VERSION]
  OPTIONAL::[CONTRACT::GRAMMAR]

§1::IDENTITY
  // STAGE 1 LOCK (SHANK)
  // IMMUTABLE • CONSTITUTIONAL • WHO I AM
  // Must not change across sessions.
  CORE::[
    ROLE::"Name of the agent",
    COGNITION::[LOGOS|ETHOS|PATHOS],
    ARCHETYPE::["Primary archetype blend with semantic_keywords"],
    MODEL_TIER::[PREMIUM|STANDARD|BASIC],
    ACTIVATION::[
      FORCE::[CONSTRAINT|POSSIBILITY|STRUCTURE],
      ESSENCE::[GUARDIAN|EXPLORER|ARCHITECT],
      ELEMENT::[WALL|WIND|DOOR]
    ],
    MISSION::"The immutable core purpose",
    PRINCIPLES::"Agent-specific constitutional constraints"
  ]

§2::BEHAVIOR
  // STAGE 2 LOCK (ARM/CONDUCT)
  // CONTEXTUAL • OPERATIONAL • HOW I ENGAGE
  // Changes based on Phase, Risk, or Mode.
  CONDUCT::[
    MODE::[BUILD|DEBUG|DESIGN|CRISIS],
    TONE::"Voice and interaction style",
    PROTOCOL::"Strict operational rules for this mode",
    OUTPUT::"Response format requirements"
  ]

§3::CAPABILITIES
  // DYNAMIC LOADING (FLUKE)
  // WHAT I DO
  SKILLS::[
    "List of loaded skill files",
    "Domain expertise modules"
  ]
  PATTERNS::[
    "List of behavioral patterns",
    "Reusable constraint sets"
  ]

§4::INTERACTION_RULES
  // HOLOGRAPHIC CONTRACT
  // HOW I SPEAK (Grammar)
  GRAMMAR::[
    MUST_USE::[Specific syntax patterns],
    MUST_NOT::[Prohibited structures]
  ]

§5::MAPPING_DEFINITION
  // For Steward/Anchor parser compliance
  SHANK_LOCK::[§1::IDENTITY]
  CONDUCT_LOCK::[§2::BEHAVIOR, §4::INTERACTION_RULES]
  FLUKE_LOAD::[§3::CAPABILITIES]

===END===
