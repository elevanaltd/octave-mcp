"""AST node definitions for OCTAVE parser.

Implements data structures for the abstract syntax tree.
"""

from dataclasses import dataclass, field
from typing import Any


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
    warnings: list[dict[str, Any]] = field(default_factory=list)  # Issue #64: parser warnings


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
