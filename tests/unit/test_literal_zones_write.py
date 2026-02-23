"""Tests for literal zone write guards and zone reporting (T10 + T14).

Issue #235: Verifies that LiteralZoneValue is handled correctly in:
- emitter.py: is_absent() returns False for LiteralZoneValue
- emitter.py: needs_quotes() returns False for LiteralZoneValue
- write.py: _normalize_value_for_ast() returns LiteralZoneValue unchanged
- write.py: zone_report and repair_log added to response when literal zones present
- write.py: literal zone content preserved byte-for-byte (T14)

Issue #259: Literal zone content inside a block value (KEY:) must survive normalization.
"""

import hashlib
import os
import tempfile

import pytest

from octave_mcp.core.ast_nodes import LiteralZoneValue
from octave_mcp.core.emitter import is_absent, needs_quotes
from octave_mcp.core.parser import parse
from octave_mcp.core.validator import _count_literal_zones
from octave_mcp.mcp.write import WriteTool, _normalize_value_for_ast

_TOOL = WriteTool()

# --- Match Point 2: is_absent() ---


class TestIsAbsentLiteralZone:
    """MP2: is_absent returns False for LiteralZoneValue."""

    def test_is_absent_literal_zone_returns_false(self) -> None:
        """LiteralZoneValue is NOT absent."""
        lzv = LiteralZoneValue(content="hello", info_tag="python")
        assert is_absent(lzv) is False

    def test_is_absent_empty_literal_zone_returns_false(self) -> None:
        """Empty LiteralZoneValue is NOT absent (I2: empty != absent)."""
        lzv = LiteralZoneValue(content="")
        assert is_absent(lzv) is False

    def test_is_absent_default_literal_zone_returns_false(self) -> None:
        """Default-constructed LiteralZoneValue is NOT absent."""
        lzv = LiteralZoneValue()
        assert is_absent(lzv) is False


# --- Match Point 3: needs_quotes() ---


class TestNeedsQuotesLiteralZone:
    """MP3: needs_quotes returns False for LiteralZoneValue."""

    def test_needs_quotes_literal_zone_returns_false(self) -> None:
        """LiteralZoneValue does not need quotes."""
        lzv = LiteralZoneValue(content="hello world", info_tag="python")
        assert needs_quotes(lzv) is False

    def test_needs_quotes_empty_literal_zone_returns_false(self) -> None:
        """Empty LiteralZoneValue does not need quotes."""
        lzv = LiteralZoneValue(content="")
        assert needs_quotes(lzv) is False

    def test_needs_quotes_literal_zone_with_special_chars_returns_false(self) -> None:
        """LiteralZoneValue with special chars still returns False (not a string)."""
        lzv = LiteralZoneValue(content='key::"value" with spaces\n')
        assert needs_quotes(lzv) is False


# --- Match Point 8: _normalize_value_for_ast() ---


class TestNormalizeValueForAstLiteralZone:
    """MP8: _normalize_value_for_ast returns LiteralZoneValue unchanged."""

    def test_literal_zone_returned_unchanged(self) -> None:
        """LiteralZoneValue passes through normalization unchanged."""
        lzv = LiteralZoneValue(content="hello\n", info_tag="python", fence_marker="```")
        result = _normalize_value_for_ast(lzv)
        assert result is lzv  # Identity check -- same object

    def test_literal_zone_content_not_normalized(self) -> None:
        """LiteralZoneValue content is NOT NFC-normalized."""
        # Content with tabs and special chars must survive unchanged
        lzv = LiteralZoneValue(content="raw\tcontent\nwith\ttabs")
        result = _normalize_value_for_ast(lzv)
        assert result.content == "raw\tcontent\nwith\ttabs"

    def test_literal_zone_not_wrapped_in_list_value(self) -> None:
        """LiteralZoneValue is NOT wrapped in ListValue (not a list)."""
        lzv = LiteralZoneValue(content="[a, b, c]")
        result = _normalize_value_for_ast(lzv)
        assert isinstance(result, LiteralZoneValue)
        assert result is lzv

    def test_literal_zone_not_wrapped_in_inline_map(self) -> None:
        """LiteralZoneValue is NOT wrapped in InlineMap (not a dict)."""
        lzv = LiteralZoneValue(content='{"key": "value"}')
        result = _normalize_value_for_ast(lzv)
        assert isinstance(result, LiteralZoneValue)
        assert result is lzv

    def test_literal_zone_preserves_all_fields(self) -> None:
        """All LiteralZoneValue fields preserved through normalization."""
        lzv = LiteralZoneValue(content="code\n", info_tag="rust", fence_marker="````")
        result = _normalize_value_for_ast(lzv)
        assert result.content == "code\n"
        assert result.info_tag == "rust"
        assert result.fence_marker == "````"


# ===========================================================================
# T14: octave_write — Zone Reporting + Preservation
# ===========================================================================

# Note: OCTAVE syntax requires the fence on the line AFTER the key
_DOC_ONE_ZONE = """\
===DOC===
META:
  TYPE::"TEST"
  VERSION::"1.0"

CODE::
```python
print("hello")
```
===END===
"""

_DOC_WITH_TABS = """\
===DOC===
META:
  TYPE::"TEST"
  VERSION::"1.0"

CODE::
```
\tindented with tabs
\t\tdouble indent
```
===END===
"""

_DOC_NO_ZONES = """\
===DOC===
META:
  TYPE::"TEST"
  VERSION::"1.0"

PLAIN::just a value
===END===
"""

_DOC_TWO_ZONES = """\
===DOC===
META:
  TYPE::"TEST"
  VERSION::"1.0"

CODE::
```python
print("hello")
```

CONFIG::
```json
{"key": "value"}
```
===END===
"""


async def _write_content_result(content: str) -> dict:
    """Helper: write content to a temp file and return result dict."""
    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "test.oct.md")
        return await _TOOL.execute(target_path=target, content=content)


class TestWriteZoneReportPresence:
    """zone_report must appear in response when literal zones are present."""

    @pytest.mark.asyncio
    async def test_zone_report_present_when_zones_exist(self) -> None:
        """zone_report key must be in result when doc has literal zones."""
        result = await _write_content_result(_DOC_ONE_ZONE)
        assert result["status"] == "success"
        assert "zone_report" in result

    @pytest.mark.asyncio
    async def test_zone_report_absent_when_no_zones(self) -> None:
        """zone_report key must NOT be in result when doc has no literal zones."""
        result = await _write_content_result(_DOC_NO_ZONES)
        assert result["status"] == "success"
        assert "zone_report" not in result

    @pytest.mark.asyncio
    async def test_contains_literal_zones_flag_true(self) -> None:
        """contains_literal_zones must be True when zones present."""
        result = await _write_content_result(_DOC_ONE_ZONE)
        assert result.get("contains_literal_zones") is True

    @pytest.mark.asyncio
    async def test_literal_zones_validated_is_false(self) -> None:
        """literal_zones_validated must always be False (I5: honest, D4: opaque)."""
        result = await _write_content_result(_DOC_ONE_ZONE)
        assert result.get("literal_zones_validated") is False

    @pytest.mark.asyncio
    async def test_literal_zone_count_is_one(self) -> None:
        """literal_zone_count must be 1 for single-zone doc."""
        result = await _write_content_result(_DOC_ONE_ZONE)
        assert result.get("literal_zone_count") == 1

    @pytest.mark.asyncio
    async def test_zone_report_literal_status_preserved(self) -> None:
        """zone_report.literal.status must be 'preserved'."""
        result = await _write_content_result(_DOC_ONE_ZONE)
        assert result["zone_report"]["literal"]["status"] == "preserved"

    @pytest.mark.asyncio
    async def test_zone_report_literal_count_one(self) -> None:
        """zone_report.literal.count must be 1."""
        result = await _write_content_result(_DOC_ONE_ZONE)
        assert result["zone_report"]["literal"]["count"] == 1

    @pytest.mark.asyncio
    async def test_zone_report_literal_content_validated_false(self) -> None:
        """zone_report.literal.content_validated must be False."""
        result = await _write_content_result(_DOC_ONE_ZONE)
        assert result["zone_report"]["literal"]["content_validated"] is False

    @pytest.mark.asyncio
    async def test_zone_report_literal_zones_list(self) -> None:
        """zone_report.literal.zones must be a list with one entry."""
        result = await _write_content_result(_DOC_ONE_ZONE)
        zones = result["zone_report"]["literal"]["zones"]
        assert isinstance(zones, list)
        assert len(zones) == 1

    @pytest.mark.asyncio
    async def test_zone_report_zones_entry_has_required_keys(self) -> None:
        """Each zone entry must have key, info_tag, and line."""
        result = await _write_content_result(_DOC_ONE_ZONE)
        zone = result["zone_report"]["literal"]["zones"][0]
        assert "key" in zone
        assert "info_tag" in zone
        assert "line" in zone

    @pytest.mark.asyncio
    async def test_two_zones_count(self) -> None:
        """literal_zone_count must be 2 for two-zone doc."""
        result = await _write_content_result(_DOC_TWO_ZONES)
        assert result.get("literal_zone_count") == 2


class TestWriteRepairLog:
    """repair_log for literal zones must appear in response when zones present."""

    @pytest.mark.asyncio
    async def test_literal_zone_repair_log_present(self) -> None:
        """literal_zone_repair_log must be in result when zones present."""
        result = await _write_content_result(_DOC_ONE_ZONE)
        assert "literal_zone_repair_log" in result

    @pytest.mark.asyncio
    async def test_literal_zone_repair_log_is_list(self) -> None:
        """literal_zone_repair_log must be a list."""
        result = await _write_content_result(_DOC_ONE_ZONE)
        assert isinstance(result["literal_zone_repair_log"], list)

    @pytest.mark.asyncio
    async def test_repair_log_absent_when_no_zones(self) -> None:
        """literal_zone_repair_log must NOT be in result when no literal zones."""
        result = await _write_content_result(_DOC_NO_ZONES)
        assert "literal_zone_repair_log" not in result


class TestWriteContentPreservation:
    """Literal zone content must be preserved byte-for-byte through write."""

    @pytest.mark.asyncio
    async def test_literal_zone_content_preserved_in_output(self) -> None:
        """Zone content must survive the write pipeline byte-for-byte."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "test.oct.md")
            result = await _TOOL.execute(target_path=target, content=_DOC_ONE_ZONE)
            assert result["status"] == "success"
            # Read back written file
            with open(target, encoding="utf-8") as f:
                written = f.read()
            # The literal content 'print("hello")' must appear verbatim
            assert 'print("hello")' in written

    @pytest.mark.asyncio
    async def test_tabs_preserved_in_literal_zone(self) -> None:
        """Tabs inside a literal zone must be preserved (not converted to spaces)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "test.oct.md")
            result = await _TOOL.execute(target_path=target, content=_DOC_WITH_TABS)
            assert result["status"] == "success"
            with open(target, encoding="utf-8") as f:
                written = f.read()
            assert "\tindented with tabs" in written
            assert "\t\tdouble indent" in written

    @pytest.mark.asyncio
    async def test_unwrap_markdown_fence_does_not_strip_inner_fence(self) -> None:
        """_unwrap_markdown_code_fence strips only the outer transport fence, not inner literal zones."""
        # A document wrapped in outer markdown fence containing a literal zone inside
        outer_wrapped = "```octave\n" + _DOC_ONE_ZONE + "```"
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "test.oct.md")
            result = await _TOOL.execute(target_path=target, content=outer_wrapped)
            assert result["status"] == "success"
            # Should have unwrapped outer fence (W_MARKDOWN_UNWRAP correction)
            assert any(c.get("code") == "W_MARKDOWN_UNWRAP" for c in result.get("corrections", []))
            # Inner literal zone must still be in the written file
            with open(target, encoding="utf-8") as f:
                written = f.read()
            assert "```python" in written or "```" in written

    @pytest.mark.asyncio
    async def test_write_without_literal_zones_no_zone_keys(self) -> None:
        """Write doc without literal zones: result has no zone-related keys."""
        result = await _write_content_result(_DOC_NO_ZONES)
        assert "contains_literal_zones" not in result
        assert "literal_zone_count" not in result
        assert "literal_zones_validated" not in result


# ===========================================================================
# T14-EXACT: Exact byte-for-byte content equality after round-trip
# ===========================================================================

# These constants are the EXACT content that the parser stores in LiteralZoneValue.content
# after round-trip.  The parser captures everything between the opening fence newline
# and the closing fence line -- the trailing newline before the closing ``` is NOT
# part of the content (the parser strips it).  This is the true byte-for-byte content.
_LITERAL_CONTENT_PYTHON = 'print("hello")'
_LITERAL_CONTENT_TABS = "\tindented with tabs\n\t\tdouble indent"
_LITERAL_CONTENT_SPECIAL = "x = 1\n# comment with unicode: \u00e9\t\ttabs too"

_DOC_EXACT_PYTHON = """\
===DOC===
META:
  TYPE::"TEST"
  VERSION::"1.0"

CODE::
```python
print("hello")
```
===END===
"""

_DOC_EXACT_TABS = """\
===DOC===
META:
  TYPE::"TEST"
  VERSION::"1.0"

CODE::
```
\tindented with tabs
\t\tdouble indent
```
===END===
"""

_DOC_EXACT_SPECIAL = """\
===DOC===
META:
  TYPE::"TEST"
  VERSION::"1.0"

CODE::
```python
x = 1
# comment with unicode: \u00e9\t\ttabs too
```
===END===
"""


def _find_literal_zone_content(doc_text: str, key: str = "CODE") -> str:
    """Parse a written document and return the literal zone content for ``key``."""
    doc = parse(doc_text)
    zones = _count_literal_zones(doc)
    matching = [z for z in zones if z["key"] == key]
    assert matching, f"No literal zone with key={key!r} found in parsed document"
    # Re-extract the LiteralZoneValue from the parsed document directly.
    # Walk the AST to find the assignment with the given key.
    from octave_mcp.core.ast_nodes import Assignment, Block

    def _find(nodes: list) -> str | None:
        for node in nodes:
            if isinstance(node, Assignment) and node.key == key:
                from octave_mcp.core.ast_nodes import LiteralZoneValue as LZV

                if isinstance(node.value, LZV):
                    return node.value.content
            if isinstance(node, Block):
                result = _find(node.children)
                if result is not None:
                    return result
        return None

    content = _find(doc.sections)
    assert content is not None, f"LiteralZoneValue for key={key!r} not found in AST"
    return content


class TestWriteContentPreservationExact:
    """Exact byte-for-byte equality of literal zone content through the write pipeline.

    These tests address the CE non-blocking finding: prior tests used substring
    checks (``in``), which cannot detect mutations that still contain the expected
    substring.  Spec requirement (I1/D3): content between fences must be preserved
    with no alteration whatsoever -- zero-processing, bijective.

    Strategy: write -> read back file -> re-parse with ``parse()`` -> extract
    ``LiteralZoneValue.content`` from AST -> assert exact equality to original.
    """

    @pytest.mark.asyncio
    async def test_python_content_exact_equality_after_roundtrip(self) -> None:
        """Parsed zone.content must equal original content exactly (not just substring)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "test.oct.md")
            result = await _TOOL.execute(target_path=target, content=_DOC_EXACT_PYTHON)
            assert result["status"] == "success"
            with open(target, encoding="utf-8") as f:
                written = f.read()
            content = _find_literal_zone_content(written)
            assert (
                content == _LITERAL_CONTENT_PYTHON
            ), f"Expected exact content {_LITERAL_CONTENT_PYTHON!r}, got {content!r}"

    @pytest.mark.asyncio
    async def test_tabs_content_exact_equality_after_roundtrip(self) -> None:
        """Tab characters must be preserved exactly (not converted to spaces)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "test.oct.md")
            result = await _TOOL.execute(target_path=target, content=_DOC_EXACT_TABS)
            assert result["status"] == "success"
            with open(target, encoding="utf-8") as f:
                written = f.read()
            content = _find_literal_zone_content(written)
            assert (
                content == _LITERAL_CONTENT_TABS
            ), f"Expected exact tab-preserved content {_LITERAL_CONTENT_TABS!r}, got {content!r}"

    @pytest.mark.asyncio
    async def test_special_chars_content_exact_equality_after_roundtrip(self) -> None:
        """Unicode and mixed whitespace content must be preserved exactly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "test.oct.md")
            result = await _TOOL.execute(target_path=target, content=_DOC_EXACT_SPECIAL)
            assert result["status"] == "success"
            with open(target, encoding="utf-8") as f:
                written = f.read()
            content = _find_literal_zone_content(written)
            assert (
                content == _LITERAL_CONTENT_SPECIAL
            ), f"Expected exact content {_LITERAL_CONTENT_SPECIAL!r}, got {content!r}"

    @pytest.mark.asyncio
    async def test_content_hash_equality_after_roundtrip(self) -> None:
        """SHA-256 hash of zone content must match after round-trip through write pipeline."""
        original_hash = hashlib.sha256(_LITERAL_CONTENT_PYTHON.encode("utf-8")).hexdigest()
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "test.oct.md")
            result = await _TOOL.execute(target_path=target, content=_DOC_EXACT_PYTHON)
            assert result["status"] == "success"
            with open(target, encoding="utf-8") as f:
                written = f.read()
            content = _find_literal_zone_content(written)
            roundtrip_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            assert roundtrip_hash == original_hash, (
                f"Hash mismatch: original={original_hash}, after round-trip={roundtrip_hash}. "
                f"Content changed from {_LITERAL_CONTENT_PYTHON!r} to {content!r}"
            )

    @pytest.mark.asyncio
    async def test_two_zone_contents_exact_equality_after_roundtrip(self) -> None:
        """Both zones in a two-zone document must be preserved exactly."""
        # Content as the parser will store it (no trailing newline before closing fence).
        content_python = 'print("hello")'
        content_json = '{"key": "value"}'
        doc = """\
===DOC===
META:
  TYPE::"TEST"
  VERSION::"1.0"

CODE::
```python
print("hello")
```

CONFIG::
```json
{"key": "value"}
```
===END===
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "test.oct.md")
            result = await _TOOL.execute(target_path=target, content=doc)
            assert result["status"] == "success"
            with open(target, encoding="utf-8") as f:
                written = f.read()
            code_content = _find_literal_zone_content(written, key="CODE")
            config_content = _find_literal_zone_content(written, key="CONFIG")
            assert code_content == content_python, f"CODE zone: expected {content_python!r}, got {code_content!r}"
            assert config_content == content_json, f"CONFIG zone: expected {content_json!r}, got {config_content!r}"


# ===========================================================================
# Issue #259: Literal zone content inside block value (KEY:) must survive
# ===========================================================================

# Reproduction case from issue #259:
# TEMPLATE: (block syntax, single colon) followed immediately by a fenced literal
# zone. After octave_write normalization the literal zone content was silently
# dropped — I1::SYNTACTIC_FIDELITY and I4::TRANSFORM_AUDITABILITY violations.
_DOC_BLOCK_WITH_LITERAL_ZONE = """\
===SCHEMA===
META:
  TYPE::PROTOCOL_DEFINITION

§6::SCHEMA_SKELETON
TEMPLATE:
```octave
===MY_SCHEMA===
META:
  TYPE::PROTOCOL_DEFINITION
===END===
```
===END===
"""

_DOC_BLOCK_WITH_LITERAL_ZONE_INDENTED = """\
===SCHEMA===
META:
  TYPE::PROTOCOL_DEFINITION

OUTER:
  TEMPLATE:
  ```octave
  ===MY_SCHEMA===
  META:
    TYPE::PROTOCOL_DEFINITION
  ===END===
  ```
===END===
"""


class TestIssue259LiteralZoneInBlockValue:
    """Issue #259: Literal zone in block value must survive octave_write normalization.

    I1::SYNTACTIC_FIDELITY — normalization must not alter semantics; literal zones
    are exempt from normalization and must be preserved exactly.
    I4::TRANSFORM_AUDITABILITY — if bits are lost there must be a receipt; silent
    dropping with no W_STRUCT or E_ code is a violation.
    """

    def test_parser_preserves_literal_zone_in_block_body(self) -> None:
        """Parser must parse the literal zone inside a block body (not drop it).

        Issue #259 RED: TEMPLATE: followed by a fence currently produces an
        empty Block node (children=[]) — the LiteralZoneValue is never parsed.
        """
        from octave_mcp.core.ast_nodes import Assignment, Block, Section
        from octave_mcp.core.parser import parse as octave_parse

        doc = octave_parse(_DOC_BLOCK_WITH_LITERAL_ZONE)
        # §6::SCHEMA_SKELETON is a Section; TEMPLATE: block is inside it.
        # Find the TEMPLATE block wherever it lives.
        template_block: Block | None = None
        for node in doc.sections:
            if isinstance(node, Block) and node.key == "TEMPLATE":
                template_block = node
                break
            if isinstance(node, Section):
                for child in node.children:
                    if isinstance(child, Block) and child.key == "TEMPLATE":
                        template_block = child
                        break

        assert template_block is not None, "TEMPLATE block not found in parsed AST"
        assert len(template_block.children) > 0, (
            "Issue #259: TEMPLATE block has no children — literal zone content was silently dropped. "
            "Expected at least one child (the literal zone)."
        )
        # The child should carry a LiteralZoneValue
        lz_found = False
        for child in template_block.children:
            if isinstance(child, Assignment) and isinstance(child.value, LiteralZoneValue):
                lz_found = True
                assert (
                    "===MY_SCHEMA===" in child.value.content
                ), f"Literal zone content should contain '===MY_SCHEMA===', got: {child.value.content!r}"
                break
        assert lz_found, (
            f"No child with LiteralZoneValue found in TEMPLATE block. " f"Children: {template_block.children!r}"
        )

    def test_emitter_preserves_literal_zone_in_block_body(self) -> None:
        """Emitter must emit the literal zone inside a block body intact.

        Issue #259 RED: After parse+emit, the literal zone content (===MY_SCHEMA===)
        is currently absent from the emitted output.
        """
        from octave_mcp.core.emitter import emit
        from octave_mcp.core.parser import parse as octave_parse

        doc = octave_parse(_DOC_BLOCK_WITH_LITERAL_ZONE)
        output = emit(doc)
        assert "===MY_SCHEMA===" in output, (
            f"Issue #259: Literal zone content ('===MY_SCHEMA===') was silently dropped "
            f"during emission. Emitted output:\n{output}"
        )
        assert "TEMPLATE:" in output, "TEMPLATE: block header must appear in output"

    @pytest.mark.asyncio
    async def test_octave_write_preserves_literal_zone_in_block_body(self) -> None:
        """octave_write normalization must not strip literal zone inside a block body.

        Issue #259 RED: The full octave_write pipeline (parse → normalize → emit)
        currently drops the literal zone content silently.
        """
        result = await _write_content_result(_DOC_BLOCK_WITH_LITERAL_ZONE)
        assert result["status"] == "success", f"Write failed: {result}"
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "test.oct.md")
            result = await _TOOL.execute(target_path=target, content=_DOC_BLOCK_WITH_LITERAL_ZONE)
            assert result["status"] == "success"
            with open(target, encoding="utf-8") as f:
                written = f.read()
        assert "===MY_SCHEMA===" in written, (
            f"Issue #259: Literal zone content dropped by octave_write normalization. " f"Written file:\n{written}"
        )
        assert "TEMPLATE:" in written, "TEMPLATE: block header must survive in written file"

    def test_round_trip_preserves_literal_zone_in_block_body(self) -> None:
        """Parse → emit must preserve the literal zone in a block body round-trip.

        Issue #259 RED: This is the core I1 fidelity check.
        """
        from octave_mcp.core.emitter import emit
        from octave_mcp.core.parser import parse as octave_parse

        doc = octave_parse(_DOC_BLOCK_WITH_LITERAL_ZONE)
        output = emit(doc)
        # The content of the literal zone must be present in the emitted output
        assert "===MY_SCHEMA===" in output, (
            "Issue #259 / I1 violation: literal zone content not preserved in round-trip. " f"Output:\n{output}"
        )
        assert "TYPE::PROTOCOL_DEFINITION" in output, (
            "Issue #259 / I1 violation: literal zone body content dropped in round-trip. " f"Output:\n{output}"
        )
