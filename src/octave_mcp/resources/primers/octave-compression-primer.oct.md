===OCTAVE_COMPRESSION_PRIMER===
META:
  TYPE::PRIMER
  VERSION::"7.0.0"
  TOKENS::"463"
  COMPRESSION_TIER::ULTRA
  LOSS_PROFILE::"keeps tier rules and transforms; drops rationale"
§1::ESSENCE
PURPOSE::"Compress prose into OCTAVE by tier"
OCTAVE::"Olympian Common Text And Vocabulary Engine — Semantic DSL for LLMs"
METHOD::[
  "read the source",
  "choose the tier",
  "extract why and evidence",
  compress,
  validate
]
LANGUAGE::"PITH: note form in plain words; identifiers, numbers and hedges copied exactly; relations in words"
§2::MAP
TIER_SELECTION::
```
audit or critical         LOSSLESS      drops nothing
research or design        CONSERVATIVE  drops redundancy
quick reference           AGGRESSIVE    drops nuance
extreme scarcity          ULTRA         drops narrative
```
TRANSFORMS::
```
keep      causality, numbers, identifiers, section names
drop      redundancy, filler, connectors
sentence  KEY::"note-form sentence"
repeats   one list
reasons   cause and effect stated in words
trade-off both sides stated in words
group     parent block with children
```
§3::SYNTAX
READING_LEGEND::
```
::    assign
→     flow
⊕     synthesis
⇌     tension
∧     conjunction
∨     disjunction
[,]   list
```
AUTHORING::"these operators appear in documents you read; write each relation in words"
§4::ONE_SHOT
IN::"Authenticate before the dashboard; failed logins alert; security versus usability."
OUT:
  AUTH::"login, validate, dashboard"
  FAIL::alert
  TRADEOFF::"security versus usability"
§5::VALIDATE
MUST::[
  "valid OCTAVE",
  "section names kept verbatim",
  "numbers, identifiers and causality kept",
  "META keeps COMPRESSION_TIER and LOSS_PROFILE",
  "no markdown, JSON or YAML",
  "nesting at most 3"
]
===END===
