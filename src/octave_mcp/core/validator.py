"""OCTAVE schema validator (P1.5).

Validates AST against schema definitions with:
- Required field checking
- Type validation
- Enum validation (with prefix matching and ambiguity detection)
- Regex pattern validation
- Unknown field detection
- Constraint chain evaluation
- Target routing with audit trail (Issue #103)
- Target validation with registry (Issue #188)
"""

from dataclasses import dataclass
from typing import Any

from octave_mcp.core.ast_nodes import Assignment, ASTNode, Block, Document, InlineMap, ListValue
from octave_mcp.core.constraints import EnumConstraint, RequiredConstraint
from octave_mcp.core.routing import InvalidTargetError, RoutingLog, TargetRegistry, TargetRouter
from octave_mcp.core.schema_extractor import SchemaDefinition


@dataclass
class ValidationError:
    """Validation error with context."""

    code: str
    message: str
    field_path: str = ""
    line: int = 0


class Validator:
    """OCTAVE AST validator."""

    def __init__(self, schema: dict[str, Any] | None = None):
        """Initialize validator with optional schema."""
        self.schema = schema or {}
        self.errors: list[ValidationError] = []
        self.routing_log: RoutingLog = RoutingLog()
        self._target_registry: TargetRegistry | None = None
        self._target_router: TargetRouter | None = None

    def _to_python_value(self, value: Any) -> Any:
        """Convert AST values to Python primitives for constraint evaluation."""
        if isinstance(value, ListValue):
            return [self._to_python_value(item) for item in value.items]
        if isinstance(value, InlineMap):
            return {k: self._to_python_value(v) for k, v in value.pairs.items()}
        return value

    def validate(
        self,
        doc: Document,
        strict: bool = False,
        section_schemas: dict[str, SchemaDefinition] | None = None,
    ) -> list[ValidationError]:
        """Validate document against schema.

        Args:
            doc: Document AST
            strict: If True, reject unknown fields
            section_schemas: Optional dict mapping section names to SchemaDefinition.
                            When provided, sections with matching keys will be validated
                            against their schema's constraints. Sections without a
                            matching entry are skipped (I5: schema sovereignty).

        Returns:
            List of validation errors (empty if valid)
        """
        self.errors = []
        self.routing_log = RoutingLog()  # Reset routing log for each validation

        # Validate META if schema defines it
        if "META" in self.schema and doc.meta:
            self._validate_meta(doc.meta, strict)

        # Validate sections
        for section in doc.sections:
            # Look up schema for this section by key (if section has a key attribute)
            section_schema = None
            if section_schemas is not None:
                section_key = getattr(section, "key", None)
                if section_key is not None:
                    section_schema = section_schemas.get(section_key)
            self._validate_section(section, strict, section_schema)

        return self.errors

    def _validate_meta(self, meta: dict[str, Any], strict: bool) -> None:
        """Validate META block."""
        schema_meta = self.schema.get("META", {})

        # Check required fields
        required = schema_meta.get("required", [])
        for field in required:
            if field not in meta:
                self.errors.append(
                    ValidationError(
                        code="E003",
                        message=f"Cannot auto-fill missing required field '{field}'. Author must provide value.",
                        field_path=f"META.{field}",
                    )
                )

        # Check unknown fields in strict mode
        if strict:
            allowed = schema_meta.get("fields", {}).keys()
            for field in meta.keys():
                if field not in allowed and allowed:
                    self.errors.append(
                        ValidationError(
                            code="E007",
                            message=f"Unknown field '{field}' not allowed in STRICT mode.",
                            field_path=f"META.{field}",
                        )
                    )

        # Type validation
        fields_schema = schema_meta.get("fields", {})
        for field, value in meta.items():
            if field in fields_schema:
                self._validate_type(field, value, fields_schema[field])

    def _validate_section(self, section: ASTNode, strict: bool, section_schema: SchemaDefinition | None = None) -> None:
        """Validate a section against its schema definition.

        Args:
            section: The section AST node to validate
            strict: Whether strict mode is enabled
            section_schema: Optional schema definition for this section.
                           If None, skip content validation (I5: schema-less = UNVALIDATED).

        Validates:
        - Holographic patterns: ["example"∧CONSTRAINT→§TARGET]
        - Constraint chains: REQ∧ENUM[A,B]∧REGEX["^[a-z]+$"]
        - Target routing with audit trail (Issue #103)
        - Target validation with registry (Issue #188)
        """
        # I5: Schema-less sections skip content validation
        if section_schema is None:
            return

        # Only Block nodes have children to validate
        if not isinstance(section, Block):
            return

        # Build map of present fields for REQ constraint checking
        present_fields: dict[str, Any] = {}
        for child in section.children:
            if isinstance(child, Assignment):
                present_fields[child.key] = self._to_python_value(child.value)

        # Get block-level default target (feudal inheritance)
        default_target = getattr(section_schema, "default_target", None)

        # Initialize target registry with custom targets from POLICY.TARGETS (Issue #188)
        registry = TargetRegistry()
        policy_targets = getattr(section_schema, "policy_targets", None)
        if policy_targets:
            for custom_target in policy_targets:
                registry.register_custom(custom_target)

        # Create router for target validation and routing
        router = TargetRouter(registry=registry, routing_log=self.routing_log)

        # Validate each field defined in schema
        for field_name, field_def in section_schema.fields.items():
            # Check if field is present
            value = present_fields.get(field_name)
            field_path = f"{section.key}.{field_name}"
            constraint_passed = True

            # Evaluate constraints if pattern exists
            if field_def.pattern and field_def.pattern.constraints:
                # Check REQ constraint first for missing fields
                has_req = any(isinstance(c, RequiredConstraint) for c in field_def.pattern.constraints.constraints)
                if has_req and value is None:
                    self.errors.append(
                        ValidationError(
                            code="E003",
                            message=f"Field '{field_name}' is required but missing",
                            field_path=field_path,
                        )
                    )
                    continue

                # Skip other validation if field is absent (and not required)
                if value is None:
                    continue

                # Evaluate full constraint chain
                result = field_def.pattern.constraints.evaluate(value=value, path=field_path)
                constraint_passed = result.valid

                # Convert constraint errors to validator errors
                for error in result.errors:
                    self.errors.append(
                        ValidationError(
                            code=error.code,
                            message=error.message,
                            field_path=error.path,
                        )
                    )

            # Target routing with audit trail (Issue #103) and validation (Issue #188)
            # Feudal inheritance: child explicit target overrides parent block target
            if field_def.pattern:
                target = field_def.pattern.target  # Child's explicit target
                if target is None:
                    target = default_target  # Inherit from parent if no explicit

                if target is not None and value is not None:
                    # Route through TargetRouter for validation and multi-target support
                    try:
                        router.route(
                            source_path=field_path,
                            target_spec=target,
                            value=value,
                            constraint_passed=constraint_passed,
                        )
                    except InvalidTargetError as e:
                        # E009: Invalid target error
                        self.errors.append(
                            ValidationError(
                                code="E009",
                                message=f"Invalid target '{e.target_name}': not a builtin, registered custom, or file path target",
                                field_path=field_path,
                            )
                        )

    def _validate_type(self, field: str, value: Any, field_schema: dict[str, Any]) -> None:
        """Validate value type and enum constraints."""
        expected_type = field_schema.get("type")
        if not expected_type:
            return

        # Handle ENUM type with constraint evaluation
        if expected_type == "ENUM":
            enum_values = field_schema.get("values", [])
            constraint = EnumConstraint(allowed_values=enum_values)
            result = constraint.evaluate(value, path=f"META.{field}")

            if not result.valid:
                for error in result.errors:
                    self.errors.append(
                        ValidationError(
                            code=error.code,
                            message=error.message,
                            field_path=error.path,
                        )
                    )
            return

        # Handle standard types
        # I1: Reject booleans for NUMBER type (bool inherits from int in Python)
        if expected_type == "NUMBER":
            if isinstance(value, bool):
                self.errors.append(
                    ValidationError(
                        code="E007",
                        message=f"Field '{field}' expected NUMBER, got {type(value).__name__}",
                        field_path=field,
                    )
                )
                return
            if not isinstance(value, int | float):
                self.errors.append(
                    ValidationError(
                        code="E007",
                        message=f"Field '{field}' expected NUMBER, got {type(value).__name__}",
                        field_path=field,
                    )
                )
            return

        # Handle other types
        type_map: dict[str, type | tuple[type, ...]] = {
            "STRING": str,
            "BOOLEAN": bool,
            "LIST": list,
        }

        expected_python_type = type_map.get(expected_type)
        if expected_python_type and not isinstance(value, expected_python_type):
            self.errors.append(
                ValidationError(
                    code="E007",  # I4: Use E007 for type errors (consistency with constraints.py)
                    message=f"Field '{field}' expected {expected_type}, got {type(value).__name__}",
                    field_path=field,
                )
            )


def validate(
    doc: Document,
    schema: dict[str, Any] | None = None,
    strict: bool = False,
    section_schemas: dict[str, SchemaDefinition] | None = None,
) -> list[ValidationError]:
    """Validate document against schema.

    Args:
        doc: Document AST
        schema: Schema definition (optional)
        strict: Reject unknown fields if True
        section_schemas: Optional dict mapping section names to SchemaDefinition

    Returns:
        List of validation errors
    """
    validator = Validator(schema)
    return validator.validate(doc, strict, section_schemas)
