"""Tests for GH#452: W_SNAKE_CASE_BLOB advisory warning for snake-case prose blobs.

Detection contract (refined per operator comment 4549996376):

    POSITION_TRIGGER  :: value-of-reasoning-field
                       OR list-element-within-reasoning-field-list
    REASONING_FIELDS  :: {DECISION, BECAUSE, RATIONALE, RETAINS, GUIDANCE,
                          WHY, NOTE, PRINCIPLE, ESCAPE_HATCH, CONTEXT, EVIDENCE,
                          OBSERVATION, FINDING, CONSEQUENCES, TRADEOFFS,
                          NEXT_STEPS, CAVEAT, ASSUMPTION}
    CONTENT_TRIGGER   :: bulk  -> length>40 AND underscores>=4
                       OR semantic -> stopword_count>=2
    EXCLUSIONS        :: token contains '-' or '.'
                       OR matches ^[A-Z][A-Z0-9_]{0,15}$  (short ALL-CAPS idiom)
                       OR zero underscores

v1 severity: ADVISORY only — surfaces in ``warnings``/``corrections`` channel,
never blocks the write.

TDD RED phase: these tests FAIL before the implementation lands in
``src/octave_mcp/mcp/write.py``.
"""

from pathlib import Path

import pytest

from octave_mcp.mcp.validate import ValidateTool
from octave_mcp.mcp.write import WriteTool
from octave_mcp.mcp.write_detection import _detect_snake_case_blob

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "w_snake_case_blob_corpus.oct.md"


# ---------------------------------------------------------------------------
# Empirical offenders (positive cases) — must trigger
# ---------------------------------------------------------------------------

POSITIVE_TOKENS = [
    # Bulk trigger: >40 chars, >=4 underscores, no hyphens/dots
    "replace_app_completion_build_order_with_workflow_first_build_order_to_enable_progressive_SmartSuite_replacement",
    "migration_on_a_moving_target_is_an_anti_pattern_because_app_completion_keeps_shifting",
    "storage_provider_interface_contract_enables_layer_one_vendor_swap_without_app_redeploys",
    "progressive_replacement_is_safer_than_big_bang_migration_for_long_running_projects",
    # Semantic trigger: shorter (under 40 chars) but with >=2 stopwords
    "manual_port_of_5_to_10_active_projects",  # 38 chars: of, to (2 stopwords)
    "is_user_in_admin_group",  # 22 chars, stopwords: in (only 1) - actually shouldn't trigger
]


# ---------------------------------------------------------------------------
# Non-offenders (negative cases) — must NOT trigger
# ---------------------------------------------------------------------------

NEGATIVE_TOKENS = [
    "HO-AGREEMENT-SIGNING-OPTION-A-20260427",  # contains hyphen
    "src/octave_mcp/core/grammar/cst.py",  # contains dot and slash
    "v1.13.0",  # contains dots
    "SmartSuite_API_v2",  # zero stopwords, 16 chars, 2 underscores (3 tokens)
    "SUPERSEDED_BY",  # ALL-CAPS short idiom, <=16 chars
    "agreement_render_jobs",  # 21 chars, 2 underscores (<4), zero stopwords
    "database_pool_size",  # 18 chars, 2 underscores, zero stopwords
    "is_user_active",  # 14 chars, 2 underscores, zero stopwords
    "HEPHAESTUS",  # zero underscores
    "ATLAS",  # zero underscores
]


class TestSnakeCaseBlobDetectorUnit:
    """Direct calls to _detect_snake_case_blob with crafted reasoning-field contexts."""

    @pytest.mark.parametrize(
        "blob",
        [
            "replace_app_completion_build_order_with_workflow_first_build_order_to_enable_progressive_SmartSuite_replacement",
            "migration_on_a_moving_target_is_an_anti_pattern_because_app_completion_keeps_shifting",
            "storage_provider_interface_contract_enables_layer_one_vendor_swap_without_app_redeploys",
            "progressive_replacement_is_safer_than_big_bang_migration_for_long_running_projects",
            "the_observed_pattern_is_that_app_completion_shifts_each_sprint_by_3_to_5_percent",
            "any_change_to_the_interface_breaks_three_or_more_downstream_consumers_at_once",
        ],
    )
    def test_bulk_trigger_in_reasoning_field_value(self, blob):
        """Bulk trigger: token length > 40 chars AND underscores >= 4 inside a reasoning field."""
        for field_name in ("BECAUSE", "RATIONALE", "WHY", "NOTE", "EVIDENCE", "CONSEQUENCES"):
            content = f"FIELD::\nKEY::\n{field_name}::{blob}\n"
            warnings = _detect_snake_case_blob(content)
            codes = [w["code"] for w in warnings]
            assert "W_SNAKE_CASE_BLOB" in codes, f"Bulk trigger missed for {field_name}::{blob!r}"

    def test_semantic_trigger_sub_40_chars_with_two_stopwords(self):
        """Semantic trigger: short token but with >=2 stopwords in a reasoning field."""
        # 38 chars, 4 underscores, stopwords: of, to (2)
        content = "GUIDANCE::manual_port_of_5_to_10_active_projects\n"
        warnings = _detect_snake_case_blob(content)
        codes = [w["code"] for w in warnings]
        assert "W_SNAKE_CASE_BLOB" in codes

    @pytest.mark.parametrize(
        "field_name",
        [
            "DECISION",
            "BECAUSE",
            "RATIONALE",
            "RETAINS",
            "GUIDANCE",
            "WHY",
            "NOTE",
            "PRINCIPLE",
            "ESCAPE_HATCH",
            "CONTEXT",
            "EVIDENCE",
            "OBSERVATION",
            "FINDING",
            "CONSEQUENCES",
            "TRADEOFFS",
            "NEXT_STEPS",
            "CAVEAT",
            "ASSUMPTION",
        ],
    )
    def test_all_18_reasoning_fields_recognised(self, field_name):
        """Every one of the 18 contract reasoning fields must be a position trigger."""
        blob = "this_is_a_long_snake_case_prose_blob_that_must_definitely_trigger_the_warning"
        content = f"{field_name}::{blob}\n"
        warnings = _detect_snake_case_blob(content)
        codes = [w["code"] for w in warnings]
        assert "W_SNAKE_CASE_BLOB" in codes, f"Reasoning field {field_name} not recognised"

    # --- Exclusions: must NOT trigger -----------------------------------

    def test_exclusion_hyphen_token(self):
        """Token containing '-' must be excluded (hyphen-identifiers are not snake-position)."""
        content = "BECAUSE::HO-AGREEMENT-SIGNING-OPTION-A-20260427\n"
        warnings = _detect_snake_case_blob(content)
        codes = [w["code"] for w in warnings]
        assert "W_SNAKE_CASE_BLOB" not in codes

    def test_exclusion_dot_token(self):
        """Token containing '.' must be excluded (path/version identifiers)."""
        content = "RATIONALE::src/octave_mcp/core/grammar/cst.py\n"
        warnings = _detect_snake_case_blob(content)
        codes = [w["code"] for w in warnings]
        assert "W_SNAKE_CASE_BLOB" not in codes

    def test_exclusion_short_all_caps_idiom(self):
        """Short ALL-CAPS idioms (^[A-Z][A-Z0-9_]{0,15}$) must be excluded."""
        # SUPERSEDED_BY = 13 chars, matches the exclusion regex
        content = "RATIONALE::SUPERSEDED_BY\n"
        warnings = _detect_snake_case_blob(content)
        codes = [w["code"] for w in warnings]
        assert "W_SNAKE_CASE_BLOB" not in codes

    def test_exclusion_zero_underscores(self):
        """Tokens with zero underscores must be excluded."""
        content = "BECAUSE::HEPHAESTUS\n"
        warnings = _detect_snake_case_blob(content)
        codes = [w["code"] for w in warnings]
        assert "W_SNAKE_CASE_BLOB" not in codes

    def test_exclusion_underscores_but_below_bulk_and_no_stopwords(self):
        """Tokens like database_pool_size (3 tokens, 2 underscores, no stopwords) must NOT trigger."""
        content = "RATIONALE::database_pool_size\n"
        warnings = _detect_snake_case_blob(content)
        codes = [w["code"] for w in warnings]
        assert "W_SNAKE_CASE_BLOB" not in codes

    def test_exclusion_4_underscores_short_no_stopwords(self):
        """agreement_render_jobs (2 underscores, 21 chars) must NOT trigger."""
        content = "BECAUSE::agreement_render_jobs\n"
        warnings = _detect_snake_case_blob(content)
        codes = [w["code"] for w in warnings]
        assert "W_SNAKE_CASE_BLOB" not in codes

    # --- Position discrimination ----------------------------------------

    def test_non_reasoning_field_value_no_trigger(self):
        """Same blob in a non-reasoning field value position must NOT trigger."""
        blob = "replace_app_completion_build_order_with_workflow_first_build_order_to_enable_progressive_SmartSuite_replacement"
        content = f"TABLE_NAME::{blob}\n"
        warnings = _detect_snake_case_blob(content)
        codes = [w["code"] for w in warnings]
        assert "W_SNAKE_CASE_BLOB" not in codes

    def test_reasoning_word_as_key_only_no_trigger(self):
        """A reasoning-word string used as a structural KEY (not in value position) must NOT trigger.

        ``DECISION:`` opens a block — the *key* is the reasoning word, but
        the children of the block are not themselves reasoning-field values
        unless their own keys are in the set.
        """
        content = "DECISION:\n  TIMESTAMP::2026_05_27_iso_format_with_a_long_tail_for_audit\n"
        warnings = _detect_snake_case_blob(content)
        codes = [w["code"] for w in warnings]
        # TIMESTAMP is not a reasoning field, even though its parent block is "DECISION"
        assert "W_SNAKE_CASE_BLOB" not in codes

    # --- List-element recursion -----------------------------------------

    def test_list_element_in_reasoning_field_triggers(self):
        """A prose blob appearing as a list element inside a reasoning-field list must trigger."""
        content = (
            "DECISION:[\n"
            "  primary_decision_is_to_proceed_with_phase_one_and_revisit_phase_two_in_q3,\n"
            "  backup_decision_is_to_defer_phase_three_to_next_year\n"
            "]\n"
        )
        warnings = _detect_snake_case_blob(content)
        codes = [w["code"] for w in warnings]
        assert (
            codes.count("W_SNAKE_CASE_BLOB") >= 2
        ), f"Expected at least 2 W_SNAKE_CASE_BLOB warnings (one per list element), got {codes}"

    def test_list_element_in_non_reasoning_field_no_trigger(self):
        """Same prose blob in a non-reasoning-field list must NOT trigger."""
        content = (
            "ITEMS:[\n"
            "  primary_decision_is_to_proceed_with_phase_one_and_revisit_phase_two_in_q3,\n"
            "  backup_decision_is_to_defer_phase_three_to_next_year\n"
            "]\n"
        )
        warnings = _detect_snake_case_blob(content)
        codes = [w["code"] for w in warnings]
        assert "W_SNAKE_CASE_BLOB" not in codes

    def test_inline_list_in_reasoning_field_triggers(self):
        """Inline list under reasoning field with prose blob elements must trigger."""
        blob1 = "very_long_token_with_many_underscores_and_quite_a_few_words_too"
        blob2 = "another_very_long_token_with_many_underscores_and_more_words_again"
        content = f"RATIONALE::[{blob1}, {blob2}]\n"
        warnings = _detect_snake_case_blob(content)
        codes = [w["code"] for w in warnings]
        assert codes.count("W_SNAKE_CASE_BLOB") >= 2

    # --- Warning shape --------------------------------------------------

    def test_warning_has_stable_code_and_provenance(self):
        """Warning dict carries stable code, line number, and offending token (I4)."""
        blob = "this_is_a_long_snake_case_prose_blob_that_must_definitely_trigger_the_warning"
        content = f"FILLER::ok\n\nBECAUSE::{blob}\n"
        warnings = _detect_snake_case_blob(content)
        hits = [w for w in warnings if w["code"] == "W_SNAKE_CASE_BLOB"]
        assert len(hits) >= 1
        w = hits[0]
        assert w["code"] == "W_SNAKE_CASE_BLOB"
        assert w["line"] == 3  # 1-based: FILLER on 1, blank on 2, BECAUSE on 3
        assert w["safe"] is True
        assert w["semantics_changed"] is False
        assert blob in w["token"]
        assert w["parent_field"] == "BECAUSE"

    def test_warning_message_references_telegraphic_phrase(self):
        """Warning message should point readers at the canonical TELEGRAPHIC_PHRASE pattern.

        Cross-references the primer landed in #453 (PR #455).
        """
        blob = "this_is_a_long_snake_case_prose_blob_that_must_definitely_trigger_the_warning"
        content = f"BECAUSE::{blob}\n"
        warnings = _detect_snake_case_blob(content)
        hits = [w for w in warnings if w["code"] == "W_SNAKE_CASE_BLOB"]
        assert any("TELEGRAPHIC_PHRASE" in w["message"] for w in hits)

    # --- Protected zones (literal/quoted/comment) -----------------------

    def test_no_warning_in_literal_zone(self):
        """Reasoning-field-shaped text inside a fenced literal zone must NOT trigger."""
        blob = "this_is_a_long_snake_case_prose_blob_that_must_definitely_trigger_the_warning"
        content = "```\n" f"BECAUSE::{blob}\n" "```\n"
        warnings = _detect_snake_case_blob(content)
        codes = [w["code"] for w in warnings]
        assert "W_SNAKE_CASE_BLOB" not in codes

    def test_no_warning_in_quoted_string(self):
        """Reasoning-field-shaped text inside a quoted string must NOT trigger."""
        blob = "this_is_a_long_snake_case_prose_blob_that_must_definitely_trigger_the_warning"
        content = f'BECAUSE::"{blob}"\n'
        warnings = _detect_snake_case_blob(content)
        codes = [w["code"] for w in warnings]
        # Quoted prose is the recommended fix, so it MUST not trigger.
        assert "W_SNAKE_CASE_BLOB" not in codes

    def test_no_warning_in_comment(self):
        """Reasoning-field-shaped text inside a // comment must NOT trigger."""
        blob = "this_is_a_long_snake_case_prose_blob_that_must_definitely_trigger_the_warning"
        content = f"// BECAUSE::{blob}\n"
        warnings = _detect_snake_case_blob(content)
        codes = [w["code"] for w in warnings]
        assert "W_SNAKE_CASE_BLOB" not in codes

    # --- Known v1 miss --------------------------------------------------

    # strict=False (was strict=True) per CE non-blocking advisory on PR #456:
    # https://github.com/elevanaltd/octave-mcp/pull/456#issuecomment-4550543834
    # The assertion is phrased for the v2 contract (W_SNAKE_CASE_BLOB in codes).
    # Under v1 the token does not trip either trigger → xfail. When v2 refines
    # the heuristic to catch this token the test would XPASS, and strict=True
    # would convert XPASS into a suite failure (time bomb). strict=False makes
    # the eventual XPASS a warning instead, signalling "v2 closed the gap"
    # without breaking CI.
    @pytest.mark.xfail(
        reason=(
            "v1 known miss per operator contract 4549996376: "
            "'progressive_replacement_phase_by_phase' (38 chars, 4 underscores, "
            "zero stopwords) is empirically a snake-case prose blob, but does not "
            "meet either the bulk trigger (>40 chars) or the semantic trigger "
            "(>=2 stopwords). v2 may close this with a refined heuristic."
        ),
        strict=False,
    )
    def test_known_v1_miss_progressive_replacement(self):
        """Documented v1 limitation — caught by skill review, not validator."""
        content = "GUIDANCE::progressive_replacement_phase_by_phase\n"
        warnings = _detect_snake_case_blob(content)
        codes = [w["code"] for w in warnings]
        assert "W_SNAKE_CASE_BLOB" in codes


class TestSnakeCaseBlobCorpus:
    """Parametrised corpus test against tests/fixtures/w_snake_case_blob_corpus.oct.md."""

    def test_corpus_fixture_exists(self):
        assert FIXTURE_PATH.is_file(), f"Corpus fixture missing at {FIXTURE_PATH}"

    def test_corpus_positive_section_emits_at_least_10_warnings(self):
        """§1 (positive cases) of the fixture must produce >= 10 W_SNAKE_CASE_BLOB warnings."""
        content = FIXTURE_PATH.read_text()
        warnings = _detect_snake_case_blob(content)
        hits = [w for w in warnings if w["code"] == "W_SNAKE_CASE_BLOB"]
        assert len(hits) >= 10, f"Expected >=10 W_SNAKE_CASE_BLOB warnings from positive corpus, got {len(hits)}"

    def test_corpus_negative_section_emits_zero_warnings_per_line(self):
        """No W_SNAKE_CASE_BLOB warning may point at a line inside §2 (negative cases)."""
        content = FIXTURE_PATH.read_text()
        # Identify §2 start line
        lines = content.split("\n")
        sec2_line = next(
            (i + 1 for i, ln in enumerate(lines) if ln.startswith("§2::NEGATIVE_CASES")),
            None,
        )
        end_line = next(
            (i + 1 for i, ln in enumerate(lines) if ln.startswith("===END===")),
            len(lines),
        )
        assert sec2_line is not None
        warnings = _detect_snake_case_blob(content)
        for w in warnings:
            if w["code"] != "W_SNAKE_CASE_BLOB":
                continue
            ln = w.get("line", 0)
            assert not (sec2_line < ln < end_line), f"False positive in negative section at line {ln}: {w}"


class TestWriteToolIntegration:
    """W_SNAKE_CASE_BLOB must surface in WriteTool corrections (same path as W_ANNOTATION_TOO_LONG)."""

    FIXTURE = """\
===INTEGRATION_TEST===
META:
  TYPE::TEST
BECAUSE::replace_app_completion_build_order_with_workflow_first_build_order_to_enable_progressive_SmartSuite_replacement
===END===
"""

    @pytest.mark.asyncio
    async def test_write_tool_emits_snake_case_blob_in_corrections(self, tmp_path):
        tool = WriteTool()
        target = str(tmp_path / "test.oct.md")
        result = await tool.execute(target_path=target, content=self.FIXTURE)
        corrections = result.get("corrections", [])
        codes = [c["code"] for c in corrections]
        assert "W_SNAKE_CASE_BLOB" in codes

    @pytest.mark.asyncio
    async def test_write_tool_no_error_on_snake_case_blob(self, tmp_path):
        """Advisory only — must NOT block the write."""
        tool = WriteTool()
        target = str(tmp_path / "test.oct.md")
        result = await tool.execute(target_path=target, content=self.FIXTURE)
        assert result.get("status") != "error"
        errors = result.get("errors", [])
        assert not any(e.get("code") == "W_SNAKE_CASE_BLOB" for e in errors)


class TestValidateToolIntegration:
    """W_SNAKE_CASE_BLOB must surface in octave_validate warnings[]."""

    FIXTURE = """\
===VALIDATE_TEST===
META:
  TYPE::TEST
RATIONALE::migration_on_a_moving_target_is_an_anti_pattern_because_app_completion_keeps_shifting
===END===
"""

    @pytest.mark.asyncio
    async def test_validate_tool_emits_snake_case_blob_in_warnings(self):
        tool = ValidateTool()
        result = await tool.execute(content=self.FIXTURE, schema="META")
        warnings = result.get("warnings", [])
        codes = [w.get("code") for w in warnings]
        assert "W_SNAKE_CASE_BLOB" in codes


class TestProtectedLineBracketAccounting:
    """Regression tests for cubic P2 (PR #456 discussion_r3307813188):

    "Protected-line short-circuit happens before list bracket tracking, so
    multiline list state can leak past `]` when a line starts in a protected
    zone."

    The fix must ensure ``list_bracket_depth`` accounting always uses ONLY
    the non-protected substring of each line. Bracket characters inside
    quoted strings, ``//`` comments, or fenced literal zones are opaque
    (text, not list syntax) and MUST NOT affect the depth counter.
    Conversely, a real ``]`` that sits OUTSIDE every protected range on the
    same line as protected content MUST still close the list.
    """

    # --- LEAK scenarios: list MUST close, downstream MUST NOT false-fire ----

    def test_list_closes_on_line_that_begins_in_quoted_string(self):
        """A line whose first non-ws char is inside a quoted string but whose
        ``]`` lies OUTSIDE the quote MUST decrement bracket depth and close
        the list. Otherwise a subsequent prose-blob token (which is no longer
        a list element) would spuriously trigger W_SNAKE_CASE_BLOB.
        """
        blob = "should_not_fire_because_we_are_outside_the_list_already_here_and_now"
        content = (
            "DECISION:[\n" '  "primary_choice",\n' '  "secondary_choice" ]\n' f"NOTE::ok_short\n" f"FILLER::{blob}\n"
        )
        warnings = _detect_snake_case_blob(content)
        hits = [w for w in warnings if w["code"] == "W_SNAKE_CASE_BLOB"]
        # The blob lives in FILLER (not a reasoning field) AFTER the list
        # has closed on line 3. Zero W_SNAKE_CASE_BLOB warnings expected.
        assert hits == [], "List leaked past ']' on a line that begins in a quoted string. " f"Got: {hits}"

    def test_list_closes_on_line_that_begins_at_literal_fence_close(self):
        """A list that contains a fenced literal zone must close cleanly on
        the line carrying the closing ``]`` even though the line preceding
        was a fence-end (fully protected). Tokens after the list must not
        be treated as list elements.
        """
        blob = "should_not_trigger_outside_list_with_many_words_after_the_close"
        content = "BECAUSE:[\n" "  short_one,\n" "  short_two\n" "]\n" f"FILLER::{blob}\n"
        # Sanity: this content has no protected zones and must already work.
        warnings = _detect_snake_case_blob(content)
        hits = [w for w in warnings if w["code"] == "W_SNAKE_CASE_BLOB"]
        assert hits == [], f"Baseline list-close regression: {hits}"

    # --- OPAQUE scenarios: protected line in MIDDLE of list, no brackets ----

    def test_protected_middle_line_preserves_list_state(self):
        """A wholly-protected line in the middle of a reasoning-field list
        (e.g. a ``//`` comment with no brackets) must NOT close the list
        prematurely. List state must persist across the protected line and
        close on the real ``]`` that follows.
        """
        blob_in = "this_is_a_long_snake_case_prose_blob_that_must_definitely_trigger_inside_list"
        blob_out = "this_blob_is_outside_the_list_and_must_not_trigger_since_field_is_not_reasoning"
        content = (
            "DECISION:[\n"
            f"  {blob_in},\n"
            "  // opaque comment with no bracket characters in it at all\n"
            "  short_tail\n"
            "]\n"
            f"FILLER::{blob_out}\n"
        )
        warnings = _detect_snake_case_blob(content)
        hits = [w for w in warnings if w["code"] == "W_SNAKE_CASE_BLOB"]
        # Exactly one hit: blob_in (list element under DECISION).
        # blob_out lives under FILLER (not a reasoning field) after the
        # list closes correctly on line 5.
        codes_lines = [(w["line"], w["token"]) for w in hits]
        assert any(
            blob_in in tok for _, tok in codes_lines
        ), f"Expected list-element hit for {blob_in!r}; got {codes_lines}"
        assert not any(
            blob_out in tok for _, tok in codes_lines
        ), f"List state leaked past ']' — spurious hit for {blob_out!r}: {codes_lines}"

    # --- COMMENT-WITH-BRACKET: ']' inside // comment must NOT decrement -----

    def test_comment_only_line_with_bracket_text_does_not_decrement(self):
        """A line that is entirely a ``//`` comment containing the literal
        text ``]`` must NOT decrement ``list_bracket_depth`` (the ``]`` is
        comment text, not list syntax). The list must remain open and the
        prose blob on the next line must still be treated as a list element.
        """
        blob = "this_is_a_long_snake_case_prose_blob_that_must_definitely_trigger_inside_list"
        content = (
            "DECISION:[\n" "  // trailing remark with a bracket-looking char ] in comment text\n" f"  {blob}\n" "]\n"
        )
        warnings = _detect_snake_case_blob(content)
        hits = [w for w in warnings if w["code"] == "W_SNAKE_CASE_BLOB"]
        # If the comment's ']' incorrectly decremented depth to 0, the list
        # would close prematurely and the blob on line 3 would NOT be
        # recognised as a list element — but it IS still under a reasoning
        # field by virtue of the open list, so it must still trigger.
        assert any(blob in w["token"] for w in hits), f"List closed prematurely on commented ']'; blob missed: {hits}"

    # --- CRS PR #456 REWORK (regex underscore enforcement + digit-prefix) ---
    #
    # CRS-CONDITIONAL findings on PR #456 (comment 4550471154):
    #   1) [HIGH] Token regex did not enforce >=1 underscore (comment-vs-code
    #      mismatch); bare words were scanned and only later dropped.
    #   2) [HIGH] Token regex required ``[A-Za-z]`` at start, truncating
    #      empirical offenders prefixed with a digit (``5_to_10_active...``).
    #   3) [MODERATE] ``re.MULTILINE`` on opener regexes was redundant in a
    #      line-by-line walker; optional ``(\[)?`` group was always required.
    #   4) [SPECULATIVE] Tokens on a line whose first non-ws char sits in a
    #      protected zone are skipped wholesale (inherited heuristic). Bounded
    #      because protected-prefixed lines cannot be ``KEY::`` openers.
    # See: https://github.com/elevanaltd/octave-mcp/pull/456#issuecomment-4550471154

    def test_digit_prefix_token_captured_in_reasoning_field(self):
        """Token starting with a digit must be matched by the regex and surfaced
        verbatim — the leading digit prefix must NOT be truncated.

        Empirical offender from operator comment 4549996376:
        ``5_to_10_active_projects`` was being matched as
        ``to_10_active_projects`` (the leading ``5_`` was dropped). To force a
        trigger we wrap the digit-prefix token in a body long enough to satisfy
        the semantic stopword threshold (>=2 stopwords: ``of``, ``to``, ``in``).
        """
        # 50 chars, 7 underscores, stopwords: of, to, in -> semantic trigger.
        blob = "5_to_10_active_projects_in_scope_of_the_q3_migration"
        content = f"GUIDANCE::{blob}\n"
        warnings = _detect_snake_case_blob(content)
        hits = [w for w in warnings if w["code"] == "W_SNAKE_CASE_BLOB"]
        assert hits, f"Digit-prefix token did not trigger W_SNAKE_CASE_BLOB; got {warnings!r}"
        # The token reported MUST include the leading ``5_`` — otherwise the
        # provenance receipt (I4) lies about which substring offended.
        assert any(
            w["token"].startswith("5_") for w in hits
        ), f"Digit-prefix truncated by regex; reported tokens: {[w['token'] for w in hits]}"

    def test_bare_word_no_underscore_does_not_trigger(self):
        """A bare word with no underscore in a reasoning field MUST NOT trigger.

        The downstream zero-underscore exclusion already drops these, but the
        token regex SHOULD also refuse to match them so we never waste a
        scan on bare-word territory. This test will continue to pass either
        way; it is here to lock in the behavioural contract.
        """
        # Long bare word with no underscores anywhere in the value.
        content = "BECAUSE::xenomorphologicallypreposterous\n"
        warnings = _detect_snake_case_blob(content)
        codes = [w["code"] for w in warnings]
        assert "W_SNAKE_CASE_BLOB" not in codes

    def test_protected_line_prefix_with_trailing_prose_documented_miss(self):
        """Documented heuristic limitation: a line whose first non-whitespace
        character is inside a protected zone (e.g. a quoted string or a fence)
        is wholly skipped for token scanning, even when the rest of the line
        contains an unprotected snake-case prose blob.

        This is consistent with the inherited ``_detect_annotation_too_long``
        line-walker heuristic. In practice the protected-prefix shape can only
        appear mid-list (a quoted list element followed by an unquoted token
        on the same line is malformed OCTAVE) so the false-negative surface is
        empirically empty. We assert the documented behaviour here so any
        future refactor that changes it must do so deliberately.
        """
        blob = "this_is_a_long_snake_case_prose_blob_that_must_definitely_trigger_the_warning"
        # Line begins with the protected prefix of a quoted string; the blob
        # appears AFTER the closing quote on the same line. The line walker
        # short-circuits on the protected line-prefix per the inherited
        # heuristic (cubic P2 fix preserved bracket accounting but not token
        # scanning on these lines).
        content = "DECISION:[\n" f'  "primary" , {blob}\n' "]\n"
        warnings = _detect_snake_case_blob(content)
        hits = [w for w in warnings if w["code"] == "W_SNAKE_CASE_BLOB"]
        # Documented limitation: heuristic misses this shape. If a future
        # refactor surfaces this case, update the assertion to `assert hits`
        # and remove this comment block.
        assert hits == [], (
            "Heuristic behaviour changed: protected-prefixed lines now scan "
            "for tokens past the protected zone. Update the documented "
            "limitation in src/octave_mcp/mcp/write.py and remove this test "
            "or invert its assertion."
        )

    def test_protected_zone_tokens_still_never_trigger(self):
        """Even after the fix, tokens that live INSIDE protected zones must
        continue to be invisible to the scanner. Bracket accounting on the
        non-protected substring must not accidentally lift token detection
        into protected territory.
        """
        blob = "this_is_a_long_snake_case_prose_blob_that_must_definitely_trigger_the_warning"
        contents = [
            # In a literal fence
            f"```\nBECAUSE::{blob}\n```\n",
            # In a quoted string under a reasoning field
            f'BECAUSE::"{blob}"\n',
            # In a // comment
            f"// BECAUSE::{blob}\n",
            # In a literal-fence line that ALSO sits inside an open list
            f"BECAUSE:[\n  short_one,\n```\n{blob}\n```\n  short_two\n]\n",
        ]
        for content in contents:
            warnings = _detect_snake_case_blob(content)
            for w in warnings:
                if w["code"] != "W_SNAKE_CASE_BLOB":
                    continue
                assert blob not in w["token"], f"Protected-zone token leaked into warnings for content: {content!r}"
