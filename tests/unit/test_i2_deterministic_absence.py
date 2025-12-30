"""Tests for I2: Deterministic Absence.

North Star Requirement (I2):
> The system shall distinguish between "absent" (field not provided),
> "null" (explicitly empty), and "default" (schema-provided).
> Absence shall propagate as addressable state, never silently collapse
> to null or default.

This test module verifies the tri-state distinction:
1. Absent: Field not provided (should NOT be emitted)
2. Null: Field explicitly set to null (`KEY::null`)
3. Value: Field has an actual value

TDD Phase: RED - These tests should fail until I2 is implemented.
"""

from octave_mcp.core.ast_nodes import Absent, Assignment, Document, ListValue
from octave_mcp.core.emitter import emit, emit_value
from octave_mcp.core.parser import parse


class TestAbsentSentinelType:
    """Test the Absent sentinel type exists and behaves correctly."""

    def test_absent_is_singleton_like(self):
        """Absent should be a recognizable sentinel distinct from None."""
        # Absent must exist as a type/sentinel
        assert Absent is not None
        # Absent must not equal None
        assert Absent != None  # noqa: E711
        # Absent instance/value should be falsy but not None
        absent_val = Absent()
        assert absent_val is not None
        assert absent_val != None  # noqa: E711

    def test_absent_repr_is_descriptive(self):
        """Absent should have a clear repr for debugging."""
        absent_val = Absent()
        assert "Absent" in repr(absent_val)

    def test_absent_is_not_truthy_like_none(self):
        """Absent should behave reasonably in boolean context."""
        absent_val = Absent()
        # Like None, Absent should be falsy for conditional checks
        assert not absent_val


class TestParserDistinguishesNullFromValue:
    """Test that parser correctly handles null vs value."""

    def test_parses_explicit_null(self):
        """KEY::null should parse to Python None value."""
        content = """===TEST===
KEY::null
===END===
"""
        doc = parse(content)
        assert len(doc.sections) == 1
        assignment = doc.sections[0]
        assert isinstance(assignment, Assignment)
        assert assignment.key == "KEY"
        assert assignment.value is None

    def test_parses_empty_list_differently_from_null(self):
        """KEY::[] should parse to empty ListValue, not None."""
        content = """===TEST===
ITEMS::[]
===END===
"""
        doc = parse(content)
        assignment = doc.sections[0]
        assert isinstance(assignment, Assignment)
        assert assignment.key == "ITEMS"
        # Empty list is NOT None
        assert assignment.value is not None
        assert isinstance(assignment.value, ListValue)
        assert assignment.value.items == []

    def test_parses_regular_value(self):
        """KEY::value should parse to the string value."""
        content = """===TEST===
KEY::value
===END===
"""
        doc = parse(content)
        assignment = doc.sections[0]
        assert assignment.key == "KEY"
        assert assignment.value == "value"


class TestEmitterDistinguishesAbsentFromNull:
    """Test that emitter handles absent vs null correctly."""

    def test_emits_null_as_keyword(self):
        """None value should be emitted as 'null'."""
        result = emit_value(None)
        assert result == "null"

    def test_emits_empty_list_as_brackets(self):
        """Empty list should be emitted as '[]'."""
        result = emit_value(ListValue(items=[]))
        assert result == "[]"

    def test_absent_value_not_emitted(self):
        """Absent values should NOT appear in emitted output."""
        # When a field has Absent as its value, it should not be emitted at all
        absent_val = Absent()
        doc = Document(
            name="TEST",
            sections=[
                Assignment(key="PRESENT", value="exists"),
                Assignment(key="MISSING", value=absent_val),
                Assignment(key="EXPLICIT_NULL", value=None),
            ],
        )
        result = emit(doc)

        # PRESENT should be in output
        assert "PRESENT::exists" in result

        # EXPLICIT_NULL should be in output as null
        assert "EXPLICIT_NULL::null" in result

        # MISSING should NOT be in output at all
        assert "MISSING" not in result


class TestRoundTripPreservesTriState:
    """Test that parse -> emit -> parse preserves tri-state semantics."""

    def test_null_survives_roundtrip(self):
        """Explicit null should survive parse -> emit -> parse."""
        original = """===TEST===
NULLABLE::null
===END===
"""
        doc1 = parse(original)
        emitted = emit(doc1)
        doc2 = parse(emitted)

        # Find the NULLABLE assignment
        nullable_assign = next(s for s in doc2.sections if isinstance(s, Assignment) and s.key == "NULLABLE")
        assert nullable_assign.value is None

    def test_empty_list_survives_roundtrip(self):
        """Empty list should survive parse -> emit -> parse."""
        original = """===TEST===
ITEMS::[]
===END===
"""
        doc1 = parse(original)
        emitted = emit(doc1)
        doc2 = parse(emitted)

        items_assign = next(s for s in doc2.sections if isinstance(s, Assignment) and s.key == "ITEMS")
        assert isinstance(items_assign.value, ListValue)
        assert items_assign.value.items == []


class TestEmitValueHandlesAbsent:
    """Test emit_value behavior with Absent sentinel."""

    def test_emit_value_with_absent_raises_value_error(self):
        """emit_value(Absent()) must raise ValueError.

        Per CRS blocking feedback and I2 compliance:
        - Absent fields should be filtered BEFORE reaching emit_value
        - If Absent reaches emit_value, it's a caller bug
        - Raising ValueError catches these bugs early

        Previous behavior (returning empty string) caused invalid output:
        - KEY:: (empty value) for direct emit_value(Absent())
        - [,a,,b,] for lists with Absent items
        - k:: for maps with Absent values
        """
        import pytest

        absent_val = Absent()
        # emit_value must raise ValueError when passed Absent
        with pytest.raises(ValueError, match="Absent"):
            emit_value(absent_val)


class TestMetaBlockHandlesAbsence:
    """Test META block handling of absent vs null."""

    def test_meta_with_null_field(self):
        """META fields can be explicitly null."""
        content = """===TEST===
META:
  TYPE::TEST_DOC
  OPTIONAL_FIELD::null
===END===
"""
        doc = parse(content)
        assert doc.meta.get("TYPE") == "TEST_DOC"
        assert "OPTIONAL_FIELD" in doc.meta
        assert doc.meta.get("OPTIONAL_FIELD") is None

    def test_meta_without_field_is_absent(self):
        """Missing META fields should be distinct from null."""
        content = """===TEST===
META:
  TYPE::TEST_DOC
===END===
"""
        doc = parse(content)
        assert doc.meta.get("TYPE") == "TEST_DOC"
        # MISSING_FIELD is absent (not in dict), not null
        assert "MISSING_FIELD" not in doc.meta
        # get() returns None for missing, but key check shows absence
        assert doc.meta.get("MISSING_FIELD") is None
        # The distinction: "in" check vs get() default


class TestI2ComplianceMarkers:
    """Test that I2 compliance is addressable in outputs."""

    def test_absent_is_addressable_not_collapsed(self):
        """Absence should be addressable, not silently collapsed.

        Per I2: "Absence shall propagate as addressable state,
        never silently collapse to null or default."

        This means we need a way to query "was this field absent?"
        distinct from "was this field null?"
        """
        absent_val = Absent()

        # Create assignment with absent value
        absent_assign = Assignment(key="ABSENT_FIELD", value=absent_val)

        # Create assignment with null value
        null_assign = Assignment(key="NULL_FIELD", value=None)

        # We must be able to distinguish them
        assert absent_assign.value is not None  # Not Python None
        assert null_assign.value is None  # Is Python None

        # Both should be falsy for conditionals
        assert not absent_assign.value
        assert not null_assign.value

        # But they should NOT be equal
        assert absent_assign.value != null_assign.value
