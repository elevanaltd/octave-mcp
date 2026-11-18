"""R2 -- E_FIDELITY refusals per loss class (tool-fidelity slice 1, PR-2).

Governing records: OCTAVE-MCP-DIRECTION-CONTAINER-RECEIPTS-PITH-20261110
(field ``write_rule``) and OCTAVE-MCP-DIRECTION-RULINGS-AMENDMENT-20261117
("meaning exact is right"). Build plan: tool-fidelity slice 1, sections 3
(F1, C1, C2, F2), 4 (E_FIDELITY, fidelity_violations[]) and 5 R2.

The write rule is exact in MEANING, not byte-exact: logged syntax-only
normalization is allowed (see test_write_fidelity_lenient_allowed.py), and
anything that drops or alters content is refused with ``E_FIDELITY``. Every
refusal test asserts that the target file is untouched, so the guard is shown
to fire rather than merely to exist.

Out of scope here (PR-3): ``bytes_changed`` (F3) and the changes-mode
preserve default.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from octave_mcp.mcp.write import WriteTool

_TOOL = WriteTool()

_VIOLATION_KEYS = {"kind", "line", "expected", "found", "hint"}


async def _run(path: Path, **kwargs: Any) -> dict[str, Any]:
    return await _TOOL.execute(target_path=str(path), **kwargs)


def _snapshot(path: Path) -> bytes | None:
    return path.read_bytes() if path.exists() else None


def _assert_refused(result: dict[str, Any], path: Path, before: bytes | None, kind: str | None = None) -> None:
    """The write is refused with E_FIDELITY, carries well-formed violations,
    and the target file is byte-for-byte unchanged (or still absent)."""
    assert result["status"] == "error", result
    codes = [e["code"] for e in result["errors"]]
    assert "E_FIDELITY" in codes, codes
    violations = result.get("fidelity_violations")
    assert violations, "an E_FIDELITY refusal must carry fidelity_violations in full"
    for v in violations:
        assert _VIOLATION_KEYS <= set(v), v
    if kind is not None:
        kinds = {v["kind"] for v in violations}
        assert kind in kinds, f"expected kind {kind!r}, got {kinds}"
    assert _snapshot(path) == before, "a refused write must leave the target untouched"


def _violation_text(result: dict[str, Any]) -> str:
    return " ".join(f"{v['expected']} {v['found']}" for v in result["fidelity_violations"])


# ---------------------------------------------------------------------------
# Content mode: parser-side losses (#533, #534, #535) and the loss codes
# ---------------------------------------------------------------------------

_REPRO_533 = """===REPRO_A===
META:
  TYPE::SPEC
  VERSION::"1.0.0"
§1::STRUCTURE
  SEQUENCE::===NAME===[META,§1::BODY,===END===]
  AFTER::"this key must survive"
§2::TAIL
  LAST::"so must this section"
===END===
"""

_REPRO_534 = """===REPRO_B===
META:
  TYPE::SPEC
  VERSION::"1.0.0"
§1::RULES
  §1a::SYNTAX
    FORMAT::SYMBOL::meaning
    EXAMPLE::⊕::synthesis, →::transform
  §1b::VALIDATE
    REQUIRED::[valid_OCTAVE,preserve_names_verbatim]
===END===
"""

_REPRO_535 = """===R===
META:
  TYPE::SPEC
  VERSION::"1.0.0"
REQUIRED::[valid_OCTAVE,preserve_§_names_verbatim]
===END===
"""

_BARE_LINE = """===D===
META:
  TYPE::T
  VERSION::"1"
§1::BODY
  KEY::value
  this bare line is dropped by the parser
===END===
"""

_NUMERIC_KEY = """===D===
META:
  TYPE::T
  VERSION::"1"
BLOCK:
  1::"first value"
  K::v
===END===
"""

_META_DUPLICATE_KEY = """===D===
META:
  TYPE::FIRST
  TYPE::SECOND
  VERSION::"1"
K::v
===END===
"""

_META_COMMENT = """===D===
META:
  TYPE::T // why this type
  VERSION::"1"
K::v
===END===
"""

# A fenced block with no owning ``KEY::`` is dropped by the parser with no
# correction and no warning (found by the SR1-T4 no-op suite during PR-2).
_ORPHAN_FENCE = """===D===
META:
  TYPE::T
  VERSION::"1"
§1::BODY
DESCRIPTION::"a fenced block follows"

```python
def f(x):
    return x + 1
```

===END===
"""

_QUOTED_FLOW = """===REPRO_DEQUOTE===
META:
  TYPE::LLM_PROFILE
  VERSION::"1.0.0"
FLOW::"A→B"
===END===
"""


class TestContentModeLoss:
    async def test_533_end_marker_in_brackets_names_the_dropped_content(self, tmp_path: Path) -> None:
        path = tmp_path / "a.oct.md"
        result = await _run(path, content=_REPRO_533)
        _assert_refused(result, path, None, "content_loss")
        text = _violation_text(result)
        assert "AFTER" in text
        assert "§2" in text or "TAIL" in text

    async def test_534_chained_assignment_names_the_dropped_words(self, tmp_path: Path) -> None:
        path = tmp_path / "b.oct.md"
        result = await _run(path, content=_REPRO_534)
        _assert_refused(result, path, None, "content_loss")
        assert "meaning" in _violation_text(result)

    async def test_535_section_sign_in_list_element(self, tmp_path: Path) -> None:
        path = tmp_path / "c.oct.md"
        result = await _run(path, content=_REPRO_535)
        _assert_refused(result, path, None)
        kinds = {v["kind"] for v in result["fidelity_violations"]}
        assert kinds & {"content_loss", "content_added"}

    @pytest.mark.parametrize(
        "content",
        [
            pytest.param(_BARE_LINE, id="bare_line_dropped"),
            pytest.param(_NUMERIC_KEY, id="numeric_key_dropped"),
            pytest.param(_META_DUPLICATE_KEY, id="meta_duplicate_key"),
            pytest.param(_META_COMMENT, id="meta_comment_511"),
            pytest.param(_ORPHAN_FENCE, id="orphan_fence_block"),
        ],
    )
    async def test_loss_codes_are_refused(self, tmp_path: Path, content: str) -> None:
        path = tmp_path / "loss.oct.md"
        result = await _run(path, content=content)
        _assert_refused(result, path, None, "content_loss")

    async def test_refusal_keeps_data_loss_warnings_visible(self, tmp_path: Path) -> None:
        """GH#349 (I4): the refusal envelope still carries the data-loss
        corrections and their top-level warnings, so a caller sees what the
        parser would have dropped as well as why the write was refused."""
        path = tmp_path / "w.oct.md"
        result = await _run(path, content=_BARE_LINE, lenient=True)
        _assert_refused(result, path, None, "content_loss")
        assert "W_BARE_LINE_DROPPED" in [c["code"] for c in result["corrections"]]
        assert "W_BARE_LINE_DROPPED" in [w["code"] for w in result["warnings"]]

    async def test_overwrite_refusal_leaves_existing_file_untouched(self, tmp_path: Path) -> None:
        path = tmp_path / "existing.oct.md"
        path.write_text('===D===\nMETA:\n  TYPE::T\n  VERSION::"1"\nK::v\n===END===\n', encoding="utf-8")
        before = _snapshot(path)
        result = await _run(path, content=_BARE_LINE)
        _assert_refused(result, path, before, "content_loss")

    async def test_510_quoted_flow_is_not_a_fixed_point(self, tmp_path: Path) -> None:
        path = tmp_path / "d.oct.md"
        result = await _run(path, content=_QUOTED_FLOW)
        _assert_refused(result, path, None, "not_fixed_point")

    async def test_dry_run_returns_the_same_refusal(self, tmp_path: Path) -> None:
        path = tmp_path / "e.oct.md"
        wet = await _run(path, content=_REPRO_533)
        dry = await _run(path, content=_REPRO_533, dry_run=True)
        _assert_refused(dry, path, None, "content_loss")
        assert dry["fidelity_violations"] == wet["fidelity_violations"]

    async def test_normalize_mode_refuses_lossy_file(self, tmp_path: Path) -> None:
        path = tmp_path / "n.oct.md"
        path.write_text(_BARE_LINE, encoding="utf-8")
        before = _snapshot(path)
        result = await _run(path)
        _assert_refused(result, path, before, "content_loss")

    async def test_summary_receipt_keeps_violations_in_full(self, tmp_path: Path) -> None:
        path = tmp_path / "s.oct.md"
        full = await _run(path, content=_BARE_LINE)
        summary = await _run(path, content=_BARE_LINE, receipt="summary")
        assert summary == full


# ---------------------------------------------------------------------------
# F1 comparator: meaning changes the lexical keys must see (CE finding 3)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Evidence completeness under the display cap (CE BLOCKED at 49d2e1f)
# ---------------------------------------------------------------------------

_MANY = 25


def _many_losses_then(tail: str) -> str:
    """A body with _MANY separate bare-line losses, then ``tail``."""
    body = "".join(f"B{i}:\n  K::v\n  lost words {i}\n" for i in range(_MANY))
    return '===D===\nMETA:\n  TYPE::T\n  VERSION::"1"\n' + body + tail + "===END===\n"


class TestViolationCapKeepsEveryClass:
    """The refusal may show at most 20 violations, but more than 20 findings
    of one class must not hide a later class, and the counts are complete."""

    def test_comparator_reports_a_later_class_after_many_of_another(self) -> None:
        """The CE counterexample: 25 separate deletions, then one addition."""
        from octave_mcp.mcp.write_fidelity import lexical_violations

        # C::kept separates the last deletion from the addition, so the
        # addition is a pure insert (adjacent, the pair is one replacement).
        reference = "===D===\n" + "".join(f"A{i}::kept\nB{i}::lost\n" for i in range(_MANY)) + "C::kept\n===END===\n"
        output = "===D===\n" + "".join(f"A{i}::kept\n" for i in range(_MANY)) + "C::kept\nZ::added\n===END===\n"
        kinds = [v["kind"] for v in lexical_violations(reference, output)]
        assert kinds.count("content_loss") == _MANY
        assert "content_added" in kinds

    async def test_refusal_shows_every_class_and_complete_counts(self, tmp_path: Path) -> None:
        """End to end: F1 finds _MANY content_loss, F2 then finds a
        not_fixed_point (#510); both classes are in the refusal."""
        path = tmp_path / "many.oct.md"
        result = await _run(path, content=_many_losses_then('FLOW::"A→B"\n'))
        _assert_refused(result, path, None)
        shown = result["fidelity_violations"]
        assert len(shown) <= 20
        assert {v["kind"] for v in shown} == {"content_loss", "not_fixed_point"}
        counts = result["fidelity_violation_counts"]
        assert counts["content_loss"] == _MANY and counts["not_fixed_point"] >= 1
        assert sum(counts.values()) > len(shown)
        assert result["fidelity_violations_truncated"] is True
        message = result["errors"][0]["message"]
        assert "content_loss" in message and "not_fixed_point" in message
        assert str(sum(counts.values())) in message

    async def test_summary_receipt_keeps_the_counts(self, tmp_path: Path) -> None:
        path = tmp_path / "many_s.oct.md"
        content = _many_losses_then('FLOW::"A→B"\n')
        full = await _run(path, content=content)
        summary = await _run(path, content=content, receipt="summary")
        assert summary == full
        assert summary["fidelity_violation_counts"] == full["fidelity_violation_counts"]

    async def test_untruncated_refusal_has_exact_counts(self, tmp_path: Path) -> None:
        path = tmp_path / "one.oct.md"
        result = await _run(path, content=_BARE_LINE)
        _assert_refused(result, path, None, "content_loss")
        assert result["fidelity_violation_counts"] == {"content_loss": len(result["fidelity_violations"])}
        assert result["fidelity_violations_truncated"] is False

    def test_display_cap_reserves_one_witness_per_class(self) -> None:
        """The cap applies once, at display, wherever the findings came from
        (F1, F2, C1, C2): each detected class keeps its first witness."""
        from octave_mcp.mcp.write_fidelity import cap_violations, violation

        found = (
            [violation("content_loss", i, f"x{i}", "") for i in range(30)]
            + [violation("declared_change_mismatch", 99, "a", "b")]
            + [violation("not_fixed_point", 100, "c", "d")]
            + [violation("content_added", 101, "", "e")]
        )
        shown, counts, truncated = cap_violations(found)
        assert len(shown) == 20 and truncated is True
        assert {v["kind"] for v in shown} == {
            "content_loss",
            "declared_change_mismatch",
            "not_fixed_point",
            "content_added",
        }
        assert counts == {"content_loss": 30, "declared_change_mismatch": 1, "not_fixed_point": 1, "content_added": 1}
        # First 17 losses fill the cap after the three other kinds' first
        # witnesses are reserved; detection order is kept.
        assert shown == found[:17] + found[30:]

    def test_display_cap_contract_when_kinds_exceed_the_limit(self) -> None:
        """Contract: at most max(limit, number of detected kinds) entries;
        one witness per kind always wins over the limit."""
        from octave_mcp.mcp.write_fidelity import cap_violations, violation

        kinds = ["content_loss", "content_added", "not_fixed_point", "declared_change_mismatch"]
        found = [violation(k, n, "x", "y") for n, k in enumerate(kinds)] * 2
        shown, counts, truncated = cap_violations(found, limit=2)
        assert [v["kind"] for v in shown] == kinds
        assert len(shown) == max(2, len(kinds)) and truncated is True
        assert counts == dict.fromkeys(kinds, 2)


class TestLexicalComparator:
    @pytest.mark.parametrize(
        ("reference", "output"),
        [
            pytest.param("===D===\nK::true\n===END===\n", "===D===\nK::false\n===END===\n", id="bool_value"),
            pytest.param('===D===\nK::"a  b"\n===END===\n', '===D===\nK::"a b"\n===END===\n', id="quoted_spaces"),
            pytest.param("===D===\nL::[a b, c]\n===END===\n", "===D===\nL::[a,b,c]\n===END===\n", id="list_boundary"),
            pytest.param("===D===\nK::1\n===END===\n", "===D===\nK::2\n===END===\n", id="number_value"),
            pytest.param("===D===\n// keep me\nK::v\n===END===\n", "===D===\nK::v\n===END===\n", id="comment_dropped"),
            pytest.param("===D===\nK::v\n===END===\n", "===D===\nK::v\nX::w\n===END===\n", id="content_added"),
            pytest.param(
                "===D===\nL::[preserve_§_names]\n===END===\n",
                '===D===\nL::[preserve_,"§_names"]\n===END===\n',
                id="regroup_must_keep_every_character",
            ),
            pytest.param(
                "===D===\nN::A[x y]\n===END===\n",
                "===D===\nN::A<xy>\n===END===\n",
                id="constructor_word_join",
            ),
            # E2 must not regroup across a list boundary: these change the
            # item count or turn a list into a string (estate R5 follow-up).
            pytest.param(
                "===D===\nL::[a, b]\n===END===\n", '===D===\nL::["a, b"]\n===END===\n', id="regroup_across_comma"
            ),
            pytest.param(
                "===D===\nL::[x]\n===END===\n", '===D===\nL::"[x]"\n===END===\n', id="regroup_across_brackets"
            ),
            # E6 (line break as list separator) must not hide a dropped,
            # altered, joined or re-split item.
            pytest.param(
                "===D===\nL::[\n  x\n  y\n  z\n]\n===END===\n",
                "===D===\nL::[x,z]\n===END===\n",
                id="multiline_item_dropped",
            ),
            pytest.param(
                "===D===\nL::[\n  x\n  y\n]\n===END===\n",
                "===D===\nL::[x,w]\n===END===\n",
                id="multiline_item_altered",
            ),
            pytest.param(
                "===D===\nL::[\n  x\n  y\n]\n===END===\n",
                '===D===\nL::["x y"]\n===END===\n',
                id="multiline_items_joined",
            ),
            pytest.param(
                "===D===\nL::[\n  x y\n  z\n]\n===END===\n",
                '===D===\nL::[x,"y z"]\n===END===\n',
                id="multiline_boundary_moved",
            ),
        ],
    )
    def test_meaning_change_is_a_violation(self, reference: str, output: str) -> None:
        from octave_mcp.mcp.write_fidelity import lexical_violations

        violations = lexical_violations(reference, output)
        assert violations, f"meaning change not detected: {reference!r} -> {output!r}"
        assert {v["kind"] for v in violations} <= {"content_loss", "content_added"}


# ---------------------------------------------------------------------------
# Changes mode: C1 (baseline round-trips before edit)
# ---------------------------------------------------------------------------

_CHANGES_BASELINE_BARE_IN_ONE = """===D===
META:
  TYPE::T
  VERSION::"1"
§1::ONE
  A::x
  this bare line is dropped by the parser
§2::TWO
  C::z
===END===
"""

_CHANGES_BASELINE_BARE_IN_TWO = """===D===
META:
  TYPE::T
  VERSION::"1"
§1::ONE
  A::x
§2::TWO
  C::z
  this bare line sits in a clean node
§3::THREE
  D::w
===END===
"""

# The bare line sits in the LAST node. The parser does not extend the last
# node's span to ===END===, so the line lies in the final gap, which today's
# preserve emitter does not carry (PR-3 fixes the emitter and keeps it).
_CHANGES_BASELINE_BARE_IN_FINAL_GAP = """===D===
META:
  TYPE::T
  VERSION::"1"
§1::ONE
  A::x
§2::TWO
  C::z
  this bare line sits in the final gap
===END===
"""


class TestChangesModeC1:
    @pytest.mark.parametrize("format_style", [None, "preserve"])
    async def test_bare_line_in_dirty_node_editing_another_key(self, tmp_path: Path, format_style: str | None) -> None:
        path = tmp_path / "c1.oct.md"
        path.write_text(_CHANGES_BASELINE_BARE_IN_ONE, encoding="utf-8")
        before = _snapshot(path)
        kwargs: dict[str, Any] = {"changes": {"§1.A": "new"}}
        if format_style is not None:
            kwargs["format_style"] = format_style
        result = await _run(path, **kwargs)
        _assert_refused(result, path, before, "content_loss")

    async def test_bare_line_in_clean_node_survives_byte_for_byte_under_preserve(self, tmp_path: Path) -> None:
        path = tmp_path / "c1clean.oct.md"
        path.write_text(_CHANGES_BASELINE_BARE_IN_TWO, encoding="utf-8")
        result = await _run(path, changes={"§1.A": "new"}, format_style="preserve")
        assert result["status"] == "success", result
        written = path.read_text(encoding="utf-8")
        assert "  this bare line sits in a clean node\n" in written
        assert "A::new" in written

    async def test_bare_line_in_final_gap_is_refused_under_preserve(self, tmp_path: Path) -> None:
        """C1 round-trips the baseline through the same emit path before the
        edit, so bytes the preserve emitter would drop outside any node span
        are refused as real loss rather than written silently."""
        path = tmp_path / "c1gap.oct.md"
        path.write_text(_CHANGES_BASELINE_BARE_IN_FINAL_GAP, encoding="utf-8")
        before = _snapshot(path)
        result = await _run(path, changes={"§1.A": "new"}, format_style="preserve")
        _assert_refused(result, path, before, "content_loss")

    async def test_bare_line_in_clean_node_is_refused_under_canonical_reemit(self, tmp_path: Path) -> None:
        """Canonical re-emit rewrites every node, so the clean node's bare line
        would be lost: that is real loss, refused (PR-3 makes preserve the
        changes-mode default)."""
        path = tmp_path / "c1canon.oct.md"
        path.write_text(_CHANGES_BASELINE_BARE_IN_TWO, encoding="utf-8")
        before = _snapshot(path)
        result = await _run(path, changes={"§1.A": "new"})
        _assert_refused(result, path, before, "content_loss")


# ---------------------------------------------------------------------------
# Changes mode: C2 (only the declared changes changed)
# ---------------------------------------------------------------------------

_C2_BASELINE = """===D===
META:
  TYPE::T
  VERSION::"1"
CONFIG:
  A::one
  B::two
  C::three
LIST::[x,y]
§1::ONE
  K::v
===END===
"""


def _c2_output(
    *,
    meta: str = '  TYPE::T\n  VERSION::"1"\n',
    config: str = "  A::one\n  B::two\n  C::three\n",
    lst: str = "[x,y]",
    section: str = "  K::v\n",
) -> str:
    return f"===D===\nMETA:\n{meta}CONFIG:\n{config}LIST::{lst}\n§1::ONE\n{section}===END===\n"


def _declared(changes: dict[str, Any], output: str) -> list[dict[str, Any]]:
    from octave_mcp.mcp.write_fidelity import declared_change_violations

    return declared_change_violations(_TOOL, _C2_BASELINE, output, changes)


class TestChangesModeC2Comparator:
    """C2 at the comparator: a crafted output stands in for an emitter or
    mutator defect, so each declared-change rule is exercised directly."""

    def test_correct_outputs_have_no_violation(self) -> None:
        assert _declared({"CONFIG.A": "uno"}, _c2_output(config="  A::uno\n  B::two\n  C::three\n")) == []
        assert _declared({"LIST": {"$op": "APPEND", "value": "z"}}, _c2_output(lst="[x,y,z]")) == []
        assert _declared({"LIST": {"$op": "PREPEND", "value": "w"}}, _c2_output(lst="[w,x,y]")) == []
        assert _declared({"CONFIG.B": {"$op": "DELETE"}}, _c2_output(config="  A::one\n  C::three\n")) == []

    def test_sibling_loss_inside_dirty_parent(self) -> None:
        """CE finding 4: the mask exempts only the declared target."""
        violations = _declared({"CONFIG.A": "uno"}, _c2_output(config="  A::uno\n  B::two\n"))
        assert {v["kind"] for v in violations} == {"declared_change_mismatch"}

    @pytest.mark.parametrize(
        ("changes", "output"),
        [
            pytest.param({"CONFIG.A": "uno"}, _c2_output(config="  A::wrong\n  B::two\n  C::three\n"), id="set"),
            pytest.param({"CONFIG.B": {"$op": "DELETE"}}, _c2_output(), id="delete_still_present"),
            pytest.param({"LIST": {"$op": "APPEND", "value": "z"}}, _c2_output(lst="[x,y]"), id="append_missing"),
            pytest.param({"LIST": {"$op": "APPEND", "value": "z"}}, _c2_output(lst="[z,x,y]"), id="append_wrong_end"),
            pytest.param({"LIST": {"$op": "PREPEND", "value": "w"}}, _c2_output(lst="[x,y,w]"), id="prepend_wrong_end"),
            pytest.param(
                {"CONFIG": {"$op": "MERGE", "value": {"A": "uno"}}},
                _c2_output(config="  A::one\n  B::two\n  C::three\n"),
                id="merge_value_not_landed",
            ),
            pytest.param(
                {"META.STATUS": "ACTIVE"},
                _c2_output(meta='  TYPE::T\n  VERSION::"1"\n  STATUS::DRAFT\n'),
                id="meta_value_not_landed",
            ),
        ],
    )
    def test_declared_value_not_what_lands(self, changes: dict[str, Any], output: str) -> None:
        violations = _declared(changes, output)
        assert {v["kind"] for v in violations} == {"declared_change_mismatch"}

    def test_merge_unmentioned_child_lost_is_caught(self) -> None:
        """CE round 4 finding 1: MERGE masks only the named children."""
        changes = {"CONFIG": {"$op": "MERGE", "value": {"A": "uno"}}}
        assert _declared(changes, _c2_output(config="  A::uno\n  B::two\n  C::three\n")) == []
        violations = _declared(changes, _c2_output(config="  A::uno\n  B::two\n"))
        assert {v["kind"] for v in violations} == {"declared_change_mismatch"}

    def test_merge_new_child_alongside_unmentioned_children(self) -> None:
        changes = {"CONFIG": {"$op": "MERGE", "value": {"D": "four"}}}
        assert _declared(changes, _c2_output(config="  A::one\n  B::two\n  C::three\n  D::four\n")) == []
        lost = _declared(changes, _c2_output(config="  A::one\n  C::three\n  D::four\n"))
        assert {v["kind"] for v in lost} == {"declared_change_mismatch"}

    def test_merge_child_delete_must_be_absent(self) -> None:
        """CE round 5: a named child carrying $op:DELETE must be absent from P1."""
        changes = {"CONFIG": {"$op": "MERGE", "value": {"B": {"$op": "DELETE"}}}}
        assert _declared(changes, _c2_output(config="  A::one\n  C::three\n")) == []
        still_there = _declared(changes, _c2_output())
        assert {v["kind"] for v in still_there} == {"declared_change_mismatch"}

    def test_meta_slot_mask_is_per_key(self) -> None:
        """CE round 4 finding 4: META is masked by key slot, so a sibling META
        change is caught while the declared slot is exempt."""
        changes = {"META.STATUS": "ACTIVE"}
        ok = _c2_output(meta='  TYPE::T\n  VERSION::"1"\n  STATUS::ACTIVE\n')
        assert _declared(changes, ok) == []
        sibling_changed = _c2_output(meta='  TYPE::T\n  VERSION::"2"\n  STATUS::ACTIVE\n')
        assert {v["kind"] for v in _declared(changes, sibling_changed)} == {"declared_change_mismatch"}
        sibling_lost = _c2_output(meta="  TYPE::T\n  STATUS::ACTIVE\n")
        assert {v["kind"] for v in _declared(changes, sibling_lost)} == {"declared_change_mismatch"}

    def test_created_path_outside_the_permitted_operations(self) -> None:
        violations = _declared({"§1.NEW_KEY": "v"}, _c2_output(section="  K::v\n  NEW_KEY::v\n"))
        assert [v["kind"] for v in violations] == ["declared_change_mismatch"]
        assert "created" in violations[0]["hint"]


class TestChangesModeC2EndToEnd:
    async def _baseline(self, tmp_path: Path) -> Path:
        path = tmp_path / "c2.oct.md"
        path.write_text(_C2_BASELINE, encoding="utf-8")
        return path

    @pytest.mark.parametrize(
        "changes",
        [
            pytest.param({"§1.NEW_KEY": "v"}, id="section_child_517"),
            pytest.param({"NEW_TOP": "v"}, id="top_level_key"),
        ],
    )
    async def test_517_auto_create_is_refused_as_created(self, tmp_path: Path, changes: dict[str, Any]) -> None:
        path = await self._baseline(tmp_path)
        before = _snapshot(path)
        result = await _run(path, changes=changes)
        _assert_refused(result, path, before, "declared_change_mismatch")
        assert any("created" in v["hint"] for v in result["fidelity_violations"])

    @pytest.mark.parametrize(
        ("changes", "expect_in_file"),
        [
            pytest.param({"META.NEW_FIELD": "added"}, "NEW_FIELD::added", id="meta_new_field"),
            pytest.param({"CONFIG": {"$op": "MERGE", "value": {"D": "four"}}}, "  D::four", id="merge_new_child"),
            pytest.param({"LIST": {"$op": "APPEND", "value": "z"}}, "  z\n", id="append_spanless_list"),
        ],
    )
    async def test_permitted_additions_succeed(
        self, tmp_path: Path, changes: dict[str, Any], expect_in_file: str
    ) -> None:
        """CE round 4 finding 2: the three supported additions are not #517."""
        from octave_mcp.core.parser import parse

        path = await self._baseline(tmp_path)
        result = await _run(path, changes=changes)
        assert result["status"] == "success", result
        written = path.read_text(encoding="utf-8")
        assert expect_in_file in written
        for survivor in ("A::one", "B::two", "C::three", "K::v"):
            assert survivor in written
        lists = [s.value.items for s in parse(written).sections if getattr(s, "key", None) == "LIST"]
        assert lists and lists[0][:2] == ["x", "y"]

    async def test_merge_child_delete_succeeds_and_child_is_absent(self, tmp_path: Path) -> None:
        path = await self._baseline(tmp_path)
        result = await _run(path, changes={"CONFIG": {"$op": "MERGE", "value": {"B": {"$op": "DELETE"}}}})
        assert result["status"] == "success", result
        written = path.read_text(encoding="utf-8")
        assert "B::two" not in written
        assert "A::one" in written and "C::three" in written


# ---------------------------------------------------------------------------
# #543: octave_compile_grammar must not drop POLICY/FIELDS silently
# ---------------------------------------------------------------------------

_SCHEMA_BASE = (
    '===S===\nMETA:\n  TYPE::SCHEMA\n  VERSION::"1"\n{X}POLICY:\n  VERSION::"1.0"\n'
    "  UNKNOWN_FIELDS::REJECT\n  TARGETS::[§SELF]\nFIELDS:\n"
    '  STATUS::["ACTIVE"∧REQ∧ENUM[ACTIVE,DRAFT]→§SELF]\n===END===\n'
)


class TestCompileGrammar543:
    async def test_contract_label_with_policy_fields_is_refused(self) -> None:
        from octave_mcp.mcp.compile_grammar import CompileGrammarTool

        content = _SCHEMA_BASE.replace("{X}", "  CONTRACT::HOLOGRAPHIC<validation_law_in_document>\n")
        result = await CompileGrammarTool().execute(content=content)
        assert result["status"] == "error", result
        assert [e["code"] for e in result["errors"]] == ["E_GRAMMAR_FIELDS_DROPPED"]

    async def test_without_contract_the_fields_reach_the_grammar(self) -> None:
        from octave_mcp.mcp.compile_grammar import CompileGrammarTool

        result = await CompileGrammarTool().execute(content=_SCHEMA_BASE.replace("{X}", ""))
        assert result["status"] == "success", result
        assert "ACTIVE" in result["grammar"]


# ---------------------------------------------------------------------------
# CLI: the same refusal through the shared entry point
# ---------------------------------------------------------------------------


class TestCliWrite:
    def test_cli_write_refuses_533(self, tmp_path: Path) -> None:
        from click.testing import CliRunner

        from octave_mcp.cli.main import cli

        path = tmp_path / "cli.oct.md"
        result = CliRunner().invoke(cli, ["write", str(path), "--content", _REPRO_533])
        assert result.exit_code == 1, result.output
        assert "E_FIDELITY" in result.output
        assert not path.exists()

    def test_cli_changes_refuses_bare_line_loss(self, tmp_path: Path) -> None:
        import json

        from click.testing import CliRunner

        from octave_mcp.cli.main import cli

        path = tmp_path / "cli_changes.oct.md"
        path.write_text(_CHANGES_BASELINE_BARE_IN_ONE, encoding="utf-8")
        before = _snapshot(path)
        result = CliRunner().invoke(cli, ["write", str(path), "--changes", json.dumps({"META.STATUS": "ACTIVE"})])
        assert result.exit_code == 1, result.output
        assert "E_FIDELITY" in result.output
        assert _snapshot(path) == before
