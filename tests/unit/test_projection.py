"""Tests for projection modes (P1.9)."""

from octave_mcp.core.parser import parse
from octave_mcp.core.projector import project


class TestProjectionModes:
    """Test projection modes."""

    def test_canonical_mode_not_lossy(self):
        """Canonical mode should not be lossy."""
        doc = parse("===TEST===\nKEY::value\n===END===")
        result = project(doc, "canonical")
        assert result.lossy is False
        assert len(result.fields_omitted) == 0

    def test_executive_mode_lossy(self):
        """Executive mode should be lossy."""
        doc = parse("===TEST===\nKEY::value\n===END===")
        result = project(doc, "executive")
        assert result.lossy is True

    def test_developer_mode_lossy(self):
        """Developer mode should be lossy."""
        doc = parse("===TEST===\nKEY::value\n===END===")
        result = project(doc, "developer")
        assert result.lossy is True


class TestProjectionFieldFiltering:
    """Test actual field filtering in projection modes (IL-PLACEHOLDER-FIX-001)."""

    def test_executive_mode_includes_status_risks_decisions(self):
        """Executive mode should include STATUS, RISKS, DECISIONS fields."""
        content = """===TEST===
STATUS::ACTIVE
RISKS::[security, performance]
DECISIONS::use_redis
TESTS::pytest_suite
CI::github_actions
DEPS::[python, redis]
===END==="""
        doc = parse(content)
        result = project(doc, "executive")

        # Should include executive fields
        assert "STATUS" in result.output
        assert "ACTIVE" in result.output
        assert "RISKS" in result.output
        assert "DECISIONS" in result.output

        # Should NOT include developer fields
        assert "TESTS::" not in result.output
        assert "CI::" not in result.output
        assert "DEPS::" not in result.output

    def test_developer_mode_includes_tests_ci_deps(self):
        """Developer mode should include TESTS, CI, DEPS fields."""
        content = """===TEST===
STATUS::ACTIVE
RISKS::[security, performance]
DECISIONS::use_redis
TESTS::pytest_suite
CI::github_actions
DEPS::[python, redis]
===END==="""
        doc = parse(content)
        result = project(doc, "developer")

        # Should include developer fields
        assert "TESTS" in result.output
        assert "pytest_suite" in result.output
        assert "CI" in result.output
        assert "DEPS" in result.output

        # Should NOT include executive fields
        assert "STATUS::" not in result.output
        assert "RISKS:" not in result.output
        assert "DECISIONS::" not in result.output

    def test_executive_mode_preserves_envelope(self):
        """Executive mode should preserve envelope markers."""
        content = """===TEST===
STATUS::ACTIVE
TESTS::pytest_suite
===END==="""
        doc = parse(content)
        result = project(doc, "executive")

        # Should have envelope
        assert "===TEST===" in result.output or "===INFERRED===" in result.output
        assert "===END===" in result.output

    def test_developer_mode_preserves_envelope(self):
        """Developer mode should preserve envelope markers."""
        content = """===TEST===
STATUS::ACTIVE
TESTS::pytest_suite
===END==="""
        doc = parse(content)
        result = project(doc, "developer")

        # Should have envelope
        assert "===TEST===" in result.output or "===INFERRED===" in result.output
        assert "===END===" in result.output

    def test_executive_mode_filters_multiple_fields(self):
        """Executive mode should filter out multiple developer fields."""
        content = """===TEST===
STATUS::ACTIVE
DECISIONS::use_microservices
TESTS::comprehensive
CI::enabled
===END==="""
        doc = parse(content)
        result = project(doc, "executive")

        # Should include executive fields
        assert "STATUS::" in result.output
        assert "DECISIONS::" in result.output

        # Should NOT include developer fields
        assert "TESTS::" not in result.output
        assert "CI::" not in result.output

    def test_developer_mode_filters_multiple_fields(self):
        """Developer mode should filter out multiple executive fields."""
        content = """===TEST===
STATUS::PLANNED
RISKS::[data_loss, performance]
TESTS::comprehensive
DEPS::[python, redis]
===END==="""
        doc = parse(content)
        result = project(doc, "developer")

        # Should include developer fields
        assert "TESTS::" in result.output
        assert "DEPS::" in result.output

        # Should NOT include executive fields
        assert "STATUS::" not in result.output
        assert "RISKS:" not in result.output

    def test_executive_mode_preserves_block_children(self):
        """Executive mode should preserve Block children when parent is kept (IL-PLACEHOLDER-FIX-001-REWORK)."""
        content = """===TEST===
RISKS:
  SECURITY::HIGH
  PERFORMANCE::LOW
STATUS::ACTIVE
===END==="""
        doc = parse(content)
        result = project(doc, "executive")

        # Should keep RISKS block with ALL children
        assert "RISKS:" in result.output
        assert "SECURITY::HIGH" in result.output
        assert "PERFORMANCE::LOW" in result.output

        # Should keep STATUS
        assert "STATUS::ACTIVE" in result.output

    def test_developer_mode_preserves_block_children(self):
        """Developer mode should preserve Block children when parent is kept (IL-PLACEHOLDER-FIX-001-REWORK)."""
        content = """===TEST===
DEPS:
  PYTHON::3.11
  REDIS::7.0
TESTS::pytest_suite
===END==="""
        doc = parse(content)
        result = project(doc, "developer")

        # Should keep DEPS block with ALL children
        assert "DEPS:" in result.output
        assert "PYTHON::3.11" in result.output
        assert "REDIS::7.0" in result.output

        # Should keep TESTS
        assert "TESTS::pytest_suite" in result.output


class TestProjectionEdgeCases:
    """Test edge cases in projection for coverage."""

    def test_authoring_mode_not_lossy(self):
        """Authoring mode should not be lossy (same as canonical for now)."""
        doc = parse("===TEST===\nKEY::value\n===END===")
        result = project(doc, "authoring")
        assert result.lossy is False
        assert len(result.fields_omitted) == 0

    def test_unknown_mode_defaults_to_canonical(self):
        """Unknown mode should default to canonical."""
        doc = parse("===TEST===\nKEY::value\n===END===")
        result = project(doc, "unknown_mode")
        assert result.lossy is False
        assert len(result.fields_omitted) == 0
        assert "KEY::value" in result.output

    def test_executive_mode_with_nested_kept_field(self):
        """Executive mode keeps nested STATUS within a parent block."""
        content = """===TEST===
PARENT:
  STATUS::ACTIVE
  OTHER::data
===END==="""
        doc = parse(content)
        result = project(doc, "executive")
        # STATUS is nested within PARENT, which is not in keep set
        # But STATUS itself is in keep set, so it should be kept
        assert "STATUS::ACTIVE" in result.output

    def test_developer_mode_with_deeply_nested_children(self):
        """Developer mode preserves deeply nested children of kept field."""
        content = """===TEST===
TESTS:
  UNIT:
    COVERAGE::90
    PASSING::true
===END==="""
        doc = parse(content)
        result = project(doc, "developer")
        # All children of TESTS should be preserved
        assert "TESTS:" in result.output
        assert "UNIT:" in result.output
        assert "COVERAGE::90" in result.output
        assert "PASSING::true" in result.output

    def test_projection_returns_filtered_doc(self):
        """Projection result should include filtered_doc for serialization."""
        content = """===TEST===
STATUS::ACTIVE
TESTS::suite
===END==="""
        doc = parse(content)
        result = project(doc, "executive")
        # filtered_doc should be a Document object
        assert result.filtered_doc is not None
        assert hasattr(result.filtered_doc, "sections")

    def test_executive_mode_reports_omitted_fields(self):
        """Executive mode should report which fields are omitted."""
        doc = parse("===TEST===\nSTATUS::ACTIVE\n===END===")
        result = project(doc, "executive")
        assert "TESTS" in result.fields_omitted
        assert "CI" in result.fields_omitted
        assert "DEPS" in result.fields_omitted

    def test_developer_mode_reports_omitted_fields(self):
        """Developer mode should report which fields are omitted."""
        doc = parse("===TEST===\nTESTS::suite\n===END===")
        result = project(doc, "developer")
        assert "STATUS" in result.fields_omitted
        assert "RISKS" in result.fields_omitted
        assert "DECISIONS" in result.fields_omitted
