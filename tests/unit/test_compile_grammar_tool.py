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


class TestCompileGrammarConstTyping:
    """Regression tests for CE Finding 1: CONST values must preserve native types.

    str(constraint.const_value) coerces all const values to strings.
    This makes JSON Schema unsatisfiable for non-string types:
      NUMBER + CONST[5]    → {"const": "5"}  (wrong, should be 5)
      BOOLEAN + CONST[true] → {"const": "True"} (wrong, should be true)
      NULL + CONST[null]   → {"const": "None"} (wrong, should be null)
    """

    @pytest.fixture
    def tool(self):
        """Create CompileGrammarTool instance."""
        return CompileGrammarTool()

    @pytest.mark.asyncio
    async def test_const_number_preserved_as_number(self, tool):
        """CONST[5] on a NUMBER field must produce JSON Schema const: 5 (integer), not '5'."""
        content = """===TYPED_SCHEMA===
META:
  TYPE::TYPED_SCHEMA
  VERSION::"1.0"

FIELDS:
  COUNT::["5"∧CONST[5]∧TYPE[NUMBER]]
===END==="""

        result = await tool.execute(content=content, format="json_schema")

        assert result["status"] == "success"
        parsed = json.loads(result["grammar"])
        count_schema = parsed["properties"]["COUNT"]
        # The const value must be the native integer 5, not the string "5"
        assert count_schema["const"] == 5
        assert isinstance(count_schema["const"], int | float)

    @pytest.mark.asyncio
    async def test_const_boolean_preserved_as_boolean(self, tool):
        """CONST[true] on a BOOLEAN field must produce JSON Schema const: true, not 'True'."""
        content = """===TYPED_SCHEMA===
META:
  TYPE::TYPED_SCHEMA
  VERSION::"1.0"

FIELDS:
  FLAG::["true"∧CONST[true]∧TYPE[BOOLEAN]]
===END==="""

        result = await tool.execute(content=content, format="json_schema")

        assert result["status"] == "success"
        parsed = json.loads(result["grammar"])
        flag_schema = parsed["properties"]["FLAG"]
        # The const value must be boolean True, not the string "True"
        assert flag_schema["const"] is True
        assert isinstance(flag_schema["const"], bool)

    @pytest.mark.asyncio
    async def test_const_null_preserved_as_null(self, tool):
        """CONST[null] must produce JSON Schema const: null (None), not 'None'."""
        content = """===TYPED_SCHEMA===
META:
  TYPE::TYPED_SCHEMA
  VERSION::"1.0"

FIELDS:
  EMPTY::["null"∧CONST[null]]
===END==="""

        result = await tool.execute(content=content, format="json_schema")

        assert result["status"] == "success"
        parsed = json.loads(result["grammar"])
        empty_schema = parsed["properties"]["EMPTY"]
        # The const value must be null (None in Python), not the string "None"
        assert empty_schema["const"] is None

    @pytest.mark.asyncio
    async def test_const_string_still_works(self, tool):
        """CONST['hello'] on a STRING field must still produce const: 'hello'."""
        content = """===TYPED_SCHEMA===
META:
  TYPE::TYPED_SCHEMA
  VERSION::"1.0"

FIELDS:
  LABEL::["hello"∧CONST["hello"]]
===END==="""

        result = await tool.execute(content=content, format="json_schema")

        assert result["status"] == "success"
        parsed = json.loads(result["grammar"])
        label_schema = parsed["properties"]["LABEL"]
        assert label_schema["const"] == "hello"
        assert isinstance(label_schema["const"], str)


class TestCompileGrammarErrorEnvelope:
    """Regression tests for CE Finding 2: compile paths must return structured errors.

    Unexpected exceptions in schema load/compile paths must be caught and
    returned as {"status": "error", "errors": [...]} rather than propagating
    as transport-level exceptions.
    """

    @pytest.fixture
    def tool(self):
        """Create CompileGrammarTool instance."""
        return CompileGrammarTool()

    @pytest.mark.asyncio
    async def test_malformed_content_returns_structured_error(self, tool):
        """Malformed content that raises during schema extraction returns error envelope."""
        # Content that parses but produces an invalid/unusual structure
        # that may cause downstream failures
        result = await tool.execute(content="{{{not_valid_octave_at_all}}}")

        # Must return structured error, not raise an exception
        assert result["status"] == "error"
        assert "errors" in result
        assert len(result["errors"]) > 0
        assert all("code" in e and "message" in e for e in result["errors"])

    @pytest.mark.asyncio
    async def test_compile_exception_returns_structured_error_not_crash(self, tool):
        """Exception during grammar compilation returns structured error envelope."""
        from unittest.mock import patch

        # Patch GBNFCompiler.compile_schema to raise an unexpected exception
        with patch(
            "octave_mcp.mcp.compile_grammar.GBNFCompiler.compile_schema",
            side_effect=RuntimeError("Unexpected compiler internal error"),
        ):
            result = await tool.execute(schema="SKILL")

        # Must return structured error dict, not raise
        assert isinstance(result, dict)
        assert result["status"] == "error"
        assert "errors" in result
        assert len(result["errors"]) > 0

    @pytest.mark.asyncio
    async def test_json_schema_conversion_exception_returns_structured_error(self, tool):
        """Exception during _gbnf_to_json_schema returns structured error envelope."""
        from unittest.mock import patch

        with patch(
            "octave_mcp.mcp.compile_grammar._gbnf_to_json_schema",
            side_effect=RuntimeError("Unexpected JSON schema conversion error"),
        ):
            result = await tool.execute(schema="SKILL", format="json_schema")

        assert isinstance(result, dict)
        assert result["status"] == "error"
        assert "errors" in result
        assert len(result["errors"]) > 0

    @pytest.mark.asyncio
    async def test_load_schema_exception_returns_structured_error(self, tool):
        """Exception during load_schema_by_name returns structured error envelope."""
        from unittest.mock import patch

        with patch(
            "octave_mcp.mcp.compile_grammar.load_schema_by_name",
            side_effect=OSError("Disk read failure"),
        ):
            result = await tool.execute(schema="SKILL")

        assert isinstance(result, dict)
        assert result["status"] == "error"
        assert "errors" in result
        assert len(result["errors"]) > 0

    @pytest.mark.asyncio
    async def test_error_envelope_has_required_fields(self, tool):
        """All error responses include status, errors, and validation_status fields."""
        result = await tool.execute(schema="NONEXISTENT_SCHEMA_XYZ")

        assert result["status"] == "error"
        assert "errors" in result
        assert "validation_status" in result
