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
from octave_mcp.core.parser import parse, parse_with_warnings


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


class TestConstructorAdjacencyCheck:
    """GH#276 rework: NAME [args] (with space) must NOT be treated as constructor."""

    def test_constructor_with_space_treated_as_list(self):
        """X::A [B,C] — space before bracket means it's a list, not constructor args.

        GH#276 round 2: The bracket content [B,C] must NOT be silently dropped.
        It should be preserved as list data, not consumed and discarded.
        """
        content = "===TEST===\nX::A [B,C]\n===END==="
        doc = parse(content)
        output = emit(doc)
        # With a space, [B,C] is a separate list, NOT constructor args on A.
        # A should NOT become A<B,C>
        assert "A<B" not in output, f"Space before bracket was incorrectly treated as constructor. Output:\n{output}"
        # GH#276 round 2: The bracket content MUST NOT be silently dropped
        assert "B" in output, f"Spaced bracket content [B,C] was silently dropped! Output:\n{output}"
        assert "C" in output, f"Spaced bracket content [B,C] was silently dropped! Output:\n{output}"


class TestConstructorNonIdentifierArgs:
    """GH#276 rework: Non-IDENTIFIER token types must be preserved in constructor args."""

    def test_constructor_numeric_arg_preserved(self):
        """X::FOO[1] must preserve numeric argument."""
        content = "===TEST===\nX::FOO[1]\n===END==="
        doc = parse(content)
        output = emit(doc)
        assert "1" in output, f"Numeric constructor arg dropped. Output:\n{output}"
        # Should be FOO<1> in canonical form
        assert "FOO" in output, f"FOO missing. Output:\n{output}"

    def test_constructor_boolean_arg_preserved(self):
        """X::FOO[true] must preserve boolean argument."""
        content = "===TEST===\nX::FOO[true]\n===END==="
        doc = parse(content)
        output = emit(doc)
        assert "true" in output, f"Boolean constructor arg dropped. Output:\n{output}"

    def test_constructor_null_arg_preserved(self):
        """X::FOO[null] must preserve null argument."""
        content = "===TEST===\nX::FOO[null]\n===END==="
        doc = parse(content)
        output = emit(doc)
        assert "null" in output, f"Null constructor arg dropped. Output:\n{output}"

    def test_constructor_flow_arrow_arg_preserved(self):
        """X::FOO[BAR->BAZ] must preserve flow arrow argument."""
        content = "===TEST===\nX::FOO[BAR->BAZ]\n===END==="
        doc = parse(content)
        output = emit(doc)
        # The flow arrow -> normalizes to the unicode arrow
        assert "BAR" in output, f"BAR lost in flow arrow constructor arg. Output:\n{output}"
        assert "BAZ" in output, f"BAZ lost in flow arrow constructor arg. Output:\n{output}"

    def test_constructor_mixed_args(self):
        """X::FOO[BAR,1,true] must preserve all mixed argument types."""
        content = "===TEST===\nX::FOO[BAR,1,true]\n===END==="
        doc = parse(content)
        output = emit(doc)
        assert "BAR" in output, f"IDENTIFIER arg dropped in mixed. Output:\n{output}"
        assert "1" in output, f"NUMBER arg dropped in mixed. Output:\n{output}"
        assert "true" in output, f"BOOLEAN arg dropped in mixed. Output:\n{output}"


class TestConstructorMissingTokenTypes:
    """GH#276 round 2: Token types missing from _consume_bracket_annotation whitelist."""

    def test_constructor_version_arg(self):
        """FOO[1.2.3] must preserve VERSION token argument."""
        content = "===TEST===\nX::FOO[1.2.3]\n===END==="
        doc = parse(content)
        output = emit(doc)
        assert "1.2.3" in output, f"VERSION constructor arg dropped. Output:\n{output}"
        assert "FOO" in output, f"FOO missing. Output:\n{output}"

    def test_constructor_variable_arg(self):
        """FOO[$VAR] must preserve VARIABLE token argument."""
        content = "===TEST===\nX::FOO[$VAR]\n===END==="
        doc = parse(content)
        output = emit(doc)
        assert "$VAR" in output, f"VARIABLE constructor arg dropped. Output:\n{output}"
        assert "FOO" in output, f"FOO missing. Output:\n{output}"

    def test_constructor_operator_args(self):
        """FOO[A+B] must preserve SYNTHESIS/operator token."""
        content = "===TEST===\nX::FOO[A+B]\n===END==="
        doc = parse(content)
        output = emit(doc)
        # The + normalizes to the unicode ⊕ operator
        assert "A" in output, f"A lost in operator constructor arg. Output:\n{output}"
        assert "B" in output, f"B lost in operator constructor arg. Output:\n{output}"
        # The operator itself must be preserved (either + or its normalized form)
        has_operator = "+" in output or "\u2295" in output
        assert has_operator, f"Operator dropped from FOO[A+B]. Output:\n{output}"

    def test_constructor_at_arg(self):
        """FOO[A@B] must preserve AT token."""
        content = "===TEST===\nX::FOO[A@B]\n===END==="
        doc = parse(content)
        output = emit(doc)
        assert "A" in output, f"A lost in AT constructor arg. Output:\n{output}"
        assert "B" in output, f"B lost in AT constructor arg. Output:\n{output}"
        assert "@" in output, f"AT operator dropped from FOO[A@B]. Output:\n{output}"


class TestConstructorEmptyBrackets:
    """GH#276 rework: Empty brackets FOO[] must not be silently dropped."""

    def test_constructor_empty_brackets(self):
        """X::FOO[] should preserve empty brackets (not silently drop)."""
        content = "===TEST===\nX::FOO[]\n===END==="
        doc = parse(content)
        output = emit(doc)
        # FOO[] should emit as FOO<> (empty annotation preserved) not just FOO
        assert "FOO<>" in output, f"Empty brackets silently dropped — expected FOO<>. Output:\n{output}"


class TestConstructorCommentNewlineFiltering:
    """GH#276 round 3: COMMENT, NEWLINE, INDENT tokens must be filtered from constructor brackets."""

    def test_constructor_with_inline_comment(self):
        """FOO[BAR, //comment\\nBAZ] must strip comment, preserve args."""
        content = "===TEST===\nX::FOO[BAR, //comment\nBAZ]\n===END==="
        doc = parse(content)
        output = emit(doc)
        assert "BAR" in output, f"BAR arg dropped. Output:\n{output}"
        assert "BAZ" in output, f"BAZ arg dropped. Output:\n{output}"
        assert "comment" not in output, f"Comment text leaked into constructor data. Output:\n{output}"

    def test_constructor_multiline(self):
        """FOO[BAR,\\nBAZ] must strip newline, preserve args."""
        content = "===TEST===\nX::FOO[BAR,\nBAZ]\n===END==="
        doc = parse(content)
        output = emit(doc)
        assert "BAR" in output, f"BAR arg dropped. Output:\n{output}"
        assert "BAZ" in output, f"BAZ arg dropped. Output:\n{output}"
        # GH#276 round 4: Verify the annotation line itself has no embedded newline
        annotation_line = [line for line in output.splitlines() if "FOO<" in line][0]
        assert "\n" not in annotation_line, f"Newline inside the annotation on a single line. Line:\n{annotation_line}"

    def test_constructor_comment_only_between_args(self):
        """FOO[A, //note\\nB, //note\\nC] must strip all comments, preserve all args."""
        content = "===TEST===\nX::FOO[A, //note\nB, //note\nC]\n===END==="
        doc = parse(content)
        output = emit(doc)
        assert "A" in output, f"A arg dropped. Output:\n{output}"
        assert "B" in output, f"B arg dropped. Output:\n{output}"
        assert "C" in output, f"C arg dropped. Output:\n{output}"
        assert "note" not in output, f"Comment text leaked into constructor data. Output:\n{output}"

    def test_constructor_with_indent_inside(self):
        """INDENT tokens inside constructor brackets should be filtered.

        GH#276 round 4: When constructor args span lines with indentation,
        the lexer generates INDENT tokens inside the brackets. These must be
        filtered (not become part of the constructor payload), just like
        COMMENT and NEWLINE tokens.

        Token stream for FOO[BAR,\\n    BAZ]:
        IDENTIFIER('FOO'), LIST_START, IDENTIFIER('BAR'), COMMA,
        NEWLINE, INDENT(4), IDENTIFIER('BAZ'), LIST_END
        """
        content = "===T===\nX::FOO[BAR,\n    BAZ]\n===END==="
        doc, warnings = parse_with_warnings(content)
        output = emit(doc)
        # Verify BAR and BAZ are preserved, no indent leakage
        assert "BAR" in output, f"BAR arg dropped. Output:\n{output}"
        assert "BAZ" in output, f"BAZ arg dropped. Output:\n{output}"
        # The constructor annotation should be clean — no INDENT value leaking in
        annotation_line = [line for line in output.splitlines() if "FOO<" in line][0]
        assert "\n" not in annotation_line, f"Newline inside annotation. Line:\n{annotation_line}"


class TestExpressionPathConstructor:
    """GH#276 round 4: Constructor brackets in expression-path (parse_flow_expression)."""

    def test_expression_constructor_boolean_arg(self):
        """CONST[true] in expression must preserve boolean argument.

        parse_flow_expression has its own bracket reconstruction logic that
        must handle all token types, not just IDENTIFIER/STRING/NUMBER.
        """
        content = "===TEST===\nX::CONST[true]\u2227REQ\n===END==="
        doc = parse(content)
        output = emit(doc)
        assert "true" in output, f"Boolean arg dropped in expression constructor. Output:\n{output}"
        assert "CONST" in output, f"CONST missing. Output:\n{output}"
        assert "REQ" in output, f"REQ missing. Output:\n{output}"

    def test_expression_constructor_variable_arg(self):
        """CONST[$VAR] in expression must preserve variable argument."""
        content = "===TEST===\nX::CONST[$VAR]\u2227REQ\n===END==="
        doc = parse(content)
        output = emit(doc)
        assert "$VAR" in output, f"Variable arg dropped in expression constructor. Output:\n{output}"
        assert "CONST" in output, f"CONST missing. Output:\n{output}"
        assert "REQ" in output, f"REQ missing. Output:\n{output}"

    def test_expression_constructor_version_arg(self):
        """CONST[1.2.3] in expression must preserve version argument."""
        content = "===TEST===\nX::CONST[1.2.3]\u2227REQ\n===END==="
        doc = parse(content)
        output = emit(doc)
        assert "1.2.3" in output, f"Version arg dropped in expression constructor. Output:\n{output}"
        assert "CONST" in output, f"CONST missing. Output:\n{output}"
        assert "REQ" in output, f"REQ missing. Output:\n{output}"
