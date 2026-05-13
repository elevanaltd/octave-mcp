"""OCTAVE repair engine with tier classification (P1.6, Gap_5).

Implements schema-driven repair with NORMALIZATION/REPAIR/FORBIDDEN tiers:
- TIER_NORMALIZATION: Always applied (ascii→unicode, whitespace, quotes, envelope)
- TIER_REPAIR: Only when fix=true (enum casefold, type coercion)
- TIER_FORBIDDEN: Always errors (no target inference, no field insertion)

Gap_5 implements the TIER_REPAIR logic:
- Enum casefold: "active" → "ACTIVE" (only if unique case-insensitive match)
- Type coercion: "42" → 42 (only if lossless conversion possible)
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from octave_mcp.core.constraints import EnumConstraint, TypeConstraint
from octave_mcp.core.grammar.cst import Assignment, Block, Document, LiteralZoneValue, Section
from octave_mcp.core.repair_log import RepairLog, RepairTier
from octave_mcp.core.schema_extractor import FieldDefinition, SchemaDefinition
from octave_mcp.core.validator import ValidationError

# Keep TYPE_CHECKING block empty for potential future use
if TYPE_CHECKING:
    pass


def repair_value(
    value: Any,
    field_def: FieldDefinition | None,
    repair_log: RepairLog,
    fix: bool = False,
) -> tuple[Any, bool]:
    """Apply schema-driven repairs to a single value.

    Gap_5 implementation: TIER_REPAIR repairs (enum casefold, type coercion).
    Only applies when fix=True and repairs are unambiguous/lossless.

    Args:
        value: The value to potentially repair
        field_def: FieldDefinition containing pattern with constraints
        repair_log: RepairLog to record any repairs made (I4 compliance)
        fix: Whether to apply TIER_REPAIR fixes (if False, no repairs applied)

    Returns:
        Tuple of (repaired_value, was_repaired)
        - repaired_value: The value after any repairs (or original if no repair)
        - was_repaired: True if a repair was applied

    Repair Rules:
        1. TIER_FORBIDDEN: Never auto-fix:
           - Missing fields (value is None with REQ constraint)
           - Target inference (pattern.target is None)
           - Field insertion (never add new fields)

        2. TIER_REPAIR (only when fix=True):
           - Enum casefold: "active" → "ACTIVE" if unique case-insensitive match
           - Type coercion: "42" → 42 if lossless string→number conversion
    """
    # Issue #235 MP12: Literal zones are never repaired (D3: zero processing).
    # Guard clause must be BEFORE all other checks to prevent any constraint
    # logic from running on literal zone content.
    if isinstance(value, LiteralZoneValue):
        return value, False

    # Early exit conditions (TIER_FORBIDDEN scenarios)
    if not fix:
        return value, False

    # No field definition - can't determine what repair to apply
    if field_def is None:
        return value, False

    # No pattern - can't determine constraints
    if field_def.pattern is None:
        return value, False

    # No constraints - nothing to repair against
    if field_def.pattern.constraints is None:
        return value, False

    # Empty constraint chain - nothing to repair
    if not field_def.pattern.constraints.constraints:
        return value, False

    # TIER_FORBIDDEN: Never insert values for missing fields
    if value is None:
        return value, False

    # Attempt repairs in order of constraint chain
    constraints = field_def.pattern.constraints.constraints
    current_value = value
    was_repaired = False

    for constraint in constraints:
        if isinstance(constraint, EnumConstraint):
            repaired, did_repair = _attempt_enum_casefold(current_value, constraint, repair_log)
            if did_repair:
                current_value = repaired
                was_repaired = True
        elif isinstance(constraint, TypeConstraint):
            repaired, did_repair = _attempt_type_coercion(current_value, constraint, repair_log)
            if did_repair:
                current_value = repaired
                was_repaired = True

    return current_value, was_repaired


def _attempt_enum_casefold(
    value: Any,
    constraint: EnumConstraint,
    repair_log: RepairLog,
) -> tuple[Any, bool]:
    """Attempt enum casefold repair.

    Repairs value to canonical case if there's a unique case-insensitive match
    in the allowed values.

    Args:
        value: Value to potentially repair
        constraint: EnumConstraint with allowed_values
        repair_log: Log to record repair

    Returns:
        Tuple of (repaired_value, was_repaired)
    """
    # Only repair string values
    if not isinstance(value, str):
        return value, False

    allowed_values = constraint.allowed_values

    # Check for exact match first - no repair needed
    if value in allowed_values:
        return value, False

    # Find case-insensitive matches
    value_lower = value.lower()
    matches = [v for v in allowed_values if v.lower() == value_lower]

    # No matches - can't repair
    if len(matches) == 0:
        return value, False

    # Ambiguous - multiple matches, can't safely repair
    if len(matches) > 1:
        return value, False

    # Unique match - repair to canonical case
    canonical = matches[0]

    # Log the repair (I4 compliance)
    repair_log.add(
        rule_id="ENUM_CASEFOLD",
        before=value,
        after=canonical,
        tier=RepairTier.REPAIR,
        safe=True,
        semantics_changed=False,  # Case change only, same semantic value
    )

    return canonical, True


def _attempt_type_coercion(
    value: Any,
    constraint: TypeConstraint,
    repair_log: RepairLog,
) -> tuple[Any, bool]:
    """Attempt type coercion repair.

    Repairs string values to numbers if the constraint expects NUMBER
    and conversion is lossless.

    Args:
        value: Value to potentially repair
        constraint: TypeConstraint with expected_type
        repair_log: Log to record repair

    Returns:
        Tuple of (repaired_value, was_repaired)
    """
    expected_type = constraint.expected_type

    # Only handle NUMBER coercion for now
    if expected_type != "NUMBER":
        return value, False

    # Only coerce strings to numbers
    if not isinstance(value, str):
        return value, False

    # Strip whitespace for conversion
    value_stripped = value.strip()

    if not value_stripped:
        return value, False

    # Attempt conversion (try int first, then float)
    coerced: int | float
    try:
        # Check if it's an integer (no decimal point, no e/E for scientific)
        if "." not in value_stripped and "e" not in value_stripped.lower():
            coerced = int(value_stripped)
        else:
            coerced = float(value_stripped)

            # BLOCKING 2 FIX: Reject non-finite results (inf, -inf, nan)
            # These are lossy conversions - original value cannot be recovered
            # e.g., "1e309" -> inf is lossy, "1e308" -> 1e308 is lossless
            if not math.isfinite(coerced):
                return value, False

        # Log the repair (I4 compliance)
        repair_log.add(
            rule_id="TYPE_COERCION",
            before=value,
            after=str(coerced),
            tier=RepairTier.REPAIR,
            safe=True,
            semantics_changed=False,  # Same semantic value, different representation
        )

        return coerced, True

    except (ValueError, OverflowError):
        # Can't convert - not a valid number
        return value, False


def repair(
    doc: Document,
    validation_errors: list[ValidationError],
    fix: bool = False,
    schema: SchemaDefinition | None = None,
) -> tuple[Document, RepairLog]:
    """Apply repairs based on tier classification.

    BLOCKING 1 FIX: Now wires repair_value() into the pipeline for schema-driven
    repairs when schema is provided.

    Args:
        doc: Parsed document AST
        validation_errors: Errors from validation
        fix: Whether to apply TIER_REPAIR fixes
        schema: Optional SchemaDefinition with field definitions for repair

    Returns:
        Tuple of (repaired document, repair log)
    """
    repair_log = RepairLog(repairs=[])

    # TIER_NORMALIZATION: Always applied (already handled by lexer/parser)
    # These are logged during parsing (ascii->unicode, whitespace, envelope)

    # TIER_REPAIR: Only when fix=true AND schema is provided
    if fix and schema is not None:
        _apply_schema_repairs(doc, schema, repair_log)

    # TIER_FORBIDDEN: Never automatic
    # These should remain as validation errors, never auto-fixed

    return doc, repair_log


def _apply_schema_repairs(
    doc: Document,
    schema: SchemaDefinition,
    repair_log: RepairLog,
) -> None:
    """Apply schema-driven repairs to document fields.

    Iterates through document sections and applies repair_value() to fields
    that have corresponding definitions in the schema.

    Args:
        doc: Document to repair (modified in place)
        schema: SchemaDefinition with field definitions
        repair_log: RepairLog to record repairs
    """
    # Iterate through document sections. Top-level Block/Section parents
    # have their body_dirty propagation managed by _repair_ast_node's
    # recursive return value — no extra plumbing needed here.
    for section in doc.sections:
        _repair_ast_node(section, schema, repair_log)


def _repair_ast_node(
    node: Any,
    schema: SchemaDefinition,
    repair_log: RepairLog,
) -> bool:
    """Recursively repair an AST node and its children.

    Returns ``True`` iff this node OR any descendant was repaired, so the
    caller (a parent Block/Section) can mark its ``body_dirty`` flag.
    This is the structural propagation that closes the CE BLOCKER on
    PR #418: without it, a repaired grandchild Assignment leaves its
    ancestor Block/Section with ``dirty=False`` and ``body_dirty=False``,
    and the Strategy A T8 slice path in ``emit()`` then slices the OLD
    baseline bytes for the parent — silently dropping the repair.

    Contract (paired-write rule, ADR-0006 SR2-T2 PR-2):
      * Repairing an Assignment value MUST be paired with
        ``node.repaired = True`` on that Assignment.
      * Repairing any descendant of a Block/Section MUST be paired with
        ``parent.body_dirty = True`` on the parent (this function).

    Args:
        node: AST node to repair (Assignment, Block, or Section)
        schema: SchemaDefinition with field definitions
        repair_log: RepairLog to record repairs

    Returns:
        True iff a repair occurred at this node or anywhere in its
        subtree; False otherwise.
    """
    if isinstance(node, Assignment):
        # Issue #235 MP13: Log literal zone presence but never modify (I4 audit).
        if isinstance(node.value, LiteralZoneValue):
            # Literal zones pass through repair unchanged.
            # Audit entry is generated by the MCP tool layer (T13/T14),
            # not here -- _repair_ast_node only ensures no modification occurs.
            return False

        # Check if field has a schema definition
        field_def = schema.fields.get(node.key)
        if field_def is not None:
            repaired_value, was_repaired = repair_value(
                value=node.value,
                field_def=field_def,
                repair_log=repair_log,
                fix=True,
            )
            if was_repaired:
                # ADR-0006 SR2-T2 PR-2 (GH#377): paired-write rule.
                # node.value mutation MUST be paired with node.repaired
                # = True. Splicing a "clean" node whose value was
                # repaired post-parse would re-introduce the source
                # bytes the schema repair just normalised away — an I1
                # violation. Setting repaired=True forces re-emit on
                # the eventual PR-3 emitter pass.
                node.value = repaired_value
                node.repaired = True
                return True
        return False

    if isinstance(node, Block):
        # Recursively process block children; if ANY child (or grandchild)
        # was repaired, mark this Block's body_dirty so emit()'s slice
        # predicate (which now checks body_dirty per CRS BLOCKER fix in
        # commit 062892c) routes us to the canonical re-emit path.
        descendant_repaired = False
        for child in node.children:
            if _repair_ast_node(child, schema, repair_log):
                descendant_repaired = True
        if descendant_repaired:
            # Paired-write: a descendant mutation requires this ancestor
            # to be re-emitted from AST, not sliced from baseline bytes.
            node.body_dirty = True
        return descendant_repaired

    if isinstance(node, Section):
        descendant_repaired = False
        for child in node.children:
            if _repair_ast_node(child, schema, repair_log):
                descendant_repaired = True
        if descendant_repaired:
            # Same paired-write contract as Block above.
            node.body_dirty = True
        return descendant_repaired

    # Unrecognised node type: no repair, no propagation.
    return False
