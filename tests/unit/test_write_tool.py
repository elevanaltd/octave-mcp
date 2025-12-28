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
