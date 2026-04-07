"""Tests for ISO timestamp handling in OCTAVE lexer/parser (GH#350).

Unquoted ISO timestamps like 2026-04-06T20:00:00Z were being fragmented
by the tokenizer into multiple tokens (NUMBER, IDENTIFIER, BLOCK, etc.)
instead of being detected and handled properly.

The fix ensures unquoted ISO timestamps raise an informative error in
strict mode, guiding agents to quote them, and auto-repair in lenient mode.
"""

import pytest

from octave_mcp.core.lexer import LexerError, TokenType, tokenize


class TestISOTimestampDetection:
    """Test that unquoted ISO timestamps are detected and handled."""

    def test_unquoted_iso_datetime_raises_error(self):
        """Unquoted ISO datetime should raise E_UNQUOTED_TIMESTAMP, not fragment silently."""
        with pytest.raises(LexerError, match="E_UNQUOTED_TIMESTAMP") as exc_info:
            tokenize("UPDATED::2026-04-06T20:00:00Z")
        # Error should suggest quoting
        assert '"2026-04-06T20:00:00Z"' in str(exc_info.value) or "quote" in str(exc_info.value).lower()

    def test_unquoted_iso_date_only_raises_error(self):
        """Unquoted ISO date (no time) should raise E_UNQUOTED_TIMESTAMP."""
        with pytest.raises(LexerError, match="E_UNQUOTED_TIMESTAMP"):
            tokenize("DATE::2026-04-06")

    def test_unquoted_iso_datetime_with_offset_raises_error(self):
        """Unquoted ISO datetime with timezone offset should raise error."""
        with pytest.raises(LexerError, match="E_UNQUOTED_TIMESTAMP"):
            tokenize("TIME::2026-04-06T20:00:00+05:30")

    def test_unquoted_iso_datetime_with_millis_raises_error(self):
        """Unquoted ISO datetime with milliseconds should raise error."""
        with pytest.raises(LexerError, match="E_UNQUOTED_TIMESTAMP"):
            tokenize("TIME::2026-04-06T20:00:00.123Z")

    def test_quoted_iso_timestamp_works(self):
        """Quoted ISO timestamps should tokenize normally as STRING."""
        tokens, _ = tokenize('UPDATED::"2026-04-06T20:00:00Z"')
        string_tokens = [t for t in tokens if t.type == TokenType.STRING]
        assert len(string_tokens) == 1
        assert string_tokens[0].value == "2026-04-06T20:00:00Z"

    def test_quoted_iso_date_works(self):
        """Quoted ISO dates should tokenize normally as STRING."""
        tokens, _ = tokenize('DATE::"2026-04-06"')
        string_tokens = [t for t in tokens if t.type == TokenType.STRING]
        assert len(string_tokens) == 1
        assert string_tokens[0].value == "2026-04-06"

    def test_plain_negative_number_still_works(self):
        """Plain negative numbers should still tokenize correctly."""
        tokens, _ = tokenize("VALUE::-42")
        number_tokens = [t for t in tokens if t.type == TokenType.NUMBER]
        assert len(number_tokens) == 1
        assert number_tokens[0].value == -42

    def test_number_minus_number_expression_still_works(self):
        """Number expressions with subtraction context should still work.

        In OCTAVE, `10-5` is not an expression -- it's tokenized as
        NUMBER(10) NUMBER(-5), which the parser coalesces into a multi-word
        value. This test ensures we don't false-positive on non-date patterns.
        """
        # 10-5 does NOT look like a date (year must be 4 digits)
        tokens, _ = tokenize("X::10-5")
        number_tokens = [t for t in tokens if t.type == TokenType.NUMBER]
        assert len(number_tokens) >= 1  # 10 and -5

    def test_version_like_pattern_not_affected(self):
        """Version strings like 1.2.3 should still work as VERSION tokens."""
        tokens, _ = tokenize("V::1.2.3")
        version_tokens = [t for t in tokens if t.type == TokenType.VERSION]
        assert len(version_tokens) == 1
        assert version_tokens[0].value == "1.2.3"

    def test_year_only_is_just_a_number(self):
        """A standalone year like 2026 should be a normal NUMBER."""
        tokens, _ = tokenize("YEAR::2026")
        number_tokens = [t for t in tokens if t.type == TokenType.NUMBER]
        assert len(number_tokens) == 1
        assert number_tokens[0].value == 2026

    def test_error_message_includes_full_timestamp(self):
        """Error message should include the detected timestamp for clarity."""
        with pytest.raises(LexerError) as exc_info:
            tokenize("UPDATED::2026-04-06T20:00:00Z")
        error_msg = str(exc_info.value)
        assert "2026-04-06" in error_msg

    def test_unquoted_timestamp_in_list_raises_error(self):
        """Unquoted timestamp inside a list should also be detected."""
        with pytest.raises(LexerError, match="E_UNQUOTED_TIMESTAMP"):
            tokenize("[2026-04-06T20:00:00Z]")


class TestISOTimestampLenientMode:
    """Test lenient mode auto-repair for unquoted ISO timestamps."""

    def test_lenient_mode_auto_repairs_datetime(self):
        """Lenient mode should auto-repair unquoted ISO datetime to quoted string."""
        tokens, repairs = tokenize("UPDATED::2026-04-06T20:00:00Z", lenient=True)
        # Should produce a STRING token with the timestamp value
        string_tokens = [t for t in tokens if t.type == TokenType.STRING]
        assert len(string_tokens) == 1
        assert string_tokens[0].value == "2026-04-06T20:00:00Z"

    def test_lenient_mode_auto_repairs_date_only(self):
        """Lenient mode should auto-repair unquoted ISO date."""
        tokens, repairs = tokenize("DATE::2026-04-06", lenient=True)
        string_tokens = [t for t in tokens if t.type == TokenType.STRING]
        assert len(string_tokens) == 1
        assert string_tokens[0].value == "2026-04-06"

    def test_lenient_mode_emits_repair_record(self):
        """Lenient mode should emit a W_REPAIR_CANDIDATE for the auto-quoted timestamp."""
        tokens, repairs = tokenize("UPDATED::2026-04-06T20:00:00Z", lenient=True)
        timestamp_repairs = [
            r for r in repairs if r.get("type") == "repair_candidate" and r.get("subtype") == "unquoted_timestamp"
        ]
        assert len(timestamp_repairs) == 1
        assert "2026-04-06T20:00:00Z" in timestamp_repairs[0]["original"]
        assert (
            "quote" in timestamp_repairs[0]["message"].lower()
            or "W_REPAIR_CANDIDATE" in timestamp_repairs[0]["message"]
        )

    def test_lenient_mode_auto_repairs_with_offset(self):
        """Lenient mode should auto-repair timestamps with timezone offsets."""
        tokens, repairs = tokenize("TIME::2026-04-06T20:00:00+05:30", lenient=True)
        string_tokens = [t for t in tokens if t.type == TokenType.STRING]
        assert len(string_tokens) == 1
        assert string_tokens[0].value == "2026-04-06T20:00:00+05:30"

    def test_lenient_mode_auto_repairs_with_millis(self):
        """Lenient mode should auto-repair timestamps with milliseconds."""
        tokens, repairs = tokenize("TIME::2026-04-06T20:00:00.123Z", lenient=True)
        string_tokens = [t for t in tokens if t.type == TokenType.STRING]
        assert len(string_tokens) == 1
        assert string_tokens[0].value == "2026-04-06T20:00:00.123Z"


class TestISOTimestampRoundTrip:
    """Test that timestamps roundtrip correctly through parse/emit."""

    def test_quoted_timestamp_roundtrips(self):
        """Quoted timestamp should survive parse -> emit cycle."""
        from octave_mcp.core.emitter import emit
        from octave_mcp.core.parser import parse

        doc = parse('===TEST===\nUPDATED::"2026-04-06T20:00:00Z"\n===END===')
        output = emit(doc)
        assert "2026-04-06T20:00:00Z" in output

    def test_lenient_timestamp_roundtrips(self):
        """Lenient-repaired timestamp should survive tokenize -> parse -> emit cycle."""
        from octave_mcp.core.emitter import emit
        from octave_mcp.core.parser import parse

        # Tokenize in lenient mode to auto-repair the timestamp
        tokens, repairs = tokenize(
            "===TEST===\nUPDATED::2026-04-06T20:00:00Z\n===END===",
            lenient=True,
        )
        # Parse from pre-tokenized tokens
        doc = parse(tokens)
        output = emit(doc)
        assert "2026-04-06T20:00:00Z" in output
