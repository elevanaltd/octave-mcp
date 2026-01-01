"""Tests for OCTAVE canonical emitter (P1.4).

Tests AST → canonical OCTAVE string emission with:
- Unicode operators (never ASCII)
- No whitespace around ::
- Explicit envelope
- Deterministic output
- Idempotence
- I2 Deterministic Absence (Absent sentinel handling)
"""

import pytest

from octave_mcp.core.ast_nodes import Absent, Assignment, Block, Document, InlineMap, ListValue
from octave_mcp.core.emitter import emit, emit_meta, emit_value
from octave_mcp.core.parser import parse


class TestCanonicalEmission:
    """Test canonical OCTAVE emission."""

    def test_emits_unicode_operators(self):
        """Should emit unicode operators, never ASCII."""
        doc = Document(
            name="TEST",
            sections=[Assignment(key="FLOW", value="A→B→C")],
        )
        result = emit(doc)
        assert "→" in result
        assert "->" not in result

    def test_no_whitespace_around_assignment(self):
        """Should emit KEY::value with no spaces."""
        doc = Document(name="TEST", sections=[Assignment(key="KEY", value="value")])
        result = emit(doc)
        assert "KEY::value" in result
        assert "KEY :: value" not in result

    def test_explicit_envelope_always_present(self):
        """Should always emit explicit envelope."""
        doc = Document(name="TEST", sections=[Assignment(key="KEY", value="value")])
        result = emit(doc)
        assert result.startswith("===TEST===")
        assert result.strip().endswith("===END===")

    def test_quoted_strings_where_required(self):
        """Should quote strings with spaces/special chars."""
        doc = Document(name="TEST", sections=[Assignment(key="KEY", value="hello world")])
        result = emit(doc)
        assert '"hello world"' in result

    def test_bare_strings_when_safe(self):
        """Should use bare words when no spaces/special chars."""
        doc = Document(name="TEST", sections=[Assignment(key="KEY", value="simple")])
        result = emit(doc)
        assert "KEY::simple" in result
        assert '"simple"' not in result

    def test_2_space_indentation(self):
        """Should use consistent 2-space indentation."""
        doc = Document(
            name="TEST",
            sections=[Block(key="BLOCK", children=[Assignment(key="CHILD", value="value")])],
        )
        result = emit(doc)
        lines = result.split("\n")
        # Find CHILD line
        child_line = [line for line in lines if "CHILD" in line][0]
        assert child_line.startswith("  ")  # 2 spaces
        assert not child_line.startswith("    ")  # Not 4 spaces

    def test_empty_list(self):
        """Should emit empty list as []."""
        doc = Document(name="TEST", sections=[Assignment(key="EMPTY", value=ListValue(items=[]))])
        result = emit(doc)
        assert "EMPTY::[]" in result

    def test_list_with_items(self):
        """Should emit list with comma-separated items."""
        doc = Document(name="TEST", sections=[Assignment(key="TAGS", value=ListValue(items=["a", "b", "c"]))])
        result = emit(doc)
        assert "TAGS::[a,b,c]" in result


class TestIdempotence:
    """Test emit is idempotent."""

    def test_emit_parse_emit_idempotent(self):
        """Should satisfy emit(parse(emit(parse(x)))) == emit(parse(x))."""
        original = """===TEST===
META:
  TYPE::TEST_DOC
  VERSION::"1.0"
---
DATA::value
TAGS::[a,b,c]
===END===
"""
        doc1 = parse(original)
        emitted1 = emit(doc1)
        doc2 = parse(emitted1)
        emitted2 = emit(doc2)
        assert emitted1 == emitted2


class TestMetaEmission:
    """Test META block emission."""

    def test_emits_meta_block(self):
        """Should emit META block."""
        doc = Document(
            name="TEST",
            meta={"TYPE": "TEST_DOC", "VERSION": "1.0"},
            sections=[],
        )
        result = emit(doc)
        assert "META:" in result
        assert "TYPE::TEST_DOC" in result
        assert "VERSION::" in result

    def test_emits_separator_when_present(self):
        """Should emit --- separator when has_separator=True."""
        doc = Document(name="TEST", has_separator=True, sections=[Assignment(key="KEY", value="value")])
        result = emit(doc)
        assert "---" in result


class TestBlockEmission:
    """Test block structure emission."""

    def test_emits_simple_block(self):
        """Should emit KEY: with nested children."""
        doc = Document(
            name="TEST",
            sections=[Block(key="CONFIG", children=[Assignment(key="NESTED", value="value")])],
        )
        result = emit(doc)
        assert "CONFIG:" in result
        assert "  NESTED::value" in result

    def test_emits_deeply_nested_blocks(self):
        """Should emit multiple nesting levels."""
        doc = Document(
            name="TEST",
            sections=[
                Block(
                    key="LEVEL1",
                    children=[
                        Block(key="LEVEL2", children=[Assignment(key="LEVEL3", value="value")]),
                    ],
                )
            ],
        )
        result = emit(doc)
        assert "LEVEL1:" in result
        assert "  LEVEL2:" in result
        assert "    LEVEL3::value" in result

    def test_empty_block(self):
        """Should emit empty block as KEY: with no children."""
        doc = Document(name="TEST", sections=[Block(key="EMPTY", children=[])])
        result = emit(doc)
        assert "EMPTY:" in result


class TestI2AbsentHandling:
    """Test I2 Deterministic Absence: Absent sentinel handling.

    Per CRS blocking feedback:
    - emit_value(Absent()) must raise ValueError (not return empty string)
    - Absent values in ListValue must be filtered out
    - Absent values in InlineMap must be filtered out
    - emit_meta() must return "" when all fields are absent
    """

    def test_emit_value_raises_on_absent(self):
        """emit_value(Absent()) must raise ValueError, not return empty string.

        CRS Issue 1: Absent can leak into emit_value producing invalid output.
        Previous behavior: returned "" which produced `KEY::` (empty value).
        Required behavior: raise ValueError to catch caller bugs.
        """
        with pytest.raises(ValueError, match="Absent"):
            emit_value(Absent())

    def test_list_with_absent_filters_absent_items(self):
        """ListValue containing Absent items must filter them out.

        CRS Issue 1: [Absent(), 'a'] previously emitted `[,a]` (invalid).
        Required: Absent items are filtered, emitting `[a]`.
        """
        list_val = ListValue(items=[Absent(), "a", Absent(), "b", Absent()])
        result = emit_value(list_val)
        assert result == "[a,b]"

    def test_inline_map_with_absent_filters_absent_values(self):
        """InlineMap with Absent values must filter those pairs out.

        CRS Issue 1: {'k': Absent()} previously emitted `k::` (invalid).
        Required: Pairs with Absent values are filtered out.
        """
        inline_map = InlineMap(pairs={"present": "value", "absent_key": Absent()})
        result = emit_value(inline_map)
        assert result == "[present::value]"
        assert "absent_key" not in result

    def test_emit_meta_empty_when_all_absent(self):
        """emit_meta() must return '' when all fields are Absent.

        CRS Issue 2: emit_meta() emitted header even if all fields skipped.
        Required: Return "" when all meta fields are absent.
        """
        meta = {"TYPE": Absent(), "VERSION": Absent()}
        result = emit_meta(meta)
        assert result == ""

    def test_emit_meta_filters_absent_preserves_values(self):
        """emit_meta() filters Absent but preserves present values."""
        meta = {"TYPE": "TEST", "VERSION": Absent(), "STATUS": "ACTIVE"}
        result = emit_meta(meta)
        assert "TYPE::TEST" in result
        assert "STATUS::ACTIVE" in result
        assert "VERSION" not in result

    def test_absent_singleton_pattern(self):
        """Absent() must return singleton instance.

        CRS Issue 3: Missing test for singleton behavior.
        """
        assert Absent() is Absent()
        a1 = Absent()
        a2 = Absent()
        assert a1 is a2


class TestEmitterEdgeCases:
    """Test edge cases in emitter for coverage."""

    def test_emit_empty_string_value(self):
        """Empty string needs quotes to be valid."""
        doc = Document(name="TEST", sections=[Assignment(key="EMPTY", value="")])
        result = emit(doc)
        assert 'EMPTY::""' in result

    def test_emit_boolean_values(self):
        """Boolean values emit as true/false."""
        doc = Document(
            name="TEST",
            sections=[
                Assignment(key="TRUE_VAL", value=True),
                Assignment(key="FALSE_VAL", value=False),
            ],
        )
        result = emit(doc)
        assert "TRUE_VAL::true" in result
        assert "FALSE_VAL::false" in result

    def test_emit_null_value(self):
        """None emits as null."""
        doc = Document(name="TEST", sections=[Assignment(key="NULL_VAL", value=None)])
        result = emit(doc)
        assert "NULL_VAL::null" in result

    def test_emit_numeric_values(self):
        """Numeric values emit directly."""
        doc = Document(
            name="TEST",
            sections=[
                Assignment(key="INT_VAL", value=42),
                Assignment(key="FLOAT_VAL", value=3.14),
            ],
        )
        result = emit(doc)
        assert "INT_VAL::42" in result
        assert "FLOAT_VAL::3.14" in result

    def test_emit_unknown_type_fallback(self):
        """Unknown types fall back to str()."""

        class CustomType:
            def __str__(self):
                return "CUSTOM_VALUE"

        doc = Document(name="TEST", sections=[Assignment(key="CUSTOM", value=CustomType())])
        result = emit(doc)
        assert "CUSTOM::CUSTOM_VALUE" in result

    def test_emit_reserved_words_quoted(self):
        """Reserved words (true, false, null, vs) need quotes."""
        doc = Document(
            name="TEST",
            sections=[
                Assignment(key="VAL1", value="true"),
                Assignment(key="VAL2", value="false"),
                Assignment(key="VAL3", value="null"),
                Assignment(key="VAL4", value="vs"),
            ],
        )
        result = emit(doc)
        assert 'VAL1::"true"' in result
        assert 'VAL2::"false"' in result
        assert 'VAL3::"null"' in result
        assert 'VAL4::"vs"' in result

    def test_emit_string_with_special_chars(self):
        """Strings with special chars need escaping."""
        doc = Document(
            name="TEST",
            sections=[
                Assignment(key="NEWLINE", value="line1\nline2"),
                Assignment(key="TAB", value="col1\tcol2"),
                Assignment(key="QUOTE", value='say "hello"'),
            ],
        )
        result = emit(doc)
        assert "\\n" in result
        assert "\\t" in result
        assert '\\"' in result

    def test_emit_inline_map(self):
        """InlineMap emits as [key::val]."""
        inline_map = InlineMap(pairs={"key": "value"})
        doc = Document(name="TEST", sections=[Assignment(key="MAP", value=inline_map)])
        result = emit(doc)
        assert "MAP::[key::value]" in result

    def test_emit_absent_in_document_sections(self):
        """Absent values in document sections are skipped."""
        doc = Document(
            name="TEST",
            sections=[
                Assignment(key="PRESENT", value="here"),
                Assignment(key="ABSENT", value=Absent()),
            ],
        )
        result = emit(doc)
        assert "PRESENT::here" in result
        assert "ABSENT" not in result

    def test_emit_absent_in_block_children(self):
        """Absent values in Block children are skipped."""
        doc = Document(
            name="TEST",
            sections=[
                Block(
                    key="BLOCK",
                    children=[
                        Assignment(key="PRESENT", value="here"),
                        Assignment(key="ABSENT", value=Absent()),
                    ],
                )
            ],
        )
        result = emit(doc)
        assert "PRESENT::here" in result
        assert "ABSENT" not in result
