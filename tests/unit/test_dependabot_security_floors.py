"""Guard test: pyproject.toml declares the Dependabot security floors.

CI and PyPI installs resolve from the *declared constraints* in
pyproject.toml (`pip install -e ".[dev]"` ignores uv.lock -- see
test_gh519_mcp_dependency_cap.py for the same rationale). A lock-only fix
would close Dependabot alerts while changing nothing users actually
install, so the floors themselves are the artifact to pin.

Tests verify:
- Every specifier carrying a `# CVE-`/`GHSA-` comment is in a floor table
  below (meta-assertion), so a future security floor cannot go unguarded.
- Each direct dependency carries a `>=` floor at or above the first
  patched version of its open advisories.
- The `dev` extra and the PEP-735 `dev` dependency-group stay in sync.
- The mcp `<2` ceiling (GH#519) survives the floor raise.
"""

import re
import tomllib
from pathlib import Path

import pytest

PYPROJECT_PATH = Path(__file__).resolve().parents[2] / "pyproject.toml"

RUNTIME_FLOORS = {
    "PyJWT": "2.15.0",
    "cryptography": "50.0.0",
    "filelock": "4.2.1",
    "python-multipart": "0.0.31",
    "mcp": "1.30.0",
}
HTTP_EXTRA_FLOORS = {"starlette": "1.3.1"}
DEV_FLOORS = {"virtualenv": "21.14.9", "black": "26.10.1", "Pygments": "2.20.0"}  # Pygments: CVE-2025-61833


def _data() -> dict:
    return tomllib.loads(PYPROJECT_PATH.read_text())


def _version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def _declared_floor(requirements: list[str], package: str) -> tuple[int, ...]:
    """Return the `>=` floor declared for `package` in a requirements list."""
    pattern = re.compile(rf"^{re.escape(package)}\s*>=\s*([0-9]+(?:\.[0-9]+)*)", re.IGNORECASE)
    matches = [m for req in requirements if (m := pattern.match(req))]
    assert len(matches) == 1, f"Expected exactly one '{package}>=' declaration, found {len(matches)}"
    return _version_tuple(matches[0].group(1))


class TestRuntimeSecurityFloors:
    @pytest.mark.parametrize("package,floor", sorted(RUNTIME_FLOORS.items()))
    def test_runtime_dependency_floor(self, package: str, floor: str):
        declared = _declared_floor(_data()["project"]["dependencies"], package)
        assert declared >= _version_tuple(floor), f"{package} floor {declared} is below security floor {floor}"

    def test_mcp_keeps_v2_ceiling(self):
        mcp = [d for d in _data()["project"]["dependencies"] if d.startswith("mcp")]
        assert len(mcp) == 1 and "<2" in mcp[0], f"GH#519 ceiling lost: {mcp}"


class TestHttpExtraSecurityFloors:
    @pytest.mark.parametrize("package,floor", sorted(HTTP_EXTRA_FLOORS.items()))
    def test_http_extra_floor(self, package: str, floor: str):
        declared = _declared_floor(_data()["project"]["optional-dependencies"]["http"], package)
        assert declared >= _version_tuple(floor), f"{package} floor {declared} is below security floor {floor}"


class TestDevSecurityFloors:
    @pytest.mark.parametrize("package,floor", sorted(DEV_FLOORS.items()))
    def test_dev_extra_floor(self, package: str, floor: str):
        declared = _declared_floor(_data()["project"]["optional-dependencies"]["dev"], package)
        assert declared >= _version_tuple(floor), f"{package} floor {declared} is below security floor {floor}"

    @pytest.mark.parametrize("package,floor", sorted(DEV_FLOORS.items()))
    def test_dependency_group_floor(self, package: str, floor: str):
        declared = _declared_floor(_data()["dependency-groups"]["dev"], package)
        assert declared >= _version_tuple(floor), f"{package} floor {declared} is below security floor {floor}"

    def test_dev_extra_and_group_stay_in_sync(self):
        data = _data()
        assert sorted(data["project"]["optional-dependencies"]["dev"]) == sorted(data["dependency-groups"]["dev"])


class TestEveryCveCommentedSpecifierIsGuarded:
    """Meta-assertion: a CVE/GHSA-commented dependency line must be guarded here."""

    def test_all_cve_commented_specifiers_are_in_floor_tables(self):
        guarded = {name.lower() for table in (RUNTIME_FLOORS, HTTP_EXTRA_FLOORS, DEV_FLOORS) for name in table}
        line_re = re.compile(r'^\s*"([A-Za-z0-9_.\-]+)[^"]*"\s*,?\s*#.*(?:CVE-|GHSA-)')
        commented = {
            m.group(1).lower() for line in PYPROJECT_PATH.read_text().splitlines() if (m := line_re.match(line))
        }
        assert commented, "no CVE-commented dependency lines found; the scan itself is broken"
        unguarded = sorted(commented - guarded)
        assert not unguarded, f"CVE/GHSA-commented dependencies missing from the guard floor tables: {unguarded}"
