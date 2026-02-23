"""MCP tool for OCTAVE grammar compilation (Issue #228).

Exposes the existing GBNF compiler as a direct MCP tool, allowing:
- Compilation from builtin schema name (e.g., schema="SKILL")
- Compilation from inline OCTAVE content with META.CONTRACT
- Output in GBNF or JSON Schema format
- Usage hints for inference engines (llama.cpp, vLLM, Outlines)
"""

import json
from typing import Any

from octave_mcp.core.constraints import (
    ConstConstraint,
    EnumConstraint,
    MaxLengthConstraint,
    MinLengthConstraint,
    RangeConstraint,
    RegexConstraint,
    RequiredConstraint,
    TypeConstraint,
)
from octave_mcp.core.gbnf_compiler import GBNFCompiler, compile_gbnf_from_meta
from octave_mcp.core.parser import parse
from octave_mcp.core.schema_extractor import (
    SchemaDefinition,
    extract_schema_from_document,
)
from octave_mcp.mcp.base_tool import BaseTool, SchemaBuilder
from octave_mcp.schemas.loader import load_schema_by_name

# Valid output formats
VALID_FORMATS = {"gbnf", "json_schema"}

# Usage hints for inference engines
USAGE_HINTS: dict[str, str] = {
    "llama_cpp": (
        "Pass the grammar string to llama.cpp via the --grammar flag "
        "or the `grammar` parameter in the API. Example: "
        '--grammar \'<grammar_string>\' or {"grammar": "<grammar_string>"}'
    ),
    "vllm": (
        "Use vLLM guided decoding with the json_schema format. "
        "Pass the JSON Schema to the guided_decoding parameter: "
        '{"guided_json": <json_schema_object>}. '
        "For GBNF format, convert to regex or use json_schema format instead."
    ),
    "outlines": (
        "Use the json_schema format with Outlines. "
        "Pass the JSON Schema to outlines.generate.json(): "
        "generator = outlines.generate.json(model, <json_schema_object>). "
        "For GBNF, use outlines.generate.cfg(model, <grammar_string>)."
    ),
}


def _gbnf_to_json_schema(schema: SchemaDefinition) -> str:
    """Convert schema fields to JSON Schema format for guided decoding.

    Produces a JSON Schema object describing the expected fields and their
    types/constraints, suitable for vLLM guided_json or Outlines.

    Args:
        schema: SchemaDefinition with field definitions

    Returns:
        JSON string representing the schema in JSON Schema format
    """
    properties: dict[str, Any] = {}
    required: list[str] = []

    for field_name, field_def in schema.fields.items():
        field_schema: dict[str, Any] = {"type": "string"}

        if field_def.pattern and field_def.pattern.constraints:
            chain = field_def.pattern.constraints
            for constraint in chain.constraints:
                if isinstance(constraint, EnumConstraint):
                    field_schema["enum"] = list(constraint.allowed_values)
                elif isinstance(constraint, ConstConstraint):
                    field_schema["const"] = constraint.const_value
                elif isinstance(constraint, TypeConstraint):
                    type_map = {
                        "STRING": "string",
                        "NUMBER": "number",
                        "BOOLEAN": "boolean",
                        "LIST": "array",
                    }
                    field_schema["type"] = type_map.get(constraint.expected_type, "string")
                elif isinstance(constraint, MaxLengthConstraint):
                    field_schema["maxLength"] = constraint.max_length
                elif isinstance(constraint, MinLengthConstraint):
                    field_schema["minLength"] = constraint.min_length
                elif isinstance(constraint, RangeConstraint):
                    if constraint.min_value is not None:
                        field_schema["minimum"] = constraint.min_value
                    if constraint.max_value is not None:
                        field_schema["maximum"] = constraint.max_value
                elif isinstance(constraint, RegexConstraint):
                    field_schema["pattern"] = constraint.pattern
                elif isinstance(constraint, RequiredConstraint):
                    required.append(field_name)

        properties[field_name] = field_schema

    json_schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        json_schema["required"] = required

    return json.dumps(json_schema, indent=2)


class CompileGrammarTool(BaseTool):
    """MCP tool for octave_compile_grammar - compile OCTAVE schema to constraint grammar."""

    def get_name(self) -> str:
        """Get tool name."""
        return "octave_compile_grammar"

    def get_description(self) -> str:
        """Get tool description."""
        return (
            "Compile OCTAVE schema or contract to constraint grammar. "
            "Supports GBNF (llama.cpp) and JSON Schema (vLLM) output formats. "
            "Provide either a builtin schema name or inline OCTAVE content."
        )

    def get_input_schema(self) -> dict[str, Any]:
        """Get input schema."""
        schema = SchemaBuilder()

        schema.add_parameter(
            "schema",
            "string",
            required=False,
            description=(
                "Builtin schema name to compile grammar from "
                "(e.g., 'SKILL', 'META'). Mutually exclusive with content."
            ),
        )

        schema.add_parameter(
            "content",
            "string",
            required=False,
            description=(
                "Inline OCTAVE document content with META.CONTRACT or " "FIELDS block. Mutually exclusive with schema."
            ),
        )

        schema.add_parameter(
            "format",
            "string",
            required=False,
            description="Output format: gbnf (default) or json_schema.",
            enum=["gbnf", "json_schema"],
        )

        return schema.build()

    def _error_response(self, errors: list[dict[str, Any]]) -> dict[str, Any]:
        """Build error response envelope.

        Args:
            errors: List of error dicts with code and message

        Returns:
            Error response dictionary
        """
        return {
            "status": "error",
            "errors": errors,
            "validation_status": "UNVALIDATED",  # I5: Explicit bypass
        }

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute grammar compilation.

        Args:
            schema: Builtin schema name (XOR with content)
            content: Inline OCTAVE content (XOR with schema)
            format: Output format - gbnf (default) or json_schema

        Returns:
            Dictionary with:
            - status: "success" or "error"
            - schema_name: Name of the compiled schema
            - format: Output format used
            - grammar: The compiled grammar string
            - usage_hints: Dict of engine-specific usage guidance
            - validation_status: I5 compliance field
            - errors: List of errors (on failure)
        """
        params = self.validate_parameters(kwargs)
        schema_name_param = params.get("schema")
        content = params.get("content")
        output_format = params.get("format", "gbnf")

        # Validate format
        if output_format not in VALID_FORMATS:
            return self._error_response(
                [
                    {
                        "code": "E_FORMAT",
                        "message": (
                            f"Invalid format '{output_format}'. " f"Valid formats: {', '.join(sorted(VALID_FORMATS))}"
                        ),
                    }
                ]
            )

        # XOR validation: exactly one of schema or content
        if schema_name_param is not None and content is not None:
            return self._error_response(
                [
                    {
                        "code": "E_INPUT",
                        "message": ("Cannot provide both schema and content - " "they are mutually exclusive"),
                    }
                ]
            )

        if schema_name_param is None and content is None:
            return self._error_response(
                [
                    {
                        "code": "E_INPUT",
                        "message": "Must provide either schema or content",
                    }
                ]
            )

        # Compile grammar from schema name or content
        schema_def: SchemaDefinition | None = None
        resolved_name: str = "UNKNOWN"

        if schema_name_param is not None:
            # Load schema by name from builtin registry
            try:
                schema_def = load_schema_by_name(schema_name_param)
            except Exception as e:
                return self._error_response(
                    [
                        {
                            "code": "E_SCHEMA",
                            "message": f"Failed to load schema '{schema_name_param}': {e}",
                        }
                    ]
                )
            if schema_def is None:
                return self._error_response(
                    [
                        {
                            "code": "E_SCHEMA",
                            "message": (
                                f"Schema '{schema_name_param}' not found in " "builtin registry or search paths"
                            ),
                        }
                    ]
                )
            resolved_name = schema_def.name

        elif content is not None:
            # Parse inline content and extract schema
            try:
                doc = parse(content)
            except Exception as e:
                return self._error_response(
                    [
                        {
                            "code": "E_PARSE",
                            "message": f"Failed to parse content: {e}",
                        }
                    ]
                )

            # Check for META.CONTRACT first (v6 self-describing documents)
            if doc.meta and "CONTRACT" in doc.meta:
                # Use compile_gbnf_from_meta for CONTRACT-based compilation
                if output_format == "gbnf":
                    grammar = compile_gbnf_from_meta(doc.meta)
                    resolved_name = str(doc.meta.get("TYPE", "UNKNOWN"))
                    return {
                        "status": "success",
                        "schema_name": resolved_name,
                        "format": "gbnf",
                        "grammar": grammar,
                        "usage_hints": USAGE_HINTS,
                        "validation_status": "UNVALIDATED",  # I5
                    }
                else:
                    # For json_schema, we need to extract schema first
                    # Parse CONTRACT into a SchemaDefinition
                    from octave_mcp.core.gbnf_compiler import (
                        _extract_contract_field_specs,
                        parse_contract_field,
                    )
                    from octave_mcp.core.holographic import HolographicPattern
                    from octave_mcp.core.schema_extractor import FieldDefinition

                    schema_type = str(doc.meta.get("TYPE", "UNKNOWN"))
                    schema_def = SchemaDefinition(
                        name=schema_type,
                        version=str(doc.meta.get("VERSION", "1.0")),
                    )
                    contract = doc.meta.get("CONTRACT")
                    if contract:
                        field_specs = _extract_contract_field_specs(contract)
                        for field_spec in field_specs:
                            try:
                                field_name, constraints = parse_contract_field(field_spec)
                                pattern = HolographicPattern(
                                    example=None,
                                    constraints=constraints,
                                    target=None,
                                )
                                schema_def.fields[field_name] = FieldDefinition(
                                    name=field_name,
                                    pattern=pattern,
                                    raw_value=field_spec,
                                )
                            except ValueError:
                                continue
                    resolved_name = schema_type
            else:
                # Extract from POLICY/FIELDS blocks
                schema_def = extract_schema_from_document(doc)
                resolved_name = schema_def.name

        # At this point schema_def should be set for non-CONTRACT paths
        if schema_def is None:
            return self._error_response(
                [
                    {
                        "code": "E_COMPILE",
                        "message": "Failed to resolve schema for compilation",
                    }
                ]
            )

        # Compile to requested format
        try:
            if output_format == "gbnf":
                compiler = GBNFCompiler()
                grammar = compiler.compile_schema(schema_def, include_envelope=True)
            elif output_format == "json_schema":
                grammar = _gbnf_to_json_schema(schema_def)
            else:
                # Should not reach here due to earlier validation
                return self._error_response([{"code": "E_FORMAT", "message": f"Unsupported format: {output_format}"}])
        except Exception as e:
            return self._error_response(
                [
                    {
                        "code": "E_COMPILE",
                        "message": f"Grammar compilation failed: {e}",
                    }
                ]
            )

        return {
            "status": "success",
            "schema_name": resolved_name,
            "format": output_format,
            "grammar": grammar,
            "usage_hints": USAGE_HINTS,
            "validation_status": "UNVALIDATED",  # I5: Grammar compilation, not validation
        }
