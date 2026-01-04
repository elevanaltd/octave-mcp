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
