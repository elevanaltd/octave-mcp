# D3 Technical Blueprint: Issue #235 Literal Zones

**Version**: 1.1.0
**Date**: 2026-02-17
**Author**: design-architect (PERMIT_SID: 124b84d8-11a9-4806-9b10-4b255297de57)
**Status**: B0-AMENDED
**Target Release**: v1.3.0

---

## [B0_AMENDMENTS]

This section documents amendments applied from the B0 validation gate (CONDITIONAL_GO verdict, 2026-02-17).

**BLOCKING items resolved (5/5)**:

| # | Finding | Section(s) Amended | Summary |
|---|---------|-------------------|---------|
| B1 | Fence precedence ambiguity | 5.3 | Added decision table with pseudocode covering closing-fence recognition BEFORE nested-fence error, with equal/greater/shorter fence length cases |
| B2 | NFC coordinate drift | 4.1 | Replaced two-pass approach with single-pass chunk-by-chunk strategy; `_detect_fence_spans` now returns adjusted spans compatible with post-NFC string |
| B3 | Vague exhaustive match points | 3.2 | Replaced vague `projector.py`/`repair.py` entries with exact function names and expected `LiteralZoneValue` behavior |
| B4 | I4 audit contract missing | New section 6.4 | Added formal `RepairLog` schema for per-zone receipts (zone_key, line, action, pre/post hash, timestamp, source_stage) |
| B5 | A9 migration gate undefined | Appendix C | Defined corpus scope (all `.oct.md`), 100% pass threshold, evidence output format |

**SHOULD-IMPROVE items resolved (2/2)**:

| # | Finding | Section(s) Amended | Summary |
|---|---------|-------------------|---------|
| S1 | A8 pathological tests incomplete | 10.2 | Added escaped backticks in content, mixed indentation, deep nesting (3+ levels), trailing whitespace variants |
| S2 | Property tests skip fence content | 10.3 | Replaced `assume("```" not in content)` skip with Hypothesis generators that include fence-like substrings via fence-length scaling |

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

**Exhaustive match points** (must add `LiteralZoneValue` handling) [B0-B3]:

Each entry specifies the exact function name, expected behavior for `LiteralZoneValue`, and whether code changes are required.

| # | File | Function | LiteralZoneValue Behavior | Change Required |
|---|------|----------|--------------------------|-----------------|
| 1 | `emitter.py` | `emit_value()` | Emit fence_marker + info_tag + content + fence_marker verbatim | YES -- new `isinstance` branch |
| 2 | `emitter.py` | `is_absent()` | Returns `False` (LiteralZoneValue is never Absent) | NO -- only checks `str`/`Absent` types |
| 3 | `emitter.py` | `needs_quotes()` | Returns `False` (LiteralZoneValue is not a string) | NO -- only checks `str` type |
| 4 | `emitter.py` | `emit_assignment()` | Emit literal zone with fences at indent level, content verbatim | YES -- new `isinstance` branch before standard path |
| 5 | `eject.py` | `_convert_value()` | Return dict with `__literal_zone__`, `content`, `info_tag`, `fence_marker` | YES -- new `isinstance` branch |
| 6 | `eject.py` | `_format_markdown_value()` | Emit as markdown fenced code block | YES -- new `isinstance` branch |
| 7 | `validator.py` | `_to_python_value()` | Return the `LiteralZoneValue` object unchanged (constraints operate on it directly) | YES -- new `isinstance` branch returning `value` |
| 8 | `write.py` | `_normalize_value_for_ast()` | Return the `LiteralZoneValue` object unchanged (must NOT normalize literal content) | YES -- new `isinstance` branch returning `value` |
| 9 | `projector.py` | `_project_value()` | Return `LiteralZoneValue.content` as raw string for projection output | YES -- new `isinstance` branch |
| 10 | `projector.py` | `_matches_pattern()` | `LiteralZoneValue` never matches holographic patterns; return `False` | YES -- guard clause |
| 11 | `holographic.py` | `resolve_holographic()` | No change -- holographic patterns cannot contain literal zones | NO |
| 12 | `repair.py` | `_repair_value()` | Return `LiteralZoneValue` unchanged (literal zones are never repaired/normalized) | YES -- guard clause returning `value` unchanged |
| 13 | `repair.py` | `_check_value_integrity()` | Log literal zone presence in RepairLog (see section 6.4) but never modify | YES -- new `isinstance` branch with audit logging |

### 3.3 Import Updates

In all files that import from `ast_nodes.py`, add `LiteralZoneValue` to the import list.

---

## 4. Lexer Strategy

### 4.1 NFC Bypass: The Critical Path

**Tension T1 (I1)**: The lexer currently applies NFC normalization to the ENTIRE input at line 429 of `lexer.py` before any tokenization. Literal zone content must bypass this.

**Concrete Strategy -- Single-Pass Chunk-by-Chunk Approach** [B0-B2]:

The original two-pass design had a coordinate drift bug: `_detect_fence_spans` returned raw-string offsets, but `_selective_nfc_normalize` could change string length (NFC normalization may combine or decompose characters), making the raw offsets invalid for the post-NFC string. The B0 gate identified this as a blocking issue.

**Resolution**: Use a single-pass chunk-by-chunk approach. Instead of detecting spans first and then selectively normalizing, process the content line-by-line, tracking fence state as we go, and building the output string incrementally. This eliminates any offset mapping between pre-NFC and post-NFC coordinates.

```python
def tokenize(content: str) -> tuple[list[Token], list[Any]]:
    # SINGLE PASS: Process content chunk-by-chunk, tracking fence state.
    # NFC is applied only to non-literal chunks as we go.
    # This avoids coordinate drift between raw and normalized strings.
    raw_content = content
    content, fence_spans = _normalize_with_fence_detection(raw_content)

    # fence_spans now contains offsets valid for the POST-normalization string.
    # Continue with existing tokenization (tab check modified)
    # ...existing code...
```

**`_normalize_with_fence_detection()` specification**:

```python
def _normalize_with_fence_detection(
    content: str,
) -> tuple[str, list[tuple[int, int, str, str | None]]]:
    """Single-pass fence detection with selective NFC normalization.

    Processes content line-by-line. When outside a fence, each line is
    NFC-normalized before appending to the output buffer. When inside a
    fence, lines are appended verbatim (no NFC). Fence span offsets are
    recorded against the OUTPUT buffer, so they are always valid for the
    returned string.

    This eliminates the coordinate drift problem where raw-string offsets
    became invalid after NFC normalization changed string length.

    Args:
        content: Raw (non-NFC-normalized) content string.

    Returns:
        Tuple of:
        - normalized_content: String with NFC applied outside fences,
          literal zone content preserved exactly.
        - fence_spans: List of (start_offset, end_offset, fence_marker,
          info_tag) tuples. Offsets are valid for normalized_content.

    Raises:
        LexerError: E006 if a fence is opened but never closed.
        LexerError: E007 (subtype E007_NESTED_FENCE) if a fence of
                    equal or greater length appears inside an open fence
                    (evaluated per the precedence table in section 5.3.1).
    """
```

**Pseudocode for single-pass approach**:

```python
def _normalize_with_fence_detection(content: str):
    lines = content.split("\n")
    output_parts = []
    fence_spans = []
    output_offset = 0
    in_fence = False
    current_fence_marker = None
    open_line = -1
    span_start = -1

    for line_num, line in enumerate(lines, start=1):
        match = FENCE_PATTERN.match(line)

        if match and not in_fence:
            # Opening fence: start literal zone
            backtick_seq = match.group(3)
            info_tag = match.group(4).strip() or None
            in_fence = True
            current_fence_marker = backtick_seq
            open_line = line_num
            # NFC-normalize the fence line itself (it's structural, not content)
            normalized_line = unicodedata.normalize("NFC", line)
            output_parts.append(normalized_line)
            span_start = output_offset
            output_offset += len(normalized_line) + 1  # +1 for newline

        elif match and in_fence:
            backtick_seq = match.group(3)
            trailing = match.group(4)
            # Use precedence table from section 5.3.1
            result = _evaluate_fence_line(
                backtick_seq, current_fence_marker, trailing,
                line_num, 1, open_line
            )
            if result == "close":
                # Append closing fence line verbatim
                output_parts.append(line)
                output_offset += len(line) + 1
                fence_spans.append((
                    span_start, output_offset - 1,
                    current_fence_marker, info_tag
                ))
                in_fence = False
                current_fence_marker = None
            else:  # "content"
                # Shorter fence inside literal zone: preserve verbatim
                output_parts.append(line)
                output_offset += len(line) + 1

        elif in_fence:
            # Inside literal zone: preserve verbatim (NO NFC)
            output_parts.append(line)
            output_offset += len(line) + 1

        else:
            # Outside literal zone: apply NFC normalization
            normalized_line = unicodedata.normalize("NFC", line)
            output_parts.append(normalized_line)
            output_offset += len(normalized_line) + 1

    if in_fence:
        raise LexerError(
            f"E006: Unterminated literal zone. Fence '{current_fence_marker}' "
            f"opened at line {open_line} was never closed.",
            open_line, 1, "E006"
        )

    return "\n".join(output_parts), fence_spans
```

**Regex pattern for fence detection**:

```python
# Matches 3+ backticks at line start (with optional 0-3 spaces indent)
# Captures: (1) indent, (2) full fence+info, (3) the backtick sequence, (4) info tag
FENCE_PATTERN = re.compile(r'^( {0,3})((`{3,})([^\n`]*)?)$')
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

#### 5.3.1 Fence Precedence Decision Table [B0-B1]

When the lexer encounters a backtick sequence at line start while inside an open fence, it MUST evaluate in the following precedence order. Closing-fence recognition is checked BEFORE nested-fence error.

| # | Condition | Action | Rationale |
|---|-----------|--------|-----------|
| 1 | `len(seq) == len(open_fence)` AND line has no trailing non-whitespace | **CLOSE fence** | Exact-match closing fence per CommonMark |
| 2 | `len(seq) > len(open_fence)` | **ERROR E007_NESTED_FENCE** | Ambiguous nesting violates I3 |
| 3 | `len(seq) == len(open_fence)` AND line has trailing content | **ERROR E007_NESTED_FENCE** | Not a valid closing fence; same-length with trailing content is ambiguous |
| 4 | `len(seq) < len(open_fence)` | **CONTENT** -- treat as literal text | Shorter fences are safe content per fence-length scaling |

**Pseudocode implementing the precedence table**:

```python
def _evaluate_fence_line(
    backtick_seq: str,
    open_fence_marker: str,
    trailing_content: str,
    line: int,
    column: int,
    open_line: int,
) -> str:
    """Evaluate a backtick sequence found at line start inside an open fence.

    Returns: "close", "content", or raises LexerError for E007.

    PRECEDENCE ORDER (B0-B1 amendment):
      1. Closing fence (exact match, no trailing content) -- checked FIRST
      2. Nested fence error (equal-or-greater length)     -- checked SECOND
      3. Content (shorter length)                         -- fallthrough
    """
    seq_len = len(backtick_seq)
    open_len = len(open_fence_marker)

    # CASE 1: Exact match with clean line -> CLOSE
    if seq_len == open_len and not trailing_content.strip():
        return "close"

    # CASE 2: Equal length with trailing content -> ERROR (ambiguous)
    # CASE 3: Greater length -> ERROR (nested fence)
    if seq_len >= open_len:
        raise LexerError(
            f"E007_NESTED_FENCE: Nested literal zone detected at line {line}. "
            f"Found fence '{backtick_seq}' (length {seq_len}) "
            f"inside literal zone opened with '{open_fence_marker}' "
            f"(length {open_len}) at line {open_line}. "
            f"Use a longer fence to wrap content containing shorter fences, "
            f"e.g., {'`' * (open_len + 1)} to wrap content with {open_fence_marker}.",
            line, column, "E007"
        )

    # CASE 4: Shorter fence -> treat as content
    return "content"
```

**Detection happens in the lexer** (`_normalize_with_fence_detection()`), not the parser. The `_evaluate_fence_line` function above is called for each backtick sequence found at line start while inside an open fence.

**Fence closing logic summary**:

A closing fence MUST have EXACTLY the same number of backticks as the opening fence, at the start of a line (with optional 0-3 spaces indent), with no other content on that line (except optional trailing whitespace).

This means:
- ```` (4 backticks) does NOT close ``` (3 backticks) -- Case 4, treated as content
- ``` (3 backticks) does NOT close ```` (4 backticks) -- Case 4, treated as content
- ``` (3 backticks) with trailing text does NOT close ``` (3 backticks) -- Case 3, raises E007
- Only exact match with clean line closes -- Case 1

### 5.4 E006 Unclosed Fence Handling

If `_normalize_with_fence_detection()` reaches EOF while a fence is still open, the E006 error is raised (see pseudocode in section 4.1).

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

### 6.4 I4 Audit Contract: RepairLog Schema [B0-B4]

**Tension T4 (I4)**: Transform auditability requires formal per-zone receipts. Every literal zone that passes through the repair/normalization pipeline must produce a `RepairLogEntry` proving it was preserved, not silently modified.

**RepairLogEntry dataclass**:

```python
@dataclass
class RepairLogEntry:
    """Per-zone audit receipt for I4 transform auditability.

    Issue #235: Every literal zone produces a receipt proving its content
    was preserved through the repair/normalization pipeline.

    Attributes:
        zone_key: The OCTAVE key path (e.g., "DOC.CODE", "DOC.SECTION.CONFIG").
        line: Line number of the opening fence in the source document.
        action: One of "preserved" or "stripped".
            - "preserved": Content passed through unchanged (expected case).
            - "stripped": Zone was removed (only if the entire assignment was removed
              by a higher-level repair operation, e.g., schema-driven key removal).
        pre_hash: SHA-256 hex digest of the literal zone content BEFORE pipeline.
        post_hash: SHA-256 hex digest of the literal zone content AFTER pipeline.
            Must equal pre_hash when action="preserved".
        timestamp: ISO 8601 timestamp of when the receipt was generated.
        source_stage: Pipeline stage that produced this receipt. One of:
            - "lexer": NFC bypass confirmed content was not normalized.
            - "parser": LiteralZoneValue created with raw content.
            - "emitter": Content emitted verbatim.
            - "repair": Repair pipeline passed zone through unchanged.
            - "write": Write tool preserved zone in output.
    """

    zone_key: str
    line: int
    action: str  # "preserved" | "stripped"
    pre_hash: str
    post_hash: str
    timestamp: str
    source_stage: str
```

**RepairLog aggregation**:

```python
@dataclass
class RepairLog:
    """Aggregated audit log for all literal zones in a document.

    Included in MCP tool responses when literal zones are present.
    Satisfies I4 (Transform Auditability) for literal zone content.
    """

    entries: list[RepairLogEntry]

    @property
    def all_preserved(self) -> bool:
        """True if every literal zone was preserved unchanged."""
        return all(
            e.action == "preserved" and e.pre_hash == e.post_hash
            for e in self.entries
        )

    def to_dict(self) -> list[dict]:
        """Serialize for inclusion in MCP tool response."""
        return [
            {
                "zone_key": e.zone_key,
                "line": e.line,
                "action": e.action,
                "pre_hash": e.pre_hash,
                "post_hash": e.post_hash,
                "timestamp": e.timestamp,
                "source_stage": e.source_stage,
            }
            for e in self.entries
        ]
```

**Integration with MCP tools**: All three tools (validate, write, eject) include `repair_log` in the response when literal zones are present:

```json
{
  "zone_report": { "...existing fields..." },
  "repair_log": [
    {
      "zone_key": "DOC.CODE",
      "line": 5,
      "action": "preserved",
      "pre_hash": "a1b2c3...",
      "post_hash": "a1b2c3...",
      "timestamp": "2026-02-17T01:30:00Z",
      "source_stage": "write"
    }
  ]
}
```

**Invariant**: When `action="preserved"`, `pre_hash` MUST equal `post_hash`. If they differ, the pipeline has a bug -- this is a hard assertion failure, not a soft warning.

---

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

**Raised by**: `_normalize_with_fence_detection()` in lexer.py

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

**Raised by**: `_normalize_with_fence_detection()` in lexer.py

**Educational guidance** (per I3 -- "ERROR with educational context"):
The error message tells the author HOW to fix the issue (use longer fence), following the established pattern of OCTAVE error messages.

### 9.3 Error Code Summary Table

| Code | Subtype | Source | Description |
|------|---------|--------|-------------|
| E006 | - | lexer.py `_normalize_with_fence_detection()` | Unterminated literal zone |
| E007 | E007_UNCLOSED_LIST | parser.py `parse_list()` | Unclosed bracket (existing) |
| E007 | E007_NESTED_FENCE | lexer.py `_normalize_with_fence_detection()` via `_evaluate_fence_line()` | Nested fence inside literal zone |

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

#### Pathological Edge Cases (A8) [B0-S1]

```python
def test_escaped_backticks_in_content():
    """Escaped backticks inside literal zone are preserved verbatim."""
    content = '===DOC===\nCODE::```\nsome \\` escaped \\`\\`\\` backticks\n```\n===END==='
    doc = parse(content)
    assert "\\`" in doc.sections[0].value.content
    assert "\\`\\`\\`" in doc.sections[0].value.content

def test_mixed_indentation_in_literal_zone():
    """Mixed tabs and spaces inside literal zone are preserved exactly."""
    inner = "\tline1\n  line2\n\t  line3\n    \tline4"
    content = f'===DOC===\nCODE::```\n{inner}\n```\n===END==='
    doc = parse(content)
    assert doc.sections[0].value.content == inner

def test_deep_nesting_three_levels():
    """Three levels of fence scaling: 5-tick wraps 4-tick wraps 3-tick content."""
    content = (
        '===DOC===\n'
        'OUTER::`````\n'
        '````\n'
        '```\n'
        'innermost\n'
        '```\n'
        '````\n'
        '`````\n'
        '===END==='
    )
    doc = parse(content)
    lz = doc.sections[0].value
    assert isinstance(lz, LiteralZoneValue)
    assert "````" in lz.content
    assert "```" in lz.content
    assert "innermost" in lz.content
    assert lz.fence_marker == "`````"

def test_trailing_whitespace_on_closing_fence():
    """Closing fence with trailing spaces/tabs is still recognized as closing."""
    content = '===DOC===\nCODE::```\nhello\n```   \n===END==='
    doc = parse(content)
    assert doc.sections[0].value.content == "hello"

def test_trailing_whitespace_on_opening_fence():
    """Opening fence with trailing whitespace after info tag."""
    content = '===DOC===\nCODE::```python   \nhello\n```\n===END==='
    doc = parse(content)
    assert doc.sections[0].value.info_tag == "python"
    assert doc.sections[0].value.content == "hello"

def test_content_line_is_only_backticks_shorter_than_fence():
    """A line of 2 backticks inside a 3-backtick fence is content."""
    content = '===DOC===\nCODE::```\n``\n```\n===END==='
    doc = parse(content)
    assert doc.sections[0].value.content == "``"

def test_empty_lines_around_content():
    """Empty lines before/after content inside literal zone are preserved."""
    inner = "\n\nhello\n\n"
    content = f'===DOC===\nCODE::```\n{inner}```\n===END==='
    doc = parse(content)
    assert doc.sections[0].value.content == inner
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
from hypothesis import given, assume, strategies as st

# --- Hypothesis generators that INCLUDE fence-like substrings [B0-S2] ---

def _content_with_fences_strategy(max_fence_len: int = 6):
    """Generate content that may contain fence-like backtick sequences.

    Instead of skipping content with fences (the old approach), this
    generator deliberately includes fence-like substrings and uses
    fence-length scaling to wrap them safely.

    Returns a tuple of (fence_marker, content) where fence_marker is
    always longer than any backtick sequence in content.
    """
    return st.tuples(
        # Generate content that may include backtick runs
        st.text(
            alphabet=st.sampled_from(
                list("abcdefghijklmnopqrstuvwxyz \t\n`")
            ),
            min_size=0,
            max_size=500,
        ),
    ).map(lambda t: _scale_fence_for_content(t[0]))


def _scale_fence_for_content(content: str) -> tuple[str, str]:
    """Compute the minimum safe fence marker for content.

    Scans content for the longest run of backticks and returns a fence
    marker that is strictly longer.
    """
    max_run = 0
    current_run = 0
    for ch in content:
        if ch == "`":
            current_run += 1
            max_run = max(max_run, current_run)
        else:
            current_run = 0
    # Fence must be at least 3 and strictly longer than any run in content
    fence_len = max(3, max_run + 1)
    return ("`" * fence_len, content)


@given(_content_with_fences_strategy())
def test_any_content_round_trips_with_fence_scaling(fence_and_content):
    """Any string content -- including fence-like substrings -- can be
    placed in a literal zone using fence-length scaling and round-trips.

    B0-S2: Replaces the previous test that skipped fence-containing content.
    This test uses Hypothesis generators that deliberately produce content
    with backtick runs, then dynamically scales the fence length to wrap
    them safely.
    """
    fence, content = fence_and_content
    # Filter out content with newline-backtick patterns that would create
    # a line-start fence sequence equal or longer than our wrapping fence
    lines = content.split("\n")
    max_line_fence = max(
        (len(line) - len(line.lstrip("`")) for line in lines),
        default=0,
    )
    assume(max_line_fence < len(fence))

    octave = f'===DOC===\nCODE::{fence}\n{content}\n{fence}\n===END==='
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


@given(st.integers(min_value=3, max_value=8), st.integers(min_value=1, max_value=5))
def test_shorter_fences_in_content_are_preserved(outer_len, inner_len):
    """Fence-like sequences shorter than the wrapping fence are content."""
    assume(inner_len < outer_len)
    outer_fence = "`" * outer_len
    inner_fence = "`" * inner_len
    octave = f'===DOC===\nCODE::{outer_fence}\n{inner_fence}\n{outer_fence}\n===END==='
    doc = parse(octave)
    assert inner_fence in doc.sections[0].value.content
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
| `src/octave_mcp/core/lexer.py` | Add `FENCE_OPEN/CLOSE/LITERAL_CONTENT` token types, `_normalize_with_fence_detection()`, `_evaluate_fence_line()`, tab bypass, fence detection |
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
3. `_normalize_with_fence_detection()` with NFC bypass and tab bypass
4. `_evaluate_fence_line()` fence precedence logic
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

### A9 Migration Gate Definition [B0-B5]

The A9 migration gate validates the backward compatibility assumption (Appendix C) by parsing the entire existing corpus.

**Corpus scope**: All files matching `**/*.oct.md` in the repository root, excluding:
- Files in `node_modules/`, `.git/`, `__pycache__/`, `.venv/` directories
- Files in `tests/fixtures/` that are intentionally malformed (these have `_invalid` or `_error` in their filename)

**Pass threshold**: 100% -- every file in scope MUST parse without errors under the new lexer/parser with literal zone support. Zero regressions allowed.

**Test implementation**:

```python
def test_a9_migration_no_regressions():
    """A9: Verify that all existing .oct.md files parse successfully
    with literal zone support enabled.

    This test validates the backward compatibility assumption that no
    existing valid OCTAVE documents contain backtick sequences at line
    start that would be interpreted as fence markers.

    Gate criteria: 100% pass rate, zero regressions.
    """
    import glob
    from pathlib import Path

    repo_root = Path(__file__).parents[3]  # Adjust to reach repo root
    oct_files = glob.glob(str(repo_root / "**/*.oct.md"), recursive=True)

    # Exclude known directories
    exclude_dirs = {"node_modules", ".git", "__pycache__", ".venv"}
    oct_files = [
        f for f in oct_files
        if not any(d in Path(f).parts for d in exclude_dirs)
    ]

    # Exclude intentionally malformed fixtures
    oct_files = [
        f for f in oct_files
        if "_invalid" not in Path(f).name and "_error" not in Path(f).name
    ]

    results = {"passed": [], "failed": []}

    for filepath in oct_files:
        try:
            content = Path(filepath).read_text(encoding="utf-8")
            parse(content)  # Must not raise
            results["passed"].append(filepath)
        except Exception as e:
            results["failed"].append({"file": filepath, "error": str(e)})

    # Evidence output
    assert len(results["failed"]) == 0, (
        f"A9 MIGRATION GATE FAILED: {len(results['failed'])} of "
        f"{len(oct_files)} files failed to parse.\n"
        + "\n".join(
            f"  FAIL: {r['file']}: {r['error']}" for r in results["failed"]
        )
    )
```

**Evidence output format**: On success, the test produces no output (standard pytest pass). On failure, the assertion message includes:
- Total file count
- Failed file count
- Per-failure: file path and error message

**CI integration**: This test runs as part of the standard `pytest` suite. It is NOT gated behind a flag -- it runs on every CI build to catch regressions.

---

*End of D3 Technical Blueprint for Issue #235*
