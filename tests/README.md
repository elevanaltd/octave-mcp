# OCTAVE Primer Test Suite

Test protocol to verify the micro-primer enables direct OCTAVE emission with ~96% validity.

## Test Setup

1. Start a fresh LLM session (ChatGPT, Claude, etc.)
2. Paste the system prompt from `/templates/system-prompt-octave.md`
3. This includes the micro-primer and canonical examples inline

## Test Cases

### Test 1: Basic Syntax Validation
**Prompt**: "Describe a system under heavy load"

**Expected**: Valid OCTAVE with proper structure
```octave
===SYSTEM_STATUS===
STATUS::DEGRADED
LOAD::HIGH
METRICS:
  CPU::89
  MEMORY::92
===END===
```

### Test 2: Mythological Semantic Activation
**Prompt**: "Analyze a project that started well but is now failing due to overconfidence"

**Expected**: Should use Greek mythological patterns
```octave
===PROJECT_ANALYSIS===
PATTERN::ICARIAN_TRAJECTORY
INITIAL_STATE::PROMETHEAN
CURRENT_STATE::HUBRIS->NEMESIS
===END===
```

### Test 3: Operator Usage
**Prompt**: "Show the tension between system reliability and feature delivery speed"

**Expected**: Correct use of ⇌ (or 'vs') tension operator
```octave
===TENSION_ANALYSIS===
CORE_CONFLICT::RELIABILITY⇌SPEED
IMPACT::TECHNICAL_DEBT
===END===
```

### Test 4: Complex Structure
**Prompt**: "Model a microservices architecture with authentication, database, and API services"

**Expected**: Proper nesting and domain assignment
```octave
===ARCHITECTURE===
SERVICES:
  AUTH:
    DOMAIN::ARES
    STATUS::ACTIVE
  DATABASE:
    DOMAIN::POSEIDON
    STATUS::DEGRADED
  API:
    DOMAIN::HERMES
    STATUS::NORMAL
===END===
```

### Test 5: Progression and Synthesis
**Prompt**: "Describe a deployment pipeline and a strategy combining wisdom with decisive action"

**Expected**: Correct operator usage
```octave
===DEPLOYMENT===
PIPELINE::[BUILD->TEST->STAGE->DEPLOY]
STRATEGY::ATHENA+GORDIAN
===END===
```

### Test 6: No Prose Compliance
**Prompt**: "Explain OCTAVE format"

**Expected**: OCTAVE response, not prose explanation
```octave
===OCTAVE_DEFINITION===
PURPOSE::SEMANTIC_COMPRESSION
METHOD::MYTHOLOGICAL_VOCABULARY
BENEFIT::10X_TOKEN_REDUCTION
===END===
```

## Validation Protocol

For each test response:

1. **Syntax Check**: Run through `lint-octave.py`
   ```bash
   python3 tools/lint-octave.py < test_response.oct
   ```
   Should return: `OCTAVE_VALID`

2. **Semantic Check**: Verify Greek mythology usage
   - Domains from: Zeus, Athena, Apollo, Hermes, Ares, etc.
   - Patterns from: Odyssean, Icarian, Promethean, etc.
   - Forces from: Chronos, Hubris, Nemesis, Kairos, etc.

3. **Operator Check**: Ensure correct usage
   - `+` only for synthesis
   - `⇌` or `vs` for binary tension (cannot chain)
   - `->` only inside lists

## Success Criteria

- 5/6 tests produce valid OCTAVE = ~83% (acceptable)
- 6/6 tests produce valid OCTAVE = ~100% (excellent)
- Greek mythology used appropriately
- No prose responses
- Operators used correctly

## Failure Modes to Watch

1. **Mixed mythology**: Norse, Roman, or modern references
2. **Prose leakage**: Explanatory text outside OCTAVE structure
3. **Operator confusion**: Using -> outside lists, wrong operator
4. **Invalid syntax**: Missing ===END===, wrong indentation

## Iterative Improvement

If success rate < 80%:
1. Check if full primer was included in system prompt
2. Verify canonical examples are present
3. Consider adding one more specific example
4. Test with different LLM temperature settings
