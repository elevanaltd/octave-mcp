"""Tests for GBNF compiler (Issue #171).

TDD: RED phase - these tests define expected behavior for GBNFCompiler.
The compiler transforms OCTAVE constraint chains into llama.cpp GBNF format.

GBNF (Grammar BNF) is llama.cpp's format for constrained generation.
Unlike full regex, GBNF uses BNF-style rules with character classes.
"""


class TestGBNFCompilerConstraintToRule:
    """Test individual constraint -> GBNF rule compilation."""

    def test_req_constraint_compiles_to_nonempty_rule(self):
        """REQ constraint should compile to non-empty char+ rule."""
        from octave_mcp.core.constraints import RequiredConstraint
        from octave_mcp.core.gbnf_compiler import GBNFCompiler

        compiler = GBNFCompiler()
        constraint = RequiredConstraint()
        rule = compiler.compile_constraint(constraint)

        # REQ means at least one character (non-empty)
        assert rule is not None
        assert len(rule) > 0
        # Should have some form of non-empty match

    def test_opt_constraint_compiles_to_optional_rule(self):
        """OPT constraint should compile to optional (can be empty) rule."""
        from octave_mcp.core.constraints import OptionalConstraint
        from octave_mcp.core.gbnf_compiler import GBNFCompiler

        compiler = GBNFCompiler()
        constraint = OptionalConstraint()
        rule = compiler.compile_constraint(constraint)

        # OPT means can be empty or have value
        assert rule is not None

    def test_enum_constraint_compiles_to_alternation(self):
        """ENUM[A,B,C] should compile to GBNF alternation rule."""
        from octave_mcp.core.constraints import EnumConstraint
        from octave_mcp.core.gbnf_compiler import GBNFCompiler

        compiler = GBNFCompiler()
        constraint = EnumConstraint(allowed_values=["ACTIVE", "ARCHIVED", "DELETED"])
        rule = compiler.compile_constraint(constraint)

        # GBNF alternation uses | operator: ("ACTIVE" | "ARCHIVED" | "DELETED")
        assert rule is not None
        assert "ACTIVE" in rule
        assert "ARCHIVED" in rule
        assert "DELETED" in rule
        # GBNF uses | for alternation (like BNF)
        assert "|" in rule

    def test_const_constraint_compiles_to_literal(self):
        """CONST[X] should compile to exact literal match in GBNF."""
        from octave_mcp.core.constraints import ConstConstraint
        from octave_mcp.core.gbnf_compiler import GBNFCompiler

        compiler = GBNFCompiler()
        constraint = ConstConstraint(const_value="FIXED")
        rule = compiler.compile_constraint(constraint)

        # GBNF literals are quoted: "FIXED"
        assert rule is not None
        assert "FIXED" in rule

    def test_type_string_compiles_to_char_class(self):
        """TYPE[STRING] should compile to GBNF string rule."""
        from octave_mcp.core.constraints import TypeConstraint
        from octave_mcp.core.gbnf_compiler import GBNFCompiler

        compiler = GBNFCompiler()
        constraint = TypeConstraint(expected_type="STRING")
        rule = compiler.compile_constraint(constraint)

        assert rule is not None
        # String type allows any characters

    def test_type_number_compiles_to_numeric_rule(self):
        """TYPE[NUMBER] should compile to GBNF numeric pattern."""
        from octave_mcp.core.constraints import TypeConstraint
        from octave_mcp.core.gbnf_compiler import GBNFCompiler

        compiler = GBNFCompiler()
        constraint = TypeConstraint(expected_type="NUMBER")
        rule = compiler.compile_constraint(constraint)

        assert rule is not None
        # Should match digits, optional decimal, optional negative

    def test_type_boolean_compiles_to_bool_alternation(self):
        """TYPE[BOOLEAN] should compile to "true" | "false" alternation."""
        from octave_mcp.core.constraints import TypeConstraint
        from octave_mcp.core.gbnf_compiler import GBNFCompiler

        compiler = GBNFCompiler()
        constraint = TypeConstraint(expected_type="BOOLEAN")
        rule = compiler.compile_constraint(constraint)

        assert rule is not None
        assert "true" in rule
        assert "false" in rule

    def test_type_list_compiles_to_array_rule(self):
        """TYPE[LIST] should compile to GBNF array structure."""
        from octave_mcp.core.constraints import TypeConstraint
        from octave_mcp.core.gbnf_compiler import GBNFCompiler

        compiler = GBNFCompiler()
        constraint = TypeConstraint(expected_type="LIST")
        rule = compiler.compile_constraint(constraint)

        assert rule is not None
        # Should have bracket matching

    def test_regex_constraint_compiles_to_char_class(self):
        """REGEX[pattern] should compile to GBNF char class (subset mapping)."""
        from octave_mcp.core.constraints import RegexConstraint
        from octave_mcp.core.gbnf_compiler import GBNFCompiler

        compiler = GBNFCompiler()
        # Simple character class regex
        constraint = RegexConstraint(pattern=r"^[a-z]+$")
        rule = compiler.compile_constraint(constraint)

        assert rule is not None
        # GBNF supports [a-z]+ style char classes

    def test_dir_constraint_compiles_to_path_rule(self):
        """DIR constraint should compile to GBNF path character rule."""
        from octave_mcp.core.constraints import DirConstraint
        from octave_mcp.core.gbnf_compiler import GBNFCompiler

        compiler = GBNFCompiler()
        constraint = DirConstraint()
        rule = compiler.compile_constraint(constraint)

        assert rule is not None

    def test_append_only_compiles_to_list_rule(self):
        """APPEND_ONLY should compile to GBNF list rule."""
        from octave_mcp.core.constraints import AppendOnlyConstraint
        from octave_mcp.core.gbnf_compiler import GBNFCompiler

        compiler = GBNFCompiler()
        constraint = AppendOnlyConstraint()
        rule = compiler.compile_constraint(constraint)

        assert rule is not None

    def test_range_constraint_compiles_to_numeric_rule(self):
        """RANGE[min,max] should compile to GBNF numeric rule."""
        from octave_mcp.core.constraints import RangeConstraint
        from octave_mcp.core.gbnf_compiler import GBNFCompiler

        compiler = GBNFCompiler()
        constraint = RangeConstraint(min_value=0, max_value=100)
        rule = compiler.compile_constraint(constraint)

        assert rule is not None
        # Note: GBNF can't enforce numeric bounds at grammar level,
        # but can match numeric pattern

    def test_max_length_constraint_compiles_to_bounded_rule(self):
        """MAX_LENGTH[N] should compile to bounded repetition."""
        from octave_mcp.core.constraints import MaxLengthConstraint
        from octave_mcp.core.gbnf_compiler import GBNFCompiler

        compiler = GBNFCompiler()
        constraint = MaxLengthConstraint(max_length=10)
        rule = compiler.compile_constraint(constraint)

        assert rule is not None

    def test_min_length_constraint_compiles_to_bounded_rule(self):
        """MIN_LENGTH[N] should compile to minimum repetition."""
        from octave_mcp.core.constraints import MinLengthConstraint
        from octave_mcp.core.gbnf_compiler import GBNFCompiler

        compiler = GBNFCompiler()
        constraint = MinLengthConstraint(min_length=3)
        rule = compiler.compile_constraint(constraint)

        assert rule is not None

    def test_date_constraint_compiles_to_date_pattern(self):
        """DATE should compile to YYYY-MM-DD GBNF pattern."""
        from octave_mcp.core.constraints import DateConstraint
        from octave_mcp.core.gbnf_compiler import GBNFCompiler

        compiler = GBNFCompiler()
        constraint = DateConstraint()
        rule = compiler.compile_constraint(constraint)

        assert rule is not None
        # Should match date format with digits and dashes

    def test_iso8601_constraint_compiles_to_datetime_pattern(self):
        """ISO8601 should compile to GBNF datetime pattern."""
        from octave_mcp.core.constraints import Iso8601Constraint
        from octave_mcp.core.gbnf_compiler import GBNFCompiler

        compiler = GBNFCompiler()
        constraint = Iso8601Constraint()
        rule = compiler.compile_constraint(constraint)

        assert rule is not None


class TestGBNFCompilerChainCompilation:
    """Test constraint chain -> GBNF compilation."""

    def test_single_constraint_chain(self):
        """Single constraint chain should produce valid GBNF."""
        from octave_mcp.core.constraints import ConstraintChain
        from octave_mcp.core.gbnf_compiler import GBNFCompiler

        compiler = GBNFCompiler()
        chain = ConstraintChain.parse("REQ")
        rule = compiler.compile_chain(chain)

        assert rule is not None
        assert len(rule) > 0

    def test_multi_constraint_chain(self):
        """Multiple constraints should combine in GBNF."""
        from octave_mcp.core.constraints import ConstraintChain
        from octave_mcp.core.gbnf_compiler import GBNFCompiler

        compiler = GBNFCompiler()
        chain = ConstraintChain.parse("REQ∧TYPE[STRING]")
        rule = compiler.compile_chain(chain)

        assert rule is not None

    def test_complex_chain_with_enum(self):
        """Complex chain with ENUM should produce valid GBNF."""
        from octave_mcp.core.constraints import ConstraintChain
        from octave_mcp.core.gbnf_compiler import GBNFCompiler

        compiler = GBNFCompiler()
        chain = ConstraintChain.parse("REQ∧ENUM[ACTIVE,ARCHIVED,DELETED]")
        rule = compiler.compile_chain(chain)

        assert rule is not None
        # The ENUM should dominate the rule
        assert "ACTIVE" in rule


class TestGBNFCompilerSchemaCompilation:
    """Test full schema -> GBNF compilation."""

    def test_compile_schema_produces_grammar(self):
        """Compiling a schema should produce complete GBNF grammar."""
        from octave_mcp.core.constraints import ConstraintChain
        from octave_mcp.core.gbnf_compiler import GBNFCompiler
        from octave_mcp.core.holographic import HolographicPattern
        from octave_mcp.core.schema_extractor import FieldDefinition, SchemaDefinition

        compiler = GBNFCompiler()

        # Create a minimal schema
        schema = SchemaDefinition(
            name="TEST_SCHEMA",
            version="1.0",
            fields={
                "STATUS": FieldDefinition(
                    name="STATUS",
                    pattern=HolographicPattern(
                        example="ACTIVE",
                        constraints=ConstraintChain.parse("REQ∧ENUM[ACTIVE,ARCHIVED]"),
                        target=None,
                    ),
                ),
            },
        )

        grammar = compiler.compile_schema(schema)

        assert grammar is not None
        assert len(grammar) > 0
        # GBNF grammar should have root rule
        assert "root" in grammar or "::=" in grammar

    def test_compile_schema_includes_all_fields(self):
        """Schema compilation should include rules for all fields."""
        from octave_mcp.core.constraints import ConstraintChain
        from octave_mcp.core.gbnf_compiler import GBNFCompiler
        from octave_mcp.core.holographic import HolographicPattern
        from octave_mcp.core.schema_extractor import FieldDefinition, SchemaDefinition

        compiler = GBNFCompiler()

        schema = SchemaDefinition(
            name="MULTI_FIELD",
            version="1.0",
            fields={
                "ID": FieldDefinition(
                    name="ID",
                    pattern=HolographicPattern(
                        example="abc123",
                        constraints=ConstraintChain.parse("REQ∧TYPE[STRING]"),
                        target=None,
                    ),
                ),
                "COUNT": FieldDefinition(
                    name="COUNT",
                    pattern=HolographicPattern(
                        example=42,
                        constraints=ConstraintChain.parse("REQ∧TYPE[NUMBER]"),
                        target=None,
                    ),
                ),
            },
        )

        grammar = compiler.compile_schema(schema)

        # Both fields should be represented
        assert "ID" in grammar or "id" in grammar.lower()
        assert "COUNT" in grammar or "count" in grammar.lower()


class TestGBNFSyntaxValidity:
    """Test that generated GBNF follows llama.cpp syntax."""

    def test_gbnf_uses_correct_assignment_operator(self):
        """GBNF uses ::= for rule definition."""
        from octave_mcp.core.constraints import ConstraintChain
        from octave_mcp.core.gbnf_compiler import GBNFCompiler
        from octave_mcp.core.holographic import HolographicPattern
        from octave_mcp.core.schema_extractor import FieldDefinition, SchemaDefinition

        compiler = GBNFCompiler()

        schema = SchemaDefinition(
            name="TEST",
            version="1.0",
            fields={
                "FIELD": FieldDefinition(
                    name="FIELD",
                    pattern=HolographicPattern(
                        example="value",
                        constraints=ConstraintChain.parse("REQ"),
                        target=None,
                    ),
                ),
            },
        )

        grammar = compiler.compile_schema(schema)

        # GBNF uses ::= operator
        assert "::=" in grammar

    def test_gbnf_literals_are_quoted(self):
        """GBNF string literals must be in double quotes."""
        from octave_mcp.core.constraints import ConstConstraint
        from octave_mcp.core.gbnf_compiler import GBNFCompiler

        compiler = GBNFCompiler()
        constraint = ConstConstraint(const_value="LITERAL")
        rule = compiler.compile_constraint(constraint)

        # Literal should be quoted
        assert '"LITERAL"' in rule

    def test_gbnf_char_classes_use_brackets(self):
        """GBNF character classes use square brackets [a-z]."""
        from octave_mcp.core.constraints import RegexConstraint
        from octave_mcp.core.gbnf_compiler import GBNFCompiler

        compiler = GBNFCompiler()
        constraint = RegexConstraint(pattern=r"^[a-z]+$")
        rule = compiler.compile_constraint(constraint)

        # Character class should use brackets
        assert "[" in rule and "]" in rule

    def test_gbnf_repetition_uses_plus_star(self):
        """GBNF uses + for one-or-more, * for zero-or-more."""
        from octave_mcp.core.constraints import RequiredConstraint
        from octave_mcp.core.gbnf_compiler import GBNFCompiler

        compiler = GBNFCompiler()
        constraint = RequiredConstraint()
        rule = compiler.compile_constraint(constraint)

        # REQ implies at least one, so should use +
        assert "+" in rule or rule.count("*") == 0  # Either explicit + or no *


class TestGBNFRuleNameSanitization:
    """Test rule name sanitization for special characters (CE blocker fix)."""

    def test_field_name_with_dot_produces_valid_rule_name(self):
        """Field name with '.' (e.g., ARM.result) should produce valid GBNF rule name."""
        from octave_mcp.core.constraints import ConstraintChain
        from octave_mcp.core.gbnf_compiler import GBNFCompiler
        from octave_mcp.core.holographic import HolographicPattern
        from octave_mcp.core.schema_extractor import FieldDefinition, SchemaDefinition

        compiler = GBNFCompiler()
        schema = SchemaDefinition(
            name="TEST",
            version="1.0",
            fields={
                "ARM.result": FieldDefinition(
                    name="ARM.result",
                    pattern=HolographicPattern(
                        example="value",
                        constraints=ConstraintChain.parse("REQ"),
                        target=None,
                    ),
                ),
            },
        )

        grammar = compiler.compile_schema(schema)

        # Rule name should not contain raw '.' - should be sanitized
        assert "arm_dot_result" in grammar.lower()
        # The field reference in literals is fine, but rule name must be valid
        assert "::=" in grammar

    def test_field_name_with_slash_produces_valid_rule_name(self):
        """Field name with '/' (e.g., path/to/file) should produce valid GBNF rule name."""
        from octave_mcp.core.constraints import ConstraintChain
        from octave_mcp.core.gbnf_compiler import GBNFCompiler
        from octave_mcp.core.holographic import HolographicPattern
        from octave_mcp.core.schema_extractor import FieldDefinition, SchemaDefinition

        compiler = GBNFCompiler()
        schema = SchemaDefinition(
            name="TEST",
            version="1.0",
            fields={
                "path/to/file": FieldDefinition(
                    name="path/to/file",
                    pattern=HolographicPattern(
                        example="value",
                        constraints=ConstraintChain.parse("REQ"),
                        target=None,
                    ),
                ),
            },
        )

        grammar = compiler.compile_schema(schema)

        # Rule name should not contain raw '/' - should be sanitized
        assert "path_slash_to_slash_file" in grammar.lower()
        assert "::=" in grammar

    def test_field_name_with_emoji_produces_valid_rule_name(self):
        """Field name with emoji should produce valid GBNF rule name with _u{hex}_ encoding."""
        from octave_mcp.core.constraints import ConstraintChain
        from octave_mcp.core.gbnf_compiler import GBNFCompiler
        from octave_mcp.core.holographic import HolographicPattern
        from octave_mcp.core.schema_extractor import FieldDefinition, SchemaDefinition

        compiler = GBNFCompiler()
        # Use actual emoji in field name: ⚠️ (U+26A0 WARNING SIGN + U+FE0F VARIATION SELECTOR)
        schema = SchemaDefinition(
            name="TEST",
            version="1.0",
            fields={
                "⚠️_warning": FieldDefinition(
                    name="⚠️_warning",
                    pattern=HolographicPattern(
                        example="value",
                        constraints=ConstraintChain.parse("REQ"),
                        target=None,
                    ),
                ),
            },
        )

        grammar = compiler.compile_schema(schema)

        # Rule name with emoji should be encoded as _u{hex}_ format
        # ⚠️ = U+26A0 + U+FE0F, so expect u26a0_ufe0f_warning as rule name
        assert "u26a0_ufe0f_warning" in grammar.lower()
        assert "::=" in grammar
        # Rule name should be sanitized, but the literal value keeps the emoji for matching
        # e.g., u26a0_ufe0f_warning ::= "⚠️_warning" "::" ...
        assert 'u26a0_ufe0f_warning ::= "⚠️_warning"' in grammar

    def test_sanitize_rule_name_method_exists(self):
        """GBNFCompiler should have _sanitize_rule_name method."""
        from octave_mcp.core.gbnf_compiler import GBNFCompiler

        compiler = GBNFCompiler()
        assert hasattr(compiler, "_sanitize_rule_name")

        # Test basic sanitization
        assert compiler._sanitize_rule_name("simple") == "simple"
        assert compiler._sanitize_rule_name("with-dash") == "with_dash"
        assert compiler._sanitize_rule_name("ARM.result") == "arm_dot_result"
        assert compiler._sanitize_rule_name("path/to") == "path_slash_to"


class TestGBNFEdgeCases:
    """Test edge cases and special scenarios."""

    def test_enum_with_special_characters(self):
        """ENUM values with special chars should be escaped."""
        from octave_mcp.core.constraints import EnumConstraint
        from octave_mcp.core.gbnf_compiler import GBNFCompiler

        compiler = GBNFCompiler()
        constraint = EnumConstraint(allowed_values=["WITH-DASH", "WITH_UNDERSCORE"])
        rule = compiler.compile_constraint(constraint)

        assert "WITH-DASH" in rule or "WITH\\-DASH" in rule
        assert "WITH_UNDERSCORE" in rule

    def test_const_with_quotes_escapes_properly(self):
        """CONST with quote chars should escape them in GBNF."""
        from octave_mcp.core.constraints import ConstConstraint
        from octave_mcp.core.gbnf_compiler import GBNFCompiler

        compiler = GBNFCompiler()
        constraint = ConstConstraint(const_value='say "hello"')
        rule = compiler.compile_constraint(constraint)

        # Quotes inside should be escaped
        assert '\\"' in rule or "\\x22" in rule or rule.count('"') >= 4

    def test_empty_schema_produces_minimal_grammar(self):
        """Empty schema should produce minimal valid grammar."""
        from octave_mcp.core.gbnf_compiler import GBNFCompiler
        from octave_mcp.core.schema_extractor import SchemaDefinition

        compiler = GBNFCompiler()
        schema = SchemaDefinition(name="EMPTY", version="1.0")

        grammar = compiler.compile_schema(schema)

        assert grammar is not None
        # Should still have root rule
        assert "root" in grammar or "::=" in grammar

    def test_regex_complex_pattern_degrades_gracefully(self):
        """Complex regex should degrade to safe pattern when unsupported."""
        from octave_mcp.core.constraints import RegexConstraint
        from octave_mcp.core.gbnf_compiler import GBNFCompiler

        compiler = GBNFCompiler()
        # Lookahead not supported in GBNF
        constraint = RegexConstraint(pattern=r"^(?=.*[a-z])(?=.*[0-9])[a-z0-9]+$")
        rule = compiler.compile_constraint(constraint)

        # Should produce something valid, even if simplified
        assert rule is not None
        assert len(rule) > 0


class TestGBNFOctaveDocumentGeneration:
    """Test GBNF generation for OCTAVE document structure."""

    def test_generates_envelope_rules(self):
        """Should generate GBNF rules for OCTAVE envelope (===NAME===...===END===)."""
        from octave_mcp.core.gbnf_compiler import GBNFCompiler
        from octave_mcp.core.schema_extractor import SchemaDefinition

        compiler = GBNFCompiler()
        schema = SchemaDefinition(name="DOC_SCHEMA", version="1.0")

        grammar = compiler.compile_schema(schema, include_envelope=True)

        # Should include envelope structure
        assert "===" in grammar or "envelope" in grammar.lower()

    def test_generates_meta_block_rules(self):
        """Should generate GBNF rules for META block structure."""
        from octave_mcp.core.gbnf_compiler import GBNFCompiler
        from octave_mcp.core.schema_extractor import SchemaDefinition

        compiler = GBNFCompiler()
        schema = SchemaDefinition(name="TEST", version="1.0")

        grammar = compiler.compile_schema(schema, include_envelope=True)

        # META block structure
        assert "META" in grammar or "meta" in grammar.lower()


class TestGBNFCompilerFromMeta:
    """Test GBNF compilation from META block (grammar.py integration)."""

    def test_compile_from_meta_dict(self):
        """compile_document_grammar should use GBNFCompiler."""
        # This tests the integration point with grammar.py
        from octave_mcp.core.grammar import compile_document_grammar

        meta = {
            "TYPE": "TEST_SCHEMA",
            "VERSION": "1.0",
            "GRAMMAR": {
                "GENERATOR": "OCTAVE_GBNF_COMPILER",
            },
        }

        grammar = compile_document_grammar(meta)

        # After implementation, should return actual GBNF
        assert grammar is not None
        # Should no longer be stub
        assert "stub" not in grammar.lower() or "::=" in grammar


class TestGBNFMetaContractCompilation:
    """Test META CONTRACT schema compilation (Issue #191).

    v6 self-describing documents carry their own validation rules via META.CONTRACT.
    CONTRACT is a list in META, format: FIELD[name]::constraint_chain.
    """

    def test_parse_contract_from_meta_basic(self):
        """CONTRACT list in META should be parsed into schema fields."""
        from octave_mcp.core.gbnf_compiler import compile_gbnf_from_meta

        meta = {
            "TYPE": "SESSION_LOG",
            "VERSION": "1.0",
            "CONTRACT": [
                "FIELD[STATUS]::REQ∧ENUM[ACTIVE,PAUSED,COMPLETE]",
                "FIELD[PRIORITY]::OPT∧ENUM[LOW,MEDIUM,HIGH]",
            ],
        }
        gbnf = compile_gbnf_from_meta(meta)

        # Should have field-specific rules
        assert "status" in gbnf.lower()  # Rule name
        assert "priority" in gbnf.lower()  # Rule name
        # GBNF grammar should be valid
        assert "::=" in gbnf

    def test_contract_enum_compiles_to_alternation(self):
        """ENUM constraint in CONTRACT should compile to GBNF alternation."""
        from octave_mcp.core.gbnf_compiler import compile_gbnf_from_meta

        meta = {
            "TYPE": "TEST_SCHEMA",
            "VERSION": "1.0",
            "CONTRACT": [
                "FIELD[STATUS]::REQ∧ENUM[ACTIVE,PAUSED,COMPLETE]",
            ],
        }
        gbnf = compile_gbnf_from_meta(meta)

        # ENUM values should appear as alternation in GBNF
        assert '"ACTIVE"' in gbnf
        assert '"PAUSED"' in gbnf
        assert '"COMPLETE"' in gbnf
        # GBNF uses | for alternation
        assert "|" in gbnf

    def test_contract_req_constraint_compiles_correctly(self):
        """REQ constraint in CONTRACT should compile to non-empty pattern."""
        from octave_mcp.core.gbnf_compiler import compile_gbnf_from_meta

        meta = {
            "TYPE": "TEST_SCHEMA",
            "VERSION": "1.0",
            "CONTRACT": [
                "FIELD[NAME]::REQ",
            ],
        }
        gbnf = compile_gbnf_from_meta(meta)

        # Should have the NAME field rule
        assert "name" in gbnf.lower()
        # REQ compiles to [^\n]+ (non-empty)
        assert "[^\\n]+" in gbnf

    def test_contract_opt_constraint_compiles_correctly(self):
        """OPT constraint in CONTRACT should compile to optional pattern."""
        from octave_mcp.core.gbnf_compiler import compile_gbnf_from_meta

        meta = {
            "TYPE": "TEST_SCHEMA",
            "VERSION": "1.0",
            "CONTRACT": [
                "FIELD[NOTES]::OPT",
            ],
        }
        gbnf = compile_gbnf_from_meta(meta)

        # Should have the NOTES field rule
        assert "notes" in gbnf.lower()
        # OPT compiles to [^\n]* (can be empty)
        assert "[^\\n]*" in gbnf

    def test_contract_multiple_constraints_chain(self):
        """Multiple constraints in CONTRACT field should be combined."""
        from octave_mcp.core.gbnf_compiler import compile_gbnf_from_meta

        meta = {
            "TYPE": "TEST_SCHEMA",
            "VERSION": "1.0",
            "CONTRACT": [
                "FIELD[LEVEL]::REQ∧ENUM[DEBUG,INFO,WARN,ERROR]",
            ],
        }
        gbnf = compile_gbnf_from_meta(meta)

        # The ENUM should take precedence in GBNF output (most restrictive)
        assert '"DEBUG"' in gbnf or '"INFO"' in gbnf
        assert "|" in gbnf

    def test_contract_empty_list_produces_minimal_grammar(self):
        """Empty CONTRACT list should produce minimal valid grammar."""
        from octave_mcp.core.gbnf_compiler import compile_gbnf_from_meta

        meta = {
            "TYPE": "MINIMAL",
            "VERSION": "1.0",
            "CONTRACT": [],
        }
        gbnf = compile_gbnf_from_meta(meta)

        # Should still have root rule and basic structure
        assert "root" in gbnf
        assert "::=" in gbnf

    def test_contract_missing_produces_minimal_grammar(self):
        """META without CONTRACT should produce basic schema grammar."""
        from octave_mcp.core.gbnf_compiler import compile_gbnf_from_meta

        meta = {
            "TYPE": "NO_CONTRACT",
            "VERSION": "1.0",
        }
        gbnf = compile_gbnf_from_meta(meta)

        # Should still produce valid GBNF
        assert "root" in gbnf
        assert "::=" in gbnf

    def test_contract_field_parsing_helper(self):
        """Helper function should parse FIELD[name]::constraints format."""
        from octave_mcp.core.gbnf_compiler import parse_contract_field

        # Test basic parsing
        field_name, constraints = parse_contract_field("FIELD[STATUS]::REQ∧ENUM[ACTIVE,PAUSED]")
        assert field_name == "STATUS"
        assert constraints is not None
        assert len(constraints.constraints) == 2

    def test_contract_field_parsing_simple_constraint(self):
        """Helper should handle single constraint."""
        from octave_mcp.core.gbnf_compiler import parse_contract_field

        field_name, constraints = parse_contract_field("FIELD[NAME]::REQ")
        assert field_name == "NAME"
        assert constraints is not None
        assert len(constraints.constraints) == 1

    def test_contract_invalid_format_raises_error(self):
        """Invalid CONTRACT field format should raise ValueError."""
        import pytest

        from octave_mcp.core.gbnf_compiler import parse_contract_field

        # Missing FIELD[] wrapper
        with pytest.raises(ValueError, match="Invalid CONTRACT field format"):
            parse_contract_field("STATUS::REQ")

        # Missing :: separator
        with pytest.raises(ValueError, match="Invalid CONTRACT field format"):
            parse_contract_field("FIELD[STATUS]REQ")

    def test_full_integration_compile_from_meta_with_contract(self):
        """Full integration: META with CONTRACT compiles to complete GBNF."""
        from octave_mcp.core.gbnf_compiler import compile_gbnf_from_meta

        meta = {
            "TYPE": "SESSION_LOG",
            "VERSION": "1.0",
            "CONTRACT": [
                "FIELD[STATUS]::REQ∧ENUM[ACTIVE,PAUSED,COMPLETE]",
                "FIELD[PRIORITY]::OPT∧ENUM[LOW,MEDIUM,HIGH]",
                "FIELD[TIMESTAMP]::REQ∧ISO8601",
            ],
        }
        gbnf = compile_gbnf_from_meta(meta)

        # Verify complete grammar structure
        assert "SESSION_LOG" in gbnf  # Schema name in envelope
        assert "status" in gbnf.lower()
        assert "priority" in gbnf.lower()
        assert "timestamp" in gbnf.lower()
        assert '"ACTIVE"' in gbnf
        assert '"LOW"' in gbnf
        # ISO8601 pattern elements
        assert "root ::=" in gbnf


class TestIntegrationHelpers:
    """Test integration helpers for different LLM backends."""

    def test_llama_cpp_helper_exists(self):
        """llama_cpp integration helper should exist."""
        from octave_mcp.integrations.llama_cpp import format_for_llama_cpp

        grammar = 'root ::= "test"'
        result = format_for_llama_cpp(grammar)
        assert result is not None

    def test_outlines_helper_exists(self):
        """Outlines integration helper should exist."""
        from octave_mcp.core.schema_extractor import SchemaDefinition
        from octave_mcp.integrations.outlines import schema_to_json_schema

        schema = SchemaDefinition(name="TEST", version="1.0")
        result = schema_to_json_schema(schema)
        assert result is not None
        assert isinstance(result, dict)

    def test_vllm_helper_exists(self):
        """vLLM integration helper should exist."""
        from octave_mcp.integrations.vllm import format_for_vllm

        grammar = 'root ::= "test"'
        result = format_for_vllm(grammar)
        assert result is not None
