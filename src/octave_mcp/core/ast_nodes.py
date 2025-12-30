"""AST node definitions for OCTAVE parser.

Implements data structures for the abstract syntax tree.

I2 (Deterministic Absence) Support:
The Absent sentinel type distinguishes between:
- Absent: Field not provided (should NOT be emitted)
- None: Field explicitly set to null (`KEY::null`)
- Value: Field has an actual value
"""

from dataclasses import dataclass, field
from typing import Any


class Absent:
    """Sentinel type for I2: Deterministic Absence.

    Represents a field that was not provided, distinct from:
    - None (Python): explicitly set to null (`KEY::null`)
    - Default: schema-provided default value

    Per North Star I2: "Absence shall propagate as addressable state,
    never silently collapse to null or default."

    Usage:
        # Creating an absent value
        absent_val = Absent()

        # Checking if a value is absent
        if isinstance(value, Absent):
            # Field was not provided
            pass

        # Absent is falsy but not None
        assert not absent_val
        assert absent_val is not None
    """

    _instance: "Absent | None" = None

    def __new__(cls) -> "Absent":
        """Create or return singleton instance for efficiency."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __bool__(self) -> bool:
        """Absent is falsy, like None."""
        return False

    def __repr__(self) -> str:
        """Clear representation for debugging."""
        return "Absent()"

    def __eq__(self, other: object) -> bool:
        """Absent only equals itself, not None."""
        return isinstance(other, Absent)

    def __hash__(self) -> int:
        """Allow Absent to be used in sets/dicts."""
        return hash("Absent")


# Module-level singleton for convenience
ABSENT = Absent()


@dataclass
class ASTNode:
    """Base class for all AST nodes."""

    line: int = 0
    column: int = 0


@dataclass
class Assignment(ASTNode):
    """KEY::value assignment."""

    key: str = ""
    value: Any = None


@dataclass
class Block(ASTNode):
    """KEY: with nested children."""

    key: str = ""
    children: list[ASTNode] = field(default_factory=list)


@dataclass
class Section(ASTNode):
    """§NUMBER::NAME section with nested children.

    section_id supports both plain numbers ("1", "2") and suffix forms ("2b", "2c").
    annotation is the optional bracket tail [content] after section name.
    """

    section_id: str = "0"
    key: str = ""
    annotation: str | None = None
    children: list[ASTNode] = field(default_factory=list)


@dataclass
class Document(ASTNode):
    """Top-level OCTAVE document with envelope."""

    name: str = "INFERRED"
    meta: dict[str, Any] = field(default_factory=dict)
    sections: list[ASTNode] = field(default_factory=list)
    has_separator: bool = False


@dataclass
class Comment(ASTNode):
    """Comment node."""

    text: str = ""


@dataclass
class ListValue:
    """List value [a, b, c]."""

    items: list[Any] = field(default_factory=list)


@dataclass
class InlineMap:
    """Inline map [k::v, k2::v2] (data mode only)."""

    pairs: dict[str, Any] = field(default_factory=dict)
