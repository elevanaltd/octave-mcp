"""OCTAVE schema extraction from documents (Issue #93).

Extracts schema definitions (POLICY, FIELDS blocks) from parsed OCTAVE documents
using holographic pattern parsing.

This module provides:
- SchemaDefinition: Complete schema definition with policy and fields
- FieldDefinition: Single field definition with holographic pattern
- PolicyDefinition: POLICY block configuration
- extract_schema_from_document(): Extract schema from parsed Document
"""

from dataclasses import dataclass, field
from typing import Any

from octave_mcp.core.ast_nodes import Assignment, Block, Document
from octave_mcp.core.constraints import RequiredConstraint
from octave_mcp.core.holographic import (
    HolographicPattern,
    HolographicPatternError,
    parse_holographic_pattern,
)


@dataclass
class PolicyDefinition:
    """POLICY block configuration for schema.

    Attributes:
        version: Schema version from POLICY block
        unknown_fields: How to handle unknown fields (REJECT|IGNORE|WARN)
        targets: List of valid extraction targets (without section markers)
    """

    version: str = "1.0"
    unknown_fields: str = "REJECT"
    targets: list[str] = field(default_factory=list)


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
        default_target: Block-level default target for feudal inheritance (Issue #103)
    """

    name: str
    version: str | None = None
    policy: PolicyDefinition = field(default_factory=PolicyDefinition)
    fields: dict[str, FieldDefinition] = field(default_factory=dict)
    default_target: str | None = None


def _extract_policy(sections: list[Any]) -> PolicyDefinition:
    """Extract POLICY block from document sections.

    Args:
        sections: List of document sections (Assignment, Block, Section)

    Returns:
        PolicyDefinition with extracted settings
    """
    policy = PolicyDefinition()

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

    return policy


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


def _extract_fields(sections: list[Any]) -> dict[str, FieldDefinition]:
    """Extract FIELDS block from document sections.

    Args:
        sections: List of document sections

    Returns:
        Dictionary of field name -> FieldDefinition
    """
    fields: dict[str, FieldDefinition] = {}

    for section in sections:
        if isinstance(section, Block) and section.key == "FIELDS":
            for child in section.children:
                if isinstance(child, Assignment):
                    field_def = _parse_field_assignment(child)
                    if field_def:
                        fields[field_def.name] = field_def

    return fields


def _parse_field_assignment(assignment: Assignment) -> FieldDefinition | None:
    """Parse a field assignment into FieldDefinition.

    Args:
        assignment: Assignment AST node (KEY::VALUE)

    Returns:
        FieldDefinition or None if parsing fails
    """
    name = assignment.key
    value = assignment.value

    # Convert value to string for pattern parsing
    if hasattr(value, "items"):
        # ListValue - need to reconstruct the holographic pattern
        raw_value = _list_value_to_pattern_string(value)
    else:
        raw_value = str(value)

    # Try to parse as holographic pattern
    try:
        pattern = parse_holographic_pattern(raw_value)
        return FieldDefinition(name=name, pattern=pattern, raw_value=raw_value)
    except HolographicPatternError:
        # Return field with no pattern for invalid holographic syntax
        return FieldDefinition(name=name, pattern=None, raw_value=raw_value)


def _list_value_to_pattern_string(list_value: Any) -> str:
    """Convert ListValue AST to holographic pattern string.

    The parser converts ["example"∧REQ→§SELF] into a ListValue.
    We need to reconstruct it back to a pattern string.

    The parser breaks the pattern into tokens:
    - ListValue(items=['example', '∧', 'REQ→', '§', 'SELF'])

    For ENUM patterns, the parser produces:
    - ListValue(items=['ACTIVE', '∧', 'REQ∧ENUM', ListValue(items=['A', 'B']), '→', '§', 'SELF'])

    We need to reconstruct this as:
    - '["example"∧REQ→§SELF]'
    - '["ACTIVE"∧REQ∧ENUM[A,B]→§SELF]'

    Args:
        list_value: ListValue AST node

    Returns:
        Reconstructed pattern string like '["example"∧REQ→§SELF]'
    """
    if not hasattr(list_value, "items"):
        return str(list_value)

    items = list_value.items
    if not items:
        return "[]"

    # Reconstruct the pattern from tokenized items
    # Items like: ['example', '∧', 'REQ→', '§', 'SELF']
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


def extract_schema_from_document(doc: Document) -> SchemaDefinition:
    """Extract schema definition from parsed OCTAVE document.

    Parses POLICY and FIELDS blocks, extracts holographic patterns,
    and builds a complete SchemaDefinition.

    Args:
        doc: Parsed Document AST

    Returns:
        SchemaDefinition with extracted policy and fields

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

    # Extract POLICY block
    policy = _extract_policy(doc.sections)

    # Extract FIELDS block
    fields = _extract_fields(doc.sections)

    return SchemaDefinition(
        name=name,
        version=version,
        policy=policy,
        fields=fields,
    )
