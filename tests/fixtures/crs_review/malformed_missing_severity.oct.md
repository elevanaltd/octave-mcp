===CRS_REVIEW===
META:
  TYPE::CRS_REVIEW
  VERSION::"1.0.0"

§1::VERDICT
  ROLE::CRS
  PROVIDER::"claude-opus-4-6"
  VERDICT::BLOCKED
  SHA::"abc1234"
  TIER::T2

§2::DISTRIBUTION
  TOTAL::1
  BLOCKING::1
  TRIAGED::true
  OMITTED::0
  P0::0
  P1::0
  P2::0
  P3::0
  P4::0
  P5::0

§3::FINDINGS
  [FILE::"auth.py",ISSUE::"Missing SEVERITY field",REQUIRED_FIX::"Add SEVERITY to the finding"]

§4::SUMMARY
  ASSESSMENT::"Test malformed fixture - missing SEVERITY"
  TOP_RISKS::[]

===END===
