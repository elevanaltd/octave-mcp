===SURVEY_ANALYSIS===
META:
  TYPE::"RESEARCH_ARTIFACT"
VERSION::SEMANTIC["6.0", ANCHOR::"octave://spec/research"]
  TIER::CONSERVATIVE[target:85-90%_compression,preserve:explanatory_depth,drop:redundancy]

  CONTRACT::HOLOGRAPHIC[
    SELF_VALIDATION::JIT_COMPILE
    GENERATIVE_CONSTRAINT::GRAMMAR_COMPILE[
      SECTION::OVERVIEW REQUIRED::true
      SECTION::SURVEY_FINDINGS REQUIRED::true
      SECTION::SYNTHESIS_AND_TRADEOFFS REQUIRED::true
      SECTION::FAILURE_MODES REQUIRED::true
      SECTION::MINIMAL_EXECUTION REQUIRED::true
    ]
    LIVING_EVOLUTION::FORWARD_COMPATIBLE[
      DEPRECATION_WARNING::true
    ]
  ]

§1::OVERVIEW
  CONCEPT::"Holographic Document Language"
  GOAL::Unified_Spec[TEACH(LLM_by_example) + VALIDATE(rules) + EXECUTE(routing)]
  EXAMPLE::ID::["sess_123" ∧ REQ → §INDEXER]
  IDEAL::"Single-source executable spec that is machine-executable and LLM-legible."

§2::SURVEY_FINDINGS
  // Comparison of existing systems against holographic goals

  JSON_SCHEMA:
    SOLVES::"Formal grammar for JSON structure validation"
    CONTEXT::"Primarily used to validate JSON documents, ensuring required properties/types."
    SCORE::[TEACH:Low, VALIDATE:High, EXTRACT:Low]
    ANALYSIS:
      TEACH::"Support basic annotations (title, description), but not primarily for LLM consumption."
      VALIDATE::"Excels at validation (types, ranges, formats). Blueprint of validity."
      EXTRACT::"No built-in extraction/routing. Needs custom extensions."
    LIMITATION::"Separate from examples; no native execution/routing binding."

  OPENAPI:
    SOLVES::"REST API contracts (endpoints + data models)"
    CONTEXT::"Standard for describing RESTful API contracts. Leverages JSON Schema."
    SCORE::[TEACH:Medium, VALIDATE:High, EXTRACT:Medium(codegen)]
    ANALYSIS:
      TEACH::"Indirectly supports teaching via human-friendly descriptions/examples."
      VALIDATE::"Can validate actual API requests/responses at runtime."
      EXTRACT::"Codegen creates handlers/stubs (form of extraction), but logic is external."
    LIMITATION::"Describes API surface, not application logic execution."

  PROTOBUF_AVRO:
    SOLVES::"Binary serialization for efficient storage/RPC"
    CONTEXT::"Used in distributed systems for efficient storage/RPC. Generates code."
    SCORE::[TEACH:Low, VALIDATE:High, EXTRACT:Low(compile-time)]
    ANALYSIS:
      TEACH::"Not LLM-legible. No inline example data (just field names/types)."
      VALIDATE::"Strong schema-driven validation and serialization."
      EXTRACT::"Extraction via generated code objects (compile-time binding)."
    LIMITATION::"Not LLM-legible; strict separation of schema and runtime logic."

  CUE_LANGUAGE:
    SOLVES::"Unified configuration constraints and data"
    CONTEXT::"Unifies schemas, config, and constraints. Types/values/constraints are same."
    SCORE::[TEACH:Medium, VALIDATE:High, EXTRACT:Medium]
    ANALYSIS:
      TEACH::"Can embed example/default in schema. LLM could learn from spec file."
      VALIDATE::"Extensive validation (constraints, regex, ranges). Unifies schema/data."
      EXTRACT::"Computes results/verifies. Scripts can transform data. No native side-effects."
    LIMITATION::"Complexity curve; no built-in side-effect/routing mechanism."

  JSON_LD_SHACL:
    SOLVES::"Semantic web constraints and linked data context"
    CONTEXT::"JSON-LD maps JSON to ontology. SHACL defines shapes/constraints on RDF graphs."
    SCORE::[TEACH:Low, VALIDATE:High, EXTRACT:Low]
    ANALYSIS:
      TEACH::"Teaches semantics (meaning of terms) via context, but not format examples."
      VALIDATE::"Strong validation of graph data shapes and semantic consistency."
      EXTRACT::"Semantic interoperability, not imperative routing. Manual routing logic."
    LIMITATION::"Heavyweight; targeted at knowledge graphs, not LLM prompting."

  ZOD_PYDANTIC:
    SOLVES::"Code-centric runtime validation (TS/Python)"
    CONTEXT::"Define schema in code (fluent API or Python classes). Runtime parsing/validation."
    SCORE::[TEACH:Low, VALIDATE:High, EXTRACT:Medium]
    ANALYSIS:
      TEACH::"Implicit teaching (developer-centric). Examples live in tests/docs."
      VALIDATE::"Strong runtime validation, type checking, and coercion."
      EXTRACT::"Returns typed object for code use. Developer handles routing manually."
    LIMITATION::"Developer-centric; schema embedded in code, not standalone artifact."

  GRAMMARS:
    SOLVES::"Formal syntax definition (PEG, Attribute Grammars)"
    CONTEXT::"Formal syntax definition. Attribute grammars add semantic rules/computations."
    SCORE::[TEACH:Low, VALIDATE:High, EXTRACT:High(potential)]
    ANALYSIS:
      TEACH::"Grammar defines language, but hard for LLM to read as 'example'."
      VALIDATE::"Strict structural validation (parsing)."
      EXTRACT::"Attribute grammars can compute/generate code (execute semantics)."
    LIMITATION::"High complexity; difficult for non-experts and LLMs to read raw."

  LLM_TOOLS:
    FUNCTION_CALLING:
      TYPE::"OpenAI API Feature"
      SCORE::[TEACH:Medium, VALIDATE:High, EXTRACT:High]
      ANALYSIS::"Schema teaches expected JSON. System validates structure. Direct routing to function."
      NOTE::"Best current analog but limited to JSON/functions."

    GUIDANCE_OUTLINES:
      TYPE::"Prompt/Generation Libraries"
      SCORE::[TEACH:High, VALIDATE:High, EXTRACT:High]
      ANALYSIS::"Prompt template = spec. Token-level validation during generation. Captures variables."
      NOTE::"Executable prompt programs; powerful but complex to maintain as docs."

    GUARDRAILS:
      TYPE::"Validation Framework"
      SCORE::[TEACH:High, VALIDATE:High, EXTRACT:Medium]
      ANALYSIS::"RAIL spec teaches via prompt instructions. Validates/corrects post-generation."
      NOTE::"Closest meta-spec; validates/corrects post-generation."

§3::SYNTHESIS_AND_TRADEOFFS
  TRADEOFF_COVERAGE:
    OBSERVATION::"Most systems optimize for exactly two of the three axes (Teach, Validate, Extract)."
    SCHEMA_PLUS_EXECUTION::[Attribute_Grammars, Function_Calling, BDD]
      Tradeoff::"Strong on logic/validation, but weak on pedagogical examples or human readability."
    SCHEMA_PLUS_EXAMPLE::[CUE, OpenAPI]
      Tradeoff::"Great for documentation and validation, but lacks runtime execution bindings."
    EXAMPLE_PLUS_EXECUTION::[BDD, Embedded_Tests]
      Tradeoff::"Great for scenarios, but lacks formal schema definition for arbitrary data."

  STRUCTURAL_VS_SEMANTIC:
    INSIGHT::"Original research distinguished three validation types."
    STRUCTURAL::"Shape, types, required fields. (Most systems handle this well)."
    SEMANTIC::"Cross-field meaning, entailment, factual correctness. (Most systems miss this)."
    OPERATIONAL::"Is this route/action allowed? (Rarely addressed directly in schema)."
    RISK::"VALID_BUT_WRONG. Systems can produce structurally perfect JSON that is factually or semantically garbage."
    MITIGATION::"Need semantic validators (entailment checkers) or logic hooks, increasing complexity."

  NOVELTY:
    UNIQUE_VALUE::"Synthesis of Declarative Rigor + Pedagogical Examples + Execution Binding."
    BOOTSTRAP::"Recursive, self-exemplifying structure (document written in its own format)."
    COMPARISON::"Closest analog is Guardrails + Outlines + CUE, but none unify all three seamlessly."

§4::FAILURE_MODES
  COMPLEXITY_RISK::
    PROBLEM::"Balance expressiveness vs. simplicity. Must avoid becoming Turing-complete."
    HISTORY::"Attribute grammars proved too powerful/unmaintainable. Simpler schemas won adoption."

  DRIFT_RISK::
    PROBLEM::"If spec and code are separate, they drift. Spec must drive execution to stay relevant."
    MITIGATION::"Make spec part of build workflow (CI enforcement)."

  LLM_MISINTERPRETATION::
    PROBLEM::"Model might ignore or misunderstand spec."
    SOLUTION::"Provide few-shot examples or include spec in system prompt."

  OVER_RELIANCE::
    PROBLEM::"Models don't always obey 100%. Edge cases where output is valid but wrong."
    MITIGATION::"Runtime validator layer (like Guardrails) is essential. Can't assume perfect output."

  PERFORMANCE_SCALABILITY::
    PROBLEM::"Large specs = high token cost. Can't always fit entire spec in prompt."
    APPROACH::"Selective spec injection or two-pass validation (generate then check)."

§5::MINIMAL_EXECUTION
  // The 'engine' required to make the holographic spec real

  COMPONENT_1_PARSER::
    TASK::"Read holographic lines → extract [field_name, example, constraint, target]"
    IMPLEMENTATION::"Straightforward string parsing or simple PEG."
    COMPLEXITY::Low

  COMPONENT_2_VALIDATOR::
    TASK::"Convert spec → validation rules."
    MAPPING::"REQ→required, REGEX→pattern, ENUM→set."
    STRATEGY::"Leverage existing (compile to JSON Schema/Pydantic)."
    HANDLING::"Unknown fields policy (warn vs reject)."

  COMPONENT_3_TEACHING::
    TASK::"Prepare LLM to follow spec."
    METHOD::"Naive: Include spec in prompt. Advanced: Transform to OpenAI function schema or Guidance grammar."
    VALIDATION::"Validate after generation. If fail → feedback loop."

  COMPONENT_4_ROUTING::
    TASK::"Dispatch fields to targets based on spec."
    ARCHITECTURE::"Plugin system (if target==INDEXER → call IndexerClient)."
    BENEFIT::"No hardcoded field routing in code; dispatch driven by spec."

  VERDICT::
    "Not reinventing the wheel, but assembling components (schema, examples, hooks) into a new vehicle for LLM-driven apps."

===END===
