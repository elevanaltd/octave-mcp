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
from octave_mcp.mcp.write import WriteTool, _all_section_marks_quoted, _auto_quote_section_refs_in_values


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


class TestIssue1R2BackslashParityInScanner:
    """Fix #1 round 2: Backslash parity in escape-aware scanner.

    PR#361 rework round 2: The single-character backslash check fails for
    even-count backslashes before a quote mark. For example, ``\\\\\"`` has
    two escaped backslashes followed by an unescaped quote, but the scanner
    sees ``line[i-1] == '\\\\'`` and incorrectly treats the quote as escaped.

    The fix counts consecutive backslashes: even count = unescaped quote,
    odd count = escaped quote.
    """

    def test_four_backslashes_then_quote_is_unescaped(self):
        r"""4 backslashes + quote = 2 escaped backslashes + unescaped quote.

        Input: KEY::"\\\\" §1::SECTION"
        The 4 backslashes are 2 escaped backslash pairs.
        The quote after them is NOT escaped — it closes the string.
        Therefore §1::SECTION is OUTSIDE quotes → should return False.
        """
        # Python string: KEY::"\\\\" §1::SECTION"
        # Raw content:   KEY::"\\" §1::SECTION"
        # The value part after KEY:: is: "\\" §1::SECTION"
        line = 'KEY::"\\\\\\\\" §1::SECTION"'
        # After KEY:: the value is: "\\\\" §1::SECTION"
        # In the actual string bytes: " \\ \\ " space § 1 :: S E C T I O N "
        # The first " opens quote, \\\\ is two escaped backslashes, " closes quote
        # Then §1::SECTION is OUTSIDE quotes
        value_part = line[len("KEY::") :]
        assert _all_section_marks_quoted(value_part) is False

    def test_two_backslashes_then_quote_is_unescaped(self):
        r"""2 backslashes + quote = 1 escaped backslash + unescaped quote.

        Input: KEY::"\\" §1::SECTION"
        The 2 backslashes are 1 escaped backslash pair.
        The quote after them is NOT escaped — it closes the string.
        Therefore §1::SECTION is OUTSIDE quotes → should return False.
        """
        line = 'KEY::"\\\\" §1::SECTION"'
        value_part = line[len("KEY::") :]
        assert _all_section_marks_quoted(value_part) is False

    def test_simple_escaped_quote_section_inside(self):
        r"""Simple escaped quote: § inside quotes should return True.

        Input: KEY::"He said \"§1::SECTION\""
        The \" is an escaped quote inside the string.
        §1::SECTION is INSIDE the outer quotes → should return True.
        """
        # KEY::"He said \"§1::SECTION\""
        line = r'KEY::"He said \"§1::SECTION\""'
        value_part = line[len("KEY::") :]
        assert _all_section_marks_quoted(value_part) is True

    def test_single_escaped_backslash_then_quote_outside(self):
        r"""Single escaped quote followed by § outside.

        Input: KEY::"\\" §1::SECTION
        The \\ is an escaped backslash. The " after it closes the string.
        §1::SECTION is OUTSIDE quotes → should return False.
        """
        # In Python string: KEY::"\\" §1::SECTION
        # The value_part is: "\\" §1::SECTION
        # Bytes: " \ \ " space § ...
        # First " opens, \\ is escaped backslash, " closes → § outside
        line = 'KEY::"\\\\" §1::SECTION'
        value_part = line[len("KEY::") :]
        assert _all_section_marks_quoted(value_part) is False

    def test_auto_quote_mutation_with_backslash_parity(self):
        r"""_auto_quote_section_refs_in_values must also handle backslash parity.

        When the value contains "\\\\" followed by §, the mutation function
        must recognize that § is outside quotes and auto-quote it.
        """
        # Line: KEY::"\\" §1::SECTION
        # Value portion: "\\" §1::SECTION
        # The \\ is an escaped backslash, " closes the string, § is outside
        content = '  KEY::"\\\\" §1::SECTION'
        transformed, corrections = _auto_quote_section_refs_in_values(content)
        # The § reference should have been auto-quoted
        assert len(corrections) >= 1, (
            f"Expected auto-quote correction for unquoted § after escaped backslash. "
            f"Input: {content!r}, Output: {transformed!r}"
        )
        assert "§1::SECTION" in transformed

    def test_auto_quote_skips_section_inside_escaped_quotes(self):
        r"""_auto_quote_section_refs_in_values must not quote § inside escaped quotes.

        When the value contains \"§1::SECTION\" (escaped quotes inside outer
        quotes), the § is inside the string and must NOT be auto-quoted.
        """
        content = r'  KEY::"He said \"§1::SECTION\""'
        transformed, corrections = _auto_quote_section_refs_in_values(content)
        # No corrections expected — § is already inside quotes
        section_corrections = [c for c in corrections if "§" in c.get("message", "")]
        assert len(section_corrections) == 0, (
            f"Should not auto-quote § inside escaped-quote string. " f"Corrections: {section_corrections}"
        )


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


class TestIssue7SlashInSectionContainingToken:
    """Fix #7: _SECTION_CONTAINING_TOKEN_RE must include slash in character class.

    CodeRabbit finding on PR#361: The regex ``(?:[\\w.\\-]|§|::)+`` stops at ``/``,
    so a token like ``§1::NAME/SUBNAME`` gets split at the slash.  The auto-quote
    scanner rewrites it as ``"§1::NAME"/SUBNAME`` instead of ``"§1::NAME/SUBNAME"``.

    The fix adds ``/`` to the character class so the full token is captured.
    """

    def test_slash_in_section_ref_quoted_as_complete_token(self):
        """A section reference containing a slash must be quoted in its entirety."""
        content = "KEY::§1::NAME/SUBNAME"
        transformed, corrections = _auto_quote_section_refs_in_values(content)
        assert '"§1::NAME/SUBNAME"' in transformed, f"Expected full token quoted as one unit, got: {transformed!r}"
        assert corrections, "Expected a correction record for auto-quoting"

    def test_slash_in_compound_section_ref(self):
        """Compound section refs with slashes should be fully captured."""
        content = "REFS::§2::CAPS/ADVISORY through §2::CAPS/EXECUTION"
        transformed, corrections = _auto_quote_section_refs_in_values(content)
        assert (
            '"§2::CAPS/ADVISORY"' in transformed
        ), f"Expected §2::CAPS/ADVISORY quoted as one unit, got: {transformed!r}"
        assert (
            '"§2::CAPS/EXECUTION"' in transformed
        ), f"Expected §2::CAPS/EXECUTION quoted as one unit, got: {transformed!r}"


class TestDoubleSlashCommentNotSwallowedByTokenRegex:
    """Cubic finding on PR#361: _SECTION_CONTAINING_TOKEN_RE swallows // comments.

    The regex ``(?:[\\w./\\-]|§|::)+`` includes ``/`` in its character class,
    which means ``§5::ANCHOR//comment_text`` gets matched as one token --
    turning comment text into quoted data.

    The fix uses a negative lookahead ``/(?!/)`` so that single ``/`` still
    works in paths but ``//`` (comment delimiter) stops the token match.
    """

    def test_double_slash_comment_not_included_in_quoted_token(self):
        """§5::ANCHOR//comment should quote only §5::ANCHOR, not the comment."""
        content = "KEY::§5::ANCHOR//comment_text"
        transformed, corrections = _auto_quote_section_refs_in_values(content)
        assert '"§5::ANCHOR"' in transformed, f"Expected only §5::ANCHOR quoted, got: {transformed!r}"
        assert (
            "//comment_text" in transformed
        ), f"Expected //comment_text preserved outside quotes, got: {transformed!r}"
        assert (
            '"§5::ANCHOR//comment_text"' not in transformed
        ), f"Comment text must NOT be swallowed into the quoted token, got: {transformed!r}"

    def test_single_slash_still_works_in_section_path(self):
        """§5::path/to/thing should still capture the full path with single slashes."""
        content = "KEY::§5::path/to/thing"
        transformed, corrections = _auto_quote_section_refs_in_values(content)
        assert (
            '"§5::path/to/thing"' in transformed
        ), f"Expected full path with single slashes quoted, got: {transformed!r}"
