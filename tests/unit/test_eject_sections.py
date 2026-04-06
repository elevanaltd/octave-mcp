"""Tests for section-aware JSON export in octave_eject (Issue #341).

Tests the `sections` parameter on octave_eject that enables extracting
specific sections from OCTAVE documents while preserving structure.

Key behaviors:
- sections parameter accepts list of section identifiers
- Flexible parsing: "§3", "3", "§3::CAPABILITIES" all match section 3
- META is always included for identification
- Non-existent sections are silently omitted (I3: reflect only present)
- When sections is omitted/None, behavior is unchanged (backward compat)
"""

import json

import pytest

from octave_mcp.core.ast_nodes import Assignment, Block, Document, ListValue, Section
from octave_mcp.mcp.eject import EjectTool, _ast_to_dict, _convert_section

# --- Unit tests for _convert_section ---


class TestConvertSection:
    """Tests for _convert_section helper function."""

    def test_convert_section_with_assignments(self):
        """Section with Assignment children is converted to dict."""
        section = Section(
            section_id="1",
            key="IDENTITY",
            children=[
                Assignment(key="ROLE", value="TEST_AGENT"),
                Assignment(key="COGNITION", value="LOGOS"),
            ],
        )
        result = _convert_section(section)
        assert result == {"ROLE": "TEST_AGENT", "COGNITION": "LOGOS"}

    def test_convert_section_with_nested_blocks(self):
        """Section with Block children is recursively converted."""
        section = Section(
            section_id="3",
            key="CAPABILITIES",
            children=[
                Assignment(key="SKILLS", value=ListValue(items=["skill1", "skill2"])),
                Block(
                    key="PROFILES",
                    children=[Assignment(key="DEFAULT", value="standard")],
                ),
            ],
        )
        result = _convert_section(section)
        assert result == {
            "SKILLS": ["skill1", "skill2"],
            "PROFILES": {"DEFAULT": "standard"},
        }

    def test_convert_empty_section(self):
        """Empty section is converted to empty dict."""
        section = Section(section_id="5", key="EMPTY", children=[])
        result = _convert_section(section)
        assert result == {}


# --- Unit tests for _ast_to_dict with Section objects ---


class TestAstToDictWithSections:
    """Tests for _ast_to_dict handling Section objects."""

    def test_ast_to_dict_includes_sections(self):
        """_ast_to_dict converts Section objects to dict entries."""
        doc = Document(
            name="TEST",
            meta={"TYPE": "TEST", "VERSION": "1.0"},
            sections=[
                Section(
                    section_id="1",
                    key="IDENTITY",
                    children=[Assignment(key="ROLE", value="AGENT")],
                ),
            ],
        )
        result = _ast_to_dict(doc)
        assert "META" in result
        # Section should appear with section header as key
        assert "\u00a71::IDENTITY" in result
        assert result["\u00a71::IDENTITY"] == {"ROLE": "AGENT"}

    def test_ast_to_dict_multiple_sections(self):
        """_ast_to_dict handles multiple Section objects."""
        doc = Document(
            name="TEST",
            meta={"TYPE": "TEST"},
            sections=[
                Section(
                    section_id="1",
                    key="FIRST",
                    children=[Assignment(key="A", value="a")],
                ),
                Section(
                    section_id="2",
                    key="SECOND",
                    children=[Assignment(key="B", value="b")],
                ),
                Section(
                    section_id="3",
                    key="THIRD",
                    children=[Assignment(key="C", value="c")],
                ),
            ],
        )
        result = _ast_to_dict(doc)
        assert "\u00a71::FIRST" in result
        assert "\u00a72::SECOND" in result
        assert "\u00a73::THIRD" in result

    def test_ast_to_dict_mixed_sections_and_assignments(self):
        """_ast_to_dict handles mix of Section, Assignment, and Block."""
        doc = Document(
            name="TEST",
            meta={"TYPE": "TEST"},
            sections=[
                Assignment(key="TOP_FIELD", value="top"),
                Section(
                    section_id="1",
                    key="IDENTITY",
                    children=[Assignment(key="ROLE", value="AGENT")],
                ),
                Block(
                    key="EXTRA",
                    children=[Assignment(key="X", value="y")],
                ),
            ],
        )
        result = _ast_to_dict(doc)
        assert result["TOP_FIELD"] == "top"
        assert "\u00a71::IDENTITY" in result
        assert result["EXTRA"] == {"X": "y"}


# --- Integration tests for sections parameter on EjectTool ---


SAMPLE_AGENT_CONTENT = """===TEST_AGENT===
META:
  TYPE::AGENT_DEFINITION
  VERSION::"1.0"

\u00a71::IDENTITY
  ROLE::TEST_AGENT
  COGNITION::LOGOS

\u00a72::BEHAVIOR
  TONE::"Technical"
  PROTOCOL:
    MUST_ALWAYS::["Write tests first"]

\u00a73::CAPABILITIES
  SKILLS::[build-execution, tdd-discipline]
  PROFILES:
    DEFAULT::standard

\u00a74::INTERACTION_RULES
  GRAMMAR:
    MUST_USE::["^\\\\[ANALYSIS\\\\]"]
===END==="""


class TestEjectToolSectionsParameter:
    """Tests for the sections parameter on EjectTool."""

    @pytest.fixture
    def eject_tool(self):
        """Create EjectTool instance."""
        return EjectTool()

    @pytest.mark.asyncio
    async def test_sections_parameter_in_schema(self, eject_tool):
        """Input schema defines sections parameter as array of strings."""
        schema = eject_tool.get_input_schema()
        assert "sections" in schema["properties"]
        sections_schema = schema["properties"]["sections"]
        assert sections_schema["type"] == "array"
        assert sections_schema["items"]["type"] == "string"
        # Not required
        assert "sections" not in schema.get("required", [])

    @pytest.mark.asyncio
    async def test_sections_extract_single_section_json(self, eject_tool):
        """Extract a single section produces JSON with only that section + META."""
        result = await eject_tool.execute(
            content=SAMPLE_AGENT_CONTENT,
            schema="AGENT_DEFINITION",
            format="json",
            sections=["\u00a73"],
        )

        parsed = json.loads(result["output"])

        # META is always included
        assert "META" in parsed
        assert parsed["META"]["TYPE"] == "AGENT_DEFINITION"

        # Requested section is present
        assert "\u00a73::CAPABILITIES" in parsed
        assert parsed["\u00a73::CAPABILITIES"]["SKILLS"] == ["build-execution", "tdd-discipline"]

        # Other sections are NOT present
        assert "\u00a71::IDENTITY" not in parsed
        assert "\u00a72::BEHAVIOR" not in parsed
        assert "\u00a74::INTERACTION_RULES" not in parsed

    @pytest.mark.asyncio
    async def test_sections_extract_multiple_sections(self, eject_tool):
        """Extract multiple sections produces JSON with those sections + META."""
        result = await eject_tool.execute(
            content=SAMPLE_AGENT_CONTENT,
            schema="AGENT_DEFINITION",
            format="json",
            sections=["\u00a71", "\u00a73"],
        )

        parsed = json.loads(result["output"])

        # META always included
        assert "META" in parsed

        # Requested sections present
        assert "\u00a71::IDENTITY" in parsed
        assert "\u00a73::CAPABILITIES" in parsed

        # Non-requested sections absent
        assert "\u00a72::BEHAVIOR" not in parsed
        assert "\u00a74::INTERACTION_RULES" not in parsed

    @pytest.mark.asyncio
    async def test_sections_bare_number_identifier(self, eject_tool):
        """Bare number '3' matches section 3."""
        result = await eject_tool.execute(
            content=SAMPLE_AGENT_CONTENT,
            schema="AGENT_DEFINITION",
            format="json",
            sections=["3"],
        )

        parsed = json.loads(result["output"])
        assert "\u00a73::CAPABILITIES" in parsed
        assert "\u00a71::IDENTITY" not in parsed

    @pytest.mark.asyncio
    async def test_sections_full_header_identifier(self, eject_tool):
        """Full header '\u00a73::CAPABILITIES' matches section 3."""
        result = await eject_tool.execute(
            content=SAMPLE_AGENT_CONTENT,
            schema="AGENT_DEFINITION",
            format="json",
            sections=["\u00a73::CAPABILITIES"],
        )

        parsed = json.loads(result["output"])
        assert "\u00a73::CAPABILITIES" in parsed
        assert "\u00a71::IDENTITY" not in parsed

    @pytest.mark.asyncio
    async def test_sections_nonexistent_section_silently_omitted(self, eject_tool):
        """Non-existent section is silently omitted (I3: reflect only present)."""
        result = await eject_tool.execute(
            content=SAMPLE_AGENT_CONTENT,
            schema="AGENT_DEFINITION",
            format="json",
            sections=["\u00a799"],
        )

        parsed = json.loads(result["output"])

        # META still present
        assert "META" in parsed

        # No section keys (only META)
        section_keys = [k for k in parsed if k != "META"]
        assert section_keys == []

    @pytest.mark.asyncio
    async def test_sections_mixed_existent_and_nonexistent(self, eject_tool):
        """Mix of existent and non-existent sections: only existent ones appear."""
        result = await eject_tool.execute(
            content=SAMPLE_AGENT_CONTENT,
            schema="AGENT_DEFINITION",
            format="json",
            sections=["\u00a73", "\u00a799", "1"],
        )

        parsed = json.loads(result["output"])

        assert "META" in parsed
        assert "\u00a71::IDENTITY" in parsed
        assert "\u00a73::CAPABILITIES" in parsed
        # S99 does not exist, should not appear
        non_meta_keys = [k for k in parsed if k != "META"]
        assert len(non_meta_keys) == 2

    @pytest.mark.asyncio
    async def test_sections_none_preserves_full_output(self, eject_tool):
        """When sections is None, full document is exported (backward compat)."""
        result = await eject_tool.execute(
            content=SAMPLE_AGENT_CONTENT,
            schema="AGENT_DEFINITION",
            format="json",
        )

        parsed = json.loads(result["output"])

        # All sections present
        assert "META" in parsed
        assert "\u00a71::IDENTITY" in parsed
        assert "\u00a72::BEHAVIOR" in parsed
        assert "\u00a73::CAPABILITIES" in parsed
        assert "\u00a74::INTERACTION_RULES" in parsed

    @pytest.mark.asyncio
    async def test_sections_empty_list_preserves_full_output(self, eject_tool):
        """When sections is empty list, full document is exported (backward compat)."""
        result = await eject_tool.execute(
            content=SAMPLE_AGENT_CONTENT,
            schema="AGENT_DEFINITION",
            format="json",
            sections=[],
        )

        parsed = json.loads(result["output"])
        assert "\u00a71::IDENTITY" in parsed
        assert "\u00a72::BEHAVIOR" in parsed
        assert "\u00a73::CAPABILITIES" in parsed
        assert "\u00a74::INTERACTION_RULES" in parsed

    @pytest.mark.asyncio
    async def test_sections_preserves_section_structure(self, eject_tool):
        """Extracted sections preserve their internal structure (nested blocks)."""
        result = await eject_tool.execute(
            content=SAMPLE_AGENT_CONTENT,
            schema="AGENT_DEFINITION",
            format="json",
            sections=["\u00a73"],
        )

        parsed = json.loads(result["output"])
        capabilities = parsed["\u00a73::CAPABILITIES"]

        # Section structure is preserved with nested blocks
        assert "SKILLS" in capabilities
        assert capabilities["SKILLS"] == ["build-execution", "tdd-discipline"]
        assert "PROFILES" in capabilities
        assert capabilities["PROFILES"]["DEFAULT"] == "standard"

    @pytest.mark.asyncio
    async def test_sections_with_yaml_format(self, eject_tool):
        """Sections parameter works with YAML format too."""
        import yaml

        result = await eject_tool.execute(
            content=SAMPLE_AGENT_CONTENT,
            schema="AGENT_DEFINITION",
            format="yaml",
            sections=["\u00a73"],
        )

        parsed = yaml.safe_load(result["output"])

        assert "META" in parsed
        assert "\u00a73::CAPABILITIES" in parsed
        assert "\u00a71::IDENTITY" not in parsed

    @pytest.mark.asyncio
    async def test_sections_validation_status_present(self, eject_tool):
        """I5: validation_status still present when using sections parameter."""
        result = await eject_tool.execute(
            content=SAMPLE_AGENT_CONTENT,
            schema="AGENT_DEFINITION",
            format="json",
            sections=["\u00a73"],
        )

        assert "validation_status" in result
        assert result["validation_status"] == "UNVALIDATED"

    @pytest.mark.asyncio
    async def test_sections_lossy_flag_set(self, eject_tool):
        """When sections filter is applied, lossy flag is True."""
        result = await eject_tool.execute(
            content=SAMPLE_AGENT_CONTENT,
            schema="AGENT_DEFINITION",
            format="json",
            sections=["\u00a73"],
        )

        assert result["lossy"] is True

    @pytest.mark.asyncio
    async def test_sections_fields_omitted_populated(self, eject_tool):
        """When sections filter is applied, fields_omitted lists omitted sections."""
        result = await eject_tool.execute(
            content=SAMPLE_AGENT_CONTENT,
            schema="AGENT_DEFINITION",
            format="json",
            sections=["\u00a73"],
        )

        # Should list the sections that were omitted
        assert len(result["fields_omitted"]) > 0

    @pytest.mark.asyncio
    async def test_sections_suffix_id(self, eject_tool):
        """Section with suffix ID (e.g., '3.5', '2b') is matched correctly."""
        content = """===TEST===
META:
  TYPE::TEST

\u00a72::MAIN
  A::1

\u00a73.5::EXTRA
  B::2
===END==="""

        result = await eject_tool.execute(
            content=content,
            schema="TEST",
            format="json",
            sections=["3.5"],
        )

        parsed = json.loads(result["output"])
        assert "\u00a73.5::EXTRA" in parsed
        assert "\u00a72::MAIN" not in parsed


# --- Tests for section-aware filtering with projection modes ---


class TestEjectSectionsWithProjectionModes:
    """Tests for sections parameter interaction with projection modes."""

    @pytest.fixture
    def eject_tool(self):
        """Create EjectTool instance."""
        return EjectTool()

    @pytest.mark.asyncio
    async def test_sections_with_canonical_mode(self, eject_tool):
        """Sections parameter works correctly with canonical mode."""
        result = await eject_tool.execute(
            content=SAMPLE_AGENT_CONTENT,
            schema="AGENT_DEFINITION",
            format="json",
            mode="canonical",
            sections=["\u00a71"],
        )

        parsed = json.loads(result["output"])
        assert "META" in parsed
        assert "\u00a71::IDENTITY" in parsed
        assert "\u00a72::BEHAVIOR" not in parsed

    @pytest.mark.asyncio
    async def test_sections_non_section_nodes_excluded(self, eject_tool):
        """When sections filter is active, non-Section nodes (Assignment, Block) are excluded."""
        content = """===TEST===
META:
  TYPE::TEST

TOP_FIELD::value
\u00a71::IDENTITY
  ROLE::AGENT
===END==="""

        result = await eject_tool.execute(
            content=content,
            schema="TEST",
            format="json",
            sections=["\u00a71"],
        )

        parsed = json.loads(result["output"])
        assert "META" in parsed
        assert "\u00a71::IDENTITY" in parsed
        # Top-level Assignment should be excluded when sections filter is active
        assert "TOP_FIELD" not in parsed

    @pytest.mark.asyncio
    async def test_sections_filter_works_for_octave_format(self, eject_tool):
        """GH#347: Sections filtering must also work for default octave format.

        Bug: When format='octave' (the default), sections filtering updated
        filtered_doc but left result.output unchanged, so the output was NOT
        actually filtered even though metadata said it was.
        """
        result = await eject_tool.execute(
            content=SAMPLE_AGENT_CONTENT,
            schema="AGENT_DEFINITION",
            format="octave",
            sections=["\u00a73"],
        )

        output = result["output"]

        # The requested section MUST be present in octave output
        assert "\u00a73::CAPABILITIES" in output

        # Other sections MUST NOT be present in octave output
        assert "\u00a71::IDENTITY" not in output
        assert "\u00a72::BEHAVIOR" not in output
        assert "\u00a74::INTERACTION_RULES" not in output

        # Metadata should reflect filtering
        assert result["lossy"] is True
        assert len(result["fields_omitted"]) > 0
