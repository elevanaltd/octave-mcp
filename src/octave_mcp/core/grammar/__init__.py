"""Unified grammar front-door package (ADR-0006 SR1-T1 Step 2).

This package is the single entry surface for the OCTAVE-MCP parse
pipeline. Its legitimate, encouraged exports are :func:`parse` and
:func:`parse_with_warnings` — re-exported identity-wrapped from
:mod:`octave_mcp.core.grammar.entry`.

Backward-compatibility shim
---------------------------

Step 1 (PR #393) relocated the GBNF compiler from the old
``octave_mcp.core.grammar`` module to
``octave_mcp.core.grammar_compiler.gbnf``. Step 2 (this PR) replaces the
flat transitional shim with this package. The legacy GBNF symbols are
still reachable through this namespace for the deprecation window, but
they are resolved lazily via :pep:`562` module ``__getattr__`` so that
the legitimate parse front-door does *not* emit a deprecation warning
on import. Accessing the legacy symbols emits a single
:class:`DeprecationWarning` and returns the canonical object from
:mod:`octave_mcp.core.grammar_compiler.gbnf` (identity-preserving).

See ``docs/adr/adr-0006-sr1-t1-grammar-core-design.md`` §2.2 and §2.3.
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any

from octave_mcp.core.grammar.entry import parse, parse_with_warnings

__all__ = ["parse", "parse_with_warnings"]

# Names re-exported from grammar_compiler.gbnf for backward compatibility.
# Listed here rather than in __all__ so they remain reachable but are not
# advertised as part of the new front-door surface.
_DEPRECATED_GBNF_EXPORTS: frozenset[str] = frozenset(
    {
        "compile_document_grammar",
        "emit_grammar_for_schema",
    }
)


def __getattr__(name: str) -> Any:
    """PEP 562 lazy resolver for legacy ``octave_mcp.core.grammar`` symbols.

    Emits a single :class:`DeprecationWarning` per attribute access for any
    legacy GBNF symbol, then returns the canonical object from
    :mod:`octave_mcp.core.grammar_compiler.gbnf`. Unknown names raise
    :class:`AttributeError` per the standard module attribute protocol.
    """
    if name in _DEPRECATED_GBNF_EXPORTS:
        warnings.warn(
            (
                f"octave_mcp.core.grammar.{name} is deprecated; import from "
                "octave_mcp.core.grammar_compiler.gbnf instead. "
                "Removal tracked at #382."
            ),
            DeprecationWarning,
            stacklevel=2,
        )
        from octave_mcp.core.grammar_compiler import gbnf

        return getattr(gbnf, name)
    raise AttributeError(f"module 'octave_mcp.core.grammar' has no attribute {name!r}")


if TYPE_CHECKING:
    # Re-declare the deprecated symbols statically so type-checkers and
    # static analysers know they are reachable from this namespace.
    # These bindings are NEVER executed at runtime; PEP 562 __getattr__
    # is the sole runtime resolution path.
    from octave_mcp.core.grammar_compiler.gbnf import (  # noqa: F401
        compile_document_grammar,
        emit_grammar_for_schema,
    )
