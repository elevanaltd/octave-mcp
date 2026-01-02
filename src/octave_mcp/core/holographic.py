"""OCTAVE holographic pattern parsing (Issue #93).

Implements parsing support for holographic patterns as defined in octave-5-llm-schema.oct.md.

Holographic Pattern Syntax:
    KEY::["example"∧CONSTRAINT→§TARGET]
         ^^^^^^^^ ^^^^^^^^^^ ^^^^^^^^
         example  constraints target

The holographic pattern is a schema definition element that specifies:
- EXAMPLE: A concrete value demonstrating the expected format
- CONSTRAINT: A constraint chain (∧ separated) for validation
- TARGET: An extraction destination (§ prefixed)

This module provides:
- HolographicPattern: Dataclass representing a parsed pattern
- parse_holographic_pattern(): Function to parse pattern strings
- HolographicPatternError: Exception for parsing errors
"""

from dataclasses import dataclass
from typing import Any

from octave_mcp.core.constraints import ConstraintChain


class HolographicPatternError(Exception):
    """Error during holographic pattern parsing."""

    def __init__(self, message: str, pattern: str | None = None):
        self.message = message
        self.pattern = pattern
        super().__init__(f"Holographic pattern error: {message}" + (f" in '{pattern}'" if pattern else ""))


@dataclass
class HolographicPattern:
    """Parsed holographic pattern: ["example"∧CONSTRAINT→§TARGET].

    Represents a schema field definition extracted from OCTAVE holographic syntax.

    Attributes:
        example: The example value demonstrating expected format.
                 Can be str, int, float, bool, list, or None.
        constraints: Parsed ConstraintChain for validation, or None if no constraints.
        target: Target destination (without § prefix), or None if no target.
    """

    example: str | int | float | bool | list | None
    constraints: ConstraintChain | None
    target: str | None

    def to_string(self) -> str:
        """Convert pattern back to string representation.

        Returns:
            String representation in holographic pattern format.
        """
        # Format example based on type
        if isinstance(self.example, str):
            example_str = f'"{self.example}"'
        elif isinstance(self.example, list):
            # Format list elements
            items = []
            for item in self.example:
                if isinstance(item, str):
                    items.append(f'"{item}"')
                else:
                    items.append(str(item))
            example_str = f"[{','.join(items)}]"
        elif isinstance(self.example, bool):
            example_str = "true" if self.example else "false"
        elif self.example is None:
            example_str = "null"
        else:
            example_str = str(self.example)

        # Build pattern string
        parts = [example_str]

        if self.constraints:
            parts.append("∧")
            parts.append(self.constraints.to_string())

        if self.target:
            parts.append("→§")
            parts.append(self.target)

        return f"[{''.join(parts)}]"


def _parse_example_value(value_str: str) -> Any:
    """Parse example value from pattern string.

    Handles:
    - Quoted strings: "foo" -> "foo"
    - Numbers: 42, 3.14 -> int/float
    - Booleans: true/false -> True/False
    - Null: null -> None
    - Lists: ["item1", "item2"] -> list

    Args:
        value_str: String representation of the value

    Returns:
        Parsed Python value
    """
    value_str = value_str.strip()

    # Handle quoted strings
    if value_str.startswith('"') and value_str.endswith('"'):
        return value_str[1:-1]

    # Handle boolean literals
    if value_str == "true":
        return True
    if value_str == "false":
        return False

    # Handle null
    if value_str == "null":
        return None

    # Handle list values
    if value_str.startswith("[") and value_str.endswith("]"):
        return _parse_list_example(value_str)

    # Try to parse as number
    try:
        if "." in value_str or "e" in value_str.lower():
            return float(value_str)
        return int(value_str)
    except ValueError:
        pass

    # Return as raw string
    return value_str


def _parse_list_example(list_str: str) -> list:
    """Parse a list example value.

    Args:
        list_str: String like '["item1", "item2"]' or '[1, 2, 3]'

    Returns:
        Parsed list
    """
    # Remove outer brackets
    inner = list_str[1:-1].strip()
    if not inner:
        return []

    # Split by comma, handling nested quotes
    items = []
    current = ""
    in_quotes = False
    depth = 0

    for char in inner:
        if char == '"' and depth == 0:
            in_quotes = not in_quotes
            current += char
        elif char == "[":
            depth += 1
            current += char
        elif char == "]":
            depth -= 1
            current += char
        elif char == "," and not in_quotes and depth == 0:
            if current.strip():
                items.append(_parse_example_value(current.strip()))
            current = ""
        else:
            current += char

    # Don't forget the last item
    if current.strip():
        items.append(_parse_example_value(current.strip()))

    return items


def _find_constraint_start(content: str) -> int:
    """Find the position of the first ∧ that starts the constraint chain.

    Handles nested brackets properly to avoid matching ∧ inside list examples.

    Args:
        content: Pattern content without outer brackets

    Returns:
        Position of first ∧ outside brackets, or -1 if not found
    """
    depth = 0
    in_quotes = False

    for i, char in enumerate(content):
        if char == '"':
            in_quotes = not in_quotes
        elif not in_quotes:
            if char == "[":
                depth += 1
            elif char == "]":
                depth -= 1
            elif char == "∧" and depth == 0:
                return i

    return -1


def _find_target_start(content: str) -> int:
    """Find the position of →§ that starts the target.

    Handles nested brackets and quoted strings properly to avoid matching
    →§ inside example values (Issue #93).

    Args:
        content: Pattern content

    Returns:
        Position of → before §, or -1 if not found
    """
    depth = 0
    in_quotes = False

    for i, char in enumerate(content):
        if char == '"' and (i == 0 or content[i - 1] != "\\"):
            in_quotes = not in_quotes
        elif not in_quotes:
            if char == "[":
                depth += 1
            elif char == "]":
                depth -= 1
            elif depth == 0:
                # Check for →§ (Unicode arrow)
                if content[i : i + 2] == "→§":
                    return i
                # Check for ->§ (ASCII variant)
                if content[i : i + 3] == "->§":
                    return i

    return -1


def parse_holographic_pattern(pattern_str: str) -> HolographicPattern:
    """Parse holographic pattern string into HolographicPattern.

    Parses patterns of the form:
        ["example"∧CONSTRAINT→§TARGET]

    Args:
        pattern_str: Full pattern string including brackets

    Returns:
        HolographicPattern with example, constraints, and target

    Raises:
        HolographicPatternError: If pattern is malformed

    Examples:
        >>> pattern = parse_holographic_pattern('["example"∧REQ→§SELF]')
        >>> pattern.example
        'example'
        >>> len(pattern.constraints.constraints)
        1
        >>> pattern.target
        'SELF'
    """
    pattern_str = pattern_str.strip()

    # Validate outer brackets
    if not pattern_str.startswith("[") or not pattern_str.endswith("]"):
        raise HolographicPatternError("Pattern must be enclosed in brackets", pattern_str)

    # Extract content between outer brackets
    content = pattern_str[1:-1].strip()

    if not content:
        raise HolographicPatternError("Pattern cannot be empty", pattern_str)

    # Find where constraints start (first ∧ outside quotes/brackets)
    constraint_start = _find_constraint_start(content)

    # Find where target starts (→§)
    target_start = _find_target_start(content)

    # Extract example value
    if constraint_start != -1:
        example_str = content[:constraint_start].strip()
    elif target_start != -1:
        example_str = content[:target_start].strip()
    else:
        example_str = content.strip()

    if not example_str:
        raise HolographicPatternError("Pattern must have an example value", pattern_str)

    # Parse example value
    example = _parse_example_value(example_str)

    # Extract and parse constraints
    constraints = None
    if constraint_start != -1:
        if target_start != -1:
            constraint_str = content[constraint_start + 1 : target_start].strip()
        else:
            constraint_str = content[constraint_start + 1 :].strip()

        if constraint_str:
            try:
                constraints = ConstraintChain.parse(constraint_str)
            except ValueError as e:
                raise HolographicPatternError(f"Invalid constraint: {e}", pattern_str) from e

    # Extract target
    target = None
    if target_start != -1:
        # Find § after →
        target_content = content[target_start:]
        section_pos = target_content.find("§")
        if section_pos != -1:
            target = target_content[section_pos + 1 :].strip()

    return HolographicPattern(example=example, constraints=constraints, target=target)
