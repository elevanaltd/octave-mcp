"""GH#487 Phase 0 — changes-mode round-trip characterization net + ratified-contract xfail spec.

This module is the FOUNDATION (Phase 0) of GH#487 (STRATEGY_S3 ``DocumentMutator`` extraction).
It is **test-only**: it touches no production code under ``src/``. It builds the safety net +
acceptance spec that the Phase 2 build (a different agent) will refactor against.

It is organised in TWO complementary layers:

1. CHARACTERIZATION layer — pins CURRENT behaviour (what ``octave_write`` / ``octave_validate``
   do *today*, including the known-bad cases). Each test that pins a KNOWN DEFECT is labelled
   in its docstring with the issue number and the phrase "CHARACTERIZATION: documents current
   buggy behavior, will flip when #487 lands". This layer is the regression net proving the
   refactor changes ONLY what is intended.

2. DESIRED-CONTRACT layer — for each defect, a ``pytest.mark.xfail(strict=True)`` test encoding
   the ratified target behaviour. These are the RED that the Phase 2 build flips to GREEN by
   removing the xfail marker. Each reason references the issue + the GH#487 contract clause.

METHOD per matrix cell (false-green detection):
  Construct a minimal ``.oct.md`` in a temp file, apply the change via ``WriteTool`` (the same
  class the MCP ``octave_write`` tool wraps — matches ``tests/unit/test_gh484_*`` idioms),
  capture the EMITTED document by reading the file back, then feed it through a strict re-parse
  (``octave_mcp.core.parser.parse``) and/or ``ValidateTool`` to detect false-green — i.e.
  ``status: success`` (or ``valid: true``) while the emitted output is structurally invalid /
  non-reparseable. Assertions cover BOTH the write/validate result AND the re-parse.

================================================================================================
MANIFEST — acceptance spec for GH#487 (cell -> current behaviour -> defect # -> desired behaviour)
================================================================================================
The ratified contract (debate-hall decision_hash a8837c80…, operator-ratified 2026-05-30):
  Q1 (#443a): bare-dict at a top-level KEY = FULL REPLACE (drops unmentioned children, I3).
              Explicit {"$op":"MERGE","value":{...}} required to merge. HARD BREAK v1.15.
  Q2 (#440):  DEFERRED CANONICALIZATION. validate + write ACCEPT nested inline maps on input
              (A2 leniency); validate warns W_INLINE_ARRAY_ROOT without mutating source (I5);
              write canonicalizes inline->BLOCK at emit only, logging TRANSFORM::INLINE_MAP_TO_BLOCK
              (I4). dict->InlineMap coercion abolished; BLOCK is the sole canonical nested form.
  #443 Defect 2: scalar<->BLOCK transition via MERGE REJECTED with E_OP_TARGET_MISMATCH (CDV
              CONDITIONAL-GO firmed this to REJECT-only, not honour) — NEVER emit duplicate keys.
  #488:       APPEND/PREPEND onto a list-of-lists must NOT emit single-quoted inline strings that
              fail strict re-parse.
  #484 (shipped): E_NESTED_DICT_IN_MERGE_PAYLOAD rejects non-DELETE dict sub-values in MERGE
              payloads — kept GREEN here as an invariant.

  CELL                                                  | CURRENT (pinned GREEN)            | ISSUE  | DESIRED (xfail strict)
  ------------------------------------------------------|----------------------------------|--------|------------------------------------------
  APPEND  x flat scalar array                           | success, reparse OK              | (none) | invariant — stays GREEN
  PREPEND x flat scalar array                           | success, reparse OK              | (none) | invariant — stays GREEN
  MERGE   x flat scalar array (op-target mismatch)      | E_OP_TARGET_MISMATCH (rejected)  | (none) | invariant — stays GREEN
  APPEND  x list-of-lists                               | success BUT reparse FAIL (E005)  | #488   | clean reparseable round-trip
  PREPEND x list-of-lists                               | success BUT reparse FAIL (E005)  | #488   | clean reparseable round-trip
  APPEND  x nested-dict element (list contains a dict)  | success BUT reparse FAIL (E005)  | #488   | reparseable (block/double-quote, no repr)
  bare-dict at NEW top-level KEY, nested dict value     | success BUT reparse FAIL         | #440   | BLOCK form, reparses, I4 TRANSFORM logged
  MERGE   x nested dict payload (#484 guard)            | E_NESTED_DICT_IN_MERGE_PAYLOAD   | #484   | invariant — stays GREEN (shipped)
  bare-dict at top-level KEY over existing nested BLOCK | success, SILENT MERGE (children  | #443a  | FULL REPLACE: unmentioned children DROPPED
                                                        | preserved + new appended)        |        | (honour I3); reparses
  MERGE   scalar value over an existing nested BLOCK    | success, DUPLICATE keys (BLOCK + | #443   | REJECT with E_OP_TARGET_MISMATCH (CDV firmed
            (Defect 2)                                  | flat scalar same scope), reparse |Defect2 | scalar<->BLOCK ruling to REJECT-only, not
                                                        | OK (lenient parser)              |        | honour); NEVER duplicate keys
  bare-scalar over an existing nested BLOCK (no $op)    | success, DUPLICATE keys (BLOCK + | #443   | full replace BLOCK w/ scalar; NEVER duplicate
                                                        | flat scalar same scope)          |Defect2 | keys
  validate: flat-vs-flat top-level duplicate            | duplicate_key in repair_log      | (R2)   | invariant — stays detected (pin)
  validate: BLOCK-key vs flat-scalar same name in block | duplicate_key in repair_log      | #443/R2| caught (duplicate_key) — FIXED GH#487 Ph1a
                                                        | (DETECTED — GH#487 Phase 1a)     |        | (parser detector registers Block children)
  --- CDV CONDITIONAL-GO blind cells (added Phase 0+, gemini critical-design-validator) ---------
  bare-dict FULL REPLACE re-mentioning a LITERAL-ZONE   | success, SILENT MERGE: fence form| #460-A | REPLACE: fence form of MENTIONED child still
    child (fenced ```...```) at a top-level Block        | of mentioned child IS preserved  | #487   | preserved (route via _normalize_value_for_ast_
    [BLOCKING-1]                                        | (I1/#460 Case A) BUT unmentioned | BLK-1  | preserving) AND unmentioned siblings DROPPED
                                                        | sibling preserved; reparse OK    |        | (Q1); reparses. Cite I1 + #460 Case A.
  MERGE   dict-or-scalar payload over a FLAT SCALAR     | E_OP_TARGET_MISMATCH (rejected)  | #443   | invariant: E_OP_TARGET_MISMATCH (CDV firmed
    [scalar<->BLOCK transition = REJECT-only]           |                                  | #487   | REJECT-only). Cite I3 + contract refinement.
  PREPEND x nested-dict element (list contains a dict)  | success BUT reparse FAIL (E005,  | #488   | reparseable (block/double-quote, no repr);
                                                        | Python repr braces)              |        | mirrors APPEND-dict cell
================================================================================================

QUALITY GATES (run by the author of this module, Phase 0):
  .venv/bin/python -m pytest tests/unit/test_changes_mode_roundtrip_characterization.py -v
  .venv/bin/python -m pytest  (full suite, no regressions)
  ruff check src tests ; black --check src tests ; mypy src

NOTE on [MISSING] coverage: the ``test-generation`` skill body was absent from this worktree at
authoring time (GH#461 missing-skills class); methodology proceeded from the agent PRINCIPLES
(Defensive Testing, Reality Validation) — every characterization assertion below was first
verified live against the current tools (APOLLO precision-measurement), not assumed.
"""

import os
import tempfile

import pytest

from octave_mcp.core.lexer import LexerError
from octave_mcp.core.parser import ParserError, parse
from octave_mcp.mcp.validate import ValidateTool
from octave_mcp.mcp.write import WriteTool

_WRITE = WriteTool()
_VALIDATE = ValidateTool()

# Both parser-level and lexer-level exceptions are "strict re-parse failures". LexerError is NOT
# a subclass of ParserError (it lives in octave_mcp.core.lexer), so we catch both explicitly.
_REPARSE_ERRORS = (ParserError, LexerError)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _roundtrip(doc: str, changes: dict, format_style: str = "preserve") -> tuple[dict, str]:
    """Seed ``doc`` to a temp file, apply ``changes``, return ``(result, emitted_document)``.

    The emitted document is read back from disk (not dry_run) so the captured bytes are exactly
    what a subsequent reader would see — this is what enables false-green detection.
    """
    fd, path = tempfile.mkstemp(suffix=".oct.md")
    os.close(fd)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(doc)
        result = await _WRITE.execute(target_path=path, changes=changes, format_style=format_style)
        with open(path, encoding="utf-8") as f:
            emitted = f.read()
        return result, emitted
    finally:
        os.unlink(path)


def _strict_reparses(document: str) -> bool:
    """True iff ``document`` survives a strict re-parse (no lexer/parser error)."""
    try:
        parse(document)
        return True
    except _REPARSE_ERRORS:
        return False


def _reparse_error(document: str) -> Exception | None:
    """Return the strict re-parse exception (or None if it parses cleanly)."""
    try:
        parse(document)
        return None
    except _REPARSE_ERRORS as exc:
        return exc


async def _validate_repair_subtypes(document: str) -> list[str]:
    """Return the ``subtype`` values of every repair_log entry for ``document`` (schema META)."""
    result = await _VALIDATE.execute(content=document, schema="META", profile="STANDARD")
    return [entry.get("subtype") for entry in result.get("repair_log", [])]


# Base documents (all carry a valid META.VERSION so duplicate-key signals are not masked by E003).
_DOC_FLAT_ARRAY = "===EXAMPLE===\n" "META:\n" "  TYPE::TEST\n" '  VERSION::"1.0"\n' "ITEMS::[a, b, c]\n" "===END===\n"

_DOC_LIST_OF_LISTS = (
    "===EXAMPLE===\n"
    "META:\n"
    "  TYPE::TEST\n"
    '  VERSION::"1.0"\n'
    "RECENT::[\n"
    "  [\n"
    "    PR_483::desc\n"
    "  ]\n"
    "]\n"
    "===END===\n"
)

_DOC_SCALAR_KEY = "===EXAMPLE===\n" "META:\n" "  TYPE::TEST\n" '  VERSION::"1.0"\n' "KEY::scalar\n" "===END===\n"

_DOC_NESTED_BLOCK = (
    "===EXAMPLE===\n"
    "META:\n"
    "  TYPE::TEST\n"
    '  VERSION::"1.0"\n'
    "PARENT:\n"
    "  CHILD_A::keep_me\n"
    "  CHILD_B::keep_me_too\n"
    "===END===\n"
)

# A top-level Block whose CODE child is a LiteralZoneValue (fenced ```...``` block) plus an
# unmentioned SIBLING scalar. Used by the CDV BLOCKING-1 literal-zone REPLACE cell.
_DOC_LITERAL_ZONE_BLOCK = (
    "===EXAMPLE===\n"
    "META:\n"
    "  TYPE::TEST\n"
    '  VERSION::"1.0"\n'
    "PARENT:\n"
    "  CODE::\n"
    "    ```python\n"
    "    x = 1\n"
    "    ```\n"
    "  SIBLING::unmentioned_value\n"
    "===END===\n"
)


def _count_key_occurrences(document: str, key: str) -> int:
    """Count lines whose first non-space token is ``key`` as a BLOCK header (``key:``) or
    flat assignment (``key::``). Used to detect duplicate-key emission (Defect 2)."""
    count = 0
    for line in document.splitlines():
        stripped = line.strip()
        if stripped == f"{key}:" or stripped.startswith(f"{key}::"):
            count += 1
    return count


# ===========================================================================
# LAYER 1 — CHARACTERIZATION (pins CURRENT behaviour; all GREEN today)
# ===========================================================================


class TestCharacterizationInvariants:
    """Cells whose current behaviour is CORRECT — pinned as regression invariants.

    These must stay GREEN through the #487 refactor (the build must not break them).
    """

    @pytest.mark.asyncio
    async def test_append_flat_scalar_array_roundtrips_clean(self) -> None:
        """APPEND onto a flat scalar array: success + strict-reparseable. INVARIANT."""
        result, emitted = await _roundtrip(_DOC_FLAT_ARRAY, {"ITEMS": {"$op": "APPEND", "value": ["d"]}})
        assert result.get("status") == "success"
        assert _strict_reparses(emitted), f"flat-array APPEND must round-trip; got:\n{emitted}"
        assert "d" in emitted

    @pytest.mark.asyncio
    async def test_prepend_flat_scalar_array_roundtrips_clean(self) -> None:
        """PREPEND onto a flat scalar array: success + strict-reparseable. INVARIANT."""
        result, emitted = await _roundtrip(_DOC_FLAT_ARRAY, {"ITEMS": {"$op": "PREPEND", "value": ["z"]}})
        assert result.get("status") == "success"
        assert _strict_reparses(emitted), f"flat-array PREPEND must round-trip; got:\n{emitted}"
        assert "z" in emitted

    @pytest.mark.asyncio
    async def test_merge_over_flat_scalar_array_is_rejected(self) -> None:
        """MERGE targeting a flat scalar array is rejected with E_OP_TARGET_MISMATCH. INVARIANT.

        A MERGE expects a map target; a flat array is not one. The tool correctly rejects rather
        than corrupting — this is the *good* shape the scalar<->BLOCK Defect-2 resolution should
        mirror.
        """
        result, _ = await _roundtrip(_DOC_FLAT_ARRAY, {"ITEMS": {"$op": "MERGE", "value": {"X": "1"}}})
        codes = [e.get("code") for e in result.get("errors", [])]
        assert "E_OP_TARGET_MISMATCH" in codes, f"expected E_OP_TARGET_MISMATCH, got: {codes}"
        assert result.get("status") != "success"

    @pytest.mark.asyncio
    async def test_merge_nested_dict_payload_rejected_gh484(self) -> None:
        """MERGE payload with a plain nested dict is rejected (E_NESTED_DICT_IN_MERGE_PAYLOAD).

        #484 (shipped, PR#485). The ratified #487 contract keeps this guard firing for explicit
        MERGE payloads. INVARIANT — must stay GREEN.
        """
        result, _ = await _roundtrip(_DOC_SCALAR_KEY, {"KEY": {"$op": "MERGE", "value": {"NESTED": {"deep": "dict"}}}})
        codes = [e.get("code") for e in result.get("errors", [])]
        assert "E_NESTED_DICT_IN_MERGE_PAYLOAD" in codes, f"#484 guard must fire; got: {codes}"
        assert result.get("status") != "success"

    @pytest.mark.asyncio
    async def test_merge_scalar_into_existing_block_roundtrips_clean(self) -> None:
        """MERGE adding a NEW scalar child into an existing BLOCK: success + reparseable. INVARIANT.

        This is the *intended* MERGE happy-path (distinct from Defect 2's scalar-over-BLOCK).
        """
        result, emitted = await _roundtrip(_DOC_SCALAR_KEY, {"META": {"$op": "MERGE", "value": {"STATUS": "OK"}}})
        assert result.get("status") == "success"
        assert _strict_reparses(emitted), f"scalar MERGE into block must round-trip; got:\n{emitted}"
        assert "STATUS" in emitted

    @pytest.mark.asyncio
    async def test_merge_over_flat_scalar_is_rejected(self) -> None:
        """MERGE targeting a FLAT SCALAR key is rejected with E_OP_TARGET_MISMATCH. INVARIANT.

        CDV CONDITIONAL-GO blind cell (MERGE-DICT-OVER-SCALAR): a MERGE expects a map target; a
        flat scalar is not one. The tool already rejects rather than corrupting — verified live
        for BOTH a dict payload and a scalar payload. This is exactly the REJECT-only shape the
        firmed scalar<->BLOCK ruling (#487 contract refinement) wants the BLOCK case to mirror.
        """
        # dict payload
        result_dict, _ = await _roundtrip(_DOC_SCALAR_KEY, {"KEY": {"$op": "MERGE", "value": {"A": "1", "B": "2"}}})
        codes_dict = [e.get("code") for e in result_dict.get("errors", [])]
        assert "E_OP_TARGET_MISMATCH" in codes_dict, f"dict-over-scalar MERGE must reject; got: {codes_dict}"
        assert result_dict.get("status") != "success"
        # scalar payload — same rejection
        result_scalar, _ = await _roundtrip(_DOC_SCALAR_KEY, {"KEY": {"$op": "MERGE", "value": {"CHILD": "x"}}})
        codes_scalar = [e.get("code") for e in result_scalar.get("errors", [])]
        assert "E_OP_TARGET_MISMATCH" in codes_scalar, f"scalar-payload MERGE must reject; got: {codes_scalar}"

    @pytest.mark.asyncio
    async def test_validate_flat_vs_flat_duplicate_is_detected(self) -> None:
        """Validator detects a pure flat-vs-flat top-level duplicate via lenient duplicate_key repair.

        Pinned as an INVARIANT: the #487 validator fix for the BLOCK-vs-flat gap must NOT regress
        this existing detection. The signal lives in ``repair_log`` (subtype ``duplicate_key``),
        and the doc validates clean otherwise (``VALIDATED`` / ``valid: true``).
        """
        doc = "===EXAMPLE===\n" "META:\n" "  TYPE::TEST\n" '  VERSION::"1.0"\n' "FOO::a\n" "FOO::b\n" "===END===\n"
        result = await _VALIDATE.execute(content=doc, schema="META", profile="STANDARD")
        subtypes = [e.get("subtype") for e in result.get("repair_log", [])]
        assert "duplicate_key" in subtypes, f"flat-vs-flat dup must be detected; repair_log={result.get('repair_log')}"


class TestCharacterizationKnownDefects:
    """Cells whose current behaviour is BUGGY — pinned to prove the refactor flips ONLY these.

    Every test here documents current buggy behavior and will flip when #487 lands.
    """

    @pytest.mark.asyncio
    async def test_append_list_of_lists_false_green_single_quote_gh488(self) -> None:
        """CHARACTERIZATION: documents current buggy behavior, will flip when #487 lands. (#488)

        APPEND onto a list-of-lists emits a single-quoted inline element (``['VALUE']``) which the
        strict lexer rejects (E005). ``octave_write`` reports ``status: success`` — a FALSE GREEN
        (I1 round-trip violation): the write claims success but the file no longer parses.
        """
        result, emitted = await _roundtrip(_DOC_LIST_OF_LISTS, {"RECENT": {"$op": "APPEND", "value": [["PR_485::x"]]}})
        assert result.get("status") == "success", "current: write reports success (false-green)"
        exc = _reparse_error(emitted)
        assert exc is not None, f"current bug: emitted output should FAIL strict re-parse; got:\n{emitted}"
        assert isinstance(exc, LexerError), f"current bug: E005 lexer rejection expected, got {exc!r}"
        assert "'" in emitted, "current bug: element emitted with single quotes"

    @pytest.mark.asyncio
    async def test_prepend_list_of_lists_false_green_single_quote_gh488(self) -> None:
        """CHARACTERIZATION: documents current buggy behavior, will flip when #487 lands. (#488)

        PREPEND variant of the #488 single-quote false-green on a list-of-lists target.
        """
        result, emitted = await _roundtrip(_DOC_LIST_OF_LISTS, {"RECENT": {"$op": "PREPEND", "value": [["PR_485::x"]]}})
        assert result.get("status") == "success", "current: write reports success (false-green)"
        exc = _reparse_error(emitted)
        assert exc is not None, f"current bug: emitted output should FAIL strict re-parse; got:\n{emitted}"
        assert isinstance(exc, LexerError), f"current bug: E005 lexer rejection expected, got {exc!r}"
        assert "'" in emitted, "current bug: element emitted with single quotes"

    @pytest.mark.asyncio
    async def test_append_nested_dict_element_false_green_gh488(self) -> None:
        """CHARACTERIZATION: documents current buggy behavior, will flip when #487 lands. (#488)

        APPEND a dict element onto a list emits a Python-repr ``{'NESTED': 'v'}`` which the strict
        lexer rejects (E005, unexpected ``{``). Same emitter/serialization family as #488/#484.
        ``status: success`` — false-green.
        """
        result, emitted = await _roundtrip(_DOC_FLAT_ARRAY, {"ITEMS": {"$op": "APPEND", "value": [{"NESTED": "v"}]}})
        assert result.get("status") == "success", "current: write reports success (false-green)"
        assert not _strict_reparses(emitted), f"current bug: emitted output should FAIL re-parse:\n{emitted}"
        assert "{" in emitted, "current bug: dict element emitted as Python repr with braces"

    @pytest.mark.asyncio
    async def test_bare_dict_new_top_key_nested_value_emits_block_gh440(self) -> None:
        """INVERTED (GH#487 B-4, Q2 dict->BLOCK landed): nested dict now emits BLOCK form.

        Formerly a characterization pin documenting the dict->InlineMap coercion bug (nested
        ``NEWKEY::[OUTER::[INNER::v]]`` failing strict re-parse with E_NESTED_INLINE_MAP). GH#487
        Q2 (#440) DEFERRED_CANONICALIZATION abolishes the coercion: a bare-dict at a NEW top-level
        KEY whose value is a nested dict is synthesized as BLOCK form (sole canonical nested form),
        which strict-re-parses cleanly. Retained as the negative-history regression guard
        (converse of ``test_bare_dict_new_top_key_nested_value_emits_block``).
        """
        result, emitted = await _roundtrip(_DOC_SCALAR_KEY, {"NEWKEY": {"OUTER": {"INNER": "v"}}})
        assert result.get("status") == "success"
        assert _strict_reparses(emitted), f"GH#487 Q2: BLOCK-form emit must round-trip; got:\n{emitted}"
        assert "[OUTER::" not in emitted, f"GH#487 Q2: no inline nested map; got:\n{emitted}"

    @pytest.mark.asyncio
    async def test_bare_dict_top_key_over_block_full_replace_gh443a(self) -> None:
        """INVERTED (GH#487 B-2, Q1 FULL REPLACE landed): bare-dict over a Block now full-replaces.

        Formerly a characterization pin documenting the silent-MERGE bug (unmentioned children
        CHILD_A/CHILD_B preserved + new child appended). GH#487 Q1 inverts this to a FULL REPLACE
        (HARD BREAK v1.15): unmentioned children are DROPPED (honours I3). Retained as the
        negative-history regression guard for the fixed behaviour; the converse of the
        desired-contract cell ``test_bare_dict_top_key_over_block_full_replace``.
        """
        result, emitted = await _roundtrip(_DOC_NESTED_BLOCK, {"PARENT": {"NEW_CHILD": "added"}})
        assert result.get("status") == "success"
        assert _strict_reparses(emitted), f"output must round-trip; got:\n{emitted}"
        # GH#487 Q1 FULL REPLACE: unmentioned children are now DROPPED.
        assert "CHILD_A" not in emitted, f"GH#487 Q1: unmentioned CHILD_A must be dropped; got:\n{emitted}"
        assert "CHILD_B" not in emitted, f"GH#487 Q1: unmentioned CHILD_B must be dropped; got:\n{emitted}"
        assert "NEW_CHILD" in emitted

    @pytest.mark.asyncio
    async def test_merge_scalar_over_block_rejected_gh443_defect2(self) -> None:
        """INVERTED (GH#487 B-3, Defect-2 REJECT landed): MERGE scalar-over-block is now rejected.

        Formerly a characterization pin documenting the duplicate-keys bug (the BLOCK left in
        place AND a flat scalar of the same name appended, status:success). GH#487 firmed the
        scalar<->BLOCK transition to REJECT-only: the MERGE now fails with E_OP_TARGET_MISMATCH
        and NO duplicate keys are emitted. Retained as the negative-history regression guard
        (converse of ``test_merge_scalar_over_block_rejected_op_target_mismatch``).
        """
        doc = (
            "===EXAMPLE===\n"
            "META:\n"
            "  TYPE::TEST\n"
            '  VERSION::"1.0"\n'
            "PARENT:\n"
            "  CHEVRON:\n"
            "    deep::x\n"
            "  PKG::y\n"
            "===END===\n"
        )
        result, _ = await _roundtrip(doc, {"PARENT": {"$op": "MERGE", "value": {"CHEVRON": "migrated"}}})
        codes = [e.get("code") for e in result.get("errors", [])]
        assert "E_OP_TARGET_MISMATCH" in codes, f"GH#487 Defect-2: expected E_OP_TARGET_MISMATCH; got: {codes}"
        assert result.get("status") != "success", "GH#487 Defect-2: scalar-over-BLOCK MERGE must not succeed"

    @pytest.mark.asyncio
    async def test_bare_scalar_over_block_full_replace_gh443_defect2(self) -> None:
        """INVERTED (GH#487 B-2, Q1 FULL REPLACE landed): bare-scalar over a Block now replaces it.

        Formerly a characterization pin documenting the duplicate-keys bug (Block left in place
        AND a flat scalar of the same name appended). GH#487 Q1 FULL REPLACE (scalar<->BLOCK
        transition) replaces the Block with a single flat Assignment IN PLACE — exactly one key.
        Retained as the negative-history regression guard for the fixed behaviour.
        """
        result, emitted = await _roundtrip(_DOC_NESTED_BLOCK, {"PARENT": "flat_now"})
        assert result.get("status") == "success"
        assert (
            _count_key_occurrences(emitted, "PARENT") == 1
        ), f"GH#487 Q1: exactly one PARENT key after scalar-over-block replace; got:\n{emitted}"
        assert _strict_reparses(emitted), f"output must round-trip; got:\n{emitted}"

    @pytest.mark.asyncio
    async def test_validate_block_vs_flat_collision_detected_gh443(self) -> None:
        """INVERTED (GH#487 Phase 1a, R2): BLOCK-vs-flat same-name collision IS now detected.

        Previously a characterization pin asserting the validator-coverage GAP: a hand-authored
        BLOCK-key (``CHEVRON:``) colliding with a flat-scalar of the same name inside the same
        parent block validated clean with NO ``duplicate_key`` repair entry. The GH#487 Phase 1a
        parser fix (extend the single duplicate-key detector to register Block children, not just
        Assignment) closes that gap. This cell is inverted to assert the collision is now caught;
        it is the converse of the desired-contract cell ``test_validate_block_vs_flat_collision_caught``
        and is retained as the negative-history pin documenting the fixed behaviour.
        """
        doc = (
            "===EXAMPLE===\n"
            "META:\n"
            "  TYPE::TEST\n"
            '  VERSION::"1.0"\n'
            "PARENT:\n"
            "  CHEVRON:\n"
            "    deep::x\n"
            "  PKG::y\n"
            "  CHEVRON::migrated\n"
            "===END===\n"
        )
        result = await _VALIDATE.execute(content=doc, schema="META", profile="STANDARD")
        subtypes = [e.get("subtype") for e in result.get("repair_log", [])]
        assert (
            "duplicate_key" in subtypes
        ), f"GH#487: BLOCK-vs-flat collision must now be DETECTED; repair_log={result.get('repair_log')}"

    @pytest.mark.asyncio
    async def test_literal_zone_replace_preserves_fence_and_drops_sibling_gh460a(self) -> None:
        """INVERTED (GH#487 B-2, CDV BLOCKING-1 landed): fence preserved AND sibling dropped.

        CDV BLOCKING-1 cell. A bare-dict FULL REPLACE at a top-level Block (``PARENT``) whose
        payload re-mentions the fenced child (``CODE``) with a plain str value:
          - The fence FORM of the mentioned child is PRESERVED (the #460 Case A path,
            ``_normalize_value_for_ast_preserving``, re-wraps the plain str as a LiteralZoneValue —
            so it emits ``CODE::`` + a fence, not ``CODE::\"...\"``). I1 form-preservation holds.
          - GH#487 Q1 FULL REPLACE: the UNMENTIONED ``SIBLING`` child is now DROPPED.
        Formerly a characterization pin documenting the silent-MERGE sibling-survives bug; now the
        negative-history regression guard for the fixed behaviour (converse of
        ``test_literal_zone_replace_preserves_fence_and_drops_sibling``).
        """
        result, emitted = await _roundtrip(_DOC_LITERAL_ZONE_BLOCK, {"PARENT": {"CODE": "new plain content"}})
        assert result.get("status") == "success"
        assert _strict_reparses(emitted), f"output must round-trip; got:\n{emitted}"
        # Fence form preserved for the mentioned child (#460 Case A / BLOCKING-1).
        assert "```" in emitted, f"fence form preserved for mentioned child; got:\n{emitted}"
        assert 'CODE::"' not in emitted, f"fence must NOT downgrade to quoted scalar; got:\n{emitted}"
        assert "new plain content" in emitted, "content was swapped into the fence"
        # GH#487 Q1 FULL REPLACE: the unmentioned sibling is now dropped.
        assert "SIBLING" not in emitted, f"GH#487 Q1: unmentioned SIBLING must be dropped; got:\n{emitted}"

    @pytest.mark.asyncio
    async def test_prepend_nested_dict_element_false_green_gh488(self) -> None:
        """CHARACTERIZATION: documents current buggy behavior, will flip when #487 lands. (#488)

        CDV PREPEND-DICT-ONTO-ARRAY cell — mirror of the APPEND-dict case. PREPEND a dict element
        onto a list-of-lists emits a Python-repr ``{'NESTED': 'v'}`` which the strict lexer rejects
        (E005, unexpected ``{``). ``status: success`` — false-green, same emitter family as #488.
        """
        result, emitted = await _roundtrip(
            _DOC_LIST_OF_LISTS, {"RECENT": {"$op": "PREPEND", "value": [{"NESTED": "v"}]}}
        )
        assert result.get("status") == "success", "current: write reports success (false-green)"
        exc = _reparse_error(emitted)
        assert exc is not None, f"current bug: emitted output should FAIL strict re-parse; got:\n{emitted}"
        assert isinstance(exc, LexerError), f"current bug: E005 lexer rejection expected, got {exc!r}"
        assert "{" in emitted, "current bug: dict element emitted as Python repr with braces"


# ===========================================================================
# LAYER 2 — DESIRED CONTRACT (xfail strict; flips GREEN when #487 build lands)
# ===========================================================================
#
# Each test removes the xfail marker when Phase 2 implements the ratified behaviour. strict=True
# means: if the desired behaviour is met prematurely, the suite FAILS loudly (XPASS), signalling
# the contract has been satisfied and the marker must be removed.


class TestDesiredContractGH488:
    """#488: APPEND/PREPEND onto a list-of-lists must emit strict-re-parseable output."""

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="GH#488 + GH#487 contract (#488 clause): APPEND onto list-of-lists must NOT emit "
        "single-quoted inline strings; emitted output MUST strict-re-parse (I1 round-trip).",
        strict=True,
    )
    async def test_append_list_of_lists_emits_reparseable(self) -> None:
        result, emitted = await _roundtrip(_DOC_LIST_OF_LISTS, {"RECENT": {"$op": "APPEND", "value": [["PR_485::x"]]}})
        assert result.get("status") == "success"
        assert _strict_reparses(emitted), f"DESIRED: emitted output must round-trip; got:\n{emitted}"

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="GH#488 + GH#487 contract (#488 clause): PREPEND onto list-of-lists must emit "
        "strict-re-parseable output (no single-quoted inline strings).",
        strict=True,
    )
    async def test_prepend_list_of_lists_emits_reparseable(self) -> None:
        result, emitted = await _roundtrip(_DOC_LIST_OF_LISTS, {"RECENT": {"$op": "PREPEND", "value": [["PR_485::x"]]}})
        assert result.get("status") == "success"
        assert _strict_reparses(emitted), f"DESIRED: emitted output must round-trip; got:\n{emitted}"

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="GH#488 + GH#487 contract (#488/serialization family): APPEND of a dict element must "
        "emit re-parseable form (block/double-quoted), never a Python repr with braces.",
        strict=True,
    )
    async def test_append_nested_dict_element_emits_reparseable(self) -> None:
        result, emitted = await _roundtrip(_DOC_FLAT_ARRAY, {"ITEMS": {"$op": "APPEND", "value": [{"NESTED": "v"}]}})
        assert result.get("status") == "success"
        assert _strict_reparses(emitted), f"DESIRED: emitted output must round-trip; got:\n{emitted}"

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="GH#488 + GH#487 contract (#488 clause, PREPEND-DICT-ONTO-ARRAY, CDV blind cell): "
        "PREPEND of a dict element onto a list-of-lists must emit re-parseable form "
        "(block/double-quoted), never a Python repr with braces.",
        strict=True,
    )
    async def test_prepend_nested_dict_element_emits_reparseable(self) -> None:
        result, emitted = await _roundtrip(
            _DOC_LIST_OF_LISTS, {"RECENT": {"$op": "PREPEND", "value": [{"NESTED": "v"}]}}
        )
        assert result.get("status") == "success"
        assert _strict_reparses(emitted), f"DESIRED: emitted output must round-trip; got:\n{emitted}"


class TestDesiredContractGH440:
    """#440 / Q2: nested dict values serialize as BLOCK at emit (dict->InlineMap abolished)."""

    @pytest.mark.asyncio
    async def test_bare_dict_new_top_key_nested_value_emits_block(self) -> None:
        result, emitted = await _roundtrip(_DOC_SCALAR_KEY, {"NEWKEY": {"OUTER": {"INNER": "v"}}})
        assert result.get("status") == "success"
        assert _strict_reparses(emitted), f"DESIRED: BLOCK-form emit must round-trip; got:\n{emitted}"
        # Desired canonical nested form is BLOCK, not an inline map.
        assert "[OUTER::" not in emitted, f"DESIRED: no inline nested map; got:\n{emitted}"


class TestDesiredContractGH443aFullReplace:
    """#443a / Q1: bare-dict at a top-level KEY = FULL REPLACE (drop unmentioned children, I3)."""

    @pytest.mark.asyncio
    async def test_bare_dict_top_key_over_block_full_replace(self) -> None:
        result, emitted = await _roundtrip(_DOC_NESTED_BLOCK, {"PARENT": {"NEW_CHILD": "added"}})
        assert result.get("status") == "success"
        assert _strict_reparses(emitted), f"DESIRED: full-replace output must round-trip; got:\n{emitted}"
        # FULL REPLACE: unmentioned children are dropped.
        assert "CHILD_A" not in emitted, f"DESIRED: unmentioned CHILD_A must be dropped; got:\n{emitted}"
        assert "CHILD_B" not in emitted, f"DESIRED: unmentioned CHILD_B must be dropped; got:\n{emitted}"
        assert "NEW_CHILD" in emitted, "DESIRED: the mentioned child must be present"

    @pytest.mark.asyncio
    async def test_literal_zone_replace_preserves_fence_and_drops_sibling(self) -> None:
        result, emitted = await _roundtrip(_DOC_LITERAL_ZONE_BLOCK, {"PARENT": {"CODE": "new plain content"}})
        assert result.get("status") == "success"
        assert _strict_reparses(emitted), f"DESIRED: output must round-trip; got:\n{emitted}"
        # (a) I1 / #460 Case A: the mentioned literal-zone child keeps its fence form.
        assert "```" in emitted, f"DESIRED: fence form preserved for mentioned child; got:\n{emitted}"
        assert 'CODE::"' not in emitted, f"DESIRED: fence must NOT downgrade to quoted scalar; got:\n{emitted}"
        assert "new plain content" in emitted, "DESIRED: replacement content present in the fence"
        # (b) Q1 FULL REPLACE: the unmentioned sibling is dropped.
        assert "SIBLING" not in emitted, f"DESIRED: unmentioned SIBLING must be dropped; got:\n{emitted}"


class TestDesiredContractGH443Defect2:
    """#443 Defect 2: scalar<->BLOCK transition resolved explicitly — NEVER duplicate keys."""

    @pytest.mark.asyncio
    async def test_merge_scalar_over_block_rejected_op_target_mismatch(self) -> None:
        doc = (
            "===EXAMPLE===\n"
            "META:\n"
            "  TYPE::TEST\n"
            '  VERSION::"1.0"\n'
            "PARENT:\n"
            "  CHEVRON:\n"
            "    deep::x\n"
            "  PKG::y\n"
            "===END===\n"
        )
        result, _ = await _roundtrip(doc, {"PARENT": {"$op": "MERGE", "value": {"CHEVRON": "migrated"}}})
        codes = [e.get("code") for e in result.get("errors", [])]
        # CDV refinement: the scalar<->BLOCK transition is REJECT-only. The earlier
        # "honour OR reject" branch is removed — only E_OP_TARGET_MISMATCH is sanctioned.
        assert "E_OP_TARGET_MISMATCH" in codes, f"DESIRED (REJECT-only): expected E_OP_TARGET_MISMATCH; got: {codes}"
        assert result.get("status") != "success", "DESIRED: scalar-over-BLOCK MERGE must not succeed"

    @pytest.mark.asyncio
    async def test_bare_scalar_over_block_no_duplicate_keys(self) -> None:
        result, emitted = await _roundtrip(_DOC_NESTED_BLOCK, {"PARENT": "flat_now"})
        assert result.get("status") == "success"
        assert (
            _count_key_occurrences(emitted, "PARENT") == 1
        ), f"DESIRED: exactly one PARENT key after scalar-over-block replace; got:\n{emitted}"
        assert _strict_reparses(emitted)


class TestDesiredContractValidatorCoverage:
    """#443 / R2 validator-coverage: BLOCK-key vs flat-scalar collision must be caught."""

    @pytest.mark.asyncio
    async def test_validate_block_vs_flat_collision_caught(self) -> None:
        # GH#487 Phase 1a (R2 validator-coverage): a BLOCK-key colliding with a
        # flat-scalar of the same name inside a parent block is now caught by
        # octave_validate (duplicate_key repair entry). xfail marker removed when
        # the parser duplicate-key detector was extended to register Block children.
        doc = (
            "===EXAMPLE===\n"
            "META:\n"
            "  TYPE::TEST\n"
            '  VERSION::"1.0"\n'
            "PARENT:\n"
            "  CHEVRON:\n"
            "    deep::x\n"
            "  PKG::y\n"
            "  CHEVRON::migrated\n"
            "===END===\n"
        )
        result = await _VALIDATE.execute(content=doc, schema="META", profile="STANDARD")
        subtypes = [e.get("subtype") for e in result.get("repair_log", [])]
        error_codes = [e.get("code") for e in result.get("errors", [])]
        caught = ("duplicate_key" in subtypes) or any("duplicate" in str(c).lower() for c in error_codes)
        assert caught, (
            "DESIRED: BLOCK-vs-flat collision must be caught; "
            f"repair_log={result.get('repair_log')} errors={result.get('errors')}"
        )
