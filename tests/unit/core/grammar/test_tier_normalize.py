"""Tests for the centralised TIER_NORMALIZATION audit channel.

ADR-0006 SR1-T1 Step 3 — centralises TIER_NORMALIZATION logging across
lexer/parser/emitter/repair into a single channel exposed at
``octave_mcp.core.grammar.tier_normalize``.

Design references:
- ``docs/adr/adr-0006-sr1-t1-grammar-core-design.md`` §3 row 3 (centralisation),
  §3a (reconciler bridge + 8/2 split), §4.3 (xfail flip table), §4.5 (G1+G2).

Two surfaces are pinned here:

* ``log_repair(repair_log, rule_id, before, after, *, safe, semantics_changed)``
  — single precise entry point. Appends a ``TIER_NORMALIZATION`` entry to
  the supplied ``RepairLog``.
* ``reconcile_canonical_emission(repair_log, baseline_bytes, canonical_bytes)``
  — reconciler bridge. Emits a single coarse-grained ``TIER_NORMALIZATION``
  entry IFF baseline ≠ canonical AND no precise ``TIER_NORMALIZATION``
  entries exist in the log. Self-deprecates when precise upstream
  instrumentation (Sprint 3+ trivia / new lexer triple-quote W-code) lands.

The reconciler MUST NOT fabricate corrections (I3 MIRROR_CONSTRAINT) and
MUST NOT change semantics (I1 SYNTACTIC_FIDELITY). It only annotates an
already-existing diff with an audit receipt (I4 TRANSFORM_AUDITABILITY).
"""

from __future__ import annotations

from octave_mcp.core.repair_log import RepairLog, RepairTier


def _empty_log() -> RepairLog:
    return RepairLog(repairs=[])


# ---------------------------------------------------------------------------
# Module API surface
# ---------------------------------------------------------------------------


def test_tier_normalize_module_exposes_log_repair() -> None:
    """The module MUST export ``log_repair`` as the precise entry point."""
    from octave_mcp.core.grammar import tier_normalize

    assert hasattr(tier_normalize, "log_repair")
    assert callable(tier_normalize.log_repair)


def test_tier_normalize_module_exposes_reconcile_canonical_emission() -> None:
    """The module MUST export ``reconcile_canonical_emission`` for the bridge."""
    from octave_mcp.core.grammar import tier_normalize

    assert hasattr(tier_normalize, "reconcile_canonical_emission")
    assert callable(tier_normalize.reconcile_canonical_emission)


def test_tier_normalize_exposes_stable_rule_ids() -> None:
    """Stable rule IDs MUST be exposed for the three normalisation classes
    plus the generic reconciler entry. I4 requires stable identifiers so
    consumers can pattern-match on rule_id across releases."""
    from octave_mcp.core.grammar import tier_normalize

    # Precise (was_quoted-driven)
    assert isinstance(tier_normalize.RULE_IDENTIFIER_DEQUOTE, str)
    assert tier_normalize.RULE_IDENTIFIER_DEQUOTE
    # Reconciler bridge entries
    assert isinstance(tier_normalize.RULE_RECONCILE_CANONICAL, str)
    assert tier_normalize.RULE_RECONCILE_CANONICAL


# ---------------------------------------------------------------------------
# log_repair semantics
# ---------------------------------------------------------------------------


def test_log_repair_appends_normalization_entry() -> None:
    """log_repair MUST append exactly one entry with tier=NORMALIZATION."""
    from octave_mcp.core.grammar import tier_normalize

    log = _empty_log()
    tier_normalize.log_repair(
        log,
        tier_normalize.RULE_IDENTIFIER_DEQUOTE,
        before='TYPE::"SPEC"',
        after="TYPE::SPEC",
    )

    assert len(log.repairs) == 1
    entry = log.repairs[0]
    assert entry.rule_id == tier_normalize.RULE_IDENTIFIER_DEQUOTE
    assert entry.tier is RepairTier.NORMALIZATION
    assert entry.before == 'TYPE::"SPEC"'
    assert entry.after == "TYPE::SPEC"


def test_log_repair_default_safe_true_semantics_unchanged() -> None:
    """Normalisations are by definition syntax-altering, NOT semantics-altering
    (per I1 SYNTACTIC_FIDELITY). Defaults MUST reflect this."""
    from octave_mcp.core.grammar import tier_normalize

    log = _empty_log()
    tier_normalize.log_repair(
        log,
        tier_normalize.RULE_IDENTIFIER_DEQUOTE,
        before='"x"',
        after="x",
    )

    entry = log.repairs[0]
    assert entry.safe is True
    assert entry.semantics_changed is False


def test_log_repair_safe_and_semantics_changed_overridable() -> None:
    """Callers MUST be able to override safe/semantics_changed for edge cases
    (e.g. boundary-condition normalisations that lose information)."""
    from octave_mcp.core.grammar import tier_normalize

    log = _empty_log()
    tier_normalize.log_repair(
        log,
        tier_normalize.RULE_RECONCILE_CANONICAL,
        before="a",
        after="b",
        safe=False,
        semantics_changed=True,
    )

    entry = log.repairs[0]
    assert entry.safe is False
    assert entry.semantics_changed is True


# ---------------------------------------------------------------------------
# reconcile_canonical_emission semantics
# ---------------------------------------------------------------------------


def test_reconciler_noops_when_bytes_match() -> None:
    """If baseline == canonical there is NO transformation to log.
    I3 MIRROR_CONSTRAINT — reflect only present; do not fabricate."""
    from octave_mcp.core.grammar import tier_normalize

    log = _empty_log()
    tier_normalize.reconcile_canonical_emission(
        log,
        baseline_bytes="===A===\nKEY::VALUE\n===END===\n",
        canonical_bytes="===A===\nKEY::VALUE\n===END===\n",
    )

    assert log.repairs == []


def test_reconciler_emits_bridge_entry_when_no_precise_entries() -> None:
    """If baseline ≠ canonical AND no precise NORMALIZATION entries exist,
    the reconciler bridges the audit gap with exactly ONE coarse entry."""
    from octave_mcp.core.grammar import tier_normalize

    log = _empty_log()
    baseline = '===A===\nKEY::""""""\n===END===\n'
    canonical = '===A===\nKEY::""\n===END===\n'

    tier_normalize.reconcile_canonical_emission(log, baseline, canonical)

    assert len(log.repairs) == 1
    entry = log.repairs[0]
    assert entry.rule_id == tier_normalize.RULE_RECONCILE_CANONICAL
    assert entry.tier is RepairTier.NORMALIZATION
    assert entry.before == baseline
    assert entry.after == canonical


def test_reconciler_dedups_against_precise_normalization_entries() -> None:
    """If a precise NORMALIZATION entry already accounts for the diff, the
    reconciler MUST NOT emit a second entry (no double-counting)."""
    from octave_mcp.core.grammar import tier_normalize

    log = _empty_log()
    # Precise precise entry pre-existing (e.g. identifier-dequote at emit)
    tier_normalize.log_repair(
        log,
        tier_normalize.RULE_IDENTIFIER_DEQUOTE,
        before='TYPE::"SPEC"',
        after="TYPE::SPEC",
    )
    assert len(log.repairs) == 1

    # Reconciler is invoked with a non-empty diff; MUST NOT add a second entry.
    tier_normalize.reconcile_canonical_emission(
        log,
        baseline_bytes='===A===\nTYPE::"SPEC"\n===END===\n',
        canonical_bytes="===A===\nTYPE::SPEC\n===END===\n",
    )

    assert len(log.repairs) == 1
    assert log.repairs[0].rule_id == tier_normalize.RULE_IDENTIFIER_DEQUOTE


def test_reconciler_ignores_non_normalization_entries_for_dedup() -> None:
    """The reconciler's de-dup check looks at TIER_NORMALIZATION entries only.
    Schema-repair / forbidden entries do NOT account for a normalisation diff
    and MUST NOT suppress the bridge."""
    from octave_mcp.core.grammar import tier_normalize

    log = _empty_log()
    # A non-NORMALIZATION entry (e.g. schema repair)
    log.add(
        rule_id="W_SCHEMA_REPAIR_ENUM_CASEFOLD",
        before="active",
        after="ACTIVE",
        tier=RepairTier.REPAIR,
    )

    tier_normalize.reconcile_canonical_emission(
        log,
        baseline_bytes='===A===\nKEY::""""""\n===END===\n',
        canonical_bytes='===A===\nKEY::""\n===END===\n',
    )

    # The pre-existing REPAIR entry stays + reconciler appends ONE
    # NORMALIZATION bridge entry.
    assert len(log.repairs) == 2
    rule_ids = [e.rule_id for e in log.repairs]
    assert tier_normalize.RULE_RECONCILE_CANONICAL in rule_ids
    normalization_entries = [e for e in log.repairs if e.tier is RepairTier.NORMALIZATION]
    assert len(normalization_entries) == 1
