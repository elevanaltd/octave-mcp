#!/usr/bin/env python3
"""Tests for tools/octave-validator.py.

The repo tool is intentionally a thin wrapper around OCTAVE-MCP core parsing.
These tests validate profile policy (YAML frontmatter) and marker requirements,
not full language semantics.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add tools directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import from octave-validator.py (hyphenated filename)
import importlib.util

spec = importlib.util.spec_from_file_location(
    "octave_validator", os.path.join(os.path.dirname(__file__), "octave-validator.py")
)
octave_validator = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(octave_validator)

OctaveValidator = octave_validator.OctaveValidator
validate_octave_document = octave_validator.validate_octave_document
validate_octave_file = octave_validator.validate_octave_file


def make_doc(name: str, content: str, meta_type: str = "TEST") -> str:
    return f"""==={name}===
META:
  TYPE::{meta_type}
  VERSION::"1.0"

{content}
===END==="""


class TestProfilesAndMarkers(unittest.TestCase):
    def test_missing_markers_is_error(self):
        validator = OctaveValidator(profile="protocol")
        ok, msgs = validator.validate_octave_document("KEY::value")
        self.assertFalse(ok)
        self.assertTrue(any("header" in m.lower() or "marker" in m.lower() for m in msgs))

    def test_protocol_forbids_yaml_frontmatter(self):
        doc = """---
name: test
---

===TEST===
META:
  TYPE::TEST
  VERSION::"1.0"

KEY::value
===END==="""
        validator = OctaveValidator(profile="protocol")
        ok, _ = validator.validate_octave_document(doc)
        self.assertFalse(ok)

    def test_hestai_agent_missing_frontmatter_is_warning_by_default(self):
        doc = make_doc("AGENT", "ROLE::test", meta_type="AGENT_DEFINITION")
        validator = OctaveValidator(profile="hestai-agent")
        ok, msgs = validator.validate_octave_document(doc)
        self.assertTrue(ok)
        self.assertTrue(any("frontmatter" in m.lower() for m in msgs))

    def test_hestai_agent_missing_frontmatter_can_be_required(self):
        doc = make_doc("AGENT", "ROLE::test", meta_type="AGENT_DEFINITION")
        validator = OctaveValidator(profile="hestai-agent")
        ok, msgs = validator.validate_octave_document(doc, require_frontmatter=True)
        self.assertFalse(ok)
        self.assertTrue(any("required" in m.lower() for m in msgs))

    def test_hestai_agent_meta_type_enforced(self):
        doc = """---
name: test-agent
---

===AGENT===
META:
  TYPE::SKILL
  VERSION::"1.0"

ROLE::test
===END==="""
        validator = OctaveValidator(profile="hestai-agent")
        ok, msgs = validator.validate_octave_document(doc)
        self.assertFalse(ok)
        self.assertTrue(any("META.TYPE" in m for m in msgs))


class TestScanMode(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

        (Path(self.temp_dir) / "valid.oct.md").write_text(make_doc("VALID", "KEY::value"))
        (Path(self.temp_dir) / "invalid.oct.md").write_text("KEY::value")
        (Path(self.temp_dir) / "readme.md").write_text("# Not an OCTAVE file")

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_scan_directory_finds_octave_files(self):
        results = octave_validator.scan_directory(self.temp_dir)
        self.assertEqual(len(results), 2)


class TestWrapperFunctions(unittest.TestCase):
    def test_validate_octave_document_returns_expected_status_prefix(self):
        doc = make_doc("TEST", "KEY::value")
        out = validate_octave_document(doc)
        self.assertTrue(out.startswith("OCTAVE_VALID"))

    def test_validate_octave_file_returns_expected_status_prefix(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".oct.md", delete=False) as f:
            f.write(make_doc("TEST", "KEY::value"))
            temp_path = f.name

        try:
            out = validate_octave_file(temp_path)
            self.assertTrue(out.startswith("OCTAVE_VALID"))
        finally:
            os.unlink(temp_path)


if __name__ == "__main__":
    unittest.main()
