===VOCABULARY_CAPSULE===
META:
  TYPE::CAPSULE
  NAME::META
  VERSION::"1.1.0"
  PURPOSE::"Core metadata vocabulary terms for OCTAVE documents"
  STATUS::ACTIVE
§1::DOCUMENT_METADATA
  TYPE::"Document type classification (SPEC|CAPSULE|SESSION_LOG|AGENT_DEFINITION|etc)"
  VERSION::"Semantic version string (MAJOR.MINOR.PATCH)"
  PURPOSE::"Human-readable purpose statement"
  STATUS::"Document lifecycle status (DRAFT|ACTIVE|DEPRECATED|ARCHIVED)"
§2::AUTHORSHIP
  AUTHOR::"Document author identifier"
  CREATED::"ISO-8601 creation timestamp"
  UPDATED::"ISO-8601 last update timestamp"
§3::CLASSIFICATION
  SCOPE::"Visibility scope (PUBLIC|INTERNAL|PRIVATE)"
  DOMAIN::"Subject domain classification"
  TAGS::"List of categorization tags"
§4::AUDIT_MARKERS
  PURPOSE::"Audit-trail markers stamped by tooling on non-canonical or degraded documents (ADR-0006 SR2-T3, GH-384). Admission is governed by META_AUDIT_ADMIT_PATTERNS in src/octave_mcp/core/validator.py; matching keys emit informational W_META_AUDIT instead of E007."
  NON_CANONICAL_DEGRADED::"bool — true when the source document was raw-ingested (octave_write --raw=true) and could not be fully canonicalised. Defence-in-depth marker; the load-bearing admission mechanism is the validator policy."
  DEGRADED_REGIONS::"list[int] — byte-offset markers identifying spans of the source document that bypassed canonicalisation. Offsets are integers; type-level validation of list contents is deferred."
===END===
