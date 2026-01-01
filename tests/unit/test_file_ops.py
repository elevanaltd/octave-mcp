"""Tests for file operations module (file_ops.py).

Tests path validation, atomic writing, and CAS (Compare-And-Swap) operations.
Targets coverage of security-critical file operations.
"""

import os
from pathlib import Path

from octave_mcp.core.file_ops import (
    ALLOWED_EXTENSIONS,
    atomic_write_octave,
    compute_hash,
    validate_octave_path,
)


class TestValidateOctavePath:
    """Tests for validate_octave_path function."""

    def test_valid_octave_md_extension(self, tmp_path):
        """Valid .oct.md extension passes validation."""
        path = str(tmp_path / "test.oct.md")
        valid, error = validate_octave_path(path)
        assert valid is True
        assert error is None

    def test_valid_octave_extension(self, tmp_path):
        """Valid .octave extension passes validation."""
        path = str(tmp_path / "test.octave")
        valid, error = validate_octave_path(path)
        assert valid is True
        assert error is None

    def test_valid_md_extension(self, tmp_path):
        """Valid .md extension passes validation."""
        path = str(tmp_path / "test.md")
        valid, error = validate_octave_path(path)
        assert valid is True
        assert error is None

    def test_invalid_extension_txt(self, tmp_path):
        """Invalid .txt extension fails validation."""
        path = str(tmp_path / "test.txt")
        valid, error = validate_octave_path(path)
        assert valid is False
        assert "Invalid file extension" in error

    def test_invalid_extension_json(self, tmp_path):
        """Invalid .json extension fails validation."""
        path = str(tmp_path / "test.json")
        valid, error = validate_octave_path(path)
        assert valid is False
        assert "Invalid file extension" in error

    def test_path_traversal_rejected(self, tmp_path):
        """Path traversal (..) is rejected."""
        path = str(tmp_path / ".." / "test.oct.md")
        valid, error = validate_octave_path(path)
        assert valid is False
        assert "Path traversal" in error

    def test_path_traversal_middle_rejected(self, tmp_path):
        """Path traversal in middle of path is rejected."""
        path = str(tmp_path / "subdir" / ".." / "test.oct.md")
        valid, error = validate_octave_path(path)
        assert valid is False
        assert "Path traversal" in error

    def test_symlink_in_path_rejected(self, tmp_path):
        """Symlink in path is rejected for security."""
        # Create a real directory and a symlink to it
        real_dir = tmp_path / "real_dir"
        real_dir.mkdir()

        symlink_dir = tmp_path / "symlink_dir"
        symlink_dir.symlink_to(real_dir)

        path = str(symlink_dir / "test.oct.md")
        valid, error = validate_octave_path(path)
        # Should reject user-controlled symlinks
        assert valid is False
        assert "symlink" in error.lower() or "Symlink" in error


class TestComputeHash:
    """Tests for compute_hash function."""

    def test_compute_hash_consistency(self):
        """Same content produces same hash."""
        content = "Hello, World!"
        hash1 = compute_hash(content)
        hash2 = compute_hash(content)
        assert hash1 == hash2

    def test_compute_hash_different_content(self):
        """Different content produces different hash."""
        hash1 = compute_hash("Hello")
        hash2 = compute_hash("World")
        assert hash1 != hash2

    def test_compute_hash_sha256_length(self):
        """Hash is 64 hex characters (SHA-256)."""
        hash_value = compute_hash("test")
        assert len(hash_value) == 64
        assert all(c in "0123456789abcdef" for c in hash_value)


class TestAtomicWriteOctave:
    """Tests for atomic_write_octave function."""

    def test_create_new_file(self, tmp_path):
        """Create new file successfully."""
        path = str(tmp_path / "new_file.oct.md")
        content = "===TEST===\nMETA:\n  TYPE::TEST\n===END==="

        result = atomic_write_octave(path, content)

        assert result["status"] == "success"
        assert result["path"] == path
        assert "canonical_hash" in result

        # Verify file was created with correct content
        assert Path(path).exists()
        assert Path(path).read_text() == content

    def test_overwrite_existing_file(self, tmp_path):
        """Overwrite existing file without CAS."""
        path = str(tmp_path / "existing.oct.md")
        Path(path).write_text("old content")

        new_content = "new content"
        result = atomic_write_octave(path, new_content)

        assert result["status"] == "success"
        assert Path(path).read_text() == new_content

    def test_cas_success_matching_hash(self, tmp_path):
        """CAS succeeds when base_hash matches current file hash."""
        path = str(tmp_path / "cas_test.oct.md")
        original_content = "original content"
        Path(path).write_text(original_content)

        base_hash = compute_hash(original_content)
        new_content = "updated content"

        result = atomic_write_octave(path, new_content, base_hash=base_hash)

        assert result["status"] == "success"
        assert Path(path).read_text() == new_content

    def test_cas_failure_hash_mismatch(self, tmp_path):
        """CAS fails when base_hash doesn't match current file."""
        path = str(tmp_path / "cas_fail.oct.md")
        Path(path).write_text("current content")

        wrong_hash = compute_hash("different content")
        new_content = "attempted update"

        result = atomic_write_octave(path, new_content, base_hash=wrong_hash)

        assert result["status"] == "error"
        assert "Hash mismatch" in result["error"]
        # Original content should be preserved
        assert Path(path).read_text() == "current content"

    def test_invalid_path_rejected(self, tmp_path):
        """Invalid path (bad extension) is rejected."""
        path = str(tmp_path / "invalid.txt")
        content = "test content"

        result = atomic_write_octave(path, content)

        assert result["status"] == "error"
        assert "Invalid file extension" in result["error"]

    def test_creates_parent_directories(self, tmp_path):
        """Parent directories are created if they don't exist."""
        path = str(tmp_path / "subdir1" / "subdir2" / "test.oct.md")
        content = "test content"

        result = atomic_write_octave(path, content)

        assert result["status"] == "success"
        assert Path(path).exists()
        assert Path(path).read_text() == content

    def test_symlink_target_rejected(self, tmp_path):
        """Writing to symlink target is rejected."""
        # Create a real file and a symlink to it
        real_file = tmp_path / "real.oct.md"
        real_file.write_text("original")

        symlink_file = tmp_path / "symlink.oct.md"
        symlink_file.symlink_to(real_file)

        result = atomic_write_octave(str(symlink_file), "new content")

        assert result["status"] == "error"
        assert "symlink" in result["error"].lower() or "Symlink" in result["error"]

    def test_preserves_file_permissions(self, tmp_path):
        """File permissions are preserved on overwrite."""
        path = str(tmp_path / "perms.oct.md")

        # Create file with specific permissions
        Path(path).write_text("original")
        os.chmod(path, 0o644)
        original_mode = os.stat(path).st_mode & 0o777

        # Overwrite
        result = atomic_write_octave(path, "new content")

        assert result["status"] == "success"
        new_mode = os.stat(path).st_mode & 0o777
        assert new_mode == original_mode

    def test_path_traversal_rejected_in_atomic_write(self, tmp_path):
        """Path traversal is rejected in atomic write."""
        path = str(tmp_path / ".." / "escape.oct.md")
        content = "test"

        result = atomic_write_octave(path, content)

        assert result["status"] == "error"
        assert "Path traversal" in result["error"]

    def test_hash_returned_on_success(self, tmp_path):
        """Canonical hash is returned on successful write."""
        path = str(tmp_path / "hash_test.oct.md")
        content = "test content for hashing"

        result = atomic_write_octave(path, content)

        assert result["status"] == "success"
        expected_hash = compute_hash(content)
        assert result["canonical_hash"] == expected_hash


class TestAllowedExtensions:
    """Tests for ALLOWED_EXTENSIONS constant."""

    def test_allowed_extensions_includes_oct_md(self):
        """ALLOWED_EXTENSIONS includes .oct.md."""
        assert ".oct.md" in ALLOWED_EXTENSIONS

    def test_allowed_extensions_includes_octave(self):
        """ALLOWED_EXTENSIONS includes .octave."""
        assert ".octave" in ALLOWED_EXTENSIONS

    def test_allowed_extensions_includes_md(self):
        """ALLOWED_EXTENSIONS includes .md."""
        assert ".md" in ALLOWED_EXTENSIONS

    def test_allowed_extensions_does_not_include_txt(self):
        """ALLOWED_EXTENSIONS does not include .txt."""
        assert ".txt" not in ALLOWED_EXTENSIONS
