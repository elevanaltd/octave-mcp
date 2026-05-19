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
                "ID": {"type": "STRING"},
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


def _canonical_schema_dirs() -> list[Path]:
    """Return the canonical schema-directory search list, resources-first.

    PR #444 CE rework: prior to this change, ``load_schema_by_name`` used
    resources-first precedence (via the legacy ``get_schema_search_paths``
    ordering) while ``load_builtin_schemas`` used builtin-first precedence
    (hard-coded directory scan order). Discovery and validation could
    therefore disagree on which file wins under a name collision.

    Both loaders now read from this single helper so the precedence is
    auditable and cannot drift. Order matches PR #431/#437/#438: new
    canonical schemas live in ``src/octave_mcp/resources/specs/schemas/``,
    so the resources directory takes precedence over the legacy builtin
    directory.

    Returned directories (in winning order):
      1. Package resources: ``<pkg>/resources/specs/schemas/``
      2. Development resources: ``<cwd>/src/octave_mcp/resources/specs/schemas/``
      3. Legacy ``<cwd>/specs/schemas/`` (backwards compatibility).
      4. Legacy ``<pkg>/schemas/builtin/``.
    """
    paths: list[Path] = []

    package_resources = Path(__file__).parent.parent / "resources" / "specs" / "schemas"
    if package_resources.exists():
        paths.append(package_resources)

    resources_dir = Path.cwd() / "src" / "octave_mcp" / "resources" / "specs" / "schemas"
    if resources_dir.exists() and resources_dir not in paths:
        paths.append(resources_dir)

    specs_dir = Path.cwd() / "specs" / "schemas"
    if specs_dir.exists() and specs_dir not in paths:
        paths.append(specs_dir)

    builtin_dir = Path(__file__).parent / "builtin"
    if builtin_dir.exists() and builtin_dir not in paths:
        paths.append(builtin_dir)

    return paths


def get_schema_search_paths() -> list[Path]:
    """Get list of paths to search for schema files (resources-first).

    Delegates to ``_canonical_schema_dirs`` so ``load_schema_by_name``
    and ``load_builtin_schemas`` share a single source of truth for
    schema directory precedence. See ``_canonical_schema_dirs`` for the
    full ordering rationale.

    Returns:
        List of Path objects for schema search directories.
    """
    return _canonical_schema_dirs()


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
    """Load all builtin schemas for discovery (e.g. grammar resource listing).

    PR #444 CE rework: this loader now delegates directory enumeration
    to ``_canonical_schema_dirs`` so it shares precedence with
    ``load_schema_by_name``. Prior behaviour was builtin-first (legacy
    directory wins on name collision); the canonical direction is
    resources-first per PR #431/#437/#438 (new schemas live in
    ``src/octave_mcp/resources/specs/schemas/``).

    ``dict.setdefault`` is preserved, so the first directory in
    ``_canonical_schema_dirs`` (resources) wins on name collision.

    Returns:
        Dictionary of schema name -> SchemaDefinition.
    """
    schemas: dict[str, SchemaDefinition] = {}

    for directory in _canonical_schema_dirs():
        if not directory.exists():
            continue
        for schema_file in directory.glob("*.oct.md"):
            try:
                schema = load_schema(schema_file)
                schemas.setdefault(schema.name, schema)
            except Exception:
                # Skip files that fail to parse
                pass

    return schemas
