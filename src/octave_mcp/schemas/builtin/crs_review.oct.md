===CRS_REVIEW_SCHEMA===
META:
  TYPE::SCHEMA
  VERSION::"1.0.0"
  STATUS::ACTIVE
---
POLICY:
  VERSION::"1.0"
  UNKNOWN_FIELDS::WARN
  TARGETS::[
    "§VERDICT",
    "§DISTRIBUTION",
    "§FINDINGS",
    "§SUMMARY"
  ]
FIELDS:
  // §1::VERDICT section fields
  ROLE::["CRS"∧REQ]
  PROVIDER::["claude-opus-4-6"∧OPT]
  VERDICT::["APPROVED"∧REQ∧ENUM[APPROVED,BLOCKED,CONDITIONAL]]
  SHA::["abc1234"∧REQ]
  TIER::["T2"∧REQ∧ENUM[T0,T1,T2,T3,T4]]
  // §2::DISTRIBUTION section fields
  TOTAL::[0∧REQ]
  BLOCKING::[0∧REQ]
  TRIAGED::[true∧REQ]
  OMITTED::[0∧OPT]
  P0::[0∧OPT]
  P1::[0∧OPT]
  P2::[0∧OPT]
  P3::[0∧OPT]
  P4::[0∧OPT]
  P5::[0∧OPT]
  // §4::SUMMARY section fields
  ASSESSMENT::["Summary assessment"∧REQ]
  TOP_RISKS::[["Risk description"]∧REQ∧TYPE[LIST]]
===END===
