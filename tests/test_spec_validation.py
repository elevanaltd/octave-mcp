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

from octave_mcp.core.parser import ParserError, parse_with_warnings

# Discover all OCTAVE spec files
SPECS_DIR = Path(__file__).parent.parent / "src" / "octave_mcp" / "resources" / "specs"
SPEC_FILES = sorted(SPECS_DIR.glob("octave-*-spec.oct.md"))

# Known issues - specs that have parsing problems
# Format: {filename: "reason for exclusion"}
KNOWN_ISSUES = {
    "octave-primers-spec.oct.md": "LexerError E005 line 45 col 24: Unexpected character '\\'",
    "octave-skills-spec.oct.md": "LexerError E005 line 97 col 54: Unexpected character '\"'",
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
    """Ensure test suite discovers all expected spec files.

    This meta-test validates that the test discovery glob pattern
    correctly finds all OCTAVE specification files.
    """
    # We expect at least 8 spec files based on current repository
    assert len(SPEC_FILES) >= 8, (
        f"Expected at least 8 spec files, found {len(SPEC_FILES)}\n"
        f"Files discovered: {[f.name for f in SPEC_FILES]}\n"
        f"Check SPECS_DIR path: {SPECS_DIR}"
    )

    # Verify all discovered files exist
    for spec_file in SPEC_FILES:
        assert spec_file.exists(), f"Spec file not found: {spec_file}"
        assert spec_file.suffix == ".md", f"Invalid spec file extension: {spec_file}"
        assert "octave-" in spec_file.name, f"Invalid spec file naming: {spec_file}"
        assert "-spec.oct.md" in spec_file.name, f"Invalid spec file naming: {spec_file}"


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


def test_unclosed_list_at_eof_emits_warning():
    """Test that unclosed lists emit I4-compliant warning instead of hanging.

    Critical Engineer blocking requirement: unclosed list must NOT cause:
    1. Infinite loop (timeout protection works) ✓
    2. Silent corruption (warning emitted for auditability) ← THIS TEST

    Per I4 (Transform Auditability): "every transformation logged with stable IDs"
    Unclosed list is a lenient parse transformation - must emit warning.

    See: CE verdict on commit a081289, continuation_id: 9a2e4f25-5ca9-42b6-ab40-e9b8733f23b1
    """
    # RED phase: This test will fail until parser emits warning
    content = """===TEST===
META:
  TYPE::TEST

FIELD::[value1, value2
===END==="""

    # Parse should succeed (lenient) but emit warning
    doc, warnings = parse_with_warnings(content)

    # Verify no timeout/hang (implicit via test completion)
    assert doc is not None

    # CE blocking requirement: Must emit warning for unclosed list
    assert len(warnings) > 0, "Expected warning for unclosed list, got none (silent corruption path)"

    # Verify warning has I4-compliant structure
    unclosed_warnings = [w for w in warnings if w.get("subtype") == "unclosed_list"]
    assert len(unclosed_warnings) > 0, f"Expected 'unclosed list' warning, got: {warnings}"

    warning = unclosed_warnings[0]
    # I4 requirement: warnings must include type, message, line, column
    assert "type" in warning, "Warning missing 'type' field (I4 violation)"
    assert "message" in warning, "Warning missing 'message' field (I4 violation)"
    assert "line" in warning, "Warning missing 'line' field (I4 violation)"
    assert "column" in warning, "Warning missing 'column' field (I4 violation)"

    # Verify warning is actionable (identifies unclosed list specifically)
    assert warning["type"] == "lenient_parse", f"Expected type 'lenient_parse', got {warning['type']}"
    assert "list" in warning["message"].lower(), "Warning should mention 'list'"
