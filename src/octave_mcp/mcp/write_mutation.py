"""Op-dispatch and AST mutation primitives extracted from write.py as part of STRATEGY_S1 (#459/#466). Home of the v1.14.0 literal-zone form preservation fix (#460 Case A) when that work lands."""

from typing import Any

from octave_mcp.core.grammar.cst import (
    Assignment,
    ASTNode,
    Block,
    InlineMap,
    ListValue,
    LiteralZoneValue,
    Section,
)


def _is_delete_sentinel(value: Any) -> bool:
    """Check if value is the DELETE sentinel.

    Args:
        value: Value to check

    Returns:
        True if value is the DELETE sentinel
    """
    return isinstance(value, dict) and value.get("$op") == "DELETE"


# GH#373: Recognised op descriptors for op-aware nested mutation.
# Bare values (no $op) preserve PR #370 full-replacement semantics.
_KNOWN_OPS = frozenset({"APPEND", "PREPEND", "MERGE", "DELETE"})


def _is_op_descriptor(value: Any) -> bool:
    """GH#373: True iff value is a dict carrying a recognised "$op" key.

    Discriminates op descriptors from bare dict values (which are valid full
    replacements emitted as InlineMap). A dict without "$op" is bare data;
    a dict with "$op" is interpreted as an instruction and validated.
    """
    return isinstance(value, dict) and "$op" in value


def _extract_op_descriptor(value: Any) -> tuple[str | None, Any, dict[str, Any] | None]:
    """GH#373: Parse a changes-mode value into (op, payload, error).

    Returns:
        (op, payload, error) tuple where:
          - op: one of "APPEND" | "PREPEND" | "MERGE" | "DELETE" if the value
            is a recognised op descriptor; None for bare values (legacy
            full-replacement semantics).
          - payload: the descriptor's "value" field (for APPEND/PREPEND/MERGE),
            None for DELETE, or the bare value verbatim when op is None.
          - error: None on success; otherwise an error dict with code
            "E_INVALID_OP_DESCRIPTOR" describing the malformation.

    Validation rules:
      - Unknown $op string -> E_INVALID_OP_DESCRIPTOR.
      - APPEND / PREPEND / MERGE without "value" key -> E_INVALID_OP_DESCRIPTOR.
        (DELETE has no "value" by design.)
      - MERGE with non-dict "value" -> E_INVALID_OP_DESCRIPTOR.
    """
    if not _is_op_descriptor(value):
        return (None, value, None)

    op = value.get("$op")
    if not isinstance(op, str) or op not in _KNOWN_OPS:
        return (
            None,
            None,
            {
                "code": "E_INVALID_OP_DESCRIPTOR",
                "message": (
                    f"Invalid $op value {op!r}: expected one of "
                    f"{sorted(_KNOWN_OPS)}. Bare values (no $op) are "
                    f"interpreted as full replacement."
                ),
            },
        )

    if op == "DELETE":
        # DELETE has no payload; ignore any extra keys for forward-compat.
        return ("DELETE", None, None)

    if "value" not in value:
        return (
            None,
            None,
            {
                "code": "E_INVALID_OP_DESCRIPTOR",
                "message": (f"$op {op!r} descriptor is missing required 'value' field."),
            },
        )

    payload = value["value"]
    if op == "MERGE" and not isinstance(payload, dict):
        return (
            None,
            None,
            {
                "code": "E_INVALID_OP_DESCRIPTOR",
                "message": (
                    f"$op MERGE requires 'value' to be a dict (block contents); " f"got {type(payload).__name__}."
                ),
            },
        )

    return (op, payload, None)


def _mark_dirty(node: Any, *, body: bool = False) -> None:
    """ADR-0006 SR2-T2 PR-2 (GH#377): mark an AST node dirty for re-emit.

    Centralises the paired-write rule across every mutation site in
    ``_apply_changes`` (and friends). Splicing a node from baseline
    bytes when its Python-side value has been changed would emit stale
    bytes (I1 violation). Pairing every mutation with a call to this
    helper IS the structural enforcement of I3+I4.

    Args:
        node: The AST node whose value/children just mutated.
        body: When True AND the node is a Block/Section, set
            ``body_dirty`` instead of ``dirty``. The header bytes still
            splice from baseline; only the children region re-emits.

    No-op for value types (ListValue/InlineMap/HolographicValue/
    LiteralZoneValue) — those do not carry a dirty flag; their parent
    Assignment owns dirtiness (ADR §4 ¶4).
    """
    if body and isinstance(node, (Block, Section)):
        node.body_dirty = True
        return
    if isinstance(node, ASTNode):
        node.dirty = True


def _apply_array_op_inplace(assignment: Assignment, op: str, payload: Any) -> None:
    """GH#373: Apply APPEND or PREPEND to a list-valued Assignment in place.

    Caller is responsible for verifying target type via _resolve_target_type
    (validator already does this and rejects mismatches with E_OP_TARGET_MISMATCH).

    Semantics:
      - payload as a single element: push/unshift one element.
      - payload as a list: bulk push/unshift in caller order.
    Existing items keep their original tokens (where present); new items are
    appended as Python values, mirroring how _normalize_value_for_ast produces
    list contents.

    ADR-0006 SR2-T2 PR-2 (GH#377): the Assignment whose value was
    mutated is marked ``dirty=True`` via ``_mark_dirty`` so Strategy
    A's emitter (PR-3) re-emits the modified array rather than splicing
    stale baseline bytes.

    Args:
        assignment: The Assignment node holding a ListValue or list.
        op: "APPEND" or "PREPEND".
        payload: Element or list of elements to push.
    """
    new_items = list(payload) if isinstance(payload, list) else [payload]

    current = assignment.value
    if isinstance(current, ListValue):
        existing = list(current.items)
        # Drop tokens: bulk-edit invalidates the verbatim token slice. Re-emission
        # will use canonical form for the modified array's bytes (diff-locality
        # gap is documented in GH#371).
        if op == "APPEND":
            assignment.value = ListValue(items=existing + new_items)
        else:  # PREPEND
            assignment.value = ListValue(items=new_items + existing)
        _mark_dirty(assignment)
    elif isinstance(current, list):
        if op == "APPEND":
            assignment.value = ListValue(items=current + new_items)
        else:  # PREPEND
            assignment.value = ListValue(items=new_items + current)
        _mark_dirty(assignment)
    else:
        # Validator should prevent this; defensive raise for direct callers.
        raise ValueError(
            [
                {
                    "code": "E_OP_TARGET_MISMATCH",
                    "message": (f"$op {op} requires list-valued target; got " f"{type(current).__name__}."),
                }
            ]
        )


def _target_type_for_assignment(value: Any) -> str:
    """GH#373: Classify an Assignment's value for op/target-type validation.

    Returns one of: "array" | "scalar" | "map".
      - "array": ListValue or Python list.
      - "map":   InlineMap or Python dict (non-op-descriptor).
      - "scalar": everything else (str, int, bool, None, LiteralZoneValue, etc.).
    """
    if isinstance(value, ListValue | list):
        return "array"
    if isinstance(value, InlineMap) or (isinstance(value, dict) and not _is_op_descriptor(value)):
        return "map"
    return "scalar"


def _normalize_value_for_ast(value: Any) -> Any:
    """Normalize a Python value to an AST-compatible type.

    I1 (Syntactic Fidelity): Ensures values are properly typed for emission.

    Python lists must be wrapped in ListValue to emit correct OCTAVE syntax.
    Without this, str(list) produces "['a', 'b']" which is invalid OCTAVE.

    Python dicts must be wrapped in InlineMap to emit correct OCTAVE syntax.
    Without this, str(dict) produces "{'key': 'value'}" which is invalid OCTAVE.
    Issue #176: Nested dicts should produce valid OCTAVE like [key::value], not Python repr.

    Args:
        value: Python value from changes dict

    Returns:
        AST-compatible value (ListValue for lists, InlineMap for dicts, original for others)
    """
    # Issue #235 MP8: Literal zones must NOT be normalized (D3: zero processing).
    # Return unchanged to prevent content being wrapped or coerced.
    if isinstance(value, LiteralZoneValue):
        return value

    if isinstance(value, list):
        # Recursively normalize list items
        normalized_items = [_normalize_value_for_ast(item) for item in value]
        return ListValue(items=normalized_items)
    elif isinstance(value, dict):
        # Issue #176: Convert dicts to InlineMap to produce valid OCTAVE syntax
        # InlineMap emits as [key::value,key2::value2] which is valid OCTAVE
        # Without this, str(dict) produces "{'key': 'value'}" which is INVALID OCTAVE
        # Recursively normalize all values in the dict
        normalized_pairs = {k: _normalize_value_for_ast(v) for k, v in value.items()}
        return InlineMap(pairs=normalized_pairs)
    # Other types (str, int, bool, None, etc.) are handled by emit_value directly
    return value
