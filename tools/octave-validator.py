#!/usr/bin/env python3
"""
OCTAVE Validator - v5.1.0 Implementation

This validator checks OCTAVE v5.1.0 formatted documents for envelope (markers + META) and formatting compliance.

Usage:
    python octave_validator.py <file_path>
    # or
    import octave_validator
    result = octave_validator.validate_octave_document(octave_text)
"""

import argparse
import json
import re
from pathlib import Path


class OctaveValidator:
    """Validator for OCTAVE v5.1.0 structured documents."""

    HEADER_RE = re.compile(r"^===([A-Z0-9_]+)===$")
    FOOTER_RE = re.compile(r"^===END===$")
    PREFACE_RE = re.compile(r"^\s*(//.*)?$")
    QUOTED_RE = re.compile(r'"(?:\\.|[^"\\])*"')

    @classmethod
    def _strip_quoted_strings(cls, line: str) -> str:
        # Replace quoted content so punctuation/operators inside quotes don't affect structural checks.
        return cls.QUOTED_RE.sub('""', line)

    def __init__(self, version: str = "5.1.0", profile: str = "protocol", unknown_policy: str = "ignore"):
        self.version = version
        self.profile = profile  # protocol, hestai-agent, hestai-skill
        self.unknown_policy = unknown_policy  # ignore | warn | strict
        self.errors = []
        self.warnings = []

    def validate_octave_document(self, document: str) -> tuple[bool, list[str]]:
        """Validate an OCTAVE document against the specification."""
        self.errors = []
        self.warnings = []

        if document.strip().startswith("{"):
            return self._validate_json_octave(document)
        else:
            return self._validate_native_octave(document)

    def _strip_yaml_frontmatter(self, document: str) -> str:
        """Remove YAML frontmatter from document (for HestAI profiles)."""
        lines = document.split("\n")
        if lines and lines[0].strip() == "---":
            # Find closing ---
            for i in range(1, len(lines)):
                if lines[i].strip() == "---":
                    # Return document without frontmatter
                    return "\n".join(lines[i + 1 :])
        return document

    def _validate_json_octave(self, document: str) -> tuple[bool, list[str]]:
        """Placeholder for JSON validation. Full validation requires a JSON Schema validator."""
        try:
            json.loads(document)
        except json.JSONDecodeError as e:
            self.errors.append(f"Invalid JSON format: {e}")
            return False, self.errors

        self.warnings.append(
            "JSON validation is a stub. For full validation, use a JSON Schema validator against json/JSON_SCHEMA.md."
        )
        return True, self.warnings

    def _validate_native_octave(self, document: str) -> tuple[bool, list[str]]:
        """Validate a native-formatted OCTAVE document."""
        # Strip YAML frontmatter for HestAI profiles
        if self.profile in ["hestai-agent", "hestai-skill"]:
            document = self._strip_yaml_frontmatter(document)

        lines = document.splitlines()
        non_ws = [i for i, line in enumerate(lines) if line.strip()]
        if not non_ws:
            self.errors.append("Document is empty.")
            return False, self.errors

        in_list = False
        list_depth = 0  # Track nested list depth

        first = non_ws[0]
        last = non_ws[-1]

        if not self.HEADER_RE.match(lines[first].strip()):
            self.errors.append("First non-whitespace line must be a header marker: ===NAME===")
        if not self.FOOTER_RE.match(lines[last].strip()):
            self.errors.append("Last non-whitespace line must be the footer marker: ===END===")

        self._validate_and_extract_meta(lines, first, last)

        for i, line in enumerate(lines):
            line_num = i + 1
            stripped_line = line.strip()
            scan_line = self._strip_quoted_strings(stripped_line)

            if not stripped_line or stripped_line.startswith("//"):
                continue

            # Track list context (opening/closing brackets)
            list_depth += stripped_line.count("[") - stripped_line.count("]")
            in_list = list_depth > 0

            # Check for incorrect assignment operators (skip marker lines)
            if not stripped_line.startswith("===") and (
                " = " in scan_line
                or (": " in scan_line and "::" not in scan_line)
                or (" :" in scan_line and "::" not in scan_line)
            ):
                self.warnings.append(
                    f"Line {line_num}: Non-canonical assignment style. Prefer 'KEY::VALUE' for assignments."
                )

            # Validate core operator usage (v5.1.0 guidance)

            # Check for progression operator -> (only allowed in lists)
            if "->" in scan_line and not re.search(r"\[.*->.*\]", scan_line) and not in_list:
                msg = f"Line {line_num}: Progression operator '->' can only be used inside lists (e.g., [A->B->C])."
                if self.profile in ["hestai-agent", "hestai-skill"]:
                    self.warnings.append(msg)
                else:
                    self.errors.append(msg)

            # Check for constraint operator & (only allowed inside brackets)
            if "&" in scan_line and not in_list:
                self.errors.append(
                    f"Line {line_num}: Constraint operator '&' can only be used inside brackets (e.g., [\"value\"&REQ&REGEX->§TARGET])."
                )

            # Check for tension operator ⇌ or vs (cannot be chained, binary only)
            # v5.1.0 spec: tension is ⇌ (Unicode) with ASCII alias 'vs' (word boundaries required)
            tension_count = scan_line.count("⇌") + len(re.findall(r"\bvs\b", scan_line))
            if tension_count > 1:
                self.errors.append(f"Line {line_num}: Tension operator '⇌'/'vs' cannot be chained (binary only).")

            # Normalize/validate target selector: allow '#TARGET' form and canonical '§TARGET'
            if "-> #".lower() in scan_line.lower() or re.search(r"->\s*#", scan_line):
                # only warn; canonicalization occurs in ingest, validator just flags non-canonical
                self.warnings.append(
                    f"Line {line_num}: Use canonical target selector '→§TARGET' or '->§TARGET' (authoring may use '-> #TARGET')."
                )

            # Check for incorrect indentation (must be multiple of 2)
            indentation = len(line) - len(line.lstrip(" "))
            if indentation % 2 != 0:
                self.warnings.append(f"Line {line_num}: Indentation is not a multiple of 2 spaces.")

            # Check for tabs
            if "\t" in line:
                self.errors.append(f"Line {line_num}: Tab characters are not allowed. Use spaces for indentation.")

            # Basic key format validation (ignore :: inside quoted strings)
            if "::" in scan_line:
                key = scan_line.split("::")[0]
                if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
                    self.warnings.append(
                        f"Line {line_num}: Key '{key}' may not follow best practices (alphanumeric and underscores, starting with a letter or underscore)."
                    )

        # HestAI-skill specific validation
        if self.profile == "hestai-skill":
            self._validate_hestai_skill_structure(document)

        return len(self.errors) == 0, self.errors + self.warnings

    def _validate_and_extract_meta(self, lines: list[str], header_index: int, footer_index: int) -> int:
        """
        Validate META placement and required keys.
        Returns index of the META line if found, otherwise -1.
        """
        i = header_index + 1
        while i < footer_index and self.PREFACE_RE.match(lines[i]):
            i += 1

        if i >= footer_index or lines[i].strip() != "META:":
            self.errors.append(
                "Missing META section. Expected META: immediately after optional preface comments/blank lines."
            )
            return -1

        meta_line_index = i
        i += 1

        meta = {}
        while i < footer_index:
            line = lines[i]
            if not line.strip() or line.lstrip().startswith("//"):
                i += 1
                continue
            if not line.startswith("  "):
                break
            m = re.match(r"^\s+([A-Za-z_][A-Za-z0-9_]*)::(.*)$", line)
            if m:
                key = m.group(1)
                raw = m.group(2).strip()
                value = raw.strip('"') if raw.startswith('"') and raw.endswith('"') else raw
                meta[key] = value
            i += 1

        meta_type = meta.get("TYPE")
        if not meta_type:
            self.errors.append("META.TYPE is required.")
            return meta_line_index

        if meta_type == "SESSION_CONTEXT":
            for k in ("SESSION_ID", "ROLE", "DATE"):
                if k not in meta:
                    self.errors.append(f"META.{k} is required for TYPE::SESSION_CONTEXT.")
        elif meta_type == "PROTOCOL_DEFINITION":
            for k in ("VERSION", "STATUS"):
                if k not in meta:
                    self.errors.append(f"META.{k} is required for TYPE::PROTOCOL_DEFINITION.")
        else:
            self.warnings.append(f"Unknown META.TYPE '{meta_type}'. No schema validation applied.")

        # Unknown fields policy (META-only initial enforcement)
        allowed_meta = {
            "TYPE",
            "VERSION",
            "STATUS",
            "DATE",
            "NAME",
            "PURPOSE",
            "OCTAVE_VERSION",
            "FIDELITY_TARGET",
            "COMPRESSION_TARGET",
            "PRINCIPLE",
            "MOTTO",
            "EVOLUTION",
            "FORMULA",
            "BREAKTHROUGH",
            "CHANGES",
            "OPERATORS",
            "ASCII_ALIASES",
            "COMPRESSION",
            "OBJECTIVE",
            "AUTHOR",
            "LICENSE",
            "SCHEMA",
            "ROLE",
        }
        unknown_keys = [k for k in meta.keys() if k not in allowed_meta]
        if unknown_keys:
            if self.unknown_policy == "strict" and self.profile == "protocol":
                self.errors.append(f"E007: Unknown META field(s) {unknown_keys} not allowed in STRICT mode.")
            elif self.unknown_policy == "warn":
                self.warnings.append(f"Unknown META field(s) {unknown_keys} encountered.")

        return meta_line_index

    def _validate_hestai_skill_structure(self, document: str) -> None:
        """Validate HestAI-skill specific requirements."""
        has_section_order = "SECTION_ORDER::" in document
        if not has_section_order:
            self.warnings.append("HestAI-skill documents should include SECTION_ORDER for navigation.")

        # Check for @N section anchors
        section_anchors = re.findall(r"@(\d+)::", document)
        if section_anchors and has_section_order:
            # Verify anchors are sequential
            anchor_nums = sorted([int(n) for n in section_anchors])
            expected = list(range(1, len(anchor_nums) + 1))
            if anchor_nums != expected:
                self.warnings.append(f"Section anchors should be sequential starting from @1. Found: {anchor_nums}")

    def format_results(self, is_valid: bool, messages: list[str]) -> str:
        """Format validation results into a readable string."""
        if is_valid and not self.warnings:
            return "✅ OCTAVE document appears to be valid."
        elif is_valid:
            warning_count = len(self.warnings)
            return (
                f"✅ OCTAVE document is valid but has {warning_count} suggestion{'s' if warning_count > 1 else ''}:\n"
                + "\n".join([f"  - {w}" for w in self.warnings])
            )
        else:
            error_count = len(self.errors)
            return (
                f"❌ OCTAVE document is invalid with {error_count} error{'s' if error_count > 1 else ''}:\n"
                + "\n".join([f"  - {e}" for e in self.errors])
            )


def validate_octave_document(octave_text: str, version: str = "5.1.0", profile: str = "protocol") -> str:
    """Validates an OCTAVE document for structure and format."""
    validator = OctaveValidator(version, profile)
    is_valid, messages = validator.validate_octave_document(octave_text)
    return validator.format_results(is_valid, messages)


def validate_octave_file(file_path: str, version: str = "5.1.0", profile: str = "protocol") -> str:
    """Validates an OCTAVE document file."""
    try:
        with open(file_path, encoding="utf-8") as f:
            octave_text = f.read()
        validator = OctaveValidator(version, profile)
        is_valid, messages = validator.validate_octave_document(octave_text)
        return validator.format_results(is_valid, messages)
    except Exception as e:
        return f"❌ File error (invalid): {str(e)}"


def scan_directory(directory: str, profile: str = "protocol", version: str = "5.1.0") -> list[dict]:
    """Scan directory for *.oct.md files and validate each."""
    results = []
    oct_files = list(Path(directory).rglob("*.oct.md"))

    for file_path in oct_files:
        validator = OctaveValidator(version, profile)
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
            is_valid, messages = validator.validate_octave_document(content)
            results.append({"file": str(file_path), "valid": is_valid, "messages": messages})
        except Exception as e:
            results.append({"file": str(file_path), "valid": False, "messages": [f"Error reading file: {str(e)}"]})

    return results


def format_scan_results(results: list[dict]) -> str:
    """Format scan results into readable summary."""
    passed = sum(1 for r in results if r["valid"])
    failed = sum(1 for r in results if not r["valid"])
    total = len(results)

    output = []
    output.append(f"\n{'='*60}")
    output.append("OCTAVE Validation Summary")
    output.append(f"{'='*60}")
    output.append(f"Total files: {total}")
    output.append(f"✅ {passed} passed")
    output.append(f"❌ {failed} failed")
    output.append(f"{'='*60}\n")

    # Show per-file results
    for result in results:
        status = "✅" if result["valid"] else "❌"
        output.append(f"{status} {result['file']}")
        if result["messages"]:
            for msg in result["messages"][:3]:  # Limit to first 3 messages
                output.append(f"    {msg}")
            if len(result["messages"]) > 3:
                output.append(f"    ... and {len(result['messages']) - 3} more")
        output.append("")

    return "\n".join(output)


def main() -> None:
    """Command-line interface for OCTAVE validator."""
    parser = argparse.ArgumentParser(description="Validate OCTAVE documents against the v5.1.0 specification.")
    parser.add_argument("file", nargs="?", help="Path to OCTAVE document file (optional if using --path)")
    parser.add_argument("--version", "-v", default="5.1.0", help="OCTAVE version to validate against (default: 5.1.0)")
    parser.add_argument(
        "--profile",
        "-p",
        choices=["protocol", "hestai-agent", "hestai-skill"],
        default="protocol",
        help="Validation profile (default: protocol)",
    )
    parser.add_argument("--path", "-d", help="Scan directory for *.oct.md files")

    args = parser.parse_args()

    if args.path:
        # Scan mode
        results = scan_directory(args.path, profile=args.profile, version=args.version)
        output = format_scan_results(results)
        print(output)
        # Exit with error code if any failed
        if any(not r["valid"] for r in results):
            exit(1)
    elif args.file:
        # Single file mode
        result = validate_octave_file(args.file, version=args.version, profile=args.profile)
        print(result)
        # Exit with error code if validation failed
        if "invalid" in result.lower():
            exit(1)
    else:
        parser.error("Either provide a file argument or use --path for directory scanning")


if __name__ == "__main__":
    main()
