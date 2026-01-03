===DOCUMENT_WITH_COLLISION===
META:
  TYPE::"SPEC"
  VERSION::"1.0.0"
  PURPOSE::"Test document with local term that collides with imported term"
  STATUS::ACTIVE

§CONTEXT::IMPORT["@test/vocabulary"]

§CONTEXT::LOCAL
  ALPHA::"Local definition of ALPHA that conflicts"

§1::CONTENT
  USES_ALPHA::true

===END===
