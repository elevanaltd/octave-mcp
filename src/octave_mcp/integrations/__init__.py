"""OCTAVE integrations for LLM backends (Issue #171).

Provides integration helpers for constrained generation:
- llama_cpp: llama.cpp GBNF format
- outlines: Outlines JSON Schema export
- vllm: vLLM GBNF format
"""

from octave_mcp.integrations.llama_cpp import format_for_llama_cpp
from octave_mcp.integrations.outlines import schema_to_json_schema
from octave_mcp.integrations.vllm import format_for_vllm

__all__ = [
    "format_for_llama_cpp",
    "schema_to_json_schema",
    "format_for_vllm",
]
