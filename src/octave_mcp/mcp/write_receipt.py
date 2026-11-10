"""Receipt level for ``octave_write`` (tool-fidelity slice 1, PR-1).

``receipt="full"`` (default) is today's receipt, unchanged. ``receipt="summary"``
drops the bulky derived fields and keeps everything I4 (audit trail) and I5
(validation status and literal-zone flags visible in output) need.

Governing record: OCTAVE-MCP-DIRECTION-CONTAINER-RECEIPTS-PITH-20261110.

Kept in its own module so the shaping logic has one home and ``write.py``
stays a thin caller.
"""

from __future__ import annotations

from typing import Any

RECEIPT_FULL = "full"
RECEIPT_SUMMARY = "summary"
RECEIPT_VALUES = (RECEIPT_FULL, RECEIPT_SUMMARY)

# Keys a summary receipt leaves out. Everything else is kept, including any
# key added later, so a new audit field is never dropped silently (I4).
SUMMARY_DROPPED_KEYS = (
    "diff",
    "diff_unified",
    "validation_hint",
    "debug_info",
    "zone_report",
    "literal_zone_repair_log",
)

RECEIPT_DESCRIPTION = (
    "Receipt level. 'full' (default): today's receipt, unchanged. "
    "'summary': keeps status, path, canonical_hash, corrections, warnings, errors, "
    "validation_status, mode and the literal-zone flags; leaves out diff, diff_unified, "
    "validation_hint, debug_info, zone_report, literal_zone_repair_log and an empty "
    "compilations. Error receipts are identical at both levels."
)


def add_receipt_parameter(built_schema: dict[str, Any]) -> dict[str, Any]:
    """Add the optional ``receipt`` property to a built input schema."""
    built_schema["properties"]["receipt"] = {
        "type": "string",
        "description": RECEIPT_DESCRIPTION,
        "enum": list(RECEIPT_VALUES),
    }
    return built_schema


def is_valid_receipt(value: Any) -> bool:
    """True when ``value`` is a supported receipt level."""
    # isinstance guard first: ``in`` on a tuple would raise for unhashable-free
    # values too, but a non-str is never valid and must not reach the compare.
    return isinstance(value, str) and value in RECEIPT_VALUES


def invalid_receipt_error(value: Any) -> dict[str, str]:
    """Structured E_INPUT error record for an unsupported receipt value."""
    return {
        "code": "E_INPUT",
        "message": f"Invalid receipt: {value!r}. Expected one of {list(RECEIPT_VALUES)}.",
    }


def summarize_receipt(result: dict[str, Any]) -> dict[str, Any]:
    """Project a success receipt to the summary level.

    Error envelopes are returned untouched: a refusal is never trimmed.
    """
    if result.get("status") == "error":
        return result
    summary = {k: v for k, v in result.items() if k not in SUMMARY_DROPPED_KEYS}
    if not summary.get("compilations"):
        summary.pop("compilations", None)
    return summary
