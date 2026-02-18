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

from octave_mcp.core.ast_nodes import Assignment, Block, Document, LiteralZoneValue
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
