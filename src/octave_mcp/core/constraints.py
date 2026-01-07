"""OCTAVE constraint evaluation (Gap 2).

Implements constraint chain evaluation with 11 constraint types:
- REQ: Required field (must be present, not None/empty)
- OPT: Optional field (can be missing)
- CONST[X]: Constant value (must equal X)
- ENUM[a,b,c]: Enumerated values (must be one of list, supports prefix matching)
- TYPE[X]: Type check (STRING|NUMBER|LIST|BOOLEAN) - preferred lexer-compatible syntax
- TYPE(X): Type check legacy syntax (works with direct ConstraintChain.parse() only)
- REGEX[pat]: Pattern matching
- DIR: Directory path validation
- APPEND_ONLY: List append semantics
- RANGE[min,max]: Numeric bounds validation
- MAX_LENGTH[N]: Maximum collection/string size
- MIN_LENGTH[N]: Minimum collection/string size
- DATE: ISO8601 date format validation

Constraint chains are evaluated left-to-right with fail-fast semantics.
Conflict detection identifies incompatible constraint combinations.
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ValidationError:
    """Validation error from constraint evaluation."""

    code: str
    path: str
    constraint: str
    expected: str
    got: str
    message: str


@dataclass
class ValidationResult:
    """Result of constraint evaluation."""

    valid: bool
    errors: list[ValidationError] = field(default_factory=list)


@dataclass
class ConstraintConflictError:
    """Represents a conflict between constraints."""

    constraint1: str
    constraint2: str
    reason: str

    def __str__(self) -> str:
        return f"Conflict: {self.constraint1} ∧ {self.constraint2} - {self.reason}"


class Constraint(ABC):
    """Base class for all constraints."""

    @abstractmethod
    def evaluate(self, value: Any, path: str = "") -> ValidationResult:
        """Evaluate constraint against value.

        Args:
            value: Value to validate
            path: Field path for error reporting

        Returns:
            ValidationResult with valid flag and any errors
        """
        pass

    @abstractmethod
    def to_string(self) -> str:
        """Return constraint as string (e.g., 'REQ', 'ENUM[A,B]')."""
        pass

    @abstractmethod
    def compile(self) -> str:
        """Compile constraint to regex pattern for grammar generation.

        Returns:
            Regex pattern string suitable for grammar construction.
            Example: EnumConstraint(['A', 'B']).compile() -> r"(A|B)"
        """
        pass


@dataclass
class RequiredConstraint(Constraint):
    """REQ constraint - value must be present and non-empty."""

    def evaluate(self, value: Any, path: str = "") -> ValidationResult:
        """Evaluate REQ constraint."""
        if value is None or value == "":
            return ValidationResult(
                valid=False,
                errors=[
                    ValidationError(
                        code="E003",
                        path=path,
                        constraint="REQ",
                        expected="non-empty value",
                        got=str(value),
                        message=f"Field '{path}' is required but got {value}",
                    )
                ],
            )
        return ValidationResult(valid=True)

    def to_string(self) -> str:
        return "REQ"

    def compile(self) -> str:
        """Compile REQ to non-empty pattern."""
        return r".+"


@dataclass
class OptionalConstraint(Constraint):
    """OPT constraint - value can be None or missing."""

    def evaluate(self, value: Any, path: str = "") -> ValidationResult:
        """Evaluate OPT constraint - always passes."""
        return ValidationResult(valid=True)

    def to_string(self) -> str:
        return "OPT"

    def compile(self) -> str:
        """Compile OPT to allow anything including empty."""
        return r".*"


@dataclass
class ConstConstraint(Constraint):
    """CONST[X] constraint - value must equal X exactly."""

    const_value: Any

    def evaluate(self, value: Any, path: str = "") -> ValidationResult:
        """Evaluate CONST constraint."""
        if value != self.const_value:
            return ValidationResult(
                valid=False,
                errors=[
                    ValidationError(
                        code="E004",
                        path=path,
                        constraint="CONST",
                        expected=str(self.const_value),
                        got=str(value),
                        message=f"Field '{path}' must be {self.const_value}, got {value}",
                    )
                ],
            )
        return ValidationResult(valid=True)

    def to_string(self) -> str:
        return f"CONST[{self.const_value}]"

    def compile(self) -> str:
        """Compile CONST to exact literal match."""
        return re.escape(str(self.const_value))


@dataclass
class EnumConstraint(Constraint):
    """ENUM[a,b,c] constraint - value must match one of the allowed values.

    Supports prefix matching: "ACT" matches "ACTIVE" if unambiguous.
    Rejects ambiguous prefixes: "ACTIV" matches both "ACTIVE" and "ACTIVATING".
    """

    allowed_values: list[str]

    def __post_init__(self):
        """Normalize allowed values to strings."""
        self.allowed_values = [str(v) for v in self.allowed_values]

    def evaluate(self, value: Any, path: str = "") -> ValidationResult:
        """Evaluate ENUM constraint with prefix matching."""
        value_str = str(value)

        # Exact match
        if value_str in self.allowed_values:
            return ValidationResult(valid=True)

        # Prefix matching
        matches = [v for v in self.allowed_values if v.startswith(value_str)]

        if len(matches) == 0:
            return ValidationResult(
                valid=False,
                errors=[
                    ValidationError(
                        code="E005",
                        path=path,
                        constraint="ENUM",
                        expected=f"one of {self.allowed_values}",
                        got=value_str,
                        message=f"Field '{path}' must be one of {self.allowed_values}, got {value_str}",
                    )
                ],
            )
        elif len(matches) > 1:
            # Ambiguous prefix - error E006
            return ValidationResult(
                valid=False,
                errors=[
                    ValidationError(
                        code="E006",
                        path=path,
                        constraint="ENUM",
                        expected=f"unambiguous match in {self.allowed_values}",
                        got=value_str,
                        message=f"Field '{path}' value '{value_str}' is ambiguous - matches {matches}",
                    )
                ],
            )

        # Unambiguous prefix match
        return ValidationResult(valid=True)

    def to_string(self) -> str:
        return f"ENUM[{','.join(self.allowed_values)}]"

    def compile(self) -> str:
        """Compile ENUM to regex alternation pattern."""
        escaped_values = [re.escape(str(v)) for v in self.allowed_values]
        return f"({'|'.join(escaped_values)})"


@dataclass
class TypeConstraint(Constraint):
    """TYPE(X) constraint - value must be of specified type.

    Supported types: STRING, NUMBER, LIST, BOOLEAN.
    NUMBER accepts both int and float.
    """

    expected_type: str

    def evaluate(self, value: Any, path: str = "") -> ValidationResult:
        """Evaluate TYPE constraint."""
        type_map: dict[str, type | tuple[type, ...]] = {
            "STRING": str,
            "NUMBER": (int, float),
            "BOOLEAN": bool,
            "LIST": list,
        }

        expected_python_type = type_map.get(self.expected_type)
        if expected_python_type is None:
            return ValidationResult(
                valid=False,
                errors=[
                    ValidationError(
                        code="E999",
                        path=path,
                        constraint="TYPE",
                        expected=f"valid type ({', '.join(type_map.keys())})",
                        got=self.expected_type,
                        message=f"Unknown type constraint: {self.expected_type}",
                    )
                ],
            )

        # I1 fix: TYPE(NUMBER) must reject bool (Python bool inherits from int)
        if self.expected_type == "NUMBER" and isinstance(value, bool):
            return ValidationResult(
                valid=False,
                errors=[
                    ValidationError(
                        code="E007",  # I4 fix: use E007 for type constraint violations
                        path=path,
                        constraint="TYPE",
                        expected=self.expected_type,
                        got=type(value).__name__,
                        message=f"Field '{path}' expected {self.expected_type}, got {type(value).__name__}",
                    )
                ],
            )

        if not isinstance(value, expected_python_type):
            return ValidationResult(
                valid=False,
                errors=[
                    ValidationError(
                        code="E007",  # I4 fix: use E007 for type constraint violations
                        path=path,
                        constraint="TYPE",
                        expected=self.expected_type,
                        got=type(value).__name__,
                        message=f"Field '{path}' expected {self.expected_type}, got {type(value).__name__}",
                    )
                ],
            )

        return ValidationResult(valid=True)

    def to_string(self) -> str:
        return f"TYPE({self.expected_type})"

    def compile(self) -> str:
        """Compile TYPE to appropriate regex pattern."""
        type_patterns = {
            "STRING": r".+",
            "NUMBER": r"-?\d+(\.\d+)?",
            "BOOLEAN": r"(true|false)",
            "LIST": r"\[.*\]",
        }
        return type_patterns.get(self.expected_type, r".+")


@dataclass
class RegexConstraint(Constraint):
    """REGEX[pattern] constraint - value must match regex pattern."""

    pattern: str
    _compiled: re.Pattern[str] | None = field(default=None, init=False, repr=False)

    def __post_init__(self):
        """Compile regex pattern once."""
        try:
            self._compiled = re.compile(self.pattern)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern '{self.pattern}': {e}") from e

    def evaluate(self, value: Any, path: str = "") -> ValidationResult:
        """Evaluate REGEX constraint."""
        value_str = str(value)

        if self._compiled and not self._compiled.match(value_str):
            return ValidationResult(
                valid=False,
                errors=[
                    ValidationError(
                        code="E008",
                        path=path,
                        constraint="REGEX",
                        expected=f"match pattern {self.pattern}",
                        got=value_str,
                        message=f"Field '{path}' does not match pattern {self.pattern}",
                    )
                ],
            )

        return ValidationResult(valid=True)

    def to_string(self) -> str:
        return f'REGEX["{self.pattern}"]'

    def compile(self) -> str:
        """Compile REGEX to its pattern (already a regex)."""
        return self.pattern


@dataclass
class DirConstraint(Constraint):
    """DIR constraint - value must be a valid directory path."""

    def evaluate(self, value: Any, path: str = "") -> ValidationResult:
        """Evaluate DIR constraint."""
        value_str = str(value)

        # Check for invalid characters (null byte is always invalid)
        if "\0" in value_str:
            return ValidationResult(
                valid=False,
                errors=[
                    ValidationError(
                        code="E009",
                        path=path,
                        constraint="DIR",
                        expected="valid directory path",
                        got=value_str,
                        message=f"Field '{path}' contains invalid path characters",
                    )
                ],
            )

        # Basic path format validation (starts with / or ./)
        if not (value_str.startswith("/") or value_str.startswith("./")):
            # Still valid if it's a relative path without ./
            pass

        return ValidationResult(valid=True)

    def to_string(self) -> str:
        return "DIR"

    def compile(self) -> str:
        """Compile DIR to path pattern (no null bytes)."""
        return r"[^\x00]+"


@dataclass
class AppendOnlyConstraint(Constraint):
    """APPEND_ONLY constraint - value must be a list (append semantics)."""

    def evaluate(self, value: Any, path: str = "") -> ValidationResult:
        """Evaluate APPEND_ONLY constraint."""
        if not isinstance(value, list):
            return ValidationResult(
                valid=False,
                errors=[
                    ValidationError(
                        code="E010",
                        path=path,
                        constraint="APPEND_ONLY",
                        expected="list",
                        got=type(value).__name__,
                        message=f"Field '{path}' must be a list for APPEND_ONLY semantics",
                    )
                ],
            )

        return ValidationResult(valid=True)

    def to_string(self) -> str:
        return "APPEND_ONLY"

    def compile(self) -> str:
        """Compile APPEND_ONLY to list pattern."""
        return r"\[.*\]"


@dataclass
class RangeConstraint(Constraint):
    """RANGE[min,max] constraint - value must be within numeric bounds (inclusive)."""

    min_value: int | float
    max_value: int | float

    def evaluate(self, value: Any, path: str = "") -> ValidationResult:
        """Evaluate RANGE constraint."""
        # Reject booleans (same issue as TYPE(NUMBER) - bool is subclass of int)
        if isinstance(value, bool):
            return ValidationResult(
                valid=False,
                errors=[
                    ValidationError(
                        code="E011",
                        path=path,
                        constraint="RANGE",
                        expected=f"numeric value in range [{self.min_value}, {self.max_value}]",
                        got="boolean",
                        message=f"Field '{path}' must be numeric (not boolean) for RANGE constraint",
                    )
                ],
            )
        # Convert value to numeric type
        try:
            numeric_value = float(value) if isinstance(value, int | float) else float(value)
        except (ValueError, TypeError):
            return ValidationResult(
                valid=False,
                errors=[
                    ValidationError(
                        code="E011",
                        path=path,
                        constraint="RANGE",
                        expected=f"numeric value in range [{self.min_value}, {self.max_value}]",
                        got=str(value),
                        message=f"Field '{path}' must be numeric for RANGE constraint",
                    )
                ],
            )

        # Check bounds (inclusive)
        if numeric_value < self.min_value or numeric_value > self.max_value:
            return ValidationResult(
                valid=False,
                errors=[
                    ValidationError(
                        code="E011",
                        path=path,
                        constraint="RANGE",
                        expected=f"value in range [{self.min_value}, {self.max_value}]",
                        got=str(value),
                        message=f"Value {value} is outside range [{self.min_value}, {self.max_value}]",
                    )
                ],
            )

        return ValidationResult(valid=True)

    def to_string(self) -> str:
        return f"RANGE[{self.min_value},{self.max_value}]"

    def compile(self) -> str:
        """Compile RANGE to numeric pattern (bounds checked at validation)."""
        return r"-?\d+(\.\d+)?"


@dataclass
class MaxLengthConstraint(Constraint):
    """MAX_LENGTH[N] constraint - string/list length must not exceed N."""

    max_length: int

    def evaluate(self, value: Any, path: str = "") -> ValidationResult:
        """Evaluate MAX_LENGTH constraint."""
        # Only accept strings and lists (not dicts, sets, tuples, etc.)
        if not isinstance(value, str | list):
            return ValidationResult(
                valid=False,
                errors=[
                    ValidationError(
                        code="E012",
                        path=path,
                        constraint="MAX_LENGTH",
                        expected="string or list",
                        got=type(value).__name__,
                        message=f"Field '{path}' must be string or list for MAX_LENGTH constraint",
                    )
                ],
            )
        # Get length
        try:
            length = len(value)
        except TypeError:
            return ValidationResult(
                valid=False,
                errors=[
                    ValidationError(
                        code="E012",
                        path=path,
                        constraint="MAX_LENGTH",
                        expected="string or list",
                        got=type(value).__name__,
                        message=f"Field '{path}' must have length for MAX_LENGTH constraint",
                    )
                ],
            )

        if length > self.max_length:
            return ValidationResult(
                valid=False,
                errors=[
                    ValidationError(
                        code="E012",
                        path=path,
                        constraint="MAX_LENGTH",
                        expected=f"length <= {self.max_length}",
                        got=str(length),
                        message=f"Length {length} exceeds maximum {self.max_length}",
                    )
                ],
            )

        return ValidationResult(valid=True)

    def to_string(self) -> str:
        return f"MAX_LENGTH[{self.max_length}]"

    def compile(self) -> str:
        """Compile MAX_LENGTH to bounded repetition."""
        return f".{{0,{self.max_length}}}"


@dataclass
class MinLengthConstraint(Constraint):
    """MIN_LENGTH[N] constraint - string/list length must be at least N."""

    min_length: int

    def evaluate(self, value: Any, path: str = "") -> ValidationResult:
        """Evaluate MIN_LENGTH constraint."""
        # Only accept strings and lists (not dicts, sets, tuples, etc.)
        if not isinstance(value, str | list):
            return ValidationResult(
                valid=False,
                errors=[
                    ValidationError(
                        code="E013",
                        path=path,
                        constraint="MIN_LENGTH",
                        expected="string or list",
                        got=type(value).__name__,
                        message=f"Field '{path}' must be string or list for MIN_LENGTH constraint",
                    )
                ],
            )
        # Get length
        try:
            length = len(value)
        except TypeError:
            return ValidationResult(
                valid=False,
                errors=[
                    ValidationError(
                        code="E013",
                        path=path,
                        constraint="MIN_LENGTH",
                        expected="string or list",
                        got=type(value).__name__,
                        message=f"Field '{path}' must be string or list for MIN_LENGTH constraint",
                    )
                ],
            )

        if length < self.min_length:
            return ValidationResult(
                valid=False,
                errors=[
                    ValidationError(
                        code="E013",
                        path=path,
                        constraint="MIN_LENGTH",
                        expected=f"length >= {self.min_length}",
                        got=str(length),
                        message=f"Length {length} is below minimum {self.min_length}",
                    )
                ],
            )

        return ValidationResult(valid=True)

    def to_string(self) -> str:
        return f"MIN_LENGTH[{self.min_length}]"

    def compile(self) -> str:
        """Compile MIN_LENGTH to minimum repetition."""
        return f".{{{self.min_length},}}"


@dataclass
class DateConstraint(Constraint):
    """DATE constraint - value must be a valid date in YYYY-MM-DD format only.

    For full ISO8601 datetime support, use ISO8601 constraint instead.
    """

    def evaluate(self, value: Any, path: str = "") -> ValidationResult:
        """Evaluate DATE constraint (strict YYYY-MM-DD only)."""
        import re

        value_str = str(value)

        # Strict YYYY-MM-DD pattern only
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", value_str):
            return ValidationResult(
                valid=False,
                errors=[
                    ValidationError(
                        code="E014",
                        path=path,
                        constraint="DATE",
                        expected="date in YYYY-MM-DD format",
                        got=value_str,
                        message="Value must be a date in YYYY-MM-DD format (use ISO8601 for datetime)",
                    )
                ],
            )

        # Validate it's actually a valid date
        try:
            datetime.fromisoformat(value_str)
            return ValidationResult(valid=True)
        except ValueError:
            return ValidationResult(
                valid=False,
                errors=[
                    ValidationError(
                        code="E014",
                        path=path,
                        constraint="DATE",
                        expected="valid date",
                        got=value_str,
                        message=f"'{value_str}' is not a valid date",
                    )
                ],
            )

    def to_string(self) -> str:
        return "DATE"

    def compile(self) -> str:
        """Compile DATE to YYYY-MM-DD pattern."""
        return r"\d{4}-\d{2}-\d{2}"


@dataclass
class Iso8601Constraint(Constraint):
    """ISO8601 constraint - value must be a valid ISO8601 date or datetime.

    Accepts:
    - YYYY-MM-DD (date only)
    - YYYY-MM-DDTHH:MM:SS (datetime)
    - YYYY-MM-DDTHH:MM:SSZ (datetime with UTC)
    - YYYY-MM-DDTHH:MM:SS+HH:MM (datetime with timezone)
    """

    def evaluate(self, value: Any, path: str = "") -> ValidationResult:
        """Evaluate ISO8601 constraint."""
        value_str = str(value)

        try:
            # datetime.fromisoformat handles various ISO8601 formats
            datetime.fromisoformat(value_str.replace("Z", "+00:00"))
            return ValidationResult(valid=True)
        except (ValueError, AttributeError):
            return ValidationResult(
                valid=False,
                errors=[
                    ValidationError(
                        code="E015",
                        path=path,
                        constraint="ISO8601",
                        expected="ISO8601 date/datetime format",
                        got=value_str,
                        message="Value is not a valid ISO8601 date or datetime",
                    )
                ],
            )

    def to_string(self) -> str:
        return "ISO8601"

    def compile(self) -> str:
        """Compile ISO8601 to pattern supporting dates and datetimes."""
        # Matches YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS with optional timezone
        return r"\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})?)?"


def _parse_atom(s: str) -> Any:
    """Parse atom value from constraint string.

    Handles:
    - Quoted strings: "foo" → foo (strip quotes, handle escapes)
    - Numbers: 42, 3.14, 1e10, -5 → int/float
    - Booleans: true, false → True, False
    - Null: null → None
    - Raw identifier otherwise

    Args:
        s: String to parse

    Returns:
        Parsed Python value
    """
    s = s.strip()

    # Handle quoted strings
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        # Strip quotes and handle basic escapes
        return s[1:-1].replace(r"\"", '"').replace(r"\'", "'").replace(r"\\", "\\")

    # Handle booleans
    if s == "true":
        return True
    if s == "false":
        return False

    # Handle null
    if s == "null":
        return None

    # Try to parse as number
    try:
        # Try int first (including negative)
        if "." not in s and "e" not in s.lower():
            return int(s)
        # Otherwise float (including scientific notation)
        return float(s)
    except ValueError:
        pass

    # Return as raw string identifier
    return s


class ConstraintChain:
    """Chain of constraints evaluated left-to-right with fail-fast semantics."""

    def __init__(self, constraints: list[Constraint]):
        """Initialize constraint chain.

        Args:
            constraints: Ordered list of constraints
        """
        self.constraints = constraints

    @classmethod
    def parse(cls, constraint_str: str) -> "ConstraintChain":
        """Parse constraint string into ConstraintChain.

        Supports:
        - Single: "REQ"
        - Chain: "REQ∧TYPE(STRING)"
        - Parameters: "ENUM[A,B,C]", "CONST[X]", "REGEX["pattern"]"

        Args:
            constraint_str: Constraint string (e.g., "REQ∧ENUM[A,B]")

        Returns:
            ConstraintChain instance
        """
        constraints: list[Constraint] = []

        # Split by ∧ operator
        parts = constraint_str.split("∧")

        for part in parts:
            part = part.strip()

            if part == "REQ":
                constraints.append(RequiredConstraint())
            elif part == "OPT":
                constraints.append(OptionalConstraint())
            elif part == "DIR":
                constraints.append(DirConstraint())
            elif part == "APPEND_ONLY":
                constraints.append(AppendOnlyConstraint())
            elif part == "DATE":
                # Strict YYYY-MM-DD only
                constraints.append(DateConstraint())
            elif part == "ISO8601":
                # Full ISO8601 datetime support
                constraints.append(Iso8601Constraint())
            elif part.startswith("CONST[") and part.endswith("]"):
                # Extract value from CONST[value] - I2 fix: use _parse_atom
                const_value_str = part[6:-1]
                const_value = _parse_atom(const_value_str)
                constraints.append(ConstConstraint(const_value=const_value))
            elif part.startswith("ENUM[") and part.endswith("]"):
                # Extract values from ENUM[A,B,C] - I2 fix: use _parse_atom
                values_str = part[5:-1]
                values = [_parse_atom(v.strip()) for v in values_str.split(",")]
                constraints.append(EnumConstraint(allowed_values=values))
            elif part.startswith("TYPE[") and part.endswith("]"):
                # Extract type from TYPE[STRING] (square brackets for lexer compatibility)
                type_str = part[5:-1]
                constraints.append(TypeConstraint(expected_type=type_str))
            elif part.startswith("TYPE(") and part.endswith(")"):
                # Legacy: TYPE(STRING) with parentheses (kept for direct ConstraintChain.parse() calls)
                type_str = part[5:-1]
                constraints.append(TypeConstraint(expected_type=type_str))
            elif part.startswith("REGEX[") and part.endswith("]"):
                # Extract pattern from REGEX["pattern"] or REGEX[pattern]
                pattern = part[6:-1]
                # Remove quotes if present
                if pattern.startswith('"') and pattern.endswith('"'):
                    pattern = pattern[1:-1]
                constraints.append(RegexConstraint(pattern=pattern))
            elif part.startswith("RANGE[") and part.endswith("]"):
                # Extract min and max from RANGE[min,max]
                range_str = part[6:-1]
                try:
                    min_str, max_str = range_str.split(",", 1)
                except ValueError as err:
                    raise ValueError(f"RANGE requires two values: RANGE[min,max], got: {part}") from err
                min_value = _parse_atom(min_str.strip())
                max_value = _parse_atom(max_str.strip())
                if not isinstance(min_value, int | float) or not isinstance(max_value, int | float):
                    raise ValueError(f"RANGE requires numeric bounds, got: {range_str}")
                if min_value > max_value:
                    raise ValueError(f"RANGE min must be <= max, got: {min_value} > {max_value}")
                constraints.append(RangeConstraint(min_value=min_value, max_value=max_value))
            elif part.startswith("MAX_LENGTH[") and part.endswith("]"):
                # Extract N from MAX_LENGTH[N]
                length_str = part[11:-1]
                max_length = _parse_atom(length_str.strip())
                if not isinstance(max_length, int) or max_length < 0:
                    raise ValueError(f"MAX_LENGTH requires non-negative integer, got: {length_str}")
                constraints.append(MaxLengthConstraint(max_length=max_length))
            elif part.startswith("MIN_LENGTH[") and part.endswith("]"):
                # Extract N from MIN_LENGTH[N]
                length_str = part[11:-1]
                min_length = _parse_atom(length_str.strip())
                if not isinstance(min_length, int) or min_length < 0:
                    raise ValueError(f"MIN_LENGTH requires non-negative integer, got: {length_str}")
                constraints.append(MinLengthConstraint(min_length=min_length))
            else:
                raise ValueError(f"Unknown constraint: {part}")

        return cls(constraints)

    def evaluate(self, value: Any, path: str = "") -> ValidationResult:
        """Evaluate constraint chain with fail-fast semantics.

        Args:
            value: Value to validate
            path: Field path for error reporting

        Returns:
            ValidationResult (stops at first failure)
        """
        # I3 fix: Enforce conflict detection before evaluation
        conflicts = self.detect_conflicts()
        if conflicts:
            # Convert conflicts to validation errors
            errors = [
                ValidationError(
                    code="E999",
                    path=path,
                    constraint="CONFLICT",
                    expected="no conflicting constraints",
                    got=f"{conflict.constraint1} ∧ {conflict.constraint2}",
                    message=f"Constraint conflict: {conflict.reason}",
                )
                for conflict in conflicts
            ]
            return ValidationResult(valid=False, errors=errors)

        for constraint in self.constraints:
            result = constraint.evaluate(value, path)
            if not result.valid:
                # Fail fast - return immediately on first failure
                return result

        return ValidationResult(valid=True)

    def detect_conflicts(self) -> list[ConstraintConflictError]:
        """Detect conflicting constraints in chain.

        Conflicts:
        - REQ ∧ OPT (mutually exclusive)
        - ENUM[A,B] ∧ CONST[C] where C not in [A,B]
        - CONST[X] ∧ CONST[Y] where X ≠ Y

        Returns:
            List of detected conflicts
        """
        conflicts: list[ConstraintConflictError] = []

        # Check for REQ ∧ OPT
        has_req = any(isinstance(c, RequiredConstraint) for c in self.constraints)
        has_opt = any(isinstance(c, OptionalConstraint) for c in self.constraints)
        if has_req and has_opt:
            conflicts.append(
                ConstraintConflictError(
                    constraint1="REQ",
                    constraint2="OPT",
                    reason="Cannot be both required and optional",
                )
            )

        # Check for CONST[X] ∧ CONST[Y]
        const_constraints = [c for c in self.constraints if isinstance(c, ConstConstraint)]
        if len(const_constraints) > 1:
            for i in range(len(const_constraints) - 1):
                if const_constraints[i].const_value != const_constraints[i + 1].const_value:
                    conflicts.append(
                        ConstraintConflictError(
                            constraint1=const_constraints[i].to_string(),
                            constraint2=const_constraints[i + 1].to_string(),
                            reason="Cannot have different constant values",
                        )
                    )

        # Check for ENUM[...] ∧ CONST[X]
        enum_constraints = [c for c in self.constraints if isinstance(c, EnumConstraint)]
        for enum_c in enum_constraints:
            for const_c in const_constraints:
                if str(const_c.const_value) not in enum_c.allowed_values:
                    conflicts.append(
                        ConstraintConflictError(
                            constraint1=enum_c.to_string(),
                            constraint2=const_c.to_string(),
                            reason=f"Constant {const_c.const_value} not in enum values {enum_c.allowed_values}",
                        )
                    )

        return conflicts

    def compile(self) -> str:
        """Compile constraint chain to regex pattern for grammar generation.

        Combines individual constraint patterns using lookahead intersection.
        Example: REQ∧ENUM[A,B] -> ^(?=(?:.+)$)(?=(?:(A|B))$).*$

        Returns:
            Regex pattern string for complete chain validation
        """
        if not self.constraints:
            return r".*"  # Empty chain matches anything

        # Compile each constraint
        patterns = [c.compile() for c in self.constraints]

        # Join patterns - intersect them using lookaheads
        # We wrap each pattern in (?:...) to handle alternation safely
        # and assert it matches to the end ($)
        lookaheads = [f"(?=(?:{p})$)" for p in patterns]
        combined = "".join(lookaheads)

        # Add start anchor and consume patterns
        return f"^{combined}.*$"

    def to_string(self) -> str:
        """Return chain as string."""
        return "∧".join(c.to_string() for c in self.constraints)
