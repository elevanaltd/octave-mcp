"""Canonical OCTAVE emitter.

Implements P1.4: canonical_emitter

Emits strict canonical OCTAVE from AST with:
- Unicode operators only
- No whitespace around ::
- Explicit envelope always present
- Deterministic formatting
- 2-space indentation

I2 (Deterministic Absence) Support:
- Absent values are NOT emitted (field is absent, not present with null)
- None values are emitted as 'null' (explicitly empty)
- This preserves the tri-state distinction: absent vs null vs value
"""

import re
from typing import Any

from octave_mcp.core.ast_nodes import Absent, Assignment, Block, Document, InlineMap, ListValue, Section

IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


def needs_quotes(value: Any) -> bool:
    """Check if a string value needs quotes."""
    if not isinstance(value, str):
        return False

    # Empty string needs quotes
    if not value:
        return True

    # Reserved words need quotes to avoid becoming literals or operators
    # This includes boolean/null literals and operator keywords
    if value in ("true", "false", "null", "vs"):
        return True

    # If it's not a valid identifier, it needs quotes
    # This covers:
    # - Numbers (start with digit)
    # - Dashes (not allowed in identifiers)
    # - Special chars (spaces, colons, brackets, etc.)
    if not IDENTIFIER_PATTERN.match(value):
        return True

    return False


def is_absent(value: Any) -> bool:
    """Check if a value is the Absent sentinel.

    I2 (Deterministic Absence): Absent fields should not be emitted.
    This helper enables filtering before emission.
    """
    return isinstance(value, Absent)


def emit_value(value: Any) -> str:
    """Emit a value in canonical form.

    I2 Compliance:
    - Absent values raise ValueError (caller must filter before calling)
    - None values return "null" (explicitly empty)
    - ListValue and InlineMap filter out Absent items/values internally

    Raises:
        ValueError: If passed an Absent value directly. This catches
            caller bugs where Absent leaked through without filtering.
    """
    if isinstance(value, Absent):
        # I2: Absent is NOT the same as null
        # Raise to catch caller bugs - Absent should be filtered BEFORE emit_value
        raise ValueError("Absent value passed to emit_value(). " "I2 requires filtering Absent before emission.")
    if value is None:
        return "null"
    elif isinstance(value, bool):
        return "true" if value else "false"
    elif isinstance(value, int | float):
        return str(value)
    elif isinstance(value, str):
        if needs_quotes(value):
            # Escape special characters
            escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
            return f'"{escaped}"'
        return value
    elif isinstance(value, ListValue):
        if not value.items:
            return "[]"
        # I2: Filter out Absent items before emission
        items = [emit_value(item) for item in value.items if not is_absent(item)]
        return f"[{','.join(items)}]"
    elif isinstance(value, InlineMap):
        # I2: Filter out pairs with Absent values before emission
        pairs = [f"{k}::{emit_value(v)}" for k, v in value.pairs.items() if not is_absent(v)]
        return f"[{','.join(pairs)}]"
    else:
        # Fallback for unknown types
        return str(value)


def emit_assignment(assignment: Assignment, indent: int = 0) -> str:
    """Emit an assignment in canonical form."""
    indent_str = "  " * indent
    value_str = emit_value(assignment.value)
    return f"{indent_str}{assignment.key}::{value_str}"


def emit_block(block: Block, indent: int = 0) -> str:
    """Emit a block in canonical form.

    I2 Compliance: Skips children with Absent values.
    """
    indent_str = "  " * indent
    lines = [f"{indent_str}{block.key}:"]

    # Emit children
    # I2: Skip assignments with Absent values
    for child in block.children:
        if isinstance(child, Assignment):
            if is_absent(child.value):
                continue
            lines.append(emit_assignment(child, indent + 1))
        elif isinstance(child, Block):
            lines.append(emit_block(child, indent + 1))
        elif isinstance(child, Section):
            lines.append(emit_section(child, indent + 1))

    return "\n".join(lines)


def emit_section(section: Section, indent: int = 0) -> str:
    """Emit a § section in canonical form.

    Supports both plain numbers ("1", "2") and suffix forms ("2b", "2c").
    Includes optional bracket annotation if present.

    I2 Compliance: Skips children with Absent values.
    """
    indent_str = "  " * indent
    section_line = f"{indent_str}§{section.section_id}::{section.key}"
    if section.annotation:
        section_line += f"[{section.annotation}]"
    lines = [section_line]

    # Emit children
    # I2: Skip assignments with Absent values
    for child in section.children:
        if isinstance(child, Assignment):
            if is_absent(child.value):
                continue
            lines.append(emit_assignment(child, indent + 1))
        elif isinstance(child, Block):
            lines.append(emit_block(child, indent + 1))
        elif isinstance(child, Section):
            lines.append(emit_section(child, indent + 1))

    return "\n".join(lines)


def emit_meta(meta: dict[str, Any]) -> str:
    """Emit META block.

    I2 Compliance:
    - Skips fields with Absent values
    - Returns empty string if all fields are absent (no empty META: header)
    """
    if not meta:
        return ""

    # I2: Collect non-absent fields first, then decide whether to emit header
    content_lines = []
    for key, value in meta.items():
        # I2: Skip Absent values
        if is_absent(value):
            continue
        value_str = emit_value(value)
        content_lines.append(f"  {key}::{value_str}")

    # I2: If all fields were absent, return empty string (no header)
    if not content_lines:
        return ""

    return "META:\n" + "\n".join(content_lines)


def emit(doc: Document) -> str:
    """Emit canonical OCTAVE from AST.

    Args:
        doc: Document AST

    Returns:
        Canonical OCTAVE text with explicit envelope,
        unicode operators, and deterministic formatting
    """
    lines = []

    # Always emit explicit envelope
    lines.append(f"==={doc.name}===")

    # Emit META if present
    if doc.meta:
        lines.append(emit_meta(doc.meta))

    # Emit separator if present
    if doc.has_separator:
        lines.append("---")

    # Emit sections
    # I2 Compliance: Skip assignments with Absent values
    for section in doc.sections:
        if isinstance(section, Assignment):
            if is_absent(section.value):
                # I2: Absent fields are not emitted
                continue
            lines.append(emit_assignment(section, 0))
        elif isinstance(section, Block):
            lines.append(emit_block(section, 0))
        elif isinstance(section, Section):
            lines.append(emit_section(section, 0))

    # Always emit END envelope
    lines.append("===END===")

    return "\n".join(lines)
