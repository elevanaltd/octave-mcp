"""Base MCP tool infrastructure (P2.1).

Provides BaseTool abstract class and SchemaBuilder for MCP tool development.
"""

from abc import ABC, abstractmethod
from typing import Any

from mcp.types import Tool


class SchemaBuilder:
    """Builder for JSON Schema used in MCP tool parameter definitions.

    Follows PAL MCP pattern for schema generation from tool parameters.
    """

    def __init__(self) -> None:
        """Initialize schema builder."""
        self._properties: dict[str, dict[str, Any]] = {}
        self._required: list[str] = []

    def add_parameter(
        self,
        name: str,
        param_type: str,
        required: bool = False,
        description: str | None = None,
        enum: list[str] | None = None,
    ) -> "SchemaBuilder":
        """Add a parameter to the schema.

        Args:
            name: Parameter name
            param_type: JSON Schema type (string, boolean, number, etc.)
            required: Whether parameter is required
            description: Parameter description
            enum: List of valid enum values (for string types)

        Returns:
            Self for method chaining
        """
        param_schema: dict[str, Any] = {"type": param_type}

        if description:
            param_schema["description"] = description

        if enum is not None:
            param_schema["enum"] = enum

        self._properties[name] = param_schema

        if required:
            self._required.append(name)

        return self

    def build(self) -> dict[str, Any]:
        """Build the final JSON Schema object.

        Returns:
            Complete JSON Schema dictionary
        """
        schema: dict[str, Any] = {
            "type": "object",
            "properties": self._properties,
        }

        if self._required:
            schema["required"] = self._required

        return schema


class BaseTool(ABC):
    """Abstract base class for MCP tools.

    Defines the interface that all OCTAVE MCP tools must implement.
    Follows PAL MCP pattern for tool structure.
    """

    @abstractmethod
    def get_name(self) -> str:
        """Get the tool name.

        Returns:
            Tool name (e.g., "octave_validate")
        """
        pass

    @abstractmethod
    def get_description(self) -> str:
        """Get the tool description.

        Returns:
            Human-readable description of what the tool does
        """
        pass

    @abstractmethod
    def get_input_schema(self) -> dict[str, Any]:
        """Get the input schema for tool parameters.

        Returns:
            JSON Schema dictionary defining tool parameters
        """
        pass

    @abstractmethod
    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute the tool with given parameters.

        Args:
            **kwargs: Tool parameters matching the input schema

        Returns:
            Tool execution result dictionary
        """
        pass

    def to_mcp_tool(self) -> Tool:
        """Convert this tool to an MCP Tool object.

        Returns:
            MCP Tool object ready for registration
        """
        return Tool(
            name=self.get_name(),
            description=self.get_description(),
            inputSchema=self.get_input_schema(),
        )

    def validate_parameters(self, params: dict[str, Any]) -> dict[str, Any]:
        """Validate parameters against the input schema.

        Args:
            params: Parameters to validate

        Returns:
            Validated parameters

        Raises:
            ValueError: If required parameters are missing
        """
        schema = self.get_input_schema()
        required = schema.get("required", [])

        # Check required parameters
        for req_param in required:
            if req_param not in params:
                raise ValueError(f"Missing required parameter: {req_param}")

        return params
