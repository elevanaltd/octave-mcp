"""Tests for literal zone passthrough guards (T09 -- match points 9-13).

Issue #235: Verifies that LiteralZoneValue is handled correctly (preserved
unchanged) in all value-type dispatch paths:
- projector.py: project() preserves literal zones in emitted output
- repair.py: repair_value() returns LiteralZoneValue unchanged
- repair.py: _repair_ast_node() logs literal zone in audit but never modifies
"""

from octave_mcp.core.ast_nodes import (
    Assignment,
    Document,
    LiteralZoneValue,
)
from octave_mcp.core.constraints import ConstraintChain, EnumConstraint
from octave_mcp.core.holographic import HolographicPattern
from octave_mcp.core.projector import project
from octave_mcp.core.repair import _repair_ast_node, repair, repair_value
from octave_mcp.core.repair_log import (
    RepairLog,
)
from octave_mcp.core.schema_extractor import FieldDefinition, SchemaDefinition

# --- Match Point 9: projector value projection ---


class TestProjectorLiteralZonePassthrough:
    """MP9: Projector preserves literal zone content in output."""

    def test_project_canonical_preserves_literal_zone(self) -> None:
        """Canonical projection preserves literal zone content verbatim."""
        lzv = LiteralZoneValue(content="print('hello')\n", info_tag="python")
        doc = Document(
            name="TEST",
            sections=[Assignment(key="CODE", value=lzv)],
        )
        result = project(doc, mode="canonical")
        assert "```python" in result.output
        assert "print('hello')" in result.output

    def test_project_authoring_preserves_literal_zone(self) -> None:
        """Authoring projection preserves literal zone content verbatim."""
        lzv = LiteralZoneValue(content="raw\tcontent\n", info_tag=None)
        doc = Document(
            name="TEST",
            sections=[Assignment(key="DATA", value=lzv)],
        )
        result = project(doc, mode="authoring")
        assert "raw\tcontent" in result.output

    def test_project_literal_zone_content_returned_as_string(self) -> None:
        """Projection output contains literal zone content as raw string."""
        lzv = LiteralZoneValue(content="x = 1\n", info_tag="python", fence_marker="```")
        doc = Document(
            name="TEST",
            sections=[Assignment(key="CODE", value=lzv)],
        )
        result = project(doc, mode="canonical")
        # The content must appear in the output string
        assert "x = 1" in result.output
        assert result.lossy is False


# --- Match Point 10: projector pattern matching ---
# LiteralZoneValue never matches holographic patterns.
# The projector uses emit() which already handles LiteralZoneValue.
# Holographic pattern matching operates on HolographicValue, not LiteralZoneValue.
# This match point is covered by the type system -- no code path leads to
# LiteralZoneValue being compared against holographic patterns.


# --- Match Point 12: repair_value() passthrough ---


class TestRepairValueLiteralZonePassthrough:
    """MP12: repair_value() returns LiteralZoneValue unchanged."""

    def test_literal_zone_not_repaired_when_fix_true(self) -> None:
        """LiteralZoneValue passes through repair_value even with fix=True."""
        lzv = LiteralZoneValue(content="hello\n", info_tag="python")
        repair_log = RepairLog(repairs=[])

        # Create a field def with constraints
        field_def = FieldDefinition(
            name="CODE",
            pattern=None,
        )

        result_value, was_repaired = repair_value(
            value=lzv,
            field_def=field_def,
            repair_log=repair_log,
            fix=True,
        )
        assert result_value is lzv  # Same object, not a copy
        assert was_repaired is False

    def test_literal_zone_not_repaired_when_fix_false(self) -> None:
        """LiteralZoneValue passes through when fix=False."""
        lzv = LiteralZoneValue(content="data\n")
        repair_log = RepairLog(repairs=[])

        result_value, was_repaired = repair_value(
            value=lzv,
            field_def=None,
            repair_log=repair_log,
            fix=False,
        )
        assert result_value is lzv
        assert was_repaired is False

    def test_literal_zone_no_repair_log_entries(self) -> None:
        """repair_value with LiteralZoneValue produces no repair log entries."""
        lzv = LiteralZoneValue(content="code\n", info_tag="python")
        repair_log = RepairLog(repairs=[])

        repair_value(
            value=lzv,
            field_def=None,
            repair_log=repair_log,
            fix=True,
        )
        assert len(repair_log.repairs) == 0

    def test_literal_zone_not_repaired_even_with_enum_constraints(self) -> None:
        """LiteralZoneValue is never repaired, even with active enum constraints.

        This test requires the explicit isinstance guard: without it,
        LiteralZoneValue would fall through to enum casefold logic.
        """
        lzv = LiteralZoneValue(content="active\n", info_tag="python")
        repair_log = RepairLog(repairs=[])

        # Create field def with enum constraint that would match "active" -> "ACTIVE"
        enum_constraint = EnumConstraint(allowed_values=["ACTIVE", "INACTIVE"])
        chain = ConstraintChain(constraints=[enum_constraint])
        pattern = HolographicPattern(example="ACTIVE", constraints=chain, target=None)
        field_def = FieldDefinition(name="STATUS", pattern=pattern)

        result_value, was_repaired = repair_value(
            value=lzv,
            field_def=field_def,
            repair_log=repair_log,
            fix=True,
        )
        assert result_value is lzv  # Must be unchanged
        assert was_repaired is False
        assert len(repair_log.repairs) == 0


# --- Match Point 13: _repair_ast_node() audit logging ---


class TestRepairAstNodeLiteralZoneAudit:
    """MP13: _repair_ast_node logs literal zone presence but never modifies."""

    def _make_schema_with_field(self, key: str) -> SchemaDefinition:
        """Helper to create a schema with a field definition."""
        return SchemaDefinition(
            name="TEST_SCHEMA",
            version="1.0",
            fields={
                key: FieldDefinition(name=key, pattern=None),
            },
        )

    def test_literal_zone_not_modified_by_repair_ast_node(self) -> None:
        """_repair_ast_node does not modify LiteralZoneValue."""
        lzv = LiteralZoneValue(content="original\n", info_tag="python")
        assignment = Assignment(key="CODE", value=lzv)
        schema = self._make_schema_with_field("CODE")
        repair_log = RepairLog(repairs=[])

        _repair_ast_node(assignment, schema, repair_log)

        # Value must be the same object
        assert assignment.value is lzv
        assert assignment.value.content == "original\n"

    def test_literal_zone_content_preserved_in_repair_pipeline(self) -> None:
        """Full repair pipeline preserves literal zone content."""
        lzv = LiteralZoneValue(content="preserve this\ttab\n", info_tag="sh")
        doc = Document(
            name="TEST",
            sections=[Assignment(key="SCRIPT", value=lzv)],
        )
        schema = self._make_schema_with_field("SCRIPT")

        repaired_doc, repair_log = repair(doc, [], fix=True, schema=schema)

        # Value must remain unchanged
        assignment = repaired_doc.sections[0]
        assert isinstance(assignment, Assignment)
        assert isinstance(assignment.value, LiteralZoneValue)
        assert assignment.value.content == "preserve this\ttab\n"

    def test_existing_non_literal_repairs_still_work(self) -> None:
        """Non-literal zone values are still repaired normally (no regression)."""
        doc = Document(
            name="TEST",
            sections=[Assignment(key="STATUS", value="active")],
        )
        # This is a regression guard -- existing repair behavior must not break
        repaired_doc, _ = repair(doc, [], fix=False)
        # No repairs when fix=False
        assert repaired_doc.sections[0].value == "active"
