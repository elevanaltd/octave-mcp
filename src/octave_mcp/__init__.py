"""OCTAVE MCP Server - Lenient-to-Canonical OCTAVE pipeline.

This package provides a complete implementation of the OCTAVE specification,
including lexer, parser, emitter, validator, and vocabulary hydration.

Public API exports:
- Core functions: parse(), emit(), tokenize(), repair(), project()
- Core classes: Parser, Validator, TokenType, Token
- AST nodes: Document, Block, Assignment, Section, ListValue, InlineMap, Absent
- Hydration: hydrate(), HydrationPolicy, VocabularyRegistry
- Schema: SchemaDefinition, FieldDefinition, extract_schema_from_document()
- Repair: repair(), RepairLog, RepairEntry, RepairTier
- Projection: project(), ProjectionResult
- Routing: RoutingLog, RoutingEntry
- Sealing: seal_document(), verify_seal(), SealVerificationResult
- Exceptions: VocabularyError, CollisionError, ParserError, LexerError, etc.
- Operators: OCTAVE_OPERATORS dict with canonical Unicode operators
"""

from octave_mcp.core.ast_nodes import Absent, Assignment, Block, Document, InlineMap, ListValue, Section
from octave_mcp.core.emitter import emit
from octave_mcp.core.hydrator import (
    CollisionError,
    CycleDetectionError,
    HydrationPolicy,
    SourceUriSecurityError,
    VersionMismatchError,
    VocabularyError,
    VocabularyRegistry,
    hydrate,
)
from octave_mcp.core.lexer import LexerError, Token, TokenType, tokenize
from octave_mcp.core.parser import Parser, ParserError, parse
from octave_mcp.core.projector import ProjectionResult, project
from octave_mcp.core.repair import repair
from octave_mcp.core.repair_log import RepairEntry, RepairLog, RepairTier
from octave_mcp.core.routing import RoutingEntry, RoutingLog
from octave_mcp.core.schema_extractor import FieldDefinition, SchemaDefinition, extract_schema_from_document
from octave_mcp.core.sealer import SealVerificationResult, seal_document, verify_seal
from octave_mcp.core.validator import ValidationError, Validator

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
    "tokenize",
    "repair",
    "project",
    # Core classes
    "Parser",
    "Validator",
    "TokenType",
    "Token",
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
    # Schema
    "SchemaDefinition",
    "FieldDefinition",
    "extract_schema_from_document",
    # Repair (I4 audit trail)
    "RepairLog",
    "RepairEntry",
    "RepairTier",
    # Projection
    "ProjectionResult",
    # Routing (I4 audit trail)
    "RoutingLog",
    "RoutingEntry",
    # Sealing (document integrity)
    "seal_document",
    "verify_seal",
    "SealVerificationResult",
    # Exceptions
    "VocabularyError",
    "CollisionError",
    "VersionMismatchError",
    "CycleDetectionError",
    "SourceUriSecurityError",
    "ParserError",
    "LexerError",
    "ValidationError",
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
