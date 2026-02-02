===OCTAVE_COMPRESSION_PRIMER===
META:
  TYPE::PRIMER
  VERSION::"6.2.0"
  TOKENS::~300
  TIER::ULTRA

§1::ESSENCE
PURPOSE::"Compress prose→OCTAVE with tier judgment"
OCTAVE::"Semantic DSL for LLMs"
METHOD::READ→EXTRACT[why,evidence]→COMPRESS→VALIDATE

§2::DECIDE
TIER_SELECT::[
  LOSSLESS::audit∨critical[drop::none],
  CONSERVATIVE::research∨design[drop::redundancy],
  AGGRESSIVE::quick_ref[drop::nuance],
  ULTRA::extreme_scarcity[drop::narrative]
]
PRESERVE::causality[X→Y_because_Z]∧numbers∧IDs∧§_names
DROP::stopwords∧redundancy∧prose_connectors

§3::MAP
sentences→KEY::value
repetition→[array]
because/therefore→A→B[reason]
tradeoffs→GAIN⇌LOSS
groupings→parent::[children]

§4::SYNTAX
::→assign[no_spaces]
→::flow
⊕::synthesis
⇌::tension
[,]::list

§5::ONE_SHOT
IN::"Users authenticate before dashboard. Failed logins trigger alerts for security while maintaining usability."
OUT::AUTH::login→validate→dashboard,FAIL::alert,INTENT::security⇌usability

§6::NEVER
AVOID::[markdown,JSON,YAML,nesting>3,losing_numbers]
===END===
