"""vLLM GBNF integration helper (Issue #171).

vLLM supports guided decoding via GBNF grammars (similar to llama.cpp).
This module provides formatting and utilities for vLLM integration.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from octave_mcp.core.schema_extractor import SchemaDefinition


def format_for_vllm(grammar: str) -> str:
    """Format GBNF grammar for vLLM consumption.

    vLLM uses a similar GBNF format to llama.cpp with minor differences.
    This ensures compatibility with vLLM's guided decoding.

    Args:
        grammar: GBNF grammar string

    Returns:
        Formatted grammar ready for vLLM
    """
    lines: list[str] = []

    for line in grammar.split("\n"):
        line = line.rstrip()

        # vLLM expects similar format to llama.cpp
        if "::=" in line:
            parts = line.split("::=", 1)
            rule_name = parts[0].strip()
            definition = parts[1].strip() if len(parts) > 1 else ""
            lines.append(f"{rule_name} ::= {definition}")
        else:
            lines.append(line)

    return "\n".join(lines)


def schema_to_vllm_grammar(schema: "SchemaDefinition", include_envelope: bool = True) -> str:
    """Convert OCTAVE schema to vLLM-compatible GBNF grammar.

    Convenience function that compiles schema and formats for vLLM.

    Args:
        schema: SchemaDefinition to compile
        include_envelope: Include OCTAVE document envelope

    Returns:
        GBNF grammar string ready for vLLM guided decoding
    """
    from octave_mcp.core.gbnf_compiler import GBNFCompiler

    compiler = GBNFCompiler()
    grammar = compiler.compile_schema(schema, include_envelope=include_envelope)
    return format_for_vllm(grammar)


def create_vllm_sampling_params(grammar: str) -> dict:
    """Create vLLM SamplingParams with grammar constraint.

    Returns a dictionary suitable for vLLM's SamplingParams.

    Args:
        grammar: GBNF grammar string

    Returns:
        Dictionary with guided_decoding configuration
    """
    return {
        "guided_decoding": {
            "backend": "outlines",
            "grammar": grammar,
        }
    }
