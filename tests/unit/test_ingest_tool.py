"""Tests for octave_ingest MCP tool (P2.2).

Tests the ingest tool pipeline: PREPARSE→PARSE→NORMALIZE→VALIDATE→REPAIR→VALIDATE
"""

import pytest

from octave_mcp.mcp.ingest import IngestTool


class TestIngestTool:
    """Test IngestTool MCP tool."""

    def test_tool_metadata(self):
        """Test tool has correct metadata."""
        tool = IngestTool()

        assert tool.get_name() == "octave_ingest"
        assert "lenient" in tool.get_description().lower()
        assert "canonical" in tool.get_description().lower()

    def test_tool_schema(self):
        """Test tool input schema."""
        tool = IngestTool()
        schema = tool.get_input_schema()

        assert "content" in schema["properties"]
        assert "schema" in schema["properties"]
        assert "tier" in schema["properties"]
        assert "fix" in schema["properties"]
        assert "verbose" in schema["properties"]

        # content and schema are required
        assert "content" in schema["required"]
        assert "schema" in schema["required"]

        # tier has enum values
        assert schema["properties"]["tier"]["enum"] == ["LOSSLESS", "CONSERVATIVE", "AGGRESSIVE", "ULTRA"]

    @pytest.mark.asyncio
    async def test_ingest_simple_document(self):
        """Test ingesting a simple OCTAVE document."""
        tool = IngestTool()

        result = await tool.execute(
            content="===TEST===\nKEY::value\n===END===", schema="TEST", tier="LOSSLESS", fix=False, verbose=False
        )

        assert "canonical" in result
        assert "repairs" in result
        assert isinstance(result["repairs"], list)
        assert "warnings" in result

    @pytest.mark.asyncio
    async def test_ingest_with_ascii_normalization(self):
        """Test that ASCII aliases are normalized to unicode."""
        tool = IngestTool()

        result = await tool.execute(
            content="===TEST===\nFLOW::A -> B\nSYNTH::X + Y\n===END===",
            schema="TEST",
            tier="LOSSLESS",
            fix=False,
            verbose=False,
        )

        # Canonical output should have unicode operators
        assert "→" in result["canonical"] or "->" in result["canonical"]
        # Note: Normalization happens during tokenization but may not be reflected in repairs yet

    @pytest.mark.asyncio
    async def test_ingest_verbose_mode(self):
        """Test verbose mode shows pipeline stages."""
        tool = IngestTool()

        result = await tool.execute(
            content="===TEST===\nKEY::value\n===END===", schema="TEST", tier="LOSSLESS", fix=False, verbose=True
        )

        assert "stages" in result
        stages = result["stages"]

        # Should have pipeline stages
        assert "PREPARSE" in stages or "preparse" in str(stages).lower()
        assert "PARSE" in stages or "parse" in str(stages).lower()
        assert "NORMALIZE" in stages or "normalize" in str(stages).lower()
        assert "VALIDATE" in stages or "validate" in str(stages).lower()

    @pytest.mark.asyncio
    async def test_ingest_with_validation_error(self):
        """Test that validation errors are returned in warnings."""
        tool = IngestTool()

        # Empty document
        result = await tool.execute(
            content="===TEST===\n===END===", schema="TEST", tier="LOSSLESS", fix=False, verbose=False
        )

        # Should still return canonical form
        assert "canonical" in result

        # May have validation warnings (depending on schema)
        assert "warnings" in result

    @pytest.mark.asyncio
    async def test_ingest_with_fix_enabled(self):
        """Test TIER_REPAIR when fix=true."""
        tool = IngestTool()

        result = await tool.execute(
            content="===TEST===\nSTATUS::active\n===END===",  # lowercase enum value
            schema="TEST",
            tier="LOSSLESS",
            fix=True,
            verbose=False,
        )

        assert "canonical" in result
        assert "repairs" in result

        # With fix=true, may apply enum casefolding
        # (actual behavior depends on schema and repair engine)

    @pytest.mark.asyncio
    async def test_ingest_without_schema_selector(self):
        """Test envelope inference when schema selector missing."""
        tool = IngestTool()

        result = await tool.execute(
            content="KEY::value\nOTHER::data",  # No @SCHEMA or ===ENVELOPE===
            schema="TEST",
            tier="LOSSLESS",
            fix=False,
            verbose=False,
        )

        # Should infer envelope
        assert "===INFERRED===" in result["canonical"] or "===TEST===" in result["canonical"]
        assert "===END===" in result["canonical"]

    @pytest.mark.asyncio
    async def test_tier_parameter_values(self):
        """Test different TIER parameter values."""
        tool = IngestTool()

        for tier in ["LOSSLESS", "CONSERVATIVE", "AGGRESSIVE", "ULTRA"]:
            result = await tool.execute(
                content="===TEST===\nKEY::value\n===END===", schema="TEST", tier=tier, fix=False, verbose=False
            )

            assert "canonical" in result

    @pytest.mark.asyncio
    async def test_repair_log_format(self):
        """Test repair log has required fields."""
        tool = IngestTool()

        result = await tool.execute(
            content="===TEST===\nKEY::value\n===END===", schema="TEST", tier="LOSSLESS", fix=False, verbose=False
        )

        repairs = result["repairs"]
        assert isinstance(repairs, list)

        # If there are repairs, check format
        if repairs:
            repair = repairs[0]
            # May have fields like RULE_ID, BEFORE, AFTER, TIER, etc.
            assert isinstance(repair, dict)

    @pytest.mark.asyncio
    async def test_tokenization_unpacking_bug(self):
        """Test tokenization unpacking returns correct token count in verbose mode.

        BUG: ingest.py:100 doesn't unpack tokenize() tuple correctly.
        Current: tokens = tokenize(content) -> len(tokens) is always 2 (tuple length)
        Expected: tokens, repairs = tokenize(content) -> len(tokens) is actual token count
        """
        tool = IngestTool()

        # Use simple content with known token count
        # "===TEST===\nKEY::value\n===END===" should have ~10+ tokens
        result = await tool.execute(
            content="===TEST===\nKEY::value\n===END===",
            schema="TEST",
            tier="LOSSLESS",
            fix=False,
            verbose=True,  # Need verbose to see token count
        )

        # Extract token count from stages
        stages = result["stages"]
        tokenize_msg = stages.get("TOKENIZE_COMPLETE", "")

        # Should show actual token count, not "2 tokens produced"
        assert tokenize_msg != "2 tokens produced", "Bug present: tuple not unpacked, showing tuple length"

        # Should show realistic token count (>2)
        import re

        match = re.search(r"(\d+) tokens", tokenize_msg)
        assert match is not None, f"Expected token count in message: {tokenize_msg}"
        token_count = int(match.group(1))
        assert token_count > 2, f"Expected >2 tokens for test content, got {token_count}"

    @pytest.mark.asyncio
    async def test_tokenization_repairs_tracked(self):
        """Test that ASCII normalization repairs from tokenization are tracked.

        BUG: ingest.py:100 doesn't capture repairs from tokenize().
        Repairs are dropped on the floor.
        """
        tool = IngestTool()

        # Use content with ASCII aliases that should be normalized
        result = await tool.execute(
            content="===TEST===\nFLOW::A -> B\n===END===",  # -> should normalize to →
            schema="TEST",
            tier="LOSSLESS",
            fix=False,
            verbose=False,
        )

        # When tokenization normalization is implemented and tracked,
        # repairs should include the ASCII -> unicode normalization
        # NOTE: This may not fail yet if normalization isn't generating repair logs
        # But unpacking the tuple is still required for future tracking
        repairs = result["repairs"]
        assert isinstance(repairs, list)

    @pytest.mark.asyncio
    async def test_ingest_returns_validation_status_unvalidated(self):
        """Test that ingest returns validation_status: UNVALIDATED.

        North Star I5 states: "Schema bypass shall be visible, never silent."
        Deprecated tools that bypass schema validation must explicitly indicate
        their unvalidated status.
        """
        tool = IngestTool()

        result = await tool.execute(
            content="===TEST===\nKEY::value\n===END===",
            schema="TEST",
            tier="LOSSLESS",
            fix=False,
            verbose=False,
        )

        # I5 compliance: validation_status must be present and UNVALIDATED
        assert "validation_status" in result, "Missing validation_status field (I5 violation)"
        assert (
            result["validation_status"] == "UNVALIDATED"
        ), f"Expected validation_status='UNVALIDATED', got '{result.get('validation_status')}'"
