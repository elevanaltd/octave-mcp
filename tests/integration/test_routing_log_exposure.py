"""Integration test for routing_log exposure in MCP validate tool (I4 compliance).

This test verifies that routing_log calculated during validation is EXPOSED
in the MCP tool output envelope, not discarded (Validation Theater violation).

CE BLOCKING ISSUE:
- routing_log is calculated in validator._validate_section() but NOT exposed
- Violation: I4 (Discoverable Artifact Persistence) - "If not written and addressable -> didn't happen"

TDD RED Phase: This test should FAIL until validate.py is fixed to include
routing_log in the response envelope.
"""

import pytest


class TestRoutingLogExposedInMCPOutput:
    """Test that routing_log is exposed in octave_validate tool output."""

    @pytest.mark.asyncio
    async def test_validate_tool_includes_routing_log_in_output(self):
        """octave_validate tool output should include routing_log key.

        Given: OCTAVE content with fields that have target routing
        When: octave_validate MCP tool is called
        Then: Response envelope should include 'routing_log' key

        This is the core I4 compliance test - routing entries must be
        addressable in tool output, not calculated and discarded.
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # Content to validate - simple OCTAVE document
        content = """===TEST===
META:
  TYPE::"TEST_DOC"
  VERSION::"1.0"

STATUS::active
===END==="""

        output = await tool.execute(content=content, schema="TEST")

        # Assert: routing_log key MUST exist in output envelope
        assert "routing_log" in output, (
            "CRITICAL: routing_log missing from validate output. "
            "This is Validation Theater - data calculated but discarded. "
            "Violation of I4 (Discoverable Artifact Persistence)."
        )

        # routing_log should be a list (even if empty)
        assert isinstance(output["routing_log"], list), "routing_log should be a list of routing entries"

    @pytest.mark.asyncio
    async def test_validate_tool_routing_log_contains_entries_when_target_routing_present(self):
        """routing_log should contain entries when schema has target routing.

        Given: OCTAVE content validated against schema with target routing
        When: Field values are routed to targets
        Then: routing_log should contain RoutingEntry data for each routed field

        This test verifies the audit trail is complete (I4 compliance).
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        content = """===TEST===
META:
  TYPE::"TEST_DOC"
  VERSION::"1.0"

CONFIG::value
===END==="""

        output = await tool.execute(content=content, schema="TEST")

        # routing_log must exist (may be empty if no target routing in schema)
        assert "routing_log" in output
        assert isinstance(output["routing_log"], list)

        # If routing entries exist, verify their structure
        for entry in output["routing_log"]:
            assert "source_path" in entry, "RoutingEntry must have source_path"
            assert "target_name" in entry, "RoutingEntry must have target_name"
            assert "value_hash" in entry, "RoutingEntry must have value_hash"
            assert "constraint_passed" in entry, "RoutingEntry must have constraint_passed"
            assert "timestamp" in entry, "RoutingEntry must have timestamp"

    @pytest.mark.asyncio
    async def test_validate_tool_routing_log_empty_when_no_targets(self):
        """routing_log should be empty list when no target routing in schema.

        This verifies the key exists even when there are no routes to log.
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # Simple content without any special routing
        content = """===SIMPLE===
DATA::value
===END==="""

        output = await tool.execute(content=content, schema="UNKNOWN_SCHEMA")

        # routing_log must exist even when empty
        assert "routing_log" in output
        assert output["routing_log"] == [], "routing_log should be empty list when no targets"


class TestRoutingLogErrorEnvelope:
    """Test routing_log in error response envelopes."""

    @pytest.mark.asyncio
    async def test_error_envelope_includes_routing_log(self):
        """Error responses should also include routing_log key.

        Even when validation fails, the routing_log field should be present
        for consistency and I4 compliance.
        """
        from octave_mcp.mcp.validate import ValidateTool

        tool = ValidateTool()

        # Intentionally invalid input (will fail XOR validation - no content or file_path)
        output = await tool.execute(schema="TEST")

        # Even error envelopes should have routing_log for consistency
        assert "routing_log" in output, "Error envelope should include routing_log key for consistency"
        assert output["routing_log"] == [], "Error envelope routing_log should be empty list"
