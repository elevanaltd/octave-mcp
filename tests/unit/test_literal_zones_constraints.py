"""Tests for LiteralConstraint and LangConstraint (Issue #235 T11).

TDD cycle: RED phase -- these tests must fail before implementation.

Tests cover:
- LiteralConstraint.evaluate() with LiteralZoneValue (valid)
- LiteralConstraint.evaluate() with non-literal values (invalid, E007)
- LangConstraint.evaluate() with matching/non-matching info_tag
- ConstraintChain.parse("TYPE[LITERAL]") produces LiteralConstraint
- ConstraintChain.parse("LANG[python]") produces LangConstraint
- ConstraintChain.parse("REQ TYPE[LITERAL] LANG[python]") produces all three
- Existing constraint parsing regressions still pass
"""

from octave_mcp.core.ast_nodes import LiteralZoneValue
from octave_mcp.core.constraints import (
    ConstraintChain,
    LangConstraint,
    LiteralConstraint,
    RequiredConstraint,
)

# ---------------------------------------------------------------------------
# LiteralConstraint tests
# ---------------------------------------------------------------------------


class TestLiteralConstraint:
    """Tests for LiteralConstraint.evaluate()."""

    def test_evaluate_literal_zone_value_is_valid(self):
        """LiteralConstraint.evaluate(LiteralZoneValue()) returns valid."""
        result = LiteralConstraint().evaluate(LiteralZoneValue())
        assert result.valid is True
        assert result.errors == []

    def test_evaluate_literal_zone_value_with_content_is_valid(self):
        """LiteralConstraint accepts LiteralZoneValue with content."""
        lzv = LiteralZoneValue(content="hello world", info_tag="python")
        result = LiteralConstraint().evaluate(lzv)
        assert result.valid is True

    def test_evaluate_empty_literal_zone_is_valid(self):
        """LiteralConstraint accepts empty LiteralZoneValue (I2: empty != absent)."""
        lzv = LiteralZoneValue(content="", info_tag=None)
        result = LiteralConstraint().evaluate(lzv)
        assert result.valid is True

    def test_evaluate_string_value_is_invalid(self):
        """LiteralConstraint.evaluate('string value') returns invalid with E007."""
        result = LiteralConstraint().evaluate("string value")
        assert result.valid is False
        assert len(result.errors) == 1
        assert result.errors[0].code == "E007"

    def test_evaluate_string_error_constraint_name(self):
        """LiteralConstraint error reports constraint as TYPE[LITERAL]."""
        result = LiteralConstraint().evaluate("string value", path="test.field")
        assert result.valid is False
        assert result.errors[0].constraint == "TYPE[LITERAL]"

    def test_evaluate_string_error_expected_literal_zone(self):
        """LiteralConstraint error says expected LiteralZoneValue."""
        result = LiteralConstraint().evaluate("string value", path="test.field")
        assert result.errors[0].expected == "LiteralZoneValue"

    def test_evaluate_integer_value_is_invalid(self):
        """LiteralConstraint.evaluate(42) returns invalid."""
        result = LiteralConstraint().evaluate(42)
        assert result.valid is False
        assert result.errors[0].code == "E007"

    def test_evaluate_none_is_invalid(self):
        """LiteralConstraint.evaluate(None) returns invalid."""
        result = LiteralConstraint().evaluate(None)
        assert result.valid is False
        assert result.errors[0].code == "E007"

    def test_evaluate_list_is_invalid(self):
        """LiteralConstraint.evaluate([]) returns invalid."""
        result = LiteralConstraint().evaluate([])
        assert result.valid is False
        assert result.errors[0].code == "E007"

    def test_evaluate_with_path(self):
        """LiteralConstraint passes path to error."""
        result = LiteralConstraint().evaluate("bad", path="SECTION.key")
        assert result.errors[0].path == "SECTION.key"

    def test_to_string(self):
        """LiteralConstraint.to_string() returns 'TYPE[LITERAL]'."""
        assert LiteralConstraint().to_string() == "TYPE[LITERAL]"

    def test_compile_returns_string(self):
        """LiteralConstraint.compile() returns a non-empty string."""
        result = LiteralConstraint().compile()
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# LangConstraint tests
# ---------------------------------------------------------------------------


class TestLangConstraint:
    """Tests for LangConstraint.evaluate()."""

    def test_evaluate_matching_info_tag_is_valid(self):
        """LangConstraint('python').evaluate(LiteralZoneValue(info_tag='python')) is valid."""
        lzv = LiteralZoneValue(info_tag="python")
        result = LangConstraint("python").evaluate(lzv)
        assert result.valid is True

    def test_evaluate_case_insensitive_upper_tag(self):
        """LangConstraint is case-insensitive: 'PYTHON' matches 'python'."""
        lzv = LiteralZoneValue(info_tag="PYTHON")
        result = LangConstraint("python").evaluate(lzv)
        assert result.valid is True

    def test_evaluate_case_insensitive_mixed_case(self):
        """LangConstraint is case-insensitive: 'PyThOn' matches 'python'."""
        lzv = LiteralZoneValue(info_tag="PyThOn")
        result = LangConstraint("python").evaluate(lzv)
        assert result.valid is True

    def test_evaluate_case_insensitive_constraint_uppercase(self):
        """LangConstraint('PYTHON') matches LiteralZoneValue(info_tag='python')."""
        lzv = LiteralZoneValue(info_tag="python")
        result = LangConstraint("PYTHON").evaluate(lzv)
        assert result.valid is True

    def test_evaluate_mismatched_tag_is_invalid(self):
        """LangConstraint('python').evaluate(LiteralZoneValue(info_tag='json')) is invalid."""
        lzv = LiteralZoneValue(info_tag="json")
        result = LangConstraint("python").evaluate(lzv)
        assert result.valid is False
        assert result.errors[0].code == "E007"

    def test_evaluate_none_tag_is_invalid(self):
        """LangConstraint('python').evaluate(LiteralZoneValue(info_tag=None)) is invalid."""
        lzv = LiteralZoneValue(info_tag=None)
        result = LangConstraint("python").evaluate(lzv)
        assert result.valid is False
        assert result.errors[0].code == "E007"

    def test_evaluate_none_tag_error_got_field(self):
        """LangConstraint error for None tag shows '(none)' in got field."""
        lzv = LiteralZoneValue(info_tag=None)
        result = LangConstraint("python").evaluate(lzv)
        assert result.errors[0].got == "(none)"

    def test_evaluate_string_value_is_invalid(self):
        """LangConstraint('python').evaluate('string') is invalid (not a LiteralZoneValue)."""
        result = LangConstraint("python").evaluate("string")
        assert result.valid is False
        assert result.errors[0].code == "E007"

    def test_evaluate_non_literal_error_got_type(self):
        """LangConstraint error for non-literal shows type name in got field."""
        result = LangConstraint("python").evaluate("string", path="test.key")
        assert result.errors[0].got == "str"

    def test_evaluate_with_path(self):
        """LangConstraint passes path to error."""
        lzv = LiteralZoneValue(info_tag="json")
        result = LangConstraint("python").evaluate(lzv, path="SECTION.code")
        assert result.errors[0].path == "SECTION.code"

    def test_to_string(self):
        """LangConstraint.to_string() returns 'LANG[python]'."""
        assert LangConstraint("python").to_string() == "LANG[python]"

    def test_to_string_preserves_lowercased_lang(self):
        """LangConstraint.to_string() lowercases the expected lang."""
        assert LangConstraint("PYTHON").to_string() == "LANG[python]"

    def test_compile_returns_string(self):
        """LangConstraint.compile() returns a non-empty string."""
        result = LangConstraint("python").compile()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_lang_constraint_json_valid(self):
        """LangConstraint('json') validates json info_tag correctly."""
        lzv = LiteralZoneValue(info_tag="json")
        result = LangConstraint("json").evaluate(lzv)
        assert result.valid is True


# ---------------------------------------------------------------------------
# ConstraintChain.parse() integration tests
# ---------------------------------------------------------------------------


class TestConstraintChainParseLiteralZone:
    """Tests for ConstraintChain.parse() recognising TYPE[LITERAL] and LANG[...]."""

    def test_parse_type_literal_produces_literal_constraint(self):
        """ConstraintChain.parse('TYPE[LITERAL]') produces a chain with LiteralConstraint."""
        chain = ConstraintChain.parse("TYPE[LITERAL]")
        assert len(chain.constraints) == 1
        assert isinstance(chain.constraints[0], LiteralConstraint)

    def test_parse_lang_python_produces_lang_constraint(self):
        """ConstraintChain.parse('LANG[python]') produces a chain with LangConstraint."""
        chain = ConstraintChain.parse("LANG[python]")
        assert len(chain.constraints) == 1
        assert isinstance(chain.constraints[0], LangConstraint)

    def test_parse_lang_python_expected_lang_stored(self):
        """ConstraintChain.parse('LANG[python]') stores expected_lang='python'."""
        chain = ConstraintChain.parse("LANG[python]")
        lang_c = chain.constraints[0]
        assert isinstance(lang_c, LangConstraint)
        assert lang_c.expected_lang == "python"

    def test_parse_req_type_literal_lang_space_separated(self):
        """ConstraintChain.parse('REQ TYPE[LITERAL] LANG[python]') produces three constraints."""
        chain = ConstraintChain.parse("REQ TYPE[LITERAL] LANG[python]")
        assert len(chain.constraints) == 3
        assert isinstance(chain.constraints[0], RequiredConstraint)
        assert isinstance(chain.constraints[1], LiteralConstraint)
        assert isinstance(chain.constraints[2], LangConstraint)

    def test_parse_req_type_literal_lang_and_separated(self):
        """ConstraintChain.parse('REQ∧TYPE[LITERAL]∧LANG[python]') produces three constraints."""
        chain = ConstraintChain.parse("REQ∧TYPE[LITERAL]∧LANG[python]")
        assert len(chain.constraints) == 3
        assert isinstance(chain.constraints[0], RequiredConstraint)
        assert isinstance(chain.constraints[1], LiteralConstraint)
        assert isinstance(chain.constraints[2], LangConstraint)

    def test_parse_lang_json_produces_correct_lang(self):
        """ConstraintChain.parse('LANG[json]') stores expected_lang='json'."""
        chain = ConstraintChain.parse("LANG[json]")
        lang_c = chain.constraints[0]
        assert isinstance(lang_c, LangConstraint)
        assert lang_c.expected_lang == "json"

    def test_chain_evaluate_type_literal_with_literal_zone_value(self):
        """ConstraintChain with TYPE[LITERAL] evaluates LiteralZoneValue as valid."""
        chain = ConstraintChain.parse("TYPE[LITERAL]")
        lzv = LiteralZoneValue(content="hello")
        result = chain.evaluate(lzv, "test.field")
        assert result.valid is True

    def test_chain_evaluate_lang_json_with_matching_tag(self):
        """ConstraintChain.parse('LANG[json]') evaluates LiteralZoneValue(info_tag='json') as valid."""
        chain = ConstraintChain.parse("LANG[json]")
        lzv = LiteralZoneValue(info_tag="json")
        result = chain.evaluate(lzv, "test.field")
        assert result.valid is True

    def test_chain_evaluate_type_literal_with_string_fails(self):
        """ConstraintChain with TYPE[LITERAL] evaluates string as invalid."""
        chain = ConstraintChain.parse("TYPE[LITERAL]")
        result = chain.evaluate("not a literal zone", "test.field")
        assert result.valid is False
        assert result.errors[0].code == "E007"

    def test_chain_evaluate_combined_req_type_literal_lang(self):
        """Combined REQ TYPE[LITERAL] LANG[python] chain validates matching LiteralZoneValue."""
        chain = ConstraintChain.parse("REQ TYPE[LITERAL] LANG[python]")
        lzv = LiteralZoneValue(content="print('hello')", info_tag="python")
        result = chain.evaluate(lzv, "test.code")
        assert result.valid is True

    def test_chain_evaluate_combined_fails_on_wrong_lang(self):
        """Combined TYPE[LITERAL] LANG[python] chain fails for info_tag='json'."""
        chain = ConstraintChain.parse("TYPE[LITERAL]∧LANG[python]")
        lzv = LiteralZoneValue(content="{'key': 'value'}", info_tag="json")
        result = chain.evaluate(lzv, "test.code")
        assert result.valid is False


# ---------------------------------------------------------------------------
# Regression tests: existing constraint parsing still works
# ---------------------------------------------------------------------------


class TestConstraintChainParseRegression:
    """Regression tests: existing constraint parsing must not break."""

    def test_req_still_parses(self):
        """REQ still parses as RequiredConstraint."""
        from octave_mcp.core.constraints import RequiredConstraint

        chain = ConstraintChain.parse("REQ")
        assert len(chain.constraints) == 1
        assert isinstance(chain.constraints[0], RequiredConstraint)

    def test_type_string_still_parses(self):
        """TYPE[STRING] still parses as TypeConstraint."""
        from octave_mcp.core.constraints import TypeConstraint

        chain = ConstraintChain.parse("TYPE[STRING]")
        assert isinstance(chain.constraints[0], TypeConstraint)
        assert chain.constraints[0].expected_type == "STRING"

    def test_enum_still_parses(self):
        """ENUM[A,B,C] still parses as EnumConstraint."""
        from octave_mcp.core.constraints import EnumConstraint

        chain = ConstraintChain.parse("ENUM[A,B,C]")
        assert isinstance(chain.constraints[0], EnumConstraint)

    def test_and_chain_still_parses(self):
        """REQ∧TYPE[STRING] still parses as two constraints."""
        chain = ConstraintChain.parse("REQ∧TYPE[STRING]")
        assert len(chain.constraints) == 2

    def test_type_literal_does_not_create_type_constraint(self):
        """TYPE[LITERAL] creates LiteralConstraint, NOT TypeConstraint."""
        from octave_mcp.core.constraints import TypeConstraint

        chain = ConstraintChain.parse("TYPE[LITERAL]")
        assert not isinstance(chain.constraints[0], TypeConstraint)
        assert isinstance(chain.constraints[0], LiteralConstraint)
