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

from octave_mcp.core.grammar import tier_normalize
from octave_mcp.core.grammar.cst import (
    Absent,
    Assignment,
    ASTNode,
    Block,
    Comment,
    Document,
    Envelope,
    HolographicValue,
    InlineMap,
    ListValue,
    LiteralZoneValue,
    NodeKind,
    Section,
)
from octave_mcp.core.grammar.visitor import (
    SymmetricVisitor,
    is_annotation_shape,
    is_expression_shape,
    is_identifier_shape,
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
    # GH#377 Strategy A (T8): span-aware preserve mode.
    # baseline_bytes MUST be normalize_content(raw).encode('utf-8') — i.e.
    # post-NFC bytes — so that start_byte/end_byte slices are valid.
    # HC-2: type is bytes | None (not str | None).
    baseline_bytes: bytes | None = None
    # When True, emit() uses dirty/repaired flags to decide per-node whether
    # to slice baseline_bytes or fall through to the re-emit path.
    # I1 (ONE_EMIT_CODEPATH): no parallel emit function.
    enable_preserve: bool = False


# ADR-0006 SR1-T1 Step 5 §4.5: identifier/annotation/expression shape
# predicates relocated to ``core/grammar/visitor.py`` (imported above as
# ``is_identifier_shape`` / ``is_annotation_shape`` / ``is_expression_shape``).
# The module-level regex constants used pre-Step-5 for the dequoting
# decision have been deleted from this module per the §4.5 fallback-
# discipline rule ("no PR ships a 'deleted regex' claim while a
# was_quoted-driven path remains in the visitor"). The shape helpers are
# NOT a fallback for missing ``was_quoted``; they are permanent
# type-safety guards (a value like ``"42"`` must stay quoted regardless
# of was_quoted state to avoid integer round-trip drift on I1).

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
# GH#301 expression-shape predicate is exported from visitor.py
# (``is_expression_shape``). See \u00a74.5 note above on the relocation.


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


def needs_quotes(value: Any, was_quoted: bool | None = None) -> bool:
    """Check if a string value needs quotes.

    ADR-0006 SR1-T1 Step 5 §4.5 G2: ``was_quoted`` is the source-quoting
    provenance recorded by the parser at Assignment construction. It is
    threaded through here so future audit-logging steps (Step 3) can
    consult the same decision rule the emitter uses.

    Decision rule (this PR preserves CURRENT canonical output — Step 3
    will log the dequoting choice via ``tier_normalize.log_repair``):

    * ``was_quoted is True``  → preserve quotes UNLESS dequoting is
      type-safe (shape predicate matches). HO directive: identifier-
      shaped strings still dequote ("TYPE::SPEC" canonical preference)
      so the 10 strict-xfails REMAIN xfailed at this PR.
    * ``was_quoted is False`` → identical to current behaviour (shape
      predicate decides).
    * ``was_quoted is None``  → no source provenance (programmatic
      construction); shape predicate decides. This is NOT a fallback
      for a deleted regex; the shape predicate is the canonical helper.

    Behavioural invariant: for every fixture parsed at main HEAD
    6adf13a, ``needs_quotes(value, was_quoted=<parser_signal>)`` returns
    the same boolean it returned at HEAD. This guarantees canonical
    output is byte-identical to baseline (smoke-test parity check).
    """
    if not isinstance(value, str):
        return False

    # Empty string needs quotes
    if not value:
        return True

    # Newlines/tabs must be escaped, so they must be quoted.
    # NOTE: Regex `$` matches before a trailing newline; the identifier
    # shape predicate uses `\\Z` to avoid treating "A\\n" as a bare identifier.
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
    if is_annotation_shape(value):
        return False

    # GH#301: Expression values with Unicode operators don't need quotes (§3b)
    if is_expression_shape(value):
        return False

    # If it's not a valid identifier, it needs quotes
    # This covers:
    # - Numbers (start with digit)
    # - Dashes (not allowed in identifiers)
    # - Special chars (spaces, colons, brackets, etc.)
    if not is_identifier_shape(value):
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
        if isinstance(item, str) and is_annotation_shape(item):
            return True
        non_absent_count += 1
    # GH#273: Any array with 3+ non-Absent plain items goes multi-line
    return non_absent_count >= 3


def _force_quote_inline_map_value(key: str, value_str: str, raw_value: Any) -> str:
    """Force-quote inline-map values for PATTERN/REGEX keys (GH#310).

    Applies the same _ALWAYS_QUOTE_KEYS logic used in emit_assignment() to
    inline-map emission paths, ensuring PATTERN/REGEX values are always quoted
    regardless of whether needs_quotes() would normally leave them bare.

    Args:
        key: The inline-map key (e.g., "PATTERN", "REGEX").
        value_str: The already-emitted value string.
        raw_value: The original AST value (to check type and escape).

    Returns:
        The value string, force-quoted if key is in _ALWAYS_QUOTE_KEYS.
    """
    if key in _ALWAYS_QUOTE_KEYS and isinstance(raw_value, str) and not value_str.startswith('"'):
        escaped = raw_value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
        return f'"{escaped}"'
    return value_str


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
                v_str = emit_value(v, indent + 1)
                # GH#310: Force-quote PATTERN/REGEX values in inline-map (I1)
                v_str = _force_quote_inline_map_value(k, v_str, v)
                inline_pairs.append(f"{k}::{v_str}")
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


def emit_value(value: Any, indent: int = 0, was_quoted: bool | None = None) -> str:
    """Emit a value in canonical form.

    I2 Compliance:
    - Absent values raise ValueError (caller must filter before calling)
    - None values return "null" (explicitly empty)
    - ListValue and InlineMap filter out Absent items/values internally

    GH#267: Multi-line emission for structured arrays.
    Arrays containing KEY::VALUE pairs or nested arrays emit multi-line
    with 2-space indentation. Simple flat arrays remain single-line.

    ADR-0006 SR1-T1 Step 5 §4.5 G2: ``was_quoted`` carries the source-
    quoting provenance from the parser. Threaded into ``needs_quotes``
    so Step 3 can wire a single ``tier_normalize.log_repair`` call at
    this seam. Current PR preserves canonical output (HO directive:
    10 strict-xfails REMAIN xfailed). For value types other than ``str``
    the parameter has no effect.

    Args:
        value: The AST value to emit.
        indent: Current indentation level (used for multi-line arrays).
        was_quoted: Source-quoting provenance for the value (parser-
            populated on Assignment; None for programmatic constructions
            or recursive descent into nested value types).

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
        if needs_quotes(value, was_quoted=was_quoted):
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
        pairs = []
        for k, v in value.pairs.items():
            if is_absent(v):
                continue
            v_str = emit_value(v, indent)
            # GH#310: Force-quote PATTERN/REGEX values in inline-map (I1)
            v_str = _force_quote_inline_map_value(k, v_str, v)
            pairs.append(f"{k}::{v_str}")
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

    # ADR-0006 SR1-T1 Step 5 §4.5 G2: thread the parser-recorded source-
    # quoting provenance into emit_value. Behaviour preserved at this
    # PR — Step 3 will wire tier_normalize.log_repair at the same seam.
    value_str = emit_value(assignment.value, indent, was_quoted=assignment.was_quoted)

    # GH#310: PATTERN/REGEX values must always be quoted for lexical matching fidelity (I1).
    # The needs_quotes() heuristic returns False for single bare-word identifiers, but
    # PATTERN and REGEX values are string literals that must preserve their quoted form.
    if assignment.key in _ALWAYS_QUOTE_KEYS and isinstance(assignment.value, str) and not value_str.startswith('"'):
        escaped = assignment.value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
        value_str = f'"{escaped}"'

    # ADR-0006 SR1-T1 Step 3 §3a: precise was_quoted-driven instrumentation
    # of identifier-dequoting decisions. When the parser recorded the value
    # as originally quoted (was_quoted=True) AND the emitter chose to emit
    # bare (value_str does not start with '"'), the canonical re-emit has
    # syntactically altered the source — log it via the central
    # tier_normalize channel so I4 (TRANSFORM_AUDITABILITY) holds.
    # Logging is conditioned on the ContextVar set by mcp/write.py
    # (tier_normalize.active(repair_log)); outside that context the call
    # is a no-op, preserving today's behaviour for callers that do not
    # opt in to the audit channel.
    if assignment.was_quoted is True and isinstance(assignment.value, str) and not value_str.startswith('"'):
        tier_normalize.log_repair_if_active(
            tier_normalize.RULE_IDENTIFIER_DEQUOTE,
            before=f'{assignment.key}::"{assignment.value}"',
            after=f"{assignment.key}::{value_str}",
        )

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
                # GH#346: LiteralZoneValue in nested META needs special
                # handling -- fence markers must be on their own lines with
                # matching indentation (mirrors emit_assignment pattern).
                if isinstance(nested_value, LiteralZoneValue):
                    indent_str = "    "  # indent level 2
                    content_lines.append(f"{indent_str}{nested_key}::")
                    opening = f"{indent_str}{nested_value.fence_marker}"
                    if nested_value.info_tag:
                        opening += nested_value.info_tag
                    content_lines.append(opening)
                    if nested_value.content:
                        content_lines.append(nested_value.content)
                    content_lines.append(f"{indent_str}{nested_value.fence_marker}")
                else:
                    nested_value_str = emit_value(nested_value, indent=2)
                    content_lines.append(f"    {nested_key}::{nested_value_str}")
        # GH#346: LiteralZoneValue in META needs special handling --
        # fence markers must be on their own lines with matching
        # indentation, not inline with the key (which produces invalid
        # OCTAVE that the lexer rejects as E006).
        elif isinstance(value, LiteralZoneValue):
            indent_str = "  "  # indent level 1
            content_lines.append(f"{indent_str}{key}::")
            opening = f"{indent_str}{value.fence_marker}"
            if value.info_tag:
                opening += value.info_tag
            content_lines.append(opening)
            if value.content:
                content_lines.append(value.content)
            content_lines.append(f"{indent_str}{value.fence_marker}")
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


def _emit_envelope(
    envelope: Envelope,
    *,
    baseline_bytes: bytes | None,
    enable_preserve: bool,
    format_options: FormatOptions | None,
    strip_comments: bool,
) -> str:
    """Emit a single additional envelope (GH #420 Option D).

    Mirrors the envelope-scoped portion of ``emit()`` for the
    ``Document`` (===NAME=== header, optional META, sections, optional
    trailing comments, ===END=== footer) but operates on an
    ``Envelope`` node.  Returns the envelope's bytes as one ``\\n``-
    separated string with NO trailing newline (the caller joins envelopes
    with ``\\n``).

    Strategy A preserve mode (#420 AC1): when ``enable_preserve=True``
    AND ``baseline_bytes is not None`` AND the envelope is clean
    (``not dirty``) AND has valid byte spans
    (``start_byte``/``end_byte``), slice the WHOLE envelope verbatim
    from baseline.  This is the per-envelope analogue of the per-section
    slice path in ``emit()``.  Any mutation to the envelope (currently
    out-of-scope for v1.13.0 via changes_mode, per HO Q3) would set
    ``envelope.dirty=True`` and force canonical re-emit.

    Re-emit path: produces the canonical bytes from the AST using the
    same ``emit_meta`` / ``emit_assignment`` / ``emit_block`` /
    ``emit_section`` helpers that ``emit()`` uses for the primary
    Document.  Layout is byte-identical to a single-envelope canonical
    document containing the same content.
    """
    # Slice path: clean envelope with valid spans under preserve mode.
    if (
        enable_preserve
        and baseline_bytes is not None
        and not envelope.dirty
        and envelope.start_byte is not None
        and envelope.end_byte is not None
    ):
        # R4 structural integrity check (I4 audit trail; ADR §5 R4).
        assert 0 <= envelope.start_byte < envelope.end_byte <= len(baseline_bytes), (
            f"Envelope {envelope.name!r} span "
            f"[{envelope.start_byte}:{envelope.end_byte}] out of bounds "
            f"for baseline ({len(baseline_bytes)} bytes). "
            "NFC contract violated."
        )
        sliced_text = baseline_bytes[envelope.start_byte : envelope.end_byte].decode("utf-8")
        # Trim a single trailing newline so the caller's "\n".join
        # produces exactly one boundary newline between this envelope
        # and the next.
        return sliced_text.removesuffix("\n")

    # Re-emit path: produce canonical bytes from the envelope AST.
    env_lines: list[str] = []
    env_lines.append(f"==={envelope.name}===")

    if envelope.meta:
        env_lines.append(emit_meta(envelope.meta, format_options))

    if envelope.has_separator:
        env_lines.append("---")

    for section in envelope.sections:
        # Per-section slice path inside an additional envelope: same
        # contract as the primary Document loop.  An unchanged section
        # whose spans are valid relative to ``baseline_bytes`` slices
        # verbatim; otherwise canonical re-emit.
        if (
            enable_preserve
            and baseline_bytes is not None
            and not section.dirty
            and not section.repaired
            and not getattr(section, "body_dirty", False)
            and section.start_byte is not None
            and section.end_byte is not None
            and 0 <= section.start_byte < section.end_byte <= len(baseline_bytes)
        ):
            sliced_text = baseline_bytes[section.start_byte : section.end_byte].decode("utf-8")
            env_lines.append(sliced_text.removesuffix("\n"))
            continue

        if isinstance(section, Assignment):
            if is_absent(section.value):
                continue
            env_lines.append(emit_assignment(section, 0, format_options))
        elif isinstance(section, Block):
            env_lines.append(emit_block(section, 0, format_options))
        elif isinstance(section, Section):
            env_lines.append(emit_section(section, 0, format_options))

    if envelope.trailing_comments and not strip_comments:
        env_lines.extend(_emit_leading_comments(envelope.trailing_comments, 0, strip_comments))

    env_lines.append("===END===")
    return "\n".join(env_lines)


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

    # GH#377 Strategy A (T8): extract preserve-mode parameters once.
    # I1 (ONE_EMIT_CODEPATH): all paths use the same emit() function.
    # The slice path is conditionally activated per-node via dirty flags;
    # the re-emit path is the existing emit_* helpers, unchanged.
    _enable_preserve = bool(format_options and format_options.enable_preserve)
    _baseline_bytes: bytes | None = format_options.baseline_bytes if format_options else None

    # Emit META if present.
    # GH#377 Strategy A: per-key META slice. When enable_preserve=True,
    # we have a single META block region (meta_start_byte..meta_end_byte).
    # Keys not in meta_dirty (or meta_dirty[key]==False) are sliced verbatim;
    # only the dirty keys are re-emitted through emit_meta.
    #
    # Implementation note: per-key META slicing requires individual key
    # byte spans. Those spans are NOT yet populated by the parser in this
    # PR — the parser populates meta_start_byte/meta_end_byte (block-level)
    # but not per-key spans. Until per-key spans are available, we fall back
    # to full META block slicing when NO key is dirty, and full META re-emit
    # when ANY key is dirty. This is correct and safe: the diff footprint for
    # a single-key META change equals the full META block size, which for
    # typical documents is well within the 0.5% threshold.
    if doc.meta:
        meta_sliced = False
        # CRS BLOCKER (PR #418): also check `doc.dirty` (whole-META
        # replacement signal from cli/main.py) and inspect meta_dirty
        # over BOTH the current doc.meta keys AND any keys that were
        # deleted (which are absent from doc.meta but still recorded
        # as dirty in meta_dirty). Without the union, a delete-only
        # mutation would slice the OLD META block from baseline and
        # silently re-introduce the deleted key.
        _meta_dirty_keys = set(doc.meta_dirty.keys())
        _meta_live_keys = set(doc.meta.keys())
        _any_meta_dirty = any(doc.meta_dirty.get(k, False) for k in _meta_dirty_keys | _meta_live_keys)
        if (
            _enable_preserve
            and _baseline_bytes is not None
            and doc.meta_start_byte is not None
            and doc.meta_end_byte is not None
            and not getattr(doc, "dirty", False)
            and not _any_meta_dirty
        ):
            # No META key is dirty — slice entire META block verbatim.
            # R4 structural integrity check (I4 audit trail).
            assert 0 <= doc.meta_start_byte < doc.meta_end_byte <= len(_baseline_bytes), (
                f"META span [{doc.meta_start_byte}:{doc.meta_end_byte}] out of bounds "
                f"for baseline ({len(_baseline_bytes)} bytes). NFC contract violated."
            )
            # Strip exactly ONE trailing newline for consistency with
            # emit_meta() output (which does not include a trailing newline;
            # "\n".join handles it).  Cubic P2: `rstrip("\n")` would consume
            # ALL trailing newlines, silently dropping trail-anchored blank
            # lines that belong inside the META block span (ADR §3 blank-line
            # policy). `removesuffix` strips at most one — the separator that
            # "\n".join below re-adds.
            lines.append(_baseline_bytes[doc.meta_start_byte : doc.meta_end_byte].decode("utf-8").removesuffix("\n"))
            meta_sliced = True
        if not meta_sliced:
            lines.append(emit_meta(doc.meta, format_options))

    # Emit separator if present
    if doc.has_separator:
        lines.append("---")

    # Emit sections
    # I2 Compliance: Skip assignments with Absent values
    # Issue #182: Pass format_options for comment handling
    # GH#377 Strategy A (T8): span-aware per-node dispatch.
    # For each node: if enable_preserve=True AND baseline_bytes is set AND
    # the node is clean (not dirty, not repaired) AND has valid byte spans,
    # slice the baseline bytes verbatim (the slice path).
    # Otherwise fall through to the existing emit_* helpers (the re-emit path).
    # TWO TRUTHS, NEVER COMPARED (ADR §5, CDV P0-2, I3):
    #   - Slice path: returns post-NFC source bytes verbatim.
    #   - Re-emit path: produces canonical bytes from the AST.
    # These two outputs are never compared; they are alternate routes that
    # cannot mix for the same node.
    for section in doc.sections:
        # GH#377 Strategy A: try the slice path first.
        #
        # CRS BLOCKER (PR #418): `body_dirty=True` means the parent's
        # children have been mutated even though the parent's header is
        # unchanged. Slicing the whole node here would emit the OLD
        # baseline bytes for the parent — INCLUDING its stale children —
        # silently discarding the user's change to a child. Force the
        # re-emit path (emit_block / emit_section) whenever body_dirty is
        # set so canonical re-emission picks up the mutated children.
        #
        # This is the conservative Option A: when body_dirty, the entire
        # subtree re-emits canonically. A future PR may add child-level
        # span dispatch (Option B) — recursive descent that slices the
        # header from baseline and dispatches each child individually —
        # but that is a larger architectural change.
        if (
            _enable_preserve
            and _baseline_bytes is not None
            and not section.dirty
            and not section.repaired
            and not getattr(section, "body_dirty", False)
            and section.start_byte is not None
            and section.end_byte is not None
        ):
            # R4 structural integrity check: validate bounds.
            # This is NOT a parse∘emit identity assertion — it is a bounds
            # check that guards against corrupt span data. (I4, ADR §5 R4)
            assert 0 <= section.start_byte < section.end_byte <= len(_baseline_bytes), (
                f"Node {type(section).__name__} span [{section.start_byte}:{section.end_byte}] "
                f"out of bounds for baseline ({len(_baseline_bytes)} bytes). "
                "NFC contract violated."
            )
            # Strip exactly ONE trailing newline from the sliced content.
            # The byte span ends at the next section's start_byte, which sits
            # immediately after a single '\n' separator. The "\n".join(lines)
            # call below re-adds that separator, so we must remove exactly
            # one to avoid double newlines between sliced sections.
            # Cubic P2: `rstrip("\n")` would consume ALL trailing newlines,
            # silently dropping trail-anchored blank lines that belong inside
            # the section's end_byte (ADR §3 blank-line policy — an I1
            # violation on clean nodes). `removesuffix` strips at most one.
            sliced_text = _baseline_bytes[section.start_byte : section.end_byte].decode("utf-8")
            lines.append(sliced_text.removesuffix("\n"))
            continue

        # Re-emit path: produce canonical output from AST.
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

    # GH #420 Option D: emit additional top-level envelopes (#2..N).
    # Single-envelope documents have ``additional_envelopes == []`` (the
    # dataclass default), so this branch is a no-op there.  For each
    # sibling envelope we either slice it verbatim from baseline (preserve
    # mode, clean envelope, valid spans) or re-emit it canonically.
    #
    # GH #420 CE rework cycle 2 (PR #451): Option A — explicit verbatim
    # byte assembly.  Cycle 1's strip-then-``"\n".join(...)`` approach
    # collapsed distinct accepted source boundaries (raw ``"\n"`` vs raw
    # ``"\n\n"`` BOTH became ``""`` after trimming, producing identical
    # canonical-blank-line output for both — an I1 SYNTACTIC_FIDELITY
    # violation: canon is no longer bijective on the inter-envelope
    # trivia space).
    #
    # The fix is to emit the captured ``pre_trivia`` byte band VERBATIM
    # — every byte between the previous envelope's ``===END===`` end_byte
    # and the next envelope's ``===NAME===`` start_byte threads through
    # the emitter unchanged.  We exit the ``"\n".join`` regime for the
    # multi-envelope tail and build the output by direct concatenation:
    #
    #   primary_output = "\n".join(lines)            # envelope #1 (no \n suffix)
    #   for env in additional_envelopes:
    #       primary_output += boundary_bytes(env)    # raw band OR canonical "\n\n"
    #       primary_output += env_text(env)          # ===NAME===...===END=== (no \n suffix)
    #
    # ``boundary_bytes`` is the raw ``pre_trivia`` slice under preserve
    # mode when the band is well-formed (including empty bands, which
    # signal zero-byte adjacency and emit no separator).  Otherwise we
    # fall back to ``"\n\n"`` — the canonical single-blank-line separator
    # — which matches pre-rework canonical-form behaviour exactly:
    # envelope #1's last element ``===END===`` is followed by ``\n`` (the
    # ``\n`` between ===END=== line and the blank line) and then ``\n``
    # (the blank line itself) then ``===NAME===``.
    additional_envelopes = getattr(doc, "additional_envelopes", None) or []

    output = "\n".join(lines)
    for envelope in additional_envelopes:
        boundary: str
        # GH #420 cubic-dev-ai P2 rework (PR #451): fail-fast on invalid
        # pre_trivia byte spans under preserve mode.  Pre-rework: the
        # combined predicate ``and 0 <= start <= end <= len(baseline)``
        # silently fell through to the canonical ``"\n\n"`` separator on
        # ANY failure mode — including the impossible-AST case where
        # spans are SET but corrupt (start > end, end > len).  That
        # silent degradation masked AST corruption rather than surfacing
        # it (PROD::I4 TRANSFORM_AUDITABILITY violation; bugs become
        # silent canonical-form drift instead of explicit errors).
        #
        # Post-rework: separate the "spans not set" (None → legitimate
        # non-preserve fallback) case from the "spans set but invalid"
        # (corrupt AST → must raise) case.
        _pt_start = envelope.pre_trivia_start_byte
        _pt_end = envelope.pre_trivia_end_byte
        _spans_set = _pt_start is not None and _pt_end is not None
        if _enable_preserve and _baseline_bytes is not None and _spans_set:
            # Validate bounds.  We've already established both spans are
            # non-None; mypy narrows them here.
            assert _pt_start is not None and _pt_end is not None  # narrow for mypy
            _baseline_len = len(_baseline_bytes)
            if not (0 <= _pt_start <= _pt_end <= _baseline_len):
                raise ValueError(
                    f"Invalid pre_trivia byte span on envelope "
                    f"{getattr(envelope, 'name', '<unnamed>')!r}: "
                    f"start={_pt_start}, end={_pt_end}, "
                    f"baseline_len={_baseline_len}. "
                    f"Required: 0 <= start <= end <= baseline_len. "
                    f"This indicates AST corruption — pre_trivia spans "
                    f"set but bounds-invalid is an impossible state for "
                    f"a parser-produced Envelope under preserve mode."
                )
            # Preserve mode with captured band: the band IS the boundary.
            # Empty band (start == end) means the source had zero bytes
            # between ===END=== and ===NAME=== (zero-byte adjacency,
            # accepted by the lexer) — emit no separator at all.  Any
            # other width (1 byte, 2 bytes, "\n\n  \n", etc.) is emitted
            # byte-for-byte.  No strip, no join, no transformation.
            boundary = _baseline_bytes[_pt_start:_pt_end].decode("utf-8")
        else:
            # Canonical / non-preserve / spans-not-set fallback: single
            # blank line between envelopes (one ``\n`` closes the previous
            # ===END=== line, second ``\n`` is the blank line).  This
            # path is reached when (a) preserve mode is off, (b) no
            # baseline_bytes were supplied, or (c) the envelope's
            # pre_trivia spans were never populated (both None) — all
            # legitimate non-preserve fallbacks.
            boundary = "\n\n"

        env_text = _emit_envelope(
            envelope,
            baseline_bytes=_baseline_bytes,
            enable_preserve=_enable_preserve,
            format_options=format_options,
            strip_comments=strip_comments,
        )
        # ``env_text`` is a fully-formed envelope text block
        # (``===NAME===\n...===END===``) with no trailing newline.
        # Direct concatenation — NO ``"\n".join`` to introduce a phantom
        # newline between boundary and env_text.
        output += boundary + env_text

    # Issue #193: Apply format options if provided
    if format_options:
        output = _apply_format_options(output, format_options)

    # GH#284: Ensure POSIX trailing newline for pre-commit compatibility
    if not output.endswith("\n"):
        output += "\n"

    return output


# ---------------------------------------------------------------------------
# CanonicalEmitter — CST visitor seam (ADR-0006 SR1-T1 Step 5)
# ---------------------------------------------------------------------------
#
# Per design §2.2 the emitter is a ``Visitor[str]`` consumer of the CST.
# The class below is the structural seam: it subclasses
# ``SymmetricVisitor[str]`` (which is the visit_T mixin landed at Step 4)
# and dispatches each node kind through the existing module-level
# ``emit_*`` helpers. The wire output is byte-identical to the
# pre-Step-5 ``emit()`` function — Step 5 is a structural change, NOT a
# canonical-output change. The 10 strict-xfails REMAIN xfailed; Step 3
# is the step that flips them via ``tier_normalize.log_repair``.
#
# Why a thin class over a full re-implementation: the existing emit_*
# helpers carry years of issue-numbered branches (LiteralZoneValue,
# YAML frontmatter, META, comments, multi-line lists, etc.). Re-
# implementing them in visit_* methods would multiply review risk and
# canonical-output drift surface for zero behaviour change. The class
# provides the seam Step 3 needs (a single point that consumes
# ``assignment.was_quoted`` from CST nodes); the per-node text is still
# produced by the proven helpers.
#
# Future steps may inline the helpers into visit_* methods once Step 3's
# audit-log wiring has settled.


class CanonicalEmitter(SymmetricVisitor[str]):
    """Visitor[str] consumer that emits canonical OCTAVE bytes from a CST.

    Each ``visit_<node>`` method delegates to the matching module-level
    ``emit_*`` helper, preserving the canonical-output guarantees of the
    pre-Step-5 emitter. ``visit()`` is the fallback dispatcher used when
    the caller has an unknown-kind ``ASTNode``.

    Attributes:
        format_options: Optional ``FormatOptions`` applied to the final
            output (post-emission transformations such as trailing-
            whitespace strip and blank-line normalisation). Passed to
            each ``emit_*`` helper.
    """

    def __init__(self, format_options: FormatOptions | None = None) -> None:
        self.format_options = format_options

    def visit_assignment(self, node: Assignment, /) -> str:
        return emit_assignment(node, 0, self.format_options)

    def visit_block(self, node: Block, /) -> str:
        return emit_block(node, 0, self.format_options)

    def visit_section(self, node: Section, /) -> str:
        return emit_section(node, 0, self.format_options)

    def visit_document(self, node: Document, /) -> str:
        return emit(node, self.format_options)

    def visit_comment(self, node: Comment, /) -> str:
        return emit_comment(node, 0, self.format_options)

    def visit(self, node: ASTNode, /) -> str:
        """Dispatch on ``node.kind`` to the matching visit_<node> method.

        Per design §2.2 the visitor dispatches on the structural
        ``NodeKind`` discriminator rather than ``isinstance`` chains.
        Unknown kinds fall through to ``str(node)`` (defensive — should
        never occur in well-formed CSTs).
        """
        kind = getattr(node, "kind", None)
        if kind is NodeKind.DOCUMENT:
            return self.visit_document(node)  # type: ignore[arg-type]
        if kind is NodeKind.SECTION:
            return self.visit_section(node)  # type: ignore[arg-type]
        if kind is NodeKind.BLOCK:
            return self.visit_block(node)  # type: ignore[arg-type]
        if kind is NodeKind.ASSIGNMENT:
            return self.visit_assignment(node)  # type: ignore[arg-type]
        if kind is NodeKind.COMMENT:
            return self.visit_comment(node)  # type: ignore[arg-type]
        return str(node)
