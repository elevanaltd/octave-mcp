"""Deprecated: use octave_mcp.core.grammar_compiler.gbnf instead.

This shim re-exports the public API from the new path and emits a
DeprecationWarning. Scheduled for removal alongside the SR1-T1 grammar
core unification milestone (post-#382 Step 6).
"""

import warnings

from octave_mcp.core.grammar_compiler.gbnf import (
    compile_document_grammar,
    emit_grammar_for_schema,
)

__all__ = [
    "compile_document_grammar",
    "emit_grammar_for_schema",
]

warnings.warn(
    "octave_mcp.core.grammar is deprecated; import from "
    "octave_mcp.core.grammar_compiler.gbnf instead. Removal tracked at #382.",
    DeprecationWarning,
    stacklevel=2,
)
