===OCTAVE_LITERACY_PRIMER===
META:
  TYPE::PRIMER
  VERSION::"6.2.0"
  TOKENS::"~240"
  TIER::ULTRA
§1::ESSENCE
PURPOSE::"Read and write OCTAVE"
OCTAVE::"Semantic DSL for LLMs"
STRUCTURE::"KEY::value, [list], indent_2"
§1b::READING
MYTHOLOGY::"Semantic zip files — compressed meaning, not system names"
CONTEXT::"Adjacent text determines which aspect of a myth applies"
FORMAT_SIGNAL::"Distinct syntax (::, →, ⇌) signals structured data — parse, not paraphrase"
FALLBACK::"If a term is unclear, translate literally and note the ambiguity"
§2::MAP
EXAMPLES::
```
KEY::value        → assignment
[a,b,c]           → list
KEY:              → block (indent 2 spaces)
  child::value
```
§3::SYNTAX
OPERATORS::
```
::    assign (no spaces around)
→     flow / sequence
⊕     synthesis / combine
⇌     tension / opposition
```
§4::ONE_SHOT
IN::"flow from A to B"
OUT::"A→B"
§5::VALIDATE
MUST::[
  valid_OCTAVE,
  "preserve_§_names_verbatim",
  "no_spaces_around_::",
  "===END==="
]
===END===
