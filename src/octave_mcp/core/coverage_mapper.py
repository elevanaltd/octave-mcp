"""VOID MAPPER: Spec-to-skill coverage analysis.

Issue #48 Phase 2 Batch 3: Implements coverage analysis between
specification documents and their implementing skills.

VOID MAPPER identifies:
1. Which spec sections are covered by the skill (covered_sections)
2. Which spec sections have gaps (not covered)
3. Which skill sections are novel (not in spec)

Output format per spec:
    COVERAGE_RATIO::57%[4/7_spec_sections]
    GAPS::[section_list]
    NOVEL::[skill_sections]
"""

from dataclasses import dataclass

from octave_mcp.core.ast_nodes import Document, Section


@dataclass
class CoverageResult:
    """Result of coverage analysis between spec and skill documents.

    Attributes:
        coverage_ratio: Ratio of covered sections (0.0 to 1.0)
        covered_sections: List of spec section IDs that are covered
        gaps: List of spec section IDs NOT covered by skill
        novel: List of skill section IDs not in spec
        spec_total: Total number of sections in spec
        skill_total: Total number of sections in skill
    """

    coverage_ratio: float
    covered_sections: list[str]
    gaps: list[str]
    novel: list[str]
    spec_total: int
    skill_total: int


def _extract_section_ids(doc: Document) -> set[str]:
    """Extract section IDs from a document.

    Recursively extracts section_id from all Section nodes in the document.

    Args:
        doc: Parsed OCTAVE Document

    Returns:
        Set of section IDs (e.g., {"1", "2", "CONTEXT", "META"})
    """
    section_ids: set[str] = set()

    for node in doc.sections:
        if isinstance(node, Section):
            section_ids.add(node.section_id)

    return section_ids


def compute_coverage(spec_doc: Document, skill_doc: Document) -> CoverageResult:
    """Compute coverage between a spec document and a skill document.

    Analyzes which spec sections are covered by skill sections based on
    section_id matching.

    Section matching logic:
    - Match by section_id (e.g., "1", "2", "CONTEXT")
    - Skill section_id "1" covers spec section_id "1"
    - Named sections match by name (e.g., "CONTEXT" matches "CONTEXT")

    Args:
        spec_doc: The specification Document (defines requirements)
        skill_doc: The skill Document (implements requirements)

    Returns:
        CoverageResult with coverage ratio, covered sections, gaps, and novel sections
    """
    # Extract section IDs from both documents
    spec_ids = _extract_section_ids(spec_doc)
    skill_ids = _extract_section_ids(skill_doc)

    # Calculate coverage
    covered = spec_ids & skill_ids  # Intersection
    gaps = spec_ids - skill_ids  # Spec sections not in skill
    novel = skill_ids - spec_ids  # Skill sections not in spec

    # Calculate coverage ratio
    spec_total = len(spec_ids)
    skill_total = len(skill_ids)

    if spec_total == 0:
        coverage_ratio = 0.0
    else:
        coverage_ratio = len(covered) / spec_total

    return CoverageResult(
        coverage_ratio=coverage_ratio,
        covered_sections=sorted(covered),
        gaps=sorted(gaps),
        novel=sorted(novel),
        spec_total=spec_total,
        skill_total=skill_total,
    )


def format_coverage_report(result: CoverageResult) -> str:
    """Format coverage result as OCTAVE-style report.

    Output format per spec:
        COVERAGE_RATIO::57%[4/7_spec_sections]
        GAPS::[section_list]
        NOVEL::[skill_sections]

    Args:
        result: CoverageResult from compute_coverage

    Returns:
        Formatted coverage report string
    """
    # Format coverage ratio as percentage (round to avoid float precision issues)
    percentage = round(result.coverage_ratio * 100)
    covered_count = len(result.covered_sections)

    lines = []

    # COVERAGE_RATIO line
    lines.append(f"COVERAGE_RATIO::{percentage}%[{covered_count}/{result.spec_total}_spec_sections]")

    # GAPS line - format section IDs with paragraph symbol
    if result.gaps:
        gap_list = ",".join(f"\u00a7{g}" for g in result.gaps)
        lines.append(f"GAPS::[{gap_list}]")
    else:
        lines.append("GAPS::[]")

    # NOVEL line - format skill sections (section IDs are plain, add SKILL_ prefix)
    if result.novel:
        novel_list = ",".join(result.novel)
        lines.append(f"NOVEL::[{novel_list}]")
    else:
        lines.append("NOVEL::[]")

    return "\n".join(lines)
