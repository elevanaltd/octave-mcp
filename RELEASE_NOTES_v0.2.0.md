# OCTAVE-MCP v0.2.0 Release Notes

**Release Date**: 2025-12-31

## Highlights

This release completes the **3-tool consolidation** and includes important **security hardening**. The MCP tool surface has been streamlined from 6 tools to 3, providing a cleaner, more maintainable API.

## Breaking Changes

### Tool Consolidation

The following deprecated tools have been **removed**:

| Removed Tool | Replacement | Migration |
|--------------|-------------|-----------|
| `octave_ingest` | `octave_validate` | Same parameters, same functionality |
| `octave_create` | `octave_write` | Use `content` parameter for new files |
| `octave_amend` | `octave_write` | Use `changes` parameter for modifications |

### Migration Examples

```python
# Before (v0.1.x)
result = await call_tool("octave_ingest", {"content": "...", "schema": "META"})
result = await call_tool("octave_create", {"content": "...", "target_path": "/path/to/file.oct.md"})
result = await call_tool("octave_amend", {"target_path": "/path/to/file.oct.md", "changes": {...}})

# After (v0.2.0)
result = await call_tool("octave_validate", {"content": "...", "schema": "META"})
result = await call_tool("octave_write", {"content": "...", "target_path": "/path/to/file.oct.md"})
result = await call_tool("octave_write", {"target_path": "/path/to/file.oct.md", "changes": {...}})
```

## New Features

### octave_validate file_path mode
- Validate files directly without reading content into prompts
- Token-efficient validation for large files
- Extension whitelist enforcement (`.md`, `.oct.md`, `.octave`)

### octave_write dot-notation
- Update nested fields with dot notation: `{"META.STATUS": "ACTIVE"}`
- Properly merges changes into existing blocks
- CAS (Compare-and-Swap) support via `base_hash`

## Security Hardening

- **Extension whitelist**: Only `.md`, `.oct.md`, `.octave` files can be validated/written
- **Path traversal prevention**: `..` sequences rejected
- **Symlink rejection**: Symlinks are rejected to prevent exfiltration attacks
- **Parent directory traversal via symlinks**: Even resolved paths that escape the allowed directory are blocked

## North Star Immutables Enforced

| Immutable | Status | Implementation |
|-----------|--------|----------------|
| I1: Syntactic Fidelity | ENFORCED | Unified operators |
| I2: Deterministic Absence | ENFORCED | Absent sentinel type |
| I3: Mirror Constraint | ENFORCED | Visible schema bypass |
| I4: Transform Auditability | ENFORCED | parse_with_warnings |
| I5: Schema Sovereignty | PARTIAL | validation_status field |

## Quality Metrics

- **Tests**: 512 passed, 4 skipped
- **Coverage**: 88%
- **Type Safety**: mypy clean
- **Lint**: ruff clean

## Files Changed

- 21 files modified
- 267 lines added
- 2,235 lines removed (net reduction)

## Contributors

- Claude Opus 4.5 (AI pair programmer)

---

**Full Changelog**: https://github.com/elevanaltd/octave-mcp/compare/v0.1.0...v0.2.0
