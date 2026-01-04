"""Tests for I1 (Syntactic Fidelity) and I3 (Mirror Constraint) bug fixes.

BUG_1 (MEDIUM): Array single quotes in write.py
- When _apply_changes() applies a Python list, it falls through to str() in emitter
- Produces "['a', 'b']" instead of proper OCTAVE "[a,b]"
- Root cause: Lists not wrapped in ListValue before assignment

BUG_2 (LOW): Markdown ListValue repr in eject.py
- Markdown emitter uses f-strings on AST values directly
- Produces "ListValue(items=[...])" instead of readable format
- Root cause: _convert_value() not called before string interpolation

TDD: RED phase - these tests define the expected behavior.
"""

import os
import tempfile

import pytest


class TestBug1ArraySingleQuotes:
    """Tests for BUG_1: Array single quotes in octave_write changes mode.

    I1 (Syntactic Fidelity): Output must be valid, parseable OCTAVE syntax.
    I3 (Mirror Constraint): Reflect only present data, create nothing (no Python internals).

    Root cause: When _apply_changes() in write.py assigns a Python list to
    section.value, the emitter's fallback at line 99 produces str(value) = "['a', 'b']"
    instead of proper OCTAVE list syntax "[a,b]".

    Fix: Wrap Python lists in ListValue before assignment.
    """

    @pytest.mark.asyncio
    async def test_changes_mode_list_produces_parseable_octave(self):
        """When changes includes a Python list, output must be parseable OCTAVE.

        I1 REQUIREMENT: OCTAVE syntax must be valid after normalization.
        Single quotes like ['a', 'b'] are NOT valid OCTAVE syntax.
        """
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            # Create initial file
            initial = """===TEST===
ITEMS::[old_item]
===END==="""
            with open(target_path, "w") as f:
                f.write(initial)

            # Apply changes with a Python list
            result = await tool.execute(
                target_path=target_path,
                changes={"ITEMS": ["alpha", "beta", "gamma"]},
            )

            assert result["status"] == "success"

            # Read the written file
            with open(target_path) as f:
                content = f.read()

            # I1: Output must NOT contain single quotes from Python list repr
            assert "'" not in content, (
                f"I1 violation: Output contains single quotes from Python list repr.\n"
                f"Expected proper OCTAVE list syntax [a,b], got:\n{content}"
            )

            # I1: Output must be parseable OCTAVE
            from octave_mcp.core.parser import parse

            try:
                parse(content)  # Just verify it parses; we don't need the result
            except Exception as e:
                pytest.fail(f"I1 violation: Output is not parseable OCTAVE: {e}\nContent:\n{content}")

            # I3: The list values should be preserved
            assert "alpha" in content
            assert "beta" in content
            assert "gamma" in content

    @pytest.mark.asyncio
    async def test_changes_mode_list_uses_octave_syntax(self):
        """When changes includes a Python list, output must use OCTAVE list syntax.

        OCTAVE lists use square brackets with comma separation: [a,b,c]
        NOT Python repr: ['a', 'b', 'c']
        """
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            # Create initial file with list
            initial = """===TEST===
TAGS::[initial]
===END==="""
            with open(target_path, "w") as f:
                f.write(initial)

            # Apply changes with Python list
            result = await tool.execute(
                target_path=target_path,
                changes={"TAGS": ["foo", "bar"]},
            )

            assert result["status"] == "success"

            # Read the written file
            with open(target_path) as f:
                content = f.read()

            # Must use OCTAVE syntax: [foo,bar] or ["foo","bar"]
            # NOT Python repr: ['foo', 'bar']
            assert "['foo'" not in content, f"I1 violation: Output uses Python list repr syntax.\nContent:\n{content}"
            # Verify proper OCTAVE list pattern exists
            # OCTAVE uses [a,b] or ["a","b"] - no spaces after commas in canonical form
            assert "TAGS::" in content
            # The list should be in OCTAVE format
            lines = content.split("\n")
            tags_line = next((line for line in lines if "TAGS::" in line), None)
            assert tags_line is not None
            # Should have proper list syntax without Python single quotes
            assert (
                "[foo," in tags_line or '["foo"' in tags_line
            ), f'Expected OCTAVE list syntax [foo,bar] or ["foo","bar"], got: {tags_line}'

    @pytest.mark.asyncio
    async def test_changes_mode_empty_list(self):
        """When changes includes an empty Python list, output must be [].

        Empty list in OCTAVE is just [].
        """
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            # Create initial file
            initial = """===TEST===
ITEMS::[old_item]
===END==="""
            with open(target_path, "w") as f:
                f.write(initial)

            # Apply changes with empty list
            result = await tool.execute(
                target_path=target_path,
                changes={"ITEMS": []},
            )

            assert result["status"] == "success"

            # Read the written file
            with open(target_path) as f:
                content = f.read()

            # Must have empty list syntax
            assert "ITEMS::[]" in content, f"Expected empty list [], got:\n{content}"

    @pytest.mark.asyncio
    async def test_changes_mode_adds_new_list_field(self):
        """When changes adds a new field with a Python list, output must be valid.

        This tests the code path at line 348 in write.py where a new Assignment
        is created for a non-existing field.
        """
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            # Create initial file WITHOUT the field we'll add
            initial = """===TEST===
EXISTING::value
===END==="""
            with open(target_path, "w") as f:
                f.write(initial)

            # Apply changes that adds a NEW field with list value
            result = await tool.execute(
                target_path=target_path,
                changes={"NEW_LIST": ["one", "two", "three"]},
            )

            assert result["status"] == "success"

            # Read the written file
            with open(target_path) as f:
                content = f.read()

            # I1: Output must NOT contain single quotes
            assert "'" not in content, f"I1 violation: New list field uses Python repr syntax.\nContent:\n{content}"

            # I1: Must be parseable
            from octave_mcp.core.parser import parse

            try:
                parse(content)
            except Exception as e:
                pytest.fail(f"I1 violation: Output not parseable: {e}\nContent:\n{content}")

            # Values should be present
            assert "one" in content
            assert "two" in content
            assert "three" in content


class TestBug2MarkdownListValueRepr:
    """Tests for BUG_2: Markdown ListValue repr in octave_eject.

    I3 (Mirror Constraint): Reflect only present data - no Python internals.

    Root cause: _ast_to_markdown() in eject.py uses f-strings directly on
    section.value without converting AST nodes to strings properly.
    ListValue.__repr__ produces "ListValue(items=[...])" instead of readable format.

    Fix: Add _format_markdown_value() helper that converts AST values.
    """

    @pytest.mark.asyncio
    async def test_markdown_format_renders_list_without_repr(self):
        """Markdown output must render lists as readable text, not ListValue repr.

        I3 REQUIREMENT: Mirror constraint - no Python internals in output.
        """
        from octave_mcp.mcp.eject import EjectTool

        tool = EjectTool()

        content = """===TEST===
META:
  VERSION::"1.0"

ITEMS::[alpha, beta, gamma]
===END==="""

        result = await tool.execute(content=content, schema="TEST", format="markdown")

        assert result["output"] is not None

        # I3: Output must NOT contain "ListValue(items=" - this is Python internal repr
        assert (
            "ListValue(items=" not in result["output"]
        ), f"I3 violation: Markdown output exposes Python ListValue repr.\nOutput:\n{result['output']}"

        # I3: Output must NOT contain "ListValue" at all
        assert (
            "ListValue" not in result["output"]
        ), f"I3 violation: Markdown output contains 'ListValue'.\nOutput:\n{result['output']}"

        # The list items should be present in readable form
        assert "alpha" in result["output"]
        assert "beta" in result["output"]
        assert "gamma" in result["output"]

    @pytest.mark.asyncio
    async def test_markdown_format_renders_list_as_comma_separated(self):
        """Markdown lists should render as comma-separated values or bullet points.

        Either format is acceptable:
        - "alpha, beta, gamma" (comma-separated)
        - "- alpha\n- beta\n- gamma" (bullet points)
        """
        from octave_mcp.mcp.eject import EjectTool

        tool = EjectTool()

        content = """===TEST===
META:
  VERSION::"1.0"

TAGS::[one, two, three]
===END==="""

        result = await tool.execute(content=content, schema="TEST", format="markdown")

        output = result["output"]

        # Items should appear in readable form
        assert "one" in output
        assert "two" in output
        assert "three" in output

        # Must NOT have Python repr patterns
        assert "['one'" not in output
        assert "ListValue" not in output

    @pytest.mark.asyncio
    async def test_markdown_format_block_with_list_child(self):
        """Markdown output must handle list values inside blocks correctly.

        This tests the code path at line 129 in eject.py where block children
        are rendered - lists inside blocks should also be formatted properly.
        """
        from octave_mcp.mcp.eject import EjectTool

        tool = EjectTool()

        content = """===TEST===
META:
  VERSION::"1.0"

SECTION:
  ITEMS::[item1, item2]
===END==="""

        result = await tool.execute(content=content, schema="TEST", format="markdown")

        output = result["output"]

        # I3: Output must NOT contain "ListValue"
        assert "ListValue" not in output, f"I3 violation: Block child list shows ListValue repr.\nOutput:\n{output}"

        # Items should be present
        assert "item1" in output
        assert "item2" in output

    @pytest.mark.asyncio
    async def test_markdown_format_empty_list(self):
        """Markdown output must handle empty lists gracefully."""
        from octave_mcp.mcp.eject import EjectTool

        tool = EjectTool()

        content = """===TEST===
META:
  VERSION::"1.0"

EMPTY_LIST::[]
===END==="""

        result = await tool.execute(content=content, schema="TEST", format="markdown")

        output = result["output"]

        # Must NOT have Python repr
        assert "ListValue" not in output

        # Empty list could render as "" or "[]" or "(empty)" - just not ListValue()
        # The key is that it's not the Python repr form

    @pytest.mark.asyncio
    async def test_markdown_format_nested_structures(self):
        """Markdown output must handle nested lists and maps correctly."""
        from octave_mcp.mcp.eject import EjectTool

        tool = EjectTool()

        # Document with both list and non-list values
        content = """===TEST===
META:
  VERSION::"1.0"

SIMPLE::value
LIST::[a, b, c]
===END==="""

        result = await tool.execute(content=content, schema="TEST", format="markdown")

        output = result["output"]

        # Simple values should work
        assert "value" in output

        # List should be formatted without ListValue repr
        assert "ListValue" not in output
        assert "a" in output or "[a" in output  # Items present somehow


class TestRegressionExistingBehavior:
    """Regression tests to ensure fixes don't break existing behavior."""

    @pytest.mark.asyncio
    async def test_write_changes_mode_string_value_unchanged(self):
        """String values in changes mode should continue to work."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            initial = """===TEST===
KEY::old_value
===END==="""
            with open(target_path, "w") as f:
                f.write(initial)

            result = await tool.execute(
                target_path=target_path,
                changes={"KEY": "new_value"},
            )

            assert result["status"] == "success"

            with open(target_path) as f:
                content = f.read()

            assert "new_value" in content
            assert "old_value" not in content

    @pytest.mark.asyncio
    async def test_write_changes_mode_numeric_value_unchanged(self):
        """Numeric values in changes mode should continue to work."""
        from octave_mcp.mcp.write import WriteTool

        tool = WriteTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "test.oct.md")

            initial = """===TEST===
COUNT::0
===END==="""
            with open(target_path, "w") as f:
                f.write(initial)

            result = await tool.execute(
                target_path=target_path,
                changes={"COUNT": 42},
            )

            assert result["status"] == "success"

            with open(target_path) as f:
                content = f.read()

            assert "42" in content

    @pytest.mark.asyncio
    async def test_eject_json_format_still_works(self):
        """JSON format should continue to work correctly."""
        import json

        from octave_mcp.mcp.eject import EjectTool

        tool = EjectTool()

        content = """===TEST===
META:
  VERSION::"1.0"

ITEMS::[a, b, c]
===END==="""

        result = await tool.execute(content=content, schema="TEST", format="json")

        # Should be valid JSON
        parsed = json.loads(result["output"])
        assert "ITEMS" in parsed
        assert parsed["ITEMS"] == ["a", "b", "c"]

    @pytest.mark.asyncio
    async def test_eject_yaml_format_still_works(self):
        """YAML format should continue to work correctly."""
        import yaml

        from octave_mcp.mcp.eject import EjectTool

        tool = EjectTool()

        content = """===TEST===
META:
  VERSION::"1.0"

ITEMS::[a, b, c]
===END==="""

        result = await tool.execute(content=content, schema="TEST", format="yaml")

        # Should be valid YAML
        parsed = yaml.safe_load(result["output"])
        assert "ITEMS" in parsed
        assert parsed["ITEMS"] == ["a", "b", "c"]
