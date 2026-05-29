"""GH#484 — E_NESTED_DICT_IN_MERGE_PAYLOAD rejection guard for ``octave_write`` changes-mode.

Root cause: ``_normalize_value_for_ast`` in write_mutation.py wraps any ``dict`` as
``InlineMap`` unconditionally.  When a MERGE payload contains a nested plain Python dict
(e.g., ``{"NESTED": {"deep": "dict"}}``), the serialization emits an inline map
(``KEY::[NESTED::[deep::dict]]``) which fails strict re-parse with
``E_NESTED_INLINE_MAP``.

STRATEGY_S3 (DocumentMutator) is deferred.  The minimum correct fix is a REJECTION guard
at input validation time: ``_validate_change_paths`` must append an
``E_NESTED_DICT_IN_MERGE_PAYLOAD`` error when a MERGE payload contains plain nested dict
values (ones that are not op-descriptors — ``_is_op_descriptor`` subsumes delete
sentinels since both carry a ``$op`` key).

TDD protocol (T2 tier): these tests were authored RED (failing before the guard lands)
and gate GREEN (guard implemented in ``_validate_change_paths``).
"""

import os
import tempfile

import pytest

from octave_mcp.mcp.write import WriteTool

_TOOL = WriteTool()

_BASE_DOC = """===EXAMPLE===
META:
  TYPE::TEST
KEY::top_level_value
===END===
"""


async def _write(doc: str, changes: dict) -> dict:
    """Seed ``doc`` to a temp file, apply ``changes``, return the result dict."""
    fd, path = tempfile.mkstemp(suffix=".oct.md")
    os.close(fd)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(doc)
        return await _TOOL.execute(target_path=path, changes=changes, format_style="preserve")
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# E_NESTED_DICT_IN_MERGE_PAYLOAD — rejection guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_merge_with_nested_dict_returns_error() -> None:
    """MERGE payload containing a plain nested dict must be rejected.

    Acceptance criterion from GH#484: calling octave_write with
    ``changes={"SOME_KEY": {"$op": "MERGE", "value": {"NESTED": {"deep": "dict"}}}}``
    must produce E_NESTED_DICT_IN_MERGE_PAYLOAD in the errors list.
    """
    result = await _write(
        _BASE_DOC,
        changes={"KEY": {"$op": "MERGE", "value": {"NESTED": {"deep": "dict"}}}},
    )
    errors = result.get("errors", [])
    error_codes = [e.get("code") for e in errors]
    assert "E_NESTED_DICT_IN_MERGE_PAYLOAD" in error_codes, (
        f"Expected E_NESTED_DICT_IN_MERGE_PAYLOAD in errors but got: {errors}"
    )


@pytest.mark.asyncio
async def test_merge_with_nested_dict_error_message_is_actionable() -> None:
    """The error message must direct the caller to the content parameter + format_style=preserve."""
    result = await _write(
        _BASE_DOC,
        changes={"KEY": {"$op": "MERGE", "value": {"NESTED": {"deep": "dict"}}}},
    )
    errors = result.get("errors", [])
    e = next((e for e in errors if e.get("code") == "E_NESTED_DICT_IN_MERGE_PAYLOAD"), None)
    assert e is not None, f"No E_NESTED_DICT_IN_MERGE_PAYLOAD error found in: {errors}"
    msg = e.get("message", "")
    assert "content" in msg, (
        f"Error message should mention the 'content' parameter. Got: {msg!r}"
    )
    assert "format_style" in msg or "preserve" in msg, (
        f"Error message should mention 'format_style=preserve'. Got: {msg!r}"
    )
    # Should mention which nested key(s) triggered the rejection
    assert "NESTED" in msg, f"Error message should cite the nested key 'NESTED'. Got: {msg!r}"


@pytest.mark.asyncio
async def test_merge_with_multiple_nested_dicts_lists_all_keys() -> None:
    """All nested dict keys must appear in the error message."""
    result = await _write(
        _BASE_DOC,
        changes={
            "KEY": {
                "$op": "MERGE",
                "value": {
                    "FIRST": {"a": "1"},
                    "SECOND": {"b": "2"},
                    "SCALAR": "fine",
                },
            }
        },
    )
    errors = result.get("errors", [])
    e = next((e for e in errors if e.get("code") == "E_NESTED_DICT_IN_MERGE_PAYLOAD"), None)
    assert e is not None
    msg = e.get("message", "")
    assert "FIRST" in msg, f"Expected 'FIRST' in message. Got: {msg!r}"
    assert "SECOND" in msg, f"Expected 'SECOND' in message. Got: {msg!r}"


@pytest.mark.asyncio
async def test_merge_with_scalar_values_passes() -> None:
    """MERGE payload with only scalar values must NOT trigger the guard."""
    result = await _write(
        _BASE_DOC,
        changes={"META": {"$op": "MERGE", "value": {"TYPE": "UPDATED", "STATUS": "OK"}}},
    )
    errors = result.get("errors", [])
    error_codes = [e.get("code") for e in errors]
    assert "E_NESTED_DICT_IN_MERGE_PAYLOAD" not in error_codes, (
        f"Unexpected E_NESTED_DICT_IN_MERGE_PAYLOAD for scalar MERGE: {errors}"
    )


@pytest.mark.asyncio
async def test_merge_with_op_descriptor_value_passes() -> None:
    """A MERGE payload whose sub-value is itself an op-descriptor must pass through.

    Op-descriptors (any dict with a ``$op`` key, including delete sentinels) are
    legitimate sub-operations and must not be misidentified as plain nested dicts.
    The guard uses ``_is_op_descriptor`` which covers all ``$op``-keyed dicts.
    """
    result = await _write(
        _BASE_DOC,
        changes={"META": {"$op": "MERGE", "value": {"TYPE": {"$op": "DELETE"}}}},
    )
    errors = result.get("errors", [])
    error_codes = [e.get("code") for e in errors]
    assert "E_NESTED_DICT_IN_MERGE_PAYLOAD" not in error_codes, (
        f"Unexpected E_NESTED_DICT_IN_MERGE_PAYLOAD for op-descriptor sub-value: {errors}"
    )


@pytest.mark.asyncio
async def test_non_merge_op_with_dict_value_not_affected() -> None:
    """Non-MERGE ops (e.g., bare dict assignment) are unaffected by the guard."""
    result = await _write(
        _BASE_DOC,
        # Bare dict (no $op) is processed differently — guard is MERGE-specific
        changes={"META": {"TYPE": "UPDATED"}},
    )
    errors = result.get("errors", [])
    error_codes = [e.get("code") for e in errors]
    assert "E_NESTED_DICT_IN_MERGE_PAYLOAD" not in error_codes, (
        f"Unexpected E_NESTED_DICT_IN_MERGE_PAYLOAD for non-MERGE change: {errors}"
    )


@pytest.mark.asyncio
async def test_merge_with_nested_dict_does_not_return_success_status() -> None:
    """When E_NESTED_DICT_IN_MERGE_PAYLOAD fires, status must not be 'success'."""
    result = await _write(
        _BASE_DOC,
        changes={"KEY": {"$op": "MERGE", "value": {"NESTED": {"deep": "dict"}}}},
    )
    errors = result.get("errors", [])
    has_error = any(e.get("code") == "E_NESTED_DICT_IN_MERGE_PAYLOAD" for e in errors)
    assert has_error
    # Status must not indicate success when a blocking error was raised
    status = result.get("status", "")
    assert status != "success", f"Expected non-success status when errors present, got: {status!r}"
