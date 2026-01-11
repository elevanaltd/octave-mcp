# CI Test Failure Fix Instructions

## Problem
10 tests are failing because we moved/removed files during the resource consolidation. The tests are looking for files in the old locations that no longer exist.

## Failed Tests Summary

### 1. Debate Schema Tests (7 failures)
**File:** `tests/unit/test_debate_schema.py`
**Issue:** Looking for `specs/schemas/debate_transcript.oct.md` which was deleted
**Solution:** Copy the file back OR update tests to look in new location

### 2. Hydrator Tests (2 failures)
**File:** `tests/unit/test_hydrator.py`
**Issue:** Looking for vocabulary files:
- `specs/vocabularies/core/SNAPSHOT.oct.md`
- `specs/vocabularies/registry.oct.md`
**Solution:** Copy files back OR update hydrator to look in new location

## Implementation Instructions

### Option 1: Quick Fix (Recommended for now)
Copy the needed files back to their original locations:

```bash
# Create directories
mkdir -p specs/schemas specs/vocabularies/core

# Copy from git history (these files were deleted in the consolidation)
git checkout 343c74c -- specs/schemas/debate_transcript.oct.md
git checkout 343c74c -- specs/vocabularies/core/SNAPSHOT.oct.md
git checkout 343c74c -- specs/vocabularies/core/META.oct.md
git checkout 343c74c -- specs/vocabularies/registry.oct.md
```

### Option 2: Update Test Paths (Better long-term)
Update the tests to look in the new consolidated location:

1. Change `test_debate_schema.py` line 28:
```python
# OLD:
schema_path = Path(__file__).parent.parent.parent / "specs" / "schemas" / "debate_transcript.oct.md"
# NEW:
schema_path = Path(__file__).parent.parent.parent / "src" / "octave_mcp" / "resources" / "specs" / "schemas" / "debate_transcript.oct.md"
```

2. Update the schema loader to search in resources directory
3. Update hydrator to look for vocabularies in resources

## Required Skills for Implementation Lead

Please load these skills:
- **build-execution** - For systematic build and test execution
- **TDD discipline** - Tests are failing, need red-green-refactor cycle
- **MIP discipline** - Ensure minimal intervention, just fix the tests

## Test Command
```bash
pytest tests/unit/test_debate_schema.py tests/unit/test_hydrator.py -xvs
```

## Success Criteria
- All 10 failing tests pass
- No new test failures introduced
- CI pipeline green

## Note
We consolidated specs/primers/skills into `src/octave_mcp/resources/` for package distribution, but some tests still expect the old structure. This needs to be fixed either by restoring the needed test files or updating the test paths.
