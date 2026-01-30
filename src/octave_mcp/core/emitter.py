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

GitHub Issue #193: Auto-Format Options
- indent_normalize: Convert all indentation to 2-space standard
- blank_line_normalize: Normalize blank lines between sections
- trailing_whitespace: Strip/preserve trailing whitespace
- key_sorting: Optionally sort keys alphabetically within blocks
"""

import re
from dataclasses import dataclass
from typing import Any, Literal

from octave_mcp.core.ast_nodes import (
    Absent,
    Assignment,
    Block,
    Comment,
    Document,
    HolographicValue,
    InlineMap,
    ListValue,
    Section,
)


@dataclass
class FormatOptions:
    """Configuration for output formatting during emission.

    GitHub Issue #193: Auto-Format Options
    GitHub Issue #182: Comment Preservation

    Attributes:
        indent_normalize: Convert all indentation to 2-space standard.
            Fixes mixed tabs/spaces. Default: True.
        blank_line_normalize: Normalize blank lines between sections.
            Single blank line between top-level sections, removes excessive
            blank lines (>2 consecutive). Default: False.
        trailing_whitespace: How to handle trailing whitespace on lines.
            "strip" removes trailing spaces/tabs, "preserve" keeps them.
            Default: "strip".
        key_sorting: Sort keys alphabetically within blocks and META.
            Default: False.
        strip_comments: Remove all comments from output for compact form.
            When False (default), comments are preserved in output.
            Default: False.
    """

    indent_normalize: bool = True
    blank_line_normalize: bool = False
    trailing_whitespace: Literal["strip", "preserve"] = "strip"
    key_sorting: bool = False
    strip_comments: bool = False


IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*\Z")

# Issue #181: Variable pattern for $VAR, $1:name placeholders
# Variables start with $ and contain alphanumeric, underscore, or colon
VARIABLE_PATTERN = re.compile(r"^\$[A-Za-z0-9_:]+\Z")


def _sort_children_by_key(children: list[Any]) -> list[Any]:
    """Sort AST children by key for key_sorting option.

    Assignments are sorted alphabetically by key and placed first.
    Non-assignment nodes (Block, Section) preserve their relative order
    and are placed after sorted assignments.

    Args:
        children: List of AST child nodes

    Returns:
        Sorted list with assignments first (by key), then other nodes
    """
    assignments = [c for c in children if isinstance(c, Assignment)]
    non_assignments = [c for c in children if not isinstance(c, Assignment)]

    # Sort assignments alphabetically by key
    sorted_assignments = sorted(assignments, key=lambda x: x.key)

    # Merge: sorted assignments first, then non-assignments in original order
    return sorted_assignments + non_assignments


def needs_quotes(value: Any) -> bool:
    """Check if a string value needs quotes."""
    if not isinstance(value, str):
        return False

    # Empty string needs quotes
    if not value:
        return True

    # Newlines/tabs must be escaped, so they must be quoted.
    # NOTE: Regex `$` matches before a trailing newline; IDENTIFIER_PATTERN uses `\\Z`
    # to avoid treating "A\\n" as a bare identifier.
    if "\n" in value or "\t" in value or "\r" in value:
        return True

    # Reserved words need quotes to avoid becoming literals or operators
    # This includes boolean/null literals and operator keywords
    if value in ("true", "false", "null", "vs"):
        return True

    # Issue #181: Variables ($VAR, $1:name) don't need quotes
    # Check this BEFORE identifier pattern since $ is not a valid identifier start
    if VARIABLE_PATTERN.match(value):
        return False

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
        raise ValueError("Absent value passed to emit_value(). I2 requires filtering Absent before emission.")
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
    elif isinstance(value, HolographicValue):
        # M3: Emit holographic pattern using raw_pattern for I1 fidelity
        # The raw_pattern preserves the original syntax: ["example"∧CONSTRAINT→§TARGET]
        return value.raw_pattern
    else:
        # Fallback for unknown types
        return str(value)


def _emit_leading_comments(comments: list[str], indent: int = 0, strip_comments: bool = False) -> list[str]:
    """Emit leading comments as lines.

    Issue #182: Comment preservation.

    Args:
        comments: List of comment text strings (without // prefix)
        indent: Current indentation level
        strip_comments: If True, return empty list

    Returns:
        List of comment lines with // prefix and proper indentation
    """
    if strip_comments or not comments:
        return []
    indent_str = "  " * indent
    return [f"{indent_str}// {comment}" for comment in comments]


def _emit_trailing_comment(comment: str | None, strip_comments: bool = False) -> str:
    """Emit trailing comment suffix.

    Issue #182: Comment preservation.

    Args:
        comment: Comment text string (without // prefix) or None
        strip_comments: If True, return empty string

    Returns:
        " // comment" suffix or empty string
    """
    if strip_comments or not comment:
        return ""
    return f" // {comment}"


def emit_comment(comment: Comment, indent: int = 0, format_options: FormatOptions | None = None) -> str:
    """Emit a standalone comment line.

    Issue #182: Support for orphan comments inside blocks/sections.
    """
    strip_comments = format_options.strip_comments if format_options else False
    if strip_comments:
        return ""

    indent_str = "  " * indent
    return f"{indent_str}// {comment.text}"


def emit_assignment(assignment: Assignment, indent: int = 0, format_options: FormatOptions | None = None) -> str:
    """Emit an assignment in canonical form.

    Issue #182: Includes leading and trailing comments.
    """
    indent_str = "  " * indent
    value_str = emit_value(assignment.value)

    # Determine if comments should be stripped
    strip_comments = format_options.strip_comments if format_options else False

    lines: list[str] = []

    # Issue #182: Emit leading comments
    if hasattr(assignment, "leading_comments"):
        lines.extend(_emit_leading_comments(assignment.leading_comments, indent, strip_comments))

    # Emit the assignment line with optional trailing comment
    assignment_line = f"{indent_str}{assignment.key}::{value_str}"
    if hasattr(assignment, "trailing_comment"):
        assignment_line += _emit_trailing_comment(assignment.trailing_comment, strip_comments)
    lines.append(assignment_line)

    return "\n".join(lines)


def emit_block(block: Block, indent: int = 0, format_options: FormatOptions | None = None) -> str:
    """Emit a block in canonical form.

    I2 Compliance: Skips children with Absent values.
    Issue #182: Includes leading comments.

    Args:
        block: Block AST node
        indent: Current indentation level
        format_options: Optional formatting configuration (Issue #193)
    """
    indent_str = "  " * indent
    strip_comments = format_options.strip_comments if format_options else False

    lines: list[str] = []

    # Issue #182: Emit leading comments
    if hasattr(block, "leading_comments"):
        lines.extend(_emit_leading_comments(block.leading_comments, indent, strip_comments))

    # M3: Emit block with optional target annotation [→§TARGET]
    block_line = f"{indent_str}{block.key}"
    if hasattr(block, "target") and block.target:
        block_line += f"[→§{block.target}]"
    block_line += ":"
    lines.append(block_line)

    # Issue #193: Optionally sort children by key
    children = list(block.children)
    if format_options and format_options.key_sorting:
        children = _sort_children_by_key(children)

    # Emit children
    # I2: Skip assignments with Absent values
    for child in children:
        if isinstance(child, Assignment):
            if is_absent(child.value):
                continue
            lines.append(emit_assignment(child, indent + 1, format_options))
        elif isinstance(child, Block):
            lines.append(emit_block(child, indent + 1, format_options))
        elif isinstance(child, Section):
            lines.append(emit_section(child, indent + 1, format_options))
        elif isinstance(child, Comment):
            comment_str = emit_comment(child, indent + 1, format_options)
            if comment_str:
                lines.append(comment_str)

    return "\n".join(lines)


def emit_section(section: Section, indent: int = 0, format_options: FormatOptions | None = None) -> str:
    """Emit a section in canonical form.

    Supports both plain numbers ("1", "2") and suffix forms ("2b", "2c").
    Includes optional bracket annotation if present.

    I2 Compliance: Skips children with Absent values.
    Issue #182: Includes leading comments.

    Args:
        section: Section AST node
        indent: Current indentation level
        format_options: Optional formatting configuration (Issue #193)
    """
    indent_str = "  " * indent
    strip_comments = format_options.strip_comments if format_options else False

    lines: list[str] = []

    # Issue #182: Emit leading comments
    if hasattr(section, "leading_comments"):
        lines.extend(_emit_leading_comments(section.leading_comments, indent, strip_comments))

    section_line = f"{indent_str}\u00a7{section.section_id}::{section.key}"
    if section.annotation:
        section_line += f"[{section.annotation}]"
    lines.append(section_line)

    # Issue #193: Optionally sort children by key
    children = list(section.children)
    if format_options and format_options.key_sorting:
        children = _sort_children_by_key(children)

    # Emit children
    # I2: Skip assignments with Absent values
    for child in children:
        if isinstance(child, Assignment):
            if is_absent(child.value):
                continue
            lines.append(emit_assignment(child, indent + 1, format_options))
        elif isinstance(child, Block):
            lines.append(emit_block(child, indent + 1, format_options))
        elif isinstance(child, Section):
            lines.append(emit_section(child, indent + 1, format_options))
        elif isinstance(child, Comment):
            comment_str = emit_comment(child, indent + 1, format_options)
            if comment_str:
                lines.append(comment_str)

    return "\n".join(lines)


def emit_meta(meta: dict[str, Any], format_options: FormatOptions | None = None) -> str:
    """Emit META block.

    I2 Compliance:
    - Skips fields with Absent values
    - Returns empty string if all fields are absent (no empty META: header)

    Args:
        meta: Dictionary of META fields
        format_options: Optional formatting configuration (Issue #193)
    """
    if not meta:
        return ""

    # Issue #193: Optionally sort keys alphabetically
    keys = list(meta.keys())
    if format_options and format_options.key_sorting:
        keys = sorted(keys)

    # I2: Collect non-absent fields first, then decide whether to emit header
    content_lines = []
    for key in keys:
        value = meta[key]
        # I2: Skip Absent values
        if is_absent(value):
            continue
        value_str = emit_value(value)
        content_lines.append(f"  {key}::{value_str}")

    # I2: If all fields were absent, return empty string (no header)
    if not content_lines:
        return ""

    return "META:\n" + "\n".join(content_lines)


def _apply_format_options(output: str, format_options: FormatOptions) -> str:
    """Apply post-emission formatting transformations.

    Issue #193: Auto-Format Options

    Args:
        output: Raw emitted OCTAVE content
        format_options: Formatting configuration

    Returns:
        Formatted OCTAVE content
    """
    lines = output.split("\n")

    # Apply trailing_whitespace handling
    # "strip" removes trailing whitespace; "preserve" keeps lines as-is
    if format_options.trailing_whitespace == "strip":
        lines = [line.rstrip() for line in lines]

    # Apply blank_line_normalize
    if format_options.blank_line_normalize:
        # Remove excessive blank lines (more than 2 consecutive)
        normalized_lines: list[str] = []
        blank_count = 0
        for line in lines:
            if line.strip() == "":
                blank_count += 1
                if blank_count <= 2:
                    normalized_lines.append(line)
            else:
                blank_count = 0
                normalized_lines.append(line)
        lines = normalized_lines

        # Ensure single blank line between top-level sections (starts with "§")
        # This is done by inserting blank lines where needed
        # MF1 Fix: Track "seen a section" separately from "prev line type"
        # so that child content doesn't reset the section tracking
        result_lines: list[str] = []
        seen_section = False  # Have we seen any section header?
        for line in lines:
            is_section_header = line.strip().startswith("§") and "::" in line
            # If this is a section and we've seen a previous section
            if is_section_header and seen_section:
                # Check if there's already a blank line before
                if result_lines and result_lines[-1].strip() != "":
                    result_lines.append("")  # Add blank line between sections
            result_lines.append(line)
            # Once we see a section, we've "seen" one (for subsequent sections)
            if is_section_header:
                seen_section = True
        lines = result_lines

    return "\n".join(lines)


def emit(doc: Document, format_options: FormatOptions | None = None) -> str:
    """Emit canonical OCTAVE from AST.

    Args:
        doc: Document AST
        format_options: Optional formatting configuration (Issue #193).
            If not provided, default behavior is used.

    Returns:
        Canonical OCTAVE text with explicit envelope,
        unicode operators, and deterministic formatting
    """
    lines = []

    # Issue #48 Phase 2: Emit grammar sentinel if present
    # Grammar sentinel must appear BEFORE the envelope
    if doc.grammar_version:
        lines.append(f"OCTAVE::{doc.grammar_version}")

    # Always emit explicit envelope
    lines.append(f"==={doc.name}===")

    # Emit META if present
    if doc.meta:
        lines.append(emit_meta(doc.meta, format_options))

    # Emit separator if present
    if doc.has_separator:
        lines.append("---")

    # Emit sections
    # I2 Compliance: Skip assignments with Absent values
    # Issue #182: Pass format_options for comment handling
    for section in doc.sections:
        if isinstance(section, Assignment):
            if is_absent(section.value):
                # I2: Absent fields are not emitted
                continue
            lines.append(emit_assignment(section, 0, format_options))
        elif isinstance(section, Block):
            lines.append(emit_block(section, 0, format_options))
        elif isinstance(section, Section):
            lines.append(emit_section(section, 0, format_options))

    # Issue #182: Emit document trailing comments before END envelope
    strip_comments = format_options.strip_comments if format_options else False
    if hasattr(doc, "trailing_comments") and doc.trailing_comments and not strip_comments:
        lines.extend(_emit_leading_comments(doc.trailing_comments, 0, strip_comments))

    # Always emit END envelope
    lines.append("===END===")

    output = "\n".join(lines)

    # Issue #193: Apply format options if provided
    if format_options:
        output = _apply_format_options(output, format_options)

    return output
