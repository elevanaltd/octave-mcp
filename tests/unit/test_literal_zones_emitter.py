"""Tests for literal zone emitter support (T08).

Issue #235: Verifies emit_value() and emit_assignment() for LiteralZoneValue,
including round-trip fidelity with the parser.

GH#346: Tests for literal zone fence indentation in emit_meta().
"""

from octave_mcp.core.ast_nodes import Assignment, LiteralZoneValue
from octave_mcp.core.emitter import emit, emit_assignment, emit_meta, emit_value
from octave_mcp.core.parser import parse


class TestEmitValueLiteralZone:
    """emit_value() for LiteralZoneValue."""

    def test_simple_literal_zone(self):
        """emit_value produces correct string for simple literal zone."""
        value = LiteralZoneValue(content="hello", info_tag="python", fence_marker="```")
        result = emit_value(value)
        assert result == "```python\nhello\n```"

    def test_no_info_tag(self):
        """emit_value with no info tag omits tag."""
        value = LiteralZoneValue(content="hello", info_tag=None, fence_marker="```")
        result = emit_value(value)
        assert result == "```\nhello\n```"

    def test_empty_literal_zone(self):
        """emit_value for empty literal zone."""
        value = LiteralZoneValue(content="", info_tag=None, fence_marker="```")
        result = emit_value(value)
        assert result == "```\n```"

    def test_four_backtick_fence(self):
        """emit_value with 4-backtick fence."""
        value = LiteralZoneValue(content="hello", info_tag=None, fence_marker="````")
        result = emit_value(value)
        assert result == "````\nhello\n````"

    def test_content_with_trailing_newline(self):
        """Content already ending with newline: no extra newline added."""
        value = LiteralZoneValue(content="hello\n", info_tag=None, fence_marker="```")
        result = emit_value(value)
        assert result == "```\nhello\n```"

    def test_content_without_trailing_newline(self):
        """Content without trailing newline: newline added before closing fence."""
        value = LiteralZoneValue(content="hello", info_tag=None, fence_marker="```")
        result = emit_value(value)
        assert result == "```\nhello\n```"

    def test_multiline_content(self):
        """Multiline content emitted correctly."""
        value = LiteralZoneValue(content="line1\nline2\nline3", info_tag="python", fence_marker="```")
        result = emit_value(value)
        assert result == "```python\nline1\nline2\nline3\n```"

    def test_tabs_in_content_preserved(self):
        """Tabs in content survive emission unchanged."""
        value = LiteralZoneValue(content="\tindented\twith\ttabs", fence_marker="```")
        result = emit_value(value)
        assert "\tindented\twith\ttabs" in result

    def test_non_nfc_characters_in_content_preserved(self):
        """Non-NFC characters in content survive emission unchanged."""
        decomposed = "e\u0301"
        value = LiteralZoneValue(content=decomposed, fence_marker="```")
        result = emit_value(value)
        assert decomposed in result


class TestEmitAssignmentLiteralZone:
    """emit_assignment() for assignments with LiteralZoneValue."""

    def test_assignment_indent_0(self):
        """Assignment at indent=0 produces correct format."""
        assignment = Assignment(
            key="CODE", value=LiteralZoneValue(content="hello", info_tag="python", fence_marker="```")
        )
        result = emit_assignment(assignment, indent=0)
        assert result == "CODE::\n```python\nhello\n```"

    def test_assignment_indent_1(self):
        """Assignment at indent=1: fence markers get indent, content is verbatim."""
        assignment = Assignment(
            key="CODE", value=LiteralZoneValue(content="hello", info_tag="python", fence_marker="```")
        )
        result = emit_assignment(assignment, indent=1)
        # Fence markers get 2-space indent; content is verbatim (no indent added)
        assert result == "  CODE::\n  ```python\nhello\n  ```"

    def test_assignment_indent_2(self):
        """Assignment at indent=2: deeper indent on fences."""
        assignment = Assignment(key="CODE", value=LiteralZoneValue(content="hello", info_tag=None, fence_marker="```"))
        result = emit_assignment(assignment, indent=2)
        assert result == "    CODE::\n    ```\nhello\n    ```"

    def test_assignment_empty_literal_zone(self):
        """Assignment with empty literal zone."""
        assignment = Assignment(key="KEY", value=LiteralZoneValue(content="", info_tag=None, fence_marker="```"))
        result = emit_assignment(assignment, indent=0)
        assert result == "KEY::\n```\n```"

    def test_assignment_multiline_content_verbatim(self):
        """Content lines are NOT indented, only fence markers are."""
        assignment = Assignment(
            key="CODE", value=LiteralZoneValue(content="line1\n  line2\n    line3", info_tag=None, fence_marker="```")
        )
        result = emit_assignment(assignment, indent=1)
        lines = result.split("\n")
        assert lines[0] == "  CODE::"  # key indented
        assert lines[1] == "  ```"  # opening fence indented
        assert lines[2] == "line1"  # content verbatim
        assert lines[3] == "  line2"  # content verbatim (its own indent)
        assert lines[4] == "    line3"  # content verbatim (its own indent)
        assert lines[5] == "  ```"  # closing fence indented


class TestRoundTrip:
    """Round-trip: parse -> emit -> parse produces identical AST."""

    def _round_trip_check(self, content: str):
        """Parse content, emit, parse again, and compare literal zone values."""
        doc1 = parse(content)
        emitted = emit(doc1)
        doc2 = parse(emitted)

        # Compare literal zone values
        for s1, s2 in zip(doc1.sections, doc2.sections, strict=True):
            if isinstance(s1, Assignment) and isinstance(s1.value, LiteralZoneValue):
                assert isinstance(s2, Assignment)
                v1 = s1.value
                v2 = s2.value
                assert isinstance(v2, LiteralZoneValue)
                assert v1.content == v2.content
                assert v1.info_tag == v2.info_tag
                assert v1.fence_marker == v2.fence_marker

    def test_round_trip_simple(self):
        """Simple literal zone round-trips correctly."""
        self._round_trip_check("===DOC===\nCODE::\n```python\nhello\n```\n===END===")

    def test_round_trip_empty(self):
        """Empty literal zone round-trips correctly."""
        self._round_trip_check("===DOC===\nKEY::\n```\n```\n===END===")

    def test_round_trip_with_info_tag(self):
        """Literal zone with info tag round-trips correctly."""
        self._round_trip_check("===DOC===\nCODE::\n```json\n{}\n```\n===END===")

    def test_round_trip_tabs_preserved(self):
        """Tabs in content survive round-trip."""
        content = "===DOC===\nKEY::\n```\n\tindented\twith\ttabs\n```\n===END==="
        doc1 = parse(content)
        emitted = emit(doc1)
        doc2 = parse(emitted)
        v1 = doc1.sections[0].value
        v2 = doc2.sections[0].value
        assert isinstance(v1, LiteralZoneValue)
        assert isinstance(v2, LiteralZoneValue)
        assert v1.content == v2.content
        assert "\t" in v2.content

    def test_round_trip_non_nfc_preserved(self):
        """Non-NFC characters in content survive round-trip."""
        decomposed = "e\u0301"
        content = f"===DOC===\nKEY::\n```\n{decomposed}\n```\n===END==="
        doc1 = parse(content)
        emitted = emit(doc1)
        doc2 = parse(emitted)
        v1 = doc1.sections[0].value
        v2 = doc2.sections[0].value
        assert isinstance(v1, LiteralZoneValue)
        assert isinstance(v2, LiteralZoneValue)
        assert v1.content == v2.content
        assert v2.content == decomposed

    def test_round_trip_multiline(self):
        """Multiline content round-trips correctly."""
        self._round_trip_check("===DOC===\nCODE::\n```python\nline1\nline2\nline3\n```\n===END===")

    def test_round_trip_multiple_zones(self):
        """Multiple literal zones in one document round-trip correctly."""
        content = "===DOC===\n" "CODE1::\n```python\nhello\n```\n" "CODE2::\n```json\n{}\n```\n" "===END==="
        self._round_trip_check(content)

    def test_round_trip_invariant(self):
        """Formal round-trip invariant: parse(emit(parse(D))) == parse(D)."""
        content = "===DOC===\nCODE::\n```python\ndef hello():\n    pass\n```\n===END==="
        doc1 = parse(content)
        emitted1 = emit(doc1)
        doc2 = parse(emitted1)
        emitted2 = emit(doc2)
        doc3 = parse(emitted2)

        # Compare doc2 and doc3 literal zones (emit is idempotent after first parse)
        for s2, s3 in zip(doc2.sections, doc3.sections, strict=True):
            if isinstance(s2, Assignment) and isinstance(s2.value, LiteralZoneValue):
                assert isinstance(s3, Assignment)
                assert isinstance(s3.value, LiteralZoneValue)
                assert s2.value.content == s3.value.content
                assert s2.value.info_tag == s3.value.info_tag
                assert s2.value.fence_marker == s3.value.fence_marker


class TestEmitMetaLiteralZone:
    """GH#346: emit_meta() for META fields with LiteralZoneValue.

    The emitter must produce valid OCTAVE when META contains literal zone
    values. The fence markers must be on their own lines (not inline with
    the key) and opening/closing fences must have matching indentation.
    """

    def test_meta_literal_zone_fence_indentation_matches(self):
        """GH#346: Opening and closing fences in META must have matching indent.

        The emitter must not produce inline fences (KEY::```), which are
        invalid OCTAVE. Instead, the key should be on its own line, followed
        by properly indented opening and closing fences.
        """
        meta = {"CONTRACT": LiteralZoneValue(content="hello", info_tag="octave", fence_marker="```")}
        result = emit_meta(meta)
        lines = result.split("\n")

        # Find fence lines
        fence_lines = [(i, line) for i, line in enumerate(lines) if "```" in line]
        assert len(fence_lines) == 2, f"Expected 2 fence lines, got {len(fence_lines)}: {fence_lines}"

        open_idx, open_line = fence_lines[0]
        close_idx, close_line = fence_lines[1]

        # Opening fence must NOT be inline with key (KEY::``` is invalid OCTAVE)
        assert "::" not in open_line, f"Opening fence must not be inline with key. Got: {open_line!r}"

        # Both fences must have the same indentation
        open_indent = len(open_line) - len(open_line.lstrip())
        close_indent = len(close_line) - len(close_line.lstrip())
        assert open_indent == close_indent, (
            f"Fence indentation mismatch: opening={open_indent} spaces, "
            f"closing={close_indent} spaces. "
            f"Opening: {open_line!r}, Closing: {close_line!r}"
        )

    def test_meta_literal_zone_round_trip(self):
        """GH#346: META with literal zone must round-trip through parse/emit.

        parse(emit(doc)) must not raise -- the emitted output must be
        valid OCTAVE that can be re-parsed.
        """
        content = (
            "===DOC===\n"
            "META:\n"
            "  TYPE::TEST\n"
            '  VERSION::"1.0"\n'
            "  CONTRACT::\n"
            "  ```octave\n"
            "hello world\n"
            "  ```\n"
            "===END==="
        )
        doc1 = parse(content)
        emitted = emit(doc1)

        # The emitted output must be parseable (not produce LexerError)
        doc2 = parse(emitted)

        # The literal zone content must survive the round-trip
        contract1 = doc1.meta["CONTRACT"]
        contract2 = doc2.meta["CONTRACT"]
        assert isinstance(contract1, LiteralZoneValue)
        assert isinstance(contract2, LiteralZoneValue)
        assert contract1.content == contract2.content
        assert contract1.info_tag == contract2.info_tag
        assert contract1.fence_marker == contract2.fence_marker

    def test_meta_nested_literal_zone_fence_indentation_matches(self):
        """GH#346: Nested dict META with literal zone has matching fence indent."""
        meta = {"NESTED": {"CODE": LiteralZoneValue(content="hello", info_tag="python", fence_marker="```")}}
        result = emit_meta(meta)
        lines = result.split("\n")

        # Find fence lines
        fence_lines = [(i, line) for i, line in enumerate(lines) if "```" in line]
        assert len(fence_lines) == 2, f"Expected 2 fence lines, got {len(fence_lines)}: {fence_lines}"

        open_idx, open_line = fence_lines[0]
        close_idx, close_line = fence_lines[1]

        # Opening fence must NOT be inline with key
        assert "::" not in open_line, f"Opening fence must not be inline with key. Got: {open_line!r}"

        # Both fences must have the same indentation
        open_indent = len(open_line) - len(open_line.lstrip())
        close_indent = len(close_line) - len(close_line.lstrip())
        assert open_indent == close_indent, (
            f"Fence indentation mismatch: opening={open_indent} spaces, "
            f"closing={close_indent} spaces. "
            f"Opening: {open_line!r}, Closing: {close_line!r}"
        )

    def test_meta_literal_zone_empty_content(self):
        """GH#346: Empty literal zone in META emits correctly."""
        meta = {"CODE": LiteralZoneValue(content="", info_tag=None, fence_marker="```")}
        result = emit_meta(meta)
        lines = result.split("\n")

        fence_lines = [(i, line) for i, line in enumerate(lines) if "```" in line]
        assert len(fence_lines) == 2

        open_indent = len(fence_lines[0][1]) - len(fence_lines[0][1].lstrip())
        close_indent = len(fence_lines[1][1]) - len(fence_lines[1][1].lstrip())
        assert open_indent == close_indent
