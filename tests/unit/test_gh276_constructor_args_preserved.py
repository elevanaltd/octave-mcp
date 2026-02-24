"""Tests for GH#276: Constructor NAME[args] arguments must be preserved.

Constructor syntax per OCTAVE spec section 1b: NAME immediately followed by [args]
(no space) represents a constructor, NOT a list. The arguments must be preserved
through parse-emit round-trip as NAME<args> (canonical annotation form).

Regression evidence:
    CONTRACT::HOLOGRAPHIC[JIT_GRAMMAR_COMPILATION]
    Expected: CONTRACT::HOLOGRAPHIC<JIT_GRAMMAR_COMPILATION>
    Actual:   CONTRACT::HOLOGRAPHIC  (args DROPPED)

    GATES::NEVER[CONSTITUTIONAL_BYPASS] ALWAYS[SYSTEM_COHERENCE]
    Expected: GATES::[NEVER<CONSTITUTIONAL_BYPASS>,ALWAYS<SYSTEM_COHERENCE>]
    Actual:   GATES::NEVER  (both args AND second token DROPPED)

Root cause: _consume_bracket_annotation(capture=False) silently consumes and
discards constructor arguments after identifiers in parse_value().
"""

from octave_mcp.core.emitter import emit
from octave_mcp.core.parser import parse


class TestConstructorArgPreservation:
    """GH#276: Constructor NAME[args] arguments must survive parse-emit round-trip."""

    def test_simple_constructor_at_assignment_level(self):
        """CONTRACT::HOLOGRAPHIC[JIT_GRAMMAR_COMPILATION] must preserve args."""
        content = "===TEST===\nCONTRACT::HOLOGRAPHIC[JIT_GRAMMAR_COMPILATION]\n===END==="
        doc = parse(content)
        assignment = doc.sections[0]
        assert assignment.key == "CONTRACT"
        # Constructor args must be preserved as NAME<args> canonical form
        assert "JIT_GRAMMAR_COMPILATION" in str(
            assignment.value
        ), f"Constructor args dropped: value={assignment.value!r}"

    def test_constructor_emits_angle_bracket_form(self):
        """Constructor NAME[args] normalizes to NAME<args> in emission."""
        content = "===TEST===\nCONTRACT::HOLOGRAPHIC[JIT_GRAMMAR_COMPILATION]\n===END==="
        doc = parse(content)
        output = emit(doc)
        assert "HOLOGRAPHIC" in output
        # The canonical form uses angle brackets, not square brackets
        assert "JIT_GRAMMAR_COMPILATION" in output, f"Constructor args lost in round-trip. Output:\n{output}"

    def test_constructor_round_trip(self):
        """Full round-trip: parse -> emit preserves constructor arguments."""
        content = "===TEST===\nCONTRACT::HOLOGRAPHIC[JIT_GRAMMAR_COMPILATION]\n===END==="
        doc = parse(content)
        output = emit(doc)
        # Re-parse the emitted output
        doc2 = parse(output)
        assignment2 = doc2.sections[0]
        assert "JIT_GRAMMAR_COMPILATION" in str(
            assignment2.value
        ), f"Constructor args lost after round-trip: value={assignment2.value!r}"

    def test_multiple_constructors_space_separated(self):
        """GATES::NEVER[CONSTITUTIONAL_BYPASS] ALWAYS[SYSTEM_COHERENCE] must preserve both."""
        content = "===TEST===\nGATES::NEVER[CONSTITUTIONAL_BYPASS] ALWAYS[SYSTEM_COHERENCE]\n===END==="
        doc = parse(content)
        assignment = doc.sections[0]
        value_str = str(assignment.value)
        assert "NEVER" in value_str, f"NEVER missing from value: {value_str}"
        assert "CONSTITUTIONAL_BYPASS" in value_str, f"CONSTITUTIONAL_BYPASS args dropped: {value_str}"
        assert "ALWAYS" in value_str, f"ALWAYS missing from value: {value_str}"
        assert "SYSTEM_COHERENCE" in value_str, f"SYSTEM_COHERENCE args dropped: {value_str}"

    def test_multiple_constructors_round_trip(self):
        """Space-separated constructors must survive round-trip."""
        content = "===TEST===\nGATES::NEVER[CONSTITUTIONAL_BYPASS] ALWAYS[SYSTEM_COHERENCE]\n===END==="
        doc = parse(content)
        output = emit(doc)
        assert "CONSTITUTIONAL_BYPASS" in output, f"Constructor args lost in round-trip. Output:\n{output}"
        assert "SYSTEM_COHERENCE" in output, f"Constructor args lost in round-trip. Output:\n{output}"

    def test_constructor_inside_list(self):
        """Constructors inside list brackets must also preserve args."""
        content = "===TEST===\nITEMS::[NEVER[X], ALWAYS[Y]]\n===END==="
        doc = parse(content)
        output = emit(doc)
        assert "X" in output, f"Constructor arg X dropped inside list. Output:\n{output}"
        assert "Y" in output, f"Constructor arg Y dropped inside list. Output:\n{output}"

    def test_constructor_does_not_break_comment_stripping(self):
        """GH#272 regression guard: comments in arrays must still be stripped.

        This test ensures the constructor fix does not re-introduce the
        comment-as-data bug from GH#272.
        """
        content = "SKILLS::[\n    ho-mode,  // Critical lane discipline\n    ho-orchestrate,  // Essential for orchestration\n]"
        doc = parse(content)
        assignment = doc.sections[0]
        items = assignment.value.items
        assert items == ["ho-mode", "ho-orchestrate"], f"Comment text leaked into array data: {items}"


class TestConstructorInNestedContext:
    """Constructor syntax in various nesting scenarios."""

    def test_constructor_in_nested_block(self):
        """Constructor inside a block child assignment."""
        content = "===TEST===\nMETA:\n  CONTRACT::HOLOGRAPHIC[JIT_GRAMMAR_COMPILATION]\n===END==="
        doc = parse(content)
        output = emit(doc)
        assert "JIT_GRAMMAR_COMPILATION" in output, f"Constructor args dropped in block context. Output:\n{output}"

    def test_constructor_in_inline_map_value(self):
        """Constructor as value in inline map inside list."""
        content = "===TEST===\nDATA::[MODE::STRICT[ENFORCE]]\n===END==="
        doc = parse(content)
        output = emit(doc)
        assert "ENFORCE" in output, f"Constructor args dropped in inline map context. Output:\n{output}"
