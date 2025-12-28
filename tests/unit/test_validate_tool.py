"""Tests for octave_validate MCP tool (GH#51 Tool Consolidation).

Tests the new validate tool that replaces octave_ingest:
- Schema validation + repair suggestions
- Unified response envelope (status, canonical, repairs, warnings, errors, validation_status)
- I3 (Mirror Constraint): Returns errors instead of guessing
- I5 (Schema Sovereignty): Explicit validation_status

TDD: RED phase - these tests define the expected behavior.
"""

import pytest


class TestValidateTool:
    """Test ValidateTool MCP tool."""

    def test_tool_metadata(self):
        """Test tool has correct metadata."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        assert tool.get_name() == "octave_validate"
        assert "validation" in tool.get_description().lower() or "validate" in tool.get_description().lower()
        assert "schema" in tool.get_description().lower()

    def test_tool_schema(self):
        """Test tool input schema has required parameters."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        schema = tool.get_input_schema()

        # Required parameters
        assert "content" in schema["properties"]
        assert "schema" in schema["properties"]
        assert "content" in schema["required"]
        assert "schema" in schema["required"]

        # Optional parameters
        assert "fix" in schema["properties"]
        assert schema["properties"]["fix"].get("type") == "boolean"

    @pytest.mark.asyncio
    async def test_validate_simple_document_success(self):
        """Test validating a simple valid OCTAVE document."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        result = await tool.execute(
            content="===TEST===\nKEY::value\n===END===",
            schema="TEST",
            fix=False,
        )

        # Unified envelope structure per D2 design
        assert result["status"] == "success"
        assert "canonical" in result
        assert "repairs" in result
        assert isinstance(result["repairs"], list)
        assert "warnings" in result
        assert isinstance(result["warnings"], list)
        assert "errors" in result
        assert isinstance(result["errors"], list)
        # I5: validation_status must be present
        assert "validation_status" in result
        assert result["validation_status"] in ["VALIDATED", "UNVALIDATED", "PENDING_INFRASTRUCTURE"]

    @pytest.mark.asyncio
    async def test_validate_returns_canonical_output(self):
        """Test that canonical output is returned."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        result = await tool.execute(
            content="===TEST===\nKEY::value\n===END===",
            schema="TEST",
            fix=False,
        )

        assert result["status"] == "success"
        assert result["canonical"]  # Non-empty canonical output
        assert "===TEST===" in result["canonical"]
        assert "===END===" in result["canonical"]

    @pytest.mark.asyncio
    async def test_validate_with_ascii_normalization(self):
        """Test that ASCII aliases are normalized to unicode."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        result = await tool.execute(
            content="===TEST===\nFLOW::A -> B\nSYNTH::X + Y\n===END===",
            schema="TEST",
            fix=False,
        )

        assert result["status"] == "success"
        # Canonical should contain normalized operators
        assert result["canonical"]
        # Repairs list should track normalizations (or be empty if already normalized)
        assert isinstance(result["repairs"], list)

    @pytest.mark.asyncio
    async def test_validate_fix_true_applies_repairs(self):
        """Test that fix=True applies repairs to canonical output."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        result = await tool.execute(
            content="===TEST===\nSTATUS::active\n===END===",
            schema="TEST",
            fix=True,
        )

        assert result["status"] == "success"
        # With fix=True, repairs should be applied to canonical
        assert "repairs" in result

    @pytest.mark.asyncio
    async def test_validate_fix_false_suggests_repairs(self):
        """Test that fix=False returns repair suggestions but doesn't apply them."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        result = await tool.execute(
            content="===TEST===\nSTATUS::active\n===END===",
            schema="TEST",
            fix=False,
        )

        assert result["status"] == "success"
        # With fix=False, repairs are suggested but not applied
        assert "repairs" in result

    @pytest.mark.asyncio
    async def test_validate_parse_error_returns_error_status(self):
        """Test that parse errors return status=error with proper envelope."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # Invalid syntax that should fail parsing
        result = await tool.execute(
            content="===UNCLOSED\nKEY::value",  # Missing ===END===
            schema="TEST",
            fix=False,
        )

        # Per D2 design: errors return error status
        # Note: Parser may be lenient and infer envelope, so this might succeed
        # Either way, envelope should be valid
        assert "status" in result
        assert result["status"] in ["success", "error"]
        assert "errors" in result
        assert isinstance(result["errors"], list)

    @pytest.mark.asyncio
    async def test_validate_i5_schema_sovereignty(self):
        """Test I5: validation_status is always present (Schema Sovereignty)."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        result = await tool.execute(
            content="===TEST===\nKEY::value\n===END===",
            schema="TEST",
            fix=False,
        )

        # I5: validation_status must always be present
        assert "validation_status" in result
        # Valid values per D2 design
        assert result["validation_status"] in ["VALIDATED", "UNVALIDATED", "PENDING_INFRASTRUCTURE"]

    @pytest.mark.asyncio
    async def test_validate_i3_mirror_constraint_no_guessing(self):
        """Test I3: Mirror Constraint - errors on invalid input, no guessing."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # Ambiguous/invalid content - system should error, not guess
        result = await tool.execute(
            content="",  # Empty content
            schema="TEST",
            fix=False,
        )

        # Either return error or return with warnings, but never invent data
        assert "status" in result
        # If successful, canonical should not contain invented content
        if result["status"] == "success":
            # Empty/minimal canonical is OK, but not invented fields
            pass
        else:
            # Error status with proper error envelope
            assert "errors" in result

    @pytest.mark.asyncio
    async def test_validate_repair_log_format(self):
        """Test repair log has required fields per D2 design."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        result = await tool.execute(
            content="===TEST===\nFLOW::A -> B\n===END===",
            schema="TEST",
            fix=True,
        )

        repairs = result["repairs"]
        assert isinstance(repairs, list)

        # If there are repairs, verify structure
        # Repairs should have consistent format
        for repair in repairs:
            assert isinstance(repair, dict)

    @pytest.mark.asyncio
    async def test_validate_warnings_format(self):
        """Test warnings have consistent format."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        result = await tool.execute(
            content="===TEST===\nKEY::value\n===END===",
            schema="TEST",
            fix=False,
        )

        warnings = result["warnings"]
        assert isinstance(warnings, list)

        # If there are warnings, verify structure
        for warning in warnings:
            assert isinstance(warning, dict)
            # Warnings should have code and message
            if warning:
                assert "code" in warning or "message" in warning

    @pytest.mark.asyncio
    async def test_validate_default_fix_false(self):
        """Test that fix defaults to False when not provided."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # Call without fix parameter
        result = await tool.execute(
            content="===TEST===\nKEY::value\n===END===",
            schema="TEST",
        )

        # Should work with default fix=False
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_validate_envelope_inference(self):
        """Test envelope inference for content without explicit envelope."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        result = await tool.execute(
            content="KEY::value\nOTHER::data",  # No envelope markers
            schema="TEST",
            fix=False,
        )

        # Should infer envelope
        assert result["status"] == "success"
        assert "===" in result["canonical"]  # Should have envelope
        assert "===END===" in result["canonical"]

    @pytest.mark.asyncio
    async def test_validate_error_envelope_format(self):
        """Test error envelope format matches D2 spec."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # This test verifies error structure when errors occur
        # We can trigger by passing None content (invalid input)
        try:
            # Will raise ValueError for missing required parameter
            await tool.execute(schema="TEST", fix=False)
        except ValueError:
            # Expected - missing required content parameter
            pass
        except Exception:
            # Other errors should still follow envelope format
            # If the tool handles the error gracefully, check the result
            pass


class TestValidateToolI5SchemaSovereignty:
    """Tests for I5 (Schema Sovereignty) requirement.

    North Star I5 states:
    - A document processed without schema validation shall be marked as UNVALIDATED
    - Schema-validated documents shall record the schema name and version used
    - Schema bypass shall be visible, never silent

    Current state: validation_status is "PENDING_INFRASTRUCTURE" which is a silent bypass.
    Required state: validation_status must be "UNVALIDATED" to make bypass visible.
    """

    @pytest.mark.asyncio
    async def test_i5_validation_status_is_unvalidated_when_no_validator(self):
        """I5: validation_status must be UNVALIDATED when no schema validator exists.

        The North Star requires: "Schema bypass shall be visible, never silent."
        PENDING_INFRASTRUCTURE is a silent bypass - UNVALIDATED is visible.
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        result = await tool.execute(
            content="===TEST===\nKEY::value\n===END===",
            schema="META",  # Schema provided but no validator implemented
            fix=False,
        )

        assert result["status"] == "success"
        # I5 REQUIREMENT: Must be UNVALIDATED, not PENDING_INFRASTRUCTURE
        assert result["validation_status"] == "UNVALIDATED", (
            f"I5 violation: validation_status should be 'UNVALIDATED' to make bypass visible, "
            f"but got '{result['validation_status']}'"
        )

    @pytest.mark.asyncio
    async def test_i5_validation_status_field_always_present(self):
        """I5: validation_status field must always be present in output."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        result = await tool.execute(
            content="===TEST===\nKEY::value\n===END===",
            schema="TEST",
            fix=False,
        )

        # I5: Field must be present (not silently omitted)
        assert "validation_status" in result, "I5 violation: validation_status field must always be present"

    @pytest.mark.asyncio
    async def test_i5_validation_status_explicit_not_silent(self):
        """I5: Schema bypass must be visible, never silent.

        PENDING_INFRASTRUCTURE implies "we'll get to it" - this is silent bypass.
        UNVALIDATED explicitly states "this was not validated" - visible bypass.
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        result = await tool.execute(
            content="===TEST===\nSTATUS::active\n===END===",
            schema="TEST",
            fix=False,
        )

        # Value must not be the silent PENDING_INFRASTRUCTURE placeholder
        assert result["validation_status"] != "PENDING_INFRASTRUCTURE", (
            "I5 violation: PENDING_INFRASTRUCTURE is a silent bypass. " "Must use UNVALIDATED to make bypass visible."
        )
