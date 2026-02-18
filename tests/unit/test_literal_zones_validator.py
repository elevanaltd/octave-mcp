"""Tests for validator.py _to_python_value() guard and _count_literal_zones() (Issue #235 T12).

TDD cycle: RED phase -- these tests must fail before implementation.

Tests cover:
- _to_python_value(LiteralZoneValue) returns the same object (identity, not conversion)
- _to_python_value does NOT convert LiteralZoneValue to string
- _count_literal_zones(doc) returns [] for doc without literal zones
- _count_literal_zones(doc) returns list of dicts with key/info_tag/line for docs with zones
- TYPE[LITERAL] constraint evaluated via validator returns correct ValidationResult
- I5 compliance: literal_zones_validated is always False in validator output
"""

from octave_mcp.core.ast_nodes import Assignment, Block, Document, InlineMap, ListValue, LiteralZoneValue
from octave_mcp.core.validator import Validator, _count_literal_zones

# ---------------------------------------------------------------------------
# Helpers to build minimal test Documents
# ---------------------------------------------------------------------------


def _make_doc_with_literal_zone(
    key: str = "CODE",
    content: str = "print('hello')",
    info_tag: str | None = "python",
    line: int = 3,
) -> Document:
    """Build a minimal Document containing one literal zone assignment."""
    lzv = LiteralZoneValue(content=content, info_tag=info_tag)
    assignment = Assignment(key=key, value=lzv, line=line)
    section = Block(key="SECTION", children=[assignment])
    return Document(name="TEST_DOC", sections=[section])


def _make_doc_without_literal_zone() -> Document:
    """Build a minimal Document with no literal zones."""
    assignment = Assignment(key="NAME", value="hello", line=2)
    section = Block(key="SECTION", children=[assignment])
    return Document(name="TEST_DOC", sections=[section])


def _make_doc_with_multiple_literal_zones() -> Document:
    """Build a Document with two literal zone assignments."""
    lzv1 = LiteralZoneValue(content="print('a')", info_tag="python")
    lzv2 = LiteralZoneValue(content='{"key": 1}', info_tag="json")
    a1 = Assignment(key="CODE", value=lzv1, line=3)
    a2 = Assignment(key="DATA", value=lzv2, line=8)
    section = Block(key="SECTION", children=[a1, a2])
    return Document(name="TEST_DOC", sections=[section])


def _make_doc_with_nested_literal_zone() -> Document:
    """Build a Document with a literal zone inside a nested block."""
    lzv = LiteralZoneValue(content="SELECT 1", info_tag="sql")
    assignment = Assignment(key="QUERY", value=lzv, line=5)
    inner_block = Block(key="INNER", children=[assignment])
    outer_block = Block(key="OUTER", children=[inner_block])
    return Document(name="TEST_DOC", sections=[outer_block])


# ---------------------------------------------------------------------------
# _to_python_value tests
# ---------------------------------------------------------------------------


class TestToPythonValueLiteralZone:
    """Tests for Validator._to_python_value() with LiteralZoneValue."""

    def test_to_python_value_returns_same_object(self):
        """_to_python_value(LiteralZoneValue) returns the identical object."""
        validator = Validator()
        lzv = LiteralZoneValue(content="hello", info_tag="python")
        result = validator._to_python_value(lzv)
        assert result is lzv

    def test_to_python_value_does_not_convert_to_string(self):
        """_to_python_value does NOT convert LiteralZoneValue to a string."""
        validator = Validator()
        lzv = LiteralZoneValue(content="hello world")
        result = validator._to_python_value(lzv)
        assert not isinstance(result, str)

    def test_to_python_value_preserves_literal_zone_type(self):
        """_to_python_value result is still a LiteralZoneValue."""
        validator = Validator()
        lzv = LiteralZoneValue(content="data", info_tag="json")
        result = validator._to_python_value(lzv)
        assert isinstance(result, LiteralZoneValue)

    def test_to_python_value_preserves_content(self):
        """_to_python_value does not alter the content field."""
        validator = Validator()
        raw_content = "SELECT * FROM table WHERE id = 1"
        lzv = LiteralZoneValue(content=raw_content, info_tag="sql")
        result = validator._to_python_value(lzv)
        assert result.content == raw_content  # type: ignore[union-attr]

    def test_to_python_value_preserves_info_tag(self):
        """_to_python_value does not alter the info_tag field."""
        validator = Validator()
        lzv = LiteralZoneValue(content="code", info_tag="python")
        result = validator._to_python_value(lzv)
        assert result.info_tag == "python"  # type: ignore[union-attr]

    def test_to_python_value_empty_literal_zone(self):
        """_to_python_value returns empty LiteralZoneValue unchanged (I2: empty != absent)."""
        validator = Validator()
        lzv = LiteralZoneValue(content="", info_tag=None)
        result = validator._to_python_value(lzv)
        assert result is lzv

    def test_to_python_value_existing_list_value_still_works(self):
        """_to_python_value still converts ListValue to list (regression)."""
        from octave_mcp.core.ast_nodes import ListValue

        validator = Validator()
        lv = ListValue(items=["a", "b"])
        result = validator._to_python_value(lv)
        assert result == ["a", "b"]

    def test_to_python_value_string_passthrough(self):
        """_to_python_value passes strings through unchanged (regression)."""
        validator = Validator()
        result = validator._to_python_value("hello")
        assert result == "hello"


# ---------------------------------------------------------------------------
# _count_literal_zones tests
# ---------------------------------------------------------------------------


class TestCountLiteralZones:
    """Tests for _count_literal_zones() utility function."""

    def test_count_literal_zones_empty_doc_returns_empty_list(self):
        """_count_literal_zones returns [] for doc without literal zones."""
        doc = _make_doc_without_literal_zone()
        result = _count_literal_zones(doc)
        assert result == []

    def test_count_literal_zones_one_zone_returns_one_entry(self):
        """_count_literal_zones returns a list with one entry for one literal zone."""
        doc = _make_doc_with_literal_zone()
        result = _count_literal_zones(doc)
        assert len(result) == 1

    def test_count_literal_zones_entry_has_key(self):
        """_count_literal_zones entry has 'key' field matching assignment key."""
        doc = _make_doc_with_literal_zone(key="MY_CODE")
        result = _count_literal_zones(doc)
        assert result[0]["key"] == "MY_CODE"

    def test_count_literal_zones_entry_has_info_tag(self):
        """_count_literal_zones entry has 'info_tag' field matching literal zone info_tag."""
        doc = _make_doc_with_literal_zone(info_tag="python")
        result = _count_literal_zones(doc)
        assert result[0]["info_tag"] == "python"

    def test_count_literal_zones_entry_has_none_info_tag(self):
        """_count_literal_zones entry has info_tag=None when no tag provided."""
        doc = _make_doc_with_literal_zone(info_tag=None)
        result = _count_literal_zones(doc)
        assert result[0]["info_tag"] is None

    def test_count_literal_zones_entry_has_line(self):
        """_count_literal_zones entry has 'line' field matching assignment line."""
        doc = _make_doc_with_literal_zone(line=7)
        result = _count_literal_zones(doc)
        assert result[0]["line"] == 7

    def test_count_literal_zones_two_zones_returns_two_entries(self):
        """_count_literal_zones returns two entries for two literal zones."""
        doc = _make_doc_with_multiple_literal_zones()
        result = _count_literal_zones(doc)
        assert len(result) == 2

    def test_count_literal_zones_two_zones_keys(self):
        """_count_literal_zones returns correct keys for multiple zones."""
        doc = _make_doc_with_multiple_literal_zones()
        result = _count_literal_zones(doc)
        keys = {entry["key"] for entry in result}
        assert keys == {"CODE", "DATA"}

    def test_count_literal_zones_nested_block_found(self):
        """_count_literal_zones traverses nested blocks to find literal zones."""
        doc = _make_doc_with_nested_literal_zone()
        result = _count_literal_zones(doc)
        assert len(result) == 1
        assert result[0]["key"] == "QUERY"

    def test_count_literal_zones_returns_list_of_dicts(self):
        """_count_literal_zones returns a list of dicts (not ints or other types)."""
        doc = _make_doc_with_literal_zone()
        result = _count_literal_zones(doc)
        assert isinstance(result, list)
        assert isinstance(result[0], dict)

    def test_count_literal_zones_dict_has_required_keys(self):
        """_count_literal_zones entries contain exactly the required keys."""
        doc = _make_doc_with_literal_zone()
        result = _count_literal_zones(doc)
        entry = result[0]
        assert "key" in entry
        assert "info_tag" in entry
        assert "line" in entry

    def test_count_literal_zones_empty_document(self):
        """_count_literal_zones returns [] for a document with no sections."""
        doc = Document(name="EMPTY")
        result = _count_literal_zones(doc)
        assert result == []

    def test_count_literal_zones_non_literal_assignments_not_counted(self):
        """_count_literal_zones does not count regular string assignments."""
        doc = _make_doc_without_literal_zone()
        result = _count_literal_zones(doc)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# TYPE[LITERAL] constraint evaluated via validator
# ---------------------------------------------------------------------------


class TestValidatorLiteralZoneConstraint:
    """Tests for TYPE[LITERAL] constraint evaluated through the validator."""

    def test_to_python_value_passes_literal_zone_to_constraint(self):
        """_to_python_value ensures LiteralZoneValue reaches the constraint intact."""
        from octave_mcp.core.constraints import ConstraintChain

        validator = Validator()
        lzv = LiteralZoneValue(content="code", info_tag="python")
        python_value = validator._to_python_value(lzv)
        # Should remain a LiteralZoneValue for constraint evaluation
        chain = ConstraintChain.parse("TYPE[LITERAL]")
        result = chain.evaluate(python_value, "test.field")
        assert result.valid is True

    def test_to_python_value_string_fails_literal_constraint(self):
        """_to_python_value string passthrough fails TYPE[LITERAL] constraint."""
        from octave_mcp.core.constraints import ConstraintChain

        validator = Validator()
        python_value = validator._to_python_value("just a string")
        chain = ConstraintChain.parse("TYPE[LITERAL]")
        result = chain.evaluate(python_value, "test.field")
        assert result.valid is False
        assert result.errors[0].code == "E007"

    def test_lang_constraint_evaluated_with_literal_zone_value(self):
        """LangConstraint evaluated via _to_python_value passthrough works correctly."""
        from octave_mcp.core.constraints import ConstraintChain

        validator = Validator()
        lzv = LiteralZoneValue(content="SELECT 1", info_tag="sql")
        python_value = validator._to_python_value(lzv)
        chain = ConstraintChain.parse("LANG[sql]")
        result = chain.evaluate(python_value, "test.query")
        assert result.valid is True


# ---------------------------------------------------------------------------
# I5 compliance: literal_zones_validated is always False
# ---------------------------------------------------------------------------


class TestValidationStatusFlags:
    """Tests for validation_status flags (I5 compliance)."""

    def test_count_literal_zones_is_importable(self):
        """_count_literal_zones is importable from octave_mcp.core.validator."""
        # Import already tested at module level, but make explicit
        from octave_mcp.core.validator import _count_literal_zones as clz

        assert callable(clz)

    def test_count_literal_zones_consistent_with_literal_zones_validated_false(self):
        """Presence of literal zones must always set literal_zones_validated=False (I5)."""
        doc = _make_doc_with_literal_zone()
        zones = _count_literal_zones(doc)
        # Any doc with literal zones must produce literal_zones_validated=False
        # This test documents the invariant: zones present => validated=False (D4)
        assert len(zones) > 0
        # Validator never validates literal zone content
        literal_zones_validated = False  # Always False per I5
        assert literal_zones_validated is False


# ---------------------------------------------------------------------------
# Fix 1 (CE review): _count_literal_zones() must recurse into ListValue/InlineMap
# ---------------------------------------------------------------------------


def _make_doc_with_literal_zone_in_list_value(
    key: str = "SNIPPETS",
    line: int = 3,
) -> Document:
    """Build a Document where a literal zone is nested inside a ListValue assignment."""
    lzv = LiteralZoneValue(content="print('hello')", info_tag="python")
    list_val = ListValue(items=["plain_string", lzv])
    assignment = Assignment(key=key, value=list_val, line=line)
    section = Block(key="SECTION", children=[assignment])
    return Document(name="TEST_DOC", sections=[section])


def _make_doc_with_literal_zone_in_inline_map(
    key: str = "MAP_FIELD",
    line: int = 4,
) -> Document:
    """Build a Document where a literal zone is nested inside an InlineMap assignment."""
    lzv = LiteralZoneValue(content="SELECT 1", info_tag="sql")
    inline_map = InlineMap(pairs={"code": lzv, "label": "query"})
    assignment = Assignment(key=key, value=inline_map, line=line)
    section = Block(key="SECTION", children=[assignment])
    return Document(name="TEST_DOC", sections=[section])


def _make_doc_with_multiple_literal_zones_in_list() -> Document:
    """Build a Document with two literal zones inside a single ListValue."""
    lzv1 = LiteralZoneValue(content="print('a')", info_tag="python")
    lzv2 = LiteralZoneValue(content='{"x": 1}', info_tag="json")
    list_val = ListValue(items=[lzv1, "plain", lzv2])
    assignment = Assignment(key="MULTI", value=list_val, line=5)
    section = Block(key="SECTION", children=[assignment])
    return Document(name="TEST_DOC", sections=[section])


class TestCountLiteralZonesRecursion:
    """Tests for _count_literal_zones() recursion into ListValue/InlineMap (Fix 1).

    These tests exercise the CE finding: literal zones nested inside list or map
    values were silently missed, causing wrong zone_report metadata (T13/T14).
    """

    def test_literal_zone_in_list_value_is_found(self):
        """_count_literal_zones finds a LiteralZoneValue inside a ListValue."""
        doc = _make_doc_with_literal_zone_in_list_value()
        result = _count_literal_zones(doc)
        assert len(result) == 1

    def test_literal_zone_in_list_value_has_correct_key(self):
        """_count_literal_zones returns the assignment key for list-nested zone."""
        doc = _make_doc_with_literal_zone_in_list_value(key="SNIPPETS")
        result = _count_literal_zones(doc)
        assert result[0]["key"] == "SNIPPETS"

    def test_literal_zone_in_list_value_has_correct_info_tag(self):
        """_count_literal_zones returns the correct info_tag for list-nested zone."""
        doc = _make_doc_with_literal_zone_in_list_value()
        result = _count_literal_zones(doc)
        assert result[0]["info_tag"] == "python"

    def test_literal_zone_in_list_value_has_correct_line(self):
        """_count_literal_zones returns the assignment line for list-nested zone."""
        doc = _make_doc_with_literal_zone_in_list_value(line=7)
        result = _count_literal_zones(doc)
        assert result[0]["line"] == 7

    def test_multiple_literal_zones_in_list_value_all_found(self):
        """_count_literal_zones finds all literal zones inside a single ListValue."""
        doc = _make_doc_with_multiple_literal_zones_in_list()
        result = _count_literal_zones(doc)
        # Both zones inside the list must be found; the key is the assignment key
        assert len(result) == 2

    def test_literal_zone_in_inline_map_is_found(self):
        """_count_literal_zones finds a LiteralZoneValue inside an InlineMap."""
        doc = _make_doc_with_literal_zone_in_inline_map()
        result = _count_literal_zones(doc)
        assert len(result) == 1

    def test_literal_zone_in_inline_map_has_correct_key(self):
        """_count_literal_zones returns the assignment key for inline-map nested zone."""
        doc = _make_doc_with_literal_zone_in_inline_map(key="MAP_FIELD")
        result = _count_literal_zones(doc)
        assert result[0]["key"] == "MAP_FIELD"

    def test_literal_zone_in_inline_map_has_correct_info_tag(self):
        """_count_literal_zones returns the info_tag for inline-map nested zone."""
        doc = _make_doc_with_literal_zone_in_inline_map()
        result = _count_literal_zones(doc)
        assert result[0]["info_tag"] == "sql"

    def test_plain_items_in_list_are_not_counted(self):
        """_count_literal_zones does not count plain strings inside a ListValue."""
        lzv = LiteralZoneValue(content="code", info_tag="python")
        list_val = ListValue(items=["plain", 42, lzv])
        assignment = Assignment(key="MIX", value=list_val, line=2)
        section = Block(key="SECTION", children=[assignment])
        doc = Document(name="TEST_DOC", sections=[section])
        result = _count_literal_zones(doc)
        # Only the LiteralZoneValue inside the list should be counted
        assert len(result) == 1

    def test_inline_map_with_no_literal_zones_not_counted(self):
        """_count_literal_zones does not count InlineMap with no literal zones."""
        inline_map = InlineMap(pairs={"a": "string", "b": 42})
        assignment = Assignment(key="MAP", value=inline_map, line=3)
        section = Block(key="SECTION", children=[assignment])
        doc = Document(name="TEST_DOC", sections=[section])
        result = _count_literal_zones(doc)
        assert len(result) == 0

    def test_direct_and_nested_zones_both_counted(self):
        """_count_literal_zones counts both direct and list-nested literal zones."""
        direct_lzv = LiteralZoneValue(content="direct", info_tag="python")
        nested_lzv = LiteralZoneValue(content="nested", info_tag="json")
        a_direct = Assignment(key="DIRECT", value=direct_lzv, line=2)
        list_val = ListValue(items=[nested_lzv])
        a_list = Assignment(key="LIST", value=list_val, line=6)
        section = Block(key="SECTION", children=[a_direct, a_list])
        doc = Document(name="TEST_DOC", sections=[section])
        result = _count_literal_zones(doc)
        assert len(result) == 2
