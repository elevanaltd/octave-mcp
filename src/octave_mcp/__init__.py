"""OCTAVE MCP Server - Lenient-to-Canonical OCTAVE pipeline.

This package provides a complete implementation of the OCTAVE specification,
including lexer, parser, emitter, validator, and vocabulary hydration.

Public API exports:
- Core functions: parse(), emit()
- Core classes: Parser, Validator, TokenType
- AST nodes: Document, Block, Assignment, Section, ListValue, InlineMap, Absent
- Hydration: hydrate(), HydrationPolicy, VocabularyRegistry
- Exceptions: VocabularyError, CollisionError, ParserError, LexerError
- Operators: OCTAVE_OPERATORS dict with canonical Unicode operators
"""

from octave_mcp.core.ast_nodes import Absent, Assignment, Block, Document, InlineMap, ListValue, Section
from octave_mcp.core.emitter import emit
from octave_mcp.core.hydrator import (
    CollisionError,
    HydrationPolicy,
    VocabularyError,
    VocabularyRegistry,
    hydrate,
)
from octave_mcp.core.lexer import LexerError, TokenType
from octave_mcp.core.parser import Parser, ParserError, parse
from octave_mcp.core.validator import Validator

__version__ = "0.3.0"

# Canonical OCTAVE operators (per specs/octave-5-llm-core.oct.md §2)
# These are the Unicode canonical forms. ASCII aliases are also accepted by the lexer.
OCTAVE_OPERATORS = {
    # Structural (Layer 1)
    "ASSIGN": "::",  # KEY::value binding
    "BLOCK": ":",  # KEY: (newline then indent)
    # Expression (Layer 2) - by precedence (lower = tighter)
    "CONCAT": "⧺",  # ASCII: ~ - Mechanical join: A⧺B
    "SYNTHESIS": "⊕",  # ASCII: + - Emergent whole: A⊕B
    "TENSION": "⇌",  # ASCII: vs, <-> - Binary opposition: A⇌B
    "CONSTRAINT": "∧",  # ASCII: & - Logical AND: [A∧B∧C]
    "ALTERNATIVE": "∨",  # ASCII: | - Logical OR: A∨B
    "FLOW": "→",  # ASCII: -> - Directional flow: A→B→C
    # Prefix/Special (Layer 3)
    "SECTION": "§",  # ASCII: # - Section target: §NAME
    "COMMENT": "//",  # Comment to end of line
}

# Individual operator constants for convenient access
OP_ASSIGN = OCTAVE_OPERATORS["ASSIGN"]
OP_BLOCK = OCTAVE_OPERATORS["BLOCK"]
OP_CONCAT = OCTAVE_OPERATORS["CONCAT"]
OP_SYNTHESIS = OCTAVE_OPERATORS["SYNTHESIS"]
OP_TENSION = OCTAVE_OPERATORS["TENSION"]
OP_CONSTRAINT = OCTAVE_OPERATORS["CONSTRAINT"]
OP_ALTERNATIVE = OCTAVE_OPERATORS["ALTERNATIVE"]
OP_FLOW = OCTAVE_OPERATORS["FLOW"]
OP_SECTION = OCTAVE_OPERATORS["SECTION"]
OP_COMMENT = OCTAVE_OPERATORS["COMMENT"]

__all__ = [
    # Version
    "__version__",
    # Core functions
    "parse",
    "emit",
    # Core classes
    "Parser",
    "Validator",
    "TokenType",
    # AST nodes
    "Document",
    "Block",
    "Assignment",
    "Section",
    "ListValue",
    "InlineMap",
    "Absent",
    # Hydration
    "hydrate",
    "HydrationPolicy",
    "VocabularyRegistry",
    # Exceptions
    "VocabularyError",
    "CollisionError",
    "ParserError",
    "LexerError",
    # Operators
    "OCTAVE_OPERATORS",
    "OP_ASSIGN",
    "OP_BLOCK",
    "OP_CONCAT",
    "OP_SYNTHESIS",
    "OP_TENSION",
    "OP_CONSTRAINT",
    "OP_ALTERNATIVE",
    "OP_FLOW",
    "OP_SECTION",
    "OP_COMMENT",
]
