"""Tests for constraint compilation to regex patterns (Phase 2: Generator Engine).

TDD RED phase - these tests will fail until compile() methods are implemented.
"""

import pytest

from octave_mcp.core.constraints import (
    AppendOnlyConstraint,
    ConstConstraint,
    DateConstraint,
    DirConstraint,
    EnumConstraint,
    Iso8601Constraint,
    MaxLengthConstraint,
    MinLengthConstraint,
    OptionalConstraint,
    RangeConstraint,
    RegexConstraint,
    RequiredConstraint,
    TypeConstraint,
)


class TestConstraintCompilation:
    """Test compile() method for all constraint types."""

    def test_enum_constraint_compile_basic(self):
        """EnumConstraint(['A', 'B']).compile() should return r'(A|B)'."""
        constraint = EnumConstraint(allowed_values=["A", "B"])
        result = constraint.compile()
        assert result == r"(A|B)"

    def test_enum_constraint_compile_three_values(self):
        """EnumConstraint with 3 values should produce proper regex alternation."""
        constraint = EnumConstraint(allowed_values=["ACTIVE", "INACTIVE", "PENDING"])
        result = constraint.compile()
        assert result == r"(ACTIVE|INACTIVE|PENDING)"

    def test_enum_constraint_compile_single_value(self):
        """EnumConstraint with single value should still wrap in parens."""
        constraint = EnumConstraint(allowed_values=["ONLY"])
        result = constraint.compile()
        assert result == r"(ONLY)"

    def test_const_constraint_compile(self):
        """ConstConstraint should compile to exact literal match."""
        constraint = ConstConstraint(const_value="FIXED_VALUE")
        result = constraint.compile()
        # Should match exactly "FIXED_VALUE"
        assert result == r"FIXED_VALUE"

    def test_const_constraint_compile_numeric(self):
        """ConstConstraint with number should compile to numeric pattern."""
        constraint = ConstConstraint(const_value=42)
        result = constraint.compile()
        assert result == r"42"

    def test_required_constraint_compile(self):
        """RequiredConstraint should compile to non-empty pattern."""
        constraint = RequiredConstraint()
        result = constraint.compile()
        # REQ means "not empty" - matches any non-empty string
        assert result == r".+"

    def test_optional_constraint_compile(self):
        """OptionalConstraint should compile to allow anything including empty."""
        constraint = OptionalConstraint()
        result = constraint.compile()
        # OPT means "anything or nothing"
        assert result == r".*"

    def test_type_string_constraint_compile(self):
        """TYPE(STRING) should compile to string pattern."""
        constraint = TypeConstraint(expected_type="STRING")
        result = constraint.compile()
        # STRING type - any character sequence
        assert result == r".+"

    def test_type_number_constraint_compile(self):
        """TYPE(NUMBER) should compile to numeric pattern."""
        constraint = TypeConstraint(expected_type="NUMBER")
        result = constraint.compile()
        # NUMBER type - matches integers and floats
        assert result == r"-?\d+(\.\d+)?"

    def test_type_boolean_constraint_compile(self):
        """TYPE(BOOLEAN) should compile to true/false pattern."""
        constraint = TypeConstraint(expected_type="BOOLEAN")
        result = constraint.compile()
        # BOOLEAN type - true or false
        assert result == r"(true|false)"

    def test_type_list_constraint_compile(self):
        """TYPE(LIST) should compile to list pattern."""
        constraint = TypeConstraint(expected_type="LIST")
        result = constraint.compile()
        # LIST type - array syntax
        assert result == r"\[.*\]"

    def test_regex_constraint_compile(self):
        """RegexConstraint should return its pattern unchanged."""
        constraint = RegexConstraint(pattern=r"^\d{4}-\d{2}-\d{2}$")
        result = constraint.compile()
        # REGEX constraint already contains a regex pattern
        assert result == r"^\d{4}-\d{2}-\d{2}$"

    def test_range_constraint_compile(self):
        """RangeConstraint should compile to numeric pattern (no bounds in regex)."""
        constraint = RangeConstraint(min_value=1, max_value=100)
        result = constraint.compile()
        # RANGE validation is semantic, regex just matches numbers
        assert result == r"-?\d+(\.\d+)?"

    def test_max_length_constraint_compile(self):
        """MaxLengthConstraint should compile to bounded repetition."""
        constraint = MaxLengthConstraint(max_length=10)
        result = constraint.compile()
        # MAX_LENGTH[10] - any string up to 10 chars
        assert result == r".{0,10}"

    def test_min_length_constraint_compile(self):
        """MinLengthConstraint should compile to minimum repetition."""
        constraint = MinLengthConstraint(min_length=5)
        result = constraint.compile()
        # MIN_LENGTH[5] - at least 5 characters
        assert result == r".{5,}"

    def test_date_constraint_compile(self):
        """DateConstraint should compile to YYYY-MM-DD pattern."""
        constraint = DateConstraint()
        result = constraint.compile()
        # DATE format: YYYY-MM-DD
        assert result == r"\d{4}-\d{2}-\d{2}"

    def test_iso8601_constraint_compile(self):
        """Iso8601Constraint should compile to full ISO8601 pattern."""
        constraint = Iso8601Constraint()
        result = constraint.compile()
        # ISO8601 supports dates and datetimes
        assert r"\d{4}-\d{2}-\d{2}" in result  # At minimum includes date

    def test_dir_constraint_compile(self):
        """DirConstraint should compile to path pattern."""
        constraint = DirConstraint()
        result = constraint.compile()
        # DIR - filesystem path
        assert result == r"[^\x00]+"  # Any string without null bytes

    def test_append_only_constraint_compile(self):
        """AppendOnlyConstraint should compile to list pattern."""
        constraint = AppendOnlyConstraint()
        result = constraint.compile()
        # APPEND_ONLY implies LIST type
        assert result == r"\[.*\]"


class TestCompileMethodExists:
    """Verify compile() method exists on base Constraint class."""

    def test_constraint_has_compile_method(self):
        """Base Constraint class should have abstract compile() method."""
        from octave_mcp.core.constraints import Constraint

        # Should have compile as abstract method
        assert hasattr(Constraint, "compile")

        # Attempt to instantiate should fail (abstract class)
        with pytest.raises(TypeError, match="abstract"):
            Constraint()  # type: ignore
