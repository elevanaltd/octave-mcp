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
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from octave_mcp.core.ast_nodes import Assignment, ASTNode, Block, Document, ListValue, Section
from octave_mcp.core.emitter import emit
from octave_mcp.core.hydrator import resolve_hermetic_standard
from octave_mcp.core.lexer import tokenize
from octave_mcp.core.parser import parse
from octave_mcp.core.schema_extractor import SchemaDefinition
from octave_mcp.core.validator import Validator
from octave_mcp.mcp.base_tool import BaseTool, SchemaBuilder
from octave_mcp.schemas.loader import get_builtin_schema, load_schema_by_name

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

    Args:
        value: Python value from changes dict

    Returns:
        AST-compatible value (ListValue for lists, original for others)
    """
    if isinstance(value, list):
        # Recursively normalize list items
        normalized_items = [_normalize_value_for_ast(item) for item in value]
        return ListValue(items=normalized_items)
    # Other types (str, int, bool, None, etc.) are handled by emit_value directly
    return value


class WriteTool(BaseTool):
    """MCP tool for octave_write - unified write operation for OCTAVE files."""

    # Security: allowed file extensions
    ALLOWED_EXTENSIONS = {".oct.md", ".octave", ".md"}

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

        return schema.build()

    def _validate_path(self, target_path: str) -> tuple[bool, str | None]:
        """Validate target path for security.

        Args:
            target_path: Path to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        path = Path(target_path)

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

        # Check for path traversal (..)
        try:
            # Check if path contains .. as a component (not substring)
            if any(part == ".." for part in path.parts):
                return False, "Path traversal not allowed (..)"

        except Exception as e:
            return False, f"Invalid path: {str(e)}"

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
        for repair in tokenize_repairs:
            corrections.append(
                {
                    "code": "W002",
                    "message": f"ASCII operator -> Unicode: {repair.get('original', '')} -> {repair.get('normalized', '')}",
                    "line": repair.get("line", 0),
                    "column": repair.get("column", 0),
                    "before": repair.get("original", ""),
                    "after": repair.get("normalized", ""),
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

    def _apply_mutations(self, content: str, mutations: dict[str, Any] | None) -> str:
        """Apply META field mutations to content.

        Args:
            content: Content to mutate
            mutations: Dictionary of META fields to inject/override

        Returns:
            Mutated content
        """
        if not mutations:
            return content

        # TODO: Implement META field injection
        # For now, return content as-is
        return content

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

        # Initialize result with unified envelope per D2 design
        # I5 (Schema Sovereignty): validation_status must be UNVALIDATED to make bypass visible
        # "Schema bypass shall be visible, never silent" - North Star I5
        result: dict[str, Any] = {
            "status": "success",
            "path": target_path,
            "canonical_hash": "",
            "corrections": [],
            "diff": "",
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
        original_content = ""
        tokenize_repairs: list[dict[str, Any]] = []
        original_metrics: StructuralMetrics | None = None
        canonical_metrics: StructuralMetrics | None = None

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
                    original_content = f.read()
            except Exception as e:
                return self._error_envelope(
                    target_path,
                    [{"code": "E_READ", "message": f"Read error: {str(e)}"}],
                )

            # Check base_hash if provided
            if base_hash:
                current_hash = self._compute_hash(original_content)
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

            # Parse existing content
            try:
                doc = parse(original_content)
                # Extract metrics from original document BEFORE applying changes
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

            # Emit canonical form
            try:
                canonical_content = emit(doc)
                # Extract metrics from modified document AFTER applying changes
                canonical_metrics = extract_structural_metrics(doc)
            except Exception as e:
                return self._error_envelope(
                    target_path,
                    [{"code": "E_EMIT", "message": f"Emit error: {str(e)}"}],
                )

            # Track repairs from canonical
            try:
                _, tokenize_repairs = tokenize(canonical_content)
            except Exception:
                pass  # Non-fatal

        else:
            # CONTENT MODE (Create/Overwrite)
            assert content is not None
            original_content = content

            # Check base_hash if provided AND file exists (CAS guard)
            if base_hash and file_exists:
                try:
                    with open(target_path, encoding="utf-8") as f:
                        existing_content = f.read()
                    current_hash = self._compute_hash(existing_content)
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
                except Exception as e:
                    return self._error_envelope(
                        target_path,
                        [{"code": "E_READ", "message": f"Read error: {str(e)}"}],
                    )

            # Tokenize with repairs
            try:
                _, tokenize_repairs = tokenize(content)
            except Exception as e:
                return self._error_envelope(
                    target_path,
                    [{"code": "E_TOKENIZE", "message": f"Tokenization error: {str(e)}"}],
                )

            # Parse to AST
            try:
                doc = parse(content)
                # Extract metrics from input document
                original_metrics = extract_structural_metrics(doc)
            except Exception as e:
                corrections = self._track_corrections(content, content, tokenize_repairs)
                return self._error_envelope(
                    target_path,
                    [{"code": "E_PARSE", "message": f"Parse error: {str(e)}"}],
                    corrections,
                )

            # Emit canonical form
            try:
                canonical_content = emit(doc)
                # Extract metrics from canonical document (same doc after emit)
                canonical_metrics = extract_structural_metrics(doc)
            except Exception as e:
                return self._error_envelope(
                    target_path,
                    [{"code": "E_EMIT", "message": f"Emit error: {str(e)}"}],
                )

        # Track corrections
        corrections = self._track_corrections(original_content, canonical_content, tokenize_repairs)
        result["corrections"] = corrections

        # Apply mutations (if any)
        if mutations:
            canonical_content = self._apply_mutations(canonical_content, mutations)

        # Schema Validation (I5 Schema Sovereignty)
        if schema_name:
            # Issue #150: Use hermetic resolution for frozen@ and latest schema references
            # Check if schema_name uses hermetic format (frozen@sha256:... or latest)
            if schema_name.startswith("frozen@") or schema_name == "latest":
                # Use hermetic resolution path
                try:
                    # Attempt hermetic resolution to verify schema exists in cache
                    _schema_path = resolve_hermetic_standard(schema_name)
                    # Hermetic schema found - for MVP, we don't perform validation yet
                    # but we record that hermetic resolution succeeded
                    # TODO: Integrate SchemaDefinition with Validator for full validation
                    schema_def = None  # No validation for hermetic schemas yet
                except Exception:
                    # Hermetic resolution failed - schema not found in cache
                    # This is expected if the cache isn't set up
                    schema_def = None
            else:
                # Legacy path: use builtin schema loader for backward compatibility
                schema_def = get_builtin_schema(schema_name)

            # Load SchemaDefinition for constraint grammar compilation (if debug_grammar=True)
            schema_definition: SchemaDefinition | None = None
            if debug_grammar:
                try:
                    schema_definition = load_schema_by_name(schema_name)
                except Exception:
                    # Schema loading may fail - continue without debug info
                    pass

            if schema_def is not None:
                # Schema found - perform validation
                # I5: "Schema-validated documents shall record the schema name and version used"
                result["schema_name"] = schema_def.get("name", schema_name)
                result["schema_version"] = schema_def.get("version", "unknown")

                # Add debug grammar information if requested
                if debug_grammar and schema_definition is not None:
                    debug_info: dict[str, Any] = {
                        "schema_name": schema_definition.name,
                        "schema_version": schema_definition.version or "unknown",
                        "field_constraints": {},
                    }
                    # Compile constraint grammar for each field
                    for field_name, field_def in schema_definition.fields.items():
                        # Use field_def.pattern.constraints (matching validate.py pattern)
                        if hasattr(field_def, "pattern") and field_def.pattern and field_def.pattern.constraints:
                            chain = field_def.pattern.constraints
                            compiled = chain.compile()
                            debug_info["field_constraints"][field_name] = {
                                "chain": chain.to_string(),
                                "compiled_regex": compiled,
                            }
                    result["debug_info"] = debug_info

                # Use the validator with the schema definition
                validator = Validator(schema=schema_def)
                validation_errors = validator.validate(doc, strict=False)

                if validation_errors:
                    # I5: Schema validation failed - mark as INVALID
                    result["validation_status"] = "INVALID"
                    result["validation_errors"] = [
                        {
                            "code": err.code,
                            "message": err.message,
                            "field": err.field_path,
                        }
                        for err in validation_errors
                    ]
                else:
                    # I5: Schema validation passed - mark as VALIDATED
                    result["validation_status"] = "VALIDATED"
            # else: schema not found - remain UNVALIDATED (bypass is visible)

        # WRITE FILE (atomic + symlink-safe)
        try:
            # Ensure parent directory exists
            path_obj.parent.mkdir(parents=True, exist_ok=True)

            # Reject symlink targets (security)
            if path_obj.exists() and path_obj.is_symlink():
                return self._error_envelope(
                    target_path,
                    [{"code": "E_WRITE", "message": "Cannot write to symlink target"}],
                    corrections,
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
                            corrections,
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
                corrections,
            )

        # Compute hash of written content
        canonical_hash = self._compute_hash(canonical_content)

        # Build success response
        result["canonical_hash"] = canonical_hash
        # I4 Auditability: Detect content changes even when byte count/structure identical
        content_changed = original_content != canonical_content
        result["diff"] = self._generate_diff(
            len(original_content),
            len(canonical_content),
            original_metrics,
            canonical_metrics,
            content_changed=content_changed,
        )

        return result
