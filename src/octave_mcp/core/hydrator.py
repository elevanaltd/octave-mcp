"""Vocabulary snapshot hydration for OCTAVE documents.

REFACTORED (ADR-003): Hermetic Anchoring - v0.4.0
- Removed: Complex dynamic resolution (Living Scrolls pattern)
- Added: Hermetic anchor loader with frozen@sha256 and latest support
- Enforced: BAN on network fetch in hot path
- Simplified: Local cache/pinned resource resolution only

Resolution modes:
- DEV: `standard: latest` → local toolchain defaults (no network)
- PROD: `standard: frozen@sha256:...` → verified cached resources

Transforms §CONTEXT::IMPORT[@namespace/name] directives into:
- §CONTEXT::SNAPSHOT[@namespace/name] with hydrated terms
- §SNAPSHOT::MANIFEST with provenance (SOURCE_URI, SOURCE_HASH, HYDRATION_TIME, HYDRATION_POLICY)
- §SNAPSHOT::PRUNED with available-but-unused terms

Key design decisions (LOCKED):
- COLLISION_DEFAULT = "error" (I3 compliance - no silent override)
- PRUNE_MANIFEST_DEFAULT = "list" (auditability)
- max_depth = 1 (single hop, no recursion for MVP)
- HERMETIC = true (no network access, local resolution only)
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


class SourceUriSecurityError(VocabularyError):
    """Raised when SOURCE_URI contains a security violation.

    Issue #48 CE Review BLOCKING: Prevents path traversal attacks via SOURCE_URI.
    Malicious documents could attempt to access sensitive files like /etc/passwd
    via absolute paths, path traversal (../../../), or symlinks.
    """

    def __init__(self, source_uri: str, reason: str):
        self.source_uri = source_uri
        self.reason = reason
        super().__init__(f"Security violation in SOURCE_URI '{source_uri}': {reason}")


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


class CycleDetectionError(VocabularyError):
    """Raised when circular import is detected.

    Issue #48 Task 2.12: Prevents infinite loops in recursive imports.

    Attributes:
        cycle_path: List of file paths showing the import chain that forms the cycle
    """

    def __init__(self, cycle_path: list[str]):
        self.cycle_path = cycle_path

        # Build descriptive message
        if len(cycle_path) == 1:
            # Self-import case
            super().__init__(f"Circular import detected: {cycle_path[0]} imports itself")
        else:
            # Multi-step cycle
            chain = " -> ".join(str(p) for p in cycle_path)
            super().__init__(f"Circular import detected: {chain}")


@dataclass
class HydrationPolicy:
    """Policy settings for vocabulary hydration.

    Attributes:
        prune_strategy: How to manifest pruned terms ("list" for MVP)
        collision_strategy: How to handle term collisions
        max_depth: Maximum recursion depth for transitive imports (1 for MVP)
    """

    prune_strategy: Literal["list", "hash", "count", "elide"] = "list"
    collision_strategy: Literal["error", "source_wins", "local_wins"] = "error"
    max_depth: int = 1


@dataclass
class StalenessResult:
    """Result of staleness check for a single snapshot.

    Issue #48 Task 2.8: Staleness detection for hydrated documents.

    Attributes:
        namespace: The vocabulary namespace (e.g., "@test/vocabulary")
        status: "FRESH" if hash matches, "STALE" if hash differs, "ERROR" on failure
        expected_hash: Hash stored in manifest (SOURCE_HASH)
        actual_hash: Current hash of source file (or None if error)
        error: Error message if status is "ERROR" (optional)
    """

    namespace: str
    status: Literal["FRESH", "STALE", "ERROR"]
    expected_hash: str
    actual_hash: str | None
    error: str | None = None


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


def resolve_hermetic_standard(standard_ref: str, cache_dir: Path | None = None) -> Path:
    """Resolve standard reference to local filesystem path (hermetic, no network).

    ADR-003: Hermetic Anchoring - enforces local-only resolution.

    Args:
        standard_ref: Either "latest" or "frozen@sha256:HASH"
        cache_dir: Optional cache directory (defaults to ~/.octave/standards/)

    Returns:
        Path to resolved standard file

    Raises:
        VocabularyError: If standard cannot be resolved locally or hash mismatch
    """
    if cache_dir is None:
        cache_dir = Path.home() / ".octave" / "standards"

    # Handle "latest" - use local toolchain default
    if standard_ref == "latest":
        # For dev mode, use bundled defaults or local cache
        default_path = cache_dir / "default.oct.md"
        if not default_path.exists():
            raise VocabularyError(
                f"Standard 'latest' not found in local cache: {default_path}. "
                "Run setup to initialize local standards cache."
            )
        return default_path

    # Handle "frozen@sha256:HASH" - verify pinned resource
    if standard_ref.startswith("frozen@sha256:"):
        # Security: validate full hash format to prevent path traversal.
        # Example malicious input: frozen@sha256:../evil
        m = re.fullmatch(r"frozen@sha256:([0-9a-fA-F]{64})", standard_ref)
        if m is None:
            raise VocabularyError(
                f"Invalid standard reference: {standard_ref}. " "Must be 'latest' (dev) or 'frozen@sha256:HASH' (prod)."
            )

        digest = m.group(1).lower()
        expected_hash = f"sha256:{digest}"

        # Look for cached file with this hash (first 16 hex chars for filename)
        cached_path = cache_dir / f"{digest[:16]}.oct.md"

        if not cached_path.exists():
            raise VocabularyError(
                f"Frozen standard not found in cache: {standard_ref}. "
                f"Expected at: {cached_path}. "
                "Hermetic mode forbids network fetch - pin resources during build."
            )

        # Verify hash matches
        actual_hash = compute_vocabulary_hash(cached_path)
        if actual_hash != expected_hash:
            raise VocabularyError(
                f"Hash mismatch for frozen standard: {standard_ref}. "
                f"Expected: {expected_hash}, Got: {actual_hash}. "
                "Cache corruption detected - re-pin resource."
            )

        return cached_path

    # Invalid format
    raise VocabularyError(
        f"Invalid standard reference: {standard_ref}. " "Must be 'latest' (dev) or 'frozen@sha256:HASH' (prod)."
    )


def validate_source_uri(source_uri: str, base_path: Path) -> Path:
    """Validate SOURCE_URI for security and return resolved path.

    Issue #48 CE Review FIX: Prevents path traversal attacks while allowing
    legitimate cross-directory layouts.

    Security checks performed:
    1. Reject absolute paths (e.g., /etc/passwd)
    2. Resolve path (following symlinks)
    3. Verify resolved path is within allowed base directory

    Note on ".." handling (Issue #48 CE Review FIX):
    - hydrate() generates SOURCE_URI with ".." for cross-directory layouts
      (e.g., vocab in specs/, output in docs/ -> "../specs/vocab.oct.md")
    - Security comes from verifying the RESOLVED path stays within base_path
    - Paths with ".." that resolve WITHIN base are ALLOWED (valid cross-directory)
    - Paths with ".." that resolve OUTSIDE base are REJECTED (path traversal attack)

    Args:
        source_uri: The SOURCE_URI string from manifest
        base_path: The allowed base directory (must be absolute)

    Returns:
        Resolved absolute Path to the file

    Raises:
        SourceUriSecurityError: If security violation detected
    """
    # Normalize base_path to absolute
    base_path = base_path.resolve()

    # Check 1: Reject absolute paths
    if source_uri.startswith("/") or (len(source_uri) > 1 and source_uri[1] == ":"):
        raise SourceUriSecurityError(
            source_uri,
            "absolute paths are not allowed for security reasons",
        )

    # Build candidate path (relative to base)
    # Note: ".." in source_uri is ALLOWED - security comes from Check 3 below
    candidate = base_path / source_uri

    # Check 2: Resolve and verify within base
    # resolve() follows symlinks and returns absolute path
    try:
        resolved = candidate.resolve()
    except (OSError, ValueError) as e:
        raise SourceUriSecurityError(
            source_uri,
            f"failed to resolve path: {e}",
        ) from e

    # Check 3: Verify resolved path is within base directory
    # THIS IS THE CRITICAL SECURITY CHECK - catches:
    # - Path traversal attacks (../../../etc/passwd)
    # - Symlink escapes (link pointing outside base)
    # - Any other mechanism that could escape base_path
    try:
        resolved.relative_to(base_path)
    except ValueError:
        raise SourceUriSecurityError(
            source_uri,
            "resolved path is outside allowed directory",
        ) from None

    return resolved


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
    output_path: Path | None = None,
    _visited: set[Path] | None = None,
) -> Document:
    """Hydrate a document by transforming IMPORT directives to SNAPSHOTs.

    Args:
        source_path: Path to source document with IMPORT directives
        registry: Vocabulary registry for namespace resolution
        policy: Hydration policy settings
        output_path: Path where hydrated document will be written (for relative SOURCE_URI)
        _visited: Internal parameter for cycle detection (set of already-visited paths)

    Returns:
        New Document with IMPORT replaced by SNAPSHOT + MANIFEST + PRUNED

    Raises:
        VocabularyError: If vocabulary cannot be resolved or parsed
        CollisionError: If term collision detected with 'error' strategy
        CycleDetectionError: If circular import is detected
    """
    # Issue #48 Task 2.12: Cycle detection
    # Initialize visited set on first call
    if _visited is None:
        _visited = set()

    # Resolve source path to absolute for consistent comparison
    source_resolved = source_path.resolve()

    # Check for cycle BEFORE processing
    if source_resolved in _visited:
        # Build cycle path from visited paths
        cycle_path = [str(p) for p in sorted(_visited)] + [str(source_resolved)]
        raise CycleDetectionError(cycle_path=cycle_path)

    # Mark current file as being processed
    _visited.add(source_resolved)

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

        # Issue #48 Task 2.12: Check for cycle in import target
        vocab_resolved = vocab_path.resolve()
        if vocab_resolved in _visited:
            # Cycle detected - import target is already in the chain
            cycle_path = [str(source_resolved), str(vocab_resolved)]
            raise CycleDetectionError(cycle_path=cycle_path)

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
        # Issue #48 Debate Decision: Store relative path (output_path or source_path as base)
        base_path = output_path if output_path else source_path
        manifest_section = _create_manifest_section(vocab_path, policy, imp.version, resolved_version, base_path)
        new_sections.append(manifest_section)

        # Create SNAPSHOT::PRUNED section (conditionally, based on strategy)
        # Issue #48 Task 2.11: Support prune_strategy options
        pruned_terms = set(vocab_terms.keys()) - used_terms
        pruned_section = _create_pruned_section(pruned_terms, policy.prune_strategy)
        if pruned_section is not None:
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
    base_path: Path | None = None,
) -> Section:
    """Create §SNAPSHOT::MANIFEST section.

    Issue #48: Now includes REQUESTED_VERSION and RESOLVED_VERSION fields.

    Issue #48 Debate Decision: SOURCE_URI stores a RELATIVE path for security.
    Absolute paths are forbidden during staleness checking to prevent
    path traversal attacks. The relative path is computed from base_path's
    parent directory (where the output file will be written).

    Args:
        vocab_path: Path to vocabulary file
        policy: Hydration policy settings
        requested_version: Version requested in IMPORT directive (or None)
        resolved_version: Version from registry (or None)
        base_path: Path to output file (for computing relative SOURCE_URI)

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

    # Issue #48 Debate Decision: Store relative path in SOURCE_URI for security
    # Compute relative path from output file's directory to vocabulary file
    if base_path is not None:
        base_dir = base_path.resolve().parent
        vocab_resolved = vocab_path.resolve()
        try:
            source_uri = str(vocab_resolved.relative_to(base_dir))
        except ValueError:
            # Vocab is outside base_dir, use os.path.relpath for cross-directory paths
            import os

            source_uri = os.path.relpath(vocab_resolved, base_dir)
    else:
        # Fallback: use absolute path (legacy behavior, will fail staleness check)
        source_uri = str(vocab_path)

    return Section(
        section_id="SNAPSHOT",
        key="MANIFEST",
        children=[
            Assignment(key="SOURCE_URI", value=source_uri),
            Assignment(key="SOURCE_HASH", value=compute_vocabulary_hash(vocab_path)),
            Assignment(key="HYDRATION_TIME", value=hydration_time),
            Assignment(key="REQUESTED_VERSION", value=requested_version_str),
            Assignment(key="RESOLVED_VERSION", value=resolved_version_str),
            policy_block,
        ],
    )


def _create_pruned_section(
    pruned_terms: set[str],
    strategy: Literal["list", "hash", "count", "elide"] = "list",
) -> Section | None:
    """Create SNAPSHOT::PRUNED section based on prune strategy.

    Issue #48 Task 2.11: Supports multiple prune manifest strategies.

    Args:
        pruned_terms: Set of term names that were not used
        strategy: How to manifest pruned terms:
            - "list": List all pruned term names in TERMS field (default)
            - "hash": Create HASH field with SHA256 of sorted term names
            - "count": Create COUNT field with integer count
            - "elide": Return None (don't include PRUNED section)

    Returns:
        Section with pruned information, or None for "elide" strategy
    """
    if strategy == "elide":
        return None

    # Sort terms for deterministic output
    sorted_terms = sorted(pruned_terms)

    if strategy == "list":
        # Default: list all pruned term names
        terms_list = ListValue(items=sorted_terms)
        return Section(
            section_id="SNAPSHOT",
            key="PRUNED",
            children=[
                Assignment(key="TERMS", value=terms_list),
            ],
        )

    elif strategy == "hash":
        # Create SHA256 hash of sorted term names
        # Hash the joined sorted term names for compact representation
        terms_string = ",".join(sorted_terms)
        hash_digest = hashlib.sha256(terms_string.encode("utf-8")).hexdigest()
        hash_value = f"sha256:{hash_digest}"
        return Section(
            section_id="SNAPSHOT",
            key="PRUNED",
            children=[
                Assignment(key="HASH", value=hash_value),
            ],
        )

    elif strategy == "count":
        # Just the count of pruned terms
        return Section(
            section_id="SNAPSHOT",
            key="PRUNED",
            children=[
                Assignment(key="COUNT", value=len(sorted_terms)),
            ],
        )

    else:
        # Issue #48 CE Review H1: Invalid strategy must fail loudly, not silent fallback
        raise VocabularyError(f"Invalid prune_strategy: {strategy!r}. " "Expected one of: list, hash, count, elide")


def check_staleness(
    doc: Document,
    base_path: Path | None = None,
    allowed_root: Path | None = None,
) -> list[StalenessResult]:
    """Check staleness of all SNAPSHOT manifests in a hydrated document.

    Issue #48 Task 2.8: Staleness detection for hydrated documents.
    Issue #48 CE Review: base_path parameter for security-compliant path resolution.
    Issue #48 CE Security Fix: allowed_root parameter for post-resolution containment.

    Parses the document to find §SNAPSHOT::MANIFEST sections, extracts
    SOURCE_URI and SOURCE_HASH from each, computes current hash of source
    file, and compares to determine if snapshot is stale.

    Security model:
    - Absolute paths are FORBIDDEN (rejected before resolution)
    - Relative paths with ".." ARE ALLOWED for cross-directory layouts
    - After resolution, path MUST be within allowed_root (containment check)
    - This prevents crafted paths like "../../../etc/passwd" from escaping

    Args:
        doc: Parsed OCTAVE document (already hydrated)
        base_path: Base directory for resolving relative SOURCE_URI paths.
                   If None, uses current working directory.
        allowed_root: Root directory for containment check. Resolved paths
                      must be within this directory. If None, defaults to base_path.

    Returns:
        List of StalenessResult, one per SNAPSHOT/MANIFEST pair found.
        Empty list if no snapshots found in document.
    """
    results: list[StalenessResult] = []

    # Track current namespace as we iterate through sections
    # SNAPSHOT sections come before their MANIFEST sections
    current_namespace: str | None = None

    for section in doc.sections:
        if isinstance(section, Section):
            # Detect §CONTEXT::SNAPSHOT["@namespace/name"]
            if section.section_id == "CONTEXT" and section.key == "SNAPSHOT":
                # Extract namespace from annotation like: "@test/vocabulary"
                # The annotation field contains the quoted namespace
                namespace = _extract_namespace_from_annotation(section.annotation)
                if namespace:
                    current_namespace = namespace

            # Detect §SNAPSHOT::MANIFEST
            elif section.section_id == "SNAPSHOT" and section.key == "MANIFEST":
                # Extract SOURCE_URI and SOURCE_HASH from manifest
                source_uri = None
                source_hash = None

                for child in section.children:
                    if isinstance(child, Assignment):
                        if child.key == "SOURCE_URI":
                            source_uri = child.value
                        elif child.key == "SOURCE_HASH":
                            source_hash = child.value

                namespace = current_namespace or "unknown"

                # Issue #48 CE Review BLOCKING: Emit ERROR for malformed manifests
                # instead of silently skipping them
                if not source_uri or (isinstance(source_uri, str) and not source_uri.strip()):
                    results.append(
                        StalenessResult(
                            namespace=namespace,
                            status="ERROR",
                            expected_hash=source_hash or "missing",
                            actual_hash=None,
                            error="Malformed manifest: missing or empty SOURCE_URI",
                        )
                    )
                elif not source_hash or (isinstance(source_hash, str) and not source_hash.strip()):
                    results.append(
                        StalenessResult(
                            namespace=namespace,
                            status="ERROR",
                            expected_hash="missing",
                            actual_hash=None,
                            error="Malformed manifest: missing or empty SOURCE_HASH",
                        )
                    )
                else:
                    # Check if source file exists and compute hash
                    # Issue #48 CE Security Fix: Pass allowed_root for containment check
                    result = _check_single_snapshot(
                        namespace=namespace,
                        source_uri=source_uri,
                        expected_hash=source_hash,
                        base_path=base_path,
                        allowed_root=allowed_root,
                    )
                    results.append(result)

    return results


def _extract_namespace_from_annotation(annotation: str | None) -> str | None:
    """Extract namespace from section annotation like '"@test/vocabulary"'.

    The parser stores annotations without brackets, so we just need to
    strip the surrounding quotes.

    Args:
        annotation: Section annotation string (may be quoted)

    Returns:
        Extracted namespace or None if not found
    """
    if not annotation:
        return None

    # Remove surrounding quotes if present
    namespace = annotation.strip()
    if namespace.startswith('"') and namespace.endswith('"'):
        namespace = namespace[1:-1]
    return namespace if namespace else None


def _extract_namespace_from_snapshot_key(key: str) -> str | None:
    """Extract namespace from SNAPSHOT key like 'SNAPSHOT["@test/vocabulary"]'.

    Args:
        key: Section key containing namespace

    Returns:
        Extracted namespace or None if not found
    """
    # Match pattern: SNAPSHOT["@namespace/name"]
    match = re.match(r'SNAPSHOT\["([^"]+)"\]', key)
    if match:
        return match.group(1)
    return None


def _check_single_snapshot(
    namespace: str,
    source_uri: str,
    expected_hash: str,
    base_path: Path | None = None,
    allowed_root: Path | None = None,
) -> StalenessResult:
    """Check staleness of a single snapshot.

    Issue #48 CE Review FIX: Secure path resolution for staleness checking.
    Issue #48 CE Security Fix: Post-resolution containment enforcement.

    Security model for staleness checking:
    - Absolute paths are FORBIDDEN (prevents /etc/passwd style attacks)
    - Relative paths with ".." ARE ALLOWED (cross-directory layouts)
    - Path is resolved relative to base_path (follows symlinks)
    - AFTER resolution, path MUST be within allowed_root (containment check)
    - Error messages do NOT echo raw paths (prevents information leakage)

    Note on ".." handling (Issue #48 CE Review FIX):
    - hydrate() generates SOURCE_URI with ".." for cross-directory layouts
      (e.g., vocab in specs/, output in docs/ -> "../specs/vocab.oct.md")
    - The old blanket rejection of ".." broke these valid workflows
    - Security now comes from: (1) rejecting absolute paths,
      (2) post-resolution containment check, (3) hash verification

    Difference from validate_source_uri():
    - validate_source_uri() enforces strict base containment (for user input)
    - _check_single_snapshot() uses allowed_root for containment (more flexible)
    - Both reject absolute paths for security

    Args:
        namespace: Vocabulary namespace
        source_uri: Path to source file from manifest
        expected_hash: Hash stored in manifest
        base_path: Optional base path for resolving relative SOURCE_URI paths
        allowed_root: Root directory for containment check. Resolved paths must
                      be within this directory. If None, defaults to base_path.

    Returns:
        StalenessResult with FRESH, STALE, or ERROR status
    """
    if base_path is None:
        base_path = Path.cwd()

    # Issue #48 CE Review FIX: Reject absolute paths (security)
    # Do NOT echo the raw path in error messages (prevents information leakage)
    if source_uri.startswith("/") or (len(source_uri) > 1 and source_uri[1] == ":"):
        return StalenessResult(
            namespace=namespace,
            status="ERROR",
            expected_hash=expected_hash,
            actual_hash=None,
            error="Security violation: absolute SOURCE_URI paths are not allowed",
        )

    # Issue #48 CE Review FIX: Resolve path relative to base_path
    # ".." patterns ARE ALLOWED for cross-directory layouts (vocab in specs/, output in docs/)
    # Security now comes from: (1) rejecting absolute paths,
    # (2) post-resolution containment check, (3) hash verification
    try:
        candidate = base_path / source_uri
        source_path = candidate.resolve()  # Follows symlinks
    except (OSError, ValueError) as e:
        return StalenessResult(
            namespace=namespace,
            status="ERROR",
            expected_hash=expected_hash,
            actual_hash=None,
            error=f"Security violation: failed to resolve path: {e}",
        )

    # Issue #48 CE Security Fix: Post-resolution containment check
    # CRITICAL: This check MUST happen BEFORE checking if file exists
    # Otherwise, an attacker could access existing files outside the project
    # Default allowed_root to base_path for backwards compatibility
    effective_root = (allowed_root or base_path).resolve()
    try:
        source_path.relative_to(effective_root)
    except ValueError:
        # Path escapes allowed_root - this is a security violation
        return StalenessResult(
            namespace=namespace,
            status="ERROR",
            expected_hash=expected_hash,
            actual_hash=None,
            error=f"Security violation: resolved path escapes allowed root for {namespace}",
        )

    # Check if source file exists
    if not source_path.exists():
        # Issue #48 CE Review FIX: Do not echo source_uri in error message
        return StalenessResult(
            namespace=namespace,
            status="ERROR",
            expected_hash=expected_hash,
            actual_hash=None,
            error=f"Source file not found for namespace: {namespace}",
        )

    try:
        # Compute current hash
        actual_hash = compute_vocabulary_hash(source_path)

        # Compare hashes
        if actual_hash == expected_hash:
            return StalenessResult(
                namespace=namespace,
                status="FRESH",
                expected_hash=expected_hash,
                actual_hash=actual_hash,
            )
        else:
            return StalenessResult(
                namespace=namespace,
                status="STALE",
                expected_hash=expected_hash,
                actual_hash=actual_hash,
            )

    except Exception as e:
        return StalenessResult(
            namespace=namespace,
            status="ERROR",
            expected_hash=expected_hash,
            actual_hash=None,
            error=str(e),
        )
