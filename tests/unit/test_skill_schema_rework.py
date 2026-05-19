"""RED reproducers for PR #444 consolidated rework (GH-428 deepening).

Five reviewer concerns surfaced after the initial GH-428 GREEN landed:

1. **TMG BLOCKED** — ``test_existing_skill_file_validates_no_missing_section_1``
   in ``test_skill_schema.py`` filters warnings for ``W_MISSING_REQUIRED_SECTION``
   only; it silently masks ``W_INCOMPLETE_SECTION_FIELDS``. The skills
   ``gap-ownership`` and ``operating-discipline`` both author an
   ``§5::ANCHOR_KERNEL`` carrying ``TARGET`` and ``GATE`` but omitting
   ``NEVER`` and ``MUST``. The corpus gap is real and currently hidden.

2. **CE CONDITIONAL (a)** — ``schema_extractor._extract_policy`` and its
   helpers (``_parse_string_list``, ``_parse_conditional_required``)
   silently accept malformed POLICY shapes. Per PROD::I4
   TRANSFORM_AUDITABILITY, every transformation MUST be logged with a
   stable code. Malformed REQUIRED_SECTION_IDS / SECTION_CONDITIONAL_REQUIRED
   shapes must emit ``W_MALFORMED_POLICY``.

3. **CE CONDITIONAL (b)** — ``load_builtin_schemas()`` uses builtin-first
   precedence; ``load_schema_by_name()`` uses resources-first (via
   ``get_schema_search_paths`` ordering). Discovery vs validation
   mismatch. Both loaders must agree.

4. **cubic P2 #1** — ``validate.py`` uses the string sentinel
   ``"__schema__"`` to register the full schema for policy-driven walks.
   A document that legitimately authors a section named ``"__schema__"``
   would have its real fields silently excluded from required-field
   coverage. Sentinel must be a non-string structural marker.

5. **cubic P2 #2** — ``validator._validate_section_body_coverage`` walks
   recursively but drops the active section context: when it enters a
   Section's children, ``current_section_key`` resets to None, so nested
   Assignments are not attributed to the enclosing section. Conditional
   warnings can be incorrect when ``SECTION_CONDITIONAL_REQUIRED`` targets
   a section whose required fields live below the top level of that
   section (e.g., directly under the §-header but discovered through a
   nested-children parser shape).

Each test in this module pins the **post-fix** behaviour, and is therefore
RED today.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from octave_mcp.core.parser import parse
from octave_mcp.core.schema_extractor import extract_schema_from_document

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SKILLS_DIR = _REPO_ROOT / ".hestai-sys" / "library" / "skills"


def _validate_content(content: str) -> dict[str, Any]:
    """Validate ``content`` against the SKILL schema through the MCP tool."""
    from octave_mcp.mcp.validate import ValidateTool

    tool = ValidateTool()
    return asyncio.run(tool.execute(content=content, schema="SKILL"))


# ---------------------------------------------------------------------------
# Item 1 — TMG BLOCKED: vacuous assertion + corpus gaps
# ---------------------------------------------------------------------------


class TestItem1AnchorKernelGapPinned:
    """Two on-disk SKILL files miss NEVER + MUST in their ANCHOR_KERNEL."""

    @pytest.mark.parametrize("skill_dirname", ["gap-ownership", "operating-discipline"])
    def test_anchor_kernel_quartet_gap_surfaces_warning(self, skill_dirname: str) -> None:
        """Both files author ANCHOR_KERNEL with TARGET+GATE but no NEVER/MUST.

        Post-fix, the validator surfaces W_INCOMPLETE_SECTION_FIELDS naming
        at least ``NEVER`` and ``MUST`` as the missing quartet members.
        This guards against the gap being silently re-introduced after the
        skill files gain the missing fields (auto-retiring the allowlist).
        """
        skill_path = _SKILLS_DIR / skill_dirname / "SKILL.md"
        if not skill_path.exists():
            pytest.skip(f"{skill_dirname}/SKILL.md not on disk")

        result = _validate_content(skill_path.read_text(encoding="utf-8"))
        warnings = result.get("warnings", []) or []
        incomplete = [w for w in warnings if isinstance(w, dict) and w.get("code") == "W_INCOMPLETE_SECTION_FIELDS"]
        assert incomplete, (
            f"{skill_dirname}/SKILL.md: expected W_INCOMPLETE_SECTION_FIELDS for "
            f"ANCHOR_KERNEL missing NEVER+MUST. Got warnings={warnings!r}"
        )
        joined = " ".join(w.get("message", "") for w in incomplete)
        for needed in ("NEVER", "MUST"):
            assert needed in joined, f"{skill_dirname}: warning should name missing field {needed!r}; got {joined!r}"


# ---------------------------------------------------------------------------
# Item 2 — CE CONDITIONAL (a): W_MALFORMED_POLICY for malformed POLICY shapes
# ---------------------------------------------------------------------------


def _build_schema_from_source(src: str) -> Any:
    doc = parse(src)
    return extract_schema_from_document(doc)


_MALFORMED_REQUIRED_SECTION_IDS_AS_STRING = """\
===BOGUS_SCHEMA===
META:
  TYPE::SCHEMA
  VERSION::"1.0"
POLICY:
  VERSION::"1.0"
  UNKNOWN_FIELDS::WARN
  REQUIRED_SECTION_IDS::"1"
===END===
"""

_MALFORMED_REQUIRED_SECTION_IDS_NONSTRING_ELEMENTS = """\
===BOGUS_SCHEMA===
META:
  TYPE::SCHEMA
  VERSION::"1.0"
POLICY:
  VERSION::"1.0"
  UNKNOWN_FIELDS::WARN
  REQUIRED_SECTION_IDS::[true,null]
===END===
"""

_MALFORMED_SECTION_CONDITIONAL_REQUIRED_NOT_A_BLOCK = """\
===BOGUS_SCHEMA===
META:
  TYPE::SCHEMA
  VERSION::"1.0"
POLICY:
  VERSION::"1.0"
  UNKNOWN_FIELDS::WARN
  SECTION_CONDITIONAL_REQUIRED::"ANCHOR_KERNEL"
===END===
"""


class TestItem2MalformedPolicyEmitsWarning:
    """``W_MALFORMED_POLICY`` stable code for silently-accepted POLICY shapes."""

    @pytest.mark.parametrize(
        "src,probe",
        [
            (_MALFORMED_REQUIRED_SECTION_IDS_AS_STRING, "REQUIRED_SECTION_IDS"),
            (_MALFORMED_REQUIRED_SECTION_IDS_NONSTRING_ELEMENTS, "REQUIRED_SECTION_IDS"),
            (_MALFORMED_SECTION_CONDITIONAL_REQUIRED_NOT_A_BLOCK, "SECTION_CONDITIONAL_REQUIRED"),
        ],
        ids=["required_ids_as_string", "required_ids_nonstring_elements", "conditional_not_a_block"],
    )
    def test_malformed_policy_surfaces_warning(self, src: str, probe: str) -> None:
        schema = _build_schema_from_source(src)
        codes = [w.code for w in schema.warnings]
        assert (
            "W_MALFORMED_POLICY" in codes
        ), f"Expected W_MALFORMED_POLICY for malformed {probe}; got warnings={schema.warnings!r}"
        msgs = " ".join(w.message for w in schema.warnings if w.code == "W_MALFORMED_POLICY")
        assert probe in msgs, f"Warning should mention {probe!r}; got {msgs!r}"


# ---------------------------------------------------------------------------
# Item 3 — CE CONDITIONAL (b): loader precedence alignment (resources-first)
# ---------------------------------------------------------------------------


class TestItem3LoaderPrecedenceAlignment:
    """Both loaders must use resources-first precedence on name collision.

    Post-fix invariant: ``load_builtin_schemas()`` consults the same
    directory list (in the same order) as ``load_schema_by_name()`` so
    discovery and validation cannot disagree on which copy is canonical.
    Resources-first matches the canonical-location precedent set by
    PR #431/#437/#438 for new schemas under
    ``src/octave_mcp/resources/specs/schemas/``.
    """

    def test_loaders_share_directory_list(self) -> None:
        """``load_builtin_schemas`` must consult ``get_schema_search_paths`` directories.

        This is a structural assertion: after the fix, the bulk loader
        must delegate its directory enumeration to ``get_schema_search_paths``
        (same source of truth as ``load_schema_by_name``). We assert by
        checking that for every schema returned by ``load_builtin_schemas``,
        ``load_schema_by_name`` returns the same name. Pre-fix, divergent
        precedence can cause the two to disagree (different files win).
        """
        from octave_mcp.schemas import loader as loader_mod

        # Sanity: builtin module exposes a shared helper used by both surfaces.
        # The helper is introduced as part of the GREEN commit; the test
        # references it via getattr to give a clean RED failure mode.
        helper = getattr(loader_mod, "_canonical_schema_dirs", None)
        assert helper is not None, (
            "load_builtin_schemas must delegate directory enumeration to a "
            "shared helper ``_canonical_schema_dirs`` so discovery and "
            "validation cannot drift. Helper not found on loader module."
        )

        bulk = loader_mod.load_builtin_schemas()
        # For every schema discovered in bulk, by-name lookup must succeed
        # and return the same canonical content (same version).
        for name, schema in bulk.items():
            by_name = loader_mod.load_schema_by_name(name)
            assert by_name is not None, (
                f"load_schema_by_name returned None for {name!r} discovered by "
                f"load_builtin_schemas — loaders disagree on visibility."
            )
            assert by_name.version == schema.version, (
                f"Loader divergence for {name!r}: bulk version={schema.version!r} "
                f"vs by-name version={by_name.version!r}. Both must resolve to the "
                f"same canonical copy (resources-first)."
            )

    def test_loaders_agree_resources_wins_on_collision(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Forced collision: resources copy wins for both loaders."""
        from octave_mcp.schemas import loader as loader_mod

        fake_builtin = tmp_path / "builtin"
        fake_builtin.mkdir()
        (fake_builtin / "collision_fixture.oct.md").write_text(
            "===COLLISION_FIXTURE===\n"
            "META:\n"
            "  TYPE::SCHEMA\n"
            '  VERSION::"BUILTIN"\n'
            "POLICY:\n"
            '  VERSION::"BUILTIN"\n'
            "  UNKNOWN_FIELDS::WARN\n"
            "===END===\n",
            encoding="utf-8",
        )

        fake_resources = tmp_path / "resources_specs_schemas"
        fake_resources.mkdir()
        (fake_resources / "collision_fixture.oct.md").write_text(
            "===COLLISION_FIXTURE===\n"
            "META:\n"
            "  TYPE::SCHEMA\n"
            '  VERSION::"RESOURCES"\n'
            "POLICY:\n"
            '  VERSION::"RESOURCES"\n'
            "  UNKNOWN_FIELDS::WARN\n"
            "===END===\n",
            encoding="utf-8",
        )

        # Post-fix seam: both loaders read directories from the shared helper.
        monkeypatch.setattr(
            loader_mod,
            "_canonical_schema_dirs",
            lambda: [fake_resources, fake_builtin],
            raising=False,
        )

        # ``load_schema_by_name`` reads from ``get_schema_search_paths``;
        # post-fix that function delegates to the same shared helper.
        monkeypatch.setattr(loader_mod, "get_schema_search_paths", lambda: [fake_resources, fake_builtin])

        by_name = loader_mod.load_schema_by_name("COLLISION_FIXTURE")
        bulk = loader_mod.load_builtin_schemas()

        assert by_name is not None, "load_schema_by_name must find COLLISION_FIXTURE"
        assert "COLLISION_FIXTURE" in bulk, f"load_builtin_schemas must surface COLLISION_FIXTURE; got {sorted(bulk)!r}"
        assert (
            by_name.version == "RESOURCES"
        ), f"load_schema_by_name should pick resources-first; got version={by_name.version!r}"
        assert bulk["COLLISION_FIXTURE"].version == "RESOURCES", (
            f"load_builtin_schemas should pick resources-first; got " f"version={bulk['COLLISION_FIXTURE'].version!r}"
        )


# ---------------------------------------------------------------------------
# Item 4 — cubic P2 #1: __schema__ sentinel structural inseparability
# ---------------------------------------------------------------------------


class TestItem4SchemaSentinelStructural:
    """A user-author-able section literally named ``__schema__`` must NOT collide.

    Pre-fix, ``validate.py`` uses the string ``"__schema__"`` as a sentinel
    in ``section_schemas``. ``_check_required_field_coverage`` filters by
    string match (``if section_key == "__schema__": continue``), so any
    real document section whose key happens to be ``__schema__`` has its
    fields treated as the sentinel and skipped — required-field coverage
    is silently weakened.

    Post-fix, the sentinel is a non-string structural object (module-level
    singleton or sentinel ``object()``). A user-author-able section keyed
    ``__schema__`` is, by construction, a distinct key from the sentinel
    and its REQ fields are correctly covered.
    """

    def test_user_block_named___schema___not_collided(self) -> None:
        """A document block literally keyed ``__schema__`` must have its fields counted.

        Pre-fix repro: a Block keyed ``__schema__`` whose only child is
        ``REQUIRED_FIELD::x`` produces a single ``section_schemas`` entry
        keyed ``"__schema__"``. ``_check_required_field_coverage`` filters
        by string match (``if section_key == "__schema__": continue``) and
        drops that entry, so ``REQUIRED_FIELD`` is reported as missing
        even though it IS present in the document.

        Post-fix: the sentinel is a non-string structural marker — the
        user block's string key ``"__schema__"`` cannot equal the sentinel
        object, so its fields are correctly seen as covered and the
        spurious E003 disappears.
        """
        from octave_mcp.core.holographic import parse_holographic_pattern
        from octave_mcp.core.parser import parse as _parse
        from octave_mcp.core.schema_extractor import (
            FieldDefinition,
            PolicyDefinition,
            SchemaDefinition,
        )
        from octave_mcp.mcp.validate import (
            _build_deep_section_schemas,
            _check_required_field_coverage,
        )

        pattern = parse_holographic_pattern('["x"∧REQ→§SELF]')
        schema = SchemaDefinition(
            name="USER_SCHEMA",
            version="1.0",
            policy=PolicyDefinition(
                version="1.0",
                unknown_fields="WARN",
                required_section_ids=["1"],
            ),
            fields={
                "REQUIRED_FIELD": FieldDefinition(name="REQUIRED_FIELD", pattern=pattern),
            },
        )

        # Block whose key is literally ``__schema__``.
        src = (
            "===USER_DOC===\n"
            "META:\n"
            "  TYPE::USER_SCHEMA\n"
            '  VERSION::"1.0"\n'
            "§1::FIRST\n"
            "__schema__:\n"
            "  REQUIRED_FIELD::x\n"
            "===END===\n"
        )
        doc = _parse(src)

        section_schemas = _build_deep_section_schemas(doc, schema)
        errors = _check_required_field_coverage(schema, section_schemas, doc=doc)

        e003 = [e for e in errors if e.code == "E003" and e.field_path == "REQUIRED_FIELD"]
        assert not e003, (
            f"User block literally keyed '__schema__' must not collide with the "
            f"coverage sentinel. REQUIRED_FIELD IS present in the document and must be "
            f"covered. Got errors={errors!r}; section_schemas keys={list(section_schemas)!r}"
        )


# ---------------------------------------------------------------------------
# Item 5 — cubic P2 #2: recursive walker section context drop
# ---------------------------------------------------------------------------


class TestItem5SectionContextThreading:
    """SECTION_CONDITIONAL_REQUIRED must fire for nested (block-shaped) targets.

    The walker today only registers top-level Section keys as buckets.
    When ANCHOR_KERNEL is authored as a nested Block under a §-Section
    (e.g., ``§1::WRAPPER`` then ``ANCHOR_KERNEL:`` block holding the
    quartet), the walker re-enters its inner recursion with
    ``current_section_key=None`` and never registers the Block's key as
    a section_field_keys bucket. The conditional check then silently
    passes because ``"ANCHOR_KERNEL" not in section_field_keys``.

    Post-fix, the walker threads the active section/block context so the
    nested-Block ANCHOR_KERNEL is correctly evaluated against the
    conditional requirement.
    """

    def test_nested_block_anchor_kernel_missing_quartet_fires_warning(self) -> None:
        from octave_mcp.core.parser import parse as _parse
        from octave_mcp.core.schema_extractor import PolicyDefinition, SchemaDefinition
        from octave_mcp.core.validator import Validator

        schema = SchemaDefinition(
            name="X",
            version="1.0",
            policy=PolicyDefinition(
                version="1.0",
                unknown_fields="WARN",
                required_section_ids=[],
                section_conditional_required={"ANCHOR_KERNEL": ["TARGET", "NEVER", "MUST", "GATE"]},
            ),
            fields={},
        )

        src = (
            "===DOC===\n"
            "META:\n"
            "  TYPE::X\n"
            '  VERSION::"1.0"\n'
            "§1::WRAPPER\n"
            "ANCHOR_KERNEL:\n"
            "  TARGET::only_target\n"
            "===END===\n"
        )
        doc = _parse(src)
        validator = Validator({})
        errors = validator.validate(doc, strict=False, section_schemas={"X": schema})

        incomplete = [e for e in errors if e.code == "W_INCOMPLETE_SECTION_FIELDS" and e.field_path == "ANCHOR_KERNEL"]
        assert incomplete, (
            f"Block-shaped ANCHOR_KERNEL under §1 missing NEVER/MUST/GATE must surface "
            f"W_INCOMPLETE_SECTION_FIELDS. Got errors={errors!r}"
        )
        joined = " ".join(e.message for e in incomplete)
        for needed in ("NEVER", "MUST", "GATE"):
            assert needed in joined, f"Warning should name missing field {needed!r}; got {joined!r}"

    def test_nested_block_anchor_kernel_complete_does_not_warn(self) -> None:
        from octave_mcp.core.parser import parse as _parse
        from octave_mcp.core.schema_extractor import PolicyDefinition, SchemaDefinition
        from octave_mcp.core.validator import Validator

        schema = SchemaDefinition(
            name="X",
            version="1.0",
            policy=PolicyDefinition(
                version="1.0",
                unknown_fields="WARN",
                required_section_ids=[],
                section_conditional_required={"ANCHOR_KERNEL": ["TARGET", "NEVER", "MUST", "GATE"]},
            ),
            fields={},
        )

        src = (
            "===DOC===\n"
            "META:\n"
            "  TYPE::X\n"
            '  VERSION::"1.0"\n'
            "§1::WRAPPER\n"
            "ANCHOR_KERNEL:\n"
            "  TARGET::a\n"
            "  NEVER::[b]\n"
            "  MUST::[c]\n"
            '  GATE::"d"\n'
            "===END===\n"
        )
        doc = _parse(src)
        validator = Validator({})
        errors = validator.validate(doc, strict=False, section_schemas={"X": schema})

        unexpected = [e for e in errors if e.code == "W_INCOMPLETE_SECTION_FIELDS" and e.field_path == "ANCHOR_KERNEL"]
        assert not unexpected, (
            f"Complete nested ANCHOR_KERNEL should not surface W_INCOMPLETE_SECTION_FIELDS. " f"Got: {unexpected!r}"
        )
