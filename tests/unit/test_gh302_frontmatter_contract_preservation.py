"""Tests for GH#302: Preserve YAML frontmatter and CONTRACT in octave_write round-trip.

TDD RED phase: These tests define the expected behavior before implementation.

Bug 1: When _apply_changes receives changes={"META": {partial_dict}}, it replaces
the entire META dict instead of merging, dropping CONTRACT and other unmentioned fields.

Bug 2: When content mode overwrites an existing file that has frontmatter, and the
new content lacks frontmatter, the tool should carry over frontmatter from the original.

Bug 3: CONTRACT::HOLOGRAPHIC[JIT_GRAMMAR_COMPILATION] loses its constructor args
during round-trip (emits as HOLOGRAPHIC without the [JIT_GRAMMAR_COMPILATION] part).
"""

import os
import tempfile

import pytest

from octave_mcp.core.emitter import emit
from octave_mcp.core.parser import parse


# ---------------------------------------------------------------------------
# Unit tests: parser/emitter round-trip preserves CONTRACT
# ---------------------------------------------------------------------------
class TestContractRoundTrip:
    """CONTRACT::HOLOGRAPHIC[JIT_GRAMMAR_COMPILATION] survives parse -> emit."""

    def test_contract_holographic_preserved_in_meta(self):
        """CONTRACT field should be present in parsed META dict."""
        content = """===TEST===
META:
  TYPE::AGENT_DEFINITION
  VERSION::"6.0.0"
  CONTRACT::HOLOGRAPHIC[JIT_GRAMMAR_COMPILATION]
§1::IDENTITY
  ROLE::TEST
===END==="""
        doc = parse(content)
        assert "CONTRACT" in doc.meta, "CONTRACT field missing from parsed META"

    def test_contract_holographic_value_preserved(self):
        """CONTRACT value should round-trip faithfully, preserving constructor args."""
        content = """===TEST===
META:
  TYPE::AGENT_DEFINITION
  CONTRACT::HOLOGRAPHIC[JIT_GRAMMAR_COMPILATION]
===END==="""
        doc = parse(content)
        emitted = emit(doc)
        # The value should contain HOLOGRAPHIC and JIT_GRAMMAR_COMPILATION
        assert "CONTRACT::" in emitted
        assert "HOLOGRAPHIC" in emitted
        assert "JIT_GRAMMAR_COMPILATION" in emitted

    def test_contract_survives_full_round_trip(self):
        """CONTRACT should survive parse -> emit -> parse -> emit."""
        content = """===TEST===
META:
  TYPE::AGENT_DEFINITION
  CONTRACT::HOLOGRAPHIC[JIT_GRAMMAR_COMPILATION]
===END==="""
        doc1 = parse(content)
        emitted1 = emit(doc1)
        doc2 = parse(emitted1)
        emitted2 = emit(doc2)
        # Idempotent: second round-trip should match first
        assert emitted1 == emitted2, "CONTRACT round-trip is not idempotent"
        assert "CONTRACT" in doc2.meta


# ---------------------------------------------------------------------------
# Unit tests: parser/emitter round-trip preserves frontmatter
# ---------------------------------------------------------------------------
class TestFrontmatterRoundTrip:
    """YAML frontmatter survives parse -> emit."""

    def test_frontmatter_preserved_in_ast(self):
        """raw_frontmatter should be populated after parse."""
        content = """---
name: test-agent
description: Test agent description
---

===TEST===
META:
  TYPE::AGENT_DEFINITION
===END==="""
        doc = parse(content)
        assert doc.raw_frontmatter is not None
        assert "name: test-agent" in doc.raw_frontmatter

    def test_frontmatter_emitted(self):
        """Frontmatter should appear in emitted output."""
        content = """---
name: test-agent
description: Test agent description
---

===TEST===
META:
  TYPE::AGENT_DEFINITION
===END==="""
        doc = parse(content)
        emitted = emit(doc)
        assert emitted.startswith("---\n")
        assert "name: test-agent" in emitted
        assert "description: Test agent description" in emitted


# ---------------------------------------------------------------------------
# Integration tests: octave_write changes mode preserves META fields
# ---------------------------------------------------------------------------
class TestChangesModeMergesMeta:
    """changes={"META": {partial}} should MERGE with existing META, not replace."""

    @pytest.mark.asyncio
    async def test_changes_meta_dict_merges_not_replaces(self):
        """changes={"META": {"VERSION": "6.2.0"}} should merge, keeping CONTRACT."""
        from octave_mcp.mcp.write import WriteTool

        content = """---
name: test-agent
description: Test agent
---

===TEST_AGENT===
META:
  TYPE::AGENT_DEFINITION
  VERSION::"6.0.0"
  PURPOSE::"Original purpose"
  CONTRACT::HOLOGRAPHIC[JIT_GRAMMAR_COMPILATION]

§1::IDENTITY
  ROLE::TEST
===END===
"""
        tool = WriteTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test.oct.md")
            with open(filepath, "w") as f:
                f.write(content)

            result = await tool.execute(
                target_path=filepath,
                changes={"META": {"VERSION": '"6.2.0"'}},
            )
            assert result["status"] == "success", f"Write failed: {result.get('errors')}"

            with open(filepath) as f:
                written = f.read()

            # CONTRACT should be preserved (was not in changes, should not be removed)
            assert "CONTRACT" in written, "CONTRACT dropped by META changes merge"
            # TYPE should be preserved
            assert "TYPE" in written, "TYPE dropped by META changes merge"
            # VERSION should be updated
            assert "6.2.0" in written, "VERSION not updated"
            # PURPOSE should be preserved (not in changes)
            assert "PURPOSE" in written, "PURPOSE dropped by META changes merge"

    @pytest.mark.asyncio
    async def test_changes_meta_dict_preserves_frontmatter(self):
        """changes mode should preserve YAML frontmatter."""
        from octave_mcp.mcp.write import WriteTool

        content = """---
name: test-agent
description: Test agent
---

===TEST_AGENT===
META:
  TYPE::AGENT_DEFINITION
  VERSION::"6.0.0"
  CONTRACT::HOLOGRAPHIC[JIT_GRAMMAR_COMPILATION]

§1::IDENTITY
  ROLE::TEST
===END===
"""
        tool = WriteTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test.oct.md")
            with open(filepath, "w") as f:
                f.write(content)

            result = await tool.execute(
                target_path=filepath,
                changes={"META": {"VERSION": '"6.2.0"'}},
            )
            assert result["status"] == "success"

            with open(filepath) as f:
                written = f.read()

            assert written.startswith("---\n"), "Frontmatter lost after changes mode"
            assert "name: test-agent" in written

    @pytest.mark.asyncio
    async def test_changes_meta_dot_notation_preserves_contract(self):
        """changes={"META.VERSION": "6.2.0"} should preserve CONTRACT."""
        from octave_mcp.mcp.write import WriteTool

        content = """---
name: test-agent
description: Test agent
---

===TEST_AGENT===
META:
  TYPE::AGENT_DEFINITION
  VERSION::"6.0.0"
  CONTRACT::HOLOGRAPHIC[JIT_GRAMMAR_COMPILATION]

§1::IDENTITY
  ROLE::TEST
===END===
"""
        tool = WriteTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test.oct.md")
            with open(filepath, "w") as f:
                f.write(content)

            result = await tool.execute(
                target_path=filepath,
                changes={"META.VERSION": '"6.2.0"'},
            )
            assert result["status"] == "success"

            with open(filepath) as f:
                written = f.read()

            assert "CONTRACT" in written, "CONTRACT dropped by dot-notation META change"

    @pytest.mark.asyncio
    async def test_changes_meta_delete_field_preserves_others(self):
        """Deleting one META field should not affect others."""
        from octave_mcp.mcp.write import WriteTool

        content = """---
name: test-agent
description: Test agent
---

===TEST_AGENT===
META:
  TYPE::AGENT_DEFINITION
  VERSION::"6.0.0"
  PURPOSE::"Original purpose"
  CONTRACT::HOLOGRAPHIC[JIT_GRAMMAR_COMPILATION]

§1::IDENTITY
  ROLE::TEST
===END===
"""
        tool = WriteTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test.oct.md")
            with open(filepath, "w") as f:
                f.write(content)

            result = await tool.execute(
                target_path=filepath,
                changes={"META.PURPOSE": {"$op": "DELETE"}},
            )
            assert result["status"] == "success"

            with open(filepath) as f:
                written = f.read()

            assert "PURPOSE" not in written, "PURPOSE should be deleted"
            assert "CONTRACT" in written, "CONTRACT should be preserved"
            assert "TYPE" in written, "TYPE should be preserved"


# ---------------------------------------------------------------------------
# Integration tests: content mode preserves frontmatter from existing file
# ---------------------------------------------------------------------------
class TestContentModePreservesFrontmatter:
    """When content overwrites a file, frontmatter from original should be carried over."""

    @pytest.mark.asyncio
    async def test_content_without_frontmatter_inherits_from_existing(self):
        """Content without frontmatter should inherit frontmatter from existing file."""
        from octave_mcp.mcp.write import WriteTool

        original_content = """---
name: test-agent
description: Test agent
---

===TEST_AGENT===
META:
  TYPE::AGENT_DEFINITION
  VERSION::"6.0.0"
  CONTRACT::HOLOGRAPHIC[JIT_GRAMMAR_COMPILATION]

§1::IDENTITY
  ROLE::TEST
===END===
"""
        new_content = """===TEST_AGENT===
META:
  TYPE::AGENT_DEFINITION
  VERSION::"6.2.0"

§1::IDENTITY
  ROLE::TEST
===END==="""

        tool = WriteTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test.oct.md")
            with open(filepath, "w") as f:
                f.write(original_content)

            result = await tool.execute(target_path=filepath, content=new_content)
            assert result["status"] == "success"

            with open(filepath) as f:
                written = f.read()

            assert written.startswith("---\n"), (
                "Frontmatter from original file should be carried over " "when new content lacks frontmatter"
            )
            assert "name: test-agent" in written


# ---------------------------------------------------------------------------
# Normalize mode should preserve everything
# ---------------------------------------------------------------------------
class TestNormalizeModePreservation:
    """Normalize mode (no content, no changes) preserves frontmatter and CONTRACT."""

    @pytest.mark.asyncio
    async def test_normalize_preserves_frontmatter_and_contract(self):
        """Normalize mode should preserve both frontmatter and CONTRACT."""
        from octave_mcp.mcp.write import WriteTool

        content = """---
name: test-agent
description: Test agent
---

===TEST_AGENT===
META:
  TYPE::AGENT_DEFINITION
  VERSION::"6.0.0"
  CONTRACT::HOLOGRAPHIC[JIT_GRAMMAR_COMPILATION]

§1::IDENTITY
  ROLE::TEST
===END===
"""
        tool = WriteTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test.oct.md")
            with open(filepath, "w") as f:
                f.write(content)

            result = await tool.execute(target_path=filepath)
            assert result["status"] == "success", f"Errors: {result.get('errors')}"

            with open(filepath) as f:
                written = f.read()

            assert written.startswith("---\n"), "Frontmatter lost in normalize mode"
            assert "CONTRACT" in written, "CONTRACT lost in normalize mode"
            assert "name: test-agent" in written
