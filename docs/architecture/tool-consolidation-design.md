# D2 Architecture Design: OCTAVE-MCP Tool Consolidation (GH#51)

## Mission
Consolidate the current 4-tool suite (`octave_ingest`, `octave_create`, `octave_amend`, `octave_eject`) into a streamlined 3-tool API (`octave_validate`, `octave_write`, `octave_eject`) to reduce cognitive load, enforce North Star immutables, and simplify the developer experience.

## Current vs Target State

### Current State (4 Tools)
1.  **`octave_ingest`**: Read-only validation and normalization. Pipeline: PREPARSE→PARSE→NORMALIZE→VALIDATE→REPAIR.
2.  **`octave_create`**: Write new files. Pipeline: TOKENIZE→PARSE→EMIT→WRITE. Tracks corrections.
3.  **`octave_amend`**: Modify existing files. Pipeline: READ→PARSE→APPLY→EMIT→WRITE. Tracks corrections.
4.  **`octave_eject`**: Read-only projection. Formats: OCTAVE, JSON, YAML, MARKDOWN.

### Target State (3 Tools)
1.  **`octave_validate`**: Schema check + repair suggestions. Focus on I3 (Mirror Constraint) and I5 (Schema Sovereignty).
2.  **`octave_write`**: Unified write operation. Auto-detects new vs existing files. Handles both full content overwrite and granular updates.
3.  **`octave_eject`**: Unchanged. Handles format conversion and views.

---

## Detailed Specification

### 1. `octave_validate`

**Purpose**: Provide authoritative validation of OCTAVE content against a schema, with optional repair suggestions. Replaces `octave_ingest`.

**Signature**:
```python
def validate(
    content: str,
    schema: str,
    fix: bool = False
) -> Dict[str, Any]
```

**Parameters**:
- `content` (Required): The OCTAVE content to validate.
- `schema` (Required): The schema name to validate against (e.g., 'META', 'SESSION_LOG').
- `fix` (Optional): If `True`, applies repair logic (TIER_REPAIR) to the canonical output. If `False`, repairs are suggested but not applied.

**Returns**:
```json
{
  "status": "success" | "error",  // CRS FIX: Unified envelope
  "canonical": "...",             // Normalized content (repaired if fix=True)
  "repairs": [],                  // List of repairs applied or suggested
  "warnings": [],                 // Validation warnings (non-fatal)
  "errors": [],                   // CRS FIX: Parse/schema errors (fatal)
  "validation_status": "VALIDATED" | "UNVALIDATED" | "PENDING_INFRASTRUCTURE"  // CRS FIX: Unified enum
}
```

**Logic**:
1.  **Parse**: Tokenize and parse `content`.
2.  **Schema Check**: Validate AST against `schema`.
3.  **Repair**:
    *   If `fix=True`: Apply TIER_REPAIR logic. Update AST.
    *   If `fix=False`: Generate repair suggestions based on validation errors.
4.  **Emit**: Generate `canonical` string from (potentially repaired) AST.
5.  **Status**: Determine `validation_status` based on schema presence and validation result.

**North Star Alignment**:
- **I3 (Mirror Constraint)**: Returns errors/warnings instead of guessing. Only repairs if explicitly requested (`fix=True`).
- **I5 (Schema Sovereignty)**: Explicitly emits `validation_status`.

### 2. `octave_write`

**Purpose**: Unified entry point for writing OCTAVE files. Handles creation (new files) and modification (existing files) with North Star compliance. Replaces `octave_create` and `octave_amend`.

**Signature**:
```python
def write(
    target_path: str,
    content: Optional[str] = None,
    changes: Optional[Dict[str, Any]] = None,
    mutations: Optional[Dict[str, Any]] = None,
    base_hash: Optional[str] = None,
    schema: Optional[str] = None  # I5 FIX: Added for schema sovereignty
) -> Dict[str, Any]
```

**Parameters**:
- `target_path` (Required): Absolute path to the file.
- `content` (Optional): Full content for new files or overwrites. Mutually exclusive with `changes`.
- `changes` (Optional): Dictionary of field updates for existing files. Mutually exclusive with `content`. Uses tri-state semantics (see I2 Compliance below).
- `mutations` (Optional): META field overrides (applies to both modes).
- `base_hash` (Optional): Expected SHA-256 hash of existing file for consistency check (CAS).
- `schema` (Optional): Schema name for validation. If provided, content is validated and `validation_status` is returned. If omitted, returns `validation_status: "UNVALIDATED"`.

**Returns**:
```json
{
  "status": "success" | "error",  // CRS FIX: Unified envelope
  "path": "/path/to/file.oct.md",
  "canonical_hash": "sha256...",
  "corrections": [],              // W001-W005 corrections
  "diff": "...",                  // Compact diff of changes
  "errors": [],                   // CRS FIX: Parse/path/hash errors
  "validation_status": "VALIDATED" | "UNVALIDATED" | "PENDING_INFRASTRUCTURE"  // Unified enum
}
```

**Error Envelope** (on failure):
```json
{
  "status": "error",
  "errors": [{"code": "E_PATH", "message": "..."}],  // E_PATH, E_PARSE, E_HASH, E_WRITE, E_INPUT
  "corrections": []  // May contain partial corrections before failure
}
```

**I2 Compliance: Tri-State Semantics for `changes`**:
The `changes` dictionary uses explicit tri-state semantics to comply with I2 (Deterministic Absence):
- **Key absent**: No change to field (field untouched)
- **Key present with value `{"$op": "DELETE"}`**: Delete the field entirely (absence)
- **Key present with value `null`**: Set field to explicit null/empty (null value, not absence)
- **Key present with other value**: Update field to new value

> **CRS FIX**: DELETE sentinel encoded as JSON object `{"$op": "DELETE"}` for MCP transmission.
> Alternative encoding: Reserved string `"__OCTAVE_DELETE__"` (validated on input).

Example (JSON):
```json
{
  "VERSION": "2.0",
  "DEPRECATED": {"$op": "DELETE"},
  "NOTES": null
}
```

Example (Python SDK):
```python
from octave_mcp import DELETE  # Sentinel that serializes to {"$op": "DELETE"}

changes = {
    "VERSION": "2.0",           # Update VERSION to "2.0"
    "DEPRECATED": DELETE,       # Remove DEPRECATED field entirely
    "NOTES": None               # Set NOTES to explicit null (empty)
}
```

**Logic (Unified Parameter Model)**:
1.  **Validation**: Ensure `target_path` is valid. Ensure strictly one of `content` or `changes` is provided.
2.  **Detection**: Check if `target_path` exists.
3.  **Branching**:
    *   **Case A: `changes` provided (Amend Mode)**:
        *   Verify file exists (Error if not).
        *   Read file.
        *   Verify `base_hash` (if provided).
        *   Parse -> Apply `changes` -> Normalize.
    *   **Case B: `content` provided (Create/Overwrite Mode)**:
        *   Parse `content` -> Normalize.
        *   If file exists AND `base_hash` provided: Verify hash matches (CAS guard against concurrent edits).
        *   If file exists: Treat as overwrite (logging diff).
4.  **Mutation**: Apply `mutations` (META fields) to AST.
5.  **Write**: Atomic write (temp file -> fsync -> rename).
6.  **Audit**: Return diff and corrections.

> **CAS Consistency**: `base_hash` is honored in BOTH modes when the target file exists. This prevents silent clobbering of concurrent edits regardless of whether `content` or `changes` is used.

**North Star Alignment**:
- **I1 (Syntactic Fidelity)**: Normalizes to canonical form. Logs all corrections.
- **I2 (Deterministic Absence)**: `changes` dict uses tri-state semantics: absent (no-op), `octave.DELETE` (remove field), `null` (set to empty).
- **I4 (Auditability)**: Returns `corrections` and `diff` for every write.
- **I5 (Schema Sovereignty)**: Always returns `validation_status`. If `schema` param provided, validates and returns `VALIDATED`/`UNVALIDATED`. If omitted, returns `UNVALIDATED` (never silent bypass).

### 3. `octave_eject`

**Purpose**: Project OCTAVE content into various formats and views. Unchanged from current implementation but verified for context.

**Signature** (Existing):
```python
def eject(
    content: Optional[str],
    schema: str,
    mode: str = "canonical",
    format: str = "octave"
) -> Dict[str, Any]
```

**North Star Alignment**:
- **I3 (Mirror Constraint)**: Read-only projection, does not invent data.
- **I5 (Schema Sovereignty)**: Uses `schema` to drive templates if content is null.

---

## Decision Record: Unified vs. Mode-Based for `octave_write`

**Decision**: **Option A (Unified Parameter Model)**

**Rationale**:
1.  **API Simplicity**: Reduces the number of required parameters. The intent is strictly inferred from the data provided (`content` = full payload, `changes` = delta payload).
2.  **Cognitive Load**: Users don't need to manually set `mode="create"` or `mode="amend"`. The tool "does the right thing" based on the input.
3.  **Error Handling**: Mutually exclusive parameters allow for clear validation errors (e.g., "Cannot provide both 'content' and 'changes'").
4.  **Migration**: Maps cleanly to the mental models of "write this file" vs "update this file".

**Rejected Option**: Option B (Explicit Mode) was rejected because it introduces redundancy. Providing `mode="create"` with `changes` is a logical conflict that requires extra validation, whereas implied mode eliminates this state space.

---

## Migration Path

### 1. Deprecation Timeline
*   **Phase 1 (Immediate)**: Introduce `octave_validate` and `octave_write`. Mark `ingest`, `create`, `amend` as deprecated with warning logs.
*   **Phase 2 (+4 Weeks)**: Soft-remove deprecated tools (hidden from list, but callable).
*   **Phase 3 (+12 Weeks)**: Hard-remove deprecated tools.

> **Note**: Timeline extended per PE review. Original 4-week hard-remove was too aggressive for production consumers.

### 2. Migration Guide Structure
*   **Mapping Table**:
    *   `octave_ingest(...)` → `octave_validate(..., fix=True)`
    *   `octave_create(...)` → `octave_write(content=...)`
    *   `octave_amend(...)` → `octave_write(changes=...)`
*   **Behavioral Changes**: Note that `validate` is explicit about status. `write` auto-detects existence.

---

## North Star Alignment Verification

| Feature | I1 (Syntactic) | I2 (Absence) | I3 (Mirror) | I4 (Audit) | I5 (Schema) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`octave_validate`** | Canonical output guarantees syntactic fidelity. | Parse logic respects absent/null distinction. | Errors on invalid input (unless `fix=True`). | Returns `repairs` list. | Returns `validation_status`. |
| **`octave_write`** | Normalizes content before write. | Tri-state: absent=no-op, `{"$op":"DELETE"}`=remove, null=empty. | No guessing; explicit inputs required. | Returns `corrections` and `diff`. | Returns `validation_status` always. |
| **`octave_eject`** | N/A (Read-only). | Preserves absence in projections. | Reflects only what exists. | N/A. | Uses schema for context. |

---

## Quality Gate Review Summary

### Critical Engineer (Gemini) Review
- **I1**: PASS
- **I2**: PASS (after adding tri-state semantics with `{"$op": "DELETE"}` sentinel)
- **I3**: PASS
- **I4**: PASS
- **I5**: PASS (after adding `schema` param and `validation_status` return to `octave_write`)

### Code Review Specialist (Codex) Review
- **API Design**: PASS (after unified envelope + error field additions)
- **I2 DELETE Encoding**: PASS (after JSON encoding `{"$op": "DELETE"}` specified)
- **I5 Enum Consistency**: PASS (after unifying enum across validate/write)
- **Error Envelope**: PASS (after specifying error codes: E_PATH, E_PARSE, E_HASH, E_WRITE, E_INPUT)
- **Migration Notes**:
  - Document dropped params from ingest→validate (`tier`, `verbose`)
  - Keep deprecated tools listed until hard-remove

### Principal Engineer (Claude) Review
- **Strategic Viability**: CONDITIONAL GO
- **Prophetic Warnings**:
  1. Schema validation infrastructure pending (P2.5) - return `PENDING_INFRASTRUCTURE` until complete
  2. `mutations` stub in current codebase needs implementation before deployment
  3. Deprecation timeline extended to 12 weeks per strategic recommendation
- **Blockers Addressed**: Schema disclaimer via explicit status, mutations documented as pending

---
