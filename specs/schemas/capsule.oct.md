===CAPSULE===
META:
  TYPE::SCHEMA
  VERSION::"1.0"
  STATUS::ACTIVE
  PURPOSE::"Schema for vocabulary capsule documents. Defines the structure for shareable term collections that can be imported via hydration."

POLICY:
  VERSION::"1.0"
  UNKNOWN_FIELDS::WARN
  TARGETS::[§INDEXER,§SELF]

FIELDS:
  TYPE::["CAPSULE"∧REQ∧CONST→§SELF]
  NAME::["vocabulary_name"∧REQ→§INDEXER]
  VERSION::["1.0.0"∧REQ∧SEMVER→§SELF]
  PURPOSE::["Purpose description"∧REQ→§SELF]
  STATUS::["ACTIVE"∧REQ∧ENUM[DRAFT,ACTIVE,DEPRECATED]→§SELF]

SECTION_SCHEMA:
  PATTERN::"§N::TERM_GROUP"
  CHILD_FORMAT::TERM_DEFINITION
  TERM_DEFINITION::["TERM_NAME::\"Definition string\""∧REQ→§SELF]

VALIDATION_RULES::[
  "META.TYPE must equal 'CAPSULE'",
  "META.NAME must be a valid identifier",
  "META.VERSION must follow semantic versioning",
  "Each section should contain term definitions as KEY::\"value\" pairs",
  "Term names should be UPPERCASE_SNAKE_CASE"
]

HYDRATION_BEHAVIOR::[
  "When imported via §CONTEXT::IMPORT[@namespace/name]:",
  "  - All term definitions are extracted from sections",
  "  - Terms are injected into §CONTEXT::SNAPSHOT block",
  "  - §SNAPSHOT.MANIFEST records provenance",
  "  - §SNAPSHOT.PRUNED lists unused terms"
]

===END===
