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
from octave_mcp.core.emitter import FormatOptions, emit, emit_meta, emit_value
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


class TestFrontmatterPreservation:
    """Test Zone 2 (Preserving Container) - YAML frontmatter round-trip.

    Issue #234: The emitter must preserve raw_frontmatter when present
    on the Document AST. This ensures Zone 2 container data survives
    parse -> emit round-trips without loss (I1: syntactic fidelity).
    """

    def test_emit_preserves_frontmatter(self):
        """emit() should prepend raw_frontmatter when present on Document."""
        doc = Document(
            name="TEST_SKILL",
            sections=[Assignment(key="PURPOSE", value="Test skill")],
            raw_frontmatter="name: test-skill\ndescription: A test skill",
        )
        result = emit(doc)
        assert result.startswith("---\n")
        assert "name: test-skill" in result
        assert "description: A test skill" in result
        # Frontmatter must be closed before envelope
        fm_end = result.index("---\n", 3)  # Find second ---
        envelope_start = result.index("===TEST_SKILL===")
        assert fm_end < envelope_start

    def test_emit_no_frontmatter_when_none(self):
        """emit() should NOT add frontmatter when raw_frontmatter is None."""
        doc = Document(
            name="TEST",
            sections=[Assignment(key="KEY", value="val")],
        )
        result = emit(doc)
        assert not result.startswith("---")
        assert result.startswith("===TEST===")

    def test_roundtrip_frontmatter_preserved(self):
        """Parse a document with frontmatter, emit it, frontmatter preserved."""
        original = (
            "---\n"
            "name: test-skill\n"
            "description: A test skill for frontmatter preservation\n"
            'allowed-tools: ["Read", "Write", "Edit"]\n'
            'version: "1.0.0"\n'
            "---\n"
            "\n"
            "===TEST_SKILL===\n"
            "META:\n"
            "  TYPE::SKILL\n"
            '  VERSION::"1.0.0"\n'
            "  STATUS::ACTIVE\n"
            "\n"
            "\u00a71::CORE\n"
            'PURPOSE::"Test skill"\n'
            "\n"
            "===END==="
        )
        doc = parse(original)
        assert doc.raw_frontmatter is not None
        emitted = emit(doc)
        # The emitted output must contain the frontmatter
        assert emitted.startswith("---\n")
        assert "name: test-skill" in emitted
        assert 'allowed-tools: ["Read", "Write", "Edit"]' in emitted
        assert 'version: "1.0.0"' in emitted
        # Re-parse to verify round-trip
        doc2 = parse(emitted)
        assert doc2.raw_frontmatter == doc.raw_frontmatter

    def test_roundtrip_no_frontmatter_unchanged(self):
        """Parse a pure OCTAVE file (no frontmatter) -> emit -> no frontmatter added."""
        original = (
            "===PURE_DOC===\n" "META:\n" "  TYPE::TEST\n" "\n" "\u00a71::SECTION\n" "KEY::value\n" "\n" "===END==="
        )
        doc = parse(original)
        assert doc.raw_frontmatter is None
        emitted = emit(doc)
        assert not emitted.startswith("---")
        assert emitted.startswith("===PURE_DOC===")

    def test_frontmatter_byte_for_byte_preserved(self):
        """Frontmatter content must be byte-for-byte preserved (no normalization)."""
        # Include special characters, tabs, unusual spacing
        raw_fm = 'name: test-skill\n  nested: "value with :: colons"\ntags: [a, b, c]'
        doc = Document(
            name="TEST",
            sections=[Assignment(key="KEY", value="val")],
            raw_frontmatter=raw_fm,
        )
        result = emit(doc)
        # Extract frontmatter from result
        lines = result.split("\n")
        assert lines[0] == "---"
        # Find closing ---
        close_idx = None
        for i in range(1, len(lines)):
            if lines[i] == "---":
                close_idx = i
                break
        assert close_idx is not None
        extracted_fm = "\n".join(lines[1:close_idx])
        assert extracted_fm == raw_fm

    def test_frontmatter_separator_no_conflict_with_doc_separator(self):
        """Frontmatter --- markers must not conflict with doc.has_separator."""
        doc = Document(
            name="TEST",
            sections=[Assignment(key="KEY", value="val")],
            raw_frontmatter="name: test",
            has_separator=True,
        )
        result = emit(doc)
        # Should have frontmatter --- pair AND document ---
        parts = result.split("---")
        # parts[0] is empty (before first ---), parts[1] is frontmatter,
        # parts[2] contains envelope + separator section onward
        assert len(parts) >= 3, f"Expected at least 3 parts split by ---, got {len(parts)}"

    def test_empty_string_frontmatter_treated_as_absent(self):
        """raw_frontmatter="" should NOT emit empty ---\\n\\n--- block."""
        doc = Document(
            name="TEST",
            sections=[Assignment(key="KEY", value="val")],
            raw_frontmatter="",
        )
        result = emit(doc)
        assert not result.startswith("---")
        assert result.startswith("===TEST===")

    def test_whitespace_only_frontmatter_treated_as_absent(self):
        """raw_frontmatter with only whitespace should NOT emit."""
        doc = Document(
            name="TEST",
            sections=[Assignment(key="KEY", value="val")],
            raw_frontmatter="   \n  \n  ",
        )
        result = emit(doc)
        assert not result.startswith("---")
        assert result.startswith("===TEST===")

    def test_frontmatter_survives_trailing_whitespace_strip(self):
        """Frontmatter content survives format_options trailing_whitespace='strip'."""
        doc = Document(
            name="TEST",
            sections=[Assignment(key="KEY", value="val")],
            raw_frontmatter="name: test-skill\ndescription: A skill",
        )
        opts = FormatOptions(trailing_whitespace="strip")
        result = emit(doc, format_options=opts)
        assert result.startswith("---\n")
        assert "name: test-skill" in result
        assert "description: A skill" in result
