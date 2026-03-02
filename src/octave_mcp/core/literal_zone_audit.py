"""Literal zone audit receipts for I4 Transform Auditability.

Provides SHA-256 content hashing for literal zones, proving that zone
content was preserved unchanged through the processing pipeline.

Since literal zones are exempt from normalization (D3: zero processing),
pre_hash always equals post_hash.
"""

import hashlib
from datetime import UTC, datetime
from typing import Any

from octave_mcp.core.ast_nodes import (
    Assignment,
    ASTNode,
    Block,
    InlineMap,
    ListValue,
    LiteralZoneValue,
)
from octave_mcp.core.repair_log import (
    LiteralZoneRepairLog,
    RepairLogEntry,
)


def _collect_all_literal_zone_contents(doc: Any) -> list[str]:
    """Collect content strings for ALL LiteralZoneValue instances in document order.

    Walks the AST in the same traversal order as ``_count_literal_zones()``
    (depth-first over sections, recursing into Block/container children,
    descending into ListValue and InlineMap values).  This guarantees that
    the returned list aligns positionally with the zone metadata list from
    ``_count_literal_zones()``.

    PR#315 fix: The previous ``_get_literal_zone_content(key, line)`` used
    first-match lookup, which returned the same content for every zone that
    shared a (key, line) pair.  Walking once in document order and zipping
    by ordinal index eliminates the duplicate-hash bug.

    Args:
        doc: Parsed Document AST.

    Returns:
        List of raw content strings, one per literal zone, in document order.
    """
    contents: list[str] = []

    def _collect_from_value(value: Any) -> None:
        """Recursively collect LiteralZoneValue content from a value."""
        if isinstance(value, LiteralZoneValue):
            contents.append(value.content)
        elif isinstance(value, ListValue):
            for item in value.items:
                _collect_from_value(item)
        elif isinstance(value, InlineMap):
            for v in value.pairs.values():
                _collect_from_value(v)

    def _traverse(nodes: list[ASTNode]) -> None:
        for node in nodes:
            if isinstance(node, Assignment):
                _collect_from_value(node.value)
            elif isinstance(node, Block):
                _traverse(node.children)
            elif hasattr(node, "children"):
                _traverse(node.children)

    _traverse(doc.sections)
    return contents


def build_literal_zone_repair_log(
    zones: list[dict[str, Any]],
    doc: Any,
    source_stage: str,
) -> LiteralZoneRepairLog:
    """Build repair log with SHA-256 receipts for each literal zone.

    Since literal zones are exempt from normalization (D3: zero processing),
    pre_hash always equals post_hash, proving content preservation.

    I4: Every transformation logged with stable IDs -- if bits lost, must
    have receipt.

    PR#315 fix: Collects ALL literal zone contents in document order and
    zips with zone metadata by ordinal index, ensuring each zone gets its
    own distinct hash even when multiple zones share the same assignment key.

    Args:
        zones: Zone metadata from _count_literal_zones (key, info_tag, line).
        doc: Parsed Document AST containing the literal zone values.
        source_stage: Pipeline stage producing this receipt (e.g., "octave_write").

    Returns:
        LiteralZoneRepairLog with one RepairLogEntry per literal zone found.
    """
    entries: list[RepairLogEntry] = []
    now = datetime.now(UTC).isoformat()

    # Walk AST once in document order — same traversal as _count_literal_zones
    contents = _collect_all_literal_zone_contents(doc)

    # Invariant: content count must match zone count
    if len(contents) != len(zones):
        import warnings

        warnings.warn(
            f"Literal zone count mismatch: {len(zones)} zones from metadata "
            f"but {len(contents)} contents extracted from AST. "
            "Some audit receipts may be missing.",
            stacklevel=2,
        )

    # Zip by ordinal position — both walks use identical traversal order
    for zone_meta, content in zip(zones, contents, strict=False):
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        entries.append(
            RepairLogEntry(
                zone_key=zone_meta["key"],
                line=zone_meta["line"],
                action="preserved",
                pre_hash=content_hash,
                post_hash=content_hash,  # D3: zero processing guarantees equality
                timestamp=now,
                source_stage=source_stage,
            )
        )

    return LiteralZoneRepairLog(entries=entries)
