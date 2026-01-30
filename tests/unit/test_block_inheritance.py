"""Tests for block inheritance (Issue #189).

Per octave-schema-spec.oct.md section 4::BLOCK_INHERITANCE:
- SYNTAX::BLOCK[->TARGET]:
- RULE::children_inherit_parent_target_unless_they_specify_own
- OVERRIDE::CHILD[->OTHER]:[replaces_inherited]
- DEPTH::unbounded_semantic[implementation_caps_at_100]

TDD RED phase: Write failing tests before implementation.
"""

import pytest

from octave_mcp.core.parser import parse


class TestBlockTargetParsing:
    """Test parsing of block-level target syntax: BLOCK[->TARGET]:"""

    def test_block_with_target_annotation_parsed(self):
        """Block with target annotation should preserve target on AST node.

        Input: RISKS[->RISK_LOG]:
        Expected: Block node with key="RISKS" and target="RISK_LOG"
        """
        from octave_mcp.core.ast_nodes import Block

        doc = parse("""
===TEST===
META:
  TYPE::TEST

RISKS[->RISK_LOG]:
  CRITICAL::"auth_bypass"
===END===
""")
        # Find the RISKS block
        risks_block = None
        for section in doc.sections:
            if isinstance(section, Block) and section.key == "RISKS":
                risks_block = section
                break

        assert risks_block is not None, "RISKS block should be parsed"
        assert hasattr(risks_block, "target"), "Block should have target attribute"
        assert risks_block.target == "RISK_LOG", f"Expected target 'RISK_LOG', got {risks_block.target!r}"

    def test_block_with_section_marker_target(self):
        """Block target with section marker should strip the marker.

        Input: DATA[->INDEXER]:  (section marker implicit in -> syntax)
        Expected: Block.target == "INDEXER"
        """
        from octave_mcp.core.ast_nodes import Block

        doc = parse("""
===TEST===
META:
  TYPE::TEST

DATA[->INDEXER]:
  ID::"abc123"
===END===
""")
        data_block = None
        for section in doc.sections:
            if isinstance(section, Block) and section.key == "DATA":
                data_block = section
                break

        assert data_block is not None
        assert data_block.target == "INDEXER"

    def test_block_without_target_has_none(self):
        """Block without target annotation should have target=None.

        Input: SIMPLE:
        Expected: Block.target is None
        """
        from octave_mcp.core.ast_nodes import Block

        doc = parse("""
===TEST===
META:
  TYPE::TEST

SIMPLE:
  KEY::"value"
===END===
""")
        simple_block = None
        for section in doc.sections:
            if isinstance(section, Block) and section.key == "SIMPLE":
                simple_block = section
                break

        assert simple_block is not None
        assert simple_block.target is None

    def test_nested_block_with_own_target(self):
        """Nested block with own target should capture that target.

        Input:
        OUTER[->OUTER_TARGET]:
          INNER[->INNER_TARGET]:
            FIELD::"value"

        Expected:
          - OUTER.target == "OUTER_TARGET"
          - INNER.target == "INNER_TARGET"
        """
        from octave_mcp.core.ast_nodes import Block

        doc = parse("""
===TEST===
META:
  TYPE::TEST

OUTER[->OUTER_TARGET]:
  INNER[->INNER_TARGET]:
    FIELD::"value"
===END===
""")
        outer_block = None
        for section in doc.sections:
            if isinstance(section, Block) and section.key == "OUTER":
                outer_block = section
                break

        assert outer_block is not None
        assert outer_block.target == "OUTER_TARGET"

        # Find INNER within OUTER's children
        inner_block = None
        for child in outer_block.children:
            if isinstance(child, Block) and child.key == "INNER":
                inner_block = child
                break

        assert inner_block is not None
        assert inner_block.target == "INNER_TARGET"


class TestInheritanceResolver:
    """Test InheritanceResolver for ancestor path walking."""

    def test_inheritance_resolver_import(self):
        """InheritanceResolver should be importable."""
        from octave_mcp.core.schema_extractor import InheritanceResolver

        assert InheritanceResolver is not None

    def test_resolve_target_from_immediate_parent(self):
        """Should resolve target from immediate parent block."""
        from octave_mcp.core.schema_extractor import InheritanceResolver

        resolver = InheritanceResolver()
        # Path: ["RISKS", "CRITICAL"] -> Check RISKS.CRITICAL, then RISKS
        block_targets = {"RISKS": "RISK_LOG"}

        target = resolver.resolve_target(["RISKS", "CRITICAL"], block_targets)
        assert target == "RISK_LOG"

    def test_resolve_target_from_grandparent(self):
        """Should resolve target from grandparent when parent has none."""
        from octave_mcp.core.schema_extractor import InheritanceResolver

        resolver = InheritanceResolver()
        # Path: ["OUTER", "MIDDLE", "INNER"]
        # -> Check OUTER.MIDDLE.INNER (none), OUTER.MIDDLE (none), OUTER (has target)
        block_targets = {"OUTER": "OUTER_TARGET"}

        target = resolver.resolve_target(["OUTER", "MIDDLE", "INNER"], block_targets)
        assert target == "OUTER_TARGET"

    def test_resolve_target_child_overrides_parent(self):
        """Child's own target should override parent's target."""
        from octave_mcp.core.schema_extractor import InheritanceResolver

        resolver = InheritanceResolver()
        # Path: ["RISKS", "WARNING"]
        # Both RISKS and RISKS.WARNING have targets - child's should be used
        block_targets = {
            "RISKS": "RISK_LOG",
            "RISKS.WARNING": "SELF",
        }

        target = resolver.resolve_target(["RISKS", "WARNING"], block_targets)
        assert target == "SELF"

    def test_resolve_target_none_when_no_ancestors_have_target(self):
        """Should return None when no ancestor has a target."""
        from octave_mcp.core.schema_extractor import InheritanceResolver

        resolver = InheritanceResolver()
        block_targets = {}

        target = resolver.resolve_target(["ORPHAN", "CHILD"], block_targets)
        assert target is None

    def test_ancestors_yields_correct_order(self):
        """_ancestors should yield from child to root."""
        from octave_mcp.core.schema_extractor import InheritanceResolver

        resolver = InheritanceResolver()
        path = ["A", "B", "C"]
        ancestors = list(resolver._ancestors(path))

        assert ancestors == ["A.B.C", "A.B", "A"]

    def test_depth_limit_enforced(self):
        """Should raise DepthLimitError when depth exceeds 100."""
        from octave_mcp.core.schema_extractor import DepthLimitError, InheritanceResolver

        resolver = InheritanceResolver()
        # Create a path with 101 levels
        deep_path = [f"LEVEL_{i}" for i in range(101)]
        block_targets = {}

        with pytest.raises(DepthLimitError) as exc_info:
            resolver.resolve_target(deep_path, block_targets)

        assert "100" in str(exc_info.value)

    def test_max_depth_constant_is_100(self):
        """MAX_DEPTH should be 100 per spec."""
        from octave_mcp.core.schema_extractor import InheritanceResolver

        assert InheritanceResolver.MAX_DEPTH == 100


class TestBlockInheritanceIntegration:
    """Integration tests for block inheritance in validation."""

    def test_children_inherit_parent_block_target(self):
        """Children should inherit target from parent block annotation.

        Per spec section 4:
        RISKS[->RISK_LOG]:
          CRITICAL::["auth_bypass"∧REQ]     // inherits ->RISK_LOG

        Expected: CRITICAL field routes to RISK_LOG
        """
        from octave_mcp.core.ast_nodes import Assignment, Block
        from octave_mcp.core.schema_extractor import (
            InheritanceResolver,
        )

        # Create document with nested block structure
        # RISKS block has target annotation, CRITICAL is a child
        _risks_block = Block(
            key="RISKS",
            children=[
                Assignment(key="CRITICAL", value="auth_bypass"),
            ],
        )
        # Mark block with target (after parser enhancement)
        _risks_block.target = "RISK_LOG"  # type: ignore

        # Build block targets map from AST
        resolver = InheritanceResolver()
        block_targets = {"RISKS": "RISK_LOG"}

        # Resolve target for CRITICAL field
        target = resolver.resolve_target(["RISKS", "CRITICAL"], block_targets)
        assert target == "RISK_LOG"

    def test_child_explicit_target_overrides_inherited(self):
        """Child with explicit target should override inherited.

        Per spec section 4:
        RISKS[->RISK_LOG]:
          CRITICAL::["auth_bypass"∧REQ]     // inherits ->RISK_LOG
          WARNING::["rate_limit"∧OPT->SELF] // overrides to SELF
        """
        from octave_mcp.core.schema_extractor import InheritanceResolver

        resolver = InheritanceResolver()
        block_targets = {"RISKS": "RISK_LOG"}

        # CRITICAL has no explicit target - inherits RISK_LOG
        critical_target = resolver.resolve_target(["RISKS", "CRITICAL"], block_targets)
        assert critical_target == "RISK_LOG"

        # For fields with explicit target, that target is used directly
        # (not from block_targets - the field's own target takes precedence)
        # This is handled at validation time, not in InheritanceResolver

    def test_deeply_nested_inheritance(self):
        """Should correctly inherit through multiple nesting levels.

        OUTER[->OUTER_LOG]:
          MIDDLE:
            INNER:
              DEEP::value  // Should inherit OUTER_LOG
        """
        from octave_mcp.core.schema_extractor import InheritanceResolver

        resolver = InheritanceResolver()
        block_targets = {"OUTER": "OUTER_LOG"}

        # DEEP field at path OUTER.MIDDLE.INNER.DEEP
        target = resolver.resolve_target(["OUTER", "MIDDLE", "INNER", "DEEP"], block_targets)
        assert target == "OUTER_LOG"

    def test_intermediate_block_can_override_ancestor(self):
        """Intermediate block can override ancestor's target.

        OUTER[->OUTER_LOG]:
          MIDDLE[->MIDDLE_LOG]:
            INNER:
              DEEP::value  // Should inherit MIDDLE_LOG (closer ancestor)
        """
        from octave_mcp.core.schema_extractor import InheritanceResolver

        resolver = InheritanceResolver()
        block_targets = {
            "OUTER": "OUTER_LOG",
            "OUTER.MIDDLE": "MIDDLE_LOG",
        }

        target = resolver.resolve_target(["OUTER", "MIDDLE", "INNER", "DEEP"], block_targets)
        assert target == "MIDDLE_LOG"


class TestBlockTargetExtraction:
    """Test extraction of block targets from parsed AST."""

    def test_extract_block_targets_from_document(self):
        """Should extract all block targets into a mapping.

        Given AST with blocks having target annotations,
        should build a dict: {"BLOCK_PATH": "TARGET"}
        """
        from octave_mcp.core.schema_extractor import extract_block_targets

        doc = parse("""
===TEST===
META:
  TYPE::TEST

RISKS[->RISK_LOG]:
  CRITICAL::"auth_bypass"

DATA[->INDEXER]:
  ID::"123"
===END===
""")
        block_targets = extract_block_targets(doc)

        assert block_targets.get("RISKS") == "RISK_LOG"
        assert block_targets.get("DATA") == "INDEXER"

    def test_extract_nested_block_targets(self):
        """Should extract targets from nested blocks with full paths.

        OUTER[->A]:
          INNER[->B]:
            FIELD::value

        Expected:
          - "OUTER" -> "A"
          - "OUTER.INNER" -> "B"
        """
        from octave_mcp.core.schema_extractor import extract_block_targets

        doc = parse("""
===TEST===
META:
  TYPE::TEST

OUTER[->TARGET_A]:
  INNER[->TARGET_B]:
    FIELD::"value"
===END===
""")
        block_targets = extract_block_targets(doc)

        assert block_targets.get("OUTER") == "TARGET_A"
        assert block_targets.get("OUTER.INNER") == "TARGET_B"


class TestI4AuditTrail:
    """Test I4 auditability for inheritance decisions."""

    def test_inheritance_decision_logged(self):
        """Inheritance resolution should log decision for I4 audit trail.

        Per I4: "If bits lost must have receipt"
        When target is inherited, log should capture:
        - Source path (the field inheriting)
        - Inherited target
        - Ancestor that provided target
        """
        from octave_mcp.core.schema_extractor import InheritanceResolver

        resolver = InheritanceResolver()
        block_targets = {"RISKS": "RISK_LOG"}

        # Resolve with audit trail capture
        target, audit = resolver.resolve_target_with_audit(["RISKS", "CRITICAL"], block_targets)

        assert target == "RISK_LOG"
        assert audit is not None
        assert audit["inherited_from"] == "RISKS"
        assert audit["target"] == "RISK_LOG"
        assert audit["field_path"] == "RISKS.CRITICAL"
