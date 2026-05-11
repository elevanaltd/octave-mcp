"""GBNF grammar compiler package (ADR-0006 SR1-T1 Step 1).

Renamed from ``octave_mcp.core.grammar`` to resolve the §72 name collision
that reserves ``core/grammar`` for the unified parse front-door promoted in
later SR1-T1 steps.

Public API is re-exported here so callers can ``from
octave_mcp.core.grammar_compiler import compile_document_grammar``.
"""

from octave_mcp.core.grammar_compiler.gbnf import (
    compile_document_grammar,
    emit_grammar_for_schema,
)

__all__ = [
    "compile_document_grammar",
    "emit_grammar_for_schema",
]
