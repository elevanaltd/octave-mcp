"""Repair log structures (P1.6)."""

from dataclasses import dataclass
from enum import Enum
from typing import Any

# GH-386 (ADR-0006 SR1, CE follow-up to PR #383): the destructive-empty-
# normalization guard now keys on warning code AND shape, not on shape
# alone. Suppression is restricted to this closed set so a future W003+
# normalization warning that legitimately reuses the (original, normalized)
# shape with an empty `normalized` value cannot be silently suppressed by
# the W002 guard.
#
# To opt a new code into suppression, add it here AND add a discriminator
# test in tests/unit/test_w002_discriminant_tagging.py asserting the
# desired empty-handling semantics. The set is frozen so it cannot be
# mutated by side effect at import time.
SUPPRESSIBLE_NORMALIZATION_CODES: frozenset[str] = frozenset({"W002"})


def is_destructive_normalization_repair(
    repair: dict[str, Any],
    *,
    warning_code: str = "W002",
) -> bool:
    """Return True iff `repair` is a destructive normalization record for
    the given warning code.

    ADR-0006 SR0-T2 (GH#381): a normalization repair with an empty
    `normalized` value would render downstream as a W002 correction with
    `after=""` — claiming a normalisation while supplying no replacement.
    That fabricates a deletion not present in source intent, violating
    I1 (SYNTACTIC_FIDELITY) and I3 (MIRROR_CONSTRAINT), and breaks the
    HARD_SYMMETRY invariant by emitting a correction the rendered diff
    cannot reflect.

    GH-386 (SR1 CE follow-up): the helper now requires the caller to
    declare which warning code it is guarding. Suppression returns True
    only when ALL of:
      1. ``warning_code`` is in ``SUPPRESSIBLE_NORMALIZATION_CODES``
         (today: ``{"W002"}``), AND
      2. the record is *normalization-shaped*, AND
      3. the ``normalized`` value is missing or empty.

    A future W003+ normalization warning that wants different empty-
    handling MUST NOT be silently suppressed by this guard; the helper
    returns False for any non-enumerated code, leaving the policy to the
    call site.

    A record is "normalization-shaped" if either:
      * ``type == "normalization"`` (lexer/parser warning shape), or
      * the record carries a ``normalized`` field (tokenize_repair shape
        used by `_track_corrections`, which has no `type` discriminator).

    The helper centralises the discriminant so all three SR0-T2 guard
    sites (core/lexer.py emit, mcp/write.py:_map_parse_warnings_to_corrections,
    mcp/write.py:_track_corrections) share one definition and cannot drift.

    Scope is intentionally narrow: it does NOT classify other warning
    codes (e.g. W_UNQUOTED_SECTION_IN_VALUE uses original/repaired and
    is out of scope).

    Args:
        repair: A repair / warning candidate dict.
        warning_code: The warning code the caller is guarding. Defaults
            to ``"W002"`` for backwards-compatibility with existing call
            sites. Pass an explicit code at every call site for clarity
            and to make future-code policy decisions self-documenting.

    Returns:
        True iff the record is a destructive (empty-normalised)
        normalization repair under the given warning code that callers
        must suppress; False otherwise (including for any warning code
        outside ``SUPPRESSIBLE_NORMALIZATION_CODES``).
    """
    if warning_code not in SUPPRESSIBLE_NORMALIZATION_CODES:
        return False
    is_normalization_shaped = repair.get("type") == "normalization" or "normalized" in repair
    if not is_normalization_shaped:
        return False
    normalized = repair.get("normalized")
    return not normalized


class RepairTier(Enum):
    """Repair classification tiers."""

    NORMALIZATION = "NORMALIZATION"  # Always applied
    REPAIR = "REPAIR"  # Only when fix=true
    FORBIDDEN = "FORBIDDEN"  # Never automatic


@dataclass
class RepairEntry:
    """Single repair log entry."""

    rule_id: str
    before: str
    after: str
    tier: RepairTier
    safe: bool
    semantics_changed: bool

    def to_dict(self) -> dict[str, str | bool]:
        """Convert to JSON-serializable dictionary.

        The tier field is converted from Enum to its string value
        for proper JSON serialization in MCP responses.

        Returns:
            Dictionary with all fields, tier as string value.
        """
        return {
            "rule_id": self.rule_id,
            "before": self.before,
            "after": self.after,
            "tier": self.tier.value,  # Convert Enum to string
            "safe": self.safe,
            "semantics_changed": self.semantics_changed,
        }


@dataclass
class RepairLog:
    """Complete repair log."""

    repairs: list[RepairEntry]

    def add(
        self,
        rule_id: str,
        before: str,
        after: str,
        tier: RepairTier,
        safe: bool = True,
        semantics_changed: bool = False,
    ) -> None:
        """Add a repair entry."""
        self.repairs.append(RepairEntry(rule_id, before, after, tier, safe, semantics_changed))

    def has_repairs(self) -> bool:
        """Check if any repairs were made."""
        return len(self.repairs) > 0


# --- Issue #235: Literal Zone Audit Receipts (I4) ---


@dataclass
class RepairLogEntry:
    """Per-zone audit receipt for I4 transform auditability.

    Issue #235: Every literal zone produces a receipt proving its content
    was preserved through the repair/normalization pipeline.

    Attributes:
        zone_key: The OCTAVE key path (e.g., "DOC.CODE", "DOC.SECTION.CONFIG").
        line: Line number of the opening fence in the source document.
        action: One of "preserved" or "stripped".
        pre_hash: SHA-256 hex digest of the literal zone content BEFORE pipeline.
        post_hash: SHA-256 hex digest of the literal zone content AFTER pipeline.
        timestamp: ISO 8601 timestamp of when the receipt was generated.
        source_stage: Pipeline stage that produced this receipt.
    """

    zone_key: str
    line: int
    action: str  # "preserved" | "stripped"
    pre_hash: str
    post_hash: str
    timestamp: str
    source_stage: str


@dataclass
class LiteralZoneRepairLog:
    """Aggregated audit log for all literal zones in a document.

    Included in MCP tool responses when literal zones are present.
    Satisfies I4 (Transform Auditability) for literal zone content.
    """

    entries: list[RepairLogEntry]

    @property
    def all_preserved(self) -> bool:
        """True if every literal zone was preserved unchanged."""
        return all(e.action == "preserved" and e.pre_hash == e.post_hash for e in self.entries)

    def to_dict(self) -> list[dict[str, str | int]]:
        """Serialize for inclusion in MCP tool response."""
        return [
            {
                "zone_key": e.zone_key,
                "line": e.line,
                "action": e.action,
                "pre_hash": e.pre_hash,
                "post_hash": e.post_hash,
                "timestamp": e.timestamp,
                "source_stage": e.source_stage,
            }
            for e in self.entries
        ]
