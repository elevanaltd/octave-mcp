---
name: testing
description: Testing patterns and conventions for HestAI MCP including pytest markers, TDD protocol, and coverage requirements
allowed-tools: ["Bash", "Read", "Write", "Edit", "Grep"]
triggers: ["pytest", "test markers", "TDD", "test driven", "unit tests", "behavior tests", "integration tests", "conftest", "async testing", "pytest-asyncio"]
---

===TESTING===
META:
  TYPE::SKILL
  VERSION::"1.0"
  STATUS::ACTIVE
  PURPOSE::"Testing patterns and conventions for HestAI MCP"
  DOMAIN::ATHENA[quality]⊕HEPHAESTUS[craftsmanship]

§1::TEST_MARKERS
  // Progressive Testing Model
  SMOKE::@pytest.mark.smoke["Fast import/sanity tests (<1s)"]
  BEHAVIOR::@pytest.mark.behavior["NOW: Real behavioral tests"]
  CONTRACT::@pytest.mark.contract["SOON: Integration contract tests"]
  INTEGRATION::@pytest.mark.integration["LATER: Full integration tests"]
  PROGRESSION::smoke→behavior→contract→integration

§2::TEST_STRUCTURE
  LAYOUT::[
    "tests/",
    "  unit/           # Component-level tests",
    "  behavior/       # Behavioral specification tests",
    "  contracts/      # External integration contracts",
    "  conftest.py     # Shared fixtures"
  ]
  MIRRORING::tests/unit/{module}/test_{file}.py↔src/{module}/{file}.py

§3::TDD_PROTOCOL
  SEQUENCE::[
    RED::"Write failing test first",
    GREEN::"Minimal implementation to pass",
    REFACTOR::"Improve while green"
  ]
  COMMIT_SEQUENCE::"test:" → "feat:" → "refactor:"
  DISCIPLINE::test_before_implementation[MANDATORY]

§4::COVERAGE
  THRESHOLD::89%[CI_enforced]
  FOCUS::behavioral_coverage[not_line_coverage]
  MOCKING::external_dependencies[not_internal_modules]
  ANTI_PATTERN::coverage_theater["Tests that hit lines but don't assert behavior"]

§5::ASYNC_TESTING
  CONFIG::asyncio_mode="auto"[pytest_config]
  FRAMEWORK::pytest-asyncio
  PATTERN::[
    "async def test_async_operation():",
    "    result = await async_function()",
    "    assert result.status == 'success'"
  ]

§6::COMMANDS
  RUN_ALL::"python -m pytest"
  RUN_MARKER::"python -m pytest -m {marker}"
  RUN_COVERAGE::"python -m pytest --cov=src --cov-report=term-missing"
  RUN_SPECIFIC::"python -m pytest tests/unit/{path}/test_{file}.py -v"

§7::FIXTURES
  LOCATION::tests/conftest.py[shared]
  SCOPE::[function,class,module,session]
  EXAMPLE::[
    "@pytest.fixture",
    "def sample_config():",
    "    return SessionConfig(role='test', working_dir='/tmp')"
  ]

===END===
