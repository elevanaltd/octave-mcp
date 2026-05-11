"""Unified parse front-door for OCTAVE-MCP (ADR-0006 SR1-T1 Step 2).

This module is an *identity wrapper* around :mod:`octave_mcp.core.parser`.
It exists to establish a single chokepoint at ``octave_mcp.core.grammar``
through which all callers (``mcp/validate.py``, ``mcp/write.py``, future
visitors) reach the parse pipeline. Later SR1-T1 steps inject
``TIER_NORMALIZATION`` logging (Step 3), CST visitor protocol (Step 4),
and emitter unification (Step 5) at this same seam without touching call
sites.

**Identity contract.** ``entry.parse`` and ``entry.parse_with_warnings``
are the *same callable objects* as ``octave_mcp.core.parser.parse`` and
``octave_mcp.core.parser.parse_with_warnings`` respectively. Re-exporting
the callable (rather than wrapping it in a new function body) preserves
``functools`` decorations, monkey-patches, and ``is``-identity checks
across the seam. This is asserted by
``tests/unit/core/grammar/test_entry.py``.

**No behaviour change.** Step 2 is a pure refactor. No logging,
normalization, or error-handling additions live here — those land at
later, gated steps in the migration plan
(``docs/adr/adr-0006-sr1-t1-grammar-core-design.md`` §3).
"""

from __future__ import annotations

from octave_mcp.core.parser import parse, parse_with_warnings

__all__ = ["parse", "parse_with_warnings"]
