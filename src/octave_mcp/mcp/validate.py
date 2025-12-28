"""MCP tool for OCTAVE validation (GH#51 Tool Consolidation).

Implements octave_validate tool - replaces octave_ingest with:
- Read-only validation + repair suggestions
- Unified envelope: status, canonical, repairs, warnings, errors, validation_status
- I3 (Mirror Constraint): Returns errors instead of guessing
- I5 (Schema Sovereignty): Explicit validation_status

Pipeline: PARSE -> NORMALIZE -> VALIDATE -> REPAIR(if fix) -> EMIT
"""

from typing import Any

from octave_mcp.core.emitter import emit
from octave_mcp.core.lexer import tokenize
from octave_mcp.core.parser import parse
from octave_mcp.core.repair import repair
from octave_mcp.core.validator import Validator
from octave_mcp.mcp.base_tool import BaseTool, SchemaBuilder


class ValidateTool(BaseTool):
    """MCP tool for octave_validate - schema validation + repair suggestions."""

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

        schema.add_parameter("content", "string", required=True, description="OCTAVE content to validate")

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

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute validation pipeline.

        Args:
            content: OCTAVE content to validate
            schema: Schema name for validation
            fix: Whether to apply repairs (default: False)

        Returns:
            Dictionary with:
            - status: "success" or "error"
            - canonical: Normalized content (repaired if fix=True)
            - repairs: List of repairs applied or suggested
            - warnings: Validation warnings (non-fatal)
            - errors: Parse/schema errors (fatal)
            - validation_status: VALIDATED | UNVALIDATED | PENDING_INFRASTRUCTURE
        """
        # Validate and extract parameters
        params = self.validate_parameters(kwargs)
        content = params["content"]
        _ = params["schema"]  # Reserved for P2.5 schema validation
        fix = params.get("fix", False)

        # Initialize result with unified envelope per D2 design
        result: dict[str, Any] = {
            "status": "success",
            "canonical": "",
            "repairs": [],
            "warnings": [],
            "errors": [],
            "validation_status": "PENDING_INFRASTRUCTURE",  # I5: Schema validation pending P2.5
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

        # STAGE 3: Validate
        # Note: Schema validation infrastructure pending P2.5
        # For now, use basic validator without schema
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

        # STAGE 5: Emit canonical form
        try:
            canonical_output = emit(doc)
            result["canonical"] = canonical_output
        except Exception as e:
            result["status"] = "error"
            result["errors"].append({"code": "E_EMIT", "message": f"Emit error: {str(e)}"})
            return result

        # I5: Set validation_status
        # PENDING_INFRASTRUCTURE until schema validation is complete (P2.5)
        # Will be VALIDATED or UNVALIDATED once schema validation is implemented
        result["validation_status"] = "PENDING_INFRASTRUCTURE"

        return result
