"""MCP server entry point (P2.4).

Provides the MCP server with OCTAVE tools:
- octave_validate (schema validation and repair)
- octave_write (unified file writing: creation and amendment)
- octave_eject (projection to different modes/formats)
- octave_debate_to_octave (debate transcript conversion - Issue #52)

Environment Variables:
- DISABLED_TOOLS: Comma-separated list of tools to disable.
  Available tools: octave_validate, octave_write, octave_eject, octave_debate_to_octave
  Example: DISABLED_TOOLS=octave_debate_to_octave
"""

import asyncio
import json
import logging
import os
from typing import Any

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from octave_mcp.mcp.base_tool import BaseTool
from octave_mcp.mcp.debate_convert import DebateConvertTool
from octave_mcp.mcp.eject import EjectTool
from octave_mcp.mcp.validate import ValidateTool
from octave_mcp.mcp.write import WriteTool

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


def parse_disabled_tools() -> set[str]:
    """Parse DISABLED_TOOLS environment variable.

    Returns:
        Set of lowercase tool names to disable
    """
    disabled_str = os.getenv("DISABLED_TOOLS", "").strip()
    if not disabled_str:
        return set()
    return {t.strip().lower() for t in disabled_str.split(",") if t.strip()}


def filter_tools(all_tools: dict[str, BaseTool]) -> dict[str, BaseTool]:
    """Filter tools based on DISABLED_TOOLS environment variable.

    Args:
        all_tools: Dictionary mapping tool names to tool instances

    Returns:
        Filtered dictionary with disabled tools removed
    """
    disabled = parse_disabled_tools()
    if not disabled:
        return all_tools

    # Validate disabled tool names
    unknown = disabled - set(all_tools.keys())
    if unknown:
        logger.warning(f"Unknown tools in DISABLED_TOOLS: {sorted(unknown)}")

    # Filter out disabled tools
    enabled = {}
    for name, tool in all_tools.items():
        if name.lower() in disabled:
            logger.info(f"Tool '{name}' disabled via DISABLED_TOOLS")
        else:
            enabled[name] = tool

    logger.info(f"Active tools: {sorted(enabled.keys())}")
    return enabled


def create_server() -> Server:
    """Create and configure the MCP server.

    Returns:
        Configured Server instance with tools registered
    """
    server = Server("octave-mcp")

    # Initialize all tools
    all_tools: dict[str, BaseTool] = {
        "octave_validate": ValidateTool(),
        "octave_write": WriteTool(),
        "octave_eject": EjectTool(),
        "octave_debate_to_octave": DebateConvertTool(),
    }

    # Apply DISABLED_TOOLS filter
    tools = filter_tools(all_tools)

    @server.list_tools()
    async def handle_list_tools() -> list[Tool]:
        """List available tools."""
        return [
            Tool(
                name=tool.get_name(),
                description=tool.get_description(),
                inputSchema=tool.get_input_schema(),
            )
            for tool in tools.values()
        ]

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict[str, Any] | None) -> list[TextContent]:
        """Route tool calls to appropriate handler.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            List of TextContent with results

        Raises:
            ValueError: If tool name is unknown or disabled
        """
        if arguments is None:
            arguments = {}

        # Route to appropriate tool
        if name not in tools:
            if name in all_tools:
                raise ValueError(f"Tool '{name}' is disabled via DISABLED_TOOLS")
            raise ValueError(f"Unknown tool: {name}")

        result = await tools[name].execute(**arguments)

        # Return result as TextContent
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    return server


async def main():
    """Run the MCP server via stdio."""
    server = create_server()

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def run():
    """Start the MCP server (entry point)."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
