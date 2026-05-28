"""AST structural metrics extracted from write.py as part of STRATEGY_S1 (#459/#464)."""

from dataclasses import dataclass, field

from octave_mcp.core.grammar.cst import (
    Assignment,
    ASTNode,
    Block,
    Document,
    Section,
)


@dataclass
class StructuralMetrics:
    """Metrics for structural comparison of OCTAVE documents.

    Tracks counts of structural elements to detect potential data loss
    during normalization or transformation.
    """

    sections: int = 0  # Count of Section nodes
    section_markers: set[str] = field(default_factory=set)  # Section IDs found
    blocks: int = 0  # Count of Block nodes
    assignments: int = 0  # Count of Assignment nodes


def extract_structural_metrics(doc: Document) -> StructuralMetrics:
    """Extract structural metrics from a parsed OCTAVE document.

    Recursively traverses the AST to count structural elements.

    Args:
        doc: Parsed Document AST

    Returns:
        StructuralMetrics with counts of structural elements
    """
    metrics = StructuralMetrics()

    def traverse(nodes: list[ASTNode]) -> None:
        """Recursively count structural elements."""
        for node in nodes:
            if isinstance(node, Section):
                metrics.sections += 1
                metrics.section_markers.add(node.section_id)
                traverse(node.children)
            elif isinstance(node, Block):
                metrics.blocks += 1
                traverse(node.children)
            elif isinstance(node, Assignment):
                metrics.assignments += 1

    traverse(doc.sections)
    return metrics
