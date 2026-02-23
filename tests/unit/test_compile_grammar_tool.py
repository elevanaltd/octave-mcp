"""Test cases for octave_compile_grammar MCP tool (Issue #228).

Tests grammar compilation from:
- Schema name (builtin registry lookup)
- Inline content (OCTAVE document with META.CONTRACT)
- Output formats: gbnf, json_schema
- Usage hints for inference engines
"""

import json

import pytest

from octave_mcp.mcp.compile_grammar import CompileGrammarTool


class TestCompileGrammarToolInterface:
    """Test CompileGrammarTool MCP interface (name, description, schema)."""

    @pytest.fixture
    def tool(self):
        """Create CompileGrammarTool instance."""
        return CompileGrammarTool()

    def test_tool_name(self, tool):
        """Tool returns correct name."""
        assert tool.get_name() == "octave_compile_grammar"

    def test_tool_description(self, tool):
        """Tool has non-empty description mentioning grammar/compile."""
        desc = tool.get_description()
        assert len(desc) > 0
        assert "grammar" in desc.lower()

    def test_input_schema_has_schema_param(self, tool):
        """Input schema defines optional schema parameter."""
        schema = tool.get_input_schema()
        assert "schema" in schema["properties"]
        # schema is optional (can use content instead)
        assert "schema" not in schema.get("required", [])

    def test_input_schema_has_content_param(self, tool):
        """Input schema defines optional content parameter."""
        schema = tool.get_input_schema()
        assert "content" in schema["properties"]
        assert "content" not in schema.get("required", [])

    def test_input_schema_has_format_param(self, tool):
        """Input schema defines format parameter with enum values."""
        schema = tool.get_input_schema()
        assert "format" in schema["properties"]
        fmt = schema["properties"]["format"]
        assert "enum" in fmt
        assert set(fmt["enum"]) == {"gbnf", "json_schema"}

    def test_to_mcp_tool(self, tool):
        """Tool converts to MCP Tool object."""
        mcp_tool = tool.to_mcp_tool()
        assert mcp_tool.name == "octave_compile_grammar"
        assert mcp_tool.inputSchema is not None


class TestCompileGrammarFromSchema:
    """Test grammar compilation from builtin schema name."""

    @pytest.fixture
    def tool(self):
        """Create CompileGrammarTool instance."""
        return CompileGrammarTool()

    @pytest.mark.asyncio
    async def test_compile_from_schema_name_skill(self, tool):
        """Compile grammar from builtin 'SKILL' schema."""
        result = await tool.execute(schema="SKILL")

        assert result["status"] == "success"
        assert result["schema_name"] == "SKILL_SCHEMA"
        assert result["format"] == "gbnf"
        assert "grammar" in result
        assert "::=" in result["grammar"]
        assert "usage_hints" in result

    @pytest.mark.asyncio
    async def test_compile_from_schema_name_meta(self, tool):
        """Compile grammar from builtin 'META' schema."""
        result = await tool.execute(schema="META")

        assert result["status"] == "success"
        assert result["format"] == "gbnf"
        assert "grammar" in result
        assert "::=" in result["grammar"]

    @pytest.mark.asyncio
    async def test_compile_schema_not_found(self, tool):
        """Error when schema name not found in registry."""
        result = await tool.execute(schema="NONEXISTENT_SCHEMA_XYZ")

        assert result["status"] == "error"
        assert any("not found" in e["message"].lower() for e in result["errors"])

    @pytest.mark.asyncio
    async def test_compile_schema_gbnf_format(self, tool):
        """Compile grammar in GBNF format explicitly."""
        result = await tool.execute(schema="SKILL", format="gbnf")

        assert result["status"] == "success"
        assert result["format"] == "gbnf"
        assert "::=" in result["grammar"]

    @pytest.mark.asyncio
    async def test_compile_schema_json_schema_format(self, tool):
        """Compile grammar in JSON Schema format."""
        result = await tool.execute(schema="SKILL", format="json_schema")

        assert result["status"] == "success"
        assert result["format"] == "json_schema"
        # JSON Schema output should be valid JSON
        grammar = result["grammar"]
        parsed = json.loads(grammar)
        assert "type" in parsed or "properties" in parsed


class TestCompileGrammarFromContent:
    """Test grammar compilation from inline OCTAVE content."""

    @pytest.fixture
    def tool(self):
        """Create CompileGrammarTool instance."""
        return CompileGrammarTool()

    @pytest.mark.asyncio
    async def test_compile_from_content_with_contract(self, tool):
        """Compile grammar from inline content with META.CONTRACT."""
        content = """===SESSION_LOG===
META:
  TYPE::SESSION_LOG
  VERSION::"1.0"
  CONTRACT::[FIELD[STATUS]::REQ∧ENUM[ACTIVE,PAUSED,COMPLETE], FIELD[PRIORITY]::OPT∧ENUM[LOW,MEDIUM,HIGH]]
===END==="""

        result = await tool.execute(content=content)

        assert result["status"] == "success"
        assert result["format"] == "gbnf"
        assert "grammar" in result
        assert "::=" in result["grammar"]
        # Grammar should reference the fields from CONTRACT
        grammar_lower = result["grammar"].lower()
        assert "status" in grammar_lower
        assert "priority" in grammar_lower

    @pytest.mark.asyncio
    async def test_compile_from_content_without_contract(self, tool):
        """Compile grammar from inline content without CONTRACT (uses FIELDS block)."""
        content = """===MY_SCHEMA===
META:
  TYPE::PROTOCOL_DEFINITION
  VERSION::"1.0"

FIELDS:
  NAME::["example"∧REQ]
  STATUS::["ACTIVE"∧ENUM[ACTIVE,INACTIVE]]
===END==="""

        result = await tool.execute(content=content)

        assert result["status"] == "success"
        assert "grammar" in result
        assert "::=" in result["grammar"]

    @pytest.mark.asyncio
    async def test_compile_from_content_invalid(self, tool):
        """Error when content cannot be parsed."""
        result = await tool.execute(content="this is not valid octave content {{{{")

        assert result["status"] == "error"
        assert len(result["errors"]) > 0


class TestCompileGrammarUsageHints:
    """Test usage_hints for inference engines."""

    @pytest.fixture
    def tool(self):
        """Create CompileGrammarTool instance."""
        return CompileGrammarTool()

    @pytest.mark.asyncio
    async def test_usage_hints_present(self, tool):
        """Usage hints are included in successful response."""
        result = await tool.execute(schema="SKILL")

        assert "usage_hints" in result
        hints = result["usage_hints"]
        assert "llama_cpp" in hints
        assert "vllm" in hints
        assert "outlines" in hints

    @pytest.mark.asyncio
    async def test_usage_hints_llama_cpp(self, tool):
        """llama_cpp hint contains relevant usage information."""
        result = await tool.execute(schema="SKILL")

        llama_hint = result["usage_hints"]["llama_cpp"]
        assert isinstance(llama_hint, str)
        assert len(llama_hint) > 0

    @pytest.mark.asyncio
    async def test_usage_hints_vllm(self, tool):
        """vLLM hint references guided decoding."""
        result = await tool.execute(schema="SKILL")

        vllm_hint = result["usage_hints"]["vllm"]
        assert isinstance(vllm_hint, str)
        assert len(vllm_hint) > 0


class TestCompileGrammarParameterValidation:
    """Test parameter validation edge cases."""

    @pytest.fixture
    def tool(self):
        """Create CompileGrammarTool instance."""
        return CompileGrammarTool()

    @pytest.mark.asyncio
    async def test_error_when_both_schema_and_content(self, tool):
        """Error when both schema and content provided."""
        result = await tool.execute(
            schema="SKILL",
            content="===TEST===\nMETA:\n  TYPE::TEST\n===END===",
        )

        assert result["status"] == "error"
        assert any("exclusive" in e["message"].lower() or "both" in e["message"].lower() for e in result["errors"])

    @pytest.mark.asyncio
    async def test_error_when_neither_schema_nor_content(self, tool):
        """Error when neither schema nor content provided."""
        result = await tool.execute()

        assert result["status"] == "error"
        assert any("must provide" in e["message"].lower() or "either" in e["message"].lower() for e in result["errors"])

    @pytest.mark.asyncio
    async def test_invalid_format(self, tool):
        """Error when invalid format specified."""
        result = await tool.execute(schema="SKILL", format="invalid_format")

        assert result["status"] == "error"
        assert any("format" in e["message"].lower() for e in result["errors"])

    @pytest.mark.asyncio
    async def test_validation_status_in_response(self, tool):
        """I5: validation_status is present in successful responses."""
        result = await tool.execute(schema="SKILL")

        assert "validation_status" in result
