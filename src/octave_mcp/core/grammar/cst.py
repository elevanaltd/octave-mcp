"""Concrete Syntax Tree (CST) node definitions (ADR-0006 SR1-T1 Step 4).

This module is the promotion of ``octave_mcp.core.ast_nodes`` to the
unified grammar package per ADR-0006 §2.2 and §3 row 4. The promotion
adds three pieces of structural surface without altering the runtime
semantics of the existing dataclasses:

1. ``NodeKind`` enum — one variant per concrete ``ASTNode`` subclass.
   Provides a stable discriminator for visitor dispatch and audit-log
   keying (I4 TRANSFORM_AUDITABILITY). Each node class auto-populates
   ``self.kind`` from its subclass declaration via a ``__post_init__``
   hook so callers do not need to pass ``kind`` explicitly — the ~30
   existing ``Section(...)`` / ``Block(...)`` / ``Assignment(...)`` /
   ``Document(...)`` call sites continue to work unchanged.

2. Reserved fidelity-preservation fields on the base ``ASTNode``
   defaulted to ``None`` (per design §4.5 G1+G2):

   * ``leading_trivia: Optional[str]`` — leading whitespace/blank-lines.
     Populated by Sprint 3+ (SR3-T1 cursor-CST). Enables precise
     blank-line-stripping audit per design §3a class 2.
   * ``trailing_trivia: Optional[str]`` — trailing whitespace. Same
     population timeline as ``leading_trivia``.
   * ``was_quoted: Optional[bool]`` — did the user write the value with
     explicit quotes (e.g. ``KEY::"42"``)? Populated by logical-Step 5
     (next task) via lexer/parser instrumentation. Enables precise
     identifier-dequoting audit per design §3a class 1 and §4.5 G2.

   These three fields are **reserved, not populated** in this PR — they
   exist purely to lock the schema shape so that the later population
   PRs do not need to re-touch every node class and every visitor
   signature. No code in this PR reads or writes them.

3. PEP 562 deprecation shim at the legacy path
   ``octave_mcp.core.ast_nodes`` (see that module). Symbol identity is
   preserved across both paths: ``ast_nodes.Section is grammar.cst.Section``.

The Absent sentinel and value types (ListValue, InlineMap, HolographicValue,
LiteralZoneValue) are re-exported unchanged — they are not ``ASTNode``
subclasses so they do not carry a ``kind``.

See ``docs/adr/adr-0006-sr1-t1-grammar-core-design.md`` §2.2, §3 row 4,
§3a, §4.5 G1+G2.

I2 (Deterministic Absence) Support
----------------------------------

The ``Absent`` sentinel type distinguishes between:

* ``Absent``: Field not provided (should NOT be emitted)
* ``None``: Field explicitly set to null (``KEY::null``)
* Value: Field has an actual value
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class NodeKind(Enum):
    """Structural discriminator for CST nodes.

    One variant per concrete ``ASTNode`` subclass. Used by visitors to
    dispatch on node shape without relying on ``isinstance`` chains, and
    by the future ``tier_normalize`` audit log to key entries by node
    shape (I4 TRANSFORM_AUDITABILITY).

    NOTE: This is a *structural* marker only. Presentation-aware
    decisions (e.g. "was this value originally quoted?") live on the
    node's ``was_quoted`` field, not on ``NodeKind``. See design §4.5 G2.
    """

    ASSIGNMENT = "ASSIGNMENT"
    BLOCK = "BLOCK"
    SECTION = "SECTION"
    DOCUMENT = "DOCUMENT"
    COMMENT = "COMMENT"


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

    _instance: Absent | None = None

    def __new__(cls) -> Absent:
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

    ADR-0006 SR1-T1 Step 4 reserved fidelity-preservation fields (NOT
    populated in this PR — see module docstring):
    - leading_trivia: Whitespace/blank-line prefix (Sprint 3+).
    - trailing_trivia: Whitespace suffix (Sprint 3+).
    - was_quoted: Original quoting state of the value (logical-Step 5).

    ADR-0006 SR1-T1 Step 4 also added ``kind: NodeKind`` as a structural
    discriminator. Concrete subclasses override the default via their own
    ``kind`` field declaration with ``init=False``.
    """

    line: int = 0
    column: int = 0
    leading_comments: list[str] = field(default_factory=list)
    trailing_comment: str | None = None
    # --- Reserved fidelity fields (ADR-0006 §4.5 G1+G2). Optional[None]; ---
    # --- DO NOT populate in this PR. Populated by Step 5 / Sprint 3+.   ---
    leading_trivia: str | None = None
    trailing_trivia: str | None = None
    was_quoted: bool | None = None
    # --- Structural discriminator (ADR-0006 §3 row 4). Subclasses     ---
    # --- override with their own NodeKind variant via init=False.     ---
    # The base ASTNode itself is abstract for kind purposes; the default
    # here is overridden by every concrete subclass. We use a placeholder
    # that should never be observed in well-formed CSTs.
    kind: NodeKind = field(default=NodeKind.DOCUMENT, init=False)


@dataclass
class Assignment(ASTNode):
    """KEY::value assignment."""

    key: str = ""
    value: Any = None
    kind: NodeKind = field(default=NodeKind.ASSIGNMENT, init=False)


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
    kind: NodeKind = field(default=NodeKind.BLOCK, init=False)


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
    kind: NodeKind = field(default=NodeKind.SECTION, init=False)


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
    kind: NodeKind = field(default=NodeKind.DOCUMENT, init=False)


@dataclass
class Comment(ASTNode):
    """Comment node."""

    text: str = ""
    kind: NodeKind = field(default=NodeKind.COMMENT, init=False)


@dataclass
class ListValue:
    """List value [a, b, c].

    NOT an ASTNode subclass — this is a value type. Does not carry a
    NodeKind discriminator.

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
    """Inline map [k::v, k2::v2] (data mode only).

    NOT an ASTNode subclass — value type. Does not carry a NodeKind.
    """

    pairs: dict[str, Any] = field(default_factory=dict)


@dataclass
class HolographicValue:
    """Holographic pattern value ["example"∧CONSTRAINT→§TARGET].

    Represents a schema field definition in L4 holographic syntax.
    This AST node is produced when the parser detects holographic operators
    (∧ constraint chain, →§ target) within a bracketed expression.

    Issue #187: Integrates holographic pattern parsing into parser L4 context.

    NOT an ASTNode subclass — value type. Does not carry a NodeKind.

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


@dataclass
class LiteralZoneValue:
    """Literal zone value (fenced code block).

    Issue #235: Represents content between fence markers (``` or longer).
    Content is preserved exactly as-is -- no NFC normalization, no escape
    processing, no operator normalization, no variable substitution.

    Follows the HolographicValue/ListValue precedent: value type (not
    ASTNode subclass). This ensures exhaustive pattern matching catches
    literal zones and prevents silent normalization through string paths.

    I1: Exempt from normalization (semantic intent is "preserve exactly").
    I2: Empty content ("") is distinct from absent (no LiteralZoneValue).
    I3: Nested fences MUST error at parse time, never reach this node.

    NOT an ASTNode subclass — value type. Does not carry a NodeKind.

    Attributes:
        content: Raw content between fences. Preserved byte-for-byte.
                 Empty string for empty literal zones (```\\n```).
        info_tag: Optional language identifier (e.g., "python", "json").
                  None when no info tag is provided.
                  Preserved but not validated by OCTAVE parser.
        fence_marker: The exact fence string used (e.g., "```", "````").
                      Needed for round-trip emission fidelity.
    """

    content: str = ""
    info_tag: str | None = None
    fence_marker: str = "```"


__all__ = [
    "ABSENT",
    "ASTNode",
    "Absent",
    "Assignment",
    "Block",
    "Comment",
    "Document",
    "HolographicValue",
    "InlineMap",
    "ListValue",
    "LiteralZoneValue",
    "NodeKind",
    "Section",
]
