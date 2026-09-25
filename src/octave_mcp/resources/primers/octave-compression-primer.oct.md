===OCTAVE_COMPRESSION_PRIMER===
META:
  TYPE::PRIMER
  VERSION::"6.6.0"
  TOKENS::"496"
  COMPRESSION_TIER::ULTRA
  LOSS_PROFILE::"[preserve:tier_rules∧transforms,drop:rationale]"
§1::ESSENCE
PURPOSE::"Compress prose→OCTAVE with tier judgment"
OCTAVE::"Olympian Common Text And Vocabulary Engine — Semantic DSL for LLMs"
METHOD::[READ→TIER→EXTRACT→COMPRESS→VALIDATE]
TELEGRAPHIC_PHRASE::"quoted, operator-joined value — e.g. 'security⇌usability'"
§2::MAP
TIER_SELECTION::
```
audit∨critical→LOSSLESS[drop::none]
research∨design→CONSERVATIVE[drop::redundancy]
quick_ref→AGGRESSIVE[drop::nuance]
extreme_scarcity→ULTRA[drop::narrative]
identity∨binding→ULTRA_MYTHIC[drop::narrative,keep::soul∧constraints]
```
TRANSFORMS::
```
content→PRESERVE[causality[X→Y_because_Z]∧numbers∧IDs∧§_names]
noise→DROP[stopwords∧redundancy∧prose_connectors]
sentences→KEY::value
repetition→[array]
because∨therefore→A→B[reason]
tradeoffs→GAIN⇌LOSS
groupings→parent::[children]
```
§3::SYNTAX
OPERATORS::
```
::    assign
→     flow
⊕     synthesis
⇌     tension
∧     conjunction
∨     disjunction
```
§4::ONE_SHOT
IN::"Auth before dashboard; failures alert; keep usability."
OUT:
  AUTH::[login→validate→dashboard]
  FAIL::alert
  INTENT::"security ⇌ usability"
§5::VALIDATE
MUST::[
  valid_OCTAVE,
  "preserve_§_names_verbatim",
  preserve_numbers∧IDs∧causality,
  tier_first,
  "no_markdown∨JSON∨YAML∧nesting<=3"
]
===END===
