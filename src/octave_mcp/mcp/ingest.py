"""MCP tool for OCTAVE ingest (P2.2).

Implements octave_ingest tool with pipeline:
PREPARSE→PARSE→NORMALIZE→VALIDATE→REPAIR(if fix)→VALIDATE

DEPRECATED: This tool is deprecated and will be removed in 12 weeks.
Use octave_validate instead:
  - octave_ingest(...) -> octave_validate(..., fix=True)
"""

import warnings
from typing import Any

from octave_mcp.core.emitter import emit
from octave_mcp.core.lexer import tokenize
from octave_mcp.core.parser import parse
from octave_mcp.core.repair import repair
from octave_mcp.core.validator import Validator
from octave_mcp.mcp.base_tool import BaseTool, SchemaBuilder


class IngestTool(BaseTool):
    """MCP tool for octave_ingest - lenient to canonical pipeline.

    DEPRECATED: Use octave_validate instead. This tool will be removed in 12 weeks.
    """

    def get_name(self) -> str:
        """Get tool name."""
        return "octave_ingest"

    def get_description(self) -> str:
        """Get tool description."""
        return (
            "[DEPRECATED: Use octave_validate instead] "
            "Ingest lenient OCTAVE content and emit canonical form. "
            "Accepts ASCII aliases (→/->, ⊕/+, etc.) and normalizes to unicode. "
            "Validates against schema and optionally applies repairs. "
            "Pipeline: PREPARSE→PARSE→NORMALIZE→VALIDATE→REPAIR(if fix)→VALIDATE"
        )

    def get_input_schema(self) -> dict[str, Any]:
        """Get input schema."""
        schema = SchemaBuilder()

        schema.add_parameter(
            "content", "string", required=True, description="OCTAVE content to ingest (lenient format accepted)"
        )

        schema.add_parameter(
            "schema", "string", required=True, description="Schema name for validation (e.g., 'META', 'SESSION_LOG')"
        )

        schema.add_parameter(
            "tier",
            "string",
            required=False,
            description="Compression tier for output",
            enum=["LOSSLESS", "CONSERVATIVE", "AGGRESSIVE", "ULTRA"],
        )

        schema.add_parameter(
            "fix", "boolean", required=False, description="Enable TIER_REPAIR fixes (enum casefold, type coercion)"
        )

        schema.add_parameter("verbose", "boolean", required=False, description="Show pipeline stages in output")

        return schema.build()

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute ingest pipeline.

        DEPRECATED: Use octave_validate instead. This tool will be removed in 12 weeks.

        Args:
            content: OCTAVE content to ingest
            schema: Schema name (reserved for future use in P2.5, currently not used for validation)
            tier: Compression tier (LOSSLESS, CONSERVATIVE, AGGRESSIVE, ULTRA)
            fix: Whether to apply TIER_REPAIR fixes
            verbose: Whether to show pipeline stages

        Returns:
            Dictionary with:
            - canonical: Canonical OCTAVE output
            - repairs: List of repairs applied
            - warnings: List of validation warnings (basic validation only, schema validation deferred to P2.5)
            - stages: Pipeline stage details (if verbose=true)
        """
        # Emit deprecation warning
        warnings.warn(
            "octave_ingest is deprecated and will be removed in 12 weeks. "
            "Use octave_validate instead: octave_ingest(...) -> octave_validate(..., fix=True)",
            DeprecationWarning,
            stacklevel=2,
        )

        # Validate and extract parameters
        params = self.validate_parameters(kwargs)
        content = params["content"]
        schema_name = params["schema"]
        # DEFERRED: tier parameter ignored until compression infrastructure ready
        # See docs/implementation-roadmap.md Gap 6 (Compression Tier Logic)
        # Estimated: 3-4 days, Phase 4 work (after schema validation complete)
        #
        # Once Gap 6 is complete, tier will control compression:
        # - LOSSLESS (100%): Preserve all prose, examples, tradeoffs
        # - CONSERVATIVE (85-90%): Drop stopwords, compress examples
        # - AGGRESSIVE (70%): Drop narratives, inline all
        # - ULTRA (50%): Bare assertions, minimal lists, no examples
        # tier = params.get("tier", "LOSSLESS")  # Ignored for now
        fix = params.get("fix", False)
        verbose = params.get("verbose", False)

        # Initialize result
        # I5 compliance: Schema bypass shall be visible, never silent
        # Deprecated tools include validation_status: UNVALIDATED
        result: dict[str, Any] = {
            "canonical": "",
            "repairs": [],
            "warnings": [],
            "validation_status": "UNVALIDATED",
        }

        # Track pipeline stages if verbose
        stages: dict[str, Any] = {}

        # STAGE 1: PREPARSE (tokenization with ASCII normalization)
        if verbose:
            stages["PREPARSE"] = "Tokenizing with ASCII normalization"

        tokens, tokenize_repairs = tokenize(content)

        if verbose:
            stages["TOKENIZE_COMPLETE"] = f"{len(tokens)} tokens produced"

        # Track normalization repairs from tokenization
        result["repairs"].extend(tokenize_repairs)

        # STAGE 2: PARSE (build AST with envelope inference)
        if verbose:
            stages["PARSE"] = "Building AST with envelope inference"

        try:
            doc = parse(content)  # Uses tokenize internally
        except Exception as e:
            # If parsing fails, return error in warnings
            result["warnings"].append({"code": "E001", "message": f"Parse error: {str(e)}"})
            # Return minimal canonical form
            result["canonical"] = content
            if verbose:
                result["stages"] = stages
            return result

        if verbose:
            stages["PARSE_COMPLETE"] = "AST built successfully"

        # STAGE 3: NORMALIZE (whitespace, quotes - already done in parser)
        if verbose:
            stages["NORMALIZE"] = "Normalization completed during parsing"

        # STAGE 4: VALIDATE
        if verbose:
            stages["VALIDATE"] = f"Validating against schema: {schema_name}"

        # For now, skip actual schema validation (will be added with P2.5)
        # Just create a basic validator
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

        if verbose:
            stages["VALIDATE_COMPLETE"] = f"{len(validation_errors)} validation errors"

        # STAGE 5: REPAIR (if fix=true)
        if fix:
            if verbose:
                stages["REPAIR"] = "Applying TIER_REPAIR fixes"

            doc, repair_log = repair(doc, validation_errors, fix=True)
            result["repairs"].extend(repair_log.repairs)

            if verbose:
                stages["REPAIR_COMPLETE"] = f"{len(repair_log.repairs)} repairs applied"

            # STAGE 6: VALIDATE again after repairs
            if verbose:
                stages["VALIDATE_POST_REPAIR"] = "Re-validating after repairs"

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

            if verbose:
                stages["VALIDATE_POST_REPAIR_COMPLETE"] = f"{len(validation_errors)} validation errors remain"

        # STAGE 7: EMIT canonical form
        if verbose:
            stages["EMIT"] = "Emitting canonical OCTAVE"

        canonical_output = emit(doc)
        result["canonical"] = canonical_output

        if verbose:
            stages["EMIT_COMPLETE"] = f"{len(canonical_output)} characters emitted"

        # Add stages to result if verbose
        if verbose:
            result["stages"] = stages

        return result
