"""MCP server entry point (P2.4).

Provides the MCP server with OCTAVE tools:
- octave_validate (schema validation and repair)
- octave_write (unified file writing: creation and amendment)
- octave_eject (projection to different modes/formats)
- octave_compile_grammar (compile schema/contract to constraint grammar)

Environment Variables:
- DISABLED_TOOLS: Comma-separated list of tools to disable.
  Available tools: octave_validate, octave_write, octave_eject, octave_compile_grammar
  Example: DISABLED_TOOLS=octave_eject
- OCTAVE_MCP_SKIP_SYNC: Set to "1" to skip dependency sync on startup.
- MCP_TRANSPORT: Transport type ("stdio" or "http"). Default: stdio
- MCP_HOST: Host address for HTTP transport. Default: 127.0.0.1
- MCP_PORT: Port number for HTTP transport. Default: 8080

CLI Usage:
  octave-mcp-server                              # Default: stdio
  octave-mcp-server --transport http             # HTTP transport
  octave-mcp-server --transport http --port 9000 # Custom port
  octave-mcp-server --transport http --host 0.0.0.0 --stateless  # Serverless mode
"""

import argparse
import asyncio
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from octave_mcp.mcp.base_tool import BaseTool
from octave_mcp.mcp.compile_grammar import CompileGrammarTool
from octave_mcp.mcp.eject import EjectTool
from octave_mcp.mcp.validate import ValidateTool
from octave_mcp.mcp.write import WriteTool

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

# Default configuration for HTTP transport
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080


def ensure_dependencies_synced() -> None:
    """Ensure venv dependencies are in sync with uv.lock.

    The MCP server runs independently from user worktrees, so it may have
    stale dependencies if the lock file was updated. This function runs
    `uv sync` if needed to ensure the server has current dependencies.

    Can be disabled by setting OCTAVE_MCP_SKIP_SYNC=1.
    """
    if os.getenv("OCTAVE_MCP_SKIP_SYNC", "").strip() == "1":
        return

    # Find the project root (where pyproject.toml lives)
    # Start from the package location and walk up
    package_dir = Path(__file__).resolve().parent
    project_root = None

    for parent in [package_dir] + list(package_dir.parents):
        if (parent / "pyproject.toml").exists():
            project_root = parent
            break

    if project_root is None:
        # Can't find project root - skip sync (installed package scenario)
        return

    lock_file = project_root / "uv.lock"
    if not lock_file.exists():
        # No lock file - skip sync
        return

    # Check if uv is available
    try:
        subprocess.run(
            ["uv", "--version"],
            capture_output=True,
            check=True,
            timeout=5,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        # uv not available - skip sync
        return

    # Run uv sync to ensure dependencies are current
    try:
        result = subprocess.run(
            ["uv", "sync", "--quiet"],
            cwd=project_root,
            capture_output=True,
            timeout=60,
        )
        if result.returncode != 0:
            # Log but don't fail - server may still work
            stderr = result.stderr.decode("utf-8", errors="replace")
            logger.warning(f"uv sync failed: {stderr}")
    except subprocess.TimeoutExpired:
        logger.warning("uv sync timed out after 60 seconds")
    except Exception as e:
        logger.warning(f"Failed to run uv sync: {e}")


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
        "octave_compile_grammar": CompileGrammarTool(),
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


# Transport selection functions


def get_transport_type() -> str:
    """Get transport type from environment or default to stdio.

    Returns:
        Transport type string: "stdio" or "http"
    """
    transport = os.getenv("MCP_TRANSPORT", "stdio").strip().lower()
    return transport


def get_server_host() -> str:
    """Get server host from environment or default to localhost.

    Returns:
        Host address string
    """
    return os.getenv("MCP_HOST", DEFAULT_HOST).strip()


def get_server_port() -> int:
    """Get server port from environment or default to 8080.

    Returns:
        Port number
    """
    port_str = os.getenv("MCP_PORT", str(DEFAULT_PORT)).strip()
    try:
        return int(port_str)
    except ValueError:
        logger.warning(f"Invalid MCP_PORT value '{port_str}', using default {DEFAULT_PORT}")
        return DEFAULT_PORT


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments.

    Args:
        args: Command line arguments. If None, uses sys.argv[1:].

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="OCTAVE MCP Server - Schema validation and OCTAVE file operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  octave-mcp-server                              # Default: stdio transport
  octave-mcp-server --transport http             # HTTP transport on localhost:8080
  octave-mcp-server --transport http --port 9000 # HTTP on port 9000
  octave-mcp-server --transport http --host 0.0.0.0 --stateless  # Serverless mode

Environment Variables:
  MCP_TRANSPORT    Transport type (stdio, http)
  MCP_HOST         HTTP host address (default: 127.0.0.1)
  MCP_PORT         HTTP port number (default: 8080)
  DISABLED_TOOLS   Comma-separated list of tools to disable
""",
    )

    parser.add_argument(
        "--transport",
        "-t",
        choices=["stdio", "http"],
        default=get_transport_type(),
        help="Transport type (default: stdio, or MCP_TRANSPORT env)",
    )

    parser.add_argument(
        "--host",
        "-H",
        default=get_server_host(),
        help="HTTP host address (default: 127.0.0.1, or MCP_HOST env)",
    )

    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=get_server_port(),
        help="HTTP port number (default: 8080, or MCP_PORT env)",
    )

    parser.add_argument(
        "--stateless",
        "-s",
        action="store_true",
        default=False,
        help="Enable stateless mode for serverless deployments",
    )

    parser.add_argument(
        "--json-response",
        "-j",
        action="store_true",
        default=False,
        help="Use JSON responses instead of SSE streams",
    )

    return parser.parse_args(args)


async def main():
    """Run the MCP server via stdio."""
    server = create_server()

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def run_stdio() -> None:
    """Run the MCP server with stdio transport."""
    asyncio.run(main())


def run_http(host: str, port: int, stateless: bool = False, json_response: bool = False) -> None:
    """Run the MCP server with HTTP transport.

    Args:
        host: Host address to bind to
        port: Port number to listen on
        stateless: Enable stateless mode for serverless
        json_response: Use JSON responses instead of SSE
    """
    from octave_mcp.mcp.http_transport import run_http_server

    run_http_server(
        host=host,
        port=port,
        stateless=stateless,
        json_response=json_response,
    )


def run():
    """Start the MCP server (entry point).

    Ensures dependencies are synced before starting the server.
    This prevents issues where the MCP server runs with stale
    dependencies after uv.lock is updated.

    Supports both stdio (default) and HTTP transports via CLI args
    or environment variables.
    """
    ensure_dependencies_synced()

    args = parse_args()

    if args.transport == "http":
        run_http(
            host=args.host,
            port=args.port,
            stateless=args.stateless,
            json_response=args.json_response,
        )
    else:
        run_stdio()


if __name__ == "__main__":
    run()
