"""Tests for W002: # in key/value names and :// in URLs must not cause silent data loss.

Bug W002 identifies two related I1 (Syntactic Fidelity) violations:

1. **# in values**: The lexer tokenizes `#` as SECTION unconditionally.
   When `#` appears mid-value (e.g., `Issue_#111`), content fragments at
   the `#` boundary causing silent data loss.

2. **:// in URLs**: URLs containing `://` (e.g., `https://example.com`)
   are truncated at the `//` comment delimiter. Silent data loss.

These tests document the expected behavior AFTER the fix.
"""

from octave_mcp.core.emitter import emit
from octave_mcp.core.lexer import TokenType, tokenize
from octave_mcp.core.parser import parse


class TestHashInValuePosition:
    """W002: # appearing mid-value must be treated as literal text, not SECTION."""

    def test_hash_in_identifier_value_preserved(self):
        """Issue_#111 must survive tokenization without fragmentation.

        Currently FAILS: lexer splits at # producing IDENTIFIER(Issue_) +
        SECTION(#) + NUMBER(111).
        """
        tokens, _ = tokenize("KEY::Issue_#111")
        # The value portion should NOT contain a SECTION token
        section_tokens = [t for t in tokens if t.type == TokenType.SECTION]
        assert section_tokens == [], (
            f"# in value position was tokenized as SECTION: {section_tokens}. "
            f"All tokens: {[(t.type, t.value) for t in tokens]}"
        )

    def test_hash_in_value_roundtrip(self):
        """Issue_#111 must survive parse-emit round trip intact."""
        content = 'KEY::"Issue_#111"'
        doc = parse(content)
        assignment = doc.sections[0]
        assert assignment.value == "Issue_#111", f"Expected 'Issue_#111' but got '{assignment.value}'"

    def test_hash_in_unquoted_value_preserved(self):
        """Unquoted value with # mid-token should not fragment.

        The lexer should either:
        - Treat # as literal within a value token, OR
        - Error explicitly (not silently transform)
        """
        # This tests the key scenario: # after :: in value position
        tokens, _ = tokenize("REF::GH_#123")
        section_tokens = [t for t in tokens if t.type == TokenType.SECTION]
        assert section_tokens == [], "# in value position was tokenized as SECTION, causing silent data loss"

    def test_hash_at_start_of_line_still_parsed_as_section(self):
        """Regression: # at start of line must still be parsed as section marker."""
        tokens, _ = tokenize("#1::OVERVIEW")
        section_tokens = [t for t in tokens if t.type == TokenType.SECTION]
        assert (
            len(section_tokens) == 1
        ), f"Expected exactly 1 SECTION token for start-of-line #, got {len(section_tokens)}"
        assert section_tokens[0].normalized_from == "#"

    def test_hash_after_indent_still_parsed_as_section(self):
        """Regression: # after leading whitespace must still be section marker."""
        tokens, _ = tokenize("  #2::DETAILS")
        section_tokens = [t for t in tokens if t.type == TokenType.SECTION]
        assert len(section_tokens) == 1, f"Expected exactly 1 SECTION token for indented #, got {len(section_tokens)}"

    def test_section_symbol_still_works(self):
        """Regression: Unicode § must still be parsed as SECTION."""
        tokens, _ = tokenize("§1::OVERVIEW")
        section_tokens = [t for t in tokens if t.type == TokenType.SECTION]
        assert len(section_tokens) == 1


class TestTrailingHashEdgeCases:
    """W002: Trailing # at EOF or before non-identifier chars must NOT be consumed."""

    def test_trailing_hash_at_eof_not_consumed_into_identifier(self):
        """FOO# at EOF: the trailing # must NOT become part of the identifier.

        The W002 fix should only consume # when it is immediately followed by
        an identifier character. A trailing # with nothing following it is a
        SECTION marker, not part of the preceding identifier.
        """
        tokens, _ = tokenize("KEY::FOO#")
        identifier_tokens = [t for t in tokens if t.type == TokenType.IDENTIFIER]
        # The value identifier must be 'FOO', not 'FOO#'
        value_identifiers = [t for t in identifier_tokens if t.value not in ("KEY",)]
        assert any(
            t.value == "FOO" for t in value_identifiers
        ), f"Expected IDENTIFIER('FOO') but got: {[(t.type.name, t.value) for t in tokens]}"
        # The trailing # must produce a SECTION token
        section_tokens = [t for t in tokens if t.type == TokenType.SECTION]
        assert len(section_tokens) == 1, (
            f"Expected 1 SECTION token for trailing #, got {len(section_tokens)}. "
            f"All tokens: {[(t.type.name, t.value) for t in tokens]}"
        )

    def test_trailing_hash_before_newline_not_consumed(self):
        """FOO# followed by newline: trailing # must NOT become part of identifier."""
        tokens, _ = tokenize("KEY::FOO#\n")
        identifier_tokens = [t for t in tokens if t.type == TokenType.IDENTIFIER]
        value_identifiers = [t for t in identifier_tokens if t.value not in ("KEY",)]
        assert any(
            t.value == "FOO" for t in value_identifiers
        ), f"Expected IDENTIFIER('FOO') but got: {[(t.type.name, t.value) for t in tokens]}"
        section_tokens = [t for t in tokens if t.type == TokenType.SECTION]
        assert len(section_tokens) == 1, (
            f"Expected 1 SECTION token for # before newline, got {len(section_tokens)}. "
            f"All tokens: {[(t.type.name, t.value) for t in tokens]}"
        )

    def test_hash_followed_by_digit_consumed_as_identifier(self):
        """REF::GH_#123 — # followed by digit IS a valid identifier continuation.

        Digits satisfy _is_valid_identifier_char, so GH_#123 must remain
        a single IDENTIFIER token (regression guard for the W002 fix).
        """
        tokens, _ = tokenize("REF::GH_#123")
        section_tokens = [t for t in tokens if t.type == TokenType.SECTION]
        assert section_tokens == [], (
            f"# followed by digit should not produce SECTION token: {section_tokens}. "
            f"All tokens: {[(t.type.name, t.value) for t in tokens]}"
        )
        identifier_tokens = [t for t in tokens if t.type == TokenType.IDENTIFIER]
        value_identifiers = [t for t in identifier_tokens if t.value not in ("REF",)]
        assert any(
            t.value == "GH_#123" for t in value_identifiers
        ), f"Expected IDENTIFIER('GH_#123') but got: {[(t.type.name, t.value) for t in tokens]}"


class TestURLProtection:
    """W002: :// in URLs must not trigger comment splitting."""

    def test_quoted_url_preserved(self):
        """Quoted URLs with :// must be preserved (already works)."""
        content = 'URL::"https://example.com/path"'
        doc = parse(content)
        assignment = doc.sections[0]
        assert assignment.value == "https://example.com/path"

    def test_unquoted_url_not_truncated_at_comment(self):
        """Unquoted URL's :// must not be interpreted as comment start.

        Currently FAILS: the // in https:// matches the COMMENT pattern,
        silently truncating everything after it.
        """
        tokens, _ = tokenize("URL::https://example.com")
        comment_tokens = [t for t in tokens if t.type == TokenType.COMMENT]
        # The // in https:// should NOT produce a comment token
        assert comment_tokens == [], (
            f":// in URL was interpreted as comment: {comment_tokens}. "
            f"All tokens: {[(t.type, t.value) for t in tokens]}"
        )

    def test_actual_comment_still_works(self):
        """Regression: standalone // comments must still be recognized."""
        tokens, _ = tokenize("KEY::value // this is a comment")
        comment_tokens = [t for t in tokens if t.type == TokenType.COMMENT]
        assert len(comment_tokens) == 1, f"Expected 1 COMMENT token, got {len(comment_tokens)}"

    def test_comment_at_start_of_line_still_works(self):
        """Regression: // at start of line must still be a comment."""
        tokens, _ = tokenize("// This is a full-line comment")
        comment_tokens = [t for t in tokens if t.type == TokenType.COMMENT]
        assert len(comment_tokens) == 1

    def test_ftp_url_not_truncated(self):
        """ftp:// URLs must not be truncated."""
        tokens, _ = tokenize("SRC::ftp://files.example.com")
        comment_tokens = [t for t in tokens if t.type == TokenType.COMMENT]
        assert comment_tokens == [], ":// in ftp URL was interpreted as comment"

    def test_file_url_not_truncated(self):
        """file:// URLs must not be truncated."""
        tokens, _ = tokenize("PATH::file:///usr/local/bin")
        comment_tokens = [t for t in tokens if t.type == TokenType.COMMENT]
        assert comment_tokens == [], ":// in file URL was interpreted as comment"

    def test_url_in_array_preserved(self):
        """URLs inside arrays must not be truncated at ://."""
        content = 'URLS::["https://a.com", "https://b.com"]'
        doc = parse(content)
        items = doc.sections[0].value.items
        assert items == ["https://a.com", "https://b.com"]


class TestDigitPrefixHash:
    """W002: # appearing after a NUMBER token (digit-prefix) must not produce E005.

    Covers the case where the value starts with digits: 123#foo.
    The NUMBER pattern consumes '123', then the SECTION guard suppresses '#'
    (lookbehind='3' is identifier_char, lookahead='f' is identifier_char), but
    no fallback handler emits a token for '#', causing E005.
    Fix: after NUMBER, if '#' is followed by identifier chars, merge into
    previous NUMBER token as IDENTIFIER.
    """

    def test_digit_prefix_hash_no_e005(self):
        """KEY::123#foo must not raise E005.

        This is the primary regression test for the digit-prefix # bug.
        Before the fix: LexerError E005 on '#' at column 9.
        After the fix: no error, value preserved.
        """
        tokens, _ = tokenize("KEY::123#foo")
        section_tokens = [t for t in tokens if t.type == TokenType.SECTION]
        assert section_tokens == [], (
            f"# in digit-prefix value was tokenized as SECTION: {section_tokens}. "
            f"All tokens: {[(t.type.name, t.value) for t in tokens]}"
        )
        error_tokens = [t for t in tokens if t.type.name == "ERROR"]
        assert error_tokens == [], f"Unexpected error tokens: {error_tokens}"

    def test_digit_prefix_hash_value_preserved(self):
        """KEY::123#foo must preserve the full value '123#foo' as a single IDENTIFIER token."""
        tokens, _ = tokenize("KEY::123#foo")
        identifier_tokens = [t for t in tokens if t.type == TokenType.IDENTIFIER]
        value_identifiers = [t for t in identifier_tokens if t.value not in ("KEY",)]
        assert any(t.value == "123#foo" for t in value_identifiers), (
            f"Expected IDENTIFIER('123#foo') but got: " f"{[(t.type.name, t.value) for t in tokens]}"
        )

    def test_digit_prefix_hash_roundtrip(self):
        """KEY::123#foo must survive parse-emit round trip intact (unquoted)."""
        content = "KEY::123#foo"
        doc = parse(content)
        assignment = doc.sections[0]
        assert str(assignment.value) == "123#foo", f"Expected '123#foo' but got '{assignment.value}'"

    def test_digit_prefix_multiple_hash_segments(self):
        """KEY::1#a#2 must not produce E005 — multiple # in digit-prefix value."""
        tokens, _ = tokenize("KEY::1#a#2")
        section_tokens = [t for t in tokens if t.type == TokenType.SECTION]
        assert section_tokens == [], (
            f"# in 1#a#2 value produced SECTION token: {section_tokens}. "
            f"All tokens: {[(t.type.name, t.value) for t in tokens]}"
        )


class TestRoundTrip:
    """W002: End-to-end round-trip fidelity for # and :// content."""

    def test_section_marker_roundtrip(self):
        """§1::SECTION_NAME must round-trip correctly."""
        content = "§1::OVERVIEW\n  KEY::value"
        doc = parse(content)
        output = emit(doc)
        assert "§1::OVERVIEW" in output

    def test_hash_in_value_roundtrip(self):
        """Unquoted value containing # must round-trip (exercises W002 _match_unicode_identifier path)."""
        content = "KEY::Issue_#111"
        doc = parse(content)
        output = emit(doc)
        assert "Issue_#111" in output, f"Expected 'Issue_#111' in output but got: {output!r}"

    def test_unquoted_url_roundtrip(self):
        """Unquoted URL with :// must round-trip (exercises W002 URL guard path)."""
        content = "URL::https://example.com"
        doc = parse(content)
        output = emit(doc)
        assert "https://example.com" in output, f"Expected 'https://example.com' in output but got: {output!r}"

    def test_quoted_hash_value_roundtrip(self):
        """Unquoted value containing # must round-trip (unquoted, exercises W002 fix path)."""
        content = "TAG::Issue_#111"
        doc = parse(content)
        output = emit(doc)
        assert "Issue_#111" in output, f"Expected 'Issue_#111' in output but got: {output!r}"

    def test_quoted_url_roundtrip(self):
        """Unquoted URL with query string :// must round-trip (exercises W002 URL guard path)."""
        content = "LINK::https://example.com/path"
        doc = parse(content)
        output = emit(doc)
        assert (
            "https://example.com/path" in output
        ), f"Expected 'https://example.com/path' in output but got: {output!r}"
