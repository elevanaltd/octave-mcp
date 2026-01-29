"""MCP tool for OCTAVE write (GH#51 Tool Consolidation).

Implements octave_write tool - replaces octave_create + octave_amend with:
- Unified write with content XOR changes parameter model
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
from dataclasses import dataclass, field
from difflib import unified_diff
from pathlib import Path
from typing import Any

from octave_mcp.core.ast_nodes import Assignment, ASTNode, Block, Document, InlineMap, ListValue, Section
from octave_mcp.core.emitter import emit
from octave_mcp.core.hydrator import resolve_hermetic_standard
from octave_mcp.core.lexer import tokenize
from octave_mcp.core.parser import parse, parse_with_warnings
from octave_mcp.core.repair import repair
from octave_mcp.core.schema_extractor import SchemaDefinition
from octave_mcp.core.validator import Validator
from octave_mcp.mcp.base_tool import BaseTool, SchemaBuilder
from octave_mcp.schemas.loader import get_builtin_schema, load_schema, load_schema_by_name

# Sentinel for DELETE operation in tri-state changes
DELETE_SENTINEL = {"$op": "DELETE"}

# Structural warning codes (Issue #92)
W_STRUCT_001 = "W_STRUCT_001"  # Section marker loss
W_STRUCT_002 = "W_STRUCT_002"  # Block count reduction
W_STRUCT_003 = "W_STRUCT_003"  # Assignment count reduction


@dataclass
class StructuralMetrics:
    """Metrics for structural comparison of OCTAVE documents.

    Tracks counts of structural elements to detect potential data loss
    during normalization or transformation.
    """

    sections: int = 0  # Count of Section nodes
    section_markers: set[str] = field(default_factory=set)  # Section IDs found
    blocks: int = 0  # Count of Block nodes
    assignments: int = 0  # Count of Assignment nodes


def extract_structural_metrics(doc: Document) -> StructuralMetrics:
    """Extract structural metrics from a parsed OCTAVE document.

    Recursively traverses the AST to count structural elements.

    Args:
        doc: Parsed Document AST

    Returns:
        StructuralMetrics with counts of structural elements
    """
    metrics = StructuralMetrics()

    def traverse(nodes: list[ASTNode]) -> None:
        """Recursively count structural elements."""
        for node in nodes:
            if isinstance(node, Section):
                metrics.sections += 1
                metrics.section_markers.add(node.section_id)
                traverse(node.children)
            elif isinstance(node, Block):
                metrics.blocks += 1
                traverse(node.children)
            elif isinstance(node, Assignment):
                metrics.assignments += 1

    traverse(doc.sections)
    return metrics


def _is_delete_sentinel(value: Any) -> bool:
    """Check if value is the DELETE sentinel.

    Args:
        value: Value to check

    Returns:
        True if value is the DELETE sentinel
    """
    return isinstance(value, dict) and value.get("$op") == "DELETE"


def _normalize_value_for_ast(value: Any) -> Any:
    """Normalize a Python value to an AST-compatible type.

    I1 (Syntactic Fidelity): Ensures values are properly typed for emission.

    Python lists must be wrapped in ListValue to emit correct OCTAVE syntax.
    Without this, str(list) produces "['a', 'b']" which is invalid OCTAVE.

    Python dicts must be wrapped in InlineMap to emit correct OCTAVE syntax.
    Without this, str(dict) produces "{'key': 'value'}" which is invalid OCTAVE.
    Issue #176: Nested dicts should produce valid OCTAVE like [key::value], not Python repr.

    Args:
        value: Python value from changes dict

    Returns:
        AST-compatible value (ListValue for lists, InlineMap for dicts, original for others)
    """
    if isinstance(value, list):
        # Recursively normalize list items
        normalized_items = [_normalize_value_for_ast(item) for item in value]
        return ListValue(items=normalized_items)
    elif isinstance(value, dict):
        # Issue #176: Convert dicts to InlineMap to produce valid OCTAVE syntax
        # InlineMap emits as [key::value,key2::value2] which is valid OCTAVE
        # Without this, str(dict) produces "{'key': 'value'}" which is INVALID OCTAVE
        # Recursively normalize all values in the dict
        normalized_pairs = {k: _normalize_value_for_ast(v) for k, v in value.items()}
        return InlineMap(pairs=normalized_pairs)
    # Other types (str, int, bool, None, etc.) are handled by emit_value directly
    return value


class WriteTool(BaseTool):
    """MCP tool for octave_write - unified write operation for OCTAVE files."""

    # Security: allowed file extensions
    ALLOWED_EXTENSIONS = {".oct.md", ".octave", ".md"}

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
        envelope_match = re.search(r"^===([A-Za-z_][A-Za-z0-9_]*)===\s*$", content, re.MULTILINE)
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
        lines = content.split("\n")
        salvaged_sections: list[ASTNode] = []
        error_lines: list[tuple[int, str]] = []
        current_valid_lines: list[str] = []

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

            # Try to parse this line as valid OCTAVE
            if stripped:
                # Wrap in minimal document for parsing
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
                corrections.append(
                    {
                        "code": "W002",
                        "tier": "NORMALIZATION",
                        "message": f"ASCII operator -> Unicode: {w.get('original', '')} -> {w.get('normalized', '')}",
                        "line": w.get("line", 0),
                        "column": w.get("column", 0),
                        "before": w.get("original", ""),
                        "after": w.get("normalized", ""),
                        "safe": True,
                        "semantics_changed": False,
                    }
                )
                continue

            if w_type == "lenient_parse":
                subtype = w.get("subtype", "unknown")
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
            description="Full content for new files or overwrites. Mutually exclusive with changes.",
        )

        schema.add_parameter(
            "changes",
            "object",
            required=False,
            description='Dictionary of field updates for existing files. Uses tri-state semantics: absent=no-op, {"$op":"DELETE"}=remove, null=empty.',
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

        schema.add_parameter("schema", "string", required=False, description="Schema name for validation (I5).")

        schema.add_parameter(
            "debug_grammar",
            "boolean",
            required=False,
            description="If True, include compiled regex/grammar in output for debugging constraint evaluation.",
        )

        schema.add_parameter(
            "lenient",
            "boolean",
            required=False,
            description="If True, enable deterministic lenient parsing + optional schema repairs.",
        )

        schema.add_parameter(
            "corrections_only",
            "boolean",
            required=False,
            description="If True, return corrections/diff without writing to disk (dry run).",
        )

        schema.add_parameter(
            "parse_error_policy",
            "string",
            required=False,
            description='Policy when tokenization/parsing fails in lenient mode: "error" (default) or "salvage".',
            enum=["error", "salvage"],
        )

        return schema.build()

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
                        return False, "Symlinks in path are not allowed for security reasons"

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
        for token_repair in tokenize_repairs:
            corrections.append(
                {
                    "code": "W002",
                    "message": f"ASCII operator -> Unicode: {token_repair.get('original', '')} -> {token_repair.get('normalized', '')}",
                    "line": token_repair.get("line", 0),
                    "column": token_repair.get("column", 0),
                    "before": token_repair.get("original", ""),
                    "after": token_repair.get("normalized", ""),
                }
            )

        return corrections

    def _apply_changes(self, doc: Any, changes: dict[str, Any]) -> Any:
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
                - "META": {...} -> replaces entire doc.meta block

        Returns:
            Modified document
        """
        for key, new_value in changes.items():
            # Check for dot-notation: META.FIELD
            if key.startswith("META."):
                # Extract the field name after "META."
                field_name = key[5:]  # Remove "META." prefix
                if _is_delete_sentinel(new_value):
                    # Delete field from doc.meta
                    if field_name in doc.meta:
                        del doc.meta[field_name]
                else:
                    # Update or add field in doc.meta
                    # I1 (Syntactic Fidelity): Normalize Python values to AST types
                    # Without this, Python lists emit as "['a', 'b']" instead of "[a,b]"
                    doc.meta[field_name] = _normalize_value_for_ast(new_value)
            elif key == "META" and isinstance(new_value, dict):
                # Replace entire META block with new dict
                if not _is_delete_sentinel(new_value):
                    # I1 (Syntactic Fidelity): Normalize all values in META block
                    # Without this, Python lists emit as "['a', 'b']" instead of "[a,b]"
                    doc.meta = {k: _normalize_value_for_ast(v) for k, v in new_value.items()}
                else:
                    # DELETE sentinel on META clears the entire block
                    doc.meta = {}
            elif _is_delete_sentinel(new_value):
                # I2: DELETE sentinel - remove field entirely from sections
                doc.sections = [s for s in doc.sections if not (isinstance(s, Assignment) and s.key == key)]
            else:
                # Update or set to null in sections
                # I1 (Syntactic Fidelity): Normalize Python values to AST types
                normalized_value = _normalize_value_for_ast(new_value)
                found = False
                for section in doc.sections:
                    if isinstance(section, Assignment) and section.key == key:
                        section.value = normalized_value
                        found = True
                        break

                # If not found and not deleting, add new field
                if not found:
                    # Create new assignment node with normalized value
                    new_assignment = Assignment(key=key, value=normalized_value)
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
                continue
            doc.meta[key] = _normalize_value_for_ast(value)

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
        # Validate and extract parameters
        params = self.validate_parameters(kwargs)
        target_path = params["target_path"]
        content = params.get("content")
        changes = params.get("changes")
        mutations = params.get("mutations")
        base_hash = params.get("base_hash")
        schema_name = params.get("schema")
        debug_grammar = params.get("debug_grammar", False)
        lenient = params.get("lenient", False)
        corrections_only = params.get("corrections_only", False)
        parse_error_policy = params.get("parse_error_policy", "error")

        if parse_error_policy not in ("error", "salvage"):
            return self._error_envelope(
                target_path,
                [{"code": "E_INPUT", "message": f"Invalid parse_error_policy: {parse_error_policy}"}],
            )

        # Initialize result with unified envelope per D2 design
        # I5 (Schema Sovereignty): validation_status must be UNVALIDATED to make bypass visible
        # "Schema bypass shall be visible, never silent" - North Star I5
        result: dict[str, Any] = {
            "status": "success",
            "path": target_path,
            "canonical_hash": "",
            "corrections": [],
            "diff": "",
            "diff_unified": "",
            "errors": [],
            "validation_status": "UNVALIDATED",  # I5: Explicit bypass until validated
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

        if content is None and changes is None:
            return self._error_envelope(
                target_path,
                [{"code": "E_INPUT", "message": "Must provide either content or changes"}],
            )

        path_obj = Path(target_path)
        file_exists = path_obj.exists()

        # Handle modes based on content vs changes
        baseline_content_for_diff = ""
        original_metrics: StructuralMetrics | None = None
        canonical_metrics: StructuralMetrics | None = None
        canonical_content = ""
        corrections: list[dict[str, Any]] = []

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
            except Exception as e:
                return self._error_envelope(
                    target_path,
                    [{"code": "E_PARSE", "message": f"Parse error: {str(e)}"}],
                )

            # Apply changes with tri-state semantics
            try:
                doc = self._apply_changes(doc, changes)
            except Exception as e:
                return self._error_envelope(
                    target_path,
                    [{"code": "E_APPLY", "message": f"Apply changes error: {str(e)}"}],
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
                        baseline_doc = parse(baseline_content_for_diff)
                    except Exception:
                        baseline_doc, _ = parse_with_warnings(baseline_content_for_diff)
                    original_metrics = extract_structural_metrics(baseline_doc)

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

            if lenient:
                # Detect likely OCTAVE structure using line-anchored patterns to avoid false positives in prose.
                # Example false positive to avoid: "use Foo::Bar" in a sentence.
                assignment_line = re.search(r"(?m)^[ \t]*[A-Za-z_][A-Za-z0-9_.]*::", parse_input) is not None
                block_line = re.search(r"(?m)^[ \t]*[A-Za-z_][A-Za-z0-9_.]*:\s*$", parse_input) is not None
                meta_block = re.search(r"(?m)^META:\s*$", parse_input) is not None
                envelope_line = re.search(r"(?m)^===.+===\s*$", parse_input) is not None
                looks_structured = assignment_line or block_line or meta_block or envelope_line
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
                    return self._error_envelope(
                        target_path,
                        [{"code": "E_TOKENIZE", "message": f"Tokenization error: {str(e)}"}],
                    )

                try:
                    doc = parse(parse_input)
                except Exception as e:
                    strict_corrections = self._track_corrections(parse_input, parse_input, tokenize_repairs)
                    return self._error_envelope(
                        target_path,
                        [{"code": "E_PARSE", "message": f"Parse error: {str(e)}"}],
                        strict_corrections,
                    )

                corrections.extend(self._track_corrections(parse_input, parse_input, tokenize_repairs))

            # Apply META mutations (if any)
            self._apply_mutations(doc, mutations)

        # Emit canonical form (may be re-emitted after schema repair)
        try:
            canonical_content = emit(doc)
            canonical_metrics = extract_structural_metrics(doc)
        except Exception as e:
            return self._error_envelope(
                target_path,
                [{"code": "E_EMIT", "message": f"Emit error: {str(e)}"}],
                corrections,
            )

        result["corrections"] = corrections

        # Schema Validation (I5 Schema Sovereignty)
        if schema_name:
            # Old-style dict schemas (META-only, backwards compatibility)
            schema_def = get_builtin_schema(schema_name)

            # New-style SchemaDefinition schemas (constraint validation via section_schemas)
            schema_definition: SchemaDefinition | None = None
            section_schemas: dict[str, SchemaDefinition] | None = None

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
                        doc.meta[field_name] = canonical_value
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
                        canonical_content = emit(doc)
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
                        # Re-emit canonical after repairs
                        canonical_content = emit(doc)
                        canonical_metrics = extract_structural_metrics(doc)
                        # Revalidate
                        validation_errors = validator.validate(doc, strict=False, section_schemas=section_schemas)
                    except Exception:
                        # Best-effort: if repair fails, preserve original validation_errors
                        pass

                if validation_errors:
                    result["validation_status"] = "INVALID"
                    result["validation_errors"] = [
                        {"code": err.code, "message": err.message, "field": err.field_path} for err in validation_errors
                    ]
                else:
                    result["validation_status"] = "VALIDATED"
            # else: schema not found - remain UNVALIDATED (bypass is visible)

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
                    [{"code": "E_WRITE", "message": "Cannot write to symlink target"}],
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

        except Exception as e:
            return self._error_envelope(
                target_path,
                [{"code": "E_WRITE", "message": f"Write error: {str(e)}"}],
                result["corrections"],
            )

        return result
