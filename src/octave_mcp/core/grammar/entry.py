"""Unified parse front-door for OCTAVE-MCP (ADR-0006 SR1-T1 Steps 2 + 6).

This module is the canonical parse seam at ``octave_mcp.core.grammar``
through which all callers (``mcp/validate.py``, ``mcp/write.py``, future
visitors) reach the parse pipeline. Later SR1-T1 steps inject
``TIER_NORMALIZATION`` logging (Step 3), CST visitor protocol (Step 4),
and emitter unification (Step 5) at this same seam without touching call
sites.

ADR-0006 SR1-T1 Step 6 (R2 closure) additionally relocates the
``validate_frontmatter`` parse-stage hook here from
``octave_mcp.core.validator``. Zone-2 (YAML frontmatter) validation is
naturally a parse-stage concern: the raw frontmatter string is captured
by the parser and surfaced on ``Document.raw_frontmatter``, and its
schema-driven validation needs only that string plus a
``SchemaDefinition``. Co-locating it with ``parse()`` makes the seam
self-contained — the validator no longer needs to reach back across
modules to validate frontmatter.

**Identity contract.** ``entry.parse``, ``entry.parse_with_warnings``,
and ``entry.ParserError`` are the *same objects* as their counterparts in
:mod:`octave_mcp.core.parser`. Re-exporting (rather than wrapping or
subclassing) preserves :mod:`functools` decorations, monkey-patches,
``is``-identity checks, and ``except``-clause matching across the seam.
This is asserted by ``tests/unit/core/grammar/test_entry.py``. The
re-export of :class:`ParserError` co-locates the call surface with its
error surface so consumers never need to pierce the seam.

**No behaviour change at Step 2.** Step 2 was a pure refactor. No
logging, normalization, or error-handling additions live here — those
land at later, gated steps in the migration plan
(``docs/adr/adr-0006-sr1-t1-grammar-core-design.md`` §3).

**Step 6 (this PR).** Adds ``validate_frontmatter`` as the only true
"parse-stage hook" on this module. It is read-only inspection of
``Document.raw_frontmatter`` (I1 compliance) and reports its validation
status visibly (I5 compliance).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from octave_mcp.core.parser import ParserError, parse, parse_with_warnings

if TYPE_CHECKING:
    from octave_mcp.core.schema_extractor import SchemaDefinition
    from octave_mcp.core.validator import ValidationError


def validate_frontmatter(
    raw_frontmatter: str | None,
    schema: SchemaDefinition,
) -> list[ValidationError]:
    """Validate YAML frontmatter against schema frontmatter definitions.

    Issue #244 — extends I5 Schema Sovereignty to Zone 2 (YAML
    frontmatter). This function is opt-in: it only validates when the
    schema defines frontmatter requirements (``schema.frontmatter``
    truthy).

    Compliance notes:

    * **I1 (Syntactic Fidelity).** Read-only inspection. Zone 2 content
      is never altered.
    * **I5 (Schema Sovereignty).** If we can't validate (YAML parse
      error), we say so — emit ``E_FM_PARSE``.

    ADR-0006 SR1-T1 Step 6 relocated this function from
    ``octave_mcp.core.validator``; see design §3 row 6 and §2.2. The
    legacy location is intentionally absent (no shim).

    Args:
        raw_frontmatter: Raw YAML frontmatter string from
            ``Document.raw_frontmatter``. May be ``None`` if no
            frontmatter is present.
        schema: ``SchemaDefinition`` that may contain frontmatter field
            definitions.

    Returns:
        List of :class:`ValidationError`. Empty if no frontmatter
        requirements in schema or if all requirements are satisfied.
    """
    # Local imports to keep the parse-stage hook self-contained and to
    # avoid a circular import (validator.py imports validate_frontmatter
    # from this module at call time).
    from octave_mcp.core.validator import ValidationError

    # No frontmatter definitions in schema = nothing to validate (opt-in)
    if not schema.frontmatter:
        return []

    errors: list[ValidationError] = []

    # If frontmatter is absent but schema requires fields, report each required field
    if raw_frontmatter is None:
        for field_name, field_def in schema.frontmatter.items():
            if field_def.required:
                errors.append(
                    ValidationError(
                        code="E_FM_REQUIRED",
                        message=f"Required frontmatter field '{field_name}' is missing",
                        field_path=f"frontmatter.{field_name}",
                    )
                )
        return errors

    # Parse YAML frontmatter
    import yaml

    try:
        parsed = yaml.safe_load(raw_frontmatter)
    except yaml.YAMLError as e:
        errors.append(
            ValidationError(
                code="E_FM_PARSE",
                message=f"Failed to parse YAML frontmatter: {e}",
                field_path="frontmatter",
            )
        )
        return errors

    # Handle case where YAML parses to non-dict (e.g., scalar string)
    if not isinstance(parsed, dict):
        parsed = {}

    # Validate each defined frontmatter field
    for field_name, field_def in schema.frontmatter.items():
        value = parsed.get(field_name)

        # Check required fields
        if field_def.required and value is None:
            errors.append(
                ValidationError(
                    code="E_FM_REQUIRED",
                    message=f"Required frontmatter field '{field_name}' is missing",
                    field_path=f"frontmatter.{field_name}",
                )
            )
            continue

        # Skip type validation for absent optional fields
        if value is None:
            continue

        # Type validation
        type_map: dict[str, type | tuple[type, ...]] = {
            "STRING": str,
            "LIST": list,
            "BOOLEAN": bool,
        }
        expected_type = type_map.get(field_def.field_type)
        if expected_type and not isinstance(value, expected_type):
            errors.append(
                ValidationError(
                    code="E_FM_TYPE",
                    message=(
                        f"Frontmatter field '{field_name}' expected {field_def.field_type}, "
                        f"got {type(value).__name__}"
                    ),
                    field_path=f"frontmatter.{field_name}",
                )
            )

    return errors


__all__ = ["ParserError", "parse", "parse_with_warnings", "validate_frontmatter"]
