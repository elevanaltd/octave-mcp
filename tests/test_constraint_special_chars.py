"""Test constraint compile() methods escape regex special characters.

Phase 2 regression test: CONST["a.b"] and ENUM["v1.0", "v2+"] must treat
dots and pluses as literals, not regex metacharacters.
"""

import re

from octave_mcp.core.constraints import ConstConstraint, EnumConstraint


class TestConstConstraintEscaping:
    """Test CONST constraint properly escapes special characters in compile()."""

    def test_const_dot_literal_not_wildcard(self):
        """CONST["a.b"] should match "a.b" exactly, NOT "axb"."""
        constraint = ConstConstraint(const_value="a.b")
        pattern = constraint.compile()
        regex = re.compile(f"^{pattern}$")

        # Should match literal "a.b"
        assert regex.match("a.b"), f"Pattern {pattern} should match 'a.b'"

        # Should NOT match "axb" (dot as wildcard would match)
        assert not regex.match("axb"), f"Pattern {pattern} should NOT match 'axb' (dot must be literal)"

    def test_const_plus_literal_not_quantifier(self):
        """CONST["v2+"] should match "v2+" exactly, NOT "v2" or "v22"."""
        constraint = ConstConstraint(const_value="v2+")
        pattern = constraint.compile()
        regex = re.compile(f"^{pattern}$")

        # Should match literal "v2+"
        assert regex.match("v2+"), f"Pattern {pattern} should match 'v2+'"

        # Should NOT match "v2" (plus as quantifier would make preceding optional)
        assert not regex.match("v2"), f"Pattern {pattern} should NOT match 'v2' (plus must be literal)"

        # Should NOT match "v22" (plus as quantifier would allow repetition)
        assert not regex.match("v22"), f"Pattern {pattern} should NOT match 'v22' (plus must be literal)"

    def test_const_star_literal_not_quantifier(self):
        """CONST["v*"] should match "v*" exactly, NOT "v" or "vvv"."""
        constraint = ConstConstraint(const_value="v*")
        pattern = constraint.compile()
        regex = re.compile(f"^{pattern}$")

        # Should match literal "v*"
        assert regex.match("v*"), f"Pattern {pattern} should match 'v*'"

        # Should NOT match "v" (star as quantifier would match zero occurrences)
        assert not regex.match("v"), f"Pattern {pattern} should NOT match 'v' (star must be literal)"

        # Should NOT match "vvv" (star as quantifier would allow repetition)
        assert not regex.match("vvv"), f"Pattern {pattern} should NOT match 'vvv' (star must be literal)"

    def test_const_bracket_literal_not_character_class(self):
        """CONST["[abc]"] should match "[abc]" exactly, NOT "a", "b", or "c"."""
        constraint = ConstConstraint(const_value="[abc]")
        pattern = constraint.compile()
        regex = re.compile(f"^{pattern}$")

        # Should match literal "[abc]"
        assert regex.match("[abc]"), f"Pattern {pattern} should match '[abc]'"

        # Should NOT match individual characters (brackets as character class would match)
        assert not regex.match("a"), f"Pattern {pattern} should NOT match 'a' (brackets must be literal)"
        assert not regex.match("b"), f"Pattern {pattern} should NOT match 'b' (brackets must be literal)"
        assert not regex.match("c"), f"Pattern {pattern} should NOT match 'c' (brackets must be literal)"


class TestEnumConstraintEscaping:
    """Test ENUM constraint properly escapes special characters in compile()."""

    def test_enum_dots_literal_not_wildcard(self):
        """ENUM["v1.0", "v2.0"] should match versions exactly, NOT "v1x0"."""
        constraint = EnumConstraint(allowed_values=["v1.0", "v2.0"])
        pattern = constraint.compile()
        regex = re.compile(f"^{pattern}$")

        # Should match literal versions
        assert regex.match("v1.0"), f"Pattern {pattern} should match 'v1.0'"
        assert regex.match("v2.0"), f"Pattern {pattern} should match 'v2.0'"

        # Should NOT match with dot as wildcard
        assert not regex.match("v1x0"), f"Pattern {pattern} should NOT match 'v1x0' (dots must be literal)"
        assert not regex.match("v2x0"), f"Pattern {pattern} should NOT match 'v2x0' (dots must be literal)"

    def test_enum_plus_literal_not_quantifier(self):
        """ENUM["v2+", "v3+"] should match with literal plus, NOT treat as quantifier."""
        constraint = EnumConstraint(allowed_values=["v2+", "v3+"])
        pattern = constraint.compile()
        regex = re.compile(f"^{pattern}$")

        # Should match literal pluses
        assert regex.match("v2+"), f"Pattern {pattern} should match 'v2+'"
        assert regex.match("v3+"), f"Pattern {pattern} should match 'v3+'"

        # Should NOT match without plus (plus as quantifier would make preceding optional)
        assert not regex.match("v2"), f"Pattern {pattern} should NOT match 'v2' (plus must be literal)"
        assert not regex.match("v3"), f"Pattern {pattern} should NOT match 'v3' (plus must be literal)"

    def test_enum_parentheses_literal_not_capture_group(self):
        """ENUM["(dev)", "(prod)"] should match with literal parens, NOT as capture groups."""
        constraint = EnumConstraint(allowed_values=["(dev)", "(prod)"])
        pattern = constraint.compile()
        regex = re.compile(f"^{pattern}$")

        # Should match literal parentheses
        assert regex.match("(dev)"), f"Pattern {pattern} should match '(dev)'"
        assert regex.match("(prod)"), f"Pattern {pattern} should match '(prod)'"

        # Should NOT match without parentheses (parens as capture group would match just content)
        assert not regex.match("dev"), f"Pattern {pattern} should NOT match 'dev' (parens must be literal)"
        assert not regex.match("prod"), f"Pattern {pattern} should NOT match 'prod' (parens must be literal)"

    def test_enum_mixed_special_chars(self):
        """ENUM with mixed special characters should escape all correctly."""
        constraint = EnumConstraint(allowed_values=["a.b+c*d[e]"])
        pattern = constraint.compile()
        regex = re.compile(f"^{pattern}$")

        # Should match literal string with all special chars
        assert regex.match("a.b+c*d[e]"), f"Pattern {pattern} should match 'a.b+c*d[e]'"

        # Should NOT match with chars interpreted as regex metacharacters
        assert not regex.match("axb+c*d[e]"), "Dot should be literal, not wildcard"
        assert not regex.match("a.b+ccd[e]"), "Star should be literal, not quantifier"
