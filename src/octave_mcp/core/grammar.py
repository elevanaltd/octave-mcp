"""OCTAVE grammar compilation orchestration (Issue #171).

Provides JIT grammar compilation from META schema definitions.
Coordinates constraint compilation into GBNF grammars for llama.cpp
constrained generation.

v6.0 Generative Holographic Contracts: Documents carry their own validation law.
"""

from typing import Any

from octave_mcp.core.gbnf_compiler import GBNFCompiler, compile_gbnf_from_meta
from octave_mcp.core.schema_extractor import SchemaDefinition


def compile_document_grammar(meta: dict[str, Any]) -> str:
    """Compile document grammar from META schema definition.

    Takes a META section containing schema information and compiles
    constraint specifications into a GBNF grammar for llama.cpp.

    Args:
        meta: META dictionary from parse_meta_only() or full parse

    Returns:
        Compiled GBNF grammar string

    Example:
        >>> meta = {"TYPE": "SESSION_LOG", "VERSION": "1.0"}
        >>> grammar = compile_document_grammar(meta)
        >>> "::=" in grammar
        True
    """
    return compile_gbnf_from_meta(meta)


def emit_grammar_for_schema(schema_name: str) -> str:
    """Emit GBNF grammar for named schema.

    Creates a minimal schema with the given name and compiles
    it to GBNF format.

    Args:
        schema_name: Name of schema to compile grammar for

    Returns:
        GBNF grammar string
    """
    schema = SchemaDefinition(name=schema_name, version="1.0")
    compiler = GBNFCompiler()
    return compiler.compile_schema(schema, include_envelope=True)
