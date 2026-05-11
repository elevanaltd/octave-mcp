"""Tests for the promoted CST module (ADR-0006 SR1-T1 Step 4).

This module pins the contract for ``octave_mcp.core.grammar.cst`` which
promotes the legacy ``octave_mcp.core.ast_nodes`` module to the unified
grammar package. The promotion adds:

* ``NodeKind`` enum (one variant per concrete ASTNode subclass) — provides
  a stable structural discriminator for visitor dispatch and audit-log
  keying (I4 TRANSFORM_AUDITABILITY).
* Reserved fidelity-preservation fields on the base ASTNode, defaulted to
  ``None``: ``leading_trivia``, ``trailing_trivia``, ``was_quoted``. These
  are reserved by Step 4 (this PR) and populated by later steps:
  - ``was_quoted`` → logical-Step 5 (next task) via lexer/parser
    instrumentation.
  - ``leading_trivia`` / ``trailing_trivia`` → Sprint 3+ (SR3-T1 cursor-CST)
    per design doc §3a class-2 dependency table.
* PEP 562 deprecation shim at the legacy path
  ``octave_mcp.core.ast_nodes`` preserving symbol identity (``is``) and
  emitting ``DeprecationWarning`` on attribute access.

See ``docs/adr/adr-0006-sr1-t1-grammar-core-design.md`` §3 row 4, §2.2,
§4.5 G1+G2.
"""

from __future__ import annotations

import warnings

# ---------------------------------------------------------------------------
# NodeKind enum coverage
# ---------------------------------------------------------------------------


def test_node_kind_enum_has_variant_per_node_class() -> None:
    """NodeKind enum MUST have one variant for each concrete ASTNode subclass."""
    from octave_mcp.core.grammar.cst import NodeKind

    expected = {"ASSIGNMENT", "BLOCK", "SECTION", "DOCUMENT", "COMMENT"}
    actual = {member.name for member in NodeKind}
    assert expected.issubset(
        actual
    ), f"NodeKind missing expected variants. Expected superset of {expected}, got {actual}."


def test_node_kind_variants_are_unique() -> None:
    """Each NodeKind variant MUST have a unique value (no aliasing)."""
    from octave_mcp.core.grammar.cst import NodeKind

    values = [member.value for member in NodeKind]
    assert len(values) == len(set(values)), f"NodeKind variants must be unique, got duplicates in {values}"


# ---------------------------------------------------------------------------
# Node classes carry their NodeKind discriminator
# ---------------------------------------------------------------------------


def test_assignment_has_assignment_kind() -> None:
    from octave_mcp.core.grammar.cst import Assignment, NodeKind

    node = Assignment(key="K", value=1)
    assert node.kind is NodeKind.ASSIGNMENT


def test_block_has_block_kind() -> None:
    from octave_mcp.core.grammar.cst import Block, NodeKind

    node = Block(key="K")
    assert node.kind is NodeKind.BLOCK


def test_section_has_section_kind() -> None:
    from octave_mcp.core.grammar.cst import NodeKind, Section

    node = Section(section_id="1", key="K")
    assert node.kind is NodeKind.SECTION


def test_document_has_document_kind() -> None:
    from octave_mcp.core.grammar.cst import Document, NodeKind

    node = Document()
    assert node.kind is NodeKind.DOCUMENT


def test_comment_has_comment_kind() -> None:
    from octave_mcp.core.grammar.cst import Comment, NodeKind

    node = Comment(text="hi")
    assert node.kind is NodeKind.COMMENT


# ---------------------------------------------------------------------------
# kind is set automatically — callers do NOT pass it to __init__
# ---------------------------------------------------------------------------


def test_assignment_init_signature_unchanged_no_kind_arg() -> None:
    """Existing call sites pass key/value; the ``kind`` field MUST NOT be
    part of the __init__ signature so the ~30 import sites continue to
    work unchanged."""
    from octave_mcp.core.grammar.cst import Assignment

    # If kind is init=True we'd need to pass it. The promotion design
    # requires init=False so this call shape is preserved.
    node = Assignment(key="X", value=42)
    assert node.key == "X"
    assert node.value == 42


# ---------------------------------------------------------------------------
# Reserved fidelity-preservation fields (§4.5 G1+G2)
# ---------------------------------------------------------------------------


def test_assignment_reserves_was_quoted_field_defaulted_none() -> None:
    """G2 fidelity guardrail: was_quoted reserved Optional[bool] = None."""
    from octave_mcp.core.grammar.cst import Assignment

    node = Assignment(key="K", value=1)
    assert node.was_quoted is None, "was_quoted MUST default to None — population is logical-Step 5"


def test_assignment_reserves_leading_trivia_field_defaulted_none() -> None:
    """G1 fidelity guardrail: leading_trivia reserved Optional[str] = None."""
    from octave_mcp.core.grammar.cst import Assignment

    node = Assignment(key="K", value=1)
    assert node.leading_trivia is None, "leading_trivia MUST default to None — population is Sprint 3+"


def test_assignment_reserves_trailing_trivia_field_defaulted_none() -> None:
    """G1 fidelity guardrail: trailing_trivia reserved Optional[str] = None."""
    from octave_mcp.core.grammar.cst import Assignment

    node = Assignment(key="K", value=1)
    assert node.trailing_trivia is None, "trailing_trivia MUST default to None — population is Sprint 3+"


def test_block_reserves_all_three_fidelity_fields() -> None:
    from octave_mcp.core.grammar.cst import Block

    node = Block(key="K")
    assert node.was_quoted is None
    assert node.leading_trivia is None
    assert node.trailing_trivia is None


def test_section_reserves_all_three_fidelity_fields() -> None:
    from octave_mcp.core.grammar.cst import Section

    node = Section(section_id="1", key="K")
    assert node.was_quoted is None
    assert node.leading_trivia is None
    assert node.trailing_trivia is None


def test_document_reserves_all_three_fidelity_fields() -> None:
    from octave_mcp.core.grammar.cst import Document

    node = Document()
    assert node.was_quoted is None
    assert node.leading_trivia is None
    assert node.trailing_trivia is None


def test_comment_reserves_all_three_fidelity_fields() -> None:
    from octave_mcp.core.grammar.cst import Comment

    node = Comment(text="hi")
    assert node.was_quoted is None
    assert node.leading_trivia is None
    assert node.trailing_trivia is None


# ---------------------------------------------------------------------------
# Backwards-compat: ASTNode base class still exposes original fields
# ---------------------------------------------------------------------------


def test_astnode_base_preserves_existing_fields() -> None:
    """Promotion MUST NOT alter existing dataclass runtime semantics."""
    from octave_mcp.core.grammar.cst import ASTNode

    node = ASTNode(line=10, column=5, leading_comments=["# x"], trailing_comment="# y")
    assert node.line == 10
    assert node.column == 5
    assert node.leading_comments == ["# x"]
    assert node.trailing_comment == "# y"


# ---------------------------------------------------------------------------
# Value types (ListValue, InlineMap, HolographicValue, LiteralZoneValue)
# are re-exported but are NOT ASTNode subclasses; they do not carry a kind.
# ---------------------------------------------------------------------------


def test_value_types_are_reexported() -> None:
    """Value types must still be importable from the new path."""
    from octave_mcp.core.grammar.cst import (
        Absent,
        HolographicValue,
        InlineMap,
        ListValue,
        LiteralZoneValue,
    )

    assert ListValue is not None
    assert InlineMap is not None
    assert HolographicValue is not None
    assert LiteralZoneValue is not None
    assert Absent is not None


def test_absent_singleton_preserved() -> None:
    """Absent sentinel remains a singleton per I2 (Deterministic Absence)."""
    from octave_mcp.core.grammar.cst import ABSENT, Absent

    assert Absent() is Absent(), "Absent must remain a singleton"
    assert ABSENT is Absent(), "ABSENT module-level constant must be the singleton"


# ---------------------------------------------------------------------------
# Symbol identity across the deprecation shim
# ---------------------------------------------------------------------------


def test_section_identity_preserved_across_shim() -> None:
    """``ast_nodes.Section`` MUST be the same object as ``grammar.cst.Section``."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from octave_mcp.core import ast_nodes as legacy
        from octave_mcp.core.grammar import cst as new_path

        assert legacy.Section is new_path.Section


def test_block_identity_preserved_across_shim() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from octave_mcp.core import ast_nodes as legacy
        from octave_mcp.core.grammar import cst as new_path

        assert legacy.Block is new_path.Block


def test_assignment_identity_preserved_across_shim() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from octave_mcp.core import ast_nodes as legacy
        from octave_mcp.core.grammar import cst as new_path

        assert legacy.Assignment is new_path.Assignment


def test_document_identity_preserved_across_shim() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from octave_mcp.core import ast_nodes as legacy
        from octave_mcp.core.grammar import cst as new_path

        assert legacy.Document is new_path.Document


def test_astnode_identity_preserved_across_shim() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from octave_mcp.core import ast_nodes as legacy
        from octave_mcp.core.grammar import cst as new_path

        assert legacy.ASTNode is new_path.ASTNode


def test_comment_identity_preserved_across_shim() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from octave_mcp.core import ast_nodes as legacy
        from octave_mcp.core.grammar import cst as new_path

        assert legacy.Comment is new_path.Comment


def test_absent_identity_preserved_across_shim() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from octave_mcp.core import ast_nodes as legacy
        from octave_mcp.core.grammar import cst as new_path

        assert legacy.Absent is new_path.Absent
        assert legacy.ABSENT is new_path.ABSENT


def test_value_type_identity_preserved_across_shim() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from octave_mcp.core import ast_nodes as legacy
        from octave_mcp.core.grammar import cst as new_path

        assert legacy.ListValue is new_path.ListValue
        assert legacy.InlineMap is new_path.InlineMap
        assert legacy.HolographicValue is new_path.HolographicValue
        assert legacy.LiteralZoneValue is new_path.LiteralZoneValue


# ---------------------------------------------------------------------------
# Deprecation contract — mirrors tests/unit/test_grammar_deprecation_shim.py
# ---------------------------------------------------------------------------


def test_accessing_legacy_ast_nodes_symbol_emits_deprecation_warning() -> None:
    """Lazy attribute access on the legacy path MUST emit DeprecationWarning."""
    import octave_mcp.core.ast_nodes as legacy

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _ = legacy.Section  # triggers PEP 562 __getattr__

    deprecation = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert deprecation, (
        "Accessing octave_mcp.core.ast_nodes.Section must emit a DeprecationWarning, "
        f"got: {[str(w.message) for w in caught]}"
    )
    message = str(deprecation[0].message)
    assert "octave_mcp.core.grammar.cst" in message, (
        "Deprecation message must reference the new grammar.cst location, " f"got: {message}"
    )


def test_from_import_of_legacy_ast_nodes_symbol_emits_warning() -> None:
    """``from octave_mcp.core.ast_nodes import Section`` MUST emit
    DeprecationWarning (TMG-coverage pattern from PR #394).

    NOTE: This test asserts the legacy import path's deprecation contract,
    so it must keep the literal legacy path even after the project-wide
    import-site rewrite landed in this PR.
    """
    import importlib
    import sys

    sys.modules.pop("octave_mcp.core.ast_nodes", None)
    importlib.import_module("octave_mcp.core.ast_nodes")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        # Deliberately import from the LEGACY path to assert the
        # deprecation contract. The import-site sweep MUST NOT touch this
        # line; if a future codemod re-runs, preserve the legacy path
        # here.
        legacy_mod = importlib.import_module("octave_mcp.core.ast_nodes")
        _ = legacy_mod.Section  # triggers PEP 562 __getattr__

    deprecation = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert deprecation, (
        "Importing Section via the legacy octave_mcp.core.ast_nodes path must emit a "
        f"DeprecationWarning, got: {[str(w.message) for w in caught]}"
    )


def test_unknown_attribute_on_legacy_shim_raises_attribute_error() -> None:
    """PEP 562 __getattr__ must still raise AttributeError for unknown names."""
    import octave_mcp.core.ast_nodes as legacy

    try:
        _ = legacy.this_symbol_does_not_exist  # type: ignore[attr-defined]
    except AttributeError:
        return
    raise AssertionError(
        "Accessing an unknown attribute on octave_mcp.core.ast_nodes must raise "
        "AttributeError, not silently succeed."
    )
