"""Tests for VOID MAPPER coverage analysis module.

TDD RED Phase: Tests written before implementation.
These tests should FAIL until coverage_mapper.py is implemented.

Issue #48 Phase 2 Batch 3: VOID MAPPER tool for spec-to-skill coverage analysis.
"""

from octave_mcp.core.coverage_mapper import (
    CoverageResult,
    compute_coverage,
    format_coverage_report,
)
from octave_mcp.core.parser import parse


class TestCoverageResult:
    """Tests for CoverageResult dataclass."""

    def test_coverage_result_creation(self):
        """Test CoverageResult can be created with all fields."""
        result = CoverageResult(
            coverage_ratio=0.57,
            covered_sections=["1", "2", "4", "6"],
            gaps=["3", "5", "7"],
            novel=["SKILL_4"],
            spec_total=7,
            skill_total=5,
        )

        assert result.coverage_ratio == 0.57
        assert result.covered_sections == ["1", "2", "4", "6"]
        assert result.gaps == ["3", "5", "7"]
        assert result.novel == ["SKILL_4"]
        assert result.spec_total == 7
        assert result.skill_total == 5

    def test_coverage_result_zero_coverage(self):
        """Test CoverageResult with zero coverage."""
        result = CoverageResult(
            coverage_ratio=0.0,
            covered_sections=[],
            gaps=["1", "2", "3"],
            novel=["X"],
            spec_total=3,
            skill_total=1,
        )

        assert result.coverage_ratio == 0.0
        assert result.covered_sections == []
        assert len(result.gaps) == 3

    def test_coverage_result_full_coverage(self):
        """Test CoverageResult with 100% coverage."""
        result = CoverageResult(
            coverage_ratio=1.0,
            covered_sections=["1", "2", "3"],
            gaps=[],
            novel=[],
            spec_total=3,
            skill_total=3,
        )

        assert result.coverage_ratio == 1.0
        assert result.gaps == []
        assert result.novel == []


class TestComputeCoverage:
    """Tests for compute_coverage function."""

    def test_full_coverage(self):
        """Test coverage calculation with full coverage (100%)."""
        spec_content = """===SPEC_FULL===
META:
  TYPE::"SPEC"

\u00a71::SYNTAX
  RULES::basic_syntax

\u00a72::OPERATORS
  RULES::operator_usage

\u00a73::TYPES
  RULES::type_system
===END==="""

        skill_content = """===SKILL_FULL===
META:
  TYPE::"SKILL"

\u00a71::SYNTAX_IMPL
  IMPLEMENTS::\u00a71

\u00a72::OPERATOR_IMPL
  IMPLEMENTS::\u00a72

\u00a73::TYPE_IMPL
  IMPLEMENTS::\u00a73
===END==="""

        spec_doc = parse(spec_content)
        skill_doc = parse(skill_content)

        result = compute_coverage(spec_doc, skill_doc)

        assert result.coverage_ratio == 1.0
        assert len(result.covered_sections) == 3
        assert result.gaps == []
        assert result.novel == []
        assert result.spec_total == 3
        assert result.skill_total == 3

    def test_partial_coverage_with_gaps(self):
        """Test coverage with gaps (partial coverage)."""
        spec_content = """===SPEC_FULL===
META:
  TYPE::"SPEC"

\u00a71::SYNTAX
  RULES::basic_syntax

\u00a72::OPERATORS
  RULES::operator_usage

\u00a73::TYPES
  RULES::type_system
===END==="""

        skill_content = """===SKILL_PARTIAL===
META:
  TYPE::"SKILL"

\u00a71::SYNTAX_IMPL
  IMPLEMENTS::\u00a71

\u00a74::NOVEL_SECTION
  NOTE::not_in_spec
===END==="""

        spec_doc = parse(spec_content)
        skill_doc = parse(skill_content)

        result = compute_coverage(spec_doc, skill_doc)

        # 1 out of 3 spec sections covered
        assert 0.3 <= result.coverage_ratio <= 0.34  # ~33.33%
        assert "1" in result.covered_sections
        assert "2" in result.gaps
        assert "3" in result.gaps
        assert "4" in result.novel
        assert result.spec_total == 3
        assert result.skill_total == 2

    def test_novel_section_detection(self):
        """Test novel section detection (skill sections not in spec)."""
        spec_content = """===SPEC===
\u00a71::BASIC
  CONTENT::base
===END==="""

        skill_content = """===SKILL===
\u00a71::BASIC_IMPL
  COVERS::\u00a71

\u00a72::EXTRA
  NOTE::novel

\u00a73::ANOTHER_EXTRA
  NOTE::also_novel
===END==="""

        spec_doc = parse(spec_content)
        skill_doc = parse(skill_content)

        result = compute_coverage(spec_doc, skill_doc)

        # Spec section 1 is covered, skill has 2 novel sections
        assert result.coverage_ratio == 1.0  # 1/1 spec sections covered
        assert "1" in result.covered_sections
        assert "2" in result.novel
        assert "3" in result.novel

    def test_empty_spec_document(self):
        """Test with empty spec document (no sections)."""
        spec_content = """===EMPTY_SPEC===
META:
  TYPE::"SPEC"
===END==="""

        skill_content = """===SKILL===
\u00a71::IMPL
  CODE::impl
===END==="""

        spec_doc = parse(spec_content)
        skill_doc = parse(skill_content)

        result = compute_coverage(spec_doc, skill_doc)

        # No spec sections means 0 total, avoid division by zero
        assert result.coverage_ratio == 0.0
        assert result.spec_total == 0
        assert result.covered_sections == []
        assert "1" in result.novel

    def test_empty_skill_document(self):
        """Test with empty skill document (no sections)."""
        spec_content = """===SPEC===
\u00a71::SYNTAX
  RULES::syntax
===END==="""

        skill_content = """===EMPTY_SKILL===
META:
  TYPE::"SKILL"
===END==="""

        spec_doc = parse(spec_content)
        skill_doc = parse(skill_content)

        result = compute_coverage(spec_doc, skill_doc)

        # All spec sections are gaps
        assert result.coverage_ratio == 0.0
        assert "1" in result.gaps
        assert result.novel == []
        assert result.skill_total == 0

    def test_section_matching_by_number(self):
        """Test that sections match by section_id number."""
        spec_content = """===SPEC===
\u00a71::FIRST
  A::1

\u00a72::SECOND
  B::2
===END==="""

        # Skill uses different names but same section numbers
        skill_content = """===SKILL===
\u00a71::DIFFERENT_NAME
  X::1

\u00a72::ANOTHER_NAME
  Y::2
===END==="""

        spec_doc = parse(spec_content)
        skill_doc = parse(skill_content)

        result = compute_coverage(spec_doc, skill_doc)

        # Should match by section ID (1, 2)
        assert result.coverage_ratio == 1.0
        assert "1" in result.covered_sections
        assert "2" in result.covered_sections


class TestFormatCoverageReport:
    """Tests for format_coverage_report function."""

    def test_format_full_coverage(self):
        """Test formatting with full coverage."""
        result = CoverageResult(
            coverage_ratio=1.0,
            covered_sections=["1", "2", "3"],
            gaps=[],
            novel=[],
            spec_total=3,
            skill_total=3,
        )

        report = format_coverage_report(result)

        assert "COVERAGE_RATIO::100%" in report
        assert "3/3" in report or "[3/3" in report
        assert "GAPS::[]" in report or "GAPS::NONE" in report

    def test_format_partial_coverage(self):
        """Test formatting with partial coverage (matches spec output)."""
        result = CoverageResult(
            coverage_ratio=0.57,
            covered_sections=["1", "2", "4", "6"],
            gaps=["3", "5", "7"],
            novel=["4"],  # Raw section ID from compute_coverage
            spec_total=7,
            skill_total=5,
        )

        report = format_coverage_report(result)

        # Per spec: COVERAGE_RATIO::57%[4/7_spec_sections]
        assert "COVERAGE_RATIO::57%" in report
        assert "4/7" in report
        # Per spec: GAPS::[section_list]
        assert "GAPS::" in report
        assert "\u00a73" in report or "3" in report
        # Per spec: NOVEL::[skill_sections]
        assert "NOVEL::" in report
        assert "4" in report  # Novel section ID

    def test_format_zero_coverage(self):
        """Test formatting with zero coverage."""
        result = CoverageResult(
            coverage_ratio=0.0,
            covered_sections=[],
            gaps=["1", "2"],
            novel=[],
            spec_total=2,
            skill_total=0,
        )

        report = format_coverage_report(result)

        assert "COVERAGE_RATIO::0%" in report
        assert "0/2" in report

    def test_format_with_novel_sections(self):
        """Test formatting when skill has novel sections."""
        result = CoverageResult(
            coverage_ratio=0.5,
            covered_sections=["1"],
            gaps=["2"],
            novel=["QUICK_START", "EXAMPLES"],
            spec_total=2,
            skill_total=3,
        )

        report = format_coverage_report(result)

        assert "NOVEL::" in report
        assert "QUICK_START" in report
        assert "EXAMPLES" in report


class TestEdgeCases:
    """Edge case tests for coverage mapper."""

    def test_both_documents_empty(self):
        """Test with both spec and skill empty."""
        spec_content = """===EMPTY===
===END==="""
        skill_content = """===EMPTY===
===END==="""

        spec_doc = parse(spec_content)
        skill_doc = parse(skill_content)

        result = compute_coverage(spec_doc, skill_doc)

        assert result.coverage_ratio == 0.0
        assert result.spec_total == 0
        assert result.skill_total == 0
        assert result.gaps == []
        assert result.novel == []
        assert result.covered_sections == []

    def test_named_sections(self):
        """Test with named sections (not numbered)."""
        spec_content = """===SPEC===
\u00a7CONTEXT::LOCAL
  VARS::local

\u00a7DEFINITIONS::TERMS
  TERM::value
===END==="""

        skill_content = """===SKILL===
\u00a7CONTEXT::IMPL
  IMPL::yes

\u00a7EXTRA::NEW
  NEW::yes
===END==="""

        spec_doc = parse(spec_content)
        skill_doc = parse(skill_content)

        result = compute_coverage(spec_doc, skill_doc)

        # CONTEXT is in both, DEFINITIONS is gap, EXTRA is novel
        assert "CONTEXT" in result.covered_sections
        assert "DEFINITIONS" in result.gaps
        assert "EXTRA" in result.novel

    def test_mixed_numbered_and_named_sections(self):
        """Test with mix of numbered and named sections."""
        spec_content = """===SPEC===
\u00a71::INTRO
  TEXT::intro

\u00a7META::INFO
  INFO::meta
===END==="""

        skill_content = """===SKILL===
\u00a71::INTRO_IMPL
  IMPL::yes

\u00a7META::INFO_IMPL
  IMPL::yes
===END==="""

        spec_doc = parse(spec_content)
        skill_doc = parse(skill_content)

        result = compute_coverage(spec_doc, skill_doc)

        assert result.coverage_ratio == 1.0
        assert "1" in result.covered_sections
        assert "META" in result.covered_sections
