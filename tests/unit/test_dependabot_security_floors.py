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
- The mcp `<2` ceiling (GH#519) survives the floor raise and excludes every
  2.x release, including 2.0 pre-releases.

Version handling uses `packaging` (PEP 440), not hand-rolled parsing, so
`>=2.15` equals `>=2.15.0` and a pre-release floor such as `>=2.15.0rc1`
fails the guard. `packaging` is a dependency of pytest, black and
virtualenv, so it is present under `pip install -e ".[dev]"`.
"""

import re
import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import Version

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


def _requirement(requirements: list[str], package: str) -> Requirement:
    """Return the single parsed requirement for `package` (name-normalised)."""
    parsed = [Requirement(r) for r in requirements]
    matches = [r for r in parsed if canonicalize_name(r.name) == canonicalize_name(package)]
    assert len(matches) == 1, f"Expected exactly one '{package}' declaration, found {len(matches)}"
    return matches[0]


def _declared_floor(requirements: list[str], package: str) -> Version:
    """Return the `>=` floor declared for `package` as a Version."""
    req = _requirement(requirements, package)
    floors = [Version(spec.version) for spec in req.specifier if spec.operator == ">="]
    assert len(floors) == 1, f"Expected exactly one '>=' floor on {package}, found {[str(f) for f in floors]}"
    return floors[0]


def _assert_floor(requirements: list[str], package: str, floor: str) -> None:
    declared = _declared_floor(requirements, package)
    assert not declared.is_prerelease, f"{package} floor {declared} is a pre-release; floors must be final releases"
    assert declared >= Version(floor), f"{package} floor {declared} is below security floor {floor}"


def _assert_excludes_v2(spec: SpecifierSet) -> None:
    for probe in ("2.0", "2.0.0rc1", "2.2.0"):
        assert not spec.contains(probe, prereleases=True), f"mcp {spec} admits {probe}"
    assert spec.contains("1.99", prereleases=True), f"mcp {spec} excludes 1.99; ceiling too tight"


class TestFloorComparisonSemantics:
    """The comparison helpers themselves must not false-green or false-red."""

    def test_trailing_zero_equivalence(self):
        _assert_floor(["pkg>=2.15"], "pkg", "2.15.0")

    def test_prerelease_floor_rejected(self):
        with pytest.raises(AssertionError, match="pre-release"):
            _assert_floor(["pkg>=2.15.0rc1"], "pkg", "2.15.0")

    def test_lower_floor_rejected(self):
        with pytest.raises(AssertionError, match="below security floor"):
            _assert_floor(["pkg>=2.14.9"], "pkg", "2.15.0")


class TestRuntimeSecurityFloors:
    @pytest.mark.parametrize("package,floor", sorted(RUNTIME_FLOORS.items()))
    def test_runtime_dependency_floor(self, package: str, floor: str):
        _assert_floor(_data()["project"]["dependencies"], package, floor)

    def test_mcp_keeps_v2_ceiling(self):
        """GH#519: every 2.x release (including 2.0 pre-releases) must stay excluded."""
        _assert_excludes_v2(_requirement(_data()["project"]["dependencies"], "mcp").specifier)

    @pytest.mark.parametrize("bad", ["mcp>=1.30.0,<2.5", "mcp>=1.30.0,<20", "mcp>=1.30.0"])
    def test_ceiling_check_rejects_loose_caps(self, bad: str):
        with pytest.raises(AssertionError, match="admits"):
            _assert_excludes_v2(Requirement(bad).specifier)


class TestHttpExtraSecurityFloors:
    @pytest.mark.parametrize("package,floor", sorted(HTTP_EXTRA_FLOORS.items()))
    def test_http_extra_floor(self, package: str, floor: str):
        _assert_floor(_data()["project"]["optional-dependencies"]["http"], package, floor)


class TestDevSecurityFloors:
    @pytest.mark.parametrize("package,floor", sorted(DEV_FLOORS.items()))
    def test_dev_extra_floor(self, package: str, floor: str):
        _assert_floor(_data()["project"]["optional-dependencies"]["dev"], package, floor)

    @pytest.mark.parametrize("package,floor", sorted(DEV_FLOORS.items()))
    def test_dependency_group_floor(self, package: str, floor: str):
        _assert_floor(_data()["dependency-groups"]["dev"], package, floor)

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
