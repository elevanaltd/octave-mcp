"""Regression tests for PR#361 code review findings.

Six blocking issues identified during code review:
1. Escape-unaware auto-quote scanner (write.py)
2. AST node in JSON payload (parser.py)
3. Strict mode suppression (write.py)
4. Comments lost on numeric key drop (parser.py)
5. Premature warning generation (write.py)
6. Unhandled compiler exceptions in grammar_resources (grammar_resources.py)
"""

import json
import os

import pytest

from octave_mcp.core.ast_nodes import Comment
from octave_mcp.core.parser import parse_with_warnings
from octave_mcp.mcp.write import WriteTool, _all_section_marks_quoted


class TestIssue1EscapeUnawareAutoQuoteScanner:
    """Fix #1: _all_section_marks_quoted must handle escaped quotes.

    When a line contains escaped quotes (\\"), they should NOT toggle
    the in_quote state. A section mark inside an escaped-quote string
    like KEY::"prefix \\"S1::SECTION\\" suffix" is properly quoted.
    """

    def test_escaped_quote_does_not_toggle_state(self):
        r"""Escaped \" inside a quoted string should not toggle in_quote.

        Input: KEY::"prefix \"S1::SECTION\" suffix"
        The S is inside the outer quotes, so should return True.
        """
        line = r'KEY::"prefix \"§1::SECTION\" suffix"'
        # The section mark is inside the outer double-quoted string despite escaped quotes
        assert _all_section_marks_quoted(line) is True

    def test_unescaped_quote_still_toggles(self):
        """Normal unescaped quotes should still toggle state correctly."""
        # Section mark is outside quotes
        line = "KEY::§1::SECTION"
        assert _all_section_marks_quoted(line) is False

        # Section mark is inside quotes
        line = 'KEY::"§1::SECTION"'
        assert _all_section_marks_quoted(line) is True

    def test_escaped_quote_at_start_means_not_opening_quote(self):
        r"""Backslash-escaped quote does not open a quoted region."""
        # \" at position 5 (after KEY::) is an escaped quote, not an opening quote.
        # So the section mark after it is NOT inside quotes.
        line = r"KEY::\"§1::SECTION\""
        assert _all_section_marks_quoted(line) is False

    def test_multiple_escaped_quotes_inside_string(self):
        r"""Multiple escaped quotes inside a quoted string preserve quote state."""
        line = r'KEY::"a \"b\" c \"§2::REF\" d"'
        # The outer " opens at position 5 after KEY::
        # Escaped \" do not close the string
        # Section mark is still inside the outer quotes
        assert _all_section_marks_quoted(line) is True


class TestIssue2ASTNodeInJSONPayload:
    """Fix #2: _try_consume_numeric_key must store string, not AST node.

    The warning dict's "value" field must be a JSON-serializable string,
    not an AST node (e.g., ListValue, Assignment).
    """

    def test_numeric_key_warning_value_is_string(self):
        """Warning value field must be a string, not an AST node."""
        content = """===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
DATA:
  1::"hello world"
===END==="""
        _, warnings = parse_with_warnings(content)
        numeric_warnings = [w for w in warnings if w.get("subtype") == "numeric_key_dropped"]
        assert len(numeric_warnings) >= 1
        # The value must be a string (JSON-serializable), not an AST node
        value = numeric_warnings[0]["value"]
        assert isinstance(value, str), f"Expected str, got {type(value).__name__}: {value}"

    def test_numeric_key_warning_list_value_is_string(self):
        """List values in numeric key warnings must also be strings."""
        content = """===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
DATA:
  1::[a,b,c]
===END==="""
        _, warnings = parse_with_warnings(content)
        numeric_warnings = [w for w in warnings if w.get("subtype") == "numeric_key_dropped"]
        assert len(numeric_warnings) >= 1
        value = numeric_warnings[0]["value"]
        assert isinstance(value, str), f"Expected str, got {type(value).__name__}: {value}"

    def test_numeric_key_warning_is_json_serializable(self):
        """Entire warning dict must be JSON-serializable for all value types."""
        content = """===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
DATA:
  1::[x,y,z]
===END==="""
        _, warnings = parse_with_warnings(content)
        numeric_warnings = [w for w in warnings if w.get("subtype") == "numeric_key_dropped"]
        assert len(numeric_warnings) >= 1
        # This must not raise TypeError (would if AST nodes stored directly)
        serialized = json.dumps(numeric_warnings[0])
        assert serialized  # Non-empty JSON string


class TestIssue3StrictModeSuppression:
    """Fix #3: Strict mode must use strict_structure=True for parsing.

    When lenient=False, parse_with_warnings should be called with
    strict_structure=True to catch structural issues that strict mode
    should report as errors.
    """

    def test_parse_with_warnings_accepts_strict_structure(self):
        """parse_with_warnings must accept strict_structure parameter."""
        content = """===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
===END==="""
        # This call should work without error
        doc, warnings = parse_with_warnings(content, strict_structure=True)
        assert doc is not None

    @pytest.mark.asyncio
    async def test_strict_mode_still_captures_numeric_key_warnings(self):
        """Even in strict mode, numeric key warnings must be captured (I4)."""
        tool = WriteTool()
        result = await tool.execute(
            target_path="/tmp/test_strict_numeric.oct.md",
            content="""===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
DATA:
  1::"Numeric key"
  VALID::"After numeric"
===END===""",
            lenient=False,
            corrections_only=True,
        )
        corrections = result.get("corrections", [])
        numeric_corrections = [c for c in corrections if c.get("code") == "W_NUMERIC_KEY_DROPPED"]
        assert (
            len(numeric_corrections) >= 1
        ), f"Strict mode must still capture numeric key warnings (I4). Got: {corrections}"


class TestIssue4CommentsLostOnNumericKeyDrop:
    """Fix #4: Comments before numeric keys must be preserved.

    When _try_consume_numeric_key handles a numeric key, it sets
    pending_comments = [], causing comments before the key to be
    silently lost (I4 violation).
    """

    def test_comments_before_numeric_key_preserved(self):
        """Comments accumulated before a numeric key must not be lost."""
        content = """===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
DATA:
  // This comment should survive
  1::"Numeric key"
  VALID::"After numeric"
===END==="""
        doc, warnings = parse_with_warnings(content)
        data_block = None
        for section in doc.sections:
            if section.key == "DATA":
                data_block = section
                break
        assert data_block is not None, "DATA block must exist"

        # Check that comment is not silently lost
        has_comment = any(
            isinstance(c, Comment) and "This comment should survive" in c.text for c in data_block.children
        )
        assert has_comment, (
            f"Comment before numeric key was silently lost (I4 violation). "
            f"Children: {[repr(c) for c in data_block.children]}"
        )

    def test_multiple_comments_before_numeric_key(self):
        """Multiple comments before a numeric key must all be preserved."""
        content = """===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
DATA:
  // First comment
  // Second comment
  1::"Numeric key"
  VALID::"After numeric"
===END==="""
        doc, warnings = parse_with_warnings(content)
        data_block = None
        for section in doc.sections:
            if section.key == "DATA":
                data_block = section
                break
        assert data_block is not None

        comment_texts = [c.text for c in data_block.children if isinstance(c, Comment)]
        assert any("First comment" in t for t in comment_texts), f"First comment lost. Found: {comment_texts}"
        assert any("Second comment" in t for t in comment_texts), f"Second comment lost. Found: {comment_texts}"


class TestIssue5PrematureWarningGeneration:
    """Fix #5: result["warnings"] must include schema repair corrections.

    The warnings array is built early from corrections, but schema repair
    logic later appends to result["corrections"]. Unsafe repairs from
    schema validation are excluded from warnings.
    """

    @pytest.mark.asyncio
    async def test_schema_repair_unsafe_corrections_in_warnings(self):
        """Unsafe corrections from any source must appear in result['warnings'].

        All safe=False corrections must be present in warnings, regardless
        of when they were appended to the corrections list.
        """
        tool = WriteTool()
        result = await tool.execute(
            target_path="/tmp/test_premature_warnings.oct.md",
            content="""===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
DATA:
  1::"Numeric key triggers safe=False correction"
===END===""",
            lenient=True,
            corrections_only=True,
        )
        corrections = result.get("corrections", [])
        warnings = result.get("warnings", [])

        # All safe=False corrections must appear in warnings
        unsafe_correction_codes = {c["code"] for c in corrections if c.get("safe") is False}
        warning_codes = {w["code"] for w in warnings}

        for code in unsafe_correction_codes:
            assert code in warning_codes, (
                f"Correction {code} has safe=False but is missing from warnings. "
                f"Corrections: {[c['code'] for c in corrections if not c.get('safe')]}, "
                f"Warnings: {[w['code'] for w in warnings]}"
            )


class TestIssue6UnhandledCompilerExceptions:
    """Fix #6: grammar_resources read_resource must handle compilation errors.

    _compile_grammar calls compiler.compile_schema which can raise
    ValueError. The read_resource handler must catch this and return
    a meaningful error instead of crashing the MCP handler.
    """

    @pytest.fixture(autouse=True)
    def _set_cwd(self, monkeypatch):
        """Ensure CWD is project root for schema search paths."""
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        monkeypatch.chdir(project_root)

    def test_compile_grammar_raises_on_nonexistent_schema(self):
        """_compile_grammar raises ValueError for non-existent schemas."""
        from octave_mcp.mcp.grammar_resources import GrammarResourceProvider

        provider = GrammarResourceProvider()
        with pytest.raises(ValueError, match="not found"):
            provider._compile_grammar("NONEXISTENT_SCHEMA_XYZ")

    @pytest.mark.asyncio
    async def test_read_resource_returns_error_content_on_compilation_failure(self):
        """read_resource must return error content, not crash, when compilation fails.

        When compile_schema raises ValueError for a malformed constraint,
        the handler should catch it and return meaningful error content.
        """

        from pydantic import AnyUrl

        from octave_mcp.mcp.grammar_resources import GrammarResourceProvider

        provider = GrammarResourceProvider()

        # Simulate a compilation error from compiler.compile_schema
        original_compile = provider._compile_grammar

        def failing_compile(schema_name: str) -> str:
            raise ValueError("Invalid constraint pattern in field 'X': bad_regex(")

        provider._compile_grammar = failing_compile  # type: ignore[assignment]

        try:
            result = await provider.read_resource(AnyUrl("octave://grammars/BAD_SCHEMA"))
            # Should return error content rather than crashing
            content = result[0].content
            assert "error" in content.lower() or "Error" in content
        except ValueError:
            # Before fix: ValueError propagates unhandled.
            # After fix: should NOT reach here.
            pytest.fail("read_resource raised unhandled ValueError instead of " "returning error content")
        finally:
            provider._compile_grammar = original_compile  # type: ignore[assignment]
