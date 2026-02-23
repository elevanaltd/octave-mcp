"""Tests for GH#269: Annotated identifiers must NOT be coalesced into a single string.

When the parser encounters:
    GATES::NEVER<CONSTITUTIONAL_BYPASS> ALWAYS<SYSTEM_COHERENCE>

It should produce two separate values (ListValue), NOT one coalesced string.
This preserves I1::SYNTACTIC_FIDELITY — normalization must not alter semantics.
"""

from octave_mcp.core.ast_nodes import Assignment, Block, ListValue
from octave_mcp.core.parser import parse, parse_with_warnings


class TestAnnotatedIdentifierCoalescing:
    """GH#269: Annotated identifiers should not be coalesced."""

    def test_two_annotated_identifiers_not_coalesced(self):
        """NEVER<X> ALWAYS<Y> should parse as two separate values, not one string."""
        content = """===TEST===
GATES::NEVER<CONSTITUTIONAL_BYPASS> ALWAYS<SYSTEM_COHERENCE>
===END==="""
        doc = parse(content)
        assignment = doc.sections[0]
        assert isinstance(assignment, Assignment)
        assert assignment.key == "GATES"
        # Must be a list of two separate values, NOT a single coalesced string
        assert isinstance(assignment.value, ListValue), (
            f"Expected ListValue with two items, got {type(assignment.value).__name__}: " f"{assignment.value!r}"
        )
        assert len(assignment.value.items) == 2
        assert assignment.value.items[0] == "NEVER<CONSTITUTIONAL_BYPASS>"
        assert assignment.value.items[1] == "ALWAYS<SYSTEM_COHERENCE>"

    def test_three_annotated_identifiers_not_coalesced(self):
        """Multiple annotated identifiers should all remain separate."""
        content = """===TEST===
GATES::NEVER<X> ALWAYS<Y> SOMETIMES<Z>
===END==="""
        doc = parse(content)
        assignment = doc.sections[0]
        assert isinstance(assignment, Assignment)
        assert isinstance(assignment.value, ListValue), (
            f"Expected ListValue, got {type(assignment.value).__name__}: " f"{assignment.value!r}"
        )
        assert len(assignment.value.items) == 3
        assert assignment.value.items[0] == "NEVER<X>"
        assert assignment.value.items[1] == "ALWAYS<Y>"
        assert assignment.value.items[2] == "SOMETIMES<Z>"

    def test_single_annotated_identifier_stays_scalar(self):
        """A single annotated identifier should remain a plain string value."""
        content = """===TEST===
ARCHETYPE::ATHENA<strategic_wisdom>
===END==="""
        doc = parse(content)
        assignment = doc.sections[0]
        assert isinstance(assignment, Assignment)
        assert assignment.value == "ATHENA<strategic_wisdom>"

    def test_annotated_mixed_with_bare_words_splits(self):
        """Annotated identifier followed by bare word should not coalesce."""
        content = """===TEST===
GATES::NEVER<BYPASS> some_text
===END==="""
        doc = parse(content)
        assignment = doc.sections[0]
        assert isinstance(assignment, Assignment)
        # When annotated identifier is present, should not coalesce with bare words
        assert isinstance(assignment.value, ListValue), (
            f"Expected ListValue, got {type(assignment.value).__name__}: " f"{assignment.value!r}"
        )
        assert assignment.value.items[0] == "NEVER<BYPASS>"

    def test_bare_word_followed_by_annotated_splits(self):
        """Bare word followed by annotated identifier should not coalesce."""
        content = """===TEST===
GATES::some_text ALWAYS<COHERENCE>
===END==="""
        doc = parse(content)
        assignment = doc.sections[0]
        assert isinstance(assignment, Assignment)
        assert isinstance(assignment.value, ListValue), (
            f"Expected ListValue, got {type(assignment.value).__name__}: " f"{assignment.value!r}"
        )

    def test_plain_bare_words_still_coalesce(self):
        """Regular bare words without annotations should still coalesce into a string."""
        content = """===TEST===
STATUS::some bare text here
===END==="""
        doc = parse(content)
        assignment = doc.sections[0]
        assert isinstance(assignment, Assignment)
        # Plain words should still coalesce into a single string
        assert assignment.value == "some bare text here"

    def test_no_coalesce_warning_for_annotated_split(self):
        """Splitting annotated identifiers should not emit coalesce warnings."""
        content = """===TEST===
GATES::NEVER<X> ALWAYS<Y>
===END==="""
        doc, warnings = parse_with_warnings(content)
        coalesce_warnings = [w for w in warnings if w.get("subtype") == "multi_word_coalesce"]
        assert len(coalesce_warnings) == 0, (
            f"Should not emit coalesce warnings for annotated identifier split, " f"got: {coalesce_warnings}"
        )

    def test_round_trip_annotated_identifiers(self):
        """Annotated identifiers should round-trip through parse -> emit."""
        from octave_mcp.core.emitter import emit

        content = """===TEST===
GATES::NEVER<CONSTITUTIONAL_BYPASS> ALWAYS<SYSTEM_COHERENCE>
===END==="""
        doc = parse(content)
        output = emit(doc)
        # Both values should appear in the output
        assert "NEVER<CONSTITUTIONAL_BYPASS>" in output
        assert "ALWAYS<SYSTEM_COHERENCE>" in output

    def test_annotated_in_nested_block(self):
        """Annotated identifiers should not coalesce inside nested blocks."""
        content = """===TEST===
VERIFICATION:
  GATES::NEVER<UNTESTED_CODE> ALWAYS<DESIGN_INTEGRITY>
===END==="""
        doc = parse(content)
        block = doc.sections[0]
        assert isinstance(block, Block)
        child = block.children[0]
        assert isinstance(child, Assignment)
        assert child.key == "GATES"
        assert isinstance(child.value, ListValue), (
            f"Expected ListValue, got {type(child.value).__name__}: " f"{child.value!r}"
        )
        assert len(child.value.items) == 2
