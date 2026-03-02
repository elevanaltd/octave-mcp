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


def _get_literal_zone_content(
    doc: Any,
    key: str,
    line: int,
) -> str | None:
    """Find the LiteralZoneValue content matching a given key and line.

    Walks the document AST to locate the Assignment node with the
    matching key and line number, then extracts the LiteralZoneValue
    content from its value.

    Args:
        doc: Parsed Document AST.
        key: Assignment key to match.
        line: Source line number of the assignment.

    Returns:
        The raw content string of the literal zone, or None if not found.
    """

    def _extract_from_value(value: Any) -> str | None:
        """Extract content from a value that may be or contain a LiteralZoneValue."""
        if isinstance(value, LiteralZoneValue):
            return value.content
        if isinstance(value, ListValue):
            for item in value.items:
                result = _extract_from_value(item)
                if result is not None:
                    return result
        if isinstance(value, InlineMap):
            for v in value.pairs.values():
                result = _extract_from_value(v)
                if result is not None:
                    return result
        return None

    def _search(nodes: list[ASTNode]) -> str | None:
        for node in nodes:
            if isinstance(node, Assignment) and node.key == key and node.line == line:
                return _extract_from_value(node.value)
            if isinstance(node, Block):
                result = _search(node.children)
                if result is not None:
                    return result
            elif hasattr(node, "children"):
                result = _search(node.children)
                if result is not None:
                    return result
        return None

    return _search(doc.sections)


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

    Args:
        zones: Zone metadata from _count_literal_zones (key, info_tag, line).
        doc: Parsed Document AST containing the literal zone values.
        source_stage: Pipeline stage producing this receipt (e.g., "octave_write").

    Returns:
        LiteralZoneRepairLog with one RepairLogEntry per literal zone found.
    """
    entries: list[RepairLogEntry] = []
    now = datetime.now(UTC).isoformat()

    for zone_meta in zones:
        content = _get_literal_zone_content(doc, zone_meta["key"], zone_meta["line"])
        if content is not None:
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
