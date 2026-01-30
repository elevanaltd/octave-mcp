"""GBNF compiler for OCTAVE constraint chains (Issue #171, #191).

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

Issue #191: META CONTRACT Schema Compilation
v6 self-describing documents carry their own validation rules via META.CONTRACT.
CONTRACT is a list in META, format: FIELD[name]::constraint_chain.
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


# CONTRACT field parsing pattern: FIELD[name]::constraints
_CONTRACT_FIELD_PATTERN = re.compile(r"^FIELD\[([^\]]+)\]::(.+)$")


def _extract_contract_field_specs(contract: object) -> list[str]:
    """Extract field spec strings from CONTRACT value.

    CONTRACT can be either:
    - A list of strings (from programmatic use or dict)
    - A ListValue from parser (contains tokens that need reconstruction)

    Args:
        contract: CONTRACT value from META (list or ListValue)

    Returns:
        List of field spec strings like "FIELD[STATUS]::REQ∧ENUM[A,B]"
    """
    from octave_mcp.core.ast_nodes import ListValue

    # Handle plain list of strings
    if isinstance(contract, list):
        return [s for s in contract if isinstance(s, str)]

    # Handle ListValue from parser - need to reconstruct field specs from tokens
    if isinstance(contract, ListValue) and hasattr(contract, "tokens") and contract.tokens:
        return _reconstruct_field_specs_from_tokens(contract.tokens)

    # Handle ListValue with items (may have partial parsing)
    if isinstance(contract, ListValue) and contract.items:
        # Try to reconstruct from items
        return _reconstruct_field_specs_from_items(contract.items)

    return []


def _reconstruct_field_specs_from_tokens(tokens: list) -> list[str]:
    """Reconstruct FIELD[name]::constraints from token stream.

    Args:
        tokens: Token list from ListValue.tokens

    Returns:
        List of reconstructed field spec strings
    """
    from octave_mcp.core.lexer import TokenType

    field_specs = []
    current_spec_parts: list[str] = []
    in_field_brackets = False
    bracket_depth = 0

    for token in tokens:
        # Skip list delimiters and whitespace
        if token.type in (TokenType.LIST_START, TokenType.LIST_END, TokenType.NEWLINE, TokenType.INDENT):
            if token.type == TokenType.LIST_START and current_spec_parts:
                # Nested bracket (e.g., ENUM[...])
                in_field_brackets = True
                bracket_depth += 1
                current_spec_parts.append("[")
            elif token.type == TokenType.LIST_END and in_field_brackets:
                bracket_depth -= 1
                current_spec_parts.append("]")
                if bracket_depth == 0:
                    in_field_brackets = False
            continue

        # Comma separates field specs (when not in brackets)
        # But preserve commas inside brackets (e.g., ENUM[A,B,C])
        if token.type == TokenType.COMMA:
            if in_field_brackets:
                # Comma inside brackets - preserve it
                current_spec_parts.append(",")
            else:
                # Comma outside brackets - field spec separator
                if current_spec_parts:
                    spec = "".join(current_spec_parts).strip()
                    if spec:
                        field_specs.append(spec)
                    current_spec_parts = []
            continue

        # Build current field spec
        if token.type == TokenType.IDENTIFIER:
            current_spec_parts.append(token.value)
        elif token.type == TokenType.ASSIGN:
            current_spec_parts.append("::")
        elif token.type == TokenType.CONSTRAINT:
            current_spec_parts.append(token.value)  # ∧
        elif token.type == TokenType.FLOW:
            current_spec_parts.append(token.value)  # →
        elif token.type == TokenType.STRING:
            current_spec_parts.append(f'"{token.value}"')
        elif token.type == TokenType.NUMBER:
            current_spec_parts.append(str(token.value))
        elif token.type == TokenType.LIST_START:
            in_field_brackets = True
            bracket_depth += 1
            current_spec_parts.append("[")
        elif token.type == TokenType.LIST_END:
            bracket_depth -= 1
            current_spec_parts.append("]")
            if bracket_depth == 0:
                in_field_brackets = False

    # Don't forget the last field spec
    if current_spec_parts:
        spec = "".join(current_spec_parts).strip()
        if spec:
            field_specs.append(spec)

    return field_specs


def _reconstruct_field_specs_from_items(items: list) -> list[str]:
    """Reconstruct field specs from ListValue.items (fallback).

    This is less reliable than token reconstruction but works
    when tokens aren't available.

    Args:
        items: ListValue.items list

    Returns:
        List of field spec strings (may be incomplete)
    """
    # Items are already partially parsed - try to find FIELD patterns
    field_specs = []
    i = 0
    while i < len(items):
        item = items[i]
        if isinstance(item, str) and item == "FIELD":
            # Found start of a field spec, try to reconstruct
            # This is fragile but handles common cases
            spec_parts = ["FIELD"]
            i += 1
            # Collect until next FIELD or end
            while i < len(items):
                next_item = items[i]
                if isinstance(next_item, str) and next_item == "FIELD":
                    break
                if isinstance(next_item, str):
                    spec_parts.append(next_item)
                i += 1
            # Try to form a valid spec
            spec = "".join(spec_parts)
            if _CONTRACT_FIELD_PATTERN.match(spec):
                field_specs.append(spec)
        else:
            i += 1

    return field_specs


def parse_contract_field(field_spec: str) -> tuple[str, ConstraintChain | None]:
    """Parse a CONTRACT field specification into field name and constraints.

    CONTRACT field format: FIELD[name]::constraint_chain

    Args:
        field_spec: Field specification string (e.g., "FIELD[STATUS]::REQ∧ENUM[ACTIVE,PAUSED]")

    Returns:
        Tuple of (field_name, ConstraintChain or None)

    Raises:
        ValueError: If field_spec format is invalid

    Examples:
        >>> name, chain = parse_contract_field("FIELD[STATUS]::REQ∧ENUM[ACTIVE,PAUSED]")
        >>> name
        'STATUS'
        >>> len(chain.constraints)
        2
    """
    field_spec = field_spec.strip()

    match = _CONTRACT_FIELD_PATTERN.match(field_spec)
    if not match:
        raise ValueError(f"Invalid CONTRACT field format: '{field_spec}'. " f"Expected: FIELD[name]::constraint_chain")

    field_name = match.group(1).strip()
    constraint_str = match.group(2).strip()

    if not field_name:
        raise ValueError(f"Invalid CONTRACT field format: empty field name in '{field_spec}'")

    if not constraint_str:
        return field_name, None

    try:
        constraints = ConstraintChain.parse(constraint_str)
        return field_name, constraints
    except ValueError as e:
        raise ValueError(f"Invalid constraint in CONTRACT field '{field_name}': {e}") from e


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
    Supports v6 self-describing documents via META.CONTRACT (Issue #191).

    CONTRACT format: list of "FIELD[name]::constraint_chain" entries.
    Each entry defines a schema field with its validation constraints.

    Args:
        meta: META dictionary from parse_meta_only() or full parse.
              May contain CONTRACT list for v6 self-describing documents.

    Returns:
        GBNF grammar string with schema-specific field rules from CONTRACT.

    Example:
        >>> meta = {
        ...     "TYPE": "SESSION_LOG",
        ...     "VERSION": "1.0",
        ...     "CONTRACT": [
        ...         "FIELD[STATUS]::REQ∧ENUM[ACTIVE,PAUSED,COMPLETE]",
        ...         "FIELD[PRIORITY]::OPT∧ENUM[LOW,MEDIUM,HIGH]",
        ...     ],
        ... }
        >>> gbnf = compile_gbnf_from_meta(meta)
        >>> "status" in gbnf.lower()
        True
    """
    from octave_mcp.core.holographic import HolographicPattern
    from octave_mcp.core.schema_extractor import FieldDefinition, SchemaDefinition

    schema_type = meta.get("TYPE", "UNKNOWN")

    # Create schema from META
    schema = SchemaDefinition(
        name=schema_type,
        version=str(meta.get("VERSION", "1.0")),
    )

    # Issue #191: Extract fields from CONTRACT if present
    contract = meta.get("CONTRACT")
    if contract:
        # Handle CONTRACT as either list of strings or ListValue from parser
        field_specs = _extract_contract_field_specs(contract)
        for field_spec in field_specs:
            try:
                field_name, constraints = parse_contract_field(field_spec)

                # Create HolographicPattern to wrap constraints
                pattern = HolographicPattern(
                    example=None,  # CONTRACT doesn't include examples
                    constraints=constraints,
                    target=None,
                )

                # Add field to schema
                schema.fields[field_name] = FieldDefinition(
                    name=field_name,
                    pattern=pattern,
                    raw_value=field_spec,
                )
            except ValueError:
                # Skip invalid CONTRACT entries (lenient parsing)
                continue

    compiler = GBNFCompiler()
    return compiler.compile_schema(schema, include_envelope=True)
