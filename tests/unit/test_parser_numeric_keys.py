"""Tests for numeric key detection and warning in OCTAVE parser (GitHub Issue #348).

Numeric keys (e.g., 1::"value", 2::"value") are not valid OCTAVE identifiers.
When encountered in block children, the parser must NOT silently drop them.
Instead, it must:
1. Emit a W_NUMERIC_KEY_DROPPED warning per I4 (Transform Auditability)
2. Include the dropped key and value in the warning for recovery
3. Continue parsing remaining children (not break the loop)

I4 Immutable: "every transformation logged with stable ids"
I1 Immutable: "normalization alters syntax never semantics" — silent drop violates this.
"""

import pytest

from octave_mcp.core.parser import parse_with_warnings


class TestNumericKeyWarning:
    """Test that numeric keys in block children emit warnings instead of being silently dropped."""

    def test_numeric_keys_emit_warning(self):
        """Should emit W_NUMERIC_KEY_DROPPED warning for numeric keys in blocks.

        Per I4: "if bits lost must have receipt"
        """
        content = """===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
ITEMS:
  1::"First item"
  2::"Second item"
===END==="""
        doc, warnings = parse_with_warnings(content)

        # Document should parse without error
        assert doc is not None
        assert doc.name == "TEST"

        # I4 Audit: Should emit warnings for numeric keys
        numeric_warnings = [w for w in warnings if w.get("subtype") == "numeric_key_dropped"]
        assert (
            len(numeric_warnings) >= 2
        ), f"Expected at least 2 numeric key warnings, got {len(numeric_warnings)}: {warnings}"

    def test_numeric_key_warning_structure(self):
        """Warning should contain key, value, and line info for recovery."""
        content = """===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
DATA:
  1::"First item"
===END==="""
        doc, warnings = parse_with_warnings(content)

        numeric_warnings = [w for w in warnings if w.get("subtype") == "numeric_key_dropped"]
        assert len(numeric_warnings) >= 1, f"Expected numeric key warning, got {warnings}"

        w = numeric_warnings[0]
        assert w.get("type") == "lenient_parse"
        assert w.get("subtype") == "numeric_key_dropped"
        assert w.get("key") == "1"
        assert w.get("value") == "First item"
        assert w.get("line") is not None
        assert "W_NUMERIC_KEY_DROPPED" in w.get("message", "")

    def test_numeric_key_warning_preserves_value_for_recovery(self):
        """Warning message must include original key and value for data recovery."""
        content = """===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
ITEMS:
  42::"The answer"
===END==="""
        doc, warnings = parse_with_warnings(content)

        numeric_warnings = [w for w in warnings if w.get("subtype") == "numeric_key_dropped"]
        assert len(numeric_warnings) >= 1
        w = numeric_warnings[0]
        # Value must be recoverable from warning
        assert w.get("key") == "42"
        assert w.get("value") == "The answer"

    def test_numeric_keys_do_not_block_subsequent_children(self):
        """Numeric keys should not prevent parsing of subsequent valid children.

        Before fix: the first numeric key caused the parser to break out of
        the block child loop, silently dropping all remaining content.
        """
        content = """===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
DATA:
  1::"Numeric first"
  VALID_KEY::"This should be parsed"
  2::"Numeric second"
  ANOTHER_KEY::"Also parsed"
===END==="""
        doc, warnings = parse_with_warnings(content)

        # Valid keys after numeric keys should still be parsed
        data_block = doc.sections[0]
        assert data_block.key == "DATA"

        # Check that valid children are present
        child_keys = [c.key for c in data_block.children]
        assert "VALID_KEY" in child_keys, f"VALID_KEY should be parsed after numeric key, got children: {child_keys}"
        assert (
            "ANOTHER_KEY" in child_keys
        ), f"ANOTHER_KEY should be parsed after numeric key, got children: {child_keys}"

        # Numeric keys should produce warnings
        numeric_warnings = [w for w in warnings if w.get("subtype") == "numeric_key_dropped"]
        assert len(numeric_warnings) >= 2

    def test_numeric_key_with_bare_value(self):
        """Numeric keys with bare (unquoted) values should also warn."""
        content = """===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
DATA:
  1::BARE_VALUE
===END==="""
        doc, warnings = parse_with_warnings(content)

        numeric_warnings = [w for w in warnings if w.get("subtype") == "numeric_key_dropped"]
        assert len(numeric_warnings) >= 1
        w = numeric_warnings[0]
        assert w.get("key") == "1"
        assert w.get("value") == "BARE_VALUE"

    def test_numeric_key_with_list_value(self):
        """Numeric keys with list values should also warn."""
        content = """===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
DATA:
  1::[a,b,c]
===END==="""
        doc, warnings = parse_with_warnings(content)

        numeric_warnings = [w for w in warnings if w.get("subtype") == "numeric_key_dropped"]
        assert len(numeric_warnings) >= 1
        w = numeric_warnings[0]
        assert w.get("key") == "1"

    def test_numeric_keys_in_nested_block(self):
        """Numeric keys in nested blocks should also emit warnings."""
        content = """===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
OUTER:
  INNER:
    1::"Nested numeric"
===END==="""
        doc, warnings = parse_with_warnings(content)

        numeric_warnings = [w for w in warnings if w.get("subtype") == "numeric_key_dropped"]
        assert len(numeric_warnings) >= 1, f"Expected numeric key warning in nested block, got {warnings}"


class TestNumericKeyWriteToolIntegration:
    """Test that numeric key warnings surface in octave_write response."""

    @pytest.mark.asyncio
    async def test_numeric_keys_produce_corrections_in_write(self):
        """octave_write should surface W_NUMERIC_KEY_DROPPED in corrections array."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()
        result = await tool.execute(
            target_path="/tmp/test_numeric_key_corrections.oct.md",
            content="""===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
ITEMS:
  1::"First item"
  2::"Second item"
===END===""",
            corrections_only=True,
        )

        corrections = result.get("corrections", [])
        numeric_corrections = [c for c in corrections if c.get("code") == "W_NUMERIC_KEY_DROPPED"]
        assert len(numeric_corrections) >= 2, (
            f"Expected W_NUMERIC_KEY_DROPPED corrections in write response, " f"got corrections: {corrections}"
        )

        # Verify correction structure
        c = numeric_corrections[0]
        assert c.get("key") is not None
        assert c.get("value") is not None
        assert c.get("safe") is False  # Data loss = not safe
        assert c.get("semantics_changed") is True  # Content removed = semantics changed

    @pytest.mark.asyncio
    async def test_numeric_keys_do_not_produce_empty_section_silently(self):
        """octave_write must not produce empty section without warning.

        This is the core I4 violation: before the fix, ITEMS section was
        emitted empty with no warning in corrections.
        """
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()
        result = await tool.execute(
            target_path="/tmp/test_numeric_key_empty.oct.md",
            content="""===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
ITEMS:
  1::"First item"
===END===""",
            corrections_only=True,
        )

        # If ITEMS section is empty in output, there MUST be a warning
        corrections = result.get("corrections", [])
        numeric_corrections = [c for c in corrections if c.get("code") == "W_NUMERIC_KEY_DROPPED"]
        assert len(numeric_corrections) >= 1, "ITEMS section content dropped but no W_NUMERIC_KEY_DROPPED correction"
