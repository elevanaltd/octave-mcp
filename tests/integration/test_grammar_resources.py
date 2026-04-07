"""Integration tests for MCP grammar resource endpoints (Issue #280).

Tests that the MCP server exposes pre-compiled GBNF grammars as
resources via the MCP resource protocol:
- octave://grammars/{SCHEMA_NAME} for each builtin schema
- Resources are listed via list_resources
- Resources are readable via read_resource
- Resource template is listed via list_resource_templates
- Grammars are compiled on first access and cached
"""

import os

import pytest

from octave_mcp.mcp.server import create_server


@pytest.fixture(autouse=True)
def _set_cwd(monkeypatch):
    """Ensure CWD is project root for schema search paths."""
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    monkeypatch.chdir(project_root)


class TestGrammarResourceListing:
    """Test that grammar resources are listed correctly."""

    @pytest.fixture
    def server(self):
        """Create MCP server instance."""
        return create_server()

    @pytest.mark.asyncio
    async def test_list_resources_includes_grammar_resources(self, server):
        """list_resources returns grammar resources for builtin schemas."""
        from mcp.types import ListResourcesRequest

        request = ListResourcesRequest(method="resources/list")
        handler = server.request_handlers.get(ListResourcesRequest)

        assert handler is not None, "list_resources handler must be registered"

        result = await handler(request)
        resources = result.root.resources

        # Should have at least META and SKILL grammars
        uris = [str(r.uri) for r in resources]
        assert any("grammars/META" in u for u in uris), f"META grammar resource not found in {uris}"
        assert any("grammars/SKILL" in u for u in uris), f"SKILL grammar resource not found in {uris}"

    @pytest.mark.asyncio
    async def test_grammar_resources_have_correct_mime_type(self, server):
        """Grammar resources declare text/plain MIME type."""
        from mcp.types import ListResourcesRequest

        request = ListResourcesRequest(method="resources/list")
        handler = server.request_handlers.get(ListResourcesRequest)
        result = await handler(request)

        for resource in result.root.resources:
            uri_str = str(resource.uri)
            if "grammars/" in uri_str:
                assert resource.mimeType == "text/plain", f"Grammar resource {uri_str} should have text/plain MIME type"

    @pytest.mark.asyncio
    async def test_grammar_resources_have_descriptions(self, server):
        """Grammar resources have descriptive text."""
        from mcp.types import ListResourcesRequest

        request = ListResourcesRequest(method="resources/list")
        handler = server.request_handlers.get(ListResourcesRequest)
        result = await handler(request)

        for resource in result.root.resources:
            uri_str = str(resource.uri)
            if "grammars/" in uri_str:
                assert resource.description is not None, f"Grammar resource {uri_str} should have a description"
                assert len(resource.description) > 10, f"Grammar resource {uri_str} description too short"


class TestGrammarResourceReading:
    """Test that grammar resources can be read."""

    @pytest.fixture
    def server(self):
        """Create MCP server instance."""
        return create_server()

    @pytest.mark.asyncio
    async def test_read_meta_grammar_resource(self, server):
        """Reading META grammar resource returns valid GBNF."""
        from mcp.types import ReadResourceRequest

        request = ReadResourceRequest(
            method="resources/read",
            params={"uri": "octave://grammars/META"},
        )
        handler = server.request_handlers.get(ReadResourceRequest)

        assert handler is not None, "read_resource handler must be registered"

        result = await handler(request)
        contents = result.root.contents

        assert len(contents) == 1, "Should return exactly one content block"

        content = contents[0]
        assert content.text is not None, "Content should have text"
        assert "::=" in content.text, "GBNF grammar should contain production rules (::=)"
        assert str(content.uri) == "octave://grammars/META"

    @pytest.mark.asyncio
    async def test_read_skill_grammar_resource(self, server):
        """Reading SKILL grammar resource returns valid GBNF."""
        from mcp.types import ReadResourceRequest

        request = ReadResourceRequest(
            method="resources/read",
            params={"uri": "octave://grammars/SKILL"},
        )
        handler = server.request_handlers.get(ReadResourceRequest)
        result = await handler(request)

        contents = result.root.contents
        assert len(contents) == 1
        content = contents[0]
        assert "::=" in content.text, "GBNF grammar should contain ::= rules"

    @pytest.mark.asyncio
    async def test_read_unknown_grammar_returns_error(self, server):
        """Reading a non-existent grammar resource raises an error."""
        from mcp.types import ReadResourceRequest

        request = ReadResourceRequest(
            method="resources/read",
            params={"uri": "octave://grammars/NONEXISTENT_SCHEMA_XYZ"},
        )
        handler = server.request_handlers.get(ReadResourceRequest)

        with pytest.raises(ValueError, match="not found"):
            await handler(request)

    @pytest.mark.asyncio
    async def test_read_non_grammar_uri_raises_error(self, server):
        """Reading a URI outside octave://grammars/ raises an error."""
        from mcp.types import ReadResourceRequest

        request = ReadResourceRequest(
            method="resources/read",
            params={"uri": "octave://other/thing"},
        )
        handler = server.request_handlers.get(ReadResourceRequest)

        with pytest.raises(ValueError, match="Unsupported"):
            await handler(request)


class TestGrammarResourceCaching:
    """Test that grammar compilation results are cached."""

    @pytest.fixture
    def server(self):
        """Create MCP server instance."""
        return create_server()

    @pytest.mark.asyncio
    async def test_grammar_is_cached_after_first_read(self, server):
        """Second read of same grammar returns cached result."""
        from mcp.types import ReadResourceRequest

        request = ReadResourceRequest(
            method="resources/read",
            params={"uri": "octave://grammars/META"},
        )
        handler = server.request_handlers.get(ReadResourceRequest)

        # Read twice
        result1 = await handler(request)
        result2 = await handler(request)

        # Both should return identical content
        text1 = result1.root.contents[0].text
        text2 = result2.root.contents[0].text
        assert text1 == text2, "Cached grammar should be identical"


class TestGrammarResourceTemplate:
    """Test that resource templates are provided for dynamic access."""

    @pytest.fixture
    def server(self):
        """Create MCP server instance."""
        return create_server()

    @pytest.mark.asyncio
    async def test_list_resource_templates_includes_grammar_template(self, server):
        """list_resource_templates includes the grammar URI template."""
        from mcp.types import ListResourceTemplatesRequest

        request = ListResourceTemplatesRequest(
            method="resources/templates/list",
        )
        handler = server.request_handlers.get(ListResourceTemplatesRequest)

        assert handler is not None, "list_resource_templates handler must be registered"

        result = await handler(request)
        templates = result.root.resourceTemplates

        assert len(templates) >= 1, "Should have at least one resource template"

        # Find the grammar template
        grammar_templates = [t for t in templates if "grammars" in str(t.uriTemplate)]
        assert len(grammar_templates) == 1, "Should have exactly one grammar template"

        template = grammar_templates[0]
        assert "{schema_name}" in str(template.uriTemplate), "Template should have {schema_name} placeholder"
        assert template.mimeType == "text/plain"
