"""GBNF compiler for OCTAVE constraint chains (Issue #171).

Transforms OCTAVE schemas and constraints into llama.cpp GBNF format
for constrained text generation.

GBNF (Grammar BNF) is a BNF-like format used by llama.cpp for grammar-based
sampling. Key syntax:
- rule-name ::= definition
- "literal" for string literals
- [a-z] for character classes
- (a | b) for alternation
- rule* for zero or more
- rule+ for one or more
- rule? for optional
"""

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from octave_mcp.core.constraints import (
    AppendOnlyConstraint,
    ConstConstraint,
    Constraint,
    ConstraintChain,
    DateConstraint,
    DirConstraint,
    EnumConstraint,
    Iso8601Constraint,
    MaxLengthConstraint,
    MinLengthConstraint,
    OptionalConstraint,
    RangeConstraint,
    RegexConstraint,
    RequiredConstraint,
    TypeConstraint,
)

if TYPE_CHECKING:
    from octave_mcp.core.schema_extractor import SchemaDefinition


@dataclass
class GBNFCompiler:
    """Compiles OCTAVE schemas and constraints to llama.cpp GBNF format.

    GBNF is a BNF-style grammar format used for constrained generation.
    Unlike full regex, GBNF uses simple rules and character classes.

    Example GBNF output:
        root ::= document
        document ::= "===NAME===" ws content ws "===END==="
        content ::= field*
        field ::= identifier "::" ws value ws
    """

    # Rule counter for generating unique rule names
    _rule_counter: int = field(default=0, init=False, repr=False)

    # Standard GBNF primitives
    PRIMITIVES: dict[str, str] = field(
        default_factory=lambda: {
            "ws": "ws ::= [ \\t\\n]*",
            "digit": "digit ::= [0-9]",
            "letter": "letter ::= [a-zA-Z]",
            "alphanum": "alphanum ::= [a-zA-Z0-9_]",
            "string-char": 'string-char ::= [^"\\\\] | "\\\\" ["\\\\/bfnrt]',
            "number": 'number ::= "-"? digit+ ("." digit+)?',
            "boolean": 'boolean ::= "true" | "false"',
            "null": 'null ::= "null"',
            "string": 'string ::= "\\"" string-char* "\\""',
        },
        init=False,
        repr=False,
    )

    def _next_rule_name(self, prefix: str = "rule") -> str:
        """Generate unique rule name.

        Args:
            prefix: Prefix for rule name

        Returns:
            Unique rule name like 'rule_0', 'rule_1', etc.
        """
        name = f"{prefix}_{self._rule_counter}"
        self._rule_counter += 1
        return name

    def _sanitize_rule_name(self, field_name: str) -> str:
        """Sanitize field name to valid GBNF rule name.

        Valid GBNF rule names: lowercase letters, digits, underscores, hyphens.
        Replaces invalid characters with descriptive encodings.

        Args:
            field_name: Raw field name that may contain invalid characters

        Returns:
            Sanitized rule name safe for GBNF grammar
        """
        result = field_name.lower()

        # Replace common special characters with descriptive names
        result = result.replace(".", "_dot_")
        result = result.replace("/", "_slash_")
        result = result.replace("-", "_")

        # Handle unicode: replace non-ASCII with _u{codepoint}_
        sanitized = []
        for char in result:
            if char.isascii() and (char.isalnum() or char == "_"):
                sanitized.append(char)
            elif not char.isascii():
                # Encode unicode as _u{hex}_
                sanitized.append(f"_u{ord(char):x}_")
            # Skip other invalid ASCII chars (already handled above)
        result = "".join(sanitized)

        # Ensure rule name doesn't start with digit
        if result and result[0].isdigit():
            result = "r_" + result

        # Collapse multiple underscores
        while "__" in result:
            result = result.replace("__", "_")

        # Remove leading/trailing underscores
        result = result.strip("_")

        return result or "unnamed_field"

    def compile_constraint(self, constraint: Constraint) -> str:
        """Compile a single constraint to GBNF rule fragment.

        Args:
            constraint: Constraint to compile

        Returns:
            GBNF rule fragment (not full rule with ::=)
        """
        if isinstance(constraint, RequiredConstraint):
            return self._compile_required()
        elif isinstance(constraint, OptionalConstraint):
            return self._compile_optional()
        elif isinstance(constraint, EnumConstraint):
            return self._compile_enum(constraint)
        elif isinstance(constraint, ConstConstraint):
            return self._compile_const(constraint)
        elif isinstance(constraint, TypeConstraint):
            return self._compile_type(constraint)
        elif isinstance(constraint, RegexConstraint):
            return self._compile_regex(constraint)
        elif isinstance(constraint, DirConstraint):
            return self._compile_dir()
        elif isinstance(constraint, AppendOnlyConstraint):
            return self._compile_list()
        elif isinstance(constraint, RangeConstraint):
            return self._compile_range(constraint)
        elif isinstance(constraint, MaxLengthConstraint):
            return self._compile_max_length(constraint)
        elif isinstance(constraint, MinLengthConstraint):
            return self._compile_min_length(constraint)
        elif isinstance(constraint, DateConstraint):
            return self._compile_date()
        elif isinstance(constraint, Iso8601Constraint):
            return self._compile_iso8601()
        else:
            # Unknown constraint - return permissive pattern
            return "[^\\n]+"

    def _compile_required(self) -> str:
        """Compile REQ constraint - must have at least one character."""
        return "[^\\n]+"

    def _compile_optional(self) -> str:
        """Compile OPT constraint - can be empty or have value."""
        return "[^\\n]*"

    def _compile_enum(self, constraint: EnumConstraint) -> str:
        """Compile ENUM constraint to alternation.

        Args:
            constraint: ENUM constraint with allowed values

        Returns:
            GBNF alternation: ("value1" | "value2" | "value3")
        """
        escaped = [self._escape_literal(v) for v in constraint.allowed_values]
        quoted = [f'"{v}"' for v in escaped]
        return f"({' | '.join(quoted)})"

    def _compile_const(self, constraint: ConstConstraint) -> str:
        """Compile CONST constraint to literal match.

        Args:
            constraint: CONST constraint with fixed value

        Returns:
            GBNF literal: "value"
        """
        value = str(constraint.const_value)
        escaped = self._escape_literal(value)
        return f'"{escaped}"'

    def _compile_type(self, constraint: TypeConstraint) -> str:
        """Compile TYPE constraint to appropriate GBNF pattern.

        Args:
            constraint: TYPE constraint (STRING, NUMBER, BOOLEAN, LIST)

        Returns:
            GBNF pattern for the type
        """
        type_patterns = {
            "STRING": "[^\\n]+",
            "NUMBER": '"-"? [0-9]+ ("." [0-9]+)?',
            "BOOLEAN": '("true" | "false")',
            "LIST": '"[" [^\\]]* "]"',
        }
        return type_patterns.get(constraint.expected_type, "[^\\n]+")

    def _compile_regex(self, constraint: RegexConstraint) -> str:
        """Compile REGEX constraint to GBNF character class.

        GBNF doesn't support full regex, so we map common patterns:
        - [a-z] -> [a-z]
        - [A-Z] -> [A-Z]
        - [0-9] -> [0-9]
        - . -> [^\\n]
        - + -> +
        - * -> *

        Complex patterns (lookahead, backrefs) degrade to permissive pattern.

        Args:
            constraint: REGEX constraint with pattern

        Returns:
            GBNF character class or simplified pattern
        """
        pattern = constraint.pattern

        # Remove anchors (GBNF always matches full rule)
        pattern = pattern.lstrip("^").rstrip("$")

        # Check for unsupported features
        unsupported = ["(?", "\\b", "\\B", "\\d", "\\w", "\\s", "\\D", "\\W", "\\S"]
        if any(u in pattern for u in unsupported):
            # Degrade gracefully - allow any non-newline chars
            return "[^\\n]+"

        # Try to preserve simple patterns
        # Handle [a-z]+, [A-Z]+, [0-9]+, etc.
        simple_char_class = re.match(r"^\[([^\]]+)\]([+*?]?)$", pattern)
        if simple_char_class:
            char_class = simple_char_class.group(1)
            quantifier = simple_char_class.group(2) or "+"
            return f"[{char_class}]{quantifier}"

        # For more complex patterns, create a safe approximation
        # Replace . with [^\\n], preserve quantifiers
        result = pattern.replace(".", "[^\\n]")

        # If result is empty or just quantifiers, use permissive
        if not result or result in ["+", "*", "?"]:
            return "[^\\n]+"

        return result

    def _compile_dir(self) -> str:
        """Compile DIR constraint to path pattern."""
        # Path characters: alphanumeric, slashes, dots, dashes, underscores
        return "[a-zA-Z0-9_./-]+"

    def _compile_list(self) -> str:
        """Compile list constraint (APPEND_ONLY or TYPE[LIST])."""
        return '"[" [^\\]]* "]"'

    def _compile_range(self, constraint: RangeConstraint) -> str:
        """Compile RANGE constraint to numeric pattern.

        Note: GBNF can't enforce numeric bounds at grammar level.
        We generate pattern that matches numeric format.

        Args:
            constraint: RANGE constraint with min/max

        Returns:
            GBNF numeric pattern
        """
        # GBNF can match numeric format but can't enforce value bounds
        # Bounds must be checked at runtime after generation
        return '"-"? [0-9]+ ("." [0-9]+)?'

    def _compile_max_length(self, constraint: MaxLengthConstraint) -> str:
        """Compile MAX_LENGTH constraint.

        Note: GBNF doesn't support bounded repetition like {0,N}.
        We approximate with unbounded pattern and note the limit.

        Args:
            constraint: MAX_LENGTH constraint

        Returns:
            GBNF pattern (unbounded, length checked at runtime)
        """
        # GBNF doesn't have {0,N} syntax - use * and note limit
        # Length validation happens at runtime
        return "[^\\n]*"

    def _compile_min_length(self, constraint: MinLengthConstraint) -> str:
        """Compile MIN_LENGTH constraint.

        Note: For min=1, use +. For min>1, we can't enforce exactly
        in GBNF, so validation happens at runtime.

        Args:
            constraint: MIN_LENGTH constraint

        Returns:
            GBNF pattern
        """
        if constraint.min_length >= 1:
            return "[^\\n]+"
        return "[^\\n]*"

    def _compile_date(self) -> str:
        """Compile DATE constraint to YYYY-MM-DD pattern."""
        return '[0-9][0-9][0-9][0-9] "-" [0-9][0-9] "-" [0-9][0-9]'

    def _compile_iso8601(self) -> str:
        """Compile ISO8601 constraint to datetime pattern."""
        # YYYY-MM-DD with optional Thh:mm:ss and timezone
        date = '[0-9][0-9][0-9][0-9] "-" [0-9][0-9] "-" [0-9][0-9]'
        time = '"T" [0-9][0-9] ":" [0-9][0-9] ":" [0-9][0-9]'
        tz = '("Z" | ("+" | "-") [0-9][0-9] ":" [0-9][0-9])?'
        return f"{date} ({time} {tz})?"

    def _escape_literal(self, value: str) -> str:
        """Escape special characters for GBNF literal.

        Args:
            value: String value to escape

        Returns:
            Escaped string safe for GBNF literal
        """
        # Escape backslashes first, then quotes
        result = value.replace("\\", "\\\\")
        result = result.replace('"', '\\"')
        return result

    def compile_chain(self, chain: ConstraintChain) -> str:
        """Compile constraint chain to GBNF rule fragment.

        For chains, we need to find the most restrictive pattern.
        ENUM and CONST take precedence over TYPE/REQ.

        Args:
            chain: Constraint chain to compile

        Returns:
            GBNF rule fragment representing the chain
        """
        if not chain.constraints:
            return "[^\\n]*"

        # Find the most specific constraint
        # Priority: CONST > ENUM > REGEX > TYPE > REQ > OPT
        for constraint in chain.constraints:
            if isinstance(constraint, ConstConstraint):
                return self.compile_constraint(constraint)

        for constraint in chain.constraints:
            if isinstance(constraint, EnumConstraint):
                return self.compile_constraint(constraint)

        for constraint in chain.constraints:
            if isinstance(constraint, RegexConstraint):
                return self.compile_constraint(constraint)

        for constraint in chain.constraints:
            if isinstance(constraint, TypeConstraint):
                return self.compile_constraint(constraint)

        for constraint in chain.constraints:
            if isinstance(constraint, DateConstraint | Iso8601Constraint):
                return self.compile_constraint(constraint)

        # Default to first constraint
        return self.compile_constraint(chain.constraints[0])

    def compile_schema(
        self,
        schema: "SchemaDefinition",
        include_envelope: bool = False,
    ) -> str:
        """Compile full schema to GBNF grammar.

        Args:
            schema: SchemaDefinition to compile
            include_envelope: Include OCTAVE document envelope (===NAME===...===END===)

        Returns:
            Complete GBNF grammar string
        """
        rules: list[str] = []

        # Add primitives
        rules.append("# GBNF Grammar for OCTAVE schema: " + schema.name)
        rules.append("")

        # Whitespace rule
        rules.append("ws ::= [ \\t\\n]*")
        rules.append("")

        # Build field rules
        field_rule_names: list[str] = []

        for field_name, field_def in schema.fields.items():
            rule_name = self._sanitize_rule_name(field_name)
            field_rule_names.append(rule_name)

            # Get constraint pattern
            if field_def.pattern and field_def.pattern.constraints:
                pattern = self.compile_chain(field_def.pattern.constraints)
            else:
                pattern = "[^\\n]*"

            # Create field rule: field-name ::= "FIELD_NAME" "::" ws pattern
            rules.append(f'{rule_name} ::= "{field_name}" "::" ws {pattern}')

        rules.append("")

        # Build content rule from fields
        if field_rule_names:
            # Fields can appear in any order, each is optional
            field_refs = " | ".join(field_rule_names)
            rules.append(f"field ::= ({field_refs})")
            rules.append("content ::= (field ws)*")
        else:
            rules.append("content ::= [^\\n]*")

        rules.append("")

        # Build document structure
        if include_envelope:
            schema_name = schema.name.upper()
            rules.append(f'envelope-start ::= "==={schema_name}==="')
            rules.append('envelope-end ::= "===END==="')
            rules.append("")
            rules.append('meta-block ::= "META:" ws meta-content')
            rules.append("meta-content ::= (meta-field ws)*")
            rules.append('meta-field ::= [A-Z_]+ "::" ws [^\\n]+')
            rules.append("")
            rules.append("document ::= envelope-start ws meta-block ws content ws envelope-end")
        else:
            rules.append("document ::= content")

        # Root rule
        rules.append("")
        rules.append("root ::= document")

        return "\n".join(rules)


def compile_gbnf_from_meta(meta: dict) -> str:
    """Compile GBNF grammar from META block.

    This is the integration point with grammar.py.

    Args:
        meta: META dictionary from parse_meta_only() or full parse

    Returns:
        GBNF grammar string
    """
    from octave_mcp.core.schema_extractor import SchemaDefinition

    schema_type = meta.get("TYPE", "UNKNOWN")

    # Create minimal schema from META
    schema = SchemaDefinition(
        name=schema_type,
        version=str(meta.get("VERSION", "1.0")),
    )

    compiler = GBNFCompiler()
    return compiler.compile_schema(schema, include_envelope=True)
