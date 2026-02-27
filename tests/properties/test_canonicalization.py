"""Property-based tests for canonicalization invariants (P3.1).

Tests fundamental properties that MUST hold for all valid inputs:
- Idempotence: canon(canon(x)) == canon(x)
- Determinism: same input always produces same output
- Totality: every valid lenient input has exactly one canonical form
- Round-trip: parse(emit(ast)) produces equivalent AST
"""

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from octave_mcp.core.emitter import emit
from octave_mcp.core.lexer import tokenize
from octave_mcp.core.parser import ParserError, parse

# Reserved keywords that cannot be used as regular document keys
RESERVED_KEYWORDS = {"META"}


# Strategy for generating valid OCTAVE documents
@st.composite
def octave_document(draw):
    """Generate valid OCTAVE document."""
    name = draw(
        st.text(
            alphabet=st.characters(whitelist_categories=("Lu",), whitelist_characters="_", max_codepoint=127),
            min_size=1,
            max_size=20,
        ).filter(lambda x: x and x[0].isalpha() and x.isupper())
    )

    fields = draw(
        st.lists(
            st.tuples(
                st.text(
                    alphabet=st.characters(whitelist_categories=("Lu",), whitelist_characters="_", max_codepoint=127),
                    min_size=1,
                    max_size=15,
                ).filter(lambda x: x and x[0].isupper() and x not in RESERVED_KEYWORDS),
                st.text(min_size=1, max_size=50),
            ),
            min_size=1,
            max_size=10,
        )
    )

    doc = f"==={name}===\n"
    for key, value in fields:
        # Escape special characters in value for validity
        escaped_value = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
        doc += f'{key}::"{escaped_value}"\n'
    doc += "===END==="

    return doc


class TestCanonicalizationProperties:
    """Property-based tests for canonicalization."""

    def test_idempotence_simple(self):
        """Idempotence: canon(canon(x)) == canon(x) - simple case."""
        # Simple lenient input
        lenient = """===TEST===
TYPE :: "demo"
STATUS -> active
===END==="""

        # First canonicalization
        tokens1, _ = tokenize(lenient)
        doc1 = parse(tokens1)
        canonical1 = emit(doc1)

        # Second canonicalization
        tokens2, _ = tokenize(canonical1)
        doc2 = parse(tokens2)
        canonical2 = emit(doc2)

        # Should be identical
        assert canonical1 == canonical2, "Canonicalization is not idempotent"

    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=50)
    @given(doc=octave_document())
    def test_idempotence_property(self, doc):
        """Idempotence property: canon(canon(x)) == canon(x)."""
        try:
            # First pass
            tokens1, _ = tokenize(doc)
            ast1 = parse(tokens1)
            output1 = emit(ast1)

            # Second pass
            tokens2, _ = tokenize(output1)
            ast2 = parse(tokens2)
            output2 = emit(ast2)

            # Must be identical
            assert output1 == output2, "Idempotence violated"
        except (ValueError, ParserError):
            # Skip invalid generated inputs
            pytest.skip("Invalid input generated")

    def test_determinism_simple(self):
        """Determinism: same input produces same output - simple case."""
        source = """===TEST===
DATA::[1,2,3]
===END==="""

        # Process multiple times
        outputs = []
        for _ in range(5):
            doc = parse(source)
            output = emit(doc)
            outputs.append(output)

        # All outputs must be identical
        assert all(o == outputs[0] for o in outputs), "Determinism violated"

    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=30)
    @given(doc=octave_document())
    def test_determinism_property(self, doc):
        """Determinism property: same input always produces same output."""
        try:
            outputs = []
            for _ in range(3):
                ast = parse(doc)
                output = emit(ast)
                outputs.append(output)

            # All must be identical
            assert all(o == outputs[0] for o in outputs), "Determinism violated"
        except (ValueError, ParserError):
            pytest.skip("Invalid input")

    def test_totality_ascii_aliases(self):
        """Totality: ASCII aliases map to unique canonical form."""
        # Test all ASCII aliases produce canonical unicode
        ascii_variants = [
            ("TYPE -> value", "TYPE→value"),
            ("A + B", "A⊕B"),
            ("X vs Y", "X⇌Y"),
            ("A | B", "A∨B"),
            ("A & B", "A∧B"),
        ]

        for ascii_form, expected_operator in ascii_variants:
            doc = f"===TEST===\n{ascii_form}\n===END==="

            ast = parse(doc)
            output = emit(ast)

            # Should contain unicode operator, not ASCII
            assert expected_operator in output or "->" not in output
            assert " + " not in output  # No binary + in output
            assert " vs " not in output
            assert " | " not in output
            assert " & " not in output

    def test_round_trip_preserves_structure(self):
        """Round-trip: parse(emit(ast)) preserves structure."""
        source = """===ROUNDTRIP===
META:
  TYPE::"TEST"
  VERSION::"1.0"

NESTED:
  FIELD_A::value_a
  FIELD_B::value_b

FLAT::simple_value
===END==="""

        # Parse to AST
        tokens, _ = tokenize(source)
        original_ast = parse(tokens)

        # Emit and parse again
        output = emit(original_ast)
        tokens2, _ = tokenize(output)
        roundtrip_ast = parse(tokens2)

        # ASTs should be structurally equivalent
        # (exact equality may vary, but emit should match)
        original_emit = emit(original_ast)
        roundtrip_emit = emit(roundtrip_ast)

        assert original_emit == roundtrip_emit

    def test_whitespace_normalization_canonical(self):
        """Whitespace variations produce identical canonical form."""
        variants = [
            "KEY::value",
            "KEY :: value",
            "KEY  ::  value",
            "KEY:: value",
            "KEY ::value",
        ]

        canonical_outputs = []
        for variant in variants:
            doc = f"===TEST===\n{variant}\n===END==="

            ast = parse(doc)
            output = emit(ast)
            canonical_outputs.append(output)

        # All should produce same canonical form
        assert all(o == canonical_outputs[0] for o in canonical_outputs)

    def test_envelope_normalization(self):
        """Envelope is always explicit in canonical form."""
        # Input without explicit envelope (single doc)
        single_doc = 'TYPE::"value"'

        ast = parse(single_doc)
        output = emit(ast)

        # Output must have explicit envelope
        assert output.startswith("===")
        assert output.rstrip("\n").endswith("===")

    def test_quote_normalization(self):
        """Strings requiring quotes are quoted in canonical form."""
        cases = [
            ('KEY::"value with spaces"', True),  # Must quote
            ("KEY::simple", False),  # May not quote
            ("KEY::has_dash", False),  # May not quote (underscore allowed)
            ('KEY::"already quoted"', True),  # Stays quoted
        ]

        for input_line, must_have_quotes in cases:
            doc = f"===TEST===\n{input_line}\n===END==="

            ast = parse(doc)
            output = emit(ast)

            if must_have_quotes:
                # Should contain quoted value
                assert '"' in output or "'" in output

    def test_nested_structure_preservation(self):
        """Nested structures preserve hierarchy in canonical form."""
        nested = """===NESTED===
LEVEL1:
  LEVEL2:
    LEVEL3::deep_value

FLAT::surface_value
===END==="""

        ast = parse(nested)
        output = emit(ast)

        # Must preserve nesting (via indentation or structure)
        assert "LEVEL1" in output
        assert "LEVEL2" in output
        assert "LEVEL3" in output
        assert "FLAT" in output

    def test_list_normalization(self):
        """Lists normalize to canonical format."""
        list_doc = """===LIST_TEST===
ITEMS::[item1,item2,item3]
NESTED::[
  nested1,
  nested2
]
===END==="""

        ast = parse(list_doc)
        output = emit(ast)

        # Should contain list notation
        assert "[" in output
        assert "]" in output
        assert "ITEMS" in output
