#!/bin/bash
set -euo pipefail

# ============================================================================
# OCTAVE MCP Server Setup Script
#
# Configures the OCTAVE MCP server for use with various AI clients:
# - Claude Desktop
# - Claude Code CLI
# - OpenAI Codex CLI
# - Google Gemini CLI
#
# This script works in both regular repositories and git worktrees.
# When run in a worktree, it will configure MCP clients to use the
# worktree-specific paths. If the worktree is deleted, you'll need to
# reconfigure or run this script from the main repository.
#
# Usage:
#   ./setup-mcp.sh                    # Interactive setup
#   ./setup-mcp.sh --claude-desktop   # Configure Claude Desktop only
#   ./setup-mcp.sh --claude-code      # Configure Claude Code CLI only
#   ./setup-mcp.sh --codex            # Configure Codex CLI only
#   ./setup-mcp.sh --gemini           # Configure Gemini CLI only
#   ./setup-mcp.sh --all              # Configure all clients
#   ./setup-mcp.sh --show-config      # Show copy/paste configuration
#   ./setup-mcp.sh --uninstall        # Remove OCTAVE from all clients
# ============================================================================

# Colors for output
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly RED='\033[0;31m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Configuration
readonly MCP_SERVER_NAME="octave"
readonly VENV_PATH=".venv"

# ----------------------------------------------------------------------------
# Utility Functions
# ----------------------------------------------------------------------------

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1" >&2
}

print_warning() {
    echo -e "${YELLOW}!${NC} $1"
}

print_info() {
    echo -e "${BLUE}→${NC} $1"
}

print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# Get the script's directory (handles both regular repos and worktrees)
get_script_dir() {
    cd "$(dirname "$0")" && pwd
}

# Detect if we're in a worktree and warn user
detect_worktree() {
    if [[ -f .git ]] && grep -q "gitdir:" .git 2>/dev/null; then
        return 0  # Is a worktree
    fi
    return 1  # Not a worktree
}

# Detect operating system
detect_os() {
    case "$OSTYPE" in
        darwin*)  echo "macos" ;;
        linux*)
            if grep -qi microsoft /proc/version 2>/dev/null; then
                echo "wsl"
            else
                echo "linux"
            fi
            ;;
        msys*|cygwin*|win32) echo "windows" ;;
        *)        echo "unknown" ;;
    esac
}

# ----------------------------------------------------------------------------
# Path Resolution Functions
# ----------------------------------------------------------------------------

# Get Claude Desktop config path
get_claude_desktop_config_path() {
    local os_type=$(detect_os)
    case "$os_type" in
        macos)
            echo "$HOME/Library/Application Support/Claude/claude_desktop_config.json"
            ;;
        linux)
            echo "$HOME/.config/Claude/claude_desktop_config.json"
            ;;
        wsl)
            if command -v wslvar &> /dev/null; then
                local win_appdata=$(wslvar APPDATA 2>/dev/null)
                if [[ -n "$win_appdata" ]]; then
                    echo "$(wslpath "$win_appdata")/Claude/claude_desktop_config.json"
                    return
                fi
            fi
            echo "/mnt/c/Users/$USER/AppData/Roaming/Claude/claude_desktop_config.json"
            ;;
        windows)
            echo "$APPDATA/Claude/claude_desktop_config.json"
            ;;
        *)
            echo ""
            ;;
    esac
}

# Get Claude Code CLI config path
get_claude_code_config_path() {
    echo "$HOME/.claude.json"
}

# Get Codex CLI config path
get_codex_config_path() {
    echo "$HOME/.codex/config.toml"
}

# Get Gemini CLI config path
get_gemini_config_path() {
    echo "$HOME/.gemini/settings.json"
}

# Get Python executable from venv
get_venv_python() {
    local script_dir=$(get_script_dir)
    local venv_python="$script_dir/$VENV_PATH/bin/python"

    if [[ -f "$venv_python" ]]; then
        echo "$venv_python"
    else
        echo ""
    fi
}

# Get server entry point
get_server_path() {
    local script_dir=$(get_script_dir)
    echo "$script_dir/src/octave_mcp/mcp/server.py"
}

# ----------------------------------------------------------------------------
# Environment Setup
# ----------------------------------------------------------------------------

ensure_venv_exists() {
    local script_dir=$(get_script_dir)
    local venv_python=$(get_venv_python)

    # Warn if in worktree
    if detect_worktree; then
        print_warning "Running in a git worktree - MCP configuration will use worktree-specific paths"
        print_info "If this worktree is deleted, you'll need to reconfigure the MCP server"
    fi

    if [[ -z "$venv_python" ]]; then
        print_info "Creating virtual environment..."

        # Check if python3 is available
        if ! command -v python3 &> /dev/null; then
            print_error "python3 not found in PATH"
            return 1
        fi

        # Try uv first (faster), fall back to python3 -m venv
        # Note: uv venv doesn't include pip by default, but uv pip install works without it
        if command -v uv &> /dev/null; then
            uv venv --python 3.11 "$script_dir/$VENV_PATH" || uv venv "$script_dir/$VENV_PATH"
        else
            python3 -m venv "$script_dir/$VENV_PATH"
        fi

        venv_python=$(get_venv_python)
        if [[ -z "$venv_python" ]]; then
            print_error "Failed to create virtual environment"
            return 1
        fi
        print_success "Virtual environment created"
    fi

    # Check if package is installed
    if ! "$venv_python" -c "import octave_mcp" 2>/dev/null; then
        print_info "Installing octave-mcp package..."

        # Use uv pip if uv is available, otherwise use regular pip
        if command -v uv &> /dev/null; then
            # uv pip install works without pip being in the venv
            uv pip install -e "$script_dir" --quiet
            if [[ $? -ne 0 ]]; then
                print_error "Failed to install octave-mcp package with uv"
                return 1
            fi
        else
            # Traditional pip install
            "$venv_python" -m pip install -e "$script_dir" --quiet
            if [[ $? -ne 0 ]]; then
                print_error "Failed to install octave-mcp package with pip"
                return 1
            fi
        fi

        print_success "Package installed"
    fi

    return 0
}

# ----------------------------------------------------------------------------
# JSON Configuration Helpers
# ----------------------------------------------------------------------------

# Add MCP server to JSON config (Claude Desktop, Gemini)
add_to_json_config() {
    local config_path="$1"
    local server_name="$2"
    local python_cmd="$3"
    local server_path="$4"

    # Verify python3 is available
    if ! command -v python3 &> /dev/null; then
        print_error "python3 not found - required for JSON manipulation"
        return 1
    fi

    # Create backup
    if [[ -f "$config_path" ]]; then
        cp "$config_path" "$config_path.backup_$(date +%Y%m%d_%H%M%S)"
    fi

    local temp_file=$(mktemp)

    python3 << EOF
import json
import os

config_path = '$config_path'
server_name = '$server_name'
python_cmd = '$python_cmd'
server_path = '$server_path'

# Load existing config or create new
if os.path.exists(config_path):
    with open(config_path, 'r') as f:
        try:
            config = json.load(f)
        except json.JSONDecodeError:
            config = {}
else:
    config = {}

# Ensure mcpServers exists
if 'mcpServers' not in config:
    config['mcpServers'] = {}

# Add or update server
config['mcpServers'][server_name] = {
    'command': python_cmd,
    'args': [server_path]
}

# Write to temp file
with open('$temp_file', 'w') as f:
    json.dump(config, f, indent=2)

print('success')
EOF

    if [[ -f "$temp_file" ]] && grep -q "success" <<< "$(python3 -c "import json; json.load(open('$temp_file'))" 2>&1 && echo success)"; then
        # Ensure parent directory exists
        mkdir -p "$(dirname "$config_path")"
        mv "$temp_file" "$config_path"
        return 0
    else
        rm -f "$temp_file"
        return 1
    fi
}

# Remove MCP server from JSON config
remove_from_json_config() {
    local config_path="$1"
    local server_name="$2"

    if [[ ! -f "$config_path" ]]; then
        return 0
    fi

    # Verify python3 is available
    if ! command -v python3 &> /dev/null; then
        print_warning "python3 not found - skipping JSON removal"
        return 0
    fi

    local temp_file=$(mktemp)

    python3 << EOF
import json

config_path = '$config_path'
server_name = '$server_name'

with open(config_path, 'r') as f:
    config = json.load(f)

if 'mcpServers' in config and server_name in config['mcpServers']:
    del config['mcpServers'][server_name]

with open('$temp_file', 'w') as f:
    json.dump(config, f, indent=2)
EOF

    mv "$temp_file" "$config_path"
}

# ----------------------------------------------------------------------------
# TOML Configuration Helpers (for Codex)
# ----------------------------------------------------------------------------

add_to_toml_config() {
    local config_path="$1"
    local server_name="$2"
    local python_cmd="$3"
    local server_path="$4"

    # Create backup
    if [[ -f "$config_path" ]]; then
        cp "$config_path" "$config_path.backup_$(date +%Y%m%d_%H%M%S)"
    fi

    # Check if mcp_servers section exists for this server
    if grep -q "^\[mcp_servers\.$server_name\]" "$config_path" 2>/dev/null; then
        # Update existing entry using sed
        local temp_file=$(mktemp)
        awk -v name="$server_name" -v cmd="$python_cmd" -v arg="$server_path" '
        BEGIN { in_section = 0 }
        /^\[mcp_servers\.'"$server_name"'\]/ {
            in_section = 1
            print
            next
        }
        /^\[/ && in_section {
            in_section = 0
        }
        in_section && /^command/ {
            print "command = \"" cmd "\""
            next
        }
        in_section && /^args/ {
            print "args = [\"" arg "\"]"
            next
        }
        { print }
        ' "$config_path" > "$temp_file"
        mv "$temp_file" "$config_path"
    else
        # Append new entry
        cat >> "$config_path" << EOF

[mcp_servers.$server_name]
command = "$python_cmd"
args = ["$server_path"]
EOF
    fi
}

remove_from_toml_config() {
    local config_path="$1"
    local server_name="$2"

    if [[ ! -f "$config_path" ]]; then
        return 0
    fi

    local temp_file=$(mktemp)
    awk -v name="$server_name" '
    BEGIN { skip = 0 }
    /^\[mcp_servers\.'"$server_name"'\]/ {
        skip = 1
        next
    }
    /^\[/ && skip {
        skip = 0
    }
    !skip { print }
    ' "$config_path" > "$temp_file"
    mv "$temp_file" "$config_path"
}

# ----------------------------------------------------------------------------
# Client Configuration Functions
# ----------------------------------------------------------------------------

configure_claude_desktop() {
    print_info "Configuring Claude Desktop..."

    local config_path=$(get_claude_desktop_config_path)
    if [[ -z "$config_path" ]]; then
        print_warning "Could not determine Claude Desktop config path for this platform"
        return 1
    fi

    local python_cmd=$(get_venv_python)
    local server_path=$(get_server_path)

    if add_to_json_config "$config_path" "$MCP_SERVER_NAME" "$python_cmd" "$server_path"; then
        print_success "Claude Desktop configured"
        print_info "Config file: $config_path"
        print_warning "Restart Claude Desktop to apply changes"
        return 0
    else
        print_error "Failed to configure Claude Desktop"
        return 1
    fi
}

configure_claude_code() {
    print_info "Configuring Claude Code CLI..."

    local config_path=$(get_claude_code_config_path)
    local python_cmd=$(get_venv_python)
    local server_path=$(get_server_path)

    # Claude Code uses mcpServers at root level in ~/.claude.json
    if [[ ! -f "$config_path" ]]; then
        print_warning "Claude Code config not found: $config_path"
        print_info "Claude Code CLI may not be installed"
        return 1
    fi

    # Create backup
    cp "$config_path" "$config_path.backup_$(date +%Y%m%d_%H%M%S)"

    local temp_file=$(mktemp)

    python3 << EOF
import json

config_path = '$config_path'
server_name = '$MCP_SERVER_NAME'
python_cmd = '$python_cmd'
server_path = '$server_path'

with open(config_path, 'r') as f:
    config = json.load(f)

# Claude Code uses 'mcpServers' at root level
if 'mcpServers' not in config:
    config['mcpServers'] = {}

config['mcpServers'][server_name] = {
    'command': python_cmd,
    'args': [server_path]
}

with open('$temp_file', 'w') as f:
    json.dump(config, f, indent=2)
EOF

    if [[ -f "$temp_file" ]]; then
        mv "$temp_file" "$config_path"
        print_success "Claude Code CLI configured"
        print_info "Config file: $config_path"
        return 0
    else
        print_error "Failed to configure Claude Code CLI"
        return 1
    fi
}

configure_codex() {
    print_info "Configuring OpenAI Codex CLI..."

    local config_path=$(get_codex_config_path)
    local python_cmd=$(get_venv_python)
    local server_path=$(get_server_path)

    if [[ ! -f "$config_path" ]]; then
        print_warning "Codex config not found: $config_path"
        print_info "Codex CLI may not be installed"
        return 1
    fi

    add_to_toml_config "$config_path" "$MCP_SERVER_NAME" "$python_cmd" "$server_path"
    print_success "Codex CLI configured"
    print_info "Config file: $config_path"
    return 0
}

configure_gemini() {
    print_info "Configuring Google Gemini CLI..."

    local config_path=$(get_gemini_config_path)
    local python_cmd=$(get_venv_python)
    local server_path=$(get_server_path)

    if [[ ! -f "$config_path" ]]; then
        print_warning "Gemini config not found: $config_path"
        print_info "Gemini CLI may not be installed"
        return 1
    fi

    if add_to_json_config "$config_path" "$MCP_SERVER_NAME" "$python_cmd" "$server_path"; then
        print_success "Gemini CLI configured"
        print_info "Config file: $config_path"
        return 0
    else
        print_error "Failed to configure Gemini CLI"
        return 1
    fi
}

# ----------------------------------------------------------------------------
# Uninstall Functions
# ----------------------------------------------------------------------------

uninstall_all() {
    print_header "Uninstalling OCTAVE MCP Server"

    local claude_desktop=$(get_claude_desktop_config_path)
    local claude_code=$(get_claude_code_config_path)
    local codex=$(get_codex_config_path)
    local gemini=$(get_gemini_config_path)

    if [[ -f "$claude_desktop" ]]; then
        remove_from_json_config "$claude_desktop" "$MCP_SERVER_NAME"
        print_success "Removed from Claude Desktop"
    fi

    if [[ -f "$claude_code" ]]; then
        remove_from_json_config "$claude_code" "$MCP_SERVER_NAME"
        print_success "Removed from Claude Code CLI"
    fi

    if [[ -f "$codex" ]]; then
        remove_from_toml_config "$codex" "$MCP_SERVER_NAME"
        print_success "Removed from Codex CLI"
    fi

    if [[ -f "$gemini" ]]; then
        remove_from_json_config "$gemini" "$MCP_SERVER_NAME"
        print_success "Removed from Gemini CLI"
    fi

    print_success "OCTAVE MCP Server uninstalled from all clients"
}

# ----------------------------------------------------------------------------
# Show Configuration (Copy/Paste)
# ----------------------------------------------------------------------------

show_config() {
    local script_dir=$(get_script_dir)
    local python_cmd=$(get_venv_python)
    local server_path=$(get_server_path)

    if [[ -z "$python_cmd" ]]; then
        print_error "Virtual environment not set up. Run ./setup-mcp.sh first."
        exit 1
    fi

    print_header "OCTAVE MCP Server Configuration"

    echo ""
    echo -e "${YELLOW}For Claude Desktop & Claude Code CLI (JSON):${NC}"
    echo ""
    cat << EOF
{
  "mcpServers": {
    "octave": {
      "command": "$python_cmd",
      "args": ["$server_path"]
    }
  }
}
EOF

    echo ""
    echo -e "${YELLOW}For Codex CLI (TOML - add to ~/.codex/config.toml):${NC}"
    echo ""
    cat << EOF
[mcp_servers.octave]
command = "$python_cmd"
args = ["$server_path"]
EOF

    echo ""
    echo -e "${YELLOW}For Gemini CLI (JSON - add to mcpServers in ~/.gemini/settings.json):${NC}"
    echo ""
    cat << EOF
"octave": {
  "command": "$python_cmd",
  "args": ["$server_path"]
}
EOF

    echo ""
    echo -e "${BLUE}Configuration File Locations:${NC}"
    echo "  Claude Desktop: $(get_claude_desktop_config_path)"
    echo "  Claude Code:    $(get_claude_code_config_path)"
    echo "  Codex CLI:      $(get_codex_config_path)"
    echo "  Gemini CLI:     $(get_gemini_config_path)"
    echo ""
}

# ----------------------------------------------------------------------------
# Interactive Setup
# ----------------------------------------------------------------------------

interactive_setup() {
    print_header "OCTAVE MCP Server Setup"

    echo ""
    echo "This script will configure the OCTAVE MCP server for your AI clients."
    echo ""
    echo "Available clients:"
    echo "  1) Claude Desktop"
    echo "  2) Claude Code CLI"
    echo "  3) OpenAI Codex CLI"
    echo "  4) Google Gemini CLI"
    echo "  5) All of the above"
    echo "  6) Show copy/paste configuration"
    echo "  7) Uninstall from all"
    echo "  0) Exit"
    echo ""

    read -p "Select option [1-7, 0 to exit]: " choice

    case "$choice" in
        1)
            ensure_venv_exists && configure_claude_desktop
            ;;
        2)
            ensure_venv_exists && configure_claude_code
            ;;
        3)
            ensure_venv_exists && configure_codex
            ;;
        4)
            ensure_venv_exists && configure_gemini
            ;;
        5)
            ensure_venv_exists
            configure_claude_desktop || true
            configure_claude_code || true
            configure_codex || true
            configure_gemini || true
            print_success "Setup complete!"
            ;;
        6)
            ensure_venv_exists && show_config
            ;;
        7)
            uninstall_all
            ;;
        0)
            echo "Exiting."
            exit 0
            ;;
        *)
            print_error "Invalid option"
            exit 1
            ;;
    esac
}

# ----------------------------------------------------------------------------
# Main Entry Point
# ----------------------------------------------------------------------------

main() {
    local script_dir=$(get_script_dir)
    cd "$script_dir"

    # Parse command line arguments
    case "${1:-}" in
        --claude-desktop)
            ensure_venv_exists && configure_claude_desktop
            ;;
        --claude-code)
            ensure_venv_exists && configure_claude_code
            ;;
        --codex)
            ensure_venv_exists && configure_codex
            ;;
        --gemini)
            ensure_venv_exists && configure_gemini
            ;;
        --all)
            ensure_venv_exists
            configure_claude_desktop || true
            configure_claude_code || true
            configure_codex || true
            configure_gemini || true
            print_success "All clients configured!"
            ;;
        --show-config)
            ensure_venv_exists && show_config
            ;;
        --uninstall)
            uninstall_all
            ;;
        --help|-h)
            cat << EOF
OCTAVE MCP Server Setup

Usage: ./setup-mcp.sh [OPTION]

Options:
  --claude-desktop   Configure Claude Desktop only
  --claude-code      Configure Claude Code CLI only
  --codex            Configure OpenAI Codex CLI only
  --gemini           Configure Google Gemini CLI only
  --all              Configure all supported clients
  --show-config      Show copy/paste configuration for manual setup
  --uninstall        Remove OCTAVE from all clients
  -h, --help         Show this help message

Without options, runs interactive setup.

Supported Clients:
  - Claude Desktop (macOS, Linux, Windows/WSL)
  - Claude Code CLI (~/.claude.json)
  - OpenAI Codex CLI (~/.codex/config.toml)
  - Google Gemini CLI (~/.gemini/settings.json)

Examples:
  ./setup-mcp.sh                    # Interactive setup
  ./setup-mcp.sh --all              # Configure all clients
  ./setup-mcp.sh --show-config      # Show manual configuration
EOF
            ;;
        "")
            interactive_setup
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
}

main "$@"
