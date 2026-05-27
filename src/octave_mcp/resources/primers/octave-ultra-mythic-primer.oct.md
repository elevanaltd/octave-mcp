===ULTRA_MYTHIC_PRIMER===
META:
  TYPE::PRIMER
  VERSION::"6.3.0"
  TIER::ULTRA
  TOKENS::"~280"
§1::ESSENCE
PURPOSE::"Convert prose→OCTAVE"
OCTAVE::"Olympian Common Text And Vocabulary Engine — Semantic DSL for LLMs"
METHOD::"prose→ATOMS[mythology]"
§2::MAP
  // Template guides structure (replace ROLE/ARCHETYPE/FORBIDDEN/ACTION)
EXAMPLES::
```
PATTERN::ROLE[ARCHETYPE]::NEVER[FORBIDDEN]→ACTION
ARCHETYPE::pick_relevant_myth[ZEUS,ARES,ATLAS,HERMES]
```
§3::SYNTAX
OPERATORS::
```
::    maps_to  definition
→     maps_to  flow
⊕     maps_to  synthesis
⇌     maps_to  tension
∧     maps_to  conjunction / all-required
∨     maps_to  disjunction / alternative
NEVER[]  maps_to  constraint
```
§4::ONE_SHOT
IN::"Architect designs, never implements"
OUT::"ARCHITECT[ATLAS]::NEVER[IMPL]"
§5::VALIDATE
MUST::[
  valid_OCTAVE,
  "preserve_§_names_verbatim",
  replace_ROLE_placeholders,
  do_not_use_ARCHITECT
]
===END===
