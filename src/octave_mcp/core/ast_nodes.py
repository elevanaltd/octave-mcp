"""Deprecation shim for the legacy AST node module (ADR-0006 SR1-T1 Step 4).

History
-------

SR1-T1 Step 4 promotes the AST node definitions from this flat module to
``octave_mcp.core.grammar.cst``. The canonical module is the new path;
this module remains as a backwards-compatibility shim so external
consumers (PyPI users on v1.11.x or earlier) keep working through the
deprecation window.

All ~62 internal call sites were rewritten in the Step-4 PR to import
from ``octave_mcp.core.grammar.cst`` directly. By PR-merge there are
zero internal callers of this module, so the lazy ``__getattr__``
deprecation warning only fires for external consumers — which is
exactly the audience the warning is for.

This shim mirrors the Step-1 pattern at ``octave_mcp.core.grammar``
(PR #393): PEP 562 ``__getattr__`` for lazy resolution, single
``DeprecationWarning`` on attribute access, **identity-preserving**
re-export so ``ast_nodes.Section is grammar.cst.Section`` holds.

See ``docs/adr/adr-0006-sr1-t1-grammar-core-design.md`` §3 row 4, §2.2.
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any

# Names re-exported from grammar.cst for backward compatibility. Listed
# here rather than in __all__ so they remain reachable but are not
# advertised as part of the new front-door surface. Includes the Absent
# sentinel, all ASTNode subclasses, and the value types — i.e. every
# public name the legacy module previously exposed.
_DEPRECATED_AST_EXPORTS: frozenset[str] = frozenset(
    {
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
    }
)


def __getattr__(name: str) -> Any:
    """PEP 562 lazy resolver for legacy ``octave_mcp.core.ast_nodes`` symbols.

    Emits a :class:`DeprecationWarning` on each attribute access for any
    legacy AST symbol (the caller's :mod:`warnings` filter controls
    deduplication), then returns the canonical object from
    :mod:`octave_mcp.core.grammar.cst`. Unknown names raise
    :class:`AttributeError` per the standard module attribute protocol.
    """
    if name in _DEPRECATED_AST_EXPORTS:
        warnings.warn(
            (
                f"octave_mcp.core.ast_nodes.{name} is deprecated; import from "
                "octave_mcp.core.grammar.cst instead. "
                "Removal tracked under ADR-0006 SR1-T1."
            ),
            DeprecationWarning,
            stacklevel=2,
        )
        from octave_mcp.core.grammar import cst

        return getattr(cst, name)
    raise AttributeError(f"module 'octave_mcp.core.ast_nodes' has no attribute {name!r}")


if TYPE_CHECKING:
    # Re-declare the deprecated symbols statically so type-checkers and
    # static analysers know they are reachable from this namespace.
    # These bindings are NEVER executed at runtime; PEP 562 __getattr__
    # is the sole runtime resolution path.
    from octave_mcp.core.grammar.cst import (  # noqa: F401
        ABSENT,
        Absent,
        Assignment,
        ASTNode,
        Block,
        Comment,
        Document,
        HolographicValue,
        InlineMap,
        ListValue,
        LiteralZoneValue,
        NodeKind,
        Section,
    )
