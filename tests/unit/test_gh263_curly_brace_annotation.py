"""Tests for GH#263: W_REPAIR_CANDIDATE hint for curly-brace annotations.

When NAME{qualifier} is encountered in OCTAVE content:
- In strict mode: E005 error is raised, plus a W_REPAIR_CANDIDATE repair hint
- In lenient mode: auto-repair {} -> <> and continue tokenizing

TDD RED phase: these tests should FAIL before implementation.
"""

import pytest

from octave_mcp.core.lexer import LexerError, TokenType, tokenize
from octave_mcp.mcp.validate import ValidateTool
from octave_mcp.mcp.write import WriteTool


class TestLexerCurlyBraceDetection:
    """Test lexer detection of NAME{qualifier} patterns."""

    def test_curly_brace_after_identifier_raises_e005(self):
        """NAME{qualifier} in strict mode must still raise E005."""
        with pytest.raises(LexerError) as exc_info:
            tokenize("ATHENA{strategic_wisdom}")
        assert exc_info.value.error_code == "E005"

    def test_curly_brace_emits_repair_candidate_in_repairs(self):
        """NAME{qualifier} should include W_REPAIR_CANDIDATE in repairs list
        even when it raises E005, to guide the user toward the correct syntax."""
        with pytest.raises(LexerError) as exc_info:
            tokenize("ATHENA{strategic_wisdom}")
        error = exc_info.value
        # The W_REPAIR_CANDIDATE hint must be present in the error message
        assert "W_REPAIR_CANDIDATE" in str(error)
        assert "ATHENA<strategic_wisdom>" in str(error)

    def test_curly_brace_repair_candidate_has_original_and_suggested(self):
        """W_REPAIR_CANDIDATE should include original and suggested syntax."""
        with pytest.raises(LexerError) as exc_info:
            tokenize("NAME{qualifier}")
        error = exc_info.value
        # The error message should mention the correct syntax
        assert "<" in str(error) or "angle" in str(error).lower() or "W_REPAIR_CANDIDATE" in str(error)

    def test_curly_brace_in_assignment_value(self):
        """NAME{qualifier} as assignment value should detect curly brace pattern."""
        with pytest.raises(LexerError) as exc_info:
            tokenize("ARCHETYPE::ATHENA{strategic_wisdom}")
        assert exc_info.value.error_code == "E005"
        assert "W_REPAIR_CANDIDATE" in str(exc_info.value) or "<" in str(exc_info.value)


class TestLexerLenientCurlyBraceRepair:
    """Test lenient-mode auto-repair of {} -> <> in tokenizer."""

    def test_lenient_repairs_curly_to_angle_bracket(self):
        """In lenient mode, NAME{qualifier} should be repaired to NAME<qualifier>."""
        tokens, repairs = tokenize("ATHENA{strategic_wisdom}", lenient=True)
        identifiers = [t for t in tokens if t.type == TokenType.IDENTIFIER]
        assert len(identifiers) == 1
        assert identifiers[0].value == "ATHENA<strategic_wisdom>"

    def test_lenient_repair_logged_in_repairs_list(self):
        """Lenient repair should be logged with W_REPAIR_CANDIDATE code."""
        tokens, repairs = tokenize("ATHENA{strategic_wisdom}", lenient=True)
        repair_candidates = [r for r in repairs if r.get("type") == "repair_candidate"]
        assert len(repair_candidates) >= 1
        rc = repair_candidates[0]
        assert rc["original"] == "ATHENA{strategic_wisdom}"
        assert rc["repaired"] == "ATHENA<strategic_wisdom>"
        assert "W_REPAIR_CANDIDATE" in rc.get("message", "")

    def test_lenient_repairs_multiple_curly_annotations(self):
        """Multiple NAME{qualifier} patterns should all be repaired."""
        tokens, repairs = tokenize("[ATHENA{strategic_wisdom},HERMES{coordination}]", lenient=True)
        identifiers = [t for t in tokens if t.type == TokenType.IDENTIFIER]
        assert len(identifiers) == 2
        assert identifiers[0].value == "ATHENA<strategic_wisdom>"
        assert identifiers[1].value == "HERMES<coordination>"

    def test_lenient_repair_in_assignment(self):
        """Lenient mode repairs NAME{qualifier} in KEY::VALUE context."""
        tokens, repairs = tokenize("ARCHETYPE::ATHENA{strict}", lenient=True)
        identifiers = [t for t in tokens if t.type == TokenType.IDENTIFIER]
        assert identifiers[1].value == "ATHENA<strict>"

    def test_standalone_curly_brace_not_repaired(self):
        """Standalone { not preceded by identifier should still error in lenient mode."""
        with pytest.raises(LexerError):
            tokenize("{ standalone }", lenient=True)


class TestValidateToolCurlyBrace:
    """Test octave_validate surfaces W_REPAIR_CANDIDATE warning."""

    @pytest.fixture
    def validate_tool(self):
        return ValidateTool()

    @pytest.mark.asyncio
    async def test_validate_surfaces_repair_candidate_warning(self, validate_tool):
        """octave_validate on NAME{qualifier} should surface W_REPAIR_CANDIDATE in warnings."""
        content = '===TEST===\nMETA:\n  TYPE::"EXAMPLE"\nARCHETYPE::ATHENA{strategic_wisdom}\n===END==='
        result = await validate_tool.execute(content=content, schema="META")
        # Should have error status (E005 from tokenization) but also surface the hint
        assert result["status"] == "error"
        # Check that errors contain the repair candidate information
        errors = result.get("errors", [])
        assert any("E_TOKENIZE" in e.get("code", "") for e in errors)
        # The error message should mention the W_REPAIR_CANDIDATE hint
        error_messages = " ".join(e.get("message", "") for e in errors)
        assert "W_REPAIR_CANDIDATE" in error_messages or "NAME<" in error_messages


class TestWriteToolCurlyBrace:
    """Test octave_write handles curly-brace annotations per lenient/strict mode."""

    @pytest.fixture
    def write_tool(self):
        return WriteTool()

    @pytest.mark.asyncio
    async def test_write_strict_mode_retains_e005(self, write_tool, tmp_path):
        """octave_write(lenient=false) should retain E005 for NAME{qualifier}."""
        target = str(tmp_path / "test.oct.md")
        content = '===TEST===\nMETA:\n  TYPE::"EXAMPLE"\nARCHETYPE::ATHENA{strategic_wisdom}\n===END==='
        result = await write_tool.execute(target_path=target, content=content, lenient=False)
        assert result["status"] == "error"
        errors = result.get("errors", [])
        assert any("E_TOKENIZE" in e.get("code", "") or "E005" in e.get("message", "") for e in errors)

    @pytest.mark.asyncio
    async def test_write_lenient_repairs_curly_and_logs_correction(self, write_tool, tmp_path):
        """octave_write(lenient=true) should repair {} -> <> and log correction."""
        target = str(tmp_path / "test.oct.md")
        content = '===TEST===\nMETA:\n  TYPE::"EXAMPLE"\nARCHETYPE::ATHENA{strategic_wisdom}\n===END==='
        result = await write_tool.execute(target_path=target, content=content, lenient=True)
        assert result["status"] == "success"
        # Should log the repair in corrections (I4 auditability)
        corrections = result.get("corrections", [])
        repair_corrections = [c for c in corrections if "W_REPAIR_CANDIDATE" in c.get("code", "")]
        assert len(repair_corrections) >= 1
        rc = repair_corrections[0]
        assert rc.get("before") == "ATHENA{strategic_wisdom}"
        assert rc.get("after") == "ATHENA<strategic_wisdom>"

    @pytest.mark.asyncio
    async def test_write_lenient_canonical_uses_angle_brackets(self, write_tool, tmp_path):
        """Lenient mode canonical output should use <> not {}."""
        target = str(tmp_path / "test.oct.md")
        content = '===TEST===\nMETA:\n  TYPE::"EXAMPLE"\nARCHETYPE::ATHENA{strategic_wisdom}\n===END==='
        result = await write_tool.execute(target_path=target, content=content, lenient=True)
        assert result["status"] == "success"
        # Read the written file to verify canonical form uses <>
        with open(target, encoding="utf-8") as f:
            written = f.read()
        assert "ATHENA<strategic_wisdom>" in written
        assert "ATHENA{strategic_wisdom}" not in written


class TestPlainTextCurlyBracePreservation:
    """GH#263 rework: plain text with curly braces must NOT be repaired.

    When content has no OCTAVE structure (no ::, no ===...=== envelopes, no META:),
    it gets RAW-wrapped. Curly-brace repair must only apply to confirmed OCTAVE DSL,
    not plain text. Otherwise FOO{bar} in prose becomes FOO<bar>.
    """

    @pytest.fixture
    def write_tool(self):
        return WriteTool()

    @pytest.mark.asyncio
    async def test_plain_text_curly_braces_not_repaired(self, write_tool, tmp_path):
        """Plain text content should not have curly braces repaired."""
        target = str(tmp_path / "test.oct.md")
        content = "This prose has FOO{bar} and should stay as-is."
        result = await write_tool.execute(target_path=target, content=content, lenient=True)
        assert result["status"] == "success"
        # The content should be RAW-wrapped without FOO{bar} being changed
        corrections = result.get("corrections", [])
        repair_corrections = [c for c in corrections if "W_REPAIR_CANDIDATE" in c.get("code", "")]
        assert len(repair_corrections) == 0, "Plain text should NOT trigger curly-brace repair"
        # Read the written file to verify FOO{bar} is preserved
        with open(target, encoding="utf-8") as f:
            written = f.read()
        assert "FOO{bar}" in written, "Plain text FOO{bar} must be preserved, not rewritten to FOO<bar>"
        assert "FOO<bar>" not in written, "FOO{bar} must NOT be rewritten to FOO<bar> in plain text"

    @pytest.mark.asyncio
    async def test_octave_content_curly_braces_still_repaired(self, write_tool, tmp_path):
        """Confirmed OCTAVE DSL content should still have curly braces repaired."""
        target = str(tmp_path / "test.oct.md")
        content = '===TEST===\nMETA:\n  TYPE::"EXAMPLE"\nARCHETYPE::ATHENA{strategic_wisdom}\n===END==='
        result = await write_tool.execute(target_path=target, content=content, lenient=True)
        assert result["status"] == "success"
        corrections = result.get("corrections", [])
        repair_corrections = [c for c in corrections if "W_REPAIR_CANDIDATE" in c.get("code", "")]
        assert len(repair_corrections) >= 1, "OCTAVE DSL should still trigger curly-brace repair"


class TestExistingAnnotationTests:
    """Verify existing angle-bracket annotation tests still pass."""

    def test_existing_angle_bracket_annotation_unchanged(self):
        """Standard NAME<qualifier> still works as before."""
        tokens, _ = tokenize("ATHENA<strategic_wisdom>")
        identifiers = [t for t in tokens if t.type == TokenType.IDENTIFIER]
        assert len(identifiers) == 1
        assert identifiers[0].value == "ATHENA<strategic_wisdom>"

    def test_existing_tension_operator_unchanged(self):
        """<-> tension operator must not be broken."""
        tokens, _ = tokenize("A<->B")
        tension_tokens = [t for t in tokens if t.type == TokenType.TENSION]
        assert len(tension_tokens) == 1

    def test_existing_standalone_angle_bracket_errors(self):
        """Standalone < outside annotation should still error."""
        with pytest.raises(LexerError):
            tokenize("5 < 10")


class TestRepairZoneBoundaries:
    """GH#263 rework: _repair_curly_brace_annotations must respect zone boundaries.

    The regex pre-processor must NOT mutate content inside:
    - Quoted strings (Zone 2 preserving container)
    - Literal zones (Zone 3 explicit literal zones)
    - Comments

    This ensures I1 (syntactic fidelity) and literal zone opacity.
    """

    @pytest.fixture
    def write_tool(self):
        return WriteTool()

    def test_repair_does_not_mutate_quoted_strings(self, write_tool):
        """Curly-brace patterns inside quoted values must NOT be rewritten.

        DESC::"ATHENA{strategic_wisdom}" should preserve the quoted content verbatim.
        """
        content = 'DESC::"ATHENA{strategic_wisdom}"'
        repaired, corrections = write_tool._repair_curly_brace_annotations(content)
        # The quoted string must remain untouched
        assert 'DESC::"ATHENA{strategic_wisdom}"' in repaired
        # No corrections should be generated for quoted content
        assert len(corrections) == 0

    def test_repair_does_not_mutate_literal_zones(self, write_tool):
        """Curly-brace patterns inside literal zones (fenced blocks) must NOT be rewritten.

        Content between ``` fences is Zone 3 and must be opaque to normalization.
        """
        content = (
            "EXAMPLE::\n" "```\n" "print('ATHENA{strategic_wisdom}')\n" "```\n" "ARCHETYPE::ATHENA{strategic_wisdom}"
        )
        repaired, corrections = write_tool._repair_curly_brace_annotations(content)
        # The literal zone content must remain untouched
        assert "print('ATHENA{strategic_wisdom}')" in repaired
        # But the Zone 1 content outside fences SHOULD be repaired
        assert "ARCHETYPE::ATHENA<strategic_wisdom>" in repaired
        # Only one correction (for the Zone 1 content)
        assert len(corrections) == 1

    def test_repair_does_not_mutate_comments(self, write_tool):
        """Curly-brace patterns inside comments must NOT be rewritten.

        // ATHENA{strategic_wisdom} is a comment and should not be mutated.
        """
        content = "// ATHENA{strategic_wisdom}\nARCHETYPE::ATHENA{strategic_wisdom}"
        repaired, corrections = write_tool._repair_curly_brace_annotations(content)
        # Comment content must remain untouched
        assert "// ATHENA{strategic_wisdom}" in repaired
        # Zone 1 content SHOULD be repaired
        assert "ARCHETYPE::ATHENA<strategic_wisdom>" in repaired
        # Only one correction (for the Zone 1 content)
        assert len(corrections) == 1

    def test_repair_does_not_mutate_multiline_quoted_string(self, write_tool):
        """Double-quoted strings spanning the value after :: must be preserved."""
        content = 'PURPOSE::"Build ATHENA{wisdom} system"\nTYPE::ATHENA{strategic_wisdom}'
        repaired, corrections = write_tool._repair_curly_brace_annotations(content)
        # Quoted value preserved
        assert 'PURPOSE::"Build ATHENA{wisdom} system"' in repaired
        # Unquoted Zone 1 value repaired
        assert "TYPE::ATHENA<strategic_wisdom>" in repaired
        assert len(corrections) == 1

    def test_repair_handles_multiple_literal_zones(self, write_tool):
        """Multiple literal zones should all be protected."""
        content = "NAME::FOO{bar}\n" "```\n" "BAZ{qux}\n" "```\n" "OTHER::AAA{bbb}\n" "```python\n" "CCC{ddd}\n" "```"
        repaired, corrections = write_tool._repair_curly_brace_annotations(content)
        # Zone 1 content repaired
        assert "NAME::FOO<bar>" in repaired
        assert "OTHER::AAA<bbb>" in repaired
        # Literal zone content NOT repaired
        assert "BAZ{qux}" in repaired
        assert "CCC{ddd}" in repaired
        assert len(corrections) == 2

    def test_repair_preserves_zone1_content_correctly(self, write_tool):
        """Zone 1 (normalizing DSL) content with curly braces should still be repaired."""
        content = "ARCHETYPE::ATHENA{strategic_wisdom}\nCOGNITION::LOGOS{reasoning}"
        repaired, corrections = write_tool._repair_curly_brace_annotations(content)
        assert "ATHENA<strategic_wisdom>" in repaired
        assert "LOGOS<reasoning>" in repaired
        assert len(corrections) == 2

    def test_repair_does_not_mutate_escaped_quoted_strings(self, write_tool):
        """Escaped quotes inside strings must not break protection."""
        content = '===TEST===\nDESC::"foo \\"ATHENA{inner}\\" bar"\nTYPE::ATHENA{outer}\n===END==='
        repaired, corrections = write_tool._repair_curly_brace_annotations(content)
        assert "ATHENA{inner}" in repaired, "Escaped quoted content should be preserved"
        assert "ATHENA<outer>" in repaired, "Zone 1 content should still be repaired"

    def test_unicode_annotation_repair_limitation(self, write_tool):
        """Document that the write pre-processor regex does not handle Unicode/emoji identifiers.

        The lexer supports emoji identifiers like emoji{qualifier}, but the write
        pre-processor regex only matches ASCII identifiers. This is an accepted
        limitation since Unicode annotation qualifiers with curly braces are
        extremely rare in practice.
        """
        # Emoji identifier with curly brace should NOT be repaired by the pre-processor
        # (it will be handled by the lexer in lenient mode instead)
        content = "\U0001f9e0{alpha}"
        repaired, corrections = write_tool._repair_curly_brace_annotations(content)
        # The pre-processor does not match emoji identifiers - this is accepted
        assert "\U0001f9e0{alpha}" in repaired
        assert len(corrections) == 0
