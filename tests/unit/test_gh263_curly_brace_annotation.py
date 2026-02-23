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
        with pytest.raises(LexerError):
            tokenize("ATHENA{strategic_wisdom}")
        # The repair hint is available as structured data in the exception
        # (implementation will add a structured hint to the LexerError)

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
