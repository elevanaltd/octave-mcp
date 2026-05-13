"""GH-384 (ADR-0006 SR2-T3, sub-spec G3): META audit-marker admission policy.

Sub-spec authority: ``docs/adr/adr-0006-g3-meta-audit-markers.md`` Option (C) —
bounded-prefix admission via the existing W_META_* warning channel.

These tests pin the acceptance criteria from §Acceptance Criteria item 3:

1. ``test_meta_audit_marker_admitted_strict`` — STRICT-mode validation of a
   doc with ``META.NON_CANONICAL_DEGRADED::true`` against a schema that
   defines META with non-empty fields produces NO ``E007`` and exactly ONE
   ``W_META_AUDIT``.
2. ``test_meta_audit_marker_admitted_lenient`` — LENIENT mode surfaces
   ``W_META_AUDIT`` (no longer silent).
3. ``test_meta_unknown_non_audit_key_still_rejected_strict`` — STRICT mode
   still emits ``E007`` for non-matching unknown keys.
4. ``test_meta_audit_marker_no_schema`` — no-schema doc still emits
   ``W_META_AUDIT`` (parity with W_META_001 unconditional behaviour).
5. ``test_degraded_regions_field`` — ``META.DEGRADED_REGIONS::[10, 42, 87]``
   is admitted.

Plus a small contract test pinning the patterns tuple and the warning code.

HARD_SYMMETRY coverage (acceptance criterion #6) is delivered by adding a
fixture under ``tests/fixtures/symmetry/`` — the parametrized HARD_SYMMETRY
suite in ``test_writer_reader_symmetry.py`` auto-discovers it via
``rglob("*.oct.md")``.
"""

from __future__ import annotations

from typing import Any

import pytest

from octave_mcp.core.parser import parse
from octave_mcp.core.validator import META_AUDIT_ADMIT_PATTERNS, Validator

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# A document with the SR2-T3 audit marker stamped in META.
DOC_WITH_NON_CANONICAL_DEGRADED = """\
===AUDIT_DOC===
META:
  TYPE::"TEST"
  NON_CANONICAL_DEGRADED::true

§1::CONTENT
  KEY::"value"

===END==="""

# A document with the second audit marker (list of byte offsets).
DOC_WITH_DEGRADED_REGIONS = """\
===AUDIT_DOC===
META:
  TYPE::"TEST"
  DEGRADED_REGIONS::[10, 42, 87]

§1::CONTENT
  KEY::"value"

===END==="""

# A document with an unknown META key that does NOT match the admit patterns.
DOC_WITH_UNKNOWN_NON_AUDIT_KEY = """\
===AUDIT_DOC===
META:
  TYPE::"TEST"
  SOMETHING_RANDOM::"unrelated"

§1::CONTENT
  KEY::"value"

===END==="""

# Schema declaring META with non-empty fields — required for the L328
# strict-mode E007 path to fire.
SCHEMA_WITH_META_FIELDS: dict[str, Any] = {
    "META": {
        "required": [],
        "fields": {
            "TYPE": {"type": "STR"},
        },
    },
}


# ---------------------------------------------------------------------------
# Contract: admit-patterns tuple + warning code
# ---------------------------------------------------------------------------


def test_admit_patterns_contains_sub_spec_prefixes() -> None:
    """The sub-spec enumerates four prefixes
    (``adr-0006-g3-meta-audit-markers.md`` §Acceptance Criteria item 1):
    ``NON_CANONICAL_``, ``DEGRADED_``, ``NORMALIZED_``, ``ROUNDTRIP_``."""
    assert "NON_CANONICAL_" in META_AUDIT_ADMIT_PATTERNS
    assert "DEGRADED_" in META_AUDIT_ADMIT_PATTERNS
    assert "NORMALIZED_" in META_AUDIT_ADMIT_PATTERNS
    assert "ROUNDTRIP_" in META_AUDIT_ADMIT_PATTERNS


def test_admit_patterns_is_a_tuple() -> None:
    """Sub-spec line 86: 'New constant ``META_AUDIT_ADMIT_PATTERNS`` ... or
    equivalent module-private tuple'. Tuple chosen over frozenset because the
    values are prefix strings consumed by ``str.startswith()`` — order does not
    affect semantics, but the sub-spec writes ``tuple`` explicitly. The
    immutability of ``tuple`` carries the closed-set intent."""
    assert isinstance(META_AUDIT_ADMIT_PATTERNS, tuple)


# ---------------------------------------------------------------------------
# Acceptance criterion 1: STRICT-mode admits without E007 + one W_META_AUDIT
# ---------------------------------------------------------------------------


def test_meta_audit_marker_admitted_strict() -> None:
    """STRICT-mode validation of a doc with ``META.NON_CANONICAL_DEGRADED::true``
    against a schema that defines META with non-empty fields produces NO E007
    and exactly ONE W_META_AUDIT (sub-spec §Acceptance Criteria item 3.1)."""
    doc = parse(DOC_WITH_NON_CANONICAL_DEGRADED)
    validator = Validator(schema=SCHEMA_WITH_META_FIELDS)
    validator.validate(doc, strict=True)

    e007s = [e for e in validator.errors if e.code == "E007"]
    audits = [e for e in validator.errors if e.code == "W_META_AUDIT"]

    assert e007s == [], (
        f"STRICT mode must admit META.NON_CANONICAL_DEGRADED (matches "
        f"NON_CANONICAL_ prefix in META_AUDIT_ADMIT_PATTERNS). "
        f"Unexpected E007s: {e007s!r}"
    )
    assert len(audits) == 1, (
        f"Exactly one W_META_AUDIT should fire for the single matching key. " f"Got {len(audits)}: {audits!r}"
    )
    assert audits[0].severity == "warning"
    assert audits[0].field_path == "META.NON_CANONICAL_DEGRADED"


# ---------------------------------------------------------------------------
# Acceptance criterion 2: LENIENT mode surfaces W_META_AUDIT (no longer silent)
# ---------------------------------------------------------------------------


def test_meta_audit_marker_admitted_lenient() -> None:
    """LENIENT validation surfaces W_META_AUDIT (sub-spec line 67–69:
    'previously silent → now visible via the warning channel')."""
    doc = parse(DOC_WITH_NON_CANONICAL_DEGRADED)
    validator = Validator(schema=SCHEMA_WITH_META_FIELDS)
    validator.validate(doc, strict=False)

    e007s = [e for e in validator.errors if e.code == "E007"]
    audits = [e for e in validator.errors if e.code == "W_META_AUDIT"]

    assert e007s == [], f"LENIENT mode must not raise E007. Got: {e007s!r}"
    assert len(audits) == 1, (
        f"LENIENT mode must surface exactly one W_META_AUDIT (no longer silent). " f"Got {len(audits)}: {audits!r}"
    )


# ---------------------------------------------------------------------------
# Acceptance criterion 3: STRICT mode still rejects non-matching unknown keys
# ---------------------------------------------------------------------------


def test_meta_unknown_non_audit_key_still_rejected_strict() -> None:
    """STRICT mode must still emit E007 for ``META.SOMETHING_RANDOM`` which
    does NOT match any pattern in META_AUDIT_ADMIT_PATTERNS (sub-spec
    §Acceptance Criteria item 3.3)."""
    doc = parse(DOC_WITH_UNKNOWN_NON_AUDIT_KEY)
    validator = Validator(schema=SCHEMA_WITH_META_FIELDS)
    validator.validate(doc, strict=True)

    e007s = [e for e in validator.errors if e.code == "E007"]
    audits = [e for e in validator.errors if e.code == "W_META_AUDIT"]

    assert any(e.field_path == "META.SOMETHING_RANDOM" for e in e007s), (
        f"STRICT mode must still raise E007 for non-matching unknown key " f"META.SOMETHING_RANDOM. Got: {e007s!r}"
    )
    assert audits == [], f"No W_META_AUDIT should fire for non-matching key. Got: {audits!r}"


# ---------------------------------------------------------------------------
# Acceptance criterion 4: no-schema doc still emits W_META_AUDIT
# ---------------------------------------------------------------------------


def test_meta_audit_marker_no_schema() -> None:
    """A doc with no schema, with ``META.NON_CANONICAL_DEGRADED::true``, must
    still surface W_META_AUDIT — parity with the W_META_001/W_META_002
    unconditional pattern (sub-spec line 88: 'in both LENIENT and STRICT
    modes, regardless of schema presence')."""
    doc = parse(DOC_WITH_NON_CANONICAL_DEGRADED)
    validator = Validator()  # no schema
    validator.validate(doc)

    audits = [e for e in validator.errors if e.code == "W_META_AUDIT"]
    assert len(audits) == 1, (
        f"W_META_AUDIT must fire unconditionally on doc.meta content, " f"even without a schema. Got: {audits!r}"
    )
    assert audits[0].severity == "warning"


# ---------------------------------------------------------------------------
# Acceptance criterion 5: DEGRADED_REGIONS admitted (second SR2-T3 marker)
# ---------------------------------------------------------------------------


def test_degraded_regions_field() -> None:
    """``META.DEGRADED_REGIONS::[10, 42, 87]`` is admitted — covers the second
    SR2-T3 marker via the ``DEGRADED_`` prefix in META_AUDIT_ADMIT_PATTERNS
    (sub-spec §Acceptance Criteria item 3.5)."""
    doc = parse(DOC_WITH_DEGRADED_REGIONS)
    validator = Validator(schema=SCHEMA_WITH_META_FIELDS)
    validator.validate(doc, strict=True)

    e007s = [e for e in validator.errors if e.code == "E007"]
    audits = [e for e in validator.errors if e.code == "W_META_AUDIT"]

    assert e007s == [], f"DEGRADED_REGIONS must be admitted under STRICT mode. Got E007s: {e007s!r}"
    assert len(audits) == 1, f"Exactly one W_META_AUDIT for DEGRADED_REGIONS. Got: {audits!r}"
    assert audits[0].field_path == "META.DEGRADED_REGIONS"


# ---------------------------------------------------------------------------
# Negative contract: severity & no error-class leakage
# ---------------------------------------------------------------------------


def test_w_meta_audit_severity_is_warning_not_error() -> None:
    """W_META_AUDIT is informational (sub-spec line 109: 'informational and
    does not fail validation')."""
    doc = parse(DOC_WITH_NON_CANONICAL_DEGRADED)
    validator = Validator(schema=SCHEMA_WITH_META_FIELDS)
    validator.validate(doc, strict=True)

    audits = [e for e in validator.errors if e.code == "W_META_AUDIT"]
    assert len(audits) >= 1
    for a in audits:
        assert a.severity == "warning", f"W_META_AUDIT must have severity='warning'. Got: {a!r}"


@pytest.mark.parametrize("prefix", list(META_AUDIT_ADMIT_PATTERNS))
def test_every_admit_pattern_admits_a_synthetic_key(prefix: str) -> None:
    """Sanity: every prefix in the tuple admits at least one synthetic key
    constructed from it. Guards against future drift where a prefix is added
    to the tuple but not exercised by any acceptance test."""
    synthetic_key = f"{prefix}SYNTHETIC"
    doc_src = (
        f"===AUDIT_DOC===\n"
        f"META:\n"
        f'  TYPE::"TEST"\n'
        f'  {synthetic_key}::"v"\n'
        f"\n"
        f"§1::CONTENT\n"
        f'  KEY::"value"\n'
        f"\n"
        f"===END==="
    )
    doc = parse(doc_src)
    validator = Validator(schema=SCHEMA_WITH_META_FIELDS)
    validator.validate(doc, strict=True)

    e007s = [e for e in validator.errors if e.code == "E007" and e.field_path == f"META.{synthetic_key}"]
    audits = [e for e in validator.errors if e.code == "W_META_AUDIT" and e.field_path == f"META.{synthetic_key}"]

    assert e007s == [], f"Prefix {prefix!r} must admit {synthetic_key}; got E007s: {e007s!r}"
    assert len(audits) == 1, f"Prefix {prefix!r} must produce one W_META_AUDIT for {synthetic_key}; " f"got: {audits!r}"
