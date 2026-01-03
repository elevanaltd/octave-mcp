===DOCUMENT_WITH_IMPORT===
META:
  TYPE::"SPEC"
  VERSION::"1.0.0"
  PURPOSE::"Test document that imports vocabulary terms"
  STATUS::ACTIVE

§CONTEXT::SNAPSHOT["@test/vocabulary"]
  ALPHA::"First letter of the Greek alphabet"
  BETA::"Second letter of the Greek alphabet"
  DELTA::"Fourth letter of the Greek alphabet"

§SNAPSHOT::MANIFEST
  SOURCE_URI::"tests/fixtures/hydration/vocabulary.oct.md"
  SOURCE_HASH::"sha256:PLACEHOLDER_HASH"
  HYDRATION_TIME::"PLACEHOLDER_TIMESTAMP"
  HYDRATION_POLICY:
    DEPTH::1
    PRUNE::"list"
    COLLISION::"error"

§SNAPSHOT::PRUNED
  TERMS::[GAMMA,EPSILON]

§1::CONTENT
  USES_ALPHA::true
  USES_BETA::true
  USES_DELTA::true
  DESCRIPTION::"This document uses ALPHA, BETA, and DELTA terms"

===END===
