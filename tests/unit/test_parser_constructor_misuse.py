"""Tests for W_CONSTRUCTOR_MISUSE warning detection (GitHub Issue #305).

Per octave-core-spec.oct.md section 2c::BRACKET_FORMS:
  CONSTRUCTOR::NAME[args][e.g._REGEX[pattern]_ENUM[a,b]]

When a known constructor name (REGEX, ENUM, TYPE, PATTERN, NEVER, ALWAYS)
is used as an inline map assignment key (REGEX::"pattern") instead of the
correct constructor form (REGEX["pattern"]), emit W_CONSTRUCTOR_MISUSE.

This is advisory only (I1::SYNTACTIC_FIDELITY) - do NOT auto-fix.
"""

from octave_mcp.core.parser import parse_with_warnings


class TestConstructorMisuseWarning:
    """Test W_CONSTRUCTOR_MISUSE warning for constructor names used as assignment keys."""

    def test_regex_as_assignment_key_triggers_warning(self):
        """REGEX::"pattern" in a list should trigger W_CONSTRUCTOR_MISUSE.

        Per issue #305: REGEX is a known constructor name (section 2c)
        and should use REGEX["pattern"] form, not REGEX::"pattern".
        """
        content = """===TEST===
MUST_USE::[
  REGEX::"Line \\\\d+:"
]
===END==="""
        doc, warnings = parse_with_warnings(content)

        # Document should parse successfully
        assert doc is not None

        # Should emit W_CONSTRUCTOR_MISUSE warning
        constructor_warnings = [w for w in warnings if w.get("subtype") == "constructor_misuse"]
        assert len(constructor_warnings) >= 1, (
            f"Expected W_CONSTRUCTOR_MISUSE warning for REGEX::'pattern', " f"got warnings: {warnings}"
        )

        w = constructor_warnings[0]
        assert w["type"] == "lenient_parse"
        assert w["key"] == "REGEX"
        assert "constructor" in w["message"].lower() or "CONSTRUCTOR" in w["message"]
        assert w.get("line") is not None

    def test_enum_as_assignment_key_triggers_warning(self):
        """ENUM::"value" in a list should trigger W_CONSTRUCTOR_MISUSE."""
        content = """===TEST===
ITEMS::[
  ENUM::"a,b,c"
]
===END==="""
        doc, warnings = parse_with_warnings(content)

        constructor_warnings = [w for w in warnings if w.get("subtype") == "constructor_misuse"]
        assert len(constructor_warnings) >= 1, f"Expected W_CONSTRUCTOR_MISUSE for ENUM, got: {warnings}"
        assert constructor_warnings[0]["key"] == "ENUM"

    def test_type_as_assignment_key_triggers_warning(self):
        """TYPE::"STRING" in a list should trigger W_CONSTRUCTOR_MISUSE."""
        content = """===TEST===
SCHEMA::[
  TYPE::"STRING"
]
===END==="""
        doc, warnings = parse_with_warnings(content)

        constructor_warnings = [w for w in warnings if w.get("subtype") == "constructor_misuse"]
        assert len(constructor_warnings) >= 1
        assert constructor_warnings[0]["key"] == "TYPE"

    def test_pattern_as_assignment_key_triggers_warning(self):
        """PATTERN::"text" in a list should trigger W_CONSTRUCTOR_MISUSE."""
        content = """===TEST===
GRAMMAR::[
  PATTERN::"some text"
]
===END==="""
        doc, warnings = parse_with_warnings(content)

        constructor_warnings = [w for w in warnings if w.get("subtype") == "constructor_misuse"]
        assert len(constructor_warnings) >= 1
        assert constructor_warnings[0]["key"] == "PATTERN"

    def test_never_as_assignment_key_triggers_warning(self):
        """NEVER::"condition" in a list should trigger W_CONSTRUCTOR_MISUSE."""
        content = """===TEST===
RULES::[
  NEVER::"skip tests"
]
===END==="""
        doc, warnings = parse_with_warnings(content)

        constructor_warnings = [w for w in warnings if w.get("subtype") == "constructor_misuse"]
        assert len(constructor_warnings) >= 1
        assert constructor_warnings[0]["key"] == "NEVER"

    def test_always_as_assignment_key_triggers_warning(self):
        """ALWAYS::"condition" in a list should trigger W_CONSTRUCTOR_MISUSE."""
        content = """===TEST===
RULES::[
  ALWAYS::"run tests"
]
===END==="""
        doc, warnings = parse_with_warnings(content)

        constructor_warnings = [w for w in warnings if w.get("subtype") == "constructor_misuse"]
        assert len(constructor_warnings) >= 1
        assert constructor_warnings[0]["key"] == "ALWAYS"

    def test_multiple_constructor_misuses_all_warned(self):
        """Multiple constructor misuses in the same list should each trigger a warning."""
        content = """===TEST===
MUST_USE::[
  REGEX::"Line \\\\d+:",
  REGEX::"CONFIDENCE::(CERTAIN|HIGH)"
]
===END==="""
        doc, warnings = parse_with_warnings(content)

        constructor_warnings = [w for w in warnings if w.get("subtype") == "constructor_misuse"]
        # Both REGEX usages should trigger warnings
        assert (
            len(constructor_warnings) >= 2
        ), f"Expected 2 W_CONSTRUCTOR_MISUSE warnings, got {len(constructor_warnings)}: {warnings}"

    def test_warning_message_suggests_constructor_form(self):
        """Warning message should suggest the correct constructor form."""
        content = """===TEST===
ITEMS::[
  REGEX::"Line \\\\d+:"
]
===END==="""
        doc, warnings = parse_with_warnings(content)

        constructor_warnings = [w for w in warnings if w.get("subtype") == "constructor_misuse"]
        assert len(constructor_warnings) >= 1

        msg = constructor_warnings[0]["message"]
        # Should mention section 2c
        assert "2c" in msg or "§2c" in msg
        # Should suggest constructor form
        assert "REGEX[" in msg

    def test_non_constructor_key_does_not_trigger_warning(self):
        """Normal identifier keys should NOT trigger W_CONSTRUCTOR_MISUSE."""
        content = """===TEST===
ITEMS::[
  NAME::"value",
  FOO::"bar"
]
===END==="""
        doc, warnings = parse_with_warnings(content)

        constructor_warnings = [w for w in warnings if w.get("subtype") == "constructor_misuse"]
        assert (
            len(constructor_warnings) == 0
        ), f"Non-constructor keys should not trigger warning, got: {constructor_warnings}"

    def test_constructor_name_with_non_string_value_no_warning(self):
        """Constructor name with non-string value should NOT trigger warning.

        Per issue #305: Only warn when value is a quoted string, as that
        strongly suggests constructor intent.
        """
        content = """===TEST===
ITEMS::[
  REGEX::some_identifier
]
===END==="""
        doc, warnings = parse_with_warnings(content)

        constructor_warnings = [w for w in warnings if w.get("subtype") == "constructor_misuse"]
        assert (
            len(constructor_warnings) == 0
        ), f"Non-string value should not trigger warning, got: {constructor_warnings}"

    def test_constructor_as_block_key_no_warning(self):
        """Constructor name used as a block-level assignment key (not in list) should NOT warn.

        The warning is specifically for inline map items in lists where
        the constructor form REGEX["pattern"] would be appropriate.
        """
        content = """===TEST===
REGEX::"some value"
===END==="""
        doc, warnings = parse_with_warnings(content)

        constructor_warnings = [w for w in warnings if w.get("subtype") == "constructor_misuse"]
        assert (
            len(constructor_warnings) == 0
        ), f"Block-level assignment should not trigger warning, got: {constructor_warnings}"


class TestConstructorMisuseCorrections:
    """Test that W_CONSTRUCTOR_MISUSE appears in corrections array via write.py."""

    def test_constructor_misuse_in_corrections(self):
        """W_CONSTRUCTOR_MISUSE should appear in corrections from octave_write."""
        from octave_mcp.mcp.write import WriteTool

        handler = WriteTool()
        warnings = [
            {
                "type": "lenient_parse",
                "subtype": "constructor_misuse",
                "key": "REGEX",
                "line": 3,
                "column": 3,
                "value": "Line \\\\d+:",
                "message": (
                    "W_CONSTRUCTOR_MISUSE at line 3: 'REGEX' is a known constructor "
                    "name (§2c) but used as an assignment key. Did you mean "
                    'REGEX["Line \\\\d+:"] (constructor form)?'
                ),
            }
        ]

        corrections = handler._map_parse_warnings_to_corrections(warnings)

        # Should produce a correction with code W_CONSTRUCTOR_MISUSE
        constructor_corrections = [c for c in corrections if c.get("code") == "W_CONSTRUCTOR_MISUSE"]
        assert len(constructor_corrections) == 1, f"Expected W_CONSTRUCTOR_MISUSE correction, got: {corrections}"

        c = constructor_corrections[0]
        assert c["key"] == "REGEX"
        assert c["safe"] is True  # Advisory only, no data loss
        assert c["semantics_changed"] is False  # No auto-fix applied
