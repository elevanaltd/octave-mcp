===OCTAVE_AGENTS===
META:
  TYPE::LLM_PROFILE
  VERSION::"6.2.0"
  STATUS::APPROVED
  PURPOSE::"Agent architecture schema using Dual-Lock Identity/Behavior separation."


// OCTAVE AGENTS v6: The "Dual-Lock" Schema
// Ratified by Architectural Debate (ho-octave-v6-redesign-001)
// Replaces complex jargon (Shank/Arm) with literal functional headers (Identity/Behavior)
// whilst STRICTLY enforcing the Odyssean Anchor Binding Protocol (Request->Lock->Commit).
//
// v6.2.0 CHANGES (Issue #248):
//   - ARCHETYPE uses NAME<qualifier> annotation syntax (see octave-core-spec §2c)
//   - §1 and §2 expanded to match actual agent structure
//   - MODE enum opened to extensible values

§0::META
  PURPOSE::"Contract definition and versioning"
  REQUIRED::[TYPE, VERSION]
  OPTIONAL::[PURPOSE, CONTRACT::GRAMMAR]

§1::IDENTITY
  // STAGE 1 LOCK (SHANK)
  // IMMUTABLE • CONSTITUTIONAL • WHO I AM
  // Must not change across sessions.
  CORE::[
    ROLE::AGENT_NAME,
    COGNITION::[LOGOS∨ETHOS∨PATHOS],
    ARCHETYPE::[
      NAME<qualifier>[list_of_annotated_archetypes]
      // Examples: ATHENA<strategic_wisdom>, ODYSSEUS<navigation>, HERMES<translation>
      // Uses angle-bracket annotation syntax (octave-core-spec §2c)
      // The archetype is the mythological identity; the qualifier selects the facet.
    ],
    MODEL_TIER::[PREMIUM∨STANDARD∨BASIC],
    ACTIVATION::[
      FORCE::[CONSTRAINT∨POSSIBILITY∨STRUCTURE],
      ESSENCE::[GUARDIAN∨EXPLORER∨ARCHITECT],
      ELEMENT::[WALL∨WIND∨DOOR]
    ],
    MISSION::purpose_expression,
    // Mission uses synthesis operator for multi-facet purposes:
    // e.g. SYSTEM_COHERENCE⊕GAP_OWNERSHIP⊕PROPHETIC_FAILURE_PREVENTION
    PRINCIPLES::[
      "List of constitutional constraints",
      // Can be bare strings or KEY::"description" pairs:
      // THOUGHTFUL_ACTION::"Philosophy actualized through deliberate progression"
      "Each principle binds the agent's behavior"
    ],
    AUTHORITY::[                          // OPTIONAL
      ULTIMATE::[scope_list],             // Highest authority domains
      BLOCKING::[scope_list],             // Can block progress in these domains
      ADVISORY::[scope_list],             // Advisory-only domains
      MANDATE::"Authority description",
      ACCOUNTABILITY::"Domain responsibility",
      NO_OVERRIDE::"Boundaries on authority"
      // Not all fields required. Use what applies.
    ]
  ]

§2::BEHAVIOR
  // STAGE 2 LOCK (ARM/CONDUCT)
  // CONTEXTUAL • OPERATIONAL • HOW I ENGAGE
  // Changes based on Phase, Risk, or Mode.
  CONDUCT::[
    MODE::mode_value,
    // Common modes: BUILD, DEBUG, DESIGN, CRISIS, CONVERGENT, VALIDATION
    // Extensible — use the mode that describes the agent's operational stance.
    TONE::"Voice and interaction style",
    PROTOCOL::[
      MUST_ALWAYS::[
        "Required behavioral rules",
        "Each rule is a binding constraint"
      ],
      MUST_NEVER::[
        "Prohibited behaviors",
        "Each rule is a hard boundary"
      ]
    ],
    OUTPUT::[
      FORMAT::"Response structure pattern",
      // e.g. "SYSTEM_STATE → COHERENCE_PATTERN → ORCHESTRATION_DIRECTIVE"
      REQUIREMENTS::[required_output_artifacts]
    ],
    VERIFICATION::[                       // OPTIONAL
      EVIDENCE::[required_evidence_types],
      GATES::NEVER[prohibited] ALWAYS[required]
    ],
    INTEGRATION::[                        // OPTIONAL
      HANDOFF::"Input/output contract with other agents",
      ESCALATION::"When and where to escalate"
    ]
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
    MUST_USE::[
      // REGEX patterns that must appear in output:
      // REGEX::"^\\[SYSTEM_STATE\\]"
      // Or plain patterns the agent must follow
      required_output_patterns
    ],
    MUST_NOT::[
      // PATTERN strings the agent must never produce:
      // PATTERN::"Here is a list of tasks"
      prohibited_output_patterns
    ]
  ]

§5::MAPPING_DEFINITION
  STATUS::DOCUMENTARY
  // For Steward/Anchor parser compliance
  SHANK_LOCK::[§1::IDENTITY]
  CONDUCT_LOCK::[§2::BEHAVIOR, §4::INTERACTION_RULES]
  FLUKE_LOAD::[§3::CAPABILITIES]

===END===
