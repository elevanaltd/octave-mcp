"""OCTAVE schema definitions and validation.

Provides Schema class and validation function that delegates to validator.py.
"""

from octave_mcp.core.grammar.cst import Document
from octave_mcp.core.validator import ValidationError
from octave_mcp.core.validator import validate as validate_impl


class Schema:
    """OCTAVE schema definition."""

    def __init__(self, name: str, version: str, fields: dict, schema_data: dict | None = None):
        """Initialize schema from parsed data.

        Args:
            name: Schema name
            version: Schema version
            fields: Schema field definitions
            schema_data: Optional parsed schema structure
        """
        self.name = name
        self.version = version
        self.fields = fields
        self._data = schema_data or {}


def validate(ast: Document, schema: Schema | dict) -> list[ValidationError]:
    """Validate AST against schema.

    Delegates to validator.py for actual validation logic.

    Args:
        ast: Parsed Document AST
        schema: Schema definition (Schema object or dict)

    Returns:
        List of validation errors (empty if valid)
    """
    # Convert Schema object to dict if needed
    schema_dict = schema._data if isinstance(schema, Schema) else schema

    # Delegate to working validator implementation
    return validate_impl(ast, schema_dict, strict=False)
