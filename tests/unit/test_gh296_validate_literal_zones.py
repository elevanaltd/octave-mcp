"""Tests for GH#296: octave_validate fails on files containing literal zones.

Bug: FENCE_PATTERN regex only allows 0-3 spaces of indent on backtick fences.
The emitter produces fences at "  " * indent, which can be 4+ spaces for
deeply-nested literal zones. Re-tokenizing such content fails with E005.

TDD RED: These tests must FAIL before the fix is applied.
"""

import pytest

from octave_mcp.core.lexer import FENCE_PATTERN, TokenType, tokenize
from octave_mcp.core.parser import parse_with_warnings
from octave_mcp.mcp.validate import ValidateTool

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALIDATE_TOOL = ValidateTool()

# Content with 2-space indented fences (within 0-3 limit -- should already pass)
DOC_2SPACE_FENCE = """\
===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
EXAMPLE::
  ```python
print("hello")
  ```
===END===
"""

# Content with 4-space indented fences (exceeds 0-3 limit -- the bug)
DOC_4SPACE_FENCE = """\
===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
EXAMPLE::
    ```python
print("hello")
    ```
===END===
"""

# Content with 6-space indented fences (deeper nesting)
DOC_6SPACE_FENCE = """\
===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
EXAMPLE::
      ```python
print("hello")
      ```
===END===
"""

# Emitter-produced content: assignment at indent=2 produces 4-space fences
DOC_EMITTER_INDENT2 = """\
===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"
CODE::
    ```python
def hello():
    pass
    ```
===END===
"""


# ---------------------------------------------------------------------------
# T1: FENCE_PATTERN regex must match 4+ space indented fences
# ---------------------------------------------------------------------------


class TestFencePatternIndent:
    """FENCE_PATTERN must recognize fences with any leading whitespace."""

    def test_fence_pattern_matches_0_spaces(self) -> None:
        """Baseline: 0-space indent matches."""
        assert FENCE_PATTERN.match("```python") is not None

    def test_fence_pattern_matches_2_spaces(self) -> None:
        """Baseline: 2-space indent matches (within 0-3)."""
        assert FENCE_PATTERN.match("  ```python") is not None

    def test_fence_pattern_matches_3_spaces(self) -> None:
        """Baseline: 3-space indent matches (boundary of 0-3)."""
        assert FENCE_PATTERN.match("   ```python") is not None

    def test_fence_pattern_matches_4_spaces(self) -> None:
        """GH#296: 4-space indent must match (emitter indent=2 output)."""
        assert FENCE_PATTERN.match("    ```python") is not None

    def test_fence_pattern_matches_6_spaces(self) -> None:
        """GH#296: 6-space indent must match (emitter indent=3 output)."""
        assert FENCE_PATTERN.match("      ```python") is not None

    def test_fence_pattern_matches_8_spaces(self) -> None:
        """GH#296: 8-space indent must match (emitter indent=4 output)."""
        assert FENCE_PATTERN.match("        ```python") is not None


# ---------------------------------------------------------------------------
# T2: tokenize() must handle 4+ space indented fences
# ---------------------------------------------------------------------------


class TestTokenize4SpaceFence:
    """tokenize() must produce FENCE_OPEN/LITERAL_CONTENT/FENCE_CLOSE for 4+ indent."""

    def test_tokenize_4space_fence_no_error(self) -> None:
        """GH#296: tokenize must not raise E005 on 4-space indented fences."""
        tokens, _ = tokenize(DOC_4SPACE_FENCE)
        token_types = [t.type for t in tokens]
        assert TokenType.FENCE_OPEN in token_types

    def test_tokenize_4space_fence_has_literal_content(self) -> None:
        """GH#296: tokenize must produce LITERAL_CONTENT token."""
        tokens, _ = tokenize(DOC_4SPACE_FENCE)
        token_types = [t.type for t in tokens]
        assert TokenType.LITERAL_CONTENT in token_types

    def test_tokenize_4space_fence_has_close(self) -> None:
        """GH#296: tokenize must produce FENCE_CLOSE token."""
        tokens, _ = tokenize(DOC_4SPACE_FENCE)
        token_types = [t.type for t in tokens]
        assert TokenType.FENCE_CLOSE in token_types

    def test_tokenize_6space_fence_no_error(self) -> None:
        """GH#296: tokenize must not raise E005 on 6-space indented fences."""
        tokens, _ = tokenize(DOC_6SPACE_FENCE)
        token_types = [t.type for t in tokens]
        assert TokenType.FENCE_OPEN in token_types


# ---------------------------------------------------------------------------
# T3: parse_with_warnings() must handle 4+ space indented fences
# ---------------------------------------------------------------------------


class TestParseWithWarnings4SpaceFence:
    """parse_with_warnings must not raise on 4+ space indented fences."""

    def test_parse_4space_fence_succeeds(self) -> None:
        """GH#296: parse must succeed with 4-space indented fences."""
        doc, warnings = parse_with_warnings(DOC_4SPACE_FENCE)
        assert doc is not None
        assert doc.name == "TEST"

    def test_parse_6space_fence_succeeds(self) -> None:
        """GH#296: parse must succeed with 6-space indented fences."""
        doc, warnings = parse_with_warnings(DOC_6SPACE_FENCE)
        assert doc is not None


# ---------------------------------------------------------------------------
# T4: octave_validate MCP tool must handle 4+ space indented fences
# ---------------------------------------------------------------------------


class TestValidateToolLiteralZones:
    """octave_validate tool must succeed on content with indented literal zones."""

    @pytest.mark.asyncio
    async def test_validate_4space_fence_succeeds(self) -> None:
        """GH#296: validate must return status=success for 4-space indented fences."""
        result = await VALIDATE_TOOL.execute(content=DOC_4SPACE_FENCE, schema="META")
        assert result["status"] == "success", f"Expected success, got errors: {result.get('errors')}"

    @pytest.mark.asyncio
    async def test_validate_4space_fence_reports_literal_zones(self) -> None:
        """GH#296: validate must report contains_literal_zones=True."""
        result = await VALIDATE_TOOL.execute(content=DOC_4SPACE_FENCE, schema="META")
        assert result.get("contains_literal_zones") is True

    @pytest.mark.asyncio
    async def test_validate_6space_fence_succeeds(self) -> None:
        """GH#296: validate must return status=success for 6-space indented fences."""
        result = await VALIDATE_TOOL.execute(content=DOC_6SPACE_FENCE, schema="META")
        assert result["status"] == "success", f"Expected success, got errors: {result.get('errors')}"

    @pytest.mark.asyncio
    async def test_validate_emitter_indent2_output(self) -> None:
        """GH#296: validate must succeed on content the emitter produces at indent=2."""
        result = await VALIDATE_TOOL.execute(content=DOC_EMITTER_INDENT2, schema="META")
        assert result["status"] == "success", f"Expected success, got errors: {result.get('errors')}"


# ---------------------------------------------------------------------------
# T5: Round-trip: emit -> re-parse must not lose literal zones
# ---------------------------------------------------------------------------


class TestEmitReparseRoundTrip:
    """Content emitted with indented fences must survive re-parse."""

    def test_emit_reparse_preserves_literal_zone(self) -> None:
        """GH#296: Round-trip parse -> emit -> re-parse must preserve literal zones."""
        from octave_mcp.core.emitter import emit
        from octave_mcp.core.validator import _count_literal_zones

        # Parse a doc with 2-space fences (works)
        doc1, _ = parse_with_warnings(DOC_2SPACE_FENCE)
        zones1 = _count_literal_zones(doc1)
        assert len(zones1) > 0, "Baseline: must have literal zones"

        # Emit canonical form
        canonical = emit(doc1)

        # Re-parse the emitted content (this is where GH#296 fails if indent > 3)
        doc2, _ = parse_with_warnings(canonical)
        zones2 = _count_literal_zones(doc2)
        assert len(zones2) == len(zones1), f"Round-trip lost literal zones: {len(zones1)} -> {len(zones2)}"
