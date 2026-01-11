===VOCABULARY_REGISTRY===
META:
  TYPE::"REGISTRY"
  VERSION::"1.0.0"
  PURPOSE::"Machine-readable index of OCTAVE vocabulary capsules"
  STATUS::ACTIVE

§1::REGISTRY_SCHEMA
  ENTRY_FORMAT::[
    NAME::"Vocabulary capsule name",
    PATH::"Relative path from registry root",
    VERSION::"Semantic version",
    HASH::"SHA-256 hash of capsule content"
  ]

§2::CORE_VOCABULARIES
  DESCRIPTION::"Built-in vocabularies shipped with octave-mcp"

  §2a::SNAPSHOT
    NAME::"SNAPSHOT"
    PATH::"core/SNAPSHOT.oct.md"
    VERSION::"1.0.0"
    TERMS::[SNAPSHOT,MANIFEST,PRUNED,SOURCE_URI,SOURCE_HASH,HYDRATION_TIME,HYDRATION_POLICY]

  §2b::META
    NAME::"META"
    PATH::"core/META.oct.md"
    VERSION::"1.0.0"
    TERMS::[TYPE,VERSION,PURPOSE,STATUS,AUTHOR,CREATED,UPDATED]

§3::CONTRIB_VOCABULARIES
  DESCRIPTION::"Community-contributed vocabularies"
  ENTRIES::[]

§4::RESOLUTION_RULES
  NAMESPACE_FORMAT::"@{namespace}/{vocabulary}"
  CORE_NAMESPACE::"core"
  LOOKUP_ORDER::[LOCAL,CORE,CONTRIB]
  COLLISION_POLICY::"error"

===END===
