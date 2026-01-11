===VOCABULARY_CAPSULE===
META:
  TYPE::"CAPSULE"
  NAME::"SNAPSHOT"
  VERSION::"1.0.0"
  PURPOSE::"Vocabulary terms for hydrated snapshots with provenance"
  STATUS::ACTIVE

§1::SNAPSHOT_TERMS
  SNAPSHOT::"Hydrated content block from imported vocabulary"
  IMPORT::"Directive to import terms from external vocabulary"

§2::MANIFEST_TERMS
  MANIFEST::"Provenance record for hydrated snapshot"
  SOURCE_URI::"Path or URI to original vocabulary source"
  SOURCE_HASH::"SHA-256 hash of source content at hydration time"
  HYDRATION_TIME::"ISO-8601 timestamp of hydration operation"
  HYDRATION_POLICY::"Policy parameters used during hydration"

§3::PRUNING_TERMS
  PRUNED::"List of available-but-unused terms from source vocabulary"
  DEPTH::"Maximum recursion depth for transitive imports"
  PRUNE::"Strategy for manifesting pruned terms (list|hash|count|elide)"
  COLLISION::"Strategy for term collision handling (error|source_wins|local_wins)"

§4::FRESHNESS_TERMS
  FRESHNESS::"Optional staleness tracking metadata"
  STALE_AFTER::"ISO-8601 timestamp after which re-hydration is recommended"
  CHECK_URI::"URI to check for vocabulary updates"

===END===
