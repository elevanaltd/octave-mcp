"""Defensive guards against malformed normalization repairs (cubic P2
follow-up to PR #383).

The shared ``is_destructive_normalization_repair`` helper in
``octave_mcp.core.repair_log`` deliberately narrows to records that are
*normalization-shaped*: either ``type == "normalization"`` or carrying a
``normalized`` key. A malformed record that lacks BOTH discriminants
slips past the helper (returns False) and — without an inline guard at
the call sites — would emit a W002 correction with ``after = ""``,
violating HARD_SYMMETRY (ADR-0006 / I1 / I3).

These tests exercise the two ``WriteTool`` boundary methods that map
warnings/repairs onto W002 corrections, asserting that malformed and
empty-normalised inputs never produce a correction with empty ``after``.

The tests target the boundary methods directly rather than going through
the full ``WriteTool.execute`` pipeline so the malformed input is
authentic — i.e. constructed by the test, not laundered through the
lexer (which would never emit such a record in practice).
"""

from __future__ import annotations

from typing import Any

from octave_mcp.core.repair_log import is_destructive_normalization_repair
from octave_mcp.mcp.write import WriteTool

# ---------------------------------------------------------------------------
# Helper-level: confirm the discriminant's narrow semantics.
# ---------------------------------------------------------------------------


def test_helper_returns_false_for_record_lacking_both_discriminants() -> None:
    """A record with neither type=="normalization" nor a `normalized` key
    is NOT normalization-shaped, so the helper returns False.

    This is the narrow-semantics contract the helper preserves; the
    inline guards at the call sites are what suppress the resulting
    malformed emit.
    """
    malformed: dict[str, Any] = {"original": "->", "line": 1, "column": 1}
    assert is_destructive_normalization_repair(malformed, warning_code="W002") is False


def test_helper_returns_true_for_normalization_typed_with_empty_normalized() -> None:
    """type=="normalization" is normalization-shaped; empty `normalized`
    is destructive."""
    record = {"type": "normalization", "original": '"""', "normalized": ""}
    assert is_destructive_normalization_repair(record, warning_code="W002") is True


def test_helper_returns_true_for_repair_with_empty_normalized_field() -> None:
    """A record carrying a `normalized` key (but no `type`) is
    normalization-shaped via the second discriminant; empty value is
    destructive."""
    record = {"original": "->", "normalized": "", "line": 1, "column": 1}
    assert is_destructive_normalization_repair(record, warning_code="W002") is True


def test_helper_returns_false_for_well_formed_repair() -> None:
    """Well-formed records with non-empty `normalized` are not
    destructive."""
    record = {"original": "->", "normalized": "→", "line": 1, "column": 1}
    assert is_destructive_normalization_repair(record, warning_code="W002") is False


# ---------------------------------------------------------------------------
# Call-site: _track_corrections (write.py)
# ---------------------------------------------------------------------------


class TestTrackCorrectionsMalformedRepair:
    """The malformed-record edge case Cubic flagged: a token_repair dict
    lacking both `type=="normalization"` and `normalized` discriminants
    slips past the helper. The inline `or not normalized_value` guard
    must suppress the resulting empty-`after` W002.
    """

    def test_malformed_repair_lacking_both_discriminants_emits_no_w002(self) -> None:
        tool = WriteTool()
        # Lacks `type` AND `normalized` — neither discriminant present.
        malformed: list[dict[str, Any]] = [{"original": "->", "line": 1, "column": 1}]

        corrections = tool._track_corrections("", "", malformed)

        assert corrections == [], (
            f"Malformed token_repair lacking both discriminants must NOT "
            f"emit a W002 correction (would have empty `after`, violating "
            f"HARD_SYMMETRY / I3). Got: {corrections!r}"
        )

    def test_repair_with_empty_normalized_field_emits_no_w002(self) -> None:
        tool = WriteTool()
        repair_with_empty_normalized: list[dict[str, Any]] = [
            {"original": '"""', "normalized": "", "line": 1, "column": 1}
        ]

        corrections = tool._track_corrections("", "", repair_with_empty_normalized)

        assert corrections == [], (
            f"Repair with explicit empty `normalized` must NOT emit a W002. " f"Got: {corrections!r}"
        )

    def test_well_formed_repair_emits_w002_with_non_empty_after(self) -> None:
        """Sanity check: well-formed input still produces the expected
        W002 correction. The defensive guard only suppresses the
        destructive cases."""
        tool = WriteTool()
        well_formed: list[dict[str, Any]] = [{"original": "->", "normalized": "→", "line": 1, "column": 1}]

        corrections = tool._track_corrections("", "", well_formed)

        assert len(corrections) == 1
        c = corrections[0]
        assert c["code"] == "W002"
        assert c["before"] == "->"
        assert c["after"] == "→"


# ---------------------------------------------------------------------------
# Call-site: _map_parse_warnings_to_corrections (write.py)
# ---------------------------------------------------------------------------


class TestMapParseWarningsMalformedNormalization:
    """Symmetric coverage at the warnings-mapping site: a warning
    dispatched into the `type=="normalization"` branch but lacking the
    `normalized` key would slip past the helper (the helper IS True for
    this case via the type discriminant — but value is missing not
    empty; the inline guard catches the malformed missing-key variant
    too via `not normalized_value`).
    """

    def test_normalization_warning_missing_normalized_key_emits_no_w002(self) -> None:
        tool = WriteTool()
        # `type==normalization` but no `normalized` key at all.
        warnings: list[dict[str, Any]] = [{"type": "normalization", "original": "->", "line": 1, "column": 1}]

        corrections = tool._map_parse_warnings_to_corrections(warnings)

        w002s = [c for c in corrections if c.get("code") == "W002"]
        assert w002s == [], (
            f"normalization-typed warning missing `normalized` key must NOT "
            f"emit a W002 (would have empty `after`). Got: {w002s!r}"
        )

    def test_normalization_warning_empty_normalized_emits_no_w002(self) -> None:
        tool = WriteTool()
        warnings: list[dict[str, Any]] = [
            {
                "type": "normalization",
                "original": '"""',
                "normalized": "",
                "line": 1,
                "column": 1,
            }
        ]

        corrections = tool._map_parse_warnings_to_corrections(warnings)

        w002s = [c for c in corrections if c.get("code") == "W002"]
        assert w002s == [], (
            f"normalization-typed warning with empty `normalized` must NOT " f"emit a W002. Got: {w002s!r}"
        )

    def test_well_formed_normalization_warning_emits_w002(self) -> None:
        """Sanity check at this call site too."""
        tool = WriteTool()
        warnings: list[dict[str, Any]] = [
            {
                "type": "normalization",
                "original": "->",
                "normalized": "→",
                "line": 1,
                "column": 1,
            }
        ]

        corrections = tool._map_parse_warnings_to_corrections(warnings)

        w002s = [c for c in corrections if c.get("code") == "W002"]
        assert len(w002s) == 1
        assert w002s[0]["before"] == "->"
        assert w002s[0]["after"] == "→"
