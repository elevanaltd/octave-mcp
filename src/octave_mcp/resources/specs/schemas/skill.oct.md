===SKILL===
META:
  TYPE::SCHEMA
  VERSION::"1.0"
  STATUS::ACTIVE
  PURPOSE::"Schema for HestAI skill definition files at .hestai-sys/library/skills/*/SKILL.md. Validates the canonical SKILL envelope: Zone 2 YAML frontmatter (name/description/allowed-tools), META block (TYPE/VERSION/STATUS), and Zone 1 §-section body coverage (§1 presence required; §5::ANCHOR_KERNEL TARGET/NEVER/MUST/GATE quartet enforced when present). WAVE_3 of pre-v1.13.0 Schema Sweep (GH-428) extends I5 SCHEMA_SOVEREIGNTY from Zone 2 (#244) into Zone 1 §-section coverage."
POLICY:
  VERSION::"1.0"
  UNKNOWN_FIELDS::WARN
  TARGETS::["§SELF"]
  REQUIRED_SECTION_IDS::["1"]
  SECTION_CONDITIONAL_REQUIRED:
    ANCHOR_KERNEL::["TARGET","NEVER","MUST","GATE"]
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
  "Zone 2 (frontmatter): name/description/allowed-tools required for Claude Code skill loading. version/triggers optional metadata.",
  "Zone 1 (§-section body): §1 (the canonical first numbered section, naming convention varies — §1::CORE, §1::PHILOSOPHY_DELEGATION, §1::TARGET, etc.) is REQUIRED. The validator emits W_MISSING_REQUIRED_SECTION when §1 is absent (GH-428).",
  "ANCHOR_KERNEL quartet: When §5::ANCHOR_KERNEL is present, it must carry TARGET, NEVER, MUST, and GATE assignments. Missing quartet members surface W_INCOMPLETE_SECTION_FIELDS naming the missing fields. SKILL files without an ANCHOR_KERNEL section are unaffected (the check is section-conditional, not unconditional)."
]
===END===
