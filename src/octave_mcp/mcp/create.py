"""MCP tool for OCTAVE create (Epic #41, Issue #37).

Implements octave_create tool for writing OCTAVE files with:
- File writing with path validation
- META field injection via mutations
- Correction tracking (W001-W005)
- Compact diff or full summary output

DEPRECATED: This tool is deprecated and will be removed in 12 weeks.
Use octave_write instead:
  - octave_create(...) -> octave_write(content=...)
"""

import hashlib
import os
import tempfile
import warnings
from pathlib import Path
from typing import Any

from octave_mcp.core.emitter import emit
from octave_mcp.core.lexer import tokenize
from octave_mcp.core.parser import parse
from octave_mcp.mcp.base_tool import BaseTool, SchemaBuilder


class CreateTool(BaseTool):
    """MCP tool for octave_create - write canonical OCTAVE to file.

    DEPRECATED: Use octave_write instead. This tool will be removed in 12 weeks.
    """

    # Security: allowed file extensions
    ALLOWED_EXTENSIONS = {".oct.md", ".octave", ".md"}

    def get_name(self) -> str:
        """Get tool name."""
        return "octave_create"

    def get_description(self) -> str:
        """Get tool description."""
        return (
            "[DEPRECATED: Use octave_write instead] "
            "Write OCTAVE content to file with normalization. "
            "Validates path, normalizes content to canonical form, "
            "tracks corrections (W001-W005), and returns diff or full summary."
        )

    def get_input_schema(self) -> dict[str, Any]:
        """Get input schema."""
        schema = SchemaBuilder()

        schema.add_parameter("content", "string", required=True, description="OCTAVE content to write")

        schema.add_parameter("target_path", "string", required=True, description="File path to write to")

        schema.add_parameter(
            "mutations",
            "object",
            required=False,
            description="META field overrides to inject (e.g., {VERSION: '2.0', STATUS: 'DRAFT'})",
        )

        schema.add_parameter(
            "full_summary",
            "boolean",
            required=False,
            description="Return full canonical content instead of compact diff (default: false)",
        )

        schema.add_parameter("schema", "string", required=False, description="Schema name for validation (optional)")

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
        # Will need to parse, modify META section, re-emit
        return content

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
        return f"Content normalized ({len(original)} → {len(canonical)} bytes)"

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute create pipeline.

        DEPRECATED: Use octave_write instead. This tool will be removed in 12 weeks.

        Args:
            content: OCTAVE content to write
            target_path: File path to write to
            mutations: Optional META field overrides
            full_summary: Whether to return full content instead of diff
            schema: Optional schema name for validation

        Returns:
            Dictionary with:
            - status: "success" or "error"
            - path: Written file path (on success)
            - canonical_hash: SHA-256 hash of canonical content (on success)
            - corrections: List of corrections applied
            - diff: Compact diff (if not full_summary)
            - content: Full canonical content (if full_summary)
            - errors: List of errors (on failure)
        """
        # Emit deprecation warning
        warnings.warn(
            "octave_create is deprecated and will be removed in 12 weeks. "
            "Use octave_write instead: octave_create(...) -> octave_write(content=...)",
            DeprecationWarning,
            stacklevel=2,
        )

        # Validate and extract parameters
        params = self.validate_parameters(kwargs)
        content = params["content"]
        target_path = params["target_path"]
        mutations = params.get("mutations")
        full_summary = params.get("full_summary", False)
        # schema parameter reserved for future validation (P2.5)
        _ = params.get("schema")

        # Initialize result
        result: dict[str, Any] = {
            "status": "success",
            "corrections": [],
        }

        # STEP 1: Validate path
        path_valid, path_error = self._validate_path(target_path)
        if not path_valid:
            return {
                "status": "error",
                "errors": [{"code": "E_PATH", "message": path_error}],
            }

        # STEP 2: Parse and normalize content
        tokenize_repairs: list[dict[str, Any]] = []  # Initialize to preserve on error path
        try:
            # Tokenize with repairs
            tokens, tokenize_repairs = tokenize(content)

            # Parse to AST
            doc = parse(content)

            # Emit canonical form
            canonical_content = emit(doc)

        except Exception as e:
            # Track corrections even on parse error (learning feedback)
            corrections = self._track_corrections(content, content, tokenize_repairs)
            return {
                "status": "error",
                "errors": [{"code": "E_PARSE", "message": f"Parse error: {str(e)}"}],
                "corrections": corrections,
            }

        # STEP 3: Track corrections
        corrections = self._track_corrections(content, canonical_content, tokenize_repairs)
        result["corrections"] = corrections

        # STEP 4: Apply mutations (if any)
        if mutations:
            canonical_content = self._apply_mutations(canonical_content, mutations)

        # STEP 5: Write file (atomic + symlink-safe)
        try:
            # Ensure parent directory exists
            path_obj = Path(target_path)
            path_obj.parent.mkdir(parents=True, exist_ok=True)

            # Reject symlink targets (security: prevent arbitrary file overwrite)
            if path_obj.exists() and path_obj.is_symlink():
                return {
                    "status": "error",
                    "errors": [{"code": "E_WRITE", "message": "Cannot write to symlink target"}],
                }

            # Atomic write: tempfile→fsync→os.replace
            # Prevents partial writes and race conditions
            fd, temp_path = tempfile.mkstemp(dir=path_obj.parent, suffix=".tmp", text=True)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(canonical_content)
                    f.flush()
                    os.fsync(f.fileno())  # Ensure data written to disk

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
            }

        # STEP 6: Compute hash
        canonical_hash = self._compute_hash(canonical_content)

        # STEP 7: Build response
        result["path"] = target_path
        result["canonical_hash"] = canonical_hash

        # Return diff or full content
        if full_summary:
            result["content"] = canonical_content
        else:
            result["diff"] = self._generate_diff(content, canonical_content)

        return result
