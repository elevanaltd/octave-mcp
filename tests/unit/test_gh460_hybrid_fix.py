"""GH#460 v1.14.0 hybrid fix for ``octave_write`` ``changes`` mode.

Two distinct latent defects in the changes-mode mutation core, both
load-bearing for PROD invariants:

Case A — Literal-zone form-switching (PROD::I1 SYNTACTIC_FIDELITY)
    When a ``changes`` value targets a child whose existing value is a
    ``LiteralZoneValue`` (fenced block), the applier downgraded the value
    to a quoted scalar (``KEY::"..."``) instead of preserving the fence
    form. Fix: when the existing child value is a ``LiteralZoneValue`` and
    the new value is a plain string/dict, preserve the fence form by
    re-wrapping the new content as ``LiteralZoneValue`` carrying the
    original ``fence_marker`` (mirrors PR #449 mutate-in-place philosophy).

Case B — Duplicate-key first-match (PROD::I3 MIRROR_CONSTRAINT,
         PROD::I4 TRANSFORM_AUDITABILITY)
    With N sibling keys (e.g. 5 sibling ``RATIONALE`` keys, one per
    immutable), only the first was reachable through bare-key ``changes``.
    Fix: an ``ANCHOR/KEY`` anchored-path form — "the KEY assignment
    following the ANCHOR key in document order". Backward-compatible with
    bare ``KEY`` and ``§<id>.KEY`` paths, and with literal keys that
    legitimately contain ``/`` (resolve-literal-first).

TDD discipline (deep tier): these tests were authored RED (failing
against the pre-fix surface) BEFORE the implementation landed.
"""

import os
import tempfile

import pytest

from octave_mcp.mcp.write import WriteTool

_TOOL = WriteTool()


async def _write_and_read(doc: str, changes: dict, *, format_style: str = "preserve") -> tuple[dict, str]:
    """Seed ``doc`` to a temp file, apply ``changes``, return (result, written bytes)."""
    fd, path = tempfile.mkstemp(suffix=".oct.md")
    os.close(fd)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(doc)
        result = await _TOOL.execute(target_path=path, changes=changes, format_style=format_style)
        with open(path, encoding="utf-8") as f:
            written = f.read()
        return result, written
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# Case B — ANCHOR/KEY anchored-path disambiguation
# ---------------------------------------------------------------------------

# Five immutables, each followed by a sibling RATIONALE. Flat top-level form
# (the exact shape the issue's acceptance criteria specifies).
_DOC_FIVE_RATIONALE = """===NS===
I1::SYNTACTIC_FIDELITY
RATIONALE::"r1_original"
I2::DETERMINISTIC_ABSENCE
RATIONALE::"r2_original"
I3::MIRROR_CONSTRAINT
RATIONALE::"r3_original"
I4::TRANSFORM_AUDITABILITY
RATIONALE::"r4_original"
I5::SCHEMA_SOVEREIGNTY
RATIONALE::"r5_original"
===END===
"""


class TestCaseBAnchoredPath:
    """ANCHOR/KEY resolves the KEY following ANCHOR in document order."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("anchor", "new_value"),
        [
            ("I1", "r1_NEW"),
            ("I2", "r2_NEW"),
            ("I3", "r3_NEW"),
            ("I4", "r4_NEW"),
            ("I5", "r5_NEW"),
        ],
    )
    async def test_each_rationale_targetable_individually(self, anchor: str, new_value: str) -> None:
        """Each of 5 sibling RATIONALE keys is reachable via ANCHOR/RATIONALE."""
        result, written = await _write_and_read(_DOC_FIVE_RATIONALE, {f"{anchor}/RATIONALE": new_value})
        assert result["status"] == "success", result.get("errors")
        # The targeted RATIONALE changed...
        assert f'RATIONALE::"{new_value}"' in written or f"RATIONALE::{new_value}" in written
        # ...and exactly one RATIONALE changed (the other four originals survive).
        survivors = [n for n in range(1, 6) if f'"r{n}_original"' in written]
        idx = int(anchor[1])
        expected_survivors = [n for n in range(1, 6) if n != idx]
        assert survivors == expected_survivors, (
            f"Anchor {anchor} should change only RATIONALE #{idx}; " f"survivors={survivors}, written=\n{written}"
        )

    @pytest.mark.asyncio
    async def test_bare_key_still_hits_first_sibling(self) -> None:
        """Backward-compat: a bare KEY resolves the first matching sibling."""
        result, written = await _write_and_read(_DOC_FIVE_RATIONALE, {"RATIONALE": "first_only"})
        assert result["status"] == "success", result.get("errors")
        assert 'RATIONALE::"first_only"' in written or "RATIONALE::first_only" in written
        # The first original is gone; the other four originals remain.
        assert '"r1_original"' not in written
        for n in range(2, 6):
            assert f'"r{n}_original"' in written

    @pytest.mark.asyncio
    async def test_anchor_not_found_is_unresolvable(self) -> None:
        """An anchor that does not exist yields a clear unresolvable-path error."""
        result, _ = await _write_and_read(_DOC_FIVE_RATIONALE, {"I9/RATIONALE": "nope"})
        assert result["status"] != "success"
        codes = {e.get("code") for e in result.get("errors", [])}
        assert "E_UNRESOLVABLE_PATH" in codes, result.get("errors")

    @pytest.mark.asyncio
    async def test_key_after_anchor_not_found_is_unresolvable(self) -> None:
        """An anchor present but no following KEY yields unresolvable-path."""
        result, _ = await _write_and_read(_DOC_FIVE_RATIONALE, {"I1/NONEXISTENT": "nope"})
        assert result["status"] != "success"
        codes = {e.get("code") for e in result.get("errors", [])}
        assert "E_UNRESOLVABLE_PATH" in codes, result.get("errors")

    @pytest.mark.asyncio
    async def test_literal_slash_key_resolves_first(self) -> None:
        """Backward-compat: a real key literally containing '/' is mutated in place.

        ``/`` is a valid OCTAVE identifier character. When ``ANCHOR/KEY``
        already exists verbatim as a real assignment, it MUST be mutated
        (resolve-literal-first) rather than reinterpreted as an anchored
        path — otherwise the fix would silently break existing documents.
        """
        doc = """===D===
A/B::"original_literal"
===END===
"""
        result, written = await _write_and_read(doc, {"A/B": "changed_literal"})
        assert result["status"] == "success", result.get("errors")
        assert "A/B::changed_literal" in written or 'A/B::"changed_literal"' in written
        assert "original_literal" not in written

    @pytest.mark.asyncio
    async def test_indexed_anchor_path_rejected(self) -> None:
        """Indexed KEY[N] notation stays rejected (E_UNRESOLVABLE_PATH).

        The issue mandates that the anchored-path form does NOT introduce
        indexed addressing: ``KEY[N]`` collides with ``_ARRAY_INDEX_RE`` and
        would breach PROD::I4 audit-stability and PROD::I3 (real keys, not
        invented indices). The applier must not silently treat ``[N]`` as a
        literal key suffix.
        """
        result, _ = await _write_and_read(_DOC_FIVE_RATIONALE, {"I1/RATIONALE[0]": "value"})
        assert result["status"] != "success"
        codes = {e.get("code") for e in result.get("errors", [])}
        assert "E_UNRESOLVABLE_PATH" in codes, result.get("errors")

    @pytest.mark.asyncio
    async def test_anchored_path_resolves_only_key_after_anchor(self) -> None:
        """A KEY appearing BEFORE the anchor is not matched; only after counts.

        Validates document-order semantics: the assertions below check the
        content of the RATIONALE BEFORE the anchor (must survive) against the
        RATIONALE AFTER the anchor (must change), so the anchor's position in
        the sibling list is what selects the target.
        """
        doc = """===D===
RATIONALE::"before_anchor"
I2::DETERMINISTIC_ABSENCE
RATIONALE::"after_anchor"
===END===
"""
        result, written = await _write_and_read(doc, {"I2/RATIONALE": "targeted"})
        assert result["status"] == "success", result.get("errors")
        assert '"before_anchor"' in written  # untouched
        assert '"after_anchor"' not in written  # changed
        assert "RATIONALE::targeted" in written or 'RATIONALE::"targeted"' in written

    @pytest.mark.asyncio
    async def test_section_path_still_works(self) -> None:
        """Backward-compat: §<id>.KEY section path is unaffected by the new form."""
        doc = """===D===
§1::IDENTITY
  ROLE::"old_role"
===END===
"""
        result, written = await _write_and_read(doc, {"§1.ROLE": "new_role"})
        assert result["status"] == "success", result.get("errors")
        assert "new_role" in written
        assert "old_role" not in written

    @pytest.mark.asyncio
    async def test_anchored_path_within_section_children(self) -> None:
        """ANCHOR/KEY resolves siblings nested inside a section's children."""
        doc = """===D===
§1::IMMUTABLES
  I1::FIDELITY
  RATIONALE::"sec_r1"
  I2::ABSENCE
  RATIONALE::"sec_r2"
===END===
"""
        result, written = await _write_and_read(doc, {"I2/RATIONALE": "sec_r2_new"})
        assert result["status"] == "success", result.get("errors")
        # First sibling untouched (quoting may be canonicalized on section
        # re-emit; assert on the value content, not the quote form).
        assert "RATIONALE::sec_r1" in written or 'RATIONALE::"sec_r1"' in written
        assert "sec_r2_new" in written  # second changed
        assert "RATIONALE::sec_r2\n" not in written and 'RATIONALE::"sec_r2"' not in written


# ---------------------------------------------------------------------------
# Case A — Literal-zone form preservation
# ---------------------------------------------------------------------------

# Top-level fenced literal zone.
_DOC_LITERAL_TOPLEVEL = "===PRIMER===\nOPERATORS::\n```\nold line 1\nold line 2\n```\n===END===\n"

# Longer fence marker (verifies fence_marker is preserved, not normalized to ```).
_DOC_LITERAL_LONGFENCE = "===PRIMER===\nOPERATORS::\n````\ncontains ``` inside\n````\n===END===\n"


class TestCaseALiteralZonePreservation:
    """A content-only change to a literal-zone child preserves the fence form."""

    @pytest.mark.asyncio
    async def test_toplevel_literal_zone_keeps_fence_form(self) -> None:
        """Changing a top-level literal zone's content keeps the ``` fence form.

        Pre-fix this emitted ``OPERATORS::"new line 1\\nnew line 2"`` —
        a quoted scalar, losing the fence (I1 violation).
        """
        result, written = await _write_and_read(_DOC_LITERAL_TOPLEVEL, {"OPERATORS": "new line 1\nnew line 2"})
        assert result["status"] == "success", result.get("errors")
        # Fence form preserved: NOT downgraded to a quoted scalar.
        assert 'OPERATORS::"' not in written, f"fence form lost:\n{written}"
        assert "```" in written, f"fence markers missing:\n{written}"
        assert "new line 1" in written
        assert "new line 2" in written
        assert "old line 1" not in written

    @pytest.mark.asyncio
    async def test_byte_identical_fence_on_content_only_change(self) -> None:
        """Round-trip: only the content bytes differ; the fence framing is identical.

        The written document equals the original with ONLY the inner
        content lines swapped — the ``OPERATORS::`` header line and the
        two ``` fence lines are byte-identical.
        """
        new_content = "alpha\nbeta"
        _, written = await _write_and_read(_DOC_LITERAL_TOPLEVEL, {"OPERATORS": new_content})
        expected = "===PRIMER===\nOPERATORS::\n```\nalpha\nbeta\n```\n===END===\n"
        assert written == expected, f"expected byte-identical fence form:\n{written!r}\n!=\n{expected!r}"

    @pytest.mark.asyncio
    async def test_long_fence_marker_preserved(self) -> None:
        """A ```` (4-backtick) fence marker is preserved, not normalized to ```."""
        _, written = await _write_and_read(_DOC_LITERAL_LONGFENCE, {"OPERATORS": "replaced"})
        assert "````" in written, f"long fence marker lost:\n{written}"
        assert "replaced" in written
        assert 'OPERATORS::"' not in written

    @pytest.mark.asyncio
    async def test_section_child_literal_zone_keeps_fence(self) -> None:
        """A literal-zone child inside a section keeps its fence on content change."""
        doc = "===PRIMER===\n§3::OPERATORS\n  LEGEND::\n  ```\n  old legend\n  ```\n===END===\n"
        result, written = await _write_and_read(doc, {"§3.LEGEND": "new legend"})
        assert result["status"] == "success", result.get("errors")
        assert "```" in written, f"fence form lost:\n{written}"
        assert 'LEGEND::"' not in written, f"fence downgraded to scalar:\n{written}"
        assert "new legend" in written
        assert "old legend" not in written

    @pytest.mark.asyncio
    async def test_non_literal_scalar_change_unaffected(self) -> None:
        """Sanity: a plain scalar child is still changed as a plain scalar."""
        doc = '===D===\nKEY::"old"\n===END===\n'
        result, written = await _write_and_read(doc, {"KEY": "new"})
        assert result["status"] == "success", result.get("errors")
        assert "new" in written
        assert "```" not in written  # no fence invented for a non-literal target
