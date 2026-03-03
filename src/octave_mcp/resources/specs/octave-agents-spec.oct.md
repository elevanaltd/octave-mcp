===OCTAVE_AGENTS===
META:
  TYPE::LLM_PROFILE
  VERSION::"7.0.0"
  STATUS::APPROVED
  PURPOSE::"Agent architecture schema with cognitive separation and operational clarity."
  CONTRACT::HOLOGRAPHIC<JIT_GRAMMAR_COMPILATION>
// OCTAVE AGENTS v7: The "Cognitive Separation" Schema
// Ratified by Issue #314 review and HO assessment
// Builds on v6 Dual-Lock by separating cognitive properties into external cognition files,
// flattening §1 structure, and renaming §2 to OPERATIONAL_BEHAVIOR.
//
// v7.0.0 CHANGES (Issue #314):
// - ACTIVATION (FORCE/ESSENCE/ELEMENT) removed from §1 — now in cognition master files
// - MODE removed from §2 — now in cognition master files
// - §2 renamed from BEHAVIOR to OPERATIONAL_BEHAVIOR
// - §1 CORE:: wrapper removed — properties are direct children of §1
// - AUTHORITY flattened to AUTHORITY_BLOCKING, AUTHORITY_MANDATE, etc.
// - COGNITION field in §1 serves as link key to cognition master file
// - Cognition masters: library/cognitions/logos.oct.md, ethos.oct.md, pathos.oct.md
//
// MIGRATION NOTE:
// Cognition-derived properties (FORCE, ESSENCE, ELEMENT, MODE, THINK, THINK_NEVER)
// live in standalone cognition files loaded before the anchor ceremony.
// Agent files reference their cognition type via COGNITION field in §1.
// No §0::COGNITIVE_FOUNDATION section in agent files — cognition is a
// pre-ceremony load, not an in-file section. §0::META below defines
// the spec's own contract metadata (unchanged from v6).
§0::META
  PURPOSE::"Contract definition and versioning"
  REQUIRED::[TYPE,VERSION]
  OPTIONAL::[
    PURPOSE,
    CONTRACT::GRAMMAR
  ]
§1::IDENTITY
  // STAGE 1 LOCK (SHANK)
  // IMMUTABLE • CONSTITUTIONAL • WHO I AM
  // Must not change across sessions.
  ROLE::AGENT_NAME
  COGNITION::[LOGOS∨ETHOS∨PATHOS]
  // Link key to cognition master file at library/cognitions/TYPE.oct.md
  // The cognition file provides NATURE, MODE, PRIME_DIRECTIVE, THINK, THINK_NEVER.
  // Agent files do NOT duplicate these properties.
  ARCHETYPE::[
    NAME<qualifier>
  ]
  MODEL_TIER::[PREMIUM∨STANDARD∨BASIC]
  MISSION::purpose_expression
  // Mission uses synthesis operator for multi-facet purposes:
  // e.g. SYSTEM_COHERENCE⊕GAP_OWNERSHIP⊕PROPHETIC_FAILURE_PREVENTION
  PRINCIPLES::["List of constitutional constraints","Each principle binds the agent's behavior"]
  AUTHORITY_BLOCKING::[scope_list] // OPTIONAL — Can block progress in these domains
  AUTHORITY_ULTIMATE::[scope_list] // OPTIONAL — Highest authority domains
  AUTHORITY_ADVISORY::[scope_list] // OPTIONAL — Advisory-only domains
  AUTHORITY_MANDATE::"Authority description" // OPTIONAL
  AUTHORITY_ACCOUNTABILITY::"Domain responsibility" // OPTIONAL
  AUTHORITY_NO_OVERRIDE::"Boundaries on authority" // OPTIONAL
  // Not all AUTHORITY fields required. Use what applies.
§2::OPERATIONAL_BEHAVIOR
  // STAGE 2 LOCK (ARM/CONDUCT)
  // CONTEXTUAL • OPERATIONAL • WHAT I DO
  // Operational rules for domain execution. Cognitive rules (HOW to think)
  // live in the cognition master file, not here.
  CONDUCT:
    TONE::"Voice and interaction style"
    PROTOCOL:
      MUST_ALWAYS::["Required operational rules","Each rule is a binding constraint on domain actions"]
      MUST_NEVER::["Prohibited operational behaviors","Each rule is a hard boundary on domain actions"]
    OUTPUT:
      FORMAT::"Response structure pattern"
      // e.g. "SYSTEM_STATE → COHERENCE_PATTERN → ORCHESTRATION_DIRECTIVE"
      REQUIREMENTS::[required_output_artifacts]
    VERIFICATION:
      EVIDENCE::[required_evidence_types]
      GATES::[
        NEVER<prohibited>,
        ALWAYS<required>
      ]
    INTEGRATION:
      HANDOFF::"Input/output contract with other agents"
      ESCALATION::"When and where to escalate"
§3::CAPABILITIES
  // DYNAMIC LOADING (FLUKE)
  // WHAT I CAN USE
  SKILLS::["List of loaded skill files","Domain expertise modules"]
  PATTERNS::["List of behavioral patterns","Reusable constraint sets"]
§4::INTERACTION_RULES
  // HOLOGRAPHIC CONTRACT
  // HOW I SPEAK (Grammar)
  GRAMMAR:
    MUST_USE::[required_output_patterns]
    MUST_NOT::[prohibited_output_patterns]
§5::MAPPING_DEFINITION
  STATUS::DOCUMENTARY
  // For Steward/Anchor parser compliance
  COGNITION_LOAD::"library/cognitions/COGNITION_TYPE.oct.md"
  SHANK_LOCK::"§1::IDENTITY"
  CONDUCT_LOCK::["§2::OPERATIONAL_BEHAVIOR","§4::INTERACTION_RULES"]
  FLUKE_LOAD::"§3::CAPABILITIES"
===END===
