"""Tests for MCP server startup and configuration."""

import os
from unittest.mock import patch

from octave_mcp.mcp.server import ensure_dependencies_synced, parse_disabled_tools


class TestEnsureDependenciesSynced:
    """Tests for startup dependency sync."""

    def test_skip_sync_when_env_var_set(self):
        """Should skip sync when OCTAVE_MCP_SKIP_SYNC=1."""
        with patch.dict(os.environ, {"OCTAVE_MCP_SKIP_SYNC": "1"}):
            # Should return early without doing anything
            ensure_dependencies_synced()
            # No exception means success

    def test_sync_runs_in_real_project(self):
        """Should attempt sync when in a real project directory."""
        # This test runs in a real project with pyproject.toml
        # Just verify it doesn't crash
        with patch.dict(os.environ, {"OCTAVE_MCP_SKIP_SYNC": ""}):
            # Should not raise - may or may not actually run uv sync
            # depending on whether uv is available
            ensure_dependencies_synced()

    def test_skip_sync_when_uv_not_available(self):
        """Should skip sync gracefully when uv is not installed."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("uv not found")
            # Should not raise
            ensure_dependencies_synced()


class TestParseDisabledTools:
    """Tests for DISABLED_TOOLS parsing."""

    def test_empty_env_returns_empty_set(self):
        """Empty DISABLED_TOOLS returns empty set."""
        with patch.dict(os.environ, {"DISABLED_TOOLS": ""}):
            assert parse_disabled_tools() == set()

    def test_single_tool_disabled(self):
        """Single tool can be disabled."""
        with patch.dict(os.environ, {"DISABLED_TOOLS": "octave_eject"}):
            assert parse_disabled_tools() == {"octave_eject"}

    def test_multiple_tools_disabled(self):
        """Multiple tools can be disabled."""
        with patch.dict(os.environ, {"DISABLED_TOOLS": "octave_eject, octave_validate"}):
            assert parse_disabled_tools() == {"octave_eject", "octave_validate"}

    def test_whitespace_handling(self):
        """Whitespace around tool names is trimmed."""
        with patch.dict(os.environ, {"DISABLED_TOOLS": "  octave_eject  ,  octave_validate  "}):
            assert parse_disabled_tools() == {"octave_eject", "octave_validate"}

    def test_unset_env_returns_empty_set(self):
        """Unset DISABLED_TOOLS returns empty set."""
        env = os.environ.copy()
        env.pop("DISABLED_TOOLS", None)
        with patch.dict(os.environ, env, clear=True):
            assert parse_disabled_tools() == set()
