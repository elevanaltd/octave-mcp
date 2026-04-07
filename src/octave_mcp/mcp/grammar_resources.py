"""MCP resource endpoints for pre-compiled GBNF grammars (Issue #280).

Exposes pre-compiled GBNF grammars as MCP resources so agents can fetch
them at session start without calling octave_compile_grammar each time.

Resources:
- octave://grammars/{SCHEMA_NAME} — pre-compiled GBNF for a named schema

Grammars are compiled on first access and cached in memory for the
lifetime of the server process.
"""

import logging

from mcp.server import Server
from mcp.server.lowlevel.server import ReadResourceContents
from mcp.types import Resource, ResourceTemplate
from pydantic import AnyUrl

from octave_mcp.core.gbnf_compiler import GBNFCompiler
from octave_mcp.schemas.loader import load_builtin_schemas, load_schema_by_name

logger = logging.getLogger(__name__)

# URI scheme and prefix for grammar resources
GRAMMAR_URI_PREFIX = "octave://grammars/"


class GrammarResourceProvider:
    """Provides pre-compiled GBNF grammars as MCP resources.

    Grammars are compiled on first access and cached in memory.
    The provider discovers available schemas from the builtin registry
    and compiles them to GBNF on demand.
    """

    def __init__(self) -> None:
        self._cache: dict[str, str] = {}
        self._available_schemas: dict[str, str] | None = None

    def _discover_schemas(self) -> dict[str, str]:
        """Discover available schemas and return name -> description mapping.

        Returns:
            Dictionary mapping schema names to descriptions.
        """
        if self._available_schemas is not None:
            return self._available_schemas

        schemas = load_builtin_schemas()
        self._available_schemas = {}

        for name, _schema_def in schemas.items():
            desc = (
                f"Pre-compiled GBNF grammar for the {name} schema. "
                f"Use with llama.cpp --grammar flag or similar "
                f"constrained decoding engines."
            )
            self._available_schemas[name] = desc

        return self._available_schemas

    def get_resources(self) -> list[Resource]:
        """List all available grammar resources.

        Returns:
            List of MCP Resource objects for each available schema grammar.
        """
        schemas = self._discover_schemas()
        resources: list[Resource] = []

        for name, description in sorted(schemas.items()):
            uri = f"{GRAMMAR_URI_PREFIX}{name}"
            resources.append(
                Resource(
                    uri=AnyUrl(uri),
                    name=f"grammar/{name}",
                    description=description,
                    mimeType="text/plain",
                )
            )

        return resources

    def get_resource_templates(self) -> list[ResourceTemplate]:
        """List resource templates for dynamic grammar access.

        Returns:
            List with a single template for octave://grammars/{schema_name}.
        """
        return [
            ResourceTemplate(
                uriTemplate=f"{GRAMMAR_URI_PREFIX}{{schema_name}}",
                name="grammar-template",
                description=(
                    "Pre-compiled GBNF grammar for any OCTAVE schema. "
                    "Replace {schema_name} with a valid schema name "
                    "(e.g., META, SKILL)."
                ),
                mimeType="text/plain",
            )
        ]

    def _compile_grammar(self, schema_name: str) -> str:
        """Compile GBNF grammar for a schema, using cache if available.

        Args:
            schema_name: Name of the schema to compile.

        Returns:
            Compiled GBNF grammar string.

        Raises:
            ValueError: If the schema is not found or compilation fails.
        """
        if schema_name in self._cache:
            return self._cache[schema_name]

        schema_def = load_schema_by_name(schema_name)
        if schema_def is None:
            raise ValueError(f"Schema '{schema_name}' not found in builtin registry " f"or search paths")

        compiler = GBNFCompiler()
        grammar = compiler.compile_schema(schema_def, include_envelope=True)

        self._cache[schema_name] = grammar
        logger.info(f"Compiled and cached GBNF grammar for schema '{schema_name}'")
        return grammar

    async def read_resource(self, uri: AnyUrl) -> list[ReadResourceContents]:
        """Read a grammar resource by URI.

        Args:
            uri: The resource URI (e.g., octave://grammars/META).

        Returns:
            List with a single ReadResourceContents containing the grammar.

        Raises:
            ValueError: If the URI is not a grammar URI or schema not found.
        """
        uri_str = str(uri)

        if not uri_str.startswith(GRAMMAR_URI_PREFIX):
            raise ValueError(f"Unsupported resource URI: {uri_str}. " f"Expected prefix: {GRAMMAR_URI_PREFIX}")

        schema_name = uri_str[len(GRAMMAR_URI_PREFIX) :]
        if not schema_name:
            raise ValueError("Schema name is required in URI")

        grammar = self._compile_grammar(schema_name)

        return [
            ReadResourceContents(
                content=grammar,
                mime_type="text/plain",
            )
        ]


def register_grammar_resources(server: Server) -> GrammarResourceProvider:
    """Register grammar resource handlers on the MCP server.

    Args:
        server: The MCP Server instance to register handlers on.

    Returns:
        The GrammarResourceProvider instance (for testing/inspection).
    """
    provider = GrammarResourceProvider()

    @server.list_resources()
    async def handle_list_resources() -> list[Resource]:
        """List available grammar resources."""
        return provider.get_resources()

    @server.list_resource_templates()
    async def handle_list_resource_templates() -> list[ResourceTemplate]:
        """List grammar resource templates."""
        return provider.get_resource_templates()

    @server.read_resource()
    async def handle_read_resource(
        uri: AnyUrl,
    ) -> list[ReadResourceContents]:
        """Read a grammar resource."""
        return await provider.read_resource(uri)

    return provider
