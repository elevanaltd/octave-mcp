"""Tests for NEVER rule spec compliance warnings (Issue #184).

These tests verify detection of patterns forbidden by octave-core-spec.oct.md §6::NEVER.
Each rule emits a warning (not error) per I4 auditability, with guidance for correction.

Reference: src/octave_mcp/resources/specs/octave-core-spec.oct.md §6::NEVER
"""

from octave_mcp.core.parser import parse_with_warnings


class TestWrongCaseWarning:
    """W_WRONG_CASE: Detect True, False, NULL (wrong case).

    Spec: BOOLEAN::true|false[lowercase_only], NULL::null[lowercase_only]
    Expected: W_WRONG_CASE::True should be true
    """

    def test_true_wrong_case_emits_warning(self):
        """True (capitalized) should emit W_WRONG_CASE warning."""
        content = """===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
VALUE::True
===END==="""
        doc, warnings = parse_with_warnings(content)

        # Should have a wrong case warning
        wrong_case_warnings = [
            w for w in warnings if w.get("type") == "spec_violation" and "W_WRONG_CASE" in w.get("message", "")
        ]
        assert len(wrong_case_warnings) >= 1, f"Expected W_WRONG_CASE warning, got: {warnings}"
        assert "True" in wrong_case_warnings[0]["message"]
        assert "true" in wrong_case_warnings[0]["message"]

    def test_false_wrong_case_emits_warning(self):
        """False (capitalized) should emit W_WRONG_CASE warning."""
        content = """===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
VALUE::False
===END==="""
        doc, warnings = parse_with_warnings(content)

        wrong_case_warnings = [
            w for w in warnings if w.get("type") == "spec_violation" and "W_WRONG_CASE" in w.get("message", "")
        ]
        assert len(wrong_case_warnings) >= 1, f"Expected W_WRONG_CASE warning, got: {warnings}"
        assert "False" in wrong_case_warnings[0]["message"]
        assert "false" in wrong_case_warnings[0]["message"]

    def test_null_wrong_case_emits_warning(self):
        """NULL (uppercase) should emit W_WRONG_CASE warning."""
        content = """===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
VALUE::NULL
===END==="""
        doc, warnings = parse_with_warnings(content)

        wrong_case_warnings = [
            w for w in warnings if w.get("type") == "spec_violation" and "W_WRONG_CASE" in w.get("message", "")
        ]
        assert len(wrong_case_warnings) >= 1, f"Expected W_WRONG_CASE warning, got: {warnings}"
        assert "NULL" in wrong_case_warnings[0]["message"]
        assert "null" in wrong_case_warnings[0]["message"]

    def test_null_mixed_case_emits_warning(self):
        """Null (mixed case) should emit W_WRONG_CASE warning."""
        content = """===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
VALUE::Null
===END==="""
        doc, warnings = parse_with_warnings(content)

        wrong_case_warnings = [
            w for w in warnings if w.get("type") == "spec_violation" and "W_WRONG_CASE" in w.get("message", "")
        ]
        assert len(wrong_case_warnings) >= 1, f"Expected W_WRONG_CASE warning, got: {warnings}"

    def test_correct_case_no_warning(self):
        """Correct lowercase true/false/null should not emit warning."""
        content = """===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
A::true
B::false
C::null
===END==="""
        doc, warnings = parse_with_warnings(content)

        wrong_case_warnings = [
            w for w in warnings if w.get("type") == "spec_violation" and "W_WRONG_CASE" in w.get("message", "")
        ]
        assert len(wrong_case_warnings) == 0, f"Should not have W_WRONG_CASE warning: {warnings}"


class TestBareFlowWarning:
    """W_BARE_FLOW: Detect KEY->value at statement level (not in list).

    Spec: bare_flow[KEY->value] is NEVER allowed
    Expected: W_BARE_FLOW::KEY->value should be KEY::[A->B]
    """

    def test_bare_flow_at_statement_level_emits_warning(self):
        """KEY->value at statement level (outside list) should emit W_BARE_FLOW warning."""
        content = """===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
A->B
===END==="""
        doc, warnings = parse_with_warnings(content)

        bare_flow_warnings = [
            w for w in warnings if w.get("type") == "spec_violation" and "W_BARE_FLOW" in w.get("message", "")
        ]
        assert len(bare_flow_warnings) >= 1, f"Expected W_BARE_FLOW warning, got: {warnings}"

    def test_flow_inside_list_no_warning(self):
        """Flow operator inside list [A->B] should NOT emit W_BARE_FLOW warning."""
        content = """===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
WORKFLOW::[A->B->C]
===END==="""
        doc, warnings = parse_with_warnings(content)

        bare_flow_warnings = [
            w for w in warnings if w.get("type") == "spec_violation" and "W_BARE_FLOW" in w.get("message", "")
        ]
        assert len(bare_flow_warnings) == 0, f"Should not have W_BARE_FLOW warning: {warnings}"

    def test_flow_in_assigned_value_emits_warning(self):
        """KEY::A->B (flow as value) should emit W_BARE_FLOW warning."""
        content = """===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
FLOW::A->B
===END==="""
        doc, warnings = parse_with_warnings(content)

        # This should emit warning because A->B is not in brackets
        bare_flow_warnings = [
            w for w in warnings if w.get("type") == "spec_violation" and "W_BARE_FLOW" in w.get("message", "")
        ]
        assert len(bare_flow_warnings) >= 1, f"Expected W_BARE_FLOW warning, got: {warnings}"


class TestConstraintOutsideBracketsWarning:
    """W_CONSTRAINT_OUTSIDE_BRACKETS: Detect and-operator outside [].

    Spec: ∧_outside_brackets is NEVER allowed
    Expected: W_CONSTRAINT_OUTSIDE_BRACKETS::and only valid inside []
    """

    def test_constraint_outside_brackets_emits_warning(self):
        """A & B at statement level should emit W_CONSTRAINT_OUTSIDE_BRACKETS warning."""
        content = """===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
CONSTRAINT::A & B
===END==="""
        doc, warnings = parse_with_warnings(content)

        constraint_warnings = [
            w
            for w in warnings
            if w.get("type") == "spec_violation" and "W_CONSTRAINT_OUTSIDE_BRACKETS" in w.get("message", "")
        ]
        assert len(constraint_warnings) >= 1, f"Expected W_CONSTRAINT_OUTSIDE_BRACKETS warning, got: {warnings}"

    def test_constraint_inside_brackets_no_warning(self):
        """[A & B] (constraint inside brackets) should NOT emit warning."""
        content = """===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
CONSTRAINT::[A & B]
===END==="""
        doc, warnings = parse_with_warnings(content)

        constraint_warnings = [
            w
            for w in warnings
            if w.get("type") == "spec_violation" and "W_CONSTRAINT_OUTSIDE_BRACKETS" in w.get("message", "")
        ]
        assert len(constraint_warnings) == 0, f"Should not have W_CONSTRAINT_OUTSIDE_BRACKETS warning: {warnings}"


class TestChainedTensionWarning:
    """W_CHAINED_TENSION: Detect A<->B<->C (more than binary).

    Spec: chained_tension[A<->B<->C] is NEVER allowed, tension is binary only
    Expected: W_CHAINED_TENSION::A<->B<->C invalid, tension is binary only
    """

    def test_chained_tension_emits_warning(self):
        """A vs B vs C (chained tension) should emit W_CHAINED_TENSION warning."""
        content = """===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
TENSION::A vs B vs C
===END==="""
        doc, warnings = parse_with_warnings(content)

        chained_warnings = [
            w for w in warnings if w.get("type") == "spec_violation" and "W_CHAINED_TENSION" in w.get("message", "")
        ]
        assert len(chained_warnings) >= 1, f"Expected W_CHAINED_TENSION warning, got: {warnings}"

    def test_binary_tension_no_warning(self):
        """A vs B (binary tension) should NOT emit warning."""
        content = """===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
TENSION::Speed vs Quality
===END==="""
        doc, warnings = parse_with_warnings(content)

        chained_warnings = [
            w for w in warnings if w.get("type") == "spec_violation" and "W_CHAINED_TENSION" in w.get("message", "")
        ]
        assert len(chained_warnings) == 0, f"Should not have W_CHAINED_TENSION warning: {warnings}"


class TestBoundaryMissingWarning:
    """W_BOUNDARY_MISSING: Detect vs without word boundaries.

    Spec: vs::requires_word_boundaries[whitespace|bracket|paren|start|end]
    INVALID: "SpeedvsQuality" (no boundaries)
    Expected: W_BOUNDARY_MISSING::vs requires word boundaries
    """

    def test_vs_without_boundaries_emits_warning(self):
        """SpeedvsQuality (vs without boundaries) should emit W_BOUNDARY_MISSING warning."""
        content = """===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
TENSION::SpeedvsQuality
===END==="""
        doc, warnings = parse_with_warnings(content)

        boundary_warnings = [
            w for w in warnings if w.get("type") == "spec_violation" and "W_BOUNDARY_MISSING" in w.get("message", "")
        ]
        assert len(boundary_warnings) >= 1, f"Expected W_BOUNDARY_MISSING warning, got: {warnings}"

    def test_vs_with_boundaries_no_warning(self):
        """Speed vs Quality (vs with boundaries) should NOT emit warning."""
        content = """===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
TENSION::Speed vs Quality
===END==="""
        doc, warnings = parse_with_warnings(content)

        boundary_warnings = [
            w for w in warnings if w.get("type") == "spec_violation" and "W_BOUNDARY_MISSING" in w.get("message", "")
        ]
        assert len(boundary_warnings) == 0, f"Should not have W_BOUNDARY_MISSING warning: {warnings}"

    def test_vs_in_brackets_no_warning(self):
        """[Speed vs Quality] should NOT emit warning."""
        content = """===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
TENSION::[Speed vs Quality]
===END==="""
        doc, warnings = parse_with_warnings(content)

        boundary_warnings = [
            w for w in warnings if w.get("type") == "spec_violation" and "W_BOUNDARY_MISSING" in w.get("message", "")
        ]
        assert len(boundary_warnings) == 0, f"Should not have W_BOUNDARY_MISSING warning: {warnings}"
