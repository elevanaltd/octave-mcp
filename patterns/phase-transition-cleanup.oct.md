===PATTERN:PHASE_TRANSITION_CLEANUP===
META:
  TYPE::PATTERN
  VERSION::"1.0"
  PURPOSE::"Protocol for maintaining system hygiene at phase boundaries"

§1::TRIGGER_POINTS
TRIGGERS::[B1_02_complete, B2_04_complete, B3_04_complete, B4_05_complete]

§2::EXECUTION
CLEANUP_SEQUENCE::"INVOKE directory-curator → RECEIVE violations report → DELEGATE workspace-architect → VALIDATE clean state"
ENFORCEMENT::"BLOCK phase progression if violations exist after workspace-architect remediation"

§3::REFERENCE
PROTOCOL_REFERENCE::"/Users/shaunbuswell/.claude/protocols/DOCUMENT_PLACEMENT_AND_VISIBILITY.md"

===END===
