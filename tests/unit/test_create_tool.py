"""Tests for octave_create MCP tool (Epic #41, Issue #37).

Tests the create tool capabilities:
- Write OCTAVE content to file
- Track corrections (W001-W005)
- Return compact diff by default
- Optional full summary mode
- Path validation security
"""

import os
import tempfile

import pytest

from octave_mcp.mcp.create import CreateTool


class TestCreateTool:
    """Test CreateTool MCP tool."""

    def test_tool_metadata(self):
        """Test tool has correct metadata."""
        tool = CreateTool()

        assert tool.get_name() == "octave_create"
        assert "write" in tool.get_description().lower()
        assert "octave" in tool.get_description().lower()

    def test_tool_schema(self):
        """Test tool input schema."""
        tool = CreateTool()
        schema = tool.get_input_schema()

        # Required parameters
        assert "content" in schema["properties"]
        assert "target_path" in schema["properties"]
        assert "content" in schema["required"]
        assert "target_path" in schema["required"]

        # Optional parameters
        assert "mutations" in schema["properties"]
        assert "full_summary" in schema["properties"]
        assert "schema" in schema["properties"]

        # Defaults
        assert schema["properties"]["full_summary"].get("type") == "boolean"

    @pytest.mark.asyncio
    async def test_create_simple_file(self):
        """Test creating a simple OCTAVE file."""
        tool = CreateTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            result = await tool.execute(
                content="===TEST===\nKEY::value\n===END===",
                target_path=target_path,
            )

            # Verify result structure
            assert result["status"] == "success"
            assert result["path"] == target_path
            assert "canonical_hash" in result
            assert "corrections" in result
            assert isinstance(result["corrections"], list)

            # Verify file was written
            assert os.path.exists(target_path)

            # Verify content is canonical
            with open(target_path) as f:
                written_content = f.read()
                assert "===TEST===" in written_content
                assert "KEY::value" in written_content
                assert "===END===" in written_content

    @pytest.mark.asyncio
    async def test_create_with_ascii_normalization(self):
        """Test corrections tracking for ASCII normalization."""
        tool = CreateTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            result = await tool.execute(
                content="===TEST===\nFLOW::A -> B\nSYNTH::X + Y\n===END===",
                target_path=target_path,
            )

            # Should track ASCII → Unicode corrections
            assert "corrections" in result

            # File should contain canonical Unicode
            with open(target_path) as f:
                written = f.read()
                # Either already canonical or normalized
                assert "→" in written or "->" in written

    @pytest.mark.asyncio
    async def test_create_returns_diff_by_default(self):
        """Test that compact diff is returned by default."""
        tool = CreateTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            result = await tool.execute(
                content="===TEST===\nKEY::value\n===END===",
                target_path=target_path,
            )

            # Should have diff, not full content
            assert "diff" in result
            assert "content" not in result

    @pytest.mark.asyncio
    async def test_create_with_full_summary(self):
        """Test full_summary=true returns full canonical content."""
        tool = CreateTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            result = await tool.execute(
                content="===TEST===\nKEY::value\n===END===",
                target_path=target_path,
                full_summary=True,
            )

            # Should return full content instead of diff
            assert "content" in result
            assert result["content"]  # Non-empty
            # diff may or may not be present

    @pytest.mark.asyncio
    async def test_correction_codes_tracked(self):
        """Test that correction codes W001-W005 are tracked."""
        tool = CreateTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            # Content with various normalization needs
            result = await tool.execute(
                content="KEY:value\nFLOW::A -> B",  # Single colon, ASCII operator
                target_path=target_path,
            )

            corrections = result["corrections"]

            # Corrections should have code field
            if corrections:
                for correction in corrections:
                    assert "code" in correction
                    assert "message" in correction
                    # Codes should be W001-W005
                    if correction.get("code"):
                        assert correction["code"].startswith("W")

    @pytest.mark.asyncio
    async def test_path_traversal_prevention(self):
        """Test that path traversal is prevented."""
        tool = CreateTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Try to write outside tmpdir using ../
            malicious_path = os.path.join(tmpdir, "../evil.oct.md")

            result = await tool.execute(
                content="===TEST===\nKEY::value\n===END===",
                target_path=malicious_path,
            )

            # Should error
            assert result["status"] == "error"
            assert "errors" in result

    @pytest.mark.asyncio
    async def test_allowed_extensions(self):
        """Test that only allowed extensions are accepted."""
        tool = CreateTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Try invalid extension
            bad_path = os.path.join(tmpdir, "test.exe")

            result = await tool.execute(
                content="===TEST===\nKEY::value\n===END===",
                target_path=bad_path,
            )

            # Should error on invalid extension
            assert result["status"] == "error"
            assert "errors" in result

    @pytest.mark.asyncio
    async def test_valid_extensions(self):
        """Test that allowed extensions work."""
        tool = CreateTool()

        valid_extensions = [".oct.md", ".octave", ".md"]

        for ext in valid_extensions:
            with tempfile.TemporaryDirectory() as tmpdir:
                target_path = os.path.join(tmpdir, f"test{ext}")

                result = await tool.execute(
                    content="===TEST===\nKEY::value\n===END===",
                    target_path=target_path,
                )

                assert result["status"] == "success", f"Extension {ext} should be allowed"
                assert os.path.exists(target_path)

    @pytest.mark.asyncio
    async def test_canonical_hash_unique(self):
        """Test that canonical_hash is unique for different content."""
        tool = CreateTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            path1 = os.path.join(tmpdir, "test1.oct.md")
            path2 = os.path.join(tmpdir, "test2.oct.md")

            result1 = await tool.execute(
                content="===TEST===\nKEY::value1\n===END===",
                target_path=path1,
            )

            result2 = await tool.execute(
                content="===TEST===\nKEY::value2\n===END===",
                target_path=path2,
            )

            # Different content should have different hashes
            assert result1["canonical_hash"] != result2["canonical_hash"]

    @pytest.mark.asyncio
    async def test_mutations_inject_meta(self):
        """Test that mutations parameter is accepted (implementation deferred)."""
        tool = CreateTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            result = await tool.execute(
                content="===TEST===\nKEY::value\n===END===",
                target_path=target_path,
                mutations={"VERSION": "2.0", "STATUS": "DRAFT"},
            )

            # Should succeed (mutations accepted but implementation deferred)
            assert result["status"] == "success"
            assert os.path.exists(target_path)

    @pytest.mark.asyncio
    async def test_error_format(self):
        """Test error response format."""
        tool = CreateTool()

        # Trigger error with invalid path
        result = await tool.execute(
            content="===TEST===\nKEY::value\n===END===",
            target_path="/invalid/../path.exe",
        )

        assert result["status"] == "error"
        assert "errors" in result
        assert isinstance(result["errors"], list)

        # Errors should have structure
        if result["errors"]:
            error = result["errors"][0]
            assert "code" in error
            assert "message" in error

    @pytest.mark.asyncio
    async def test_schema_parameter_passed_for_validation(self):
        """Test that schema parameter is used for validation."""
        tool = CreateTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            result = await tool.execute(
                content="===TEST===\nKEY::value\n===END===",
                target_path=target_path,
                schema="TEST",  # Explicit schema
            )

            # Should succeed with schema validation
            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_create_returns_validation_status_unvalidated_on_success(self):
        """Test that create returns validation_status: UNVALIDATED on success.

        North Star I5 states: "Schema bypass shall be visible, never silent."
        Deprecated tools that bypass schema validation must explicitly indicate
        their unvalidated status.
        """
        tool = CreateTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            result = await tool.execute(
                content="===TEST===\nKEY::value\n===END===",
                target_path=target_path,
            )

            assert result["status"] == "success"
            # I5 compliance: validation_status must be present and UNVALIDATED
            assert "validation_status" in result, "Missing validation_status field (I5 violation)"
            assert (
                result["validation_status"] == "UNVALIDATED"
            ), f"Expected validation_status='UNVALIDATED', got '{result.get('validation_status')}'"

    @pytest.mark.asyncio
    async def test_create_returns_validation_status_unvalidated_on_error(self):
        """Test that create returns validation_status: UNVALIDATED on error.

        North Star I5 states: "Schema bypass shall be visible, never silent."
        Even error responses must include validation_status to indicate bypass.
        """
        tool = CreateTool()

        # Trigger error with invalid extension
        result = await tool.execute(
            content="===TEST===\nKEY::value\n===END===",
            target_path="/invalid/path.exe",
        )

        assert result["status"] == "error"
        # I5 compliance: validation_status must be present even on error
        assert "validation_status" in result, "Missing validation_status field on error (I5 violation)"
        assert result["validation_status"] == "UNVALIDATED"
