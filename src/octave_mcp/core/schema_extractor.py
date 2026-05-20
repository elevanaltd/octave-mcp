"""OCTAVE schema extraction from documents (Issue #93).

Extracts schema definitions (POLICY, FIELDS, FRONTMATTER blocks) from parsed
OCTAVE documents using holographic pattern parsing.

This module provides:
- SchemaDefinition: Complete schema definition with policy, fields, and frontmatter
- FieldDefinition: Single field definition with holographic pattern
- FrontmatterFieldDef: Frontmatter field definition for Zone 2 validation (Issue #244)
- PolicyDefinition: POLICY block configuration
- InheritanceResolver: Block target inheritance resolution (Issue #189)
- DepthLimitError: Raised when inheritance depth exceeds MAX_DEPTH
- extract_schema_from_document(): Extract schema from parsed Document
- extract_block_targets(): Extract block-level targets from document AST
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from octave_mcp.core.constraints import RequiredConstraint
from octave_mcp.core.grammar.cst import Assignment, ASTNode, Block, Document, HolographicValue, Section
from octave_mcp.core.holographic import (
    HolographicPattern,
    HolographicPatternError,
    parse_holographic_pattern,
)
from octave_mcp.core.lexer import TokenType


class DepthLimitError(Exception):
    """Raised when inheritance depth exceeds MAX_DEPTH (100).

    Issue #189: Block inheritance depth limit per spec section 4::BLOCK_INHERITANCE.
    DEPTH::unbounded_semantic[implementation_caps_at_100]
    """

    pass


class InheritanceResolver:
    """Resolves block-level target inheritance.

    Issue #189: Implements block inheritance per spec section 4::BLOCK_INHERITANCE.

    Children inherit parent block's target unless they specify their own.
    Resolution walks from child to root, returning first target found.
    Depth is capped at MAX_DEPTH (100) per spec.

    Example:
        RISKS[->RISK_LOG]:
          CRITICAL::["auth_bypass"∧REQ]     // inherits ->RISK_LOG
          WARNING::["rate_limit"∧OPT->SELF] // overrides to SELF
    """

    MAX_DEPTH = 100

    def resolve_target(self, path: list[str], block_targets: dict[str, str]) -> str | None:
        """Walk from child to ancestors, return first target found.

        Args:
            path: Path components from root to current node, e.g., ["RISKS", "CRITICAL"]
            block_targets: Mapping of block paths to their targets, e.g., {"RISKS": "RISK_LOG"}

        Returns:
            The inherited target, or None if no ancestor has a target.

        Raises:
            DepthLimitError: If path depth exceeds MAX_DEPTH (100).
        """
        for depth, prefix in enumerate(self._ancestors(path)):
            if depth >= self.MAX_DEPTH:
                raise DepthLimitError(
                    f"Inheritance depth exceeds {self.MAX_DEPTH}. " f"Path: {'.'.join(path[:self.MAX_DEPTH])}..."
                )
            if prefix in block_targets:
                return block_targets[prefix]
        return None

    def resolve_target_with_audit(
        self, path: list[str], block_targets: dict[str, str]
    ) -> tuple[str | None, dict[str, Any] | None]:
        """Resolve target with I4 audit trail.

        Args:
            path: Path components from root to current node.
            block_targets: Mapping of block paths to their targets.

        Returns:
            Tuple of (target, audit_info).
            audit_info contains inherited_from, target, and field_path when target is found.
        """
        for depth, prefix in enumerate(self._ancestors(path)):
            if depth >= self.MAX_DEPTH:
                raise DepthLimitError(
                    f"Inheritance depth exceeds {self.MAX_DEPTH}. " f"Path: {'.'.join(path[:self.MAX_DEPTH])}..."
                )
            if prefix in block_targets:
                target = block_targets[prefix]
                audit = {
                    "inherited_from": prefix,
                    "target": target,
                    "field_path": ".".join(path),
                }
                return target, audit
        return None, None

    def _ancestors(self, path: list[str]) -> Iterator[str]:
        """Yield ancestor paths from child to root.

        Args:
            path: Path components, e.g., ["A", "B", "C"]

        Yields:
            Ancestor paths: "A.B.C", "A.B", "A"
        """
        for i in range(len(path), 0, -1):
            yield ".".join(path[:i])


def extract_block_targets(doc: Document) -> dict[str, str]:
    """Extract all block-level targets from document AST.

    Issue #189: Builds a mapping of block paths to their target annotations.

    Args:
        doc: Parsed Document AST

    Returns:
        Dictionary mapping block paths to targets.
        Example: {"RISKS": "RISK_LOG", "OUTER.INNER": "INNER_TARGET"}
    """
    targets: dict[str, str] = {}
    _extract_targets_recursive(doc.sections, [], targets)
    return targets


def _extract_targets_recursive(nodes: list[ASTNode], path: list[str], targets: dict[str, str]) -> None:
    """Recursively extract block targets from AST nodes.

    Args:
        nodes: List of AST nodes to process
        path: Current path prefix (list of ancestor keys)
        targets: Output dictionary to populate
    """
    for node in nodes:
        if isinstance(node, Block):
            current_path = path + [node.key]
            path_str = ".".join(current_path)

            # Capture block's target if present
            if node.target is not None:
                targets[path_str] = node.target

            # Recurse into children
            _extract_targets_recursive(node.children, current_path, targets)

        elif isinstance(node, Section):
            # Sections can also contain nested blocks
            current_path = path + [node.key]
            _extract_targets_recursive(node.children, current_path, targets)


@dataclass
class SchemaExtractionWarning:
    """Warning generated during schema extraction (M3 CE violation #3).

    Per lenient parsing philosophy: warn but don't block.
    Malformed holographic patterns produce warnings, not errors.

    Attributes:
        code: Warning code (W002 for malformed patterns)
        message: Human-readable description
        field_path: Path to the field (e.g., "FIELDS.FIELD_NAME")
        severity: Always "warning"
    """

    code: str
    message: str
    field_path: str = ""
    severity: str = field(default="warning")


@dataclass
class PolicyDefinition:
    """POLICY block configuration for schema.

    Attributes:
        version: Schema version from POLICY block
        unknown_fields: How to handle unknown fields (REJECT|IGNORE|WARN)
        targets: List of valid extraction targets (without section markers)
        required_section_ids: Section ids (e.g. "1", "2b") whose presence
            the validator MUST surface (GH-428). Absence emits
            W_MISSING_REQUIRED_SECTION. Empty list disables the check.
        section_conditional_required: Map of section key -> list of field
            names that MUST appear inside that section IF the section is
            present in the document (GH-428). The check is conditional:
            documents without the section are unaffected. Missing field
            members emit W_INCOMPLETE_SECTION_FIELDS naming the gaps.
        section_allows_empty: Set of section keys for which a present-but-empty
            section (zero Assignment children) is semantically valid and
            should NOT surface W_INCOMPLETE_SECTION_FIELDS (GH-426, cubic P2
            fix on PR #446). Default is the empty set — every schema's
            SECTION_CONDITIONAL_REQUIRED enforcement stays strict unless the
            schema explicitly opts a section in via
            POLICY.SECTION_ALLOWS_EMPTY::["SECTION_KEY", ...]. CRS_REVIEW
            opts in for FINDINGS (an APPROVED review with TOTAL::0
            legitimately authors an empty §3); SKILL does NOT opt in for
            ANCHOR_KERNEL (an empty kernel block is malformed by intent).
    """

    version: str = "1.0"
    unknown_fields: str = "REJECT"
    targets: list[str] = field(default_factory=list)
    required_section_ids: list[str] = field(default_factory=list)
    section_conditional_required: dict[str, list[str]] = field(default_factory=dict)
    section_allows_empty: set[str] = field(default_factory=set)


@dataclass
class FrontmatterFieldDef:
    """Frontmatter field definition for Zone 2 validation (Issue #244).

    Describes a single field expected in YAML frontmatter.
    Used by schemas that extend I5 Schema Sovereignty to Zone 2.

    Attributes:
        name: Field name as it appears in YAML frontmatter (e.g., "allowed-tools")
        required: Whether this field must be present
        field_type: Expected YAML type: STRING, LIST, or BOOLEAN
    """

    name: str
    required: bool = False
    field_type: str = "STRING"


@dataclass
class FieldDefinition:
    """Single field definition extracted from FIELDS block.

    Attributes:
        name: Field name (key)
        pattern: Parsed HolographicPattern, or None if parsing failed
        raw_value: Original raw value string for debugging
    """

    name: str
    pattern: HolographicPattern | None
    raw_value: str | None = None

    @property
    def is_required(self) -> bool:
        """Check if field is required (has REQ constraint)."""
        if not self.pattern or not self.pattern.constraints:
            return False
        return any(isinstance(c, RequiredConstraint) for c in self.pattern.constraints.constraints)


@dataclass
class SchemaDefinition:
    """Complete schema definition extracted from OCTAVE document.

    Attributes:
        name: Schema name (from document envelope)
        version: Schema version (from META block)
        policy: POLICY block configuration
        fields: Dictionary of field name -> FieldDefinition
        frontmatter: Dictionary of frontmatter field name -> FrontmatterFieldDef (Issue #244)
        default_target: Block-level default target for feudal inheritance (Issue #103)
        warnings: List of warnings generated during extraction (M3 CE violation #3)
    """

    name: str
    version: str | None = None
    policy: PolicyDefinition = field(default_factory=PolicyDefinition)
    fields: dict[str, FieldDefinition] = field(default_factory=dict)
    frontmatter: dict[str, FrontmatterFieldDef] = field(default_factory=dict)
    default_target: str | None = None
    warnings: list[SchemaExtractionWarning] = field(default_factory=list)
    # GH-427: Per-item sub-schema for repeated structures. The DEBATE_TRANSCRIPT
    # schema declares ``TURN_SCHEMA:`` describing the structure each TURN must
    # satisfy. When populated the validator enforces that each child block of
    # the matching repeated-structure parent (TURNS) conforms to this sub-schema.
    # ``None`` means the schema does not declare a TURN_SCHEMA block.
    turn_schema: dict[str, FieldDefinition] | None = None


def _extract_policy(
    sections: list[Any],
) -> tuple[PolicyDefinition, str | None, list[SchemaExtractionWarning]]:
    """Extract POLICY block from document sections.

    Args:
        sections: List of document sections (Assignment, Block, Section)

    Returns:
        Tuple of (PolicyDefinition, default_target, warnings).
        default_target is extracted from POLICY.DEFAULT_TARGET for feudal inheritance.
        warnings carries ``W_MALFORMED_POLICY`` diagnostics for shape errors
        per PROD::I4 TRANSFORM_AUDITABILITY — every transformation logged.
    """
    policy = PolicyDefinition()
    default_target: str | None = None
    warnings: list[SchemaExtractionWarning] = []

    for section in sections:
        if isinstance(section, Block) and section.key == "POLICY":
            for child in section.children:
                if isinstance(child, Assignment):
                    if child.key == "VERSION":
                        policy.version = str(child.value).strip('"')
                    elif child.key == "UNKNOWN_FIELDS":
                        policy.unknown_fields = str(child.value)
                    elif child.key == "TARGETS":
                        # Parse targets list, stripping section markers
                        policy.targets = _parse_targets(child.value)
                    elif child.key == "DEFAULT_TARGET":
                        # Extract default target, stripping section marker if present
                        target_value = str(child.value)
                        if target_value.startswith("§"):
                            target_value = target_value[1:]
                        default_target = target_value
                    elif child.key == "REQUIRED_SECTION_IDS":
                        # GH-428: Section presence requirement (e.g., ["1"]).
                        ids, item_warnings = _parse_string_list_audited(child.value, "REQUIRED_SECTION_IDS")
                        policy.required_section_ids = ids
                        warnings.extend(item_warnings)
                    elif child.key == "SECTION_ALLOWS_EMPTY":
                        # GH-426 (cubic P2 fix on PR #446): per-schema opt-in
                        # for the walker's empty-section pass-through. Sections
                        # listed here may be authored present-but-empty without
                        # surfacing W_INCOMPLETE_SECTION_FIELDS for their
                        # SECTION_CONDITIONAL_REQUIRED triple. Default
                        # (omitted/empty list) keeps every schema strict — only
                        # an explicit opt-in changes behaviour. Reuses
                        # ``_parse_string_list_audited`` for shape validation
                        # (W_MALFORMED_POLICY on non-list / non-string-element
                        # values, mirroring REQUIRED_SECTION_IDS).
                        allow_list, item_warnings = _parse_string_list_audited(child.value, "SECTION_ALLOWS_EMPTY")
                        policy.section_allows_empty = set(allow_list)
                        warnings.extend(item_warnings)
                    elif child.key == "SECTION_CONDITIONAL_REQUIRED":
                        # CE rework: a SECTION_CONDITIONAL_REQUIRED authored as a
                        # scalar Assignment (rather than a Block) is malformed.
                        # Pre-fix this was silently dropped; emit
                        # W_MALFORMED_POLICY so the gap is visible (PROD::I4).
                        warnings.append(
                            SchemaExtractionWarning(
                                code="W_MALFORMED_POLICY",
                                message=(
                                    "POLICY.SECTION_CONDITIONAL_REQUIRED must be a block of "
                                    "section_key -> [field_names]; got a scalar Assignment value. "
                                    "The conditional-required check is disabled for this schema."
                                ),
                                field_path="POLICY.SECTION_CONDITIONAL_REQUIRED",
                            )
                        )
                elif isinstance(child, Block) and child.key == "SECTION_CONDITIONAL_REQUIRED":
                    # GH-428: Section-conditional field requirement.
                    # SECTION_CONDITIONAL_REQUIRED:
                    #   ANCHOR_KERNEL::["TARGET","NEVER","MUST","GATE"]
                    mapping, block_warnings = _parse_conditional_required_audited(child)
                    policy.section_conditional_required = mapping
                    warnings.extend(block_warnings)

    return policy, default_target, warnings


def _parse_targets(value: Any) -> list[str]:
    """Parse TARGETS value into list of target names.

    Args:
        value: TARGETS value (ListValue or list)

    Returns:
        List of target names (without section markers)
    """
    targets: list[str] = []

    # Handle ListValue object
    if hasattr(value, "items"):
        items = value.items
    elif isinstance(value, list):
        items = value
    else:
        return targets

    for item in items:
        target_str = str(item)
        # Remove section marker if present
        if target_str.startswith("§"):
            target_str = target_str[1:]
        targets.append(target_str)

    return targets


def _parse_string_list(value: Any) -> list[str]:
    """Parse a list-shaped Assignment value into a list of plain strings.

    Used by GH-428 POLICY.REQUIRED_SECTION_IDS extraction. Section ids in
    OCTAVE source are stored as strings ("1", "2b"); numeric ids may
    arrive as ints from the parser, so we coerce defensively. Non-list
    values yield an empty list rather than raising — lenient parsing
    philosophy (PROD::I5: SCHEMA_SOVEREIGNTY surfaces malformed schemas
    via missing-fields warnings downstream, not extractor exceptions).

    Backwards-compat wrapper: discards audit. New callers should use
    ``_parse_string_list_audited`` to capture ``W_MALFORMED_POLICY``
    diagnostics per PROD::I4 TRANSFORM_AUDITABILITY.
    """
    result, _ = _parse_string_list_audited(value, field_path="")
    return result


def _parse_string_list_audited(value: Any, field_path: str) -> tuple[list[str], list[SchemaExtractionWarning]]:
    """Audited variant of ``_parse_string_list``.

    Emits ``W_MALFORMED_POLICY`` for shapes that deviate from
    list-of-strings:
      * Non-list scalar (e.g., a bare string).
      * Non-string, non-numeric list elements (booleans, nulls, nested
        structures): the element is dropped AND a warning fires naming
        the field_path.

    PROD::I4 TRANSFORM_AUDITABILITY: every transformation logged.
    """
    warnings: list[SchemaExtractionWarning] = []

    # Shape A: not a list at all.
    if not hasattr(value, "items") and not isinstance(value, list):
        # ``None``/empty cases are legitimately absent — only warn for
        # truthy scalars (a bare string is the canonical malformed shape).
        if value is not None and str(value).strip():
            warnings.append(
                SchemaExtractionWarning(
                    code="W_MALFORMED_POLICY",
                    message=(
                        f"POLICY.{field_path} must be a list of strings; got "
                        f"scalar value {value!r}. The list is treated as empty."
                    ),
                    field_path=f"POLICY.{field_path}" if field_path else "POLICY",
                )
            )
        return [], warnings

    items = value.items if hasattr(value, "items") else value

    result: list[str] = []
    for index, item in enumerate(items):
        if item is None:
            warnings.append(
                SchemaExtractionWarning(
                    code="W_MALFORMED_POLICY",
                    message=(f"POLICY.{field_path}[{index}] must be a string; got null. " f"Element dropped."),
                    field_path=f"POLICY.{field_path}[{index}]" if field_path else f"POLICY[{index}]",
                )
            )
            continue
        # Booleans are an int subclass in Python — reject explicitly before
        # the str() coercion silently turns ``True`` into ``"True"``.
        if isinstance(item, bool):
            warnings.append(
                SchemaExtractionWarning(
                    code="W_MALFORMED_POLICY",
                    message=(
                        f"POLICY.{field_path}[{index}] must be a string; got " f"boolean {item!r}. Element dropped."
                    ),
                    field_path=f"POLICY.{field_path}[{index}]" if field_path else f"POLICY[{index}]",
                )
            )
            continue
        if not isinstance(item, str | int | float):
            warnings.append(
                SchemaExtractionWarning(
                    code="W_MALFORMED_POLICY",
                    message=(
                        f"POLICY.{field_path}[{index}] must be a string; got "
                        f"{type(item).__name__}. Element dropped."
                    ),
                    field_path=f"POLICY.{field_path}[{index}]" if field_path else f"POLICY[{index}]",
                )
            )
            continue
        s = str(item).strip().strip('"').strip("'")
        if s:
            result.append(s)
    return result, warnings


def _parse_conditional_required(block: Any) -> dict[str, list[str]]:
    """Backwards-compat wrapper that discards audit warnings.

    New callers should use ``_parse_conditional_required_audited``.
    """
    result, _ = _parse_conditional_required_audited(block)
    return result


def _parse_conditional_required_audited(
    block: Any,
) -> tuple[dict[str, list[str]], list[SchemaExtractionWarning]]:
    """Parse a SECTION_CONDITIONAL_REQUIRED block into a mapping.

    Source shape (Block value):
        SECTION_CONDITIONAL_REQUIRED:
          ANCHOR_KERNEL::["TARGET","NEVER","MUST","GATE"]
          OTHER_SECTION::["FIELD_A","FIELD_B"]

    Each Assignment child maps a section key (the key as it appears in
    the document, without the §N:: prefix — e.g. ``ANCHOR_KERNEL``) to a
    list of field names that must be present inside that section IF the
    section is present (GH-428).

    Per PROD::I4 TRANSFORM_AUDITABILITY, malformed children (non-list
    values, non-string elements) emit ``W_MALFORMED_POLICY`` warnings.
    """
    result: dict[str, list[str]] = {}
    warnings: list[SchemaExtractionWarning] = []
    for child in getattr(block, "children", []):
        if isinstance(child, Assignment):
            field_path = f"SECTION_CONDITIONAL_REQUIRED.{child.key}"
            fields, child_warnings = _parse_string_list_audited(child.value, field_path)
            warnings.extend(child_warnings)
            if fields:
                result[child.key] = fields
        else:
            # Nested Block under SECTION_CONDITIONAL_REQUIRED is unexpected:
            # the canonical shape is flat Assignment children.
            child_key = getattr(child, "key", "<unknown>")
            warnings.append(
                SchemaExtractionWarning(
                    code="W_MALFORMED_POLICY",
                    message=(
                        f"POLICY.SECTION_CONDITIONAL_REQUIRED expects flat Assignment "
                        f"children (section_key::[field,...]); got nested "
                        f"{type(child).__name__} for key {child_key!r}. Entry skipped."
                    ),
                    field_path=f"POLICY.SECTION_CONDITIONAL_REQUIRED.{child_key}",
                )
            )
    return result, warnings


def _extract_fields(sections: list[Any]) -> tuple[dict[str, FieldDefinition], list[SchemaExtractionWarning]]:
    """Extract FIELDS block from document sections.

    M3 CE violation #3: Now returns warnings for malformed patterns.

    Args:
        sections: List of document sections

    Returns:
        Tuple of (fields dict, warnings list)
    """
    fields: dict[str, FieldDefinition] = {}
    warnings: list[SchemaExtractionWarning] = []

    for section in sections:
        if isinstance(section, Block) and section.key == "FIELDS":
            for child in section.children:
                if isinstance(child, Assignment):
                    field_def, warning = _parse_field_assignment(child)
                    if field_def:
                        fields[field_def.name] = field_def
                    if warning:
                        warnings.append(warning)

    return fields, warnings


def _extract_turn_schema(
    sections: list[Any],
) -> tuple[dict[str, FieldDefinition] | None, list[SchemaExtractionWarning]]:
    """Extract TURN_SCHEMA block as a per-item sub-schema (GH-427).

    DEBATE_TRANSCRIPT declares a ``TURN_SCHEMA:`` block describing the
    structure each TURN entry must satisfy (ROLE REQ ENUM, CONTENT REQ,
    TURN_INDEX REQ, SPEAKER OPT, etc.). Prior to GH-427 this block was silently
    discarded by ``_extract_fields`` — only the top-level ``FIELDS:`` block
    reached the validator, leaving documented-but-not-enforced contract drift
    (PROD::I5 SCHEMA_SOVEREIGNTY violation).

    This helper parses each TURN_SCHEMA child Assignment as a holographic
    pattern field, reusing ``_parse_field_assignment`` so the validator can
    apply standard constraint evaluation (REQ, ENUM, TYPE, etc.) per turn
    without bespoke logic.

    Args:
        sections: List of document sections.

    Returns:
        Tuple of (turn_schema dict or None, warnings list).
        Returns ``(None, [])`` when no TURN_SCHEMA block is present so callers
        can distinguish "schema declares no per-item structure" from "schema
        declares an empty per-item structure".
    """
    turn_fields: dict[str, FieldDefinition] = {}
    warnings: list[SchemaExtractionWarning] = []
    found = False

    for section in sections:
        if isinstance(section, Block) and section.key == "TURN_SCHEMA":
            found = True
            for child in section.children:
                if isinstance(child, Assignment):
                    field_def, warning = _parse_field_assignment(child)
                    if field_def:
                        turn_fields[field_def.name] = field_def
                    if warning:
                        # Re-scope warning path under TURN_SCHEMA so audit
                        # trails distinguish it from FIELDS-level warnings.
                        warning.field_path = f"TURN_SCHEMA.{field_def.name if field_def else '?'}"
                        warnings.append(warning)

    if not found:
        return None, warnings
    return turn_fields, warnings


def _parse_field_assignment(
    assignment: Assignment,
) -> tuple[FieldDefinition | None, SchemaExtractionWarning | None]:
    """Parse a field assignment into FieldDefinition.

    M3 CE violation #3: Now returns warning for malformed patterns.

    Args:
        assignment: Assignment AST node (KEY::VALUE)

    Returns:
        Tuple of (FieldDefinition or None, Warning or None)
        Warning is generated for malformed holographic patterns.
    """
    name = assignment.key
    value = assignment.value

    # Issue #187: Check for HolographicValue first (parser already did the work)
    if isinstance(value, HolographicValue):
        # Parser already parsed this as holographic pattern
        pattern = HolographicPattern(
            example=value.example,
            constraints=value.constraints,
            target=value.target,
        )
        return FieldDefinition(name=name, pattern=pattern, raw_value=value.raw_pattern), None

    # Convert value to string for pattern parsing
    if hasattr(value, "items"):
        # ListValue - need to reconstruct the holographic pattern
        raw_value = _list_value_to_pattern_string(value)
    else:
        raw_value = str(value)

    # Try to parse as holographic pattern
    try:
        pattern = parse_holographic_pattern(raw_value)
        return FieldDefinition(name=name, pattern=pattern, raw_value=raw_value), None
    except HolographicPatternError as e:
        # M3 CE violation #3 fix: Emit warning for malformed pattern
        warning = SchemaExtractionWarning(
            code="W002",
            message=f"Malformed holographic pattern for field '{name}': {e}",
            field_path=f"FIELDS.{name}",
            severity="warning",
        )
        # Return field with no pattern for invalid holographic syntax
        return FieldDefinition(name=name, pattern=None, raw_value=raw_value), warning


def _list_value_to_pattern_string(list_value: Any) -> str:
    """Convert ListValue AST to holographic pattern string.

    Gap_2 ADR-0012: Token-witnessed reconstruction for operator masquerade.

    When list_value.tokens is available (captured by parser), uses token-type-aware
    reconstruction that correctly distinguishes quoted operator symbols from actual
    operators. Falls back to items-based heuristic reconstruction when tokens unavailable.

    The token-witnessed approach solves the operator masquerade problem:
    - Input: ["∧"∧REQ→§SELF]
    - Tokens: [STRING("∧"), CONSTRAINT(∧), IDENTIFIER(REQ), FLOW(→), SECTION(§), IDENTIFIER(SELF)]
    - Output: ["∧"∧REQ→§SELF] (quoted example preserved)

    Without tokens, reconstruction cannot distinguish STRING("∧") from CONSTRAINT(∧)
    because both have the same value after lexer processing.

    Args:
        list_value: ListValue AST node (may have tokens attribute)

    Returns:
        Reconstructed pattern string like '["example"∧REQ→§SELF]'
    """
    if not hasattr(list_value, "items"):
        return str(list_value)

    items = list_value.items
    if not items:
        return "[]"

    # Gap_2: Prefer token-witnessed reconstruction when available
    if hasattr(list_value, "tokens") and list_value.tokens:
        return _token_witnessed_reconstruction(list_value.tokens)

    # Fall back to items-based heuristic reconstruction (backwards compat)
    return _items_based_reconstruction(items)


def _token_witnessed_reconstruction(tokens: list[Any]) -> str:
    """Reconstruct holographic pattern from token slice with type awareness.

    Gap_2 ADR-0012: Token-type-aware reconstruction that preserves quoted operator
    symbols correctly. Each token's type metadata determines how it's rendered:

    - STRING tokens: Values quoted in source, render with quotes
    - CONSTRAINT (∧), FLOW (→), SECTION (§): Render as operators
    - IDENTIFIER: Render bare (constraint keywords, target names)
    - LIST_START/LIST_END: Structural delimiters
    - COMMA: Item separator

    This approach is deterministic and mirrors the source exactly.

    Args:
        tokens: Token slice from ListValue.tokens (includes [ and ])

    Returns:
        Reconstructed pattern string like '["∧"∧REQ→§SELF]'
    """
    parts = []

    for token in tokens:
        token_type = token.type

        if token_type == TokenType.LIST_START:
            parts.append("[")
        elif token_type == TokenType.LIST_END:
            parts.append("]")
        elif token_type == TokenType.STRING:
            # Gap_2: STRING tokens were quoted in source - preserve quotes
            parts.append(f'"{token.value}"')
        elif token_type == TokenType.CONSTRAINT:
            # Actual constraint operator ∧
            parts.append(token.value)
        elif token_type == TokenType.FLOW:
            # Flow operator →
            parts.append(token.value)
        elif token_type == TokenType.SECTION:
            # Section marker § (for routing target)
            parts.append(token.value)
        elif token_type == TokenType.IDENTIFIER:
            # Bare identifiers: constraint keywords (REQ, OPT), target names (SELF, INDEXER)
            parts.append(token.value)
        elif token_type == TokenType.NUMBER:
            # Numeric values
            if token.raw is not None:
                parts.append(token.raw)  # Preserve original format
            else:
                parts.append(str(token.value))
        elif token_type == TokenType.BOOLEAN:
            parts.append("true" if token.value else "false")
        elif token_type == TokenType.NULL:
            parts.append("null")
        elif token_type == TokenType.COMMA:
            parts.append(",")
        elif token_type == TokenType.SYNTHESIS:
            # Synthesis operator ⊕
            parts.append(token.value)
        elif token_type == TokenType.TENSION:
            # Tension operator ⇌
            parts.append(token.value)
        elif token_type == TokenType.ALTERNATIVE:
            # Alternative operator ∨
            parts.append(token.value)
        elif token_type == TokenType.CONCAT:
            # Concat operator ⧺
            parts.append(token.value)
        elif token_type == TokenType.AT:
            # At operator @
            parts.append(token.value)
        # Skip whitespace tokens (NEWLINE, INDENT) - they don't affect pattern semantics

    return "".join(parts)


def _items_based_reconstruction(items: list[Any]) -> str:
    """Reconstruct holographic pattern from parsed items (fallback heuristic).

    This is the original reconstruction logic, used when tokens are not available.
    It uses heuristics to guess whether values should be quoted, which can fail
    for operator masquerade cases like ["∧"∧REQ→§SELF].

    Gap_2: This path is preserved for backwards compatibility with ListValue
    objects that don't have tokens (e.g., programmatically created).

    Args:
        items: ListValue.items list

    Returns:
        Reconstructed pattern string (may have incorrect quoting for edge cases)
    """
    parts = []
    i = 0
    while i < len(items):
        item = items[i]

        if isinstance(item, str):
            # Operators (standalone ∧, →, etc.)
            if item in ("∧", "→", "⊕", "⇌", "∨"):
                parts.append(item)
            # Section marker
            elif item == "§":
                parts.append("§")
            # Combined constraint+flow like "REQ→" or "ENUM[A,B]→"
            elif "→" in item:
                parts.append(item)
            # Constraint keywords (standalone)
            elif item in ("REQ", "OPT", "DIR", "APPEND_ONLY", "DATE", "ISO8601"):
                parts.append(item)
            # Combined constraints like "REQ∧ENUM" (without the bracket part yet)
            elif "∧" in item and item not in ("∧",):
                # This is like "REQ∧ENUM" - look ahead for the ListValue with parameters
                if i + 1 < len(items) and hasattr(items[i + 1], "items"):
                    # The next item is the parameter list for ENUM
                    param_list = items[i + 1]
                    params = ",".join(str(p) for p in param_list.items)
                    parts.append(f"{item}[{params}]")
                    i += 1  # Skip the ListValue we just processed
                else:
                    parts.append(item)
            # Parameterized constraints (complete with brackets)
            elif any(
                item.startswith(prefix)
                for prefix in ("ENUM[", "TYPE[", "TYPE(", "REGEX[", "CONST[", "RANGE[", "MAX_LENGTH[", "MIN_LENGTH[")
            ):
                parts.append(item)
            # Example value - needs quoting if it doesn't look like an operator
            else:
                # Check if it's already quoted or looks like a target name after §
                if parts and parts[-1] == "§":
                    # This is the target name, don't quote
                    parts.append(item)
                else:
                    # Example value or unrecognized - quote it
                    parts.append(f'"{item}"')
        elif isinstance(item, int | float):
            # Numeric example
            parts.append(str(item))
        elif isinstance(item, bool):
            # Boolean example
            parts.append("true" if item else "false")
        elif item is None:
            parts.append("null")
        elif isinstance(item, list):
            # Nested list for list example values
            inner_parts = []
            for inner_item in item:
                if isinstance(inner_item, str):
                    inner_parts.append(f'"{inner_item}"')
                else:
                    inner_parts.append(str(inner_item))
            parts.append(f"[{','.join(inner_parts)}]")
        elif hasattr(item, "items"):
            # Nested ListValue - could be ENUM parameters or list example
            # Check if the previous part ends with a constraint that expects parameters
            if parts and any(
                parts[-1].endswith(suffix) for suffix in ("ENUM", "RANGE", "CONST", "MAX_LENGTH", "MIN_LENGTH")
            ):
                # This is a parameter list for the constraint
                params = ",".join(str(p) for p in item.items)
                parts[-1] = f"{parts[-1]}[{params}]"
            else:
                # This is a nested list for the example value
                inner_parts = []
                for inner_item in item.items:
                    if isinstance(inner_item, str):
                        inner_parts.append(f'"{inner_item}"')
                    else:
                        inner_parts.append(str(inner_item))
                parts.append(f"[{','.join(inner_parts)}]")
        else:
            parts.append(str(item))

        i += 1

    # Join and wrap in brackets
    return f"[{''.join(parts)}]"


def _extract_frontmatter_defs(sections: list[Any]) -> dict[str, FrontmatterFieldDef]:
    """Extract FRONTMATTER block from schema document sections (Issue #244).

    Parses a FRONTMATTER block that defines Zone 2 (YAML frontmatter) field
    requirements. Each child block within FRONTMATTER describes one field:

        FRONTMATTER:
          name:
            REQUIRED::true
            TYPE::STRING
          allowed-tools:
            REQUIRED::true
            TYPE::LIST

    Args:
        sections: List of document sections (Assignment, Block, Section)

    Returns:
        Dictionary of field name -> FrontmatterFieldDef.
        Empty dict if no FRONTMATTER block found.
    """
    frontmatter: dict[str, FrontmatterFieldDef] = {}

    for section in sections:
        if isinstance(section, Block) and section.key == "FRONTMATTER":
            for child in section.children:
                if isinstance(child, Block):
                    # Each child block is a frontmatter field definition
                    field_name = child.key
                    required = False
                    field_type = "STRING"

                    for grandchild in child.children:
                        if isinstance(grandchild, Assignment):
                            if grandchild.key == "REQUIRED":
                                val = grandchild.value
                                if isinstance(val, bool):
                                    required = val
                                elif isinstance(val, str):
                                    required = val.lower() == "true"
                            elif grandchild.key == "TYPE":
                                field_type = str(grandchild.value)

                    frontmatter[field_name] = FrontmatterFieldDef(
                        name=field_name,
                        required=required,
                        field_type=field_type,
                    )

    return frontmatter


def extract_schema_from_document(doc: Document) -> SchemaDefinition:
    """Extract schema definition from parsed OCTAVE document.

    Parses POLICY, FIELDS, and FRONTMATTER blocks, extracts holographic patterns,
    and builds a complete SchemaDefinition.

    Args:
        doc: Parsed Document AST

    Returns:
        SchemaDefinition with extracted policy, fields, and frontmatter

    Example:
        >>> doc = parse('''
        ... ===MY_SCHEMA===
        ... META:
        ...   TYPE::PROTOCOL_DEFINITION
        ...   VERSION::"1.0"
        ...
        ... POLICY:
        ...   VERSION::"1.0"
        ...   UNKNOWN_FIELDS::REJECT
        ...
        ... FIELDS:
        ...   NAME::["example"∧REQ→§SELF]
        ... ===END===
        ... ''')
        >>> schema = extract_schema_from_document(doc)
        >>> schema.name
        'MY_SCHEMA'
        >>> len(schema.fields)
        1
    """
    # Extract name from document envelope
    name = doc.name if doc.name else "UNKNOWN"

    # Extract version from META block
    version = None
    if doc.meta and "VERSION" in doc.meta:
        version = str(doc.meta["VERSION"]).strip('"')

    # Extract POLICY block and default_target (Issue #103: feudal inheritance).
    # PR #444 rework: POLICY extraction now returns W_MALFORMED_POLICY
    # warnings per PROD::I4 TRANSFORM_AUDITABILITY.
    policy, default_target, policy_warnings = _extract_policy(doc.sections)

    # Extract FIELDS block (M3 CE violation #3: now returns warnings)
    fields, warnings = _extract_fields(doc.sections)
    warnings.extend(policy_warnings)

    # Extract FRONTMATTER block (Issue #244: Zone 2 validation)
    frontmatter = _extract_frontmatter_defs(doc.sections)

    # GH-427: Extract TURN_SCHEMA block as per-item sub-schema (e.g., for
    # DEBATE_TRANSCRIPT). None when the schema does not declare one.
    turn_schema, turn_warnings = _extract_turn_schema(doc.sections)
    if turn_warnings:
        warnings = warnings + turn_warnings

    return SchemaDefinition(
        name=name,
        version=version,
        policy=policy,
        fields=fields,
        frontmatter=frontmatter,
        default_target=default_target,
        warnings=warnings,
        turn_schema=turn_schema,
    )
