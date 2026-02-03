"""Streamable HTTP transport for OCTAVE MCP server.

This module provides HTTP transport support for the OCTAVE MCP server,
enabling web-based clients (ChatGPT, browsers, Obsidian plugins) to
access OCTAVE validation and writing tools.

Implements the MCP Streamable HTTP transport specification:
- Single /mcp endpoint for all MCP interactions
- DNS rebinding protection via Host header validation
- Localhost binding by default (127.0.0.1)
- Stateless mode support for serverless compatibility

References:
- MCP Spec: https://modelcontextprotocol.io/specification/2025-03-26/basic/transports
- Issue #218: Streamable HTTP transport for web clients
"""

import contextlib
import logging
from collections.abc import AsyncIterator
from typing import Any

from mcp.server.lowlevel.server import Server as MCPServer
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.types import Receive, Scope, Send

logger = logging.getLogger(__name__)

# Default configuration constants
DEFAULT_HOST = "127.0.0.1"  # Localhost for security
DEFAULT_PORT = 8080
MCP_ENDPOINT = "/mcp"


def get_default_security_settings() -> TransportSecuritySettings:
    """Get default security settings with DNS rebinding protection.

    Returns:
        TransportSecuritySettings configured for localhost access with
        DNS rebinding protection enabled.
    """
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        # Allow localhost with any port (for development flexibility)
        allowed_hosts=[
            "localhost:*",
            "127.0.0.1:*",
        ],
        allowed_origins=[
            "http://localhost:*",
            "http://127.0.0.1:*",
        ],
    )


def create_mcp_server() -> MCPServer[Any, Any]:
    """Create and configure the MCP server with OCTAVE tools.

    This mirrors the create_server() logic from server.py but returns
    the low-level server for use with StreamableHTTPSessionManager.

    Returns:
        Configured MCPServer instance with tools registered
    """
    import json
    import os

    from mcp.types import TextContent, Tool

    from octave_mcp.mcp.base_tool import BaseTool
    from octave_mcp.mcp.eject import EjectTool
    from octave_mcp.mcp.validate import ValidateTool
    from octave_mcp.mcp.write import WriteTool

    server: MCPServer[Any, Any] = MCPServer("octave-mcp")

    # Initialize all tools
    all_tools: dict[str, BaseTool] = {
        "octave_validate": ValidateTool(),
        "octave_write": WriteTool(),
        "octave_eject": EjectTool(),
    }

    # Parse disabled tools from environment
    disabled_str = os.getenv("DISABLED_TOOLS", "").strip()
    disabled = {t.strip().lower() for t in disabled_str.split(",") if t.strip()} if disabled_str else set()

    # Filter tools
    tools = {name: tool for name, tool in all_tools.items() if name.lower() not in disabled}

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
        """Route tool calls to appropriate handler."""
        if arguments is None:
            arguments = {}

        if name not in tools:
            if name in all_tools:
                raise ValueError(f"Tool '{name}' is disabled via DISABLED_TOOLS")
            raise ValueError(f"Unknown tool: {name}")

        result = await tools[name].execute(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    return server


def create_http_app(
    security_settings: TransportSecuritySettings | None = None,
    stateless: bool = False,
    json_response: bool = False,
) -> Starlette:
    """Create a Starlette application with Streamable HTTP transport.

    Args:
        security_settings: Optional security settings. Defaults to localhost-only
                          with DNS rebinding protection enabled.
        stateless: If True, creates stateless transport suitable for serverless.
                  Each request gets a fresh transport with no session persistence.
        json_response: If True, uses JSON responses instead of SSE streams.

    Returns:
        Starlette application configured for MCP Streamable HTTP transport.
    """
    if security_settings is None:
        security_settings = get_default_security_settings()

    # Create the MCP server with tools
    mcp_server = create_mcp_server()

    # Create the session manager
    session_manager = StreamableHTTPSessionManager(
        app=mcp_server,
        event_store=None,  # No resumability for now
        json_response=json_response,
        stateless=stateless,
        security_settings=security_settings,
    )

    async def health_check(request: Request) -> JSONResponse:
        """Health check endpoint for load balancers."""
        return JSONResponse({"status": "ok", "service": "octave-mcp"})

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        """Manage application lifecycle."""
        logger.info("Starting OCTAVE MCP HTTP server")
        async with session_manager.run():
            yield
        logger.info("OCTAVE MCP HTTP server stopped")

    # Create a custom ASGI app that wraps the session manager
    class MCPApp:
        """ASGI app wrapper for MCP session manager."""

        async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
            """Handle ASGI request."""
            await session_manager.handle_request(scope, receive, send)

    mcp_app = MCPApp()

    # Create routes
    routes = [
        Route("/health", health_check, methods=["GET"]),
        # Use Route with the ASGI app directly
        Route(MCP_ENDPOINT, mcp_app, methods=["GET", "POST"]),
    ]

    return Starlette(
        routes=routes,
        lifespan=lifespan,
    )


def run_http_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    security_settings: TransportSecuritySettings | None = None,
    stateless: bool = False,
    json_response: bool = False,
) -> None:
    """Run the HTTP server with uvicorn.

    Args:
        host: Host address to bind to. Default: 127.0.0.1
        port: Port number. Default: 8080
        security_settings: Optional security settings.
        stateless: If True, enables stateless mode.
        json_response: If True, uses JSON responses instead of SSE.
    """
    import uvicorn

    app = create_http_app(
        security_settings=security_settings,
        stateless=stateless,
        json_response=json_response,
    )

    logger.info(f"Starting OCTAVE MCP server on http://{host}:{port}")
    logger.info(f"MCP endpoint: http://{host}:{port}{MCP_ENDPOINT}")
    logger.info(f"Health check: http://{host}:{port}/health")

    uvicorn.run(app, host=host, port=port, log_level="info")
