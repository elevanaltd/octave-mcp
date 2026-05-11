"""Tests for ``was_quoted`` population on Assignment nodes by the parser.

ADR-0006 SR1-T1 Step 5 (logical) — Part A: ensure the parser records
whether an ``Assignment``'s string value originated as a quoted STRING
token (``KEY::"value"``) versus a bare IDENTIFIER (``KEY::value``). This is
the structural enabler for §4.5 G2 (I1 type-fidelity guard) and for
logical-Step 3's precise ``tier_normalize.log_repair`` instrumentation.

These tests are BEHAVIOURAL — they exercise the parser end-to-end and
inspect the resulting CST ``Assignment.was_quoted`` field. They do NOT
inspect parser internals; the contract is that after ``parse(source)``,
each Assignment node carries the correct ``was_quoted`` provenance.

Scope-fence note: ``was_quoted`` is populated on ``Assignment`` nodes
constructed by the lexer/parser pipeline only. Programmatic constructions
(hydrator, sealer, validator, etc.) leave the field as its default
(``None``), which the emitter's identifier-shape predicate handles via a
permanent shape helper — NOT a fallback. See design doc §4.5.

See ``docs/adr/adr-0006-sr1-t1-grammar-core-design.md`` §3 row 5, §4.5 G2.
"""

from __future__ import annotations

from octave_mcp.core.grammar.cst import Assignment, Block, Section
from octave_mcp.core.parser import parse


def _find_assignment(doc, key: str) -> Assignment:
    """Locate the first Assignment with the given key anywhere in the document."""

    def _walk(nodes):
        for n in nodes:
            if isinstance(n, Assignment) and n.key == key:
                return n
            if isinstance(n, (Block, Section)):
                found = _walk(n.children)
                if found is not None:
                    return found
        return None

    found = _walk(doc.sections)
    assert found is not None, f"Assignment {key!r} not found in document"
    return found


# ---------------------------------------------------------------------------
# Quoted STRING token → was_quoted is True
# ---------------------------------------------------------------------------


def test_was_quoted_true_for_quoted_string_value() -> None:
    """A KEY::"VALUE" assignment must record was_quoted=True on the node."""
    source = "===DOC===\n" "§1::ITEMS\n" '  KEY::"hello"\n' "===END===\n"
    doc = parse(source)
    assignment = _find_assignment(doc, "KEY")
    assert assignment.was_quoted is True, "Quoted STRING value must set was_quoted=True (Step 5 §4.5 G2)"


def test_was_quoted_true_for_quoted_identifier_shaped_string() -> None:
    """The §4.5 G2 canonical case: KEY::"identifier_looking" must be was_quoted=True.

    This is the exact provenance Step 3 needs to log the dequoting decision
    via tier_normalize.log_repair. Without this, the audit-cardinality
    breach behind the 10 strict-xfails cannot be precisely logged.
    """
    source = "===DOC===\n" "§1::ITEMS\n" '  TYPE::"SPEC"\n' "===END===\n"
    doc = parse(source)
    assignment = _find_assignment(doc, "TYPE")
    assert assignment.value == "SPEC"
    assert assignment.was_quoted is True, (
        'Identifier-shaped quoted strings (e.g., "SPEC") must still '
        "carry was_quoted=True so Step 3 can log the dequoting decision."
    )


# ---------------------------------------------------------------------------
# Bare IDENTIFIER token → was_quoted is False
# ---------------------------------------------------------------------------


def test_was_quoted_false_for_bare_identifier_value() -> None:
    """KEY::VALUE (bare) must record was_quoted=False on the node."""
    source = "===DOC===\n" "§1::ITEMS\n" "  KEY::hello\n" "===END===\n"
    doc = parse(source)
    assignment = _find_assignment(doc, "KEY")
    assert assignment.was_quoted is False, (
        "Bare IDENTIFIER value must set was_quoted=False; emitter relies "
        "on the (False vs True) distinction for the §4.5 G2 audit."
    )


# ---------------------------------------------------------------------------
# Non-string value types → was_quoted is False (no provenance to preserve)
# ---------------------------------------------------------------------------


def test_was_quoted_false_for_integer_value() -> None:
    """Non-string values have no quoting provenance; was_quoted=False."""
    source = "===DOC===\n" "§1::ITEMS\n" "  COUNT::42\n" "===END===\n"
    doc = parse(source)
    assignment = _find_assignment(doc, "COUNT")
    assert assignment.value == 42
    assert assignment.was_quoted is False, "Non-string scalar values must set was_quoted=False (no source quoting)"


def test_was_quoted_false_for_boolean_value() -> None:
    source = "===DOC===\n" "§1::ITEMS\n" "  FLAG::true\n" "===END===\n"
    doc = parse(source)
    assignment = _find_assignment(doc, "FLAG")
    assert assignment.value is True
    assert assignment.was_quoted is False


# ---------------------------------------------------------------------------
# Programmatically-constructed Assignment → was_quoted defaults to None
# ---------------------------------------------------------------------------


def test_was_quoted_defaults_to_none_for_programmatic_construction() -> None:
    """Hydrator/sealer/validator construct Assignments programmatically.

    For those construction sites the source-quoting signal does not exist,
    and the field default is ``None``. The emitter's identifier-shape
    helper (visitor module) handles this case — it is NOT a fallback path
    for missing was_quoted; it is a permanent type-safety predicate that
    applies when no source provenance exists.
    """
    a = Assignment(key="K", value="V")
    assert a.was_quoted is None


# ---------------------------------------------------------------------------
# Round-trip: was_quoted survives parse → emit → parse (data availability)
# ---------------------------------------------------------------------------


def test_was_quoted_populated_on_every_string_valued_assignment() -> None:
    """End-to-end: parsing a fixture yields Assignments with was_quoted in {True, False}.

    Step 5 acceptance: at every emit-time entry path, ``was_quoted`` is
    non-None for Assignments produced from source. This is the data
    availability claim that lets Step 3 delete the regex fallback in
    emitter.py (per §4.5 fallback discipline).
    """
    source = "===DOC===\n" "§1::A\n" '  X::"quoted"\n' "  Y::bare\n" "  N::5\n" "===END===\n"
    doc = parse(source)
    for key in ("X", "Y", "N"):
        a = _find_assignment(doc, key)
        assert a.was_quoted is not None, (
            f"Assignment {key!r} from parsed source must have non-None was_quoted; "
            "this is the §4.5 fallback-discipline precondition for deleting "
            "the regex fallback in emitter.py."
        )
