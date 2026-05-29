"""MCP tool for OCTAVE write (GH#51 Tool Consolidation).

Implements octave_write tool - replaces octave_create + octave_amend with:
- Unified write with content XOR changes parameter model (or neither for normalize)
- Normalize mode: omit both content and changes to re-emit existing file in canonical form
- Tri-state semantics for changes: absent=no-op, {"$op":"DELETE"}=remove, null=empty
- base_hash CAS guard in BOTH modes when file exists
- Unified envelope: status, path, canonical_hash, corrections, diff, errors, validation_status
- I1 (Syntactic Fidelity): Normalizes to canonical form
- I2 (Deterministic Absence): Tri-state semantics
- I4 (Auditability): Returns corrections and diff
- I5 (Schema Sovereignty): Always returns validation_status
"""

import hashlib
import os
import re
import tempfile
from difflib import unified_diff
from pathlib import Path
from typing import Any

from octave_mcp.core.emitter import emit
from octave_mcp.core.gbnf_compiler import GBNFCompiler
from octave_mcp.core.grammar import ParserError, parse, parse_with_warnings, tier_normalize
from octave_mcp.core.grammar.cst import (
    Assignment,
    ASTNode,
    Block,
    Document,
    InlineMap,
    ListValue,
    Section,
)
from octave_mcp.core.hydrator import resolve_hermetic_standard
from octave_mcp.core.lexer import ENVELOPE_ID_PATTERN, LexerError, tokenize
from octave_mcp.core.literal_zone_audit import build_literal_zone_repair_log
from octave_mcp.core.repair import repair
from octave_mcp.core.repair_log import RepairLog, is_destructive_normalization_repair
from octave_mcp.core.schema_extractor import SchemaDefinition
from octave_mcp.core.validator import Validator, _count_literal_zones
from octave_mcp.mcp.base_tool import BaseTool, SchemaBuilder
from octave_mcp.mcp.compile_grammar import USAGE_HINTS
from octave_mcp.mcp.write_detection import (
    _auto_quote_section_refs_in_values,
    _detect_annotation_too_long,
    _detect_flat_prefix_scalar,
    _detect_inline_array_root,
    _detect_snake_case_blob,
    _detect_unquoted_section_in_values,
)
from octave_mcp.mcp.write_format import (
    E_INVALID_FORMAT_STYLE,
    FORMAT_STYLE_VALUES,
    W_COMPACT_REFUSED,
    OctaveASTCycleError,
    _emit_with_style,
    _to_baseline_bytes,
)
from octave_mcp.mcp.write_metrics import StructuralMetrics, extract_structural_metrics
from octave_mcp.mcp.write_mutation import (
    _apply_array_op_inplace,
    _extract_op_descriptor,
    _is_delete_sentinel,
    _is_op_descriptor,
    _mark_dirty,
    _normalize_value_for_ast,
    _normalize_value_for_ast_preserving,
    _parse_anchored_path,
    _resolve_anchored_assignment,
    _target_type_for_assignment,
)
from octave_mcp.schemas.loader import (
    BUILTIN_SCHEMA_DEFINITIONS,
    get_builtin_schema,
    get_schema_search_paths,
    load_schema,
    load_schema_by_name,
)

# Sentinel for DELETE operation in tri-state changes
DELETE_SENTINEL = {"$op": "DELETE"}

# Structural warning codes (Issue #92)
W_STRUCT_001 = "W_STRUCT_001"  # Section marker loss
W_STRUCT_002 = "W_STRUCT_002"  # Block count reduction
W_STRUCT_003 = "W_STRUCT_003"  # Assignment count reduction


# GH#349: Data loss warning for bare lines dropped during lenient parsing (I4)
W_BARE_LINE_DROPPED = "W_BARE_LINE_DROPPED"

# ADR-0006 SR1-T3a (#391, split from #369): deprecation warning for the
# conflicted-document case where a single-dot change key K.X resolves to
# BOTH a top-level Block(K) and a coexisting flat top-level Assignment("K.X").
# Surfaces as a non-fatal correction so the PR#370 tolerate-and-warn applier
# path is preserved (existing GH#372 migration sweep + repair-corridor traffic
# remain unaffected). The companion E_AMBIGUOUS_PATH constant below is
# scaffolding for the SR1-T3 hard-fail conversion that lands after SR1-T1
# grammar core (#382) provides unambiguous block-scoped accessor syntax.
W_AMBIGUOUS_PATH = "W_AMBIGUOUS_PATH"
E_AMBIGUOUS_PATH = "E_AMBIGUOUS_PATH"

# GH#376 PR-A: format_style parameter constants, exception, and AST pipeline
# helpers live in write_format.py as of #465 (STRATEGY_S1 CLUSTER_D extraction).
# Imported here so existing internal call sites continue to resolve unchanged.

# GH#352: Guidance hint for UNVALIDATED status (I5)
# GH#361r3: Base hint text; available schemas appended dynamically at runtime.
_VALIDATION_HINT_BASE = "Pass schema='META' (or another schema name) to enable I5 schema validation."


# GH#373: op-dispatch (_is_delete_sentinel, _is_op_descriptor, _extract_op_descriptor,
# _apply_array_op_inplace, _target_type_for_assignment) + AST mutation primitives
# (_mark_dirty, _normalize_value_for_ast) live in write_mutation.py as of #466
# (STRATEGY_S1 CLUSTER_C extraction). The _KNOWN_OPS frozenset co-migrated since
# it is exclusively consumed by _extract_op_descriptor. Imported above so existing
# internal call sites continue to resolve unchanged. This module is the v1.14.0
# (#460 Case A literal-zone form preservation) home for _normalize_value_for_ast.


# GH#263: Regex pattern for detecting NAME{qualifier} curly-brace annotations
# Matches: identifier characters followed by {qualifier_chars}
# The identifier pattern mirrors _is_valid_identifier_start/char from lexer.py
_CURLY_BRACE_ANNOTATION_PATTERN = re.compile(r"([A-Za-z_][A-Za-z0-9_./\-]*)\{([A-Za-z_][A-Za-z0-9_./\-]*)\}")

# GH#335: Regex pattern for detecting array-index notation in change paths.
# Matches keys containing bracket-enclosed integers like KEY[0], ITEMS[42], etc.
# Used to reject unresolvable paths instead of silently appending them.
_ARRAY_INDEX_RE = re.compile(r"\[\d+\]")

# GH#353: Regex pattern for parsing section-prefixed change paths.
# Matches: §<id>.<key>  or  §<id>::<name>.<key>
# Where <id> is a section number with optional suffix (e.g., "1", "2b", "3.5"),
# <name> is the section name (identifiers), and <key> is the child key to target.
# Only single-level child keys are supported (no deep nesting like §1.BLOCK.NESTED).
# Group layout: (1) section_id, (2) optional ::name, (3) child_key
# NOTE: The child key pattern excludes dots to prevent matching deep paths like §1.A.B.C.
# The section name in ::NAME allows dots (for names like v2.0) but the child key does NOT,
# since dots in the child position indicate hierarchical path traversal which is unsupported.
_SECTION_PATH_RE = re.compile(
    r"^§([0-9]+[a-zA-Z]?(?:\.[0-9]+)?)"  # §<id>: digits + optional letter suffix + optional .N
    r"(?:::([A-Za-z_][A-Za-z0-9_/\-]*))?"  # optional ::NAME (no dots in name)
    r"\.([A-Za-z_][A-Za-z0-9_/\-]*)$"  # .KEY (required child key, no dots)
)


class WriteTool(BaseTool):
    """MCP tool for octave_write - unified write operation for OCTAVE files."""

    # Security: allowed file extensions
    ALLOWED_EXTENSIONS = {".oct.md", ".octave", ".md"}

    def _repair_curly_brace_annotations(self, content: str) -> tuple[str, list[dict[str, Any]]]:
        """GH#263: Pre-process content to repair NAME{qualifier} -> NAME<qualifier>.

        I1 (Syntactic Fidelity): Only applies to Zone 1 (normalizing DSL) content.
        Quoted strings, literal zones (fenced blocks), and comments are protected.

        I4 (Transform Auditability): Every repair is logged with original and repaired
        syntax for full auditability.

        Args:
            content: Raw content that may contain curly-brace annotations

        Returns:
            Tuple of (repaired_content, list of correction records)
        """
        corrections: list[dict[str, Any]] = []

        # Build a set of character ranges that are protected from repair:
        # 1. Literal zones (``` fenced blocks) - Zone 3
        # 2. Quoted strings (text between "" after ::) - Zone 2
        # 3. Comments (// to end of line)
        protected: list[tuple[int, int]] = []

        # Find literal zone boundaries (``` fences)
        in_fence = False
        fence_start = 0
        offset = 0
        for line in content.split("\n"):
            line_start = offset
            offset += len(line) + 1  # +1 for the newline separator
            stripped = line.strip()
            if stripped.startswith("```"):
                if not in_fence:
                    in_fence = True
                    fence_start = line_start
                else:
                    in_fence = False
                    fence_end = line_start + len(line)
                    protected.append((fence_start, fence_end))

        # If fence was never closed, protect from fence_start to end
        if in_fence:
            protected.append((fence_start, len(content)))

        # Find quoted strings: text between "" on a line (after ::)
        quote_pattern = re.compile(r'"(?:[^"\\]|\\.)*"')
        for m in quote_pattern.finditer(content):
            protected.append((m.start(), m.end()))

        # Find comments: // to end of line
        comment_pattern = re.compile(r"//[^\n]*")
        for m in comment_pattern.finditer(content):
            protected.append((m.start(), m.end()))

        # Sort protected ranges for efficient lookup
        protected.sort()

        def _is_protected(pos: int) -> bool:
            """Check if a position falls within any protected range."""
            for start, end in protected:
                if start <= pos < end:
                    return True
                if start > pos:
                    break
            return False

        # Apply regex only to unprotected regions
        repaired = content
        # Collect matches that are in Zone 1 (unprotected)
        zone1_matches = []
        for match in _CURLY_BRACE_ANNOTATION_PATTERN.finditer(content):
            if not _is_protected(match.start()):
                zone1_matches.append(match)

        for match in zone1_matches:
            original = match.group(0)
            name = match.group(1)
            qualifier = match.group(2)
            suggested = f"{name}<{qualifier}>"

            corrections.append(
                {
                    "code": "W_REPAIR_CANDIDATE",
                    "tier": "LENIENT_PARSE",
                    "message": (
                        f"W_REPAIR_CANDIDATE::{original} repaired to {suggested}. "
                        f"Use angle brackets <> for annotation qualifiers, not curly braces {{}}."
                    ),
                    "before": original,
                    "after": suggested,
                    "safe": True,
                    "semantics_changed": False,
                }
            )

        # Replace only unprotected matches (process in reverse to preserve offsets)
        if corrections:
            for match in reversed(zone1_matches):
                name = match.group(1)
                qualifier = match.group(2)
                repaired = repaired[: match.start()] + f"{name}<{qualifier}>" + repaired[match.end() :]

        return repaired, corrections

    def _unwrap_markdown_code_fence(self, content: str) -> tuple[str, bool]:
        """Extract OCTAVE payload from a single outer markdown code fence.

        Accepts common fenced forms such as ```octave and ```markdown.
        Returns the original content when no full-document fence is present.
        """
        fence_match = re.match(r"^\s*```[^\n]*\n([\s\S]*?)\n```\s*$", content)
        if not fence_match:
            return content, False
        return fence_match.group(1), True

    def _build_unified_diff(self, before: str, after: str) -> str:
        """Build a compact unified diff string for diff-first responses."""
        before_lines = before.splitlines(keepends=True)
        after_lines = after.splitlines(keepends=True)
        diff_iter = unified_diff(before_lines, after_lines, fromfile="original", tofile="canonical", n=3)

        max_chars = 200_000
        out: list[str] = []
        total = 0
        for line in diff_iter:
            # Stop once we exceed the cap (streaming to avoid allocating huge diffs)
            if total + len(line) > max_chars:
                out.append("\n... (diff truncated)\n")
                break
            out.append(line)
            total += len(line)

        return "".join(out)

    def _wrap_plain_text_as_doc(self, raw_text: str, schema_name: str | None) -> tuple[str, list[dict[str, Any]]]:
        """Deterministically wrap plain text into a canonical OCTAVE carrier doc."""
        doc = Document(name="DOC")
        doc.meta = {"TYPE": schema_name or "UNKNOWN", "VERSION": "1.0"}
        doc.sections = [Block(key="BODY", children=[Assignment(key="RAW", value=raw_text)])]

        corrections: list[dict[str, Any]] = [
            {
                "code": "W_STRUCT_RAW_WRAP",
                "tier": "LENIENT_PARSE",
                "message": "Wrapped plain text into BODY: RAW carrier to produce parseable canonical OCTAVE",
                "safe": True,
                "semantics_changed": False,
            }
        ]
        return emit(doc), corrections

    def _localized_salvage(
        self, content: str, parse_error: str, schema_name: str | None
    ) -> tuple[Document, list[dict[str, Any]]]:
        """Issue #177: Attempt localized salvaging that preserves document structure.

        Instead of wrapping the entire file into a generic DOC with BODY::RAW,
        this method:
        1. Extracts and preserves the document envelope name (===NAME===)
        2. Parses line-by-line to identify which specific lines fail
        3. Preserves valid sections/fields
        4. Wraps only failing lines with _PARSE_ERROR_LINE_N markers

        Args:
            content: The original content that failed to parse
            parse_error: The error message from the failed parse attempt
            schema_name: Optional schema name for META.TYPE

        Returns:
            Tuple of (Document, corrections list)
        """
        corrections: list[dict[str, Any]] = []

        # Extract document envelope name from content
        envelope_match = re.search(rf"^===({ENVELOPE_ID_PATTERN})===\s*$", content, re.MULTILINE)
        doc_name = envelope_match.group(1) if envelope_match else "DOC"

        # Create document with extracted name
        doc = Document(name=doc_name)

        # Try to extract and preserve META block if present
        meta_match = re.search(
            r"^META:\s*\n((?:[ \t]+[^\n]+\n)*)",
            content,
            re.MULTILINE,
        )
        if meta_match:
            meta_content = meta_match.group(1)
            # Try to parse META fields
            meta_dict: dict[str, Any] = {}
            for line in meta_content.split("\n"):
                line = line.strip()
                if "::" in line:
                    key_value = line.split("::", 1)
                    if len(key_value) == 2:
                        key = key_value[0].strip()
                        value = key_value[1].strip().strip('"')
                        meta_dict[key] = value
            if meta_dict:
                doc.meta = meta_dict
            else:
                doc.meta = {"TYPE": schema_name or "UNKNOWN", "VERSION": "1.0"}
        else:
            doc.meta = {"TYPE": schema_name or "UNKNOWN", "VERSION": "1.0"}

        # Parse content line-by-line to identify valid vs failing lines
        # Issue #248: Track bracket depth so multi-line [...] blocks are tested
        # as complete units rather than line-by-line (which falsely rejects ] and ],)
        lines = content.split("\n")
        salvaged_sections: list[ASTNode] = []
        error_lines: list[tuple[int, str]] = []
        current_valid_lines: list[str] = []
        bracket_depth = 0
        bracket_block_lines: list[str] = []
        bracket_block_start_indices: list[int] = []

        # Skip envelope and end markers for line-by-line processing
        in_content = False
        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Track envelope markers
            if re.match(r"^===.+===\s*$", stripped):
                in_content = not in_content
                continue

            # Skip META block lines (already processed)
            if stripped.startswith("META:") or (meta_match and line in meta_match.group(0)):
                continue
            if stripped == "---":  # META separator
                continue

            if not in_content:
                continue

            # Issue #248: Track bracket depth for multi-line bracket blocks.
            # Lines like `],` and `]` are only valid inside an open bracket context.
            # When inside brackets (depth > 0), accumulate lines and test the
            # complete block once all brackets are balanced.
            if stripped:
                # Count bracket transitions on this line, skipping brackets
                # inside quoted strings to avoid false depth changes.
                line_opens = 0
                line_closes = 0
                in_quote = False
                escape_next = False
                for ch in stripped:
                    if escape_next:
                        escape_next = False
                        continue
                    if ch == "\\":
                        escape_next = True
                        continue
                    if ch == '"':
                        in_quote = not in_quote
                        continue
                    if not in_quote:
                        if ch == "[":
                            line_opens += 1
                        elif ch == "]":
                            line_closes += 1

                if bracket_depth > 0:
                    # Inside a bracket block - accumulate unconditionally
                    bracket_block_lines.append(line)
                    bracket_block_start_indices.append(i)
                    bracket_depth += line_opens - line_closes

                    if bracket_depth <= 0:
                        # Brackets balanced - flush accumulated valid lines then
                        # test the complete bracket block
                        bracket_depth = 0

                        # First, flush any pre-bracket valid lines
                        if current_valid_lines:
                            try:
                                vbc = "===TEST===\n" + "\n".join(current_valid_lines) + "\n===END==="
                                vd = parse(vbc)
                                salvaged_sections.extend(vd.sections)
                            except Exception:
                                for vl in current_valid_lines:
                                    if vl.strip():
                                        salvaged_sections.append(Assignment(key="_SALVAGED_LINE", value=vl))

                        # Now test the bracket block as a complete unit
                        # (opening line was stored as first bracket_block_lines entry)
                        try:
                            block_content = "===TEST===\n" + "\n".join(bracket_block_lines) + "\n===END==="
                            valid_doc = parse(block_content)
                            salvaged_sections.extend(valid_doc.sections)
                        except Exception:
                            # Bracket block failed as a unit - wrap as a single
                            # salvaged assignment preserving the full block text
                            block_text = "\n".join(bracket_block_lines)
                            salvaged_sections.append(Assignment(key="_SALVAGED_BLOCK", value=block_text))

                        current_valid_lines = []
                        bracket_block_lines = []
                        bracket_block_start_indices = []
                    continue

                if line_opens > line_closes:
                    # Opening a new multi-line bracket block
                    bracket_depth = line_opens - line_closes
                    bracket_block_lines = [line]
                    bracket_block_start_indices = [i]
                    continue

                # Normal line (no open bracket context) - test in isolation
                test_content = f"===TEST===\n{line}\n===END==="
                try:
                    parse(test_content)
                    current_valid_lines.append(line)
                except Exception:
                    # This line has an error - record it
                    error_lines.append((i, line))
                    # Flush any accumulated valid lines before the error
                    if current_valid_lines:
                        # Try to parse accumulated valid lines as a block
                        try:
                            valid_block_content = "===TEST===\n" + "\n".join(current_valid_lines) + "\n===END==="
                            valid_doc = parse(valid_block_content)
                            salvaged_sections.extend(valid_doc.sections)
                        except Exception:
                            # Even accumulated lines failed together - wrap as error
                            for vl in current_valid_lines:
                                salvaged_sections.append(Assignment(key="_SALVAGED_LINE", value=vl))
                        current_valid_lines = []
            else:
                # Empty line - keep in current valid block
                if current_valid_lines:
                    current_valid_lines.append(line)

        # Flush any remaining bracket block (unbalanced brackets at end of doc)
        if bracket_block_lines:
            # First flush pre-bracket valid lines
            if current_valid_lines:
                try:
                    vbc = "===TEST===\n" + "\n".join(current_valid_lines) + "\n===END==="
                    vd = parse(vbc)
                    salvaged_sections.extend(vd.sections)
                except Exception:
                    for vl in current_valid_lines:
                        if vl.strip():
                            salvaged_sections.append(Assignment(key="_SALVAGED_LINE", value=vl))
            # Try bracket block as unit; if it fails, wrap as single error
            try:
                block_content = "===TEST===\n" + "\n".join(bracket_block_lines) + "\n===END==="
                valid_doc = parse(block_content)
                salvaged_sections.extend(valid_doc.sections)
            except Exception:
                block_text = "\n".join(bracket_block_lines)
                salvaged_sections.append(Assignment(key="_SALVAGED_BLOCK", value=block_text))
            current_valid_lines = []

        # Flush remaining valid lines
        if current_valid_lines:
            try:
                valid_block_content = "===TEST===\n" + "\n".join(current_valid_lines) + "\n===END==="
                valid_doc = parse(valid_block_content)
                salvaged_sections.extend(valid_doc.sections)
            except Exception:
                for vl in current_valid_lines:
                    if vl.strip():
                        salvaged_sections.append(Assignment(key="_SALVAGED_LINE", value=vl))

        # Add error markers for each failing line
        for line_num, line_content in error_lines:
            # I1 (Syntactic Fidelity): emit_value handles escaping, don't pre-escape
            # Pre-escaping would cause double-escaping of backslashes and quotes
            salvaged_sections.append(Assignment(key=f"_PARSE_ERROR_LINE_{line_num}", value=line_content))
            corrections.append(
                {
                    "code": "W_SALVAGE_LINE",
                    "tier": "LENIENT_PARSE",
                    "message": f"Line {line_num} failed to parse: wrapped as _PARSE_ERROR_LINE_{line_num}",
                    "line": line_num,
                    "original": line_content,
                    "safe": True,
                    "semantics_changed": False,
                }
            )

        doc.sections = salvaged_sections if salvaged_sections else []

        # Add overall salvage correction
        corrections.insert(
            0,
            {
                "code": "W_SALVAGE_LOCALIZED",
                "tier": "LENIENT_PARSE",
                "message": f"Localized salvage: preserved document envelope '{doc_name}', "
                f"salvaged {len(salvaged_sections) - len(error_lines)} valid elements, "
                f"wrapped {len(error_lines)} failing line(s)",
                "safe": True,
                "semantics_changed": False,
                "parse_error": parse_error,
            },
        )

        return doc, corrections

    def _map_parse_warnings_to_corrections(self, warnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert parser/lexer warnings (I4) into octave_write corrections entries."""
        corrections: list[dict[str, Any]] = []
        for w in warnings:
            w_type = w.get("type", "")
            if w_type == "normalization":
                # ADR-0006 SR0-T2 (GH#381): suppress destructive empty-`after`
                # corrections via the shared discriminant in core.repair_log.
                # Boundary guard: lexer should never produce these post-fix,
                # but enforcing here too prevents drift if any future repair
                # source emits an empty-normalised record.
                #
                # Cubic P2 follow-up to #383: the helper deliberately narrows
                # to normalization-shaped records (type=="normalization" OR
                # has `normalized` key). A malformed record dispatched into
                # this branch on the strength of `w_type=="normalization"`
                # alone but lacking the `normalized` key would slip past the
                # helper. Belt-and-braces: also gate on a non-empty
                # normalized_value so neither defect class can land.
                #
                # GH-386: the helper now keys on warning code AND shape. Pass
                # the W002 discriminant explicitly so a future W003+
                # normalization warning routed through this branch is not
                # silently suppressed by the W002 guard.
                normalized_value = w.get("normalized", "")
                if is_destructive_normalization_repair(w, warning_code="W002") or not normalized_value:
                    continue
                corrections.append(
                    {
                        "code": "W002",
                        "tier": "NORMALIZATION",
                        "message": f"ASCII operator -> Unicode: {w.get('original', '')} -> {normalized_value}",
                        "line": w.get("line", 0),
                        "column": w.get("column", 0),
                        "before": w.get("original", ""),
                        "after": normalized_value,
                        "safe": True,
                        "semantics_changed": False,
                    }
                )
                continue

            if w_type == "lenient_parse":
                subtype = w.get("subtype", "unknown")

                # GH#305: Constructor misuse warnings are advisory
                # No data loss, no auto-fix — just advisory per I1
                if subtype == "constructor_misuse":
                    corrections.append(
                        {
                            "code": "W_CONSTRUCTOR_MISUSE",
                            "tier": "LENIENT_PARSE",
                            "message": w.get("message", f"Constructor misuse: {w.get('key', '?')}"),
                            "line": w.get("line", 0),
                            "column": w.get("column", 0),
                            "key": w.get("key", ""),
                            "value": w.get("value", ""),
                            "safe": True,
                            "semantics_changed": False,
                        }
                    )
                # GH#310: PATTERN/REGEX auto-quoting is advisory + safe
                # Value was bare, emitter will auto-quote for I1 fidelity
                elif subtype == "pattern_autoquote":
                    corrections.append(
                        {
                            "code": "W_PATTERN_AUTOQUOTE",
                            "tier": "LENIENT_PARSE",
                            "message": w.get(
                                "message",
                                f"PATTERN/REGEX value auto-quoted: {w.get('key', '?')}",
                            ),
                            "line": w.get("line", 0),
                            "column": w.get("column", 0),
                            "key": w.get("key", ""),
                            "value": w.get("value", ""),
                            "safe": True,
                            "semantics_changed": False,
                        }
                    )
                # GH#294: Duplicate key warnings get special treatment
                # Data loss = safe:false, semantics_changed:true
                elif subtype == "duplicate_key":
                    corrections.append(
                        {
                            "code": "W_DUPLICATE_KEY",
                            "tier": "LENIENT_PARSE",
                            "message": w.get("message", f"Duplicate key: {w.get('key', '?')}"),
                            "line": w.get("duplicate_line", w.get("line", 0)),
                            "column": w.get("column", 0),
                            "key": w.get("key", ""),
                            "all_lines": w.get("all_lines", []),
                            "safe": False,
                            "semantics_changed": True,
                        }
                    )
                # GH#348: Numeric key dropped = silent data loss (I4 violation)
                # Numeric keys are not valid OCTAVE identifiers; content is
                # dropped from canonical output. Must be safe:false,
                # semantics_changed:true so agents detect the loss.
                elif subtype == "numeric_key_dropped":
                    corrections.append(
                        {
                            "code": "W_NUMERIC_KEY_DROPPED",
                            "tier": "LENIENT_PARSE",
                            "message": w.get(
                                "message",
                                f"Numeric key dropped: {w.get('key', '?')}",
                            ),
                            "line": w.get("line", 0),
                            "column": w.get("column", 0),
                            "key": w.get("key", ""),
                            "value": w.get("value", ""),
                            "safe": False,
                            "semantics_changed": True,
                        }
                    )
                # GH#349: Bare line dropped = silent data loss (I4 violation)
                # Must be safe:false, semantics_changed:true so agents detect loss
                elif subtype == "bare_line_dropped":
                    original = w.get("original", "?")
                    corrections.append(
                        {
                            "code": W_BARE_LINE_DROPPED,
                            "tier": "LENIENT_PARSE",
                            "message": f"Bare line dropped: '{original}' has no :: or : operator and was silently removed",
                            "line": w.get("line", 0),
                            "column": w.get("column", 0),
                            "before": original,
                            "after": "",
                            "safe": False,
                            "semantics_changed": True,
                        }
                    )
                else:
                    corrections.append(
                        {
                            "code": f"W_LENIENT_{subtype}".upper(),
                            "tier": "LENIENT_PARSE",
                            "message": f"Lenient parse: {subtype}",
                            "line": w.get("line", 0),
                            "column": w.get("column", 0),
                            "before": w.get("original", ""),
                            "after": w.get("result", ""),
                            "safe": True,
                            "semantics_changed": False,
                        }
                    )
        return corrections

    def _error_envelope(
        self,
        target_path: str,
        errors: list[dict[str, Any]],
        corrections: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Build consistent error envelope with all required fields.

        Args:
            target_path: The target file path
            errors: List of error records
            corrections: Optional list of corrections (defaults to empty list)

        Returns:
            Complete error envelope with all required fields per D2 design
        """
        # I5 (Schema Sovereignty): validation_status must be UNVALIDATED to make bypass visible
        # "Schema bypass shall be visible, never silent" - North Star I5
        return {
            "status": "error",
            "path": target_path,
            "canonical_hash": "",
            "corrections": corrections if corrections is not None else [],
            "diff": "",
            "diff_unified": "",
            "errors": errors,
            "validation_status": "UNVALIDATED",  # I5: Explicit bypass - no schema validator yet
            "validation_hint": self._build_validation_hint(),  # GH#352+361r3: guidance with available schemas
        }

    def get_name(self) -> str:
        """Get tool name."""
        return "octave_write"

    def get_description(self) -> str:
        """Get tool description."""
        return (
            "Unified entry point for writing OCTAVE files. "
            "Handles creation (new files) and modification (existing files). "
            "Use content for full payload, changes for delta updates. "
            "Omit both content and changes to normalize an existing file in-place. "
            "Replaces octave_create and octave_amend."
        )

    def get_input_schema(self) -> dict[str, Any]:
        """Get input schema."""
        schema = SchemaBuilder()

        schema.add_parameter("target_path", "string", required=True, description="File path to write to")

        schema.add_parameter(
            "content",
            "string",
            required=False,
            description="Full content for new files or overwrites. Accepts raw OCTAVE or a single markdown fenced code block. Mutually exclusive with changes.",
        )

        schema.add_parameter(
            "changes",
            "object",
            required=False,
            description=(
                "Dictionary of field updates for existing files. "
                "Each value is either a bare value (full replacement, default) "
                "or a $op descriptor: "
                '{"$op":"DELETE"} removes the target; '
                '{"$op":"APPEND","value":x} pushes x (or each item of list x) '
                "onto the end of an array target; "
                '{"$op":"PREPEND","value":x} unshifts onto the front of an array; '
                '{"$op":"MERGE","value":{...}} deep-merges into a block target, '
                "preserving unmentioned children (use inner $op:DELETE to remove). "
                "Op/target-type mismatches return E_OP_TARGET_MISMATCH; "
                "missing paths return E_UNRESOLVABLE_PATH (no auto-create, I3); "
                "malformed descriptors return E_INVALID_OP_DESCRIPTOR. "
                "Paths support: top-level KEY, META.FIELD, PARENT.CHILD into a "
                "top-level Block, and §N.KEY / §N::NAME.KEY into Sections. "
                "(GH#373)"
            ),
        )

        schema.add_parameter(
            "mutations",
            "object",
            required=False,
            description="META field overrides (applies to both modes).",
        )

        schema.add_parameter(
            "base_hash",
            "string",
            required=False,
            description="Expected SHA-256 hash of existing file for consistency check (CAS).",
        )

        # GH#355: List common schemas in description so agents know what's available
        schema.add_parameter(
            "schema",
            "string",
            required=False,
            description=(
                "Schema name for validation (I5). "
                "Common schemas: META, SKILL, CRS_REVIEW, COGNITION_DEFINITION, DEBATE_TRANSCRIPT. "
                "Use 'frozen@<hash>' or 'latest' for hermetic resolution. "
                "If an unknown schema is provided, the response includes available_schemas."
            ),
        )

        schema.add_parameter(
            "debug_grammar",
            "boolean",
            required=False,
            description="If True, include compiled regex/grammar in output for debugging constraint evaluation.",
        )

        schema.add_parameter(
            "grammar_hint",
            "boolean",
            required=False,
            description="If True and validation returns INVALID, include compiled GBNF grammar in response to guide correction.",
        )

        schema.add_parameter(
            "lenient",
            "boolean",
            required=False,
            # GH#359: Explicitly state default value so agents know lenient is opt-in
            description="If True, enable deterministic lenient parsing + optional schema repairs. Default: false (strict parsing).",
        )

        schema.add_parameter(
            "corrections_only",
            "boolean",
            required=False,
            description="If True, return corrections/diff without writing to disk (dry run).",
        )

        # GH#354: Accept dry_run as alias for corrections_only
        schema.add_parameter(
            "dry_run",
            "boolean",
            required=False,
            description="Alias for corrections_only. If True, return corrections/diff without writing to disk (default: false).",
        )

        schema.add_parameter(
            "parse_error_policy",
            "string",
            required=False,
            description='Policy when tokenization/parsing fails in lenient mode: "error" (default) or "salvage".',
            enum=["error", "salvage"],
        )

        # GH#376 PR-A: format_style toggle. Three modes are AST projections
        # of one canonical emit() (I1 Single-Canon Discipline).
        #
        # CE + CRS CONDITIONAL on PR #422: the schema description and
        # null-handling must reflect Strategy A (GH#377, shipped via PR #418)
        # AND the Shape B deprecation contract — otherwise JSON-RPC clients
        # see stale Strategy-C metadata, and explicit `null` from a client
        # gets rejected at the schema boundary before reaching the Python
        # DeprecationWarning code path.
        schema.add_parameter(
            "format_style",
            "string",
            required=False,
            description=(
                "Output formatting style for canonical emission. "
                "'preserve' (Strategy A, GH#377): span-aware preserve mode — "
                "clean nodes slice from baseline_bytes, dirty/repaired nodes "
                "re-emit canonically. Diff footprint ≤0.5% of file size on "
                "single-key edits against representative documents. Subsumes "
                "GH#248 mixed annotation form drift. "
                "'expanded': lift inline-map shapes (KEY::[K::V,...]) into "
                "Block form before emit. "
                "'compact': collapse atom-only Blocks (no comments, "
                f"arity-bounded) into inline-list-of-InlineMap form. "
                f"Comment-bearing subtrees vetoed with {W_COMPACT_REFUSED} "
                "(I3 Mirror Constraint, I4 Auditability). "
                "DEPRECATED v1.13.0: Passing format_style=null explicitly "
                "emits a DeprecationWarning; the default will change from "
                "full canonical re-emit to 'preserve' in v1.14.0. To keep "
                "canonical re-emit past the flip, pass 'expanded' "
                "explicitly. To opt in to the new default early, pass "
                "'preserve'. Omitting the parameter accepts the future "
                "default silently."
            ),
            enum=list(FORMAT_STYLE_VALUES),
        )

        built = schema.build()

        # CE + CRS CONDITIONAL on PR #422: widen format_style to allow
        # explicit null so JSON-RPC clients reach the Python-side
        # DeprecationWarning instead of being rejected at the schema
        # boundary. SchemaBuilder.add_parameter accepts only a scalar
        # type string and a string-only enum list, so we post-process
        # the built schema rather than widening the builder API (which
        # has 29 other callsites). The contract on Python callers is
        # unchanged — explicit None still triggers the deprecation
        # warning at WriteTool.execute (the warning's source-of-truth
        # check is "format_style" in kwargs and kwargs["format_style"]
        # is None, not the schema enum).
        _fs_schema = built["properties"]["format_style"]
        _fs_schema["type"] = ["string", "null"]
        # Append None to the enum so the canonical JSON Schema validator
        # accepts a literal `null` from JSON-RPC clients.
        _fs_schema["enum"] = [*FORMAT_STYLE_VALUES, None]

        return built

    def _validate_path(self, target_path: str) -> tuple[bool, str | None]:
        """Validate target path for security.

        Args:
            target_path: Path to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        path = Path(target_path)

        # Reject path traversal early (before any filesystem resolution)
        try:
            if any(part == ".." for part in path.parts):
                return False, "Path traversal not allowed (..)"
        except Exception as e:
            return False, f"Invalid path: {str(e)}"

        # Check for symlinks anywhere in path (security: prevent symlink-based exfiltration)
        # This includes both the final component AND any parent directories
        # Example attack: /tmp/link/secret.oct.md where 'link' is a symlink
        #
        # Strategy: Use resolve() to follow all symlinks and compare to original
        # If they differ, a symlink was traversed. However, we need to handle
        # system-level symlinks (like /var -> /private/var on macOS).
        #
        # Safe approach: Resolve both paths and compare. If they're different,
        # check if the resolved path is still within an acceptable system location.
        try:
            # Get absolute path (does not follow symlinks)
            absolute = path.absolute()

            # Resolve to canonical path (follows all symlinks)
            resolved = absolute.resolve(strict=False)

            # If paths differ after normalization, symlinks were involved
            # Now check each component to see if it's a user-controlled symlink
            if absolute != resolved:
                # Walk the path to find which component is the symlink
                current = Path("/")
                for part in absolute.parts[1:]:  # Skip root
                    current = current / part
                    if current.exists() and current.is_symlink():
                        # Found a symlink - check if it's a system symlink
                        # System symlinks are typically in the first 2-3 components
                        # and resolve to /private/* or other system paths
                        symlink_depth = len(Path(current).parts)
                        resolved_target = current.resolve()

                        # Allow common system symlinks:
                        # - /var -> /private/var (depth 1)
                        # - /tmp -> /private/tmp (depth 1)
                        # - /etc -> /private/etc (depth 1)
                        if symlink_depth <= 2 and str(resolved_target).startswith("/private/"):
                            # Likely system symlink, allow it
                            continue

                        # User-controlled symlink - reject
                        return (
                            False,
                            f"Symlinks in path are not allowed for security reasons: '{target_path}'. Use corrections_only=true to preview normalization without writing.",
                        )

        except Exception as e:
            return False, f"Path resolution failed: {str(e)}"

        # Check file extension
        if path.suffix not in self.ALLOWED_EXTENSIONS:
            compound_suffix = "".join(path.suffixes[-2:]) if len(path.suffixes) >= 2 else path.suffix
            if compound_suffix not in self.ALLOWED_EXTENSIONS:
                allowed = ", ".join(sorted(self.ALLOWED_EXTENSIONS))
                return False, f"Invalid file extension. Allowed: {allowed}"

        return True, None

    def _compute_hash(self, content: str) -> str:
        """Compute SHA-256 hash of content.

        Args:
            content: Content to hash

        Returns:
            Hex digest of SHA-256 hash
        """
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _list_available_schemas(self) -> list[str]:
        """Enumerate all available schema names from builtins and search paths.

        GH#355: Returns a sorted list of schema names that agents can use
        with the schema parameter. Combines builtin dict schemas and
        file-based schemas from search paths.

        Returns:
            Sorted list of available schema name strings.
        """
        names: set[str] = set()

        # Builtin dict schemas (e.g. META)
        names.update(BUILTIN_SCHEMA_DEFINITIONS.keys())

        # File-based schemas from search paths
        for search_path in get_schema_search_paths():
            for schema_file in search_path.glob("*.oct.md"):
                # Schema name is derived from filename: meta.oct.md -> META
                name = schema_file.stem  # e.g. "meta" from "meta.oct.md"
                # Remove .oct suffix if present (stem of .oct.md is "meta.oct" not "meta")
                if name.endswith(".oct"):
                    name = name[:-4]
                names.add(name.upper())

        return sorted(names)

    def _build_validation_hint(self) -> str:
        """Build UNVALIDATED hint including available schema names.

        GH#361r3: Agents receiving UNVALIDATED status need to know which
        schema names are valid so they can self-correct. Appends the
        available schemas list to the base hint text.

        Returns:
            Hint string with available schemas enumerated.
        """
        schemas = self._list_available_schemas()
        if schemas:
            return f"{_VALIDATION_HINT_BASE} Available schemas: {', '.join(schemas)}"
        return _VALIDATION_HINT_BASE

    def _track_corrections(
        self, original: str, canonical: str, tokenize_repairs: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Track normalization corrections.

        Args:
            original: Original content
            canonical: Canonical content
            tokenize_repairs: Repairs from tokenization

        Returns:
            List of correction records with W001-W005 codes
        """
        corrections = []

        # Map tokenize repairs to W002 (ASCII operator -> Unicode)
        # ADR-0006 SR0-T2 (GH#381): skip destructive empty-`after` corrections
        # via the shared discriminant in core.repair_log. Boundary guard so a
        # defensive caller cannot land an I3-violating normalisation even if
        # the lexer guard is bypassed.
        #
        # Cubic P2 follow-up to #383: the helper deliberately narrows to
        # normalization-shaped records (type=="normalization" OR has
        # `normalized` key). A malformed token_repair lacking BOTH would
        # slip past the helper (helper returns False for not-normalization-
        # shaped) and emit W002 with empty `after`. Belt-and-braces: also
        # gate on a non-empty normalized_value so the malformed case is
        # suppressed too. The helper's narrow semantics are preserved.
        #
        # GH-386: the helper now keys on warning code AND shape. Pass the
        # W002 discriminant explicitly so a future W003+ normalization
        # warning routed through this mapping is not silently suppressed
        # by the W002 guard.
        for token_repair in tokenize_repairs:
            normalized_value = token_repair.get("normalized", "")
            if is_destructive_normalization_repair(token_repair, warning_code="W002") or not normalized_value:
                continue
            corrections.append(
                {
                    "code": "W002",
                    "message": f"ASCII operator -> Unicode: {token_repair.get('original', '')} -> {normalized_value}",
                    "line": token_repair.get("line", 0),
                    "column": token_repair.get("column", 0),
                    "before": token_repair.get("original", ""),
                    "after": normalized_value,
                }
            )

        return corrections

    def _validate_change_paths(
        self,
        changes: dict[str, Any],
        doc: Any | None = None,
        *,
        change_warnings: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """GH#335/GH#353: Validate change paths are resolvable before applying.

        Detects paths that _apply_changes cannot resolve to AST nodes and
        returns error records instead of silently appending literal dot-path
        lines to the document.

        GH#353: Section-prefixed paths (§N.KEY or §N::NAME.KEY) are now valid
        when they match a single child key within an existing section. When
        ``doc`` is provided, section existence and name matching are verified.

        I3 (Mirror Constraint): reflect only present, create nothing.
        Silent append of unresolvable paths fabricates content, violating I3.

        Unresolvable path patterns:
        1. Array-index notation: KEY[N] -- _apply_changes has no array element
           resolution; would silently append 'KEY[N]::"value"' as a literal key.
        2. Invalid section paths: §N without child key, or deep nested §N.A.B.C
           -- only §N.KEY and §N::NAME.KEY are supported (GH#353).
        3. Non-META dot-paths: X.Y.Z (where X != "META") -- _apply_changes only
           resolves META.FIELD; other dot-paths would be treated as literal keys
           containing dots, which is almost certainly not what the caller intended.

        Args:
            changes: Dictionary of change paths to validate
            doc: Optional parsed AST document for section existence validation.
                When provided, section paths are verified against actual sections.
            change_warnings: Optional caller-owned list that this method appends
                non-fatal change-path warnings to (currently W_AMBIGUOUS_PATH on
                the conflicted-document case). Per-call ownership eliminates the
                singleton race of an instance-attribute buffer (CE follow-up to
                #392). When None, warnings are suppressed.

        Returns:
            List of error dicts for unresolvable paths (empty if all paths are valid)
        """
        errors: list[dict[str, Any]] = []

        # GH#373: Pre-pass for op-descriptor shape validation. Catches malformed
        # descriptors (unknown $op, missing 'value', MERGE-with-non-dict) before
        # path resolution so the caller sees descriptor errors even when the path
        # itself is fine. Op/target-type mismatch is checked further below
        # (requires AST lookup of the resolved target).
        op_descriptors: dict[str, tuple[str | None, Any]] = {}
        for key, raw_value in changes.items():
            op, payload, op_err = _extract_op_descriptor(raw_value)
            if op_err is not None:
                err = {**op_err, "message": f"Invalid descriptor for '{key}': {op_err['message']}"}
                errors.append(err)
                continue
            op_descriptors[key] = (op, payload)

        for key in changes:
            # Skip keys that already failed descriptor validation; their target
            # type cannot be safely inspected in op/target-mismatch checks.
            if key not in op_descriptors:
                continue

            # Pattern 1: Array-index notation (e.g., KEY[4], §2.X.Y[0])
            if _ARRAY_INDEX_RE.search(key):
                errors.append(
                    {
                        "code": "E_UNRESOLVABLE_PATH",
                        "message": (
                            f"Unresolvable change path '{key}': array-index notation "
                            f"(e.g., KEY[N]) is not supported by the changes parameter. "
                            f"The changes parameter can only update top-level keys and "
                            f"META fields (via META.FIELD dot-notation). To modify array "
                            f"elements, use the content parameter with the full document."
                        ),
                    }
                )
                continue

            # Pattern 2: Section-prefixed paths
            # GH#353: Valid section paths (§N.KEY or §N::NAME.KEY) are now resolvable.
            # Only reject invalid section path patterns.
            if key.startswith("§"):
                match = _SECTION_PATH_RE.match(key)
                if not match:
                    # Invalid section path: either bare §N, or deep nested §N.A.B.C,
                    # or malformed syntax.
                    errors.append(
                        {
                            "code": "E_UNRESOLVABLE_PATH",
                            "message": (
                                f"Unresolvable change path '{key}': invalid section path. "
                                f"Section paths must use §N.KEY or §N::NAME.KEY format "
                                f"(single child key only). Deep nested paths like "
                                f"§N.BLOCK.NESTED are not supported. To modify deeply "
                                f"nested fields, use the content parameter with the full document."
                            ),
                        }
                    )
                elif doc is not None:
                    # GH#353: Verify the section actually exists in the document.
                    section_id, section_name, _child_key = match.groups()
                    section = self._find_section(doc, section_id, section_name)
                    if section is None:
                        name_detail = f" with name '{section_name}'" if section_name else ""
                        errors.append(
                            {
                                "code": "E_UNRESOLVABLE_PATH",
                                "message": (
                                    f"Unresolvable change path '{key}': section "
                                    f"§{section_id}{name_detail} not found in document."
                                ),
                            }
                        )
                continue

            # Pattern 3: Non-META hierarchical dot-paths.
            # META.FIELD is handled by _apply_changes.
            #
            # GH#347 carve-out: Single-dot keys like P1.1 or v2.0 are valid OCTAVE
            # identifiers (the lexer allows dots in identifiers).
            # GH#369: AST-aware resolution distinguishes "identifier with dots"
            # from "PARENT.CHILD path expression":
            #   - 2+ dots, non-META: always reject (deep nested paths unsupported).
            #   - exactly 1 dot, non-META:
            #       * If PARENT is a top-level Block in the AST -> treat dot as
            #         path separator. CHILD must resolve inside that Block,
            #         otherwise reject with E_UNRESOLVABLE_PATH.
            #       * Else if the literal dotted key already exists as a flat
            #         top-level Assignment -> accept (modify in place).
            #       * Else if doc is None (no AST available for resolution) ->
            #         accept (defer; legacy behaviour relied on this for the
            #         GH#347 carve-out without parsing).
            #       * Else -> reject (no resolvable target).
            if "." in key and not key.startswith("META."):
                if key.count(".") >= 2:
                    errors.append(
                        {
                            "code": "E_UNRESOLVABLE_PATH",
                            "message": (
                                f"Unresolvable change path '{key}': nested dot-path notation "
                                f"is only supported for META fields (e.g., META.STATUS). "
                                f"Other dot-paths cannot be resolved to AST nodes. To modify "
                                f"nested fields, use the content parameter with the full document."
                            ),
                        }
                    )
                    continue

                # Exactly one dot, non-META. AST-aware resolution.
                if doc is not None:
                    parent_key, _, child_key = key.partition(".")
                    parent_block = self._find_block(doc, parent_key)
                    if parent_block is not None:
                        # PARENT exists as a top-level Block. Treat dot as path
                        # separator; CHILD must resolve inside the Block.
                        flat_match = any(isinstance(s, Assignment) and s.key == key for s in doc.sections)
                        block_child_match = any(
                            isinstance(c, Assignment) and c.key == child_key for c in parent_block.children
                        )
                        if flat_match:
                            # ADR-0006 SR1-T3a (#391, split from #369):
                            # conflicted source document — both Block(parent) and a
                            # flat top-level Assignment(parent.child) coexist. The
                            # change key is genuinely ambiguous (which target should
                            # the update land on?). PR#370 tolerate-and-warn applier
                            # path is preserved (status=success; the existing
                            # GH#347 carve-out routes to the flat assignment), but
                            # we additionally surface a deprecation warning so
                            # callers can migrate ahead of the post-SR1-T1 hard-fail
                            # conversion (E_AMBIGUOUS_PATH).
                            block_candidate_desc = (
                                f"child '{child_key}' inside top-level Block('{parent_key}')"
                                if block_child_match
                                else (f"top-level Block('{parent_key}') (no child " f"'{child_key}' present)")
                            )
                            # CE follow-up to #392: warning attaches to the
                            # caller-owned per-invocation list passed in via
                            # ``change_warnings``. When the kwarg is None
                            # (direct/legacy callers), the warning is silently
                            # dropped — the validator's PRIMARY contract is
                            # error reporting, not warning surfacing; warnings
                            # only matter when execute() drains them into
                            # corrections.
                            if change_warnings is not None:
                                change_warnings.append(
                                    {
                                        "code": W_AMBIGUOUS_PATH,
                                        "tier": "STRUCTURAL_CHECK",
                                        "message": (
                                            f"Ambiguous change path '{key}': source document contains "
                                            f"both a top-level Block('{parent_key}') and a flat "
                                            f"top-level Assignment('{key}'). Candidate targets: "
                                            f"flat top-level Assignment('{key}'); "
                                            f"{block_candidate_desc}. Applier currently routes to the "
                                            f"flat assignment per the PR#370 repair-corridor contract; "
                                            f"this case will hard-fail with E_AMBIGUOUS_PATH after the "
                                            f"SR1-T1 grammar core lands. To resolve now: (a) use the "
                                            f"content= parameter with the full document to rewrite "
                                            f"verbatim, or (b) clean up the source so only one of the "
                                            f"two targets remains (this is the W_DUPLICATE_TARGET "
                                            f"corruption pattern tracked by GH#372 SR1-T2)."
                                        ),
                                        "field": key,
                                        "safe": True,
                                        "semantics_changed": False,
                                    }
                                )
                            # Tolerate here per PR#370 contract; applier handles the
                            # flat assignment via the GH#347 carve-out.
                            continue
                        if not block_child_match:
                            # No flat fallback; reject the unresolvable path.
                            errors.append(
                                {
                                    "code": "E_UNRESOLVABLE_PATH",
                                    "message": (
                                        f"Unresolvable change path '{key}': '{parent_key}' is a "
                                        f"top-level block but does not contain a child assignment "
                                        f"named '{child_key}'. To add a new child field to a block, "
                                        f"use the content parameter with the full document."
                                    ),
                                }
                            )
                            continue
                        # PARENT.CHILD resolves unambiguously inside the block.
                        # _apply_changes will route to _apply_block_change.
                        continue
                    # PARENT is not a top-level Block. The key is acceptable
                    # only if it already exists as a flat top-level Assignment
                    # (preserves the GH#347 single-identifier carve-out for
                    # legitimate dotted identifiers like P1.1).
                    flat_match = any(isinstance(s, Assignment) and s.key == key for s in doc.sections)
                    if flat_match:
                        continue
                    errors.append(
                        {
                            "code": "E_UNRESOLVABLE_PATH",
                            "message": (
                                f"Unresolvable change path '{key}': '{parent_key}' is not a "
                                f"top-level block and the literal key '{key}' does not exist "
                                f"as a flat top-level assignment. If you intended a nested "
                                f"field, use the content parameter with the full document. "
                                f"If you intended a flat top-level key, ensure it exists "
                                f"or pass content= to create it."
                            ),
                        }
                    )
                    continue
                # doc is None: cannot do AST-aware resolution. Fall through and
                # accept (legacy behaviour). _apply_changes will resolve.

            # Pattern 4: ANCHOR/KEY anchored-path (#460 Case B).
            # A '/'-bearing key with no '.' / '§' / '[' is either a literal key
            # (real assignment whose identifier contains '/') or an anchored
            # path. Resolve-literal-first: if a literal top-level Assignment
            # matches the raw key, accept it (backward-compat). Otherwise, when
            # an AST is available, the anchored target MUST resolve, else the
            # applier would silently append a fabricated 'ANCHOR/KEY' key
            # (I3 violation). Reject unresolvable anchored paths here.
            elif _parse_anchored_path(key) is not None and doc is not None:
                literal_match = any(isinstance(s, Assignment) and s.key == key for s in doc.sections)
                if not literal_match and self._resolve_anchored_change(doc, key) is None:
                    anchor, child_key = _parse_anchored_path(key)  # type: ignore[misc]
                    errors.append(
                        {
                            "code": "E_UNRESOLVABLE_PATH",
                            "message": (
                                f"Unresolvable change path '{key}': anchored-path "
                                f"'{anchor}/{child_key}' did not resolve. It selects the "
                                f"first '{child_key}' assignment following the '{anchor}' "
                                f"key in document order, but no such anchor+key pair was "
                                f"found (and no literal key '{key}' exists). Auto-create is "
                                f"forbidden by I3 (Mirror Constraint); use content= to add "
                                f"new structure."
                            ),
                        }
                    )
                    continue

        # GH#373: Op/target-type compatibility post-pass.
        # For each key with a recognised $op, look up the resolved target in the
        # AST and verify the op is compatible with the target type.
        # I5 (Schema Sovereignty): mismatches surface as visible E_OP_TARGET_MISMATCH
        # errors, never silent coercion.
        # I3 (Mirror Constraint): MERGE/APPEND/PREPEND on a missing path is
        # rejected (no auto-create) via E_UNRESOLVABLE_PATH.
        # Already-errored keys are skipped to keep error reports focused.
        already_errored_keys = {
            k
            for k in changes
            if any(
                # Heuristic: any error message that quotes this key counts.
                # Keeps the post-pass from double-reporting.
                f"'{k}'" in (e.get("message") or "")
                for e in errors
            )
        }
        if doc is not None:
            for key, (op, _payload) in op_descriptors.items():
                if op is None or op == "DELETE":
                    # Bare values: no target-type constraint.
                    # DELETE is permitted on any target (idempotent for missing).
                    continue
                if key in already_errored_keys:
                    continue

                target_kind, target_node = self._resolve_target_type(doc, key)
                if target_kind == "missing":
                    errors.append(
                        {
                            "code": "E_UNRESOLVABLE_PATH",
                            "message": (
                                f"Unresolvable change path '{key}': $op {op} "
                                f"requires an existing target, but no node "
                                f"resolves at this path. Auto-create is forbidden "
                                f"by I3 (Mirror Constraint); use content= to add "
                                f"new structure."
                            ),
                        }
                    )
                    continue

                if op in ("APPEND", "PREPEND"):
                    if target_kind != "array":
                        errors.append(
                            {
                                "code": "E_OP_TARGET_MISMATCH",
                                "message": (
                                    f"$op {op} requires an array target at '{key}', "
                                    f"but found {target_kind}. APPEND/PREPEND only "
                                    f"apply to list-valued assignments."
                                ),
                            }
                        )
                elif op == "MERGE":
                    if target_kind not in ("block", "section", "meta"):
                        errors.append(
                            {
                                "code": "E_OP_TARGET_MISMATCH",
                                "message": (
                                    f"$op MERGE requires a block (dict) target at "
                                    f"'{key}', but found {target_kind}. MERGE only "
                                    f"applies to top-level Blocks, Sections, or META."
                                ),
                            }
                        )

        return errors

    def _resolve_target_type(self, doc: Any, key: str) -> tuple[str, Any]:
        """GH#373: Classify the AST target a change-path resolves to.

        Returns:
            (kind, node) where kind is one of:
              - "missing": no target node exists at this path.
              - "array":   target is a list-valued Assignment (ListValue / list).
              - "scalar":  target is a non-list, non-map Assignment value.
              - "map":     target is an InlineMap or dict Assignment value.
              - "block":   target is a top-level Block.
              - "section": target is a Section node.
              - "meta":    target is the document's META block as a whole.
            node is the resolved AST node (or value), or None when missing.

        Used by _validate_change_paths to enforce op/target-type compatibility.
        Path patterns mirror the resolution logic in _apply_changes.
        """
        # META.FIELD -> doc.meta[field]
        if key.startswith("META.") and len(key) > 5:
            field_name = key[5:]
            if field_name in doc.meta:
                value = doc.meta[field_name]
                if isinstance(value, ListValue | list):
                    return ("array", value)
                if isinstance(value, InlineMap) or (isinstance(value, dict) and not _is_op_descriptor(value)):
                    return ("map", value)
                return ("scalar", value)
            return ("missing", None)

        # Top-level META as a whole -> meta block.
        if key == "META":
            return ("meta", doc.meta)

        # §N.KEY or §N::NAME.KEY -> child Assignment within Section.
        if key.startswith("§"):
            match = _SECTION_PATH_RE.match(key)
            if match is not None:
                section_id, section_name, child_key = match.groups()
                section = self._find_section(doc, section_id, section_name)
                if section is None:
                    return ("missing", None)
                for child in section.children:
                    if isinstance(child, Assignment) and child.key == child_key:
                        kind = _target_type_for_assignment(child.value)
                        return (kind, child)
                    if isinstance(child, Block) and child.key == child_key:
                        return ("block", child)
                return ("missing", None)
            return ("missing", None)

        # PARENT.CHILD where PARENT is a top-level Block -> nested Assignment.
        if "." in key and key.count(".") == 1:
            parent_key, _, child_key = key.partition(".")
            parent_block = self._find_block(doc, parent_key)
            # SR1-T3a CRS follow-up to #392: on the conflicted-document case
            # (Block(parent) coexists with flat top-level Assignment(parent.child))
            # _apply_changes routes the update to the FLAT assignment, not into
            # the Block (see line ~2741 elif guard: only routes to block when
            # `not any(...s.key == key)`). The validator's $op/target-type
            # post-pass MUST consult the same target the applier will hit,
            # otherwise APPEND/PREPEND/MERGE on conflicted documents validates
            # against the block child but mutates the flat — causing silent
            # type-mismatch corruption or runtime safety-net raises. So when a
            # flat top-level Assignment with the literal dotted key exists,
            # prefer it over any block child here.
            flat_node: Assignment | None = None
            for node in doc.sections:
                if isinstance(node, Assignment) and node.key == key:
                    flat_node = node
                    break
            if flat_node is not None:
                kind = _target_type_for_assignment(flat_node.value)
                return (kind, flat_node)
            if parent_block is not None:
                for child in parent_block.children:
                    if isinstance(child, Assignment) and child.key == child_key:
                        kind = _target_type_for_assignment(child.value)
                        return (kind, child)
                    if isinstance(child, Block) and child.key == child_key:
                        return ("block", child)
            return ("missing", None)

        # Bare top-level KEY.
        for node in doc.sections:
            if isinstance(node, Assignment) and node.key == key:
                kind = _target_type_for_assignment(node.value)
                return (kind, node)
            if isinstance(node, Block) and node.key == key:
                return ("block", node)
            if isinstance(node, Section) and node.key == key:
                return ("section", node)

        # #460 Case B: ANCHOR/KEY anchored-path (only reached when no literal
        # key matched above — resolve-literal-first). Mirrors the applier so the
        # $op/target-type post-pass validates against the node the applier hits.
        anchored = self._resolve_anchored_change(doc, key)
        if anchored is not None:
            target_assignment, _parent = anchored
            kind = _target_type_for_assignment(target_assignment.value)
            return (kind, target_assignment)

        return ("missing", None)

    def _find_block(self, doc: Any, block_key: str) -> Block | None:
        """Find a top-level Block node in doc.sections by key.

        GH#369: Companion to _find_section for nested Block path resolution.
        Walks doc.sections looking for a Block whose .key matches block_key.
        Only inspects direct children of the document (top-level blocks);
        deeper nesting is intentionally not searched, mirroring the single-
        level child-key constraint of _find_section.

        Args:
            doc: Parsed AST document
            block_key: Block key name to match (e.g., "NAV")

        Returns:
            Matching Block node, or None if not found.
        """
        for node in doc.sections:
            if isinstance(node, Block) and node.key == block_key:
                return node
        return None

    def _resolve_anchored_change(self, doc: Any, key: str) -> tuple[Assignment, Any] | None:
        """#460 Case B: resolve an ``ANCHOR/KEY`` anchored path to a node.

        Returns the Assignment that the path ``ANCHOR/KEY`` selects — "the KEY
        assignment following the ANCHOR key in document order" — together with
        its parent container, or ``None`` when the key is not an anchored path
        or does not resolve.

        Search order (document order, depth-first):
          1. The top-level ``doc.sections`` list (parent reported as ``None``).
          2. The ``children`` of each top-level Block/Section (parent reported
             as that Block/Section), so siblings nested one level deep are
             reachable too.

        Anchor and target must be siblings in the SAME list; the resolver does
        not cross container boundaries (an anchor in one block cannot select a
        key in another). This keeps resolution local and predictable, honouring
        PROD::I3 (reflect real structure) and PROD::I4 (stable real-key anchor).

        Args:
            doc: Parsed AST document.
            key: The raw change-path key (may or may not be an anchored path).

        Returns:
            ``(assignment, parent)`` when resolved; ``None`` otherwise. ``parent``
            is ``None`` for a top-level match, else the containing Block/Section.
        """
        parsed = _parse_anchored_path(key)
        if parsed is None:
            return None
        anchor, child_key = parsed

        # 1. Top-level sibling list.
        top = _resolve_anchored_assignment(doc.sections, anchor, child_key)
        if top is not None:
            return (top, None)

        # 2. One level into each Block/Section's children.
        for node in doc.sections:
            if isinstance(node, (Block, Section)):
                hit = _resolve_anchored_assignment(node.children, anchor, child_key)
                if hit is not None:
                    return (hit, node)
        return None

    def _is_anchored_change(self, doc: Any, key: str) -> bool:
        """#460 Case B: True iff ``key`` must be routed to the anchored handler.

        A key is an anchored change when ALL hold:
          - it parses as an ``ANCHOR/KEY`` anchored path, AND
          - no literal top-level Assignment matches the raw key verbatim
            (resolve-literal-first: a real ``A/B`` key wins), AND
          - the anchored target resolves in document order.

        Centralising the predicate keeps the dispatch chain in ``_apply_changes``
        in lock-step: the bare-DELETE branch is suppressed for exactly the keys
        the anchored branch will claim, so anchored DELETE can never fall into a
        silent-success no-op (rework B2) and a literal ``A/B`` DELETE is never
        stranded between the two branches.
        """
        if not any(isinstance(s, Assignment) and s.key == key for s in doc.sections):
            return self._resolve_anchored_change(doc, key) is not None
        return False

    def _apply_block_change(
        self,
        doc: Any,
        original_key: str,
        block_key: str,
        child_key: str,
        new_value: Any,
    ) -> None:
        """Apply a change to a child Assignment within a top-level Block node.

        GH#369: Mirrors _apply_section_change for top-level Block nodes.
        Used when the change key is PARENT.CHILD and PARENT is a top-level
        Block. Supports set/replace and DELETE sentinel for the child
        Assignment. Modifying nested Block-within-Block targets and array
        merge ops are explicitly out of scope.

        Args:
            doc: Parsed AST document
            original_key: The original changes key (for error messages)
            block_key: Top-level block key to navigate into
            child_key: Child key within the block to modify
            new_value: New value (with tri-state semantics)

        Raises:
            ValueError: If the block cannot be found, or if child_key resolves
                to a Block (nested block-in-block modification not supported).
                _validate_change_paths runs first so these are safety nets.
        """
        block = self._find_block(doc, block_key)
        if block is None:
            raise ValueError(
                [
                    {
                        "code": "E_UNRESOLVABLE_PATH",
                        "message": (f"Block '{block_key}' not found in document for " f"change path '{original_key}'."),
                    }
                ]
            )

        # Reject Block-in-Block targets (mirrors _apply_section_change I3 guard).
        for child in block.children:
            if isinstance(child, Block) and child.key == child_key:
                raise ValueError(
                    [
                        {
                            "code": "E_BLOCK_TARGET",
                            "message": (
                                f"Cannot modify '{child_key}' in block '{block_key}' via "
                                f"changes-mode: it is a Block (nested structure), not an "
                                f"Assignment. Use content= to rewrite the block, or target "
                                f"individual keys within the inner block."
                            ),
                        }
                    ]
                )

        # GH#373: Op-aware dispatch. Bare values fall through to legacy
        # full-replacement; descriptors (DELETE/APPEND/PREPEND) take their op
        # branch. MERGE on a nested Assignment is unreachable here because
        # _validate_change_paths rejects it via E_OP_TARGET_MISMATCH.
        op, payload, _ = _extract_op_descriptor(new_value)

        if op == "DELETE" or _is_delete_sentinel(new_value):
            block.children = [c for c in block.children if not (isinstance(c, Assignment) and c.key == child_key)]
            # PR-2 T6: children list mutated -> block body dirty.
            _mark_dirty(block, body=True)
            return

        if op in ("APPEND", "PREPEND"):
            for child in block.children:
                if isinstance(child, Assignment) and child.key == child_key:
                    _apply_array_op_inplace(child, op, payload)
                    # PR-2 T6: child mutated -> parent block body dirty.
                    _mark_dirty(block, body=True)
                    return
            # Validator should have caught missing target; safety net.
            raise ValueError(
                [
                    {
                        "code": "E_UNRESOLVABLE_PATH",
                        "message": (
                            f"$op {op} target '{child_key}' not found in block "
                            f"'{block_key}' (path '{original_key}')."
                        ),
                    }
                ]
            )

        # Legacy full-value replacement (or new Assignment if missing).
        for child in block.children:
            if isinstance(child, Assignment) and child.key == child_key:
                # #460 Case A: preserve literal-zone fence form in place.
                child.value = _normalize_value_for_ast_preserving(new_value, child.value)
                # PR-2 T6: child Assignment value mutated; parent block
                # body region must re-emit (the child line bytes are
                # stale) while block header line still splices.
                _mark_dirty(child)
                _mark_dirty(block, body=True)
                return

        # If we reach here, _validate_change_paths missed the case. Add as new
        # child Assignment to keep behaviour consistent with _apply_section_change.
        new_child = Assignment(key=child_key, value=_normalize_value_for_ast(new_value), dirty=True)
        block.children.append(new_child)
        _mark_dirty(block, body=True)

    def _find_section(
        self,
        doc: Any,
        section_id: str,
        section_name: str | None,
    ) -> Section | None:
        """Find a Section node in doc.sections by ID and optional name.

        GH#353: Navigates doc.sections to locate a Section matching the given
        section_id. If section_name is provided, also verifies the name matches.

        Args:
            doc: Parsed AST document
            section_id: Section number to match (e.g., "1", "2b", "3.5")
            section_name: Optional section name to verify (e.g., "IDENTITY")

        Returns:
            Matching Section node, or None if not found / name mismatch.
        """
        for node in doc.sections:
            if isinstance(node, Section) and node.section_id == section_id:
                if section_name is not None and node.key != section_name:
                    return None  # Name mismatch
                return node
        return None

    def _apply_section_change(
        self,
        doc: Any,
        original_key: str,
        section_id: str,
        section_name: str | None,
        child_key: str,
        new_value: Any,
    ) -> None:
        """Apply a change to a child key within a section node.

        GH#353: Navigates into a Section's children to update, add, or delete
        a child Assignment by key name.

        Args:
            doc: Parsed AST document
            original_key: The original changes key (for error messages)
            section_id: Section number (e.g., "1", "2b")
            section_name: Optional section name for verification (e.g., "IDENTITY")
            child_key: The child key to modify within the section
            new_value: The new value (with tri-state semantics)

        Raises:
            ValueError: If the section cannot be found (section_id not present
                or section_name mismatch). This should not happen because
                _validate_change_paths runs first, but provides a safety net
                for direct callers.
        """
        section = self._find_section(doc, section_id, section_name)
        if section is None:
            # Safety net: _validate_change_paths should catch this first.
            raise ValueError(
                [
                    {
                        "code": "E_UNRESOLVABLE_PATH",
                        "message": (
                            f"Section §{section_id} not found in document"
                            + (f" (expected name '{section_name}')" if section_name else "")
                            + f" for change path '{original_key}'."
                        ),
                    }
                ]
            )

        # GH#361r3: Reject changes targeting Block children (I3 - Mirror Constraint).
        # Section-path changes only support Assignment children. If the child_key
        # resolves to a Block node, reject with an error rather than silently
        # no-opping (delete) or appending a sibling Assignment (set).
        for child in section.children:
            if isinstance(child, Block) and child.key == child_key:
                raise ValueError(
                    [
                        {
                            "code": "E_BLOCK_TARGET",
                            "message": (
                                f"Cannot modify '{child_key}' in §{section_id} via section-path: "
                                f"it is a Block (nested structure), not an Assignment. "
                                f"Use content= to rewrite the section, or target individual "
                                f"keys within the block."
                            ),
                        }
                    ]
                )

        # GH#373: Op-aware dispatch parallel to _apply_block_change.
        op, payload, _ = _extract_op_descriptor(new_value)

        if op == "DELETE" or _is_delete_sentinel(new_value):
            # I2: DELETE sentinel - remove child from section
            section.children = [c for c in section.children if not (isinstance(c, Assignment) and c.key == child_key)]
            # PR-2 T6: children list mutated -> section body dirty.
            _mark_dirty(section, body=True)
            return

        if op in ("APPEND", "PREPEND"):
            for child in section.children:
                if isinstance(child, Assignment) and child.key == child_key:
                    _apply_array_op_inplace(child, op, payload)
                    # PR-2 T6: child mutated -> section body dirty.
                    _mark_dirty(section, body=True)
                    return
            raise ValueError(
                [
                    {
                        "code": "E_UNRESOLVABLE_PATH",
                        "message": (
                            f"$op {op} target '{child_key}' not found in §{section_id} " f"(path '{original_key}')."
                        ),
                    }
                ]
            )

        # Update or add child assignment
        # I1 (Syntactic Fidelity): Normalize Python values to AST types
        found = False
        for child in section.children:
            if isinstance(child, Assignment) and child.key == child_key:
                # #460 Case A: preserve literal-zone fence form in place.
                child.value = _normalize_value_for_ast_preserving(new_value, child.value)
                # PR-2 T6: child Assignment value mutated.
                _mark_dirty(child)
                found = True
                break

        if not found:
            # Add new assignment to section children
            new_assignment = Assignment(key=child_key, value=_normalize_value_for_ast(new_value), dirty=True)
            section.children.append(new_assignment)
        # PR-2 T6: in both branches the section's body region changed
        # (either an existing child mutated, or a new child appended),
        # so mark the section body dirty so the children region
        # re-emits even though the section header line still splices.
        _mark_dirty(section, body=True)

    def _apply_changes(
        self,
        doc: Any,
        changes: dict[str, Any],
        *,
        change_warnings: list[dict[str, Any]] | None = None,
    ) -> Any:
        """Apply changes to AST document with tri-state and dot-notation semantics.

        Args:
            doc: Parsed AST document
            changes: Dictionary of field updates with tri-state semantics:
                - Key absent: No change to field
                - Key present with {"$op": "DELETE"}: Delete the field
                - Key present with None: Set field to null/empty
                - Key present with value: Update field to new value

                Dot-notation support for nested updates:
                - "META.STATUS": "ACTIVE" -> updates doc.meta["STATUS"]
                - "META.NEW_FIELD": "value" -> adds field to doc.meta
                - "META.FIELD": {"$op": "DELETE"} -> removes field from doc.meta
                - "META": {...} -> merges into existing doc.meta (unmentioned fields preserved)
                  Use {"$op": "DELETE"} on individual keys within the dict to remove them.

        Returns:
            Modified document

        Raises:
            ValueError: If any change paths are unresolvable (GH#335)
        """
        # GH#335: Validate all paths before applying any changes.
        # Fail-fast: if ANY path is unresolvable, reject the entire batch
        # to prevent partial application with silent corruption.
        path_errors = self._validate_change_paths(changes, doc, change_warnings=change_warnings)
        if path_errors:
            raise ValueError(path_errors)

        for key, new_value in changes.items():
            # GH#353: Section-prefixed paths (§N.KEY or §N::NAME.KEY)
            if key.startswith("§"):
                match = _SECTION_PATH_RE.match(key)
                if match:
                    section_id, section_name, child_key = match.groups()
                    self._apply_section_change(doc, key, section_id, section_name, child_key, new_value)
                # Invalid section paths already rejected by _validate_change_paths
                continue

            # Check for dot-notation: META.FIELD
            if key.startswith("META."):
                # Extract the field name after "META."
                field_name = key[5:]  # Remove "META." prefix

                # GH #447: I3 (MIRROR_CONSTRAINT) + I1 (SYNTACTIC_FIDELITY)
                # mutate-in-place contract. When a META envelope was parsed
                # with FLAT-form atoms (no ``META:`` block prefix), the
                # parser puts each atom in ``doc.sections`` as a top-level
                # ``Assignment`` rather than into the ``doc.meta`` dict. The
                # original ``META.<field>`` resolver wrote unconditionally
                # to ``doc.meta`` which on emit produced a NEW canonical
                # ``META:`` block alongside the surviving flat atom —
                # duplicate-key, form switch, I3 violation. We must locate
                # the existing flat atom FIRST and mutate it in place;
                # only when no flat atom exists do we fall through to the
                # ``doc.meta`` dict path (preserving today's behaviour for
                # documents whose META is parsed into the dict).
                #
                # PR #449 CE REWORK BLOCKING #1: the flat-atom scan MUST be
                # constrained to the ``===META===`` envelope shape only.
                # ``META.<field>`` addresses the flat-atom inside an envelope
                # whose name is "META", NOT any top-level atom with the
                # matching key anywhere in the document. CE's repro showed
                # that without this constraint a document like
                # ``===DOC===\nSTATUS::content_status\n===END===`` would have
                # its DOC envelope's ``STATUS`` atom silently mutated by
                # ``changes={"META.STATUS": ...}`` -- a cross-envelope scope
                # leak. We gate the scan on ``doc.name == "META"`` so that
                # only true META envelopes participate in the flat-atom path.
                flat_idx: int | None = None
                if doc.name == "META":
                    for idx, section in enumerate(doc.sections):
                        if isinstance(section, Assignment) and section.key == field_name:
                            flat_idx = idx
                            break

                if flat_idx is not None:
                    if _is_delete_sentinel(new_value):
                        # Remove the flat top-level Assignment in place.
                        del doc.sections[flat_idx]
                        # PR #449 CE REWORK observation #4: the deletion
                        # mechanism is OMISSION -- removing the Assignment
                        # node from ``doc.sections`` means the emitter
                        # cannot re-emit what is no longer there. We also
                        # mark ``doc.dirty=True`` so the preserve-mode
                        # emitter cannot splice the now-stale baseline
                        # bytes for this envelope; instead it re-emits
                        # canonically, naturally skipping the deleted
                        # atom. (No section-emission consults
                        # ``doc.dirty`` directly; the flag fences the
                        # baseline-slice path in ``emit()`` instead.)
                        doc.dirty = True
                    else:
                        # I1 (Syntactic Fidelity): normalise the value.
                        target_assignment = doc.sections[flat_idx]
                        assert isinstance(target_assignment, Assignment)
                        # #460 Case A: preserve literal-zone fence form in place.
                        target_assignment.value = _normalize_value_for_ast_preserving(
                            new_value, target_assignment.value
                        )
                        # PR-2 T6: paired-write — mark only this leaf
                        # dirty so the preserve-mode emitter re-emits
                        # just this atom and splices the rest of the
                        # envelope verbatim.
                        _mark_dirty(target_assignment)
                elif _is_delete_sentinel(new_value):
                    # No flat atom; fall through to doc.meta dict deletion.
                    if field_name in doc.meta:
                        del doc.meta[field_name]
                    # PR-2 T6: per-key META dirty map captures the
                    # deletion event so PR-3's emitter knows this META
                    # key no longer exists in the AST.
                    doc.meta_dirty[field_name] = True
                else:
                    # Update or add field in doc.meta
                    # I1 (Syntactic Fidelity): Normalize Python values to AST types
                    # Without this, Python lists emit as "['a', 'b']" instead of "[a,b]"
                    doc.meta[field_name] = _normalize_value_for_ast(new_value)
                    # PR-2 T6: paired-write — mark per-key dirty so PR-3
                    # emitter re-emits only this META key and splices
                    # the rest of META verbatim.
                    doc.meta_dirty[field_name] = True
            elif key == "META" and isinstance(new_value, dict):
                if _is_delete_sentinel(new_value):
                    # DELETE sentinel on META clears the entire block
                    doc.meta = {}
                    # PR-2 T6: whole-META clear -> mark every existing
                    # key in meta_dirty so PR-3 emitter knows no key
                    # survives. Use a sentinel "*" to denote whole-meta
                    # dirty WITHOUT inventing a key shape that doesn't
                    # match observable data. We instead mark
                    # ``doc.dirty=True`` for whole-doc re-emit; the
                    # per-key map remains the precision instrument.
                    doc.dirty = True
                else:
                    # GH#302: MERGE into existing META, not replace.
                    # Previous behavior replaced the entire META dict, silently
                    # dropping fields like CONTRACT::HOLOGRAPHIC that were not
                    # included in the changes dict.  Merge preserves unmentioned
                    # fields (I3 Mirror Constraint: reflect only present, create
                    # nothing -- and do not destroy what is already present).
                    #
                    # GH#373: An explicit {"$op": "MERGE", "value": {...}} descriptor
                    # has the same semantics as the bare-dict legacy form; payload
                    # is the inner dict.
                    op_meta, payload_meta, _ = _extract_op_descriptor(new_value)
                    merge_dict = payload_meta if op_meta == "MERGE" else new_value
                    for mk, mv in merge_dict.items():
                        if _is_delete_sentinel(mv):
                            doc.meta.pop(mk, None)
                            # PR-2 T6: per-key META dirty (deletion).
                            doc.meta_dirty[mk] = True
                        else:
                            # I1 (Syntactic Fidelity): Normalize values for AST
                            doc.meta[mk] = _normalize_value_for_ast(mv)
                            # PR-2 T6: paired-write — only touched keys
                            # are marked dirty; unmentioned META keys
                            # stay clean per the sibling-clean invariant
                            # (ADR §4 per-key dirty model).
                            doc.meta_dirty[mk] = True
            elif (
                "." in key
                and key.count(".") == 1
                and self._find_block(doc, key.split(".", 1)[0]) is not None
                and not any(isinstance(s, Assignment) and s.key == key for s in doc.sections)
            ):
                # GH#369: PARENT.CHILD where PARENT is a top-level Block and the
                # literal dotted key does NOT already exist as a flat top-level
                # Assignment. Route into the Block instead of falling through to
                # the flat-assignment branch (which would silently append a
                # duplicate assignment with a dotted key, violating I3).
                #
                # The "literal dotted key already exists at top level" check
                # preserves the GH#347 edge case where a block named e.g. "P1"
                # coexists with a flat assignment "P1.1::value": we still
                # modify the flat assignment in that scenario.
                parent_key, _, child_key = key.partition(".")
                self._apply_block_change(doc, key, parent_key, child_key, new_value)
            elif _is_delete_sentinel(new_value) and not self._is_anchored_change(doc, key):
                # I2: DELETE sentinel - remove field entirely from sections.
                # #460 Case B (rework B2): the bare-DELETE branch matches by
                # ``s.key == key`` and never matches an anchored path, so it
                # must NOT consume a resolvable ANCHOR/KEY DELETE (which would
                # otherwise silent-success no-op). Suppressing it for exactly
                # the keys the anchored branch claims (_is_anchored_change)
                # lets a resolvable anchored DELETE fall through to the
                # anchored handler below; a literal ``A/B`` key (resolve-
                # literal-first) is still handled here.
                doc.sections = [s for s in doc.sections if not (isinstance(s, Assignment) and s.key == key)]
                # PR-2 T6: doc.sections list changed (deletion). The
                # Document does not carry body_dirty; mark whole-doc
                # dirty so PR-3 emitter knows the sections list shape
                # differs from baseline. The other clean sections
                # still slice individually via their own dirty=False
                # spans.
                doc.dirty = True
            elif (
                isinstance(new_value, dict)
                and not _is_op_descriptor(new_value)
                and self._find_block(doc, key) is not None
            ):
                # ADR-0006 SR2-T2 PR-2 (GH#377) T7: bare ``{KEY: {child:
                # v2}}`` change against an EXISTING top-level Block.
                # Without this branch, the dict would be normalised to
                # an InlineMap and appended as a NEW top-level
                # Assignment beside the Block (duplicate key, silent
                # shape switch — I3 violation under format_style
                # ``"preserve"``). With this branch, the dict is
                # expanded into per-child Assignment mutations against
                # the existing Block, keeping the Block shape and
                # marking only the touched children dirty.
                t7_block = self._find_block(doc, key)
                assert t7_block is not None  # narrowed by branch guard
                for mk, mv in new_value.items():
                    if _is_delete_sentinel(mv):
                        t7_block.children = [
                            c for c in t7_block.children if not (isinstance(c, Assignment) and c.key == mk)
                        ]
                        _mark_dirty(t7_block, body=True)
                        continue
                    found_child = False
                    for child in t7_block.children:
                        if isinstance(child, Assignment) and child.key == mk:
                            # #460 Case A: preserve literal-zone fence form in place.
                            child.value = _normalize_value_for_ast_preserving(mv, child.value)
                            _mark_dirty(child)
                            found_child = True
                            break
                    if not found_child:
                        new_child = Assignment(key=mk, value=_normalize_value_for_ast(mv), dirty=True)
                        t7_block.children.append(new_child)
                    _mark_dirty(t7_block, body=True)
            elif self._is_anchored_change(doc, key):
                # #460 Case B: ANCHOR/KEY anchored-path. Resolve-literal-first —
                # _is_anchored_change is True only when no literal top-level
                # Assignment matches the raw key verbatim (that case is handled
                # by the legacy branch, preserving backward-compat for real keys
                # containing '/'). The same predicate gates the bare-DELETE
                # suppression above, keeping the two branches in lock-step.
                resolved = self._resolve_anchored_change(doc, key)
                assert resolved is not None  # narrowed by _is_anchored_change
                target_assignment, parent = resolved
                # #460 (cubic P1): the anchored target is an Assignment, so it
                # MUST go through the SAME op machinery as a bare top-level key.
                # Otherwise a $op descriptor is normalized and written as literal
                # data (PROD::I3 violation: control descriptors as content).
                op, payload, _ = _extract_op_descriptor(new_value)
                if op == "DELETE" or _is_delete_sentinel(new_value):
                    # Remove the resolved sibling from its parent's child list.
                    if parent is None:
                        doc.sections = [s for s in doc.sections if s is not target_assignment]
                        doc.dirty = True
                    elif isinstance(parent, (Block, Section)):
                        parent.children = [c for c in parent.children if c is not target_assignment]
                        _mark_dirty(parent, body=True)
                elif op in ("APPEND", "PREPEND"):
                    # Array op on the resolved Assignment. _validate_change_paths
                    # has already verified the target is array-typed via
                    # _resolve_target_type (which resolves anchored paths), so a
                    # type mismatch surfaces as E_OP_TARGET_MISMATCH before apply.
                    _apply_array_op_inplace(target_assignment, op, payload)
                    if isinstance(parent, (Block, Section)):
                        _mark_dirty(parent, body=True)
                elif op == "MERGE":
                    # An anchored path resolves only to an Assignment, never a
                    # Block/Section/META, so MERGE has no valid anchored target.
                    # The validator rejects this upstream (E_OP_TARGET_MISMATCH);
                    # this is a defensive loud failure so a MERGE descriptor can
                    # NEVER be written as literal data if it ever reaches apply.
                    raise ValueError(
                        [
                            {
                                "code": "E_OP_TARGET_MISMATCH",
                                "message": (
                                    f"$op MERGE is not supported on anchored path '{key}': "
                                    f"it resolves to an assignment (scalar/array), not a "
                                    f"Block/Section/META target. MERGE only applies to "
                                    f"top-level Blocks, Sections, or META."
                                ),
                            }
                        ]
                    )
                else:
                    # Bare value: full replacement.
                    # #460 Case A interplay: preserve literal-zone fence form.
                    target_assignment.value = _normalize_value_for_ast_preserving(new_value, target_assignment.value)
                    _mark_dirty(target_assignment)
                    if isinstance(parent, (Block, Section)):
                        _mark_dirty(parent, body=True)
            else:
                # GH#373: Op-aware dispatch on top-level keys.
                # MERGE on a top-level Block; APPEND/PREPEND on a top-level
                # array Assignment. Bare values fall through to legacy
                # full-replacement.
                op, payload, _ = _extract_op_descriptor(new_value)

                if op == "MERGE":
                    # Validator restricts MERGE to block/section/meta targets.
                    target_block: Block | None = self._find_block(doc, key)
                    if target_block is not None:
                        for mk, mv in payload.items():
                            if _is_delete_sentinel(mv):
                                target_block.children = [
                                    c for c in target_block.children if not (isinstance(c, Assignment) and c.key == mk)
                                ]
                                _mark_dirty(target_block, body=True)
                                continue
                            found_child = False
                            for child in target_block.children:
                                if isinstance(child, Assignment) and child.key == mk:
                                    # #460 Case A: preserve literal-zone fence form
                                    # when MERGE replaces an existing fenced child.
                                    child.value = _normalize_value_for_ast_preserving(mv, child.value)
                                    # PR-2 T6: paired-write per leaf.
                                    _mark_dirty(child)
                                    found_child = True
                                    break
                            if not found_child:
                                # New child: nothing to preserve, plain normalize.
                                new_child = Assignment(key=mk, value=_normalize_value_for_ast(mv), dirty=True)
                                target_block.children.append(new_child)
                            # PR-2 T6: in every MERGE-on-Block branch
                            # (existing-child mutate or new-child
                            # append), the block's body region changed.
                            _mark_dirty(target_block, body=True)
                        continue

                    # MERGE on a Section -- search and merge children.
                    target_section: Section | None = None
                    for node in doc.sections:
                        if isinstance(node, Section) and node.key == key:
                            target_section = node
                            break
                    if target_section is not None:
                        for mk, mv in payload.items():
                            if _is_delete_sentinel(mv):
                                target_section.children = [
                                    c
                                    for c in target_section.children
                                    if not (isinstance(c, Assignment) and c.key == mk)
                                ]
                                _mark_dirty(target_section, body=True)
                                continue
                            found_child = False
                            for child in target_section.children:
                                if isinstance(child, Assignment) and child.key == mk:
                                    # #460 Case A: preserve literal-zone fence form
                                    # when MERGE replaces an existing fenced child.
                                    child.value = _normalize_value_for_ast_preserving(mv, child.value)
                                    _mark_dirty(child)
                                    found_child = True
                                    break
                            if not found_child:
                                # New child: nothing to preserve, plain normalize.
                                new_child = Assignment(key=mk, value=_normalize_value_for_ast(mv), dirty=True)
                                target_section.children.append(new_child)
                            _mark_dirty(target_section, body=True)
                        continue
                    # Validator should have caught missing target; safety net.
                    raise ValueError(
                        [
                            {
                                "code": "E_UNRESOLVABLE_PATH",
                                "message": (f"$op MERGE target '{key}' not found as a Block " f"or Section."),
                            }
                        ]
                    )

                if op in ("APPEND", "PREPEND"):
                    for section in doc.sections:
                        if isinstance(section, Assignment) and section.key == key:
                            _apply_array_op_inplace(section, op, payload)
                            break
                    else:
                        raise ValueError(
                            [
                                {
                                    "code": "E_UNRESOLVABLE_PATH",
                                    "message": (f"$op {op} target '{key}' not found as a " f"top-level Assignment."),
                                }
                            ]
                        )
                    continue

                # Legacy full-value replacement (or new Assignment if missing).
                # I1 (Syntactic Fidelity): Normalize Python values to AST types
                found = False
                for section in doc.sections:
                    if isinstance(section, Assignment) and section.key == key:
                        # #460 Case A: preserve literal-zone fence form in place.
                        section.value = _normalize_value_for_ast_preserving(new_value, section.value)
                        # PR-2 T6: paired-write on top-level Assignment.
                        _mark_dirty(section)
                        found = True
                        break

                # If not found and not deleting, add new field
                if not found:
                    # Create new assignment node with normalized value.
                    # PR-2 T6: new Assignment is born dirty (no source
                    # bytes to splice; its value MUST be re-emitted).
                    new_assignment = Assignment(key=key, value=_normalize_value_for_ast(new_value), dirty=True)
                    doc.sections.append(new_assignment)

        return doc

    def _apply_mutations(self, doc: Document, mutations: dict[str, Any] | None) -> None:
        """Apply META field mutations to document AST.

        Args:
            doc: Parsed document to mutate
            mutations: Dictionary of META fields to inject/override

        Mutations support:
        - Set/override fields (including None/null)
        - DELETE sentinel removes field
        - Python lists normalized to ListValue for canonical emission
        """
        if not mutations:
            return

        for key, value in mutations.items():
            if _is_delete_sentinel(value):
                doc.meta.pop(key, None)
                # PR-2 T6: per-key META dirty (deletion via mutations).
                doc.meta_dirty[key] = True
                continue
            doc.meta[key] = _normalize_value_for_ast(value)
            # PR-2 T6: paired-write — touched META keys mark per-key
            # dirty so PR-3 emitter re-emits only the affected keys.
            doc.meta_dirty[key] = True

    def _generate_diff(
        self,
        original_bytes: int,
        canonical_bytes: int,
        original_metrics: StructuralMetrics | None,
        canonical_metrics: StructuralMetrics | None,
        content_changed: bool = False,
    ) -> str:
        """Generate structural diff from pre-computed metrics.

        Compares structural metrics to detect potential data loss during
        normalization. Returns warnings for significant structural changes.

        Args:
            original_bytes: Byte length of original content
            canonical_bytes: Byte length of canonical content
            original_metrics: Pre-computed metrics from original document (or None)
            canonical_metrics: Pre-computed metrics from canonical document (or None)
            content_changed: Whether content differs (for I4 auditability when
                byte count and structure are identical but values differ)

        Returns:
            Structural diff summary with warning codes for significant changes
        """
        # I4 Auditability: Must report changes even when byte count and structure
        # are identical but content values differ (e.g., KEY::foo -> KEY::bar)
        if not content_changed and original_bytes == canonical_bytes and original_metrics == canonical_metrics:
            return "No changes"

        # Build structural summary with warnings
        summary_parts = []
        warnings = []

        # Byte count change
        summary_parts.append(f"{original_bytes} -> {canonical_bytes} bytes")

        # If we have metrics, check for structural changes
        if original_metrics is not None and canonical_metrics is not None:
            # Section marker loss (W_STRUCT_001)
            lost_sections = original_metrics.section_markers - canonical_metrics.section_markers
            if lost_sections:
                warnings.append(f"{W_STRUCT_001}: section markers removed ({', '.join(sorted(lost_sections))})")

            # Block count reduction (W_STRUCT_002)
            if canonical_metrics.blocks < original_metrics.blocks:
                block_diff = original_metrics.blocks - canonical_metrics.blocks
                warnings.append(f"{W_STRUCT_002}: {block_diff} block(s) removed")

            # Assignment count reduction (W_STRUCT_003)
            if canonical_metrics.assignments < original_metrics.assignments:
                assign_diff = original_metrics.assignments - canonical_metrics.assignments
                warnings.append(f"{W_STRUCT_003}: {assign_diff} assignment(s) removed")

        # Build final summary
        result = " | ".join(summary_parts)
        if warnings:
            result += " | WARNINGS: " + "; ".join(warnings)

        return result

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute write pipeline.

        Args:
            target_path: File path to write to
            content: Full content for new files/overwrites (XOR with changes)
            changes: Field updates for existing files (XOR with content)
            mutations: Optional META field overrides
            base_hash: Optional CAS consistency check hash
            schema: Optional schema name for validation
            debug_grammar: Whether to include compiled grammar in output (default: False)
            format_style: Output formatting mode. One of ``"preserve"`` /
                ``"expanded"`` / ``"compact"`` or omitted.

                .. deprecated:: 1.13.0
                    Passing ``format_style=None`` EXPLICITLY is deprecated.
                    In v1.14.0 the default will change from full canonical
                    re-emit to span-aware ``"preserve"`` mode. To keep the
                    current canonical re-emit behaviour beyond v1.14.0,
                    pass ``format_style="expanded"`` explicitly. To opt in
                    to preserve mode now, pass ``format_style="preserve"``.
                    OMITTING the parameter does NOT emit a warning — that
                    is the supported way to accept the future default
                    silently. See ADR-0006 Sprint 2 addendum §5 Shape B.

        Returns:
            Dictionary with:
            - status: "success" or "error"
            - path: Written file path (on success)
            - canonical_hash: SHA-256 hash of canonical content (on success)
            - corrections: List of corrections applied
            - diff: Compact diff of changes
            - errors: List of errors (on failure)
            - validation_status: VALIDATED | UNVALIDATED | INVALID
            - schema_name: Schema name used (when VALIDATED or INVALID)
            - schema_version: Schema version used (when VALIDATED or INVALID)
            - validation_errors: List of schema validation errors (when INVALID)
            - debug_info: Constraint grammar debug information (when debug_grammar=True)
        """
        # ADR-0006 SR1-T3a (#391, CE follow-up to #392): per-call local list
        # for non-fatal change-path warnings (currently only W_AMBIGUOUS_PATH)
        # emitted by _validate_change_paths. Local-scope ownership eliminates
        # the singleton race that an instance attribute would cause across
        # concurrent MCP invocations on the shared WriteTool() instance held
        # by server.py / http_transport.py.
        change_warnings: list[dict[str, Any]] = []

        # Validate and extract parameters
        params = self.validate_parameters(kwargs)
        target_path = params["target_path"]
        content = params.get("content")
        changes = params.get("changes")
        mutations = params.get("mutations")
        base_hash = params.get("base_hash")
        schema_name = params.get("schema")
        debug_grammar = params.get("debug_grammar", False)
        grammar_hint = params.get("grammar_hint", False)
        lenient = params.get("lenient", False)
        # GH#354: Accept dry_run as alias for corrections_only (either triggers dry-run)
        corrections_only = params.get("corrections_only", False) or params.get("dry_run", False)
        parse_error_policy = params.get("parse_error_policy", "error")
        # GH#376 PR-A: format_style is optional; None preserves today's behaviour.
        #
        # ADR-0006 Sprint 2 addendum §5 Shape B (PR-4 T10): in v1.13.0,
        # passing format_style=None EXPLICITLY emits a DeprecationWarning
        # so callers know the v1.14.0 default flip is coming. Omitting
        # the parameter does NOT warn — that would spam every caller of
        # the default path. The distinction is made by checking
        # ``"format_style" in kwargs`` (explicit) versus absent (omitted).
        # In v1.14.0 the default will flip from full canonical re-emit
        # to span-aware "preserve" mode.
        if "format_style" in kwargs and kwargs["format_style"] is None:
            import warnings as _warnings

            _warnings.warn(
                "Passing format_style=None explicitly is deprecated. "
                "In v1.14.0 the default will change from full canonical "
                "re-emit to span-aware preserve mode. To keep the current "
                "canonical re-emit behaviour, pass format_style='expanded' "
                "explicitly. To opt in to preserve mode now, pass "
                "format_style='preserve'. To accept the future default "
                "silently, omit the parameter entirely.",
                DeprecationWarning,
                stacklevel=2,
            )
        format_style = params.get("format_style")

        if parse_error_policy not in ("error", "salvage"):
            return self._error_envelope(
                target_path,
                [{"code": "E_INPUT", "message": f"Invalid parse_error_policy: {parse_error_policy}"}],
            )

        if format_style is not None and format_style not in FORMAT_STYLE_VALUES:
            return self._error_envelope(
                target_path,
                [
                    {
                        "code": E_INVALID_FORMAT_STYLE,
                        "message": (
                            f"Invalid format_style: {format_style!r}. " f"Expected one of {list(FORMAT_STYLE_VALUES)}."
                        ),
                    }
                ],
            )

        # Initialize result with unified envelope per D2 design
        # I5 (Schema Sovereignty): validation_status must be UNVALIDATED to make bypass visible
        # "Schema bypass shall be visible, never silent" - North Star I5
        result: dict[str, Any] = {
            "status": "success",
            "path": target_path,
            "canonical_hash": "",
            "corrections": [],
            "warnings": [],  # GH#349: Top-level warnings for data loss (I4)
            "diff": "",
            "diff_unified": "",
            "errors": [],
            "validation_status": "UNVALIDATED",  # I5: Explicit bypass until validated
            "validation_hint": self._build_validation_hint(),  # GH#352+361r3: guidance with available schemas
        }

        # STEP 1: Validate path
        path_valid, path_error = self._validate_path(target_path)
        if not path_valid:
            return self._error_envelope(
                target_path,
                [{"code": "E_PATH", "message": path_error}],
            )

        # STEP 2: Validate content XOR changes
        if content is not None and changes is not None:
            return self._error_envelope(
                target_path,
                [
                    {
                        "code": "E_INPUT",
                        "message": "Cannot provide both content and changes - they are mutually exclusive",
                    }
                ],
            )

        path_obj = Path(target_path)
        file_exists = path_obj.exists()

        # Handle modes based on content vs changes
        baseline_content_for_diff = ""
        original_metrics: StructuralMetrics | None = None
        canonical_metrics: StructuralMetrics | None = None
        canonical_content = ""
        corrections: list[dict[str, Any]] = []

        # ADR-0006 SR1-T1 Step 3 §3a: centralised TIER_NORMALIZATION audit
        # log. Threaded through the canonical emit paths via the
        # tier_normalize.active() ContextVar so precise instrumentation
        # sites (notably emitter identifier-dequoting) can record receipts
        # without the public emit() signature having to grow a RepairLog
        # parameter. Drained into ``corrections`` after final emit + after
        # the reconciler bridge has had its chance.
        tier_normalize_log: RepairLog = RepairLog(repairs=[])

        # Determine mode
        normalize_mode = content is None and changes is None

        # GH#377 Strategy A (T8): track whether doc's byte spans (start_byte,
        # end_byte) were computed from the same bytes as baseline_content_for_diff.
        # True only for changes mode and normalize mode (doc parsed from the
        # existing file).  False for content mode (doc parsed from user-supplied
        # new content — spans index the new content, NOT the old baseline).
        # This guards against slicing old baseline bytes using new-content spans,
        # which would produce garbage output.
        _doc_spans_match_baseline = False

        if normalize_mode:
            # NORMALIZE MODE: read existing file, parse, emit canonical form, write back
            # Pure I1 (Syntactic Fidelity) enforcement: normalization alters syntax never semantics
            if not file_exists:
                return self._error_envelope(
                    target_path,
                    [{"code": "E_FILE", "message": "File does not exist - normalize mode requires existing file"}],
                )

            # Read existing file
            try:
                with open(target_path, encoding="utf-8") as f:
                    baseline_content_for_diff = f.read()
            except Exception as e:
                return self._error_envelope(
                    target_path,
                    [{"code": "E_READ", "message": f"Read error: {str(e)}"}],
                )

            # Check base_hash if provided (CAS guard)
            if base_hash:
                current_hash = self._compute_hash(baseline_content_for_diff)
                if current_hash != base_hash:
                    return self._error_envelope(
                        target_path,
                        [
                            {
                                "code": "E_HASH",
                                "message": f"Hash mismatch - file has been modified (expected {base_hash[:8]}..., got {current_hash[:8]}...)",
                            }
                        ],
                    )

            # Feed through parse -> emit pipeline (reuse content-mode logic)
            # I3 (Mirror Constraint): reflect only what is present, create nothing
            content = baseline_content_for_diff
            # GH#377 Strategy A: normalize mode parses the baseline content,
            # so doc spans will be valid against baseline_content_for_diff.
            _doc_spans_match_baseline = True

        if changes is not None:
            # CHANGES MODE (Amend) - file must exist
            if not file_exists:
                return self._error_envelope(
                    target_path,
                    [{"code": "E_FILE", "message": "File does not exist - changes mode requires existing file"}],
                )

            # Read existing file
            try:
                with open(target_path, encoding="utf-8") as f:
                    baseline_content_for_diff = f.read()
            except Exception as e:
                return self._error_envelope(
                    target_path,
                    [{"code": "E_READ", "message": f"Read error: {str(e)}"}],
                )

            # Check base_hash if provided
            if base_hash:
                current_hash = self._compute_hash(baseline_content_for_diff)
                if current_hash != base_hash:
                    return self._error_envelope(
                        target_path,
                        [
                            {
                                "code": "E_HASH",
                                "message": f"Hash mismatch - file has been modified (expected {base_hash[:8]}..., got {current_hash[:8]}...)",
                            }
                        ],
                    )

            # Parse existing content (strict)
            try:
                doc = parse(baseline_content_for_diff)
                original_metrics = extract_structural_metrics(doc)
                # GH#377 Strategy A: doc spans index baseline_content_for_diff.
                _doc_spans_match_baseline = True
            except Exception as e:
                return self._error_envelope(
                    target_path,
                    [{"code": "E_PARSE", "message": f"Parse error: {str(e)}"}],
                )

            # Apply changes with tri-state semantics. CE follow-up to #392:
            # change_warnings is owned by this scope and threaded through; the
            # error envelope branches below ALSO drain it via _error_envelope's
            # corrections argument so deprecation warnings remain visible even
            # when validation fails the request.
            try:
                doc = self._apply_changes(doc, changes, change_warnings=change_warnings)
            except ValueError as e:
                # GH#335: _validate_change_paths raises ValueError with
                # structured error list for unresolvable paths.
                # CE follow-up to #392: drain change_warnings into the error
                # envelope so deprecation warnings remain visible even when the
                # request fails (no warning leaks across calls; buffer is
                # function-local).
                error_list = e.args[0] if e.args and isinstance(e.args[0], list) else []
                if error_list:
                    return self._error_envelope(
                        target_path,
                        error_list,
                        corrections=list(change_warnings),
                    )
                return self._error_envelope(
                    target_path,
                    [{"code": "E_APPLY", "message": f"Apply changes error: {str(e)}"}],
                    corrections=list(change_warnings),
                )
            except Exception as e:
                return self._error_envelope(
                    target_path,
                    [{"code": "E_APPLY", "message": f"Apply changes error: {str(e)}"}],
                    corrections=list(change_warnings),
                )

            # Apply META mutations (if any)
            self._apply_mutations(doc, mutations)

        else:
            # CONTENT MODE (Create/Overwrite)
            assert content is not None

            # baseline for diff: existing file content if overwriting
            if file_exists:
                try:
                    with open(target_path, encoding="utf-8") as f:
                        baseline_content_for_diff = f.read()
                except Exception:
                    baseline_content_for_diff = ""
                if baseline_content_for_diff:
                    try:
                        try:
                            baseline_doc = parse(baseline_content_for_diff)
                        except (LexerError, ParserError):
                            baseline_doc, _ = parse_with_warnings(baseline_content_for_diff)
                        original_metrics = extract_structural_metrics(baseline_doc)
                    except (LexerError, ParserError) as e:
                        # GH#266: parse may fail on pre-repair content (e.g. NAME{qualifier}).
                        # Narrow to parse exceptions; let unexpected errors (IOError,
                        # MemoryError, etc.) propagate naturally.
                        original_metrics = None
                        corrections.append(
                            {
                                "code": "W_BASELINE_METRICS_SKIPPED",
                                "message": f"Baseline metrics skipped: {type(e).__name__}: {e}",
                                "safe": True,
                                "semantics_changed": False,
                            }
                        )

            # Check base_hash if provided AND file exists (CAS guard)
            if base_hash and file_exists:
                current_hash = self._compute_hash(baseline_content_for_diff)
                if current_hash != base_hash:
                    return self._error_envelope(
                        target_path,
                        [
                            {
                                "code": "E_HASH",
                                "message": f"Hash mismatch - file has been modified (expected {base_hash[:8]}..., got {current_hash[:8]}...)",
                            }
                        ],
                    )

            parse_input = content
            parse_input, unwrapped = self._unwrap_markdown_code_fence(parse_input)
            if unwrapped:
                corrections.append(
                    {
                        "code": "W_MARKDOWN_UNWRAP",
                        "message": "Unwrapped markdown code fence before OCTAVE parsing.",
                        "safe": True,
                        "semantics_changed": False,
                    }
                )

            # GH#334: Auto-quote unquoted § references in value positions BEFORE
            # parsing. The lexer is context-free and always produces SECTION tokens
            # for §, which fragments intended string values. Auto-quoting preserves
            # author intent (I1) and logs corrections (I4).
            parse_input, section_quote_corrections = _auto_quote_section_refs_in_values(parse_input)
            corrections.extend(section_quote_corrections)

            if lenient:
                # Detect likely OCTAVE structure using line-anchored patterns to avoid false positives in prose.
                # GH#263 rework round 4: Only strong, unambiguous OCTAVE signals trigger structured mode.
                # - assignment_line (KEY::value): The :: operator is definitively OCTAVE syntax.
                # - envelope_line (===NAME===): Definitively OCTAVE envelope markers.
                # Weak signals like block_line (KEY:\s*$) and meta_block (META:) are excluded
                # because they match prose headers like "Title:", "Note:", "Summary:", "META:".
                # Real OCTAVE files with META: blocks always contain :: assignments inside,
                # so they are still detected via assignment_line.
                assignment_line = re.search(r"(?m)^[ \t]*[A-Za-z_][A-Za-z0-9_.]*::", parse_input) is not None
                envelope_line = re.search(r"(?m)^===.+===\s*$", parse_input) is not None
                looks_structured = assignment_line or envelope_line

                if looks_structured:
                    # GH#263: Pre-process curly-brace annotations ONLY for confirmed OCTAVE content.
                    # Plain text with FOO{bar} must not be mutated (I1 syntactic fidelity).
                    # I4 (Transform Auditability): repairs logged in corrections.
                    parse_input, curly_corrections = self._repair_curly_brace_annotations(parse_input)
                    corrections.extend(curly_corrections)

                if not looks_structured and parse_input.strip():
                    parse_input, wrap_corrections = self._wrap_plain_text_as_doc(parse_input, schema_name)
                    corrections.extend(wrap_corrections)

                try:
                    doc, parse_warnings = parse_with_warnings(parse_input)
                    corrections.extend(self._map_parse_warnings_to_corrections(parse_warnings))
                except Exception as e:
                    if parse_error_policy == "salvage":
                        # Issue #177: Use localized salvaging to preserve document structure
                        doc, salvage_corrections = self._localized_salvage(content, str(e), schema_name)
                        corrections.extend(salvage_corrections)
                    else:
                        return self._error_envelope(
                            target_path,
                            [{"code": "E_PARSE", "message": f"Parse error: {str(e)}"}],
                            corrections,
                        )

            else:
                # Strict tokenization + strict parse
                try:
                    _, tokenize_repairs = tokenize(parse_input)
                except Exception as e:
                    # GH#329: Emit § quoting warnings even on strict tokenize failure path.
                    # GH#334: Include auto-quoting corrections already accumulated in
                    # `corrections` (from the pre-parse auto-quoting step).
                    error_corrections = list(corrections)
                    error_corrections.extend(_detect_unquoted_section_in_values(parse_input))
                    return self._error_envelope(
                        target_path,
                        [
                            {
                                "code": "E_TOKENIZE",
                                "message": f"Tokenization error: {str(e)}",
                            }
                        ],
                        error_corrections,
                    )

                try:
                    # GH#348: Use parse_with_warnings even in strict mode to
                    # capture I4 audit warnings (e.g., W_NUMERIC_KEY_DROPPED).
                    # Silent data loss must be reported regardless of mode.
                    # GH#361r3: Pass strict_structure=True so structural issues
                    # (unclosed lists, nested inline maps) raise ParserError
                    # instead of being silently recovered.
                    doc, strict_parse_warnings = parse_with_warnings(parse_input, strict_structure=True)
                    corrections.extend(self._map_parse_warnings_to_corrections(strict_parse_warnings))
                except Exception as e:
                    # GH#334: Start from existing corrections (includes auto-quoting).
                    strict_corrections = list(corrections)
                    strict_corrections.extend(self._track_corrections(parse_input, parse_input, tokenize_repairs))
                    # GH#329: Emit § quoting warnings even on strict parse failure.
                    strict_corrections.extend(_detect_unquoted_section_in_values(parse_input))
                    return self._error_envelope(
                        target_path,
                        [
                            {
                                "code": "E_PARSE",
                                "message": f"Parse error: {str(e)}",
                            }
                        ],
                        strict_corrections,
                    )

                corrections.extend(self._track_corrections(parse_input, parse_input, tokenize_repairs))

            # Detect unquoted § in value positions and emit guidance warnings.
            # This runs on parse_input (after markdown fence unwrapping) so that
            # outer ``` fences don't suppress the warning via literal zone detection.
            # The lexer/parser behavior is correct; this is purely user-facing guidance.
            section_warnings = _detect_unquoted_section_in_values(parse_input)
            corrections.extend(section_warnings)

            # GH#403: Detect annotation identifier content that violates discipline
            # thresholds (len > 32 chars OR underscore-token count >= 5).
            # Non-blocking advisory — goes to corrections only, not errors.
            annotation_discipline_warnings = _detect_annotation_too_long(parse_input)
            corrections.extend(annotation_discipline_warnings)

            # GH#452: Detect snake-case prose blobs in reasoning-field positions.
            # Refined contract per operator comment 4549996376. v1 ADVISORY only.
            snake_case_blob_warnings = _detect_snake_case_blob(parse_input)
            corrections.extend(snake_case_blob_warnings)

            # Structural advisory: map-as-inline-array root pattern.
            # Advisory only — non-blocking, routed to corrections.
            inline_array_root_warnings = _detect_inline_array_root(parse_input)
            corrections.extend(inline_array_root_warnings)

            # Structural advisory: flat sibling keys sharing a redundant prefix.
            # Advisory only — non-blocking, routed to corrections.
            flat_prefix_warnings = _detect_flat_prefix_scalar(parse_input)
            corrections.extend(flat_prefix_warnings)

            # Apply META mutations (if any)
            self._apply_mutations(doc, mutations)

            # GH#302: Inherit frontmatter from existing file when new content lacks it.
            # When an agent rewrites a file via content mode but omits YAML frontmatter,
            # the original frontmatter (required for skill/agent discovery) would be lost.
            # I3 (Mirror Constraint): preserve what exists; do not silently destroy.
            if not normalize_mode and doc.raw_frontmatter is None and file_exists and baseline_content_for_diff:
                try:
                    baseline_doc = parse(baseline_content_for_diff)
                    if baseline_doc.raw_frontmatter is not None:
                        doc.raw_frontmatter = baseline_doc.raw_frontmatter
                        # ADR-0006 SR2-T2 PR-2 (GH#377): the inheritance
                        # branch mutates a post-parse field on doc. Per
                        # ADR §3 frontmatter-inheritance policy, mark the
                        # whole document dirty so any future Strategy-A
                        # emitter pass cannot silently splice the
                        # frontmatter region from a stale baseline.
                        doc.dirty = True
                        corrections.append(
                            {
                                "code": "W_FRONTMATTER_INHERITED",
                                "message": "YAML frontmatter inherited from existing file (new content lacked frontmatter).",
                                "safe": True,
                                "semantics_changed": False,
                            }
                        )
                except (LexerError, ParserError) as exc:
                    corrections.append(
                        {
                            "code": "W_FRONTMATTER_INHERITANCE_SKIPPED",
                            "message": (
                                f"Frontmatter inheritance skipped: baseline file could not be parsed ({type(exc).__name__}: {exc})"
                            ),
                            "safe": True,
                            "semantics_changed": False,
                        }
                    )

        # Emit canonical form (may be re-emitted after schema repair).
        # GH#376 PR-A / GH#377 Strategy A (T8): format_style routes through
        # _emit_with_style — a single canonical AST→bytes orchestrator that
        # applies expanded/compact AST pre-passes or Strategy A span-aware
        # preserve emit, all via the SAME emit() call (I1 Single-Canon Discipline).
        # HC-1: _to_baseline_bytes() converts raw str → post-NFC bytes so
        # start_byte/end_byte slices are valid.
        # ADR-0006 SR1-T1 Step 3: emit under tier_normalize.active() so
        # precise instrumentation (identifier dequoting) records its receipts.
        try:
            with tier_normalize.active(tier_normalize_log):
                canonical_content = _emit_with_style(
                    doc,
                    baseline_bytes=_to_baseline_bytes(baseline_content_for_diff),
                    new_bytes=content,
                    format_style=format_style,
                    corrections=corrections,
                    spans_valid_for_baseline=_doc_spans_match_baseline,
                )
            canonical_metrics = extract_structural_metrics(doc)
        except OctaveASTCycleError as cyc:
            # Cubic C3 (#376 PR-A): preserve the structured E_AST_CYCLE code
            # so clients can discriminate cycle errors from generic emit
            # failures. MUST appear BEFORE the broad ``except Exception``
            # below — OctaveASTCycleError is a ValueError subclass and would
            # otherwise be swallowed into the generic E_EMIT envelope.
            #
            # CE follow-up to #392: change_warnings (e.g. W_AMBIGUOUS_PATH)
            # captured by _validate_change_paths during the changes-mode pass
            # are merged into the error envelope here. Without this drain the
            # success-path drain at line ~3519 would never run on emit failure
            # and the deprecation signal would be silently dropped.
            return self._error_envelope(
                target_path,
                [{"code": OctaveASTCycleError.code, "message": str(cyc)}],
                corrections + list(change_warnings),
            )
        except Exception as e:
            # CE follow-up to #392: same change_warnings drain as the
            # E_AST_CYCLE branch above — emit failure must not lose
            # W_AMBIGUOUS_PATH (or any future change-path warning).
            return self._error_envelope(
                target_path,
                [{"code": "E_EMIT", "message": f"Emit error: {str(e)}"}],
                corrections + list(change_warnings),
            )

        result["corrections"] = corrections

        # GH#361r5: warnings generation moved AFTER schema repair logic below.
        # Previously built here, but schema repairs can append safe=False
        # corrections that would be excluded from the warnings array.

        # GH#287 Decision 6: Confirmation echo — show SOURCE→STRICT compilations
        # When lenient parsing produces corrections, build a compilations list
        # showing the delta in structured format. Cap at 5 entries + summary.
        if lenient:
            compilations: list[dict[str, str] | str] = []
            _compilation_rule_map = {
                "W002": "ascii_to_unicode",
                "W_LENIENT_MULTI_WORD_COALESCE": "multi_word_coalesce",
                "W_LENIENT_SOURCE_COMPILE_VALUE": "operator_rich_value",
                "W_LENIENT_DUPLICATE_KEY": "duplicate_key",
                "W_MARKDOWN_UNWRAP": "markdown_unwrap",
                "W_SALVAGE_LOCALIZED": "salvage",
            }
            for c in corrections:
                code = c.get("code", "")
                before = c.get("before", "")
                after = c.get("after", "")
                if not before and not after:
                    continue
                rule = _compilation_rule_map.get(code, "normalization")
                # Format source and strict in KEY::value style where applicable
                source_str = str(before) if before else ""
                strict_str = str(after) if after else source_str
                if source_str or strict_str:
                    compilations.append(
                        {
                            "source": source_str,
                            "strict": strict_str,
                            "rule": rule,
                        }
                    )

            # Cap at 5 entries + summary per ADR-0005
            if len(compilations) > 5:
                total = len(compilations)
                compilations = compilations[:5]
                compilations.append(f"...and {total - 5} other normalizations applied.")

            result["compilations"] = compilations
        else:
            result["compilations"] = []

        # Issue #235 T14: Literal zone reporting (§8.2, §8.4)
        # After emit, populate zone_report when literal zones are present.
        zones = _count_literal_zones(doc)
        if zones:
            result["contains_literal_zones"] = True
            result["literal_zone_count"] = len(zones)
            result["literal_zones_validated"] = False  # I5: always False (D4: content opaque)
            result["zone_report"] = {
                "dsl": {"status": "valid", "errors": []},
                "container": {
                    "status": "preserved" if doc.raw_frontmatter else "absent",
                    "validation_status": "UNVALIDATED",  # I5: default before schema validation runs
                },
                "literal": {
                    "status": "preserved",
                    "count": len(zones),
                    "content_validated": False,  # D4: content opaque; I5: honest
                    "zones": zones,
                },
            }
            result["literal_zone_repair_log"] = build_literal_zone_repair_log(zones, doc, "octave_write").to_dict()

        # GH#370: Structural validation (runs regardless of schema).
        # Detects W_DUPLICATE_TARGET warnings that must surface in default flow.
        # This is a lightweight check that doesn't require schema binding.

        structural_validator = Validator(schema=None)
        structural_warnings = structural_validator.validate(doc, strict=False, section_schemas=None)

        # Filter to only warnings (severity='warning') and add them as corrections
        # so they surface in the result.
        for warning in structural_warnings:
            if warning.severity == "warning":
                result["corrections"].append(
                    {
                        "code": warning.code,
                        "tier": "STRUCTURAL_CHECK",
                        "message": warning.message,
                        "field": warning.field_path,
                        "safe": True,  # W_DUPLICATE_TARGET is a safety net, not data loss
                        "semantics_changed": False,
                    }
                )

        # ADR-0006 SR1-T3a (#391, CE follow-up to #392): drain the per-call
        # change_warnings local (currently W_AMBIGUOUS_PATH on the conflicted-
        # document case) into the unified corrections list, alongside the
        # structural-validator warnings above. Local-scope ownership ensures no
        # cross-invocation leakage on the shared WriteTool() singleton.
        if change_warnings:
            result["corrections"].extend(change_warnings)

        # Schema Validation (I5 Schema Sovereignty)
        if schema_name:
            # Old-style dict schemas (META-only, backwards compatibility)
            schema_def = get_builtin_schema(schema_name)

            # New-style SchemaDefinition schemas (constraint validation via section_schemas)
            schema_definition: SchemaDefinition | None = None
            section_schemas: dict[Any, SchemaDefinition] | None = None

            # Issue #150: Hermetic resolution for frozen@ and latest schema references
            if schema_name.startswith("frozen@") or schema_name == "latest":
                try:
                    schema_path = resolve_hermetic_standard(schema_name)
                    schema_definition = load_schema(schema_path)
                except Exception:
                    schema_definition = None
            else:
                try:
                    schema_definition = load_schema_by_name(schema_name)
                except Exception:
                    schema_definition = None

            if schema_definition is not None and schema_definition.fields:
                # Map only the schema's name to its definition (validate.py Gap_1 pattern)
                section_schemas = {schema_definition.name: schema_definition}

            has_schema = schema_def is not None or (schema_definition is not None and bool(schema_definition.fields))

            # Add debug grammar information if requested
            if debug_grammar and schema_definition is not None:
                debug_info: dict[str, Any] = {
                    "schema_name": schema_definition.name,
                    "schema_version": schema_definition.version or "unknown",
                    "field_constraints": {},
                }
                for field_name, field_def in schema_definition.fields.items():
                    if hasattr(field_def, "pattern") and field_def.pattern and field_def.pattern.constraints:
                        chain = field_def.pattern.constraints
                        debug_info["field_constraints"][field_name] = {
                            "chain": chain.to_string(),
                            "compiled_regex": chain.compile(),
                        }
                result["debug_info"] = debug_info

            if has_schema:
                # I5: Schema-validated documents shall record schema name and version used
                if schema_def is not None:
                    result["schema_name"] = schema_def.get("name", schema_name)
                    result["schema_version"] = schema_def.get("version", "unknown")
                elif schema_definition is not None:
                    result["schema_name"] = schema_definition.name
                    result["schema_version"] = schema_definition.version or "unknown"

                validator = Validator(schema=schema_def)
                validation_errors = validator.validate(doc, strict=False, section_schemas=section_schemas)

                # Lenient mode: apply minimal safe repairs for builtin dict schemas (META-only)
                if lenient and schema_def is not None and validation_errors:
                    meta_schema = schema_def.get("META", {})
                    fields = meta_schema.get("fields", {})
                    did_repair = False

                    for field_name, field_spec in fields.items():
                        if field_spec.get("type") != "ENUM":
                            continue
                        allowed_values = field_spec.get("values", [])
                        current = doc.meta.get(field_name)
                        if not isinstance(current, str):
                            continue

                        if current in allowed_values:
                            continue

                        matches = [v for v in allowed_values if isinstance(v, str) and v.lower() == current.lower()]
                        if len(matches) != 1:
                            continue

                        canonical_value = matches[0]
                        # ADR-0006 SR2-T2 PR-2 (GH#377): paired-write rule.
                        # doc.meta[k] mutation in the enum-casefold branch
                        # must pair with doc.meta_dirty[k]=True. The source
                        # bytes for this META key would re-introduce the
                        # un-casefolded value on re-parse, so Strategy A's
                        # emitter (PR-3) must re-emit this key from the
                        # AST rather than splice from baseline (I1).
                        doc.meta[field_name] = canonical_value
                        doc.meta_dirty[field_name] = True
                        did_repair = True
                        result["corrections"].append(
                            {
                                "code": "ENUM_CASEFOLD",
                                "tier": "REPAIR",
                                "before": current,
                                "after": canonical_value,
                                "safe": True,
                                "semantics_changed": False,
                                "message": f"Schema repair: enum casefold {field_name}",
                            }
                        )

                    if did_repair:
                        # GH#376 PR-A: re-emit through the single-canon orchestrator
                        # so format_style applies to schema-repaired output too.
                        # ADR-0006 SR1-T1 Step 3: re-emit also under
                        # tier_normalize.active() so post-repair dequoting is logged.
                        with tier_normalize.active(tier_normalize_log):
                            canonical_content = _emit_with_style(
                                doc,
                                baseline_bytes=_to_baseline_bytes(baseline_content_for_diff),
                                new_bytes=content,
                                format_style=format_style,
                                corrections=result["corrections"],
                                spans_valid_for_baseline=_doc_spans_match_baseline,
                            )
                        canonical_metrics = extract_structural_metrics(doc)
                        validation_errors = validator.validate(doc, strict=False, section_schemas=section_schemas)

                # Lenient mode may apply safe schema repairs (enum casefold, type coercion)
                if lenient and schema_definition is not None and validation_errors:
                    try:
                        doc, repair_log = repair(doc, validation_errors, fix=True, schema=schema_definition)
                        for entry in repair_log.repairs:
                            result["corrections"].append(
                                {
                                    "code": entry.rule_id,
                                    "tier": entry.tier.value,
                                    "before": entry.before,
                                    "after": entry.after,
                                    "safe": entry.safe,
                                    "semantics_changed": entry.semantics_changed,
                                    "message": f"Schema repair: {entry.rule_id}",
                                }
                            )
                        # Re-emit canonical after repairs (GH#376 PR-A: single-canon
                        # orchestrator so format_style applies to repaired output).
                        # ADR-0006 SR1-T1 Step 3: re-emit also under
                        # tier_normalize.active() so post-repair dequoting is logged.
                        with tier_normalize.active(tier_normalize_log):
                            canonical_content = _emit_with_style(
                                doc,
                                baseline_bytes=_to_baseline_bytes(baseline_content_for_diff),
                                new_bytes=content,
                                format_style=format_style,
                                corrections=result["corrections"],
                                spans_valid_for_baseline=_doc_spans_match_baseline,
                            )
                        canonical_metrics = extract_structural_metrics(doc)
                        # Revalidate
                        validation_errors = validator.validate(doc, strict=False, section_schemas=section_schemas)
                    except Exception:
                        # Best-effort: if repair fails, preserve original validation_errors
                        pass

                if validation_errors:
                    result["validation_status"] = "INVALID"
                    result.pop("validation_hint", None)  # GH#352: remove hint when validated
                    result["validation_errors"] = [
                        {"code": err.code, "message": err.message, "field": err.field_path} for err in validation_errors
                    ]

                    # GH#278: Include compiled grammar hint on INVALID when requested
                    if grammar_hint and schema_definition is not None:
                        try:
                            compiled = GBNFCompiler().compile_schema(schema_definition, include_envelope=True)
                            result["grammar_hint"] = {
                                "format": "gbnf",
                                "grammar": compiled,
                                "usage_hints": USAGE_HINTS,
                            }
                        except Exception:
                            result["grammar_hint"] = {
                                "error": "E_GRAMMAR_COMPILE",
                                "message": "Grammar compilation failed for this schema",
                            }
                else:
                    result["validation_status"] = "VALIDATED"
                    result.pop("validation_hint", None)  # GH#352: remove hint when validated
            else:
                # GH#355: Schema not found - remain UNVALIDATED but list available schemas
                # I5 (Schema Sovereignty): make available options visible so agents can self-correct
                result["available_schemas"] = self._list_available_schemas()

        # ADR-0006 SR1-T1 Step 3 §3a: drain the centralised TIER_NORMALIZATION
        # log into ``corrections``. Mirrors the schema-repair drain pattern
        # immediately above (the lenient-mode ``repair_log.repairs`` loop).
        #
        # The reconciler bridge runs AFTER precise loggers have had their
        # chance — if the final ``canonical_content`` differs from the
        # user's submitted bytes AND no precise NORMALIZATION entries
        # account for the diff, a single coarse-grained
        # TIER_RECONCILE_CANONICAL receipt is emitted (closes the audit-
        # cardinality gap for blank-line stripping and triple-quote
        # collapse until Sprint 3+ trivia + new lexer W-code).
        #
        # Cubic AI P2 fix (PR #399 review 4265564132): reconcile against
        # the USER-SUBMITTED bytes (``content``), not the OLD on-disk
        # baseline (``baseline_content_for_diff``). The bridge exists to
        # catch transformations the parse→canonical-emit pipeline applied
        # to user intent; conflating "user changed the file's content"
        # with "canonical normaliser altered bytes" produced false-
        # positive entries in changes-mode and content-mode overwrites.
        #
        # In ``changes`` and ``normalize_mode`` the user did NOT submit
        # raw bytes (they submitted a delta, or asked for in-place
        # normalisation), so there are no "pre-emit intended bytes"
        # against which a coarse-grained bridge can correctly reconcile.
        # The precise was_quoted logger still fires in those modes —
        # only the bridge is suppressed. Per §3a the reconciler
        # self-deprecates without code change when precise upstream
        # instrumentation lands.
        if not normalize_mode and changes is None and content is not None:
            tier_normalize.reconcile_canonical_emission(
                tier_normalize_log,
                baseline_bytes=content,
                canonical_bytes=canonical_content,
            )
        for entry in tier_normalize_log.repairs:
            result["corrections"].append(
                {
                    "code": entry.rule_id,
                    "tier": entry.tier.value,
                    "before": entry.before,
                    "after": entry.after,
                    "safe": entry.safe,
                    "semantics_changed": entry.semantics_changed,
                    "message": f"Tier normalization: {entry.rule_id}",
                }
            )

        # GH#349 + GH#361r5: Surface data-loss corrections as top-level warnings (I4).
        # Agents can detect data loss by checking result["warnings"] without
        # parsing corrections internals. Any correction with safe=False
        # indicates data loss and is promoted to the warnings array.
        # IMPORTANT: This MUST run AFTER schema repair logic above, which may
        # append additional safe=False corrections to result["corrections"].
        result["warnings"] = [
            {"code": c["code"], "message": c["message"], "line": c.get("line", 0)}
            for c in result["corrections"]
            if c.get("safe") is False
        ]

        # I4 (Transform Auditability): record the mode in the response envelope
        if normalize_mode:
            result["mode"] = "normalize"

        # Diff-first output + hashes (works for dry-run)
        result["diff_unified"] = self._build_unified_diff(baseline_content_for_diff, canonical_content)
        result["canonical_hash"] = self._compute_hash(canonical_content)

        content_changed = baseline_content_for_diff != canonical_content
        result["diff"] = self._generate_diff(
            len(baseline_content_for_diff),
            len(canonical_content),
            original_metrics,
            canonical_metrics,
            content_changed=content_changed,
        )

        if corrections_only:
            # Explicit dry-run: no filesystem writes, no mkdir side effects
            return result

        # WRITE FILE (atomic + symlink-safe)
        try:
            # Ensure parent directory exists
            path_obj.parent.mkdir(parents=True, exist_ok=True)

            # Reject symlink targets (security)
            if path_obj.exists() and path_obj.is_symlink():
                return self._error_envelope(
                    target_path,
                    [
                        {
                            "code": "E_WRITE",
                            "message": f"Cannot write to symlink target '{target_path}'. Use corrections_only=true to preview normalization without writing.",
                        }
                    ],
                    result["corrections"],
                )

            # Preserve permissions if file exists
            original_mode = None
            if path_obj.exists():
                original_stat = os.stat(target_path)
                original_mode = original_stat.st_mode & 0o777

            # Atomic write: tempfile -> fsync -> os.replace
            fd, temp_path = tempfile.mkstemp(dir=path_obj.parent, suffix=".tmp", text=True)
            try:
                if original_mode is not None:
                    os.fchmod(fd, original_mode)

                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(canonical_content)
                    f.flush()
                    os.fsync(f.fileno())

                # TOCTOU protection: recheck base_hash before replace
                if base_hash and file_exists:
                    with open(target_path, encoding="utf-8") as verify_f:
                        verify_content = verify_f.read()
                    verify_hash = self._compute_hash(verify_content)
                    if verify_hash != base_hash:
                        os.unlink(temp_path)
                        return self._error_envelope(
                            target_path,
                            [
                                {
                                    "code": "E_HASH",
                                    "message": f"Hash mismatch before write - file was modified during operation (expected {base_hash[:8]}..., got {verify_hash[:8]}...)",
                                }
                            ],
                            result["corrections"],
                        )

                # Atomic replace
                os.replace(temp_path, target_path)

            except Exception:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise

        except PermissionError:
            return self._error_envelope(
                target_path,
                [
                    {
                        "code": "E_WRITE",
                        "message": f"Permission denied writing '{target_path}'. Use corrections_only=true to preview normalization without writing.",
                    }
                ],
                result["corrections"],
            )
        except Exception as e:
            return self._error_envelope(
                target_path,
                [
                    {
                        "code": "E_WRITE",
                        "message": f"Write error: {str(e)}. Use corrections_only=true to preview normalization without writing.",
                    }
                ],
                result["corrections"],
            )

        return result
