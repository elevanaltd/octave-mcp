# D3 Technical Blueprint: Issue #235 Literal Zones

**Version**: 1.0.0
**Date**: 2026-02-16
**Author**: design-architect (PERMIT_SID: eeaa61f7-8ddf-47dd-8449-24027486c132)
**Status**: B0-READY
**Target Release**: v1.3.0

---

## [BLUEPRINT_OVERVIEW]

This blueprint specifies the implementation of literal zones (fenced code blocks) and container preservation in OCTAVE-MCP. It covers all layers of the system: lexer, parser, AST, emitter, validator, constraints, MCP tools, spec, and grammar.

**Three-Zone Model** (from North Star v1.0.2):
1. **Zone 1: Normalizing DSL** -- Core OCTAVE syntax. Operators, keys, values normalized.
2. **Zone 2: Preserving Container** -- YAML frontmatter. Byte-for-byte preservation (already implemented).
3. **Zone 3: Explicit Literal Zones** -- Fenced code blocks. Zero processing. New in v1.3.0.

**Governing Immutables**:
- I1 (Syntactic Fidelity): Literal zones are EXEMPT from normalization -- this fulfills I1 because the semantic intent is "preserve exactly."
- I2 (Deterministic Absence): Empty literal zone is DISTINCT from absent.
- I3 (Mirror Constraint): Nested fences MUST error, not guess.
- I4 (Transform Auditability): Preservation must be logged.
- I5 (Schema Sovereignty): Validation status must report literal zone presence honestly.

---

## [DECISION_LOG]

All six design decisions were resolved through structured debate (2026-02-16) and are APPROVED with UNANIMOUS or STRONG consensus.

| ID | Question | Decision | Rationale |
|----|----------|----------|-----------|
| D1 | AST representation | New `LiteralZoneValue` value type (not ASTNode subclass) | Follows HolographicValue/ListValue precedent. Type safety prevents silent normalization. |
| D2 | Syntax | Backticks only (```) | Triple-quotes remain normalizing strings. Fence-length scaling per CommonMark. No ambiguity. |
| D3 | Escape handling | Zero processing | Content between fences absolutely raw. NFC normalization bypassed for literal spans. |
| D4 | Schema constraints | Envelope/boundary only | Schema validates presence, language tag. Content opaque. validation_status flags. |
| D5 | Container scope | YAML frontmatter only | 100+ files use YAML frontmatter. Zero use other formats. SUBTRACTION principle. |
| D6 | MCP tool behavior | Preserve always + zone-aware audit | Non-configurable preservation. Per-zone reporting in all three tools. |

---

## 1. Updated Core Spec (`octave-core-spec.oct.md`)

### 1.1 Changes to Section 3 (TYPES)

Add after `ESCAPES::...` line 137:

```
LITERAL::```[info_tag][fence_length_scaling_per_CommonMark]
LITERAL_RULES::[
  zero_processing_between_fences,
  NFC_bypass_for_content,
  tabs_allowed_inside_literal_zones,
  info_tag_preserved_not_validated,
  empty_literal_distinct_from_absent
]
```

### 1.2 Changes to Section 2 (OPERATORS)

Add to Section 2c (BRACKET_FORMS), after line 129:

```
LITERAL_FENCE::```[info_tag][content]```[fenced_code_block]
FENCE_SCALING::````[N_backticks_where_N>=3][inner_content_may_contain_shorter_fences]
```

### 1.3 Changes to Section 6b (VALIDATION_CHECKLIST)

Add new subsection after SCHEMA_MODE:

```
LITERAL_ZONES::[
  opening_fence_matches_closing_fence,
  no_nested_fences_of_equal_or_greater_length,
  info_tag_on_opening_fence_only,
  content_between_fences_verbatim,
  empty_literal_zone_is_valid
]
```

### 1.4 Changes to Section 7 (CANONICAL_EXAMPLES)

Add after BLOCK_INHERITANCE_PATTERN:

```
LITERAL_ZONE_PATTERN:
  CODE::```python
    def hello():
        print("hello world")
  ```
  CONFIG::```json
    {"key": "value", "tabs": "\t"}
  ```
  EMPTY_LITERAL::```
  ```
  SCALED_FENCE::````
    Content with ``` inside
  ````
```

---

## 2. Updated EBNF Grammar (`docs/grammar/octave-v1.0-grammar.ebnf`)

### 2.1 New Productions (add as SECTION 4b after SECTION 4)

```ebnf
(* ========================================================================== *)
(* SECTION 4b: LITERAL VALUES (Issue #235)                                    *)
(* Source: lexer.py fence detection, parser.py parse_literal_zone()           *)
(* ========================================================================== *)

(* Literal zone: fenced code block with optional info tag *)
(* Fence must be 3+ backticks; closing fence must match opening length *)
literal_value = code_fence ;

code_fence = opening_fence, [ info_tag ], newline,
             fence_content,
             closing_fence ;

opening_fence = backtick, backtick, backtick, { backtick } ;

closing_fence = backtick, backtick, backtick, { backtick } ;
(* Constraint: closing fence length must equal opening fence length *)

info_tag = identifier ;  (* e.g., python, json, yaml *)

fence_content = { ? any character including tabs and newlines ? } ;
(* Constraint: fence_content must NOT contain a sequence of backticks *)
(* equal to or longer than the opening fence at line start             *)

backtick = "`" ;
```

### 2.2 Integration with `value` Production

Update the existing `value` production in SECTION 4:

```ebnf
value = string_literal
      | number_literal
      | boolean_literal
      | null_literal
      | version_literal
      | variable_reference
      | list_value
      | literal_value          (* NEW: Issue #235 *)
      | section_reference
      | identifier_value
      | flow_expression ;
```

### 2.3 Update Error Codes Appendix (APPENDIX B)

Add:

```ebnf
(*   E006                  Unterminated literal zone (fence not closed)      *)
(*   E007                  Ambiguous nested fence (same or longer fence       *)
(*                         inside literal zone)                               *)
(*                         Subtypes:                                          *)
(*                           E007_NESTED_FENCE   - fence inside literal zone *)
(*                           E007_UNCLOSED_LIST  - existing unclosed list    *)
```

---

## 3. AST Definition

### 3.1 LiteralZoneValue Dataclass

**File**: `src/octave_mcp/core/ast_nodes.py`

Add after the `HolographicValue` dataclass (line 207):

```python
@dataclass
class LiteralZoneValue:
    """Literal zone value (fenced code block).

    Issue #235: Represents content between fence markers (``` or longer).
    Content is preserved exactly as-is -- no NFC normalization, no escape
    processing, no operator normalization, no variable substitution.

    Follows the HolographicValue/ListValue precedent: value type (not
    ASTNode subclass). This ensures exhaustive pattern matching catches
    literal zones and prevents silent normalization through string paths.

    I1: Exempt from normalization (semantic intent is "preserve exactly").
    I2: Empty content ("") is distinct from absent (no LiteralZoneValue).
    I3: Nested fences MUST error at parse time, never reach this node.

    Attributes:
        content: Raw content between fences. Preserved byte-for-byte.
                 Empty string for empty literal zones (```\\n```).
        info_tag: Optional language identifier (e.g., "python", "json").
                  None when no info tag is provided.
                  Preserved but not validated by OCTAVE parser.
        fence_marker: The exact fence string used (e.g., "```", "````").
                      Needed for round-trip emission fidelity.
    """

    content: str = ""
    info_tag: str | None = None
    fence_marker: str = "```"
```

### 3.2 Type Union Updates

The `Assignment.value` field is typed as `Any`, so no type union update is needed at the dataclass level. However, all code that pattern-matches on value types must be updated:

**Exhaustive match points** (must add `LiteralZoneValue` handling):
1. `emitter.py`: `emit_value()` -- line 146
2. `emitter.py`: `is_absent()` / `needs_quotes()` -- no change needed (LiteralZoneValue is not str/Absent)
3. `eject.py`: `_convert_value()` -- line 55
4. `eject.py`: `_format_markdown_value()` -- line 92
5. `validator.py`: `_to_python_value()` -- line 78
6. `write.py`: `_normalize_value_for_ast()` -- line 99
7. `projector.py`: any value traversal
8. `holographic.py`: value extraction (no change -- holographic patterns cannot contain literal zones)
9. `repair.py`: value traversal

### 3.3 Import Updates

In all files that import from `ast_nodes.py`, add `LiteralZoneValue` to the import list.

---

## 4. Lexer Strategy

### 4.1 NFC Bypass: The Critical Path

**Tension T1 (I1)**: The lexer currently applies NFC normalization to the ENTIRE input at line 429 of `lexer.py` before any tokenization. Literal zone content must bypass this.

**Concrete Strategy -- Two-Pass Approach**:

```python
def tokenize(content: str) -> tuple[list[Token], list[Any]]:
    # PHASE 1: Detect fence boundaries in RAW content (BEFORE NFC)
    # This preserves non-NFC characters inside literal zones
    raw_content = content
    fence_spans = _detect_fence_spans(raw_content)

    # PHASE 2: Apply NFC only to NON-LITERAL spans
    # Build a new string where literal spans are preserved raw
    content = _selective_nfc_normalize(raw_content, fence_spans)

    # PHASE 3: Continue with existing tokenization (tab check modified)
    # ...existing code...
```

**`_detect_fence_spans()` specification**:

```python
def _detect_fence_spans(content: str) -> list[tuple[int, int, str, str | None]]:
    """Detect code fence boundaries in raw content BEFORE NFC normalization.

    Scans line-by-line for opening/closing fence patterns.
    A fence is 3+ backtick characters at the START of a line (column 0),
    optionally preceded by up to 3 spaces of indentation.

    Args:
        content: Raw (non-NFC-normalized) content string.

    Returns:
        List of (start_offset, end_offset, fence_marker, info_tag) tuples.
        start_offset: byte offset of the opening fence line start.
        end_offset: byte offset of the closing fence line end.
        fence_marker: the exact backtick sequence (e.g., "```", "````").
        info_tag: the info string if present, or None.

    Raises:
        LexerError: E006 if a fence is opened but never closed.
        LexerError: E007 (subtype E007_NESTED_FENCE) if a fence of
                    equal or greater length appears inside an open fence.
    """
```

**Regex pattern for fence detection**:

```python
# Matches 3+ backticks at line start (with optional 0-3 spaces indent)
# Captures: (1) the backtick sequence, (2) optional info tag
FENCE_PATTERN = re.compile(r'^( {0,3})((`{3,})([^\n`]*)?)$', re.MULTILINE)
```

**`_selective_nfc_normalize()` specification**:

```python
def _selective_nfc_normalize(
    content: str,
    fence_spans: list[tuple[int, int, str, str | None]]
) -> str:
    """Apply NFC normalization only to content OUTSIDE fence spans.

    Args:
        content: Raw content.
        fence_spans: List of (start, end, marker, tag) from _detect_fence_spans.

    Returns:
        Content with NFC applied to non-literal regions,
        literal zone content preserved exactly.
    """
```

### 4.2 Tab Bypass

**Current behavior** (lexer.py line 435): Tabs anywhere in content raise `LexerError E005`.

**Modified behavior**: Tab check must skip fence spans.

```python
# Check for tabs OUTSIDE literal zones only
for i, char in enumerate(content):
    if char == '\t':
        # Check if this position falls within any fence span
        in_literal = any(start <= i < end for start, end, _, _ in fence_spans)
        if not in_literal:
            line = content[:i].count('\n') + 1
            column = len(content[:i].split('\n')[-1]) + 1
            raise LexerError(
                "Tabs are not allowed. Use 2 spaces for indentation.",
                line, column, "E005"
            )
```

**Performance note**: The tab check can be optimized by pre-sorting fence_spans and using binary search, but given typical document sizes (under 100KB), linear scan is acceptable for v1.3.0.

### 4.3 New TokenType Entries

Add to `TokenType` enum (lexer.py):

```python
class TokenType(Enum):
    # ... existing entries ...

    # Literal zone tokens (Issue #235)
    FENCE_OPEN = auto()     # Opening ``` with optional info tag
    FENCE_CLOSE = auto()    # Closing ```
    LITERAL_CONTENT = auto() # Raw content between fences
```

### 4.4 Token Emission for Literal Zones

The tokenizer emits THREE tokens for each literal zone:

1. `FENCE_OPEN` -- value: `{"fence_marker": "```", "info_tag": "python"}` (dict)
2. `LITERAL_CONTENT` -- value: raw string content between fences
3. `FENCE_CLOSE` -- value: `"```"` (the closing fence marker)

This three-token approach allows the parser to reconstruct `LiteralZoneValue` with full fidelity.

### 4.5 Integration with Existing Tokenization Loop

The fence detection happens BEFORE the main tokenization loop. In the main loop, when the tokenizer encounters a position that falls within a fence span, it emits the three literal zone tokens and advances past the span. The existing pattern matching loop is skipped for these positions.

```python
# In the main tokenization while loop, before pattern matching:
if fence_span_idx < len(fence_spans) and pos == fence_spans[fence_span_idx][0]:
    start, end, marker, tag = fence_spans[fence_span_idx]
    # Emit FENCE_OPEN
    tokens.append(Token(TokenType.FENCE_OPEN,
                        {"fence_marker": marker, "info_tag": tag},
                        line, column))
    # Emit LITERAL_CONTENT
    content_start = content.index('\n', start) + 1  # After opening fence line
    content_end = content.rindex('\n', start, end)   # Before closing fence line
    literal_text = raw_content[content_start:content_end]
    # ... update line/column tracking ...
    tokens.append(Token(TokenType.LITERAL_CONTENT, literal_text,
                        content_line, 1))
    # Emit FENCE_CLOSE
    tokens.append(Token(TokenType.FENCE_CLOSE, marker,
                        close_line, close_column))
    pos = end
    fence_span_idx += 1
    continue
```

---

## 5. Parser Strategy

### 5.1 `parse_literal_zone()` Method

**File**: `src/octave_mcp/core/parser.py`

```python
def parse_literal_zone(self) -> LiteralZoneValue:
    """Parse a literal zone from FENCE_OPEN, LITERAL_CONTENT, FENCE_CLOSE tokens.

    Called when parse_value() encounters a FENCE_OPEN token.

    Returns:
        LiteralZoneValue with content, info_tag, and fence_marker.

    Raises:
        ParserError (E006): If FENCE_CLOSE is missing (unterminated zone).
            Message: "E006: Unterminated literal zone starting at line {line}.
            Expected closing fence '{marker}' but reached end of input."
    """
    fence_token = self.expect(TokenType.FENCE_OPEN)
    fence_data = fence_token.value  # dict with fence_marker and info_tag
    marker = fence_data["fence_marker"]
    info_tag = fence_data.get("info_tag")

    # Clean info_tag: strip whitespace, normalize to None if empty
    if info_tag is not None:
        info_tag = info_tag.strip()
        if not info_tag:
            info_tag = None

    # Expect literal content
    if self.current().type == TokenType.LITERAL_CONTENT:
        content = self.current().value
        self.advance()
    else:
        content = ""  # Empty literal zone (I2: distinct from absent)

    # Expect closing fence
    if self.current().type == TokenType.FENCE_CLOSE:
        self.advance()
    else:
        raise ParserError(
            f"Unterminated literal zone starting at line {fence_token.line}. "
            f"Expected closing fence '{marker}' but reached "
            f"{self.current().type.name}.",
            fence_token,
            "E006",
        )

    return LiteralZoneValue(
        content=content,
        info_tag=info_tag,
        fence_marker=marker,
    )
```

### 5.2 Integration with `parse_value()`

In the `parse_value()` method, add a new branch BEFORE the IDENTIFIER branch (order matters because FENCE_OPEN is a distinct token type):

```python
def parse_value(self) -> Any:
    token = self.current()

    if token.type == TokenType.STRING:
        # ... existing ...

    # NEW: Literal zone detection (Issue #235)
    elif token.type == TokenType.FENCE_OPEN:
        return self.parse_literal_zone()

    elif token.type == TokenType.NUMBER:
        # ... existing ...
```

### 5.3 E007 Nested Fence Detection

**Tension T2 (I3)**: E007 is currently used for unclosed lists. Per the design decision, E007 needs subtype discipline.

**Error code allocation**:
- `E007` remains the family code for "structural ambiguity" errors
- Subtypes distinguish the specific issue via the error message prefix

**Detection happens in the lexer** (`_detect_fence_spans()`), not the parser:

```python
# In _detect_fence_spans():
# When scanning inside an open fence, if we encounter another fence
# of equal or greater length, raise E007 with nested fence subtype.

if in_fence and len(backtick_sequence) >= len(current_fence_marker):
    # This is NOT a closing fence (closing must be exact match)
    # This IS a nested fence attempt -- violates I3
    raise LexerError(
        f"E007_NESTED_FENCE: Nested literal zone detected at line {line}. "
        f"Found fence '{backtick_sequence}' (length {len(backtick_sequence)}) "
        f"inside literal zone opened with '{current_fence_marker}' "
        f"(length {len(current_fence_marker)}) at line {open_line}. "
        f"Use a longer fence to wrap content containing shorter fences, "
        f"e.g., ```` to wrap content with ```.",
        line, column, "E007"
    )
```

**Fence closing logic**:

A closing fence MUST have EXACTLY the same number of backticks as the opening fence, at the start of a line (with optional 0-3 spaces indent), with no other content on that line (except optional trailing whitespace).

```python
# Closing fence detection:
# - Must be at start of line (column 0-3)
# - Must have EXACTLY len(current_fence_marker) backticks
# - No non-whitespace characters after the backticks on the same line
if (len(backtick_sequence) == len(current_fence_marker)
    and not trailing_content.strip()):
    # This is the closing fence
    in_fence = False
```

This means:
- ```` (4 backticks) does NOT close ``` (3 backticks)
- ``` (3 backticks) does NOT close ```` (4 backticks)
- Only exact match closes
- Content can contain shorter fence sequences freely

### 5.4 E006 Unclosed Fence Handling

If `_detect_fence_spans()` reaches EOF while a fence is still open:

```python
if in_fence:
    raise LexerError(
        f"E006: Unterminated literal zone. Fence '{current_fence_marker}' "
        f"opened at line {open_line} was never closed. "
        f"Add a matching closing fence: {current_fence_marker}",
        open_line, open_column, "E006"
    )
```

### 5.5 Update TOKEN_PATTERNS and Imports

Add `TokenType.FENCE_OPEN`, `TokenType.FENCE_CLOSE`, `TokenType.LITERAL_CONTENT` to imports in parser.py.

Add `LiteralZoneValue` to imports from `ast_nodes`.

---

## 6. Emitter Strategy

### 6.1 Verbatim Emission

**File**: `src/octave_mcp/core/emitter.py`

Add a branch to `emit_value()` (after the `HolographicValue` branch, before the fallback):

```python
def emit_value(value: Any) -> str:
    # ... existing branches ...

    elif isinstance(value, LiteralZoneValue):
        # I1: Verbatim emission -- no escaping, no normalization
        # The fence_marker and info_tag are reconstructed exactly
        parts = [value.fence_marker]
        if value.info_tag:
            parts.append(value.info_tag)
        parts.append("\n")
        parts.append(value.content)
        # Ensure content ends with newline before closing fence
        if value.content and not value.content.endswith("\n"):
            parts.append("\n")
        parts.append(value.fence_marker)
        return "".join(parts)

    # ... existing fallback ...
```

### 6.2 Indentation Handling

Literal zone content indentation is PRESERVED. The emitter does NOT add indentation to literal zone content lines. Only the opening and closing fence markers receive the current indentation level.

In `emit_assignment()`:

```python
def emit_assignment(assignment: Assignment, indent: int = 0, ...) -> str:
    indent_str = "  " * indent

    if isinstance(assignment.value, LiteralZoneValue):
        # Literal zone: fence markers get indent, content is verbatim
        lz = assignment.value
        lines = []
        # Leading comments
        if hasattr(assignment, "leading_comments"):
            lines.extend(_emit_leading_comments(
                assignment.leading_comments, indent, strip_comments))

        # KEY::```info_tag
        fence_line = f"{indent_str}{assignment.key}::{lz.fence_marker}"
        if lz.info_tag:
            fence_line += lz.info_tag
        lines.append(fence_line)

        # Content lines -- verbatim, NO indent added
        if lz.content:
            for content_line in lz.content.split("\n"):
                lines.append(content_line)

        # Closing fence at same indent as opening
        lines.append(f"{indent_str}{lz.fence_marker}")

        # Trailing comment (after closing fence)
        if hasattr(assignment, "trailing_comment") and assignment.trailing_comment:
            if not strip_comments:
                lines[-1] += f" // {assignment.trailing_comment}"

        return "\n".join(lines)

    # ... existing non-literal path ...
```

### 6.3 Round-Trip Fidelity Requirements

The emitter MUST satisfy this invariant:

```
For any valid OCTAVE document D containing literal zones:
  parse(emit(parse(D))) == parse(D)
```

Specifically:
- `LiteralZoneValue.content` is emitted byte-for-byte
- `LiteralZoneValue.fence_marker` is preserved (backtick count)
- `LiteralZoneValue.info_tag` is preserved (including case)
- Tabs within content survive the round-trip
- Non-NFC characters within content survive the round-trip

---

## 7. Validator/Constraint Strategy

### 7.1 TYPE[LITERAL] Constraint

**Tension T3 (I5)**: No validation theater. Content is opaque.

Add a new constraint type to `constraints.py`:

```python
class LiteralConstraint(Constraint):
    """TYPE[LITERAL] constraint: value must be a LiteralZoneValue.

    Issue #235: Validates that a field contains a literal zone.
    Does NOT validate the content of the literal zone (D4: content opaque).

    I5: Honest about what is validated -- only the presence and type.
    """

    def evaluate(self, value: Any, path: str = "") -> ValidationResult:
        from octave_mcp.core.ast_nodes import LiteralZoneValue

        if not isinstance(value, LiteralZoneValue):
            return ValidationResult(
                valid=False,
                errors=[ValidationError(
                    code="E007",
                    path=path,
                    constraint="TYPE[LITERAL]",
                    expected="LiteralZoneValue",
                    got=type(value).__name__,
                    message=f"Field '{path}' expected LITERAL (fenced code block), "
                            f"got {type(value).__name__}",
                )],
            )
        return ValidationResult(valid=True)
```

### 7.2 LANG[python] Constraint on Info Tag

Add a new constraint type for language tag validation:

```python
class LangConstraint(Constraint):
    """LANG[tag] constraint: literal zone must have matching info_tag.

    Issue #235: Validates the language tag on a literal zone.
    Does NOT validate the content against the language grammar.

    Args:
        expected_lang: Expected language tag (e.g., "python", "json").
    """

    def __init__(self, expected_lang: str):
        self.expected_lang = expected_lang.lower()

    def evaluate(self, value: Any, path: str = "") -> ValidationResult:
        from octave_mcp.core.ast_nodes import LiteralZoneValue

        if not isinstance(value, LiteralZoneValue):
            return ValidationResult(
                valid=False,
                errors=[ValidationError(
                    code="E007",
                    path=path,
                    constraint=f"LANG[{self.expected_lang}]",
                    expected="LiteralZoneValue",
                    got=type(value).__name__,
                    message=f"LANG constraint requires a literal zone, "
                            f"got {type(value).__name__}",
                )],
            )

        actual_tag = (value.info_tag or "").lower()
        if actual_tag != self.expected_lang:
            return ValidationResult(
                valid=False,
                errors=[ValidationError(
                    code="E007",
                    path=path,
                    constraint=f"LANG[{self.expected_lang}]",
                    expected=self.expected_lang,
                    got=actual_tag or "(none)",
                    message=f"Field '{path}' expected language tag "
                            f"'{self.expected_lang}', got '{actual_tag or '(none)'}'",
                )],
            )

        return ValidationResult(valid=True)
```

### 7.3 Constraint Chain Parsing

Update `ConstraintChain.parse()` in `constraints.py` to recognize:
- `TYPE[LITERAL]` -- creates `LiteralConstraint`
- `LANG[python]` -- creates `LangConstraint`

### 7.4 validation_status Flags

Add to validation result dictionaries (in both validate and write tools):

```python
# When document contains literal zones:
result["contains_literal_zones"] = True
result["literal_zone_count"] = count_of_literal_zones

# validation_status interpretation:
# - VALIDATED: DSL syntax checked, literal zone envelope checked,
#              literal zone CONTENT not checked (opaque per D4)
# - The presence of literal_zones_validated:false is honest reporting
result["literal_zones_validated"] = False  # Content is always opaque
```

### 7.5 `_to_python_value()` Update

In `validator.py`, handle `LiteralZoneValue`:

```python
def _to_python_value(self, value: Any) -> Any:
    if isinstance(value, ListValue):
        return [self._to_python_value(item) for item in value.items]
    if isinstance(value, InlineMap):
        return {k: self._to_python_value(v) for k, v in value.pairs.items()}
    if isinstance(value, LiteralZoneValue):
        # Literal zones remain as-is for constraint evaluation
        # TYPE[LITERAL] and LANG[] constraints operate on the object directly
        return value
    return value
```

---

## 8. MCP Tool Updates

### 8.1 octave_validate

**File**: `src/octave_mcp/mcp/validate.py`

Changes:
1. **Per-zone reporting**: Add zone-aware summary to result envelope.
2. **Literal zone detection**: After parsing, count literal zones in AST.
3. **validation_status update**: Include `contains_literal_zones` and `literal_zones_validated` flags.

```python
# After STAGE 1+2 (parse), before STAGE 3 (validate):
literal_zone_count = _count_literal_zones(doc)
if literal_zone_count > 0:
    result["contains_literal_zones"] = True
    result["literal_zone_count"] = literal_zone_count
    result["literal_zones_validated"] = False  # I5: honest
    # Per-zone reporting
    result["zone_report"] = {
        "dsl": {"status": "checked", "errors": []},
        "container": {
            "status": "preserved" if doc.raw_frontmatter else "absent"
        },
        "literal": {
            "status": "preserved",
            "count": literal_zone_count,
            "content_validated": False,  # D4: content opaque
        },
    }
```

**`_count_literal_zones()` utility**:

```python
def _count_literal_zones(doc: Document) -> int:
    """Count LiteralZoneValue instances in document AST."""
    count = 0

    def _traverse(nodes):
        nonlocal count
        for node in nodes:
            if isinstance(node, Assignment):
                if isinstance(node.value, LiteralZoneValue):
                    count += 1
            elif isinstance(node, Block):
                _traverse(node.children)
            elif isinstance(node, Section):
                _traverse(node.children)

    _traverse(doc.sections)
    return count
```

### 8.2 octave_write

**File**: `src/octave_mcp/mcp/write.py`

Changes:
1. **Container preservation**: Already implemented (YAML frontmatter). No changes needed.
2. **Literal zone preservation**: The parse -> emit pipeline now handles literal zones. The existing `_unwrap_markdown_code_fence()` method must be updated to NOT unwrap fences that are INSIDE the document (only the outer transport wrapper).
3. **zone_report**: Same as validate tool.

**Critical update to `_unwrap_markdown_code_fence()`**:

The existing method strips a SINGLE outer markdown fence that wraps the entire document. This is the "transport wrapper" per D5. This behavior must be preserved unchanged. Literal zones INSIDE the document are parsed by the lexer, not stripped by the write tool.

No change needed to `_unwrap_markdown_code_fence()` -- it already only matches a fence that wraps the ENTIRE content (`^\s*```[^\n]*\n([\s\S]*?)\n```\s*$`).

### 8.3 octave_eject

**File**: `src/octave_mcp/mcp/eject.py`

Changes:
1. **`_convert_value()`**: Add `LiteralZoneValue` handling for JSON/YAML export.
2. **`_format_markdown_value()`**: Add `LiteralZoneValue` handling for markdown export.

```python
def _convert_value(value: Any) -> Any:
    if isinstance(value, LiteralZoneValue):
        # Export as string with info_tag metadata
        return {
            "__literal_zone__": True,
            "content": value.content,
            "info_tag": value.info_tag,
            "fence_marker": value.fence_marker,
        }
    # ... existing branches ...

def _format_markdown_value(value: Any) -> str:
    if isinstance(value, LiteralZoneValue):
        # Emit as markdown fenced code block
        parts = [value.fence_marker]
        if value.info_tag:
            parts.append(value.info_tag)
        parts.append("\n")
        parts.append(value.content)
        if value.content and not value.content.endswith("\n"):
            parts.append("\n")
        parts.append(value.fence_marker)
        return "".join(parts)
    # ... existing branches ...
```

### 8.4 Per-Zone Reporting Format

All three MCP tools include `zone_report` when literal zones are present:

```json
{
  "zone_report": {
    "dsl": {
      "status": "checked",
      "errors": ["list of DSL validation errors"]
    },
    "container": {
      "status": "preserved | absent",
      "type": "yaml_frontmatter"
    },
    "literal": {
      "status": "preserved",
      "count": 3,
      "content_validated": false,
      "zones": [
        {"key": "CODE", "info_tag": "python", "line": 15},
        {"key": "CONFIG", "info_tag": "json", "line": 28},
        {"key": "SCRIPT", "info_tag": null, "line": 42}
      ]
    }
  }
}
```

---

## 9. Error Codes

### 9.1 E006: Unterminated Literal Zone

**When**: Opening fence found but no matching closing fence before EOF.

**Error message format**:
```
E006 at line {open_line}, column {open_column}: Unterminated literal zone.
Fence '{marker}' opened at line {open_line} was never closed.
Add a matching closing fence: {marker}
```

**Raised by**: `_detect_fence_spans()` in lexer.py

**Example input**:
```
===DOC===
CODE::```python
def hello():
    pass
===END===
```

### 9.2 E007: Structural Ambiguity (Subtype Discipline)

E007 is now a family code for structural ambiguity errors. Each occurrence includes a subtype in the message:

#### E007_UNCLOSED_LIST (existing)

**When**: List opened with `[` but no matching `]` before EOF.

**Error message format** (unchanged):
```
E007 at line {line}, column {column}: Unclosed list at end of content.
Expected ']' before {token_type}
```

**Raised by**: `parse_list()` in parser.py (unchanged)

#### E007_NESTED_FENCE (new)

**When**: A fence of equal or greater length is detected inside an open fence.

**Error message format**:
```
E007 at line {line}, column {column}: Nested literal zone detected.
Found fence '{inner_marker}' (length {inner_len}) inside literal zone
opened with '{outer_marker}' (length {outer_len}) at line {open_line}.
Use a longer fence to wrap content containing shorter fences,
e.g., ```` to wrap content with ```.
```

**Raised by**: `_detect_fence_spans()` in lexer.py

**Educational guidance** (per I3 -- "ERROR with educational context"):
The error message tells the author HOW to fix the issue (use longer fence), following the established pattern of OCTAVE error messages.

### 9.3 Error Code Summary Table

| Code | Subtype | Source | Description |
|------|---------|--------|-------------|
| E006 | - | lexer.py `_detect_fence_spans()` | Unterminated literal zone |
| E007 | E007_UNCLOSED_LIST | parser.py `parse_list()` | Unclosed bracket (existing) |
| E007 | E007_NESTED_FENCE | lexer.py `_detect_fence_spans()` | Nested fence inside literal zone |

---

## 10. Test Strategy Overview

### 10.1 Test Categories

| Category | Approximate Count | Priority |
|----------|------------------|----------|
| Lexer: fence detection | 25 | HIGH |
| Lexer: NFC bypass | 10 | CRITICAL |
| Lexer: tab bypass | 8 | HIGH |
| Parser: literal zone parsing | 20 | HIGH |
| Parser: error cases | 15 | HIGH |
| Emitter: round-trip | 20 | CRITICAL |
| Emitter: indentation | 10 | HIGH |
| Validator: TYPE[LITERAL] | 10 | MEDIUM |
| Validator: LANG[] constraint | 8 | MEDIUM |
| Validator: validation_status | 8 | HIGH |
| MCP validate: zone reporting | 10 | HIGH |
| MCP write: preservation | 15 | HIGH |
| MCP eject: format export | 10 | MEDIUM |
| Integration: end-to-end | 15 | CRITICAL |
| Property-based | 10 | HIGH |
| **Total** | **~194** | |

### 10.2 Critical Test Cases

#### Round-Trip Fidelity (CRITICAL)

```python
def test_round_trip_literal_zone():
    """Parse -> emit -> parse produces identical AST."""
    content = '''===DOC===
CODE::```python
def hello():
\tprint("hello")  # tab preserved
```
===END==='''
    doc1 = parse(content)
    emitted = emit(doc1)
    doc2 = parse(emitted)
    assert doc1.sections[0].value.content == doc2.sections[0].value.content

def test_round_trip_nfc_bypass():
    """Non-NFC characters inside literal zones survive round-trip."""
    # U+00E9 (e-acute precomposed) vs U+0065 U+0301 (e + combining acute)
    decomposed = "caf\u0065\u0301"  # NFD form
    content = f'===DOC===\nTEXT::```\n{decomposed}\n```\n===END==='
    doc = parse(content)
    assert doc.sections[0].value.content == decomposed  # NOT NFC normalized
```

#### Nested Fence Detection

```python
def test_nested_fence_equal_length_errors():
    """Fence of equal length inside literal zone raises E007."""
    content = '===DOC===\nCODE::```\n```\n```\n===END==='
    with pytest.raises(LexerError, match="E007.*Nested literal zone"):
        parse(content)

def test_nested_fence_longer_errors():
    """Fence longer than opening inside literal zone raises E007."""
    content = '===DOC===\nCODE::```\n````\n```\n===END==='
    with pytest.raises(LexerError, match="E007.*Nested literal zone"):
        parse(content)

def test_shorter_fence_inside_is_content():
    """Fence shorter than opening is treated as content."""
    content = '===DOC===\nCODE::````\n```\nmore content\n````\n===END==='
    doc = parse(content)
    assert "```" in doc.sections[0].value.content
```

#### Tab Bypass

```python
def test_tabs_in_literal_zone_allowed():
    """Tabs inside literal zones do not raise E005."""
    content = '===DOC===\nCODE::```\n\tindented\n```\n===END==='
    doc = parse(content)
    assert "\t" in doc.sections[0].value.content

def test_tabs_outside_literal_zone_still_error():
    """Tabs outside literal zones still raise E005."""
    content = '===DOC===\n\tKEY::value\n===END==='
    with pytest.raises(LexerError, match="E005"):
        parse(content)
```

#### Empty Literal Zone (I2)

```python
def test_empty_literal_zone():
    """Empty literal zone is valid and distinct from absent."""
    content = '===DOC===\nCODE::```\n```\n===END==='
    doc = parse(content)
    lz = doc.sections[0].value
    assert isinstance(lz, LiteralZoneValue)
    assert lz.content == ""  # Empty, not absent

def test_absent_vs_empty_literal():
    """Absent literal zone field vs empty literal zone are distinct."""
    empty = '===DOC===\nCODE::```\n```\n===END==='
    absent = '===DOC===\nOTHER::value\n===END==='
    doc_empty = parse(empty)
    doc_absent = parse(absent)
    assert isinstance(doc_empty.sections[0].value, LiteralZoneValue)
    assert not any(
        isinstance(s.value, LiteralZoneValue)
        for s in doc_absent.sections
        if hasattr(s, 'value')
    )
```

### 10.3 Property-Based Testing

Using Hypothesis:

```python
from hypothesis import given, strategies as st

@given(st.text(min_size=0, max_size=1000))
def test_any_content_round_trips(content):
    """Any string content can be placed in a literal zone and round-trips."""
    # Skip content containing fence sequences
    assume("```" not in content)
    octave = f'===DOC===\nCODE::```\n{content}\n```\n===END==='
    try:
        doc = parse(octave)
        emitted = emit(doc)
        doc2 = parse(emitted)
        assert doc.sections[0].value.content == doc2.sections[0].value.content
    except (LexerError, ParserError):
        pass  # Some content may be invalid OCTAVE outside the fence

@given(st.integers(min_value=3, max_value=10))
def test_fence_length_scaling(n):
    """Any fence length >= 3 works correctly."""
    fence = "`" * n
    content = f'===DOC===\nCODE::{fence}\nhello\n{fence}\n===END==='
    doc = parse(content)
    assert doc.sections[0].value.fence_marker == fence
    assert doc.sections[0].value.content == "hello"
```

### 10.4 Regression Tests

- All existing 1610 tests MUST continue to pass
- Literal zone syntax must not break existing documents
- Triple-quoted strings ("""...""") continue to be normalizing strings, NOT literal zones
- YAML frontmatter handling unchanged
- Markdown code fence unwrapping in write tool unchanged (outer wrapper only)

---

## Appendix A: File Change Summary

| File | Changes |
|------|---------|
| `src/octave_mcp/core/ast_nodes.py` | Add `LiteralZoneValue` dataclass |
| `src/octave_mcp/core/lexer.py` | Add `FENCE_OPEN/CLOSE/LITERAL_CONTENT` token types, `_detect_fence_spans()`, `_selective_nfc_normalize()`, tab bypass, fence detection |
| `src/octave_mcp/core/parser.py` | Add `parse_literal_zone()`, update `parse_value()`, update imports |
| `src/octave_mcp/core/emitter.py` | Update `emit_value()` for `LiteralZoneValue`, update `emit_assignment()` for literal zone indentation |
| `src/octave_mcp/core/validator.py` | Update `_to_python_value()`, add `contains_literal_zones` to results |
| `src/octave_mcp/core/constraints.py` | Add `LiteralConstraint`, `LangConstraint`, update `ConstraintChain.parse()` |
| `src/octave_mcp/mcp/validate.py` | Add zone reporting, literal zone flags |
| `src/octave_mcp/mcp/write.py` | Add zone reporting, literal zone flags |
| `src/octave_mcp/mcp/eject.py` | Update `_convert_value()` and `_format_markdown_value()` |
| `src/octave_mcp/resources/specs/octave-core-spec.oct.md` | Add LITERAL type, validation checklist, examples |
| `docs/grammar/octave-v1.0-grammar.ebnf` | Add literal_value production, update value production, update error codes |

## Appendix B: Implementation Order (Suggested)

Phase 1: Foundation (lexer + AST)
1. `LiteralZoneValue` dataclass in ast_nodes.py
2. New token types in lexer.py
3. `_detect_fence_spans()` with NFC bypass and tab bypass
4. `_selective_nfc_normalize()`
5. Token emission for literal zones in tokenize()

Phase 2: Core Pipeline (parser + emitter)
6. `parse_literal_zone()` in parser.py
7. Integration with `parse_value()`
8. `emit_value()` for LiteralZoneValue
9. `emit_assignment()` for literal zone indentation
10. Round-trip tests

Phase 3: Validation
11. `LiteralConstraint` and `LangConstraint`
12. `_to_python_value()` update
13. validation_status flags

Phase 4: Tools
14. octave_validate zone reporting
15. octave_write zone reporting
16. octave_eject export formats

Phase 5: Spec + Grammar
17. Update octave-core-spec.oct.md
18. Update EBNF grammar

## Appendix C: Backward Compatibility

**Non-breaking change**: Documents without literal zones parse identically before and after this change. The backtick character (`) is currently an unrecognized character in the lexer and would raise `E005: Unexpected character`. Since no existing valid OCTAVE documents contain backticks at line start, this change introduces new syntax without breaking existing documents.

**A9 assumption validation**: The implementation must include a migration test that parses the entire existing `.oct.md` corpus to verify no documents are affected.

---

*End of D3 Technical Blueprint for Issue #235*
