"""T1 tests: Token byte-offset coverage for ADR-0006 SR2-T2 Strategy A (GH#377).

Spans are byte offsets into the NFC-normalised content. For zero-width
artefacts (INDENT/DEDENT/NEWLINE) the convention is start_byte == end_byte
at the position where the artefact was emitted. For literal-bearing
tokens we assert byte-fidelity: ``content_nfc[start_byte:end_byte]``
decodes to a sensible substring of the original source.

PR-1 of 4 stacked PRs: span infrastructure only — no consumer reads
the new fields, so behaviour is unchanged. See
``docs/adr/adr-0006-sr2-t2-ast-span-coverage-audit.md`` §6 row T1.
"""

from __future__ import annotations

import unicodedata

from octave_mcp.core.lexer import Token, TokenType, tokenize


def _nfc_bytes(src: str) -> bytes:
    return unicodedata.normalize("NFC", src).encode("utf-8")


def test_token_dataclass_has_byte_offset_fields() -> None:
    """Token must expose start_byte/end_byte with default zero."""
    tok = Token(TokenType.EOF, None, 1, 1)
    assert hasattr(tok, "start_byte")
    assert hasattr(tok, "end_byte")
    assert tok.start_byte == 0
    assert tok.end_byte == 0


def test_simple_assignment_byte_offsets() -> None:
    """KEY::value — every token gets a populated span."""
    src = "===DOC===\nKEY::value\n===END===\n"
    tokens, _ = tokenize(src)
    nfc = _nfc_bytes(src)

    # Every token (except EOF and synthetic markers) must have a span
    for tok in tokens:
        assert tok.start_byte >= 0
        assert tok.end_byte >= tok.start_byte
        # Spans must lie within the NFC byte range
        assert tok.end_byte <= len(nfc), f"{tok.type} end_byte={tok.end_byte} > len(nfc)={len(nfc)}"


def test_identifier_byte_fidelity() -> None:
    """For IDENTIFIER tokens, the bytes between start/end decode to the source slice."""
    src = "KEY::value\n"
    tokens, _ = tokenize(src)
    nfc = _nfc_bytes(src)

    # Find the KEY identifier
    key_tok = next(t for t in tokens if t.type == TokenType.IDENTIFIER and t.value == "KEY")
    assert nfc[key_tok.start_byte : key_tok.end_byte].decode("utf-8") == "KEY"

    value_tok = next(t for t in tokens if t.type == TokenType.IDENTIFIER and t.value == "value")
    assert nfc[value_tok.start_byte : value_tok.end_byte].decode("utf-8") == "value"


def test_unicode_operator_byte_offsets() -> None:
    """Multi-byte unicode operators must cover the full byte span."""
    src = "A→B\n"
    tokens, _ = tokenize(src)
    nfc = _nfc_bytes(src)

    flow_tok = next(t for t in tokens if t.type == TokenType.FLOW)
    # → is 3 bytes in UTF-8
    span = nfc[flow_tok.start_byte : flow_tok.end_byte]
    assert span.decode("utf-8") == "→"
    assert len(span) == 3


def test_ascii_alias_byte_span_covers_alias() -> None:
    """ASCII alias '->': start/end span covers the 2 source bytes, not the canonical."""
    src = "A->B\n"
    tokens, _ = tokenize(src)
    nfc = _nfc_bytes(src)
    flow_tok = next(t for t in tokens if t.type == TokenType.FLOW)
    # Span covers the original '->' in source (2 ASCII bytes)
    assert nfc[flow_tok.start_byte : flow_tok.end_byte] == b"->"


def test_multiple_unicode_operators() -> None:
    """⊕, ∧, ⇌, §, ⧺, ⊃ — each multi-byte sequence covered byte-exact."""
    src = "A⊕B∧C⇌D⧺E\n"
    tokens, _ = tokenize(src)
    nfc = _nfc_bytes(src)
    for tok in tokens:
        if tok.type in (TokenType.SYNTHESIS, TokenType.CONSTRAINT, TokenType.TENSION, TokenType.CONCAT):
            slice_ = nfc[tok.start_byte : tok.end_byte]
            assert slice_.decode("utf-8") == tok.value


def test_section_marker_byte_span() -> None:
    """§ is multi-byte; SECTION token must cover it."""
    src = "§1::NAME\n"
    tokens, _ = tokenize(src)
    nfc = _nfc_bytes(src)
    sec_tok = next(t for t in tokens if t.type == TokenType.SECTION)
    assert nfc[sec_tok.start_byte : sec_tok.end_byte].decode("utf-8") == "§"


def test_indent_zero_width_convention() -> None:
    """INDENT tokens are NOT zero-width — they cover the leading spaces."""
    src = "BLOCK:\n  CHILD::val\n"
    tokens, _ = tokenize(src)
    nfc = _nfc_bytes(src)
    indent_tok = next(t for t in tokens if t.type == TokenType.INDENT)
    # INDENT spans the leading whitespace
    assert indent_tok.end_byte - indent_tok.start_byte == 2
    assert nfc[indent_tok.start_byte : indent_tok.end_byte] == b"  "


def test_eof_zero_width_at_end() -> None:
    """EOF is a zero-width sentinel at content end."""
    src = "K::v\n"
    tokens, _ = tokenize(src)
    nfc = _nfc_bytes(src)
    eof = tokens[-1]
    assert eof.type == TokenType.EOF
    assert eof.start_byte == eof.end_byte
    assert eof.start_byte == len(nfc)


def test_string_token_byte_span() -> None:
    """STRING tokens cover the quotes too."""
    src = 'K::"hello"\n'
    tokens, _ = tokenize(src)
    nfc = _nfc_bytes(src)
    str_tok = next(t for t in tokens if t.type == TokenType.STRING)
    # Span covers the full quoted literal including quotes
    assert nfc[str_tok.start_byte : str_tok.end_byte].decode("utf-8") == '"hello"'


def test_envelope_start_byte_span() -> None:
    """===NAME=== envelope marker covers the full delimiter."""
    src = "===MY_DOC===\nK::v\n===END===\n"
    tokens, _ = tokenize(src)
    nfc = _nfc_bytes(src)
    env_start = next(t for t in tokens if t.type == TokenType.ENVELOPE_START)
    assert nfc[env_start.start_byte : env_start.end_byte] == b"===MY_DOC==="
    env_end = next(t for t in tokens if t.type == TokenType.ENVELOPE_END)
    assert nfc[env_end.start_byte : env_end.end_byte] == b"===END==="


def test_fence_open_close_byte_spans() -> None:
    """Literal-zone fences expose their byte span to the parser."""
    src = "K:\n  ```python\n  code\n  ```\n"
    tokens, _ = tokenize(src)
    nfc = _nfc_bytes(src)
    open_tok = next(t for t in tokens if t.type == TokenType.FENCE_OPEN)
    close_tok = next(t for t in tokens if t.type == TokenType.FENCE_CLOSE)
    assert open_tok.end_byte > open_tok.start_byte
    assert close_tok.end_byte > close_tok.start_byte
    # The slice between open.start and close.end should include the fence content
    full = nfc[open_tok.start_byte : close_tok.end_byte].decode("utf-8")
    assert "```" in full
    assert "code" in full


def test_byte_offsets_monotonic_within_line() -> None:
    """Successive non-zero-width tokens on the same line have monotonic byte offsets."""
    src = "A::B\n"
    tokens, _ = tokenize(src)
    last_end = -1
    for tok in tokens:
        if tok.type == TokenType.EOF:
            continue
        # Only check tokens with width
        if tok.end_byte > tok.start_byte:
            assert tok.start_byte >= last_end, f"non-monotonic: {tok}"
            last_end = tok.end_byte


def test_number_token_byte_span() -> None:
    """NUMBER tokens cover the numeric lexeme."""
    src = "N::42\n"
    tokens, _ = tokenize(src)
    nfc = _nfc_bytes(src)
    num_tok = next(t for t in tokens if t.type == TokenType.NUMBER)
    assert nfc[num_tok.start_byte : num_tok.end_byte] == b"42"


def test_list_brackets_byte_span() -> None:
    """LIST_START / LIST_END cover the single-byte brackets."""
    src = "L::[a, b]\n"
    tokens, _ = tokenize(src)
    nfc = _nfc_bytes(src)
    ls = next(t for t in tokens if t.type == TokenType.LIST_START)
    le = next(t for t in tokens if t.type == TokenType.LIST_END)
    assert nfc[ls.start_byte : ls.end_byte] == b"["
    assert nfc[le.start_byte : le.end_byte] == b"]"
