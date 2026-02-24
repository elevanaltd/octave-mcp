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


class TestAnnotatedIdentifierCoalescingRework:
    """GH#269 rework: Unified accumulator fixes from CRS+CE review.

    These tests target the inconsistencies identified by both reviewers:
    1. Bare words AFTER annotated identifiers must coalesce with each other
    2. Expression operators must still work when preceded by annotated tokens
    3. Behavior must be order-independent
    """

    def test_bare_words_after_annotated_coalesce_together(self):
        """A<X> followed by multiple bare words should coalesce the bare words.

        CRS/CE finding: A<X> more bare words produced ['A<X>', 'more', 'bare', 'words']
        Expected: ['A<X>', 'more bare words']
        """
        content = """===TEST===
GATES::A<X> more bare words
===END==="""
        doc = parse(content)
        assignment = doc.sections[0]
        assert isinstance(assignment, Assignment)
        assert isinstance(assignment.value, ListValue), (
            f"Expected ListValue, got {type(assignment.value).__name__}: " f"{assignment.value!r}"
        )
        assert len(assignment.value.items) == 2, (
            f"Expected 2 items ['A<X>', 'more bare words'], " f"got {assignment.value.items!r}"
        )
        assert assignment.value.items[0] == "A<X>"
        assert assignment.value.items[1] == "more bare words"

    def test_bare_words_around_annotated_coalesce(self):
        """Bare words on both sides of an annotated token should each coalesce.

        CRS/CE finding: Order-dependent behavior.
        Expected: ['some text', 'A<X>', 'more text']
        """
        content = """===TEST===
GATES::some text A<X> more text
===END==="""
        doc = parse(content)
        assignment = doc.sections[0]
        assert isinstance(assignment, Assignment)
        assert isinstance(assignment.value, ListValue), (
            f"Expected ListValue, got {type(assignment.value).__name__}: " f"{assignment.value!r}"
        )
        assert len(assignment.value.items) == 3, (
            f"Expected 3 items ['some text', 'A<X>', 'more text'], " f"got {assignment.value.items!r}"
        )
        assert assignment.value.items[0] == "some text"
        assert assignment.value.items[1] == "A<X>"
        assert assignment.value.items[2] == "more text"

    def test_multiple_annotated_with_trailing_bare_word(self):
        """Multiple annotated tokens followed by bare words.

        Expected: ['A<X>', 'B<Y>', 'bare word']
        """
        content = """===TEST===
GATES::A<X> B<Y> bare word
===END==="""
        doc = parse(content)
        assignment = doc.sections[0]
        assert isinstance(assignment, Assignment)
        assert isinstance(assignment.value, ListValue), (
            f"Expected ListValue, got {type(assignment.value).__name__}: " f"{assignment.value!r}"
        )
        assert len(assignment.value.items) == 3, (
            f"Expected 3 items ['A<X>', 'B<Y>', 'bare word'], " f"got {assignment.value.items!r}"
        )
        assert assignment.value.items[0] == "A<X>"
        assert assignment.value.items[1] == "B<Y>"
        assert assignment.value.items[2] == "bare word"

    def test_annotated_with_expression_operator(self):
        """Annotated token followed by expression operator must not drop tokens.

        CRS/CE finding: Early return for annotated-first skips operator checks.
        A<X> WORD->NEXT should produce expression output, not drop tokens.
        """
        content = """===TEST===
EXPR::A<X> WORD->NEXT
===END==="""
        doc = parse(content)
        assignment = doc.sections[0]
        assert isinstance(assignment, Assignment)
        # The expression operator should be handled, not dropped.
        # The value must contain all tokens - A<X>, WORD, ->, NEXT
        val = assignment.value
        if isinstance(val, ListValue):
            # If returned as list, all items must be present
            combined = " ".join(str(item) for item in val.items)
            assert "A<X>" in combined, f"A<X> missing from {val.items!r}"
            assert "WORD" in combined, f"WORD missing from {val.items!r}"
            assert "NEXT" in combined, f"NEXT missing from {val.items!r}"
        else:
            # If returned as expression string, all parts must be present
            val_str = str(val)
            assert "A<X>" in val_str, f"A<X> missing from {val_str!r}"
            assert "WORD" in val_str, f"WORD missing from {val_str!r}"
            assert "NEXT" in val_str, f"NEXT missing from {val_str!r}"

    def test_order_independence_annotated_first_vs_last(self):
        """Behavior should be consistent regardless of annotated token position.

        CRS/CE finding: A<X> B C -> 3 items, but A B C<X> -> 2 items.
        Both should produce a ListValue with annotated token separate from bare words.
        """
        # Case 1: Annotated first
        content1 = """===TEST===
GATES::A<X> B C
===END==="""
        doc1 = parse(content1)
        a1 = doc1.sections[0]
        assert isinstance(a1, Assignment)
        assert isinstance(a1.value, ListValue), (
            f"Annotated-first: Expected ListValue, got " f"{type(a1.value).__name__}: {a1.value!r}"
        )
        assert len(a1.value.items) == 2, f"Annotated-first: Expected ['A<X>', 'B C'], " f"got {a1.value.items!r}"
        assert a1.value.items[0] == "A<X>"
        assert a1.value.items[1] == "B C"

        # Case 2: Annotated last
        content2 = """===TEST===
GATES::A B C<X>
===END==="""
        doc2 = parse(content2)
        a2 = doc2.sections[0]
        assert isinstance(a2, Assignment)
        assert isinstance(a2.value, ListValue), (
            f"Annotated-last: Expected ListValue, got " f"{type(a2.value).__name__}: {a2.value!r}"
        )
        assert len(a2.value.items) == 2, f"Annotated-last: Expected ['A B', 'C<X>'], " f"got {a2.value.items!r}"
        assert a2.value.items[0] == "A B"
        assert a2.value.items[1] == "C<X>"
