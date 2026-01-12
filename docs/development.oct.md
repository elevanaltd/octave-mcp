===OCTAVE_MCP_DEVELOPMENT===
META:
  TYPE::"DEVELOPER_DOC"
  VERSION::"1.0.0"
  STATUS::ACTIVE
  PURPOSE::"How to set up a local dev environment and run tests/quality gates"

§1::GOAL
  PRINCIPLE::"Make local workflows match CI to avoid surprise failures"

§2::INSTALLATION
  RECOMMENDED::"Use an isolated virtualenv and install the package in editable mode"
  COMMANDS::[
    "python -m pip install -e '.[dev]'",
    "python -m pip install -e ."
  ]
  NOTES::[
    "The dev extra includes test/runtime tooling such as pytest-timeout and hypothesis (see pyproject.toml)",
    "Without installation, many tests will fail to import octave_mcp"
  ]

§3::RUNNING_TESTS
  FULL_SUITE::[
    "python -m pytest",
    "python -m pytest -q"
  ]

  FAST_PATH_NO_INSTALL::[
    "If you only need parser-level validation on repo resources, you can run a subset with PYTHONPATH",
    "Example: PYTHONPATH=src python -m pytest -q tests/test_spec_validation.py"
  ]

§4::QUALITY_GATES
  LINT::"ruff check src tests"
  FORMAT::"black --check src tests"
  TYPES::"mypy src"

§5::TROUBLESHOOTING
  IMPORT_ERRORS::[
    "Symptom: ModuleNotFoundError: no module named 'octave_mcp'",
    "Fix: install editable (recommended) or run targeted tests with PYTHONPATH=src"
  ]
  MISSING_DEPS::[
    "Symptom: ModuleNotFoundError for tools like 'hypothesis' or pytest plugins",
    "Fix: python -m pip install -e '.[dev]'"
  ]

===END===
