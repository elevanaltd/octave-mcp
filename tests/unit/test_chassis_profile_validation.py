"""Tests for chassis-profile validation (ADR-0283).

TDD RED phase: These tests define expected behavior for static validation
of the CHASSIS/PROFILES structure in §3::CAPABILITIES.

Overlap rules from ADR-0283:
- CHASSIS skill in profile skills → error (redundant)
- CHASSIS skill in profile kernel_only → error (contradictory)
- default mixed with context:: in match → error
- Duplicate profile names → error
- 4+ profiles → warning
- Flat SKILLS::[] → no errors (backward compat)
"""

from octave_mcp.core.parser import parse
from octave_mcp.core.validator import validate_chassis_profiles

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _errors_only(results):
    """Filter to severity='error' results."""
    return [e for e in results if e.severity == "error"]


def _warnings_only(results):
    """Filter to severity='warning' results."""
    return [e for e in results if e.severity == "warning"]


# ---------------------------------------------------------------------------
# Valid cases
# ---------------------------------------------------------------------------


class TestChassisProfileValid:
    """Valid chassis-profile structures should produce no errors."""

    def test_valid_chassis_profile_document(self):
        """Full chassis-profile structure with two profiles passes."""
        doc = parse("""===TEST_AGENT===
META:
  TYPE::AGENT_DEFINITION
  VERSION::"8.0.0"
§3::CAPABILITIES
  CHASSIS::[ho-mode, prophetic-intelligence]
  PROFILES:
    STANDARD:
      match::[default]
      skills::[ho-orchestrate, subagent-rules]
      patterns::[mip-orchestration]
    ECOSYSTEM:
      match::[context::p15]
      skills::[ho-ecosystem]
      patterns::[dependency-graph-map]
      kernel_only::[constitutional-enforcement]
===END===""")
        errors = validate_chassis_profiles(doc)
        assert not _errors_only(errors)

    def test_valid_flat_backward_compatible(self):
        """Flat SKILLS::[]/PATTERNS::[] format produces no errors (v7 compat)."""
        doc = parse("""===TEST_AGENT===
META:
  TYPE::AGENT_DEFINITION
  VERSION::"7.0.0"
§3::CAPABILITIES
  SKILLS::[build-execution, build-philosophy]
  PATTERNS::[tdd-discipline]
===END===""")
        errors = validate_chassis_profiles(doc)
        assert len(errors) == 0

    def test_valid_default_as_sole_match(self):
        """default as the only match condition is valid."""
        doc = parse("""===TEST_AGENT===
META:
  TYPE::AGENT_DEFINITION
  VERSION::"8.0.0"
§3::CAPABILITIES
  CHASSIS::[ho-mode]
  PROFILES:
    STANDARD:
      match::[default]
      skills::[ho-orchestrate]
===END===""")
        errors = validate_chassis_profiles(doc)
        assert not _errors_only(errors)

    def test_valid_profile_with_kernel_only(self):
        """Profile with kernel_only field passes validation."""
        doc = parse("""===TEST_AGENT===
META:
  TYPE::AGENT_DEFINITION
  VERSION::"8.0.0"
§3::CAPABILITIES
  CHASSIS::[ho-mode]
  PROFILES:
    STANDARD:
      match::[default]
      skills::[ho-orchestrate]
      kernel_only::[system-orchestration]
===END===""")
        errors = validate_chassis_profiles(doc)
        assert not _errors_only(errors)

    def test_valid_same_skill_across_profiles_different_fidelity(self):
        """Same skill in skills for Profile A and kernel_only for Profile B is valid.

        Profiles are mutually exclusive; the skill loads at different fidelity
        depending on active profile.
        """
        doc = parse("""===TEST_AGENT===
META:
  TYPE::AGENT_DEFINITION
  VERSION::"8.0.0"
§3::CAPABILITIES
  CHASSIS::[ho-mode]
  PROFILES:
    STANDARD:
      match::[default]
      skills::[constitutional-enforcement]
    ECOSYSTEM:
      match::[context::p15]
      skills::[ho-ecosystem]
      kernel_only::[constitutional-enforcement]
===END===""")
        errors = validate_chassis_profiles(doc)
        assert not _errors_only(errors)

    def test_valid_same_skill_in_skills_both_profiles(self):
        """Same skill in skills for both profiles is valid (explicit duplication)."""
        doc = parse("""===TEST_AGENT===
META:
  TYPE::AGENT_DEFINITION
  VERSION::"8.0.0"
§3::CAPABILITIES
  CHASSIS::[ho-mode]
  PROFILES:
    STANDARD:
      match::[default]
      skills::[ho-orchestrate, constitutional-enforcement]
    ECOSYSTEM:
      match::[context::p15]
      skills::[ho-ecosystem, constitutional-enforcement]
===END===""")
        errors = validate_chassis_profiles(doc)
        assert not _errors_only(errors)

    def test_no_capabilities_section(self):
        """Documents without §3::CAPABILITIES skip validation entirely."""
        doc = parse("""===TEST_DOC===
META:
  TYPE::GENERAL
§1::CONTENT
  KEY::value
===END===""")
        errors = validate_chassis_profiles(doc)
        assert len(errors) == 0

    def test_chassis_only_no_profiles(self):
        """CHASSIS without PROFILES is valid (chassis-only mode)."""
        doc = parse("""===TEST_AGENT===
META:
  TYPE::AGENT_DEFINITION
  VERSION::"8.0.0"
§3::CAPABILITIES
  CHASSIS::[ho-mode, prophetic-intelligence]
===END===""")
        errors = validate_chassis_profiles(doc)
        assert not _errors_only(errors)

    def test_profiles_only_no_chassis(self):
        """PROFILES without CHASSIS is valid (profiles-only mode).

        Structured mode is triggered by CHASSIS or PROFILES keys.
        An agent may use profiles without declaring invariant chassis skills.
        """
        doc = parse("""===TEST_AGENT===
META:
  TYPE::AGENT_DEFINITION
  VERSION::"8.0.0"
§3::CAPABILITIES
  PROFILES:
    STANDARD:
      match::[default]
      skills::[ho-orchestrate, subagent-rules]
    ECOSYSTEM:
      match::[context::p15]
      skills::[ho-ecosystem]
===END===""")
        errors = validate_chassis_profiles(doc)
        assert not _errors_only(errors)


# ---------------------------------------------------------------------------
# Invalid cases — overlap rules
# ---------------------------------------------------------------------------


class TestChassisProfileOverlapErrors:
    """Overlap rule violations should produce errors."""

    def test_chassis_skill_in_profile_skills(self):
        """CHASSIS skill also in a profile's skills → error (redundant)."""
        doc = parse("""===TEST_AGENT===
META:
  TYPE::AGENT_DEFINITION
  VERSION::"8.0.0"
§3::CAPABILITIES
  CHASSIS::[ho-mode, prophetic-intelligence]
  PROFILES:
    STANDARD:
      match::[default]
      skills::[ho-mode, ho-orchestrate]
===END===""")
        errors = validate_chassis_profiles(doc)
        err = _errors_only(errors)
        assert len(err) >= 1
        assert any(e.code == "E_CHASSIS_OVERLAP" for e in err)
        assert any("ho-mode" in e.message for e in err)

    def test_chassis_skill_in_profile_kernel_only(self):
        """CHASSIS skill also in a profile's kernel_only → error (contradictory)."""
        doc = parse("""===TEST_AGENT===
META:
  TYPE::AGENT_DEFINITION
  VERSION::"8.0.0"
§3::CAPABILITIES
  CHASSIS::[ho-mode]
  PROFILES:
    STANDARD:
      match::[default]
      skills::[ho-orchestrate]
      kernel_only::[ho-mode]
===END===""")
        errors = validate_chassis_profiles(doc)
        err = _errors_only(errors)
        assert len(err) >= 1
        assert any(e.code == "E_CHASSIS_OVERLAP" for e in err)
        assert any("ho-mode" in e.message for e in err)

    def test_chassis_overlap_multiple_profiles(self):
        """CHASSIS skill overlapping in multiple profiles reports each."""
        doc = parse("""===TEST_AGENT===
META:
  TYPE::AGENT_DEFINITION
  VERSION::"8.0.0"
§3::CAPABILITIES
  CHASSIS::[ho-mode]
  PROFILES:
    STANDARD:
      match::[default]
      skills::[ho-mode]
    ECOSYSTEM:
      match::[context::p15]
      skills::[ho-mode]
===END===""")
        errors = validate_chassis_profiles(doc)
        err = _errors_only(errors)
        overlap_errors = [e for e in err if e.code == "E_CHASSIS_OVERLAP"]
        assert len(overlap_errors) >= 2  # One per profile


# ---------------------------------------------------------------------------
# Invalid cases — match rules
# ---------------------------------------------------------------------------


class TestChassisProfileMatchErrors:
    """Match field violations should produce errors."""

    def test_default_mixed_with_context(self):
        """default mixed with context:: conditions in same match → error."""
        doc = parse("""===TEST_AGENT===
META:
  TYPE::AGENT_DEFINITION
  VERSION::"8.0.0"
§3::CAPABILITIES
  CHASSIS::[ho-mode]
  PROFILES:
    BAD_PROFILE:
      match::[default, context::p15]
      skills::[ho-orchestrate]
===END===""")
        errors = validate_chassis_profiles(doc)
        err = _errors_only(errors)
        assert any(e.code == "E_CHASSIS_DEFAULT_MIXED" for e in err)


# ---------------------------------------------------------------------------
# Invalid cases — duplicate profiles
# ---------------------------------------------------------------------------


class TestChassisProfileDuplicateErrors:
    """Duplicate profile names should produce errors."""

    def test_duplicate_profile_names(self):
        """Two profiles with the same name → error."""
        doc = parse("""===TEST_AGENT===
META:
  TYPE::AGENT_DEFINITION
  VERSION::"8.0.0"
§3::CAPABILITIES
  CHASSIS::[ho-mode]
  PROFILES:
    STANDARD:
      match::[default]
      skills::[ho-orchestrate]
    STANDARD:
      match::[context::p15]
      skills::[ho-ecosystem]
===END===""")
        errors = validate_chassis_profiles(doc)
        err = _errors_only(errors)
        assert any(e.code == "E_CHASSIS_DUPLICATE_PROFILE" for e in err)


# ---------------------------------------------------------------------------
# Warning cases
# ---------------------------------------------------------------------------


class TestChassisProfileWarnings:
    """Warning conditions should produce warnings (not errors)."""

    def test_four_or_more_profiles_warning(self):
        """4+ profiles emits a warning."""
        doc = parse("""===TEST_AGENT===
META:
  TYPE::AGENT_DEFINITION
  VERSION::"8.0.0"
§3::CAPABILITIES
  CHASSIS::[ho-mode]
  PROFILES:
    P1:
      match::[default]
      skills::[skill-a]
    P2:
      match::[context::a]
      skills::[skill-b]
    P3:
      match::[context::b]
      skills::[skill-c]
    P4:
      match::[context::c]
      skills::[skill-d]
===END===""")
        errors = validate_chassis_profiles(doc)
        warnings = _warnings_only(errors)
        assert any(e.code == "W_CHASSIS_PROFILE_COUNT" for e in warnings)
        # Should not be an error
        err = _errors_only(errors)
        assert not any(e.code == "W_CHASSIS_PROFILE_COUNT" for e in err)

    def test_three_profiles_no_warning(self):
        """3 profiles does not emit a warning."""
        doc = parse("""===TEST_AGENT===
META:
  TYPE::AGENT_DEFINITION
  VERSION::"8.0.0"
§3::CAPABILITIES
  CHASSIS::[ho-mode]
  PROFILES:
    P1:
      match::[default]
      skills::[skill-a]
    P2:
      match::[context::a]
      skills::[skill-b]
    P3:
      match::[context::b]
      skills::[skill-c]
===END===""")
        errors = validate_chassis_profiles(doc)
        warnings = _warnings_only(errors)
        assert not any(e.code == "W_CHASSIS_PROFILE_COUNT" for e in warnings)


# ---------------------------------------------------------------------------
# Invalid cases — missing required fields (Fix 2)
# ---------------------------------------------------------------------------


class TestChassisProfileMissingFields:
    """Profile blocks missing required fields should produce errors."""

    def test_profile_missing_match_field(self):
        """Profile without match field -> E_CHASSIS_MISSING_FIELD error."""
        doc = parse("""===TEST_AGENT===
META:
  TYPE::AGENT_DEFINITION
  VERSION::"8.0.0"
§3::CAPABILITIES
  CHASSIS::[ho-mode]
  PROFILES:
    BAD_PROFILE:
      skills::[ho-orchestrate]
===END===""")
        errors = validate_chassis_profiles(doc)
        err = _errors_only(errors)
        assert len(err) >= 1
        assert any(e.code == "E_CHASSIS_MISSING_FIELD" for e in err)
        assert any("match" in e.message for e in err)

    def test_profile_missing_skills_field(self):
        """Profile without skills field -> E_CHASSIS_MISSING_FIELD error."""
        doc = parse("""===TEST_AGENT===
META:
  TYPE::AGENT_DEFINITION
  VERSION::"8.0.0"
§3::CAPABILITIES
  CHASSIS::[ho-mode]
  PROFILES:
    BAD_PROFILE:
      match::[default]
===END===""")
        errors = validate_chassis_profiles(doc)
        err = _errors_only(errors)
        assert len(err) >= 1
        assert any(e.code == "E_CHASSIS_MISSING_FIELD" for e in err)
        assert any("skills" in e.message for e in err)

    def test_profile_missing_both_match_and_skills(self):
        """Profile with only kernel_only (missing match and skills) -> two errors."""
        doc = parse("""===TEST_AGENT===
META:
  TYPE::AGENT_DEFINITION
  VERSION::"8.0.0"
§3::CAPABILITIES
  CHASSIS::[ho-mode]
  PROFILES:
    BAD_PROFILE:
      kernel_only::[system-orchestration]
===END===""")
        errors = validate_chassis_profiles(doc)
        err = _errors_only(errors)
        missing_field_errors = [e for e in err if e.code == "E_CHASSIS_MISSING_FIELD"]
        assert len(missing_field_errors) >= 2
        messages = " ".join(e.message for e in missing_field_errors)
        assert "match" in messages
        assert "skills" in messages

    def test_one_valid_one_invalid_profile(self):
        """Mixed profiles: valid profile passes, invalid one still errors."""
        doc = parse("""===TEST_AGENT===
META:
  TYPE::AGENT_DEFINITION
  VERSION::"8.0.0"
§3::CAPABILITIES
  CHASSIS::[ho-mode]
  PROFILES:
    GOOD:
      match::[default]
      skills::[ho-orchestrate]
    BAD:
      kernel_only::[system-orchestration]
===END===""")
        errors = validate_chassis_profiles(doc)
        err = _errors_only(errors)
        missing_field_errors = [e for e in err if e.code == "E_CHASSIS_MISSING_FIELD"]
        assert len(missing_field_errors) >= 2  # match + skills missing from BAD
        # All errors should reference BAD profile
        assert all("BAD" in e.field_path for e in missing_field_errors)


# ---------------------------------------------------------------------------
# Integration test — chassis errors surface through Validator.validate() (Fix 3)
# ---------------------------------------------------------------------------


class TestChassisProfileIntegration:
    """Chassis-profile errors must surface through the public Validator interface."""

    def test_chassis_errors_surface_through_validator(self):
        """Validator.validate() should include chassis-profile errors for AGENT_DEFINITION docs."""
        from octave_mcp.core.validator import Validator

        doc = parse("""===TEST_AGENT===
META:
  TYPE::AGENT_DEFINITION
  VERSION::"8.0.0"
§3::CAPABILITIES
  CHASSIS::[ho-mode]
  PROFILES:
    STANDARD:
      match::[default]
      skills::[ho-mode]
    BAD:
      kernel_only::[system-orchestration]
===END===""")
        validator = Validator(schema=None)
        errors = validator.validate(doc)
        # Should contain chassis-profile errors (overlap + missing fields)
        codes = [e.code for e in errors]
        assert "E_CHASSIS_OVERLAP" in codes, "Overlap error should surface through Validator.validate()"
        assert "E_CHASSIS_MISSING_FIELD" in codes, "Missing field error should surface through Validator.validate()"

    def test_chassis_errors_surface_through_mcp_validate(self):
        """octave_validate MCP tool should report chassis-profile errors."""
        import asyncio

        from octave_mcp.mcp.validate import ValidateTool

        content = """===TEST_AGENT===
META:
  TYPE::AGENT_DEFINITION
  VERSION::"8.0.0"
§3::CAPABILITIES
  CHASSIS::[ho-mode]
  PROFILES:
    BAD:
      kernel_only::[system-orchestration]
===END==="""
        tool = ValidateTool()
        result = asyncio.run(tool.execute(content=content, schema="META"))
        # Chassis errors should appear in warnings or validation_errors
        all_messages = []
        for w in result.get("warnings", []):
            all_messages.append(w.get("code", ""))
        for e in result.get("validation_errors", []):
            all_messages.append(e.get("code", ""))
        assert any(
            "E_CHASSIS" in code for code in all_messages
        ), f"Chassis errors should surface through MCP validate tool. Got: {all_messages}"
