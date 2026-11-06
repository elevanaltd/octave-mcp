---
name: octave-chatter
description: "PITH on the wire: how to write the bodies of messages between agents in note form, with exact identifiers, hedges as words and provenance on every message. Wire messages are checked by the receiving model, not by octave_validate. For agents that read and write OCTAVE in conversation but do not author files."
allowed-tools: ["Read"]
triggers: ["octave chatter", "octave wire", "reply in octave", "octave message", "inter-agent message", "read octave", "answer in octave"]
version: "2.0.0"
---

===OCTAVE_CHATTER===
META:
  TYPE::SKILL
  VERSION::"2.0.0"
  STATUS::ACTIVE
  PURPOSE::"The wire register: PITH applied to the bodies of messages between agents"
  AUDIENCE::"agents that read and write OCTAVE in conversation but do not author .oct.md files"
  REQUIRES::[]
  RELATION::"file authoring: octave-literacy; tool receipts: octave-tool-reference"
  GOVERNING_RECORD::OCTAVE-MCP-CHATTER-WIRE-PITH-REWRITE-RULINGS-20261106
  STANDARD::"src/octave_mcp/resources/specs/pith-spec.md"
  KERNEL::"the §5 kernel measures 175 cl100k tokens as extracted (the span A4 and the drift test count) and 182 with its header line, on top of `9c58708f`; the 11 standard items are 85 of them; the hard cap is 300"
  SEAM::"the §5 kernel is the target for a later dispatch-envelope stamp; that stamp is not implemented, so nothing yet keeps an envelope copy equal to this one"
§1::REGISTER
  FORMAL::".oct.md files and closing anchors are checked by `octave_validate`; octave-literacy governs them"
  WIRE::"message bodies are checked by the receiving model; this skill governs them"
  SPLIT::"the split is decided by who validates, not by grammar; the syntax is the same"
  NOT_NEEDED::[
    "META block",
    "file schema",
    canonicalisation,
    "holographic contracts"
  ]
  EVIDENCE::"relay test on the OCTAVE_WIRE primer v1.1: 45 facts, 0 wrong, 1 lost, and every loss was an identifier; syntax was never the failure"
  LIMIT::"no tool checks a wire message; whether a receiver reads one correctly is not tested here"
§2::WRITING
  RULES::[
    "Write a message body in PITH: note form, plain words, one fact per line.",
    "Copy every identifier, number, SHA and role exactly, in backticks; never shorten, merge or paraphrase one.",
    "Write a hedge as words, as the sender wrote it; never mark doubt with a symbol.",
    "Name the sender in every message and say how each fact is known: measured at a SHA, relayed, or inferred.",
    "Write relations in words; an arrow or other operator in a value is read differently by different receivers.",
    "Write none or not known for an empty slot; never invent a value to fill it.",
    "Keep contradictions: state both claims and flag the conflict.",
    "Put code and commands in fences.",
    "Name what a reply could not resolve under UNCLEAR."
  ]
§3::SHAPES
  HANDOFF::"For asks and handoffs, use the Handoff shape in PITH (`pith-spec.md`, Shapes)."
  ENVELOPE::"the envelope line pair is optional on the wire for other messages, to quote one as a unit; a Handoff carries none"
  EXAMPLE:
    ```
    ASK::"Can you confirm the lockfile change before merge?"
    FROM::"implementation-lead[align-octave-skills]"
    DECIDED::"the guard tests are approved at `9c58708f`; GREEN may start"
    OUT_OF_SCOPE::"changes to test files"
    DONE::[
      "measured at `9c58708f`: 195 tests pass",
      "measured at `9c58708f`: 20 tests fail as expected",
      "relayed from the review comment: approved",
      "inferred: the lockfile is unchanged"
    ]
    UNCLEAR::"which profile loads first: not known"
    LEFT_OUT::"restates the ask: confirm the lockfile change"
    ```
  // section 4 is deliberately unused: the ratified record OCTAVE-WIRE-POSITION-0-WITHDRAWN-20260909 cites the kernel here as section 5; do not renumber
§5::ANCHOR_KERNEL
  TARGET::"auditable OCTAVE messages between agents, in PITH"
  NEVER::[]
  MUST::[
    "Note form",
    "Exact identifiers (copied exactly, in backticks; never shortened or merged)",
    "Hedges verbatim",
    "Relations in words (no operators in prose or values)",
    "Nothing invented (none or not known)",
    "No writer-made ids, tags or counts",
    "One calibration sentence",
    "Judgement unattributed",
    "Code in fences",
    "Contradictions kept and flagged",
    "Plain vocabulary (no blobs, no mythology as instruction words)",
    "provenance on every message: measured at a SHA, relayed or inferred"
  ]
  GATE::"Could the receiver act on this without asking what any identifier meant or how a fact is known?"
===END===
