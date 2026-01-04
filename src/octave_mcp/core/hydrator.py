"""Vocabulary snapshot hydration for OCTAVE documents.

Issue #48 Phase 1: Implements the "Living Scrolls" pattern for vocabulary sharing.

Transforms §CONTEXT::IMPORT[@namespace/name] directives into:
- §CONTEXT::SNAPSHOT[@namespace/name] with hydrated terms
- §SNAPSHOT::MANIFEST with provenance (SOURCE_URI, SOURCE_HASH, HYDRATION_TIME, HYDRATION_POLICY)
- §SNAPSHOT::PRUNED with available-but-unused terms

Key design decisions (LOCKED):
- COLLISION_DEFAULT = "error" (I3 compliance - no silent override)
- PRUNE_MANIFEST_DEFAULT = "list" (auditability)
- max_depth = 1 (single hop, no recursion for MVP)
"""

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from octave_mcp.core.ast_nodes import Assignment, ASTNode, Block, Document, ListValue, Section
from octave_mcp.core.parser import parse


class VocabularyError(Exception):
    """Base exception for vocabulary-related errors."""

    pass


class CollisionError(VocabularyError):
    """Raised when term collision is detected with 'error' strategy."""

    def __init__(
        self,
        term: str,
        local_def: str,
        imported_def: str,
        all_collisions: list[str] | None = None,
    ):
        self.term = term
        self.local_def = local_def
        self.imported_def = imported_def
        self.all_collisions = all_collisions or [term]

        # Build message showing first collision in detail, plus list of all collisions
        if len(self.all_collisions) > 1:
            all_terms = ", ".join(f"'{t}'" for t in self.all_collisions)
            super().__init__(
                f"Term collision detected: {len(self.all_collisions)} terms conflict. "
                f"Colliding terms: {all_terms}. "
                f"First collision '{term}': Local: {local_def!r}, Imported: {imported_def!r}"
            )
        else:
            super().__init__(
                f"Term collision detected: '{term}' is defined both locally and in imported vocabulary. "
                f"Local: {local_def!r}, Imported: {imported_def!r}"
            )


class VersionMismatchError(VocabularyError):
    """Raised when requested version doesn't match registry version.

    Issue #48: Version string handling for deterministic vocabulary resolution.
    """

    def __init__(
        self,
        namespace: str,
        requested_version: str,
        registry_version: str | None,
    ):
        self.namespace = namespace
        self.requested_version = requested_version
        self.registry_version = registry_version

        if registry_version is None:
            super().__init__(
                f"Version mismatch for '{namespace}': "
                f"requested version '{requested_version}' but registry has no version information"
            )
        else:
            super().__init__(
                f"Version mismatch for '{namespace}': "
                f"requested version '{requested_version}' but registry has version '{registry_version}'"
            )


@dataclass
class HydrationPolicy:
    """Policy settings for vocabulary hydration.

    Attributes:
        prune_strategy: How to manifest pruned terms ("list" for MVP)
        collision_strategy: How to handle term collisions
        max_depth: Maximum recursion depth for transitive imports (1 for MVP)
    """

    prune_strategy: Literal["list"] = "list"  # hash/count/elide in Phase 2
    collision_strategy: Literal["error", "source_wins", "local_wins"] = "error"
    max_depth: int = 1


@dataclass
class ImportDirective:
    """Parsed import directive information.

    Attributes:
        namespace: The import namespace (e.g., "@core/meta")
        version: Optional version specifier (e.g., "1.0.0")
        section: Reference to the original Section AST node
    """

    namespace: str
    version: str | None = None
    section: Section | None = None


@dataclass
class VocabularyEntry:
    """Entry in the vocabulary registry.

    Attributes:
        path: Path to vocabulary file
        version: Optional semantic version string
    """

    path: Path
    version: str | None = None


class VocabularyRegistry:
    """Registry for resolving vocabulary namespaces to file paths.

    Supports two modes:
    1. Registry file mode: Parses specs/vocabularies/registry.oct.md
    2. Direct mapping mode: Uses explicit namespace -> path mapping

    Issue #48: Now supports version information for deterministic resolution.
    """

    def __init__(self, registry_path: Path | None = None):
        """Initialize registry from registry file.

        Args:
            registry_path: Path to registry.oct.md file
        """
        self.registry_path = registry_path
        self._entries: dict[str, VocabularyEntry] = {}

        if registry_path and registry_path.exists():
            self._load_registry(registry_path)

    @classmethod
    def from_mappings(cls, mappings: dict[str, Path]) -> "VocabularyRegistry":
        """Create registry from direct namespace -> path mappings.

        Backwards-compatible API that creates entries without version info.

        Args:
            mappings: Dictionary of namespace to Path mappings

        Returns:
            VocabularyRegistry instance with the provided mappings
        """
        registry = cls(registry_path=None)
        for namespace, path in mappings.items():
            registry._entries[namespace] = VocabularyEntry(path=path, version=None)
        return registry

    @classmethod
    def from_mappings_with_versions(cls, mappings: dict[str, dict[str, Any]]) -> "VocabularyRegistry":
        """Create registry from mappings that include version information.

        Issue #48: New API for version-aware resolution.

        Args:
            mappings: Dictionary of namespace to {"path": Path, "version": str}

        Returns:
            VocabularyRegistry instance with versioned entries
        """
        registry = cls(registry_path=None)
        for namespace, entry_data in mappings.items():
            registry._entries[namespace] = VocabularyEntry(
                path=entry_data["path"],
                version=entry_data.get("version"),
            )
        return registry

    def _load_registry(self, registry_path: Path) -> None:
        """Load vocabulary mappings from registry file."""
        content = registry_path.read_text(encoding="utf-8")
        doc = parse(content)

        # Extract vocabulary entries from registry structure
        for section in doc.sections:
            if isinstance(section, Section):
                self._extract_vocabulary_entries(section, registry_path.parent)

    def _extract_vocabulary_entries(self, section: Section, base_path: Path) -> None:
        """Extract vocabulary entries from registry section.

        Issue #48: Now extracts VERSION field in addition to NAME and PATH.
        """
        # Look for NAME, PATH, and VERSION assignments in nested sections
        for child in section.children:
            if isinstance(child, Section):
                name = None
                path = None
                version = None
                for grandchild in child.children:
                    if isinstance(grandchild, Assignment):
                        if grandchild.key == "NAME":
                            name = grandchild.value
                        elif grandchild.key == "PATH":
                            path = grandchild.value
                        elif grandchild.key == "VERSION":
                            version = grandchild.value

                if name and path:
                    # Build namespace from section structure
                    # e.g., §2a::SNAPSHOT -> @core/SNAPSHOT
                    namespace = f"@core/{name}"
                    self._entries[namespace] = VocabularyEntry(
                        path=base_path / path,
                        version=version,
                    )

            # Recurse into nested sections
            if isinstance(child, Section):
                self._extract_vocabulary_entries(child, base_path)

    def resolve(self, namespace: str, requested_version: str | None = None) -> tuple[Path, str | None]:
        """Resolve namespace to file path and version.

        Issue #48: Now returns tuple of (path, version) and validates version match.

        Args:
            namespace: Vocabulary namespace (e.g., "@core/meta")
            requested_version: Optional version to validate against

        Returns:
            Tuple of (Path to vocabulary file, resolved version or None)

        Raises:
            VocabularyError: If namespace cannot be resolved
            VersionMismatchError: If requested version doesn't match registry version
        """
        if namespace not in self._entries:
            raise VocabularyError(f"Unknown vocabulary namespace: {namespace}")

        entry = self._entries[namespace]

        # Version validation if version was requested
        if requested_version is not None:
            if entry.version is None:
                # Registry has no version but caller requested one
                raise VersionMismatchError(
                    namespace=namespace,
                    requested_version=requested_version,
                    registry_version=None,
                )
            if entry.version != requested_version:
                # Version mismatch
                raise VersionMismatchError(
                    namespace=namespace,
                    requested_version=requested_version,
                    registry_version=entry.version,
                )

        return entry.path, entry.version


def compute_vocabulary_hash(vocab_path: Path, chunk_size: int = 8192) -> str:
    """Compute SHA-256 hash of vocabulary file using streaming.

    Uses chunked reading to avoid loading entire file into memory,
    which is critical for large vocabulary files (100MB+).

    Args:
        vocab_path: Path to vocabulary file
        chunk_size: Size of chunks to read (default 8KB)

    Returns:
        Hash string in format "sha256:HEXDIGEST"
    """
    hasher = hashlib.sha256()
    with open(vocab_path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return f"sha256:{hasher.hexdigest()}"


def parse_vocabulary(vocab_path: Path) -> dict[str, str]:
    """Parse vocabulary capsule and extract term definitions.

    Args:
        vocab_path: Path to vocabulary capsule file

    Returns:
        Dictionary of term names to definitions

    Raises:
        VocabularyError: If file is not a valid CAPSULE
    """
    content = vocab_path.read_text(encoding="utf-8")
    doc = parse(content)

    # Validate META.TYPE == "CAPSULE"
    if "TYPE" not in doc.meta:
        raise VocabularyError("Vocabulary file is not a CAPSULE: missing META.TYPE")

    meta_type = doc.meta.get("TYPE")
    if meta_type != "CAPSULE":
        raise VocabularyError(f"Vocabulary file is not a CAPSULE: META.TYPE is '{meta_type}'")

    # Extract terms from all sections
    terms: dict[str, str] = {}

    for section in doc.sections:
        if isinstance(section, Section):
            _extract_terms_from_section(section, terms)

    return terms


def _extract_terms_from_section(section: Section, terms: dict[str, str]) -> None:
    """Recursively extract term definitions from a section."""
    for child in section.children:
        if isinstance(child, Assignment):
            # Term definitions are KEY::"definition"
            terms[child.key] = child.value
        elif isinstance(child, Section):
            # Recurse into nested sections
            _extract_terms_from_section(child, terms)


def find_imports(doc: Document) -> list[ImportDirective]:
    """Find all §CONTEXT::IMPORT directives in document.

    Args:
        doc: Parsed OCTAVE document

    Returns:
        List of ImportDirective objects
    """
    imports: list[ImportDirective] = []

    for section in doc.sections:
        if isinstance(section, Section):
            if section.section_id == "CONTEXT" and section.key.startswith("IMPORT"):
                directive = _parse_import_directive(section)
                if directive:
                    imports.append(directive)

    return imports


def _parse_import_directive(section: Section) -> ImportDirective | None:
    """Parse import directive from section.

    Expected formats:
    - §CONTEXT::IMPORT["@namespace/name"]
    - §CONTEXT::IMPORT["@namespace/name","version"]

    The annotation is captured by the parser and stored in section.annotation.
    The format uses quoted strings to allow special characters like '/'.
    """
    # Extract annotation from section
    # The parser captures bracket annotation content as a string
    key = section.key

    # Handle case where annotation is in section.annotation
    if section.annotation:
        annotation = section.annotation
    else:
        # Try to extract from key
        match = re.match(r"IMPORT\[(.+)\]", key)
        if not match:
            return None
        annotation = match.group(1)

    # Parse annotation content - may contain quoted strings
    # Format: "namespace" or "namespace","version"
    # Remove surrounding quotes from each part
    parts = _parse_annotation_parts(annotation)

    if not parts:
        return None

    namespace = parts[0]
    version = parts[1] if len(parts) > 1 else None

    return ImportDirective(namespace=namespace, version=version, section=section)


def _parse_annotation_parts(annotation: str) -> list[str]:
    """Parse annotation content into parts, handling quoted strings.

    Args:
        annotation: Raw annotation content like '"@ns/name","1.0.0"'

    Returns:
        List of unquoted parts
    """
    parts: list[str] = []
    current = ""
    in_quotes = False

    for char in annotation:
        if char == '"':
            in_quotes = not in_quotes
        elif char == "," and not in_quotes:
            if current.strip():
                parts.append(current.strip())
            current = ""
        else:
            current += char

    if current.strip():
        parts.append(current.strip())

    return parts


def detect_used_terms(doc: Document, available_terms: set[str]) -> set[str]:
    """Detect which terms from vocabulary are used in document.

    Scans the document for references to term names in:
    - Assignment keys
    - Assignment values (strings)
    - Block/Section content

    Args:
        doc: Parsed OCTAVE document
        available_terms: Set of available term names

    Returns:
        Set of terms that are used in the document
    """
    used: set[str] = set()

    # Build a set for fast lookup
    term_set = set(available_terms)

    # Scan all content
    _scan_for_terms(doc.sections, term_set, used)

    # Also check META
    for key, value in doc.meta.items():
        if key in term_set:
            used.add(key)
        if isinstance(value, str):
            for term in term_set:
                if term in value:
                    used.add(term)

    return used


def _scan_for_terms(nodes: list[Any], term_set: set[str], used: set[str]) -> None:
    """Recursively scan nodes for term usage."""
    for node in nodes:
        if isinstance(node, Assignment):
            # Check key
            if node.key in term_set:
                used.add(node.key)
            # Check value
            _check_value_for_terms(node.value, term_set, used)
        elif isinstance(node, Block):
            # Check block key
            if node.key in term_set:
                used.add(node.key)
            # Recurse into children
            _scan_for_terms(node.children, term_set, used)
        elif isinstance(node, Section):
            # Check section key
            if node.key in term_set:
                used.add(node.key)
            # Recurse into children
            _scan_for_terms(node.children, term_set, used)


def _check_value_for_terms(value: Any, term_set: set[str], used: set[str]) -> None:
    """Check a value for term references."""
    if isinstance(value, str):
        for term in term_set:
            if term in value:
                used.add(term)
    elif isinstance(value, ListValue):
        for item in value.items:
            _check_value_for_terms(item, term_set, used)


def detect_collisions(doc: Document, imported_terms: set[str]) -> set[str]:
    """Detect term collisions between imported and local terms.

    Scans §CONTEXT::LOCAL section for term definitions that conflict
    with imported terms.

    Args:
        doc: Parsed OCTAVE document
        imported_terms: Set of term names being imported

    Returns:
        Set of colliding term names
    """
    collisions: set[str] = set()

    for section in doc.sections:
        if isinstance(section, Section):
            if section.section_id == "CONTEXT" and section.key == "LOCAL":
                # Check children for conflicting definitions
                for child in section.children:
                    if isinstance(child, Assignment):
                        if child.key in imported_terms:
                            collisions.add(child.key)

    return collisions


def _get_local_definitions(doc: Document) -> dict[str, str]:
    """Extract local term definitions from §CONTEXT::LOCAL."""
    local_defs: dict[str, str] = {}

    for section in doc.sections:
        if isinstance(section, Section):
            if section.section_id == "CONTEXT" and section.key == "LOCAL":
                for child in section.children:
                    if isinstance(child, Assignment):
                        local_defs[child.key] = child.value

    return local_defs


def hydrate(
    source_path: Path,
    registry: VocabularyRegistry,
    policy: HydrationPolicy,
) -> Document:
    """Hydrate a document by transforming IMPORT directives to SNAPSHOTs.

    Args:
        source_path: Path to source document with IMPORT directives
        registry: Vocabulary registry for namespace resolution
        policy: Hydration policy settings

    Returns:
        New Document with IMPORT replaced by SNAPSHOT + MANIFEST + PRUNED

    Raises:
        VocabularyError: If vocabulary cannot be resolved or parsed
        CollisionError: If term collision detected with 'error' strategy
    """
    # Read and parse source document
    content = source_path.read_text(encoding="utf-8")
    doc = parse(content)

    # Find all import directives
    imports = find_imports(doc)

    if not imports:
        # No imports to hydrate
        return doc

    # Process each import
    new_sections: list[Section | Assignment | Block] = []
    local_defs = _get_local_definitions(doc)

    for imp in imports:
        # Resolve namespace to path, passing version for validation
        # Issue #48: Version handling - pass version to resolve for validation
        vocab_path, resolved_version = registry.resolve(imp.namespace, imp.version)

        # Parse vocabulary
        vocab_terms = parse_vocabulary(vocab_path)

        # Check for collisions
        collisions = set(vocab_terms.keys()) & set(local_defs.keys())

        if collisions:
            if policy.collision_strategy == "error":
                # I2 compliance: Use sorted() for deterministic error reporting
                sorted_collisions = sorted(collisions)
                term = sorted_collisions[0]
                raise CollisionError(
                    term=term,
                    local_def=local_defs[term],
                    imported_def=vocab_terms[term],
                    all_collisions=sorted_collisions,
                )
            # For source_wins/local_wins, we continue with appropriate filtering
            # (handled below when building snapshot)

        # Detect which terms are used (both from vocab and local definitions)
        all_available_terms = set(vocab_terms.keys()) | set(local_defs.keys())
        used_terms = detect_used_terms(doc, all_available_terms)

        # Build SNAPSHOT section with used terms only
        # I3 compliance: When local_wins, merge local defs INTO snapshot for self-contained output
        snapshot_children: list[ASTNode] = []
        for term, definition in vocab_terms.items():
            if term in used_terms:
                # Apply collision strategy
                if term in collisions:
                    if policy.collision_strategy == "local_wins":
                        # Use local definition instead of imported
                        snapshot_children.append(Assignment(key=term, value=local_defs[term]))
                        continue
                    # source_wins: use imported definition
                snapshot_children.append(Assignment(key=term, value=definition))

        # Also add used local terms that DON'T collide (they're not in vocab_terms)
        for term, definition in local_defs.items():
            if term in used_terms and term not in vocab_terms:
                snapshot_children.append(Assignment(key=term, value=definition))

        # Create §CONTEXT::SNAPSHOT section
        # Quote the namespace to preserve special characters like '/'
        snapshot_section = Section(
            section_id="CONTEXT",
            key=f'SNAPSHOT["{imp.namespace}"]',
            children=snapshot_children,
        )
        new_sections.append(snapshot_section)

        # Create §SNAPSHOT::MANIFEST section
        # Issue #48: Pass version information to manifest
        manifest_section = _create_manifest_section(vocab_path, policy, imp.version, resolved_version)
        new_sections.append(manifest_section)

        # Create §SNAPSHOT::PRUNED section
        pruned_terms = set(vocab_terms.keys()) - used_terms
        pruned_section = _create_pruned_section(pruned_terms)
        new_sections.append(pruned_section)

    # Build new document with SNAPSHOT replacing IMPORT
    result = Document(
        name=doc.name,
        meta=doc.meta.copy(),
        has_separator=doc.has_separator,
    )

    # Add hydrated sections
    for section in doc.sections:
        if isinstance(section, Section):
            if section.section_id == "CONTEXT" and section.key.startswith("IMPORT"):
                # Skip - will be replaced by SNAPSHOT
                continue
            if section.section_id == "CONTEXT" and section.key == "LOCAL":
                # Skip LOCAL sections (terms are resolved)
                continue

        result.sections.append(section)

    # Insert new sections after META (at the beginning of sections)
    result.sections = new_sections + result.sections

    return result


def _create_manifest_section(
    vocab_path: Path,
    policy: HydrationPolicy,
    requested_version: str | None = None,
    resolved_version: str | None = None,
) -> Section:
    """Create §SNAPSHOT::MANIFEST section.

    Issue #48: Now includes REQUESTED_VERSION and RESOLVED_VERSION fields.

    Args:
        vocab_path: Path to vocabulary file
        policy: Hydration policy settings
        requested_version: Version requested in IMPORT directive (or None)
        resolved_version: Version from registry (or None)

    Returns:
        Section with manifest information
    """
    now = datetime.now(UTC)
    hydration_time = now.isoformat()

    # Build policy block
    policy_block = Block(
        key="HYDRATION_POLICY",
        children=[
            Assignment(key="DEPTH", value=policy.max_depth),
            Assignment(key="PRUNE", value=policy.prune_strategy),
            Assignment(key="COLLISION", value=policy.collision_strategy),
        ],
    )

    # Issue #48: Version fields in manifest
    # REQUESTED_VERSION: what the IMPORT directive specified (or "unspecified")
    # RESOLVED_VERSION: what the registry provided (or "unknown")
    requested_version_str = requested_version if requested_version else "unspecified"
    resolved_version_str = resolved_version if resolved_version else "unknown"

    return Section(
        section_id="SNAPSHOT",
        key="MANIFEST",
        children=[
            Assignment(key="SOURCE_URI", value=str(vocab_path)),
            Assignment(key="SOURCE_HASH", value=compute_vocabulary_hash(vocab_path)),
            Assignment(key="HYDRATION_TIME", value=hydration_time),
            Assignment(key="REQUESTED_VERSION", value=requested_version_str),
            Assignment(key="RESOLVED_VERSION", value=resolved_version_str),
            policy_block,
        ],
    )


def _create_pruned_section(pruned_terms: set[str]) -> Section:
    """Create §SNAPSHOT::PRUNED section."""
    # Create sorted list of pruned terms
    terms_list = ListValue(items=sorted(pruned_terms))

    return Section(
        section_id="SNAPSHOT",
        key="PRUNED",
        children=[
            Assignment(key="TERMS", value=terms_list),
        ],
    )
