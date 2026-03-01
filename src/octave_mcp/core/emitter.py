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
    LiteralZoneValue,
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


# GH#299: Include hyphens to match lexer's _is_valid_identifier_char which allows '-'.
# Negative lookbehind (?<!-) prevents trailing hyphen (mirrors lexer's trailing-hyphen strip).
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-]*(?<!-)\Z")

# Issue #248, GH#300: Pattern for NAME<qualifier> annotation syntax (§2c)
# Must match lexer rules: qualifier starts with letter/underscore, body is identifier chars.
# GH#300: Extended to support multi-arg qualifiers (comma-separated) like NEVER<A,B,C>
# and empty qualifiers like FOO<> (produced by parser for empty constructor brackets).
ANNOTATION_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-]*(?<!-)<([A-Za-z_]([A-Za-z0-9_,]*[A-Za-z0-9_])?)?>\Z")

# GH#310: Keys whose values must always be quoted (string literals for lexical matching).
# PATTERN and REGEX values are match targets in §4::INTERACTION_RULES GRAMMAR context.
# Emitting them bare violates I1 (SYNTACTIC_FIDELITY) because the quotes carry semantic
# meaning (they denote string literals, not identifiers).
_ALWAYS_QUOTE_KEYS: frozenset[str] = frozenset({"PATTERN", "REGEX"})

# Issue #181: Variable pattern for $VAR, $1:name placeholders
# Variables start with $ and contain alphanumeric, underscore, or colon
VARIABLE_PATTERN = re.compile(r"^\$[A-Za-z0-9_:]+\Z")

# GH#301: Pattern for expression values containing spec-defined Unicode operators.
# Per §3b::QUOTING_RULES, defined operators in expressions (A->B, X|Y, P&Q) are exempt
# from quoting. Unicode operators: ⊕ (U+2295), ⧺ (U+29FA), ⇌ (U+21CC), ∧ (U+2227),
# ∨ (U+2228), → (U+2192), and @ for location context.
# Matches: identifier segments connected by one or more Unicode operators.
_UNICODE_OPS = "\u2295\u29fa\u21cc\u2227\u2228\u2192@"
EXPRESSION_PATTERN = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_.\-]*(?<!-)([" + _UNICODE_OPS + r"][A-Za-z_][A-Za-z0-9_.\-]*(?<!-))+\Z"
)


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

    # Issue #248: NAME<qualifier> annotations don't need quotes (§2c)
    if ANNOTATION_PATTERN.match(value):
        return False

    # GH#301: Expression values with Unicode operators don't need quotes (§3b)
    if EXPRESSION_PATTERN.match(value):
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


def _needs_multiline(value: ListValue) -> bool:
    """Determine if a ListValue needs multi-line emission (GH#267, GH#273).

    Returns True when:
    - The array contains InlineMap items (KEY::VALUE pairs) (GH#267)
    - The array contains nested ListValue items (sub-arrays) (GH#267)
    - The array has 3 or more non-Absent items (GH#273)

    Arrays with 1-2 items remain single-line for compactness.
    The 3-item threshold improves readability for string-only arrays
    that would otherwise produce 300+ character lines.
    """
    non_absent_count = 0
    for item in value.items:
        if is_absent(item):
            continue
        if isinstance(item, InlineMap):
            # GH#267 rework: Only count InlineMaps with non-Absent pairs.
            # All-Absent InlineMaps are filtered during emission, so they
            # shouldn't trigger multi-line mode (I1 idempotency).
            if any(not is_absent(v) for v in item.pairs.values()):
                return True
            continue
        if isinstance(item, ListValue):
            return True
        # GH#304: Annotation items (NAME<qualifier>) are structured content
        # that should always trigger multi-line emission, regardless of count.
        # This fixes inconsistency where 2-item annotation lists stayed single-line
        # while 3-item ones went multi-line.
        if isinstance(item, str) and ANNOTATION_PATTERN.match(item):
            return True
        non_absent_count += 1
    # GH#273: Any array with 3+ non-Absent plain items goes multi-line
    return non_absent_count >= 3


def _emit_multiline_list(value: ListValue, indent: int = 0) -> str:
    """Emit a ListValue in multi-line format with 2-space indentation (GH#267).

    Used for arrays containing structured content (InlineMap or nested ListValue).
    Each item gets its own line with proper indentation. Nested arrays recurse
    with increased indent level.

    Format:
        [
          ITEM1,
          ITEM2
        ]

    Args:
        value: The ListValue to emit.
        indent: Current indentation level for the opening bracket.

    Returns:
        Multi-line string representation of the array.
    """
    child_indent_str = "  " * (indent + 1)
    close_indent_str = "  " * indent

    parts: list[str] = []
    for item in value.items:
        if is_absent(item):
            continue
        if isinstance(item, InlineMap):
            # Issue #246: InlineMap items within lists emit as bare k::v pairs
            # In multi-line mode, each pair gets its own line
            inline_pairs = []
            for k, v in item.pairs.items():
                if is_absent(v):
                    continue
                inline_pairs.append(f"{k}::{emit_value(v, indent + 1)}")
            # GH#267 fix: skip InlineMap items where all pairs are Absent.
            # An empty inline_pairs list would produce an empty string in
            # parts, emitting a blank line that breaks emit-parse idempotency.
            if inline_pairs:
                parts.append(",".join(inline_pairs))
        else:
            parts.append(emit_value(item, indent + 1))

    # GH#267 fix: if all items were filtered (Absent), return empty array
    if not parts:
        return "[]"

    # Build multi-line output: opening [, items with trailing commas, closing ]
    lines = ["["]
    for i, part in enumerate(parts):
        comma = "," if i < len(parts) - 1 else ""
        lines.append(f"{child_indent_str}{part}{comma}")
    lines.append(f"{close_indent_str}]")
    return "\n".join(lines)


def emit_value(value: Any, indent: int = 0) -> str:
    """Emit a value in canonical form.

    I2 Compliance:
    - Absent values raise ValueError (caller must filter before calling)
    - None values return "null" (explicitly empty)
    - ListValue and InlineMap filter out Absent items/values internally

    GH#267: Multi-line emission for structured arrays.
    Arrays containing KEY::VALUE pairs or nested arrays emit multi-line
    with 2-space indentation. Simple flat arrays remain single-line.

    Args:
        value: The AST value to emit.
        indent: Current indentation level (used for multi-line arrays).

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
        # GH#267: Check if this array needs multi-line emission
        if _needs_multiline(value):
            return _emit_multiline_list(value, indent)
        # Simple flat array: single-line emission
        parts: list[str] = []
        for item in value.items:
            if is_absent(item):
                continue
            # GH#267: Skip all-Absent InlineMaps (same guard as multi-line path)
            if isinstance(item, InlineMap) and not any(not is_absent(v) for v in item.pairs.values()):
                continue
            parts.append(emit_value(item, indent))
        return f"[{','.join(parts)}]"
    elif isinstance(value, InlineMap):
        # I2: Filter out pairs with Absent values before emission
        # Standalone InlineMap (not inside a list) keeps its brackets
        pairs = [f"{k}::{emit_value(v, indent)}" for k, v in value.pairs.items() if not is_absent(v)]
        return f"[{','.join(pairs)}]"
    elif isinstance(value, HolographicValue):
        # M3: Emit holographic pattern using raw_pattern for I1 fidelity
        # The raw_pattern preserves the original syntax: ["example"∧CONSTRAINT→§TARGET]
        return value.raw_pattern
    elif isinstance(value, LiteralZoneValue):
        # Issue #235: Verbatim emission -- no escaping, no normalization (I1)
        parts = [value.fence_marker]
        if value.info_tag:
            parts.append(value.info_tag)
        parts.append("\n")
        parts.append(value.content)
        if value.content and not value.content.endswith("\n"):
            parts.append("\n")
        parts.append(value.fence_marker)
        return "".join(parts)
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
    Issue #235: Special handling for LiteralZoneValue -- fence markers get
    indent, content lines are verbatim (no indent added).
    """
    indent_str = "  " * indent

    # Determine if comments should be stripped
    strip_comments = format_options.strip_comments if format_options else False

    lines: list[str] = []

    # Issue #182: Emit leading comments
    if hasattr(assignment, "leading_comments"):
        lines.extend(_emit_leading_comments(assignment.leading_comments, indent, strip_comments))

    # Issue #235: Literal zone values need special indentation handling
    if isinstance(assignment.value, LiteralZoneValue):
        lzv = assignment.value
        # Key line: KEY:: (value starts on next line)
        lines.append(f"{indent_str}{assignment.key}::")
        # Opening fence with indent
        opening = f"{indent_str}{lzv.fence_marker}"
        if lzv.info_tag:
            opening += lzv.info_tag
        lines.append(opening)
        # Content lines: verbatim, NO indent added
        if lzv.content:
            lines.append(lzv.content)
        # Closing fence with indent
        lines.append(f"{indent_str}{lzv.fence_marker}")
        return "\n".join(lines)

    value_str = emit_value(assignment.value, indent)

    # GH#310: PATTERN/REGEX values must always be quoted for lexical matching fidelity (I1).
    # The needs_quotes() heuristic returns False for single bare-word identifiers, but
    # PATTERN and REGEX values are string literals that must preserve their quoted form.
    if assignment.key in _ALWAYS_QUOTE_KEYS and isinstance(assignment.value, str) and not value_str.startswith('"'):
        escaped = assignment.value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
        value_str = f'"{escaped}"'

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
            # Issue #259: Bare-key literal zone child (key="") produced by the parser
            # when a fenced literal zone appears directly in the block body (no key prefix).
            # Emit just the fence block lines without a key:: header line.
            if child.key == "" and isinstance(child.value, LiteralZoneValue):
                child_indent_str = "  " * (indent + 1)
                lzv = child.value
                opening = f"{child_indent_str}{lzv.fence_marker}"
                if lzv.info_tag:
                    opening += lzv.info_tag
                lines.append(opening)
                if lzv.content:
                    lines.append(lzv.content)
                lines.append(f"{child_indent_str}{lzv.fence_marker}")
            else:
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
        # GH#287 P3: Handle nested dict values as OCTAVE block structures
        if isinstance(value, dict):
            content_lines.append(f"  {key}:")
            # Optionally sort nested keys
            nested_keys = list(value.keys())
            if format_options and format_options.key_sorting:
                nested_keys = sorted(nested_keys)
            for nested_key in nested_keys:
                nested_value = value[nested_key]
                if is_absent(nested_value):
                    continue
                nested_value_str = emit_value(nested_value, indent=2)
                content_lines.append(f"    {nested_key}::{nested_value_str}")
        else:
            value_str = emit_value(value, indent=1)
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

    # Issue #234: Zone 2 (Preserving Container) - prepend YAML frontmatter
    # when present on Document. Frontmatter is byte-for-byte preserved (no
    # normalization). Must appear before grammar sentinel and envelope.
    if doc.raw_frontmatter is not None and doc.raw_frontmatter.strip():
        lines.append("---")
        lines.append(doc.raw_frontmatter)
        lines.append("---")
        lines.append("")  # blank line separator between frontmatter and envelope

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

    # GH#284: Ensure POSIX trailing newline for pre-commit compatibility
    if not output.endswith("\n"):
        output += "\n"

    return output
