"""Outlines JSON Schema integration helper (Issue #171).

Outlines uses JSON Schema for constrained generation.
This module converts OCTAVE schemas to JSON Schema format.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from octave_mcp.core.schema_extractor import SchemaDefinition

from octave_mcp.core.constraints import (
    ConstConstraint,
    DateConstraint,
    EnumConstraint,
    Iso8601Constraint,
    MaxLengthConstraint,
    MinLengthConstraint,
    RangeConstraint,
    RegexConstraint,
    TypeConstraint,
)


def schema_to_json_schema(schema: "SchemaDefinition") -> dict[str, Any]:
    """Convert OCTAVE schema to JSON Schema format.

    Outlines uses JSON Schema for constrained generation. This converts
    OCTAVE field definitions to JSON Schema properties.

    Args:
        schema: SchemaDefinition to convert

    Returns:
        JSON Schema dictionary
    """
    properties: dict[str, Any] = {}
    required: list[str] = []

    for field_name, field_def in schema.fields.items():
        prop = _field_to_json_schema_property(field_def)
        properties[field_name] = prop

        if field_def.is_required:
            required.append(field_name)

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "title": schema.name,
        "properties": properties,
        "required": required,
    }


def _field_to_json_schema_property(field_def: Any) -> dict[str, Any]:
    """Convert field definition to JSON Schema property.

    Args:
        field_def: FieldDefinition with pattern and constraints

    Returns:
        JSON Schema property definition
    """
    prop: dict[str, Any] = {}

    if not field_def.pattern or not field_def.pattern.constraints:
        return {"type": "string"}

    constraints = field_def.pattern.constraints.constraints

    for constraint in constraints:
        if isinstance(constraint, TypeConstraint):
            prop.update(_type_to_json_schema(constraint.expected_type))
        elif isinstance(constraint, EnumConstraint):
            prop["enum"] = constraint.allowed_values
        elif isinstance(constraint, ConstConstraint):
            prop["const"] = constraint.const_value
        elif isinstance(constraint, RegexConstraint):
            prop["type"] = "string"
            prop["pattern"] = constraint.pattern
        elif isinstance(constraint, MinLengthConstraint):
            prop["minLength"] = constraint.min_length
        elif isinstance(constraint, MaxLengthConstraint):
            prop["maxLength"] = constraint.max_length
        elif isinstance(constraint, RangeConstraint):
            prop["type"] = "number"
            prop["minimum"] = constraint.min_value
            prop["maximum"] = constraint.max_value
        elif isinstance(constraint, DateConstraint):
            prop["type"] = "string"
            prop["format"] = "date"
        elif isinstance(constraint, Iso8601Constraint):
            prop["type"] = "string"
            prop["format"] = "date-time"

    # Default to string if no type specified
    if "type" not in prop and "enum" not in prop and "const" not in prop:
        prop["type"] = "string"

    return prop


def _type_to_json_schema(octave_type: str) -> dict[str, Any]:
    """Convert OCTAVE type to JSON Schema type.

    Args:
        octave_type: OCTAVE type name (STRING, NUMBER, BOOLEAN, LIST)

    Returns:
        JSON Schema type definition
    """
    type_map = {
        "STRING": {"type": "string"},
        "NUMBER": {"type": "number"},
        "BOOLEAN": {"type": "boolean"},
        "LIST": {"type": "array"},
    }
    return type_map.get(octave_type, {"type": "string"})


def json_schema_to_outlines_format(json_schema: dict[str, Any]) -> str:
    """Format JSON Schema for Outlines consumption.

    Outlines expects JSON Schema as a string or dict.
    This formats it as a Python-evaluable string.

    Args:
        json_schema: JSON Schema dictionary

    Returns:
        JSON string representation
    """
    import json

    return json.dumps(json_schema, indent=2)
