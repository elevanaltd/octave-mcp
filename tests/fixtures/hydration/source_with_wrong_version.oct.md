===DOCUMENT_WITH_WRONG_VERSION===
META:
  TYPE::"SPEC"
  VERSION::"1.0.0"
  PURPOSE::"Test document with mismatched version import"
  STATUS::ACTIVE

§CONTEXT::IMPORT["@test/vocabulary","2.0.0"]

§1::CONTENT
  USES_ALPHA::true
  DESCRIPTION::"This document requests version 2.0.0 but registry has 1.0.0"

===END===
