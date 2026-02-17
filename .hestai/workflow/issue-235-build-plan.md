# B1 Build Plan: Issue #235 Literal Zones

**Version**: 1.0.0
**Date**: 2026-02-17
**Author**: task-decomposer (PERMIT_SID: 66ebe005-64b4-42f4-a333-be9054542e84)
**Phase**: B1_BUILD_PLAN
**Blueprint**: `.hestai/workflow/literal-zones-blueprint.md` v1.1.0 (B0-AMENDED)
**Branch**: `issue-235-literal-zones`
**Target Release**: v1.3.0

---

## [SCOPE_CLARIFICATION]

### Baseline

- 1610 tests passing (all must continue to pass throughout)
- Quality gates: ruff, black, mypy, pytest all passing
- `repair_log.py` already contains `RepairLog`/`RepairEntry` for existing repair operations;
  the blueprint §6.4 `RepairLogEntry`/`RepairLog` for literal zone audit receipts is a new
  addition to that file (the existing class and the new class share the module)
- The blueprint match point functions in `projector.py` (`_project_value`, `_matches_pattern`)
  are internal implementation details to be located during TDD; the public surface is `project()`
- New test files are created alongside existing `tests/unit/test_lexer.py` etc., not inside them

### Governing Decisions (All LOCKED)

| ID | Decision |
|----|----------|
| D1 | New `LiteralZoneValue` dataclass (not ASTNode subclass) |
| D2 | Backticks only; triple-quotes remain normalizing strings |
| D3 | Zero processing inside fences; NFC bypass before normalization |
| D4 | Schema validates envelope/boundary only; content opaque |
| D5 | Container preservation scoped to YAML frontmatter only |
| D6 | Preserve always + per-zone audit (non-configurable) |

### Key Constraints

- I1: NFC bypass is mandatory; single-pass `_normalize_with_fence_detection()` replaces any two-pass approach
- I3: Nested fences MUST error (E007_NESTED_FENCE); closing-fence checked BEFORE nested-fence error
- I4: `RepairLogEntry` schema required for per-zone audit receipts
- I5: `literal_zones_validated: false` honest reporting (no validation theater)
- A9: 100% corpus parse pass required before merge

### Task Count

20 tasks across 5 phases. Within agent constraints (15-25).

---

## Phase 1: Foundation (Lexer + AST)

### T01 -- LiteralZoneValue Dataclass

**Size**: S
**Blueprint**: §3.1
**TDD Cycle**: Write failing type-check test first, then add dataclass

**Files**:
- `src/octave_mcp/core/ast_nodes.py` (add dataclass after `HolographicValue` at line 207)
- `tests/unit/test_literal_zones_ast.py` (NEW -- create)

**Implementation**:
Add `LiteralZoneValue` dataclass with three fields: `content: str = ""`,
`info_tag: str | None = None`, `fence_marker: str = "``\`"`. Include full docstring
documenting I1/I2/I3 compliance. Import `dataclass` from `dataclasses` (already imported).

**Test cases** (from §10.1 category "AST representation"):
- `LiteralZoneValue()` default construction (empty content, None info_tag, 3-backtick marker)
- `LiteralZoneValue(content="hello", info_tag="python", fence_marker="```")` field access
- Dataclass equality: two identical `LiteralZoneValue` instances are equal
- `LiteralZoneValue` is NOT an instance of `ASTNode` (D1: not a subclass)
- Empty `content=""` is a valid value (I2: distinct from absent)

**Acceptance**: `isinstance(LiteralZoneValue(), LiteralZoneValue)` is True; mypy passes.

**Dependencies**: None (first task)

---

### T02 -- RepairLogEntry Schema

**Size**: S
**Blueprint**: §6.4
**TDD Cycle**: Write failing schema test first, then add dataclasses

**Files**:
- `src/octave_mcp/core/repair_log.py` (add `RepairLogEntry` and `LiteralZoneRepairLog` classes
  alongside existing `RepairLog`/`RepairEntry`)
- `tests/unit/test_literal_zones_repair_log.py` (NEW -- create)

**Implementation**:
Add `RepairLogEntry` dataclass with fields: `zone_key: str`, `line: int`,
`action: str` (literal "preserved" | "stripped"), `pre_hash: str`, `post_hash: str`,
`timestamp: str`, `source_stage: str`.
Add `LiteralZoneRepairLog` dataclass with `entries: list[RepairLogEntry]`,
`all_preserved` property, and `to_dict()` method.
NOTE: Name the new aggregator `LiteralZoneRepairLog` to avoid collision with the existing
`RepairLog` class in the same module.

**Test cases** (from §6.4 contract):
- `RepairLogEntry` construction with all fields
- `RepairLogEntry.action` must be "preserved" or "stripped" (document as invariant)
- `LiteralZoneRepairLog.all_preserved` returns True when all entries have matching hashes
- `LiteralZoneRepairLog.all_preserved` returns False when pre_hash != post_hash
- `LiteralZoneRepairLog.to_dict()` returns list of dicts with all required keys
- Invariant: when `action="preserved"`, `pre_hash == post_hash`

**Acceptance**: `LiteralZoneRepairLog(entries=[]).all_preserved` is True; `to_dict()` serializes.

**Dependencies**: T01

---

### T03 -- Lexer Token Types

**Size**: S
**Blueprint**: §4.3
**TDD Cycle**: Write token-type existence tests first, then add enum values

**Files**:
- `src/octave_mcp/core/lexer.py` (add three `TokenType` enum values)
- `tests/unit/test_literal_zones_lexer.py` (NEW -- create, start with token type tests)

**Implementation**:
Add to `TokenType` enum:
- `FENCE_OPEN = auto()` -- opening ``` with optional info tag
- `FENCE_CLOSE = auto()` -- closing ```
- `LITERAL_CONTENT = auto()` -- raw content between fences

Also add `FENCE_PATTERN` regex constant at module level:
```python
FENCE_PATTERN = re.compile(r'^( {0,3})((`{3,})([^\n`]*)?)$')
```

**Test cases**:
- `TokenType.FENCE_OPEN` exists in enum
- `TokenType.FENCE_CLOSE` exists in enum
- `TokenType.LITERAL_CONTENT` exists in enum
- `FENCE_PATTERN.match("```")` matches (3 backticks)
- `FENCE_PATTERN.match("````python")` matches (4 backticks with tag)
- `FENCE_PATTERN.match("``")` does NOT match (only 2 backticks)
- `FENCE_PATTERN.match("    ```")` does NOT match (4 spaces indent exceeds limit)
- `FENCE_PATTERN.match("   ```")` matches (3 spaces indent is allowed)

**Acceptance**: All three token types accessible; regex compiled without error.

**Dependencies**: T01

---

### T04 -- _evaluate_fence_line() Precedence Logic

**Size**: M
**Blueprint**: §5.3.1 (fence precedence decision table, B0-B1 amendment)
**TDD Cycle**: Write all four precedence cases as failing tests, then implement function

**Files**:
- `src/octave_mcp/core/lexer.py` (add `_evaluate_fence_line()` function)
- `tests/unit/test_literal_zones_lexer.py` (add precedence tests)

**Implementation**:
Add `_evaluate_fence_line(backtick_seq, open_fence_marker, trailing_content, line, column,
open_line) -> str` function implementing the four-case precedence table:
- Case 1: `len(seq) == len(open)` AND no trailing non-whitespace -> return "close"
- Case 2: `len(seq) >= len(open)` AND has trailing content -> raise `LexerError` E007_NESTED_FENCE
- Case 3: `len(seq) > len(open)` -> raise `LexerError` E007_NESTED_FENCE
- Case 4: `len(seq) < len(open)` -> return "content"

CRITICAL: Case 1 (closing fence) is checked BEFORE Cases 2/3 (error). This is the
B0-B1 amendment requirement.

**Test cases** (from §5.3.1 table + §10.2 nested fence tests):
- Exact-length fence with clean line -> "close"
- Exact-length fence with trailing spaces -> "close" (trailing whitespace is clean)
- Exact-length fence with trailing non-whitespace -> raises E007_NESTED_FENCE
- Longer fence than open -> raises E007_NESTED_FENCE
- Shorter fence than open -> "content"
- Error message contains "E007_NESTED_FENCE" and "Use a longer fence" guidance (I3 educational)
- Error message includes the open line number

**Acceptance**: All four cases handled; error messages include actionable guidance.

**Dependencies**: T03

---

### T05 -- _normalize_with_fence_detection() Single-Pass

**Size**: L
**Blueprint**: §4.1 (critical path, B0-B2 amendment)
**TDD Cycle**: Write NFC bypass tests and fence span return tests first, then implement

**Files**:
- `src/octave_mcp/core/lexer.py` (add `_normalize_with_fence_detection()` function)
- `tests/unit/test_literal_zones_lexer.py` (add NFC bypass and fence span tests)

**Implementation**:
Add `_normalize_with_fence_detection(content: str) -> tuple[str, list[tuple[int, int, str, str | None]]]`
with single-pass line-by-line approach per blueprint §4.1 pseudocode.
- Outside fence: apply `unicodedata.normalize("NFC", line)`
- Inside fence: append lines verbatim (NO NFC)
- Fence spans recorded against OUTPUT buffer offsets (eliminates coordinate drift)
- Raises `LexerError` E006 for unclosed fences
- Calls `_evaluate_fence_line()` for all backtick sequences found at line start inside a fence

CRITICAL SINGLE-PASS INVARIANT: Fence span offsets in returned list must be valid
for the RETURNED normalized string, not the original input string.

**Test cases** (from §10.1 "Lexer: NFC bypass" -- 10 cases):
- Text outside fence is NFC-normalized
- Content inside fence is NOT NFC-normalized (NFD characters preserved)
- `U+00E9` outside fence -> normalized to precomposed form
- `U+0065 U+0301` (decomposed e-acute) inside fence -> preserved as-is (test case from §10.2)
- Fence spans list has correct start/end offsets for returned string
- Simple document with one fence: correct span returned
- Document with no fences: empty spans list returned
- Unclosed fence raises E007 from `_evaluate_fence_line()` via nested call
- Unclosed fence at EOF raises E006 with open line number
- Multiple fences in one document: all spans returned

**Acceptance**: Round-trip: `_normalize_with_fence_detection(content)[0]` is idempotent
for content without literal zones.

**Dependencies**: T04

---

### T06 -- Lexer Token Emission + Tab Bypass

**Size**: M
**Blueprint**: §4.2, §4.4, §4.5
**TDD Cycle**: Write tab bypass tests and fence token emission tests first, then wire up

**Files**:
- `src/octave_mcp/core/lexer.py` (update `tokenize()`: call `_normalize_with_fence_detection()`,
  add fence span token emission in main loop, update tab check)
- `tests/unit/test_literal_zones_lexer.py` (add tab bypass + token emission tests)

**Implementation**:
1. In `tokenize()`: replace bare `unicodedata.normalize("NFC", content)` at line 429 with call
   to `_normalize_with_fence_detection(content)` -> get `(content, fence_spans)`.
2. Update tab check (line 435) to skip positions inside fence_spans.
3. In main tokenization loop: before pattern matching, check if current `pos` == a fence span start;
   if so, emit FENCE_OPEN, LITERAL_CONTENT, FENCE_CLOSE tokens and advance past span.

**Test cases** (from §10.1 "Lexer: fence detection" 25 cases, "tab bypass" 8 cases):
- Tabs inside literal zone do NOT raise E005
- Tabs outside literal zone still raise E005
- Mixed tabs and spaces inside literal zone preserved (§10.2 pathological case)
- Tokenizing `KEY::```python\nhello\n\`\`\`` produces FENCE_OPEN, LITERAL_CONTENT, FENCE_CLOSE
- FENCE_OPEN token value is dict with `fence_marker` and `info_tag` keys
- LITERAL_CONTENT token value is raw string "hello"
- FENCE_CLOSE token value is the fence string "```"
- Empty literal zone `KEY::```\n\`\`\`` produces FENCE_OPEN with no LITERAL_CONTENT between
- Info tag stripped of trailing whitespace
- Info tag None when no tag provided
- Fence with 4 backticks: FENCE_OPEN has `fence_marker="````"`
- E006 raised for unclosed fence (via `_normalize_with_fence_detection`)
- E007_NESTED_FENCE raised for nested fence of equal length

**Acceptance**: Tokenizing a complete OCTAVE doc with a literal zone produces a valid token stream
that includes FENCE_OPEN / LITERAL_CONTENT / FENCE_CLOSE.

**Dependencies**: T05

---

## Phase 2: Core Pipeline (Parser + Emitter)

### T07 -- parse_literal_zone() + parse_value() Integration

**Size**: M
**Blueprint**: §5.1, §5.2, §5.5
**TDD Cycle**: Write parser-level tests (input -> LiteralZoneValue) first, then implement

**Files**:
- `src/octave_mcp/core/parser.py` (add `parse_literal_zone()`, update `parse_value()`,
  add `LiteralZoneValue` import)
- `tests/unit/test_literal_zones_parser.py` (NEW -- create)

**Implementation**:
1. Add `LiteralZoneValue` to imports from `ast_nodes`.
2. Add `TokenType.FENCE_OPEN`, `FENCE_CLOSE`, `LITERAL_CONTENT` to imports from `lexer`.
3. Implement `parse_literal_zone()` per blueprint §5.1 spec (consumes FENCE_OPEN, optional
   LITERAL_CONTENT, FENCE_CLOSE; raises ParserError E006 if FENCE_CLOSE missing).
4. In `parse_value()`: add `elif token.type == TokenType.FENCE_OPEN: return self.parse_literal_zone()`
   BEFORE the IDENTIFIER branch.
5. Clean `info_tag`: strip whitespace, normalize empty to None.

**Test cases** (from §10.1 "Parser: literal zone parsing" 20 cases):
- `parse("===DOC===\nCODE::```python\nhello\n```\n===END===")` returns AST with
  `Assignment.value` of type `LiteralZoneValue`
- `info_tag` is "python"
- `content` is "hello"
- `fence_marker` is "```"
- Empty literal zone: `content == ""` (I2)
- Missing closing fence raises ParserError with E006 and line number
- Error message contains the expected fence marker
- 4-backtick fence parsed correctly with `fence_marker="````"`
- Info tag with trailing whitespace normalized: `"python   "` -> `"python"`
- Info tag absent: `info_tag is None`
- Document with multiple literal zone assignments
- Literal zone at nested block level (e.g., inside a section)
- Triple-quoted string `"""..."""` still parsed as normalizing string, NOT literal zone (D2)

**Acceptance**: `parse("===DOC===\nKEY::```\n\`\`\`\n===END===").sections[0].children[0].value`
is `LiteralZoneValue(content="", info_tag=None, fence_marker="```")`.

**Dependencies**: T06

---

### T08 -- Emitter: emit_value() + emit_assignment()

**Size**: M
**Blueprint**: §6.1, §6.2, §6.3
**TDD Cycle**: Write round-trip and indentation tests first, then implement

**Files**:
- `src/octave_mcp/core/emitter.py` (update `emit_value()`, update `emit_assignment()`,
  add `LiteralZoneValue` import)
- `tests/unit/test_literal_zones_emitter.py` (NEW -- create)

**Implementation**:
1. Add `LiteralZoneValue` to imports from `ast_nodes`.
2. In `emit_value()`: add `isinstance(value, LiteralZoneValue)` branch after `HolographicValue`
   branch. Reconstruct: `fence_marker + (info_tag or "") + "\n" + content + closing_fence`.
   Ensure content ends with newline before closing fence.
3. In `emit_assignment()`: add `isinstance(assignment.value, LiteralZoneValue)` branch BEFORE
   the standard path. Fence markers get current indent; content lines are verbatim (NO indent added).

**Test cases** (from §10.1 "Emitter: round-trip" 20 cases, "indentation" 10 cases):
- `emit_value(LiteralZoneValue(content="hello", info_tag="python"))` produces
  "```python\nhello\n```"
- Content with no trailing newline: newline added before closing fence
- Content already ending with newline: no extra newline added
- Empty literal zone: "```\n```"
- 4-backtick fence: "````\nhello\n````"
- Info tag None: fence with no tag "```\nhello\n```"
- `emit_assignment(Assignment(key="CODE", value=LiteralZoneValue(...)), indent=0)` produces
  "CODE::```python\nhello\n```"
- `indent=1`: "  CODE::```python\nhello\n```" (fence markers indented; content verbatim)
- Tabs in content survive emission unchanged
- Non-NFC characters in content survive emission unchanged
- Round-trip invariant: `parse(emit(parse(D))) == parse(D)` for docs with literal zones
  (§6.3 formal invariant test)
- Round-trip with NFC bypass: NFD content preserved through emit/parse cycle (§10.2 test case)
- Round-trip with tabs: tab content preserved (§10.2 test case)

**Acceptance**: Round-trip invariant holds for all test documents.

**Dependencies**: T07

---

### T09 -- Exhaustive Match Points: projector.py + holographic.py + repair.py

**Size**: M
**Blueprint**: §3.2 match points 9-13 (projector x2, holographic x1, repair x2)
**TDD Cycle**: Write "no silent normalization" tests first, then add guard clauses

**Files**:
- `src/octave_mcp/core/projector.py` (add `LiteralZoneValue` handling in value projection)
- `src/octave_mcp/core/repair.py` (add `LiteralZoneValue` guard clauses in `repair_value()`
  and any integrity-check path; add audit logging to `LiteralZoneRepairLog`)
- `src/octave_mcp/core/holographic.py` (confirm no change needed; add comment)
- `tests/unit/test_literal_zones_passthrough.py` (NEW -- create)

**Implementation**:
For each match point, locate the actual function (may differ from blueprint names -- discover
during TDD) and add appropriate handling:

- **Match point 9** (`projector.py` value projection): Return `LiteralZoneValue.content` as
  raw string for projection output. Add `isinstance` branch.
- **Match point 10** (`projector.py` pattern matching): `LiteralZoneValue` never matches
  holographic patterns; add guard clause returning False.
- **Match point 11** (`holographic.py` `resolve_holographic()`): NO CODE CHANGE -- confirm
  by inspection and add a comment: "LiteralZoneValue cannot contain holographic patterns (D3)".
- **Match point 12** (`repair.py` `repair_value()`): Add guard clause at top:
  `if isinstance(value, LiteralZoneValue): return value` (literal zones are never repaired).
- **Match point 13** (`repair.py` integrity check / `_repair_ast_node()`): Log literal zone
  presence in `LiteralZoneRepairLog` (from T02) but never modify; add `isinstance` branch
  that generates a `RepairLogEntry` with `action="preserved"` and matching hashes.

Add `LiteralZoneValue` import to all modified files.

**Test cases** (from §3.2 behavior column):
- Projecting a doc with literal zone value returns `content` as string in projection output
- Literal zone does not match holographic pattern `{{VAR}}` (returns False/no match)
- `repair_value(LiteralZoneValue(...), ...)` returns the same object unchanged
- `repair_value` does NOT produce a repair log entry (it passes through unchanged)
- `_repair_ast_node` with literal zone value generates a `RepairLogEntry` with
  `action="preserved"` and `pre_hash == post_hash`
- Existing repair tests for non-literal values still pass (no regression)

**Acceptance**: A document with literal zones passing through repair pipeline produces
`LiteralZoneRepairLog.all_preserved == True`.

**Dependencies**: T02, T08

---

### T10 -- Exhaustive Match Points: emitter.py is_absent + needs_quotes + write.py

**Size**: S
**Blueprint**: §3.2 match points 2, 3, 8
**TDD Cycle**: Verify existing behavior with new type, then confirm no change needed

**Files**:
- `src/octave_mcp/core/emitter.py` (confirm `is_absent()` and `needs_quotes()` handle
  `LiteralZoneValue` correctly without code changes; add type-safety tests)
- `src/octave_mcp/mcp/write.py` (add `LiteralZoneValue` guard in `_normalize_value_for_ast()`,
  add import)
- `tests/unit/test_literal_zones_emitter.py` (add is_absent/needs_quotes tests)
- `tests/unit/test_literal_zones_write.py` (NEW -- create, write normalization tests)

**Implementation**:
- **Match point 2** (`emitter.py` `is_absent()`): Inspect current implementation.
  If it only checks for `str`/`Absent` types, `LiteralZoneValue` will correctly return False
  without code changes. Write a test to lock this behavior.
- **Match point 3** (`emitter.py` `needs_quotes()`): Same -- inspect and test. If only
  checks `str` type, no code change needed.
- **Match point 8** (`write.py` `_normalize_value_for_ast()`): Add guard clause:
  `if isinstance(value, LiteralZoneValue): return value`. This prevents the write pipeline
  from normalizing literal zone content (D3: zero processing).

**Test cases**:
- `is_absent(LiteralZoneValue())` returns False
- `is_absent(LiteralZoneValue(content=""))` returns False (empty != absent, I2)
- `needs_quotes(LiteralZoneValue(...))` returns False
- `_normalize_value_for_ast(LiteralZoneValue(content="hello"))` returns the same
  `LiteralZoneValue` object unchanged (identity, not copy)
- `_normalize_value_for_ast` does NOT apply NFC normalization to content
- Write tool: document with literal zone passes through `_normalize_value_for_ast` unchanged

**Acceptance**: `_normalize_value_for_ast(LiteralZoneValue(content="raw\tcontent"))` returns
object with `content == "raw\tcontent"`.

**Dependencies**: T08

---

## Phase 3: Validation (Constraints + Validator)

### T11 -- LiteralConstraint + LangConstraint

**Size**: M
**Blueprint**: §7.1, §7.2, §7.3
**TDD Cycle**: Write constraint evaluation tests first, then implement

**Files**:
- `src/octave_mcp/core/constraints.py` (add `LiteralConstraint`, `LangConstraint`,
  update `ConstraintChain.parse()`)
- `tests/unit/test_literal_zones_constraints.py` (NEW -- create)

**Implementation**:
1. Add `LiteralConstraint(Constraint)` class implementing `evaluate()`:
   validates value is `isinstance(value, LiteralZoneValue)`; returns ValidationResult with
   E007 error if not.
2. Add `LangConstraint(Constraint)` class with `__init__(self, expected_lang: str)` and
   `evaluate()`: validates value is `LiteralZoneValue` with matching `info_tag` (case-insensitive
   comparison).
3. Update `ConstraintChain.parse()` to recognize:
   - `TYPE[LITERAL]` -> creates `LiteralConstraint()`
   - `LANG[python]` -> creates `LangConstraint("python")`
   (Pattern: `LANG\[([^\]]+)\]`)
4. Add `LiteralZoneValue` import.

**Test cases** (from §10.1 "Validator: TYPE[LITERAL]" 10 cases, "LANG[]" 8 cases):
- `LiteralConstraint().evaluate(LiteralZoneValue())` -> valid
- `LiteralConstraint().evaluate("string value")` -> invalid, error code E007
- `LiteralConstraint().evaluate(42)` -> invalid
- `LangConstraint("python").evaluate(LiteralZoneValue(info_tag="python"))` -> valid
- `LangConstraint("python").evaluate(LiteralZoneValue(info_tag="PYTHON"))` -> valid (case-insensitive)
- `LangConstraint("python").evaluate(LiteralZoneValue(info_tag="json"))` -> invalid
- `LangConstraint("python").evaluate(LiteralZoneValue(info_tag=None))` -> invalid
- `LangConstraint("python").evaluate("string")` -> invalid
- `ConstraintChain.parse("TYPE[LITERAL]")` produces chain with `LiteralConstraint`
- `ConstraintChain.parse("LANG[python]")` produces chain with `LangConstraint("python")`
- `ConstraintChain.parse("REQ TYPE[LITERAL] LANG[python]")` produces chain with all three
- Existing constraint parsing tests still pass (no regression)

**Acceptance**: `ConstraintChain.parse("LANG[json]").evaluate_all(LiteralZoneValue(info_tag="json"), "path")` passes.

**Dependencies**: T01

---

### T12 -- validator.py _to_python_value() + validation_status Flags

**Size**: S
**Blueprint**: §7.4, §7.5
**TDD Cycle**: Write validation_status flag tests first, then implement

**Files**:
- `src/octave_mcp/core/validator.py` (update `_to_python_value()`, add `LiteralZoneValue` import)
- `tests/unit/test_literal_zones_validator.py` (NEW -- create)

**Implementation**:
1. Add `LiteralZoneValue` to imports from `ast_nodes`.
2. In `_to_python_value()`: add `if isinstance(value, LiteralZoneValue): return value`
   BEFORE the `return value` fallthrough. This ensures literal zone objects are passed
   directly to constraint evaluation (LiteralConstraint and LangConstraint operate on the
   object itself, not a converted Python value).
3. Add `contains_literal_zones` and `literal_zones_validated` flag support to validation
   result dictionaries. Implement `_count_literal_zones(doc)` utility (from §8.1) as
   a shared helper (used by both validator and MCP tools).

**Test cases** (from §10.1 "Validator: validation_status" 8 cases):
- `_to_python_value(LiteralZoneValue(...))` returns the same `LiteralZoneValue` object
- `_to_python_value` does NOT convert `LiteralZoneValue` to a string
- Validator result for doc with literal zones includes `contains_literal_zones: True`
- Validator result includes `literal_zone_count: N`
- Validator result includes `literal_zones_validated: False` (D4: content opaque; I5: honest)
- `_count_literal_zones(doc)` returns 0 for doc without literal zones
- `_count_literal_zones(doc)` returns correct count for doc with N literal zones
- TYPE[LITERAL] constraint evaluated via validator returns correct ValidationResult

**Acceptance**: I5 compliance: `literal_zones_validated` is always `False` in output
(content is always opaque).

**Dependencies**: T11

---

## Phase 4: MCP Tools

### T13 -- octave_validate: Zone Reporting

**Size**: M
**Blueprint**: §8.1, §8.4
**TDD Cycle**: Write zone_report format tests first, then implement

**Files**:
- `src/octave_mcp/mcp/validate.py` (add zone reporting, literal zone flags, import
  `LiteralZoneValue`, import `_count_literal_zones` from validator)
- `tests/unit/test_literal_zones_mcp_validate.py` (NEW -- create)

**Implementation**:
After parsing (Stage 1+2), before validation (Stage 3):
1. Call `_count_literal_zones(doc)`.
2. If count > 0: add `contains_literal_zones`, `literal_zone_count`,
   `literal_zones_validated: False`, and `zone_report` to result.
3. `zone_report` format per §8.4: `dsl` (status + errors), `container` (status),
   `literal` (status, count, content_validated: false, zones list with key/info_tag/line).
4. Add `repair_log` from `LiteralZoneRepairLog.to_dict()` when literal zones present.

**Test cases** (from §10.1 "MCP validate: zone reporting" 10 cases):
- Validate doc with no literal zones: no `contains_literal_zones` key in result
- Validate doc with one literal zone: `contains_literal_zones: True`
- `literal_zone_count: 1`
- `literal_zones_validated: False` (always)
- `zone_report.literal.count == 1`
- `zone_report.literal.content_validated == False`
- `zone_report.literal.zones[0]` has keys: `key`, `info_tag`, `line`
- `zone_report.container.status` is "preserved" for doc with frontmatter
- `zone_report.container.status` is "absent" for doc without frontmatter
- Existing validate tests still pass (no regression)

**Acceptance**: `validate("===DOC===\nCODE::```python\nhello\n```\n===END===")` result
contains `zone_report.literal.status == "preserved"`.

**Dependencies**: T12

---

### T14 -- octave_write: Zone Reporting + Preservation

**Size**: M
**Blueprint**: §8.2, §8.4
**TDD Cycle**: Write preservation tests first, then implement

**Files**:
- `src/octave_mcp/mcp/write.py` (add zone reporting, confirm `_unwrap_markdown_code_fence()`
  unchanged, add `LiteralZoneRepairLog` integration)
- `tests/unit/test_literal_zones_write.py` (add to file from T10)

**Implementation**:
1. After parse, count literal zones (reuse `_count_literal_zones`).
2. Add `zone_report` to response when literal zones present (same format as validate).
3. Add `repair_log` from `LiteralZoneRepairLog.to_dict()`.
4. Confirm that `_unwrap_markdown_code_fence()` is NOT changed -- it only strips the outer
   transport fence, not internal literal zones. Write a regression test to lock this.

**Test cases** (from §10.1 "MCP write: preservation" 15 cases):
- Write doc with literal zone: zone content preserved byte-for-byte in output
- Write doc with literal zone: `zone_report` in response
- Write doc with literal zone containing tabs: tabs preserved in output
- Write doc with literal zone containing non-NFC chars: chars preserved
- Write doc with NO literal zone inside a markdown transport fence: `_unwrap_markdown_code_fence`
  still strips the outer fence correctly (regression test -- D5)
- Write doc with literal zone inside transport fence: inner fence NOT unwrapped
- `repair_log` in response when literal zones present
- `repair_log[0].action == "preserved"` for normal pass-through
- `repair_log[0].pre_hash == repair_log[0].post_hash`
- Write doc with multiple literal zones: all preserved, all in repair_log
- Existing write tests still pass (no regression)

**Acceptance**: A document written and re-read has identical literal zone content.

**Dependencies**: T10, T13

---

### T15 -- octave_eject: Format Export

**Size**: M
**Blueprint**: §8.3, §3.2 match points 5-6
**TDD Cycle**: Write JSON/YAML and markdown export tests first, then implement

**Files**:
- `src/octave_mcp/mcp/eject.py` (update `_convert_value()`, update `_format_markdown_value()`,
  add `LiteralZoneValue` import)
- `tests/unit/test_literal_zones_eject.py` (NEW -- create)

**Implementation**:
1. In `_convert_value()`: add `isinstance(value, LiteralZoneValue)` branch returning dict:
   `{"__literal_zone__": True, "content": value.content, "info_tag": value.info_tag,
    "fence_marker": value.fence_marker}`.
2. In `_format_markdown_value()`: add `isinstance(value, LiteralZoneValue)` branch emitting
   the fence block as a markdown fenced code block (same logic as `emit_value()`).
3. Add zone reporting to eject response when literal zones present.

**Test cases** (from §10.1 "MCP eject: format export" 10 cases):
- Eject doc with literal zone to JSON: field contains `{"__literal_zone__": True, ...}`
- Eject JSON export: `content` key has verbatim content
- Eject JSON export: `info_tag` key has correct value or None
- Eject JSON export: `fence_marker` key has correct value
- Eject doc with literal zone to markdown: field formatted as markdown fenced code block
- Eject markdown: fence markers present and correct
- Eject markdown: content verbatim
- Eject doc with NO literal zones: no `__literal_zone__` key in JSON output
- `zone_report` in eject response when literal zones present
- Existing eject tests still pass (no regression)

**Acceptance**: `eject(doc_with_literal_zone, "json")["CODE"]["__literal_zone__"] == True`.

**Dependencies**: T13

---

## Phase 5: Spec + Grammar + Migration

### T16 -- Error Code Documentation (E006 + E007 subtype)

**Size**: S
**Blueprint**: §9.1, §9.2, §9.3; §2.3
**TDD Cycle**: Write error message format tests first, then verify/update error strings

**Files**:
- `src/octave_mcp/core/lexer.py` (verify E006 and E007_NESTED_FENCE error messages match
  blueprint §9.1 and §9.2 format exactly)
- `docs/grammar/octave-v1.0-grammar.ebnf` (add E006/E007 subtype comments per §2.3)
- `tests/unit/test_literal_zones_errors.py` (NEW -- create, error message format tests)

**Implementation**:
The error messages were written during T04 (E007_NESTED_FENCE) and T05 (E006). This task
verifies they match the documented format exactly and updates EBNF grammar.

Error format verification:
- E006: `"E006 at line {open_line}, column {open_column}: Unterminated literal zone.\nFence '{marker}' opened at line {open_line} was never closed.\nAdd a matching closing fence: {marker}"`
- E007_NESTED_FENCE: `"E007 at line {line}, column {column}: Nested literal zone detected."`

EBNF grammar update: Add E006 and E007 subtype comments to APPENDIX B.

**Test cases** (from §9.1, §9.2):
- E006 error message contains "E006"
- E006 error message contains the fence marker
- E006 error message contains the open line number
- E006 error message contains "Add a matching closing fence"
- E007_NESTED_FENCE error message contains "E007"
- E007_NESTED_FENCE error message contains "Nested literal zone"
- E007_NESTED_FENCE error message contains "Use a longer fence"
- E007_NESTED_FENCE error message contains the outer fence marker
- E007_NESTED_FENCE error message contains the open line number

**Acceptance**: Error messages are self-documenting and actionable per I3.

**Dependencies**: T05

---

### T17 -- EBNF Grammar: literal_value Production

**Size**: S
**Blueprint**: §2.1, §2.2
**TDD Cycle**: Validate grammar file parses correctly; update value production

**Files**:
- `docs/grammar/octave-v1.0-grammar.ebnf` (add `literal_value` and `code_fence` productions
  per §2.1; update `value` production per §2.2)
- `tests/test_spec_validation.py` (check if grammar tests exist; add literal_value grammar test)

**Implementation**:
Add new SECTION 4b after SECTION 4 with productions from blueprint §2.1:
- `literal_value = code_fence ;`
- `code_fence` with `opening_fence`, `info_tag`, `fence_content`, `closing_fence`
- `backtick` terminal
- Constraint comments for fence length matching and content restrictions

Update `value` production in SECTION 4 to include `| literal_value` (NEW: Issue #235).

**Test cases**:
- Grammar file is valid EBNF (no syntax errors in structure)
- `literal_value` production exists in grammar
- `value` production includes `literal_value`
- `code_fence` production includes `opening_fence`, `fence_content`, `closing_fence`
- Constraint comments are present explaining fence length matching rule

**Acceptance**: Grammar file updated; no existing grammar-based tests broken.

**Dependencies**: T16

---

### T18 -- Core Spec Update (octave-core-spec.oct.md)

**Size**: S
**Blueprint**: §1.1, §1.2, §1.3, §1.4
**TDD Cycle**: Validate spec file is valid OCTAVE; check spec-compliance tests

**Files**:
- `src/octave_mcp/resources/specs/octave-core-spec.oct.md` (add LITERAL type in Section 3,
  LITERAL_FENCE in Section 2c, LITERAL_ZONES validation checklist in Section 6b,
  LITERAL_ZONE_PATTERN in Section 7)
- `tests/test_spec_validation.py` (check for spec parsing tests; add literal zone spec test)

**Implementation**:
Make the four additions from blueprint §1.1-§1.4 to the core spec file:
1. §1.1: Add `LITERAL::` type with `LITERAL_RULES::[]` after `ESCAPES::` line (Section 3).
2. §1.2: Add `LITERAL_FENCE::` and `FENCE_SCALING::` to Section 2c.
3. §1.3: Add `LITERAL_ZONES::[]` validation checklist to Section 6b.
4. §1.4: Add `LITERAL_ZONE_PATTERN:` canonical examples to Section 7.

The spec file itself is OCTAVE; it must parse correctly after changes.

**Test cases**:
- Spec file parses without errors after changes
- Spec file contains "LITERAL" keyword in Section 3
- Spec file contains "literal_zones" keyword in Section 6
- Spec file contains "LITERAL_ZONE_PATTERN" in Section 7
- Existing spec validation tests still pass

**Acceptance**: `parse(open("octave-core-spec.oct.md").read())` succeeds without errors.

**Dependencies**: T17

---

### T19 -- Integration: End-to-End + Property-Based Tests

**Size**: L
**Blueprint**: §10.2, §10.3
**TDD Cycle**: These ARE the tests -- write property tests and e2e tests in RED, then
verify they pass GREEN against complete implementation

**Files**:
- `tests/unit/test_literal_zones_roundtrip.py` (NEW -- create; round-trip and pathological tests)
- `tests/properties/test_literal_zones_property.py` (NEW -- create; Hypothesis-based tests)

**Implementation**:
This task consolidates the critical integration tests from §10.2 and property tests from §10.3.

Round-trip + pathological tests (§10.2 -- 8 cases explicitly listed, ~7 more):
- `test_round_trip_literal_zone()` (tabs preserved)
- `test_round_trip_nfc_bypass()` (NFD form preserved)
- `test_nested_fence_equal_length_errors()` (E007)
- `test_nested_fence_longer_errors()` (E007)
- `test_shorter_fence_inside_is_content()` (fence-length scaling)
- `test_escaped_backticks_in_content()` (B0-S1 pathological)
- `test_mixed_indentation_in_literal_zone()` (B0-S1 pathological)
- `test_deep_nesting_three_levels()` (B0-S1 pathological, 5-tick wraps 4-tick wraps 3-tick)
- `test_trailing_whitespace_on_closing_fence()`
- `test_trailing_whitespace_on_opening_fence()`
- `test_content_line_is_only_backticks_shorter_than_fence()`
- `test_empty_lines_around_content()`
- `test_empty_literal_zone()` (I2)
- `test_absent_vs_empty_literal()` (I2)

Hypothesis property tests (§10.3 -- B0-S2 amendment):
- `test_any_content_round_trips_with_fence_scaling()` (replaces old `assume("```" not in content)`)
- `test_fence_length_scaling()` (any N >= 3 works)
- `test_shorter_fences_in_content_are_preserved()`

All test source from blueprint §10.2 and §10.3 can be used verbatim as starting point.

**Acceptance**: All ~194 test cases across all 15 categories passing.

**Dependencies**: T15 (all implementation complete)

---

### T20 -- A9 Migration Gate + Regression Guard

**Size**: M
**Blueprint**: Appendix C, §10.4
**TDD Cycle**: Write corpus-scan test in RED (it trivially passes on current code since
backticks are currently illegal); verify it still passes GREEN after all changes

**Files**:
- `tests/test_a9_migration.py` (NEW -- create; corpus-scan test per Appendix C spec)
- `tests/test_literal_zones_regression.py` (NEW -- create; regression guard for D2/D5)

**Implementation**:
A9 test (`test_a9_migration_no_regressions()`): Scan all `**/*.oct.md` files excluding
`node_modules`, `.git`, `__pycache__`, `.venv`, and intentionally malformed fixtures
(`_invalid`/`_error` in filename). Parse each file. Assert 100% pass rate with detailed
error output per blueprint Appendix C spec.

Regression tests (§10.4):
- All 1610 existing tests still pass (validated by running full suite)
- `"""triple-quoted strings"""` still parsed as normalizing strings (D2: NOT literal zones)
- YAML frontmatter handling unchanged (D5)
- `_unwrap_markdown_code_fence()` behavior unchanged for outer transport fence (D5)
- Documents without literal zones produce identical output before/after changes

**Test cases**:
- `test_a9_migration_no_regressions()`: 100% corpus parse pass (zero regressions)
- `test_triple_quoted_string_not_literal_zone()`: `"""..."""` is still a string
- `test_yaml_frontmatter_unchanged()`: frontmatter parsed as before
- `test_outer_fence_unwrapping_unchanged()`: write tool transport wrapper behavior
- `test_no_backtick_collision_in_corpus()`: no existing `.oct.md` file is broken

**Acceptance Gate**: A9 gate -- `assert len(results["failed"]) == 0`. This is a BLOCKING
gate before merge. CI must pass 100%.

**Dependencies**: T18, T19

---

## [DEPENDENCY_GRAPH]

```
T01 (LiteralZoneValue AST)
├── T02 (RepairLogEntry schema)       -> T09
├── T03 (Lexer token types)           -> T04 -> T05 -> T06 -> T07 -> T08
│                                                                     ├── T09
│                                                                     └── T10
└── T11 (Constraints)                 -> T12 -> T13 -> T14 -> T15
                                                                └─── T19 -> T20
                                                                T18 ─┘
T16 (Error codes)   -> T17 (Grammar) -> T18 (Spec) ─────────────────┘
```

**Detailed dependency matrix**:

| Task | Blocked By |
|------|-----------|
| T01 | (none) |
| T02 | T01 |
| T03 | T01 |
| T04 | T03 |
| T05 | T04 |
| T06 | T05 |
| T07 | T06 |
| T08 | T07 |
| T09 | T02, T08 |
| T10 | T08 |
| T11 | T01 |
| T12 | T11 |
| T13 | T12 |
| T14 | T10, T13 |
| T15 | T13 |
| T16 | T05 (errors validated during lexer impl) |
| T17 | T16 |
| T18 | T17 |
| T19 | T15 |
| T20 | T18, T19 |

**Parallel opportunities** (can run in same session):
- T02 and T03 can run in parallel (both depend only on T01)
- T11 can run in parallel with T03/T04/T05/T06 chain
- T16/T17 can begin when T05 is complete (independent of parser/emitter chain)

**Critical path**: T01 -> T03 -> T04 -> T05 -> T06 -> T07 -> T08 -> T09/T10 -> T13/T14 -> T15 -> T19 -> T20

---

## Phase Grouping Summary

| Phase | Tasks | Focus | Gate |
|-------|-------|-------|------|
| Phase 1: Foundation | T01-T06 | LiteralZoneValue + Lexer | Tokenizer produces correct token stream |
| Phase 2: Core Pipeline | T07-T10 | Parser + Emitter + Passthrough | Round-trip invariant holds |
| Phase 3: Validation | T11-T12 | Constraints + Validator | TYPE[LITERAL] and LANG[] working |
| Phase 4: Tools | T13-T15 | MCP validate/write/eject | Zone reporting in all tools |
| Phase 5: Spec + Migration | T16-T20 | Grammar + Spec + A9 gate | 100% corpus pass |

---

## Test Mapping (Blueprint §10.1 Categories -> Tasks)

| Blueprint Category | Count | Mapped To |
|-------------------|-------|-----------|
| Lexer: fence detection | 25 | T06 |
| Lexer: NFC bypass | 10 | T05 |
| Lexer: tab bypass | 8 | T06 |
| Parser: literal zone parsing | 20 | T07 |
| Parser: error cases | 15 | T07, T16 |
| Emitter: round-trip | 20 | T08, T19 |
| Emitter: indentation | 10 | T08 |
| Validator: TYPE[LITERAL] | 10 | T11 |
| Validator: LANG[] constraint | 8 | T11 |
| Validator: validation_status | 8 | T12 |
| MCP validate: zone reporting | 10 | T13 |
| MCP write: preservation | 15 | T14 |
| MCP eject: format export | 10 | T15 |
| Integration: end-to-end | 15 | T19 |
| Property-based | 10 | T19 |
| **Total** | **~194** | |

---

## Risk Register

### HIGH-RISK Tasks

**T05 -- _normalize_with_fence_detection() (HIGHEST)**
- Risk: Coordinate drift if output buffer offsets are miscalculated; this was the B0-B2
  blocking issue. Single-pass approach must be implemented precisely.
- Mitigation: Test with documents where NFC normalization CHANGES string length
  (e.g., content with combining characters outside fences). Verify span offsets
  against returned string, not original.
- Flag: Requires careful line-by-line offset tracking. Test `output_offset` accumulation.

**T06 -- Lexer Token Emission (HIGH)**
- Risk: `raw_content[content_start:content_end]` extraction in §4.5 uses raw string
  offsets but `fence_spans` are against normalized string. Blueprint uses `raw_content`
  for LITERAL_CONTENT but normalized offsets -- these must be reconciled.
- Mitigation: During TDD, verify that LITERAL_CONTENT token value matches the original
  raw content between fences, not the NFC-normalized version.
- Flag: May require carrying both raw and normalized versions of the content.

**T09 -- Exhaustive Match Points projector.py/repair.py (MEDIUM)**
- Risk: Blueprint function names (`_project_value`, `_matches_pattern`, `_repair_value`,
  `_check_value_integrity`) may not match actual function names in codebase. The actual
  functions are `project()` in projector.py and `repair_value()`/`_repair_ast_node()` in repair.py.
- Mitigation: Read each file before implementing; find the actual value-handling code paths.
  The behavior (passthrough) is unambiguous; only the exact insertion point differs.

**T20 -- A9 Migration Gate (MEDIUM)**
- Risk: A pre-existing `.oct.md` file might contain a backtick at line start (currently
  parsed as LexerError E005 "unexpected character"). After this change, such content would
  be interpreted as a fence opener, potentially causing E006.
- Mitigation: Run the A9 test IMMEDIATELY after T06 (lexer complete) to catch any corpus
  regressions early. Do not wait until T20 to discover this.
- Flag: This is an early-warning task, not just a final gate.

### CROSS-CUTTING CONCERNS

**Import consistency**: Every file that imports from `ast_nodes.py` must add `LiteralZoneValue`
to its import list (§3.3). Files affected: `emitter.py`, `validator.py`, `projector.py`,
`repair.py`, `holographic.py` (confirm), `write.py`, `validate.py`, `eject.py`.
Risk: Missing import causes `NameError` at runtime, not at parse time (mypy would catch it).
Mitigation: Add to quality gate -- `mypy` must pass after each task.

**RepairLog naming collision**: `repair_log.py` already has `RepairLog` class for existing
repairs. The new class is named `LiteralZoneRepairLog` in this plan to avoid collision.
However, blueprint §6.4 calls it `RepairLog`. Implementer must use the name `LiteralZoneRepairLog`
(or an agreed rename) and update MCP tool references accordingly.

**E007 subtype discipline**: E007 is currently used for unclosed lists in `parse_list()`.
The new E007_NESTED_FENCE adds a subtype. Existing E007 error messages must not be changed
(backward compatibility); only new occurrences use the `E007_NESTED_FENCE:` prefix.
Verify: `grep -n "E007" src/octave_mcp/core/parser.py` to confirm existing usage.

**TDD gate enforcement**: Per tdd-discipline pattern, each task requires the commit
sequence: `test: Add failing test for X` (RED) then `feat: Implement X` (GREEN).
The constitutional-enforcement skill requires this -- no feat commits without prior
red test commit.

---

## Quality Gate Checklist (Before Merge)

All items must pass on branch `issue-235-literal-zones` before PR to `main`:

- [ ] `pytest` -- all ~1804 tests passing (1610 existing + ~194 new)
- [ ] `mypy` -- zero type errors
- [ ] `ruff` -- zero lint errors
- [ ] `black` -- zero format errors
- [ ] A9 gate -- 100% corpus parse pass (`test_a9_migration_no_regressions`)
- [ ] Round-trip invariant -- `parse(emit(parse(D))) == parse(D)` for all test docs
- [ ] All 13 exhaustive match points from §3.2 covered (verified by grep)
- [ ] `repair_log` present in all three MCP tool responses for docs with literal zones
- [ ] `literal_zones_validated: false` in all validation responses
- [ ] No silent normalization: `LiteralZoneValue.content` never modified by pipeline

---

*End of B1 Build Plan for Issue #235 Literal Zones*
*Handoff to: implementation-lead (B2 phase)*
