"""OCTAVE target routing (Issue #103, Issue #188).

Implements audit trail and target routing system as defined in the spec:
1. RoutingEntry dataclass captures route operations
2. RoutingLog collects entries during validation
3. I4 compliant: every route operation logged

Issue #188: Target Routing System
4. Target dataclass representing a routing destination
5. TargetRegistry manages builtin + custom targets
6. TargetRouter handles routing logic with multi-target broadcast support

Target Routing Syntax:
    KEY::["example"^CONSTRAINT->TARGET]
                                ^^^^^^
                                target

Multi-target broadcast: "§A∨§B∨§C" routes to all targets

This module provides:
- Target: Dataclass representing a routing destination
- TargetRegistry: Manages builtin and custom targets
- TargetRouter: Routes values to targets with broadcast support
- RoutingEntry: Dataclass representing a single route operation
- RoutingLog: Collection of routing entries for audit trail
- InvalidTargetError: Raised when routing to unknown target
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


class InvalidTargetError(Exception):
    """Raised when routing to an unknown/invalid target.

    Spec §3::TARGETS VALIDATION::target_must_exist[declared_in_POLICY.TARGETS∨builtin]
    """

    def __init__(self, target_name: str, message: str | None = None):
        """Initialize with target name and optional message.

        Args:
            target_name: The invalid target name
            message: Optional custom error message
        """
        self.target_name = target_name
        self.message = (
            message or f"Invalid target: '{target_name}' is not a builtin, registered custom, or file path target"
        )
        super().__init__(self.message)


@dataclass(frozen=True)
class Target:
    """Represents a routing destination.

    Spec §3::TARGETS defines three types:
    - BUILTIN: §SELF, §META, §INDEXER, §DECISION_LOG, §RISK_LOG, §KNOWLEDGE_BASE
    - FILE: §./relative/path (resolved from document directory)
    - CUSTOM: Declared in POLICY.TARGETS

    Attributes:
        name: Target identifier (e.g., "INDEXER", "DECISION_LOG", "./output.oct")
        target_type: One of "builtin", "custom", "file"
        path: For file targets, the relative path; None for others
    """

    name: str
    target_type: str  # "builtin", "custom", "file"
    path: str | None = None


class TargetRegistry:
    """Registry for managing builtin and custom targets.

    Spec §3::TARGETS defines:
    - BUILTIN::[§SELF,§META,§INDEXER,§DECISION_LOG,§RISK_LOG,§KNOWLEDGE_BASE]
    - VALIDATION::target_must_exist[declared_in_POLICY.TARGETS∨builtin]
    """

    BUILTINS: frozenset[str] = frozenset(
        {
            "SELF",
            "META",
            "INDEXER",
            "DECISION_LOG",
            "RISK_LOG",
            "KNOWLEDGE_BASE",
        }
    )

    def __init__(self) -> None:
        """Initialize registry with empty custom targets."""
        self.custom_targets: set[str] = set()

    def is_builtin(self, name: str) -> bool:
        """Check if target is a builtin.

        Args:
            name: Target name (without § prefix)

        Returns:
            True if target is a builtin
        """
        return name in self.BUILTINS

    def register_custom(self, name: str) -> None:
        """Register a custom target from POLICY.TARGETS.

        Args:
            name: Custom target name to register
        """
        self.custom_targets.add(name)

    def is_valid(self, name: str) -> bool:
        """Check if target is valid (builtin, custom, or file path).

        Args:
            name: Target name to validate

        Returns:
            True if target is valid
        """
        # Builtin targets
        if name in self.BUILTINS:
            return True

        # Custom registered targets
        if name in self.custom_targets:
            return True

        # File path targets (start with ./)
        if name.startswith("./"):
            return True

        return False

    def resolve(self, name: str) -> Target | None:
        """Resolve target name to Target object.

        Args:
            name: Target name to resolve

        Returns:
            Target object if valid, None if unknown
        """
        if name in self.BUILTINS:
            return Target(name=name, target_type="builtin")

        if name in self.custom_targets:
            return Target(name=name, target_type="custom")

        if name.startswith("./"):
            return Target(name=name, target_type="file", path=name)

        return None


class TargetRouter:
    """Routes values to targets with multi-target broadcast support.

    Spec §3::TARGETS defines:
    - MULTI::"§A∨§B∨§C"[broadcast_to_all]
    - MULTI_FAILURE::non_transactional[partial_success_possible,handler_responsibility]
    """

    def __init__(self, registry: TargetRegistry, routing_log: RoutingLog) -> None:
        """Initialize router with registry and routing log.

        Args:
            registry: Target registry for validation
            routing_log: Log for recording routing entries
        """
        self.registry = registry
        self.log = routing_log

    def parse_target_spec(self, spec: str) -> list[str]:
        """Parse target specification, handling multi-target broadcast.

        Spec: MULTI::"§A∨§B∨§C"[broadcast_to_all]

        Args:
            spec: Target specification (e.g., "INDEXER" or "§A∨§B∨§C")

        Returns:
            List of target names (without § prefix)
        """
        # Split by unicode disjunction (∨) for multi-target
        targets = spec.split("∨")

        # Strip § section marker from each target
        return [t.lstrip("§").strip() for t in targets]

    def route(
        self,
        source_path: str,
        target_spec: str,
        value: Any,
        constraint_passed: bool,
    ) -> list[RoutingEntry]:
        """Route value to target(s) and log routing entries.

        Spec: MULTI_FAILURE::non_transactional[partial_success_possible,handler_responsibility]

        Args:
            source_path: Full path to source field (e.g., "CONFIG.STATUS")
            target_spec: Target specification (single or multi with ∨)
            value: Value being routed
            constraint_passed: Whether constraint validation passed

        Returns:
            List of routing entries created

        Raises:
            InvalidTargetError: If any target is invalid (after partial success for multi-target)
        """
        targets = self.parse_target_spec(target_spec)
        entries: list[RoutingEntry] = []
        value_hash = compute_value_hash(value)

        for target_name in targets:
            # Validate target
            if not self.registry.is_valid(target_name):
                raise InvalidTargetError(target_name)

            # Log routing entry (I4 compliance)
            self.log.add(
                source_path=source_path,
                target_name=target_name,
                value_hash=value_hash,
                constraint_passed=constraint_passed,
            )

            # Return the created entry
            entries.append(self.log.entries[-1])

        return entries


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
