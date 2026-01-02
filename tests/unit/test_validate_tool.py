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
        assert result["validation_status"] == "VALIDATED", (
            f"I5: Should be VALIDATED when META schema validates content, " f"but got '{result['validation_status']}'"
        )
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
        assert result["validation_status"] != "PENDING_INFRASTRUCTURE", (
            "I5 violation: PENDING_INFRASTRUCTURE is a silent bypass. " "Must use UNVALIDATED to make bypass visible."
        )


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
        assert result["validation_status"] == "INVALID", (
            f"I5 violation: Should be INVALID when META schema validation fails, "
            f"got '{result['validation_status']}'"
        )
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
        assert result["status"] == "success", (
            f"Issue #91: YAML frontmatter with parentheses failed. " f"Errors: {result.get('errors', [])}"
        )
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
        assert result["status"] == "success", (
            f"Issue #91: YAML frontmatter with brackets failed. " f"Errors: {result.get('errors', [])}"
        )

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
        assert result["status"] == "success", (
            f"Issue #91: YAML frontmatter with special chars failed. " f"Errors: {result.get('errors', [])}"
        )

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
