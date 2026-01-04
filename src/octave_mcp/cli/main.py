"""CLI entry point for OCTAVE tools.

Aligned with MCP tools per Issue #51.
"""

import click

from octave_mcp import __version__


@click.group()
@click.version_option(version=__version__)
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


def _compute_allowed_root_for_check(doc, base_path):
    """Compute allowed_root by finding common ancestor of document and SOURCE_URIs.

    Issue #48 Cross-directory fix: When hydrate creates output in a different
    directory than the vocabulary (e.g., output in docs/, vocab in specs/),
    the SOURCE_URI contains ".." patterns. The default allowed_root (document's
    parent) is too restrictive for these legitimate cross-directory layouts.

    This function:
    1. Extracts all SOURCE_URI paths from MANIFEST sections
    2. Resolves them relative to base_path
    3. Finds the common ancestor of base_path and all resolved paths
    4. Returns that as the allowed_root for containment checking

    Security: The common ancestor approach is safe because:
    - Absolute paths are still rejected by check_staleness()
    - The allowed_root is at most as broad as the common ancestor
    - Path traversal attacks (../../../etc/passwd) would still fail
      because they resolve outside any reasonable project root

    Args:
        doc: Parsed OCTAVE document (already hydrated)
        base_path: Document's parent directory (resolved)

    Returns:
        Path to use as allowed_root for check_staleness()
    """
    from pathlib import Path

    from octave_mcp.core.ast_nodes import Assignment, Section

    # Collect all resolved SOURCE_URI paths
    resolved_paths = [base_path]  # Start with document's directory

    for section in doc.sections:
        if isinstance(section, Section):
            if section.section_id == "SNAPSHOT" and section.key == "MANIFEST":
                for child in section.children:
                    if isinstance(child, Assignment) and child.key == "SOURCE_URI":
                        source_uri = child.value
                        if isinstance(source_uri, str) and source_uri.strip():
                            # Skip absolute paths (they'll be rejected later anyway)
                            if source_uri.startswith("/") or (len(source_uri) > 1 and source_uri[1] == ":"):
                                continue
                            # Resolve relative path
                            try:
                                resolved = (base_path / source_uri).resolve()
                                resolved_paths.append(resolved)
                            except (OSError, ValueError):
                                # Path resolution failed - let check_staleness handle it
                                continue

    # Find common ancestor of all paths
    if len(resolved_paths) == 1:
        # No SOURCE_URIs found or all failed - use base_path
        return base_path

    # Compute common ancestor using Path parents
    # Start with first path's parents and intersect with others
    common_parts = list(resolved_paths[0].parts)

    for path in resolved_paths[1:]:
        path_parts = list(path.parts)
        # Find longest common prefix
        new_common = []
        for a, b in zip(common_parts, path_parts, strict=False):
            if a == b:
                new_common.append(a)
            else:
                break
        common_parts = new_common

    if not common_parts:
        # No common ancestor (shouldn't happen on same filesystem)
        return base_path

    # Reconstruct path from common parts
    common_ancestor = Path(*common_parts)

    return common_ancestor


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
@click.option(
    "--require-seal",
    "require_seal",
    is_flag=True,
    help="Require SEAL section (exit 1 if missing). Only valid with --verify-seal",
)
def validate(file: str | None, use_stdin: bool, schema: str | None, fix: bool, verify_seal: bool, require_seal: bool):
    """Validate OCTAVE against schema.

    Matches MCP octave_validate tool. Returns validation_status:
    VALIDATED (schema passed), UNVALIDATED (no schema), or INVALID (schema failed).

    With --verify-seal, also checks SEAL section integrity:
    - VERIFIED: Hash matches content
    - INVALID: Hash mismatch (content modified) - exits with code 1
    - No SEAL section: Informational message (exit 0 unless --require-seal)

    With --require-seal (requires --verify-seal):
    - Exit 1 if no SEAL section found
    - Useful for CI to enforce sealed documents

    Exit code 0 on success, 1 on validation or seal failure.
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

    # Issue #131: --require-seal only valid with --verify-seal
    if require_seal and not verify_seal:
        click.echo("Error: --require-seal requires --verify-seal", err=True)
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

        # If schema validation INVALID, output errors and exit with code 1
        if validation_status == "INVALID":
            for error in validation_errors:
                click.echo(f"  {error.code}: {error.message}", err=True)
            raise SystemExit(1)

        # Issue #131: Exit with failure if seal verification failed
        if verify_seal:
            from octave_mcp.core.sealer import SealStatus

            if seal_status == SealStatus.INVALID:
                raise SystemExit(1)
            if require_seal and seal_status == SealStatus.NO_SEAL:
                click.echo("Error: --require-seal specified but no SEAL section found", err=True)
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
@click.option(
    "--check",
    "check_mode",
    is_flag=True,
    help="Check staleness of hydrated document (exit 0=fresh, 1=stale or error)",
)
@click.option(
    "--project-root",
    "project_root",
    type=click.Path(exists=True),
    help="Project root directory for security containment (default: document's parent directory)",
)
@click.option(
    "--prune-manifest",
    "prune_manifest",
    type=click.Choice(["list", "hash", "count", "elide"]),
    default="list",
    help="How to manifest pruned terms: list (default), hash (SHA256), count (integer), or elide (omit section)",
)
def hydrate(
    file: str,
    registry: str | None,
    mapping: tuple[str, ...],
    collision: str,
    output: str | None,
    check_mode: bool,
    project_root: str | None,
    prune_manifest: str,
):
    """Hydrate vocabulary imports in OCTAVE document.

    Transforms §CONTEXT::IMPORT["@namespace/name"] directives into:
    - §CONTEXT::SNAPSHOT["@namespace/name"] with hydrated terms
    - §SNAPSHOT::MANIFEST with provenance (SOURCE_URI, SOURCE_HASH, HYDRATION_TIME)
    - §SNAPSHOT::PRUNED with available-but-unused terms

    With --check flag, checks staleness of already-hydrated document:
    - Exit 0: All snapshots are fresh (hashes match)
    - Exit 1: At least one snapshot is stale or error occurred

    Security: The --project-root option specifies the containment boundary.
    All resolved SOURCE_URI paths must stay within this directory.
    Defaults to the document's parent directory if not specified.

    Issue #48: Living Scrolls vocabulary hydration.

    Examples:
        octave hydrate doc.oct.md --registry specs/vocabularies/registry.oct.md
        octave hydrate doc.oct.md --mapping "@test/vocab=./vocab.oct.md"
        octave hydrate doc.oct.md -o hydrated.oct.md
        octave hydrate hydrated.oct.md --check
        octave hydrate hydrated.oct.md --check --project-root /path/to/project

    Exit code 0 on success, 1 on failure.
    """
    from pathlib import Path

    from octave_mcp.core import hydrator
    from octave_mcp.core.emitter import emit
    from octave_mcp.core.parser import parse

    try:
        # Handle --check mode (staleness detection)
        if check_mode:
            # --check is mutually exclusive with hydration options
            if mapping or registry or output:
                click.echo(
                    "Error: --check cannot be used with --mapping, --registry, or --output. "
                    "Use --check alone to verify staleness of an already-hydrated document.",
                    err=True,
                )
                raise SystemExit(1)

            # Read and parse the document
            source_path = Path(file)
            content = source_path.read_text(encoding="utf-8")
            doc = parse(content)

            # Check staleness
            # Issue #48 CE Review: Use document's directory as base_path for
            # resolving relative SOURCE_URI paths (security + portability)
            # Issue #48 CE Security Fix: Use allowed_root for post-resolution containment
            # Issue #48 Cross-directory fix: Auto-detect allowed_root when SOURCE_URI contains ".."
            base_path = source_path.parent.resolve()

            if project_root:
                # User explicitly specified project root
                allowed_root = Path(project_root).resolve()
            else:
                # Auto-detect allowed_root from SOURCE_URI paths
                # This handles cross-directory layouts (e.g., output in docs/, vocab in specs/)
                allowed_root = _compute_allowed_root_for_check(doc, base_path)

            results = hydrator.check_staleness(doc, base_path=base_path, allowed_root=allowed_root)

            if not results:
                # No snapshots found - nothing to check
                click.echo("No SNAPSHOT sections found in document.")
                raise SystemExit(0)

            # Report results
            has_stale_or_error = False
            for staleness_result in results:
                if staleness_result.status == "FRESH":
                    actual_hash = staleness_result.actual_hash or "N/A"
                    click.echo(f"FRESH: {staleness_result.namespace} (hash: {actual_hash[:20]}...)")
                elif staleness_result.status == "STALE":
                    actual = staleness_result.actual_hash[:20] if staleness_result.actual_hash else "N/A"
                    click.echo(
                        f"STALE: {staleness_result.namespace} "
                        f"(expected: {staleness_result.expected_hash[:20]}..., got: {actual}...)"
                    )
                    has_stale_or_error = True
                else:  # ERROR
                    click.echo(f"ERROR: {staleness_result.namespace} - {staleness_result.error}")
                    has_stale_or_error = True

            if has_stale_or_error:
                raise SystemExit(1)
            else:
                raise SystemExit(0)

        # Normal hydration mode
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
                    "Error: No registry specified and default registry not found. Use --registry or --mapping option.",
                    err=True,
                )
                raise SystemExit(1)

        # Build policy
        # Issue #48 Task 2.11: Use --prune-manifest option for prune_strategy
        policy = hydrator.HydrationPolicy(
            collision_strategy=collision,  # type: ignore
            prune_strategy=prune_manifest,  # type: ignore
            max_depth=1,
        )

        # Hydrate the document
        # Issue #48 Debate Decision: Pass output_path for relative SOURCE_URI
        source_path = Path(file)
        output_path = Path(output) if output else None
        result = hydrator.hydrate(source_path, vocab_registry, policy, output_path)

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


@cli.group()
def vocab():
    """Vocabulary management commands.

    Issue #48 Task 2.9: Commands for working with OCTAVE vocabularies.
    """
    pass


@vocab.command("list")
@click.option(
    "--registry",
    type=click.Path(exists=True),
    help="Path to vocabulary registry file (default: specs/vocabularies/registry.oct.md)",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format (default: table)",
)
def vocab_list(registry: str | None, output_format: str):
    """List available vocabularies from registry.

    Reads the vocabulary registry and displays:
    - Name: Vocabulary capsule name
    - Version: Semantic version
    - Path: Relative path from registry root
    - Term count: Number of terms in the vocabulary

    Examples:
        octave vocab list
        octave vocab list --registry specs/vocabularies/registry.oct.md
        octave vocab list --format json

    Exit code 0 on success, 1 on error.
    """
    import json as json_module
    from pathlib import Path

    from octave_mcp.core.parser import parse

    try:
        # Determine registry path
        if registry:
            registry_path = Path(registry)
        else:
            # Try default location
            registry_path = Path("specs/vocabularies/registry.oct.md")
            if not registry_path.exists():
                click.echo(
                    "Error: No registry specified and default registry not found at "
                    "specs/vocabularies/registry.oct.md. Use --registry option.",
                    err=True,
                )
                raise SystemExit(1)

        # Read and parse registry
        content = registry_path.read_text(encoding="utf-8")
        doc = parse(content)

        # Extract vocabulary entries
        vocabularies = _extract_vocabulary_entries_from_registry(doc)

        if not vocabularies:
            click.echo("No vocabularies found in registry.")
            raise SystemExit(0)

        # Output based on format
        if output_format == "json":
            output = json_module.dumps(vocabularies, indent=2)
            click.echo(output)
        else:
            # Table format
            _print_vocabulary_table(vocabularies)

    except SystemExit:
        raise
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1) from e


def _extract_vocabulary_entries_from_registry(doc) -> list[dict]:
    """Extract vocabulary entries from parsed registry document.

    Looks for nested sections with NAME, PATH, VERSION, and TERMS fields.

    Args:
        doc: Parsed OCTAVE document

    Returns:
        List of vocabulary entry dictionaries
    """
    from octave_mcp.core.ast_nodes import Assignment, ListValue, Section

    vocabularies = []

    def extract_from_section(section):
        """Recursively extract vocabulary entries from section."""
        name = None
        path = None
        version = None
        terms = []

        for child in section.children:
            if isinstance(child, Assignment):
                if child.key == "NAME":
                    name = child.value
                elif child.key == "PATH":
                    path = child.value
                elif child.key == "VERSION":
                    version = child.value
                elif child.key == "TERMS":
                    if isinstance(child.value, ListValue):
                        terms = child.value.items
                    elif isinstance(child.value, list):
                        terms = child.value
            elif isinstance(child, Section):
                # Recurse into nested sections
                extract_from_section(child)

        # If we found a vocabulary entry, add it
        if name and path:
            vocabularies.append(
                {
                    "name": name,
                    "version": version or "unknown",
                    "path": path,
                    "term_count": len(terms),
                }
            )

    # Search all sections
    for section in doc.sections:
        if isinstance(section, Section):
            extract_from_section(section)

    return vocabularies


def _print_vocabulary_table(vocabularies: list[dict]) -> None:
    """Print vocabulary entries in table format.

    Args:
        vocabularies: List of vocabulary entry dictionaries
    """
    # Calculate column widths
    name_width = max(len("Name"), max(len(v["name"]) for v in vocabularies))
    version_width = max(len("Version"), max(len(str(v["version"])) for v in vocabularies))
    path_width = max(len("Path"), max(len(v["path"]) for v in vocabularies))
    count_width = max(len("Terms"), max(len(str(v["term_count"])) for v in vocabularies))

    # Print header
    header = f"{'Name':<{name_width}}  {'Version':<{version_width}}  {'Path':<{path_width}}  {'Terms':>{count_width}}"
    click.echo(header)
    click.echo("-" * len(header))

    # Print rows
    for vocab in vocabularies:
        row = (
            f"{vocab['name']:<{name_width}}  "
            f"{vocab['version']:<{version_width}}  "
            f"{vocab['path']:<{path_width}}  "
            f"{vocab['term_count']:>{count_width}}"
        )
        click.echo(row)


if __name__ == "__main__":
    cli()
