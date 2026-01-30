"""MCP tool for OCTAVE eject (P2.3, Issue #171 GBNF).

Implements octave_eject tool with projection modes:
- canonical: Full document, lossy=false
- authoring: Lenient format, lossy=false
- executive: STATUS,RISKS,DECISIONS only, lossy=true
- developer: TESTS,CI,DEPS only, lossy=true

Output formats:
- octave: OCTAVE syntax
- json: JSON representation
- yaml: YAML representation
- markdown: Markdown format
- gbnf: llama.cpp GBNF grammar (Issue #171)
"""

import json
from typing import Any

import yaml

from octave_mcp.core.ast_nodes import Assignment, Block, Document, InlineMap, ListValue
from octave_mcp.core.gbnf_compiler import GBNFCompiler, compile_gbnf_from_meta
from octave_mcp.core.parser import parse
from octave_mcp.core.projector import project
from octave_mcp.core.schema_extractor import extract_schema_from_document
from octave_mcp.mcp.base_tool import BaseTool, SchemaBuilder


def _ast_to_dict(doc: Document) -> dict[str, Any]:
    """Convert AST Document to dictionary for JSON/YAML export.

    Args:
        doc: Document AST

    Returns:
        Dictionary representation of document
    """
    result: dict[str, Any] = {}

    # Add META if present, converting any AST types (e.g., ListValue) to native Python
    if doc.meta:
        result["META"] = {k: _convert_value(v) for k, v in doc.meta.items()}

    # Convert sections
    for section in doc.sections:
        if isinstance(section, Assignment):
            result[section.key] = _convert_value(section.value)
        elif isinstance(section, Block):
            result[section.key] = _convert_block(section)

    return result


def _convert_value(value: Any) -> Any:
    """Convert AST value to native Python type.

    Args:
        value: AST value node

    Returns:
        Native Python value
    """
    if isinstance(value, ListValue):
        return [_convert_value(item) for item in value.items]
    elif isinstance(value, InlineMap):
        return {k: _convert_value(v) for k, v in value.pairs.items()}
    else:
        return value


def _convert_block(block: Block) -> dict[str, Any]:
    """Convert Block AST node to dictionary.

    Args:
        block: Block node

    Returns:
        Dictionary representation
    """
    result: dict[str, Any] = {}

    for child in block.children:
        if isinstance(child, Assignment):
            result[child.key] = _convert_value(child.value)
        elif isinstance(child, Block):
            result[child.key] = _convert_block(child)

    return result


def _format_markdown_value(value: Any) -> str:
    """Format an AST value for markdown output.

    I3 (Mirror Constraint): Reflect only present data, create nothing.
    Python internals (like ListValue.__repr__) must not leak into output.

    Args:
        value: AST value node

    Returns:
        Human-readable string representation for markdown
    """
    if isinstance(value, ListValue):
        # Format list items, recursively formatting nested values
        items = [_format_markdown_value(item) for item in value.items]
        return ", ".join(str(item) for item in items)
    elif isinstance(value, InlineMap):
        # Format inline map as key: value pairs
        pairs = [f"{k}: {_format_markdown_value(v)}" for k, v in value.pairs.items()]
        return ", ".join(pairs)
    else:
        # Regular values are stringified directly
        return str(value)


def _ast_to_markdown(doc: Document) -> str:
    """Convert AST Document to Markdown format.

    Args:
        doc: Document AST

    Returns:
        Markdown representation
    """
    lines: list[str] = []

    # Add title
    lines.append(f"# {doc.name}")
    lines.append("")

    # Add META section
    if doc.meta:
        lines.append("## META")
        lines.append("")
        for key, value in doc.meta.items():
            # I3: Format values to avoid exposing Python internals
            lines.append(f"- **{key}**: {_format_markdown_value(value)}")
        lines.append("")

    # Add sections
    for section in doc.sections:
        if isinstance(section, Assignment):
            # I3: Format values to avoid exposing Python internals
            lines.append(f"**{section.key}**: {_format_markdown_value(section.value)}")
            lines.append("")
        elif isinstance(section, Block):
            lines.append(f"## {section.key}")
            lines.append("")
            _block_to_markdown(section, lines, level=3)

    return "\n".join(lines)


def _block_to_markdown(block: Block, lines: list[str], level: int = 3) -> None:
    """Convert Block to Markdown recursively.

    Args:
        block: Block node
        lines: Output lines list (mutated)
        level: Heading level
    """
    for child in block.children:
        if isinstance(child, Assignment):
            # I3: Format values to avoid exposing Python internals
            lines.append(f"- **{child.key}**: {_format_markdown_value(child.value)}")
        elif isinstance(child, Block):
            lines.append(f"{'#' * level} {child.key}")
            lines.append("")
            _block_to_markdown(child, lines, level + 1)


class EjectTool(BaseTool):
    """MCP tool for octave_eject - projection and formatting."""

    def get_name(self) -> str:
        """Get tool name."""
        return "octave_eject"

    def get_description(self) -> str:
        """Get tool description."""
        return (
            "Eject OCTAVE content with projection modes. "
            "Supports canonical, authoring, executive, and developer views. "
            "Can generate templates when content is null. "
            "Output formats: octave, json, yaml, markdown, gbnf."
        )

    def get_input_schema(self) -> dict[str, Any]:
        """Get input schema."""
        schema = SchemaBuilder()

        schema.add_parameter(
            "content", "string", required=False, description="OCTAVE content to eject (null for template generation)"
        )

        schema.add_parameter(
            "schema", "string", required=True, description="Schema name for validation or template generation"
        )

        schema.add_parameter(
            "mode",
            "string",
            required=False,
            description="Projection mode: canonical (full), authoring (lenient), executive (STATUS,RISKS,DECISIONS), developer (TESTS,CI,DEPS)",
            enum=["canonical", "authoring", "executive", "developer"],
        )

        schema.add_parameter(
            "format",
            "string",
            required=False,
            description="Output format (gbnf exports llama.cpp GBNF grammar)",
            enum=["octave", "json", "yaml", "markdown", "gbnf"],
        )

        return schema.build()

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute eject projection.

        Args:
            content: OCTAVE content to eject (None for template)
            schema: Schema name for validation/template
            mode: Projection mode (canonical, authoring, executive, developer)
            format: Output format (octave, json, yaml, markdown, gbnf)

        Returns:
            Dictionary with:
            - output: Formatted content
            - lossy: Boolean (true if mode discards fields)
            - fields_omitted: List of dropped fields if lossy
        """
        # Validate and extract parameters
        params = self.validate_parameters(kwargs)
        content = params.get("content", None)
        schema_name = params["schema"]
        mode = params.get("mode", "canonical")
        output_format = params.get("format", "octave")

        # If content is None, generate template
        if content is None:
            # For now, generate minimal template
            template = f"""===TEMPLATE===
META:
  TYPE::{schema_name}
  VERSION::"1.0"

// Template generated for schema: {schema_name}
===END==="""
            # I5 (Schema Sovereignty): validation_status must be UNVALIDATED to make bypass visible
            # "Schema bypass shall be visible, never silent" - North Star I5
            return {
                "output": template,
                "lossy": False,
                "fields_omitted": [],
                "validation_status": "UNVALIDATED",  # I5: Explicit bypass - no schema validator yet
            }

        # Parse content to AST
        try:
            doc = parse(content)
        except Exception as e:
            # If parsing fails, return error
            # I5 (Schema Sovereignty): validation_status must be UNVALIDATED to make bypass visible
            return {
                "output": f"// Parse error: {str(e)}\n{content}",
                "lossy": False,
                "fields_omitted": [],
                "validation_status": "UNVALIDATED",  # I5: Explicit bypass - no schema validator yet
            }

        # Project to desired mode
        result = project(doc, mode=mode)

        # Convert to requested output format
        # IL-PLACEHOLDER-FIX-002-REWORK: Use filtered AST from projection for all formats
        # I5 (Schema Sovereignty): All outputs must include validation_status
        # "Schema bypass shall be visible, never silent" - North Star I5
        if output_format == "json":
            # Convert filtered AST to dictionary, then serialize as JSON
            data = _ast_to_dict(result.filtered_doc)
            output = json.dumps(data, indent=2, ensure_ascii=False)
            return {
                "output": output,
                "lossy": result.lossy,
                "fields_omitted": result.fields_omitted,
                "validation_status": "UNVALIDATED",  # I5: Explicit bypass
            }

        elif output_format == "yaml":
            # Convert filtered AST to dictionary, then serialize as YAML
            data = _ast_to_dict(result.filtered_doc)
            output = yaml.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
            return {
                "output": output,
                "lossy": result.lossy,
                "fields_omitted": result.fields_omitted,
                "validation_status": "UNVALIDATED",  # I5: Explicit bypass
            }

        elif output_format == "markdown":
            # Convert filtered AST to Markdown
            output = _ast_to_markdown(result.filtered_doc)
            return {
                "output": output,
                "lossy": result.lossy,
                "fields_omitted": result.fields_omitted,
                "validation_status": "UNVALIDATED",  # I5: Explicit bypass
            }

        elif output_format == "gbnf":
            # Issue #171/#191: Export as llama.cpp GBNF grammar
            # Check for META.CONTRACT first (v6 self-describing documents)
            # Fall back to POLICY/FIELDS blocks if no CONTRACT
            doc = result.filtered_doc
            if doc.meta and "CONTRACT" in doc.meta:
                # Issue #191: Use META.CONTRACT for schema-specific GBNF
                gbnf_grammar = compile_gbnf_from_meta(doc.meta)
            else:
                # Fall back to extracting from POLICY/FIELDS blocks
                schema = extract_schema_from_document(doc)
                compiler = GBNFCompiler()
                gbnf_grammar = compiler.compile_schema(schema, include_envelope=True)
            return {
                "output": gbnf_grammar,
                "lossy": False,  # GBNF export is lossless from schema perspective
                "fields_omitted": [],
                "validation_status": "UNVALIDATED",  # I5: Explicit bypass
                "format": "gbnf",  # Indicate output format
            }

        else:  # output_format == "octave"
            return {
                "output": result.output,
                "lossy": result.lossy,
                "fields_omitted": result.fields_omitted,
                "validation_status": "UNVALIDATED",  # I5: Explicit bypass
            }
