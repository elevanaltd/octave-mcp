"""Schema repository with builtin and custom schema support (P2.5).

Provides centralized schema storage and retrieval.

ADR-0006 SR1-T1 Step 6 (R2 closure)
-----------------------------------
The ``Schema`` container class previously lived at
``octave_mcp.core.schema`` alongside a thin delegator ``validate()``
function. ``core/schema.py`` has been deleted in Step 6 (design §2.2);
the ``Schema`` container has been relocated here, co-located with its
sole consumer (``SchemaRepository``). The ``validate()`` delegator was
removed entirely — callers must use the class-based ``Validator``
surface from ``octave_mcp.core.validator``.

See ``docs/adr/adr-0006-sr1-t1-grammar-core-design.md`` §3 row 6, §2.2.
"""


class Schema:
    """OCTAVE schema definition (container).

    A lightweight container used by :class:`SchemaRepository` to register
    and retrieve named schemas. Validation is performed by
    :class:`octave_mcp.core.validator.Validator`, which accepts the
    schema as a dict (see :attr:`Schema._data`).
    """

    def __init__(self, name: str, version: str, fields: dict, schema_data: dict | None = None):
        """Initialize schema from parsed data.

        Args:
            name: Schema name
            version: Schema version
            fields: Schema field definitions
            schema_data: Optional parsed schema structure
        """
        self.name = name
        self.version = version
        self.fields = fields
        self._data = schema_data or {}


class SchemaRepository:
    """Repository for OCTAVE schemas."""

    def __init__(self):
        """Initialize schema repository."""
        self._schemas: dict[str, Schema] = {}
        # Future: Load builtin schemas from package
        # self._load_builtin_schemas()

    def _load_builtin_schemas(self):
        """Load builtin schemas from package.

        DEFERRED: Builtin schema loading requires holographic pattern parser.
        See docs/implementation-roadmap.md Gap 1 (Holographic Pattern Parsing).
        Estimated: 1-2 days, Phase 1 foundational work

        Once Gap 1 is complete, this will:
        - Load schemas from src/octave_mcp/schemas/builtin/*.oct.md
        - Parse holographic patterns: KEY::["example"∧CONSTRAINT→§TARGET]
        - Register builtin schemas (META, SESSION_LOG, etc.)
        - Enable schema-driven validation

        Current status: No builtin schemas can be parsed without holographic parser
        """
        # Will load from src/octave_mcp/schemas/builtin/ once Gap 1 complete
        pass

    def register(self, name: str, schema: Schema | None):
        """Register custom schema.

        Args:
            name: Schema name
            schema: Schema object (can be None for stub)
        """
        self._schemas[name] = schema  # type: ignore

    def get(self, name: str) -> Schema | None:
        """Retrieve schema by name.

        Args:
            name: Schema name

        Returns:
            Schema object or None if not found
        """
        return self._schemas.get(name)

    def list_schemas(self) -> list[str]:
        """List all available schema names.

        Returns:
            List of schema names
        """
        return list(self._schemas.keys())
