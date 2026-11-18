===SKILL===
META:
  TYPE::SCHEMA
  VERSION::"1.1"
  STATUS::ACTIVE
  PURPOSE::"Schema for HestAI skill definition files at .hestai-sys/library/skills/*/SKILL.md. Validates the canonical SKILL envelope: Zone 2 YAML frontmatter (name/description/allowed-tools, enforced only when a frontmatter block is present — see POLICY.FRONTMATTER_PRESENCE), META block (TYPE/VERSION/STATUS), and Zone 1 section body coverage (section 1 presence required; ANCHOR_KERNEL TARGET/NEVER/MUST/GATE quartet enforced when present). WAVE_3 of pre-v1.13.0 Schema Sweep (GH-428) extends I5 SCHEMA_SOVEREIGNTY from Zone 2 (#244) into Zone 1 section coverage. v1.1 (GH#520) realigns Zone 2 with octave-skills-spec v9.1, which makes YAML OPTIONAL at the hub location this schema governs."
  IMPLEMENTS_SPEC::"octave-skills-spec@9.2.0"
POLICY:
  VERSION::"1.0"
  UNKNOWN_FIELDS::WARN
  TARGETS::["§SELF"]
  REQUIRED_SECTION_IDS::["1"]
  SECTION_CONDITIONAL_REQUIRED:
    ANCHOR_KERNEL::[
      TARGET,
      NEVER,
      MUST,
      GATE
    ]
  FRONTMATTER_PRESENCE::OPTIONAL
FRONTMATTER:
  name:
    REQUIRED::true
    TYPE::STRING
  description:
    REQUIRED::true
    TYPE::STRING
  allowed-tools:
    REQUIRED::true
    TYPE::LIST
  version:
    REQUIRED::false
    TYPE::STRING
  triggers:
    REQUIRED::false
    TYPE::LIST
FIELDS:
  TYPE::["SKILL"∧REQ∧ENUM[SKILL]→§SELF]
  VERSION::["1.0"∧REQ→§SELF]
  STATUS::["ACTIVE"∧OPT∧ENUM[ACTIVE,DRAFT,DEPRECATED]→§SELF]
USAGE_NOTES::[
  "TYPE: Skill files declare META.TYPE::SKILL at the envelope level.",
  "VERSION: Authoring-format version of the skill content (free-form string).",
  "STATUS: Lifecycle state. Optional — defaults to ACTIVE if absent.",
  "IMPLEMENTS_SPEC: The octave-skills-spec version whose rules this schema encodes. Bump it whenever the spec moves, so spec/schema drift is visible at a glance rather than silent (GH#520).",
  "Zone 2 (frontmatter): POLICY.FRONTMATTER_PRESENCE::OPTIONAL. octave-skills-spec v9.1 §7 PLATFORM_ADAPTATION makes YAML REQUIRED at platform locations (.claude/skills/, .codex/skills/) and OPTIONAL at the hub location (.hestai-sys/library/skills/) this schema governs, because the anchor ceremony reads OCTAVE META and §5::ANCHOR_KERNEL rather than YAML. A hub skill with no frontmatter block therefore validates clean. When frontmatter IS present, name/description/allowed-tools serve Claude Code skill loading and version/triggers remain optional metadata.",
  "Zone 2 enforcement is presence-conditional, not abandoned: a document that DOES author a frontmatter block must still supply name, description and allowed-tools, and each present field is still type-checked. Absent (permitted) and incomplete (rejected) are distinct facts — PROD::I2 DETERMINISTIC_ABSENCE.",
  "Zone 2 residual: the validator receives no filesystem path (octave_validate accepts bare content), so it cannot tell a platform skill from a hub skill. 'Platform deployment requires YAML' is enforceable only at the platform-deployment boundary, which is outside this processor's scope. This schema enforces everything a path-blind validator can justify, and no more (PROD::I5).",
  "Zone 1 (§-section body): §1 (the canonical first numbered section, naming convention varies — §1::CORE, §1::PHILOSOPHY_DELEGATION, §1::TARGET, etc.) is REQUIRED. The validator emits W_MISSING_REQUIRED_SECTION when §1 is absent (GH-428).",
  "ANCHOR_KERNEL quartet: When §5::ANCHOR_KERNEL is present, it must carry TARGET, NEVER, MUST, and GATE assignments. Missing quartet members surface W_INCOMPLETE_SECTION_FIELDS naming the missing fields. SKILL files without an ANCHOR_KERNEL section are unaffected (the check is section-conditional, not unconditional)."
]
===END===
