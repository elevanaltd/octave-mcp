"""Tests for octave_write MCP tool (GH#51 Tool Consolidation).

Tests the new write tool that replaces octave_create + octave_amend:
- Unified write with content XOR changes parameter model
- Tri-state semantics for changes: absent=no-op, {"$op":"DELETE"}=remove, null=empty
- base_hash CAS guard in BOTH modes when file exists
- Unified envelope: status, path, canonical_hash, corrections, diff, errors, validation_status
- I1 (Syntactic Fidelity): Normalizes to canonical form
- I2 (Deterministic Absence): Tri-state semantics
- I4 (Auditability): Returns corrections and diff
- I5 (Schema Sovereignty): Always returns validation_status

TDD: RED phase - these tests define the expected behavior.
"""

import os
import tempfile

import pytest


class TestWriteTool:
    """Test WriteTool MCP tool."""

    def test_tool_metadata(self):
        """Test tool has correct metadata."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        assert tool.get_name() == "octave_write"
        # Description contains "writing" which satisfies the semantic requirement
        desc_lower = tool.get_description().lower()
        assert "writ" in desc_lower or "write" in desc_lower
        assert "octave" in desc_lower

    def test_tool_schema(self):
        """Test tool input schema has required parameters."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()
        schema = tool.get_input_schema()

        # Required parameter
        assert "target_path" in schema["properties"]
        assert "target_path" in schema["required"]

        # Optional parameters
        assert "content" in schema["properties"]
        assert "changes" in schema["properties"]
        assert "mutations" in schema["properties"]
        assert "base_hash" in schema["properties"]
        assert "schema" in schema["properties"]

        # content and changes are optional (mutually exclusive)
        assert "content" not in schema.get("required", [])
        assert "changes" not in schema.get("required", [])

    @pytest.mark.asyncio
    async def test_write_content_mode_new_file(self):
        """Test creating a new file with content mode."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            result = await tool.execute(
                target_path=target_path,
                content="===TEST===\nKEY::value\n===END===",
            )

            # Unified envelope per D2 design
            assert result["status"] == "success"
            assert result["path"] == target_path
            assert "canonical_hash" in result
            assert "corrections" in result
            assert isinstance(result["corrections"], list)
            assert "diff" in result
            assert "errors" in result
            assert isinstance(result["errors"], list)
            # I5: validation_status must be present
            assert "validation_status" in result
            assert result["validation_status"] in ["VALIDATED", "UNVALIDATED", "PENDING_INFRASTRUCTURE"]

            # Verify file was written
            assert os.path.exists(target_path)

    @pytest.mark.asyncio
    async def test_write_content_mode_overwrite_existing(self):
        """Test overwriting an existing file with content mode."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            # Create initial file
            with open(target_path, "w") as f:
                f.write("===OLD===\nOLD::content\n===END===")

            result = await tool.execute(
                target_path=target_path,
                content="===NEW===\nNEW::content\n===END===",
            )

            assert result["status"] == "success"

            # Verify file was overwritten
            with open(target_path) as f:
                content = f.read()
                assert "NEW" in content
                assert "OLD" not in content

    @pytest.mark.asyncio
    async def test_write_changes_mode_update_existing(self):
        """Test updating an existing file with changes mode."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            # Create initial file
            with open(target_path, "w") as f:
                f.write("===TEST===\nKEY::old_value\n===END===")

            result = await tool.execute(
                target_path=target_path,
                changes={"KEY": "new_value"},
            )

            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_write_changes_mode_requires_existing_file(self):
        """Test that changes mode errors when file doesn't exist."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "nonexistent.oct.md")

            result = await tool.execute(
                target_path=target_path,
                changes={"KEY": "value"},
            )

            # Should error - can't amend non-existent file
            assert result["status"] == "error"
            assert "errors" in result
            assert len(result["errors"]) > 0

    @pytest.mark.asyncio
    async def test_write_content_xor_changes(self):
        """Test that content and changes are mutually exclusive."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            result = await tool.execute(
                target_path=target_path,
                content="===TEST===\nKEY::value\n===END===",
                changes={"KEY": "value"},  # Both provided - should error
            )

            # Should error - mutually exclusive
            assert result["status"] == "error"
            assert "errors" in result
            # Error should mention mutual exclusivity
            error_messages = " ".join(e.get("message", "") for e in result["errors"])
            assert "content" in error_messages.lower() or "changes" in error_messages.lower()

    @pytest.mark.asyncio
    async def test_write_neither_content_nor_changes(self):
        """Test that either content or changes must be provided."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            result = await tool.execute(
                target_path=target_path,
                # Neither content nor changes provided
            )

            # Should error - need one of them
            assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_write_tristate_delete_sentinel(self):
        """Test I2: DELETE sentinel removes field entirely."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            # Create file with field to delete
            with open(target_path, "w") as f:
                f.write("===TEST===\nKEY::value\nDEPRECATED::old\n===END===")

            result = await tool.execute(
                target_path=target_path,
                changes={
                    "DEPRECATED": {"$op": "DELETE"},  # Delete this field
                },
            )

            assert result["status"] == "success"

            # Verify field was removed
            with open(target_path) as f:
                content = f.read()
                assert "DEPRECATED" not in content

    @pytest.mark.asyncio
    async def test_write_tristate_null_sets_empty(self):
        """Test I2: null value sets field to empty (not absence)."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            # Create file with field to clear
            with open(target_path, "w") as f:
                f.write("===TEST===\nNOTES::has content\n===END===")

            result = await tool.execute(
                target_path=target_path,
                changes={
                    "NOTES": None,  # Set to null/empty (not delete)
                },
            )

            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_write_base_hash_content_mode(self):
        """Test CAS guard in content/overwrite mode."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            # Create initial file and get its hash
            initial_content = "===TEST===\nKEY::value\n===END==="
            with open(target_path, "w") as f:
                f.write(initial_content)

            import hashlib

            correct_hash = hashlib.sha256(initial_content.encode()).hexdigest()

            # Correct hash should succeed
            result1 = await tool.execute(
                target_path=target_path,
                content="===NEW===\nNEW::content\n===END===",
                base_hash=correct_hash,
            )
            assert result1["status"] == "success"

    @pytest.mark.asyncio
    async def test_write_base_hash_mismatch_content_mode(self):
        """Test CAS guard rejects mismatched hash in content mode."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            # Create initial file
            with open(target_path, "w") as f:
                f.write("===TEST===\nKEY::value\n===END===")

            wrong_hash = "0" * 64

            # Wrong hash should fail
            result = await tool.execute(
                target_path=target_path,
                content="===NEW===\nNEW::content\n===END===",
                base_hash=wrong_hash,
            )
            assert result["status"] == "error"
            assert any("E_HASH" in e.get("code", "") for e in result["errors"])

    @pytest.mark.asyncio
    async def test_write_base_hash_changes_mode(self):
        """Test CAS guard in changes/amend mode."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            # Create initial file and get its hash
            initial_content = "===TEST===\nKEY::value\n===END==="
            with open(target_path, "w") as f:
                f.write(initial_content)

            import hashlib

            correct_hash = hashlib.sha256(initial_content.encode()).hexdigest()

            # Correct hash should succeed
            result = await tool.execute(
                target_path=target_path,
                changes={"KEY": "new_value"},
                base_hash=correct_hash,
            )
            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_write_base_hash_mismatch_changes_mode(self):
        """Test CAS guard rejects mismatched hash in changes mode."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            # Create initial file
            with open(target_path, "w") as f:
                f.write("===TEST===\nKEY::value\n===END===")

            wrong_hash = "0" * 64

            # Wrong hash should fail
            result = await tool.execute(
                target_path=target_path,
                changes={"KEY": "new_value"},
                base_hash=wrong_hash,
            )
            assert result["status"] == "error"
            assert any("E_HASH" in e.get("code", "") for e in result["errors"])

    @pytest.mark.asyncio
    async def test_write_mutations_applied(self):
        """Test that mutations parameter applies META field overrides."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            result = await tool.execute(
                target_path=target_path,
                content="===TEST===\nKEY::value\n===END===",
                mutations={"VERSION": "2.0", "STATUS": "DRAFT"},
            )

            # Should succeed (mutations accepted)
            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_write_schema_validation(self):
        """Test that schema parameter triggers validation."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            result = await tool.execute(
                target_path=target_path,
                content="===TEST===\nKEY::value\n===END===",
                schema="TEST",
            )

            assert result["status"] == "success"
            # I5: validation_status should be present
            assert "validation_status" in result

    @pytest.mark.asyncio
    async def test_write_path_security(self):
        """Test path traversal is prevented."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            malicious_path = os.path.join(tmpdir, "../evil.oct.md")

            result = await tool.execute(
                target_path=malicious_path,
                content="===TEST===\nKEY::value\n===END===",
            )

            assert result["status"] == "error"
            assert any("E_PATH" in e.get("code", "") for e in result["errors"])

    @pytest.mark.asyncio
    async def test_write_invalid_extension(self):
        """Test that invalid extensions are rejected."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            bad_path = os.path.join(tmpdir, "test.exe")

            result = await tool.execute(
                target_path=bad_path,
                content="===TEST===\nKEY::value\n===END===",
            )

            assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_write_valid_extensions(self):
        """Test that valid extensions are accepted."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        valid_extensions = [".oct.md", ".octave", ".md"]

        for ext in valid_extensions:
            with tempfile.TemporaryDirectory() as tmpdir:
                target_path = os.path.join(tmpdir, f"test{ext}")

                result = await tool.execute(
                    target_path=target_path,
                    content="===TEST===\nKEY::value\n===END===",
                )

                assert result["status"] == "success", f"Extension {ext} should be allowed"

    @pytest.mark.asyncio
    async def test_write_error_envelope_format(self):
        """Test error envelope format matches D2 spec."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        # Trigger error with invalid path
        result = await tool.execute(
            target_path="/invalid/../path.exe",
            content="===TEST===\nKEY::value\n===END===",
        )

        # Error envelope format per D2 design
        assert result["status"] == "error"
        assert "errors" in result
        assert isinstance(result["errors"], list)

        if result["errors"]:
            error = result["errors"][0]
            assert "code" in error
            assert "message" in error
            # Error codes should be E_PATH, E_PARSE, E_HASH, E_WRITE, E_INPUT
            assert error["code"].startswith("E_")

        # Corrections may be partially filled before failure
        assert "corrections" in result

    @pytest.mark.asyncio
    async def test_write_i5_validation_status_always_present(self):
        """Test I5: validation_status is always returned."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            result = await tool.execute(
                target_path=target_path,
                content="===TEST===\nKEY::value\n===END===",
            )

            assert result["status"] == "success"
            # I5: validation_status must always be present
            assert "validation_status" in result
            assert result["validation_status"] in ["VALIDATED", "UNVALIDATED", "PENDING_INFRASTRUCTURE"]

    @pytest.mark.asyncio
    async def test_write_i4_returns_corrections_and_diff(self):
        """Test I4: corrections and diff are always returned for auditing."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            result = await tool.execute(
                target_path=target_path,
                content="===TEST===\nFLOW::A -> B\n===END===",
            )

            assert result["status"] == "success"
            # I4: corrections and diff must be present
            assert "corrections" in result
            assert isinstance(result["corrections"], list)
            assert "diff" in result

    @pytest.mark.asyncio
    async def test_write_canonical_hash_unique(self):
        """Test that canonical_hash is unique for different content."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            path1 = os.path.join(tmpdir, "test1.oct.md")
            path2 = os.path.join(tmpdir, "test2.oct.md")

            result1 = await tool.execute(
                target_path=path1,
                content="===TEST===\nKEY::value1\n===END===",
            )

            result2 = await tool.execute(
                target_path=path2,
                content="===TEST===\nKEY::value2\n===END===",
            )

            # Different content should have different hashes
            assert result1["canonical_hash"] != result2["canonical_hash"]

    @pytest.mark.asyncio
    async def test_write_symlink_rejection(self):
        """Test that symlinks are rejected for security."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            real_path = os.path.join(tmpdir, "real.oct.md")
            link_path = os.path.join(tmpdir, "link.oct.md")

            # Create real file
            with open(real_path, "w") as f:
                f.write("===TEST===\nKEY::value\n===END===")

            # Create symlink
            os.symlink(real_path, link_path)

            # Writing to symlink should be rejected
            result = await tool.execute(
                target_path=link_path,
                content="===NEW===\nNEW::content\n===END===",
            )

            assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_write_atomic_operation(self):
        """Test that writes are atomic (temp file + rename)."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            result = await tool.execute(
                target_path=target_path,
                content="===TEST===\nKEY::value\n===END===",
            )

            assert result["status"] == "success"

            # File should exist with no temp files left behind
            files = os.listdir(tmpdir)
            assert "test.oct.md" in files
            # No .tmp files should remain
            tmp_files = [f for f in files if f.endswith(".tmp")]
            assert len(tmp_files) == 0


class TestWriteToolI5SchemaSovereignty:
    """Tests for I5 (Schema Sovereignty) requirement in octave_write.

    North Star I5 states:
    - A document processed without schema validation shall be marked as UNVALIDATED
    - Schema-validated documents shall record the schema name and version used
    - Schema bypass shall be visible, never silent

    Current state: validation_status is "PENDING_INFRASTRUCTURE" which is a silent bypass.
    Required state: validation_status must be "UNVALIDATED" to make bypass visible.
    """

    @pytest.mark.asyncio
    async def test_i5_write_validation_status_is_unvalidated_on_success(self):
        """I5: validation_status must be UNVALIDATED when no schema validator exists."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            result = await tool.execute(
                target_path=target_path,
                content="===TEST===\nKEY::value\n===END===",
            )

            assert result["status"] == "success"
            # I5 REQUIREMENT: Must be UNVALIDATED, not PENDING_INFRASTRUCTURE
            assert result["validation_status"] == "UNVALIDATED", (
                f"I5 violation: validation_status should be 'UNVALIDATED' to make bypass visible, "
                f"but got '{result['validation_status']}'"
            )

    @pytest.mark.asyncio
    async def test_i5_write_validation_status_is_unvalidated_on_error(self):
        """I5: validation_status must be UNVALIDATED even on error responses."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Trigger error with path traversal
            result = await tool.execute(
                target_path=os.path.join(tmpdir, "../evil.oct.md"),
                content="===TEST===\nKEY::value\n===END===",
            )

            assert result["status"] == "error"
            # I5: Even error responses must have visible bypass status
            assert result["validation_status"] == "UNVALIDATED", (
                f"I5 violation: validation_status should be 'UNVALIDATED' even on error, "
                f"but got '{result['validation_status']}'"
            )

    @pytest.mark.asyncio
    async def test_i5_write_validation_status_not_pending_infrastructure(self):
        """I5: Schema bypass must be visible, never silent.

        PENDING_INFRASTRUCTURE implies "we'll get to it" - this is silent bypass.
        UNVALIDATED explicitly states "this was not validated" - visible bypass.
        """
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            result = await tool.execute(
                target_path=target_path,
                content="===TEST===\nSTATUS::active\n===END===",
            )

            # Value must not be the silent PENDING_INFRASTRUCTURE placeholder
            assert result["validation_status"] != "PENDING_INFRASTRUCTURE", (
                "I5 violation: PENDING_INFRASTRUCTURE is a silent bypass. "
                "Must use UNVALIDATED to make bypass visible."
            )


class TestWriteToolSchemaValidation:
    """Tests for schema validation wiring in octave_write.

    I5 North Star requirement:
    - "Schema-validated documents shall record the schema name and version used"
    - "Schema bypass shall be visible, never silent"

    These tests verify that when a schema is provided, actual validation occurs.
    """

    @pytest.mark.asyncio
    async def test_write_without_schema_returns_unvalidated(self):
        """When no schema param provided, validation_status should be UNVALIDATED."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            result = await tool.execute(
                target_path=target_path,
                content="===TEST===\nKEY::value\n===END===",
                # No schema param
            )

            assert result["status"] == "success"
            assert result["validation_status"] == "UNVALIDATED"

    @pytest.mark.asyncio
    async def test_write_with_unknown_schema_returns_unvalidated(self):
        """When unknown schema provided, validation_status should be UNVALIDATED."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            result = await tool.execute(
                target_path=target_path,
                content="===TEST===\nKEY::value\n===END===",
                schema="NONEXISTENT_SCHEMA",
            )

            assert result["status"] == "success"
            assert result["validation_status"] == "UNVALIDATED"

    @pytest.mark.asyncio
    async def test_write_with_meta_schema_valid_content_returns_validated(self):
        """When META schema provided with valid content, should return VALIDATED.

        I5: Schema-validated documents shall record the schema name and version used.
        """
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        # Valid META content with required fields (TYPE, VERSION)
        valid_meta_content = """===TEST===
META:
  TYPE::"TEST_DOCUMENT"
  VERSION::"1.0.0"
  STATUS::ACTIVE
---
KEY::value
===END==="""

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            result = await tool.execute(
                target_path=target_path,
                content=valid_meta_content,
                schema="META",
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
    async def test_write_with_meta_schema_invalid_content_returns_invalid(self):
        """When META schema provided with invalid content, should return INVALID.

        I5: Schema bypass shall be visible, never silent.
        """
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        # Invalid META content - missing required TYPE field
        invalid_meta_content = """===TEST===
META:
  VERSION::"1.0.0"
---
KEY::value
===END==="""

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            result = await tool.execute(
                target_path=target_path,
                content=invalid_meta_content,
                schema="META",
            )

            assert result["status"] == "success"  # Operation succeeded, content is invalid
            # I5: Must return INVALID when schema validation fails
            assert result["validation_status"] == "INVALID", (
                f"I5 violation: Should be INVALID when META schema validation fails, "
                f"got '{result['validation_status']}'"
            )
            # Should record schema info even on invalid
            assert result.get("schema_name") == "META", "I5: schema_name should be recorded even on INVALID"

    @pytest.mark.asyncio
    async def test_write_with_meta_schema_missing_version_returns_invalid(self):
        """META schema requires VERSION field - missing it should return INVALID."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        # Invalid META content - missing required VERSION field
        invalid_meta_content = """===TEST===
META:
  TYPE::"TEST_DOCUMENT"
---
KEY::value
===END==="""

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            result = await tool.execute(
                target_path=target_path,
                content=invalid_meta_content,
                schema="META",
            )

            assert result["status"] == "success"
            assert (
                result["validation_status"] == "INVALID"
            ), f"META schema requires VERSION field, got '{result['validation_status']}'"

    @pytest.mark.asyncio
    async def test_write_schema_validation_errors_included_in_response(self):
        """When validation fails, specific errors should be in response."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        # Content missing both TYPE and VERSION
        invalid_content = """===TEST===
META:
  STATUS::ACTIVE
---
KEY::value
===END==="""

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            result = await tool.execute(
                target_path=target_path,
                content=invalid_content,
                schema="META",
            )

            assert result["validation_status"] == "INVALID"
            # Should have validation_errors with details about missing fields
            errors = result.get("validation_errors", [])
            assert len(errors) >= 1, "Should report at least one validation error for missing required fields"


class TestWriteToolDotNotationChanges:
    """Tests for dot-notation path support in changes mode.

    Dot-notation allows updating nested fields:
    - "META.STATUS": "ACTIVE" -> updates doc.meta["STATUS"]
    - "META.NEW_FIELD": "value" -> adds field to doc.meta
    - "META.FIELD": {"$op": "DELETE"} -> removes field from doc.meta
    - "META": {...} -> replaces entire META block (existing behavior)
    - Top-level keys still work (regression)
    """

    @pytest.mark.asyncio
    async def test_dot_notation_updates_meta_field(self):
        """Test dot notation updates existing META field in META block."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            # Create file with META block
            initial = """===TEST===
META:
  TYPE::"TEST_DOC"
  STATUS::DRAFT
---
KEY::value
===END==="""
            with open(target_path, "w") as f:
                f.write(initial)

            # Update META.STATUS using dot notation
            result = await tool.execute(
                target_path=target_path,
                changes={"META.STATUS": "ACTIVE"},
            )

            assert result["status"] == "success"

            # Verify META.STATUS was updated WITHIN the META block
            with open(target_path) as f:
                content = f.read()
                # ACTIVE should appear in META block (after META:, before ---)
                lines = content.split("\n")
                in_meta = False
                found_active_in_meta = False
                for line in lines:
                    if line.strip().startswith("META:"):
                        in_meta = True
                    elif line.strip() == "---":
                        in_meta = False
                    elif in_meta and "STATUS" in line and "ACTIVE" in line:
                        found_active_in_meta = True

                assert found_active_in_meta, f"ACTIVE should be in META block, not as top-level key. Got:\n{content}"
                # DRAFT should be gone (replaced by ACTIVE)
                assert "DRAFT" not in content
                # TYPE should be preserved
                assert "TEST_DOC" in content
                # Should NOT have 'META.STATUS' as literal key
                assert "META.STATUS::" not in content

    @pytest.mark.asyncio
    async def test_dot_notation_adds_new_meta_field(self):
        """Test dot notation adds new META field in META block."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            # Create file with META block
            initial = """===TEST===
META:
  TYPE::"TEST_DOC"
---
KEY::value
===END==="""
            with open(target_path, "w") as f:
                f.write(initial)

            # Add new META.VERSION field using dot notation
            result = await tool.execute(
                target_path=target_path,
                changes={"META.VERSION": "1.0.0"},
            )

            assert result["status"] == "success"

            # Verify new field was added WITHIN the META block
            with open(target_path) as f:
                content = f.read()
                # VERSION should appear in META block (after META:, before ---)
                lines = content.split("\n")
                in_meta = False
                found_version_in_meta = False
                for line in lines:
                    if line.strip().startswith("META:"):
                        in_meta = True
                    elif line.strip() == "---":
                        in_meta = False
                    elif in_meta and "VERSION" in line and "1.0.0" in line:
                        found_version_in_meta = True

                assert found_version_in_meta, f"VERSION should be in META block, not as top-level key. Got:\n{content}"
                # TYPE should be preserved
                assert "TEST_DOC" in content
                # Should NOT have 'META.VERSION' as literal key
                assert "META.VERSION::" not in content

    @pytest.mark.asyncio
    async def test_dot_notation_deletes_meta_field(self):
        """Test dot notation deletes META field with DELETE sentinel."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            # Create file with META block with DEPRECATED field
            initial = """===TEST===
META:
  TYPE::"TEST_DOC"
  DEPRECATED::old_stuff
---
KEY::value
===END==="""
            with open(target_path, "w") as f:
                f.write(initial)

            # Delete META.DEPRECATED using dot notation + DELETE sentinel
            result = await tool.execute(
                target_path=target_path,
                changes={"META.DEPRECATED": {"$op": "DELETE"}},
            )

            assert result["status"] == "success"

            # Verify field was deleted
            with open(target_path) as f:
                content = f.read()
                assert "DEPRECATED" not in content
                # TYPE should be preserved
                assert "TEST_DOC" in content

    @pytest.mark.asyncio
    async def test_meta_dict_replaces_entire_block(self):
        """Test META={...} replaces entire META block (not dot notation)."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            # Create file with META block
            initial = """===TEST===
META:
  TYPE::"TEST_DOC"
  OLD_FIELD::should_be_gone
---
KEY::value
===END==="""
            with open(target_path, "w") as f:
                f.write(initial)

            # Replace entire META block
            result = await tool.execute(
                target_path=target_path,
                changes={"META": {"TYPE": "NEW_DOC", "VERSION": "2.0"}},
            )

            assert result["status"] == "success"

            # Verify META was replaced
            with open(target_path) as f:
                content = f.read()
                # New fields should be present
                assert "NEW_DOC" in content or "TYPE" in content
                assert "2.0" in content or "VERSION" in content
                # Old field should be gone (replaced)
                assert "OLD_FIELD" not in content
                # Should NOT have malformed dict syntax
                assert "{'TYPE'" not in content

    @pytest.mark.asyncio
    async def test_top_level_changes_still_work_regression(self):
        """Test top-level changes still work (regression test)."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            # Create file with top-level assignment
            initial = """===TEST===
KEY::old_value
OTHER::preserved
===END==="""
            with open(target_path, "w") as f:
                f.write(initial)

            # Update top-level KEY
            result = await tool.execute(
                target_path=target_path,
                changes={"KEY": "new_value"},
            )

            assert result["status"] == "success"

            # Verify update worked
            with open(target_path) as f:
                content = f.read()
                assert "new_value" in content
                assert "preserved" in content

    @pytest.mark.asyncio
    async def test_dot_notation_multiple_meta_fields(self):
        """Test dot notation can update multiple META fields at once."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            # Create file with META block
            initial = """===TEST===
META:
  TYPE::"TEST_DOC"
  STATUS::DRAFT
  VERSION::"0.1"
---
KEY::value
===END==="""
            with open(target_path, "w") as f:
                f.write(initial)

            # Update multiple META fields at once
            result = await tool.execute(
                target_path=target_path,
                changes={
                    "META.STATUS": "ACTIVE",
                    "META.VERSION": "1.0.0",
                },
            )

            assert result["status"] == "success"

            # Verify updates are in META block
            with open(target_path) as f:
                content = f.read()
                # Both updates should be in META block
                lines = content.split("\n")
                in_meta = False
                found_active = False
                found_version = False
                for line in lines:
                    if line.strip().startswith("META:"):
                        in_meta = True
                    elif line.strip() == "---":
                        in_meta = False
                    elif in_meta:
                        if "STATUS" in line and "ACTIVE" in line:
                            found_active = True
                        if "VERSION" in line and "1.0.0" in line:
                            found_version = True

                assert found_active, f"ACTIVE should be in META block. Got:\n{content}"
                assert found_version, f"1.0.0 should be in META block. Got:\n{content}"
                # Old values should be gone
                assert "DRAFT" not in content
                assert "0.1" not in content
                # TYPE should be preserved
                assert "TEST_DOC" in content
                # Should NOT have literal META.* keys
                assert "META.STATUS::" not in content
                assert "META.VERSION::" not in content


class TestStructuralMetrics:
    """Tests for structural metrics extraction (Issue #92).

    The _generate_diff() function needs to report structural changes between
    input and output documents. This test class verifies the metrics extraction
    and structural diff functionality.
    """

    def test_extract_structural_metrics_counts_sections(self):
        """Test extract_structural_metrics() counts sections correctly."""
        from octave_mcp.core.parser import parse
        from octave_mcp.mcp.write import extract_structural_metrics

        # Document with 2 numbered sections
        content = """===TEST===

\u00a71::FIRST_SECTION
  KEY1::value1

\u00a72::SECOND_SECTION
  KEY2::value2

===END==="""

        doc = parse(content)
        metrics = extract_structural_metrics(doc)

        assert metrics.sections == 2, f"Expected 2 sections, got {metrics.sections}"

    def test_extract_structural_metrics_counts_section_markers(self):
        """Test extract_structural_metrics() identifies section markers."""
        from octave_mcp.core.parser import parse
        from octave_mcp.mcp.write import extract_structural_metrics

        # Document with section markers
        content = """===DOC===

\u00a71::CORE
  RULE::one

\u00a72::SECONDARY
  RULE::two

===END==="""

        doc = parse(content)
        metrics = extract_structural_metrics(doc)

        # section_markers tracks the section IDs found
        assert "1" in metrics.section_markers
        assert "2" in metrics.section_markers

    def test_extract_structural_metrics_counts_blocks(self):
        """Test extract_structural_metrics() counts blocks correctly."""
        from octave_mcp.core.parser import parse
        from octave_mcp.mcp.write import extract_structural_metrics

        # Document with 2 blocks
        content = """===TEST===
OUTER_BLOCK:
  INNER_KEY::value
SECOND_BLOCK:
  ANOTHER_KEY::value
===END==="""

        doc = parse(content)
        metrics = extract_structural_metrics(doc)

        assert metrics.blocks == 2, f"Expected 2 blocks, got {metrics.blocks}"

    def test_extract_structural_metrics_counts_assignments(self):
        """Test extract_structural_metrics() counts assignments correctly."""
        from octave_mcp.core.parser import parse
        from octave_mcp.mcp.write import extract_structural_metrics

        # Document with 3 assignments (including nested)
        content = """===TEST===
TOP::value1
BLOCK:
  NESTED::value2
  ANOTHER::value3
===END==="""

        doc = parse(content)
        metrics = extract_structural_metrics(doc)

        assert metrics.assignments == 3, f"Expected 3 assignments, got {metrics.assignments}"

    def test_generate_diff_no_changes(self):
        """Test _generate_diff() returns 'No changes' for identical documents."""
        from octave_mcp.core.parser import parse
        from octave_mcp.mcp.write import WriteTool, extract_structural_metrics

        tool = WriteTool()

        content = "===TEST===\nKEY::value\n===END==="
        doc = parse(content)
        metrics = extract_structural_metrics(doc)
        diff = tool._generate_diff(len(content), len(content), metrics, metrics)

        assert diff == "No changes", f"Expected 'No changes', got '{diff}'"

    def test_generate_diff_detects_section_marker_removal(self):
        """Test _generate_diff() detects section marker removal (W_STRUCT_001)."""
        from octave_mcp.core.parser import parse
        from octave_mcp.mcp.write import WriteTool, extract_structural_metrics

        tool = WriteTool()

        original = """===TEST===

\u00a71::FIRST
  KEY::value

\u00a72::SECOND
  OTHER::value

===END==="""

        # Canonical form after some operation removes section markers
        canonical = """===TEST===
KEY::value
OTHER::value
===END==="""

        original_doc = parse(original)
        canonical_doc = parse(canonical)
        original_metrics = extract_structural_metrics(original_doc)
        canonical_metrics = extract_structural_metrics(canonical_doc)

        diff = tool._generate_diff(len(original), len(canonical), original_metrics, canonical_metrics)

        # Should contain warning code W_STRUCT_001 for section marker loss
        assert "W_STRUCT_001" in diff, f"Expected W_STRUCT_001 warning, got: {diff}"
        assert "section" in diff.lower(), f"Expected 'section' in diff message: {diff}"

    def test_generate_diff_detects_assignment_reduction(self):
        """Test _generate_diff() detects assignment count reduction (W_STRUCT_003)."""
        from octave_mcp.core.parser import parse
        from octave_mcp.mcp.write import WriteTool, extract_structural_metrics

        tool = WriteTool()

        original = """===TEST===
KEY1::value1
KEY2::value2
KEY3::value3
===END==="""

        # Fewer assignments in output
        canonical = """===TEST===
KEY1::value1
===END==="""

        original_doc = parse(original)
        canonical_doc = parse(canonical)
        original_metrics = extract_structural_metrics(original_doc)
        canonical_metrics = extract_structural_metrics(canonical_doc)

        diff = tool._generate_diff(len(original), len(canonical), original_metrics, canonical_metrics)

        # Should contain warning code W_STRUCT_003 for assignment reduction
        assert "W_STRUCT_003" in diff, f"Expected W_STRUCT_003 warning, got: {diff}"

    def test_generate_diff_structural_summary_format(self):
        """Test structural summary format in _generate_diff() response."""
        from octave_mcp.core.parser import parse
        from octave_mcp.mcp.write import WriteTool, extract_structural_metrics

        tool = WriteTool()

        # Use content with different byte lengths to trigger non-"No changes" path
        original = """===TEST===
KEY::old_value_here
===END==="""

        canonical = """===TEST===
KEY::new
===END==="""

        original_doc = parse(original)
        canonical_doc = parse(canonical)
        original_metrics = extract_structural_metrics(original_doc)
        canonical_metrics = extract_structural_metrics(canonical_doc)

        diff = tool._generate_diff(len(original), len(canonical), original_metrics, canonical_metrics)

        # Diff should include structural metrics (byte count at minimum)
        assert "bytes" in diff.lower() or "->" in diff, f"Expected structural info in diff: {diff}"

    @pytest.mark.asyncio
    async def test_octave_write_includes_structural_diff(self):
        """Test that octave_write response envelope contains structural diff."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            # Create file with sections
            original = """===TEST===

\u00a71::SECTION_ONE
  KEY::value

===END==="""

            with open(target_path, "w") as f:
                f.write(original)

            # Modify via changes
            result = await tool.execute(
                target_path=target_path,
                changes={"KEY": "new_value"},
            )

            assert result["status"] == "success"
            # diff field should contain structural information
            assert "diff" in result
            # Diff should not just be empty or "No changes" for real changes
            assert result["diff"], "diff field should contain structural summary"
