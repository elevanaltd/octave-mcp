"""Unified parse front-door for OCTAVE-MCP (ADR-0006 SR1-T1 Step 2).

This module is an *identity wrapper* around :mod:`octave_mcp.core.parser`.
It exists to establish a single chokepoint at ``octave_mcp.core.grammar``
through which all callers (``mcp/validate.py``, ``mcp/write.py``, future
visitors) reach the parse pipeline. Later SR1-T1 steps inject
``TIER_NORMALIZATION`` logging (Step 3), CST visitor protocol (Step 4),
and emitter unification (Step 5) at this same seam without touching call
sites.

**Identity contract.** ``entry.parse``, ``entry.parse_with_warnings``,
and ``entry.ParserError`` are the *same objects* as their counterparts in
:mod:`octave_mcp.core.parser`. Re-exporting (rather than wrapping or
subclassing) preserves :mod:`functools` decorations, monkey-patches,
``is``-identity checks, and ``except``-clause matching across the seam.
This is asserted by ``tests/unit/core/grammar/test_entry.py``. The
re-export of :class:`ParserError` co-locates the call surface with its
error surface so consumers never need to pierce the seam.

**No behaviour change.** Step 2 is a pure refactor. No logging,
normalization, or error-handling additions live here — those land at
later, gated steps in the migration plan
(``docs/adr/adr-0006-sr1-t1-grammar-core-design.md`` §3).
"""

from __future__ import annotations

from octave_mcp.core.parser import ParserError, parse, parse_with_warnings

__all__ = ["ParserError", "parse", "parse_with_warnings"]
