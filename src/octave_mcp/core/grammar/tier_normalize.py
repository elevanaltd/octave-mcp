"""Centralised TIER_NORMALIZATION audit channel (ADR-0006 SR1-T1 Step 3).

This module is the SINGLE seam through which every ``TIER_NORMALIZATION``
event reaches the :class:`octave_mcp.core.repair_log.RepairLog`. The
design intent (per ``docs/adr/adr-0006-sr1-t1-grammar-core-design.md``
§3 row 3) is to collapse the four pre-Step-3 logging surfaces
(lexer W002 path, parser whitespace normalisation, emitter
``FormatOptions`` strip / blank-line repairs, and ``repair.py``'s
TIER_NORMALIZATION comment-only acknowledgement) into one canonical
channel so that I4 (TRANSFORM_AUDITABILITY) holds at boundary cases.

Two public surfaces are exposed:

* :func:`log_repair` — precise entry point. Called from the emitter
  (was_quoted-driven identifier dequoting), the lexer (W002 / ASCII→Unicode),
  the parser (whitespace normalisation), and any future site that
  produces a deterministic, value-typed normalisation event.

* :func:`reconcile_canonical_emission` — reconciler bridge (per
  design §3a). Called from :mod:`octave_mcp.mcp.write` after canonical
  emission. Emits a single coarse-grained ``TIER_NORMALIZATION`` entry
  IFF ``baseline_bytes != canonical_bytes`` AND no precise
  ``TIER_NORMALIZATION`` entries exist on the supplied log. The bridge
  is **temporary and self-deprecating** — once Sprint 3+ trivia
  population (G1) and the new triple-quote-collapse lexer W-code land,
  the precise loggers will cover their respective diffs, the
  de-duplication precondition will fail, and the reconciler no-ops
  without any code change.

The de-duplication check distinguishes ``TIER_NORMALIZATION`` entries
from ``TIER_REPAIR`` entries: a schema-driven ``TIER_REPAIR`` (e.g.
enum casefold, type coercion) does NOT account for a normalisation diff
and MUST NOT suppress the bridge. The bridge fires when **no** prior
``TIER_NORMALIZATION`` entry exists.

Design invariants (binding):
* I1 (SYNTACTIC_FIDELITY): this module never changes canonical bytes;
  it only records receipts of changes already produced upstream.
* I3 (MIRROR_CONSTRAINT): the reconciler MUST NOT fabricate a record
  when ``baseline == canonical`` (early return).
* I4 (TRANSFORM_AUDITABILITY): every TIER_NORMALIZATION decision routed
  through this module produces a stable-rule_id receipt on the log.

See ``docs/adr/adr-0006-sr1-t1-grammar-core-design.md`` §3 row 3, §3a
("Reconciler bridge pattern"), §4.3 (xfail flip table), §4.5 (G1/G2).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

from octave_mcp.core.repair_log import RepairLog, RepairTier

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Stable rule IDs
# ---------------------------------------------------------------------------
#
# These IDs are stable across releases. Consumers may pattern-match on
# them to discriminate normalisation classes (e.g. analytics, UI
# rendering, downstream audit pipelines). Adding a new rule_id is a
# minor / additive change; renaming or removing an existing rule_id is
# a breaking change and requires a CHANGELOG entry.

RULE_IDENTIFIER_DEQUOTE = "TN_IDENTIFIER_DEQUOTE"
"""Precise: emitter dequoted a string whose ``was_quoted=True`` AND whose
textual shape is identifier-like (type-safe dequoting). Fires once per
dequoting decision inside ``emit_assignment``."""

RULE_RECONCILE_CANONICAL = "TN_RECONCILE_CANONICAL"
"""Reconciler bridge: post-emit baseline-vs-canonical comparison surfaced
a diff that no precise upstream logger accounted for. Coarse-grained
audit receipt covering blank-line stripping (until Sprint 3+ trivia
population lands) and triple-quote collapse (until the new lexer W-code
lands)."""

RULE_INLINE_MAP_TO_BLOCK = "TN_INLINE_MAP_TO_BLOCK"
"""GH#487 Q2 (#440) DEFERRED_CANONICALIZATION: changes-mode synthesised a
canonical BLOCK node for a nested dict value instead of the legacy nested
``InlineMap`` coercion (which re-parsed to E_NESTED_INLINE_MAP). Fires once per
nested dict synthesised, recording the structural id of the key. BLOCK is the
sole canonical nested form (Wall M1); the surfaced audit atom is
``TRANSFORM::INLINE_MAP_TO_BLOCK`` (I4 TRANSFORM_AUDITABILITY)."""


# ---------------------------------------------------------------------------
# Active-log context (thread / async safe)
# ---------------------------------------------------------------------------
#
# Some loggers (notably the emitter) operate inside pure functions that
# do not currently thread a ``RepairLog`` through their signature. A
# ``ContextVar`` is the minimal-intervention seam (per MIP_BUILD
# "could we achieve same outcome with simpler means?"): callers stash
# the active log into the context before invoking the pipeline, and
# precise loggers read it back at the point of the normalisation
# decision. The ContextVar is reset on exit via the ``active`` context
# manager — no leakage between requests / tasks.

_active_log: ContextVar[RepairLog | None] = ContextVar("tier_normalize_active_log", default=None)


def get_active_log() -> RepairLog | None:
    """Return the currently-active ``RepairLog`` (or ``None`` if none).

    Precise instrumentation sites in the emitter (and any future caller
    that cannot thread a ``RepairLog`` through its signature without
    breaking the public API) consult this accessor to obtain the
    sink for their normalisation receipt. When ``None`` (the default
    outside the :func:`active` context manager), instrumentation
    sites short-circuit to a no-op — preserving today's behaviour for
    callers that don't opt in.
    """
    return _active_log.get()


@contextmanager
def active(log: RepairLog) -> Iterator[RepairLog]:
    """Bind ``log`` as the active TIER_NORMALIZATION sink for this context.

    Use as::

        with tier_normalize.active(repair_log):
            canonical = emit(doc)

    Precise instrumentation inside the pipeline will append entries to
    ``log`` while the context is active. On exit the previous binding
    is restored — supporting nested invocations without leakage.
    """
    token = _active_log.set(log)
    try:
        yield log
    finally:
        _active_log.reset(token)


# ---------------------------------------------------------------------------
# log_repair — precise entry point
# ---------------------------------------------------------------------------


def log_repair(
    log: RepairLog,
    rule_id: str,
    before: str,
    after: str,
    *,
    safe: bool = True,
    semantics_changed: bool = False,
) -> None:
    """Append a precise ``TIER_NORMALIZATION`` entry to ``log``.

    This is the canonical entry point for every TIER_NORMALIZATION
    audit event in the codebase. Lexer, parser, emitter, and repair
    binding sites all route through here so I4 (TRANSFORM_AUDITABILITY)
    is enforced at a single seam.

    Args:
        log: The RepairLog to mutate. (See also :func:`active` /
            :func:`get_active_log` for the ContextVar-based seam that
            lets pipeline-internal sites obtain the sink without
            threading it through their signatures.)
        rule_id: Stable identifier for the normalisation class
            (e.g. ``RULE_IDENTIFIER_DEQUOTE``). New rule IDs MUST be
            declared as module-level constants and documented.
        before: Source-side representation prior to normalisation
            (e.g. ``'TYPE::"SPEC"'``).
        after: Canonical-side representation post-normalisation
            (e.g. ``"TYPE::SPEC"``).
        safe: Whether the normalisation is information-preserving on
            the semantic plane (per I1 SYNTACTIC_FIDELITY). Defaults
            to True — normalisations are by definition syntax-altering
            but semantics-preserving. Override only for edge cases
            (boundary-condition lossy normalisations) and pair with
            ``semantics_changed=True``.
        semantics_changed: Whether the normalisation alters semantics.
            Defaults to False. Setting this True without setting
            ``safe=False`` is a self-contradiction and reviewers
            should reject such records.
    """
    log.add(
        rule_id=rule_id,
        before=before,
        after=after,
        tier=RepairTier.NORMALIZATION,
        safe=safe,
        semantics_changed=semantics_changed,
    )


def log_repair_if_active(
    rule_id: str,
    before: str,
    after: str,
    *,
    safe: bool = True,
    semantics_changed: bool = False,
) -> None:
    """Log via the active context if present; no-op otherwise.

    Convenience wrapper used by pipeline-internal sites (notably the
    emitter) that cannot thread a ``RepairLog`` through their signature
    without breaking the public API. When no :func:`active` context is
    in scope, the call is a no-op — preserving today's behaviour for
    callers that don't opt in to the audit channel.
    """
    log = _active_log.get()
    if log is None:
        return
    log_repair(
        log,
        rule_id,
        before,
        after,
        safe=safe,
        semantics_changed=semantics_changed,
    )


# ---------------------------------------------------------------------------
# reconcile_canonical_emission — reconciler bridge (§3a)
# ---------------------------------------------------------------------------


def reconcile_canonical_emission(
    log: RepairLog,
    baseline_bytes: str,
    canonical_bytes: str,
) -> None:
    """Reconciler bridge: emit a single coarse-grained TIER_NORMALIZATION
    entry IFF ``baseline_bytes != canonical_bytes`` AND no precise
    ``TIER_NORMALIZATION`` entries exist on ``log``.

    Per design §3a, this is a temporary, self-deprecating mechanism that
    closes the audit-cardinality gap for 2 of 10 strict-xfailed fixtures
    (``coverage/spec_full.oct.md`` blank-line stripping;
    ``symmetry/empty_triple_quoted.oct.md`` triple-quote collapse) until
    upstream precise instrumentation (Sprint 3+ trivia population,
    new lexer triple-quote W-code) lands. When precise loggers cover
    their respective diffs, the de-duplication precondition fails and
    this function no-ops — no code change required.

    De-duplication discriminant: the check looks at the ``tier`` field
    of existing log entries. Only ``RepairTier.NORMALIZATION`` entries
    suppress the bridge. ``TIER_REPAIR`` (schema repairs) and
    ``TIER_FORBIDDEN`` entries do NOT account for a normalisation diff
    and so do NOT suppress the bridge — they are independent dimensions.

    Args:
        log: The RepairLog to mutate. Same instance threaded through
            the emit pipeline; the dedup check is local to this log.
        baseline_bytes: Source bytes the caller intended to write
            (post any pre-processing / repair, but pre canonical emit).
        canonical_bytes: Canonical bytes produced by the emitter.

    Returns:
        None. Side effect: optional single entry appended to ``log``.
    """
    if baseline_bytes == canonical_bytes:
        # I3 MIRROR_CONSTRAINT: no diff, no receipt.
        return

    for entry in log.repairs:
        if entry.tier is RepairTier.NORMALIZATION:
            # Precise upstream logger already accounted for the diff;
            # bridge no-ops to avoid double-counting.
            return

    log_repair(
        log,
        RULE_RECONCILE_CANONICAL,
        before=baseline_bytes,
        after=canonical_bytes,
    )


__all__ = [
    "RULE_IDENTIFIER_DEQUOTE",
    "RULE_INLINE_MAP_TO_BLOCK",
    "RULE_RECONCILE_CANONICAL",
    "active",
    "get_active_log",
    "log_repair",
    "log_repair_if_active",
    "reconcile_canonical_emission",
]
