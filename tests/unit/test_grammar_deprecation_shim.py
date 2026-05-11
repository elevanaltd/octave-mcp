"""Tests for the octave_mcp.core.grammar deprecation contract.

History:
- SR1-T1 Step 1 (PR #393) relocated the GBNF compiler from
  ``octave_mcp.core.grammar`` to ``octave_mcp.core.grammar_compiler.gbnf``
  and installed a transitional shim at ``octave_mcp.core.grammar`` (a
  flat ``.py`` module) that re-exported the public API and emitted a
  ``DeprecationWarning`` on import.

- SR1-T1 Step 2 (this PR) replaces that flat module with the
  ``octave_mcp.core.grammar`` package required by ADR-0006 §2.2. The
  package's legitimate, encouraged exports are ``parse`` and
  ``parse_with_warnings`` (the unified front-door per ADR §73), and
  importing them MUST NOT emit a ``DeprecationWarning`` — they are not
  deprecated.

  The deprecated GBNF symbols (``compile_document_grammar`` and
  ``emit_grammar_for_schema``) remain reachable through the
  ``core.grammar`` namespace for backward compatibility, but are now
  resolved lazily via PEP 562 module ``__getattr__``. Attribute access
  emits a ``DeprecationWarning`` and returns the symbol from
  ``grammar_compiler.gbnf``. Symbol identity (``is``) is preserved so
  downstream monkey-patches and identity checks continue to work.

These tests pin both halves of that contract.
"""

from __future__ import annotations

import warnings


def test_importing_parse_from_new_package_does_not_warn() -> None:
    """The legitimate front-door (parse / parse_with_warnings) MUST NOT warn.

    ADR-0006 §73 makes ``from octave_mcp.core.grammar import parse`` the
    encouraged path. Emitting a DeprecationWarning here would spam every
    new consumer; the warning is reserved for the legacy GBNF symbols.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        # Re-import fresh so any module-load side effects would surface.
        import importlib

        import octave_mcp.core.grammar as grammar_pkg

        importlib.reload(grammar_pkg)
        from octave_mcp.core.grammar import (  # noqa: F401  (import is the assertion)
            parse,
            parse_with_warnings,
        )

    deprecation = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert not deprecation, (
        "Importing the legitimate front-door symbols from octave_mcp.core.grammar "
        "must NOT emit a DeprecationWarning. "
        f"Got: {[str(w.message) for w in deprecation]}"
    )


def test_accessing_deprecated_gbnf_symbol_emits_deprecation_warning() -> None:
    """Lazy attribute access for legacy GBNF symbols MUST warn."""
    import octave_mcp.core.grammar as grammar_pkg

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _ = grammar_pkg.compile_document_grammar  # triggers __getattr__

    deprecation = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert deprecation, (
        "Accessing octave_mcp.core.grammar.compile_document_grammar must emit a "
        f"DeprecationWarning, got: {[str(w.message) for w in caught]}"
    )
    message = str(deprecation[0].message)
    assert (
        "octave_mcp.core.grammar_compiler.gbnf" in message
    ), "Deprecation message must reference the new GBNF location"
    assert "#382" in message, "Deprecation message must reference issue #382"


def test_from_import_of_deprecated_gbnf_symbol_emits_warning() -> None:
    """``from octave_mcp.core.grammar import compile_document_grammar`` MUST warn.

    The ``from ... import name`` statement resolves ``name`` via the same
    attribute-lookup machinery that triggers PEP 562 ``__getattr__`` when
    ``name`` is not bound at module-load time. This test explicitly pins
    that the legacy GBNF symbols emit a ``DeprecationWarning`` whether
    they are reached via attribute access or via a ``from ... import``
    statement. (TMG review of PR #394 requested this coverage.)
    """
    import importlib
    import sys

    # Force a fresh resolution by evicting any cached symbol bindings.
    sys.modules.pop("octave_mcp.core.grammar", None)
    importlib.import_module("octave_mcp.core.grammar")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        from octave_mcp.core.grammar import (  # noqa: F401
            compile_document_grammar,
        )

    deprecation = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert deprecation, (
        "`from octave_mcp.core.grammar import compile_document_grammar` must emit "
        f"a DeprecationWarning, got: {[str(w.message) for w in caught]}"
    )
    message = str(deprecation[0].message)
    assert "octave_mcp.core.grammar_compiler.gbnf" in message
    assert "#382" in message


def test_deprecated_symbols_are_identical_to_new_path() -> None:
    """The package shim must re-export, not re-implement (identity preserved)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        import octave_mcp.core.grammar as grammar_pkg
        from octave_mcp.core.grammar_compiler import gbnf as new_path

        assert grammar_pkg.compile_document_grammar is new_path.compile_document_grammar
        assert grammar_pkg.emit_grammar_for_schema is new_path.emit_grammar_for_schema


def test_unknown_attribute_raises_attribute_error() -> None:
    """PEP 562 __getattr__ must still raise AttributeError for unknown names."""
    import octave_mcp.core.grammar as grammar_pkg

    try:
        _ = grammar_pkg.this_symbol_does_not_exist  # type: ignore[attr-defined]
    except AttributeError:
        return
    raise AssertionError(
        "Accessing an unknown attribute on octave_mcp.core.grammar must raise " "AttributeError, not silently succeed."
    )
