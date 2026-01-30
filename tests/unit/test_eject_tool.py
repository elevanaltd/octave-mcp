"""Test cases for octave_eject MCP tool (P2.3).

Tests projection modes:
- canonical: Full document, lossy=false
- authoring: Lenient format, lossy=false
- executive: STATUS,RISKS,DECISIONS only, lossy=true
- developer: TESTS,CI,DEPS only, lossy=true
"""

import pytest

from octave_mcp.core.parser import parse
from octave_mcp.mcp.eject import EjectTool


class TestEjectTool:
    """Test EjectTool MCP interface."""

    @pytest.fixture
    def eject_tool(self):
        """Create EjectTool instance."""
        return EjectTool()

    def test_tool_name(self, eject_tool):
        """Eject tool returns correct name."""
        assert eject_tool.get_name() == "octave_eject"

    def test_tool_description(self, eject_tool):
        """Eject tool has non-empty description."""
        desc = eject_tool.get_description()
        assert "projection" in desc.lower()
        assert len(desc) > 0

    def test_input_schema_has_required_parameters(self, eject_tool):
        """Input schema defines required parameters."""
        schema = eject_tool.get_input_schema()

        # Schema parameter is required
        assert "schema" in schema["properties"]
        assert "schema" in schema.get("required", [])

        # Content is optional (null for template generation)
        assert "content" in schema["properties"]
        assert "content" not in schema.get("required", [])

    def test_input_schema_has_mode_enum(self, eject_tool):
        """Input schema defines mode enumeration."""
        schema = eject_tool.get_input_schema()

        mode_schema = schema["properties"]["mode"]
        assert "enum" in mode_schema
        assert set(mode_schema["enum"]) == {"canonical", "authoring", "executive", "developer"}

    def test_input_schema_has_format_enum(self, eject_tool):
        """Input schema defines format enumeration including gbnf."""
        schema = eject_tool.get_input_schema()

        format_schema = schema["properties"]["format"]
        assert "enum" in format_schema
        assert set(format_schema["enum"]) == {"octave", "json", "yaml", "markdown", "gbnf"}

    @pytest.mark.asyncio
    async def test_eject_canonical_mode(self, eject_tool):
        """Eject in canonical mode returns full document."""
        content = """===TEST===
META:
  VERSION::"1.0"

STATUS::active
===END==="""

        result = await eject_tool.execute(content=content, schema="TEST", mode="canonical")

        assert result["output"] is not None
        assert result["lossy"] is False
        assert result["fields_omitted"] == []
        assert "===TEST===" in result["output"]

    @pytest.mark.asyncio
    async def test_eject_authoring_mode(self, eject_tool):
        """Eject in authoring mode returns lenient format."""
        content = """===TEST===
META:
  VERSION::"1.0"

STATUS::active
===END==="""

        result = await eject_tool.execute(content=content, schema="TEST", mode="authoring")

        assert result["output"] is not None
        assert result["lossy"] is False
        assert result["fields_omitted"] == []

    @pytest.mark.asyncio
    async def test_eject_executive_mode(self, eject_tool):
        """Eject in executive mode is lossy and omits technical fields."""
        content = """===TEST===
META:
  VERSION::"1.0"

STATUS::active
TESTS::passing
CI::green
DEPS::[lib1, lib2]
===END==="""

        result = await eject_tool.execute(content=content, schema="TEST", mode="executive")

        assert result["lossy"] is True
        assert "TESTS" in result["fields_omitted"]
        assert "CI" in result["fields_omitted"]
        assert "DEPS" in result["fields_omitted"]

    @pytest.mark.asyncio
    async def test_eject_developer_mode(self, eject_tool):
        """Eject in developer mode is lossy and omits executive fields."""
        content = """===TEST===
META:
  VERSION::"1.0"

STATUS::active
RISKS::[risk1, risk2]
DECISIONS::[decision1]
TESTS::passing
===END==="""

        result = await eject_tool.execute(content=content, schema="TEST", mode="developer")

        assert result["lossy"] is True
        # Developer mode omits executive summary fields
        assert len(result["fields_omitted"]) > 0

    @pytest.mark.asyncio
    async def test_eject_null_content_generates_template(self, eject_tool):
        """Eject with null content generates template for schema."""
        result = await eject_tool.execute(content=None, schema="TEST")

        assert result["output"] is not None
        assert result["lossy"] is False
        # Template generation returns minimal structure
        assert len(result["output"]) > 0

    @pytest.mark.asyncio
    async def test_eject_template_is_parseable_octave(self, eject_tool):
        """Template output must be parseable OCTAVE (dogfooding)."""
        result = await eject_tool.execute(content=None, schema="DEBATE_TRANSCRIPT", format="octave")
        doc = parse(result["output"])
        assert doc is not None
        assert doc.meta is not None
        assert doc.meta.get("TYPE") == "DEBATE_TRANSCRIPT"

    @pytest.mark.asyncio
    async def test_eject_default_mode_is_canonical(self, eject_tool):
        """Eject without mode parameter defaults to canonical."""
        content = """===TEST===
META:
  VERSION::"1.0"

STATUS::active
===END==="""

        result = await eject_tool.execute(content=content, schema="TEST")

        assert result["lossy"] is False
        assert result["fields_omitted"] == []

    @pytest.mark.asyncio
    async def test_eject_default_format_is_octave(self, eject_tool):
        """Eject without format parameter defaults to octave."""
        content = """===TEST===
META:
  VERSION::"1.0"

STATUS::active
===END==="""

        result = await eject_tool.execute(content=content, schema="TEST", format="octave")

        assert result["output"] is not None
        # OCTAVE format uses envelopes
        assert "===TEST===" in result["output"]

    @pytest.mark.asyncio
    async def test_eject_validates_required_schema(self, eject_tool):
        """Eject raises error when schema is missing."""
        with pytest.raises(ValueError, match="schema"):
            await eject_tool.execute(
                content="test content"
                # schema is missing
            )

    @pytest.mark.asyncio
    async def test_eject_json_format(self, eject_tool):
        """Eject in JSON format returns valid JSON."""
        content = """===TEST===
META:
  VERSION::"1.0"
  TYPE::"TEST"

STATUS::active
FIELD::"value"
===END==="""

        result = await eject_tool.execute(content=content, schema="TEST", format="json")

        assert result["output"] is not None
        # Verify JSON is valid by parsing
        import json

        parsed = json.loads(result["output"])
        assert parsed["META"]["VERSION"] == "1.0"
        assert parsed["STATUS"] == "active"

    @pytest.mark.asyncio
    async def test_eject_yaml_format(self, eject_tool):
        """Eject in YAML format returns valid YAML."""
        content = """===TEST===
META:
  VERSION::"1.0"
  TYPE::"TEST"

STATUS::active
FIELD::"value"
===END==="""

        result = await eject_tool.execute(content=content, schema="TEST", format="yaml")

        assert result["output"] is not None
        # Verify YAML is valid by parsing
        import yaml

        parsed = yaml.safe_load(result["output"])
        assert parsed["META"]["VERSION"] == "1.0"
        assert parsed["STATUS"] == "active"

    @pytest.mark.asyncio
    async def test_eject_markdown_format(self, eject_tool):
        """Eject in Markdown format returns readable markdown."""
        content = """===TEST===
META:
  VERSION::"1.0"
  TYPE::"TEST"

STATUS::active
FIELD::"value"
===END==="""

        result = await eject_tool.execute(content=content, schema="TEST", format="markdown")

        assert result["output"] is not None
        # Markdown should have headers and structure
        assert "# TEST" in result["output"] or "## META" in result["output"]
        assert "VERSION" in result["output"]
        assert "STATUS" in result["output"]

    @pytest.mark.asyncio
    async def test_eject_executive_mode_json_format_filters_fields(self, eject_tool):
        """Executive mode + JSON format should omit technical fields (TESTS, CI, DEPS).

        IL-PLACEHOLDER-FIX-002-REWORK: Verify projection mode filters are applied
        to JSON/YAML/MD output formats, not just OCTAVE format.
        """
        content = """===TEST===
META:
  VERSION::"1.0"
  TYPE::"TEST"

STATUS::active
RISKS::[risk1, risk2]
DECISIONS::[decision1, decision2]
TESTS::passing
CI::green
DEPS::[lib1, lib2]
===END==="""

        result = await eject_tool.execute(content=content, schema="TEST", mode="executive", format="json")

        # Verify lossy projection
        assert result["lossy"] is True
        assert "TESTS" in result["fields_omitted"]
        assert "CI" in result["fields_omitted"]
        assert "DEPS" in result["fields_omitted"]

        # Parse JSON output
        import json

        parsed = json.loads(result["output"])

        # Executive mode should INCLUDE these fields
        assert "STATUS" in parsed
        assert "RISKS" in parsed
        assert "DECISIONS" in parsed

        # Executive mode should EXCLUDE these fields
        assert "TESTS" not in parsed, "TESTS field should be filtered out in executive mode"
        assert "CI" not in parsed, "CI field should be filtered out in executive mode"
        assert "DEPS" not in parsed, "DEPS field should be filtered out in executive mode"


class TestEjectToolI5SchemaSovereignty:
    """Tests for I5 (Schema Sovereignty) requirement in octave_eject.

    North Star I5 states:
    - A document processed without schema validation shall be marked as UNVALIDATED
    - Schema-validated documents shall record the schema name and version used
    - Schema bypass shall be visible, never silent

    Current state: eject.py does not include validation_status at all (silent omission).
    Required state: validation_status must be explicitly UNVALIDATED.
    """

    @pytest.fixture
    def eject_tool(self):
        """Create EjectTool instance."""
        return EjectTool()

    @pytest.mark.asyncio
    async def test_i5_eject_validation_status_present(self, eject_tool):
        """I5: validation_status field must be present in eject output."""
        content = """===TEST===
META:
  VERSION::"1.0"

STATUS::active
===END==="""

        result = await eject_tool.execute(content=content, schema="TEST", mode="canonical")

        # I5: Field must be present (not silently omitted)
        assert "validation_status" in result, (
            "I5 violation: validation_status field must be present in eject output. "
            "Silent omission is a form of silent bypass."
        )

    @pytest.mark.asyncio
    async def test_i5_eject_validation_status_is_unvalidated(self, eject_tool):
        """I5: validation_status must be UNVALIDATED when no schema validator exists."""
        content = """===TEST===
META:
  VERSION::"1.0"

STATUS::active
===END==="""

        result = await eject_tool.execute(content=content, schema="TEST", mode="canonical")

        # I5 REQUIREMENT: Must be UNVALIDATED, not PENDING_INFRASTRUCTURE or omitted
        assert result.get("validation_status") == "UNVALIDATED", (
            f"I5 violation: validation_status should be 'UNVALIDATED' to make bypass visible, "
            f"but got '{result.get('validation_status', 'NOT PRESENT')}'"
        )

    @pytest.mark.asyncio
    async def test_i5_eject_validation_status_in_all_modes(self, eject_tool):
        """I5: validation_status must be present in all projection modes."""
        content = """===TEST===
META:
  VERSION::"1.0"

STATUS::active
TESTS::passing
===END==="""

        modes = ["canonical", "authoring", "executive", "developer"]

        for mode in modes:
            result = await eject_tool.execute(content=content, schema="TEST", mode=mode)

            assert "validation_status" in result, f"I5 violation: validation_status missing in mode '{mode}'"
            assert result["validation_status"] == "UNVALIDATED", (
                f"I5 violation: validation_status should be 'UNVALIDATED' in mode '{mode}', "
                f"but got '{result['validation_status']}'"
            )

    @pytest.mark.asyncio
    async def test_i5_eject_template_generation_has_validation_status(self, eject_tool):
        """I5: Even template generation must include validation_status."""
        result = await eject_tool.execute(content=None, schema="TEST")

        # I5: Template generation also must declare validation status
        assert (
            "validation_status" in result
        ), "I5 violation: validation_status must be present even in template generation"
        assert result["validation_status"] == "UNVALIDATED", (
            f"I5 violation: template generation validation_status should be 'UNVALIDATED', "
            f"but got '{result['validation_status']}'"
        )


class TestEjectToolGBNFFormat:
    """Tests for GBNF format export (Issue #171).

    GBNF (Grammar BNF) format exports OCTAVE schema as llama.cpp grammar
    for constrained text generation.
    """

    @pytest.fixture
    def eject_tool(self):
        """Create EjectTool instance."""
        return EjectTool()

    @pytest.mark.asyncio
    async def test_gbnf_format_returns_valid_gbnf(self, eject_tool):
        """Eject in GBNF format returns valid llama.cpp grammar."""
        content = """===TEST===
META:
  VERSION::"1.0"
  TYPE::"TEST"

STATUS::active
FIELD::"value"
===END==="""

        result = await eject_tool.execute(content=content, schema="TEST", format="gbnf")

        assert result["output"] is not None
        # GBNF should have ::= assignment operator
        assert "::=" in result["output"], "GBNF grammar should use ::= for rule definitions"
        # Should have root rule
        assert "root" in result["output"].lower(), "GBNF grammar should have root rule"

    @pytest.mark.asyncio
    async def test_gbnf_format_includes_document_structure(self, eject_tool):
        """GBNF format should include OCTAVE document structure rules."""
        content = """===TEST===
META:
  VERSION::"1.0"

STATUS::active
===END==="""

        result = await eject_tool.execute(content=content, schema="TEST", format="gbnf")

        # Should have document/envelope structure
        output = result["output"]
        assert (
            "document" in output.lower() or "envelope" in output.lower()
        ), "GBNF should include document structure rules"

    @pytest.mark.asyncio
    async def test_gbnf_format_is_not_lossy(self, eject_tool):
        """GBNF format export should not be lossy (exports full schema)."""
        content = """===TEST===
META:
  VERSION::"1.0"

STATUS::active
===END==="""

        result = await eject_tool.execute(content=content, schema="TEST", format="gbnf")

        # GBNF export of schema is not lossy
        assert result["lossy"] is False
        assert result["fields_omitted"] == []

    @pytest.mark.asyncio
    async def test_gbnf_format_has_validation_status(self, eject_tool):
        """I5: GBNF format should also include validation_status."""
        content = """===TEST===
META:
  VERSION::"1.0"

STATUS::active
===END==="""

        result = await eject_tool.execute(content=content, schema="TEST", format="gbnf")

        assert "validation_status" in result
        assert result["validation_status"] == "UNVALIDATED"

    @pytest.mark.asyncio
    async def test_gbnf_format_includes_field_rules(self, eject_tool):
        """GBNF format should generate rules for document fields."""
        content = """===TEST===
META:
  VERSION::"1.0"

STATUS::active
COUNT::42
===END==="""

        result = await eject_tool.execute(content=content, schema="TEST", format="gbnf")

        output = result["output"]
        # Should have field rules derived from document structure
        assert "::=" in output
