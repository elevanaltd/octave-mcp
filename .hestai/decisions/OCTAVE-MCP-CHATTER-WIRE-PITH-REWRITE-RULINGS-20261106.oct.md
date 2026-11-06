===DECISION_RECORD===
META:
  TYPE::DECISION_RECORD
  VERSION::"1.0"
  TOKEN::OCTAVE-MCP-CHATTER-WIRE-PITH-REWRITE-RULINGS-20261106
  STATUS::RATIFIED
  TIER::STRATEGIC
  AUTHORED_AT::"2026-11-06T00:00:00Z"
  RATIFIED_BY::"human:operator"
  RATIFIED_AT::"2026-11-06T00:00:00Z"
  DECIDED_BY::operator
  DECIDED::"2026-11-06"
  SCOPE::octave-mcp
  SUPERSEDES::"REGISTER_SPLIT.RULE line only, of hestai-workbench record OCTAVE-WIRE-POSITION-0-WITHDRAWN-20260909"
  RELATED::[OCTAVE-MCP-P2-8-SKILLS-LANGUAGE-RULINGS-20261101,INNER-LANGUAGE-NAMED-PITH-20261102,PITH-SPEC-HOME-OCTAVE-MCP-20261102,LANG-ARCH-RECONCILIATION-RULINGS-20261031,OCTAVE-WIRE-POSITION-0-WITHDRAWN-20260909]
  DECISION::"Keep octave-chatter and rewrite it as PITH applied to message bodies. Supersede only the REGISTER_SPLIT.RULE line of the 2026-09-09 wire record. Fold the rewrite into the single P2-8b2 PR, after PR 545 merges."
  BECAUSE::"Operator ruled 2026-11-06 in the chatter-review session. LANG-ARCH-RECONCILIATION-RULINGS-20261031 does not explicitly supersede the wire record RULE line, so without this record two ratified records conflict."
RULINGS:
  SOURCE::"operator answers in the chatter-review session on 2026-11-06, verbatim"
  ANSWER_1::"Yes, keep and rewrite"
  ANSWER_2::"Yes, to supersede with this new info"
  ANSWER_3::"Fold into single rewrite"
QUESTIONS_ASKED:
  Q1::"Direction for octave-chatter (P2-8b Q2): keep and rewrite as PITH applied to message bodies, the WIRE register carrier, instead of deprecating it with a pointer to PITH."
  Q2::"Supersedure: this record supersedes ONLY the REGISTER_SPLIT.RULE line of hestai-workbench record OCTAVE-WIRE-POSITION-0-WITHDRAWN-20260909, replacing it with 'PITH rules apply in message bodies'. It KEEPS REGISTER_SPLIT itself (FORMAL versus WIRE, split by who validates) and DELIVERY_SEAM (octave-chatter kernel, section 5, as the dispatch-envelope target, still unimplemented and unfunded)."
  Q3::"Sequencing: the chatter rewrite folds into the single P2-8b2 PR owned by the octave-expert session, after octave-mcp PR 545 (b1) merges. No parallel chatter PR. The release hold stays until b2 merges."
REWRITE_SCOPE:
  SOURCE::"keep, drop and add content from octave-expert session octave-expert-a2, ceremony f794270b, accepted by the holistic-orchestrator; the operator rulings authorise this scope"
  KEEP::"the register split as the skill purpose; provenance on every message; identifiers verbatim in backticks and hedges verbatim; a kernel of about 138 tokens as the seam target"
  DROP::"the section 3 operator table as authoring guidance (a fenced reading reference at most); 'operators carry the connectives' and the ASCII wire policy; mythology as 'semantic zip' and first-use glosses; the 'quote the phrase, drop stopwords' telegraphic form, replaced by PITH Note form; '?' as the hedge marker"
  ADD::"the PITH standard items in the page's own wording; TARGET citing PITH; a pointer to the PITH Handoff shape, and to a peer-message shape once LANG-ARCH adds one"
EVIDENCE:
  CONFLICT::"measured by octave-expert: grep for SUPERSED, WIRE, chatter and REGISTER at hestai-workbench 0b2c11a found no explicit supersedure of the wire record RULE line in LANG-ARCH-RECONCILIATION-RULINGS-20261031"
  PITH_ON_MESSAGES::"arrows carrying a verb misread 12 of 12 (E1, E1b); operators copied through unless replaced (E15 C)"
  CONSUMERS::"hestai-workbench HEAD 0b2c11a7 has no code or archetype-matrix references to octave-chatter or OCTAVE_WIRE (git grep by the holistic-orchestrator), so the seam is unimplemented and the rewrite breaks no consumer today"
  BASE::"octave-expert verdict c at hestai-workbench origin/main 0b2c11a and octave-mcp PR 545 at ec9a6cf"
CROSS_REPO::"the superseded record lives in hestai-workbench at .hestai/decisions/OCTAVE-WIRE-POSITION-0-WITHDRAWN-20260909.oct.md; a forward-reference MERGE delta on it is a hestai-workbench-lane follow-on and is not made here"
OUT_OF_SCOPE::"any edit to octave-chatter SKILL.md, the PITH spec or any skill file; any edit in hestai-workbench; Q1 ultra-mythic, owned by another session"
PROVENANCE::"filed by octave-secretary on dispatch from holistic-orchestrator at chatter-review-bc; the rulings are the operator's, given in the dispatching session, and are transcribed here, not made by the filing agents"
===END===