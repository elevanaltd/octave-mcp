"""CST visitor protocol (ADR-0006 SR1-T1 Step 4 — scaffold).

This module is the minimum viable visitor surface that logical-Step 5
(emitter rewrite) consumes. Per design §2.2 the visitor file provides:

* ``Visitor[T]`` — a generic ``typing.Protocol`` declaring the four core
  visit methods (``visit_section``, ``visit_block``, ``visit_assignment``,
  ``visit_document``) plus a fallback ``visit`` dispatcher.
* ``SymmetricVisitor[T]`` — a mixin that asserts emit-after-parse
  round-trip in debug builds (``__debug__`` gated). The assertion hook
  is exposed as ``assert_round_trip`` so Step 5's emitter rewrite can
  wire its parse-after-emit symmetry check without re-touching this
  file.

Per design §3a the visitor signatures land **once** at Step 4. The
reserved fidelity fields on ``cst.ASTNode`` mean Step 5 / Sprint 3+ can
populate ``was_quoted`` / trivia without changing any visit-method
signature here. See design §4.5.

See ``docs/adr/adr-0006-sr1-t1-grammar-core-design.md`` §2.2, §4.5.
"""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Generic,
    Protocol,
    TypeVar,
    runtime_checkable,
)

if TYPE_CHECKING:
    from octave_mcp.core.grammar.cst import (
        Assignment,
        ASTNode,
        Block,
        Document,
        Section,
    )


T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)


@runtime_checkable
class Visitor(Protocol[T_co]):
    """Generic visitor protocol over CST nodes.

    A ``Visitor[T]`` consumes a CST and produces a value of type ``T``
    for each node visited. The four ``visit_*`` methods cover the
    concrete ``ASTNode`` subclasses; the fallback ``visit`` dispatcher
    is the entry point callers use when they have an unknown-kind node.

    Implementations may dispatch on ``node.kind`` (a ``NodeKind`` enum)
    to avoid ``isinstance`` chains. Step 5's emitter is the first
    consumer; the surface is intentionally minimal so it lands once and
    Step 5 does not have to re-touch this file.

    NOTE: This is a ``runtime_checkable`` Protocol so ``isinstance(obj,
    Visitor)`` works for structural typing checks in tests. The runtime
    check verifies method presence only; mypy strict performs the full
    structural type check at static analysis time.
    """

    def visit_assignment(self, node: Assignment, /) -> T_co:
        """Visit an Assignment node."""
        ...

    def visit_block(self, node: Block, /) -> T_co:
        """Visit a Block node."""
        ...

    def visit_section(self, node: Section, /) -> T_co:
        """Visit a Section node."""
        ...

    def visit_document(self, node: Document, /) -> T_co:
        """Visit a Document node."""
        ...

    def visit(self, node: ASTNode, /) -> T_co:
        """Fallback dispatcher for unknown-kind nodes.

        Implementations typically dispatch on ``node.kind`` to one of
        the typed ``visit_*`` methods above.
        """
        ...


class SymmetricVisitor(Generic[T]):
    """Mixin that asserts emit-after-parse round-trip in debug builds.

    This is the Step-4 scaffold. Logical-Step 5 (emitter rewrite) is the
    first real consumer; it will call ``self.assert_round_trip(...)``
    from inside its emit pipeline whenever it has both the source bytes
    and the freshly-emitted bytes available.

    The assertion is **debug-gated**: when Python is run with the ``-O``
    flag (``__debug__ == False``), the check short-circuits to a no-op
    so production callers pay no overhead. This is consistent with
    Python's ``assert`` semantics and ensures the symmetry check is a
    development-time invariant, not a runtime cost.

    The mixin is deliberately minimal. Future steps (notably the
    Sprint 3+ cursor-CST) will populate ``leading_trivia`` /
    ``trailing_trivia`` and may extend this hook with byte-precise diff
    reporting. For now, the contract is: ``source == emitted`` (when
    both are provided) → no-op; mismatch → ``AssertionError`` in
    ``__debug__`` mode, no-op otherwise.
    """

    def assert_round_trip(
        self,
        node: ASTNode,
        /,
        *,
        source: str | None = None,
        emitted: str | None = None,
    ) -> None:
        """Assert emit(parse(source)) == source.

        Called from inside the emitter visitor (Step 5) once both the
        original source bytes and the canonical emitted bytes are
        available. In ``__debug__`` mode (the default), a mismatch
        raises ``AssertionError`` with a short diagnostic. In ``-O``
        mode the call is a no-op — Step 5 may invoke this on every
        emit without paying overhead in production.

        Args:
            node: The root CST node that was emitted. Currently unused
                by the assertion logic; reserved for Step 5 / Sprint 3+
                to attach precise diff reporting.
            source: The original source bytes (or ``None`` if not
                available, e.g. when emitting from a constructed CST
                that did not originate from parsed bytes).
            emitted: The freshly-emitted bytes (or ``None`` if not
                available).

        Note:
            When either ``source`` or ``emitted`` is ``None``, the
            assertion is skipped — the check is only meaningful when
            both halves of the round trip are present.
        """
        if not __debug__:
            return
        if source is None or emitted is None:
            return
        if source != emitted:
            raise AssertionError(
                "SymmetricVisitor round-trip mismatch: "
                f"len(source)={len(source)} len(emitted)={len(emitted)} "
                f"node.kind={getattr(node, 'kind', None)!r}. "
                "Emit-after-parse must be byte-identical in debug builds."
            )


__all__ = [
    "SymmetricVisitor",
    "Visitor",
]
