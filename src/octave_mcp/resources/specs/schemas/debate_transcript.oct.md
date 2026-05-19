===DEBATE_TRANSCRIPT===
META:
  TYPE::SCHEMA
  VERSION::"1.1"
  STATUS::ACTIVE
  PURPOSE::"Schema for debate-hall-mcp debate transcripts. Enables OCTAVE validation and archival of structured debates with Wind/Wall/Door cognition patterns."
POLICY:
  VERSION::"1.0"
  UNKNOWN_FIELDS::WARN
  TARGETS::["§INDEXER","§SELF"]
FIELDS:
  THREAD_ID::["example-debate-001"∧REQ→§INDEXER]
  TOPIC::["The topic of the debate"∧REQ→§SELF]
  MODE::["fixed"∧REQ∧ENUM[fixed,mediated]→§SELF]
  STATUS::["active"∧REQ∧ENUM[active,paused,synthesis,closed]→§SELF]
  PARTICIPANTS::[[Wind,Wall,Door]∧REQ∧TYPE[LIST]→§SELF]
  TURNS::[[turn1,turn2]∧REQ∧TYPE[LIST]→§SELF]
  SYNTHESIS::["Final synthesis from Door agent"∧OPT→§SELF]
  MAX_ROUNDS::[4∧OPT∧TYPE[NUMBER]→§SELF]
  MAX_TURNS::[12∧OPT∧TYPE[NUMBER]→§SELF]
TURN_SCHEMA:
  ROLE::["Wind"∧REQ∧ENUM[Wind,Wall,Door,Synthesis,Human,Mediator]→§SELF]
  CONTENT::["The turn content"∧REQ→§SELF]
  TURN_INDEX::[1∧REQ∧TYPE[NUMBER]→§SELF]
  SPEAKER::["agent-id"∧OPT→§SELF]
  COGNITION::["PATHOS"∧OPT∧ENUM[PATHOS,ETHOS,LOGOS]→§SELF]
  AGENT_ROLE::["impl-lead"∧OPT→§SELF]
  MODEL::["claude-sonnet"∧OPT→§SELF]
  TIMESTAMP::["2025-01-01T00:00:00Z"∧OPT∧ISO8601→§SELF]
USAGE_NOTES::[
  "THREAD_ID: Unique identifier for the debate, used for indexing and retrieval",
  "TOPIC: Human-readable description of what the debate is about",
  "MODE: 'fixed' for strict rotation, 'mediated' for flexible speaker selection",
  "STATUS: 'active' during debate, 'paused' when awaiting human interjection, 'synthesis' when Door is finalizing, 'closed' when complete",
  "PARTICIPANTS: List of roles participating (typically Wind, Wall, Door)",
  "TURNS: Array of turn records with role, content, and optional cognition metadata. When emitted as a structured TURNS: block, each child block is validated against TURN_SCHEMA per GH-427.",
  "SYNTHESIS: Final resolution from Door agent when debate closes",
  "TURN_SCHEMA: Per-turn structural contract enforced by the validator (GH-427). ROLE/CONTENT/TURN_INDEX are required per turn; TURN_INDEX values must be unique across the transcript. Expanded ROLE enum (Wind|Wall|Door|Synthesis|Human|Mediator) covers debate-hall-mcp consumer reality."
]
===END===
