"""ADR-0006 SR1-T1 Step 6 — validator surface collapse (R2 closure).

Regression fences for the validator-surface collapse documented in
``docs/adr/adr-0006-sr1-t1-grammar-core-design.md`` §3 row 6 and §2.2:

* ``core/schema.py`` is DELETED — was a thin delegator. No shim retained.
* Module-level ``validate()`` is REMOVED from ``core/validator.py``.
  The canonical surface is the class-based API: ``Validator().validate(doc)``.
* ``validate_frontmatter`` is RELOCATED to ``core/grammar/entry.py`` as
  a parse-stage hook.
* ``class Validator`` is a structural ``Visitor[None]`` (per design §3 row 6).

This file is the R2 closure witness: if any of these regress, R2
(``validator_drift_multiple_validators``) has been re-introduced.
"""

from __future__ import annotations

import pytest


class TestSchemaModuleDeleted:
    """``core/schema.py`` is deleted; no shim retained (design §2.2)."""

    def test_schema_module_import_raises(self):
        """``from octave_mcp.core.schema import X`` raises ModuleNotFoundError."""
        with pytest.raises(ModuleNotFoundError):
            import octave_mcp.core.schema  # noqa: F401


class TestModuleLevelValidateRemoved:
    """Module-level ``validate()`` is removed from ``core/validator.py``.

    The canonical surface is the class-based API: ``Validator().validate(doc)``.
    """

    def test_no_module_level_validate(self):
        """``octave_mcp.core.validator`` does not expose a module-level ``validate``."""
        import octave_mcp.core.validator as validator_module

        assert not hasattr(validator_module, "validate"), (
            "core/validator.py must not expose module-level validate(); "
            "use Validator().validate(doc) instead. See ADR-0006 §3 row 6."
        )

    def test_class_validator_still_exposes_validate_method(self):
        """``Validator.validate`` (the instance method) remains the canonical surface."""
        from octave_mcp.core.validator import Validator

        assert callable(getattr(Validator, "validate", None))


class TestValidateFrontmatterRelocated:
    """``validate_frontmatter`` lives at ``core/grammar/entry.py`` (parse-stage hook)."""

    def test_validate_frontmatter_importable_from_grammar_entry(self):
        """``from octave_mcp.core.grammar.entry import validate_frontmatter`` works."""
        from octave_mcp.core.grammar.entry import validate_frontmatter

        assert callable(validate_frontmatter)

    def test_validate_frontmatter_re_exported_from_grammar_package(self):
        """The grammar package re-exports validate_frontmatter for callers."""
        from octave_mcp.core.grammar import validate_frontmatter

        assert callable(validate_frontmatter)

    def test_validate_frontmatter_not_on_validator_module(self):
        """The legacy location ``octave_mcp.core.validator.validate_frontmatter`` is gone.

        Design §3 row 6: ``validate_frontmatter()`` moves to ``grammar/entry.py``.
        No shim retained — direct relocation.
        """
        import octave_mcp.core.validator as validator_module

        assert not hasattr(validator_module, "validate_frontmatter"), (
            "validate_frontmatter must live at octave_mcp.core.grammar.entry, "
            "not octave_mcp.core.validator. See ADR-0006 §3 row 6."
        )


class TestValidatorIsVisitorNone:
    """``class Validator`` is a structural ``Visitor[None]`` (design §3 row 6)."""

    def test_validator_instance_is_visitor_protocol(self):
        """``isinstance(Validator(), Visitor)`` is True (runtime-checkable Protocol)."""
        from octave_mcp.core.grammar.visitor import Visitor
        from octave_mcp.core.validator import Validator

        instance = Validator()
        assert isinstance(instance, Visitor), (
            "Validator must structurally satisfy Visitor[None] protocol "
            "(visit_assignment, visit_block, visit_section, visit_document, visit). "
            "See ADR-0006 §3 row 6 + §2.2."
        )

    def test_validator_has_visit_methods(self):
        """``Validator`` exposes all four typed visit methods plus the dispatcher."""
        from octave_mcp.core.validator import Validator

        for method_name in ("visit_assignment", "visit_block", "visit_section", "visit_document", "visit"):
            assert callable(
                getattr(Validator, method_name, None)
            ), f"Validator missing required visitor method: {method_name}"
