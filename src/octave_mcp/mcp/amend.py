"""MCP tool for OCTAVE amend (Epic #41, Issue #41 Phase 2).

Implements octave_amend tool for updating existing OCTAVE files with:
- File reading and modification
- Field-level updates via changes parameter
- Optional base_hash consistency check
- Correction tracking (W001-W005)
- Compact diff or full summary output

DEPRECATED: This tool is deprecated and will be removed in 12 weeks.
Use octave_write instead:
  - octave_amend(...) -> octave_write(changes=...)
"""

import hashlib
import warnings
from pathlib import Path
from typing import Any

from octave_mcp.core.ast_nodes import Assignment
from octave_mcp.core.emitter import emit
from octave_mcp.core.lexer import tokenize
from octave_mcp.core.parser import parse
from octave_mcp.mcp.base_tool import BaseTool, SchemaBuilder


class AmendTool(BaseTool):
    """MCP tool for octave_amend - update existing OCTAVE files.

    DEPRECATED: Use octave_write instead. This tool will be removed in 12 weeks.
    """

    # Security: allowed file extensions (same as CreateTool)
    ALLOWED_EXTENSIONS = {".oct.md", ".octave", ".md"}

    def get_name(self) -> str:
        """Get tool name."""
        return "octave_amend"

    def get_description(self) -> str:
        """Get tool description."""
        return (
            "[DEPRECATED: Use octave_write instead] "
            "Amend existing OCTAVE file with field updates. "
            "Reads file, applies changes, normalizes to canonical form, "
            "tracks corrections (W001-W005), and returns diff or full summary."
        )

    def get_input_schema(self) -> dict[str, Any]:
        """Get input schema."""
        schema = SchemaBuilder()

        schema.add_parameter("target_path", "string", required=True, description="Existing file path to amend")

        schema.add_parameter(
            "changes",
            "object",
            required=True,
            description="Field updates to apply (e.g., {KEY: 'new_value', TIMEOUT: 60})",
        )

        schema.add_parameter(
            "base_hash",
            "string",
            required=False,
            description="Optional consistency check - current file hash must match",
        )

        return schema.build()

    def _validate_path(self, target_path: str) -> tuple[bool, str | None]:
        """Validate target path for security.

        Args:
            target_path: Path to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Convert to Path for normalization
        path = Path(target_path)

        # Check for path traversal
        try:
            # Resolve to absolute path (validates path exists)
            _ = path.resolve()

            # Check if path contains .. as a component (not substring)
            # This prevents false positives for files like "name..ok.oct.md"
            if any(part == ".." for part in path.parts):
                return False, "Path traversal not allowed (..)"

        except Exception as e:
            return False, f"Invalid path: {str(e)}"

        # Check file extension
        if path.suffix not in self.ALLOWED_EXTENSIONS:
            # Also check for compound extensions like .oct.md
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
            Schema: {code: str, message: str, line: int, column: int, before: str, after: str}
        """
        corrections = []

        # Map tokenize repairs to W002 (ASCII operator → Unicode)
        # tokenize_repairs format: {type, original, normalized, line, column}
        for repair in tokenize_repairs:
            corrections.append(
                {
                    "code": "W002",
                    "message": f"ASCII operator → Unicode: {repair.get('original', '')} → {repair.get('normalized', '')}",
                    "line": repair.get("line", 0),
                    "column": repair.get("column", 0),
                    "before": repair.get("original", ""),
                    "after": repair.get("normalized", ""),
                }
            )

        # TODO: Add more correction tracking for:
        # W001: Single colon → double colon
        # W003: Indentation normalized
        # W004: Missing envelope added
        # W005: Trailing whitespace removed

        return corrections

    def _apply_changes(self, doc: Any, changes: dict[str, Any]) -> Any:
        """Apply changes to AST document.

        Args:
            doc: Parsed AST document
            changes: Dictionary of field updates

        Returns:
            Modified document
        """
        # Simple implementation: update top-level sections
        # For each change, find matching section and update value
        for key, new_value in changes.items():
            # Find section with matching key
            for section in doc.sections:
                # I3 FIX: Use isinstance instead of hasattr to avoid matching Block nodes
                # Block nodes also have 'key' attribute but shouldn't be updated as assignments
                if isinstance(section, Assignment) and section.key == key:
                    # Update the value
                    section.value = new_value
                    break

        return doc

    def _generate_diff(self, original: str, canonical: str) -> str:
        """Generate compact diff between original and canonical.

        Args:
            original: Original content
            canonical: Canonical content

        Returns:
            Compact diff string
        """
        # Simple diff: just show if changed
        if original == canonical:
            return "No changes"

        # TODO: Implement proper unified diff
        # For now, return basic summary
        return f"Content updated ({len(original)} → {len(canonical)} bytes)"

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute amend pipeline.

        DEPRECATED: Use octave_write instead. This tool will be removed in 12 weeks.

        Args:
            target_path: Existing file path to amend
            changes: Field updates to apply
            base_hash: Optional consistency check hash

        Returns:
            Dictionary with:
            - status: "success" or "error"
            - path: Updated file path (on success)
            - canonical_hash: SHA-256 hash of canonical content (on success)
            - corrections: List of corrections applied
            - diff: Compact diff
            - errors: List of errors (on failure)
        """
        # Emit deprecation warning
        warnings.warn(
            "octave_amend is deprecated and will be removed in 12 weeks. "
            "Use octave_write instead: octave_amend(...) -> octave_write(changes=...)",
            DeprecationWarning,
            stacklevel=2,
        )

        # Validate and extract parameters
        params = self.validate_parameters(kwargs)
        target_path = params["target_path"]
        changes = params["changes"]
        base_hash = params.get("base_hash")

        # Initialize result
        # I5 compliance: Schema bypass shall be visible, never silent
        # Deprecated tools include validation_status: UNVALIDATED
        result: dict[str, Any] = {
            "status": "success",
            "corrections": [],
            "validation_status": "UNVALIDATED",
        }

        # STEP 1: Validate path
        path_valid, path_error = self._validate_path(target_path)
        if not path_valid:
            return {
                "status": "error",
                "errors": [{"code": "E_PATH", "message": path_error}],
                "validation_status": "UNVALIDATED",
            }

        # STEP 2: Check file exists
        path_obj = Path(target_path)
        if not path_obj.exists():
            return {
                "status": "error",
                "errors": [{"code": "E_FILE", "message": "File does not exist"}],
                "validation_status": "UNVALIDATED",
            }

        # STEP 3: Read existing file
        try:
            with open(target_path, encoding="utf-8") as f:
                original_content = f.read()
        except Exception as e:
            return {
                "status": "error",
                "errors": [{"code": "E_READ", "message": f"Read error: {str(e)}"}],
                "validation_status": "UNVALIDATED",
            }

        # STEP 4: Check base_hash if provided
        if base_hash:
            current_hash = self._compute_hash(original_content)
            if current_hash != base_hash:
                return {
                    "status": "error",
                    "errors": [
                        {
                            "code": "E_HASH",
                            "message": f"Hash mismatch - file has been modified (expected {base_hash[:8]}..., got {current_hash[:8]}...)",
                        }
                    ],
                    "validation_status": "UNVALIDATED",
                }

        # STEP 5: Parse existing content
        tokenize_repairs: list[dict[str, Any]] = []  # Initialize to preserve on error path
        try:
            # Parse to AST
            doc = parse(original_content)

        except Exception as e:
            return {
                "status": "error",
                "errors": [{"code": "E_PARSE", "message": f"Parse error: {str(e)}"}],
                "validation_status": "UNVALIDATED",
            }

        # STEP 6: Apply changes to AST
        try:
            doc = self._apply_changes(doc, changes)
        except Exception as e:
            return {
                "status": "error",
                "errors": [{"code": "E_APPLY", "message": f"Apply changes error: {str(e)}"}],
                "validation_status": "UNVALIDATED",
            }

        # STEP 7: Emit canonical form
        try:
            canonical_content = emit(doc)
        except Exception as e:
            return {
                "status": "error",
                "errors": [{"code": "E_EMIT", "message": f"Emit error: {str(e)}"}],
                "validation_status": "UNVALIDATED",
            }

        # STEP 8: Tokenize canonical for repair tracking
        try:
            _, tokenize_repairs = tokenize(canonical_content)
        except Exception:
            # Non-fatal - just skip repair tracking
            pass

        # STEP 9: Track corrections
        corrections = self._track_corrections(original_content, canonical_content, tokenize_repairs)
        result["corrections"] = corrections

        # STEP 10: Write file (atomic + symlink-safe) - reuse CreateTool pattern
        try:
            import os
            import tempfile

            # Reject symlink targets (security: prevent arbitrary file overwrite)
            if path_obj.exists() and path_obj.is_symlink():
                return {
                    "status": "error",
                    "errors": [{"code": "E_WRITE", "message": "Cannot write to symlink target"}],
                    "validation_status": "UNVALIDATED",
                }

            # I2 FIX: Preserve original file permissions
            # mkstemp creates files with 0600 mode by default
            # We must capture and restore the original permissions
            original_stat = os.stat(target_path)
            original_mode = original_stat.st_mode & 0o777

            # Atomic write: tempfile→fsync→os.replace
            # Prevents partial writes and race conditions
            fd, temp_path = tempfile.mkstemp(dir=path_obj.parent, suffix=".tmp", text=True)
            try:
                # Apply original permissions to temp file before writing
                os.fchmod(fd, original_mode)

                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(canonical_content)
                    f.flush()
                    os.fsync(f.fileno())  # Ensure data written to disk

                # I4 FIX: Recheck base_hash immediately before replace (TOCTOU protection)
                # File could have been modified between initial check and now
                if base_hash:
                    with open(target_path, encoding="utf-8") as verify_f:
                        verify_content = verify_f.read()
                    verify_hash = self._compute_hash(verify_content)
                    if verify_hash != base_hash:
                        # File was modified during our operation - abort
                        os.unlink(temp_path)
                        return {
                            "status": "error",
                            "errors": [
                                {
                                    "code": "E_HASH",
                                    "message": f"Hash mismatch before write - file was modified during operation (expected {base_hash[:8]}..., got {verify_hash[:8]}...)",
                                }
                            ],
                            "validation_status": "UNVALIDATED",
                        }

                # Atomic replace (POSIX guarantees atomicity)
                os.replace(temp_path, target_path)

            except Exception:
                # Clean up temp file on error
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise

        except Exception as e:
            return {
                "status": "error",
                "errors": [{"code": "E_WRITE", "message": f"Write error: {str(e)}"}],
                "validation_status": "UNVALIDATED",
            }

        # STEP 11: Compute hash
        canonical_hash = self._compute_hash(canonical_content)

        # STEP 12: Build response
        result["path"] = target_path
        result["canonical_hash"] = canonical_hash
        result["diff"] = self._generate_diff(original_content, canonical_content)

        return result
