"""Identity-equivalence tests for the SR1-T1 Step 2 grammar entry seam.

ADR-0006 SR1-T1 Step 2 installs ``octave_mcp.core.grammar`` as the
front-door package for the unified parse pipeline. ``entry.parse`` is an
identity wrapper that delegates to ``octave_mcp.core.parser.parse`` (and
``parse_with_warnings``) so that future steps (TIER_NORMALIZATION
centralisation, visitor extraction, regex-constant deletion) can be
injected at a single chokepoint without touching call sites.

This test locks the wrapper as an identity contract: for any input, the
new path MUST produce a document equal-by-comparison to the legacy path,
and the function objects MUST be the same callable (re-export, not
re-implementation).
"""

from __future__ import annotations

import pytest

from octave_mcp.core import parser as legacy_parser
from octave_mcp.core.grammar import parse as new_parse
from octave_mcp.core.grammar import parse_with_warnings as new_parse_with_warnings

# A small, representative corpus of OCTAVE documents.  The identity
# guarantee must hold for every shape the parser supports, not just the
# trivial case.
_CORPUS: list[str] = [
    # Minimal envelope
    "===DOC===\nKEY::value\n===END===\n",
    # Envelope with META block
    '===DOC===\nMETA:\n  TYPE::TEST\n  VERSION::"1.0"\nBODY::content\n===END===\n',
    # Section with list operator
    "===DOC===\n§1::SECTION\n  ITEMS::[a, b, c]\n===END===\n",
    # YAML frontmatter (parser strips it internally)
    "---\ntitle: example\n---\n===DOC===\nKEY::value\n===END===\n",
]


@pytest.mark.parametrize("source", _CORPUS, ids=range(len(_CORPUS)))
def test_grammar_parse_equals_parser_parse(source: str) -> None:
    """grammar.parse(x) MUST equal parser.parse(x) for every x in corpus."""
    legacy_doc = legacy_parser.parse(source)
    new_doc = new_parse(source)
    assert new_doc == legacy_doc, (
        "core.grammar.parse must produce a document equal to "
        "core.parser.parse for identical input (Step 2 identity wrapper)."
    )


@pytest.mark.parametrize("source", _CORPUS, ids=range(len(_CORPUS)))
def test_grammar_parse_with_warnings_equals_parser_parse_with_warnings(
    source: str,
) -> None:
    """grammar.parse_with_warnings must match parser.parse_with_warnings."""
    legacy_doc, legacy_warnings = legacy_parser.parse_with_warnings(source)
    new_doc, new_warnings = new_parse_with_warnings(source)
    assert new_doc == legacy_doc
    assert new_warnings == legacy_warnings


def test_grammar_parse_is_identical_callable_to_parser_parse() -> None:
    """The wrapper MUST re-export the legacy callable, not re-implement it.

    Identity (``is``) preservation guarantees that monkey-patches,
    ``functools.lru_cache`` decorations, and ``isinstance`` checks against
    the function object continue to work across the seam.
    """
    assert new_parse is legacy_parser.parse
    assert new_parse_with_warnings is legacy_parser.parse_with_warnings
