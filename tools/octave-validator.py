#!/usr/bin/env python3
"""OCTAVE Validator (repo tool)

This is a thin wrapper around the OCTAVE-MCP *core* parser/validator so repo tooling
and runtime validation do not drift.

What it validates:
- Envelope markers (===NAME=== ... ===END===) are required
- YAML frontmatter handling per profile
- OCTAVE parsing via octave_mcp.core.parser.parse_with_warnings
  - NOTE: non-protocol profiles may apply a small lenient preprocess for HestAI dialect features (e.g., quoting NAME{tag})
- Basic META sanity (TYPE + VERSION required)
- Optional schema validation when --schema is provided (builtin dict and/or SchemaDefinition)

Profiles:
- protocol: YAML frontmatter forbidden
- hestai-agent: YAML frontmatter recommended by default (warning if missing; use --require-frontmatter to fail); META.TYPE must be AGENT_DEFINITION
- hestai-skill: YAML frontmatter recommended by default (warning if missing; use --require-frontmatter to fail); META.TYPE must be SKILL
- hestai-pattern: YAML frontmatter forbidden; META.TYPE must be PATTERN

Usage:
  python tools/octave-validator.py path/to/doc.oct.md
  python tools/octave-validator.py --path .hestai-sys/library/agents --profile hestai-agent
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def _ensure_src_on_path() -> None:
    """Allow running this tool without an installed package (dev convenience)."""
    try:
        import octave_mcp  # noqa: F401

        return
    except Exception:
        pass

    repo_root = Path(__file__).resolve().parent.parent
    src_dir = repo_root / "src"
    if src_dir.exists():
        sys.path.insert(0, str(src_dir))


_ensure_src_on_path()

from octave_mcp.core.parser import ParserError, parse_with_warnings  # noqa: E402
from octave_mcp.core.validator import Validator  # noqa: E402
from octave_mcp.schemas.loader import get_builtin_schema, load_schema_by_name  # noqa: E402

_HEADER_RE = re.compile(r"^===([A-Z0-9_]+)===$")
_FOOTER_RE = re.compile(r"^===END===$")

# HestAI dialect compatibility:
# Some HestAI library docs use brace-annotations like HEPHAESTUS{implementation_excellence}.
# Core OCTAVE syntax does not currently treat '{' / '}' as valid tokens.
# For non-protocol profiles, we attempt a lenient preprocess to quote these as strings.
_BRACE_ANNOTATION_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*\{[A-Za-z0-9_]+\})")


def _quote_brace_annotations_for_parsing(document: str) -> tuple[str, bool]:
    repaired, n = _BRACE_ANNOTATION_RE.subn(r'"\1"', document)
    return repaired, n > 0


def _has_yaml_frontmatter(document: str) -> bool:
    lines = document.split("\n")
    if not lines:
        return False
    if lines[0].strip() != "---":
        return False
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return True
    return False


def _strip_yaml_frontmatter_for_text_checks(document: str) -> str:
    """Remove YAML frontmatter without preserving line numbers (for marker checks only)."""
    lines = document.split("\n")
    if not lines or lines[0].strip() != "---":
        return document
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[i + 1 :])
    return document


def _first_last_nonempty_lines(document: str) -> tuple[str | None, str | None]:
    lines = [ln for ln in document.splitlines() if ln.strip()]
    if not lines:
        return None, None
    return lines[0].strip(), lines[-1].strip()


def _format_parse_warning(w: dict[str, Any]) -> str:
    t = w.get("type", "warning")
    st = w.get("subtype")
    line = w.get("line")
    col = w.get("column")
    msg = w.get("message") or w.get("reason") or json.dumps(w, ensure_ascii=False)
    where = ""
    if line is not None and col is not None:
        where = f" (line {line}, col {col})"
    if st:
        return f"{t}:{st}{where}: {msg}"
    return f"{t}{where}: {msg}"


class OctaveValidator:
    def __init__(self, version: str = "6.0.0", profile: str = "protocol", require_frontmatter: bool = False):
        self.version = version
        self.profile = profile
        self.require_frontmatter = require_frontmatter
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def validate_octave_document(
        self,
        document: str,
        schema: str | None = None,
        require_frontmatter: bool | None = None,
    ) -> tuple[bool, list[str]]:
        self.errors = []
        self.warnings = []

        require_frontmatter_effective = self.require_frontmatter if require_frontmatter is None else require_frontmatter

        # JSON input is supported only as a syntactic check
        if document.strip().startswith("{"):
            return self._validate_json(document)

        return self._validate_octave_text(document, schema=schema, require_frontmatter=require_frontmatter_effective)

    def _validate_json(self, document: str) -> tuple[bool, list[str]]:
        try:
            json.loads(document)
            self.warnings.append("JSON validation is syntactic only (no schema enforcement in this tool).")
            return True, self.warnings
        except json.JSONDecodeError as e:
            self.errors.append(f"Invalid JSON: {e}")
            return False, self.errors

    def _validate_octave_text(
        self, document: str, schema: str | None, require_frontmatter: bool
    ) -> tuple[bool, list[str]]:
        if not document.strip():
            self.errors.append("Document is empty")
            return False, self.errors

        has_frontmatter = _has_yaml_frontmatter(document)

        # Profile policy: YAML frontmatter
        if self.profile == "protocol" and has_frontmatter:
            self.errors.append("YAML frontmatter is forbidden in protocol profile")
            return False, self.errors

        if self.profile in {"hestai-agent", "hestai-skill"} and not has_frontmatter:
            msg = "YAML frontmatter is recommended for this profile (use --require-frontmatter to enforce)"
            if require_frontmatter:
                self.errors.append("YAML frontmatter is required for this profile")
                return False, self.errors
            self.warnings.append(msg)

        if self.profile == "hestai-pattern" and has_frontmatter:
            self.errors.append("YAML frontmatter is forbidden in hestai-pattern profile")
            return False, self.errors

        # Envelope markers are mandatory (after frontmatter, if present)
        marker_view = _strip_yaml_frontmatter_for_text_checks(document)
        first, last = _first_last_nonempty_lines(marker_view)
        if first is None or last is None:
            self.errors.append("Document has no content after frontmatter")
            return False, self.errors

        if not _HEADER_RE.match(first):
            self.errors.append("First non-whitespace line must be a header marker: ===NAME===")
        if not _FOOTER_RE.match(last):
            self.errors.append("Last non-whitespace line must be the footer marker: ===END===")

        if self.errors:
            return False, self.errors

        # Parse (this also strips frontmatter with line-number preservation)
        try:
            doc, parse_warnings = parse_with_warnings(document)
            for w in parse_warnings:
                self.warnings.append(_format_parse_warning(w))
        except ParserError as e:
            self.errors.append(str(e))
            return False, self.errors
        except Exception as e:
            # Non-protocol profiles may include dialect features not yet supported by the core lexer.
            # Attempt a single, explicit repair pass for brace-annotations.
            msg = str(e)
            if self.profile != "protocol" and "Unexpected character: '{'" in msg:
                repaired, did_repair = _quote_brace_annotations_for_parsing(document)
                if did_repair:
                    try:
                        doc, parse_warnings = parse_with_warnings(repaired)
                        self.warnings.append(
                            "lenient_preprocess: quoted brace-annotations like NAME{tag} for parsing (non-canonical OCTAVE)"
                        )
                        for w in parse_warnings:
                            self.warnings.append(_format_parse_warning(w))
                    except Exception as e2:
                        self.errors.append(f"Unexpected parse failure: {type(e2).__name__}: {e2}")
                        return False, self.errors
                else:
                    self.errors.append(f"Unexpected parse failure: {type(e).__name__}: {e}")
                    return False, self.errors
            else:
                self.errors.append(f"Unexpected parse failure: {type(e).__name__}: {e}")
                return False, self.errors

        # Minimal META sanity (independent of schema availability)
        meta_type = (doc.meta or {}).get("TYPE")
        meta_version = (doc.meta or {}).get("VERSION")
        if not meta_type:
            self.errors.append("META.TYPE is required")
        if not meta_version:
            self.errors.append("META.VERSION is required")

        # Profile expectations for META.TYPE
        expected_type = {
            "hestai-agent": "AGENT_DEFINITION",
            "hestai-skill": "SKILL",
            "hestai-pattern": "PATTERN",
        }.get(self.profile)
        if expected_type is not None and meta_type and str(meta_type) != expected_type:
            self.errors.append(f"META.TYPE must be {expected_type} for profile {self.profile} (got {meta_type})")

        if self.errors:
            return False, self.errors

        # Optional schema validation (mirrors octave_validate tool logic)
        if schema:
            schema_def = get_builtin_schema(schema)

            schema_definition = None
            section_schemas = None
            try:
                schema_definition = load_schema_by_name(schema)
                if schema_definition is not None and schema_definition.fields:
                    section_schemas = {schema_definition.name: schema_definition}
            except Exception:
                schema_definition = None

            has_schema = schema_def is not None or (schema_definition is not None and schema_definition.fields)
            if not has_schema:
                self.warnings.append(f"Schema '{schema}' not found; document is parse-valid but UNVALIDATED")
            else:
                v = Validator(schema=schema_def)
                errors = v.validate(doc, strict=False, section_schemas=section_schemas)
                if errors:
                    for err in errors:
                        self.errors.append(f"{err.code}: {err.message} ({err.field_path})")
                    return False, self.errors + self.warnings

        return True, self.warnings

    def format_results(self, is_valid: bool, messages: list[str]) -> str:
        if is_valid and not self.warnings:
            return "OCTAVE_VALID"
        if is_valid:
            return "OCTAVE_VALID_WITH_WARNINGS\n" + "\n".join([f"- {w}" for w in self.warnings])
        return "OCTAVE_INVALID\n" + "\n".join([f"- {e}" for e in self.errors])


def validate_octave_document(
    octave_text: str,
    version: str = "6.0.0",
    profile: str = "protocol",
    schema: str | None = None,
    require_frontmatter: bool = False,
) -> str:
    validator = OctaveValidator(version=version, profile=profile, require_frontmatter=require_frontmatter)
    is_valid, messages = validator.validate_octave_document(octave_text, schema=schema)
    return validator.format_results(is_valid, messages)


def validate_octave_file(
    file_path: str,
    version: str = "6.0.0",
    profile: str = "protocol",
    schema: str | None = None,
    require_frontmatter: bool = False,
) -> str:
    try:
        with open(file_path, encoding="utf-8") as f:
            octave_text = f.read()
        validator = OctaveValidator(version=version, profile=profile, require_frontmatter=require_frontmatter)
        is_valid, messages = validator.validate_octave_document(octave_text, schema=schema)
        return validator.format_results(is_valid, messages)
    except Exception as e:
        return f"OCTAVE_INVALID\n- File error: {e}"


def scan_directory(
    directory: str,
    profile: str = "protocol",
    version: str = "6.0.0",
    schema: str | None = None,
    require_frontmatter: bool = False,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    oct_files = list(Path(directory).rglob("*.oct.md"))

    for file_path in oct_files:
        validator = OctaveValidator(version=version, profile=profile, require_frontmatter=require_frontmatter)
        try:
            content = file_path.read_text(encoding="utf-8")
            is_valid, messages = validator.validate_octave_document(content, schema=schema)
            results.append({"file": str(file_path), "valid": is_valid, "messages": messages})
        except Exception as e:
            results.append({"file": str(file_path), "valid": False, "messages": [f"File error: {e}"]})

    return results


def format_scan_results(results: list[dict[str, Any]]) -> str:
    passed = sum(1 for r in results if r["valid"])
    failed = sum(1 for r in results if not r["valid"])
    total = len(results)

    out: list[str] = []
    out.append(f"\n{'=' * 60}")
    out.append("OCTAVE Validation Summary")
    out.append(f"{'=' * 60}")
    out.append(f"Total files: {total}")
    out.append(f"✅ {passed} passed")
    out.append(f"❌ {failed} failed")
    out.append(f"{'=' * 60}\n")

    for result in results:
        status = "✅" if result["valid"] else "❌"
        out.append(f"{status} {result['file']}")
        for msg in (result.get("messages") or [])[:3]:
            out.append(f"    {msg}")
        if result.get("messages") and len(result["messages"]) > 3:
            out.append(f"    ... and {len(result['messages']) - 3} more")
        out.append("")

    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate OCTAVE documents using OCTAVE-MCP core parser/validator")
    parser.add_argument("file", nargs="?", help="Path to OCTAVE document file (optional if using --path)")
    parser.add_argument("--version", "-v", default="6.0.0", help="OCTAVE version label (informational)")
    parser.add_argument(
        "--profile",
        "-p",
        choices=["protocol", "hestai-agent", "hestai-skill", "hestai-pattern"],
        default="protocol",
        help="Validation profile",
    )
    parser.add_argument("--schema", help="Schema name to validate against (optional)")
    parser.add_argument(
        "--require-frontmatter",
        action="store_true",
        help="Fail validation for hestai-agent/hestai-skill documents missing YAML frontmatter",
    )
    parser.add_argument("--path", "-d", help="Scan directory for *.oct.md files")

    args = parser.parse_args()

    if args.path:
        results = scan_directory(
            args.path,
            profile=args.profile,
            version=args.version,
            schema=args.schema,
            require_frontmatter=args.require_frontmatter,
        )
        print(format_scan_results(results))
        if any(not r["valid"] for r in results):
            raise SystemExit(1)
        return

    if args.file:
        out = validate_octave_file(
            args.file,
            version=args.version,
            profile=args.profile,
            schema=args.schema,
            require_frontmatter=args.require_frontmatter,
        )
        print(out)
        if out.startswith("OCTAVE_INVALID"):
            raise SystemExit(1)
        return

    parser.error("Either provide a file argument or use --path for directory scanning")


if __name__ == "__main__":
    main()
