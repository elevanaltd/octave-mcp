"""GH#373: Op-aware nested mutation for changes-mode.

Extends the PR #370 AST walker with $op descriptor support:
  - APPEND   : push value(s) onto end of array target
  - PREPEND  : unshift value(s) onto front of array target
  - MERGE    : deep-merge dict into block target (unmentioned keys preserved)
  - DELETE   : remove key/element entirely (extends flat support to nested)
  - (no $op) : full-value replacement (current PR #370 behavior, MUST be unchanged)

I3 (Mirror Constraint): missing paths are rejected, NEVER auto-created.
I5 (Schema Sovereignty): op/target-type mismatches surface as visible error
codes (E_OP_TARGET_MISMATCH / E_INVALID_OP_DESCRIPTOR), NEVER silent coercion.

Validation centralised in _validate_change_paths so the fail-fast batch-rejection
invariant from PR #370 is preserved: if ANY descriptor in a batch is invalid,
NONE are applied.

TDD: RED phase - these tests define the expected behavior.
"""

import os
import tempfile

import pytest

_NAV_DOC = (
    "===NAV_TEST===\n"
    "META:\n"
    "  TYPE::TEST\n"
    "NAV:\n"
    "  FOUNDATIONAL::[A,B]\n"
    "  OPERATIONAL_CONVENTIONS::[SEARCH_PATH_CONVENTION]\n"
    "  INFRASTRUCTURE::[QR_REDIRECT_LAYER]\n"
    "===END===\n"
)


def _write_initial(tmpdir: str, content: str = _NAV_DOC) -> str:
    target_path = os.path.join(tmpdir, "test.oct.md")
    with open(target_path, "w") as f:
        f.write(content)
    return target_path


class TestOpAwareNestedAppend:
    """APPEND op on nested arrays."""

    @pytest.mark.asyncio
    async def test_append_single_element_to_nested_array(self):
        """APPEND with a single element pushes onto end of nested array."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = _write_initial(tmpdir)

            result = await tool.execute(
                target_path=target_path,
                changes={"NAV.OPERATIONAL_CONVENTIONS": {"$op": "APPEND", "value": "NEW_TOKEN"}},
            )

            assert result["status"] == "success", f"errors: {result.get('errors')}"
            with open(target_path) as f:
                final = f.read()
            assert "SEARCH_PATH_CONVENTION" in final
            assert "NEW_TOKEN" in final
            # Order: original first, appended after
            idx_orig = final.index("SEARCH_PATH_CONVENTION")
            idx_new = final.index("NEW_TOKEN")
            assert idx_orig < idx_new
            # I3: no flat duplicate created
            assert "NAV.OPERATIONAL_CONVENTIONS::" not in final

    @pytest.mark.asyncio
    async def test_append_list_of_elements_to_nested_array(self):
        """APPEND with a list value bulk-pushes elements in order."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = _write_initial(tmpdir)

            result = await tool.execute(
                target_path=target_path,
                changes={
                    "NAV.OPERATIONAL_CONVENTIONS": {
                        "$op": "APPEND",
                        "value": ["TOKEN_A", "TOKEN_B"],
                    }
                },
            )

            assert result["status"] == "success", f"errors: {result.get('errors')}"
            with open(target_path) as f:
                final = f.read()
            assert "TOKEN_A" in final
            assert "TOKEN_B" in final
            assert final.index("TOKEN_A") < final.index("TOKEN_B")

    @pytest.mark.asyncio
    async def test_append_to_top_level_array(self):
        """APPEND op works on top-level array assignments, not just nested."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = "===T===\nMETA:\n  TYPE::TEST\nTAGS::[X,Y]\n===END===\n"
            target_path = _write_initial(tmpdir, content)

            result = await tool.execute(
                target_path=target_path,
                changes={"TAGS": {"$op": "APPEND", "value": "Z"}},
            )

            assert result["status"] == "success", f"errors: {result.get('errors')}"
            with open(target_path) as f:
                final = f.read()
            assert "X" in final and "Y" in final and "Z" in final


class TestOpAwareNestedPrepend:
    """PREPEND op on nested arrays."""

    @pytest.mark.asyncio
    async def test_prepend_single_element_to_nested_array(self):
        """PREPEND with single element unshifts onto front."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = _write_initial(tmpdir)

            result = await tool.execute(
                target_path=target_path,
                changes={"NAV.OPERATIONAL_CONVENTIONS": {"$op": "PREPEND", "value": "FIRST"}},
            )

            assert result["status"] == "success", f"errors: {result.get('errors')}"
            with open(target_path) as f:
                final = f.read()
            # FIRST appears before SEARCH_PATH_CONVENTION inside the array
            assert "FIRST" in final
            assert final.index("FIRST") < final.index("SEARCH_PATH_CONVENTION")

    @pytest.mark.asyncio
    async def test_prepend_list_of_elements_preserves_order(self):
        """PREPEND with list preserves caller's order at the front of the array."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = _write_initial(tmpdir)

            result = await tool.execute(
                target_path=target_path,
                changes={
                    "NAV.OPERATIONAL_CONVENTIONS": {
                        "$op": "PREPEND",
                        "value": ["A1", "A2"],
                    }
                },
            )

            assert result["status"] == "success", f"errors: {result.get('errors')}"
            with open(target_path) as f:
                final = f.read()
            # A1, A2 in caller order, both before SEARCH_PATH_CONVENTION
            assert final.index("A1") < final.index("A2")
            assert final.index("A2") < final.index("SEARCH_PATH_CONVENTION")


class TestOpAwareNestedMerge:
    """MERGE op on nested blocks (and top-level blocks not named META)."""

    @pytest.mark.asyncio
    async def test_merge_into_top_level_nav_block_preserves_unmentioned_keys(self):
        """MERGE on a top-level Block (NAV) adds/updates only mentioned children;
        unmentioned children are preserved (extends GH#302 META MERGE invariant
        to nested blocks)."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = _write_initial(tmpdir)

            result = await tool.execute(
                target_path=target_path,
                changes={
                    "NAV": {
                        "$op": "MERGE",
                        "value": {"OPERATIONAL_CONVENTIONS": ["NEW"]},
                    }
                },
            )

            assert result["status"] == "success", f"errors: {result.get('errors')}"
            with open(target_path) as f:
                final = f.read()
            # FOUNDATIONAL and INFRASTRUCTURE unmentioned -> preserved
            assert "FOUNDATIONAL" in final
            assert "INFRASTRUCTURE" in final
            # OPERATIONAL_CONVENTIONS replaced with new value
            assert "NEW" in final
            assert "SEARCH_PATH_CONVENTION" not in final

    @pytest.mark.asyncio
    async def test_merge_with_inner_delete_removes_key(self):
        """MERGE value with {"$op": "DELETE"} on an inner key removes that key
        from the block, mirroring GH#302 META MERGE semantics."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = _write_initial(tmpdir)

            result = await tool.execute(
                target_path=target_path,
                changes={
                    "NAV": {
                        "$op": "MERGE",
                        "value": {"INFRASTRUCTURE": {"$op": "DELETE"}},
                    }
                },
            )

            assert result["status"] == "success", f"errors: {result.get('errors')}"
            with open(target_path) as f:
                final = f.read()
            assert "INFRASTRUCTURE" not in final
            assert "FOUNDATIONAL" in final
            assert "OPERATIONAL_CONVENTIONS" in final


class TestOpAwareNestedDelete:
    """DELETE op on nested targets (extending PR #370 nested DELETE coverage)."""

    @pytest.mark.asyncio
    async def test_delete_nested_block_child(self):
        """DELETE sentinel on PARENT.CHILD removes the child Assignment from
        the Block (already supported in PR #370; locking the behaviour)."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = _write_initial(tmpdir)

            result = await tool.execute(
                target_path=target_path,
                changes={"NAV.INFRASTRUCTURE": {"$op": "DELETE"}},
            )

            assert result["status"] == "success", f"errors: {result.get('errors')}"
            with open(target_path) as f:
                final = f.read()
            assert "INFRASTRUCTURE" not in final
            assert "FOUNDATIONAL" in final


class TestOpTargetMismatchErrors:
    """I5: op/target-type mismatches must produce visible error codes."""

    @pytest.mark.asyncio
    async def test_append_on_scalar_target_rejected(self):
        """APPEND on a scalar (non-list) target -> E_OP_TARGET_MISMATCH."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = "===T===\nMETA:\n  TYPE::TEST\nNAV:\n  COUNT::3\n===END===\n"
            target_path = _write_initial(tmpdir, content)

            result = await tool.execute(
                target_path=target_path,
                changes={"NAV.COUNT": {"$op": "APPEND", "value": 1}},
            )

            assert result["status"] == "error"
            codes = {e.get("code") for e in result.get("errors", [])}
            assert "E_OP_TARGET_MISMATCH" in codes, f"got: {result.get('errors')}"

    @pytest.mark.asyncio
    async def test_prepend_on_scalar_target_rejected(self):
        """PREPEND on a scalar -> E_OP_TARGET_MISMATCH."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = '===T===\nMETA:\n  TYPE::TEST\nVERSION::"1.0"\n===END===\n'
            target_path = _write_initial(tmpdir, content)

            result = await tool.execute(
                target_path=target_path,
                changes={"VERSION": {"$op": "PREPEND", "value": "X"}},
            )

            assert result["status"] == "error"
            codes = {e.get("code") for e in result.get("errors", [])}
            assert "E_OP_TARGET_MISMATCH" in codes, f"got: {result.get('errors')}"

    @pytest.mark.asyncio
    async def test_merge_on_scalar_target_rejected(self):
        """MERGE on a non-block target -> E_OP_TARGET_MISMATCH."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            content = '===T===\nMETA:\n  TYPE::TEST\nVERSION::"1.0"\n===END===\n'
            target_path = _write_initial(tmpdir, content)

            result = await tool.execute(
                target_path=target_path,
                changes={"VERSION": {"$op": "MERGE", "value": {"X": 1}}},
            )

            assert result["status"] == "error"
            codes = {e.get("code") for e in result.get("errors", [])}
            assert "E_OP_TARGET_MISMATCH" in codes, f"got: {result.get('errors')}"

    @pytest.mark.asyncio
    async def test_merge_on_array_target_rejected(self):
        """MERGE on a list target -> E_OP_TARGET_MISMATCH."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = _write_initial(tmpdir)

            result = await tool.execute(
                target_path=target_path,
                changes={"NAV.OPERATIONAL_CONVENTIONS": {"$op": "MERGE", "value": {"K": 1}}},
            )

            assert result["status"] == "error"
            codes = {e.get("code") for e in result.get("errors", [])}
            assert "E_OP_TARGET_MISMATCH" in codes, f"got: {result.get('errors')}"


class TestOpMissingPathRejected:
    """I3: APPEND/PREPEND/MERGE on missing paths must reject (no auto-create)."""

    @pytest.mark.asyncio
    async def test_append_on_missing_nested_path_rejected(self):
        """APPEND on a missing nested path -> E_UNRESOLVABLE_PATH (no auto-create)."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = _write_initial(tmpdir)

            result = await tool.execute(
                target_path=target_path,
                changes={"NAV.NONEXISTENT": {"$op": "APPEND", "value": "X"}},
            )

            assert result["status"] == "error"
            codes = {e.get("code") for e in result.get("errors", [])}
            assert "E_UNRESOLVABLE_PATH" in codes, f"got: {result.get('errors')}"

    @pytest.mark.asyncio
    async def test_merge_on_missing_block_rejected(self):
        """MERGE on a missing block path -> E_UNRESOLVABLE_PATH (no auto-create)."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = _write_initial(tmpdir)

            result = await tool.execute(
                target_path=target_path,
                changes={"NO_SUCH_BLOCK": {"$op": "MERGE", "value": {"X": 1}}},
            )

            assert result["status"] == "error"
            codes = {e.get("code") for e in result.get("errors", [])}
            assert "E_UNRESOLVABLE_PATH" in codes, f"got: {result.get('errors')}"


class TestInvalidDescriptorErrors:
    """Malformed descriptors must produce E_INVALID_OP_DESCRIPTOR."""

    @pytest.mark.asyncio
    async def test_unknown_op_rejected(self):
        """Descriptor with unrecognised $op value -> E_INVALID_OP_DESCRIPTOR."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = _write_initial(tmpdir)

            result = await tool.execute(
                target_path=target_path,
                changes={"NAV.OPERATIONAL_CONVENTIONS": {"$op": "FROBNICATE", "value": "X"}},
            )

            assert result["status"] == "error"
            codes = {e.get("code") for e in result.get("errors", [])}
            assert "E_INVALID_OP_DESCRIPTOR" in codes, f"got: {result.get('errors')}"

    @pytest.mark.asyncio
    async def test_append_missing_value_rejected(self):
        """APPEND descriptor without 'value' field -> E_INVALID_OP_DESCRIPTOR."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = _write_initial(tmpdir)

            result = await tool.execute(
                target_path=target_path,
                changes={"NAV.OPERATIONAL_CONVENTIONS": {"$op": "APPEND"}},
            )

            assert result["status"] == "error"
            codes = {e.get("code") for e in result.get("errors", [])}
            assert "E_INVALID_OP_DESCRIPTOR" in codes, f"got: {result.get('errors')}"

    @pytest.mark.asyncio
    async def test_merge_value_not_dict_rejected(self):
        """MERGE descriptor with non-dict 'value' -> E_INVALID_OP_DESCRIPTOR."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = _write_initial(tmpdir)

            result = await tool.execute(
                target_path=target_path,
                changes={"NAV": {"$op": "MERGE", "value": "not_a_dict"}},
            )

            assert result["status"] == "error"
            codes = {e.get("code") for e in result.get("errors", [])}
            assert "E_INVALID_OP_DESCRIPTOR" in codes, f"got: {result.get('errors')}"


class TestBatchAtomicity:
    """Fail-fast: invalid descriptor in a batch rejects the entire batch."""

    @pytest.mark.asyncio
    async def test_one_invalid_descriptor_rejects_entire_batch(self):
        """If ANY descriptor is invalid, NONE of the changes are applied
        (preserves PR #370 batch-rejection invariant)."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = _write_initial(tmpdir)

            result = await tool.execute(
                target_path=target_path,
                changes={
                    "NAV.OPERATIONAL_CONVENTIONS": {"$op": "APPEND", "value": "OK"},
                    "NAV.FOUNDATIONAL": {"$op": "FROBNICATE", "value": "X"},
                },
            )

            assert result["status"] == "error"
            with open(target_path) as f:
                after = f.read()
            # File untouched (or at most identical canonical re-write; OK must
            # NOT have leaked through since the batch was rejected).
            assert "OK" not in after, "Partial application leaked despite batch rejection"


class TestBackwardCompatibility:
    """Bare-value writes MUST keep PR #370 behaviour exactly."""

    @pytest.mark.asyncio
    async def test_bare_value_full_replacement_unchanged(self):
        """Bare value (no $op) still triggers full-value replacement."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = _write_initial(tmpdir)

            result = await tool.execute(
                target_path=target_path,
                changes={"NAV.OPERATIONAL_CONVENTIONS": ["A", "B", "C"]},
            )

            assert result["status"] == "success", f"errors: {result.get('errors')}"
            with open(target_path) as f:
                final = f.read()
            assert "A" in final and "B" in final and "C" in final
            # Original token replaced (not appended)
            assert "SEARCH_PATH_CONVENTION" not in final

    @pytest.mark.asyncio
    async def test_bare_delete_sentinel_still_works(self):
        """The bare {"$op": "DELETE"} sentinel still removes targets."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = _write_initial(tmpdir)

            result = await tool.execute(
                target_path=target_path,
                changes={"NAV.OPERATIONAL_CONVENTIONS": {"$op": "DELETE"}},
            )

            assert result["status"] == "success", f"errors: {result.get('errors')}"
            with open(target_path) as f:
                final = f.read()
            assert "OPERATIONAL_CONVENTIONS" not in final
