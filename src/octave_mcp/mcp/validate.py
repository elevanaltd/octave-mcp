"""MCP tool for OCTAVE validation (GH#51 Tool Consolidation).

Implements octave_validate tool - replaces octave_ingest with:
- Read-only validation + repair suggestions
- file_path XOR content parameter model (one required, not both)
- Unified envelope: status, canonical, repairs, warnings, errors, validation_status
- I3 (Mirror Constraint): Returns errors instead of guessing
- I5 (Schema Sovereignty): Explicit validation_status

Pipeline: PARSE -> NORMALIZE -> VALIDATE -> REPAIR(if fix) -> EMIT
"""

from pathlib import Path
from typing import Any

from octave_mcp.core.emitter import emit
from octave_mcp.core.lexer import tokenize
from octave_mcp.core.parser import parse
from octave_mcp.core.repair import repair
from octave_mcp.core.validator import Validator
from octave_mcp.mcp.base_tool import BaseTool, SchemaBuilder
from octave_mcp.schemas.loader import get_builtin_schema


class ValidateTool(BaseTool):
    """MCP tool for octave_validate - schema validation + repair suggestions."""

    # Security: allowed file extensions
    ALLOWED_EXTENSIONS = {".oct.md", ".octave", ".md"}

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

    def get_name(self) -> str:
        """Get tool name."""
        return "octave_validate"

    def get_description(self) -> str:
        """Get tool description."""
        return (
            "Schema check + repair suggestions for OCTAVE content. "
            "Validates content against schema, returns canonical form with optional repairs. "
            "Focus on I3 (Mirror Constraint) and I5 (Schema Sovereignty)."
        )

    def get_input_schema(self) -> dict[str, Any]:
        """Get input schema."""
        schema = SchemaBuilder()

        # content XOR file_path - one required, not both
        schema.add_parameter(
            "content",
            "string",
            required=False,
            description="OCTAVE content to validate (mutually exclusive with file_path)",
        )

        schema.add_parameter(
            "file_path",
            "string",
            required=False,
            description="Path to OCTAVE file to validate (mutually exclusive with content)",
        )

        schema.add_parameter(
            "schema",
            "string",
            required=True,
            description="Schema name to validate against (e.g., 'META', 'SESSION_LOG')",
        )

        schema.add_parameter(
            "fix",
            "boolean",
            required=False,
            description="If True, apply repairs to canonical output. If False (default), suggest repairs only.",
        )

        return schema.build()

    def _error_envelope(
        self,
        errors: list[dict[str, Any]],
        content: str = "",
    ) -> dict[str, Any]:
        """Build consistent error envelope with all required fields.

        Args:
            errors: List of error records
            content: Original content to return in canonical (on error)

        Returns:
            Complete error envelope with all required fields per D2 design
        """
        return {
            "status": "error",
            "canonical": content,
            "repairs": [],
            "warnings": [],
            "errors": errors,
            "validation_status": "UNVALIDATED",  # I5: Explicit bypass on error
        }

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute validation pipeline.

        Args:
            content: OCTAVE content to validate (XOR with file_path)
            file_path: Path to OCTAVE file to validate (XOR with content)
            schema: Schema name for validation
            fix: Whether to apply repairs (default: False)

        Returns:
            Dictionary with:
            - status: "success" or "error"
            - canonical: Normalized content (repaired if fix=True)
            - repairs: List of repairs applied or suggested
            - warnings: Validation warnings (non-fatal)
            - errors: Parse/schema errors (fatal)
            - validation_status: VALIDATED | UNVALIDATED | INVALID
            - schema_name: Schema name used (when VALIDATED or INVALID)
            - schema_version: Schema version used (when VALIDATED or INVALID)
            - validation_errors: List of schema validation errors (when INVALID)
        """
        # Validate and extract parameters
        params = self.validate_parameters(kwargs)
        content = params.get("content")
        file_path = params.get("file_path")
        schema_name = params["schema"]
        fix = params.get("fix", False)

        # XOR validation: exactly one of content or file_path must be provided
        if content is not None and file_path is not None:
            return self._error_envelope(
                [
                    {
                        "code": "E_INPUT",
                        "message": "Cannot provide both content and file_path - they are mutually exclusive",
                    }
                ]
            )

        if content is None and file_path is None:
            return self._error_envelope([{"code": "E_INPUT", "message": "Must provide either content or file_path"}])

        # If file_path provided, read file content
        if file_path is not None:
            # Security: validate path before reading
            is_valid, error_msg = self._validate_path(file_path)
            if not is_valid:
                return self._error_envelope([{"code": "E_PATH", "message": error_msg or "Invalid file path"}])

            path = Path(file_path)
            if not path.exists():
                return self._error_envelope([{"code": "E_FILE", "message": f"File not found: {file_path}"}])

            try:
                content = path.read_text(encoding="utf-8")
            except Exception as e:
                return self._error_envelope([{"code": "E_READ", "message": f"Error reading file: {str(e)}"}])

        # At this point content is guaranteed to be a string
        assert content is not None

        # Initialize result with unified envelope per D2 design
        # I5 (Schema Sovereignty): validation_status must be UNVALIDATED to make bypass visible
        # "Schema bypass shall be visible, never silent" - North Star I5
        result: dict[str, Any] = {
            "status": "success",
            "canonical": "",
            "repairs": [],
            "warnings": [],
            "errors": [],
            "validation_status": "UNVALIDATED",  # I5: Explicit bypass until validated
        }

        # STAGE 1: Tokenize with ASCII normalization
        try:
            tokens, tokenize_repairs = tokenize(content)
        except Exception as e:
            result["status"] = "error"
            result["errors"].append({"code": "E_TOKENIZE", "message": f"Tokenization error: {str(e)}"})
            result["canonical"] = content  # Return original on error
            return result

        # Track normalization repairs from tokenization
        result["repairs"].extend(tokenize_repairs)

        # STAGE 2: Parse (build AST with envelope inference)
        try:
            doc = parse(content)
        except Exception as e:
            result["status"] = "error"
            result["errors"].append({"code": "E_PARSE", "message": f"Parse error: {str(e)}"})
            result["canonical"] = content  # Return original on error
            return result

        # STAGE 3: Schema Validation (I5 Schema Sovereignty)
        # Try to load the requested schema
        schema_def = get_builtin_schema(schema_name)

        if schema_def is not None:
            # Schema found - perform validation
            # I5: "Schema-validated documents shall record the schema name and version used"
            result["schema_name"] = schema_def.get("name", schema_name)
            result["schema_version"] = schema_def.get("version", "unknown")

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
                # Also add to warnings for backward compatibility
                result["warnings"].extend(result["validation_errors"])
            else:
                # I5: Schema validation passed - mark as VALIDATED
                result["validation_status"] = "VALIDATED"
        else:
            # Schema not found - remain UNVALIDATED
            # I5: "Schema bypass shall be visible, never silent"
            validator = Validator(schema=None)
            validation_errors = validator.validate(doc, strict=False)

            if validation_errors:
                result["warnings"].extend(
                    [
                        {
                            "code": err.code,
                            "message": err.message,
                            "field": err.field_path,
                        }
                        for err in validation_errors
                    ]
                )

        # STAGE 4: Repair (if fix=True)
        if fix:
            doc, repair_log = repair(doc, validation_errors, fix=True)
            result["repairs"].extend(repair_log.repairs)

            # Re-validate after repairs
            validator_for_repair = Validator(schema=schema_def if schema_def else None)
            validation_errors = validator_for_repair.validate(doc, strict=False)
            if validation_errors:
                result["warnings"].extend(
                    [
                        {
                            "code": err.code,
                            "message": err.message,
                            "field": err.field_path,
                        }
                        for err in validation_errors
                    ]
                )

        # STAGE 5: Emit canonical form
        try:
            canonical_output = emit(doc)
            result["canonical"] = canonical_output
        except Exception as e:
            result["status"] = "error"
            result["errors"].append({"code": "E_EMIT", "message": f"Emit error: {str(e)}"})
            return result

        return result
