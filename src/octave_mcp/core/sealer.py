"""SEAL cryptographic integrity layer for OCTAVE documents.

Issue #48 Phase 2 Batch 2: Implements document sealing and verification.

The SEAL section provides cryptographic proof that document content
has not been modified since sealing. Uses SHA256 hashing.

Section format:
    SEAL:
      SCOPE::LINES[1,N]
      ALGORITHM::SHA256
      HASH::"hexdigest..."
      GRAMMAR::5.1.0  # Optional, from document grammar_version
"""

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Any

from octave_mcp.core.ast_nodes import Assignment, ASTNode, Document, Section
from octave_mcp.core.emitter import emit


class SealStatus(Enum):
    """Result status from seal verification."""

    VERIFIED = "VERIFIED"
    INVALID = "INVALID"
    NO_SEAL = "NO_SEAL"


@dataclass
class SealVerificationResult:
    """Result of seal verification."""

    status: SealStatus
    expected_hash: str | None = None
    actual_hash: str | None = None
    message: str | None = None


def compute_seal(content: str, grammar_version: str | None) -> dict[str, Any]:
    """Compute SEAL data for normalized content.

    The seal provides cryptographic integrity verification for OCTAVE documents.
    Content should be in canonical form (from emitter) before sealing.

    Args:
        content: Canonicalized document content to seal
        grammar_version: Optional grammar version to include in seal

    Returns:
        Dict with SCOPE, ALGORITHM, HASH, and optionally GRAMMAR
    """
    lines = content.split("\n")
    line_count = len(lines)

    # Compute SHA256 hash of entire content
    hash_value = hashlib.sha256(content.encode("utf-8")).hexdigest()

    seal: dict[str, Any] = {
        "SCOPE": f"LINES[1,{line_count}]",
        "ALGORITHM": "SHA256",
        "HASH": f'"{hash_value}"',
    }

    if grammar_version is not None:
        seal["GRAMMAR"] = grammar_version

    return seal


def seal_document(doc: Document) -> Document:
    """Add SEAL section to a document.

    Creates a new document with the SEAL section appended.
    The seal is computed on the canonical form of the document
    (everything except the SEAL section itself).

    Args:
        doc: Document to seal

    Returns:
        New Document with SEAL section added
    """
    # First, get canonical content without any existing seal
    doc_without_seal = _remove_seal_section(doc)
    canonical_content = emit(doc_without_seal)

    # Compute seal for canonical content
    seal_data = compute_seal(canonical_content, doc.grammar_version)

    # Create SEAL section with children
    seal_children: list[ASTNode] = [
        Assignment(key="SCOPE", value=seal_data["SCOPE"]),
        Assignment(key="ALGORITHM", value=seal_data["ALGORITHM"]),
        Assignment(key="HASH", value=seal_data["HASH"].strip('"')),  # Store without quotes
    ]

    if "GRAMMAR" in seal_data:
        seal_children.append(Assignment(key="GRAMMAR", value=seal_data["GRAMMAR"]))

    seal_section = Section(
        section_id="SEAL",
        key="SEAL",
        children=seal_children,
    )

    # Create new document with seal
    sealed_doc = Document(
        name=doc.name,
        meta=doc.meta.copy() if doc.meta else {},
        sections=list(doc_without_seal.sections) + [seal_section],
        has_separator=doc.has_separator,
        raw_frontmatter=doc.raw_frontmatter,
        grammar_version=doc.grammar_version,
    )

    return sealed_doc


def extract_seal(doc: Document) -> dict[str, Any] | None:
    """Extract SEAL section data from a document.

    Args:
        doc: Document to extract seal from

    Returns:
        Dict with seal data if present, None if no SEAL section
    """
    for section in doc.sections:
        if isinstance(section, Section) and section.key == "SEAL":
            seal_data: dict[str, Any] = {}
            for child in section.children:
                if isinstance(child, Assignment):
                    seal_data[child.key] = child.value
            return seal_data if seal_data else None
    return None


def verify_seal(doc: Document) -> SealVerificationResult:
    """Verify the SEAL of a document.

    Checks that the document content matches the hash in its SEAL section.

    Args:
        doc: Document to verify

    Returns:
        SealVerificationResult with status and hash information
    """
    seal_data = extract_seal(doc)

    if seal_data is None:
        return SealVerificationResult(
            status=SealStatus.NO_SEAL,
            message="No SEAL section found",
        )

    # Get the stored hash
    stored_hash = seal_data.get("HASH", "")
    if isinstance(stored_hash, str):
        stored_hash = stored_hash.strip('"')

    # Get canonical content without the seal section
    doc_without_seal = _remove_seal_section(doc)
    canonical_content = emit(doc_without_seal)

    # Compute expected hash
    computed_hash = hashlib.sha256(canonical_content.encode("utf-8")).hexdigest()

    if computed_hash == stored_hash:
        return SealVerificationResult(
            status=SealStatus.VERIFIED,
            expected_hash=computed_hash,
            actual_hash=stored_hash,
            message="Seal verified - content matches hash",
        )
    else:
        return SealVerificationResult(
            status=SealStatus.INVALID,
            expected_hash=computed_hash,
            actual_hash=stored_hash,
            message="Seal invalid - content has been modified",
        )


def _remove_seal_section(doc: Document) -> Document:
    """Create a copy of document without SEAL section.

    Args:
        doc: Document to copy

    Returns:
        New Document without SEAL section
    """
    # Filter out SEAL sections
    filtered_sections = [s for s in doc.sections if not (isinstance(s, Section) and s.key == "SEAL")]

    return Document(
        name=doc.name,
        meta=doc.meta.copy() if doc.meta else {},
        sections=filtered_sections,
        has_separator=doc.has_separator,
        raw_frontmatter=doc.raw_frontmatter,
        grammar_version=doc.grammar_version,
    )
