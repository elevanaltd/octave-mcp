"""Schema loader (P1.11) - Enhanced with holographic pattern parsing (Issue #93).

Parse .oct.md schema files into SchemaDefinition objects for validator consumption.

This module provides:
- load_schema(): Load schema from file path, returns SchemaDefinition
- load_schema_by_name(): Load schema by name from search paths
- get_schema_search_paths(): Get list of schema search paths
- get_builtin_schema(): Get builtin schema definition by name
- load_builtin_schemas(): Load all builtin schemas
"""

import re
from pathlib import Path
from typing import Any

from octave_mcp.core.parser import parse
from octave_mcp.core.schema_extractor import (
    SchemaDefinition,
    extract_schema_from_document,
)

# Security: Pattern for valid schema names (uppercase letters, digits, underscores)
# Must start with uppercase letter. Prevents path traversal attacks like "../secret"
SCHEMA_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


# BUILTIN_SCHEMA_DEFINITIONS maintained for backwards compatibility
# These provide fallback schemas when schema files are not available
BUILTIN_SCHEMA_DEFINITIONS: dict[str, dict[str, Any]] = {
    "META": {
        "name": "META",
        "version": "1.0.0",
        "META": {
            "required": ["TYPE", "VERSION"],
            "fields": {
                "TYPE": {"type": "STRING"},
                "VERSION": {"type": "STRING"},
                "STATUS": {"type": "ENUM", "values": ["DRAFT", "ACTIVE", "DEPRECATED"]},
            },
        },
    },
}


def get_builtin_schema(schema_name: str) -> dict[str, Any] | None:
    """Get a builtin schema definition by name.

    Args:
        schema_name: Schema name (e.g., 'META', 'SESSION_LOG')

    Returns:
        Schema definition dict or None if not found
    """
    return BUILTIN_SCHEMA_DEFINITIONS.get(schema_name)


def get_schema_search_paths() -> list[Path]:
    """Get list of paths to search for schema files.

    Returns paths in priority order:
    1. resources/specs/schemas/ in package directory (installed package)
    2. src/octave_mcp/resources/specs/schemas/ in project root (development)
    3. specs/schemas/ in project root (backward compatibility)
    4. schemas/builtin/ in package directory

    Returns:
        List of Path objects for schema search directories
    """
    paths: list[Path] = []

    # 1. Package resources location (for installed package)
    package_resources = Path(__file__).parent.parent / "resources" / "specs" / "schemas"
    if package_resources.exists():
        paths.append(package_resources)

    # 2. New consolidated location in resources (development)
    resources_dir = Path.cwd() / "src" / "octave_mcp" / "resources" / "specs" / "schemas"
    if resources_dir.exists():
        paths.append(resources_dir)

    # 3. specs/schemas/ for backward compatibility
    specs_dir = Path.cwd() / "specs" / "schemas"
    if specs_dir.exists():
        paths.append(specs_dir)

    # 4. schemas/builtin/ in package directory
    builtin_dir = Path(__file__).parent / "builtin"
    if builtin_dir.exists():
        paths.append(builtin_dir)

    return paths


def load_schema(schema_path: str | Path) -> SchemaDefinition:
    """Load schema from .oct.md file using holographic pattern parsing.

    Issue #93: This now uses the holographic pattern parser to extract
    complete schema definitions including:
    - Field definitions with holographic patterns
    - Constraint chains (REQ, OPT, ENUM, REGEX, etc.)
    - Extraction targets (section markers)
    - POLICY blocks with VERSION, UNKNOWN_FIELDS, TARGETS

    Args:
        schema_path: Path to schema file

    Returns:
        SchemaDefinition with parsed fields, constraints, and policy

    Raises:
        FileNotFoundError: If schema file doesn't exist
    """
    path = Path(schema_path)
    if not path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    with open(path) as f:
        content = f.read()

    # Parse schema document
    doc = parse(content)

    # Extract schema definition using holographic pattern parser
    schema = extract_schema_from_document(doc)

    return schema


def load_schema_by_name(schema_name: str) -> SchemaDefinition | None:
    """Load schema by name from search paths.

    Searches for schema files in priority order:
    1. {search_path}/{schema_name.lower()}.oct.md
    2. {search_path}/{schema_name}.oct.md

    Args:
        schema_name: Schema name (e.g., 'META', 'SESSION_LOG')

    Returns:
        SchemaDefinition if found, None otherwise

    Security:
        Validates schema_name against SCHEMA_NAME_PATTERN to prevent path traversal.
        Names containing path separators, '..' or other special characters are rejected.
    """
    # Security: Validate schema name to prevent path traversal attacks
    # Schema names must be uppercase letters, digits, underscores only
    # This blocks attacks like "../secret", "foo/bar", etc.
    if not SCHEMA_NAME_PATTERN.match(schema_name):
        return None  # Invalid schema name format - reject silently

    search_paths = get_schema_search_paths()

    # Try different filename patterns
    patterns = [
        f"{schema_name.lower()}.oct.md",
        f"{schema_name}.oct.md",
    ]

    for search_path in search_paths:
        for pattern in patterns:
            schema_file = search_path / pattern
            if schema_file.exists():
                return load_schema(schema_file)

    return None


def load_builtin_schemas() -> dict[str, SchemaDefinition]:
    """Load all builtin schemas from schemas/builtin/ directory.

    Returns:
        Dictionary of schema name -> SchemaDefinition
    """
    schemas: dict[str, SchemaDefinition] = {}

    # Load from builtin directory
    builtin_dir = Path(__file__).parent / "builtin"
    if builtin_dir.exists():
        for schema_file in builtin_dir.glob("*.oct.md"):
            try:
                schema = load_schema(schema_file)
                schemas[schema.name] = schema
            except Exception:
                # Skip files that fail to parse
                pass

    return schemas
