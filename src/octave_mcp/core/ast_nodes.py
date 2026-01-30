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
    """Base class for all AST nodes.

    Issue #182: Comment preservation support.
    All AST nodes can have attached comments:
    - leading_comments: Comment lines appearing before this node
    - trailing_comment: End-of-line comment after this node's value
    """

    line: int = 0
    column: int = 0
    leading_comments: list[str] = field(default_factory=list)
    trailing_comment: str | None = None


@dataclass
class Assignment(ASTNode):
    """KEY::value assignment."""

    key: str = ""
    value: Any = None


@dataclass
class Block(ASTNode):
    """KEY: with nested children.

    Issue #189: Block inheritance support.
    Blocks can have a target annotation: BLOCK[->TARGET]:
    Children inherit this target unless they specify their own.

    Attributes:
        key: Block key name
        children: Nested AST nodes
        target: Optional target for block-level routing inheritance.
                Syntax: BLOCK[->TARGET]: sets target="TARGET".
                Children without explicit targets inherit from parent blocks.
    """

    key: str = ""
    children: list[ASTNode] = field(default_factory=list)
    target: str | None = None


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
    """Top-level OCTAVE document with envelope.

    Attributes:
        name: Document envelope name (e.g., "MY_DOC" from ===MY_DOC===)
        meta: Parsed META block as dictionary
        sections: List of parsed sections (Assignment, Block, Section)
        has_separator: True if document contains --- separator
        raw_frontmatter: YAML frontmatter content if present (Issue #91)
        grammar_version: OCTAVE grammar version from sentinel (Issue #48 Phase 2)
            Format: OCTAVE::VERSION at document start, e.g., "OCTAVE::5.1.0"
            When present, enables forward compatibility detection and migration routing.
        trailing_comments: Comment lines appearing before ===END=== (Issue #182)
            These are comments that don't have a subsequent section to attach to.
    """

    name: str = "INFERRED"
    meta: dict[str, Any] = field(default_factory=dict)
    sections: list[ASTNode] = field(default_factory=list)
    has_separator: bool = False
    raw_frontmatter: str | None = None
    trailing_comments: list[str] = field(default_factory=list)
    grammar_version: str | None = None


@dataclass
class Comment(ASTNode):
    """Comment node."""

    text: str = ""


@dataclass
class ListValue:
    """List value [a, b, c].

    Attributes:
        items: Parsed list item values
        tokens: Optional token slice for token-witnessed reconstruction (ADR-0012).
                When present, enables correct reconstruction of holographic patterns
                containing quoted operator symbols (e.g., ["∧"∧REQ→§SELF]).
                The token list preserves type metadata lost during value extraction.
    """

    items: list[Any] = field(default_factory=list)
    tokens: list[Any] | None = None  # Gap_2: Token slice for fidelity reconstruction


@dataclass
class InlineMap:
    """Inline map [k::v, k2::v2] (data mode only)."""

    pairs: dict[str, Any] = field(default_factory=dict)


@dataclass
class HolographicValue:
    """Holographic pattern value ["example"∧CONSTRAINT→§TARGET].

    Represents a schema field definition in L4 holographic syntax.
    This AST node is produced when the parser detects holographic operators
    (∧ constraint chain, →§ target) within a bracketed expression.

    Issue #187: Integrates holographic pattern parsing into parser L4 context.

    Attributes:
        example: The example value demonstrating expected format.
        constraints: Parsed ConstraintChain for validation, or None if no constraints.
        target: Target destination (without § prefix), or None if no target.
        raw_pattern: Original pattern string for I1 syntactic fidelity.
        tokens: Optional token slice for token-witnessed reconstruction (ADR-0012).
    """

    example: Any
    constraints: Any  # ConstraintChain | None - Any to avoid circular import
    target: str | None
    raw_pattern: str = ""
    tokens: list[Any] | None = None
