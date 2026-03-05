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
- Policy enforcement (Issue #190): UNKNOWN_FIELDS policy, custom targets
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from octave_mcp.core.ast_nodes import (
    Assignment,
    ASTNode,
    Block,
    Document,
    InlineMap,
    ListValue,
    LiteralZoneValue,
    Section,
)
from octave_mcp.core.constraints import EnumConstraint, RequiredConstraint
from octave_mcp.core.routing import InvalidTargetError, RoutingLog, TargetRegistry, TargetRouter
from octave_mcp.core.schema_extractor import (
    InheritanceResolver,
    SchemaDefinition,
    extract_block_targets,
)


class UnknownFieldPolicy(Enum):
    """Policy for handling unknown fields during validation.

    Issue #190: Spec §5::POLICY_BLOCK defines UNKNOWN_FIELDS::REJECT∨IGNORE∨WARN

    Attributes:
        REJECT: Error on unknown fields (E007)
        IGNORE: Skip unknown fields silently
        WARN: Add warning but don't fail (W001)
    """

    REJECT = "REJECT"
    IGNORE = "IGNORE"
    WARN = "WARN"


@dataclass
class ValidationError:
    """Validation error with context.

    Attributes:
        code: Error/warning code (E007, W001, etc.)
        message: Human-readable description
        field_path: Dot-separated path to field (e.g., "SECTION.FIELD")
        line: Line number in source (0 if unknown)
        severity: "error" or "warning" (default: "error")
    """

    code: str
    message: str
    field_path: str = ""
    line: int = 0
    severity: str = field(default="error")


class Validator:
    """OCTAVE AST validator."""

    def __init__(self, schema: dict[str, Any] | None = None):
        """Initialize validator with optional schema."""
        self.schema = schema or {}
        self.errors: list[ValidationError] = []
        self.routing_log: RoutingLog = RoutingLog()
        self._target_registry: TargetRegistry | None = None
        self._target_router: TargetRouter | None = None
        # Block inheritance support (Issue #189, M3 CE violations)
        self._block_targets: dict[str, str] = {}
        self._inheritance_resolver: InheritanceResolver = InheritanceResolver()

    def _to_python_value(self, value: Any) -> Any:
        """Convert AST values to Python primitives for constraint evaluation.

        LiteralZoneValue is returned as-is: TYPE[LITERAL] and LANG[] constraints
        operate directly on the object (Issue #235 T12).
        """
        if isinstance(value, ListValue):
            return [self._to_python_value(item) for item in value.items]
        if isinstance(value, InlineMap):
            return {k: self._to_python_value(v) for k, v in value.pairs.items()}
        if isinstance(value, LiteralZoneValue):
            # Literal zones remain as-is for constraint evaluation.
            # TYPE[LITERAL] and LANG[] constraints operate on the object directly.
            # D4: content is opaque; no conversion or normalization applied.
            return value
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

        # Extract block-level targets from document AST (Issue #189, M3 CE violations)
        # This enables feudal inheritance: children inherit parent block targets
        self._block_targets = extract_block_targets(doc)

        # Validate META if schema defines it
        if "META" in self.schema and doc.meta:
            self._validate_meta(doc.meta, strict)

        # Loss accounting warnings fire on document content, not schema presence.
        # PR#315 fix: moved outside the "META" in self.schema guard so that
        # W_META_001/W_META_002 fire regardless of whether a schema is provided.
        if doc.meta:
            self._check_meta_warnings(doc.meta)

        # Validate sections
        # Issue #325: Walk document tree recursively so nested blocks (e.g., NATURE:
        # inside §1::COGNITIVE_IDENTITY) are also validated against section_schemas.
        self._validate_sections_recursive(doc.sections, strict, section_schemas)

        # Issue #244: Validate Zone 2 (YAML frontmatter) when schema defines frontmatter
        # This is opt-in: only schemas with frontmatter defs trigger validation.
        # I1: Read-only inspection, never alters Zone 2 content.
        if section_schemas is not None:
            for schema_def in section_schemas.values():
                if schema_def.frontmatter:
                    fm_errors = validate_frontmatter(doc.raw_frontmatter, schema_def)
                    self.errors.extend(fm_errors)

        # ADR-0283: Chassis-profile validation for AGENT_DEFINITION documents.
        # Runs after all other validation passes. Documents without
        # §3::CAPABILITIES or using flat SKILLS::[]/PATTERNS::[] skip
        # automatically (backward compatible).
        chassis_errors = validate_chassis_profiles(doc)
        self.errors.extend(chassis_errors)

        return self.errors

    def _validate_meta(self, meta: dict[str, Any], strict: bool) -> None:
        """Validate META block."""
        schema_meta = self.schema.get("META", {})

        # Check required fields
        required = schema_meta.get("required", [])
        for field_name in required:
            if field_name not in meta:
                self.errors.append(
                    ValidationError(
                        code="E003",
                        message=f"Cannot auto-fill missing required field '{field_name}'. Author must provide value.",
                        field_path=f"META.{field_name}",
                    )
                )

        # Check unknown fields in strict mode
        if strict:
            allowed = schema_meta.get("fields", {}).keys()
            for field_name in meta.keys():
                if field_name not in allowed and allowed:
                    self.errors.append(
                        ValidationError(
                            code="E007",
                            message=f"Unknown field '{field_name}' not allowed in STRICT mode.",
                            field_path=f"META.{field_name}",
                        )
                    )

        # Type validation
        fields_schema = schema_meta.get("fields", {})
        for field_name, value in meta.items():
            if field_name in fields_schema:
                self._validate_type(field_name, value, fields_schema[field_name])

    def _check_meta_warnings(self, meta: dict[str, Any]) -> None:
        """Emit loss accounting consistency warnings based on META content.

        PR#315 fix: These warnings are based on document content, not schema
        presence.  Runs unconditionally when doc.meta exists.

        I4 (Transform Auditability): COMPRESSION_TIER without LOSS_PROFILE
        means loss accounting is incomplete.
        """
        compression_tier = meta.get("COMPRESSION_TIER")
        loss_profile = meta.get("LOSS_PROFILE")

        if compression_tier and not loss_profile:
            self.errors.append(
                ValidationError(
                    code="W_META_001",
                    message="COMPRESSION_TIER declared but LOSS_PROFILE absent — loss accounting incomplete",
                    field_path="META.LOSS_PROFILE",
                    severity="warning",
                )
            )

        if (
            loss_profile is not None
            and str(loss_profile).lower() == "none"
            and compression_tier
            and str(compression_tier).upper() != "LOSSLESS"
        ):
            self.errors.append(
                ValidationError(
                    code="W_META_002",
                    message=(
                        f"LOSS_PROFILE is 'none' but COMPRESSION_TIER is " f"{compression_tier} — verify accuracy"
                    ),
                    field_path="META.LOSS_PROFILE",
                    severity="warning",
                )
            )

    def _validate_unknown_fields(
        self,
        document_fields: set[str],
        schema_fields: set[str],
        policy: UnknownFieldPolicy,
        section_key: str,
    ) -> list[ValidationError]:
        """Check for unknown fields per UNKNOWN_FIELDS policy.

        Issue #190: Implements §5::POLICY_BLOCK UNKNOWN_FIELDS enforcement.

        Args:
            document_fields: Set of field names present in the document section
            schema_fields: Set of field names defined in the schema
            policy: How to handle unknown fields (REJECT, WARN, or IGNORE)
            section_key: Section name for error path construction

        Returns:
            List of ValidationErrors (errors for REJECT, warnings for WARN, empty for IGNORE)
        """
        unknown = document_fields - schema_fields
        if not unknown:
            return []

        errors: list[ValidationError] = []

        if policy == UnknownFieldPolicy.REJECT:
            for field_name in sorted(unknown):  # Sort for deterministic output
                errors.append(
                    ValidationError(
                        code="E007",
                        message=f"Unknown field '{field_name}' not allowed per UNKNOWN_FIELDS::REJECT policy",
                        field_path=f"{section_key}.{field_name}",
                        severity="error",
                    )
                )
        elif policy == UnknownFieldPolicy.WARN:
            for field_name in sorted(unknown):
                errors.append(
                    ValidationError(
                        code="W001",
                        message=f"Unknown field '{field_name}' (UNKNOWN_FIELDS::WARN policy)",
                        field_path=f"{section_key}.{field_name}",
                        severity="warning",
                    )
                )
        # IGNORE: return empty list (no errors/warnings)

        return errors

    def _validate_sections_recursive(
        self,
        nodes: list[ASTNode],
        strict: bool,
        section_schemas: dict[str, SchemaDefinition] | None,
    ) -> None:
        """Walk document tree and validate each section/block against section_schemas.

        Issue #325: For document-type schemas (e.g., COGNITION_DEFINITION), fields
        may be nested inside sections and sub-blocks. This method recursively walks
        the AST so that nested blocks (e.g., NATURE: inside §1::COGNITIVE_IDENTITY)
        are also matched against section_schemas and validated.

        Args:
            nodes: List of AST nodes to walk
            strict: Whether strict mode is enabled
            section_schemas: Optional dict mapping section/block names to SchemaDefinition
        """
        for node in nodes:
            # Look up schema for this node by key
            section_schema = None
            if section_schemas is not None:
                section_key = getattr(node, "key", None)
                if section_key is not None:
                    section_schema = section_schemas.get(section_key)
            self._validate_section(node, strict, section_schema)

            # Recurse into children if section_schemas is provided and node has children
            if section_schemas is not None:
                children = getattr(node, "children", None)
                if children:
                    self._validate_sections_recursive(children, strict, section_schemas)

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
        - Unknown fields per UNKNOWN_FIELDS policy (Issue #190)
        """
        # I5: Schema-less sections skip content validation
        if section_schema is None:
            return

        # Only Block and Section nodes have children to validate
        # Issue #325: Section nodes (§N::NAME) also need validation for
        # document-type schemas like COGNITION_DEFINITION where fields are
        # inside numbered sections, not at the envelope level.
        if not isinstance(section, Block | Section):
            return

        # Build map of present fields for REQ constraint checking
        present_fields: dict[str, Any] = {}
        for child in section.children:
            if isinstance(child, Assignment):
                present_fields[child.key] = self._to_python_value(child.value)

        # Issue #190: UNKNOWN_FIELDS policy enforcement
        # Parse policy from schema, defaulting to REJECT
        policy_str = section_schema.policy.unknown_fields if section_schema.policy else "REJECT"
        try:
            unknown_policy = UnknownFieldPolicy(policy_str)
        except ValueError:
            # Invalid policy value, default to REJECT (fail-safe)
            unknown_policy = UnknownFieldPolicy.REJECT

        # Check for unknown fields
        document_fields = set(present_fields.keys())
        schema_fields = set(section_schema.fields.keys())
        unknown_errors = self._validate_unknown_fields(document_fields, schema_fields, unknown_policy, section.key)
        self.errors.extend(unknown_errors)

        # Get block-level default target (feudal inheritance)
        default_target = getattr(section_schema, "default_target", None)

        # Initialize target registry with custom targets from POLICY.TARGETS (Issue #190)
        registry = TargetRegistry()
        # Get custom targets from policy
        policy_targets = section_schema.policy.targets if section_schema.policy else []
        for custom_target in policy_targets:
            registry.register_custom(custom_target)

        # Register default_target as custom if not already a builtin (M3 fix)
        # This ensures policy default targets are valid routing destinations
        if default_target and default_target not in registry.BUILTINS:
            registry.register_custom(default_target)

        # Register block-level targets as custom targets (M3 fix for CE violation #1)
        # Block targets from [->TARGET] syntax are implicitly valid routing destinations
        for block_target in self._block_targets.values():
            if block_target not in registry.BUILTINS:
                registry.register_custom(block_target)

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
            # Feudal inheritance hierarchy (closest wins):
            # 1. Field explicit target (highest priority)
            # 2. Block-level target [->TARGET] from AST (Issue #189, M3 CE violations)
            # 3. POLICY.DEFAULT_TARGET (lowest priority)
            if field_def.pattern:
                target: str | None = field_def.pattern.target  # Field's explicit target
                if target is None:
                    # Try block inheritance: resolve from block hierarchy
                    field_path_parts = field_path.split(".")
                    inherited_target = self._inheritance_resolver.resolve_target(field_path_parts, self._block_targets)
                    # Use inherited target if found, otherwise fall back to policy default
                    target = inherited_target if inherited_target is not None else default_target

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


def validate_frontmatter(
    raw_frontmatter: str | None,
    schema: SchemaDefinition,
) -> list[ValidationError]:
    """Validate YAML frontmatter against schema frontmatter definitions (Issue #244).

    Extends I5 Schema Sovereignty to Zone 2 (YAML frontmatter). This function
    is opt-in: it only validates when the schema defines frontmatter requirements.

    I1 compliance: This is read-only inspection. Zone 2 content is never altered.
    I5 compliance: If we can't validate, we say so (E_FM_PARSE for bad YAML).

    Args:
        raw_frontmatter: Raw YAML frontmatter string from Document.raw_frontmatter.
                         May be None if no frontmatter is present.
        schema: SchemaDefinition that may contain frontmatter field definitions.

    Returns:
        List of ValidationError. Empty if no frontmatter requirements in schema
        or if all requirements are satisfied.
    """
    # No frontmatter definitions in schema = nothing to validate (opt-in)
    if not schema.frontmatter:
        return []

    errors: list[ValidationError] = []

    # If frontmatter is absent but schema requires fields, report each required field
    if raw_frontmatter is None:
        for field_name, field_def in schema.frontmatter.items():
            if field_def.required:
                errors.append(
                    ValidationError(
                        code="E_FM_REQUIRED",
                        message=f"Required frontmatter field '{field_name}' is missing",
                        field_path=f"frontmatter.{field_name}",
                    )
                )
        return errors

    # Parse YAML frontmatter
    import yaml

    try:
        parsed = yaml.safe_load(raw_frontmatter)
    except yaml.YAMLError as e:
        errors.append(
            ValidationError(
                code="E_FM_PARSE",
                message=f"Failed to parse YAML frontmatter: {e}",
                field_path="frontmatter",
            )
        )
        return errors

    # Handle case where YAML parses to non-dict (e.g., scalar string)
    if not isinstance(parsed, dict):
        parsed = {}

    # Validate each defined frontmatter field
    for field_name, field_def in schema.frontmatter.items():
        value = parsed.get(field_name)

        # Check required fields
        if field_def.required and value is None:
            errors.append(
                ValidationError(
                    code="E_FM_REQUIRED",
                    message=f"Required frontmatter field '{field_name}' is missing",
                    field_path=f"frontmatter.{field_name}",
                )
            )
            continue

        # Skip type validation for absent optional fields
        if value is None:
            continue

        # Type validation
        type_map: dict[str, type | tuple[type, ...]] = {
            "STRING": str,
            "LIST": list,
            "BOOLEAN": bool,
        }
        expected_type = type_map.get(field_def.field_type)
        if expected_type and not isinstance(value, expected_type):
            errors.append(
                ValidationError(
                    code="E_FM_TYPE",
                    message=(
                        f"Frontmatter field '{field_name}' expected {field_def.field_type}, "
                        f"got {type(value).__name__}"
                    ),
                    field_path=f"frontmatter.{field_name}",
                )
            )

    return errors


def validate_chassis_profiles(doc: Document) -> list[ValidationError]:
    """Validate chassis-profile structure in §3::CAPABILITIES (ADR-0283).

    Static validation of the CHASSIS/PROFILES capability tiering structure.
    Documents without §3::CAPABILITIES or using flat SKILLS::[]/PATTERNS::[]
    skip validation (backward compatible).

    Overlap rules from ADR-0283:
    - CHASSIS skill in profile skills → E_CHASSIS_OVERLAP (redundant)
    - CHASSIS skill in profile kernel_only → E_CHASSIS_OVERLAP (contradictory)
    - default mixed with context:: in match → E_CHASSIS_DEFAULT_MIXED
    - Duplicate profile names → E_CHASSIS_DUPLICATE_PROFILE
    - 4+ profiles → W_CHASSIS_PROFILE_COUNT (warning)

    Args:
        doc: Parsed Document AST

    Returns:
        List of ValidationError (empty if valid or not applicable)
    """
    errors: list[ValidationError] = []

    # Find §3::CAPABILITIES section
    capabilities = _find_capabilities_section(doc)
    if capabilities is None:
        return errors

    # Detect format: look for CHASSIS or PROFILES children
    chassis_node = None
    profiles_node = None
    for child in capabilities.children:
        if isinstance(child, Assignment) and child.key == "CHASSIS":
            chassis_node = child
        elif isinstance(child, Block) and child.key == "PROFILES":
            profiles_node = child

    # If neither CHASSIS nor PROFILES exist, this is flat format (v7) → skip
    if chassis_node is None and profiles_node is None:
        return errors

    # Extract CHASSIS skill names
    chassis_skills: set[str] = set()
    if chassis_node is not None and isinstance(chassis_node.value, ListValue):
        for item in chassis_node.value.items:
            if isinstance(item, str):
                chassis_skills.add(item)

    # Validate PROFILES if present
    if profiles_node is not None:
        seen_names: set[str] = set()
        profile_count = 0

        for child in profiles_node.children:
            if not isinstance(child, Block):
                continue

            profile_name = child.key
            profile_count += 1

            # Check duplicate profile names
            if profile_name in seen_names:
                errors.append(
                    ValidationError(
                        code="E_CHASSIS_DUPLICATE_PROFILE",
                        message=f"Duplicate profile name '{profile_name}' in PROFILES",
                        field_path=f"CAPABILITIES.PROFILES.{profile_name}",
                        severity="error",
                    )
                )
            seen_names.add(profile_name)

            # Extract profile fields
            profile_skills: set[str] = set()
            profile_kernel_only: set[str] = set()
            match_items: list[Any] = []
            has_match = False
            has_skills = False

            for field_node in child.children:
                if not isinstance(field_node, Assignment):
                    continue
                if field_node.key == "skills" and isinstance(field_node.value, ListValue):
                    has_skills = True
                    for item in field_node.value.items:
                        if isinstance(item, str):
                            profile_skills.add(item)
                elif field_node.key == "kernel_only" and isinstance(field_node.value, ListValue):
                    for item in field_node.value.items:
                        if isinstance(item, str):
                            profile_kernel_only.add(item)
                elif field_node.key == "match" and isinstance(field_node.value, ListValue):
                    has_match = True
                    match_items = list(field_node.value.items)

            # Check required fields (ADR-0283: match and skills are mandatory)
            if not has_match:
                errors.append(
                    ValidationError(
                        code="E_CHASSIS_MISSING_FIELD",
                        message=f"Profile '{profile_name}' is missing required field 'match'",
                        field_path=f"CAPABILITIES.PROFILES.{profile_name}.match",
                        severity="error",
                    )
                )
            if not has_skills:
                errors.append(
                    ValidationError(
                        code="E_CHASSIS_MISSING_FIELD",
                        message=f"Profile '{profile_name}' is missing required field 'skills'",
                        field_path=f"CAPABILITIES.PROFILES.{profile_name}.skills",
                        severity="error",
                    )
                )

            # Check CHASSIS overlap with profile skills
            for skill in sorted(profile_skills & chassis_skills):
                errors.append(
                    ValidationError(
                        code="E_CHASSIS_OVERLAP",
                        message=(f"CHASSIS skill '{skill}' redundantly listed " f"in profile '{profile_name}' skills"),
                        field_path=f"CAPABILITIES.PROFILES.{profile_name}.skills",
                        severity="error",
                    )
                )

            # Check CHASSIS overlap with profile kernel_only
            for skill in sorted(profile_kernel_only & chassis_skills):
                errors.append(
                    ValidationError(
                        code="E_CHASSIS_OVERLAP",
                        message=(f"CHASSIS skill '{skill}' contradicts " f"kernel_only in profile '{profile_name}'"),
                        field_path=f"CAPABILITIES.PROFILES.{profile_name}.kernel_only",
                        severity="error",
                    )
                )

            # Check default mixed with other conditions in match
            has_default = any(item == "default" for item in match_items if isinstance(item, str))
            has_other = len(match_items) > 1
            if has_default and has_other:
                errors.append(
                    ValidationError(
                        code="E_CHASSIS_DEFAULT_MIXED",
                        message=(
                            f"'default' cannot be mixed with other conditions " f"in profile '{profile_name}' match"
                        ),
                        field_path=f"CAPABILITIES.PROFILES.{profile_name}.match",
                        severity="error",
                    )
                )

        # Warn at 4+ profiles
        if profile_count >= 4:
            errors.append(
                ValidationError(
                    code="W_CHASSIS_PROFILE_COUNT",
                    message=f"Agent has {profile_count} profiles; consider if all are necessary",
                    field_path="CAPABILITIES.PROFILES",
                    severity="warning",
                )
            )

    return errors


def _find_capabilities_section(doc: Document) -> Section | Block | None:
    """Find §3::CAPABILITIES or CAPABILITIES section/block in document."""
    for node in doc.sections:
        if isinstance(node, Section) and node.key == "CAPABILITIES":
            return node
        if isinstance(node, Block) and node.key == "CAPABILITIES":
            return node
    return None


def _count_literal_zones(doc: Document) -> list[dict[str, Any]]:
    """Return per-zone metadata for all LiteralZoneValue instances in a Document.

    Issue #235 T12: Shared utility used by the validator and MCP tools (T13, T14).

    Returns per-zone metadata rather than a plain count so that MCP tools can
    populate ``zone_report.literal.zones`` with key/info_tag/line entries.

    D4: Content is opaque -- only envelope metadata (key, info_tag, line) is
    reported.  I5: Caller is responsible for setting ``literal_zones_validated=False``.

    **Line semantics**: The ``line`` field records the source line of the
    *assignment* (the ``KEY::`` line), not the line of the opening fence
    marker (the ` ``` ` line).  ``LiteralZoneValue`` does not store its own
    source position; only the containing ``Assignment`` node carries a line
    number (inherited from ``ASTNode.line``).  The fence opening always
    appears on ``assignment.line + 1`` in well-formed OCTAVE documents, but
    this function does not compute that offset -- it exposes the assignment
    line directly.  Consumers that need the fence line should add 1 to the
    reported ``line`` value.

    Args:
        doc: Parsed Document AST to inspect.

    Returns:
        List of dicts, each with keys:
          - "key":      Assignment key (str)
          - "info_tag": Language tag from fence opener, or None
          - "line":     Source line number of the *assignment* node (the
                        ``KEY::`` line), NOT the fence opening line.

        Returns an empty list when no literal zones are present.
    """
    zones: list[dict[str, Any]] = []

    def _collect_from_value(key: str, value: Any, line: int) -> None:
        """Recursively collect LiteralZoneValue instances from a value.

        Descends into ListValue.items and InlineMap.pairs so that literal
        zones nested inside list or map assignments are not silently missed
        (Fix for CE review finding: T13/T14 zone_report metadata correctness).

        Args:
            key:   Assignment key (used as the zone key in the report entry).
            value: The assignment value to inspect (may be any AST value type).
            line:  Source line of the containing assignment.
        """
        if isinstance(value, LiteralZoneValue):
            zones.append(
                {
                    "key": key,
                    "info_tag": value.info_tag,
                    "line": line,
                }
            )
        elif isinstance(value, ListValue):
            for item in value.items:
                _collect_from_value(key, item, line)
        elif isinstance(value, InlineMap):
            for v in value.pairs.values():
                _collect_from_value(key, v, line)

    def _traverse(nodes: list[ASTNode]) -> None:
        for node in nodes:
            if isinstance(node, Assignment):
                _collect_from_value(node.key, node.value, node.line)
            elif isinstance(node, Block):
                _traverse(node.children)
            elif hasattr(node, "children"):
                # Handles Section nodes and any future container nodes.
                _traverse(node.children)

    _traverse(doc.sections)
    return zones
