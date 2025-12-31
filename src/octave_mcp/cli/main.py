"""CLI entry point for OCTAVE tools.

Stub for P1.7: cli_implementation
"""

import click


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """OCTAVE command-line tools."""
    pass


def _ast_to_dict(doc):
    """Convert AST Document to dictionary for JSON/YAML export."""
    from octave_mcp.core.ast_nodes import Assignment, Block, InlineMap, ListValue

    def convert_value(value):
        if isinstance(value, ListValue):
            return [convert_value(item) for item in value.items]
        elif isinstance(value, InlineMap):
            return {k: convert_value(v) for k, v in value.pairs.items()}
        return value

    def convert_block(block):
        result = {}
        for child in block.children:
            if isinstance(child, Assignment):
                result[child.key] = convert_value(child.value)
            elif isinstance(child, Block):
                result[child.key] = convert_block(child)
        return result

    result = {}
    if doc.meta:
        result["META"] = doc.meta
    for section in doc.sections:
        if isinstance(section, Assignment):
            result[section.key] = convert_value(section.value)
        elif isinstance(section, Block):
            result[section.key] = convert_block(section)
    return result


def _ast_to_markdown(doc):
    """Convert AST Document to Markdown format."""
    from octave_mcp.core.ast_nodes import Assignment, Block

    lines = [f"# {doc.name}", ""]
    if doc.meta:
        lines.append("## META")
        lines.append("")
        for key, value in doc.meta.items():
            lines.append(f"- **{key}**: {value}")
        lines.append("")
    for section in doc.sections:
        if isinstance(section, Assignment):
            lines.append(f"**{section.key}**: {section.value}")
            lines.append("")
        elif isinstance(section, Block):
            lines.append(f"## {section.key}")
            lines.append("")
    return "\n".join(lines)


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--schema", help="Schema name for validation or template generation")
@click.option(
    "--mode",
    type=click.Choice(["canonical", "authoring", "executive", "developer"]),
    default="canonical",
    help="Projection mode",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["octave", "json", "yaml", "markdown"]),
    default="octave",
    help="Output format",
)
def eject(file: str, schema: str | None, mode: str, output_format: str):
    """Eject OCTAVE to projected format.

    Matches MCP octave_eject tool. Supports projection modes:
    - canonical: Full document (default)
    - authoring: Lenient format
    - executive: STATUS, RISKS, DECISIONS only (lossy)
    - developer: TESTS, CI, DEPS only (lossy)

    Output formats: octave (default), json, yaml, markdown.
    """
    import json as json_module

    import yaml as yaml_module

    from octave_mcp.core.parser import parse
    from octave_mcp.core.projector import project

    with open(file) as f:
        content = f.read()

    try:
        # Parse content to AST
        doc = parse(content)

        # Project to desired mode
        result = project(doc, mode=mode)

        # Convert to requested output format
        if output_format == "json":
            data = _ast_to_dict(result.filtered_doc)
            output = json_module.dumps(data, indent=2, ensure_ascii=False)
        elif output_format == "yaml":
            data = _ast_to_dict(result.filtered_doc)
            output = yaml_module.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
        elif output_format == "markdown":
            output = _ast_to_markdown(result.filtered_doc)
        else:  # octave
            output = result.output

        click.echo(output)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1) from e


@cli.command()
@click.argument("file", type=click.Path(exists=True), required=False)
@click.option("--stdin", "use_stdin", is_flag=True, help="Read content from stdin")
@click.option("--schema", help="Schema name for validation (e.g., 'META', 'SESSION_LOG')")
@click.option("--fix", is_flag=True, help="Apply repairs to output")
def validate(file: str | None, use_stdin: bool, schema: str | None, fix: bool):
    """Validate OCTAVE against schema.

    Matches MCP octave_validate tool. Returns validation_status:
    VALIDATED (schema passed), UNVALIDATED (no schema), or INVALID (schema failed).

    Exit code 0 on success, 1 on validation failure.
    """
    import sys

    from octave_mcp.core.emitter import emit
    from octave_mcp.core.parser import parse
    from octave_mcp.core.repair import repair
    from octave_mcp.core.validator import Validator
    from octave_mcp.schemas.loader import get_builtin_schema

    # Get content from file or stdin
    if use_stdin:
        content = sys.stdin.read()
    elif file:
        with open(file) as f:
            content = f.read()
    else:
        click.echo("Error: Must provide FILE or --stdin", err=True)
        raise SystemExit(1)

    try:
        # Parse content
        doc = parse(content)

        # Determine validation status
        validation_status = "UNVALIDATED"
        validation_errors: list = []

        if schema:
            schema_def = get_builtin_schema(schema)
            if schema_def is not None:
                validator = Validator(schema=schema_def)
                validation_errors = validator.validate(doc, strict=False)
                if validation_errors:
                    validation_status = "INVALID"
                else:
                    validation_status = "VALIDATED"
            else:
                # Schema not found - remain UNVALIDATED
                validator = Validator(schema=None)
                validation_errors = validator.validate(doc, strict=False)
        else:
            # No schema specified - basic validation only
            validator = Validator(schema=None)
            validation_errors = validator.validate(doc, strict=False)

        # Apply repairs if requested
        if fix and validation_errors:
            doc, repair_log = repair(doc, validation_errors, fix=True)
            # Re-validate after repairs
            if schema:
                schema_def = get_builtin_schema(schema)
                validator = Validator(schema=schema_def)
                validation_errors = validator.validate(doc, strict=False)
                if not validation_errors:
                    validation_status = "VALIDATED"

        # Output canonical form
        canonical = emit(doc)
        click.echo(canonical)

        # Output validation status
        click.echo(f"\nvalidation_status: {validation_status}")

        # If INVALID, output errors and exit with code 1
        if validation_status == "INVALID":
            for error in validation_errors:
                click.echo(f"  {error.code}: {error.message}", err=True)
            raise SystemExit(1)

    except SystemExit:
        raise
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1) from e


@cli.command()
@click.argument("file", type=click.Path())
@click.option("--content", help="Full OCTAVE content to write")
@click.option("--stdin", "use_stdin", is_flag=True, help="Read content from stdin")
@click.option("--changes", help="JSON string of field changes for existing files")
@click.option("--base-hash", help="Expected SHA-256 hash for CAS consistency check")
@click.option("--schema", help="Schema name for validation before write")
def write(
    file: str,
    content: str | None,
    use_stdin: bool,
    changes: str | None,
    base_hash: str | None,
    schema: str | None,
):
    """Write OCTAVE file with validation.

    Matches MCP octave_write tool. Unified write operation:
    - Use --content or --stdin for full content mode
    - Use --changes for delta updates to existing files

    Exit code 0 on success, 1 on failure.
    """
    import hashlib
    import json as json_module
    import sys
    from pathlib import Path

    from octave_mcp.core.ast_nodes import Assignment
    from octave_mcp.core.emitter import emit
    from octave_mcp.core.parser import parse
    from octave_mcp.core.validator import Validator
    from octave_mcp.schemas.loader import get_builtin_schema

    target_path = Path(file)

    # Get content from options or stdin
    if use_stdin:
        content = sys.stdin.read()

    # Validate that either content or changes is provided
    if content is None and changes is None:
        click.echo("Error: Must provide --content, --stdin, or --changes", err=True)
        raise SystemExit(1)

    if content is not None and changes is not None:
        click.echo("Error: Cannot provide both --content and --changes", err=True)
        raise SystemExit(1)

    try:
        # Handle content mode (create/overwrite)
        if content is not None:
            # Check base hash if provided and file exists
            if base_hash and target_path.exists():
                existing_content = target_path.read_text(encoding="utf-8")
                current_hash = hashlib.sha256(existing_content.encode("utf-8")).hexdigest()
                if current_hash != base_hash:
                    click.echo(
                        f"Error: Hash mismatch (expected {base_hash[:8]}..., got {current_hash[:8]}...)", err=True
                    )
                    raise SystemExit(1)

            # Parse and emit canonical form
            doc = parse(content)
            canonical_content = emit(doc)

        else:
            # Handle changes mode (delta update)
            if not target_path.exists():
                click.echo("Error: File does not exist - changes mode requires existing file", err=True)
                raise SystemExit(1)

            # Read existing file
            original_content = target_path.read_text(encoding="utf-8")

            # Check base hash if provided
            if base_hash:
                current_hash = hashlib.sha256(original_content.encode("utf-8")).hexdigest()
                if current_hash != base_hash:
                    click.echo(
                        f"Error: Hash mismatch (expected {base_hash[:8]}..., got {current_hash[:8]}...)", err=True
                    )
                    raise SystemExit(1)

            # Parse existing content
            doc = parse(original_content)

            # Apply changes (changes is guaranteed to be non-None in this branch)
            assert changes is not None
            changes_dict = json_module.loads(changes)
            for key, value in changes_dict.items():
                if key.startswith("META."):
                    field_name = key[5:]
                    doc.meta[field_name] = value
                elif key == "META" and isinstance(value, dict):
                    doc.meta = value.copy()
                else:
                    # Update or add field in sections
                    found = False
                    for section in doc.sections:
                        if isinstance(section, Assignment) and section.key == key:
                            section.value = value
                            found = True
                            break
                    if not found:
                        doc.sections.append(Assignment(key=key, value=value))

            canonical_content = emit(doc)

        # Schema validation if requested
        validation_status = "UNVALIDATED"
        if schema:
            schema_def = get_builtin_schema(schema)
            if schema_def is not None:
                validator = Validator(schema=schema_def)
                validation_errors = validator.validate(doc, strict=False)
                if validation_errors:
                    validation_status = "INVALID"
                else:
                    validation_status = "VALIDATED"

        # Write file
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(canonical_content, encoding="utf-8")

        # Compute hash
        canonical_hash = hashlib.sha256(canonical_content.encode("utf-8")).hexdigest()

        # Output success information
        click.echo(f"path: {target_path}")
        click.echo(f"canonical_hash: {canonical_hash}")
        click.echo(f"validation_status: {validation_status}")

    except SystemExit:
        raise
    except json_module.JSONDecodeError as e:
        click.echo(f"Error: Invalid JSON in --changes: {e}", err=True)
        raise SystemExit(1) from e
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1) from e


if __name__ == "__main__":
    cli()
