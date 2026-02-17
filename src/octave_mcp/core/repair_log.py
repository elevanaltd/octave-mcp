"""Repair log structures (P1.6)."""

from dataclasses import dataclass
from enum import Enum


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
