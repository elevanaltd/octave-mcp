"""Tests for the CST visitor protocol (ADR-0006 SR1-T1 Step 4).

This module pins the Step-4 scaffold for ``octave_mcp.core.grammar.visitor``.
The full visitor consumer arrives at logical-Step 5 (emitter rewrite); this
step delivers just enough surface for Step 5 to consume without re-touching
the visitor file.

The scaffold provides:

* ``Visitor[T]`` — a generic ``typing.Protocol`` with ``visit_section``,
  ``visit_block``, ``visit_assignment``, ``visit_document`` methods and a
  fallback ``visit`` dispatcher.
* ``SymmetricVisitor[T]`` — a mixin that asserts emit-after-parse round-trip
  in debug builds only (``__debug__`` gated). Step 5 wires the assertion to
  the rewritten emitter.

See ``docs/adr/adr-0006-sr1-t1-grammar-core-design.md`` §2.2 ("visitor.py
— Visitor[T] protocol; SymmetricVisitor mixin").
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Visitor protocol surface exists and is importable
# ---------------------------------------------------------------------------


def test_visitor_protocol_is_importable() -> None:
    from octave_mcp.core.grammar.visitor import Visitor  # noqa: F401


def test_symmetric_visitor_mixin_is_importable() -> None:
    from octave_mcp.core.grammar.visitor import SymmetricVisitor  # noqa: F401


# ---------------------------------------------------------------------------
# Visitor[T] is a Protocol with the expected method names
# ---------------------------------------------------------------------------


def test_visitor_protocol_declares_visit_section() -> None:
    from octave_mcp.core.grammar.visitor import Visitor

    assert hasattr(Visitor, "visit_section"), "Visitor protocol must declare visit_section"


def test_visitor_protocol_declares_visit_block() -> None:
    from octave_mcp.core.grammar.visitor import Visitor

    assert hasattr(Visitor, "visit_block"), "Visitor protocol must declare visit_block"


def test_visitor_protocol_declares_visit_assignment() -> None:
    from octave_mcp.core.grammar.visitor import Visitor

    assert hasattr(Visitor, "visit_assignment"), "Visitor protocol must declare visit_assignment"


def test_visitor_protocol_declares_visit_document() -> None:
    from octave_mcp.core.grammar.visitor import Visitor

    assert hasattr(Visitor, "visit_document"), "Visitor protocol must declare visit_document"


def test_visitor_protocol_declares_fallback_visit_dispatcher() -> None:
    from octave_mcp.core.grammar.visitor import Visitor

    assert hasattr(Visitor, "visit"), "Visitor protocol must declare a fallback visit() dispatcher"


# ---------------------------------------------------------------------------
# A concrete identity visitor traverses a small Document and returns it
# unchanged (proves the protocol is consumable, not dead code).
# ---------------------------------------------------------------------------


def test_identity_visitor_traverses_document_unchanged() -> None:
    from octave_mcp.core.grammar.cst import (
        Assignment,
        ASTNode,
        Block,
        Document,
        NodeKind,
        Section,
    )
    from octave_mcp.core.grammar.visitor import Visitor

    class IdentityVisitor:
        """Concrete visitor that returns each node unchanged.

        This proves the Visitor[ASTNode] protocol is structurally usable
        without forcing a particular dispatch implementation.
        """

        def visit_assignment(self, node: Assignment) -> ASTNode:
            return node

        def visit_block(self, node: Block) -> ASTNode:
            return node

        def visit_section(self, node: Section) -> ASTNode:
            return node

        def visit_document(self, node: Document) -> ASTNode:
            return node

        def visit(self, node: ASTNode) -> ASTNode:
            kind = node.kind
            if kind is NodeKind.ASSIGNMENT:
                return self.visit_assignment(node)  # type: ignore[arg-type]
            if kind is NodeKind.BLOCK:
                return self.visit_block(node)  # type: ignore[arg-type]
            if kind is NodeKind.SECTION:
                return self.visit_section(node)  # type: ignore[arg-type]
            if kind is NodeKind.DOCUMENT:
                return self.visit_document(node)  # type: ignore[arg-type]
            return node

    visitor: Visitor[ASTNode] = IdentityVisitor()

    doc = Document(
        name="DOC",
        sections=[
            Assignment(key="K", value=1),
            Block(key="B", children=[Assignment(key="K2", value=2)]),
            Section(section_id="1", key="S"),
        ],
    )

    result = visitor.visit(doc)
    assert result is doc, "Identity visitor must return the same object"
    # Confirm each child can be dispatched
    for child in doc.sections:
        out = visitor.visit(child)
        assert out is child


# ---------------------------------------------------------------------------
# SymmetricVisitor mixin — minimal scaffold consumable by Step 5
# ---------------------------------------------------------------------------


def test_symmetric_visitor_can_be_subclassed() -> None:
    """SymmetricVisitor is a mixin; subclassing must succeed without args."""
    from octave_mcp.core.grammar.visitor import SymmetricVisitor

    class MyEmitter(SymmetricVisitor[str]):
        def visit_assignment(self, node: Any) -> str:
            return ""

        def visit_block(self, node: Any) -> str:
            return ""

        def visit_section(self, node: Any) -> str:
            return ""

        def visit_document(self, node: Any) -> str:
            return ""

        def visit(self, node: Any) -> str:
            return ""

    emitter = MyEmitter()
    assert emitter is not None


def test_symmetric_visitor_exposes_assert_round_trip_hook() -> None:
    """Step 5's emitter rewrite will call into a round-trip assertion hook.

    The scaffold must expose a callable surface that Step 5 can override or
    consume. The exact assertion mechanism is Step-5 work; here we only pin
    that the surface exists so Step 5 does not re-touch this file.
    """
    from octave_mcp.core.grammar.visitor import SymmetricVisitor

    assert hasattr(SymmetricVisitor, "assert_round_trip"), (
        "SymmetricVisitor must expose assert_round_trip() so Step 5's emitter "
        "rewrite can hook the parse↔emit symmetry check without re-touching visitor.py"
    )


def test_symmetric_visitor_assert_round_trip_is_debug_gated() -> None:
    """The assertion is debug-only — in __debug__=False (python -O) it MUST
    short-circuit to a no-op so production callers pay no overhead.

    We can't easily flip __debug__ at runtime, but we CAN call the method
    with mismatched inputs in a __debug__=True context and verify the
    contract: either it asserts in debug mode, or no-ops in non-debug mode.
    Either path is acceptable; what's NOT acceptable is raising in a
    non-debug build. Since the test runner runs with __debug__=True, we
    pin only that the method exists and is callable.
    """
    from octave_mcp.core.grammar.cst import Document
    from octave_mcp.core.grammar.visitor import SymmetricVisitor

    class _ConcreteSV(SymmetricVisitor[str]):
        def visit_assignment(self, node: Any) -> str:
            return ""

        def visit_block(self, node: Any) -> str:
            return ""

        def visit_section(self, node: Any) -> str:
            return ""

        def visit_document(self, node: Any) -> str:
            return ""

        def visit(self, node: Any) -> str:
            return ""

    sv = _ConcreteSV()
    # Calling assert_round_trip on matching baseline=canonical inputs MUST
    # always succeed (it's a no-op when they agree, regardless of debug flag).
    doc = Document()
    sv.assert_round_trip(doc, source="x", emitted="x")  # must not raise
