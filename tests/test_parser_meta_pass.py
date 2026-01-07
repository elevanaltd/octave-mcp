"""Tests for Parser.parse_meta_only() fast META extraction (Phase 2: Generator Engine).

TDD RED phase - these tests will fail until parse_meta_only() is implemented.
"""

from octave_mcp.core.parser import parse_meta_only


class TestParseMetaOnly:
    """Test fast META-only extraction without full parsing."""

    def test_parse_meta_only_basic(self):
        """parse_meta_only() should extract META section without parsing body."""
        content = """===DOC===
META:
  TYPE::SESSION_LOG
  VERSION::"1.0"

BODY:
  CONTENT::"This should not be parsed"
===END==="""

        result = parse_meta_only(content)
        assert result is not None
        assert "TYPE" in result
        assert result["TYPE"] == "SESSION_LOG"
        assert "VERSION" in result
        assert result["VERSION"] == "1.0"
        # Body should NOT be in META
        assert "BODY" not in result

    def test_parse_meta_only_no_meta(self):
        """parse_meta_only() should return empty dict when no META present."""
        content = """===DOC===
BODY:
  CONTENT::"Just body content"
===END==="""

        result = parse_meta_only(content)
        assert result == {}

    def test_parse_meta_only_with_separator(self):
        """parse_meta_only() should handle documents with separator."""
        content = """===DOC===
META:
  TYPE::BUILD_PLAN
  PHASE::B2
---
TASKS::[task1, task2, task3]
===END==="""

        result = parse_meta_only(content)
        assert "TYPE" in result
        assert result["TYPE"] == "BUILD_PLAN"
        assert "PHASE" in result
        # Tasks should not be in META
        assert "TASKS" not in result

    def test_parse_meta_only_nested_meta(self):
        """parse_meta_only() should handle nested META fields."""
        content = """===DOC===
META:
  TYPE::SCHEMA
  FIELDS:
    NAME::REQ
    AGE::OPT
===END==="""

        result = parse_meta_only(content)
        assert "TYPE" in result
        assert result["TYPE"] == "SCHEMA"
        # Nested FIELDS parsing is handled by parse_meta_block
        # which uses the existing parser logic - if present, it will be a dict
        if "FIELDS" in result:
            assert isinstance(result["FIELDS"], dict)
            assert result["FIELDS"]["NAME"] == "REQ"

    def test_parse_meta_only_with_frontmatter(self):
        """parse_meta_only() should handle YAML frontmatter."""
        content = """---
name: Test Agent
---

===DOC===
META:
  TYPE::AGENT
===END==="""

        result = parse_meta_only(content)
        assert "TYPE" in result
        assert result["TYPE"] == "AGENT"

    def test_parse_meta_only_performance(self):
        """parse_meta_only() should be fast - stops after META."""
        # Large document body that would be slow to fully parse
        large_body = "\n".join([f"FIELD_{i}::value_{i}" for i in range(1000)])

        content = f"""===DOC===
META:
  TYPE::LARGE_DOC
  VERSION::"1.0"

{large_body}
===END==="""

        result = parse_meta_only(content)
        assert result["TYPE"] == "LARGE_DOC"
        # Should extract META without parsing the 1000 field lines


class TestParseMetaOnlyEdgeCases:
    """Edge cases for parse_meta_only()."""

    def test_meta_only_empty_document(self):
        """parse_meta_only() should handle empty document."""
        content = ""
        result = parse_meta_only(content)
        assert result == {}

    def test_meta_only_envelope_only(self):
        """parse_meta_only() should handle document with only envelope."""
        content = """===DOC===
===END==="""
        result = parse_meta_only(content)
        assert result == {}

    def test_meta_only_implicit_envelope(self):
        """parse_meta_only() should handle implicit envelope (lenient mode)."""
        content = """META:
  TYPE::IMPLICIT
  STATUS::ACTIVE"""

        result = parse_meta_only(content)
        assert result["TYPE"] == "IMPLICIT"
        assert result["STATUS"] == "ACTIVE"

    def test_meta_only_with_type_and_version(self):
        """parse_meta_only() should handle TYPE and VERSION fields."""
        content = """===DOC===
META:
  TYPE::AGENT
  VERSION::"1.0"
===END==="""

        result = parse_meta_only(content)
        assert result["TYPE"] == "AGENT"
        assert result["VERSION"] == "1.0"
