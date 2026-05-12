"""GH-386: Warning-code discriminant on the destructive-normalization guard.

Context
-------
PR #383 centralised the destructive-empty-`after` suppression into
``is_destructive_normalization_repair`` in ``octave_mcp.core.repair_log``.
The helper keyed purely on *shape* (``type == "normalization"`` OR a
``normalized`` field present), which is safe for today's W002 ASCII-alias
set but brittle: a future W003+ that reuses the same record shape but
legitimately wants different empty-handling would be silently suppressed.

GH-386 (CE follow-up from PR #383) refactors the helper to additionally
accept a warning code (or category) and only suppress when BOTH:
  * the warning code is W002 (or an explicitly enumerated successor), AND
  * the ``normalized`` value is empty.

A future W003+ normalization warning must pass through the helper (return
False) so its caller can apply its own empty-handling policy.

These tests pin the new contract.
"""

from __future__ import annotations

from typing import Any

from octave_mcp.core.repair_log import (
    SUPPRESSIBLE_NORMALIZATION_CODES,
    is_destructive_normalization_repair,
)

# ---------------------------------------------------------------------------
# Suppression-eligible code set
# ---------------------------------------------------------------------------


def test_suppressible_codes_contains_w002() -> None:
    """W002 is the canonical destructive-normalization code today."""
    assert "W002" in SUPPRESSIBLE_NORMALIZATION_CODES


def test_suppressible_codes_is_a_frozen_set() -> None:
    """The enumeration is intentionally a closed set; mutation is forbidden
    so a future warning code cannot opt itself into suppression by side
    effect at import time.
    """
    assert isinstance(SUPPRESSIBLE_NORMALIZATION_CODES, frozenset)


# ---------------------------------------------------------------------------
# Helper signature: accepts warning_code
# ---------------------------------------------------------------------------


def test_helper_accepts_explicit_w002_code_and_suppresses_empty() -> None:
    """Explicit W002 + normalization-shaped + empty `normalized` -> True."""
    record = {"type": "normalization", "original": '"""', "normalized": ""}
    assert is_destructive_normalization_repair(record, warning_code="W002") is True


def test_helper_default_warning_code_is_w002_for_backwards_compat() -> None:
    """Existing call sites that pass no code MUST get the legacy
    W002-suppression behaviour (preserves PR #383's centralisation
    contract).
    """
    record = {"type": "normalization", "original": '"""', "normalized": ""}
    assert is_destructive_normalization_repair(record) is True


# ---------------------------------------------------------------------------
# Non-W002 normalization warning passes through
# ---------------------------------------------------------------------------


def test_helper_does_not_suppress_non_w002_normalization_with_empty_value() -> None:
    """A future W003+ normalization warning with the same record shape and
    an empty ``normalized`` value MUST NOT be silently suppressed by the
    W002 guard. The helper returns False so the caller can apply its own
    policy.

    This is the GH-386 acceptance criterion.
    """
    record = {"type": "normalization", "original": "x", "normalized": ""}
    assert is_destructive_normalization_repair(record, warning_code="W003") is False


def test_helper_does_not_suppress_unknown_code_with_normalized_shape() -> None:
    """Any warning code outside the suppression-eligible set passes
    through, regardless of shape."""
    record = {"original": "x", "normalized": "", "line": 1, "column": 1}
    assert is_destructive_normalization_repair(record, warning_code="W_FUTURE") is False


def test_helper_passes_non_w002_through_even_for_non_empty_record() -> None:
    """Sanity: non-W002 + well-formed record -> False (no suppression)."""
    record = {"type": "normalization", "original": "x", "normalized": "y"}
    assert is_destructive_normalization_repair(record, warning_code="W003") is False


# ---------------------------------------------------------------------------
# Existing W002 behaviour is preserved
# ---------------------------------------------------------------------------


def test_w002_still_suppresses_empty_normalized_key_only_shape() -> None:
    """A record carrying ``normalized`` (no ``type``) is normalization-
    shaped via the second discriminant; the W002 guard still applies."""
    record: dict[str, Any] = {"original": "->", "normalized": "", "line": 1, "column": 1}
    assert is_destructive_normalization_repair(record, warning_code="W002") is True


def test_w002_does_not_suppress_well_formed_record() -> None:
    """Well-formed records with non-empty ``normalized`` are not
    destructive even under W002."""
    record = {"original": "->", "normalized": "→", "line": 1, "column": 1}
    assert is_destructive_normalization_repair(record, warning_code="W002") is False
