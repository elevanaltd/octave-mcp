===OCTAVE_COMPRESSION_PRIMER===
META:
  TYPE::PRIMER
  VERSION::"6.1.0"
  TOKENS::~55
  TIER::ULTRA

§1::ESSENCE
PURPOSE::"Compress prose→OCTAVE"
OCTAVE::"Semantic DSL for LLMs"
WORKFLOW::READ→EXTRACT[why,numbers]→COMPRESS[tier]→VALIDATE

§2::MAP
VERBOSE→DENSE
REDUNDANCY→[array]
HIERARCHY→parent::[children]
TIERS::LOSSLESS∨CONSERVATIVE∨AGGRESSIVE∨ULTRA
PRESERVE::[causality,IDs,§_names]
NEVER::[JSON,YAML,>3_levels]

§3::SYNTAX
::→assign
→::flow
⇌::tradeoff
[,]::list

§4::ONE_SHOT
IN::"The system processes input data because users need quick results"
OUT::SYSTEM::input→process→output[b/c::user_speed_need]

§5::VALIDATE
MUST::[valid_OCTAVE,preserve_§_names_verbatim,why_intact,"60%_reduction"]
===END===
