===OCTAVE_PHILOSOPHY===
META:
  TYPE::GUIDE
  VERSION::"1.0"
  PURPOSE::"Anti-patterns and quality principles for effective OCTAVE"
§1::GOLDEN_RULE
  LITMUS::"If your OCTAVE were a database schema, would it have foreign keys?"
  MEANING::"Flat lists provide information. Relationship networks provide understanding."
  MANDATE::"Show how elements connect, influence, depend"
§2::SEVEN_DEADLY_SMELLS
  ISOLATED_LISTS:
    SYMPTOM::"Array items without explicit relationships"
    IMPACT::"LLM knows WHAT, not HOW they connect"
    FIX::"Hierarchy with relationship keys (ENABLES, CONFLICTS_WITH)"
  CEREMONY_OVERFLOW:
    SYMPTOM::"Prose, metaphors, comments everywhere"
    IMPACT::"Signal vs Noise. LLMs extract from structure, not poetry"
    FIX::"Be ruthless. One metaphor max"
  FAKE_DEFINITIONS:
    SYMPTOM::"0.DEF defines obvious terms"
    IMPACT::"Clutters space, hides domain terms"
    FIX::"Only custom terms used repeatedly"
  FLAT_HIERARCHIES:
    SYMPTOM::"15-20 keys at root"
    IMPACT::"Structure implies meaning. Flat implies none"
    FIX::"Group into sections. Depth 2-3 levels"
  MISSING_EXAMPLES:
    SYMPTOM::"Abstract rules, no concrete examples"
    IMPACT::"LLMs learn from examples > descriptions"
    FIX::"Every rule needs VALID+INVALID examples"
  BURIED_NETWORKS:
    SYMPTOM::"Relationships in prose DESCRIPTION fields"
    IMPACT::"LLMs cannot parse prose to graphs"
    FIX::"Explicit keys (REQUIRES::X, ENABLES::Y)"
  MIXED_CONCERNS:
    SYMPTOM::"Mandatory mixed with optional"
    IMPACT::"Ambiguous boundaries"
    FIX::"Separate MANDATORY and OPTIONAL sections"
§3::AUTHORING_CHECKLIST
  BEFORE::["relationships?","mandatory_vs_optional?","simplest_example?"]
  DURING::["remove_50_percent_words?","explicit_keys?","examples>descriptions?"]
  AFTER::["works_without_metaphors?","drawable_diagram?","all_0.DEF_referenced?"]
===END===
