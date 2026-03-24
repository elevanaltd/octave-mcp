===OCTAVE_COGNITION===
META:
  TYPE::COGNITION_DEFINITION
  VERSION::"1.1.0"
  STATUS::ACTIVE
  PURPOSE::"Cognition master file schema — behavioral kernel for cognitive types"
// OCTAVE COGNITION v1.1: Adds CRAFT (optional methodological stance)
// Companion to octave-agents-spec.oct.md v7.0.0 (Cognitive Separation)
// Agent files reference cognition type via COGNITION field in §1::IDENTITY.
// This spec defines the structure of cognition master files loaded before
// the anchor ceremony as a pre-ceremony read.
//
// EVIDENCE BASIS:
// - N=40 study: labels + matching behavioral rules = +20% improvement (C041, p=0.901 for labels alone)
// - M022: Grammar contracts (§4) drove 92% vs 54% adherence — §4 untouched by this separation
// - Standalone files make A/B testing trivial (load it or don't)
//
// v1.1.0 CHANGES:
// - Added CRAFT (OPT) to §2::COGNITIVE_RULES between PRIME_DIRECTIVE and THINK
// - CRAFT provides methodological stance — bridges existential (PRIME_DIRECTIVE) and operational (THINK)
// - Backward compatible: v1.0.0 cognition files without CRAFT remain valid
//
// FIELD CONTRACT (must match octave-agents-spec.oct.md §1::IDENTITY COGNITION comment):
// NATURE (FORCE/ESSENCE/ELEMENT), MODE, PRIME_DIRECTIVE, CRAFT (OPT), THINK, THINK_NEVER
§1::COGNITIVE_IDENTITY
  // WHAT I AM — cognitive nature (immutable per type)
  NATURE:
    FORCE::[STRUCTURE∨CONSTRAINT∨POSSIBILITY]
    ESSENCE::"Archetype descriptor"
    // e.g. "ARCHITECT", "GUARDIAN", "EXPLORER"
    ELEMENT::[DOOR∨WALL∨WIND]
§2::COGNITIVE_RULES
  // HOW I THINK — behavioral kernel (enforcement payload)
  // These rules shape reasoning approach, not domain actions.
  // Domain-specific MUST_ALWAYS/MUST_NEVER live in the agent's §2::OPERATIONAL_BEHAVIOR.
  MODE::[CONVERGENT∨VALIDATION∨DIVERGENT]
  PRIME_DIRECTIVE::"Core cognitive instruction"
  // Single sentence that captures the essence of how this cognition type reasons.
  CRAFT::"Methodological stance"
  // OPTIONAL. Single sentence describing the discipline of practice.
  // Where PRIME_DIRECTIVE says "what to reveal" and THINK says "how to reason step-by-step",
  // CRAFT says "what approach to embody" — the methodological bridge.
  // v1.0.0 cognition files without CRAFT remain valid.
  THINK::["Cognitive behavioral rules","Each rule shapes reasoning approach"]
  // THINK rules define positive cognitive patterns — how to approach problems.
  THINK_NEVER::["Cognitive anti-patterns","Each rule is a hard cognitive boundary"]
  // THINK_NEVER rules define hard cognitive boundaries — reasoning traps to avoid.
===END===
