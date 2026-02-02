===OCTAVE_COMPRESSION_PRIMER===
META:
  TYPE::PRIMER
  VERSION::"6.1.0"
  TOKENS::~260
  TIER::ULTRA

§1::ESSENCE
PURPOSE::"Compress prose→OCTAVE"
OCTAVE::"Semantic DSL for LLMs"
WORKFLOW::READ→EXTRACT[why,evidence]→COMPRESS→VALIDATE

§2::MAP
VERBOSE→DENSE
REDUNDANCY→[array]
HIERARCHY→parent::[children]
TIERS::LOSSLESS∨CONSERVATIVE∨AGGRESSIVE∨ULTRA
PRESERVE::[causality,numbers,IDs,§_names]
NEVER::[JSON,YAML,>3_nesting]

§3::SYNTAX
::→assign
→::flow
⇌::tradeoff
[,]::list

§4::ONE_SHOT
IN::"System processes data because users need speed"
OUT::SYSTEM::data→process[b/c::user_speed]

§5::VALIDATE
MUST::[valid_OCTAVE,preserve_§_names_verbatim,why_preserved,"60%_reduction"]
===END===
