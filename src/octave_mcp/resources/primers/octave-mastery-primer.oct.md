===OCTAVE_MASTERY_PRIMER===
META:
  TYPE::PRIMER
  VERSION::"8.0.0"
  TOKENS::"477"
  COMPRESSION_TIER::ULTRA
  LOSS_PROFILE::"keeps forms and usage law; drops rationale and vocabulary tables"
§1::ESSENCE
PURPOSE::"Write the advanced OCTAVE forms a parser or validator reads"
OCTAVE::"Olympian Common Text And Vocabulary Engine — Semantic DSL for LLMs"
METHOD::[
  "one facet per identity",
  "constraints only in schema-definition files",
  "maps of maps as blocks"
]
LANGUAGE::"PITH: plain words; relations in words; mythology terms are read by their one domain, never written as instructions"
§2::MAP
EXAMPLES:
  ```
  NAME<facet>     identity with one facet, 32 characters at most: REVIEWER<strict>
  NAME[args]      constructor, never an identity: ENUM[ACTIVE,DRAFT]
  KEY:            nested map: block with indented children
    child::value
  KEY::[K::[...]] never: a map of maps as an inline list
  ```
§3::SYNTAX
READING_LEGEND:
  ```
  ::    assign, no spaces around
  →     flow
  ⊕     synthesis
  ⇌     tension
  ∧     conjunction, inside brackets
  ∨     alternative
  <>    facet on an identity
  []    arguments on an operation, or a constraint container
  §     target reference
  ```
SCHEMA_EXAMPLE:
  ```
  STATUS::["ACTIVE"∧ENUM[ACTIVE,DRAFT]]
  ```
AUTHORING::"glyphs and constraints appear only in schema-definition files; write every other relation in words"
§4::ONE_SHOT
IN::"A schema field status must be ACTIVE or DRAFT; a reviewer validates input."
OUT:
  REVIEWER::"validates input"
  STATUS::"ACTIVE or DRAFT"
§5::VALIDATE
MUST::[
  "valid OCTAVE",
  "section names kept verbatim",
  "facet in angle brackets",
  "constraint inside brackets, schema-definition files only",
  "every other relation in words"
]
===END===
