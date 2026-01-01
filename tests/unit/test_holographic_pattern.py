"""Tests for holographic pattern parsing (Issue #93).

Tests parsing of OCTAVE holographic patterns as defined in octave-5-llm-schema.oct.md.

Holographic Pattern Syntax:
    KEY::["example"∧CONSTRAINT→§TARGET]
         ^^^^^^^^ ^^^^^^^^^^ ^^^^^^^^
         example  constraints target

TDD RED phase: Write failing tests before implementation.
"""

import pytest


class TestHolographicPatternDataclass:
    """Test HolographicPattern dataclass structure."""

    def test_holographic_pattern_import(self):
        """HolographicPattern should be importable from core.holographic."""
        from octave_mcp.core.holographic import HolographicPattern

        assert HolographicPattern is not None

    def test_holographic_pattern_has_example_field(self):
        """HolographicPattern should have example field."""
        from octave_mcp.core.holographic import HolographicPattern

        pattern = HolographicPattern(example="test", constraints=None, target=None)
        assert pattern.example == "test"

    def test_holographic_pattern_has_constraints_field(self):
        """HolographicPattern should have constraints field (ConstraintChain)."""
        from octave_mcp.core.constraints import ConstraintChain
        from octave_mcp.core.holographic import HolographicPattern

        chain = ConstraintChain.parse("REQ")
        pattern = HolographicPattern(example="test", constraints=chain, target=None)
        assert pattern.constraints is not None
        assert len(pattern.constraints.constraints) == 1

    def test_holographic_pattern_has_target_field(self):
        """HolographicPattern should have target field."""
        from octave_mcp.core.holographic import HolographicPattern

        pattern = HolographicPattern(example="test", constraints=None, target="INDEXER")
        assert pattern.target == "INDEXER"

    def test_holographic_pattern_target_can_be_none(self):
        """HolographicPattern target should be optional (None allowed)."""
        from octave_mcp.core.holographic import HolographicPattern

        pattern = HolographicPattern(example="test", constraints=None, target=None)
        assert pattern.target is None

    def test_holographic_pattern_example_accepts_string(self):
        """HolographicPattern example should accept string."""
        from octave_mcp.core.holographic import HolographicPattern

        pattern = HolographicPattern(example="implementation-lead", constraints=None, target=None)
        assert pattern.example == "implementation-lead"

    def test_holographic_pattern_example_accepts_number(self):
        """HolographicPattern example should accept numeric values."""
        from octave_mcp.core.holographic import HolographicPattern

        pattern = HolographicPattern(example=42, constraints=None, target=None)
        assert pattern.example == 42

    def test_holographic_pattern_example_accepts_list(self):
        """HolographicPattern example should accept list values."""
        from octave_mcp.core.holographic import HolographicPattern

        pattern = HolographicPattern(example=["item1", "item2"], constraints=None, target=None)
        assert pattern.example == ["item1", "item2"]

    def test_holographic_pattern_example_accepts_boolean(self):
        """HolographicPattern example should accept boolean values."""
        from octave_mcp.core.holographic import HolographicPattern

        pattern = HolographicPattern(example=True, constraints=None, target=None)
        assert pattern.example is True


class TestParseHolographicPattern:
    """Test parse_holographic_pattern() function."""

    def test_parse_holographic_pattern_import(self):
        """parse_holographic_pattern should be importable from core.holographic."""
        from octave_mcp.core.holographic import parse_holographic_pattern

        assert parse_holographic_pattern is not None

    def test_parse_simple_pattern_with_req(self):
        """Should parse simple pattern with REQ constraint."""
        from octave_mcp.core.holographic import parse_holographic_pattern

        pattern = parse_holographic_pattern('["example"∧REQ→§SELF]')
        assert pattern.example == "example"
        assert len(pattern.constraints.constraints) == 1
        assert pattern.target == "SELF"

    def test_parse_pattern_without_target(self):
        """Should parse pattern without target (target is optional)."""
        from octave_mcp.core.holographic import parse_holographic_pattern

        pattern = parse_holographic_pattern('["value"∧REQ]')
        assert pattern.example == "value"
        assert len(pattern.constraints.constraints) == 1
        assert pattern.target is None

    def test_parse_pattern_with_constraint_chain(self):
        """Should parse pattern with constraint chain."""
        from octave_mcp.core.holographic import parse_holographic_pattern

        pattern = parse_holographic_pattern('["ACTIVE"∧REQ∧ENUM[ACTIVE,DRAFT]→§INDEXER]')
        assert pattern.example == "ACTIVE"
        assert len(pattern.constraints.constraints) == 2
        assert pattern.target == "INDEXER"

    def test_parse_pattern_with_regex_constraint(self):
        """Should parse pattern with REGEX constraint."""
        from octave_mcp.core.holographic import parse_holographic_pattern

        pattern = parse_holographic_pattern('["implementation-lead"∧REQ∧REGEX[^[a-z-]+$]→§INDEXER]')
        assert pattern.example == "implementation-lead"
        assert len(pattern.constraints.constraints) == 2
        assert pattern.target == "INDEXER"

    def test_parse_pattern_with_type_constraint(self):
        """Should parse pattern with TYPE constraint."""
        from octave_mcp.core.holographic import parse_holographic_pattern

        pattern = parse_holographic_pattern('[["Fixed bugs"]∧REQ∧TYPE(LIST)→§SELF]')
        assert pattern.example == ["Fixed bugs"]
        assert len(pattern.constraints.constraints) == 2
        assert pattern.target == "SELF"

    def test_parse_pattern_with_opt_constraint(self):
        """Should parse pattern with OPT constraint."""
        from octave_mcp.core.holographic import parse_holographic_pattern

        pattern = parse_holographic_pattern('["optional"∧OPT→§SELF]')
        assert pattern.example == "optional"
        assert len(pattern.constraints.constraints) == 1
        assert pattern.target == "SELF"

    def test_parse_pattern_with_numeric_example(self):
        """Should parse pattern with numeric example."""
        from octave_mcp.core.holographic import parse_holographic_pattern

        pattern = parse_holographic_pattern("[42∧REQ∧TYPE(NUMBER)→§SELF]")
        assert pattern.example == 42
        assert len(pattern.constraints.constraints) == 2

    def test_parse_pattern_with_range_constraint(self):
        """Should parse pattern with RANGE constraint."""
        from octave_mcp.core.holographic import parse_holographic_pattern

        pattern = parse_holographic_pattern("[50∧REQ∧RANGE[0,100]→§SELF]")
        assert pattern.example == 50
        assert len(pattern.constraints.constraints) == 2

    def test_parse_pattern_extracts_target_correctly(self):
        """Should extract target correctly (without section marker)."""
        from octave_mcp.core.holographic import parse_holographic_pattern

        # Target is stored without the section marker for consistency
        pattern = parse_holographic_pattern('["value"∧REQ→§DECISION_LOG]')
        assert pattern.target == "DECISION_LOG"

    def test_parse_pattern_with_const_constraint(self):
        """Should parse pattern with CONST constraint."""
        from octave_mcp.core.holographic import parse_holographic_pattern

        pattern = parse_holographic_pattern('["PROTOCOL_DEFINITION"∧CONST[PROTOCOL_DEFINITION]→§META]')
        assert pattern.example == "PROTOCOL_DEFINITION"
        assert len(pattern.constraints.constraints) == 1
        assert pattern.target == "META"

    def test_parse_pattern_with_quoted_regex_pattern(self):
        """Should parse REGEX with quoted pattern containing brackets."""
        from octave_mcp.core.holographic import parse_holographic_pattern

        # Per schema spec: REGEX_BRACKETS::quote_if_contains_brackets
        pattern = parse_holographic_pattern('["agent-name"∧REQ∧REGEX["^[a-z-]+$"]→§INDEXER]')
        assert pattern.example == "agent-name"
        assert len(pattern.constraints.constraints) == 2

    def test_parse_pattern_with_dir_constraint(self):
        """Should parse pattern with DIR constraint."""
        from octave_mcp.core.holographic import parse_holographic_pattern

        pattern = parse_holographic_pattern('["/path/to/dir"∧REQ∧DIR→§SELF]')
        assert pattern.example == "/path/to/dir"
        assert len(pattern.constraints.constraints) == 2

    def test_parse_pattern_with_append_only_constraint(self):
        """Should parse pattern with APPEND_ONLY constraint."""
        from octave_mcp.core.holographic import parse_holographic_pattern

        pattern = parse_holographic_pattern('[["item1"]∧REQ∧APPEND_ONLY→§SELF]')
        assert pattern.example == ["item1"]
        assert len(pattern.constraints.constraints) == 2

    def test_parse_pattern_with_date_constraint(self):
        """Should parse pattern with DATE constraint."""
        from octave_mcp.core.holographic import parse_holographic_pattern

        pattern = parse_holographic_pattern('["2025-01-15"∧REQ∧DATE→§SELF]')
        assert pattern.example == "2025-01-15"
        assert len(pattern.constraints.constraints) == 2

    def test_parse_pattern_with_iso8601_constraint(self):
        """Should parse pattern with ISO8601 constraint."""
        from octave_mcp.core.holographic import parse_holographic_pattern

        pattern = parse_holographic_pattern('["2025-01-15T10:30:00Z"∧REQ∧ISO8601→§SELF]')
        assert pattern.example == "2025-01-15T10:30:00Z"
        assert len(pattern.constraints.constraints) == 2

    def test_parse_pattern_with_max_length_constraint(self):
        """Should parse pattern with MAX_LENGTH constraint."""
        from octave_mcp.core.holographic import parse_holographic_pattern

        pattern = parse_holographic_pattern('["short"∧REQ∧MAX_LENGTH[100]→§SELF]')
        assert pattern.example == "short"
        assert len(pattern.constraints.constraints) == 2

    def test_parse_pattern_with_min_length_constraint(self):
        """Should parse pattern with MIN_LENGTH constraint."""
        from octave_mcp.core.holographic import parse_holographic_pattern

        pattern = parse_holographic_pattern('["nonempty"∧REQ∧MIN_LENGTH[1]→§SELF]')
        assert pattern.example == "nonempty"
        assert len(pattern.constraints.constraints) == 2


class TestParseHolographicPatternErrors:
    """Test error handling in parse_holographic_pattern()."""

    def test_parse_pattern_invalid_format_raises_error(self):
        """Should raise error for invalid pattern format."""
        from octave_mcp.core.holographic import HolographicPatternError, parse_holographic_pattern

        with pytest.raises(HolographicPatternError):
            parse_holographic_pattern("not a valid pattern")

    def test_parse_pattern_missing_brackets_raises_error(self):
        """Should raise error when brackets are missing."""
        from octave_mcp.core.holographic import HolographicPatternError, parse_holographic_pattern

        with pytest.raises(HolographicPatternError):
            parse_holographic_pattern('"example"∧REQ→§SELF')

    def test_parse_pattern_empty_raises_error(self):
        """Should raise error for empty pattern."""
        from octave_mcp.core.holographic import HolographicPatternError, parse_holographic_pattern

        with pytest.raises(HolographicPatternError):
            parse_holographic_pattern("[]")

    def test_parse_pattern_missing_example_raises_error(self):
        """Should raise error when example is missing."""
        from octave_mcp.core.holographic import HolographicPatternError, parse_holographic_pattern

        with pytest.raises(HolographicPatternError):
            parse_holographic_pattern("[∧REQ→§SELF]")


class TestHolographicPatternToString:
    """Test HolographicPattern.to_string() for round-trip validation."""

    def test_holographic_pattern_to_string_simple(self):
        """Should convert simple pattern back to string."""
        from octave_mcp.core.constraints import ConstraintChain
        from octave_mcp.core.holographic import HolographicPattern

        chain = ConstraintChain.parse("REQ")
        pattern = HolographicPattern(example="test", constraints=chain, target="SELF")
        result = pattern.to_string()
        assert "test" in result
        assert "REQ" in result
        assert "SELF" in result

    def test_holographic_pattern_to_string_with_constraint_chain(self):
        """Should convert pattern with constraint chain to string."""
        from octave_mcp.core.constraints import ConstraintChain
        from octave_mcp.core.holographic import HolographicPattern

        chain = ConstraintChain.parse("REQ∧ENUM[ACTIVE,DRAFT]")
        pattern = HolographicPattern(example="ACTIVE", constraints=chain, target="INDEXER")
        result = pattern.to_string()
        assert "ACTIVE" in result
        assert "REQ" in result
        assert "ENUM" in result
        assert "INDEXER" in result

    def test_holographic_pattern_to_string_without_target(self):
        """Should convert pattern without target to string."""
        from octave_mcp.core.constraints import ConstraintChain
        from octave_mcp.core.holographic import HolographicPattern

        chain = ConstraintChain.parse("REQ")
        pattern = HolographicPattern(example="value", constraints=chain, target=None)
        result = pattern.to_string()
        assert "value" in result
        assert "REQ" in result
        # No section marker when target is None
        assert "§" not in result or result.endswith("]")
