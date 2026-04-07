"""GH#357: Regression tests for deeply nested blocks inside section nodes.

Validates that the emitter preserves correct indentation depth for blocks
nested 3+ levels inside section (paragraph) nodes. Section nodes use emit_section()
which delegates to emit_block() for block children, each incrementing indent by 1.

I1 (Syntactic Fidelity): Indentation depth IS semantic content in OCTAVE.
Canonicalization must preserve nesting structure.

TDD Context: Investigation found no reproducible bug in the current emitter
(parse -> emit correctly handles all nesting depths). These tests close the
coverage gap: prior to GH#357, zero tests covered Section nodes with deeply
nested blocks, leaving the codebase vulnerable to silent regressions.
"""

from octave_mcp.core.ast_nodes import Assignment, Block, Document, Section
from octave_mcp.core.emitter import emit, emit_section
from octave_mcp.core.parser import parse


def _build_indent_map(text: str) -> dict[str, int]:
    """Build a map of key -> indentation level from emitted OCTAVE text.

    Parses each non-blank, non-envelope line to extract the key and its
    leading whitespace count.
    """
    indent_map: dict[str, int] = {}
    for line in text.split("\n"):
        stripped = line.lstrip()
        if stripped and not stripped.startswith("==="):
            key = stripped.split("::")[0].rstrip(":")
            indent_map[key] = len(line) - len(stripped)
    return indent_map


class TestSectionWith3PlusLevelNesting:
    """Emitter indentation for blocks nested 3+ levels inside sections."""

    def test_section_with_3_level_nested_blocks(self):
        """Section containing blocks nested 3 levels must preserve indentation.

        Expected indentation (2 spaces per level):
          section header: indent=0
          block level 1:  indent=2  (section child)
          block level 2:  indent=4  (block child)
          assignment:     indent=6  (leaf at depth 3)
        """
        doc = Document(
            name="TEST",
            sections=[
                Section(
                    section_id="5",
                    key="HEALTH_GATES",
                    children=[
                        Block(
                            key="CANARY_METRICS",
                            children=[
                                Block(
                                    key="LATENCY",
                                    children=[
                                        Assignment(key="P99_MAX", value=1000),
                                        Assignment(key="WARNING", value=500),
                                    ],
                                ),
                                Block(
                                    key="ERROR_RATE",
                                    children=[
                                        Assignment(key="THRESHOLD", value=0.01),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )
        result = emit(doc)
        indent_map = _build_indent_map(result)

        # Section header at indent 0
        assert indent_map["\u00a75"] == 0
        # Block level 1 at indent 2
        assert indent_map["CANARY_METRICS"] == 2
        # Block level 2 at indent 4
        assert indent_map["LATENCY"] == 4
        assert indent_map["ERROR_RATE"] == 4
        # Assignments at indent 6
        assert indent_map["P99_MAX"] == 6
        assert indent_map["WARNING"] == 6
        assert indent_map["THRESHOLD"] == 6

    def test_section_with_4_level_nested_blocks(self):
        """Section with 4-level nesting preserves all indentation depths.

        Expected: section(0) -> block(2) -> block(4) -> block(6) -> assignment(8)
        """
        doc = Document(
            name="TEST",
            sections=[
                Section(
                    section_id="5",
                    key="HEALTH_GATES",
                    children=[
                        Block(
                            key="CANARY_METRICS",
                            children=[
                                Block(
                                    key="LATENCY",
                                    children=[
                                        Block(
                                            key="PERCENTILES",
                                            children=[
                                                Assignment(key="P99", value=1000),
                                                Assignment(key="P95", value=800),
                                            ],
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )
        result = emit(doc)

        assert "  CANARY_METRICS:" in result
        assert "    LATENCY:" in result
        assert "      PERCENTILES:" in result
        assert "        P99::1000" in result
        assert "        P95::800" in result

    def test_section_with_5_level_nested_blocks(self):
        """Section with 5-level nesting (deepest realistic case).

        Expected: section(0) -> block(2) -> block(4) -> block(6) -> block(8) -> assign(10)
        """
        doc = Document(
            name="TEST",
            sections=[
                Section(
                    section_id="5",
                    key="DEEP",
                    children=[
                        Block(
                            key="L1",
                            children=[
                                Block(
                                    key="L2",
                                    children=[
                                        Block(
                                            key="L3",
                                            children=[
                                                Block(
                                                    key="L4",
                                                    children=[
                                                        Assignment(key="LEAF", value="deep_value"),
                                                    ],
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )
        result = emit(doc)

        assert "  L1:" in result
        assert "    L2:" in result
        assert "      L3:" in result
        assert "        L4:" in result
        assert "          LEAF::deep_value" in result


class TestSectionWithManySiblingBlocks:
    """GH#357 exact scenario: section with 6 sub-blocks at various depths."""

    def test_section_with_6_sibling_sub_blocks(self):
        """Section with 6 sub-blocks (siblings) at various nesting depths.

        This is the exact scenario from GH#357: 6 nested sub-blocks where
        after canonicalization some nested fields were reportedly flattened
        to the parent level.
        """
        doc = Document(
            name="TEST",
            sections=[
                Section(
                    section_id="5",
                    key="HEALTH_GATES",
                    children=[
                        Block(
                            key="CANARY_METRICS",
                            children=[
                                Block(
                                    key="LATENCY",
                                    children=[
                                        Assignment(key="P99_MAX", value=1000),
                                        Assignment(key="WARNING", value=500),
                                    ],
                                ),
                                Block(
                                    key="ERROR_RATE",
                                    children=[
                                        Assignment(key="THRESHOLD", value=0.01),
                                        Assignment(key="CRITICAL", value=0.05),
                                    ],
                                ),
                                Block(
                                    key="MEMORY",
                                    children=[
                                        Block(
                                            key="HEAP",
                                            children=[
                                                Assignment(key="MAX_GB", value=4),
                                                Assignment(key="WARNING_GB", value=3),
                                            ],
                                        ),
                                        Block(
                                            key="STACK",
                                            children=[
                                                Assignment(key="MAX_MB", value=512),
                                            ],
                                        ),
                                    ],
                                ),
                                Block(
                                    key="CPU",
                                    children=[
                                        Block(
                                            key="USAGE",
                                            children=[
                                                Assignment(key="THRESHOLD", value=80),
                                                Assignment(key="CRITICAL", value=95),
                                            ],
                                        ),
                                        Block(
                                            key="CORES",
                                            children=[
                                                Assignment(key="MIN", value=2),
                                                Assignment(key="RECOMMENDED", value=4),
                                            ],
                                        ),
                                    ],
                                ),
                            ],
                        ),
                        Block(
                            key="SLA_TARGETS",
                            children=[
                                Block(
                                    key="AVAILABILITY",
                                    children=[
                                        Assignment(key="TARGET", value=99.9),
                                    ],
                                ),
                                Block(
                                    key="RESPONSE_TIME",
                                    children=[
                                        Assignment(key="P50", value=100),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )
        result = emit(doc)
        indent_map = _build_indent_map(result)

        # Section-level blocks at indent 2
        assert indent_map["CANARY_METRICS"] == 2
        assert indent_map["SLA_TARGETS"] == 2

        # Second-level blocks at indent 4
        assert indent_map["LATENCY"] == 4
        assert indent_map["ERROR_RATE"] == 4
        assert indent_map["MEMORY"] == 4
        assert indent_map["CPU"] == 4
        assert indent_map["AVAILABILITY"] == 4
        assert indent_map["RESPONSE_TIME"] == 4

        # Third-level blocks at indent 6
        assert indent_map["HEAP"] == 6
        assert indent_map["STACK"] == 6
        assert indent_map["USAGE"] == 6
        assert indent_map["CORES"] == 6

        # Leaf assignments at indent 6 (under second-level blocks)
        assert indent_map["P99_MAX"] == 6
        assert indent_map["TARGET"] == 6
        assert indent_map["P50"] == 6

        # Leaf assignments at indent 8 (under third-level blocks)
        assert indent_map["MAX_GB"] == 8
        assert indent_map["WARNING_GB"] == 8
        assert indent_map["MAX_MB"] == 8
        assert indent_map["MIN"] == 8
        assert indent_map["RECOMMENDED"] == 8


class TestSectionDeepNestingIdempotency:
    """Round-trip and idempotency tests for deeply nested section content."""

    def test_idempotent_3_plus_levels(self):
        """Parse -> emit -> parse -> emit idempotency for deeply nested section content.

        GH#357: Verifies that canonicalization round-trips do not collapse indentation.
        """
        source = (
            "===TEST===\n"
            "\u00a75::HEALTH_GATES\n"
            "  CANARY_METRICS:\n"
            "    LATENCY:\n"
            "      P99_MAX::1000\n"
            "      WARNING::500\n"
            "    ERROR_RATE:\n"
            "      THRESHOLD::0.01\n"
            "      CRITICAL::0.05\n"
            "    MEMORY:\n"
            "      HEAP:\n"
            "        MAX_GB::4\n"
            "        WARNING_GB::3\n"
            "      STACK:\n"
            "        MAX_MB::512\n"
            "    CPU:\n"
            "      USAGE:\n"
            "        THRESHOLD::80\n"
            "        CRITICAL::95\n"
            "      CORES:\n"
            "        MIN::2\n"
            "        RECOMMENDED::4\n"
            "===END==="
        )

        doc1 = parse(source)
        emitted1 = emit(doc1)

        doc2 = parse(emitted1)
        emitted2 = emit(doc2)

        assert emitted1 == emitted2, (
            "Idempotency violated for deeply nested section content.\n"
            f"First emit:\n{emitted1}\nSecond emit:\n{emitted2}"
        )

    def test_round_trip_preserves_5_depth_levels(self):
        """Round-trip parse -> emit preserves AST structure for 5 nesting levels.

        Validates that the parser correctly reconstructs the nesting hierarchy
        from the emitter's canonical indentation output.
        """
        source = (
            "===TEST===\n"
            "\u00a75::HEALTH_GATES\n"
            "  CANARY_METRICS:\n"
            "    LATENCY:\n"
            "      PERCENTILES:\n"
            "        P99:\n"
            "          MAX::1000\n"
            "          WARNING::500\n"
            "        P95:\n"
            "          MAX::800\n"
            "===END==="
        )

        doc = parse(source)
        result = emit(doc)
        indent_map = _build_indent_map(result)

        # Verify all 5 depth levels
        assert indent_map["\u00a75"] == 0  # section header
        assert indent_map["CANARY_METRICS"] == 2  # depth 1
        assert indent_map["LATENCY"] == 4  # depth 2
        assert indent_map["PERCENTILES"] == 6  # depth 3
        assert indent_map["P99"] == 8  # depth 4
        assert indent_map["MAX"] == 10  # depth 5

        # Round-trip: parse the emitted output again
        doc2 = parse(result)
        result2 = emit(doc2)
        assert result == result2

    def test_multiple_sections_each_with_deep_nesting(self):
        """Multiple sibling sections, each containing deeply nested blocks.

        Verifies that sibling section boundaries don't interfere with
        internal nesting indentation.
        """
        source = (
            "===TEST===\n"
            "\u00a71::METRICS\n"
            "  LATENCY:\n"
            "    P99:\n"
            "      MAX::1000\n"
            "\u00a72::ALERTS\n"
            "  CHANNELS:\n"
            "    EMAIL:\n"
            "      RECIPIENTS:\n"
            "        TEAM::engineering\n"
            "\u00a73::SLA\n"
            "  TARGETS:\n"
            "    AVAILABILITY:\n"
            "      NINES::99.99\n"
            "===END==="
        )

        doc = parse(source)
        result = emit(doc)

        # Idempotency
        doc2 = parse(result)
        result2 = emit(doc2)
        assert result == result2

        # Verify each section's deep nesting is preserved
        for line in result.split("\n"):
            stripped = line.lstrip()
            if not stripped or stripped.startswith("==="):
                continue
            indent = len(line) - len(stripped)
            # MAX and NINES should be at depth 6 (3 blocks inside section)
            if "MAX::1000" in stripped:
                assert indent == 6
            if "NINES::99.99" in stripped:
                assert indent == 6
            # TEAM should be at depth 8 (4 blocks inside section)
            if "TEAM::engineering" in stripped:
                assert indent == 8


class TestNestedSectionsWithDeepBlocks:
    """Tests for section-inside-section with deep block nesting."""

    def test_nested_section_inside_section_with_deep_blocks(self):
        """Nested sections (section inside section) with deeply nested blocks.

        Tests the rare but valid case where section nodes are children of
        other section nodes, combined with deep block nesting.
        """
        source = (
            "===TEST===\n"
            "\u00a71::OUTER\n"
            "  \u00a72::INNER\n"
            "    DEEP:\n"
            "      DEEPER:\n"
            "        FIELD::value\n"
            "===END==="
        )

        doc = parse(source)
        result = emit(doc)
        indent_map = _build_indent_map(result)

        assert indent_map["\u00a71"] == 0  # outer section
        assert indent_map["\u00a72"] == 2  # inner section (child)
        assert indent_map["DEEP"] == 4  # block inside inner section
        assert indent_map["DEEPER"] == 6  # nested block
        assert indent_map["FIELD"] == 8  # leaf assignment


class TestEmitSectionDirect:
    """Direct emit_section() unit tests for indentation correctness."""

    def test_emit_section_with_deep_nesting(self):
        """Direct emit_section() call with deeply nested blocks.

        Tests the emit_section() function in isolation to verify
        indentation tracking independent of the full emit() pipeline.
        """
        section = Section(
            section_id="5",
            key="HEALTH_GATES",
            children=[
                Block(
                    key="METRICS",
                    children=[
                        Block(
                            key="LATENCY",
                            children=[
                                Block(
                                    key="P99",
                                    children=[
                                        Assignment(key="MAX", value=1000),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

        result = emit_section(section, indent=0)

        assert result == ("\u00a75::HEALTH_GATES\n" "  METRICS:\n" "    LATENCY:\n" "      P99:\n" "        MAX::1000")

    def test_emit_section_at_nonzero_indent(self):
        """emit_section() called with non-zero indent (section as child of section).

        When a section is a child of another section, its base indent > 0.
        All children must be indented relative to the section's own indent.
        """
        section = Section(
            section_id="2",
            key="INNER",
            children=[
                Block(
                    key="DEEP",
                    children=[
                        Assignment(key="FIELD", value="value"),
                    ],
                ),
            ],
        )

        # Section at indent 1 (child of parent section at indent 0)
        result = emit_section(section, indent=1)

        # Note: "value" is a valid identifier, so emitter does not quote it
        assert result == ("  \u00a72::INNER\n" "    DEEP:\n" "      FIELD::value")
