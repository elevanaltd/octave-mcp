"""MCP tool for debate transcript conversion (Issue #52).

Converts debate-hall-mcp JSON transcripts to OCTAVE format for archival.
Integrates functionality from tools/json-to-octave.py into MCP server.

Features:
- JSON-to-OCTAVE conversion with proper envelope formatting
- Turn representation with cognition metadata
- Optional compression metrics tracking
"""

import json
import re
from dataclasses import dataclass
from typing import Any

from octave_mcp.mcp.base_tool import BaseTool, SchemaBuilder


def _sanitize_value(value: Any) -> str:
    """Sanitize untrusted strings to prevent OCTAVE structure injection.

    Prevents injection attacks where malicious input could:
    - Inject newlines to break OCTAVE structure
    - Inject envelope markers (===XXX===) to create fake sections
    - Inject control characters to corrupt document parsing

    Args:
        value: Untrusted value from user input (will be converted to string if needed)

    Returns:
        Sanitized string safe for OCTAVE output

    Examples:
        >>> _sanitize_value("normal text")
        'normal text'
        >>> _sanitize_value("has\\nnewline")
        'has\\\\n newline'
        >>> _sanitize_value("has===END===marker")
        'hasESCAPED_ENVELOPE_ENDmarker'
    """
    if not isinstance(value, str):
        return str(value)

    # Escape newlines and carriage returns
    sanitized = value.replace("\r\n", "\\r\\n")
    sanitized = sanitized.replace("\n", "\\n")
    sanitized = sanitized.replace("\r", "\\r")

    # Escape envelope markers (===XXX===) to prevent structure injection
    # Replace with visually similar but safe representation
    sanitized = re.sub(
        r"===([A-Z_]+)===",
        r"ESCAPED_ENVELOPE_\1",
        sanitized,
    )

    return sanitized


@dataclass
class CompressionMetrics:
    """Metrics for tracking compression of debate transcripts.

    Attributes:
        original_size_bytes: Size of original JSON input in bytes
        compressed_size_bytes: Size of OCTAVE output in bytes
        compression_ratio: Ratio of compressed to original (0-1, lower is better)
        elements_before: Number of distinct elements in JSON (keys + array items)
        elements_after: Number of lines in OCTAVE output
    """

    original_size_bytes: int
    compressed_size_bytes: int
    compression_ratio: float
    elements_before: int
    elements_after: int

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary for JSON serialization."""
        return {
            "original_size_bytes": self.original_size_bytes,
            "compressed_size_bytes": self.compressed_size_bytes,
            "compression_ratio": self.compression_ratio,
            "elements_before": self.elements_before,
            "elements_after": self.elements_after,
        }


def _count_json_elements(data: Any) -> int:
    """Count distinct elements in JSON structure.

    Args:
        data: JSON data (dict, list, or scalar)

    Returns:
        Count of elements (keys + array items)
    """
    if isinstance(data, dict):
        count = len(data)  # Count keys
        for value in data.values():
            count += _count_json_elements(value)
        return count
    elif isinstance(data, list):
        count = len(data)  # Count items
        for item in data:
            count += _count_json_elements(item)
        return count
    else:
        return 1  # Scalar value


def _format_value(value: Any) -> str:
    """Format a value for OCTAVE output.

    Args:
        value: Value to format

    Returns:
        Formatted string representation
    """
    if isinstance(value, str):
        # Escape and quote strings that might be ambiguous
        if any(c in value for c in ["\n", "::", "["]):
            return f'"{value}"'
        return value
    elif isinstance(value, bool):
        return "true" if value else "false"
    elif value is None:
        return "null"
    elif isinstance(value, list):
        return "[" + ", ".join(_format_value(v) for v in value) + "]"
    elif isinstance(value, dict):
        # Inline dict representation
        pairs = [f"{k}:{_format_value(v)}" for k, v in value.items()]
        return "{" + ", ".join(pairs) + "}"
    else:
        return str(value)


def _format_turn(turn: dict[str, Any], index: int) -> list[str]:
    """Format a single turn for OCTAVE output.

    All user-controlled fields are sanitized to prevent structure injection.

    Args:
        turn: Turn dictionary with role, content, cognition, etc.
        index: Turn index (0-based)

    Returns:
        List of formatted lines
    """
    lines = []
    lines.append(f"  TURN_{index + 1}:")

    # Role and cognition on same line for compactness - SANITIZE both
    role = _sanitize_value(turn.get("role", "Unknown"))
    cognition = turn.get("cognition", "")
    if cognition:
        lines.append(f"    ROLE::{role}|{_sanitize_value(cognition)}")
    else:
        lines.append(f"    ROLE::{role}")

    # Content - SANITIZE (sanitization handles newlines, so no multiline needed)
    content = _sanitize_value(turn.get("content", ""))
    # After sanitization, content is single-line (newlines escaped)
    lines.append(f"    CONTENT::{content}")

    # Optional fields - SANITIZE
    if "agent_role" in turn:
        lines.append(f"    AGENT_ROLE::{_sanitize_value(turn['agent_role'])}")
    if "model" in turn:
        lines.append(f"    MODEL::{_sanitize_value(turn['model'])}")

    return lines


def _debate_to_octave(debate: dict[str, Any]) -> str:
    """Convert debate transcript to OCTAVE format.

    All user-controlled fields are sanitized to prevent structure injection.

    Args:
        debate: Debate transcript dictionary

    Returns:
        OCTAVE formatted string
    """
    lines = []

    # Document envelope
    lines.append("===DEBATE_TRANSCRIPT===")

    # META block
    lines.append("META:")
    lines.append("  TYPE::DEBATE_TRANSCRIPT")
    lines.append('  VERSION::"1.0"')
    lines.append("")

    # Core fields - SANITIZE all user-controlled strings
    thread_id = _sanitize_value(debate.get("thread_id", "unknown"))
    lines.append(f"THREAD_ID::{thread_id}")

    topic = debate.get("topic", "")
    if topic:
        lines.append(f"TOPIC::{_sanitize_value(topic)}")

    mode = _sanitize_value(debate.get("mode", "fixed"))
    lines.append(f"MODE::{mode}")

    status = _sanitize_value(debate.get("status", "active"))
    lines.append(f"STATUS::{status}")

    # Participants - sanitize each participant name
    participants = debate.get("participants", [])
    sanitized_participants = [_sanitize_value(p) for p in participants]
    lines.append(f"PARTICIPANTS::{_format_value(sanitized_participants)}")

    # Optional configuration (numeric values, no sanitization needed)
    if "max_rounds" in debate:
        lines.append(f"MAX_ROUNDS::{debate['max_rounds']}")
    if "max_turns" in debate:
        lines.append(f"MAX_TURNS::{debate['max_turns']}")

    lines.append("")

    # Turns block
    turns = debate.get("turns", [])
    if turns:
        lines.append("TURNS:")
        for i, turn in enumerate(turns):
            lines.extend(_format_turn(turn, i))
        lines.append("")

    # Synthesis (if present) - SANITIZE
    synthesis = debate.get("synthesis")
    if synthesis:
        lines.append(f"SYNTHESIS::{_sanitize_value(synthesis)}")
        lines.append("")

    # End envelope
    lines.append("===END===")

    return "\n".join(lines)


class DebateConvertTool(BaseTool):
    """MCP tool for converting debate JSON to OCTAVE format."""

    def get_name(self) -> str:
        """Get tool name."""
        return "octave_debate_to_octave"

    def get_description(self) -> str:
        """Get tool description."""
        return (
            "Convert debate-hall-mcp JSON transcript to OCTAVE format. "
            "Takes debate JSON as input and produces structured OCTAVE output "
            "suitable for archival and analysis."
        )

    def get_input_schema(self) -> dict[str, Any]:
        """Get input schema."""
        schema = SchemaBuilder()

        schema.add_parameter(
            "debate_json",
            "string",
            required=True,
            description="Debate transcript as JSON string or dict. Expected fields: thread_id, topic, mode, status, participants, turns, synthesis (optional)",
        )

        schema.add_parameter(
            "include_metrics",
            "boolean",
            required=False,
            description="Include compression metrics in response (default: false)",
        )

        return schema.build()

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute debate conversion.

        Args:
            debate_json: Debate transcript as JSON string or dict
            include_metrics: Whether to include compression metrics (default: False)

        Returns:
            Dictionary with:
            - status: "success" or "error"
            - output: OCTAVE formatted debate (on success)
            - metrics: CompressionMetrics dict (if requested and successful)
            - errors: List of error records (on failure)
        """
        # Validate and extract parameters
        params = self.validate_parameters(kwargs)
        debate_json = params["debate_json"]
        include_metrics = params.get("include_metrics", False)

        # Parse input
        try:
            if isinstance(debate_json, dict):
                debate = debate_json
                original_json_str = json.dumps(debate_json)
            else:
                original_json_str = debate_json
                debate = json.loads(debate_json)
        except json.JSONDecodeError as e:
            return {
                "status": "error",
                "errors": [{"code": "E_JSON", "message": f"Invalid JSON: {str(e)}"}],
            }

        # Convert to OCTAVE
        try:
            octave_output = _debate_to_octave(debate)
        except Exception as e:
            return {
                "status": "error",
                "errors": [{"code": "E_CONVERT", "message": f"Conversion error: {str(e)}"}],
            }

        # Build response
        result: dict[str, Any] = {
            "status": "success",
            "output": octave_output,
        }

        # Add metrics if requested
        if include_metrics:
            original_bytes = len(original_json_str.encode("utf-8"))
            compressed_bytes = len(octave_output.encode("utf-8"))
            elements_before = _count_json_elements(debate)
            elements_after = len(octave_output.split("\n"))

            metrics = CompressionMetrics(
                original_size_bytes=original_bytes,
                compressed_size_bytes=compressed_bytes,
                compression_ratio=round(compressed_bytes / original_bytes, 3) if original_bytes > 0 else 0.0,
                elements_before=elements_before,
                elements_after=elements_after,
            )
            result["metrics"] = metrics.to_dict()

        return result
