"""Tests for the octave_mcp.core.grammar deprecation shim (SR1-T1 Step 1).

The shim preserves backward compatibility for external importers of
``octave_mcp.core.grammar`` after the module was relocated to
``octave_mcp.core.grammar_compiler.gbnf`` per ADR-0006 SR1-T1 Step 1
(PR #393, CE follow-up).

These tests assert that:

1. Importing the deprecated path emits a ``DeprecationWarning``.
2. The public API symbols are accessible from both the old and new paths.
3. The symbols are the SAME object (re-exports, not re-implementations) so
   downstream identity checks (``is``, monkey-patching) keep working.
"""

import importlib
import sys
import warnings


def _reload_deprecated_module():
    """Force a fresh import so the warning is re-emitted on each test."""
    sys.modules.pop("octave_mcp.core.grammar", None)
    return importlib.import_module("octave_mcp.core.grammar")


def test_importing_deprecated_path_emits_deprecation_warning():
    """Importing octave_mcp.core.grammar must emit a DeprecationWarning."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _reload_deprecated_module()

    deprecation_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert deprecation_warnings, (
        "expected a DeprecationWarning when importing octave_mcp.core.grammar, "
        f"got: {[str(w.message) for w in caught]}"
    )
    message = str(deprecation_warnings[0].message)
    assert "octave_mcp.core.grammar" in message
    assert "octave_mcp.core.grammar_compiler.gbnf" in message
    assert "#382" in message


def test_public_api_accessible_from_both_paths():
    """compile_document_grammar and emit_grammar_for_schema must resolve via both paths."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        deprecated = _reload_deprecated_module()

    from octave_mcp.core.grammar_compiler import gbnf as new_path

    for symbol in ("compile_document_grammar", "emit_grammar_for_schema"):
        assert hasattr(deprecated, symbol), f"deprecated path missing {symbol}"
        assert hasattr(new_path, symbol), f"new path missing {symbol}"


def test_symbols_are_identical_objects_across_paths():
    """The shim must re-export, not re-implement, so identity is preserved."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        deprecated = _reload_deprecated_module()

    from octave_mcp.core.grammar_compiler import gbnf as new_path

    assert (
        deprecated.compile_document_grammar is new_path.compile_document_grammar
    ), "compile_document_grammar must be the same object on old and new paths"
    assert (
        deprecated.emit_grammar_for_schema is new_path.emit_grammar_for_schema
    ), "emit_grammar_for_schema must be the same object on old and new paths"
