"""Tests for GH#310: PATTERN/REGEX values must preserve quotes during normalization.

In GRAMMAR context, PATTERN and REGEX values are string literals for lexical matching.
The normalizer must always emit them quoted, even for single bare-word values that
would normally be emitted bare by needs_quotes().

I1 (SYNTACTIC_FIDELITY): Normalization alters syntax, never semantics.
I4 (TRANSFORM_AUDITABILITY): Auto-quoting bare values must be logged.

TDD: RED phase - these tests define the expected behavior before implementation.
"""

from octave_mcp.core.ast_nodes import Assignment
from octave_mcp.core.emitter import emit, emit_assignment
from octave_mcp.core.parser import parse, parse_with_warnings


class TestPatternRegexQuotePreservation:
    """GH#310: PATTERN/REGEX values must always be quoted in emission."""

    def test_pattern_single_word_preserves_quotes(self):
        """PATTERN::"Workaround" must round-trip as PATTERN::"Workaround", not bare."""
        source = '===TEST===\nGRAMMAR:\n  PATTERN::"Workaround"\n===END===\n'
        doc = parse(source)
        result = emit(doc)
        assert 'PATTERN::"Workaround"' in result

    def test_pattern_multi_word_preserves_quotes(self):
        """PATTERN::"Quick fix src/App.tsx" preserves quotes (multi-word)."""
        source = '===TEST===\nGRAMMAR:\n  PATTERN::"Quick fix src/App.tsx"\n===END===\n'
        doc = parse(source)
        result = emit(doc)
        assert 'PATTERN::"Quick fix src/App.tsx"' in result

    def test_regex_special_chars_preserves_quotes(self):
        """REGEX::"^\\[SYSTEM_STATE\\]" preserves quotes (special chars)."""
        source = '===TEST===\nGRAMMAR:\n  REGEX::"^\\\\[SYSTEM_STATE\\\\]"\n===END===\n'
        doc = parse(source)
        result = emit(doc)
        assert "REGEX::" in result
        # Must be quoted
        regex_line = [line for line in result.split("\n") if "REGEX::" in line][0]
        regex_value = regex_line.split("REGEX::")[1].strip()
        assert regex_value.startswith('"') and regex_value.endswith('"')

    def test_pattern_bare_input_gets_auto_quoted(self):
        """PATTERN::Workaround (bare input) must be auto-quoted to PATTERN::"Workaround"."""
        source = "===TEST===\nGRAMMAR:\n  PATTERN::Workaround\n===END===\n"
        doc = parse(source)
        result = emit(doc)
        assert 'PATTERN::"Workaround"' in result

    def test_non_pattern_key_stays_bare(self):
        """STATUS::active stays bare - only PATTERN/REGEX keys force quotes."""
        source = "===TEST===\nSTATUS::active\n===END===\n"
        doc = parse(source)
        result = emit(doc)
        assert "STATUS::active" in result
        assert 'STATUS::"active"' not in result

    def test_idempotency_pattern_quoted(self):
        """Normalizing PATTERN::"Workaround" twice produces same output."""
        source = '===TEST===\nGRAMMAR:\n  PATTERN::"Workaround"\n===END===\n'
        doc1 = parse(source)
        emitted1 = emit(doc1)
        doc2 = parse(emitted1)
        emitted2 = emit(doc2)
        assert emitted1 == emitted2

    def test_idempotency_pattern_bare(self):
        """Normalizing bare PATTERN::Workaround twice produces same output."""
        source = "===TEST===\nGRAMMAR:\n  PATTERN::Workaround\n===END===\n"
        doc1 = parse(source)
        emitted1 = emit(doc1)
        doc2 = parse(emitted1)
        emitted2 = emit(doc2)
        assert emitted1 == emitted2

    def test_regex_in_list_preserves_quotes(self):
        """REGEX values inside MUST_USE list preserve quotes."""
        source = "===TEST===\n" "GRAMMAR:\n" "  MUST_USE:\n" '    REGEX::"^\\\\[ANALYSIS\\\\]"\n' "===END===\n"
        doc = parse(source)
        result = emit(doc)
        regex_line = [line for line in result.split("\n") if "REGEX::" in line][0]
        regex_value = regex_line.split("REGEX::")[1].strip()
        assert regex_value.startswith('"') and regex_value.endswith('"')

    def test_pattern_in_must_not_list_preserves_quotes(self):
        """PATTERN values inside MUST_NOT list preserve quotes."""
        source = (
            "===TEST===\n"
            "GRAMMAR:\n"
            "  MUST_NOT:\n"
            '    PATTERN::"I will just fix it"\n'
            '    PATTERN::"Skipping tests"\n'
            "===END===\n"
        )
        doc = parse(source)
        result = emit(doc)
        assert 'PATTERN::"I will just fix it"' in result
        assert 'PATTERN::"Skipping tests"' in result


class TestPatternRegexEmitAssignment:
    """Test emit_assignment directly for PATTERN/REGEX key awareness."""

    def test_emit_assignment_pattern_forces_quotes(self):
        """emit_assignment with key=PATTERN must quote even single-word values."""
        assignment = Assignment(key="PATTERN", value="Workaround")
        result = emit_assignment(assignment, indent=1)
        assert 'PATTERN::"Workaround"' in result

    def test_emit_assignment_regex_forces_quotes(self):
        """emit_assignment with key=REGEX must quote even single-word values."""
        assignment = Assignment(key="REGEX", value="identifier")
        result = emit_assignment(assignment, indent=1)
        assert 'REGEX::"identifier"' in result

    def test_emit_assignment_normal_key_bare(self):
        """emit_assignment with normal key keeps bare words bare."""
        assignment = Assignment(key="STATUS", value="active")
        result = emit_assignment(assignment, indent=0)
        assert "STATUS::active" in result
        assert '"active"' not in result


class TestPatternAutoquoteWarning:
    """GH#310 I4: W_PATTERN_AUTOQUOTE warning for bare PATTERN/REGEX values."""

    def test_bare_pattern_emits_warning(self):
        """Bare PATTERN::Workaround should emit W_PATTERN_AUTOQUOTE warning."""
        source = "===TEST===\nGRAMMAR:\n  PATTERN::Workaround\n===END===\n"
        doc, warnings = parse_with_warnings(source)
        autoquote_warnings = [w for w in warnings if w.get("subtype") == "pattern_autoquote"]
        assert len(autoquote_warnings) == 1
        assert autoquote_warnings[0]["key"] == "PATTERN"
        assert autoquote_warnings[0]["value"] == "Workaround"

    def test_quoted_pattern_no_warning(self):
        """Quoted PATTERN::"Workaround" should NOT emit W_PATTERN_AUTOQUOTE warning."""
        source = '===TEST===\nGRAMMAR:\n  PATTERN::"Workaround"\n===END===\n'
        doc, warnings = parse_with_warnings(source)
        autoquote_warnings = [w for w in warnings if w.get("subtype") == "pattern_autoquote"]
        assert len(autoquote_warnings) == 0

    def test_bare_regex_emits_warning(self):
        """Bare REGEX::identifier should emit W_PATTERN_AUTOQUOTE warning."""
        source = "===TEST===\nGRAMMAR:\n  REGEX::identifier\n===END===\n"
        doc, warnings = parse_with_warnings(source)
        autoquote_warnings = [w for w in warnings if w.get("subtype") == "pattern_autoquote"]
        assert len(autoquote_warnings) == 1
        assert autoquote_warnings[0]["key"] == "REGEX"

    def test_non_pattern_key_no_warning(self):
        """Non-PATTERN/REGEX bare values should NOT emit W_PATTERN_AUTOQUOTE."""
        source = "===TEST===\nSTATUS::active\n===END===\n"
        doc, warnings = parse_with_warnings(source)
        autoquote_warnings = [w for w in warnings if w.get("subtype") == "pattern_autoquote"]
        assert len(autoquote_warnings) == 0


class TestInlineMapPatternRegexQuotePreservation:
    """GH#310 rework: PATTERN/REGEX quote preservation in inline-map emission path."""

    def test_inline_map_pattern_quoted_roundtrip(self):
        """GRAMMAR::[PATTERN::"Workaround"] must round-trip with quotes preserved."""
        source = '===TEST===\nGRAMMAR::[PATTERN::"Workaround"]\n===END===\n'
        doc = parse(source)
        result = emit(doc)
        assert 'PATTERN::"Workaround"' in result

    def test_inline_map_pattern_bare_gets_auto_quoted(self):
        """GRAMMAR::[PATTERN::Workaround] (bare) must be auto-quoted to PATTERN::"Workaround"."""
        source = "===TEST===\nGRAMMAR::[PATTERN::Workaround]\n===END===\n"
        doc = parse(source)
        result = emit(doc)
        assert 'PATTERN::"Workaround"' in result

    def test_inline_map_regex_quoted_roundtrip(self):
        """GRAMMAR::[REGEX::"^pattern"] must round-trip with quotes preserved in inline-map."""
        source = '===TEST===\nGRAMMAR::[REGEX::"^pattern"]\n===END===\n'
        doc = parse(source)
        result = emit(doc)
        assert 'REGEX::"^pattern"' in result

    def test_inline_map_pattern_idempotency(self):
        """Normalizing inline-map PATTERN twice produces same output (I1)."""
        source = '===TEST===\nGRAMMAR::[PATTERN::"Workaround"]\n===END===\n'
        doc1 = parse(source)
        emitted1 = emit(doc1)
        doc2 = parse(emitted1)
        emitted2 = emit(doc2)
        assert emitted1 == emitted2

    def test_inline_map_bare_pattern_idempotency(self):
        """Normalizing bare inline-map PATTERN twice produces same output (I1)."""
        source = "===TEST===\nGRAMMAR::[PATTERN::Workaround]\n===END===\n"
        doc1 = parse(source)
        emitted1 = emit(doc1)
        doc2 = parse(emitted1)
        emitted2 = emit(doc2)
        assert emitted1 == emitted2

    def test_multiline_list_pattern_quoted_roundtrip(self):
        """PATTERN in multi-line list (MUST_NOT block with inline-maps) preserves quotes."""
        source = (
            "===TEST===\n"
            "GRAMMAR:\n"
            "  MUST_NOT:[\n"
            '    PATTERN::"I will just fix it",\n'
            '    PATTERN::"Skipping tests"\n'
            "  ]\n"
            "===END===\n"
        )
        doc = parse(source)
        result = emit(doc)
        assert 'PATTERN::"I will just fix it"' in result
        assert 'PATTERN::"Skipping tests"' in result

    def test_inline_map_non_pattern_key_stays_bare(self):
        """Non-PATTERN/REGEX keys in inline-maps keep bare values bare."""
        source = "===TEST===\nDATA::[STATUS::active]\n===END===\n"
        doc = parse(source)
        result = emit(doc)
        assert "STATUS::active" in result
        assert 'STATUS::"active"' not in result


class TestInlineMapPatternAutoquoteWarning:
    """GH#310 rework: W_PATTERN_AUTOQUOTE warning for bare PATTERN/REGEX in inline-map context."""

    def test_bare_pattern_in_inline_map_emits_warning(self):
        """Bare PATTERN::Workaround in inline-map should emit W_PATTERN_AUTOQUOTE warning."""
        source = "===TEST===\nGRAMMAR::[PATTERN::Workaround]\n===END===\n"
        doc, warnings = parse_with_warnings(source)
        autoquote_warnings = [w for w in warnings if w.get("subtype") == "pattern_autoquote"]
        assert len(autoquote_warnings) >= 1
        assert any(w["key"] == "PATTERN" and w["value"] == "Workaround" for w in autoquote_warnings)

    def test_quoted_pattern_in_inline_map_no_autoquote_warning(self):
        """Quoted PATTERN::"Workaround" in inline-map should NOT emit W_PATTERN_AUTOQUOTE."""
        source = '===TEST===\nGRAMMAR::[PATTERN::"Workaround"]\n===END===\n'
        doc, warnings = parse_with_warnings(source)
        autoquote_warnings = [w for w in warnings if w.get("subtype") == "pattern_autoquote"]
        assert len(autoquote_warnings) == 0

    def test_bare_regex_in_inline_map_emits_warning(self):
        """Bare REGEX::identifier in inline-map should emit W_PATTERN_AUTOQUOTE warning."""
        source = "===TEST===\nGRAMMAR::[REGEX::identifier]\n===END===\n"
        doc, warnings = parse_with_warnings(source)
        autoquote_warnings = [w for w in warnings if w.get("subtype") == "pattern_autoquote"]
        assert len(autoquote_warnings) >= 1
        assert any(w["key"] == "REGEX" for w in autoquote_warnings)
