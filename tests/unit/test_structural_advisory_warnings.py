"""Tests for structural advisory warnings W_INLINE_ARRAY_ROOT and W_FLAT_PREFIX_SCALAR.

Advisory note 2026-05-29 (Ask 1): two new structural advisory warnings for the
OCTAVE-MCP validator, following the same pattern as W_SNAKE_CASE_BLOB (GH#452/PR#456).

Detection contracts:

W_INLINE_ARRAY_ROOT
    TRIGGER   :: key's value is an inline array [...] whose elements are K::V
                 map-entries (map-as-inline-array), AND entry count >= 3 OR
                 serialized length > reasonable threshold.
    EXCLUSION :: elements are plain scalars/strings (no '::' map syntax).
    SEVERITY  :: advisory (warnings channel, non-blocking)
    MESSAGE   :: "multi-field token authored as inline-array root; prefer BLOCK
                  form (KEY: + indented children). Inline arrays are for scalar
                  lists, not maps-of-maps."

W_FLAT_PREFIX_SCALAR
    TRIGGER   :: >= 3 sibling keys share a longest common underscore-delimited
                 prefix; flagging them suggests nesting under a block parent to
                 remove the redundant prefix.
    HEURISTIC :: group sibling keys by longest-common-prefix-up-to-_; flag
                 groups of size >= 3.
    SEVERITY  :: advisory (warnings channel, non-blocking)
    MESSAGE   :: "sibling keys share prefix '{PREFIX}_'; nest under '{PREFIX}:'
                  block to drop the redundant prefix (key-token saving + better
                  attention inheritance)."

TDD RED phase: these tests FAIL before the implementation lands in
``src/octave_mcp/mcp/write_detection.py``.
"""

import pytest

from octave_mcp.mcp.validate import ValidateTool
from octave_mcp.mcp.write import WriteTool
from octave_mcp.mcp.write_detection import (
    _detect_flat_prefix_scalar,
    _detect_inline_array_root,
)

# ---------------------------------------------------------------------------
# W_INLINE_ARRAY_ROOT — unit tests
# ---------------------------------------------------------------------------


class TestInlineArrayRootDetector:
    """Direct calls to _detect_inline_array_root."""

    # --- Positive cases: must fire ---

    def test_fires_on_map_as_inline_array_three_entries(self):
        """Three K::V elements in inline array must trigger."""
        content = "ITEMS::[KEY_A::val_a, KEY_B::val_b, KEY_C::val_c]\n"
        warnings = _detect_inline_array_root(content)
        codes = [w["code"] for w in warnings]
        assert "W_INLINE_ARRAY_ROOT" in codes

    def test_fires_on_map_as_inline_array_four_entries(self):
        """Four K::V elements in inline array must trigger."""
        content = "META_ITEMS::[A::1, B::2, C::3, D::4]\n"
        warnings = _detect_inline_array_root(content)
        codes = [w["code"] for w in warnings]
        assert "W_INLINE_ARRAY_ROOT" in codes

    def test_fires_on_long_serialized_inline_map_array(self):
        """Long inline map-array (even 2 entries, long serialized form) triggers on length."""
        # > reasonable threshold via length even if count is only 2
        long_key_a = "A" * 40
        long_key_b = "B" * 40
        content = f"SECTION::[{long_key_a}::value_one, {long_key_b}::value_two]\n"
        warnings = _detect_inline_array_root(content)
        codes = [w["code"] for w in warnings]
        assert "W_INLINE_ARRAY_ROOT" in codes

    def test_fires_on_block_form_assignment_inline_array_with_map_elements(self):
        """KEY: [...] block-form opening with map elements must also trigger."""
        content = "SECTION:[\n  A::1,\n  B::2,\n  C::3\n]\n"
        warnings = _detect_inline_array_root(content)
        codes = [w["code"] for w in warnings]
        assert "W_INLINE_ARRAY_ROOT" in codes

    # --- Negative cases: must NOT fire ---

    def test_no_fire_on_scalar_list(self):
        """Plain scalar list must NOT trigger — this is legitimate OCTAVE."""
        content = "IMMUTABLES::[a, b, c]\n"
        warnings = _detect_inline_array_root(content)
        codes = [w["code"] for w in warnings]
        assert "W_INLINE_ARRAY_ROOT" not in codes

    def test_no_fire_on_authority_scalar_list(self):
        """AUTHORITY::[a, b] — scalar list, no :: in elements."""
        content = "AUTHORITY::[admin, user]\n"
        warnings = _detect_inline_array_root(content)
        codes = [w["code"] for w in warnings]
        assert "W_INLINE_ARRAY_ROOT" not in codes

    def test_no_fire_on_consolidates_scalar_list(self):
        """CONSOLIDATES::[...] with scalar entries must NOT trigger."""
        content = "CONSOLIDATES::[GH_123, GH_456, GH_789]\n"
        warnings = _detect_inline_array_root(content)
        codes = [w["code"] for w in warnings]
        assert "W_INLINE_ARRAY_ROOT" not in codes

    def test_no_fire_on_two_map_entries_short(self):
        """Two short K::V elements is not a strong enough signal without length pressure."""
        content = "SMALL::[A::1, B::2]\n"
        warnings = _detect_inline_array_root(content)
        codes = [w["code"] for w in warnings]
        assert "W_INLINE_ARRAY_ROOT" not in codes

    def test_no_fire_in_literal_zone(self):
        """Map-as-inline-array inside a fenced literal zone must NOT trigger."""
        content = "```\nSECTION::[A::1, B::2, C::3]\n```\n"
        warnings = _detect_inline_array_root(content)
        codes = [w["code"] for w in warnings]
        assert "W_INLINE_ARRAY_ROOT" not in codes

    def test_no_fire_in_comment(self):
        """Map-as-inline-array inside a // comment must NOT trigger."""
        content = "// SECTION::[A::1, B::2, C::3]\n"
        warnings = _detect_inline_array_root(content)
        codes = [w["code"] for w in warnings]
        assert "W_INLINE_ARRAY_ROOT" not in codes

    # --- Warning shape ---

    def test_warning_has_stable_code_and_provenance(self):
        """Warning carries stable code, line number, and key (I4)."""
        content = "FILLER::ok\n\nSECTION::[A::1, B::2, C::3]\n"
        warnings = _detect_inline_array_root(content)
        hits = [w for w in warnings if w["code"] == "W_INLINE_ARRAY_ROOT"]
        assert len(hits) >= 1
        w = hits[0]
        assert w["code"] == "W_INLINE_ARRAY_ROOT"
        assert w["line"] == 3
        assert w["safe"] is True
        assert w["semantics_changed"] is False

    def test_warning_message_references_block_form(self):
        """Warning message mentions BLOCK form preference."""
        content = "SECTION::[A::1, B::2, C::3]\n"
        warnings = _detect_inline_array_root(content)
        hits = [w for w in warnings if w["code"] == "W_INLINE_ARRAY_ROOT"]
        assert any("BLOCK" in w["message"] or "block" in w["message"] for w in hits)

    def test_advisory_severity_only(self):
        """W_INLINE_ARRAY_ROOT must carry safe=True, semantics_changed=False."""
        content = "SECTION::[A::1, B::2, C::3]\n"
        warnings = _detect_inline_array_root(content)
        for w in warnings:
            if w["code"] == "W_INLINE_ARRAY_ROOT":
                assert w["safe"] is True
                assert w["semantics_changed"] is False


# ---------------------------------------------------------------------------
# W_FLAT_PREFIX_SCALAR — unit tests
# ---------------------------------------------------------------------------


class TestFlatPrefixScalarDetector:
    """Direct calls to _detect_flat_prefix_scalar."""

    # --- Positive cases: must fire ---

    def test_fires_on_three_siblings_with_shared_prefix(self):
        """NODE_RUNTIME_FLOOR, NODE_RUNTIME_PIN_SITES, NODE_RUNTIME_WHY → fires."""
        content = (
            "===DOC===\n"
            "META::\n"
            "  TYPE::TEST\n"
            "NODE_RUNTIME_FLOOR::3.12\n"
            "NODE_RUNTIME_PIN_SITES::[a, b]\n"
            "NODE_RUNTIME_WHY::performance\n"
            "===END===\n"
        )
        warnings = _detect_flat_prefix_scalar(content)
        codes = [w["code"] for w in warnings]
        assert "W_FLAT_PREFIX_SCALAR" in codes

    def test_fires_on_four_siblings_with_shared_prefix(self):
        """Four sibling keys with shared prefix must trigger."""
        content = (
            "DB_HOST::localhost\n"
            "DB_PORT::5432\n"
            "DB_NAME::mydb\n"
            "DB_USER::admin\n"
        )
        warnings = _detect_flat_prefix_scalar(content)
        codes = [w["code"] for w in warnings]
        assert "W_FLAT_PREFIX_SCALAR" in codes

    def test_warning_message_names_the_prefix(self):
        """Warning message must name the shared prefix."""
        content = (
            "NODE_RUNTIME_FLOOR::3.12\n"
            "NODE_RUNTIME_PIN_SITES::[a, b]\n"
            "NODE_RUNTIME_WHY::performance\n"
        )
        warnings = _detect_flat_prefix_scalar(content)
        hits = [w for w in warnings if w["code"] == "W_FLAT_PREFIX_SCALAR"]
        assert hits, "Expected W_FLAT_PREFIX_SCALAR warning"
        # Message should mention the prefix
        assert any("NODE_RUNTIME" in w["message"] for w in hits)

    def test_fires_with_mixed_depth_prefix(self):
        """CACHE_READ, CACHE_WRITE, CACHE_EXPIRE at document root must fire."""
        content = (
            "CACHE_READ::fast\n"
            "CACHE_WRITE::slow\n"
            "CACHE_EXPIRE::300\n"
        )
        warnings = _detect_flat_prefix_scalar(content)
        codes = [w["code"] for w in warnings]
        assert "W_FLAT_PREFIX_SCALAR" in codes

    # --- Negative cases: must NOT fire ---

    def test_no_fire_on_two_siblings_with_shared_prefix(self):
        """Only 2 siblings with shared prefix is below threshold — must NOT trigger."""
        content = (
            "NODE_RUNTIME_FLOOR::3.12\n"
            "NODE_RUNTIME_WHY::performance\n"
            "OTHER_KEY::value\n"
        )
        warnings = _detect_flat_prefix_scalar(content)
        codes = [w["code"] for w in warnings]
        assert "W_FLAT_PREFIX_SCALAR" not in codes

    def test_no_fire_on_keys_without_shared_prefix(self):
        """Keys that don't share a prefix must NOT trigger."""
        content = (
            "ALPHA_ONE::1\n"
            "BETA_TWO::2\n"
            "GAMMA_THREE::3\n"
        )
        warnings = _detect_flat_prefix_scalar(content)
        codes = [w["code"] for w in warnings]
        assert "W_FLAT_PREFIX_SCALAR" not in codes

    def test_no_fire_on_single_underscore_segment_keys(self):
        """Keys with no shared multi-segment prefix must NOT trigger.

        E.g. FOO, BAR, BAZ all have no common prefix.
        """
        content = (
            "FOO::1\n"
            "BAR::2\n"
            "BAZ::3\n"
        )
        warnings = _detect_flat_prefix_scalar(content)
        codes = [w["code"] for w in warnings]
        assert "W_FLAT_PREFIX_SCALAR" not in codes

    def test_no_fire_in_literal_zone(self):
        """Flat prefix pattern inside a literal zone must NOT trigger."""
        content = "```\nDB_HOST::localhost\nDB_PORT::5432\nDB_NAME::mydb\n```\n"
        warnings = _detect_flat_prefix_scalar(content)
        codes = [w["code"] for w in warnings]
        assert "W_FLAT_PREFIX_SCALAR" not in codes

    def test_no_fire_in_comment_lines(self):
        """Keys that appear only in comment lines must NOT trigger."""
        content = (
            "// DB_HOST::localhost\n"
            "// DB_PORT::5432\n"
            "// DB_NAME::mydb\n"
            "REAL_KEY::value\n"
        )
        warnings = _detect_flat_prefix_scalar(content)
        codes = [w["code"] for w in warnings]
        assert "W_FLAT_PREFIX_SCALAR" not in codes

    # --- Warning shape ---

    def test_warning_has_stable_code_line_and_provenance(self):
        """Warning carries stable code, line number, safe=True, semantics_changed=False (I4)."""
        content = (
            "DB_HOST::localhost\n"
            "DB_PORT::5432\n"
            "DB_NAME::mydb\n"
        )
        warnings = _detect_flat_prefix_scalar(content)
        hits = [w for w in warnings if w["code"] == "W_FLAT_PREFIX_SCALAR"]
        assert len(hits) >= 1
        w = hits[0]
        assert w["code"] == "W_FLAT_PREFIX_SCALAR"
        assert "line" in w
        assert w["safe"] is True
        assert w["semantics_changed"] is False

    def test_advisory_severity_only(self):
        """W_FLAT_PREFIX_SCALAR must carry safe=True, semantics_changed=False."""
        content = (
            "CACHE_READ::fast\n"
            "CACHE_WRITE::slow\n"
            "CACHE_EXPIRE::300\n"
        )
        warnings = _detect_flat_prefix_scalar(content)
        for w in warnings:
            if w["code"] == "W_FLAT_PREFIX_SCALAR":
                assert w["safe"] is True
                assert w["semantics_changed"] is False

    def test_warning_message_references_nesting_suggestion(self):
        """Warning message mentions nesting under a block parent."""
        content = (
            "CACHE_READ::fast\n"
            "CACHE_WRITE::slow\n"
            "CACHE_EXPIRE::300\n"
        )
        warnings = _detect_flat_prefix_scalar(content)
        hits = [w for w in warnings if w["code"] == "W_FLAT_PREFIX_SCALAR"]
        assert hits
        # Must mention nesting or the prefix block pattern
        assert any("nest" in w["message"].lower() or "CACHE" in w["message"] for w in hits)


# ---------------------------------------------------------------------------
# ValidateTool integration — both warnings surface in warnings[]
# ---------------------------------------------------------------------------


class TestValidateToolInlineArrayRoot:
    """W_INLINE_ARRAY_ROOT must surface in octave_validate warnings[]."""

    FIXTURE = """\
===VALIDATE_TEST===
META:
  TYPE::TEST
SECTION::[A::1, B::2, C::3]
===END===
"""

    @pytest.mark.asyncio
    async def test_validate_tool_emits_inline_array_root_in_warnings(self):
        tool = ValidateTool()
        result = await tool.execute(content=self.FIXTURE, schema="META")
        warnings = result.get("warnings", [])
        codes = [w.get("code") for w in warnings]
        assert "W_INLINE_ARRAY_ROOT" in codes

    @pytest.mark.asyncio
    async def test_validate_tool_does_not_block_on_inline_array_root(self):
        """Advisory only — must NOT produce an error for W_INLINE_ARRAY_ROOT."""
        tool = ValidateTool()
        result = await tool.execute(content=self.FIXTURE, schema="META")
        errors = result.get("errors", [])
        assert not any(e.get("code") == "W_INLINE_ARRAY_ROOT" for e in errors)


class TestValidateToolFlatPrefixScalar:
    """W_FLAT_PREFIX_SCALAR must surface in octave_validate warnings[]."""

    FIXTURE = """\
===VALIDATE_TEST===
META:
  TYPE::TEST
DB_HOST::localhost
DB_PORT::5432
DB_NAME::mydb
===END===
"""

    @pytest.mark.asyncio
    async def test_validate_tool_emits_flat_prefix_scalar_in_warnings(self):
        tool = ValidateTool()
        result = await tool.execute(content=self.FIXTURE, schema="META")
        warnings = result.get("warnings", [])
        codes = [w.get("code") for w in warnings]
        assert "W_FLAT_PREFIX_SCALAR" in codes

    @pytest.mark.asyncio
    async def test_validate_tool_does_not_block_on_flat_prefix_scalar(self):
        """Advisory only — must NOT produce an error for W_FLAT_PREFIX_SCALAR."""
        tool = ValidateTool()
        result = await tool.execute(content=self.FIXTURE, schema="META")
        errors = result.get("errors", [])
        assert not any(e.get("code") == "W_FLAT_PREFIX_SCALAR" for e in errors)


# ---------------------------------------------------------------------------
# WriteTool integration — both warnings surface in corrections[]
# ---------------------------------------------------------------------------


class TestWriteToolInlineArrayRoot:
    """W_INLINE_ARRAY_ROOT must surface in WriteTool corrections[]."""

    FIXTURE = """\
===WRITE_TEST===
META:
  TYPE::TEST
SECTION::[A::1, B::2, C::3]
===END===
"""

    @pytest.mark.asyncio
    async def test_write_tool_emits_inline_array_root_in_corrections(self, tmp_path):
        tool = WriteTool()
        target = str(tmp_path / "test.oct.md")
        result = await tool.execute(target_path=target, content=self.FIXTURE)
        corrections = result.get("corrections", [])
        codes = [c["code"] for c in corrections]
        assert "W_INLINE_ARRAY_ROOT" in codes

    @pytest.mark.asyncio
    async def test_write_tool_does_not_error_on_inline_array_root(self, tmp_path):
        """Advisory only — must NOT block the write."""
        tool = WriteTool()
        target = str(tmp_path / "test.oct.md")
        result = await tool.execute(target_path=target, content=self.FIXTURE)
        assert result.get("status") != "error"
        errors = result.get("errors", [])
        assert not any(e.get("code") == "W_INLINE_ARRAY_ROOT" for e in errors)


class TestWriteToolFlatPrefixScalar:
    """W_FLAT_PREFIX_SCALAR must surface in WriteTool corrections[]."""

    FIXTURE = """\
===WRITE_TEST===
META:
  TYPE::TEST
DB_HOST::localhost
DB_PORT::5432
DB_NAME::mydb
===END===
"""

    @pytest.mark.asyncio
    async def test_write_tool_emits_flat_prefix_scalar_in_corrections(self, tmp_path):
        tool = WriteTool()
        target = str(tmp_path / "test.oct.md")
        result = await tool.execute(target_path=target, content=self.FIXTURE)
        corrections = result.get("corrections", [])
        codes = [c["code"] for c in corrections]
        assert "W_FLAT_PREFIX_SCALAR" in codes

    @pytest.mark.asyncio
    async def test_write_tool_does_not_error_on_flat_prefix_scalar(self, tmp_path):
        """Advisory only — must NOT block the write."""
        tool = WriteTool()
        target = str(tmp_path / "test.oct.md")
        result = await tool.execute(target_path=target, content=self.FIXTURE)
        assert result.get("status") != "error"
        errors = result.get("errors", [])
        assert not any(e.get("code") == "W_FLAT_PREFIX_SCALAR" for e in errors)


# ---------------------------------------------------------------------------
# TMG advisory follow-ups (A1–A5 from TMG review)
# ---------------------------------------------------------------------------


class TestInlineArrayRootTMGAdvisory:
    """TMG A1: tier assertion; TMG A5: long scalar list must NOT fire."""

    def test_warning_tier_is_structural_check(self):
        """A1: tier field must be STRUCTURAL_CHECK (not silently absent or wrong)."""
        content = "SECTION::[A::1, B::2, C::3]\n"
        warnings = _detect_inline_array_root(content)
        hits = [w for w in warnings if w["code"] == "W_INLINE_ARRAY_ROOT"]
        assert hits, "Expected W_INLINE_ARRAY_ROOT warning"
        assert all(w["tier"] == "STRUCTURAL_CHECK" for w in hits)

    def test_long_scalar_list_does_not_fire(self):
        """A5: a >80-char scalar list (no '::') must NOT trigger — map discriminator guards this."""
        # Scalars, no K::V syntax. Length > 80 chars.
        long_scalars = ", ".join([f"item_{i:03d}" for i in range(15)])
        content = f"LONG_ITEMS::[{long_scalars}]\n"
        assert len(long_scalars) > 80, "Fixture must be > 80 chars to exercise length branch"
        warnings = _detect_inline_array_root(content)
        codes = [w["code"] for w in warnings]
        assert "W_INLINE_ARRAY_ROOT" not in codes


class TestFlatPrefixScalarTMGAdvisory:
    """TMG A1/A2/A3/A4 follow-ups for W_FLAT_PREFIX_SCALAR."""

    def test_warning_tier_is_structural_check(self):
        """A1: tier field must be STRUCTURAL_CHECK."""
        content = (
            "DB_HOST::localhost\n"
            "DB_PORT::5432\n"
            "DB_NAME::mydb\n"
        )
        warnings = _detect_flat_prefix_scalar(content)
        hits = [w for w in warnings if w["code"] == "W_FLAT_PREFIX_SCALAR"]
        assert hits, "Expected W_FLAT_PREFIX_SCALAR warning"
        assert all(w["tier"] == "STRUCTURAL_CHECK" for w in hits)

    def test_dedup_emits_exactly_one_warning_per_group(self):
        """A2: deduplication logic — NODE_RUNTIME_* group must emit exactly one warning.

        Without dedup, the multi-prefix algorithm could emit both under
        prefix 'NODE' and prefix 'NODE_RUNTIME' for the same key set.
        """
        content = (
            "NODE_RUNTIME_FLOOR::3.12\n"
            "NODE_RUNTIME_PIN_SITES::[a, b]\n"
            "NODE_RUNTIME_WHY::performance\n"
        )
        warnings = _detect_flat_prefix_scalar(content)
        hits = [w for w in warnings if w["code"] == "W_FLAT_PREFIX_SCALAR"]
        assert len(hits) == 1, (
            f"Expected exactly 1 W_FLAT_PREFIX_SCALAR warning for NODE_RUNTIME_* group, "
            f"got {len(hits)}: {[w['prefix'] for w in hits]}"
        )

    def test_mixed_indent_keys_not_grouped_across_indents(self):
        """A3: sibling-by-indentation — same prefix at different indent levels must NOT be grouped.

        DB_HOST at indent 0 and indented DB_HOST::... at indent 2 are not siblings.
        """
        content = (
            "DB_HOST::localhost\n"
            "DB_PORT::5432\n"
            "SECTION:\n"
            "  DB_NAME::inner\n"
            "  DB_USER::inner_user\n"
            "  DB_PASS::inner_pass\n"
        )
        warnings = _detect_flat_prefix_scalar(content)
        hits = [w for w in warnings if w["code"] == "W_FLAT_PREFIX_SCALAR"]
        # Top-level DB_HOST + DB_PORT = 2 only (below threshold).
        # Indented DB_NAME + DB_USER + DB_PASS = 3 (triggers for indented group).
        # They must NOT be merged into one cross-indent group of 5.
        for hit in hits:
            key_list = hit["keys"]
            # No warning should contain keys from BOTH indent levels.
            has_top_level = any(k in ("DB_HOST", "DB_PORT") for k in key_list)
            has_indented = any(k in ("DB_NAME", "DB_USER", "DB_PASS") for k in key_list)
            assert not (has_top_level and has_indented), (
                f"Cross-indent grouping detected: {key_list}"
            )

    def test_block_form_siblings_detected(self):
        """A4: block-form siblings (KEY: child) should also trigger after regex fix.

        After fixing the [:s] typo to [:\\s], a 'KEY: ' (block-open with space)
        form is also matched. Three such siblings at the same level should trigger.
        """
        # Block-open form: DB_HOST: followed by value on next line would be
        # `DB_HOST:\n  value`, but at the key-scan level we match the opener line.
        # The simplest form that exercises the \\s branch: `KEY: value` (space after colon).
        content = (
            "DB_HOST: localhost\n"
            "DB_PORT: 5432\n"
            "DB_NAME: mydb\n"
        )
        warnings = _detect_flat_prefix_scalar(content)
        codes = [w["code"] for w in warnings]
        assert "W_FLAT_PREFIX_SCALAR" in codes, (
            "Block-form (KEY: value with space) siblings must also trigger "
            "W_FLAT_PREFIX_SCALAR after regex fix."
        )

    def test_no_false_positive_across_different_parent_blocks(self):
        """CRS-1: Keys in different parent blocks must NOT be grouped as siblings.

        SECTION_A:\n  DB_HOST and SECTION_B:\n  DB_NAME are NOT siblings even if
        both are indented equally — they have different parents.
        """
        content = (
            "SECTION_A:\n"
            "  DB_HOST::localhost\n"
            "  DB_PORT::5432\n"
            "SECTION_B:\n"
            "  DB_NAME::mydb\n"
        )
        warnings = _detect_flat_prefix_scalar(content)
        hits = [w for w in warnings if w["code"] == "W_FLAT_PREFIX_SCALAR"]
        # DB_HOST + DB_PORT = 2 (below threshold in SECTION_A group).
        # DB_NAME = 1 (only key in SECTION_B group).
        # No cross-block group of 3+ should form.
        for hit in hits:
            key_list = hit["keys"]
            has_section_a = any(k in ("DB_HOST", "DB_PORT") for k in key_list)
            has_section_b = any(k in ("DB_NAME",) for k in key_list)
            assert not (has_section_a and has_section_b), (
                f"Cross-parent-block grouping detected: {key_list}"
            )


class TestInlineArrayRootCRSAdvisory:
    """CRS advisory follow-ups for W_INLINE_ARRAY_ROOT."""

    def test_no_false_positive_when_double_colon_in_quoted_string(self):
        """CRS-2: '::' appearing only inside a quoted string element must NOT trigger.

        SECTION::[\"note, A::x\"] — the '::' is inside a quote, not a map entry.
        """
        # Only one quoted scalar element containing '::'; no unquoted K::V entries.
        content = 'SECTION::["note with A::x embedded"]\n'
        warnings = _detect_inline_array_root(content)
        codes = [w["code"] for w in warnings]
        assert "W_INLINE_ARRAY_ROOT" not in codes

    def test_no_false_positive_mixed_scalar_map_below_threshold(self):
        """CRS-3: Mixed array with 1 map entry and 2 scalars must NOT trigger.

        Entry count threshold (>= 3 map entries) guards against firing when only
        one element is a K::V pair and the rest are scalars.
        """
        # One map entry + two scalars = 1 map-entry, below threshold of 3.
        content = "SECTION::[A::1, scalar_b, scalar_c]\n"
        warnings = _detect_inline_array_root(content)
        codes = [w["code"] for w in warnings]
        assert "W_INLINE_ARRAY_ROOT" not in codes

    def test_no_false_positive_closing_bracket_in_quoted_value(self):
        """CRS-2: A ']' inside a quoted string value must NOT close the array scan early.

        Without quote-protection, SECTION::[A::'foo]', B::2, C::3] would close
        prematurely on the ']' inside the first quoted value.
        """
        content = 'SECTION::[A::"foo]", B::2, C::3]\n'
        warnings = _detect_inline_array_root(content)
        codes = [w["code"] for w in warnings]
        # The array has 3 unquoted map-entry elements after correct bracket tracking.
        assert "W_INLINE_ARRAY_ROOT" in codes
