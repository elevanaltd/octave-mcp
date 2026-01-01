#!/usr/bin/env python3
"""
JSON to OCTAVE converter - Minimal implementation
Enables round-trip conversion for integration needs
"""

import json
import sys


def json_to_octave(data, indent=0):
    """Convert JSON to OCTAVE format"""
    lines = []
    spacing = "  " * indent

    # Handle the body of the octave document
    if indent == 0 and "octave" in data and "body" in data["octave"]:
        body = data["octave"]["body"]
    else:
        body = data

    for key, value in body.items():
        # Skip metadata keys
        if key.endswith("_blank_after"):
            continue

        if isinstance(value, dict) and not any(op in value for op in ["progression", "tension", "synthesis"]):
            lines.append(f"{spacing}{key}:")
            lines.append(json_to_octave(value, indent + 1))
        else:
            value_str = format_value(value)
            lines.append(f"{spacing}{key}::{value_str}")

        # Only add blank line if it existed in original
        if f"{key}_blank_after" in body and body[f"{key}_blank_after"]:
            lines.append("")

    return "\n".join(lines)


def format_value(value):
    """Format individual values"""
    if isinstance(value, str):
        return value
    elif isinstance(value, bool):
        return "true" if value else "false"
    elif value is None:
        return "null"
    elif isinstance(value, list):
        return "[" + ", ".join(str(v) for v in value) + "]"
    elif isinstance(value, dict):
        if "progression" in value:
            return "[" + "->".join(str(v) for v in value["progression"]) + "]"
        if "tension" in value:
            # v5.1.0: Use canonical Unicode ⇌ for tension operator
            return f"{value['tension'][0]}⇌{value['tension'][1]}"
        if "synthesis" in value:
            return "+".join(str(v) for v in value["synthesis"])

    return str(value)


if __name__ == "__main__":
    try:
        if len(sys.argv) > 1:
            with open(sys.argv[1]) as f:
                data = json.load(f)
        else:
            data = json.load(sys.stdin)

        title = data.get("octave", {}).get("title", "OCTAVE_DOCUMENT")

        print(f"==={title}===")
        print(json_to_octave(data))
        print("===END===")

    except FileNotFoundError:
        print(f"Error: File not found at {sys.argv[1]}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print("Error: Invalid JSON input", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
        sys.exit(1)
