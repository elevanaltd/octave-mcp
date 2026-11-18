===OCTAVE_LITERACY_PRIMER===
META:
  TYPE::PRIMER
  VERSION::"7.0.1"
  TOKENS::"446"
  COMPRESSION_TIER::ULTRA
  LOSS_PROFILE::"keeps syntax rules; drops rationale"
§1::ESSENCE
PURPOSE::"Read and write OCTAVE"
OCTAVE::"Olympian Common Text And Vocabulary Engine — Semantic DSL for LLMs"
STRUCTURE::"KEY::value, [list], indent 2 spaces"
LANGUAGE::"Write in PITH: note form in plain words; identifiers copied exactly, in backticks; hedges verbatim; relations in words; none or not known for an empty slot; code in fences"
READING::"A distinct syntax marks structured data: parse it, do not paraphrase it; read a term by its plain meaning; if a term is unclear, translate it literally and note the ambiguity"
§2::MAP
EXAMPLES::
```
KEY::value        assignment, no spaces around the double colon
[a,b,c]           list
KEY:              block opener; children indented 2 spaces
  child::value
KEY::             not a block: empty value, children below hoist out
§1::NAME          section header, never carries a value
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
```
AUTHORING::"these operators appear in documents you read; write each relation in words"
§4::ONE_SHOT
IN::"The auth service validates tokens. Failed logins alert the on-call. Rate limit: not known."
OUT:
  AUTH::"validates tokens"
  ALERT::"failed logins alert the on-call"
  RISK::"rate limit not known"
§5::VALIDATE
MUST::[
  "valid OCTAVE",
  "section names kept verbatim",
  "no spaces around the double colon",
  "closing line ===END==="
]
===END===
