"""Tests for OCTAVE auto-format options (GitHub Issue #193).

TDD RED phase: Tests written BEFORE implementation.

Tests cover:
1. indent_normalize - Convert all indentation to 2-space standard
2. blank_line_normalize - Normalize blank lines between sections
3. trailing_whitespace - Strip/preserve trailing whitespace
4. key_sorting - Optionally sort keys alphabetically within blocks
"""

from octave_mcp.core.ast_nodes import Assignment, Block, Document, Section
from octave_mcp.core.emitter import FormatOptions, emit


class TestFormatOptionsDataclass:
    """Test FormatOptions dataclass structure and defaults."""

    def test_format_options_exists(self):
        """FormatOptions dataclass should exist and be importable."""
        opts = FormatOptions()
        assert opts is not None

    def test_default_indent_normalize_true(self):
        """indent_normalize should default to True."""
        opts = FormatOptions()
        assert opts.indent_normalize is True

    def test_default_blank_line_normalize_false(self):
        """blank_line_normalize should default to False."""
        opts = FormatOptions()
        assert opts.blank_line_normalize is False

    def test_default_trailing_whitespace_strip(self):
        """trailing_whitespace should default to 'strip'."""
        opts = FormatOptions()
        assert opts.trailing_whitespace == "strip"

    def test_default_key_sorting_false(self):
        """key_sorting should default to False."""
        opts = FormatOptions()
        assert opts.key_sorting is False

    def test_can_override_all_options(self):
        """All options should be configurable."""
        opts = FormatOptions(
            indent_normalize=False,
            blank_line_normalize=True,
            trailing_whitespace="preserve",
            key_sorting=True,
        )
        assert opts.indent_normalize is False
        assert opts.blank_line_normalize is True
        assert opts.trailing_whitespace == "preserve"
        assert opts.key_sorting is True


class TestIndentNormalize:
    """Test indent_normalize option - converts tabs to 2-space standard."""

    def test_emit_accepts_format_options(self):
        """emit() should accept format_options parameter."""
        doc = Document(name="TEST", sections=[Assignment(key="KEY", value="value")])
        # Should not raise
        result = emit(doc, format_options=FormatOptions())
        assert "===TEST===" in result

    def test_tabs_converted_to_2_spaces(self):
        """Tab indentation should be converted to 2-space indentation."""
        # Create a document with nested content that uses indentation
        doc = Document(
            name="TEST",
            sections=[
                Block(
                    key="OUTER",
                    children=[
                        Block(
                            key="INNER",
                            children=[Assignment(key="DEEP", value="value")],
                        )
                    ],
                )
            ],
        )
        opts = FormatOptions(indent_normalize=True)
        result = emit(doc, format_options=opts)

        # Should use 2-space indentation, not tabs
        assert "\t" not in result
        # Check 2-space at first level, 4-space at second level
        lines = result.split("\n")
        inner_line = [ln for ln in lines if "INNER:" in ln][0]
        deep_line = [ln for ln in lines if "DEEP::" in ln][0]
        assert inner_line.startswith("  ")  # 2 spaces
        assert deep_line.startswith("    ")  # 4 spaces

    def test_mixed_indentation_normalized(self):
        """Mixed tab/space indentation should all become 2-space."""
        doc = Document(
            name="TEST",
            sections=[
                Block(
                    key="BLOCK",
                    children=[
                        Assignment(key="CHILD1", value="a"),
                        Assignment(key="CHILD2", value="b"),
                    ],
                )
            ],
        )
        opts = FormatOptions(indent_normalize=True)
        result = emit(doc, format_options=opts)

        lines = result.split("\n")
        child_lines = [ln for ln in lines if "CHILD" in ln]
        for line in child_lines:
            # All should have exactly 2 leading spaces
            stripped = line.lstrip()
            leading = line[: len(line) - len(stripped)]
            assert leading == "  ", f"Expected 2 spaces, got: {repr(leading)}"

    def test_indent_normalize_disabled(self):
        """When disabled, output should still use canonical 2-space format."""
        doc = Document(
            name="TEST",
            sections=[Block(key="BLOCK", children=[Assignment(key="CHILD", value="x")])],
        )
        # Even when disabled, canonical output uses 2-space
        opts = FormatOptions(indent_normalize=False)
        result = emit(doc, format_options=opts)
        assert "  CHILD::x" in result


class TestBlankLineNormalize:
    """Test blank_line_normalize option."""

    def test_single_blank_line_between_sections(self):
        """Should ensure single blank line between top-level sections."""
        doc = Document(
            name="TEST",
            meta={"TYPE": "TEST"},
            sections=[
                Section(section_id="1", key="FIRST", children=[]),
                Section(section_id="2", key="SECOND", children=[]),
            ],
        )
        opts = FormatOptions(blank_line_normalize=True)
        result = emit(doc, format_options=opts)

        # There should be exactly one blank line between sections
        lines = result.split("\n")
        first_idx = None
        second_idx = None
        for i, line in enumerate(lines):
            if "FIRST" in line:
                first_idx = i
            if "SECOND" in line:
                second_idx = i

        # Should have one blank line between sections
        assert first_idx is not None
        assert second_idx is not None
        assert second_idx == first_idx + 2  # One blank line = index difference of 2

    def test_excessive_blank_lines_reduced(self):
        """Multiple consecutive blank lines (>2) should be reduced."""
        doc = Document(
            name="TEST",
            sections=[
                Assignment(key="FIRST", value="a"),
                Assignment(key="SECOND", value="b"),
            ],
        )
        opts = FormatOptions(blank_line_normalize=True)
        result = emit(doc, format_options=opts)

        # Should not have 3+ consecutive blank lines
        assert "\n\n\n" not in result

    def test_blank_line_normalize_disabled_by_default(self):
        """By default, blank_line_normalize is False."""
        doc = Document(
            name="TEST",
            sections=[Assignment(key="KEY", value="value")],
        )
        opts = FormatOptions()  # Default: blank_line_normalize=False
        result = emit(doc, format_options=opts)
        # Should produce standard output without extra blank line manipulation
        assert "===TEST===" in result


class TestTrailingWhitespace:
    """Test trailing_whitespace option."""

    def test_trailing_whitespace_stripped_by_default(self):
        """Trailing whitespace should be stripped by default."""
        doc = Document(
            name="TEST",
            sections=[Assignment(key="KEY", value="value")],
        )
        opts = FormatOptions(trailing_whitespace="strip")
        result = emit(doc, format_options=opts)

        # No line should end with spaces or tabs
        for line in result.split("\n"):
            if line:  # Skip empty lines
                assert line == line.rstrip(), f"Trailing whitespace in: {repr(line)}"

    def test_trailing_whitespace_preserve(self):
        """When preserve mode, trailing whitespace kept if present."""
        doc = Document(
            name="TEST",
            sections=[Assignment(key="KEY", value="value")],
        )
        opts = FormatOptions(trailing_whitespace="preserve")
        result = emit(doc, format_options=opts)
        # In preserve mode, output may have trailing whitespace if AST had it
        # The emitter naturally doesn't add trailing whitespace, so result is same
        assert "===TEST===" in result

    def test_invalid_trailing_whitespace_option(self):
        """Invalid trailing_whitespace value should raise or be handled."""
        # This tests that the dataclass properly validates the option
        # We expect either "strip" or "preserve"
        opts = FormatOptions(trailing_whitespace="invalid")
        # The emit function should either handle gracefully or emit function validates
        doc = Document(name="TEST", sections=[])
        # Should still work but treat as strip (default behavior)
        result = emit(doc, format_options=opts)
        assert "===TEST===" in result


class TestKeySorting:
    """Test key_sorting option."""

    def test_keys_sorted_alphabetically_when_enabled(self):
        """Keys within blocks should be sorted alphabetically when enabled."""
        doc = Document(
            name="TEST",
            meta={"ZEBRA": "z", "ALPHA": "a", "MIDDLE": "m"},
            sections=[
                Block(
                    key="CONFIG",
                    children=[
                        Assignment(key="ZEBRA", value="z"),
                        Assignment(key="ALPHA", value="a"),
                        Assignment(key="MIDDLE", value="m"),
                    ],
                )
            ],
        )
        opts = FormatOptions(key_sorting=True)
        result = emit(doc, format_options=opts)

        lines = result.split("\n")

        # Find META section and check order
        meta_lines = []
        in_meta = False
        for line in lines:
            if line.strip() == "META:":
                in_meta = True
                continue
            if in_meta and line.startswith("  ") and "::" in line:
                meta_lines.append(line.strip().split("::")[0])
            elif in_meta and not line.startswith("  "):
                in_meta = False

        assert meta_lines == sorted(meta_lines), f"META not sorted: {meta_lines}"

        # Find CONFIG block and check order
        config_lines = []
        in_config = False
        for line in lines:
            if "CONFIG:" in line:
                in_config = True
                continue
            if in_config and line.startswith("  ") and "::" in line:
                config_lines.append(line.strip().split("::")[0])
            elif in_config and not line.startswith("  "):
                in_config = False

        assert config_lines == sorted(config_lines), f"CONFIG not sorted: {config_lines}"

    def test_keys_preserve_order_when_disabled(self):
        """Keys should maintain original order when key_sorting is False."""
        doc = Document(
            name="TEST",
            sections=[
                Block(
                    key="CONFIG",
                    children=[
                        Assignment(key="ZEBRA", value="z"),
                        Assignment(key="ALPHA", value="a"),
                        Assignment(key="MIDDLE", value="m"),
                    ],
                )
            ],
        )
        opts = FormatOptions(key_sorting=False)
        result = emit(doc, format_options=opts)

        lines = result.split("\n")
        config_lines = []
        in_config = False
        for line in lines:
            if "CONFIG:" in line:
                in_config = True
                continue
            if in_config and line.startswith("  ") and "::" in line:
                config_lines.append(line.strip().split("::")[0])
            elif in_config and not line.startswith("  "):
                in_config = False

        # Should preserve original order
        assert config_lines == ["ZEBRA", "ALPHA", "MIDDLE"]


class TestBlankLineNormalizeWithChildren:
    """Test blank_line_normalize with sections that have children.

    Critical Engineer review MF1: blank_line_normalize must insert blank lines
    between top-level sections even when prior section has child lines.
    """

    def test_blank_line_between_sections_with_children(self):
        """Sections with children should still have blank line before next section.

        This tests the edge case where prev_was_section tracking was reset
        by child content lines, preventing blank line insertion.
        """
        doc = Document(
            name="TEST",
            sections=[
                Section(
                    section_id="1",
                    key="FIRST",
                    children=[
                        Assignment(key="ALPHA", value="a"),
                        Assignment(key="BETA", value="b"),
                    ],
                ),
                Section(
                    section_id="2",
                    key="SECOND",
                    children=[
                        Assignment(key="GAMMA", value="g"),
                    ],
                ),
            ],
        )
        opts = FormatOptions(blank_line_normalize=True)
        result = emit(doc, format_options=opts)

        lines = result.split("\n")

        # Find the indices of section headers
        first_section_idx = None
        second_section_idx = None
        for i, line in enumerate(lines):
            if "§1::FIRST" in line:
                first_section_idx = i
            if "§2::SECOND" in line:
                second_section_idx = i

        assert first_section_idx is not None, "First section not found"
        assert second_section_idx is not None, "Second section not found"

        # The line immediately before second section should be blank
        # (regardless of how many children the first section has)
        assert lines[second_section_idx - 1].strip() == "", (
            f"Expected blank line before second section. " f"Got: {repr(lines[second_section_idx - 1])}"
        )

    def test_multiple_sections_all_with_children(self):
        """Three sections with children should all have blank lines between them."""
        doc = Document(
            name="TEST",
            sections=[
                Section(
                    section_id="1",
                    key="FIRST",
                    children=[Assignment(key="A", value="1")],
                ),
                Section(
                    section_id="2",
                    key="SECOND",
                    children=[Assignment(key="B", value="2")],
                ),
                Section(
                    section_id="3",
                    key="THIRD",
                    children=[Assignment(key="C", value="3")],
                ),
            ],
        )
        opts = FormatOptions(blank_line_normalize=True)
        result = emit(doc, format_options=opts)

        lines = result.split("\n")

        # Find all section header indices
        section_indices = []
        for i, line in enumerate(lines):
            if line.strip().startswith("§") and "::" in line:
                section_indices.append(i)

        assert len(section_indices) == 3, f"Expected 3 sections, found {len(section_indices)}"

        # Each subsequent section should have a blank line before it
        for i in range(1, len(section_indices)):
            prev_line = lines[section_indices[i] - 1]
            assert prev_line.strip() == "", (
                f"Expected blank line before section at index {section_indices[i]}. " f"Got: {repr(prev_line)}"
            )


class TestFormatOptionsIntegration:
    """Test combining multiple format options."""

    def test_all_options_together(self):
        """All format options should work together."""
        doc = Document(
            name="TEST",
            meta={"TYPE": "TEST", "VERSION": "1.0"},
            sections=[
                Section(
                    section_id="1",
                    key="FIRST",
                    children=[
                        Assignment(key="ZEBRA", value="z"),
                        Assignment(key="ALPHA", value="a"),
                    ],
                ),
                Section(
                    section_id="2",
                    key="SECOND",
                    children=[Assignment(key="KEY", value="value")],
                ),
            ],
        )
        opts = FormatOptions(
            indent_normalize=True,
            blank_line_normalize=True,
            trailing_whitespace="strip",
            key_sorting=True,
        )
        result = emit(doc, format_options=opts)

        # Should have no tabs
        assert "\t" not in result
        # Should have no trailing whitespace
        for line in result.split("\n"):
            if line:
                assert line == line.rstrip()
        # Should not have excessive blank lines
        assert "\n\n\n" not in result
        # Should be valid OCTAVE
        assert "===TEST===" in result
        assert "===END===" in result

    def test_default_options_produce_canonical_output(self):
        """Default FormatOptions should produce standard canonical OCTAVE."""
        doc = Document(
            name="TEST",
            sections=[Block(key="BLOCK", children=[Assignment(key="KEY", value="value")])],
        )
        result_with_opts = emit(doc, format_options=FormatOptions())
        result_without_opts = emit(doc)

        # Should be identical - defaults don't change behavior
        assert result_with_opts == result_without_opts
