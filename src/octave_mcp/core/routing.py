"""OCTAVE target routing (Issue #103).

Implements audit trail for target routing as defined in the design decision:
1. RoutingEntry dataclass captures route operations
2. RoutingLog collects entries during validation
3. I4 compliant: every route operation logged

Target Routing Syntax:
    KEY::["example"^CONSTRAINT->TARGET]
                                ^^^^^^
                                target

This module provides:
- RoutingEntry: Dataclass representing a single route operation
- RoutingLog: Collection of routing entries for audit trail
"""

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class RoutingEntry:
    """Single routing entry for audit trail (I4 compliance).

    Records a target routing operation during validation.

    Attributes:
        source_path: Full path to the source field (e.g., "CONFIG.STATUS")
        target_name: Target destination name (without section marker)
        value_hash: SHA-256 hash of the routed value
        constraint_passed: Whether constraint validation passed
        timestamp: ISO8601 timestamp of the routing operation
    """

    source_path: str
    target_name: str
    value_hash: str
    constraint_passed: bool
    timestamp: str


@dataclass
class RoutingLog:
    """Collection of routing entries for audit trail.

    Provides methods to add entries and serialize for MCP output.
    """

    entries: list[RoutingEntry] = field(default_factory=list)

    def add(
        self,
        source_path: str,
        target_name: str,
        value_hash: str,
        constraint_passed: bool,
    ) -> None:
        """Add a routing entry with auto-generated timestamp.

        Args:
            source_path: Full path to the source field
            target_name: Target destination name
            value_hash: SHA-256 hash of the value
            constraint_passed: Whether constraint validation passed
        """
        timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        self.entries.append(
            RoutingEntry(
                source_path=source_path,
                target_name=target_name,
                value_hash=value_hash,
                constraint_passed=constraint_passed,
                timestamp=timestamp,
            )
        )

    def has_routes(self) -> bool:
        """Check if any routes were logged."""
        return len(self.entries) > 0

    def to_dict(self) -> list[dict]:
        """Serialize routing log for JSON output.

        Returns:
            List of routing entry dictionaries
        """
        return [
            {
                "source_path": entry.source_path,
                "target_name": entry.target_name,
                "value_hash": entry.value_hash,
                "constraint_passed": entry.constraint_passed,
                "timestamp": entry.timestamp,
            }
            for entry in self.entries
        ]


def compute_value_hash(value) -> str:
    """Compute SHA-256 hash of a value.

    Args:
        value: Value to hash (will be converted to string)

    Returns:
        Hexadecimal SHA-256 hash string
    """
    return hashlib.sha256(str(value).encode()).hexdigest()
