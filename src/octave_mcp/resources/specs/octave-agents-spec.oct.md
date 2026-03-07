===OCTAVE_AGENTS===
META:
  TYPE::LLM_PROFILE
  VERSION::"8.1.0"
  STATUS::ACTIVE
  PURPOSE::"Agent architecture schema with cognitive separation, operational clarity, and capability tiering."
  CONTRACT::HOLOGRAPHIC<JIT_GRAMMAR_COMPILATION>
// OCTAVE AGENTS v8.1: Adds §6::YAML_FRONTMATTER section.
// YAML frontmatter is OPTIONAL — required only for platform-deployed agents.
// Hub/system agents (.hestai-sys/library/agents/) consumed by anchor ceremony need only OCTAVE.
// This aligns agents and skills specs on the same YAML-optional contract.
//
// v8.0.0 CHANGES (ADR-0283):
// - §3::CAPABILITIES extended with CHASSIS (invariant skills) and PROFILES (context-specific)
// - Each profile declares: match (documentation-as-schema), skills, patterns, kernel_only
// - Flat SKILLS::[]/PATTERNS::[] remains valid (backward compatible, treated as single DEFAULT profile)
// - Version detection: presence of CHASSIS or PROFILES keys → structured mode
// - Overlap rules enforced by validator (not grammar): CHASSIS∩profile.skills → error, etc.
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
// Cognition-derived properties (NATURE block, MODE, PRIME_DIRECTIVE, THINK, THINK_NEVER)
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
  // The cognition file provides NATURE (FORCE/ESSENCE/ELEMENT), MODE, PRIME_DIRECTIVE, THINK, THINK_NEVER.
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
      // e.g. "ANALYSIS → PLAN → IMPLEMENTATION → VERIFICATION"
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
  //
  // v8 FORMAT (Chassis-Profile — ADR-0283):
  // CHASSIS: Invariant skills loaded every ceremony, regardless of profile.
  // PROFILES: Named blocks declaring context-specific skill sets.
  // Each profile has: match (documentation-as-schema), skills, patterns, kernel_only.
  // - match::[default] designates the fallback profile (sole condition only)
  // - match::[context::X] documents intended context (not runtime logic)
  // - skills: Full body loading when profile is active
  // - patterns: Full body loading when profile is active
  // - kernel_only: §5::ANCHOR_KERNEL extraction only when profile is active
  //
  // OVERLAP RULES (validator-enforced):
  // - CHASSIS skill in profile skills → error (redundant)
  // - CHASSIS skill in profile kernel_only → error (contradictory)
  // - default mixed with context:: in same match → error
  // - Duplicate profile names → error
  // - 4+ profiles → warning
  //
  // BACKWARD COMPATIBILITY:
  // Flat SKILLS::[]/PATTERNS::[] remains valid (v7 format).
  // Treated as equivalent to a single DEFAULT profile with all skills as full-body.
  // Version detection: presence of CHASSIS or PROFILES keys → structured mode.
  //
  // EXAMPLE (v8 structured):
  // CHASSIS::[ho-mode, prophetic-intelligence, gap-ownership]
  // PROFILES:
  // STANDARD:
  // match::[default]
  // skills::[ho-orchestrate, subagent-rules, constitutional-enforcement]
  // patterns::[mip-orchestration]
  // kernel_only::[system-orchestration, decision-record-authoring]
  // ECOSYSTEM:
  // match::[context::p15, context::ecosystem]
  // skills::[ho-ecosystem]
  // patterns::[dependency-graph-map]
  // kernel_only::[constitutional-enforcement]
  //
  // EXAMPLE (v7 flat — still valid):
  // SKILLS::["skill-a","skill-b"]
  // PATTERNS::["pattern-a","pattern-b"]
  CHASSIS::["Invariant skills loaded every ceremony"]
  PROFILES:
    PROFILE_NAME:
      match::["documentation-as-schema context conditions"]
      skills::["Full body skills for this profile"]
      patterns::["Full body patterns for this profile"]
      kernel_only::["Kernel-only skills for this profile"]
  // OR flat format (v7 backward compat):
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
§6::YAML_FRONTMATTER
  // v8.1: YAML frontmatter for platform discovery.
  // Same contract as skills spec v9.1 — agents and skills treat YAML identically.
  //
  // RATIONALE:
  // The anchor ceremony reads OCTAVE META (§0, §1, §2, §3, §4), not YAML.
  // YAML frontmatter serves external platform discovery (Claude Code, Desktop, Codex).
  // Hub/system agents have never used YAML and work correctly — this section
  // documents that reality and provides the schema for platform agents.
  STATUS::OPTIONAL
  REQUIRED_WHEN::"Agent is deployed to a platform discovery path"
  YAML_FIELDS::[
    name,
    description,
    allowed-tools,
    triggers,
    version
  ]
  DEPLOYMENT_CONTEXT:
    PLATFORM_AGENTS:
      LOCATION::[".claude/agents/", ".codex/agents/", "~/.claude/agents/"]
      YAML::REQUIRED
      RATIONALE::"Platforms parse YAML frontmatter for agent matching, description, and tool gating"
    HUB_AGENTS:
      LOCATION::[".hestai-sys/library/agents/"]
      YAML::NOT_REQUIRED
      RATIONALE::"Anchor ceremony reads OCTAVE META. No platform parser consumes hub agent YAML."
  // This mirrors skills spec v9.1 §7::PLATFORM_ADAPTATION::YAML_FRONTMATTER_RULES.
  // Both specs follow the same principle: YAML serves platform discovery, OCTAVE serves definition.
===END===
