"""Tests for GH#297: Comments inside META block break nesting.

A `//` comment placed inside the META block (inline after a value or
standalone line) causes subsequent META keys to lose indentation and
escape to document root level in canonical output.

`octave_validate` returns `status: success` but with structurally
damaged canonical form -- silent structural corruption violating I1
(Syntactic Fidelity).

TDD: RED phase -- these tests MUST fail before the fix is applied.
"""

from octave_mcp.core.emitter import emit
from octave_mcp.core.parser import parse


class TestGH297InlineCommentInMeta:
    """Case 1: Inline comment after value inside META block."""

    def test_inline_comment_does_not_break_meta_nesting(self):
        """Keys after an inline comment must remain inside META block."""
        content = """\
===TEST===
META:
  TYPE::LLM_PROFILE
  VERSION::"1.0"
  COMPRESSION_TIER::CONSERVATIVE // This is a comment
  LOSS_PROFILE::"some_loss"
  REQUIRES::"some_tool"
===END==="""
        doc = parse(content)
        # All keys should be in META, not escaped to root
        assert "TYPE" in doc.meta
        assert "VERSION" in doc.meta
        assert "COMPRESSION_TIER" in doc.meta
        assert "LOSS_PROFILE" in doc.meta, "LOSS_PROFILE escaped META block due to inline comment on previous line"
        assert "REQUIRES" in doc.meta, "REQUIRES escaped META block due to inline comment on previous line"

    def test_inline_comment_meta_roundtrip_structure(self):
        """Canonical output must keep all keys indented under META."""
        content = """\
===TEST===
META:
  TYPE::LLM_PROFILE
  VERSION::"1.0"
  COMPRESSION_TIER::CONSERVATIVE // This is a comment
  LOSS_PROFILE::"some_loss"
  REQUIRES::"some_tool"
===END==="""
        doc = parse(content)
        result = emit(doc)
        # All keys must appear indented under META:, not at root level
        lines = result.strip().split("\n")
        meta_started = False
        meta_keys_found = []
        root_keys_found = []
        for line in lines:
            if line.strip() == "META:":
                meta_started = True
                continue
            if meta_started and line.startswith("  ") and "::" in line:
                key = line.strip().split("::")[0]
                meta_keys_found.append(key)
            elif meta_started and not line.startswith("  ") and "::" in line:
                key = line.strip().split("::")[0]
                root_keys_found.append(key)
            elif line.startswith("==="):
                meta_started = False

        assert "LOSS_PROFILE" not in root_keys_found, f"LOSS_PROFILE escaped to root level: {root_keys_found}"
        assert "REQUIRES" not in root_keys_found, f"REQUIRES escaped to root level: {root_keys_found}"
        assert "LOSS_PROFILE" in meta_keys_found
        assert "REQUIRES" in meta_keys_found


class TestGH297StandaloneCommentInMeta:
    """Case 2: Standalone comment line inside META block."""

    def test_standalone_comment_does_not_break_meta_nesting(self):
        """Keys after a standalone comment line must remain inside META block."""
        content = """\
===TEST===
META:
  TYPE::LLM_PROFILE
  VERSION::"1.0"
  // This is a comment about the next key
  COMPRESSION_TIER::CONSERVATIVE
  LOSS_PROFILE::"some_loss"
===END==="""
        doc = parse(content)
        assert "TYPE" in doc.meta
        assert "VERSION" in doc.meta
        assert "COMPRESSION_TIER" in doc.meta, "COMPRESSION_TIER escaped META block due to standalone comment"
        assert "LOSS_PROFILE" in doc.meta, "LOSS_PROFILE escaped META block due to standalone comment"

    def test_standalone_comment_meta_roundtrip_structure(self):
        """Canonical output must keep all keys indented under META after standalone comment."""
        content = """\
===TEST===
META:
  TYPE::LLM_PROFILE
  VERSION::"1.0"
  // This is a comment about the next key
  COMPRESSION_TIER::CONSERVATIVE
  LOSS_PROFILE::"some_loss"
===END==="""
        doc = parse(content)
        result = emit(doc)
        lines = result.strip().split("\n")
        meta_started = False
        root_keys_found = []
        for line in lines:
            if line.strip() == "META:":
                meta_started = True
                continue
            if meta_started and not line.startswith("  ") and "::" in line:
                key = line.strip().split("::")[0]
                root_keys_found.append(key)
            elif line.startswith("==="):
                meta_started = False

        assert len(root_keys_found) == 0, f"Keys escaped META to root level: {root_keys_found}"


class TestGH297MetaCommentEdgeCases:
    """Edge cases for comments in META blocks."""

    def test_multiple_inline_comments_in_meta(self):
        """Multiple inline comments should not break META nesting."""
        content = """\
===TEST===
META:
  TYPE::AGENT // type comment
  VERSION::"2.0" // version comment
  PURPOSE::"testing"
===END==="""
        doc = parse(content)
        assert "TYPE" in doc.meta
        assert "VERSION" in doc.meta
        assert "PURPOSE" in doc.meta, "PURPOSE escaped META after multiple inline comments"

    def test_comment_at_start_of_meta(self):
        """Comment as first child of META should not break parsing."""
        content = """\
===TEST===
META:
  // Leading comment in META
  TYPE::LLM_PROFILE
  VERSION::"1.0"
===END==="""
        doc = parse(content)
        assert "TYPE" in doc.meta
        assert "VERSION" in doc.meta

    def test_meta_values_correct_after_comment(self):
        """Values of keys after comments must be correct, not corrupted."""
        content = """\
===TEST===
META:
  TYPE::LLM_PROFILE
  COMPRESSION_TIER::CONSERVATIVE // This is a comment
  LOSS_PROFILE::"some_loss"
===END==="""
        doc = parse(content)
        assert doc.meta.get("LOSS_PROFILE") == "some_loss"
        assert doc.meta.get("COMPRESSION_TIER") == "CONSERVATIVE"
