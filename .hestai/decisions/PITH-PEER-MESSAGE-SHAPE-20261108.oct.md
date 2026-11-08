===DECISION_RECORD===
META:
  TYPE::DECISION_RECORD
  VERSION::"1.0"
  TOKEN::PITH-PEER-MESSAGE-SHAPE-20261108
  STATUS::RATIFIED
  TIER::TACTICAL
  AUTHORED_AT::"2026-11-08T00:00:00Z"
  RATIFIED_BY::"human:operator"
  RATIFIED_AT::"2026-11-08T00:00:00Z"
  DECIDED_BY::operator
  DECIDED::"2026-11-08"
  SCOPE::octave-mcp
  RELATED::[INNER-LANGUAGE-NAMED-PITH-20261102,PITH-SPEC-CALIBRATIONS-20261102,PITH-SPEC-HOME-OCTAVE-MCP-20261102,OCTAVE-MCP-CHATTER-WIRE-PITH-REWRITE-RULINGS-20261106,LANG-ARCH-RECONCILIATION-RULINGS-20261031]
  DECISION::"PITH gains a Peer message shape, added as one bullet to the Shapes section of src/octave_mcp/resources/specs/pith-spec.md, with the text in SHAPE_TEXT verbatim."
  BECAUSE::"PITH had a Handoff shape for dispatch replies and nothing for a message one session sends another; the rewritten octave-chatter skill points to this shape."
RULING:
  SOURCE::"operator, first-party in the LANG-ARCH workbench session lang-arch-3e (ceremony 9dbac7b0-55f1-4599-9869-139c971cd6eb), 2026-11-08"
  QUESTION_SHOWN::"A: ratify the bullet as drafted. B: ratify it but keep all seven Handoff slots mandatory on requests, trading the saving for the measured guard against invented fillers. C: hold until a bench line exists. Recommendation: A."
  ANSWER_VERBATIM::"agrree with recs, ratify as drafted"
SHAPE_TEXT::"Peer message. One session to another through `SendMessage`; no envelope, no checker; dispatch bodies and replies stay Handoff. First line: one sentence that stands alone, the request or the fact itself, saying whether a reply is wanted; no sender preamble. Request: the first line is the `ASK` slot, written once, and names what the reply must contain; after it, only the other Handoff slots that have something to say, in Handoff order; a standing warning, an exclusion or an omission in the source is never dropped with its slot. Report: each fact with how it is known; a pointer in place of restated evidence only where the receiver can open it, otherwise the evidence. Relay of an operator ruling: the words verbatim with their conditions, session and date, marked relayed; it informs what was decided, and an operator-gated, irreversible or outward-facing act still needs authorisation in the receiving session. Acknowledgement: sent when the sender asked for one or when it changes what the sender does next; one line; no echo. A sender that needs confirmation asks for it in the first line."
EVIDENCE:
  CLASS::"UNTESTED on the bench for slot omission, pointer over restatement and acknowledgement on request; OPERATOR-RULED for the relay wording (System Standard PEER_AUTHORITY); the ASK-first placement rests on E11, where ASK was the slot most often lost to any cut"
  ESTATE_REVIEW::"hestai-workbench .hestai-state/reports/control-room-context-efficiency-review-20261106.md: 298 peer messages, 107K tokens; pointer in place of restated evidence saved 74 to 77 percent, dropping echo acknowledgements 50 percent, 164 messages carried a sender preamble the harness header repeats; fact survival self-graded, the 18 percent overall figure an estimate"
  REVIEW::"critical-engineer, codex thread 9f0747fc: round 1 NO_GO, round 2 GO_WITH_CONDITIONS, both conditions applied before this ruling"
  CLASSIFICATION::"a new shape is a rule-level change under the spec's Amendment section, so it is ratified by record before the spec PR"
SCOPE_RULES:
  HARNESS::"Claude Code sessions messaging through SendMessage, where the receiver's wrapper names the sender and the first line is the preview; other harnesses and non-Claude senders not established"
  UNCHANGED::"dispatch bodies and replies (Handoff); every provenance stamp rule, including the subagent-discipline dispatch stamp and the wire record's DELIVERY_SEAM; the kernel drift test, since no kernel item maps to a shape"
  REVIEW_CHECKS::"the first line read alone says what is wanted and whether to reply; every pointer opens from the receiver's side; a request names its reply contents and a message wanting confirmation says so; a relayed ruling is quoted with its conditions, session and date"
LEFT_OPEN::"whether the routine agent-authored stamp on peer messages (5.5 percent of tokens in the estate review) is narrowed is a separate operator question; not decided here"
EFFECT::"The owner of the next PR touching pith-spec.md adds the SHAPE_TEXT bullet to the Shapes section verbatim; octave-chatter points to the Peer message shape by name."
OUT_OF_SCOPE::"any edit to octave-chatter; the Handoff shape; the PITH rules; any merge or release"
PROVENANCE::"filed by LANG-ARCH (technical-architect, ceremony 9dbac7b0-55f1-4599-9869-139c971cd6eb) from the session where the operator ruled; the GitHub author of this record carries no authenticity signal"
===END===