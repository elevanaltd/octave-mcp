"""Tests for comment preservation (Issue #182).

Tests that comments survive the parse -> emit round-trip:
- Line comments (// comment at line start)
- End-of-line comments (KEY::value // comment)
- Comments before/after sections
- Multiple consecutive comment lines
- strip_comments=True option for compact output

Per spec octave-core-spec.oct.md section 1::ENVELOPE:
COMMENTS:://[line_start_or_after_value]
"""

from octave_mcp.core.emitter import FormatOptions, emit
from octave_mcp.core.parser import parse


class TestCommentParsing:
    """Test that comments are parsed and attached to AST nodes."""

    def test_line_comment_preserved_in_ast(self):
        """Line comments (// at start) should be attached as leading_comments."""
        content = """===TEST===
// This is a comment before KEY
KEY::value
===END==="""
        doc = parse(content)
        # The assignment should have the comment attached
        assert len(doc.sections) == 1
        assignment = doc.sections[0]
        assert hasattr(assignment, "leading_comments")
        assert len(assignment.leading_comments) == 1
        assert "This is a comment before KEY" in assignment.leading_comments[0]

    def test_trailing_comment_preserved_in_ast(self):
        """End-of-line comments should be attached as trailing_comment."""
        content = """===TEST===
KEY::value // inline comment
===END==="""
        doc = parse(content)
        assert len(doc.sections) == 1
        assignment = doc.sections[0]
        assert hasattr(assignment, "trailing_comment")
        assert assignment.trailing_comment is not None
        assert "inline comment" in assignment.trailing_comment

    def test_multiple_leading_comments(self):
        """Multiple consecutive comment lines should all be preserved."""
        content = """===TEST===
// Comment line 1
// Comment line 2
// Comment line 3
KEY::value
===END==="""
        doc = parse(content)
        assignment = doc.sections[0]
        assert hasattr(assignment, "leading_comments")
        assert len(assignment.leading_comments) == 3
        assert "Comment line 1" in assignment.leading_comments[0]
        assert "Comment line 2" in assignment.leading_comments[1]
        assert "Comment line 3" in assignment.leading_comments[2]


class TestCommentRoundTrip:
    """Test that comments survive parse -> emit round-trip."""

    def test_line_comment_survives_roundtrip(self):
        """Line comments should survive parse -> emit."""
        content = """===TEST===
// This is a comment
KEY::value
===END==="""
        doc = parse(content)
        result = emit(doc)
        assert "// This is a comment" in result
        assert "KEY::value" in result

    def test_trailing_comment_survives_roundtrip(self):
        """End-of-line comments should survive parse -> emit."""
        content = """===TEST===
KEY::value // inline comment
===END==="""
        doc = parse(content)
        result = emit(doc)
        assert "KEY::value" in result
        assert "// inline comment" in result

    def test_multiple_comments_survive_roundtrip(self):
        """Multiple comments should all survive parse -> emit."""
        content = """===TEST===
// Comment 1
KEY1::value1
// Comment 2
// Comment 3
KEY2::value2 // trailing
===END==="""
        doc = parse(content)
        result = emit(doc)
        assert "// Comment 1" in result
        assert "// Comment 2" in result
        assert "// Comment 3" in result
        assert "// trailing" in result

    def test_comments_in_blocks_survive_roundtrip(self):
        """Comments inside blocks should survive parse -> emit."""
        content = """===TEST===
BLOCK:
  // Comment inside block
  NESTED::value // inline in block
===END==="""
        doc = parse(content)
        result = emit(doc)
        assert "// Comment inside block" in result
        assert "// inline in block" in result

    def test_comments_in_sections_survive_roundtrip(self):
        """Comments in section markers should survive parse -> emit."""
        content = """===TEST===
// Comment before section
\u00a71::SECTION_NAME
  // Comment inside section
  FIELD::value
===END==="""
        doc = parse(content)
        result = emit(doc)
        assert "// Comment before section" in result
        assert "// Comment inside section" in result

    def test_comment_only_lines_preserved(self):
        """Lines with only comments should be preserved."""
        content = """===TEST===
KEY1::value1
// standalone comment
KEY2::value2
===END==="""
        doc = parse(content)
        result = emit(doc)
        assert "// standalone comment" in result


class TestStripComments:
    """Test strip_comments option for compact output."""

    def test_strip_comments_removes_line_comments(self):
        """strip_comments=True should remove line comments."""
        content = """===TEST===
// This comment should be removed
KEY::value
===END==="""
        doc = parse(content)
        options = FormatOptions(strip_comments=True)
        result = emit(doc, format_options=options)
        assert "//" not in result
        assert "KEY::value" in result

    def test_strip_comments_removes_trailing_comments(self):
        """strip_comments=True should remove trailing comments."""
        content = """===TEST===
KEY::value // this should be removed
===END==="""
        doc = parse(content)
        options = FormatOptions(strip_comments=True)
        result = emit(doc, format_options=options)
        assert "//" not in result
        assert "KEY::value" in result

    def test_strip_comments_false_preserves_comments(self):
        """strip_comments=False (default) should preserve comments."""
        content = """===TEST===
// comment
KEY::value // trailing
===END==="""
        doc = parse(content)
        options = FormatOptions(strip_comments=False)
        result = emit(doc, format_options=options)
        assert "// comment" in result
        assert "// trailing" in result

    def test_default_format_options_preserves_comments(self):
        """Default FormatOptions should preserve comments."""
        content = """===TEST===
// comment
KEY::value // trailing
===END==="""
        doc = parse(content)
        # No format_options = default behavior (preserve comments)
        result = emit(doc)
        assert "// comment" in result
        assert "// trailing" in result


class TestCommentEdgeCases:
    """Test edge cases for comment preservation."""

    def test_empty_comment(self):
        """Empty comment (//) should be preserved."""
        content = """===TEST===
//
KEY::value
===END==="""
        doc = parse(content)
        result = emit(doc)
        assert "//" in result

    def test_comment_with_special_characters(self):
        """Comments with special OCTAVE characters should be preserved."""
        content = """===TEST===
// Comment with :: and -> and [brackets]
KEY::value
===END==="""
        doc = parse(content)
        result = emit(doc)
        assert "// Comment with :: and -> and [brackets]" in result

    def test_comment_at_document_end(self):
        """Comment before ===END=== should be preserved."""
        content = """===TEST===
KEY::value
// Final comment
===END==="""
        doc = parse(content)
        result = emit(doc)
        assert "// Final comment" in result

    def test_comment_after_meta(self):
        """Comment after META block should be preserved."""
        content = """===TEST===
META:
  TYPE::TEST
// Comment after META
KEY::value
===END==="""
        doc = parse(content)
        result = emit(doc)
        assert "// Comment after META" in result

    def test_multiple_spaces_in_comment_preserved(self):
        """Multiple spaces in comment text should be preserved."""
        content = """===TEST===
//   Multiple   spaces   here
KEY::value
===END==="""
        doc = parse(content)
        result = emit(doc)
        # The comment text (after //) should preserve internal spacing
        assert "Multiple   spaces   here" in result


class TestCommentIdempotence:
    """Test that emit(parse(emit(parse(x)))) == emit(parse(x)) with comments."""

    def test_comment_idempotence(self):
        """Comments should be idempotent through multiple round-trips."""
        original = """===TEST===
// Comment before
KEY::value // trailing
// Comment after
KEY2::value2
===END==="""
        doc1 = parse(original)
        emitted1 = emit(doc1)
        doc2 = parse(emitted1)
        emitted2 = emit(doc2)
        assert emitted1 == emitted2

    def test_complex_document_with_comments_idempotent(self):
        """Complex document with comments should be idempotent."""
        original = """===TEST===
META:
  TYPE::TEST
  // META comment
  VERSION::"1.0"
---
// Section comment
\u00a71::SECTION
  // Nested comment
  FIELD::value // inline
// Between sections
\u00a72::ANOTHER
  DATA::[a,b,c]
===END==="""
        doc1 = parse(original)
        emitted1 = emit(doc1)
        doc2 = parse(emitted1)
        emitted2 = emit(doc2)
        assert emitted1 == emitted2
