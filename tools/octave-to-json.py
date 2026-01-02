#!/usr/bin/env python3
"""
OCTAVE to JSON converter - Minimal implementation
Preserves semantic structure while enabling integration
"""

import json
import re
import sys


def octave_to_json(content):
    """Convert OCTAVE format to JSON for integration purposes"""
    lines = content.strip().split("\n")
    title = "OCTAVE_DOCUMENT"
    if lines and lines[0].startswith("==="):
        title = lines[0].strip("=").strip()

    result = {"octave": {"title": title, "version": "2.0", "body": {}}}
    current = result["octave"]["body"]
    stack = [current]
    indent_stack = [0]
    last_key = None

    for line in lines:
        if line.startswith("===") or line.strip().startswith("//"):
            continue

        # Track blank lines after content
        if not line.strip():
            if last_key and last_key in stack[-1]:
                stack[-1][last_key + "_blank_after"] = True
            continue

        indent = len(line) - len(line.lstrip())
        content = line.strip()

        while indent_stack and indent < indent_stack[-1]:
            stack.pop()
            indent_stack.pop()

        if "::" in content and not content.startswith('"'):
            key, value_str = content.split("::", 1)
            last_key = key

            # Preserve original string quotes in JSON value
            if value_str.startswith('"') and value_str.endswith('"'):
                parsed_value = value_str
            elif value_str.startswith("[") and value_str.endswith("]"):
                list_content = value_str[1:-1]
                if "->" in list_content:
                    parsed_value = {"progression": [v.strip() for v in list_content.split("->")]}
                else:
                    parsed_value = [v.strip() for v in list_content.split(",")]
            elif value_str in ["true", "false"]:
                parsed_value = value_str == "true"
            elif value_str == "null":
                parsed_value = None
            elif re.match(r"^-?\d+(\.\d+)?([eE][+-]?\d+)?$", value_str):
                parsed_value = float(value_str) if "." in value_str or "e" in value_str.lower() else int(value_str)
            # v5.1.0: Detect tension operator ⇌ or ' vs ' (word-bounded)
            elif "⇌" in value_str or re.search(r"\s+vs\s+", value_str):
                if "⇌" in value_str:
                    parts = value_str.split("⇌")
                else:
                    parts = re.split(r"\s+vs\s+", value_str)
                parsed_value = {"tension": [parts[0].strip(), parts[1].strip()]}
            elif "~" in value_str and not value_str.startswith('"'):
                parsed_value = {"concatenation": [v.strip() for v in value_str.split("~")]}
            elif "+" in value_str and not value_str.startswith('"'):
                parsed_value = {"synthesis": [v.strip() for v in value_str.split("+")]}
            else:
                parsed_value = value_str

            stack[-1][key] = parsed_value

        elif content.endswith(":"):
            key = content[:-1]
            last_key = key
            new_dict = {}
            stack[-1][key] = new_dict
            stack.append(new_dict)
            # This is a new indentation level
            if indent >= indent_stack[-1]:
                indent_stack.append(indent + 2)  # Assume 2-space indents
            else:  # handle dedent case
                indent_stack.append(indent)

    return result


if __name__ == "__main__":
    try:
        content = sys.stdin.read() if not sys.argv[1:] else open(sys.argv[1]).read()
        print(json.dumps(octave_to_json(content), indent=2))
    except FileNotFoundError:
        print(f"Error: File not found at {sys.argv[1]}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
        sys.exit(1)
