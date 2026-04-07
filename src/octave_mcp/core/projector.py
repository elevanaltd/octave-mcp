"""OCTAVE projection modes (P1.9).

Implements eject() projection modes:
- canonical: Full document, lossy=false
- authoring: Lenient format, lossy=false
- executive: STATUS,RISKS,DECISIONS only, lossy=true
- developer: TESTS,CI,DEPS only, lossy=true
"""

from dataclasses import dataclass, replace

from octave_mcp.core.ast_nodes import Assignment, Block, Document
from octave_mcp.core.emitter import emit


@dataclass
class ProjectionResult:
    """Result of projection operation."""

    output: str
    lossy: bool
    fields_omitted: list[str]
    filtered_doc: Document  # Filtered AST for serialization to JSON/YAML/MD


def _filter_fields(doc: Document, keep: list[str]) -> Document:
    """Filter document to keep only specified top-level fields with all descendants.

    When a field's key matches the keep list, the entire subtree is kept.
    Filtering is applied only at the top level - once a Block is kept,
    all its children are preserved (IL-PLACEHOLDER-FIX-001-REWORK).

    Args:
        doc: Document to filter
        keep: List of field names to keep

    Returns:
        Filtered document with only specified fields and their descendants
    """
    keep_set = set(keep)

    def filter_recursively(nodes: list, apply_filter: bool = True) -> list:
        """Recursively process nodes.

        Args:
            nodes: List of nodes to process
            apply_filter: If True, filter against keep_set; if False, keep all

        Returns:
            Filtered list of nodes
        """
        filtered: list = []
        for node in nodes:
            if isinstance(node, Assignment | Block):
                if apply_filter:
                    # Top-level filtering: check if this node's key is in keep set
                    if node.key in keep_set:
                        # Keep this node with ALL descendants (no filtering on children)
                        if isinstance(node, Block):
                            # Preserve all children without filtering
                            preserved_children = filter_recursively(node.children, apply_filter=False)
                            filtered.append(replace(node, children=preserved_children))
                        else:
                            filtered.append(node)
                    else:
                        # Node key not in keep set - check children recursively
                        # (handles case where kept field is nested under non-kept field)
                        if isinstance(node, Block):
                            filtered_children = filter_recursively(node.children, apply_filter=True)
                            # Only include this node if it has children that were kept
                            if filtered_children:
                                filtered.append(replace(node, children=filtered_children))
                else:
                    # No filtering - preserve everything
                    if isinstance(node, Block):
                        preserved_children = filter_recursively(node.children, apply_filter=False)
                        filtered.append(replace(node, children=preserved_children))
                    else:
                        filtered.append(node)
            else:
                # Keep other node types (comments, etc.)
                filtered.append(node)
        return filtered

    filtered_sections = filter_recursively(doc.sections, apply_filter=True)
    return replace(doc, sections=filtered_sections)


def _collect_top_level_keys(doc: Document) -> list[str]:
    """Collect top-level Assignment and Block keys from document sections.

    Extracts the key from each top-level node in doc.sections, preserving
    insertion order. META is excluded since it lives in doc.meta and is
    always preserved by projection modes.

    Args:
        doc: Document AST

    Returns:
        List of top-level field key strings in document order
    """
    keys: list[str] = []
    for node in doc.sections:
        if isinstance(node, Assignment | Block):
            keys.append(node.key)
    return keys


def _compute_fields_omitted(original_doc: Document, filtered_doc: Document) -> list[str]:
    """Compute which top-level fields were omitted by projection filtering.

    Compares original document keys against filtered document keys to produce
    an accurate I4-compliant transform receipt. Only top-level field keys are
    reported; children of omitted blocks are not individually listed.

    Args:
        original_doc: Document before projection filtering
        filtered_doc: Document after projection filtering

    Returns:
        List of omitted top-level field key strings in original document order
    """
    original_keys = _collect_top_level_keys(original_doc)
    kept_keys = set(_collect_top_level_keys(filtered_doc))
    return [key for key in original_keys if key not in kept_keys]


def project(doc: Document, mode: str = "canonical") -> ProjectionResult:
    """Project document to specified mode.

    Args:
        doc: Document AST
        mode: Projection mode (canonical, authoring, executive, developer)

    Returns:
        ProjectionResult with output, lossy flag, omitted fields, and filtered AST
    """
    if mode == "canonical":
        # Full document
        output = emit(doc)
        return ProjectionResult(output=output, lossy=False, fields_omitted=[], filtered_doc=doc)

    elif mode == "authoring":
        # Lenient format (for now, same as canonical)
        output = emit(doc)
        return ProjectionResult(output=output, lossy=False, fields_omitted=[], filtered_doc=doc)

    elif mode == "executive":
        # Executive view: STATUS, RISKS, DECISIONS only
        filtered_doc = _filter_fields(doc, keep=["STATUS", "RISKS", "DECISIONS"])
        output = emit(filtered_doc)
        omitted = _compute_fields_omitted(doc, filtered_doc)
        return ProjectionResult(output=output, lossy=True, fields_omitted=omitted, filtered_doc=filtered_doc)

    elif mode == "developer":
        # Developer view: TESTS, CI, DEPS only
        filtered_doc = _filter_fields(doc, keep=["TESTS", "CI", "DEPS"])
        output = emit(filtered_doc)
        omitted = _compute_fields_omitted(doc, filtered_doc)
        return ProjectionResult(output=output, lossy=True, fields_omitted=omitted, filtered_doc=filtered_doc)

    else:
        # Default to canonical
        output = emit(doc)
        return ProjectionResult(output=output, lossy=False, fields_omitted=[], filtered_doc=doc)
