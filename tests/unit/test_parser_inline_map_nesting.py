"""Tests for inline map nesting validation (GitHub Issue #185).

Per octave-core-spec.oct.md section 5::MODES:
  INLINE_MAP_NESTING::forbidden[values_must_be_atoms]

And section 7::CANONICAL_EXAMPLES:
  // INLINE_MAP_NESTING (Forbidden pattern)
  BAD::[config::[nested::value]]
  GOOD:
    CONFIG:
      NESTED::value

Inline maps MUST contain only atomic values.
Nested inline maps or lists containing inline maps are FORBIDDEN.

Expected error: E_NESTED_INLINE_MAP::inline maps cannot contain inline maps, use block structure
"""

import pytest

from octave_mcp.core.parser import ParserError, parse


class TestNestedInlineMapRejection:
    """Test that nested inline maps are rejected with clear error messages."""

    def test_rejects_inline_map_containing_inline_map(self):
        """Direct nested inline map should be rejected.

        Pattern: [config::[nested::value]]
        The outer inline map's value is another inline map - forbidden.
        """
        content = """===TEST===
DATA::[config::[nested::value]]
===END==="""
        with pytest.raises(ParserError) as exc_info:
            parse(content)

        error = exc_info.value
        assert "E_NESTED_INLINE_MAP" in str(error) or "nested" in str(error).lower()
        assert "inline map" in str(error).lower() or "block structure" in str(error).lower()

    def test_rejects_inline_map_value_that_is_list_with_inline_map(self):
        """Inline map value that is a list containing inline maps should be rejected.

        Pattern: [config::[[nested::value]]]
        The value is a list, and that list contains an inline map.
        """
        content = """===TEST===
DATA::[config::[[nested::value]]]
===END==="""
        with pytest.raises(ParserError) as exc_info:
            parse(content)

        error = exc_info.value
        assert "E_NESTED_INLINE_MAP" in str(error) or "nested" in str(error).lower()

    def test_rejects_deeply_nested_inline_map(self):
        """Multiple levels of nesting should be rejected at first level.

        Pattern: [a::[b::[c::value]]]
        Should fail on the first level of nesting.
        """
        content = """===TEST===
DATA::[a::[b::[c::value]]]
===END==="""
        with pytest.raises(ParserError) as exc_info:
            parse(content)

        error = exc_info.value
        assert "E_NESTED_INLINE_MAP" in str(error) or "nested" in str(error).lower()

    def test_error_message_provides_guidance(self):
        """Error message should guide user toward correct block structure."""
        content = """===TEST===
DATA::[config::[nested::value]]
===END==="""
        with pytest.raises(ParserError) as exc_info:
            parse(content)

        error_msg = str(exc_info.value)
        # Should suggest using block structure
        assert "block" in error_msg.lower() or "structure" in error_msg.lower()


class TestValidInlineMapsStillWork:
    """Ensure valid inline maps without nesting continue to work."""

    def test_simple_inline_map_with_atoms(self):
        """Inline map with atomic values (strings, numbers) should work."""
        content = """===TEST===
DATA::[name::Alice, age::30, active::true]
===END==="""
        doc = parse(content)
        assert doc is not None
        assert doc.name == "TEST"

    def test_inline_map_with_string_value(self):
        """Inline map with quoted string value should work."""
        content = """===TEST===
DATA::[key::"string value", other::123]
===END==="""
        doc = parse(content)
        assert doc is not None

    def test_inline_map_with_expression_value(self):
        """Inline map with flow expression value should work.

        Expressions like A->B are atomic (single rendered value).
        """
        content = """===TEST===
DATA::[flow::A->B, synthesis::X+Y]
===END==="""
        doc = parse(content)
        assert doc is not None

    def test_list_of_inline_maps_is_valid(self):
        """List containing multiple inline maps is valid.

        Pattern: [[a::1], [b::2], [c::3]]
        Each inline map is atomic, the list just holds them.
        This is NOT nested inline maps - the values 1,2,3 are atoms.
        """
        content = """===TEST===
DATA::[[a::1], [b::2], [c::3]]
===END==="""
        doc = parse(content)
        assert doc is not None

    def test_mixed_list_with_atoms_and_simple_inline_maps(self):
        """List with both atoms and simple inline maps is valid."""
        content = """===TEST===
DATA::[item1, [k::v], item2, [k2::v2]]
===END==="""
        doc = parse(content)
        assert doc is not None


class TestNestedInlineMapEdgeCases:
    """Edge cases for inline map nesting detection."""

    def test_inline_map_in_block_assignment_value(self):
        """Inline map as block assignment value is fine if it contains atoms."""
        content = """===TEST===
META:
  CONFIG::[key::value, other::123]
===END==="""
        doc = parse(content)
        assert doc is not None

    def test_inline_map_with_list_of_atoms_is_valid(self):
        """Inline map value that is a list of atoms is valid.

        Pattern: [config::[a, b, c]]
        The value [a, b, c] is a list of atoms, not inline maps.
        """
        content = """===TEST===
DATA::[config::[a, b, c]]
===END==="""
        doc = parse(content)
        assert doc is not None

    def test_inline_map_with_empty_list_is_valid(self):
        """Inline map value that is empty list is valid.

        Pattern: [config::[]]
        Empty list is an atom (no inline maps inside).
        """
        content = """===TEST===
DATA::[config::[]]
===END==="""
        doc = parse(content)
        assert doc is not None

    def test_inline_map_with_nested_list_of_atoms_is_valid(self):
        """Inline map value with nested list of atoms is valid.

        Pattern: [config::[[a, b], [c, d]]]
        The value [[a,b],[c,d]] is a list of lists of atoms.
        """
        content = """===TEST===
DATA::[config::[[a, b], [c, d]]]
===END==="""
        doc = parse(content)
        assert doc is not None


class TestErrorLineInfo:
    """Test that error includes location information."""

    def test_error_includes_line_number(self):
        """Error should include line number for the nested inline map."""
        content = """===TEST===
META:
  TYPE::TEST
DATA::[config::[nested::value]]
===END==="""
        with pytest.raises(ParserError) as exc_info:
            parse(content)

        error = exc_info.value
        # ParserError includes token info with line number
        assert error.token is not None or "line" in str(error).lower()

    def test_error_includes_key_context(self):
        """Error message should identify which key has the nested value."""
        content = """===TEST===
DATA::[config::[nested::value]]
===END==="""
        with pytest.raises(ParserError) as exc_info:
            parse(content)

        error_msg = str(exc_info.value)
        # Should mention the key name for context
        assert "config" in error_msg.lower() or "nested" in error_msg.lower()
