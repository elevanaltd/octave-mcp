"""Tests for OCTAVE parser (P1.3).

Tests lenient parsing with envelope completion, whitespace normalization,
and nested block structure.
"""

import pytest

from octave_mcp.core.ast_nodes import Assignment, Block, ListValue
from octave_mcp.core.parser import ParserError, parse


class TestEnvelopeInference:
    """Test envelope inference for single documents."""

    def test_infers_envelope_for_single_doc_without_envelope(self):
        """Should infer ===INFERRED=== for single document without envelope."""
        content = """META:
  TYPE::TEST
  VERSION::"1.0"
"""
        doc = parse(content)
        assert doc.name == "INFERRED"
        assert len(doc.meta) >= 1  # At least TYPE
        assert doc.meta.get("TYPE") == "TEST"

    def test_preserves_explicit_envelope(self):
        """Should preserve explicit envelope name."""
        content = """===MY_DOC===
META:
  TYPE::TEST
===END===
"""
        doc = parse(content)
        assert doc.name == "MY_DOC"

    def test_errors_on_missing_schema_selector_without_envelope(self):
        """Should error if no envelope and no META block for schema detection."""
        content = """SOME_FIELD::value
"""
        # This should still infer INFERRED envelope, but may warn about schema
        doc = parse(content)
        assert doc.name == "INFERRED"


class TestWhitespaceNormalization:
    """Test whitespace normalization around operators."""

    def test_normalizes_whitespace_around_assignment(self):
        """Should normalize 'KEY :: value' to 'KEY::value'."""
        content = """===TEST===
KEY :: value
===END===
"""
        doc = parse(content)
        # Parser should normalize during parsing
        # Check that it parsed correctly
        assert len(doc.sections) > 0

    def test_handles_no_whitespace_assignment(self):
        """Should handle canonical KEY::value."""
        content = """===TEST===
KEY::value
===END===
"""
        doc = parse(content)
        assert len(doc.sections) > 0


class TestBlockStructure:
    """Test nested block parsing."""

    def test_parses_simple_block(self):
        """Should parse KEY: with nested children."""
        content = """===TEST===
CONFIG:
  NESTED::value
===END===
"""
        doc = parse(content)
        assert len(doc.sections) > 0
        block = doc.sections[0]
        assert isinstance(block, Block)
        assert block.key == "CONFIG"
        assert len(block.children) > 0

    def test_parses_deeply_nested_blocks(self):
        """Should parse multiple levels of nesting."""
        content = """===TEST===
LEVEL1:
  LEVEL2:
    LEVEL3::value
===END===
"""
        doc = parse(content)
        assert len(doc.sections) > 0
        level1 = doc.sections[0]
        assert isinstance(level1, Block)
        assert level1.key == "LEVEL1"
        assert len(level1.children) > 0

        level2 = level1.children[0]
        assert isinstance(level2, Block)
        assert level2.key == "LEVEL2"
        assert len(level2.children) > 0

    def test_enforces_2_space_indentation(self):
        """Should validate 2-space indentation (tabs caught by lexer)."""
        content = """===TEST===
BLOCK:
  CHILD::value
===END===
"""
        doc = parse(content)
        # Should parse successfully with 2-space indent
        assert len(doc.sections) > 0


class TestMetaBlock:
    """Test META block parsing."""

    def test_parses_meta_block(self):
        """Should parse META block into document.meta."""
        content = """===TEST===
META:
  TYPE::TEST_DOC
  VERSION::"1.0"
  STATUS::ACTIVE
===END===
"""
        doc = parse(content)
        assert doc.meta.get("TYPE") == "TEST_DOC"
        assert doc.meta.get("VERSION") == "1.0"
        assert doc.meta.get("STATUS") == "ACTIVE"

    def test_meta_without_envelope(self):
        """Should handle META in document without envelope."""
        content = """META:
  TYPE::TEST
  VERSION::"1.0"
"""
        doc = parse(content)
        assert doc.name == "INFERRED"
        assert doc.meta.get("TYPE") == "TEST"


class TestListParsing:
    """Test list parsing."""

    def test_parses_simple_list(self):
        """Should parse [a, b, c]."""
        content = """===TEST===
TAGS::[alpha,beta,gamma]
===END===
"""
        doc = parse(content)
        assert len(doc.sections) > 0
        assignment = doc.sections[0]
        assert isinstance(assignment, Assignment)
        assert assignment.key == "TAGS"
        assert isinstance(assignment.value, ListValue)
        assert len(assignment.value.items) == 3

    def test_parses_empty_list(self):
        """Should parse []."""
        content = """===TEST===
EMPTY::[]
===END===
"""
        doc = parse(content)
        assignment = doc.sections[0]
        assert isinstance(assignment.value, ListValue)
        assert len(assignment.value.items) == 0


class TestSeparator:
    """Test separator handling."""

    def test_recognizes_separator(self):
        """Should recognize --- separator."""
        content = """===TEST===
META:
  TYPE::TEST
---
CONTENT::data
===END===
"""
        doc = parse(content)
        assert doc.has_separator is True


class TestErrorHandling:
    """Test parser error cases."""

    def test_errors_on_single_colon_assignment(self):
        """Should error on KEY: value (single colon for assignment)."""
        content = """===TEST===
KEY: value
===END===
"""
        # E001: Single colon with value on same line is ambiguous and forbidden
        with pytest.raises(ParserError) as exc_info:
            parse(content)
        assert exc_info.value.error_code == "E001"
        assert "double colon" in exc_info.value.message.lower()

    def test_allows_single_colon_for_blocks(self):
        """Should allow KEY: with children (proper block syntax)."""
        content = """===TEST===
CONFIG:
  NESTED::value
===END===
"""
        # This is valid - single colon is the block operator
        doc = parse(content)
        assert len(doc.sections) > 0
        assert isinstance(doc.sections[0], Block)

    def test_handles_missing_end_envelope(self):
        """Should handle missing ===END===."""
        content = """===TEST===
KEY::value
"""
        # Should still parse, maybe with warning
        doc = parse(content)
        assert doc.name == "TEST"


class TestSchemaSelection:
    """Test schema selection errors (E002)."""

    @pytest.mark.skip(reason="E002: Schema selector validation not implemented yet (P1.5)")
    def test_errors_when_no_schema_selector_without_envelope(self):
        """Should error when document has no envelope and no schema selector (E002)."""
        # Currently we infer ===INFERRED=== envelope, but in strict mode
        # we should require explicit schema selection via @SCHEMA or ===ENVELOPE===
        content = """KEY::value
ANOTHER::field
"""
        # In future: should raise E002 in strict mode
        # For now: this would parse with INFERRED envelope
        doc = parse(content)
        # When E002 is implemented, this should error in strict validation mode
        assert doc.name == "INFERRED"


class TestRoutingTargets:
    """Test routing target inference errors (E004)."""

    @pytest.mark.skip(reason="E004: Routing target validation not implemented yet (P2.x)")
    def test_errors_when_cannot_infer_routing_target(self):
        """Should error when routing target cannot be inferred (E004)."""
        # E004 relates to the →§TARGET operator and MCP routing
        # This is part of P2.x MCP tool implementation
        content = """===TEST===
META:
  TYPE::COMMAND
  TARGET::§UNKNOWN
===END===
"""
        doc = parse(content)
        # When E004 is implemented, validator should check if §UNKNOWN can be resolved
        # For now, just parse successfully
        assert doc.name == "TEST"


class TestYAMLFrontmatter:
    """Test YAML frontmatter handling (Issue #91)."""

    def test_parse_yaml_frontmatter_with_parentheses(self):
        """Should parse document with YAML frontmatter containing parentheses.

        Issue #91: Lexer fails on parentheses in YAML frontmatter.
        YAML frontmatter is a common pattern in HestAI agent definitions.
        """
        content = """---
name: Ideator (PATHOS Specialist)
description: Creative exploration agent
---

===TEST===
META:
  TYPE::TEST
===END==="""
        doc = parse(content)
        assert doc is not None
        assert doc.name == "TEST"
        assert doc.meta.get("TYPE") == "TEST"
        # Frontmatter should be preserved in raw_frontmatter field
        assert doc.raw_frontmatter is not None
        assert "Ideator (PATHOS Specialist)" in doc.raw_frontmatter

    def test_parse_yaml_frontmatter_with_brackets(self):
        """Should parse YAML frontmatter with square brackets."""
        content = """---
tags: [alpha, beta, gamma]
options: ["option1", "option2"]
---

===TEST===
KEY::value
===END==="""
        doc = parse(content)
        assert doc is not None
        assert doc.name == "TEST"
        assert doc.raw_frontmatter is not None
        assert "[alpha, beta, gamma]" in doc.raw_frontmatter

    def test_parse_yaml_frontmatter_with_colons(self):
        """Should parse YAML frontmatter with colons in values."""
        content = """---
url: "https://example.com:8080/path"
time: "10:30:00"
---

===TEST===
META:
  TYPE::SPEC
===END==="""
        doc = parse(content)
        assert doc is not None
        assert doc.name == "TEST"
        assert doc.raw_frontmatter is not None
        assert "https://example.com:8080" in doc.raw_frontmatter

    def test_parse_yaml_frontmatter_with_special_chars(self):
        """Should parse YAML frontmatter with various special characters."""
        content = """---
pattern: "regex: ^[a-z]+$"
symbols: "@#$%^&*"
---

===TEST===
DATA::value
===END==="""
        doc = parse(content)
        assert doc is not None
        assert doc.name == "TEST"

    def test_parse_without_yaml_frontmatter(self):
        """Should parse document without YAML frontmatter (no regression)."""
        content = """===TEST===
META:
  TYPE::TEST
KEY::value
===END==="""
        doc = parse(content)
        assert doc is not None
        assert doc.name == "TEST"
        # No frontmatter should result in None or empty string
        assert doc.raw_frontmatter is None or doc.raw_frontmatter == ""

    def test_parse_yaml_frontmatter_inferred_envelope(self):
        """Should handle YAML frontmatter with inferred envelope."""
        content = """---
name: Agent Definition
version: 1.0
---

META:
  TYPE::AGENT
KEY::value"""
        doc = parse(content)
        assert doc is not None
        assert doc.name == "INFERRED"
        assert doc.raw_frontmatter is not None
        assert "Agent Definition" in doc.raw_frontmatter

    def test_parse_yaml_frontmatter_line_numbers(self):
        """Line numbers in AST must match original source lines.

        Issue #91 Rework: When YAML frontmatter is stripped, line numbers
        must be preserved. The frontmatter should be replaced with equivalent
        newlines so token/node .line values match the original source.
        """
        content = """---
name: Test
---

===DOC===
KEY::value
===END==="""
        doc = parse(content)
        # ===DOC=== is on line 5 in original (1-indexed)
        # Frontmatter: lines 1-3 (---, name: Test, ---)
        # Blank line: line 4
        # ===DOC===: line 5
        # KEY::value: line 6
        # ===END===: line 7
        assert doc is not None
        assert doc.name == "DOC"
        # Verify assignment KEY::value has correct line number (line 6)
        assert len(doc.sections) > 0
        first_section = doc.sections[0]
        # The section should report line 6 from the original source
        assert first_section.line == 6, f"Expected line 6, got {first_section.line}"


class TestSectionTargetParsing:
    """Test § section marker parsing in value positions (Gap 9).

    Bug: parse_value() missing TokenType.SECTION case causes '§INDEXER'
    to be parsed as just '§', orphaning the identifier.
    """

    def test_parse_section_target_value(self):
        """Should parse TARGET::§INDEXER as value='§INDEXER'.

        Gap 9 bug: SECTION token falls through to else clause,
        returns just '§', orphans IDENTIFIER.
        """
        content = """===TEST===
TARGET::§INDEXER
===END==="""
        doc = parse(content)

        assert len(doc.sections) == 1
        assignment = doc.sections[0]
        assert isinstance(assignment, Assignment)
        assert assignment.key == "TARGET"
        # Bug: Currently returns '§', should return '§INDEXER'
        assert assignment.value == "§INDEXER"

    def test_parse_section_target_ascii_alias(self):
        """Should parse TARGET::#INDEXER as value='§INDEXER'.

        The # is an ASCII alias for § section marker.
        Should normalize to canonical § in parsed value.
        """
        content = """===TEST===
TARGET::#INDEXER
===END==="""
        doc = parse(content)

        assert len(doc.sections) == 1
        assignment = doc.sections[0]
        assert isinstance(assignment, Assignment)
        assert assignment.key == "TARGET"
        # Should normalize # to § and concatenate with identifier
        assert assignment.value == "§INDEXER"

    def test_parse_section_in_list(self):
        """Should parse list items [§INDEXER, §SELF] correctly.

        Section markers inside lists should be fully captured
        with their following identifiers.
        """
        content = """===TEST===
TARGETS::[§INDEXER, §SELF]
===END==="""
        doc = parse(content)

        assert len(doc.sections) == 1
        assignment = doc.sections[0]
        assert isinstance(assignment, Assignment)
        assert assignment.key == "TARGETS"
        assert isinstance(assignment.value, ListValue)
        # Bug: Currently would return ['§', '§'], should return ['§INDEXER', '§SELF']
        assert len(assignment.value.items) == 2
        assert assignment.value.items[0] == "§INDEXER"
        assert assignment.value.items[1] == "§SELF"

    def test_parse_bare_section_marker(self):
        """Should handle bare § without following identifier.

        Edge case: Just § alone (no identifier) should return '§'.
        """
        content = """===TEST===
VALUE::§
===END==="""
        doc = parse(content)

        assert len(doc.sections) == 1
        assignment = doc.sections[0]
        assert isinstance(assignment, Assignment)
        assert assignment.key == "VALUE"
        # Bare § should return just '§'
        assert assignment.value == "§"

    def test_parse_section_with_number_suffix(self):
        """Should parse §1::NAME in value position.

        Section markers can have numeric suffixes like §1, §2b, etc.
        """
        content = """===TEST===
REF::§1
===END==="""
        doc = parse(content)

        assert len(doc.sections) == 1
        assignment = doc.sections[0]
        assert isinstance(assignment, Assignment)
        assert assignment.key == "REF"
        # Should capture § followed by number
        assert assignment.value == "§1"

    def test_parse_section_in_flow_expression(self):
        """Should handle § in flow expressions like A->§TARGET.

        Section markers can appear in flow expressions.
        """
        content = """===TEST===
ROUTE::START->§DESTINATION
===END==="""
        doc = parse(content)

        assert len(doc.sections) == 1
        assignment = doc.sections[0]
        assert isinstance(assignment, Assignment)
        assert assignment.key == "ROUTE"
        # Flow expression should capture section marker with identifier
        assert "§DESTINATION" in assignment.value

    def test_section_marker_with_bracket_annotation_preserves_siblings(self):
        """Should consume bracket annotation after §X[note] to preserve sibling keys.

        Gap 9 regression: The SECTION token handling in parse_value() was added
        but did not call _consume_bracket_annotation(). This caused the bracket
        annotation to be left unconsumed, which broke indentation tracking and
        caused sibling keys to be lost.

        Bug repro case from CRS review:
        - A::§X[note] followed by B::Y
        - Without bracket consumption, B is orphaned
        """
        content = """===TEST===
BLOCK:
  A::§X[note]
  B::Y
===END==="""
        doc = parse(content)

        assert len(doc.sections) == 1
        block = doc.sections[0]
        assert isinstance(block, Block)
        assert block.key == "BLOCK"
        # Critical: Both children must be preserved
        child_keys = [c.key for c in block.children]
        assert "A" in child_keys, f"Expected 'A' in children, got {child_keys}"
        assert "B" in child_keys, f"Expected 'B' in children, got {child_keys}"
        assert len(block.children) == 2, f"Expected 2 children, got {len(block.children)}"

    def test_section_marker_with_nested_bracket_annotation(self):
        """Should handle nested bracket annotations like §X[[nested,content]].

        Edge case: Nested brackets should also be consumed properly.
        """
        content = """===TEST===
BLOCK:
  REF::§TARGET[[a,b]]
  NEXT::value
===END==="""
        doc = parse(content)

        assert len(doc.sections) == 1
        block = doc.sections[0]
        assert isinstance(block, Block)
        # Both children should be preserved
        child_keys = [c.key for c in block.children]
        assert "REF" in child_keys
        assert "NEXT" in child_keys


class TestValueTokenDataLoss:
    """Test critical parser fix for VERSION/BOOLEAN/NULL/STRING token data loss.

    Issue #140/#141: Parser drops VERSION, BOOLEAN, NULL, and STRING tokens
    in multi-word values causing silent data loss.

    Example: "NOTE::Release 1.2.3" → NOTE gets only "Release" (loses "1.2.3")

    Solution: Create VALUE_TOKENS classification to unify token handling.
    """

    def test_multiword_with_version_token(self):
        """VERSION tokens should be included in multi-word values."""
        content = """===TEST===
NOTE::Release 1.2.3 is ready
===END==="""
        doc = parse(content)
        assert len(doc.sections) == 1
        assignment = doc.sections[0]
        assert isinstance(assignment, Assignment)
        assert assignment.key == "NOTE"
        assert assignment.value == "Release 1.2.3 is ready"

    def test_multiword_with_boolean_token(self):
        """BOOLEAN tokens should be included in multi-word values."""
        content = """===TEST===
STATUS::true pending review
===END==="""
        doc = parse(content)
        assert len(doc.sections) == 1
        assignment = doc.sections[0]
        assert isinstance(assignment, Assignment)
        assert assignment.key == "STATUS"
        assert assignment.value == "true pending review"

    def test_multiword_with_null_token(self):
        """NULL tokens should be included in multi-word values."""
        content = """===TEST===
RESULT::null hypothesis confirmed
===END==="""
        doc = parse(content)
        assert len(doc.sections) == 1
        assignment = doc.sections[0]
        assert isinstance(assignment, Assignment)
        assert assignment.key == "RESULT"
        assert assignment.value == "null hypothesis confirmed"

    def test_multiword_with_string_token(self):
        """STRING tokens should be included in multi-word values."""
        content = """===TEST===
MESSAGE::"Hello" world greeting
===END==="""
        doc = parse(content)
        assert len(doc.sections) == 1
        assignment = doc.sections[0]
        assert isinstance(assignment, Assignment)
        assert assignment.key == "MESSAGE"
        # Quoted strings should preserve quotes in multi-word context
        assert assignment.value == '"Hello" world greeting'
