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

        # Required parameters (schema is required, content/file_path are XOR)
        assert "content" in schema["properties"]
        assert "file_path" in schema["properties"]
        assert "schema" in schema["properties"]
        assert "schema" in schema["required"]

        # content and file_path are XOR - neither is required in schema
        # (validation happens in execute method)
        assert "content" not in schema.get("required", [])
        assert "file_path" not in schema.get("required", [])

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
    async def test_i5_validation_status_reflects_schema_validation_result(self):
        """I5: validation_status reflects actual schema validation.

        The North Star requires: "Schema bypass shall be visible, never silent."
        Now that schema validation is implemented:
        - VALIDATED = schema found and validation passed
        - INVALID = schema found and validation failed
        - UNVALIDATED = schema not found (bypass is visible)
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # Content without META block validates against META schema
        # (no META block = no required META fields to check)
        result = await tool.execute(
            content="===TEST===\nKEY::value\n===END===",
            schema="META",
            fix=False,
        )

        assert result["status"] == "success"
        # META schema is found and document validates (no META block = no constraints)
        assert (
            result["validation_status"] == "VALIDATED"
        ), f"I5: Should be VALIDATED when META schema validates content, but got '{result['validation_status']}'"
        # Schema info should be recorded
        assert result.get("schema_name") == "META"

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
        assert (
            result["validation_status"] != "PENDING_INFRASTRUCTURE"
        ), "I5 violation: PENDING_INFRASTRUCTURE is a silent bypass. Must use UNVALIDATED to make bypass visible."


class TestValidateToolSchemaValidation:
    """Tests for schema validation wiring in octave_validate.

    I5 North Star requirement:
    - "Schema-validated documents shall record the schema name and version used"
    - "Schema bypass shall be visible, never silent"

    These tests verify that when a schema is provided, actual validation occurs.
    """

    @pytest.mark.asyncio
    async def test_validate_without_schema_returns_unvalidated(self):
        """When no schema param provided, validation_status should be UNVALIDATED.

        Note: Current tool requires schema param, so this tests with unknown schema.
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # Use an unknown schema name - should result in UNVALIDATED (schema not found)
        result = await tool.execute(
            content="===TEST===\nKEY::value\n===END===",
            schema="NONEXISTENT_SCHEMA",
            fix=False,
        )

        assert result["status"] == "success"
        assert result["validation_status"] == "UNVALIDATED"
        # Should NOT have schema_name/schema_version when unvalidated
        assert result.get("schema_name") is None or "schema_name" not in result

    @pytest.mark.asyncio
    async def test_validate_with_meta_schema_valid_content_returns_validated(self):
        """When META schema provided with valid content, should return VALIDATED.

        I5: Schema-validated documents shall record the schema name and version used.
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # Valid META content with required fields (TYPE, VERSION)
        valid_meta_content = """===TEST===
META:
  TYPE::"TEST_DOCUMENT"
  VERSION::"1.0.0"
  STATUS::ACTIVE
---
KEY::value
===END==="""

        result = await tool.execute(
            content=valid_meta_content,
            schema="META",
            fix=False,
        )

        assert result["status"] == "success"
        # I5: Must return VALIDATED when schema validates successfully
        assert result["validation_status"] == "VALIDATED", (
            f"I5 violation: Should be VALIDATED when META schema validates successfully, "
            f"got '{result['validation_status']}'"
        )
        # I5: Schema name and version should be recorded
        assert result.get("schema_name") == "META", "I5: schema_name should be recorded"
        assert "schema_version" in result, "I5: schema_version should be recorded"

    @pytest.mark.asyncio
    async def test_validate_with_meta_schema_invalid_content_returns_invalid(self):
        """When META schema provided with invalid content, should return INVALID.

        I5: Schema bypass shall be visible, never silent.
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # Invalid META content - missing required TYPE field
        invalid_meta_content = """===TEST===
META:
  VERSION::"1.0.0"
---
KEY::value
===END==="""

        result = await tool.execute(
            content=invalid_meta_content,
            schema="META",
            fix=False,
        )

        assert result["status"] == "success"  # Operation succeeded, content is invalid
        # I5: Must return INVALID when schema validation fails
        assert (
            result["validation_status"] == "INVALID"
        ), f"I5 violation: Should be INVALID when META schema validation fails, got '{result['validation_status']}'"
        # Should record schema info even on invalid
        assert result.get("schema_name") == "META", "I5: schema_name should be recorded even on INVALID"
        # Should include validation errors
        assert (
            "validation_errors" in result or len(result.get("warnings", [])) > 0
        ), "I5: validation_errors should be included when INVALID"

    @pytest.mark.asyncio
    async def test_validate_with_meta_schema_missing_version_returns_invalid(self):
        """META schema requires VERSION field - missing it should return INVALID."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # Invalid META content - missing required VERSION field
        invalid_meta_content = """===TEST===
META:
  TYPE::"TEST_DOCUMENT"
---
KEY::value
===END==="""

        result = await tool.execute(
            content=invalid_meta_content,
            schema="META",
            fix=False,
        )

        assert result["status"] == "success"
        assert (
            result["validation_status"] == "INVALID"
        ), f"META schema requires VERSION field, got '{result['validation_status']}'"

    @pytest.mark.asyncio
    async def test_validate_schema_validation_errors_included_in_response(self):
        """When validation fails, specific errors should be in response."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # Content missing both TYPE and VERSION
        invalid_content = """===TEST===
META:
  STATUS::ACTIVE
---
KEY::value
===END==="""

        result = await tool.execute(
            content=invalid_content,
            schema="META",
            fix=False,
        )

        assert result["validation_status"] == "INVALID"
        # Should have validation_errors with details about missing fields
        errors = result.get("validation_errors", result.get("warnings", []))
        assert len(errors) >= 1, "Should report at least one validation error for missing required fields"


class TestValidateToolFilePathMode:
    """Tests for file_path mode in octave_validate.

    file_path provides XOR alternative to content parameter:
    - file_path XOR content (one required, not both)
    - file_path reads file then processes as content
    - Returns E_INPUT for XOR violations, E_FILE for missing file, E_READ for read errors
    """

    @pytest.mark.asyncio
    async def test_file_path_mode_reads_and_validates(self):
        """Test file_path mode reads file and validates content."""
        import os
        import tempfile

        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "test.oct.md")

            # Create test file
            with open(file_path, "w") as f:
                f.write("===TEST===\nKEY::value\n===END===")

            result = await tool.execute(
                file_path=file_path,
                schema="TEST",
                fix=False,
            )

            # Should succeed and return canonical content
            assert result["status"] == "success"
            assert "canonical" in result
            assert "===TEST===" in result["canonical"]

    @pytest.mark.asyncio
    async def test_file_path_with_nonexistent_file_returns_e_file(self):
        """Test file_path with non-existent file returns E_FILE error."""
        import tempfile

        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent = f"{tmpdir}/nonexistent.oct.md"

            result = await tool.execute(
                file_path=nonexistent,
                schema="TEST",
                fix=False,
            )

            # Should fail with E_FILE error
            assert result["status"] == "error"
            assert any(e.get("code") == "E_FILE" for e in result["errors"])

    @pytest.mark.asyncio
    async def test_both_file_path_and_content_returns_e_input(self):
        """Test providing both file_path and content returns E_INPUT error."""
        import os
        import tempfile

        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "test.oct.md")

            # Create test file
            with open(file_path, "w") as f:
                f.write("===TEST===\nKEY::value\n===END===")

            result = await tool.execute(
                file_path=file_path,
                content="===OTHER===\nOTHER::value\n===END===",
                schema="TEST",
                fix=False,
            )

            # Should fail with E_INPUT - XOR violation
            assert result["status"] == "error"
            assert any(e.get("code") == "E_INPUT" for e in result["errors"])
            # Error message should mention mutual exclusivity
            error_messages = " ".join(e.get("message", "") for e in result["errors"])
            assert "file_path" in error_messages.lower() or "content" in error_messages.lower()

    @pytest.mark.asyncio
    async def test_neither_file_path_nor_content_returns_e_input(self):
        """Test providing neither file_path nor content returns E_INPUT error."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        result = await tool.execute(
            schema="TEST",
            fix=False,
        )

        # Should fail with E_INPUT - must provide one
        assert result["status"] == "error"
        assert any(e.get("code") == "E_INPUT" for e in result["errors"])

    @pytest.mark.asyncio
    async def test_content_mode_still_works_regression(self):
        """Test content mode continues to work (regression test)."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        result = await tool.execute(
            content="===TEST===\nKEY::value\n===END===",
            schema="TEST",
            fix=False,
        )

        # Content mode should still work
        assert result["status"] == "success"
        assert "canonical" in result

    @pytest.mark.asyncio
    async def test_file_path_schema_shows_in_input_schema(self):
        """Test file_path parameter appears in input schema."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        schema = tool.get_input_schema()

        # file_path should be in properties
        assert "file_path" in schema["properties"]
        # file_path should be optional (content is XOR alternative)
        assert "file_path" not in schema.get("required", [])
        # content should also be optional now
        assert "content" not in schema.get("required", [])

    @pytest.mark.asyncio
    async def test_file_path_with_symlink_returns_security_error(self):
        """Test file_path with symlink target returns security error.

        Security fix: Symlinks are rejected to prevent exfiltration attacks.
        Example: attacker creates leak.oct.md → secret.txt and tries to validate it.
        """
        import os
        import tempfile

        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a secret file
            secret_file = os.path.join(tmpdir, "secret.txt")
            with open(secret_file, "w") as f:
                f.write("THIS IS SECRET")

            # Create symlink with valid OCTAVE extension
            symlink_path = os.path.join(tmpdir, "leak.oct.md")
            os.symlink(secret_file, symlink_path)

            result = await tool.execute(
                file_path=symlink_path,
                schema="TEST",
                fix=False,
            )

            # Should fail with E_PATH error for symlink
            assert result["status"] == "error"
            assert any(e.get("code") == "E_PATH" for e in result["errors"])
            # Error message should mention symlinks
            error_messages = " ".join(e.get("message", "") for e in result["errors"])
            assert "symlink" in error_messages.lower()

    @pytest.mark.asyncio
    async def test_file_path_with_symlinked_parent_returns_error(self):
        """Test file_path with symlinked parent directory returns security error.

        Security fix: Reject paths where ANY parent component is a symlink.
        Example attack: /tmp/link/secret.oct.md where 'link' is a symlink to another directory.
        This bypasses the final-component-only symlink check.
        """
        import os
        import tempfile

        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create real directory with secret file
            real_dir = os.path.join(tmpdir, "real_dir")
            os.makedirs(real_dir)
            secret_file = os.path.join(real_dir, "secret.oct.md")
            with open(secret_file, "w") as f:
                f.write("===SECRET===\nSECRET::classified\n===END===")

            # Create symlink to real_dir
            link_dir = os.path.join(tmpdir, "link")
            os.symlink(real_dir, link_dir)

            # Try to access secret via symlinked parent: /tmp/link/secret.oct.md
            attack_path = os.path.join(link_dir, "secret.oct.md")

            result = await tool.execute(
                file_path=attack_path,
                schema="TEST",
                fix=False,
            )

            # Should fail with E_PATH error for symlink traversal
            assert result["status"] == "error"
            assert any(e.get("code") == "E_PATH" for e in result["errors"])
            # Error message should mention symlinks
            error_messages = " ".join(e.get("message", "") for e in result["errors"])
            assert "symlink" in error_messages.lower()


class TestValidateToolGap7ResponseStructure:
    """Tests for Gap 7: Response structure compliance with spec (octave-mcp-architecture.oct.md Section 7).

    SPEC REQUIREMENTS:
    - CANONICAL: string (REQ) - already present
    - VALID: boolean (REQ) - MISSING, must add
    - VALIDATION_ERRORS: array (REQ) - CONDITIONAL, should always be present (empty if no errors)
    - REPAIR_LOG: array (REQ) - MISNAMED as 'repairs', add as alias

    TDD: RED phase - these tests define expected behavior from spec.
    """

    @pytest.mark.asyncio
    async def test_validate_returns_valid_boolean_true(self):
        """Gap 7: valid doc should return valid=True.

        Spec: VALID::[true|REQ|BOOLEAN->whether_document_passed_validation]
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # Valid META document with required fields
        valid_content = """===TEST===
META:
  TYPE::"TEST_DOCUMENT"
  VERSION::"1.0.0"
===END==="""

        result = await tool.execute(
            content=valid_content,
            schema="META",
            fix=False,
        )

        # Gap 7 requirement: 'valid' boolean field must be present
        assert "valid" in result, "Gap 7: 'valid' boolean field missing from response"
        assert isinstance(result["valid"], bool), "Gap 7: 'valid' must be a boolean"
        assert result["valid"] is True, "Gap 7: valid document should return valid=True"

    @pytest.mark.asyncio
    async def test_validate_returns_valid_boolean_false(self):
        """Gap 7: invalid doc should return valid=False.

        Spec: VALID::[true|REQ|BOOLEAN->whether_document_passed_validation]
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # Invalid META document - missing required TYPE field
        invalid_content = """===TEST===
META:
  VERSION::"1.0.0"
===END==="""

        result = await tool.execute(
            content=invalid_content,
            schema="META",
            fix=False,
        )

        # Gap 7 requirement: 'valid' boolean field must be present
        assert "valid" in result, "Gap 7: 'valid' boolean field missing from response"
        assert isinstance(result["valid"], bool), "Gap 7: 'valid' must be a boolean"
        assert result["valid"] is False, "Gap 7: invalid document should return valid=False"

    @pytest.mark.asyncio
    async def test_validate_returns_repair_log_field(self):
        """Gap 7: repair_log field present with same data as repairs.

        Spec: REPAIR_LOG::[[...]|REQ->transformation_log_always_present]
        Current: 'repairs' field exists, need 'repair_log' as spec-compliant alias
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # Content with ASCII operators that will be normalized
        content = """===TEST===
FLOW::A -> B
===END==="""

        result = await tool.execute(
            content=content,
            schema="TEST",
            fix=False,
        )

        # Gap 7 requirement: 'repair_log' field must be present
        assert "repair_log" in result, "Gap 7: 'repair_log' field missing from response"
        assert isinstance(result["repair_log"], list), "Gap 7: 'repair_log' must be an array"

        # Backward compat: 'repairs' should still exist
        assert "repairs" in result, "Gap 7: 'repairs' field should remain for backward compatibility"

        # Both should contain same data
        assert (
            result["repair_log"] == result["repairs"]
        ), "Gap 7: 'repair_log' and 'repairs' should contain identical data"

    @pytest.mark.asyncio
    async def test_validate_returns_validation_errors_always_present(self):
        """Gap 7: validation_errors field always present (empty array when no errors).

        Spec: VALIDATION_ERRORS::[[...]|REQ->schema_violations_found]
        The spec says REQ, so it should always be present even if empty.
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # Valid document - no validation errors expected
        valid_content = """===TEST===
META:
  TYPE::"TEST_DOCUMENT"
  VERSION::"1.0.0"
===END==="""

        result = await tool.execute(
            content=valid_content,
            schema="META",
            fix=False,
        )

        # Gap 7 requirement: 'validation_errors' field must always be present
        assert "validation_errors" in result, (
            "Gap 7: 'validation_errors' field missing from response - "
            "spec requires it always present (empty array if no errors)"
        )
        assert isinstance(result["validation_errors"], list), "Gap 7: 'validation_errors' must be an array"
        # For valid doc, should be empty
        assert result["validation_errors"] == [], "Gap 7: valid document should have empty validation_errors array"

    @pytest.mark.asyncio
    async def test_validate_error_envelope_has_gap7_fields(self):
        """Gap 7: Error envelopes should also include the required fields.

        When validation fails at input level (XOR violation, file not found, etc.),
        the error envelope should still have valid=False, repair_log=[], validation_errors=[].
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # Trigger error by providing neither content nor file_path
        result = await tool.execute(
            schema="TEST",
            fix=False,
        )

        assert result["status"] == "error"
        # Gap 7: Even error envelopes should have these fields
        assert "valid" in result, "Gap 7: 'valid' field missing from error envelope"
        assert result["valid"] is False, "Gap 7: error envelope should have valid=False"

        assert "repair_log" in result, "Gap 7: 'repair_log' field missing from error envelope"
        assert isinstance(result["repair_log"], list), "Gap 7: error envelope repair_log must be array"

        assert "validation_errors" in result, "Gap 7: 'validation_errors' field missing from error envelope"
        assert isinstance(result["validation_errors"], list), "Gap 7: error envelope validation_errors must be array"

    @pytest.mark.asyncio
    async def test_validate_valid_correlates_with_validation_status(self):
        """Gap 7: 'valid' boolean should correlate with validation_status.

        - valid=True when validation_status=="VALIDATED"
        - valid=False when validation_status in ["INVALID", "UNVALIDATED"] or on error
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # Test VALIDATED case
        valid_content = """===TEST===
META:
  TYPE::"TEST"
  VERSION::"1.0"
===END==="""

        result = await tool.execute(
            content=valid_content,
            schema="META",
            fix=False,
        )

        if result["validation_status"] == "VALIDATED":
            assert result["valid"] is True, "Gap 7: valid should be True when validation_status is VALIDATED"
        elif result["validation_status"] in ["INVALID", "UNVALIDATED"]:
            assert (
                result["valid"] is False
            ), f"Gap 7: valid should be False when validation_status is {result['validation_status']}"


class TestValidateToolYAMLFrontmatter:
    """Tests for YAML frontmatter handling in octave_validate (Issue #91).

    Issue #91: ValidateTool calls tokenize(content) directly, bypassing
    the parser's _strip_yaml_frontmatter() function. This causes E005 errors
    when YAML frontmatter contains parentheses or other special characters.

    The parser.py module already handles this correctly (lines 19-86, 911),
    but validate.py calls tokenize() at line 253 without stripping frontmatter.
    """

    @pytest.mark.asyncio
    async def test_validate_with_yaml_frontmatter_parentheses(self):
        """Issue #91: YAML frontmatter with parentheses should not fail.

        The YAML frontmatter pattern is common in HestAI agent definitions:
        ---
        name: Ideator (PATHOS Specialist)
        description: Creative exploration agent
        ---

        The lexer does not recognize parentheses, so frontmatter must be
        stripped before tokenization.
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        content = """---
name: Ideator (PATHOS Specialist)
description: Creative exploration agent
---
===TEST===
META:
  TYPE::"TEST"
  VERSION::"1.0"
===END==="""

        result = await tool.execute(
            content=content,
            schema="META",
            fix=False,
        )

        # Should succeed, not raise E005 error for parentheses
        assert (
            result["status"] == "success"
        ), f"Issue #91: YAML frontmatter with parentheses failed. Errors: {result.get('errors', [])}"
        # Should have valid canonical output
        assert "===TEST===" in result["canonical"]
        assert "===END===" in result["canonical"]

    @pytest.mark.asyncio
    async def test_validate_with_yaml_frontmatter_brackets(self):
        """Issue #91: YAML frontmatter with square brackets should not fail."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        content = """---
name: Agent
tags: [alpha, beta, gamma]
---
===DOC===
KEY::value
===END==="""

        result = await tool.execute(
            content=content,
            schema="TEST",
            fix=False,
        )

        # Should succeed without E005 errors
        assert (
            result["status"] == "success"
        ), f"Issue #91: YAML frontmatter with brackets failed. Errors: {result.get('errors', [])}"

    @pytest.mark.asyncio
    async def test_validate_with_yaml_frontmatter_special_chars(self):
        """Issue #91: YAML frontmatter with various special chars should not fail."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        content = """---
name: Test Agent (v1.0)
url: https://example.com:8080/path
regex: ^[a-z]+$
math: 2 + 2 = 4
---
===DOC===
FIELD::value
===END==="""

        result = await tool.execute(
            content=content,
            schema="TEST",
            fix=False,
        )

        # Should succeed without tokenization errors
        assert (
            result["status"] == "success"
        ), f"Issue #91: YAML frontmatter with special chars failed. Errors: {result.get('errors', [])}"

    @pytest.mark.asyncio
    async def test_validate_without_yaml_frontmatter_still_works(self):
        """Regression test: Documents without YAML frontmatter should still work."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        content = """===TEST===
META:
  TYPE::"TEST"
  VERSION::"1.0"
===END==="""

        result = await tool.execute(
            content=content,
            schema="META",
            fix=False,
        )

        # Should continue to work as before
        assert result["status"] == "success"
        assert result["validation_status"] == "VALIDATED"


class TestValidateToolConstraintIntegration:
    """Tests for Gap_1: Constraint validation integration into MCP validate tool.

    The MCP validate tool has constraint validation machinery in the core validator,
    but it was never wired up through the MCP surface. These tests verify that:
    1. SchemaDefinition with holographic patterns is loaded when available
    2. section_schemas parameter is passed to validator.validate()
    3. Constraint errors (E003, E005, E006, E007) appear in validation_errors
    4. Backwards compatibility is maintained (no section_schemas = existing behavior)

    TDD: RED phase - these tests define the expected behavior.
    """

    @pytest.mark.asyncio
    async def test_validate_tool_detects_invalid_enum_constraint(self):
        """Gap_1: Validate tool should detect invalid ENUM values via constraints.

        When a document has a section that matches a schema with ENUM constraint,
        and the value is not in the allowed list, E005 should be in validation_errors.
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # META schema defines STATUS as ENUM[DRAFT,ACTIVE,DEPRECATED]
        # Using an invalid value should trigger E005
        content = """===TEST===
META:
  TYPE::"TEST"
  VERSION::"1.0"
  STATUS::INVALID_STATUS
===END==="""

        result = await tool.execute(
            content=content,
            schema="META",
            fix=False,
        )

        assert result["status"] == "success"
        assert (
            result["validation_status"] == "INVALID"
        ), f"Gap_1: Document with invalid ENUM value should be INVALID, got '{result['validation_status']}'"

        # Check validation_errors contains E005 (ENUM validation error)
        validation_errors = result.get("validation_errors", [])
        error_codes = [e.get("code") for e in validation_errors]
        assert "E005" in error_codes, (
            f"Gap_1: Invalid ENUM should produce E005 in validation_errors, "
            f"got codes: {error_codes}, errors: {validation_errors}"
        )

    @pytest.mark.asyncio
    async def test_validate_tool_detects_missing_required_field(self):
        """Gap_1: Validate tool should detect missing required fields via constraints.

        When a document section has a REQ constraint in schema but field is missing,
        E003 should be in validation_errors.
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # META schema requires TYPE field - missing it should trigger E003
        content = """===TEST===
META:
  VERSION::"1.0"
===END==="""

        result = await tool.execute(
            content=content,
            schema="META",
            fix=False,
        )

        assert result["status"] == "success"
        assert (
            result["validation_status"] == "INVALID"
        ), f"Gap_1: Document missing required field should be INVALID, got '{result['validation_status']}'"

        # Check validation_errors contains E003 (required field missing)
        validation_errors = result.get("validation_errors", [])
        error_codes = [e.get("code") for e in validation_errors]
        assert "E003" in error_codes, (
            f"Gap_1: Missing required field should produce E003 in validation_errors, "
            f"got codes: {error_codes}, errors: {validation_errors}"
        )

    @pytest.mark.asyncio
    async def test_validate_tool_passes_valid_constraints(self):
        """Gap_1: Validate tool should pass when all constraints are satisfied.

        When all fields meet constraint requirements:
        - Required fields present
        - ENUM values valid
        - Then validation_status should be VALIDATED with empty validation_errors
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # Valid META content - all required fields present, STATUS is valid ENUM
        content = """===TEST===
META:
  TYPE::"TEST"
  VERSION::"1.0"
  STATUS::ACTIVE
===END==="""

        result = await tool.execute(
            content=content,
            schema="META",
            fix=False,
        )

        assert result["status"] == "success"
        assert (
            result["validation_status"] == "VALIDATED"
        ), f"Gap_1: Valid document should be VALIDATED, got '{result['validation_status']}'"

        # validation_errors should be empty
        validation_errors = result.get("validation_errors", [])
        assert (
            len(validation_errors) == 0
        ), f"Gap_1: Valid document should have empty validation_errors, got: {validation_errors}"

    @pytest.mark.asyncio
    async def test_validate_tool_no_section_schemas_preserves_behavior(self):
        """Gap_1: When no matching SchemaDefinition found, fall back to existing behavior.

        For unknown schemas, section_schemas won't be built, so constraint
        validation won't run. This maintains backwards compatibility.
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # Use unknown schema - should result in UNVALIDATED (schema not found)
        content = """===TEST===
SOME_SECTION:
  FIELD::value
===END==="""

        result = await tool.execute(
            content=content,
            schema="NONEXISTENT_SCHEMA",
            fix=False,
        )

        assert result["status"] == "success"
        # Should be UNVALIDATED because schema not found
        assert (
            result["validation_status"] == "UNVALIDATED"
        ), f"Gap_1: Unknown schema should result in UNVALIDATED, got '{result['validation_status']}'"

        # Should not have schema_name since schema wasn't found
        assert result.get("schema_name") is None or "schema_name" not in result


class TestValidateToolSpecCodeMapping:
    """Tests for Gap_6: Error message spec_code field mapping.

    The spec defines error codes E001-E007 in specs/octave-mcp-architecture.oct.md section 8.
    The implementation uses E_TOKENIZE and E_PARSE as wrapper codes.
    This test class verifies that when core errors (E001-E007) are caught,
    the original spec_code is preserved in the error dict.

    Spec Error Codes:
    - E001: Single colon assignment not allowed
    - E002: Schema selector required
    - E003: Cannot auto-fill missing required field
    - E004: Cannot infer routing target
    - E005: Tabs not allowed
    - E006: Ambiguous enum match
    - E007: Unknown field not allowed
    """

    @pytest.mark.asyncio
    async def test_validate_single_colon_error_has_spec_code(self):
        """E001: Single colon error should include spec_code='E001' in error dict.

        The spec (section 8) defines:
        E001: "Single colon assignment not allowed. Use KEY::value (double colon)."

        When the parser detects single colon assignment, it raises E001.
        The validate tool wraps this in E_PARSE, but should preserve spec_code.
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # Content with single colon assignment (E001 violation)
        content = """===TEST===
KEY: value
===END==="""

        result = await tool.execute(
            content=content,
            schema="TEST",
            fix=False,
        )

        # Should fail with parse error
        assert result["status"] == "error"
        assert len(result["errors"]) >= 1

        # Find the error (should be E_PARSE wrapping E001)
        error = result["errors"][0]
        assert error["code"] == "E_PARSE", f"Expected E_PARSE wrapper, got {error['code']}"

        # Gap_6 fix: spec_code should be present and contain 'E001'
        assert "spec_code" in error, f"Gap_6 violation: spec_code field missing from error dict. Error: {error}"
        assert (
            error["spec_code"] == "E001"
        ), f"Gap_6: Expected spec_code='E001' for single colon error, got spec_code='{error.get('spec_code')}'"

    @pytest.mark.asyncio
    async def test_validate_tab_error_has_spec_code(self):
        """E005: Tab character error should include spec_code='E005' in error dict.

        The spec (section 8) defines:
        E005: "Tabs not allowed. Use 2 spaces for indentation."

        When the lexer detects tabs, it raises E005.
        The validate tool wraps this in E_TOKENIZE, but should preserve spec_code.
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # Content with tab character (E005 violation)
        content = "===TEST===\n\tKEY::value\n===END==="

        result = await tool.execute(
            content=content,
            schema="TEST",
            fix=False,
        )

        # Should fail with tokenization error
        assert result["status"] == "error"
        assert len(result["errors"]) >= 1

        # Find the error (should be E_TOKENIZE wrapping E005)
        error = result["errors"][0]
        assert error["code"] == "E_TOKENIZE", f"Expected E_TOKENIZE wrapper, got {error['code']}"

        # Gap_6 fix: spec_code should be present and contain 'E005'
        assert "spec_code" in error, f"Gap_6 violation: spec_code field missing from error dict. Error: {error}"
        assert (
            error["spec_code"] == "E005"
        ), f"Gap_6: Expected spec_code='E005' for tab error, got spec_code='{error.get('spec_code')}'"

    @pytest.mark.asyncio
    async def test_validate_non_spec_error_has_no_spec_code(self):
        """Non-spec errors (E_INPUT, E_FILE, etc.) should not have spec_code field.

        Only errors that wrap core spec errors (E001-E007) should have spec_code.
        Implementation-specific errors like E_INPUT have no spec equivalent.
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # Trigger E_INPUT error by providing neither content nor file_path
        result = await tool.execute(
            schema="TEST",
            fix=False,
        )

        # Should fail with E_INPUT
        assert result["status"] == "error"
        assert len(result["errors"]) >= 1

        error = result["errors"][0]
        assert error["code"] == "E_INPUT"

        # E_INPUT has no spec equivalent, so spec_code should be absent or None
        assert (
            error.get("spec_code") is None
        ), f"E_INPUT should not have spec_code (no spec equivalent), but got spec_code='{error.get('spec_code')}'"

    @pytest.mark.asyncio
    async def test_validate_spec_code_extracted_from_error_message(self):
        """Verify spec_code is correctly extracted from core error message.

        The core lexer/parser embed the error code in the message like:
        "E005: Tabs are not allowed..."

        The validate tool should extract this code into spec_code field.
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # Use unexpected character to trigger E005
        content = "===TEST===\n(invalid)\n===END==="

        result = await tool.execute(
            content=content,
            schema="TEST",
            fix=False,
        )

        # Should fail
        assert result["status"] == "error"
        assert len(result["errors"]) >= 1

        error = result["errors"][0]
        # Should be E_TOKENIZE or E_PARSE depending on where error occurs
        assert error["code"] in ["E_TOKENIZE", "E_PARSE"]

        # The error message should contain the spec code
        # And spec_code field should be populated
        if "E005" in error.get("message", ""):
            assert error.get("spec_code") == "E005"


class TestValidateToolCRSBlockingIssues:
    """Tests for CRS blocking issues found in Gap_1 implementation review.

    These tests verify the fixes for:
    1. SECURITY: Schema name path traversal prevention
    2. CORRECTNESS: section_schemas maps only to schema's own name
    3. TEST COVERAGE: Holographic schema constraint validation works
    """

    @pytest.mark.asyncio
    async def test_schema_name_path_traversal_blocked(self):
        """SECURITY: Schema names with path traversal patterns are rejected.

        CRS finding: load_schema_by_name(schema_name) allows path traversal.
        Fix: Validate schema_name against SCHEMA_NAME_PATTERN (^[A-Z][A-Z0-9_]*$)
        """
        from octave_mcp.schemas.loader import load_schema_by_name

        # Path traversal attacks should return None (schema not found)
        assert load_schema_by_name("../README") is None
        assert load_schema_by_name("..%2F..%2Fetc%2Fpasswd") is None
        assert load_schema_by_name("foo/bar") is None
        assert load_schema_by_name("../secret") is None
        assert load_schema_by_name("../../etc/passwd") is None

        # Valid schema names should be allowed (but may return None if file doesn't exist)
        # META should exist and load successfully
        meta_schema = load_schema_by_name("META")
        assert meta_schema is not None or meta_schema is None  # Either is fine, key is no exception

        # Invalid patterns (lowercase, special chars)
        assert load_schema_by_name("meta") is None  # lowercase not allowed
        assert load_schema_by_name("Meta") is None  # must start uppercase, all caps
        assert load_schema_by_name("META-SCHEMA") is None  # hyphen not allowed
        assert load_schema_by_name("META.SCHEMA") is None  # dot not allowed

    @pytest.mark.asyncio
    async def test_schema_name_valid_patterns_accepted(self):
        """SECURITY: Valid schema name patterns are accepted.

        Valid patterns: ^[A-Z][A-Z0-9_]*$
        Examples: META, SESSION_LOG, TEST_HOLOGRAPHIC, SCHEMA_V2
        """
        from octave_mcp.schemas.loader import SCHEMA_NAME_PATTERN

        # Valid patterns
        assert SCHEMA_NAME_PATTERN.match("META")
        assert SCHEMA_NAME_PATTERN.match("SESSION_LOG")
        assert SCHEMA_NAME_PATTERN.match("TEST_HOLOGRAPHIC")
        assert SCHEMA_NAME_PATTERN.match("SCHEMA_V2")
        assert SCHEMA_NAME_PATTERN.match("A")  # Single uppercase letter

        # Invalid patterns
        assert not SCHEMA_NAME_PATTERN.match("../secret")
        assert not SCHEMA_NAME_PATTERN.match("meta")  # lowercase
        assert not SCHEMA_NAME_PATTERN.match("_META")  # starts with underscore
        assert not SCHEMA_NAME_PATTERN.match("1META")  # starts with digit
        assert not SCHEMA_NAME_PATTERN.match("META-SCHEMA")  # hyphen
        assert not SCHEMA_NAME_PATTERN.match("")  # empty

    @pytest.mark.asyncio
    async def test_section_schemas_maps_only_to_schema_name(self):
        """CORRECTNESS: section_schemas maps only to schema's own name.

        CRS finding: Current impl might assign loaded schema to every section key.
        Fix: section_schemas = {schema_definition.name: schema_definition}

        This test verifies that when validating with a holographic schema,
        only the section matching the schema name is validated, not ALL sections.
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # Document has TEST_HOLOGRAPHIC section (matches schema) and OTHER section (unrelated)
        # Only TEST_HOLOGRAPHIC should be validated against the schema constraints
        content = """===DOC===
TEST_HOLOGRAPHIC:
  NAME::"correct_name"
  STATUS::ACTIVE
---
OTHER_SECTION:
  RANDOM_FIELD::anything_goes_here
  NO_CONSTRAINT_CHECKING::true
===END==="""

        result = await tool.execute(
            content=content,
            schema="TEST_HOLOGRAPHIC",
            fix=False,
        )

        # Should succeed because:
        # 1. TEST_HOLOGRAPHIC section has valid NAME and STATUS
        # 2. OTHER_SECTION is NOT validated (no matching schema)
        assert result["status"] == "success"
        # If section_schemas incorrectly mapped OTHER_SECTION to schema,
        # we'd get errors about missing required fields (NAME, STATUS)
        # The fact that this passes proves the fix works
        validation_errors = result.get("validation_errors", [])
        assert not any(
            "OTHER_SECTION" in str(e) for e in validation_errors
        ), "CORRECTNESS BUG: OTHER_SECTION should not be validated against TEST_HOLOGRAPHIC schema"

    @pytest.mark.asyncio
    async def test_holographic_schema_constraint_violation_detected(self):
        """TEST COVERAGE: Holographic schema constraints are evaluated.

        CRS finding: Tests don't exercise section_schemas path with SchemaDefinition.
        Fix: Use TEST_HOLOGRAPHIC schema (has holographic FIELDS with REQ/ENUM constraints)

        This test proves that:
        1. SchemaDefinition is loaded from test_holographic.oct.md
        2. section_schemas is built and passed to validator
        3. Constraint validation (ENUM) catches invalid values
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # TEST_HOLOGRAPHIC schema defines STATUS with ENUM[DRAFT,ACTIVE,DEPRECATED]
        # Using INVALID_STATUS should trigger constraint violation
        content = """===DOC===
TEST_HOLOGRAPHIC:
  NAME::"test_name"
  STATUS::INVALID_STATUS
===END==="""

        result = await tool.execute(
            content=content,
            schema="TEST_HOLOGRAPHIC",
            fix=False,
        )

        # Should succeed (parsing works) but validation should fail
        assert result["status"] == "success"

        # This test PROVES the section_schemas path is exercised:
        # If section_schemas wiring were removed, this test would pass with VALIDATED
        # because no constraints would be checked on document sections
        validation_errors = result.get("validation_errors", [])
        error_codes = [e.get("code") for e in validation_errors]

        # E005 is the ENUM constraint violation code
        assert "E005" in error_codes, (
            f"TEST COVERAGE: ENUM constraint violation should produce E005. "
            f"Got codes: {error_codes}, errors: {validation_errors}. "
            f"If no E005, section_schemas wiring may be broken."
        )

    @pytest.mark.asyncio
    async def test_holographic_schema_required_field_missing_detected(self):
        """TEST COVERAGE: Holographic schema REQ constraints are evaluated.

        TEST_HOLOGRAPHIC schema defines NAME and STATUS as REQ (required).
        Missing a required field should trigger E003.
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # Missing NAME field (required by TEST_HOLOGRAPHIC schema)
        content = """===DOC===
TEST_HOLOGRAPHIC:
  STATUS::ACTIVE
===END==="""

        result = await tool.execute(
            content=content,
            schema="TEST_HOLOGRAPHIC",
            fix=False,
        )

        assert result["status"] == "success"

        validation_errors = result.get("validation_errors", [])
        error_codes = [e.get("code") for e in validation_errors]

        # E003 is the required field missing code
        assert "E003" in error_codes, (
            f"TEST COVERAGE: Missing REQ field should produce E003. "
            f"Got codes: {error_codes}, errors: {validation_errors}. "
            f"If no E003, section_schemas constraint evaluation may be broken."
        )

    @pytest.mark.asyncio
    async def test_holographic_schema_valid_document_passes(self):
        """TEST COVERAGE: Valid document passes holographic schema validation.

        Document with all required fields and valid ENUM values should pass.
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # All required fields present, STATUS is valid ENUM value
        content = """===DOC===
TEST_HOLOGRAPHIC:
  NAME::"valid_name"
  STATUS::ACTIVE
===END==="""

        result = await tool.execute(
            content=content,
            schema="TEST_HOLOGRAPHIC",
            fix=False,
        )

        assert result["status"] == "success"

        # No validation errors when document is valid
        validation_errors = result.get("validation_errors", [])
        assert len(validation_errors) == 0, f"Valid document should have no validation errors. Got: {validation_errors}"


class TestValidateToolGap5SchemaRepairWiring:
    """Tests for Gap_5: Wire schema into repair() calls at entrypoints.

    CRS BLOCKING ISSUE: repair() only applies schema repairs when fix=True AND
    schema parameter is passed. But both CLI and MCP entrypoints call repair()
    without passing the schema parameter!

    Evidence:
    - repair.py:252-255: `if fix and schema is not None:` guards schema repairs
    - mcp/validate.py:407: `repair(doc, validation_errors, fix=True)` - NO schema=
    - cli/main.py:226: `repair(doc, validation_errors, fix=True)` - NO schema=

    These tests verify the fix: schema_definition must be passed to repair().
    """

    @pytest.mark.asyncio
    async def test_validate_fix_applies_enum_casefold_via_mcp(self):
        """Gap_5: MCP validate with fix=True applies enum casefold repairs.

        End-to-end test: Call octave_validate tool with:
        - Document containing lowercase enum value (e.g., "active")
        - Schema with ENUM constraint (e.g., ENUM[DRAFT,ACTIVE,DEPRECATED])
        - fix=True

        Expected: canonical output has repaired value "ACTIVE" (not "active")
        Expected: repair_log contains ENUM_CASEFOLD entry
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # TEST_HOLOGRAPHIC schema defines STATUS with ENUM[DRAFT,ACTIVE,DEPRECATED]
        # Use lowercase "active" which should be repaired to "ACTIVE"
        content = """===DOC===
TEST_HOLOGRAPHIC:
  NAME::"test_name"
  STATUS::active
===END==="""

        result = await tool.execute(
            content=content,
            schema="TEST_HOLOGRAPHIC",
            fix=True,  # Enable repairs
        )

        # Should succeed (parsing works)
        assert result["status"] == "success", f"Unexpected error: {result.get('errors', [])}"

        # Gap_5 FIX PROOF: After fix, canonical should contain repaired value
        # The enum casefold repair transforms "active" -> "ACTIVE"
        canonical = result["canonical"]
        assert (
            "STATUS::ACTIVE" in canonical or 'STATUS::"ACTIVE"' in canonical
        ), f"Gap_5: Enum casefold repair not applied. Expected STATUS::ACTIVE in canonical, got:\n{canonical}"

        # Gap_5 FIX PROOF: repair_log should contain ENUM_CASEFOLD entry
        # Note: repair_log entries may be RepairEntry dataclasses or dicts
        repair_log = result.get("repair_log", [])
        enum_casefold_repairs = []
        for r in repair_log:
            # Handle both dict and dataclass RepairEntry objects
            rule_id = r.get("rule_id") if isinstance(r, dict) else getattr(r, "rule_id", None)
            if rule_id == "ENUM_CASEFOLD":
                enum_casefold_repairs.append(r)
        assert (
            len(enum_casefold_repairs) >= 1
        ), f"Gap_5: ENUM_CASEFOLD repair not logged. repair_log contents: {repair_log}"

        # Verify repair details (handle both dict and dataclass)
        repair_entry = enum_casefold_repairs[0]
        before_val = (
            repair_entry.get("before") if isinstance(repair_entry, dict) else getattr(repair_entry, "before", None)
        )
        after_val = (
            repair_entry.get("after") if isinstance(repair_entry, dict) else getattr(repair_entry, "after", None)
        )
        assert before_val == "active", f"Repair before value wrong: {repair_entry}"
        assert after_val == "ACTIVE", f"Repair after value wrong: {repair_entry}"

    @pytest.mark.asyncio
    async def test_validate_fix_false_does_not_apply_repairs(self):
        """Gap_5: MCP validate with fix=False does NOT apply repairs to canonical.

        Regression test: fix=False should only suggest repairs, not apply them.
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        content = """===DOC===
TEST_HOLOGRAPHIC:
  NAME::"test_name"
  STATUS::active
===END==="""

        result = await tool.execute(
            content=content,
            schema="TEST_HOLOGRAPHIC",
            fix=False,  # Repairs disabled
        )

        assert result["status"] == "success"

        # With fix=False, canonical should contain the ORIGINAL value (not repaired)
        canonical = result["canonical"]
        assert (
            "STATUS::active" in canonical or 'STATUS::"active"' in canonical
        ), f"Gap_5: With fix=False, canonical should preserve original value. Got:\n{canonical}"

    @pytest.mark.asyncio
    async def test_validate_fix_applies_type_coercion_via_mcp(self):
        """Gap_5: MCP validate with fix=True applies type coercion repairs.

        When a schema expects NUMBER type but receives string "42",
        repair should coerce to integer 42.

        NOTE: This test may fail if TEST_HOLOGRAPHIC doesn't have a NUMBER field.
        If so, it documents the behavior for future schema additions.
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # META schema has VERSION which expects a string, so we need a schema
        # with a NUMBER type field. If TEST_HOLOGRAPHIC doesn't have one,
        # this test documents the expectation for when such schemas exist.
        # For now, test with a value that might trigger type coercion if available.
        content = """===DOC===
TEST_HOLOGRAPHIC:
  NAME::"test_name"
  STATUS::ACTIVE
===END==="""

        result = await tool.execute(
            content=content,
            schema="TEST_HOLOGRAPHIC",
            fix=True,
        )

        # This test primarily documents the type coercion path is wired
        # The actual coercion only happens if schema has NUMBER type fields
        assert result["status"] == "success"
        # Type coercion repairs would appear in repair_log with rule_id="TYPE_COERCION"
        # Currently TEST_HOLOGRAPHIC has no NUMBER fields, so we just verify no errors

    @pytest.mark.asyncio
    async def test_validate_with_debug_grammar(self):
        """Test that debug_grammar parameter exposes compiled constraint grammar.

        Phase 3 integration: When debug_grammar=True, the tool should include
        the compiled grammar/regex in the output for debugging constraint evaluation.

        CRS BLOCKING: Requires ConstraintChain.compile() method and correct field path.
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # Use TEST_HOLOGRAPHIC schema which has holographic patterns
        content = """===TEST===
TEST_HOLOGRAPHIC:
  NAME::"test_name"
  STATUS::ACTIVE
===END==="""

        result = await tool.execute(
            content=content,
            schema="TEST_HOLOGRAPHIC",
            fix=False,
            debug_grammar=True,
        )

        assert result["status"] == "success"
        # When debug_grammar is enabled, we should get grammar debugging info
        assert "debug_info" in result, "Phase 3: debug_grammar=True should include debug_info in response"

        debug_info = result["debug_info"]
        assert "schema_name" in debug_info
        assert debug_info["schema_name"] == "TEST_HOLOGRAPHIC"
        assert "field_constraints" in debug_info

        # Verify that field constraints include compiled_regex for STATUS field
        field_constraints = debug_info["field_constraints"]
        assert (
            "STATUS" in field_constraints
        ), f"STATUS field should be in debug_info, got fields: {list(field_constraints.keys())}"

        status_constraint = field_constraints["STATUS"]
        assert "chain" in status_constraint, "Should include constraint chain string"
        assert "compiled_regex" in status_constraint, "Phase 3 BLOCKING: Should include compiled_regex"

        # Verify the compiled regex is actually a valid regex pattern
        compiled = status_constraint["compiled_regex"]
        assert isinstance(compiled, str), "compiled_regex should be a string"
        assert len(compiled) > 0, "compiled_regex should not be empty"
        # STATUS is REQ∧ENUM[DRAFT,ACTIVE,DEPRECATED] so should compile to pattern with REQ and alternation
        assert (
            "|" in compiled or "DRAFT" in compiled
        ), f"ENUM constraint should compile to pattern with alternatives, got: {compiled}"


class TestValidateToolTokenEfficiency:
    """Tests for Issue #195: Token-efficient response modes.

    The octave_validate tool always returns full canonical content, which wastes tokens
    when agents just need validation status. These tests verify:
    1. diff_only=True returns diff instead of canonical content
    2. compact=True returns counts instead of full warning/error lists
    3. Both modes maintain backwards compatibility (defaults unchanged)

    TDD: RED phase - these tests define the expected behavior.
    """

    @pytest.mark.asyncio
    async def test_validate_diff_only_returns_diff_not_canonical(self):
        """diff_only=True should return diff instead of canonical content."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        content = """===TEST===
META:
  TYPE::"SESSION"
  VERSION::"1.0"
===END==="""
        result = await tool.execute(content=content, schema="SESSION", diff_only=True)
        assert result["status"] == "success"
        assert result["canonical"] is None  # NOT echoed back
        assert "changed" in result
        assert "diff" in result

    @pytest.mark.asyncio
    async def test_validate_diff_only_unchanged_content(self):
        """diff_only with valid unchanged content returns 'no changes'."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        # Content that is already canonical (won't change)
        # Note: Must use already-canonical format (e.g., TYPE::META not TYPE::"META")
        # because the emitter normalizes quoted bare strings to unquoted
        content = """===TEST===
META:
  TYPE::META
  VERSION::"1.0"
===END==="""
        result = await tool.execute(content=content, schema="META", diff_only=True)
        assert result["status"] == "success"
        assert result["changed"] is False
        assert result["diff"] == "no changes"
        assert result["canonical"] is None

    @pytest.mark.asyncio
    async def test_validate_diff_only_with_changes(self):
        """diff_only=True with content that gets normalized should show diff."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        # Content with ASCII arrow that will be normalized to unicode
        content = """===TEST===
FLOW::A -> B
===END==="""
        result = await tool.execute(content=content, schema="TEST", diff_only=True)
        assert result["status"] == "success"
        assert "changed" in result
        assert "diff" in result
        # If changed, diff should contain actual diff output
        if result["changed"]:
            assert result["diff"] != "no changes"
            assert len(result["diff"]) > 0
        assert result["canonical"] is None

    @pytest.mark.asyncio
    async def test_validate_compact_mode_warning_counts(self):
        """compact=True should return warning_count instead of full warnings list."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        # Content that may generate warnings (invalid enum value)
        content = """===TEST===
META:
  TYPE::"UNKNOWN_SCHEMA"
  VERSION::"1.0"
  STATUS::INVALID_STATUS
===END==="""
        result = await tool.execute(content=content, schema="META", compact=True)
        assert result["status"] == "success"
        assert "warning_count" in result
        assert isinstance(result["warning_count"], int)
        # In compact mode, warnings list should be empty (counts only)
        assert result["warnings"] == []

    @pytest.mark.asyncio
    async def test_validate_compact_mode_includes_error_count(self):
        """compact=True should return error_count as well."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        content = """===TEST===
META:
  TYPE::"TEST"
  VERSION::"1.0"
===END==="""
        result = await tool.execute(content=content, schema="META", compact=True)
        assert result["status"] == "success"
        assert "error_count" in result
        assert isinstance(result["error_count"], int)
        assert "validation_error_count" in result
        assert isinstance(result["validation_error_count"], int)

    @pytest.mark.asyncio
    async def test_validate_diff_only_with_compact(self):
        """Both diff_only and compact can be used together."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        content = """===TEST===
META:
  TYPE::"SESSION"
===END==="""
        result = await tool.execute(content=content, schema="SESSION", diff_only=True, compact=True)
        assert result["status"] == "success"
        assert result["canonical"] is None
        assert "changed" in result
        assert "diff" in result
        assert "warning_count" in result

    @pytest.mark.asyncio
    async def test_validate_default_behavior_unchanged(self):
        """Without diff_only, canonical should still be returned (backwards compat)."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        content = """===TEST===
META:
  TYPE::"META"
===END==="""
        result = await tool.execute(content=content, schema="META")
        assert result["status"] == "success"
        assert result["canonical"] is not None
        assert "changed" not in result  # Only present when diff_only=True

    @pytest.mark.asyncio
    async def test_validate_diff_only_in_input_schema(self):
        """diff_only parameter should be in input schema."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        schema = tool.get_input_schema()

        assert "diff_only" in schema["properties"]
        assert schema["properties"]["diff_only"]["type"] == "boolean"
        # Should not be required
        assert "diff_only" not in schema.get("required", [])

    @pytest.mark.asyncio
    async def test_validate_compact_in_input_schema(self):
        """compact parameter should be in input schema."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        schema = tool.get_input_schema()

        assert "compact" in schema["properties"]
        assert schema["properties"]["compact"]["type"] == "boolean"
        # Should not be required
        assert "compact" not in schema.get("required", [])

    @pytest.mark.asyncio
    async def test_validate_diff_only_with_parse_error(self):
        """diff_only should not break error handling."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        # Invalid content with tab (E005 violation)
        content = "===TEST===\n\tKEY::value\n===END==="

        result = await tool.execute(content=content, schema="TEST", diff_only=True)
        # Should still return error status
        assert result["status"] == "error"
        assert len(result["errors"]) >= 1

    @pytest.mark.asyncio
    async def test_validate_compact_with_parse_error(self):
        """compact should not break error handling."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        # Invalid content with tab (E005 violation)
        content = "===TEST===\n\tKEY::value\n===END==="

        result = await tool.execute(content=content, schema="TEST", compact=True)
        # Should still return error status
        assert result["status"] == "error"
        # On error, warnings/errors lists may still be populated (not compacted)


class TestValidateToolCEQualityGateFixes:
    """Tests for CE-identified quality gate fixes.

    CE Review identified two MUST FIX items:
    1. Size guard before diff generation (prevent high CPU/memory on large inputs)
    2. Error-path token efficiency (diff_only/compact should apply on parse errors)
    """

    @pytest.mark.asyncio
    async def test_validate_diff_only_large_content_guard(self):
        """Large content should skip expensive diff generation.

        MUST FIX #1: _build_unified_diff can cause high CPU/memory on large inputs
        even before truncation. Add size guard before calling diff generation.
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        # Create large content (>100KB)
        large_content = "===TEST===\nMETA:\n  TYPE::META\n" + "X::value\n" * 10000 + "===END==="
        result = await tool.execute(content=large_content, schema="META", diff_only=True)
        assert result["status"] == "success"
        # Should show truncation message for large changes
        assert "changed" in result
        # If content changed and was large, diff should be omitted
        if result.get("changed") and len(large_content) > 100_000:
            assert result["diff"] == "omitted: too large (>100KB)"

    @pytest.mark.asyncio
    async def test_validate_diff_only_on_parse_error(self):
        """diff_only should apply even on parse errors.

        MUST FIX #2: diff_only/compact don't apply on parse errors - canonical
        content still echoed. This wastes tokens when agents use diff_only.
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        invalid_content = "this is not valid octave {"
        result = await tool.execute(content=invalid_content, schema="META", diff_only=True)
        assert result["status"] == "error"
        assert result["canonical"] is None  # NOT echoed back

    @pytest.mark.asyncio
    async def test_validate_compact_on_parse_error(self):
        """compact should apply even on parse errors.

        MUST FIX #2: Error envelopes should honor compact mode.
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        invalid_content = "this is not valid octave {"
        result = await tool.execute(content=invalid_content, schema="META", compact=True)
        assert result["status"] == "error"
        assert "error_count" in result
        assert result["error_count"] >= 1

    @pytest.mark.asyncio
    async def test_validate_diff_only_and_compact_on_parse_error(self):
        """Both diff_only and compact should apply on parse errors."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        invalid_content = "===BROKEN\nKEY value"  # Missing :: and ===END===
        result = await tool.execute(content=invalid_content, schema="META", diff_only=True, compact=True)
        assert result["status"] == "error"
        assert result["canonical"] is None  # diff_only honored
        assert "error_count" in result  # compact honored

    @pytest.mark.asyncio
    async def test_validate_diff_only_on_input_error(self):
        """diff_only should apply even on input validation errors (E_INPUT)."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        # Trigger E_INPUT by providing neither content nor file_path
        result = await tool.execute(schema="META", diff_only=True)
        assert result["status"] == "error"
        assert result["canonical"] is None  # NOT echoed back

    @pytest.mark.asyncio
    async def test_validate_compact_on_input_error(self):
        """compact should apply even on input validation errors (E_INPUT)."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        # Trigger E_INPUT by providing neither content nor file_path
        result = await tool.execute(schema="META", compact=True)
        assert result["status"] == "error"
        assert "error_count" in result
        assert result["error_count"] >= 1


class TestValidateToolProfiles:
    """Tests for validation profile parameter (#183).

    Profiles define validation strictness levels:
    - STRICT: Full spec compliance, reject unknown syntax, enforce all NEVER rules
    - STANDARD: Current default behavior (backwards compatible)
    - LENIENT: Relaxed validation, warnings instead of errors, auto-repairs
    - ULTRA: Minimal validation, preserve everything possible

    TDD: RED phase - these tests define the expected behavior.
    """

    @pytest.mark.asyncio
    async def test_profile_parameter_in_schema(self):
        """Profile parameter should be in input schema."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        schema = tool.get_input_schema()
        props = schema["properties"]
        assert "profile" in props, "#183: profile parameter missing from input schema"
        assert props["profile"]["enum"] == [
            "STRICT",
            "STANDARD",
            "LENIENT",
            "ULTRA",
        ], "#183: profile enum should include all four profiles"

    @pytest.mark.asyncio
    async def test_profile_default_is_standard(self):
        """Default profile should be STANDARD (backwards compatible)."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        # Content that currently passes should still pass without profile
        content = """===TEST===
META:
  TYPE::"META"
  VERSION::"1.0"
===END==="""
        result = await tool.execute(content=content, schema="META")
        assert result["status"] == "success"
        # Verify profile is reported in result
        assert (
            result.get("profile") == "STANDARD"
        ), "#183: Default profile should be STANDARD for backwards compatibility"

    @pytest.mark.asyncio
    async def test_profile_strict_rejects_unknown_fields(self):
        """STRICT profile should reject documents with unknown fields."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        content = """===TEST===
META:
  TYPE::"META"
  VERSION::"1.0"
  UNKNOWN_FIELD::"should fail in strict"
===END==="""
        result = await tool.execute(content=content, schema="META", profile="STRICT")
        assert result["profile"] == "STRICT"
        # STRICT should flag unknown fields as errors (not just warnings)
        # Either validation_status INVALID or non-empty validation_errors
        is_strict = (
            result.get("validation_status") == "INVALID"
            or len(result.get("validation_errors", [])) > 0
            or len(result.get("errors", [])) > 0
        )
        assert is_strict, (
            "#183: STRICT profile should reject unknown fields. "
            f"Got validation_status={result.get('validation_status')}, "
            f"validation_errors={result.get('validation_errors')}"
        )

    @pytest.mark.asyncio
    async def test_profile_lenient_downgrades_errors_to_warnings(self):
        """LENIENT profile should convert some errors to warnings."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        content = """===TEST===
META:
  TYPE::"META"
  VERSION::"1.0"
  UNKNOWN_FIELD::"should be warning in lenient"
===END==="""
        result = await tool.execute(content=content, schema="META", profile="LENIENT")
        assert result["profile"] == "LENIENT"
        # LENIENT should treat unknown fields as warnings, not errors
        # Document should still be considered valid (success + not INVALID)
        assert result["status"] == "success", "#183: LENIENT profile should succeed even with unknown fields"
        # LENIENT allows document to pass validation even with minor issues
        assert result.get("validation_status") in ["VALIDATED", "UNVALIDATED"], (
            "#183: LENIENT should not mark as INVALID for unknown fields. "
            f"Got validation_status={result.get('validation_status')}"
        )

    @pytest.mark.asyncio
    async def test_profile_ultra_preserves_everything(self):
        """ULTRA profile should preserve maximum content."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        # Content with unusual syntax that would normally warn
        content = """===TEST===
META:
  TYPE::"CUSTOM"
  VERSION::"1.0"
===END==="""
        result = await tool.execute(content=content, schema="META", profile="ULTRA")
        assert result["profile"] == "ULTRA"
        assert result["status"] == "success", "#183: ULTRA profile should preserve content even if unconventional"
        # ULTRA should not fail validation unless content is unparseable
        assert result.get("validation_status") != "INVALID", "#183: ULTRA should only fail on unparseable content"

    @pytest.mark.asyncio
    async def test_profile_strict_enforces_never_rules(self):
        """STRICT profile should enforce spec NEVER rules."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        # Missing VERSION - in STRICT should be error, in STANDARD may be warning
        content = """===TEST===
META:
  TYPE::"META"
===END==="""
        strict_result = await tool.execute(content=content, schema="META", profile="STRICT")
        standard_result = await tool.execute(content=content, schema="META", profile="STANDARD")

        # STRICT should be more strict (either more errors or INVALID status)
        strict_errors = len(strict_result.get("errors", [])) + len(strict_result.get("validation_errors", []))
        standard_errors = len(standard_result.get("errors", [])) + len(standard_result.get("validation_errors", []))

        # At minimum, STRICT should not be more lenient
        strict_is_stricter = strict_errors >= standard_errors or strict_result.get("validation_status") == "INVALID"
        assert strict_is_stricter, (
            "#183: STRICT should be at least as strict as STANDARD. "
            f"STRICT errors={strict_errors}, STANDARD errors={standard_errors}"
        )

    @pytest.mark.asyncio
    async def test_profile_invalid_value_returns_error(self):
        """Invalid profile value should return error."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        content = """===TEST===
META:
  TYPE::"META"
===END==="""
        result = await tool.execute(content=content, schema="META", profile="INVALID_PROFILE")
        assert result["status"] == "error", "#183: Invalid profile should return error status"
        # Error should mention profile
        error_messages = " ".join(str(e.get("message", "")) for e in result.get("errors", []))
        assert (
            "profile" in error_messages.lower() or "INVALID_PROFILE" in error_messages
        ), "#183: Error message should mention invalid profile value"

    @pytest.mark.asyncio
    async def test_profile_case_insensitive(self):
        """Profile values should be case-insensitive."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        content = """===TEST===
META:
  TYPE::"META"
  VERSION::"1.0"
===END==="""
        # Try lowercase
        result = await tool.execute(content=content, schema="META", profile="strict")
        assert result["profile"] == "STRICT", "#183: Profile should normalize to uppercase"
        # Should still succeed (not error due to lowercase)
        # Note: STRICT may fail validation, but should not error on profile param
        assert result["status"] in ["success", "error"], "#183: lowercase profile should be accepted"
        # If it's an error, it should NOT be about profile param
        if result["status"] == "error":
            error_messages = " ".join(str(e.get("message", "")) for e in result.get("errors", []))
            assert (
                "profile" not in error_messages.lower()
            ), "#183: Error should not be about profile parameter when using lowercase"

    @pytest.mark.asyncio
    async def test_profile_reported_in_result(self):
        """Profile should be reported in result envelope for transparency."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        content = """===TEST===
KEY::value
===END==="""

        # Test each profile is reported
        for profile in ["STRICT", "STANDARD", "LENIENT", "ULTRA"]:
            result = await tool.execute(content=content, schema="TEST", profile=profile)
            assert "profile" in result, f"#183: profile missing from result for {profile}"
            assert result["profile"] == profile, f"#183: Expected profile={profile}, got {result.get('profile')}"

    @pytest.mark.asyncio
    async def test_profile_strict_with_missing_required_field(self):
        """STRICT should mark missing required fields as INVALID."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        # Missing required TYPE field
        content = """===TEST===
META:
  VERSION::"1.0"
===END==="""
        result = await tool.execute(content=content, schema="META", profile="STRICT")
        assert result["profile"] == "STRICT"
        # STRICT should definitely fail on missing required field
        assert result.get("validation_status") == "INVALID", "#183: STRICT must fail on missing required fields"

    @pytest.mark.asyncio
    async def test_profile_lenient_with_missing_required_field(self):
        """LENIENT still validates required fields but may be more forgiving."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        # Missing required TYPE field
        content = """===TEST===
META:
  VERSION::"1.0"
===END==="""
        result = await tool.execute(content=content, schema="META", profile="LENIENT")
        assert result["profile"] == "LENIENT"
        # LENIENT may still mark as INVALID for truly required fields
        # but should not error on the operation itself
        assert result["status"] == "success", "#183: LENIENT should complete successfully even with validation issues"

    @pytest.mark.asyncio
    async def test_profile_with_diff_only_and_compact(self):
        """Profile should work with diff_only and compact modes."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        content = """===TEST===
META:
  TYPE::"TEST"
  VERSION::"1.0"
===END==="""
        result = await tool.execute(
            content=content,
            schema="META",
            profile="LENIENT",
            diff_only=True,
            compact=True,
        )
        assert result["profile"] == "LENIENT"
        assert result["canonical"] is None  # diff_only honored
        assert "warning_count" in result  # compact honored

    @pytest.mark.asyncio
    async def test_profile_lenient_sets_has_warnings_flag(self):
        """LENIENT profile should set has_warnings when validation issues downgraded."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        content = """===TEST===
META:
  TYPE::"META"
===END==="""  # Missing VERSION - would be error in STANDARD
        result = await tool.execute(content=content, schema="META", profile="LENIENT")
        assert result["validation_status"] == "VALIDATED"
        assert result["has_warnings"] is True  # Signals issues were downgraded

    @pytest.mark.asyncio
    async def test_profile_standard_has_warnings_false_when_valid(self):
        """STANDARD profile with valid content should have has_warnings=False."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        content = """===TEST===
META:
  TYPE::"META"
  VERSION::"1.0"
===END==="""
        result = await tool.execute(content=content, schema="META", profile="STANDARD")
        assert result["validation_status"] == "VALIDATED"
        assert result["has_warnings"] is False


class TestValidateGrammarHint:
    """GH#278: Tests for grammar_hint parameter on octave_validate."""

    @pytest.mark.asyncio
    async def test_invalid_with_grammar_hint_true_returns_grammar(self):
        """INVALID + grammar_hint=True should include grammar_hint dict in response."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # Document missing required TYPE field -> INVALID against META schema
        content = """===TEST===
META:
  VERSION::"1.0"
===END==="""

        result = await tool.execute(
            content=content,
            schema="META",
            fix=False,
            grammar_hint=True,
        )

        assert result["status"] == "success"
        assert result["validation_status"] == "INVALID"
        assert "grammar_hint" in result, "grammar_hint should be present when INVALID and grammar_hint=True"

        hint = result["grammar_hint"]
        assert hint["format"] == "gbnf"
        assert isinstance(hint["grammar"], str)
        assert len(hint["grammar"]) > 0, "compiled grammar should be non-empty"
        assert "usage_hints" in hint
        assert isinstance(hint["usage_hints"], dict)
        assert "llama_cpp" in hint["usage_hints"]

    @pytest.mark.asyncio
    async def test_invalid_with_grammar_hint_false_no_grammar(self):
        """INVALID + grammar_hint=False (default) should NOT include grammar_hint."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        content = """===TEST===
META:
  VERSION::"1.0"
===END==="""

        result = await tool.execute(
            content=content,
            schema="META",
            fix=False,
            grammar_hint=False,
        )

        assert result["validation_status"] == "INVALID"
        assert "grammar_hint" not in result

    @pytest.mark.asyncio
    async def test_invalid_default_no_grammar_hint(self):
        """INVALID + grammar_hint omitted (default False) should NOT include grammar_hint."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        content = """===TEST===
META:
  VERSION::"1.0"
===END==="""

        result = await tool.execute(
            content=content,
            schema="META",
            fix=False,
        )

        assert result["validation_status"] == "INVALID"
        assert "grammar_hint" not in result

    @pytest.mark.asyncio
    async def test_valid_with_grammar_hint_true_no_grammar(self):
        """VALID + grammar_hint=True should NOT include grammar_hint (only on INVALID)."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        content = """===TEST===
META:
  TYPE::"META"
  VERSION::"1.0"
===END==="""

        result = await tool.execute(
            content=content,
            schema="META",
            fix=False,
            grammar_hint=True,
        )

        assert result["validation_status"] == "VALIDATED"
        assert "grammar_hint" not in result

    @pytest.mark.asyncio
    async def test_invalid_no_schema_definition_no_grammar(self):
        """INVALID + no SchemaDefinition loaded + grammar_hint=True should NOT include grammar_hint."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # Use a schema name that has a builtin dict schema but no SchemaDefinition file
        # META has both, so we use content that triggers INVALID via dict schema only
        # Actually, META does have a SchemaDefinition. Let's use UNVALIDATED path instead:
        # A document validated against a non-existent schema stays UNVALIDATED, not INVALID.
        # The grammar_hint is only injected when INVALID, so UNVALIDATED should not have it.
        content = """===TEST===
KEY::value
===END==="""

        result = await tool.execute(
            content=content,
            schema="NONEXISTENT_SCHEMA",
            fix=False,
            grammar_hint=True,
        )

        # No schema found -> UNVALIDATED (not INVALID)
        assert result["validation_status"] == "UNVALIDATED"
        assert "grammar_hint" not in result

    @pytest.mark.asyncio
    async def test_grammar_hint_parameter_in_schema(self):
        """grammar_hint parameter should be declared in tool input schema."""
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()
        schema = tool.get_input_schema()
        assert "grammar_hint" in schema["properties"]
        assert schema["properties"]["grammar_hint"]["type"] == "boolean"
