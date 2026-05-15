===AGENT_DEFINITION===
META:
  TYPE::SCHEMA
  VERSION::"1.0"
  STATUS::ACTIVE
  PURPOSE::"Schema for HestAI agent definition files at .hestai-sys/library/agents/*.oct.md. Validates the canonical multi-section envelope (META, §1::IDENTITY, §2::OPERATIONAL_BEHAVIOR, §3::CAPABILITIES, §4::INTERACTION_RULES) shared by 33+ on-disk agents. WAVE_2 of pre-v1.13.0 Schema Sweep (GH-424)."
POLICY:
  VERSION::"1.0"
  UNKNOWN_FIELDS::WARN
  TARGETS::[
    "§1::IDENTITY",
    "§2::OPERATIONAL_BEHAVIOR",
    "§3::CAPABILITIES",
    "§4::INTERACTION_RULES",
    "§SELF"
  ]
FIELDS:
  ROLE::["AGENT_ROLE_IDENTIFIER"∧REQ→§SELF]
  COGNITION::["LOGOS"∧REQ∧ENUM[LOGOS,ETHOS,PATHOS]→§SELF]
  ARCHETYPE::[["Archetype list"]∧OPT∧TYPE[LIST]→§SELF]
  MODEL_TIER::["PREMIUM"∧OPT∧ENUM[PREMIUM,STANDARD]→§SELF]
  MISSION::["MISSION_STATEMENT"∧REQ→§SELF]
  PRINCIPLES::[["Principle list"]∧OPT∧TYPE[LIST]→§SELF]
  AUTHORITY_ULTIMATE::[["Authority items"]∧OPT∧TYPE[LIST]→§SELF]
  AUTHORITY_BLOCKING::[["Authority items"]∧OPT∧TYPE[LIST]→§SELF]
  AUTHORITY_ADVISORY::[["Authority items"]∧OPT∧TYPE[LIST]→§SELF]
  AUTHORITY_NO_OVERRIDE::["Boundary statement"∧OPT→§SELF]
  AUTHORITY_MANDATE::["Accountability statement"∧REQ→§SELF]
  AUTHORITY_ACCOUNTABILITY::["Accountability domain"∧OPT→§SELF]
  CONDUCT::["Operational conduct block"∧OPT→§SELF]
  SKILLS::[["Skill references"]∧OPT∧TYPE[LIST]→§SELF]
  PATTERNS::[["Pattern references"]∧OPT∧TYPE[LIST]→§SELF]
  CHASSIS::[["Chassis skill references"]∧OPT∧TYPE[LIST]→§SELF]
  PROFILES::[["Profile entries"]∧OPT∧TYPE[LIST]→§SELF]
  GRAMMAR::["Grammar block"∧OPT→§SELF]
USAGE_NOTES::[
  "TYPE: Agent definition documents declare META.TYPE::AGENT_DEFINITION at the envelope level. The schema name AGENT_DEFINITION matches this TYPE so the validator activates the deep section schema path.",
  "ROLE: Uppercase identifier matching the agent's role; convention is one role per file (e.g., IMPLEMENTATION_LEAD, HOLISTIC_ORCHESTRATOR).",
  "COGNITION: Reasoning style — LOGOS (convergent/Door), ETHOS (validation/Wall), PATHOS (divergent/Wind). Links to library/cognitions/<name>.oct.md for kernel decompression.",
  "ARCHETYPE: List of archetype<qualifier> entries (e.g., HEPHAESTUS<implementation_craft>). Archetypes operate as analytical lenses, not personas.",
  "MODEL_TIER: PREMIUM for deep reasoning agents; STANDARD for mechanical execution agents. Optional — defaults are role-dependent.",
  "MISSION: Single-line mission compound joined by ⊕ (e.g., TECHNICAL_LEADERSHIP⊕CODE_QUALITY). Captures the agent's domain mandate.",
  "PRINCIPLES: Ordered list of operating principles. Authoring convention is 3–6 entries.",
  "AUTHORITY_ULTIMATE: Domains over which the agent has final say (e.g., Code_implementation). Composes with AUTHORITY_BLOCKING and AUTHORITY_ADVISORY.",
  "AUTHORITY_BLOCKING: Conditions under which the agent MUST halt downstream work (e.g., Untested_code, CI_failures).",
  "AUTHORITY_ADVISORY: Domains where the agent may advise but not block.",
  "AUTHORITY_NO_OVERRIDE: Boundary statement — what the agent cannot unilaterally override even within its mandate.",
  "AUTHORITY_MANDATE: Single-line accountability statement. REQUIRED — every agent must declare what it is accountable for.",
  "AUTHORITY_ACCOUNTABILITY: Optional named accountability domain (e.g., 12 critical domains for critical-engineer).",
  "CONDUCT: §2::OPERATIONAL_BEHAVIOR block holding TONE/PROTOCOL/OUTPUT/VERIFICATION/INTEGRATION sub-blocks. Free-form internal structure across agents.",
  "SKILLS / PATTERNS: §3::CAPABILITIES references — must point to real on-disk skills/patterns (no phantom references).",
  "CHASSIS / PROFILES: Alternative §3 shape used by chassis-profile agents (agent-expert, octave-secretary). Either {SKILLS,PATTERNS} or {CHASSIS,PROFILES} is acceptable.",
  "GRAMMAR: §4::INTERACTION_RULES block with MUST_USE and MUST_NOT regex lists enforcing output discipline (e.g., '^\\[ANALYSIS\\]')."
]
===END===
