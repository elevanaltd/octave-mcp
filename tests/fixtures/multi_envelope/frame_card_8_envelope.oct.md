===META===
TYPE::FRAME_CARD
ID::FIXTURE_THREE_LAYER_GOVERNANCE_FRAME
STATUS::proposed
CARD_SCHEMA_VERSION::1
===END===

===EXACT===
IDS::[FIXTURE_FRAME]
PROD_IMMUTABLES::[I1, I2, I3]
ADR_REFS::[ADR_0013]
===END===

===SOURCE_REFS===
PATHS::[src/fixture_one.py, src/fixture_two.py]
===END===

===FACETS===
INTENT::"three-layer governance fixture for octave-mcp #420 multi-envelope round-trip"
CONSTRAINTS::[c1, c2]
===END===

===AUDIENCE_VIEW_SEEDS===
GLOBAL::"reviewer_50_tokens"
AGENT::"reviewer_200_tokens"
===END===

===EDGES===
EXTENDS::[ADR_0013]
RELATED::[CONCEPT_FIXTURE]
===END===

===PROVENANCE===
MARKERS::["src/fixture_one.py#layer"]
===END===

===VALIDATION===
SOURCE_REF_RESOLVES::true
MARKERS_RESOLVE_TO_CARD::true
===END===
