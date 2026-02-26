# Migration Guide: octave_ingest to octave_validate

## Overview

The `octave_ingest` tool is deprecated and will be removed 12 weeks from the GH#51 merge date.
Use `octave_validate` as the replacement.

**Deprecation Timeline**: 12 weeks from GH#51 merge (see CHANGELOG for exact date)

## Why This Change?

The consolidation aligns with HestAI immutables:

- **I3 (Mirror Constraint)**: `octave_validate` returns explicit errors instead of guessing intent
- **I5 (Schema Sovereignty)**: Adds `validation_status` field for explicit validation state tracking

## Envelope Differences

### Before: octave_ingest Response

```python
{
    "canonical": "",      # Normalized OCTAVE content
    "repairs": [],        # List of repairs applied
    "warnings": [],       # Validation warnings
    "stages": {}          # Optional: pipeline stages (if verbose=True)
}
```

### After: octave_validate Response

```python
{
    "status": "success",                        # NEW: "success" or "error"
    "canonical": "",                            # Normalized OCTAVE content
    "repairs": [],                              # List of repairs applied/suggested
    "warnings": [],                             # Validation warnings (non-fatal)
    "errors": [],                               # NEW: Parse/schema errors (fatal)
    "validation_status": "PENDING_INFRASTRUCTURE"  # NEW: I5 validation state
}
```

### Key Differences

| Field | octave_ingest | octave_validate | Notes |
|-------|---------------|-----------------|-------|
| `status` | Not present | Present | "success" or "error" |
| `errors` | Not present | Present | Fatal errors separated from warnings |
| `validation_status` | Not present | Present | VALIDATED, UNVALIDATED, or PENDING_INFRASTRUCTURE |
| `stages` | Present (if verbose) | Removed | Pipeline stages no longer exposed |
| `tier` parameter | Accepted (ignored) | Removed | Compression tiers deferred to future phase |
| `verbose` parameter | Accepted | Removed | Pipeline internals no longer exposed |

## Code Migration Examples

### Python Client Migration

**Before:**
```python
result = await mcp_client.call_tool("octave_ingest", {
    "content": octave_content,
    "schema": "META",
    "fix": True,
    "verbose": True
})

canonical = result["canonical"]
warnings = result.get("warnings", [])
```

**After:**
```python
result = await mcp_client.call_tool("octave_validate", {
    "content": octave_content,
    "schema": "META",
    "fix": True
})

# Handle new envelope structure
if result["status"] == "error":
    for error in result["errors"]:
        print(f"Error {error['code']}: {error['message']}")
    raise ValidationError(result["errors"])

canonical = result["canonical"]
warnings = result.get("warnings", [])
validation_status = result["validation_status"]

# Check validation status per I5
if validation_status == "UNVALIDATED":
    log.warning("Content failed schema validation")
```

### Error Handling Changes

**Before** (errors mixed with warnings):
```python
result = await mcp_client.call_tool("octave_ingest", {...})
# Errors hidden in warnings - easy to miss fatal issues
for warning in result.get("warnings", []):
    if warning["code"].startswith("E"):  # Heuristic to find errors
        handle_error(warning)
```

**After** (explicit error separation):
```python
result = await mcp_client.call_tool("octave_validate", {...})

# Fatal errors are explicit
if result["status"] == "error":
    for error in result["errors"]:
        handle_error(error)  # Contains: code, message
    return  # Stop processing

# Non-fatal warnings separate
for warning in result["warnings"]:
    log.warning(f"{warning['code']}: {warning['message']}")
```

## Parameter Migration

| octave_ingest | octave_validate | Action |
|---------------|-----------------|--------|
| `content` | `content` | No change |
| `schema` | `schema` | No change |
| `fix` | `fix` | No change |
| `tier` | - | Remove (not supported) |
| `verbose` | - | Remove (not supported) |

## Validation Status Values

The new `validation_status` field (I5 compliance) has three possible values:

- **VALIDATED**: Content passed schema validation
- **UNVALIDATED**: Content failed schema validation
- **PENDING_INFRASTRUCTURE**: Schema validation infrastructure not yet available (P2.5 work)

## Migration Checklist

- [ ] Replace `octave_ingest` calls with `octave_validate`
- [ ] Remove `tier` parameter (not supported)
- [ ] Remove `verbose` parameter (not supported)
- [ ] Add `status` field check before processing results
- [ ] Update error handling to use `errors` array (not warnings)
- [ ] Add `validation_status` handling per I5 requirements
- [ ] Update any code that parsed `stages` (removed)

## Timeline

- **Now**: `octave_ingest` emits DeprecationWarning
- **12 weeks from GH#51**: `octave_ingest` removed from codebase

## Questions?

See GH#51 for full consolidation discussion and rationale.
