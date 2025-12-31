"""Shared file operations for OCTAVE files.

Provides security-validated file operations used by both CLI and MCP tools:
- validate_octave_path: Security checks for path safety
- atomic_write_octave: Atomic write with optional CAS (Compare-And-Swap) support
"""

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Any

# Security: allowed file extensions for OCTAVE files
ALLOWED_EXTENSIONS = {".oct.md", ".octave", ".md"}


def validate_octave_path(target_path: str) -> tuple[bool, str | None]:
    """Validate target path for security.

    Performs security checks:
    1. Rejects symlinks in path (prevents symlink-based exfiltration)
    2. Rejects path traversal (..)
    3. Validates file extension

    Args:
        target_path: Path to validate

    Returns:
        Tuple of (is_valid, error_message)
        - (True, None) if path is valid
        - (False, error_message) if path is invalid
    """
    path = Path(target_path)

    # Check for path traversal (..)
    try:
        # Check if path contains .. as a component (not substring)
        if any(part == ".." for part in path.parts):
            return False, "Path traversal not allowed (..)"
    except Exception as e:
        return False, f"Invalid path: {str(e)}"

    # Check for symlinks anywhere in path (security: prevent symlink-based exfiltration)
    try:
        # Get absolute path (does not follow symlinks)
        absolute = path.absolute()

        # Resolve to canonical path (follows all symlinks)
        resolved = absolute.resolve(strict=False)

        # If paths differ after normalization, symlinks were involved
        if absolute != resolved:
            # Walk the path to find which component is the symlink
            current = Path("/")
            for part in absolute.parts[1:]:  # Skip root
                current = current / part
                if current.exists() and current.is_symlink():
                    # Found a symlink - check if it's a system symlink
                    symlink_depth = len(Path(current).parts)
                    resolved_target = current.resolve()

                    # Allow common system symlinks (macOS):
                    # - /var -> /private/var (depth 1)
                    # - /tmp -> /private/tmp (depth 1)
                    # - /etc -> /private/etc (depth 1)
                    if symlink_depth <= 2 and str(resolved_target).startswith("/private/"):
                        continue

                    # User-controlled symlink - reject
                    return False, "Symlink in path not allowed for security reasons"

    except Exception as e:
        return False, f"Path resolution failed: {str(e)}"

    # Check file extension
    if path.suffix not in ALLOWED_EXTENSIONS:
        compound_suffix = "".join(path.suffixes[-2:]) if len(path.suffixes) >= 2 else path.suffix
        if compound_suffix not in ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
            return False, f"Invalid file extension. Allowed: {allowed}"

    return True, None


def compute_hash(content: str) -> str:
    """Compute SHA-256 hash of content.

    Args:
        content: Content to hash

    Returns:
        Hex digest of SHA-256 hash
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def atomic_write_octave(
    target_path: str,
    content: str,
    base_hash: str | None = None,
) -> dict[str, Any]:
    """Atomically write OCTAVE content to file with optional CAS.

    Performs:
    1. Path validation (security checks)
    2. Optional base_hash verification (CAS - Compare-And-Swap)
    3. Atomic write via tempfile + os.replace
    4. Permission preservation for existing files

    Args:
        target_path: Path to write to
        content: Content to write
        base_hash: Optional expected hash of existing file (for CAS)

    Returns:
        Dictionary with:
        - status: "success" or "error"
        - canonical_hash: SHA-256 of written content (on success)
        - path: Written file path (on success)
        - error: Error message (on failure)
    """
    path_obj = Path(target_path)

    # Step 1: Validate path
    path_valid, path_error = validate_octave_path(target_path)
    if not path_valid:
        return {
            "status": "error",
            "error": path_error,
            "path": target_path,
        }

    # Step 2: Check symlink at target
    if path_obj.exists() and path_obj.is_symlink():
        return {
            "status": "error",
            "error": "Cannot write to symlink target",
            "path": target_path,
        }

    # Step 3: CAS check if base_hash provided
    if base_hash and path_obj.exists():
        try:
            existing_content = path_obj.read_text(encoding="utf-8")
            current_hash = compute_hash(existing_content)
            if current_hash != base_hash:
                return {
                    "status": "error",
                    "error": f"Hash mismatch (expected {base_hash[:8]}..., got {current_hash[:8]}...)",
                    "path": target_path,
                }
        except Exception as e:
            return {
                "status": "error",
                "error": f"Read error: {str(e)}",
                "path": target_path,
            }

    # Step 4: Atomic write
    try:
        # Ensure parent directory exists
        path_obj.parent.mkdir(parents=True, exist_ok=True)

        # Preserve permissions if file exists
        original_mode = None
        if path_obj.exists():
            original_stat = os.stat(target_path)
            original_mode = original_stat.st_mode & 0o777

        # Atomic write: tempfile -> fsync -> os.replace
        fd, temp_path = tempfile.mkstemp(dir=path_obj.parent, suffix=".tmp", text=True)
        try:
            if original_mode is not None:
                os.fchmod(fd, original_mode)

            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())

            # TOCTOU protection: recheck base_hash before replace
            if base_hash and path_obj.exists():
                with open(target_path, encoding="utf-8") as verify_f:
                    verify_content = verify_f.read()
                verify_hash = compute_hash(verify_content)
                if verify_hash != base_hash:
                    os.unlink(temp_path)
                    return {
                        "status": "error",
                        "error": f"Hash mismatch before write (expected {base_hash[:8]}..., got {verify_hash[:8]}...)",
                        "path": target_path,
                    }

            # Atomic replace
            os.replace(temp_path, target_path)

        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    except Exception as e:
        return {
            "status": "error",
            "error": f"Write error: {str(e)}",
            "path": target_path,
        }

    # Success
    canonical_hash = compute_hash(content)
    return {
        "status": "success",
        "canonical_hash": canonical_hash,
        "path": target_path,
    }
