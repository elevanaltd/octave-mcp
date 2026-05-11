"""Tests for the CanonicalEmitter CST visitor (ADR-0006 SR1-T1 Step 5).

This module pins the Step-5 structural seam: ``emitter.py`` is a
``Visitor[str]`` consumer that walks the CST and produces canonical
OCTAVE bytes. Identifier/annotation/expression shape decisions are
sourced from a single helper surface (in ``core/grammar/visitor.py``)
rather than re-derived regex constants in ``emitter.py``.

Tests here cover:

1. The ``CanonicalEmitter`` class exists, subclasses ``Visitor[str]``, and
   implements the required visit_* methods.
2. The ``emit()`` module-level entry point dispatches through the visitor.
3. ``IDENTIFIER_PATTERN`` / ``ANNOTATION_PATTERN`` / ``EXPRESSION_PATTERN``
   are NOT defined as module-level attributes in ``emitter.py``. (§4.5
   fallback discipline — "delete the regex fallback in the same PR".)
4. Behavioural emit branches: was_quoted=True with identifier-shaped
   value still dequotes (canonical preference per HO directive — the
   I1-correct canonical output stays the same; Step 3 logs it later).
5. Behavioural: was_quoted=False with identifier-shaped value emits bare.
6. Behavioural: was_quoted=True with non-identifier-shaped value (e.g.
   ``"42"``) preserves the quoting at emit time — the §4.5 G2 type-fidelity
   guard (this case is the canonical preservation case).

See ``docs/adr/adr-0006-sr1-t1-grammar-core-design.md`` §3 row 5, §4.5.
"""

from __future__ import annotations

import importlib

import pytest

# ---------------------------------------------------------------------------
# CanonicalEmitter exists and implements the Visitor[str] surface
# ---------------------------------------------------------------------------


def test_canonical_emitter_is_importable() -> None:
    from octave_mcp.core.emitter import CanonicalEmitter  # noqa: F401


def test_canonical_emitter_implements_visitor_protocol() -> None:
    """CanonicalEmitter MUST satisfy the Visitor[str] structural Protocol."""
    from octave_mcp.core.emitter import CanonicalEmitter
    from octave_mcp.core.grammar.visitor import Visitor

    ce = CanonicalEmitter()
    assert isinstance(ce, Visitor)


def test_canonical_emitter_has_visit_methods() -> None:
    from octave_mcp.core.emitter import CanonicalEmitter

    for name in (
        "visit_assignment",
        "visit_block",
        "visit_section",
        "visit_document",
        "visit",
    ):
        assert hasattr(CanonicalEmitter, name), f"CanonicalEmitter must implement {name} per Visitor[str] protocol"


def test_emit_dispatches_through_canonical_emitter() -> None:
    """``emit(doc)`` must produce the same bytes whether called directly or
    via ``CanonicalEmitter().visit(doc)``. This pins the entry point as a
    thin wrapper around the visitor."""
    from octave_mcp.core.emitter import CanonicalEmitter, emit
    from octave_mcp.core.grammar.cst import Assignment, Document

    doc = Document(name="DOC", sections=[Assignment(key="K", value="v")])

    via_emit = emit(doc)
    via_visitor = CanonicalEmitter().visit(doc)
    # The visitor result may not include the trailing newline that emit()
    # appends for POSIX compatibility; compare the meaningful payload.
    assert via_emit.rstrip("\n") == via_visitor.rstrip("\n")


# ---------------------------------------------------------------------------
# Regex constants are deleted from emitter.py (§4.5 fallback discipline)
# ---------------------------------------------------------------------------


def test_emitter_module_has_no_identifier_pattern_constant() -> None:
    """emitter.py MUST NOT expose IDENTIFIER_PATTERN at module scope.

    The shape predicate moved to ``core/grammar/visitor.py``. The regex
    fallback for "dequoting decision" is deleted per §4.5.
    """
    emitter = importlib.import_module("octave_mcp.core.emitter")
    assert not hasattr(emitter, "IDENTIFIER_PATTERN"), (
        "IDENTIFIER_PATTERN must be deleted from emitter.py per §4.5 "
        "fallback discipline (shape predicate moved to visitor.py)."
    )


def test_emitter_module_has_no_annotation_pattern_constant() -> None:
    emitter = importlib.import_module("octave_mcp.core.emitter")
    assert not hasattr(emitter, "ANNOTATION_PATTERN"), "ANNOTATION_PATTERN must be deleted from emitter.py per §4.5."


def test_emitter_module_has_no_expression_pattern_constant() -> None:
    emitter = importlib.import_module("octave_mcp.core.emitter")
    assert not hasattr(emitter, "EXPRESSION_PATTERN"), "EXPRESSION_PATTERN must be deleted from emitter.py per §4.5."


# ---------------------------------------------------------------------------
# Shape predicates exist in visitor.py (the relocated permanent helpers)
# ---------------------------------------------------------------------------


def test_identifier_shape_predicate_lives_in_visitor_module() -> None:
    """The identifier-shape predicate moved to ``core/grammar/visitor.py``.

    The function is a permanent type-safety helper (not a fallback), and
    is the SINGLE source the emitter consults for shape decisions.
    """
    from octave_mcp.core.grammar.visitor import is_identifier_shape

    assert is_identifier_shape("ABC") is True
    assert is_identifier_shape("foo_bar") is True
    assert is_identifier_shape("hello world") is False
    assert is_identifier_shape("42") is False
    assert is_identifier_shape("") is False


def test_annotation_shape_predicate_lives_in_visitor_module() -> None:
    from octave_mcp.core.grammar.visitor import is_annotation_shape

    assert is_annotation_shape("NEVER<X>") is True
    assert is_annotation_shape("FOO<>") is True
    assert is_annotation_shape("plain") is False


def test_expression_shape_predicate_lives_in_visitor_module() -> None:
    from octave_mcp.core.grammar.visitor import is_expression_shape

    assert is_expression_shape("A→B") is True  # A→B
    assert is_expression_shape("plain") is False


# ---------------------------------------------------------------------------
# Behavioural emit branches (the §3 row 5 decision rule)
# ---------------------------------------------------------------------------


def test_emit_dequotes_identifier_shaped_value_with_was_quoted_true() -> None:
    """The canonical preference: was_quoted=True + identifier-shape → bare.

    This is the I1-canonical-output rule the HO directive pins. The 10
    strict-xfails REMAIN xfailed because the visible dequoting persists;
    Step 3 will log the decision via tier_normalize.log_repair.
    """
    from octave_mcp.core.emitter import emit
    from octave_mcp.core.grammar.cst import Assignment, Document

    a = Assignment(key="TYPE", value="SPEC")
    a.was_quoted = True
    doc = Document(name="DOC", sections=[a])
    output = emit(doc)
    assert "TYPE::SPEC" in output, (
        "was_quoted=True + identifier-shape MUST still dequote per HO "
        "directive (Step 3 logs the normalisation; Step 5 preserves "
        "canonical output)."
    )
    assert 'TYPE::"SPEC"' not in output


def test_emit_preserves_quote_for_non_identifier_shaped_value_with_was_quoted_true() -> None:
    """§4.5 G2 type-fidelity case: was_quoted=True + non-identifier-shape → quoted.

    A value like "42" must stay quoted to avoid being read as integer 42
    on round-trip (current emitter behaviour — preserved).
    """
    from octave_mcp.core.emitter import emit
    from octave_mcp.core.grammar.cst import Assignment, Document

    a = Assignment(key="N", value="42")
    a.was_quoted = True
    doc = Document(name="DOC", sections=[a])
    output = emit(doc)
    assert 'N::"42"' in output


def test_emit_keeps_bare_for_identifier_shaped_value_with_was_quoted_false() -> None:
    """Bare identifier remains bare on round-trip."""
    from octave_mcp.core.emitter import emit
    from octave_mcp.core.grammar.cst import Assignment, Document

    a = Assignment(key="K", value="bareval")
    a.was_quoted = False
    doc = Document(name="DOC", sections=[a])
    output = emit(doc)
    assert "K::bareval" in output
    assert 'K::"bareval"' not in output


def test_emit_handles_was_quoted_none_via_shape_predicate() -> None:
    """Programmatic construction → was_quoted=None → shape predicate decides.

    This case arises from hydrator/sealer/validator programmatic Assignment
    construction (no source provenance). The emitter's shape helper is the
    permanent decision source — NOT a fallback to a deleted regex.
    """
    from octave_mcp.core.emitter import emit
    from octave_mcp.core.grammar.cst import Assignment, Document

    a_ident = Assignment(key="K", value="identifier_like")
    # was_quoted left as None (the dataclass default).
    assert a_ident.was_quoted is None
    doc1 = Document(name="DOC", sections=[a_ident])
    assert "K::identifier_like" in emit(doc1)

    a_str = Assignment(key="K", value="has spaces")
    assert a_str.was_quoted is None
    doc2 = Document(name="DOC", sections=[a_str])
    assert 'K::"has spaces"' in emit(doc2)


# ---------------------------------------------------------------------------
# Canonical-output parity guard (the smoke-test fixture invariant)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture_path,expected_substring,forbidden_substring",
    [
        ("tests/fixtures/hydration/source.oct.md", "TYPE::SPEC", 'TYPE::"SPEC"'),
    ],
)
def test_emit_preserves_baseline_canonical_output(
    fixture_path: str, expected_substring: str, forbidden_substring: str
) -> None:
    """Smoke-test reproducibility — Step 5 MUST NOT change canonical output.

    HO declared baseline at main HEAD 6adf13a produces TYPE::SPEC (dequoted)
    on hydration/source.oct.md. Step 5 is structural; canonical bytes are
    invariant. If this test fails, Step 5 has flipped behaviour — STOP
    and surface to HO (10 strict-xfails would also flip).
    """
    from pathlib import Path

    from octave_mcp.core.emitter import emit
    from octave_mcp.core.parser import parse

    source = Path(fixture_path).read_text()
    doc = parse(source)
    output = emit(doc)
    assert expected_substring in output, (
        f"Canonical output must contain {expected_substring!r} (Step 5 "
        "preserves baseline; Step 3 logs the normalisation)."
    )
    assert forbidden_substring not in output, (
        f"Canonical output must NOT contain {forbidden_substring!r} — that "
        "would flip an xfail; this is a Step 5 scope-fence breach."
    )
