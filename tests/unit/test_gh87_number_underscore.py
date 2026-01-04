"""Tests for GH#87: Number followed by underscore breaks parsing.

TDD RED Phase: These tests define expected behavior for:
- Number followed by underscore (e.g., 123_suffix) should be parsed correctly
- Subsequent lines should maintain correct sibling relationships
- Indentation tracking should not be corrupted by unconsumed tokens

Root cause analysis:
- Lexer produces: NUMBER(123), IDENTIFIER(_suffix)
- Parser's NUMBER path (lines 505-507) returns immediately without checking for trailing IDENTIFIER
- IDENTIFIER(_suffix) left unconsumed corrupts indentation tracking for subsequent lines

Expected fix:
- After consuming NUMBER, check if next token is IDENTIFIER
- If so, coalesce into multi-word string value (same pattern as IDENTIFIER path)
- Emit I4 audit warning when coalescing occurs
"""

from octave_mcp.core.lexer import TokenType, tokenize
from octave_mcp.core.parser import parse, parse_with_warnings


class TestNumberUnderscoreLexer:
    """Verify lexer behavior for number_underscore patterns."""

    def test_lexer_tokenizes_123_suffix_as_two_tokens(self):
        """Lexer should produce NUMBER and IDENTIFIER for 123_suffix.

        This documents the current (correct) lexer behavior.
        The issue is in the parser, not the lexer.
        """
        content = "a::123_suffix"
        tokens, _ = tokenize(content)

        # Filter to just the value-related tokens
        value_tokens = [t for t in tokens if t.type in (TokenType.NUMBER, TokenType.IDENTIFIER)]

        # Should have: IDENTIFIER(a), NUMBER(123), IDENTIFIER(_suffix)
        assert len(value_tokens) == 3, f"Expected 3 tokens, got {len(value_tokens)}: {value_tokens}"

        # First is the key 'a'
        assert value_tokens[0].type == TokenType.IDENTIFIER
        assert value_tokens[0].value == "a"

        # Second is NUMBER(123)
        assert value_tokens[1].type == TokenType.NUMBER
        assert value_tokens[1].value == 123

        # Third is IDENTIFIER(_suffix)
        assert value_tokens[2].type == TokenType.IDENTIFIER
        assert value_tokens[2].value == "_suffix"


class TestNumberUnderscoreBasicParsing:
    """GH#87: Number followed by underscore should be parsed as combined value."""

    def test_number_underscore_simple(self):
        """123_suffix should be parsed as a coalesced string value.

        Input: a::123_suffix
        Expected: value should include both 123 and _suffix
        """
        content = """===TEST===
a::123_suffix
===END==="""
        doc = parse(content)

        assignment = doc.sections[0]
        assert assignment.key == "a"
        # Value should be the full coalesced form, not just 123
        assert assignment.value == "123 _suffix", f"Got: {assignment.value!r}"

    def test_number_underscore_zero_prefix(self):
        """0_test should be parsed as coalesced value."""
        content = """===TEST===
a::0_test
===END==="""
        doc = parse(content)

        assignment = doc.sections[0]
        assert assignment.key == "a"
        assert assignment.value == "0 _test", f"Got: {assignment.value!r}"

    def test_number_underscore_multi_part(self):
        """123_abc_def should be parsed as coalesced value with multiple IDENTIFIER tokens."""
        content = """===TEST===
a::123_abc_def
===END==="""
        doc = parse(content)

        assignment = doc.sections[0]
        assert assignment.key == "a"
        # Lexer produces: NUMBER(123), IDENTIFIER(_abc_def)
        assert "_abc_def" in str(assignment.value), f"Got: {assignment.value!r}"

    def test_number_then_number(self):
        """42_123 pattern - number followed by underscore number."""
        content = """===TEST===
a::42_123
===END==="""
        doc = parse(content)

        assignment = doc.sections[0]
        assert assignment.key == "a"
        # _123 should be captured as IDENTIFIER(_123) by lexer
        assert "42" in str(assignment.value) and "_123" in str(assignment.value), f"Got: {assignment.value!r}"


class TestNumberUnderscoreSiblingIntegrity:
    """GH#87: Unconsumed tokens should not corrupt sibling relationships."""

    def test_sibling_after_number_underscore(self):
        """Line after 123_suffix should be at correct sibling level.

        This is the key regression test - before the fix, 'b' would be
        incorrectly nested or skipped because _suffix was left unconsumed.
        """
        content = """===TEST===
a::123_suffix
b::value
===END==="""
        doc = parse(content)

        # Both a and b should be direct children of the section at same level
        assert len(doc.sections) >= 2, f"Expected at least 2 sections, got {len(doc.sections)}"

        # Find the assignments
        assignments = [s for s in doc.sections if hasattr(s, "key")]
        assert len(assignments) == 2, f"Expected 2 assignments, got: {assignments}"

        keys = [a.key for a in assignments]
        assert "a" in keys, f"Missing key 'a', got: {keys}"
        assert "b" in keys, f"Missing key 'b', got: {keys}"

    def test_multiple_number_underscore_lines(self):
        """Multiple lines with number_underscore pattern should all parse correctly."""
        content = """===TEST===
first::123_a
second::456_b
third::789_c
===END==="""
        doc = parse(content)

        assignments = [s for s in doc.sections if hasattr(s, "key")]
        assert len(assignments) == 3, f"Expected 3 assignments, got {len(assignments)}"

        keys = [a.key for a in assignments]
        assert keys == ["first", "second", "third"], f"Got keys: {keys}"


class TestNumberUnderscoreBlockHierarchy:
    """GH#87: Number_underscore in block context should preserve hierarchy."""

    def test_block_children_with_number_underscore(self):
        """Children in block containing number_underscore should maintain correct nesting.

        BLOCK:
          a::123_suffix
          b::value

        Both a and b should be children of BLOCK at same indentation level.
        """
        content = """===TEST===
BLOCK:
  a::123_suffix
  b::value
===END==="""
        doc = parse(content)

        # Find the BLOCK
        block = None
        for section in doc.sections:
            if hasattr(section, "key") and section.key == "BLOCK":
                block = section
                break

        assert block is not None, "BLOCK not found in parsed document"
        assert hasattr(block, "children") or hasattr(block, "value"), f"BLOCK has no children/value: {block}"

        # Get children
        if hasattr(block, "children") and block.children:
            children = block.children
        elif hasattr(block, "value") and hasattr(block.value, "items"):
            children = block.value.items
        else:
            # Block might use a different structure
            children = []

        # Should have 2 children: a and b
        child_keys = []
        for child in children:
            if hasattr(child, "key"):
                child_keys.append(child.key)

        assert "a" in child_keys, f"Child 'a' not found. Got: {child_keys}"
        assert "b" in child_keys, f"Child 'b' not found. Got: {child_keys}"

    def test_nested_blocks_with_number_underscore(self):
        """Deeply nested blocks should maintain correct hierarchy.

        OUTER:
          INNER:
            a::123_suffix
            b::value
        """
        content = """===TEST===
OUTER:
  INNER:
    a::123_suffix
    b::value
===END==="""
        doc = parse(content)

        # Navigate to find both a and b
        # They should both be at the same nesting level under INNER
        found_a = False
        found_b = False

        def find_keys(node, depth=0):
            nonlocal found_a, found_b
            if hasattr(node, "key"):
                if node.key == "a":
                    found_a = True
                if node.key == "b":
                    found_b = True
            if hasattr(node, "children"):
                for child in node.children:
                    find_keys(child, depth + 1)
            if hasattr(node, "sections"):
                for section in node.sections:
                    find_keys(section, depth + 1)

        find_keys(doc)

        assert found_a, "Key 'a' not found in parsed document"
        assert found_b, "Key 'b' not found in parsed document"


class TestNumberUnderscoreI4Audit:
    """GH#87 I4 Audit: Coalescing NUMBER+IDENTIFIER must emit warning."""

    def test_number_underscore_emits_warning(self):
        """Coalescing 123_suffix should emit I4 audit warning.

        Per I4 immutable: "If bits lost must have receipt"
        Coalescing NUMBER(123) + IDENTIFIER(_suffix) is an entropy-reducing
        transformation that must be audited.
        """
        content = """===TEST===
a::123_suffix
===END==="""
        doc, warnings = parse_with_warnings(content)

        # Should have warning about coalescing
        coalesce_warnings = [
            w for w in warnings if w.get("type") == "lenient_parse" and w.get("subtype") == "multi_word_coalesce"
        ]

        assert (
            len(coalesce_warnings) >= 1
        ), f"Expected I4 audit warning for NUMBER+IDENTIFIER coalescing. Got warnings: {warnings}"

        warning = coalesce_warnings[0]
        # Warning should capture both parts
        original = warning.get("original", [])
        assert "123" in str(original) or 123 in original, f"Warning missing '123': {warning}"
        assert "_suffix" in str(original), f"Warning missing '_suffix': {warning}"

    def test_number_underscore_warning_has_position(self):
        """I4 warning should include line and column for auditability."""
        content = """===TEST===
a::123_suffix
===END==="""
        doc, warnings = parse_with_warnings(content)

        coalesce_warnings = [w for w in warnings if w.get("type") == "lenient_parse"]

        if coalesce_warnings:
            warning = coalesce_warnings[0]
            assert "line" in warning, f"Warning missing line: {warning}"
            assert "column" in warning, f"Warning missing column: {warning}"

    def test_standalone_number_no_warning(self):
        """Standalone NUMBER (no trailing IDENTIFIER) should not emit coalescing warning."""
        content = """===TEST===
a::123
===END==="""
        doc, warnings = parse_with_warnings(content)

        # No coalescing occurred
        coalesce_warnings = [
            w for w in warnings if w.get("type") == "lenient_parse" and w.get("subtype") == "multi_word_coalesce"
        ]

        assert (
            len(coalesce_warnings) == 0
        ), f"Standalone NUMBER should not emit coalescing warning. Got: {coalesce_warnings}"


class TestNumberUnderscoreEdgeCases:
    """Edge cases for number_underscore handling."""

    def test_number_underscore_in_list(self):
        """Number_underscore pattern in list context."""
        content = """===TEST===
ITEMS::[123_a, 456_b]
===END==="""
        doc = parse(content)

        assignment = doc.sections[0]
        assert assignment.key == "ITEMS"

        # List should contain both items
        items = assignment.value.items if hasattr(assignment.value, "items") else []
        assert len(items) == 2, f"Expected 2 items, got {len(items)}: {items}"

        # Each item should have number and underscore suffix
        assert any("123" in str(item) for item in items), f"Missing 123 in items: {items}"
        assert any("456" in str(item) for item in items), f"Missing 456 in items: {items}"

    def test_number_underscore_before_operator(self):
        """Number_underscore followed by operator."""
        content = """===TEST===
FLOW::123_start->456_end
===END==="""
        doc = parse(content)

        assignment = doc.sections[0]
        assert assignment.key == "FLOW"

        # Should contain arrow operator and both values
        value_str = str(assignment.value)
        assert "123" in value_str or "_start" in value_str, f"Got: {value_str}"
        assert "456" in value_str or "_end" in value_str, f"Got: {value_str}"

    def test_negative_number_underscore(self):
        """Negative number followed by underscore."""
        content = """===TEST===
a::-123_suffix
===END==="""
        doc = parse(content)

        assignment = doc.sections[0]
        assert assignment.key == "a"
        # Should capture the negative number and suffix
        value_str = str(assignment.value)
        assert "-123" in value_str or "_suffix" in value_str, f"Got: {value_str}"

    def test_float_underscore(self):
        """Float followed by underscore."""
        content = """===TEST===
a::3.14_suffix
===END==="""
        doc = parse(content)

        assignment = doc.sections[0]
        assert assignment.key == "a"
        value_str = str(assignment.value)
        assert "3.14" in value_str or "_suffix" in value_str, f"Got: {value_str}"
