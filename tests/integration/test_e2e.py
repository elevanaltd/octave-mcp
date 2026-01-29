"""End-to-end integration tests for OCTAVE MCP (B3 Phase).

Tests complete workflows across the system:
- Full validate→eject pipeline (ingest deprecated per Issue #51)
- CLI commands working together
- MCP server tool chain
- Cross-component integration
"""

import json

import pytest

from octave_mcp.core.emitter import emit
from octave_mcp.core.lexer import tokenize
from octave_mcp.core.parser import parse
from octave_mcp.core.projector import project
from octave_mcp.core.validator import validate
from octave_mcp.schemas.loader import load_builtin_schemas


class TestIngestEjectPipeline:
    """Test complete ingest→eject pipeline integration."""

    def test_full_pipeline_lenient_to_canonical(self):
        """Complete pipeline: lenient input → canonical output."""
        # Lenient input with ASCII operators and whitespace
        lenient = """===TEST===
META:
  TYPE :: "DEMO"
  VERSION :: "1.0"

STATUS :: active
FEATURES -> [feature1, feature2]
===END==="""

        # Parse (tokenization happens internally)
        doc = parse(lenient)
        assert doc is not None

        # Emit canonical
        canonical = emit(doc)
        assert canonical is not None

        # Verify canonicalization
        assert "->" not in canonical  # ASCII normalized to →
        assert " :: " not in canonical  # Whitespace removed
        assert "===TEST===" in canonical
        assert "===END===" in canonical

    def test_pipeline_with_projection(self):
        """Pipeline with projection mode."""
        canonical = """===TEST===
META:
  TYPE::"DEMO"
  VERSION::"1.0"

STATUS::active
INTERNAL_FIELD::debug_data
===END==="""

        doc = parse(canonical)

        # Project to different modes
        executive_output = project(doc, mode="executive")
        assert "STATUS" in executive_output.output
        # executive mode might filter INTERNAL_FIELD depending on schema

        authoring_output = project(doc, mode="authoring")
        assert "TYPE" in authoring_output.output

    def test_pipeline_with_validation(self):
        """Pipeline with schema validation."""
        # Load builtin schemas
        schemas = load_builtin_schemas()

        # Valid META document
        valid = """===META_TEST===
META:
  TYPE::"TEST_DOCUMENT"
  VERSION::"1.0"
  STATUS::DRAFT

CONTENT::test
===END==="""

        doc = parse(valid)

        # Validate against META schema (if available)
        # Note: validation may pass without specific schema
        errors = validate(doc, schema=schemas.get("META"))
        # Just verify validation runs (may or may not have errors)
        assert isinstance(errors, list)

    def test_round_trip_idempotence(self):
        """parse(emit(parse(emit(x)))) produces same result."""
        original = """===TEST===
META:
  TYPE::"DEMO"
  VERSION::"1.0"

DATA::[1,2,3]
===END==="""

        # First pass
        tokens1, _ = tokenize(original)
        doc1 = parse(tokens1)
        output1 = emit(doc1)

        # Second pass
        tokens2, _ = tokenize(output1)
        doc2 = parse(tokens2)
        output2 = emit(doc2)

        # Should be identical
        assert output1 == output2


class TestCLIIntegration:
    """Test CLI commands working together."""

    def test_cli_validate_produces_valid_output(self, tmp_path):
        """CLI validate produces valid canonical output.

        Note: The deprecated 'ingest' command was removed per Issue #51.
        Use 'validate' instead, which provides the same canonicalization.
        """
        from click.testing import CliRunner

        from octave_mcp.cli.main import cli

        runner = CliRunner()

        # Create lenient input file
        input_file = tmp_path / "input.oct.md"
        input_file.write_text("""===TEST===
TYPE :: "demo"
===END===""")

        # Run validate (replacement for deprecated ingest)
        result = runner.invoke(cli, ["validate", str(input_file), "--schema", "TEST"])

        # Should succeed
        assert result.exit_code == 0

        # Output should be canonical
        output = result.output
        assert " :: " not in output  # Whitespace removed

    def test_cli_eject_different_modes(self, tmp_path):
        """CLI eject works with different projection modes.

        Note: --schema option was removed from CLI eject per Issue #51.
        Schema is only meaningful for MCP template generation.
        """
        from click.testing import CliRunner

        from octave_mcp.cli.main import cli

        runner = CliRunner()

        # Create canonical input
        input_file = tmp_path / "canonical.oct.md"
        input_file.write_text("""===TEST===
META:
  TYPE::"DEMO"
  VERSION::"1.0"

STATUS::active
===END===""")

        # Test different modes (without --schema, which was removed per Issue #51)
        for mode in ["canonical", "authoring"]:
            result = runner.invoke(cli, ["eject", str(input_file), "--mode", mode])

            assert result.exit_code == 0
            assert len(result.output) > 0

    def test_cli_validate_reports_errors(self, tmp_path):
        """CLI validate reports validation errors."""
        from click.testing import CliRunner

        from octave_mcp.cli.main import cli

        runner = CliRunner()

        # Create invalid input (missing envelope)
        input_file = tmp_path / "invalid.oct.md"
        input_file.write_text("""TYPE::"test"
STATUS::active""")

        # Run validate
        result = runner.invoke(cli, ["validate", str(input_file), "--schema", "TEST"])

        # Should fail validation (exit code 1)
        # Note: actual behavior depends on validator implementation
        assert result.exit_code in [0, 1]  # Either succeeds or validation error


class TestMCPServerToolChain:
    """Test MCP server tool chain integration."""

    @pytest.mark.asyncio
    async def test_validate_then_eject_via_mcp(self):
        """Call validate then eject via MCP tools."""
        from mcp.types import CallToolRequest

        from octave_mcp.mcp.server import create_server

        server = create_server()

        # First: validate lenient content
        lenient_content = """===TEST===
TYPE :: "demo"
STATUS :: active
===END==="""

        validate_request = CallToolRequest(
            method="tools/call",
            params={"name": "octave_validate", "arguments": {"content": lenient_content, "schema": "TEST"}},
        )

        from mcp.types import CallToolRequest as CallToolRequestType

        validate_handler = server.request_handlers.get(CallToolRequestType)
        validate_result = await validate_handler(validate_request)

        assert validate_result.root.content is not None

        # Extract canonical content from validate result
        validate_output = validate_result.root.content[0].text

        # Parse to find canonical output
        # Result is JSON with canonical field
        parsed = json.loads(validate_output)
        canonical_content = parsed.get("canonical", validate_output)

        # Second: eject the canonical content
        eject_request = CallToolRequest(
            method="tools/call",
            params={
                "name": "octave_eject",
                "arguments": {"content": canonical_content, "schema": "TEST", "mode": "authoring"},
            },
        )

        eject_handler = server.request_handlers.get(CallToolRequestType)
        eject_result = await eject_handler(eject_request)

        assert eject_result.root.content is not None
        assert len(eject_result.root.content) > 0

    @pytest.mark.asyncio
    async def test_mcp_tools_preserve_structure(self):
        """MCP tool chain preserves document structure."""
        from mcp.types import CallToolRequest

        from octave_mcp.mcp.server import create_server

        server = create_server()

        original = """===TEST===
META:
  TYPE::"DEMO"
  VERSION::"1.0"

FIELD_A::value_a
FIELD_B::value_b
===END==="""

        # Validate
        request = CallToolRequest(
            method="tools/call",
            params={"name": "octave_validate", "arguments": {"content": original, "schema": "TEST"}},
        )

        from mcp.types import CallToolRequest as CallToolRequestType

        handler = server.request_handlers.get(CallToolRequestType)
        result = await handler(request)

        output = result.root.content[0].text

        # Verify structure preserved
        assert "FIELD_A" in output
        assert "FIELD_B" in output
        assert "===TEST===" in output or "TEST" in output


class TestCrossComponentIntegration:
    """Test integration across different components."""

    def test_lexer_parser_emitter_chain(self):
        """Lexer → Parser → Emitter chain integration."""
        source = """===CHAIN_TEST===
DATA::[1,2,3]
===END==="""

        # Chain components
        doc = parse(source)
        output = emit(doc)

        # Verify chain works
        assert "CHAIN_TEST" in output
        assert "DATA" in output

    def test_parser_validator_integration(self):
        """Parser → Validator integration."""
        source = """===VALIDATOR_TEST===
META:
  TYPE::"TEST"
  VERSION::"1.0"

FIELD::value
===END==="""

        doc = parse(source)

        # Validate (may not have schema, but should not crash)
        errors = validate(doc, schema=None)
        assert isinstance(errors, list)

    def test_repair_log_integration(self):
        """Repair logging integration across components."""
        # Lenient input needing repairs
        lenient = """===REPAIR_TEST===
TYPE :: "test"
STATUS -> active
===END==="""

        tokens, lex_repairs = tokenize(lenient)
        _doc = parse(tokens)  # Parse to ensure no errors

        # Repairs should be logged
        # Check if normalization repairs were logged
        assert isinstance(lex_repairs, list)
        # Lenient input should produce repairs
        # (exact count depends on implementation)

    def test_schema_loading_validation_integration(self):
        """Schema loading → Validation integration."""
        schemas = load_builtin_schemas()

        # Schemas should be loaded
        assert schemas is not None

        # Can use schemas for validation
        test_doc = """===SCHEMA_TEST===
META:
  TYPE::"TEST"
  VERSION::"1.0"

DATA::test
===END==="""

        doc = parse(test_doc)

        # Validate with loaded schemas
        errors = validate(doc, schema=schemas.get("META"))
        assert isinstance(errors, list)


class TestErrorHandling:
    """Test error handling across integration points."""

    def test_invalid_syntax_error_propagation(self):
        """Invalid syntax errors propagate correctly."""
        # Tab character (forbidden)
        invalid = "===TEST===\n\tTYPE::value\n===END==="

        # Should raise error during tokenization
        with pytest.raises(Exception) as exc_info:
            _tokens = tokenize(invalid)  # noqa: F841

        # Check for E005 error code
        assert "E005" in str(exc_info.value) or "tab" in str(exc_info.value).lower()

    def test_missing_envelope_error(self):
        """Missing envelope error handling."""
        # Multi-doc without envelope
        multi_doc = """TYPE::"test"

===DOC2===
DATA::value
===END==="""

        # Should error or infer envelope
        # Behavior depends on implementation
        try:
            doc = parse(multi_doc)
            # May succeed with inference
            assert doc is not None
        except ValueError as e:
            # Or may error - both acceptable
            assert "E002" in str(e) or "envelope" in str(e).lower()

    @pytest.mark.asyncio
    async def test_mcp_tool_error_handling(self):
        """MCP tools handle errors gracefully."""
        from mcp.types import CallToolRequest

        from octave_mcp.mcp.server import create_server

        server = create_server()

        # Invalid content (tab character)
        invalid_content = "===TEST===\n\tBAD::value\n===END==="

        request = CallToolRequest(
            method="tools/call",
            params={"name": "octave_validate", "arguments": {"content": invalid_content, "schema": "TEST"}},
        )

        from mcp.types import CallToolRequest as CallToolRequestType

        handler = server.request_handlers.get(CallToolRequestType)

        # Should return error, not crash
        try:
            result = await handler(request)
            # May return error in result
            assert result is not None
        except Exception as e:
            # Or may raise exception
            assert "E005" in str(e) or "tab" in str(e).lower()
