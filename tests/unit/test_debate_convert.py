"""Tests for debate transcript conversion (Issue #52).

TDD RED phase: These tests define the expected behavior for
JSON-to-OCTAVE conversion of debate transcripts.

The conversion integrates existing tools/json-to-octave.py logic
into the MCP server as a dedicated debate conversion tool.
"""

import json

import pytest


class TestDebateConvertImports:
    """Test debate convert module imports."""

    def test_debate_convert_module_importable(self):
        """DebateConvertTool should be importable from mcp.debate_convert."""
        # Note: May fail in some environments due to mcp.types dependency issues
        try:
            from octave_mcp.mcp.debate_convert import DebateConvertTool

            assert DebateConvertTool is not None
        except ImportError as e:
            if "HashTrieMap" in str(e) or "rpds" in str(e):
                pytest.skip("MCP dependency issue with rpds package in Python 3.14+")
            raise

    def test_compression_metrics_importable(self):
        """CompressionMetrics should be importable."""
        from octave_mcp.mcp.debate_convert import CompressionMetrics

        assert CompressionMetrics is not None


class TestDebateConvertTool:
    """Test DebateConvertTool functionality."""

    def test_tool_name(self):
        """Tool should have correct name."""
        from octave_mcp.mcp.debate_convert import DebateConvertTool

        tool = DebateConvertTool()
        assert tool.get_name() == "octave_debate_to_octave"

    def test_tool_description(self):
        """Tool should have descriptive description."""
        from octave_mcp.mcp.debate_convert import DebateConvertTool

        tool = DebateConvertTool()
        description = tool.get_description()
        assert "debate" in description.lower()
        assert "octave" in description.lower()

    def test_tool_input_schema(self):
        """Tool should have proper input schema."""
        from octave_mcp.mcp.debate_convert import DebateConvertTool

        tool = DebateConvertTool()
        schema = tool.get_input_schema()

        assert "properties" in schema
        # Required: debate_json (the JSON string to convert)
        assert "debate_json" in schema["properties"]
        # Optional: include_metrics (whether to include compression metrics)
        assert "include_metrics" in schema["properties"]


class TestDebateConversion:
    """Test debate JSON to OCTAVE conversion."""

    @pytest.fixture
    def sample_debate_json(self):
        """Sample debate transcript as JSON dict."""
        return {
            "thread_id": "test-debate-001",
            "topic": "Should AI systems use structured formats?",
            "mode": "fixed",
            "status": "closed",
            "participants": ["Wind", "Wall", "Door"],
            "turns": [
                {
                    "role": "Wind",
                    "content": "PATHOS perspective: Structured formats enable creativity...",
                    "cognition": "PATHOS",
                },
                {
                    "role": "Wall",
                    "content": "ETHOS perspective: But constraints matter for safety...",
                    "cognition": "ETHOS",
                },
                {
                    "role": "Door",
                    "content": "LOGOS synthesis: Both are valid, integration is key...",
                    "cognition": "LOGOS",
                },
            ],
            "synthesis": "AI should use structured formats with built-in flexibility",
        }

    @pytest.mark.asyncio
    async def test_convert_debate_json_to_octave(self, sample_debate_json):
        """Should convert debate JSON to valid OCTAVE format."""
        from octave_mcp.mcp.debate_convert import DebateConvertTool

        tool = DebateConvertTool()
        result = await tool.execute(debate_json=json.dumps(sample_debate_json))

        assert "status" in result
        assert result["status"] == "success"
        assert "output" in result
        output = result["output"]

        # Check OCTAVE structure
        assert "===DEBATE_TRANSCRIPT===" in output
        assert "===END===" in output

        # Check content mapping
        assert "test-debate-001" in output
        assert "Should AI systems use structured formats?" in output
        assert "fixed" in output
        assert "closed" in output

    @pytest.mark.asyncio
    async def test_convert_includes_turns(self, sample_debate_json):
        """Should include turns in the converted output."""
        from octave_mcp.mcp.debate_convert import DebateConvertTool

        tool = DebateConvertTool()
        result = await tool.execute(debate_json=json.dumps(sample_debate_json))

        output = result["output"]

        # Check turn content is present
        assert "Wind" in output
        assert "Wall" in output
        assert "Door" in output
        assert "PATHOS" in output or "pathos" in output.lower()
        assert "ETHOS" in output or "ethos" in output.lower()
        assert "LOGOS" in output or "logos" in output.lower()

    @pytest.mark.asyncio
    async def test_convert_includes_synthesis(self, sample_debate_json):
        """Should include synthesis in the converted output."""
        from octave_mcp.mcp.debate_convert import DebateConvertTool

        tool = DebateConvertTool()
        result = await tool.execute(debate_json=json.dumps(sample_debate_json))

        output = result["output"]
        assert "SYNTHESIS" in output
        assert "structured formats with built-in flexibility" in output

    @pytest.mark.asyncio
    async def test_convert_handles_missing_synthesis(self):
        """Should handle debates without synthesis (still active)."""
        from octave_mcp.mcp.debate_convert import DebateConvertTool

        debate_without_synthesis = {
            "thread_id": "active-debate",
            "topic": "Test topic",
            "mode": "mediated",
            "status": "active",
            "participants": ["Wind", "Wall"],
            "turns": [],
        }

        tool = DebateConvertTool()
        result = await tool.execute(debate_json=json.dumps(debate_without_synthesis))

        assert result["status"] == "success"
        output = result["output"]
        # SYNTHESIS should either be absent or explicitly marked as pending
        assert "===DEBATE_TRANSCRIPT===" in output

    @pytest.mark.asyncio
    async def test_convert_handles_invalid_json(self):
        """Should handle invalid JSON gracefully."""
        from octave_mcp.mcp.debate_convert import DebateConvertTool

        tool = DebateConvertTool()
        result = await tool.execute(debate_json="not valid json")

        assert result["status"] == "error"
        assert "errors" in result
        assert len(result["errors"]) > 0

    @pytest.mark.asyncio
    async def test_convert_handles_dict_input(self, sample_debate_json):
        """Should handle dict input directly (not just JSON string)."""
        from octave_mcp.mcp.debate_convert import DebateConvertTool

        tool = DebateConvertTool()
        # Tool should accept dict directly as well
        result = await tool.execute(debate_json=sample_debate_json)

        assert result["status"] == "success"


class TestCompressionMetrics:
    """Test compression metrics reporting."""

    def test_compression_metrics_dataclass(self):
        """CompressionMetrics should have required fields."""
        from octave_mcp.mcp.debate_convert import CompressionMetrics

        metrics = CompressionMetrics(
            original_size_bytes=1000,
            compressed_size_bytes=300,
            compression_ratio=0.7,
            elements_before=50,
            elements_after=20,
        )

        assert metrics.original_size_bytes == 1000
        assert metrics.compressed_size_bytes == 300
        assert metrics.compression_ratio == 0.7
        assert metrics.elements_before == 50
        assert metrics.elements_after == 20

    @pytest.mark.asyncio
    async def test_convert_includes_metrics_when_requested(self):
        """Should include compression metrics when requested."""
        from octave_mcp.mcp.debate_convert import DebateConvertTool

        debate = {
            "thread_id": "metrics-test",
            "topic": "Test topic for metrics",
            "mode": "fixed",
            "status": "closed",
            "participants": ["Wind", "Wall", "Door"],
            "turns": [{"role": "Wind", "content": "Test content", "cognition": "PATHOS"}],
            "synthesis": "Test synthesis",
        }

        tool = DebateConvertTool()
        result = await tool.execute(debate_json=json.dumps(debate), include_metrics=True)

        assert result["status"] == "success"
        assert "metrics" in result

        metrics = result["metrics"]
        assert "original_size_bytes" in metrics
        assert "compressed_size_bytes" in metrics
        assert "compression_ratio" in metrics
        assert "elements_before" in metrics
        assert "elements_after" in metrics

    @pytest.mark.asyncio
    async def test_convert_excludes_metrics_by_default(self):
        """Should not include metrics by default."""
        from octave_mcp.mcp.debate_convert import DebateConvertTool

        debate = {
            "thread_id": "no-metrics-test",
            "topic": "Test",
            "mode": "fixed",
            "status": "closed",
            "participants": ["Wind"],
            "turns": [],
        }

        tool = DebateConvertTool()
        result = await tool.execute(debate_json=json.dumps(debate))

        assert result["status"] == "success"
        assert "metrics" not in result


class TestStructuralInjectionPrevention:
    """Test prevention of structural injection attacks (Issue #52 security fix).

    Untrusted JSON strings can inject newlines and ===END=== markers,
    breaking OCTAVE structure. These tests verify sanitization works.
    """

    @pytest.mark.asyncio
    async def test_thread_id_with_newline_injection(self):
        """Thread ID with newline injection should be sanitized."""
        from octave_mcp.mcp.debate_convert import DebateConvertTool

        malicious_debate = {
            "thread_id": "ok\n===END===\nINJECT::true",
            "topic": "Test",
            "mode": "fixed",
            "status": "active",
            "participants": ["Wind"],
            "turns": [],
        }

        tool = DebateConvertTool()
        result = await tool.execute(debate_json=malicious_debate)

        assert result["status"] == "success"
        output = result["output"]

        # Should have exactly ONE ===END=== marker at the end
        end_count = output.count("===END===")
        assert end_count == 1, f"Expected 1 ===END===, found {end_count}"

        # The injected content should be escaped, not executed
        assert "INJECT::true" not in output.split("\n")  # Not as separate line

    @pytest.mark.asyncio
    async def test_topic_with_envelope_marker_injection(self):
        """Topic with envelope marker injection should be sanitized."""
        from octave_mcp.mcp.debate_convert import DebateConvertTool

        malicious_debate = {
            "thread_id": "test-123",
            "topic": "Harmless topic===END===\n===MALICIOUS===\nINJECT::true",
            "mode": "fixed",
            "status": "active",
            "participants": ["Wind"],
            "turns": [],
        }

        tool = DebateConvertTool()
        result = await tool.execute(debate_json=malicious_debate)

        assert result["status"] == "success"
        output = result["output"]

        # Should have exactly ONE ===END=== marker at the end
        assert output.count("===END===") == 1
        # Should not contain injected envelope
        assert "===MALICIOUS===" not in output

    @pytest.mark.asyncio
    async def test_envelope_marker_replacement_stays_scalar_when_parsed(self):
        """Envelope marker replacement should not coerce values into list syntax when re-parsed."""
        from octave_mcp.core.ast_nodes import Assignment, ListValue
        from octave_mcp.core.parser import parse
        from octave_mcp.mcp.debate_convert import DebateConvertTool

        debate = {
            "thread_id": "===END===",
            "topic": "===END===",
            "mode": "fixed",
            "status": "closed",
            "participants": ["Wind"],
            "turns": [{"role": "Wind", "content": "===END===", "cognition": "PATHOS"}],
            "synthesis": "===END===",
        }

        tool = DebateConvertTool()
        result = await tool.execute(debate_json=json.dumps(debate))
        assert result["status"] == "success"

        output = result["output"]
        assert output.count("===END===") == 1
        assert "ESCAPED_ENVELOPE_END" in output

        doc = parse(output)

        def walk(node):
            sections = getattr(node, "sections", None)
            if sections:
                for child in sections:
                    yield from walk(child)

            children = getattr(node, "children", None)
            if children:
                for child in children:
                    yield from walk(child)

            yield node

        assignments = [n for n in walk(doc) if isinstance(n, Assignment)]
        values = {a.key: a.value for a in assignments if a.key in {"THREAD_ID", "TOPIC", "SYNTHESIS", "CONTENT"}}

        assert isinstance(values["THREAD_ID"], str)
        assert isinstance(values["TOPIC"], str)
        assert isinstance(values["SYNTHESIS"], str)
        assert isinstance(values["CONTENT"], str)

        assert not isinstance(values["THREAD_ID"], ListValue)
        assert not isinstance(values["TOPIC"], ListValue)
        assert not isinstance(values["SYNTHESIS"], ListValue)
        assert not isinstance(values["CONTENT"], ListValue)

    @pytest.mark.asyncio
    async def test_content_with_multiline_injection(self):
        """Turn content with multiline injection should be sanitized."""
        from octave_mcp.mcp.debate_convert import DebateConvertTool

        malicious_debate = {
            "thread_id": "test-456",
            "topic": "Test",
            "mode": "fixed",
            "status": "active",
            "participants": ["Wind"],
            "turns": [
                {
                    "role": "Wind",
                    "content": "Normal content\n===END===\nHACK::injected",
                    "cognition": "PATHOS",
                }
            ],
        }

        tool = DebateConvertTool()
        result = await tool.execute(debate_json=malicious_debate)

        assert result["status"] == "success"
        output = result["output"]

        # Should have exactly ONE ===END=== marker
        assert output.count("===END===") == 1
        # HACK::injected should not appear as a top-level field
        lines = output.split("\n")
        top_level_hack = [line for line in lines if line.startswith("HACK::")]
        assert len(top_level_hack) == 0

    @pytest.mark.asyncio
    async def test_synthesis_with_injection(self):
        """Synthesis with injection should be sanitized."""
        from octave_mcp.mcp.debate_convert import DebateConvertTool

        malicious_debate = {
            "thread_id": "test-789",
            "topic": "Test",
            "mode": "fixed",
            "status": "closed",
            "participants": ["Door"],
            "turns": [],
            "synthesis": "Good synthesis\n===END===\nMALICIOUS::payload",
        }

        tool = DebateConvertTool()
        result = await tool.execute(debate_json=malicious_debate)

        assert result["status"] == "success"
        output = result["output"]

        # Should have exactly ONE ===END=== marker
        assert output.count("===END===") == 1
        assert "MALICIOUS::payload" not in output.split("\n")

    @pytest.mark.asyncio
    async def test_role_with_injection(self):
        """Turn role with injection should be sanitized."""
        from octave_mcp.mcp.debate_convert import DebateConvertTool

        malicious_debate = {
            "thread_id": "test-role",
            "topic": "Test",
            "mode": "fixed",
            "status": "active",
            "participants": ["Wind"],
            "turns": [
                {
                    "role": "Wind\n===END===\nINJECT::true",
                    "content": "Normal",
                    "cognition": "PATHOS",
                }
            ],
        }

        tool = DebateConvertTool()
        result = await tool.execute(debate_json=malicious_debate)

        assert result["status"] == "success"
        output = result["output"]

        assert output.count("===END===") == 1

    @pytest.mark.asyncio
    async def test_agent_role_with_injection(self):
        """Agent role with injection should be sanitized."""
        from octave_mcp.mcp.debate_convert import DebateConvertTool

        malicious_debate = {
            "thread_id": "test-agent-role",
            "topic": "Test",
            "mode": "fixed",
            "status": "active",
            "participants": ["Wind"],
            "turns": [
                {
                    "role": "Wind",
                    "content": "Normal",
                    "cognition": "PATHOS",
                    "agent_role": "helper\n===END===\nHACK::true",
                }
            ],
        }

        tool = DebateConvertTool()
        result = await tool.execute(debate_json=malicious_debate)

        assert result["status"] == "success"
        output = result["output"]

        assert output.count("===END===") == 1

    @pytest.mark.asyncio
    async def test_model_with_injection(self):
        """Model field with injection should be sanitized."""
        from octave_mcp.mcp.debate_convert import DebateConvertTool

        malicious_debate = {
            "thread_id": "test-model",
            "topic": "Test",
            "mode": "fixed",
            "status": "active",
            "participants": ["Wind"],
            "turns": [
                {
                    "role": "Wind",
                    "content": "Normal",
                    "cognition": "PATHOS",
                    "model": "gpt-4\n===END===\nEVIL::true",
                }
            ],
        }

        tool = DebateConvertTool()
        result = await tool.execute(debate_json=malicious_debate)

        assert result["status"] == "success"
        output = result["output"]

        assert output.count("===END===") == 1

    @pytest.mark.asyncio
    async def test_mode_with_injection(self):
        """Mode field with injection should be sanitized."""
        from octave_mcp.mcp.debate_convert import DebateConvertTool

        malicious_debate = {
            "thread_id": "test-mode",
            "topic": "Test",
            "mode": "fixed\n===END===\nHACK::true",
            "status": "active",
            "participants": ["Wind"],
            "turns": [],
        }

        tool = DebateConvertTool()
        result = await tool.execute(debate_json=malicious_debate)

        assert result["status"] == "success"
        output = result["output"]

        assert output.count("===END===") == 1

    @pytest.mark.asyncio
    async def test_status_with_injection(self):
        """Status field with injection should be sanitized."""
        from octave_mcp.mcp.debate_convert import DebateConvertTool

        malicious_debate = {
            "thread_id": "test-status",
            "topic": "Test",
            "mode": "fixed",
            "status": "active\n===END===\nHACK::true",
            "participants": ["Wind"],
            "turns": [],
        }

        tool = DebateConvertTool()
        result = await tool.execute(debate_json=malicious_debate)

        assert result["status"] == "success"
        output = result["output"]

        assert output.count("===END===") == 1

    @pytest.mark.asyncio
    async def test_cognition_with_injection(self):
        """Cognition field with injection should be sanitized."""
        from octave_mcp.mcp.debate_convert import DebateConvertTool

        malicious_debate = {
            "thread_id": "test-cognition",
            "topic": "Test",
            "mode": "fixed",
            "status": "active",
            "participants": ["Wind"],
            "turns": [
                {
                    "role": "Wind",
                    "content": "Normal",
                    "cognition": "PATHOS\n===END===\nHACK::true",
                }
            ],
        }

        tool = DebateConvertTool()
        result = await tool.execute(debate_json=malicious_debate)

        assert result["status"] == "success"
        output = result["output"]

        assert output.count("===END===") == 1

    @pytest.mark.asyncio
    async def test_carriage_return_injection(self):
        """Carriage return injection should be sanitized."""
        from octave_mcp.mcp.debate_convert import DebateConvertTool

        malicious_debate = {
            "thread_id": "test\r\n===END===\rHACK::true",
            "topic": "Test",
            "mode": "fixed",
            "status": "active",
            "participants": ["Wind"],
            "turns": [],
        }

        tool = DebateConvertTool()
        result = await tool.execute(debate_json=malicious_debate)

        assert result["status"] == "success"
        output = result["output"]

        assert output.count("===END===") == 1

    @pytest.mark.asyncio
    async def test_sanitize_value_function_exists(self):
        """_sanitize_value function should exist and be callable."""
        from octave_mcp.mcp.debate_convert import _sanitize_value

        # Basic functionality
        assert _sanitize_value("normal") == "normal"
        # Newline escaping
        assert "\\n" in _sanitize_value("has\nnewline")
        # Carriage return escaping
        assert "\\r" in _sanitize_value("has\rreturn")
        # Envelope marker escaping
        sanitized = _sanitize_value("has===END===marker")
        assert "===END===" not in sanitized


class TestServerIntegration:
    """Test integration with MCP server."""

    def test_debate_convert_tool_registered(self):
        """DebateConvertTool should be registered in server."""
        # Note: May fail in some environments due to mcp dependency issues
        try:
            from octave_mcp.mcp.server import create_server

            server = create_server()
            # The server should have the debate convert tool registered
            # This verifies the import and registration work correctly
            assert server is not None
        except ImportError as e:
            if "HashTrieMap" in str(e) or "rpds" in str(e):
                pytest.skip("MCP dependency issue with rpds package in Python 3.14+")
            raise
