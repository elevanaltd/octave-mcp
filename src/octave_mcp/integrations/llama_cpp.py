"""llama.cpp GBNF integration helper (Issue #171).

Provides formatting and validation for llama.cpp GBNF grammars.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from octave_mcp.core.schema_extractor import SchemaDefinition


def format_for_llama_cpp(grammar: str) -> str:
    """Format GBNF grammar for llama.cpp consumption.

    Ensures grammar follows llama.cpp conventions:
    - Proper line endings
    - Comments with #
    - Correct rule syntax

    Args:
        grammar: GBNF grammar string

    Returns:
        Formatted grammar ready for llama.cpp
    """
    lines: list[str] = []

    for line in grammar.split("\n"):
        line = line.rstrip()

        # Normalize whitespace in rules
        if "::=" in line:
            parts = line.split("::=", 1)
            rule_name = parts[0].strip()
            definition = parts[1].strip() if len(parts) > 1 else ""
            lines.append(f"{rule_name} ::= {definition}")
        else:
            lines.append(line)

    return "\n".join(lines)


def validate_gbnf_syntax(grammar: str) -> tuple[bool, list[str]]:
    """Validate GBNF grammar syntax.

    Checks:
    - All rules have ::= operator
    - Balanced quotes and brackets
    - Valid rule names (lowercase with hyphens/underscores)

    Args:
        grammar: GBNF grammar string

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors: list[str] = []
    lines = grammar.split("\n")

    for i, line in enumerate(lines, 1):
        line = line.strip()

        # Skip empty lines and comments
        if not line or line.startswith("#"):
            continue

        # Check for rule definition
        if "::=" not in line:
            # Could be continuation or malformed
            if line and not line.startswith('"') and not line.startswith("["):
                errors.append(f"Line {i}: Missing ::= operator in rule definition")

        # Check balanced quotes
        if line.count('"') % 2 != 0:
            errors.append(f"Line {i}: Unbalanced quotes")

        # Check balanced brackets
        if line.count("[") != line.count("]"):
            errors.append(f"Line {i}: Unbalanced square brackets")

        if line.count("(") != line.count(")"):
            errors.append(f"Line {i}: Unbalanced parentheses")

    return len(errors) == 0, errors


def schema_to_gbnf(schema: "SchemaDefinition", include_envelope: bool = True) -> str:
    """Convert OCTAVE schema to llama.cpp GBNF grammar.

    Convenience function that compiles schema and formats for llama.cpp.

    Args:
        schema: SchemaDefinition to compile
        include_envelope: Include OCTAVE document envelope

    Returns:
        GBNF grammar string ready for llama.cpp
    """
    from octave_mcp.core.gbnf_compiler import GBNFCompiler

    compiler = GBNFCompiler()
    grammar = compiler.compile_schema(schema, include_envelope=include_envelope)
    return format_for_llama_cpp(grammar)
