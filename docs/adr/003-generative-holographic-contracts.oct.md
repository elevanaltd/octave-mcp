===ADR_003_GENERATIVE_HOLOGRAPHIC_CONTRACTS===
META:
  TYPE::ARCHITECTURE_DECISION
  VERSION::"6.0.0"
  STATUS::ACCEPTED
  DATE::"2026-01-06"

  CONTRACT::HOLOGRAPHIC[
    PRINCIPLE::"The document carries its own law."
    VALIDATION::JIT_COMPILE[META -> GRAMMAR]
    ANCHORING::HERMETIC[NO_NETWORK_HOT_PATH]
  ]

§1::CONTEXT
  PROBLEM::"The 'Validator' model (post-hoc checking) creates 'Formatting Theater' and dependency hell."
  TENSION::Wind[Flexibility] ⇌ Wall[Rigor] → Door[Sovereignty]
  PREVIOUS_STATE::External schema files, runtime network resolution, loose regex.

§2::DECISION
  STRATEGY::"Generative Holographic Contracts"

  1::EMBEDDED_CONTRACTS
    RULE::"Schema lives in META."
    IMPACT::Removes registry bottlenecks. Files are self-describing.

  2::GENERATIVE_CONSTRAINTS
    RULE::"Validation precedes generation."
    MECHANISM::META compiles to GBNF/Outlines grammar.
    RESULT::Impossible to generate invalid syntax.

  3::HERMETIC_ANCHORING
    RULE::"Frozen Standards."
    DEV::`standard: latest` (local).
    PROD::`standard: frozen@sha256:...` (immutable).

§3::IMPACT
  CODEBASE::Streamline `hydrator.py` (remove dynamic resolution), refactor `parser.py` (two-pass), pivot `constraints.py` (compile vs evaluate).
  VERSIONING::Bump LLM Profiles to 6.0.0. Bump Package to v0.4.0.
  SECURITY::Root-of-Trust signature required for base schemas.

===END===
