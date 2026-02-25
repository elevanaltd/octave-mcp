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
        assert "lenient" in schema["properties"]
        assert "corrections_only" in schema["properties"]
        assert "parse_error_policy" in schema["properties"]

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
    async def test_write_content_mode_accepts_markdown_fence(self):
        """Strict mode should accept an OCTAVE payload wrapped in markdown fence."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "fenced.oct.md")

            result = await tool.execute(
                target_path=target_path,
                content="""```octave
===TEST===
KEY::value
===END===
```""",
            )

            assert result["status"] == "success"
            assert any(c.get("code") == "W_MARKDOWN_UNWRAP" for c in result.get("corrections", []))

            with open(target_path, encoding="utf-8") as f:
                written = f.read()
            assert written.startswith("===TEST===")

    @pytest.mark.asyncio
    async def test_write_corrections_only_does_not_write(self):
        """Test corrections_only mode returns preview but does not write file."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "preview.oct.md")

            result = await tool.execute(
                target_path=target_path,
                content="===TEST===\nKEY::value\n===END===",
                corrections_only=True,
            )

            assert result["status"] == "success"
            assert result["path"] == target_path
            assert "canonical_hash" in result
            assert "diff_unified" in result
            assert isinstance(result["corrections"], list)
            assert not os.path.exists(target_path)

    @pytest.mark.asyncio
    async def test_write_lenient_plain_text_wraps_into_canonical_doc(self):
        """Test lenient mode can canonicalize plain text input without OCTAVE syntax."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "plain.oct.md")

            result = await tool.execute(
                target_path=target_path,
                content="Design system needs authentication before allowing access\nSecond line of notes",
                lenient=True,
            )

            assert result["status"] == "success"
            assert os.path.exists(target_path)
            assert any(c.get("code") == "W_STRUCT_RAW_WRAP" for c in result.get("corrections", []))

            with open(target_path, encoding="utf-8") as f:
                written = f.read()
            assert "BODY:" in written
            assert "RAW::" in written

    @pytest.mark.asyncio
    async def test_write_lenient_schema_repair_enum_casefold(self):
        """Test lenient mode applies safe schema repairs (enum casefold) when schema provided."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "meta.oct.md")

            result = await tool.execute(
                target_path=target_path,
                content='===META_SCHEMA===\nMETA:\n  TYPE::META\n  VERSION::"1.0.0"\n  STATUS::draft\n===END===',
                schema="META",
                lenient=True,
            )

            assert result["status"] == "success"
            assert result["validation_status"] == "VALIDATED"

            with open(target_path, encoding="utf-8") as f:
                written = f.read()
            assert "STATUS::DRAFT" in written

            # Repair log should be reflected in corrections
            assert any(c.get("code") == "ENUM_CASEFOLD" for c in result.get("corrections", []))

    @pytest.mark.asyncio
    async def test_write_lenient_parse_error_policy_salvage_handles_lexer_errors(self):
        """Test optional salvage mode can emit canonical carrier on lexer errors.

        Issue #177: Now uses localized salvaging that preserves document envelope
        and wraps only failing lines.
        """
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "salvage.oct.md")

            result = await tool.execute(
                target_path=target_path,
                content="===DOC===\nKEY::a\tb\n===END===",
                lenient=True,
                parse_error_policy="salvage",
            )

            assert result["status"] == "success"
            assert os.path.exists(target_path)
            # Issue #177: Check for localized salvage correction codes
            correction_codes = [c.get("code", "") for c in result.get("corrections", [])]
            assert any(
                code in ("W_SALVAGE_LOCALIZED", "W_SALVAGE_LINE", "W_SALVAGE_WRAP") for code in correction_codes
            ), f"Expected salvage correction code, got: {correction_codes}"

            with open(target_path, encoding="utf-8") as f:
                written = f.read()
            # Issue #177: Document envelope should be preserved (DOC not replaced)
            assert "===DOC===" in written
            # Should have error marker for the failing line
            assert "_PARSE_ERROR_LINE_" in written or "RAW::" in written

    @pytest.mark.asyncio
    async def test_write_lenient_parse_error_policy_error_fails_on_lexer_error(self):
        """Test default error policy returns an error when lenient parsing fails."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "error.oct.md")

            result = await tool.execute(
                target_path=target_path,
                content="===DOC===\nKEY::a\tb\n===END===",
                lenient=True,
                parse_error_policy="error",
            )

            assert result["status"] == "error"

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
    async def test_write_neither_content_nor_changes_nonexistent_file(self):
        """Test that normalize mode (no content, no changes) errors on non-existent file."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            result = await tool.execute(
                target_path=target_path,
                # Neither content nor changes = normalize mode, but file doesn't exist
            )

            # Should error - normalize requires existing file
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
            assert os.path.exists(target_path)

            with open(target_path, encoding="utf-8") as f:
                written = f.read()
            assert "META:" in written
            assert '  VERSION::"2.0"' in written
            assert "  STATUS::DRAFT" in written

    @pytest.mark.asyncio
    async def test_write_schema_definition_validation_missing_required_field(self):
        """SchemaDefinition-backed validation should mark INVALID when required fields are missing."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            content = """===TEST===
DEBATE_TRANSCRIPT:
  TOPIC::topic
  MODE::fixed
  STATUS::active
===END==="""

            result = await tool.execute(
                target_path=target_path,
                content=content,
                schema="DEBATE_TRANSCRIPT",
            )

            assert result["status"] == "success"
            assert result["validation_status"] == "INVALID"
            assert "validation_errors" in result
            assert any(err.get("field", "").endswith(".THREAD_ID") for err in result["validation_errors"])

    @pytest.mark.asyncio
    async def test_write_schema_definition_validation_valid_document(self):
        """SchemaDefinition-backed validation should mark VALIDATED for valid content."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            content = """===TEST===
DEBATE_TRANSCRIPT:
  THREAD_ID::test-debate-001
  TOPIC::Whether AI should use OCTAVE format
  MODE::fixed
  STATUS::active
  PARTICIPANTS::[Wind, Wall, Door]
  TURNS::[turn1, turn2]
  MAX_ROUNDS::4
  MAX_TURNS::12
===END==="""

            result = await tool.execute(
                target_path=target_path,
                content=content,
                schema="DEBATE_TRANSCRIPT",
            )

            assert result["status"] == "success"
            assert result["validation_status"] == "VALIDATED"

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
            # GH#264: Error message should include path and corrections_only hint
            error_msg = result["errors"][0]["message"]
            assert link_path in error_msg, f"Symlink error should include the path '{link_path}', got: {error_msg}"
            assert (
                "corrections_only=true" in error_msg
            ), f"Symlink error should include corrections_only hint, got: {error_msg}"

    @pytest.mark.asyncio
    async def test_write_permission_denied_error_message(self):
        """GH#264: Permission denied errors should include path and corrections_only hint."""
        from unittest.mock import patch

        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "readonly.oct.md")

            # Mock os.replace to raise PermissionError (simulates read-only target)
            with patch("os.replace", side_effect=PermissionError("Permission denied")):
                result = await tool.execute(
                    target_path=target_path,
                    content="===TEST===\nKEY::value\n===END===",
                )

            assert result["status"] == "error"
            error_msg = result["errors"][0]["message"]
            assert (
                "Permission denied" in error_msg
            ), f"Permission error should mention 'Permission denied', got: {error_msg}"
            assert (
                target_path in error_msg
            ), f"Permission error should include the path '{target_path}', got: {error_msg}"
            assert (
                "corrections_only=true" in error_msg
            ), f"Permission error should include corrections_only hint, got: {error_msg}"

    @pytest.mark.asyncio
    async def test_write_generic_error_includes_hint(self):
        """GH#264: Generic write errors should include corrections_only hint."""
        from unittest.mock import patch

        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            # Mock os.replace to raise a generic OS error
            with patch("os.replace", side_effect=OSError("Disk full")):
                result = await tool.execute(
                    target_path=target_path,
                    content="===TEST===\nKEY::value\n===END===",
                )

            assert result["status"] == "error"
            error_msg = result["errors"][0]["message"]
            assert (
                "corrections_only=true" in error_msg
            ), f"Generic write error should include corrections_only hint, got: {error_msg}"

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
            assert (
                result["validation_status"] != "PENDING_INFRASTRUCTURE"
            ), "I5 violation: PENDING_INFRASTRUCTURE is a silent bypass. Must use UNVALIDATED to make bypass visible."


class TestWriteToolDebugGrammar:
    """Tests for debug_grammar parameter in octave_write.

    Feature parity with octave_validate: debug_grammar should return
    compiled constraint grammar for debugging constraint evaluation.
    """

    @pytest.mark.asyncio
    async def test_write_debug_grammar_returns_compiled_regexes(self):
        """Test debug_grammar=True returns compiled constraint regexes."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        # Valid META content with schema
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
                debug_grammar=True,
            )

            assert result["status"] == "success"

            # debug_info should be present when debug_grammar=True and schema provided
            assert "debug_info" in result, "debug_info should be present when debug_grammar=True"

            debug_info = result["debug_info"]
            assert "schema_name" in debug_info
            # Schema name from loaded SchemaDefinition (may differ from parameter)
            assert debug_info["schema_name"] in ["META", "META_SCHEMA"], f"Got schema_name: {debug_info['schema_name']}"
            assert "field_constraints" in debug_info

            # Should have constraint info for META fields
            field_constraints = debug_info["field_constraints"]
            assert isinstance(field_constraints, dict)

            # Each field should have chain and compiled_regex
            for field_name, constraint_info in field_constraints.items():
                assert "chain" in constraint_info, f"Field {field_name} should have chain"
                assert "compiled_regex" in constraint_info, f"Field {field_name} should have compiled_regex"
                assert isinstance(constraint_info["compiled_regex"], str), "compiled_regex should be string"


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
    async def test_changes_mode_meta_dot_notation_list_produces_valid_octave(self):
        """Test META dot-notation list values emit valid OCTAVE syntax.

        CRS BLOCKING BUG: META dot-notation updates bypass normalization.

        ROOT CAUSE:
        - write.py::doc.meta[field_name] = new_value (line 338-347)
        - emitter.py::emit_meta() uses emit_value(value)
        - emitter.py::unknown types -> return str(value) -> "['alpha', 'beta']"

        REQUIREMENT:
        - META.TAGS with ["alpha", "beta"] must emit as [alpha,beta] (valid OCTAVE)
        - NOT ['alpha', 'beta'] (Python str(list) - INVALID OCTAVE)

        I1 (Syntactic Fidelity): All values must emit canonical OCTAVE syntax.
        """
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

            # Update META.TAGS using dot notation with a LIST value
            result = await tool.execute(
                target_path=target_path,
                changes={"META.TAGS": ["alpha", "beta"]},
            )

            assert result["status"] == "success"

            # Verify the output is VALID OCTAVE syntax
            with open(target_path) as f:
                content = f.read()

                # MUST have valid OCTAVE list syntax: [alpha,beta]
                # MUST NOT have Python list str() syntax: ['alpha', 'beta']
                assert "['alpha', 'beta']" not in content, (
                    f"BUG: META dot-notation produced invalid OCTAVE syntax. "
                    f"Found Python str(list) instead of OCTAVE list. Content:\n{content}"
                )
                assert '["alpha", "beta"]' not in content, (
                    f"BUG: META dot-notation produced invalid OCTAVE syntax. "
                    f"Found Python repr(list) instead of OCTAVE list. Content:\n{content}"
                )
                # Should contain valid OCTAVE list (with or without quotes on items)
                # Valid forms: [alpha,beta] or ["alpha","beta"]
                assert "TAGS::" in content, f"TAGS field should be present. Content:\n{content}"
                # The emitted value should be parseable - check for opening bracket
                lines = content.split("\n")
                for line in lines:
                    if "TAGS::" in line:
                        # Extract value after ::
                        value_part = line.split("::", 1)[1].strip()
                        # Should start with [ and end with ] (valid list)
                        assert value_part.startswith(
                            "["
                        ), f"TAGS value should be a list starting with [, got: {value_part}"
                        assert value_part.endswith("]"), f"TAGS value should be a list ending with ], got: {value_part}"
                        # Should NOT have Python string quotes around list items
                        # Valid: [alpha,beta] or ["alpha","beta"]
                        # Invalid: ['alpha', 'beta'] (Python repr)
                        assert (
                            "'" not in value_part or value_part.count("'") == 0
                        ), f"TAGS value has Python-style single quotes (invalid OCTAVE): {value_part}"
                        break

    @pytest.mark.asyncio
    async def test_changes_mode_meta_full_replacement_list_produces_valid_octave(self):
        """Test full META block replacement with lists emits valid OCTAVE.

        Companion test to ensure full META replacement also normalizes lists.
        """
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

            # Replace entire META block with a dict containing a list
            result = await tool.execute(
                target_path=target_path,
                changes={"META": {"TYPE": "NEW_DOC", "TAGS": ["one", "two", "three"]}},
            )

            assert result["status"] == "success"

            # Verify the output is VALID OCTAVE syntax
            with open(target_path) as f:
                content = f.read()

                # MUST NOT have Python list syntax
                assert (
                    "['one', 'two', 'three']" not in content
                ), f"BUG: Full META replacement produced invalid OCTAVE. Content:\n{content}"
                # Should have valid OCTAVE list
                assert "TAGS::" in content

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

    def test_generate_diff_detects_value_change_same_length(self):
        """Test _generate_diff reports changes when content differs but length/structure same.

        Regression test for Issue #92: When content changes but preserves byte count
        and structural metrics (e.g., KEY::foo -> KEY::bar), _generate_diff must NOT
        return "No changes". This violates I4 (Auditability) - all changes must be
        visible in the diff.

        Root cause: The original implementation only checked byte counts and
        structural metrics, missing actual content comparison.

        Fix: Add content_changed parameter that the caller computes and passes in.
        """
        from octave_mcp.core.parser import parse
        from octave_mcp.mcp.write import WriteTool, extract_structural_metrics

        tool = WriteTool()

        # Original and canonical have SAME byte count and SAME structure
        # but DIFFERENT content values
        original = "===TEST===\nKEY::foo\n===END==="
        canonical = "===TEST===\nKEY::bar\n===END==="

        # Verify byte counts are identical (the bug condition)
        assert len(original) == len(canonical), "Test setup: byte counts must be equal"

        # Verify structural metrics are identical (the bug condition)
        original_doc = parse(original)
        canonical_doc = parse(canonical)
        original_metrics = extract_structural_metrics(original_doc)
        canonical_metrics = extract_structural_metrics(canonical_doc)

        assert original_metrics.sections == canonical_metrics.sections
        assert original_metrics.blocks == canonical_metrics.blocks
        assert original_metrics.assignments == canonical_metrics.assignments

        # The content HAS changed (foo -> bar)
        content_changed = original != canonical
        assert content_changed, "Test setup: content must differ"

        # Call _generate_diff with content_changed=True
        diff = tool._generate_diff(
            len(original),
            len(canonical),
            original_metrics,
            canonical_metrics,
            content_changed=True,
        )

        # I4 REQUIREMENT: Must NOT return "No changes" when content changed
        assert diff != "No changes", (
            "I4 violation: _generate_diff returned 'No changes' even though content "
            "changed from 'foo' to 'bar'. Diff should indicate content was modified."
        )
        # Should indicate bytes AND that content changed
        assert "bytes" in diff.lower() or "->" in diff, f"Diff should include byte count info, got: {diff}"

    @pytest.mark.asyncio
    async def test_hermetic_schema_resolution_with_latest(self):
        """Test that octave_write uses hermetic resolution for schema='latest'.

        Issue #150: octave_write must use resolve_hermetic_standard from hydrator
        instead of bypassing to get_builtin_schema directly.

        This tests the hermetic resolution path for frozen@ and latest schema references.
        """
        from pathlib import Path

        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            # Create a test standard in local cache
            cache_dir = Path(tmpdir) / ".octave" / "standards"
            cache_dir.mkdir(parents=True, exist_ok=True)
            default_schema = cache_dir / "default.oct.md"

            # Write a minimal schema (doesn't need to be valid, just needs to exist)
            default_schema.write_text("===SCHEMA===\n===END===")

            # Test that schema="latest" attempts hermetic resolution
            # This should fail in RED phase because write.py currently uses get_builtin_schema
            # which doesn't support "latest" - it will return None and remain UNVALIDATED

            # In GREEN phase, when we integrate resolve_hermetic_standard,
            # the cache_dir parameter will need to be passed through somehow
            # For now, we test that attempting to use "latest" doesn't crash
            result = await tool.execute(
                target_path=target_path,
                content="===TEST===\nKEY::value\n===END===",
                schema="latest",
            )

            # RED phase expectation: get_builtin_schema("latest") returns None
            # so validation is skipped and validation_status remains UNVALIDATED
            assert result["status"] == "success"
            assert (
                result["validation_status"] == "UNVALIDATED"
            ), "Expected UNVALIDATED because get_builtin_schema doesn't handle 'latest'"

            # GREEN phase will change this behavior:
            # resolve_hermetic_standard("latest", cache_dir) -> loads schema -> VALIDATED/INVALID


class TestWriteToolNestedDictSerialization:
    """Tests for Issue #176: Nested dicts should produce valid OCTAVE, not Python repr.

    ROOT CAUSE:
    - _normalize_value_for_ast() handles lists (wrapping in ListValue) but passes dicts unchanged
    - emit_value() falls back to str(value) for unknown types
    - str(dict) produces Python repr like "{'sub': 1}" which is INVALID OCTAVE

    REQUIREMENT:
    - Nested dicts in changes parameter must emit valid OCTAVE syntax
    - Either as InlineMap [key::value] or Block structure
    - NOT as Python repr {'key': 'value'}
    """

    @pytest.mark.asyncio
    async def test_changes_nested_dict_produces_valid_octave_not_python_repr(self):
        """Issue #176: Nested dicts should produce valid OCTAVE, not Python repr.

        RED PHASE: This test proves the bug exists.

        When changes parameter contains a nested dict like {'my_field': {'sub': 1}},
        the output should contain valid OCTAVE syntax like my_field::[sub::1]
        NOT my_field::{'sub': 1} (Python repr - INVALID OCTAVE).
        """
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            # Create initial file
            initial = """===TEST===
KEY::old_value
===END==="""
            with open(target_path, "w") as f:
                f.write(initial)

            # Apply changes with nested dict
            result = await tool.execute(
                target_path=target_path,
                changes={"CONFIG": {"sub_key": "sub_value", "num": 42}},
            )

            assert result["status"] == "success"

            # Read the output file
            with open(target_path) as f:
                content = f.read()

            # CRITICAL: Must NOT contain Python dict repr syntax
            assert "{'sub_key'" not in content, (
                f"BUG (Issue #176): Nested dict produced Python repr instead of valid OCTAVE. "
                f"Found Python dict syntax in output:\n{content}"
            )
            assert "{'num'" not in content, (
                f"BUG (Issue #176): Nested dict produced Python repr instead of valid OCTAVE. "
                f"Found Python dict syntax in output:\n{content}"
            )
            # Check for various Python repr forms
            assert "'sub_key':" not in content, f"Found Python dict syntax:\n{content}"
            assert '"sub_key":' not in content.replace("sub_key::", ""), f"Found Python dict syntax:\n{content}"

            # MUST contain valid OCTAVE structure
            # Either InlineMap: CONFIG::[sub_key::sub_value,num::42]
            # Or Block: CONFIG:\n  sub_key::sub_value\n  num::42
            assert "CONFIG::" in content or "CONFIG:" in content, f"CONFIG field should be present. Content:\n{content}"

            # The nested values should be accessible
            assert "sub_value" in content, f"sub_value should be in output:\n{content}"
            assert "42" in content, f"42 should be in output:\n{content}"

    @pytest.mark.asyncio
    async def test_changes_deeply_nested_dict_produces_valid_octave(self):
        """Issue #176: Deeply nested dicts should also produce valid OCTAVE.

        Tests recursive normalization of nested structures.
        """
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            # Create initial file
            initial = """===TEST===
KEY::value
===END==="""
            with open(target_path, "w") as f:
                f.write(initial)

            # Apply changes with deeply nested dict
            result = await tool.execute(
                target_path=target_path,
                changes={"OUTER": {"inner": {"deep": "value"}}},
            )

            assert result["status"] == "success"

            with open(target_path) as f:
                content = f.read()

            # CRITICAL: Must NOT contain any Python dict repr
            assert "{'" not in content, f"BUG (Issue #176): Deeply nested dict produced Python repr:\n{content}"
            assert "': " not in content, f"BUG (Issue #176): Deeply nested dict produced Python repr:\n{content}"

            # Deep value should be accessible
            assert "value" in content

    @pytest.mark.asyncio
    async def test_changes_dict_with_list_values_produces_valid_octave(self):
        """Issue #176: Dict containing list values should produce valid OCTAVE.

        Tests mixed nested structures (dict with list).
        """
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            # Create initial file
            initial = """===TEST===
KEY::value
===END==="""
            with open(target_path, "w") as f:
                f.write(initial)

            # Apply changes with dict containing list
            result = await tool.execute(
                target_path=target_path,
                changes={"CONFIG": {"items": ["a", "b", "c"]}},
            )

            assert result["status"] == "success"

            with open(target_path) as f:
                content = f.read()

            # CRITICAL: Must NOT contain Python dict repr
            assert "{'" not in content, f"BUG (Issue #176): Dict with list produced Python repr:\n{content}"
            # Also must NOT contain Python list repr
            assert "['a'" not in content, f"BUG: List produced Python repr:\n{content}"

            # Values should be present in valid OCTAVE format
            assert "a" in content
            assert "b" in content
            assert "c" in content

    @pytest.mark.asyncio
    async def test_normalize_value_for_ast_handles_nested_dict(self):
        """Unit test for _normalize_value_for_ast with nested dicts.

        This directly tests the normalization function to verify it converts
        dicts to proper AST structures.
        """
        from octave_mcp.core.ast_nodes import Block, InlineMap
        from octave_mcp.mcp.write import _normalize_value_for_ast

        # Test simple nested dict
        nested_dict = {"key1": "value1", "key2": 42}
        result = _normalize_value_for_ast(nested_dict)

        # Result should be an AST type, not a raw dict
        assert not isinstance(result, dict), (
            f"BUG (Issue #176): _normalize_value_for_ast should convert dict to AST type, "
            f"got {type(result).__name__}"
        )

        # Should be either InlineMap or Block
        assert isinstance(
            result, InlineMap | Block
        ), f"Expected InlineMap or Block for nested dict, got {type(result).__name__}"


class TestSalvageModeLocalizedErrorWrapping:
    """Tests for Issue #177: Salvage mode should wrap only failing lines, not entire file.

    PROBLEM:
    When salvage mode encounters a parse error (like unterminated string), it wraps
    the ENTIRE file content into a generic ===DOC=== with BODY::RAW. This destroys
    the document's top-level structure.

    REQUIREMENT:
    - Preserve document envelope name (===MY_PROJECT=== not ===DOC===)
    - Preserve valid sections/fields that parsed successfully
    - Wrap only the failing line/content with appropriate error markers
    - I4 (Auditability): corrections must log exactly what was salvaged and why
    - I3 (Mirror Constraint): reflect what's present, don't invent structure

    ROOT CAUSE:
    write.py lines 779-790 wraps everything into generic DOC envelope on any parse failure.
    """

    @pytest.mark.asyncio
    async def test_salvage_mode_preserves_document_envelope_name(self):
        """Issue #177: Salvage mode should preserve document envelope name, not replace with DOC.

        When parsing fails, the original document name should be preserved, not replaced
        with a generic 'DOC' envelope.
        """
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            # Content with valid envelope but a parse error (unterminated string)
            # The tab character causes a lexer error
            content = """===MY_PROJECT===
META:
  TYPE::CONFIG
FIELD1::value1
BROKEN::a\tb
FIELD2::value2
===END==="""

            result = await tool.execute(
                target_path=target_path,
                content=content,
                lenient=True,
                parse_error_policy="salvage",
            )

            assert result["status"] == "success"
            assert os.path.exists(target_path)

            with open(target_path, encoding="utf-8") as f:
                written = f.read()

            # CRITICAL: Document envelope name should be preserved
            assert "===MY_PROJECT===" in written, (
                f"Issue #177 BUG: Document envelope name was not preserved. "
                f"Expected '===MY_PROJECT===' but got content:\n{written}"
            )
            # Should NOT have generic DOC envelope
            assert "===DOC===" not in written, (
                f"Issue #177 BUG: Salvage mode replaced document name with generic DOC. " f"Content:\n{written}"
            )

    @pytest.mark.asyncio
    async def test_salvage_mode_preserves_valid_fields(self):
        """Issue #177: Salvage mode should preserve valid fields that parsed successfully.

        Fields that parse correctly should remain accessible in their original form,
        not wrapped into BODY::RAW.
        """
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            # Content with some valid fields and one broken field
            content = """===CONFIG===
VALID1::good_value
BROKEN::has\ttab
VALID2::also_good
===END==="""

            result = await tool.execute(
                target_path=target_path,
                content=content,
                lenient=True,
                parse_error_policy="salvage",
            )

            assert result["status"] == "success"

            with open(target_path, encoding="utf-8") as f:
                written = f.read()

            # Valid fields should be preserved as-is, not wrapped in BODY::RAW
            assert "VALID1::good_value" in written or "VALID1" in written, (
                f"Issue #177 BUG: Valid field VALID1 was not preserved. " f"Content:\n{written}"
            )
            assert "VALID2::also_good" in written or "VALID2" in written, (
                f"Issue #177 BUG: Valid field VALID2 was not preserved. " f"Content:\n{written}"
            )

    @pytest.mark.asyncio
    async def test_salvage_mode_wraps_only_failing_line(self):
        """Issue #177: Salvage mode should wrap only the failing line, not entire content.

        Only the problematic content should be wrapped with an error marker.
        """
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            # Content with one broken line
            content = """===TEST===
GOOD::value
BAD::has\ttab\there
ALSO_GOOD::fine
===END==="""

            result = await tool.execute(
                target_path=target_path,
                content=content,
                lenient=True,
                parse_error_policy="salvage",
            )

            assert result["status"] == "success"

            with open(target_path, encoding="utf-8") as f:
                written = f.read()

            # The entire content should NOT be in a single BODY::RAW field
            # If it is, that means localized salvaging failed
            raw_field_count = written.count("RAW::")

            # BODY::RAW wrapping entire content is the bug - should have at most one
            # error marker for the broken line, not the entire file as RAW
            if "BODY:" in written and raw_field_count == 1:
                # Check if the RAW content contains the entire file (bug)
                # by looking for valid fields inside RAW
                # If GOOD::value appears inside RAW, that's wrong
                raw_start = written.find("RAW::")
                if raw_start != -1:
                    raw_content = written[raw_start:]
                    if "GOOD::value" in raw_content:
                        pytest.fail(
                            f"Issue #177 BUG: Entire file wrapped in RAW instead of only failing line. "
                            f"Content:\n{written}"
                        )

    @pytest.mark.asyncio
    async def test_salvage_mode_corrections_log_what_was_salvaged(self):
        """Issue #177: I4 Auditability - corrections must log what was salvaged.

        When content is salvaged, the corrections log should describe:
        - Which line(s) had errors
        - What the original content was
        - Why it was wrapped (the error)
        """
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            content = """===AUDIT===
OK::value
PROBLEM::a\tb
===END==="""

            result = await tool.execute(
                target_path=target_path,
                content=content,
                lenient=True,
                parse_error_policy="salvage",
            )

            assert result["status"] == "success"

            # Should have salvage-related corrections
            corrections = result.get("corrections", [])
            salvage_corrections = [c for c in corrections if "SALVAGE" in c.get("code", "").upper()]

            assert len(salvage_corrections) > 0, (
                f"Issue #177: No salvage corrections found. "
                f"I4 requires auditability of what was salvaged. "
                f"Corrections: {corrections}"
            )

            # At least one correction should indicate line-level salvaging
            # not just "wrapped entire file"
            # Check that corrections have meaningful messages about salvaging
            assert any(
                "salvage" in c.get("message", "").lower() or "line" in c.get("message", "").lower()
                for c in salvage_corrections
            ), f"Expected salvage corrections to mention salvaging or line, got: {salvage_corrections}"

    @pytest.mark.asyncio
    async def test_salvage_mode_meta_block_preserved(self):
        """Issue #177: META block should be preserved even when body has errors.

        The META block, if valid, should remain intact when only the body has issues.
        """
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            content = """===WITH_META===
META:
  TYPE::TEST
  VERSION::"1.0"
---
GOOD_FIELD::value
BROKEN_FIELD::has\ttab
===END==="""

            result = await tool.execute(
                target_path=target_path,
                content=content,
                lenient=True,
                parse_error_policy="salvage",
            )

            assert result["status"] == "success"

            with open(target_path, encoding="utf-8") as f:
                written = f.read()

            # META block should be preserved
            assert "META:" in written, f"Issue #177 BUG: META block was not preserved. Content:\n{written}"
            assert (
                "TYPE::" in written or "TYPE" in written
            ), f"Issue #177 BUG: META.TYPE was not preserved. Content:\n{written}"

    @pytest.mark.asyncio
    async def test_salvage_mode_error_line_escaping_integrity(self):
        """Issue #177: Error line markers should preserve content fidelity via emit_value.

        Regression test for CE recommendation: ensure error markers don't double-escape
        when content contains backslashes or quotes. The emitter handles escaping,
        so we pass raw content without pre-escaping.
        """
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            # Content with a failing line that contains backslashes and quotes
            content = """===TEST===
GOOD::value
BROKEN::path\\\\to\\\\file with "quotes"
===END==="""

            result = await tool.execute(
                target_path=target_path,
                content=content,
                lenient=True,
                parse_error_policy="salvage",
            )

            assert result["status"] == "success"

            with open(target_path, encoding="utf-8") as f:
                written = f.read()

            # The error marker should contain the escaped content (once, not double-escaped)
            # Looking for a _PARSE_ERROR_LINE marker that includes the backslash content
            assert "_PARSE_ERROR_LINE" in written, f"Expected error marker for failing line. Content:\n{written}"

            # The written content should be valid OCTAVE (parseable)
            # If double-escaping occurred, it would have extra backslashes
            # that would break the format or parse incorrectly
            from octave_mcp.core.parser import parse

            try:
                parsed = parse(written)
                # Success - content is valid OCTAVE
                assert parsed is not None
            except Exception as e:
                pytest.fail(
                    f"Salvaged content should be valid OCTAVE after escaping fix. "
                    f"Parse error: {e}\nContent:\n{written}"
                )


class TestSalvageBracketDepthAwareness:
    """Issue #248 Bug 2: _localized_salvage must handle multi-line nested bracket blocks.

    When salvage mode processes content with multi-line nested [...]  blocks,
    lines like `],` and `]` are syntactically valid ONLY in the context of an
    open bracket. Tested in isolation they fail, causing false _PARSE_ERROR_LINE_N
    wrapping that destroys document structure.

    The fix must track bracket depth so that continuation lines inside brackets
    are accumulated and tested as a complete block, not individually.
    """

    @pytest.mark.asyncio
    async def test_salvage_simple_multiline_brackets_no_false_errors(self):
        """Issue #248: Multi-line bracket block should not produce false _PARSE_ERROR markers.

        When salvage is triggered by a genuine error (tab character), multi-line bracket
        blocks in the same document must not have their `[` and `]` lines wrapped
        as _PARSE_ERROR. These lines are only invalid when tested in isolation.
        """
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            # Tab on BROKEN line triggers full parse failure -> salvage path.
            # The multi-line bracket block must survive salvage intact.
            content = (
                "===BRACKET_TEST===\n"
                "META:\n"
                "  TYPE::TEST\n"
                "CORE::[\n"
                "  ROLE::AGENT,\n"
                "  MISSION::BUILD\n"
                "]\n"
                "BROKEN::has\ttab\n"
                "===END==="
            )

            result = await tool.execute(
                target_path=target_path,
                content=content,
                lenient=True,
                parse_error_policy="salvage",
            )

            assert result["status"] == "success"

            with open(target_path, encoding="utf-8") as f:
                written = f.read()

            # Count _PARSE_ERROR markers - only the BROKEN line should be wrapped
            import re

            parse_error_markers = re.findall(r"_PARSE_ERROR_LINE_\d+", written)
            # Only 1 genuine error (the tab line), not the bracket lines
            assert len(parse_error_markers) <= 1, (
                f"Issue #248 BUG: Expected at most 1 _PARSE_ERROR (for tab line), "
                f"got {len(parse_error_markers)}: {parse_error_markers}. "
                f"Bracket lines were falsely wrapped. Content:\n{written}"
            )

            # CORE bracket structure should be preserved as a field, not as error markers
            assert "CORE::" in written, f"CORE field should be preserved. Content:\n{written}"

    @pytest.mark.asyncio
    async def test_salvage_deeply_nested_brackets_three_levels(self):
        """Issue #248: Deeply nested (3+ levels) bracket blocks should survive salvage.

        When a genuine error triggers salvage, deeply nested structures like:
            OUTER::[
              INNER::[
                DEEP::[A,B,C]
              ],
              OTHER::VALUE
            ]
        must not produce false _PARSE_ERROR markers on `[` and `]` lines.
        """
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            content = (
                "===DEEP_NEST===\n"
                "META:\n"
                "  TYPE::TEST\n"
                "OUTER::[\n"
                "  INNER::[\n"
                "    DEEP::[A,B,C]\n"
                "  ],\n"
                "  OTHER::VALUE\n"
                "]\n"
                "BAD::x\ty\n"
                "===END==="
            )

            result = await tool.execute(
                target_path=target_path,
                content=content,
                lenient=True,
                parse_error_policy="salvage",
            )

            assert result["status"] == "success"

            with open(target_path, encoding="utf-8") as f:
                written = f.read()

            import re

            parse_error_markers = re.findall(r"_PARSE_ERROR_LINE_\d+", written)
            # Only 1 genuine error (the tab line)
            assert len(parse_error_markers) <= 1, (
                f"Issue #248 BUG: Expected at most 1 _PARSE_ERROR (for tab line), "
                f"got {len(parse_error_markers)}: {parse_error_markers}. "
                f"Deeply nested bracket lines were falsely wrapped. Content:\n{written}"
            )

            # Verify structural preservation
            assert "OUTER::" in written, f"OUTER should be preserved. Content:\n{written}"

    @pytest.mark.asyncio
    async def test_salvage_mixed_valid_brackets_and_genuine_errors(self):
        """Issue #248: Multi-line brackets should survive but genuine errors still get wrapped.

        Content mixing multi-line bracket blocks with actual broken syntax should:
        - Preserve bracket blocks without false _PARSE_ERROR on [ or ] lines
        - Still wrap genuinely broken lines (e.g., tabs) as _PARSE_ERROR
        """
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            content = (
                "===MIXED===\n"
                "META:\n"
                "  TYPE::TEST\n"
                "LIST::[\n"
                "  A,\n"
                "  B,\n"
                "  C\n"
                "]\n"
                "BROKEN::has\ttab\n"
                "SIMPLE::value\n"
                "===END==="
            )

            result = await tool.execute(
                target_path=target_path,
                content=content,
                lenient=True,
                parse_error_policy="salvage",
            )

            assert result["status"] == "success"

            with open(target_path, encoding="utf-8") as f:
                written = f.read()

            # The broken line (with tab) SHOULD still be wrapped as _PARSE_ERROR
            assert (
                "_PARSE_ERROR" in written
            ), f"Genuine parse error (tab character) should still be wrapped. Content:\n{written}"

            # The valid bracket content and simple fields should be preserved
            assert "LIST::" in written, f"LIST bracket block should be preserved. Content:\n{written}"
            assert "SIMPLE::" in written, f"SIMPLE field should be preserved. Content:\n{written}"

    @pytest.mark.asyncio
    async def test_salvage_multiline_bracket_with_trailing_comma(self):
        """Issue #248: Closing `],` (bracket with trailing comma) must not become _PARSE_ERROR.

        This is the exact pattern from the bug report:
            CORE::[
              ROLE::AGENT_NAME,
              ACTIVATION::[
                FORCE::STRUCTURE,
                ESSENCE::ARCHITECT
              ],
              MISSION::SOMETHING
            ]
        The `],` and `]` lines fail isolation testing and get wrapped.
        """
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            content = (
                "===AGENT===\n"
                "META:\n"
                "  TYPE::AGENT\n"
                "CORE::[\n"
                "  ROLE::AGENT_NAME,\n"
                "  ACTIVATION::[\n"
                "    FORCE::STRUCTURE,\n"
                "    ESSENCE::ARCHITECT\n"
                "  ],\n"
                "  MISSION::SOMETHING\n"
                "]\n"
                "ERR::a\tb\n"
                "===END==="
            )

            result = await tool.execute(
                target_path=target_path,
                content=content,
                lenient=True,
                parse_error_policy="salvage",
            )

            assert result["status"] == "success"

            with open(target_path, encoding="utf-8") as f:
                written = f.read()

            import re

            parse_error_markers = re.findall(r"_PARSE_ERROR_LINE_\d+", written)
            # Only 1 genuine error (the tab line), not the bracket lines
            assert len(parse_error_markers) <= 1, (
                f"Issue #248 BUG: Expected at most 1 _PARSE_ERROR (for tab line), "
                f"got {len(parse_error_markers)}: {parse_error_markers}. "
                f"Bracket continuation lines like '],', ']' were falsely wrapped. Content:\n{written}"
            )

            # The nested structure should be preserved
            assert "CORE::" in written, f"CORE should be preserved. Content:\n{written}"

    @pytest.mark.asyncio
    async def test_salvage_bracket_block_parseable_output(self):
        """Issue #248: Salvaged content with bracket blocks must be parseable OCTAVE.

        The output from salvage mode must be valid OCTAVE that can be parsed again,
        even when bracket blocks are present alongside genuine errors.
        """
        from octave_mcp.core.parser import parse as octave_parse
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            content = (
                "===PARSEABLE===\n"
                "META:\n"
                "  TYPE::TEST\n"
                "DATA::[\n"
                "  ITEM1::VALUE1,\n"
                "  ITEM2::VALUE2\n"
                "]\n"
                "EXTRA::field\n"
                "BAD::x\ty\n"
                "===END==="
            )

            result = await tool.execute(
                target_path=target_path,
                content=content,
                lenient=True,
                parse_error_policy="salvage",
            )

            assert result["status"] == "success"

            with open(target_path, encoding="utf-8") as f:
                written = f.read()

            # Output must be parseable
            try:
                parsed = octave_parse(written)
                assert parsed is not None
            except Exception as e:
                pytest.fail(
                    f"Issue #248: Salvaged bracket content should produce parseable OCTAVE. "
                    f"Parse error: {e}\nContent:\n{written}"
                )

    @pytest.mark.asyncio
    async def test_salvage_brackets_inside_quoted_strings_not_counted(self):
        """Brackets inside quoted strings should not affect bracket depth tracking.

        Issue #248 CRS finding: REGEX::"[A-Z" contains a '[' inside quotes
        that should NOT increment bracket depth.
        """
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            # Content with brackets inside quoted strings and a genuine error (tab)
            content = "===TEST===\n" 'REGEX::"[A-Z]+"\n' "VALID::true\n" "\tBAD_TAB::error\n" "===END==="

            await tool.execute(
                target_path=target_path,
                content=content,
                lenient=True,
                parse_error_policy="salvage",
            )

            with open(target_path, encoding="utf-8") as f:
                written = f.read()

            # The quoted bracket should not cause bracket accumulation.
            # The REGEX and VALID lines should survive as normal keys.
            # The tab line should be a parse error.
            assert "REGEX" in written
            assert "VALID" in written
            assert "_PARSE_ERROR_LINE_" in written or "_SALVAGED" in written


class TestNormalizeMode:
    """Tests for normalize mode: octave_write with neither content nor changes.

    When both content and changes are None, octave_write should read the
    existing file, parse it, emit canonical form, and write it back.
    This is pure I1 (Syntactic Fidelity) enforcement.
    """

    @pytest.mark.asyncio
    async def test_normalize_existing_file(self):
        """Normalize mode reads, parses, emits canonical form, and writes back."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            # Write a file with non-canonical formatting (extra spaces, etc.)
            original = '===TEST===\nMETA:\n  TYPE::"EXAMPLE"\n  VERSION::"1.0"\nKEY::value\n===END==='
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(original)

            result = await tool.execute(target_path=target_path)

            assert result["status"] == "success"
            assert result["path"] == target_path
            assert result["mode"] == "normalize"
            assert "canonical_hash" in result
            assert result["canonical_hash"] != ""
            assert "corrections" in result
            assert isinstance(result["corrections"], list)
            assert "diff" in result
            assert "diff_unified" in result
            assert "errors" in result
            assert isinstance(result["errors"], list)
            assert "validation_status" in result

            # File should have been written with canonical content
            with open(target_path, encoding="utf-8") as f:
                written = f.read()
            assert "===TEST===" in written
            assert "KEY" in written

    @pytest.mark.asyncio
    async def test_normalize_nonexistent_file_errors(self):
        """Normalize mode should error when file does not exist."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "nonexistent.oct.md")

            result = await tool.execute(target_path=target_path)

            assert result["status"] == "error"
            assert any(e["code"] == "E_FILE" for e in result["errors"])

    @pytest.mark.asyncio
    async def test_normalize_corrections_only_dry_run(self):
        """Normalize with corrections_only=True returns diff without writing."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            original = '===TEST===\nMETA:\n  TYPE::"EXAMPLE"\n  VERSION::"1.0"\nKEY::value\n===END==='
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(original)

            result = await tool.execute(
                target_path=target_path,
                corrections_only=True,
            )

            assert result["status"] == "success"
            assert result["mode"] == "normalize"
            assert "canonical_hash" in result
            assert "diff_unified" in result

            # File should NOT have been modified (dry run)
            with open(target_path, encoding="utf-8") as f:
                content_after = f.read()
            assert content_after == original

    @pytest.mark.asyncio
    async def test_normalize_with_base_hash(self):
        """Normalize mode supports base_hash CAS guard."""
        import hashlib

        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            original = '===TEST===\nMETA:\n  TYPE::"EXAMPLE"\n  VERSION::"1.0"\nKEY::value\n===END==='
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(original)

            correct_hash = hashlib.sha256(original.encode("utf-8")).hexdigest()

            # Correct hash should succeed
            result = await tool.execute(
                target_path=target_path,
                base_hash=correct_hash,
            )
            assert result["status"] == "success"
            assert result["mode"] == "normalize"

    @pytest.mark.asyncio
    async def test_normalize_with_wrong_base_hash(self):
        """Normalize mode rejects wrong base_hash."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            original = '===TEST===\nMETA:\n  TYPE::"EXAMPLE"\n  VERSION::"1.0"\nKEY::value\n===END==='
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(original)

            result = await tool.execute(
                target_path=target_path,
                base_hash="wrong_hash_value",
            )
            assert result["status"] == "error"
            assert any(e["code"] == "E_HASH" for e in result["errors"])

    @pytest.mark.asyncio
    async def test_normalize_with_schema_validation(self):
        """Normalize mode supports schema validation (I5)."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            original = '===TEST===\nMETA:\n  TYPE::"EXAMPLE"\n  VERSION::"1.0"\nKEY::value\n===END==='
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(original)

            result = await tool.execute(
                target_path=target_path,
                schema="nonexistent_schema_xyz",
            )
            # Should succeed (schema not found = UNVALIDATED, not error)
            assert result["status"] == "success"
            assert result["mode"] == "normalize"
            assert result["validation_status"] == "UNVALIDATED"

    @pytest.mark.asyncio
    async def test_normalize_idempotent(self):
        """Normalizing an already-canonical file should produce identical output."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            # First, create a canonical file via content mode
            result1 = await tool.execute(
                target_path=target_path,
                content='===TEST===\nMETA:\n  TYPE::"EXAMPLE"\n  VERSION::"1.0"\nKEY::value\n===END===',
            )
            assert result1["status"] == "success"
            hash_after_create = result1["canonical_hash"]

            # Now normalize it - should produce same hash
            result2 = await tool.execute(target_path=target_path)
            assert result2["status"] == "success"
            assert result2["mode"] == "normalize"
            assert result2["canonical_hash"] == hash_after_create

    @pytest.mark.asyncio
    async def test_normalize_produces_audit_trail(self):
        """I4: Normalize operations must produce audit trail (corrections, diff)."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            original = '===TEST===\nMETA:\n  TYPE::"EXAMPLE"\n  VERSION::"1.0"\nKEY::value\n===END==='
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(original)

            result = await tool.execute(target_path=target_path)

            assert result["status"] == "success"
            assert result["mode"] == "normalize"
            # I4: corrections and diff must be present
            assert "corrections" in result
            assert "diff" in result
            assert "diff_unified" in result


class TestWriteGrammarHint:
    """GH#278: Tests for grammar_hint parameter on octave_write."""

    @pytest.mark.asyncio
    async def test_invalid_with_grammar_hint_true_returns_grammar(self):
        """INVALID + grammar_hint=True should include grammar_hint dict in response."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            # Document missing required TYPE field -> INVALID against META schema
            content = """===TEST===
META:
  VERSION::"1.0"
===END==="""

            result = await tool.execute(
                target_path=target_path,
                content=content,
                schema="META",
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
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            content = """===TEST===
META:
  VERSION::"1.0"
===END==="""

            result = await tool.execute(
                target_path=target_path,
                content=content,
                schema="META",
                grammar_hint=False,
            )

            assert result["validation_status"] == "INVALID"
            assert "grammar_hint" not in result

    @pytest.mark.asyncio
    async def test_invalid_default_no_grammar_hint(self):
        """INVALID + grammar_hint omitted (default False) should NOT include grammar_hint."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            content = """===TEST===
META:
  VERSION::"1.0"
===END==="""

            result = await tool.execute(
                target_path=target_path,
                content=content,
                schema="META",
            )

            assert result["validation_status"] == "INVALID"
            assert "grammar_hint" not in result

    @pytest.mark.asyncio
    async def test_valid_with_grammar_hint_true_no_grammar(self):
        """VALID + grammar_hint=True should NOT include grammar_hint (only on INVALID)."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            content = """===TEST===
META:
  TYPE::"META"
  VERSION::"1.0"
===END==="""

            result = await tool.execute(
                target_path=target_path,
                content=content,
                schema="META",
                grammar_hint=True,
            )

            assert result["validation_status"] == "VALIDATED"
            assert "grammar_hint" not in result

    @pytest.mark.asyncio
    async def test_no_schema_with_grammar_hint_true_no_grammar(self):
        """No schema provided + grammar_hint=True should NOT include grammar_hint."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            content = """===TEST===
KEY::value
===END==="""

            result = await tool.execute(
                target_path=target_path,
                content=content,
                grammar_hint=True,
            )

            # No schema -> UNVALIDATED
            assert result["validation_status"] == "UNVALIDATED"
            assert "grammar_hint" not in result

    @pytest.mark.asyncio
    async def test_grammar_hint_parameter_in_schema(self):
        """grammar_hint parameter should be declared in tool input schema."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()
        schema = tool.get_input_schema()
        assert "grammar_hint" in schema["properties"]
        assert schema["properties"]["grammar_hint"]["type"] == "boolean"

    @pytest.mark.asyncio
    async def test_grammar_hint_compile_failure(self, tmp_path, monkeypatch):
        """Grammar compilation failure returns error envelope, not raw exception."""
        from octave_mcp.core.gbnf_compiler import GBNFCompiler
        from octave_mcp.mcp.write import WriteTool

        monkeypatch.setattr(
            GBNFCompiler,
            "compile_schema",
            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("test failure")),
        )

        tool = WriteTool()
        target_path = str(tmp_path / "test_compile_fail.oct.md")

        # Document missing required TYPE field -> INVALID against META schema
        content = """===TEST===
META:
  VERSION::"1.0"
===END==="""

        result = await tool.execute(
            target_path=target_path,
            content=content,
            schema="META",
            grammar_hint=True,
        )

        assert result["validation_status"] == "INVALID"
        assert "grammar_hint" in result, "grammar_hint should be present even on compile failure"

        hint = result["grammar_hint"]
        assert hint["error"] == "E_GRAMMAR_COMPILE"
        assert isinstance(hint["message"], str)
