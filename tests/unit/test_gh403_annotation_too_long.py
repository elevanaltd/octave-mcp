"""Tests for GH#403: W_ANNOTATION_TOO_LONG warning for oversized annotation content.

When annotation identifier content (the qualifier inside <>) exceeds the
discipline threshold (len > 32 chars OR underscore_token_count >= 5),
the validator/write tool emits a non-blocking W_ANNOTATION_TOO_LONG warning
via the corrections/repair_log rather than a validation failure.

TDD RED phase: these tests FAIL before implementation.
"""

import pytest

from octave_mcp.mcp.write import WriteTool, _detect_annotation_too_long


class TestDetectAnnotationTooLong:
    """Unit tests for the _detect_annotation_too_long scanning function."""

    LONG_ANNOTATION_CONTENT = """\
===TEST===
NORTH_STAR_ALIGNMENT::[
  I8<via_HO_PRODUCTION_STACK_ARCHITECTURE_20260426_StorageProvider_interface_contract_enables_layer_1_vendor_swap_without_app_redeploys>,
  I6<production_grade_quality>
]
===END===
"""

    SHORT_ONLY_CONTENT = """\
===TEST===
ARCHETYPES::[
  HEPHAESTUS<implementation_craft>,
  ATLAS<structural_foundation>,
  HERMES<coordination>
]
===END===
"""

    BOUNDARY_CONTENT = """\
===TEST===
ROLES::[
  AGENT<exactly_32_char_identifier__>,
  AGENT<five_under_score_tokens_here>
]
===END===
"""

    def test_long_annotation_fires_warning(self):
        """W_ANNOTATION_TOO_LONG must fire for annotation content > 32 chars."""
        warnings = _detect_annotation_too_long(self.LONG_ANNOTATION_CONTENT)
        codes = [w["code"] for w in warnings]
        assert "W_ANNOTATION_TOO_LONG" in codes

    def test_short_clean_annotations_no_warning(self):
        """W_ANNOTATION_TOO_LONG must NOT fire for clean short annotations."""
        warnings = _detect_annotation_too_long(self.SHORT_ONLY_CONTENT)
        assert warnings == []

    def test_production_grade_quality_is_clean(self):
        """I6<production_grade_quality> must NOT trigger warning (4 tokens, 22 chars)."""
        content = "NORTH_STAR_ALIGNMENT::[I6<production_grade_quality>]"
        warnings = _detect_annotation_too_long(content)
        assert warnings == []

    def test_long_qualifier_detected_correctly(self):
        """The long annotation from GH-403 examples must trigger exactly one warning."""
        long_annotation = "I8<via_HO_PRODUCTION_STACK_ARCHITECTURE_20260426_StorageProvider_interface_contract_enables_layer_1_vendor_swap_without_app_redeploys>"
        content = f"FIELD::[{long_annotation}]"
        warnings = _detect_annotation_too_long(content)
        assert len(warnings) == 1
        w = warnings[0]
        assert w["code"] == "W_ANNOTATION_TOO_LONG"
        assert w["safe"] is True
        assert w["semantics_changed"] is False

    def test_warning_includes_annotation_value(self):
        """Warning dict must include the offending annotation value."""
        content = "FIELD::I6<migration_on_moving_target_is_anti_pattern>"
        warnings = _detect_annotation_too_long(content)
        assert len(warnings) == 1
        assert "migration_on_moving_target_is_anti_pattern" in warnings[0]["annotation"]

    def test_five_underscore_tokens_triggers_warning(self):
        """Annotation with exactly 5 underscore-delimited tokens must trigger warning."""
        # "a_b_c_d_e" has 5 tokens separated by 4 underscores — boundary case
        # threshold is >= 5 tokens (i.e., >= 4 underscores in the content)
        content = "AGENT<token_one_two_three_four>"  # 5 tokens
        warnings = _detect_annotation_too_long(content)
        assert len(warnings) == 1

    def test_four_underscore_tokens_no_warning(self):
        """Annotation with 4 underscore-delimited tokens must NOT trigger warning."""
        content = "AGENT<production_grade_quality>"  # 3 tokens, clearly fine
        warnings = _detect_annotation_too_long(content)
        assert warnings == []

    def test_exactly_32_chars_no_warning(self):
        """Annotation content of exactly 32 chars must NOT trigger (boundary is > 32)."""
        # 32 chars exactly
        qualifier = "a" * 32
        content = f"AGENT<{qualifier}>"
        warnings = _detect_annotation_too_long(content)
        assert warnings == []

    def test_33_chars_triggers_warning(self):
        """Annotation content of 33 chars must trigger warning (len > 32)."""
        qualifier = "a" * 33
        content = f"AGENT<{qualifier}>"
        warnings = _detect_annotation_too_long(content)
        assert len(warnings) == 1

    def test_empty_qualifier_no_warning(self):
        """Empty annotation content FOO<> must NOT trigger warning."""
        content = "FOO<>"
        warnings = _detect_annotation_too_long(content)
        assert warnings == []

    def test_multiple_long_annotations_all_flagged(self):
        """Multiple oversized annotations in one document must each get a warning."""
        content = (
            "FIELD::[I8<via_HO_PRODUCTION_STACK_ARCHITECTURE_20260426_long>, "
            "I6<another_very_long_annotation_content_here_exceeding_limit>]"
        )
        warnings = _detect_annotation_too_long(content)
        assert len(warnings) == 2


class TestWriteToolAnnotationWarnings:
    """Integration tests: W_ANNOTATION_TOO_LONG surfaces in WriteTool corrections."""

    FIXTURE_WITH_LONG_ANNOTATION = """\
===NORTH_STAR_ALIGNMENT_TEST===
META:
  TYPE::TEST
NORTH_STAR_ALIGNMENT::[
  I8<via_HO_PRODUCTION_STACK_ARCHITECTURE_20260426_StorageProvider_interface_contract_enables_layer_1_vendor_swap_without_app_redeploys>,
  I6<production_grade_quality>
]
===END===
"""

    @pytest.mark.asyncio
    async def test_write_tool_emits_annotation_too_long_in_corrections(self, tmp_path):
        """WriteTool must include W_ANNOTATION_TOO_LONG in corrections for oversized annotations."""
        tool = WriteTool()
        target = str(tmp_path / "test.oct.md")
        result = await tool.execute(
            target_path=target,
            content=self.FIXTURE_WITH_LONG_ANNOTATION,
        )
        corrections = result.get("corrections", [])
        codes = [c["code"] for c in corrections]
        assert "W_ANNOTATION_TOO_LONG" in codes

    @pytest.mark.asyncio
    async def test_write_tool_no_error_on_long_annotation(self, tmp_path):
        """W_ANNOTATION_TOO_LONG must be non-blocking — no errors in envelope."""
        tool = WriteTool()
        target = str(tmp_path / "test.oct.md")
        result = await tool.execute(
            target_path=target,
            content=self.FIXTURE_WITH_LONG_ANNOTATION,
        )
        # Must not be an error response — file should be written
        assert result.get("status") != "error"
        errors = result.get("errors", [])
        assert not any(e.get("code") == "W_ANNOTATION_TOO_LONG" for e in errors)

    @pytest.mark.asyncio
    async def test_write_tool_no_warning_for_clean_annotations(self, tmp_path):
        """No W_ANNOTATION_TOO_LONG correction for documents with clean annotations."""
        content = """\
===CLEAN_TEST===
META:
  TYPE::TEST
ARCHETYPES::[HEPHAESTUS<implementation_craft>,ATLAS<structural_foundation>]
===END===
"""
        tool = WriteTool()
        target = str(tmp_path / "clean.oct.md")
        result = await tool.execute(
            target_path=target,
            content=content,
        )
        corrections = result.get("corrections", [])
        codes = [c["code"] for c in corrections]
        assert "W_ANNOTATION_TOO_LONG" not in codes
