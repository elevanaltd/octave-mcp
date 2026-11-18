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
    # Transitive via mcp/httpx, floored in core metadata because pip ignores uv.lock.
    "anyio": "4.14.2",
    "certifi": "2026.10.18",
    "idna": "3.15",
    "pydantic-settings": "2.14.2",
    "starlette": "1.3.1",
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


# Guard floor table for each manifest section (tomllib section id -> table).
# A section absent from this map has NO guard, so any CVE-commented specifier
# in it is reported as unguarded.
SECTION_TABLES = {
    "project.dependencies": RUNTIME_FLOORS,
    "project.optional-dependencies.http": HTTP_EXTRA_FLOORS,
    "project.optional-dependencies.dev": DEV_FLOORS,
    "dependency-groups.dev": DEV_FLOORS,
}
_CVE_COMMENT = re.compile(r"#.*(?:CVE-|GHSA-)")


def _sections(data: dict) -> dict[str, list[str]]:
    """Section id -> specifier strings, in file order, from the parsed TOML."""
    sections = {"project.dependencies": list(data["project"].get("dependencies", []))}
    for extra, reqs in data["project"].get("optional-dependencies", {}).items():
        sections[f"project.optional-dependencies.{extra}"] = list(reqs)
    for group, reqs in data.get("dependency-groups", {}).items():
        sections[f"dependency-groups.{group}"] = list(reqs)
    return sections


def _cve_commented(raw_text: str, sections: dict[str, list[str]]) -> dict[str, list[str]]:
    """Per section, the specifiers whose raw line carries a CVE-/GHSA- comment.

    Section structure comes from tomllib; raw lines are used only to learn which
    specifiers carry a comment. A specifier is matched to its raw line by its
    text inside a quoted TOML string (either quote style). Identical specifier
    text appearing in several sections is paired by order of occurrence, which
    holds because tomllib preserves file order.
    """
    lines = raw_text.splitlines()
    seen: dict[str, int] = {}
    commented: dict[str, list[str]] = {}
    for section, specs in sections.items():
        for spec in specs:
            raw = [ln for ln in lines if f'"{spec}"' in ln or f"'{spec}'" in ln]
            index = seen.get(spec, 0)
            seen[spec] = index + 1
            assert index < len(raw), f"could not locate {spec!r} in the raw pyproject text"
            line = raw[index]
            tail = line.split(f'"{spec}"', 1)[-1] if f'"{spec}"' in line else line.split(f"'{spec}'", 1)[-1]
            if _CVE_COMMENT.search(tail):
                commented.setdefault(section, []).append(spec)
    return commented


def _unguarded(raw_text: str, data: dict) -> list[str]:
    """CVE-commented specifiers whose package is not in THEIR OWN section's table."""
    out = []
    for section, specs in _cve_commented(raw_text, _sections(data)).items():
        table = {canonicalize_name(name) for name in SECTION_TABLES.get(section, {})}
        out += [f"{section}: {spec}" for spec in specs if canonicalize_name(Requirement(spec).name) not in table]
    return sorted(out)


class TestEveryCveCommentedSpecifierIsGuarded:
    """Meta-assertion: a CVE/GHSA-commented specifier must be guarded in its own section."""

    def test_all_cve_commented_specifiers_are_in_their_section_tables(self):
        raw = PYPROJECT_PATH.read_text()
        data = tomllib.loads(raw)
        assert _cve_commented(raw, _sections(data)), "no CVE-commented specifiers found; the scan is broken"
        unguarded = _unguarded(raw, data)
        assert not unguarded, f"CVE/GHSA-commented specifiers missing from their section's guard table: {unguarded}"

    def test_single_quoted_commented_specifier_is_detected(self):
        raw = "[project]\ndependencies = [\n  'newpkg>=1.0',  # CVE-2099-0001: x\n]\n"
        assert _unguarded(raw, tomllib.loads(raw)) == ["project.dependencies: newpkg>=1.0"]

    def test_specifier_guarded_only_by_another_section_is_detected(self):
        # black is guarded for the dev extra/group, NOT for runtime dependencies.
        raw = '[project]\ndependencies = [\n  "black>=26.10.1",  # CVE-2026-114134\n]\n'
        assert _unguarded(raw, tomllib.loads(raw)) == ["project.dependencies: black>=26.10.1"]

    def test_guarded_specifier_in_its_own_section_passes(self):
        raw = '[project]\ndependencies = [\n  "PyJWT>=2.15.0",  # CVE-2026-101917\n]\n'
        assert _unguarded(raw, tomllib.loads(raw)) == []
