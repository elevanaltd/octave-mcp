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


# ---------------------------------------------------------------------------
# TMG follow-up (PR #419 comment 4439247781): boundary tests for
# prefix-adjacent non-matching META keys.
#
# Sub-spec §Acceptance Criteria implies that "close-but-non-matching keys
# like NON_CANON_DEGRADED or _NON_CANONICAL_" must STILL trigger E007 in
# STRICT mode AND NOT emit W_META_AUDIT. The 8 tests below cover the
# closure: one close-match (root-word resemblance, prefix mismatch) and
# one leading-underscore variant per admit pattern.
#
# Selection methodology for "close-match" non-admit keys:
# - Each close-match shares the prefix's root word but truncates or alters
#   the trailing portion so ``str.startswith(prefix)`` returns False.
# - Documented in each test docstring; future-prefix admissibility is
#   called out where relevant (e.g. NON_CANON_ could plausibly be added
#   as a future admit prefix, but at the present admit-pattern surface
#   it is a non-match and MUST reject).
# ---------------------------------------------------------------------------


def _make_doc_with_meta_key(key: str) -> str:
    """Build a minimal OCTAVE doc whose META block contains ``key``."""
    return (
        f"===AUDIT_DOC===\n"
        f"META:\n"
        f'  TYPE::"TEST"\n'
        f'  {key}::"v"\n'
        f"\n"
        f"§1::CONTENT\n"
        f'  KEY::"value"\n'
        f"\n"
        f"===END==="
    )


def _assert_strict_rejects_non_match(field_name: str) -> None:
    """Shared assertion: STRICT-mode emits E007 for ``field_name`` and does
    NOT emit W_META_AUDIT for it.

    This is the closure half of the admission policy — anything that does
    not match ``META_AUDIT_ADMIT_PATTERNS`` is governed by the existing
    L328 unknown-field check (E007), not by the admit path.
    """
    doc = parse(_make_doc_with_meta_key(field_name))
    validator = Validator(schema=SCHEMA_WITH_META_FIELDS)
    validator.validate(doc, strict=True)

    e007_for_key = [e for e in validator.errors if e.code == "E007" and e.field_path == f"META.{field_name}"]
    audit_for_key = [e for e in validator.errors if e.code == "W_META_AUDIT" and e.field_path == f"META.{field_name}"]

    assert e007_for_key, (
        f"STRICT mode must reject prefix-adjacent non-match {field_name!r} with E007 "
        f"(no admit pattern in META_AUDIT_ADMIT_PATTERNS matches). "
        f"All errors: {validator.errors!r}"
    )
    assert audit_for_key == [], (
        f"W_META_AUDIT must NOT fire for prefix-adjacent non-match {field_name!r}; " f"got: {audit_for_key!r}"
    )


# --- NON_CANONICAL_ prefix boundary -----------------------------------------


def test_close_match_non_canon_degraded_rejected() -> None:
    """``NON_CANON_DEGRADED`` shares the root word ``NON_`` and contains
    ``CANON`` but drops the trailing ``ICAL_`` — does NOT match the
    ``NON_CANONICAL_`` admit prefix. STRICT mode must reject with E007.

    Note: ``NON_CANON_`` could plausibly be added as a future admit
    prefix (it carries the same semantic intent — a "non-canonical"
    audit marker). At the present admit-pattern surface
    (``META_AUDIT_ADMIT_PATTERNS``), however, it is a non-match and MUST
    reject — that closure is the whole point of the bounded admission
    policy (sub-spec §Out of Scope: 'closing the broader admission gap
    ... is separate validator-vocabulary alignment work')."""
    _assert_strict_rejects_non_match("NON_CANON_DEGRADED")


def test_leading_underscore_non_canonical_rejected() -> None:
    """``_NON_CANONICAL_PREFIX`` has a leading underscore so
    ``str.startswith("NON_CANONICAL_")`` returns False. STRICT mode must
    reject with E007."""
    _assert_strict_rejects_non_match("_NON_CANONICAL_PREFIX")


# --- DEGRADED_ prefix boundary ----------------------------------------------


def test_close_match_degrade_regions_rejected() -> None:
    """``DEGRADE_REGIONS`` drops the trailing ``D`` so it does NOT match
    ``DEGRADED_``. STRICT mode must reject with E007.

    Selection rationale: this is the canonical "off-by-one trailing
    char" boundary case — ``DEGRADE`` is a real English word and a
    plausible typo for ``DEGRADED``, so this guards a likely real-world
    misspelling."""
    _assert_strict_rejects_non_match("DEGRADE_REGIONS")


def test_leading_underscore_degraded_rejected() -> None:
    """``_DEGRADED_MARKER`` has a leading underscore so
    ``str.startswith("DEGRADED_")`` returns False. STRICT mode must
    reject with E007."""
    _assert_strict_rejects_non_match("_DEGRADED_MARKER")


# --- NORMALIZED_ prefix boundary --------------------------------------------


def test_close_match_normalised_from_rejected() -> None:
    """``NORMALISED_FROM`` (British spelling, S not Z) does NOT match the
    American-spelling admit prefix ``NORMALIZED_``. STRICT mode must
    reject with E007.

    Selection rationale: locale-spelling drift is a known accumulator of
    silent-pass-through bugs. Pinning the rejection here makes the
    locale assumption in the admit-pattern set explicit."""
    _assert_strict_rejects_non_match("NORMALISED_FROM")


def test_leading_underscore_normalized_rejected() -> None:
    """``_NORMALIZED_AT`` has a leading underscore so
    ``str.startswith("NORMALIZED_")`` returns False. STRICT mode must
    reject with E007."""
    _assert_strict_rejects_non_match("_NORMALIZED_AT")


# --- ROUNDTRIP_ prefix boundary ---------------------------------------------


def test_close_match_round_trip_loss_rejected() -> None:
    """``ROUND_TRIP_LOSS`` splits ``ROUNDTRIP`` with an underscore so it
    does NOT start with ``ROUNDTRIP_``. STRICT mode must reject with
    E007.

    Selection rationale: ``ROUND_TRIP`` is a common two-word variant in
    documentation; this guards against a casual reader assuming the
    prefix is word-segmentation-insensitive. The admit set is
    byte-prefix exact."""
    _assert_strict_rejects_non_match("ROUND_TRIP_LOSS")


def test_leading_underscore_roundtrip_rejected() -> None:
    """``_ROUNDTRIP_HASH`` has a leading underscore so
    ``str.startswith("ROUNDTRIP_")`` returns False. STRICT mode must
    reject with E007."""
    _assert_strict_rejects_non_match("_ROUNDTRIP_HASH")


# ---------------------------------------------------------------------------
# Existing parametric coverage of the admit side (preserved unchanged).
# ---------------------------------------------------------------------------


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
