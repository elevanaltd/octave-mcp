"""CI validation tests for OCTAVE specification files.

This test suite validates all OCTAVE spec files in src/octave_mcp/resources/specs/
against the parser they define. This prevents dogfooding regressions where the
specs themselves violate their own syntax rules.

Rationale:
- Specs are authoritative documentation of OCTAVE syntax
- If specs don't parse, the grammar is either wrong or specs are wrong
- CI validation catches syntax violations before they reach production
- Timeout protection prevents hanging parsers from blocking CI

See: Dogfooding initiative (Jan 2025) - validated 8 specs, fixed 7/8
"""

from pathlib import Path

import pytest

from octave_mcp.core.lexer import LexerError
from octave_mcp.core.parser import ParserError, parse_with_warnings

# Discover all OCTAVE spec files (including architecture docs, vocabularies, and schemas)
SPECS_DIR = Path(__file__).parent.parent / "src" / "octave_mcp" / "resources" / "specs"
SPEC_FILES = sorted(SPECS_DIR.rglob("*.oct.md"))

# Known issues - specs that have parsing problems
# Format: {filename: "reason for exclusion"}
KNOWN_ISSUES = {
    "octave-primers-spec.oct.md": "LexerError E005 line 45 col 24: Unexpected character '\\'",
}


@pytest.mark.timeout(10)
@pytest.mark.parametrize("spec_file", SPEC_FILES, ids=lambda f: f.name)
def test_spec_parses_successfully(spec_file: Path):
    """Validate that each OCTAVE spec file parses successfully within timeout.

    This test ensures specs comply with their own syntax rules (dogfooding) AND
    that parsing completes within reasonable time (10s timeout prevents CI hangs).

    Failure indicates either:
    1. Spec syntax violation (fix the spec)
    2. Parser bug (fix the parser)
    3. Grammar definition error (update grammar)
    4. Parser hang/infinite loop (timeout triggers)

    Args:
        spec_file: Path to OCTAVE spec file to validate
    """
    # Check for known issues
    if spec_file.name in KNOWN_ISSUES:
        pytest.skip(f"Known issue: {KNOWN_ISSUES[spec_file.name]}")

    # Read spec content
    content = spec_file.read_text()

    # Parse with warnings to get full I4 audit trail
    try:
        doc, warnings = parse_with_warnings(content)
    except ParserError as e:
        pytest.fail(
            f"Parser error in {spec_file.name}:\n"
            f"  Error: {e.message}\n"
            f"  Code: {e.error_code}\n"
            f"  Location: line {e.token.line if e.token else 'unknown'}, "
            f"column {e.token.column if e.token else 'unknown'}\n\n"
            f"Fix the spec file or update the parser to handle this syntax."
        )
    except Exception as e:
        pytest.fail(
            f"Unexpected error parsing {spec_file.name}:\n"
            f"  {type(e).__name__}: {e}\n\n"
            f"This may indicate a parser bug or invalid spec syntax."
        )

    # Validation passed - document is parseable
    assert doc is not None, f"{spec_file.name} produced None document"

    # Optional: Check for excessive warnings (indicates lenient parsing)
    # This is informational - not a failure condition
    if len(warnings) > 10:
        print(f"\nNote: {spec_file.name} has {len(warnings)} parser warnings (lenient mode)")


def test_all_specs_discovered():
    """Ensure test suite discovers all expected OCTAVE .oct.md spec documents."""
    # This test is intentionally broad: we validate that *all* .oct.md files under
    # resources/specs/ are parseable by the parser they document.
    assert len(SPEC_FILES) >= 10, (
        f"Expected at least 10 spec documents, found {len(SPEC_FILES)}\n"
        f"Files discovered: {[f.relative_to(SPECS_DIR) for f in SPEC_FILES]}\n"
        f"Check SPECS_DIR path: {SPECS_DIR}"
    )

    for spec_file in SPEC_FILES:
        assert spec_file.exists(), f"Spec file not found: {spec_file}"
        assert spec_file.is_file(), f"Spec path is not a file: {spec_file}"
        assert spec_file.name.endswith(".oct.md"), f"Invalid OCTAVE spec extension: {spec_file}"


def test_no_known_issues_when_all_fixed():
    """Fail if KNOWN_ISSUES contains specs that now parse successfully.

    This ensures we remove specs from KNOWN_ISSUES once they're fixed.
    Prevents stale skip directives from hiding regressions.
    """
    if not KNOWN_ISSUES:
        pytest.skip("No known issues - all specs parse successfully")

    # Try parsing each known-issue spec to see if it's fixed
    # Skip timeout issues since they can't be validated quickly
    still_broken = {}
    for spec_name, reason in KNOWN_ISSUES.items():
        spec_file = SPECS_DIR / spec_name
        if not spec_file.exists():
            continue

        # Skip timeout issues - they need manual investigation
        if "timeout" in reason.lower() or "hang" in reason.lower():
            still_broken[spec_name] = reason
            continue

        try:
            content = spec_file.read_text()
            doc, warnings = parse_with_warnings(content)
            # If we get here without exception, the spec is FIXED
            pytest.fail(
                f"Spec {spec_name} now parses successfully!\n"
                f"Remove it from KNOWN_ISSUES dict in test_spec_validation.py\n"
                f"Original reason: {reason}"
            )
        except (ParserError, Exception):
            # Still broken - keep in KNOWN_ISSUES
            still_broken[spec_name] = reason

    # If we get here, all KNOWN_ISSUES are still broken (expected)
    assert still_broken == KNOWN_ISSUES, "KNOWN_ISSUES has changed unexpectedly"


def test_unclosed_list_at_eof_raises_lexer_error():
    """Test that unclosed lists raise LexerError instead of hanging (GH#180).

    Critical Engineer blocking requirement: unclosed list must NOT cause:
    1. Infinite loop (timeout protection works) ✓
    2. Silent corruption (error raised for auditability) ← THIS TEST

    Per GH#180: Unbalanced brackets are now detected at lexer level with
    clear error messages pointing to the opening bracket location.

    See: CE verdict on commit a081289, continuation_id: 9a2e4f25-5ca9-42b6-ab40-e9b8733f23b1
    Updated for GH#180: Lexer-level bracket detection.
    """
    content = """===TEST===
META:
  TYPE::TEST

FIELD::[value1, value2
===END==="""

    # Lexer should raise E_UNBALANCED_BRACKET error
    with pytest.raises(LexerError) as exc_info:
        parse_with_warnings(content)

    error = exc_info.value
    assert error.error_code == "E_UNBALANCED_BRACKET"
    assert "opening '['" in error.message
    assert "no matching ']'" in error.message
    # Points to the unclosed bracket location
    assert error.line == 5
    assert error.column == 8


# ---------------------------------------------------------------------------
# T17: EBNF Grammar -- literal_value production (Issue #235)
# ---------------------------------------------------------------------------

GRAMMAR_FILE = Path(__file__).parent.parent / "docs" / "grammar" / "octave-v1.0-grammar.ebnf"


def test_grammar_file_exists():
    """Grammar file must exist at the expected path."""
    assert GRAMMAR_FILE.exists(), f"Grammar file not found: {GRAMMAR_FILE}"


def test_grammar_literal_value_production_exists():
    """Grammar file must contain the literal_value production (Issue #235)."""
    content = GRAMMAR_FILE.read_text()
    assert "literal_value" in content, (
        "Grammar file missing 'literal_value' production. "
        "Issue #235 T17 requires adding the literal_value EBNF rule."
    )


def test_grammar_value_production_includes_literal_value():
    """The 'value' production in the grammar must include 'literal_value'."""
    content = GRAMMAR_FILE.read_text()
    # Find the value production block
    assert "| literal_value" in content, (
        "Grammar 'value' production must include '| literal_value'. "
        "Issue #235 T17 requires updating the value production."
    )


def test_grammar_code_fence_production_exists():
    """Grammar file must contain the code_fence production."""
    content = GRAMMAR_FILE.read_text()
    assert "code_fence" in content, (
        "Grammar file missing 'code_fence' production. "
        "Issue #235 T17 requires adding code_fence with opening/closing fences."
    )


def test_grammar_fence_content_production_exists():
    """Grammar file must contain opening_fence and closing_fence productions."""
    content = GRAMMAR_FILE.read_text()
    assert "opening_fence" in content, "Grammar missing 'opening_fence' production."
    assert "closing_fence" in content, "Grammar missing 'closing_fence' production."
    assert "fence_content" in content, "Grammar missing 'fence_content' production."


def test_grammar_constraint_comments_present():
    """Grammar must include constraint comments explaining fence length matching."""
    content = GRAMMAR_FILE.read_text()
    # Check that fence length constraint is documented
    assert (
        "closing fence length must equal opening fence length" in content
    ), "Grammar must document the fence length matching constraint."


def test_grammar_section_4b_exists():
    """Grammar file must contain SECTION 4b for literal values."""
    content = GRAMMAR_FILE.read_text()
    assert "SECTION 4b" in content, "Grammar file must contain SECTION 4b: LITERAL VALUES (Issue #235)."


def test_grammar_no_duplicate_sections():
    """Grammar file must not have duplicate SECTION markers (structural integrity)."""
    content = GRAMMAR_FILE.read_text()
    import re

    section_markers = re.findall(r"\(\* SECTION \d+[a-z]?:", content)
    assert len(section_markers) == len(
        set(section_markers)
    ), f"Grammar file has duplicate section markers: {section_markers}"


# ---------------------------------------------------------------------------
# T18: Core Spec -- LITERAL type and literal zone documentation (Issue #235)
# ---------------------------------------------------------------------------

CORE_SPEC_FILE = Path(__file__).parent.parent / "src" / "octave_mcp" / "resources" / "specs" / "octave-core-spec.oct.md"


def test_core_spec_parses_after_literal_zone_additions():
    """Core spec must parse without errors after Issue #235 T18 additions."""
    from octave_mcp.core.parser import parse

    content = CORE_SPEC_FILE.read_text()
    doc = parse(content)
    assert doc is not None, "Core spec produced None document after T18 changes."


def test_core_spec_contains_literal_keyword():
    """Core spec Section 3 (TYPES) must contain 'LITERAL' keyword."""
    content = CORE_SPEC_FILE.read_text()
    assert "LITERAL" in content, (
        "Core spec missing 'LITERAL' keyword in Section 3. "
        "Issue #235 T18 requires adding LITERAL type documentation."
    )


def test_core_spec_contains_literal_zones_keyword():
    """Core spec Section 6b (VALIDATION_CHECKLIST) must contain 'literal_zones'."""
    content = CORE_SPEC_FILE.read_text()
    assert "literal_zones" in content or "LITERAL_ZONES" in content, (
        "Core spec missing 'literal_zones' keyword in Section 6b. "
        "Issue #235 T18 requires adding LITERAL_ZONES validation checklist."
    )


def test_core_spec_contains_literal_zone_pattern():
    """Core spec Section 7 (CANONICAL_EXAMPLES) must contain 'LITERAL_ZONE_PATTERN'."""
    content = CORE_SPEC_FILE.read_text()
    assert "LITERAL_ZONE_PATTERN" in content, (
        "Core spec missing 'LITERAL_ZONE_PATTERN' in Section 7. "
        "Issue #235 T18 requires adding canonical example pattern."
    )


def test_core_spec_contains_literal_fence():
    """Core spec Section 2c must contain 'LITERAL_FENCE' for syntax reference."""
    content = CORE_SPEC_FILE.read_text()
    assert "LITERAL_FENCE" in content, (
        "Core spec missing 'LITERAL_FENCE' in Section 2c. "
        "Issue #235 T18 requires adding LITERAL_FENCE syntax documentation."
    )
