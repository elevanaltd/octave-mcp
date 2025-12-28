"""Integration tests for MCP server (P2.4).

Tests the MCP server entry point:
- Server initialization
- Tool registration (new and deprecated tools)
- Basic integration smoke tests
"""

import pytest

from octave_mcp.mcp.server import create_server


class TestMCPServer:
    """Test MCP server integration."""

    @pytest.fixture
    def server(self):
        """Create MCP server instance."""
        return create_server()

    def test_server_name(self, server):
        """Server has correct name."""
        assert server.name == "octave-mcp"

    @pytest.mark.asyncio
    async def test_server_lists_all_tools(self, server):
        """Server lists new and deprecated tools (GH#51 consolidation)."""
        from mcp.types import ListToolsRequest

        request = ListToolsRequest(method="tools/list")
        handler = server.request_handlers.get(ListToolsRequest)

        assert handler is not None

        result = await handler(request)

        # ServerResult wraps the actual result in .root
        tools = result.root.tools
        tool_names = [tool.name for tool in tools]

        # New tools (GH#51)
        assert "octave_validate" in tool_names
        assert "octave_write" in tool_names
        assert "octave_eject" in tool_names

        # Deprecated tools (kept for 12-week migration)
        assert "octave_ingest" in tool_names
        assert "octave_create" in tool_names
        assert "octave_amend" in tool_names

        # Total: 6 tools
        assert len(tool_names) == 6

    @pytest.mark.asyncio
    async def test_ingest_tool_has_required_params(self, server):
        """Ingest tool schema has required parameters."""
        from mcp.types import ListToolsRequest

        request = ListToolsRequest(method="tools/list")
        handler = server.request_handlers.get(ListToolsRequest)
        result = await handler(request)

        tools = result.root.tools
        ingest = next(t for t in tools if t.name == "octave_ingest")

        assert "content" in ingest.inputSchema["required"]
        assert "schema" in ingest.inputSchema["required"]

    @pytest.mark.asyncio
    async def test_eject_tool_has_required_params(self, server):
        """Eject tool schema has required parameters."""
        from mcp.types import ListToolsRequest

        request = ListToolsRequest(method="tools/list")
        handler = server.request_handlers.get(ListToolsRequest)
        result = await handler(request)

        tools = result.root.tools
        eject = next(t for t in tools if t.name == "octave_eject")

        assert "schema" in eject.inputSchema["required"]
        assert "mode" in eject.inputSchema["properties"]
        assert "format" in eject.inputSchema["properties"]

    @pytest.mark.asyncio
    async def test_call_ingest_tool_succeeds(self, server):
        """Can call octave_ingest tool."""
        from mcp.types import CallToolRequest

        content = """===TEST===
META:
  VERSION::"1.0"

STATUS::active
===END==="""

        request = CallToolRequest(
            method="tools/call", params={"name": "octave_ingest", "arguments": {"content": content, "schema": "TEST"}}
        )

        from mcp.types import CallToolRequest as CallToolRequestType

        handler = server.request_handlers.get(CallToolRequestType)
        assert handler is not None

        result = await handler(request)

        # Result should have content
        assert result.root.content is not None
        assert len(result.root.content) > 0

    @pytest.mark.asyncio
    async def test_call_eject_tool_succeeds(self, server):
        """Can call octave_eject tool."""
        from mcp.types import CallToolRequest

        content = """===TEST===
META:
  VERSION::"1.0"

STATUS::active
===END==="""

        request = CallToolRequest(
            method="tools/call",
            params={"name": "octave_eject", "arguments": {"content": content, "schema": "TEST", "mode": "canonical"}},
        )

        from mcp.types import CallToolRequest as CallToolRequestType

        handler = server.request_handlers.get(CallToolRequestType)

        result = await handler(request)

        # Result should have content
        assert result.root.content is not None
        assert len(result.root.content) > 0
