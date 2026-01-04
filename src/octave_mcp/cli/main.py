"""CLI entry point for OCTAVE tools.

Aligned with MCP tools per Issue #51.
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
        result["META"] = {k: convert_value(v) for k, v in doc.meta.items()}
    for section in doc.sections:
        if isinstance(section, Assignment):
            result[section.key] = convert_value(section.value)
        elif isinstance(section, Block):
            result[section.key] = convert_block(section)
    return result


def _block_to_markdown(block, lines, level=3):
    """Convert Block to Markdown recursively.

    CRS-FIX #2: Complete implementation that processes nested block children.

    Args:
        block: Block node
        lines: Output lines list (mutated)
        level: Heading level
    """
    from octave_mcp.core.ast_nodes import Assignment, Block

    for child in block.children:
        if isinstance(child, Assignment):
            lines.append(f"- **{child.key}**: {child.value}")
        elif isinstance(child, Block):
            lines.append(f"{'#' * level} {child.key}")
            lines.append("")
            _block_to_markdown(child, lines, level + 1)


def _ast_to_markdown(doc):
    """Convert AST Document to Markdown format.

    CRS-FIX #2: Complete implementation that processes nested block children,
    matching the MCP octave_eject tool behavior.
    """
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
            _block_to_markdown(section, lines, level=3)

    return "\n".join(lines)


@cli.command()
@click.argument("file", type=click.Path(exists=True))
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
def eject(file: str, mode: str, output_format: str):
    """Eject OCTAVE to projected format.

    Matches MCP octave_eject tool. Supports projection modes:
    - canonical: Full document (default)
    - authoring: Lenient format
    - executive: STATUS, RISKS, DECISIONS only (lossy)
    - developer: TESTS, CI, DEPS only (lossy)

    Output formats: octave (default), json, yaml, markdown.

    Note: --schema option is not available in CLI eject (file-based).
    Schema is only meaningful for MCP template generation.
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
@click.option("--verify-seal", "verify_seal", is_flag=True, help="Verify SEAL section integrity")
def validate(file: str | None, use_stdin: bool, schema: str | None, fix: bool, verify_seal: bool):
    """Validate OCTAVE against schema.

    Matches MCP octave_validate tool. Returns validation_status:
    VALIDATED (schema passed), UNVALIDATED (no schema), or INVALID (schema failed).

    With --verify-seal, also checks SEAL section integrity:
    - VERIFIED: Hash matches content
    - INVALID: Hash mismatch (content modified)
    - No SEAL section: Informational message

    Exit code 0 on success, 1 on validation failure.
    """
    import sys

    from octave_mcp.core.emitter import emit
    from octave_mcp.core.parser import parse
    from octave_mcp.core.repair import repair
    from octave_mcp.core.validator import Validator
    from octave_mcp.schemas.loader import get_builtin_schema, load_schema_by_name

    # CRS-FIX #4: XOR enforcement - exactly ONE input source
    if file is not None and use_stdin:
        click.echo("Error: Cannot provide both FILE and --stdin", err=True)
        raise SystemExit(1)

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

        # Gap_5: Load SchemaDefinition for repair() to use
        # repair() requires SchemaDefinition (not old-style dict) for TIER_REPAIR fixes
        schema_definition = load_schema_by_name(schema) if schema else None

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
        # Gap_5: Pass schema_definition to repair() for schema-driven repairs
        # repair() requires schema parameter to apply TIER_REPAIR fixes (enum casefold, type coercion)
        if fix and validation_errors:
            doc, repair_log = repair(doc, validation_errors, fix=True, schema=schema_definition)
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

        # Seal verification if requested
        seal_status = None
        if verify_seal:
            from octave_mcp.core.sealer import SealStatus
            from octave_mcp.core.sealer import verify_seal as do_verify_seal

            seal_result = do_verify_seal(doc)
            seal_status = seal_result.status

            if seal_status == SealStatus.VERIFIED:
                click.echo("Seal: VERIFIED (SHA256 match)")
            elif seal_status == SealStatus.INVALID:
                click.echo("Seal: INVALID (hash mismatch - content modified)")
            elif seal_status == SealStatus.NO_SEAL:
                click.echo("Seal: No SEAL section found")

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

    Exactly ONE of --content, --stdin, or --changes must be provided.

    Exit code 0 on success, 1 on failure.
    """
    import json as json_module
    import sys

    from octave_mcp.core.ast_nodes import Assignment
    from octave_mcp.core.emitter import emit
    from octave_mcp.core.file_ops import atomic_write_octave, validate_octave_path
    from octave_mcp.core.parser import parse
    from octave_mcp.core.validator import Validator
    from octave_mcp.schemas.loader import get_builtin_schema

    # CRS-FIX #3: XOR enforcement - exactly ONE input source
    # Count how many input sources are provided
    input_sources = sum([content is not None, use_stdin, changes is not None])

    if input_sources == 0:
        click.echo("Error: Must provide --content, --stdin, or --changes", err=True)
        raise SystemExit(1)

    if input_sources > 1:
        click.echo(
            "Error: Cannot provide multiple input sources (use exactly ONE of --content, --stdin, or --changes)",
            err=True,
        )
        raise SystemExit(1)

    # CRS-FIX #5: Security validation
    path_valid, path_error = validate_octave_path(file)
    if not path_valid:
        click.echo(f"Error: {path_error}", err=True)
        raise SystemExit(1)

    # Get content from stdin if requested
    if use_stdin:
        content = sys.stdin.read()

    try:
        # Handle content mode (create/overwrite)
        if content is not None:
            # Parse and emit canonical form
            doc = parse(content)
            canonical_content = emit(doc)

        else:
            # Handle changes mode (delta update)
            from pathlib import Path

            target_path = Path(file)

            if not target_path.exists():
                click.echo("Error: File does not exist - changes mode requires existing file", err=True)
                raise SystemExit(1)

            # Read existing file
            original_content = target_path.read_text(encoding="utf-8")

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

        # CRS-FIX #5: Use atomic write with security checks
        write_result = atomic_write_octave(file, canonical_content, base_hash)

        if write_result["status"] == "error":
            click.echo(f"Error: {write_result['error']}", err=True)
            raise SystemExit(1)

        # Output success information
        click.echo(f"path: {write_result['path']}")
        click.echo(f"canonical_hash: {write_result['canonical_hash']}")
        click.echo(f"validation_status: {validation_status}")

    except SystemExit:
        raise
    except json_module.JSONDecodeError as e:
        click.echo(f"Error: Invalid JSON in --changes: {e}", err=True)
        raise SystemExit(1) from e
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1) from e


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option(
    "--registry",
    type=click.Path(exists=True),
    help="Path to vocabulary registry file (default: specs/vocabularies/registry.oct.md)",
)
@click.option(
    "--mapping",
    multiple=True,
    help="Direct namespace mapping in format 'namespace=path' (can be repeated)",
)
@click.option(
    "--collision",
    type=click.Choice(["error", "source_wins", "local_wins"]),
    default="error",
    help="Collision handling strategy (default: error)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output file path (default: stdout)",
)
def hydrate(
    file: str,
    registry: str | None,
    mapping: tuple[str, ...],
    collision: str,
    output: str | None,
):
    """Hydrate vocabulary imports in OCTAVE document.

    Transforms §CONTEXT::IMPORT["@namespace/name"] directives into:
    - §CONTEXT::SNAPSHOT["@namespace/name"] with hydrated terms
    - §SNAPSHOT::MANIFEST with provenance (SOURCE_URI, SOURCE_HASH, HYDRATION_TIME)
    - §SNAPSHOT::PRUNED with available-but-unused terms

    Issue #48: Living Scrolls vocabulary hydration.

    Examples:
        octave hydrate doc.oct.md --registry specs/vocabularies/registry.oct.md
        octave hydrate doc.oct.md --mapping "@test/vocab=./vocab.oct.md"
        octave hydrate doc.oct.md -o hydrated.oct.md

    Exit code 0 on success, 1 on failure.
    """
    from pathlib import Path

    from octave_mcp.core import hydrator
    from octave_mcp.core.emitter import emit

    try:
        # Build registry from options
        if mapping:
            # Direct mappings provided via --mapping
            mappings_dict: dict[str, Path] = {}
            for m in mapping:
                if "=" not in m:
                    click.echo(f"Error: Invalid mapping format '{m}'. Use 'namespace=path'", err=True)
                    raise SystemExit(1)
                namespace, path_str = m.split("=", 1)
                mappings_dict[namespace] = Path(path_str)
            vocab_registry = hydrator.VocabularyRegistry.from_mappings(mappings_dict)
        elif registry:
            # Registry file provided
            vocab_registry = hydrator.VocabularyRegistry(Path(registry))
        else:
            # Try default registry location
            default_registry = Path("specs/vocabularies/registry.oct.md")
            if default_registry.exists():
                vocab_registry = hydrator.VocabularyRegistry(default_registry)
            else:
                click.echo(
                    "Error: No registry specified and default registry not found. "
                    "Use --registry or --mapping option.",
                    err=True,
                )
                raise SystemExit(1)

        # Build policy
        policy = hydrator.HydrationPolicy(
            collision_strategy=collision,  # type: ignore
            prune_strategy="list",
            max_depth=1,
        )

        # Hydrate the document
        source_path = Path(file)
        result = hydrator.hydrate(source_path, vocab_registry, policy)

        # Emit canonical output
        output_content = emit(result)

        # Write to file or stdout
        if output:
            # Security: validate output path before writing (Issue #48 CRS fix)
            from octave_mcp.core.file_ops import atomic_write_octave, validate_octave_path

            path_valid, path_error = validate_octave_path(output)
            if not path_valid:
                click.echo(f"Error: {path_error}", err=True)
                raise SystemExit(1)

            write_result = atomic_write_octave(output, output_content, None)
            if write_result["status"] == "error":
                click.echo(f"Error: {write_result['error']}", err=True)
                raise SystemExit(1)

            click.echo(f"Hydrated document written to: {write_result['path']}")
        else:
            click.echo(output_content)

    except hydrator.CollisionError as e:
        click.echo(f"Error: Term collision - {e}", err=True)
        raise SystemExit(1) from e
    except hydrator.VocabularyError as e:
        click.echo(f"Error: Vocabulary error - {e}", err=True)
        raise SystemExit(1) from e
    except SystemExit:
        raise
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1) from e


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output file path (default: stdout)",
)
def normalize(file: str, output: str | None):
    """Normalize OCTAVE document to canonical form.

    Transforms an OCTAVE document to canonical form with:
    - UTF-8 encoding
    - LF-only line endings (no CRLF)
    - Trimmed trailing whitespace
    - Normalized indentation (2 spaces)
    - Unicode operators (-> to U+2192, + to U+2295, # to U+00A7, etc.)

    Issue #48 Phase 2: Wall Condition C1 canonical text rules.

    Examples:
        octave normalize doc.oct.md
        octave normalize doc.oct.md -o normalized.oct.md

    Exit code 0 on success, 1 on failure.
    """
    from pathlib import Path

    from octave_mcp.core.emitter import emit
    from octave_mcp.core.parser import parse

    try:
        # Read input file
        input_path = Path(file)
        content = input_path.read_text(encoding="utf-8")

        # Parse (lenient) -> AST
        doc = parse(content)

        # Emit (canonical) -> normalized output
        output_content = emit(doc)

        # Write to file or stdout
        if output:
            # Security: validate output path before writing
            from octave_mcp.core.file_ops import atomic_write_octave, validate_octave_path

            path_valid, path_error = validate_octave_path(output)
            if not path_valid:
                click.echo(f"Error: {path_error}", err=True)
                raise SystemExit(1)

            write_result = atomic_write_octave(output, output_content, None)
            if write_result["status"] == "error":
                click.echo(f"Error: {write_result['error']}", err=True)
                raise SystemExit(1)

            click.echo(f"Normalized document written to: {write_result['path']}")
        else:
            click.echo(output_content)

    except SystemExit:
        raise
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1) from e


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output file path (default: stdout)",
)
def seal(file: str, output: str | None):
    """Seal OCTAVE document with cryptographic integrity proof.

    Adds a SEAL section to the document containing:
    - SCOPE: Line range covered by seal (LINES[1,N])
    - ALGORITHM: Hash algorithm used (SHA256)
    - HASH: SHA256 hash of normalized content
    - GRAMMAR: Grammar version (if present in document)

    The document is normalized (parse -> emit) before sealing to ensure
    consistent hashing regardless of input formatting.

    Issue #48 Phase 2: SEAL Cryptographic Integrity Layer.

    Examples:
        octave seal doc.oct.md
        octave seal doc.oct.md -o sealed.oct.md

    Exit code 0 on success, 1 on failure.
    """
    from pathlib import Path

    from octave_mcp.core.emitter import emit
    from octave_mcp.core.parser import parse
    from octave_mcp.core.sealer import seal_document

    try:
        # Read input file
        input_path = Path(file)
        content = input_path.read_text(encoding="utf-8")

        # Parse (lenient) -> AST
        doc = parse(content)

        # Seal the document (handles normalization internally)
        sealed_doc = seal_document(doc)

        # Emit canonical sealed output
        output_content = emit(sealed_doc)

        # Write to file or stdout
        if output:
            # Security: validate output path before writing
            from octave_mcp.core.file_ops import atomic_write_octave, validate_octave_path

            path_valid, path_error = validate_octave_path(output)
            if not path_valid:
                click.echo(f"Error: {path_error}", err=True)
                raise SystemExit(1)

            write_result = atomic_write_octave(output, output_content, None)
            if write_result["status"] == "error":
                click.echo(f"Error: {write_result['error']}", err=True)
                raise SystemExit(1)

            click.echo(f"Sealed document written to: {write_result['path']}")
        else:
            click.echo(output_content)

    except SystemExit:
        raise
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1) from e


@cli.command()
@click.argument("spec_file", type=click.Path(exists=True))
@click.argument("skill_file", type=click.Path(exists=True))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (default: text)",
)
def coverage(spec_file: str, skill_file: str, output_format: str):
    """Analyze coverage between SPEC and SKILL documents.

    VOID MAPPER tool for spec-to-skill coverage analysis.
    Identifies gaps between specifications and their implementing skills.

    Output shows:
    - COVERAGE_RATIO: Percentage of spec sections covered
    - GAPS: Spec sections NOT implemented in skill
    - NOVEL: Skill sections NOT in spec

    Examples:
        octave coverage spec.oct.md skill.oct.md
        octave coverage spec.oct.md skill.oct.md --format json

    Exit code 0 on success, 1 on failure.
    """
    import json as json_module
    from pathlib import Path

    from octave_mcp.core.coverage_mapper import compute_coverage, format_coverage_report
    from octave_mcp.core.parser import parse

    try:
        # Read spec and skill files
        spec_path = Path(spec_file)
        skill_path = Path(skill_file)

        spec_content = spec_path.read_text(encoding="utf-8")
        skill_content = skill_path.read_text(encoding="utf-8")

        # Parse documents
        spec_doc = parse(spec_content)
        skill_doc = parse(skill_content)

        # Compute coverage
        result = compute_coverage(spec_doc, skill_doc)

        # Output based on format
        if output_format == "json":
            data = {
                "spec": str(spec_path),
                "skill": str(skill_path),
                "coverage_ratio": result.coverage_ratio,
                "covered_sections": result.covered_sections,
                "gaps": result.gaps,
                "novel": result.novel,
                "spec_total": result.spec_total,
                "skill_total": result.skill_total,
            }
            click.echo(json_module.dumps(data, indent=2))
        else:
            # Text format with header
            click.echo("Coverage Analysis")
            click.echo("=================")
            click.echo(f"Spec: {spec_path.name}")
            click.echo(f"Skill: {skill_path.name}")
            click.echo("")
            click.echo(format_coverage_report(result))

    except SystemExit:
        raise
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1) from e


if __name__ == "__main__":
    cli()
