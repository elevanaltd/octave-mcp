"""MCP tool for OCTAVE validation (GH#51 Tool Consolidation).

Implements octave_validate tool - replaces octave_ingest with:
- Read-only validation + repair suggestions
- file_path XOR content parameter model (one required, not both)
- Unified envelope: status, canonical, repairs, warnings, errors, validation_status
- I3 (Mirror Constraint): Returns errors instead of guessing
- I5 (Schema Sovereignty): Explicit validation_status

Pipeline: PARSE -> NORMALIZE -> VALIDATE -> REPAIR(if fix) -> EMIT
"""

import re
from difflib import unified_diff
from pathlib import Path
from typing import Any

from octave_mcp.core.constraints import RequiredConstraint
from octave_mcp.core.emitter import emit
from octave_mcp.core.gbnf_compiler import GBNFCompiler
from octave_mcp.core.grammar import parse_with_warnings
from octave_mcp.core.grammar.cst import Assignment, ASTNode, Block
from octave_mcp.core.literal_zone_audit import build_literal_zone_repair_log
from octave_mcp.core.repair import repair
from octave_mcp.core.schema_extractor import SchemaDefinition
from octave_mcp.core.validator import ValidationError, Validator, _count_literal_zones
from octave_mcp.mcp.base_tool import BaseTool, SchemaBuilder
from octave_mcp.mcp.compile_grammar import USAGE_HINTS
from octave_mcp.mcp.write_detection import _detect_snake_case_blob
from octave_mcp.schemas.loader import get_builtin_schema, load_schema_by_name

# Gap_6: Regex pattern to extract spec error codes (E001-E007) from error messages
# The core lexer/parser embed codes like "E005 at line 2, column 1: ..."
SPEC_CODE_PATTERN = re.compile(r"\b(E00[1-7])\b")

# CE MUST FIX #1: Size threshold for diff generation (100KB)
# Skip expensive diff computation on large content to prevent high CPU/memory
DIFF_SIZE_THRESHOLD = 100_000

# Validation profiles (#183)
# Each profile defines strictness level for validation
VALID_PROFILES = {"STRICT", "STANDARD", "LENIENT", "ULTRA"}
DEFAULT_PROFILE = "STANDARD"


class _PolicyWalkSentinel:
    """Marker class for the policy-walk schema slot in ``section_schemas``.

    PR #444 cubic P2 #1 rework: the previous implementation used the
    string ``"__schema__"`` as the dict key. A document that legitimately
    authors a Block keyed ``__schema__`` would collide with the sentinel
    — ``_check_required_field_coverage`` filtered by string match and
    silently dropped the user's fields from coverage, producing false
    E003 errors. Using a dedicated class as the key makes the sentinel
    structurally inseparable from any user-author-able string key.

    The class itself is used as the dict key (not an instance) so it is
    hashable and identity-comparable across imports.
    """


# Single module-level marker used as the dict key for the policy-walk slot.
POLICY_WALK_SENTINEL: type = _PolicyWalkSentinel


def _build_deep_section_schemas(
    doc: Any,
    schema_definition: SchemaDefinition,
) -> dict[Any, SchemaDefinition]:
    """Build per-section schemas from a document-type schema definition.

    Issue #325: For document-type schemas where META.TYPE matches the schema name
    (e.g., COGNITION_DEFINITION), fields are distributed across sections and nested
    blocks. This function walks the document tree, identifies which schema fields
    are present in each block/section, and creates a targeted SchemaDefinition per
    section containing only the relevant fields.

    This avoids false "required but missing" errors when a flat schema's REQ fields
    are checked against every section -- fields belonging to §2 won't be flagged
    as missing from §1.

    Args:
        doc: Parsed Document AST
        schema_definition: The loaded SchemaDefinition with all fields

    Returns:
        Dict mapping section/block keys to per-section SchemaDefinition objects
    """
    from dataclasses import replace

    all_fields = schema_definition.fields
    schemas: dict[Any, SchemaDefinition] = {}

    def _collect_child_keys(node: ASTNode) -> set[str]:
        """Collect assignment keys from a node's direct children."""
        keys: set[str] = set()
        children = getattr(node, "children", None)
        if children:
            for child in children:
                if isinstance(child, Assignment):
                    keys.add(child.key)
        return keys

    # Issue #326: Collect envelope-level assignments — fields at the document
    # root that are not inside blocks or sections. These are direct Assignment
    # nodes in doc.sections (e.g., THREAD_ID::..., TOPIC::... in DEBATE_TRANSCRIPT).
    # Without this, envelope-style documents produce empty section_schemas and
    # _check_required_field_coverage falsely flags all required fields as missing.
    #
    # GH-427: Also collect envelope-level Block keys (e.g., TURNS: as a Block
    # rather than as an inline list). Without this, structured DEBATE_TRANSCRIPT
    # documents that emit TURNS as a Block (the canonical shape for per-turn
    # validation under TURN_SCHEMA) would falsely surface
    # ``Field 'TURNS' is required but missing`` even though the Block is the
    # whole point of the per-turn enforcement contract.
    envelope_keys: set[str] = set()
    for node in doc.sections:
        if isinstance(node, Assignment) and node.key != "META":
            envelope_keys.add(node.key)
        elif isinstance(node, Block) and node.key != "META":
            envelope_keys.add(node.key)

    if envelope_keys:
        matching_fields = {fname: fdef for fname, fdef in all_fields.items() if fname in envelope_keys}
        if matching_fields:
            envelope_schema = replace(schema_definition, fields=matching_fields)
            schemas["__envelope__"] = envelope_schema

    def _walk(nodes: list[ASTNode]) -> None:
        for node in nodes:
            key = getattr(node, "key", None)
            if key is not None and key != "META":
                # Find which schema fields are present in this node's children
                child_keys = _collect_child_keys(node)
                matching_fields = {fname: fdef for fname, fdef in all_fields.items() if fname in child_keys}
                if matching_fields:
                    # Create a per-section schema with only the relevant fields
                    section_schema = replace(schema_definition, fields=matching_fields)
                    schemas[key] = section_schema

            # Recurse into children
            children = getattr(node, "children", None)
            if children:
                _walk(children)

    _walk(doc.sections)

    # GH-428: Policy-driven section-body coverage warnings
    # (W_MISSING_REQUIRED_SECTION, W_INCOMPLETE_SECTION_FIELDS) read
    # POLICY off the schema in ``section_schemas``. If the document has
    # no sections matching schema fields, the dict above can be empty —
    # leaving the validator with nothing to read POLICY from. Register
    # the full schema under a sentinel key so policy-driven walks always
    # discover it, regardless of section presence.
    #
    # PR #444 cubic P2 #1 rework: the sentinel was previously the string
    # ``"__schema__"``. A user-author-able section/block literally keyed
    # ``__schema__`` then collided with the sentinel and had its fields
    # silently excluded from coverage. The sentinel is now a non-string
    # class (POLICY_WALK_SENTINEL) — structurally inseparable from any
    # user string key.
    if schema_definition.policy.required_section_ids or schema_definition.policy.section_conditional_required:
        schemas.setdefault(POLICY_WALK_SENTINEL, schema_definition)

    return schemas


def _check_required_field_coverage(
    full_schema: SchemaDefinition,
    section_schemas: dict[Any, SchemaDefinition],
    doc: Any | None = None,
) -> list[ValidationError]:
    """Check that all required schema fields appear in at least one section.

    Issue #325: When fields are distributed across sections (e.g., FORCE in §1,
    MODE in §2), the per-section validator correctly checks each section's fields.
    But if a required field is entirely absent from the document, no section schema
    is created for it, so it silently passes. This function catches those gaps.

    Issue #344: Fields present in doc.meta (like TYPE, VERSION) are also considered
    covered. Schema FIELDS blocks may define META-level fields with REQ constraints.
    These fields live in doc.meta, not in sections, so section_schemas alone cannot
    detect them. Passing the parsed Document allows this function to check doc.meta
    for coverage, preventing false E003 errors for META-resident fields.

    Args:
        full_schema: The complete schema with all fields
        section_schemas: Per-section schemas built by _build_deep_section_schemas
        doc: Optional parsed Document. When provided, fields present in doc.meta
             are considered covered (fixes GH#344 false positive).

    Returns:
        List of ValidationError for required fields not covered by any section
    """
    from octave_mcp.core.constraints import RequiredConstraint

    errors: list[ValidationError] = []

    # Collect all fields covered across all section schemas. The
    # POLICY_WALK_SENTINEL slot (GH-428) carries the full schema for
    # policy-driven walks and would otherwise mark every field as covered;
    # skip it so legitimate "missing required field" errors are still
    # surfaced for §-section-less documents.
    #
    # PR #444 cubic P2 #1: identity comparison against the class sentinel
    # (``is POLICY_WALK_SENTINEL``) replaces the previous string match
    # (``section_key == "__schema__"``) so a user block literally keyed
    # ``__schema__`` no longer collides with the sentinel.
    covered_fields: set[str] = set()
    for section_key, section_schema in section_schemas.items():
        if section_key is POLICY_WALK_SENTINEL:
            continue
        covered_fields.update(section_schema.fields.keys())

    # GH#344: Fields present in doc.meta are also covered.
    # Schema FIELDS blocks (e.g., SKILL) may define TYPE/VERSION with REQ
    # constraints. These fields reside in doc.meta, not in document sections.
    # Without this check, _build_deep_section_schemas never finds them
    # (it only walks doc.sections), causing false E003 errors.
    if doc is not None and hasattr(doc, "meta") and doc.meta:
        covered_fields.update(doc.meta.keys())

    # Check each required field in the full schema
    for field_name, field_def in full_schema.fields.items():
        if field_name in covered_fields:
            continue  # Field is present in at least one section

        # Check if this field is required
        if field_def.pattern and field_def.pattern.constraints:
            has_req = any(isinstance(c, RequiredConstraint) for c in field_def.pattern.constraints.constraints)
            if has_req:
                errors.append(
                    ValidationError(
                        code="E003",
                        message=f"Field '{field_name}' is required but missing from document",
                        field_path=field_name,
                    )
                )

    return errors


def _validate_turn_schema(
    doc: Any,
    schema_definition: SchemaDefinition,
) -> list[ValidationError]:
    """Validate per-turn structure against TURN_SCHEMA (GH-427).

    The DEBATE_TRANSCRIPT schema declares a ``TURN_SCHEMA:`` block describing
    the contract each TURN entry must satisfy. Prior to GH-427 this block was
    documented but not enforced — malformed TURN entries (missing REQ ROLE,
    duplicate TURN_INDEX, out-of-enum ROLE) silently validated clean.

    This helper closes the gap by:

    1. Locating a top-level ``TURNS:`` Block in the document.
    2. Treating each child Block of TURNS as one turn entry.
    3. For each turn:
       - Checking every REQ field declared in ``schema_definition.turn_schema``
         is present (emits ``E_TURN_FIELD`` when absent).
       - Evaluating the holographic constraint chain (ENUM, TYPE, REGEX, etc.)
         on each present turn field, wrapping any constraint failures as
         ``E_TURN_FIELD`` so the per-turn error code remains stable for
         downstream tooling (I4 TRANSFORM_AUDITABILITY: stable error IDs).
    4. Tracking ``TURN_INDEX`` values across all turns and emitting
       ``E_TURN_INDEX`` on any duplicate (uniqueness invariant).

    Args:
        doc: Parsed Document AST.
        schema_definition: Loaded SchemaDefinition whose ``turn_schema`` is the
            per-item sub-schema. Caller MUST verify ``turn_schema is not None``
            before invoking this helper — passing ``None`` is a programming
            error and surfaces as no-op.

    Returns:
        List of ``ValidationError`` instances. Empty when no TURNS block is
        present (lenient: turn-level validation only fires when the document
        commits to the structured shape) or when every turn validates clean.
    """
    errors: list[ValidationError] = []

    turn_schema = schema_definition.turn_schema
    if not turn_schema:
        return errors

    # Locate the top-level TURNS: Block. If TURNS is emitted as a flat list
    # assignment instead, per-turn validation cannot run (turn structure is
    # opaque); we intentionally do not surface a warning here — the FIELDS-level
    # TYPE[LIST] constraint already covers the "TURNS is present in some shape"
    # contract, and treating bare lists as enforceable would conflict with the
    # documented schema fixture ``TURNS::[[turn1,turn2]∧...]``.
    turns_block: Block | None = None
    for node in doc.sections:
        if isinstance(node, Block) and node.key == "TURNS":
            turns_block = node
            break

    if turns_block is None:
        return errors

    # Pre-compute REQ field names from turn_schema for O(1) lookup.
    required_turn_fields = {
        fname
        for fname, fdef in turn_schema.items()
        if fdef.pattern
        and fdef.pattern.constraints
        and any(isinstance(c, RequiredConstraint) for c in fdef.pattern.constraints.constraints)
    }

    # Track TURN_INDEX values across all turns for uniqueness enforcement.
    seen_turn_indices: dict[Any, str] = {}

    for child in turns_block.children:
        if not isinstance(child, Block):
            # Skip non-Block children (e.g., stray Assignments inside TURNS:).
            # A stricter policy could surface these as warnings, but the issue
            # acceptance criteria only require per-turn field enforcement.
            continue

        turn_key = child.key
        turn_path_prefix = f"TURNS.{turn_key}"

        # Collect field assignments for this turn.
        turn_fields: dict[str, Any] = {}
        for grandchild in child.children:
            if isinstance(grandchild, Assignment):
                turn_fields[grandchild.key] = grandchild.value

        # REQ field coverage check.
        for req_name in required_turn_fields:
            if req_name not in turn_fields:
                errors.append(
                    ValidationError(
                        code="E_TURN_FIELD",
                        message=(f"Turn '{turn_key}' is missing required TURN_SCHEMA " f"field '{req_name}' (GH-427)."),
                        field_path=f"{turn_path_prefix}.{req_name}",
                    )
                )

        # Per-field constraint evaluation (ENUM, TYPE, REGEX, etc.).
        for fname, fdef in turn_schema.items():
            if fname not in turn_fields:
                continue  # absent fields handled above (REQ) or skipped (OPT)
            if not fdef.pattern or not fdef.pattern.constraints:
                continue

            value = turn_fields[fname]
            result = fdef.pattern.constraints.evaluate(value=value, path=f"{turn_path_prefix}.{fname}")
            if not result.valid:
                for err in result.errors:
                    # Wrap constraint failures under the stable E_TURN_FIELD
                    # code so per-turn enforcement uses ONE discriminant
                    # regardless of which underlying constraint fired. The
                    # original code is preserved in the message tail for
                    # diagnostic depth.
                    errors.append(
                        ValidationError(
                            code="E_TURN_FIELD",
                            message=(
                                f"Turn '{turn_key}' field '{fname}' failed "
                                f"TURN_SCHEMA constraint [{err.code}]: {err.message}"
                            ),
                            field_path=err.path,
                        )
                    )

        # TURN_INDEX uniqueness invariant.
        if "TURN_INDEX" in turn_fields:
            ti_value = turn_fields["TURN_INDEX"]
            # CE rework: guard the duplicate-tracking dict lookup against
            # non-hashable TURN_INDEX values (e.g. a malformed
            # ``TURN_INDEX::[1,2]`` parses as ``ListValue`` — an unhashable
            # dataclass). Without this guard, the ``in seen_turn_indices``
            # probe raised ``TypeError: unhashable type`` and escaped the
            # validator entirely, bypassing the INVALID envelope contract
            # and silently breaking PROD::I5 SCHEMA_SOVEREIGNTY
            # (validation_status_visible_in_output).
            try:
                hash(ti_value)
            except TypeError:
                errors.append(
                    ValidationError(
                        code="E_TURN_INDEX_TYPE",
                        message=(
                            f"Turn '{turn_key}' TURN_INDEX value {ti_value!r} "
                            f"is not a hashable scalar (got "
                            f"{type(ti_value).__name__}); TURN_INDEX must be a "
                            f"scalar value to participate in uniqueness "
                            f"enforcement (GH-427 CE rework)."
                        ),
                        field_path=f"{turn_path_prefix}.TURN_INDEX",
                    )
                )
                # Skip duplicate tracking for this turn and continue with
                # remaining siblings — the surfaced error is sufficient to
                # mark the document INVALID.
                continue
            if ti_value in seen_turn_indices:
                errors.append(
                    ValidationError(
                        code="E_TURN_INDEX",
                        message=(
                            f"Duplicate TURN_INDEX value {ti_value!r} across "
                            f"turns '{seen_turn_indices[ti_value]}' and "
                            f"'{turn_key}' (GH-427: TURN_INDEX must be unique)."
                        ),
                        field_path=f"{turn_path_prefix}.TURN_INDEX",
                    )
                )
            else:
                seen_turn_indices[ti_value] = turn_key

    return errors


def _extract_spec_code(error_message: str) -> str | None:
    """Extract spec error code (E001-E007) from error message.

    Gap_6 fix: The core lexer/parser embed spec codes in error messages like:
    "E005 at line 2, column 1: Tabs are not allowed..."
    "E001 at line 2, column 4: Single colon assignment detected..."

    This function extracts the spec code so it can be preserved in the
    error dict alongside the wrapper code (E_TOKENIZE, E_PARSE).

    Args:
        error_message: The error message from lexer/parser exception

    Returns:
        The spec code (e.g., "E005") if found, None otherwise
    """
    match = SPEC_CODE_PATTERN.search(error_message)
    return match.group(1) if match else None


class ValidateTool(BaseTool):
    """MCP tool for octave_validate - schema validation + repair suggestions."""

    # Security: allowed file extensions
    ALLOWED_EXTENSIONS = {".oct.md", ".octave", ".md"}

    def _build_unified_diff(self, before: str, after: str) -> str:
        """Build a compact unified diff string for diff-first responses.

        Args:
            before: Original content
            after: Canonical content

        Returns:
            Unified diff string, truncated if too large
        """
        before_lines = before.splitlines(keepends=True)
        after_lines = after.splitlines(keepends=True)
        diff_iter = unified_diff(before_lines, after_lines, fromfile="original", tofile="canonical", n=3)

        max_chars = 200_000
        out: list[str] = []
        total = 0
        for line in diff_iter:
            if total + len(line) > max_chars:
                out.append("\n... (diff truncated)\n")
                break
            out.append(line)
            total += len(line)

        return "".join(out)

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
            "diff_only",
            "boolean",
            required=False,
            description="If True, return diff instead of canonical content. Saves tokens when validating.",
        )

        schema.add_parameter(
            "compact",
            "boolean",
            required=False,
            description="If True, return warning/error counts instead of full lists. Saves tokens.",
        )

        schema.add_parameter(
            "profile",
            "string",
            required=False,
            description=(
                "Validation strictness profile: "
                "STRICT (full compliance, reject unknown), "
                "STANDARD (default), "
                "LENIENT (warnings not errors, auto-repairs), "
                "ULTRA (minimal validation)."
            ),
            enum=["STRICT", "STANDARD", "LENIENT", "ULTRA"],
        )

        return schema.build()

    def _error_envelope(
        self,
        errors: list[dict[str, Any]],
        content: str = "",
        diff_only: bool = False,
        compact: bool = False,
        profile: str = DEFAULT_PROFILE,
    ) -> dict[str, Any]:
        """Build consistent error envelope with all required fields.

        Args:
            errors: List of error records
            content: Original content to return in canonical (on error)
            diff_only: If True, set canonical to None instead of content
            compact: If True, include counts instead of full lists
            profile: Validation profile used (#183)

        Returns:
            Complete error envelope with all required fields per spec Section 7
        """
        repairs: list[dict[str, Any]] = []
        result: dict[str, Any] = {
            "status": "error",
            "canonical": None if diff_only else content,  # CE FIX #2: Honor diff_only on errors
            "repairs": repairs,
            "repair_log": repairs,  # Gap 7: Spec-compliant alias (same reference)
            "warnings": [],
            "errors": errors,
            "validation_status": "UNVALIDATED",  # I5: Explicit bypass on error
            "valid": False,  # Gap 7: Boolean derived from validation_status
            "validation_errors": [],  # Gap 7: Always present per spec Section 7
            "routing_log": [],  # I4: Always include routing_log for consistency
            "profile": profile,  # #183: Include profile in error envelope
        }

        # CE FIX #2: Honor compact mode on errors
        if compact:
            result["warning_count"] = 0
            result["error_count"] = len(errors)
            result["validation_error_count"] = 0

        # CE Review: has_warnings flag for profile-aware gating (always False on error envelope)
        result["has_warnings"] = False

        return result

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute validation pipeline.

        Args:
            content: OCTAVE content to validate (XOR with file_path)
            file_path: Path to OCTAVE file to validate (XOR with content)
            schema: Schema name for validation
            fix: Whether to apply repairs (default: False)
            debug_grammar: Whether to include compiled grammar in output (default: False)

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
            - routing_log: Target routing audit trail (I4 compliance, Issue #103)
            - debug_info: Constraint grammar debug information (when debug_grammar=True)
        """
        # Validate and extract parameters
        params = self.validate_parameters(kwargs)
        content = params.get("content")
        file_path = params.get("file_path")
        schema_name = params["schema"]
        fix = params.get("fix", False)
        debug_grammar = params.get("debug_grammar", False)
        grammar_hint = params.get("grammar_hint", False)
        diff_only = params.get("diff_only", False)
        compact = params.get("compact", False)

        # #183: Extract and validate profile parameter
        profile_raw = params.get("profile", DEFAULT_PROFILE)
        profile = profile_raw.upper() if profile_raw else DEFAULT_PROFILE

        # Validate profile value
        if profile not in VALID_PROFILES:
            return self._error_envelope(
                [
                    {
                        "code": "E_PROFILE",
                        "message": (
                            f"Invalid profile '{profile_raw}'. " f"Valid profiles: {', '.join(sorted(VALID_PROFILES))}"
                        ),
                    }
                ],
                diff_only=diff_only,
                compact=compact,
                profile=profile_raw or "",  # Report raw value for debugging
            )

        # XOR validation: exactly one of content or file_path must be provided
        if content is not None and file_path is not None:
            return self._error_envelope(
                [
                    {
                        "code": "E_INPUT",
                        "message": "Cannot provide both content and file_path - they are mutually exclusive",
                    }
                ],
                diff_only=diff_only,
                compact=compact,
                profile=profile,
            )

        if content is None and file_path is None:
            return self._error_envelope(
                [{"code": "E_INPUT", "message": "Must provide either content or file_path"}],
                diff_only=diff_only,
                compact=compact,
                profile=profile,
            )

        # If file_path provided, read file content
        if file_path is not None:
            # Security: validate path before reading
            is_valid, error_msg = self._validate_path(file_path)
            if not is_valid:
                return self._error_envelope(
                    [{"code": "E_PATH", "message": error_msg or "Invalid file path"}],
                    diff_only=diff_only,
                    compact=compact,
                    profile=profile,
                )

            path = Path(file_path)
            if not path.exists():
                return self._error_envelope(
                    [{"code": "E_FILE", "message": f"File not found: {file_path}"}],
                    diff_only=diff_only,
                    compact=compact,
                    profile=profile,
                )

            try:
                content = path.read_text(encoding="utf-8")
            except Exception as e:
                return self._error_envelope(
                    [{"code": "E_READ", "message": f"Error reading file: {str(e)}"}],
                    diff_only=diff_only,
                    compact=compact,
                    profile=profile,
                )

        # At this point content is guaranteed to be a string
        assert content is not None

        # Initialize repairs list - used by both 'repairs' and 'repair_log' (Gap 7 spec compliance)
        repairs_list: list[dict[str, Any]] = []

        # Initialize result with unified envelope per D2 design and spec Section 7
        # I5 (Schema Sovereignty): validation_status must be UNVALIDATED to make bypass visible
        # "Schema bypass shall be visible, never silent" - North Star I5
        # Gap 7: Added 'valid', 'repair_log', 'validation_errors' per spec Section 7
        result: dict[str, Any] = {
            "status": "success",
            "canonical": "",
            "repairs": repairs_list,
            "repair_log": repairs_list,  # Gap 7: Spec-compliant alias (same reference)
            "warnings": [],
            "errors": [],
            "validation_status": "UNVALIDATED",  # I5: Explicit bypass until validated
            "valid": False,  # Gap 7: Boolean derived from validation_status (updated later)
            "validation_errors": [],  # Gap 7: Always present per spec Section 7
            "routing_log": [],  # I4: Target routing audit trail (Issue #103)
            "profile": profile,  # #183: Include profile in result for transparency
        }

        # STAGE 1+2: Parse with frontmatter handling and collect repairs
        # Issue #91 CE Fix: Use parse_with_warnings() as single authority for:
        # 1. Strip YAML frontmatter internally
        # 2. Tokenize stripped content
        # 3. Parse into AST
        # 4. Return combined lexer_repairs + parser warnings with correct positions
        # This eliminates positional divergence from separate tokenize/parse calls
        try:
            doc, parse_repairs = parse_with_warnings(content)
            result["repairs"].extend(parse_repairs)

            # Issue #235 T13: Literal zone reporting (§8.1, §8.4)
            # After parse, before validation — count zones and populate zone_report.
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
                result["literal_zone_repair_log"] = build_literal_zone_repair_log(
                    zones, doc, "octave_validate"
                ).to_dict()

            # GH#452: Detect snake-case prose blobs in reasoning-field positions.
            # Refined contract per operator comment 4549996376. v1 ADVISORY only —
            # surfaces in warnings[] alongside other non-blocking validator output.
            # Same audit path as W_ANNOTATION_TOO_LONG (in WriteTool); here we
            # route into the validator's ``warnings`` channel so ``octave_validate``
            # callers see the discipline guidance (I4/I5).
            snake_case_blob_warnings = _detect_snake_case_blob(content)
            result["warnings"].extend(snake_case_blob_warnings)

        except Exception as e:
            result["status"] = "error"
            # Check if it's a tokenization or parse error
            error_msg = str(e)

            # Gap_6: Extract spec code (E001-E007) from error message if present
            spec_code = _extract_spec_code(error_msg)

            if "E005" in error_msg or "Unexpected character" in error_msg:
                error_dict: dict[str, Any] = {
                    "code": "E_TOKENIZE",
                    "message": f"Tokenization error: {error_msg}",
                }
            else:
                error_dict = {
                    "code": "E_PARSE",
                    "message": f"Parse error: {error_msg}",
                }

            # Gap_6: Add spec_code if extracted (only for core errors)
            if spec_code is not None:
                error_dict["spec_code"] = spec_code

            result["errors"].append(error_dict)
            # CE FIX #2: Honor diff_only on parse errors
            result["canonical"] = None if diff_only else content
            # CE FIX #2: Honor compact mode on parse errors
            if compact:
                result["warning_count"] = len(result["warnings"])
                result["error_count"] = len(result["errors"])
                result["validation_error_count"] = len(result.get("validation_errors", []))
            return result

        # STAGE 3: Schema Validation (I5 Schema Sovereignty)
        # Try to load the requested schema (old-style dict for META block validation)
        schema_def = get_builtin_schema(schema_name)

        # Gap_1: Also try to load SchemaDefinition for section constraint validation
        # This enables holographic pattern constraint evaluation via section_schemas
        schema_definition: SchemaDefinition | None = None
        section_schemas: dict[Any, SchemaDefinition] | None = None
        try:
            schema_definition = load_schema_by_name(schema_name)
            if schema_definition is not None and schema_definition.fields:
                # Build section_schemas dict for constraint validation.
                # Map schema name to schema (handles envelope-level fields like DEBATE_TRANSCRIPT).
                section_schemas = {schema_definition.name: schema_definition}

                # Issue #325: For document-type schemas (e.g., COGNITION_DEFINITION), the
                # document's sections and nested blocks have different keys than the schema name.
                # Map all document sections AND their nested blocks to the schema so the
                # validator can check field constraints at every level of the document tree.
                if doc.meta.get("TYPE") == schema_name:
                    section_schemas = _build_deep_section_schemas(doc, schema_definition)
        except Exception:
            # Schema loading may fail - continue with old-style dict validation
            pass

        # Phase 3: Add debug grammar information if requested
        if debug_grammar and schema_definition is not None:
            debug_info: dict[str, Any] = {
                "schema_name": schema_definition.name,
                "schema_version": schema_definition.version or "unknown",
                "field_constraints": {},
            }
            # Compile constraint grammar for each field
            for field_name, field_def in schema_definition.fields.items():
                # CORRECTNESS FIX: Use field_def.pattern.constraints (not field_def.constraint_chain)
                if hasattr(field_def, "pattern") and field_def.pattern and field_def.pattern.constraints:
                    chain = field_def.pattern.constraints
                    compiled = chain.compile()
                    debug_info["field_constraints"][field_name] = {
                        "chain": chain.to_string(),
                        "compiled_regex": compiled,
                    }
            result["debug_info"] = debug_info

        # Determine if we have a schema available for validation
        # Priority: old-style builtin dict OR file-based SchemaDefinition
        has_schema = schema_def is not None or (schema_definition is not None and schema_definition.fields)

        if has_schema:
            # Schema found - perform validation
            # I5: "Schema-validated documents shall record the schema name and version used"
            if schema_def is not None:
                result["schema_name"] = schema_def.get("name", schema_name)
                result["schema_version"] = schema_def.get("version", "unknown")
            elif schema_definition is not None:
                result["schema_name"] = schema_definition.name
                result["schema_version"] = schema_definition.version or "unknown"

            # Use the validator with the schema definition
            # Gap_1: Pass section_schemas for constraint validation on document sections
            # #183: STRICT mode uses strict validation (reject unknown fields)
            strict_mode = profile == "STRICT"
            validator = Validator(schema=schema_def)
            validation_errors = validator.validate(doc, strict=strict_mode, section_schemas=section_schemas)

            # Issue #325: Document-level required field coverage check.
            # When using deep section_schemas (per-section schemas), required fields
            # that are entirely absent from the document won't be caught by the
            # per-section validator (because no section schema is created for them).
            # Check that every REQ field from the full schema appears in at least
            # one section's schema.
            if section_schemas is not None and schema_definition is not None and doc.meta.get("TYPE") == schema_name:
                coverage_errors = _check_required_field_coverage(schema_definition, section_schemas, doc=doc)
                validation_errors.extend(coverage_errors)

            # GH-427: Per-turn TURN_SCHEMA enforcement for DEBATE_TRANSCRIPT and
            # any other schema declaring a ``TURN_SCHEMA:`` block. Prior to this
            # hook the block was extracted but never consulted, leaving a
            # documented-but-not-enforced contract drift (PROD::I5).
            if schema_definition is not None and schema_definition.turn_schema:
                turn_errors = _validate_turn_schema(doc, schema_definition)
                validation_errors.extend(turn_errors)

            if validation_errors:
                # Convert errors to dicts for reporting
                error_dicts = [
                    {
                        "code": err.code,
                        "message": err.message,
                        "field": err.field_path,
                    }
                    for err in validation_errors
                ]

                # #183: Profile-based handling of validation errors
                # CE REVIEW: LENIENT/ULTRA profiles downgrade validation errors to warnings
                # and set validation_status=VALIDATED. Callers gating only on validation_status
                # must also check warnings/has_warnings when using these profiles.
                # This is intentional: these profiles prioritize flexibility over strict validation.
                if profile in ("LENIENT", "ULTRA"):
                    # LENIENT/ULTRA: Downgrade validation errors to warnings
                    # Document is still considered valid (can proceed with warnings)
                    result["validation_status"] = "VALIDATED"
                    result["valid"] = True
                    result["warnings"].extend(error_dicts)
                    # validation_errors empty since we're treating as warnings
                    result["validation_errors"] = []
                else:
                    # STRICT/STANDARD: Validation errors are blocking
                    # I5: Schema validation failed - mark as INVALID
                    result["validation_status"] = "INVALID"
                    result["valid"] = False  # Gap 7: Boolean correlates with validation_status
                    result["validation_errors"] = error_dicts
                    # Also add to warnings for backward compatibility
                    result["warnings"].extend(result["validation_errors"])

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
                # I5: Schema validation passed - mark as VALIDATED
                result["validation_status"] = "VALIDATED"
                result["valid"] = True  # Gap 7: Boolean correlates with validation_status
                # Gap 7: validation_errors always present (empty when valid)
        else:
            # Schema not found - remain UNVALIDATED
            # I5: "Schema bypass shall be visible, never silent"
            validator = Validator(schema=None)
            validation_errors = validator.validate(doc, strict=False, section_schemas=section_schemas)

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

        # I4 (Discoverable Artifact Persistence): Expose routing_log in output
        # "If not written and addressable -> didn't happen" - Issue #103
        result["routing_log"] = validator.routing_log.to_dict()

        # STAGE 4: Repair (if fix=True)
        # Gap_5: Pass schema_definition to repair() for schema-driven repairs
        # repair() requires schema parameter to apply TIER_REPAIR fixes (enum casefold, type coercion)
        if fix:
            doc, repair_log = repair(doc, validation_errors, fix=True, schema=schema_definition)
            # Convert RepairEntry dataclasses to dicts for JSON serialization
            result["repairs"].extend([entry.to_dict() for entry in repair_log.repairs])

            # Re-validate after repairs
            # Gap_1: Pass section_schemas for constraint validation
            validator_for_repair = Validator(schema=schema_def if schema_def else None)
            validation_errors = validator_for_repair.validate(doc, strict=False, section_schemas=section_schemas)
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

            if diff_only:
                # Token efficiency: return diff instead of full canonical
                content_changed = content != canonical_output
                result["changed"] = content_changed

                # CE FIX #1: Size guard before expensive diff generation
                # Skip diff computation on large content to prevent high CPU/memory
                if content_changed and len(content) > DIFF_SIZE_THRESHOLD:
                    result["diff"] = "omitted: too large (>100KB)"
                elif content_changed:
                    result["diff"] = self._build_unified_diff(content, canonical_output)
                else:
                    result["diff"] = "no changes"
                result["canonical"] = None  # Don't echo back
            else:
                result["canonical"] = canonical_output

        except Exception as e:
            result["status"] = "error"
            result["errors"].append({"code": "E_EMIT", "message": f"Emit error: {str(e)}"})
            return result

        # Compact mode: summarize warnings as counts
        if compact:
            result["warning_count"] = len(result["warnings"])
            result["error_count"] = len(result["errors"])
            result["validation_error_count"] = len(result.get("validation_errors", []))
            result["warnings"] = []
            result["validation_errors"] = []

        # Add has_warnings flag for profile-aware gating
        # CE Review: Makes it explicit when warnings exist alongside VALIDATED status
        result["has_warnings"] = len(result.get("warnings", [])) > 0 or result.get("warning_count", 0) > 0

        return result
