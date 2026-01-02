# OCTAVE MCP Server - Configuration Guide

Complete guide for configuring the OCTAVE MCP server with various MCP clients.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Claude Desktop Configuration](#claude-desktop-configuration)
- [Custom MCP Clients](#custom-mcp-clients)
- [Environment Variables](#environment-variables)
- [Troubleshooting](#troubleshooting)
- [Advanced Configuration](#advanced-configuration)

---

## Overview

The OCTAVE MCP server implements the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/), enabling integration with any MCP-compatible client.

The server exposes three tools:
- **octave_validate** - Schema validation and parsing
- **octave_write** - File creation and modification (content mode OR changes mode)
- **octave_eject** - Format projection (octave, json, yaml, markdown)

---

## Prerequisites

### 1. Install OCTAVE MCP Server

```bash
pip install octave-mcp
```

Verify installation:

```bash
octave-mcp-server --help
```

### 2. Verify Python Environment

The server requires Python 3.11 or higher:

```bash
python --version  # Should show 3.11+
```

### 3. Check PATH

Ensure the installation location is in your PATH:

```bash
which octave-mcp-server
# Should output: /path/to/bin/octave-mcp-server
```

If not found, add Python's bin directory to PATH:

```bash
# For pip user install
export PATH="$HOME/.local/bin:$PATH"

# For pip global install
export PATH="/usr/local/bin:$PATH"

# For virtual environment
source /path/to/venv/bin/activate
```

---

## Claude Desktop Configuration

Claude Desktop is a desktop application that supports MCP servers.

### macOS Configuration

1. **Locate the configuration file:**

   ```bash
   ~/Library/Application Support/Claude/claude_desktop_config.json
   ```

2. **Edit the configuration:**

   Open the file in your favorite editor:

   ```bash
   code ~/Library/Application\ Support/Claude/claude_desktop_config.json
   ```

3. **Add the OCTAVE server:**

   ```json
   {
     "mcpServers": {
       "octave": {
         "command": "octave-mcp-server"
       }
     }
   }
   ```

   If you have other MCP servers configured:

   ```json
   {
     "mcpServers": {
       "octave": {
         "command": "octave-mcp-server"
       },
       "other-server": {
         "command": "other-mcp-server"
       }
     }
   }
   ```

4. **Restart Claude Desktop**

   Quit and relaunch Claude Desktop for changes to take effect.

5. **Verify the server is loaded:**

   In Claude Desktop, check that the OCTAVE tools are available:
   - Look for "octave_validate", "octave_write", and "octave_eject" in the tools menu
   - Or ask Claude: "What MCP tools are available?"

### Windows Configuration

1. **Locate the configuration file:**

   ```
   %APPDATA%\Claude\claude_desktop_config.json
   ```

2. **Edit the configuration:**

   Open the file in Notepad or your preferred editor.

3. **Add the OCTAVE server:**

   ```json
   {
     "mcpServers": {
       "octave": {
         "command": "octave-mcp-server.exe"
       }
     }
   }
   ```

   Note: Use `.exe` extension on Windows.

4. **Restart Claude Desktop**

### Linux Configuration

1. **Locate the configuration file:**

   ```bash
   ~/.config/Claude/claude_desktop_config.json
   ```

2. **Edit the configuration:**

   ```bash
   nano ~/.config/Claude/claude_desktop_config.json
   ```

3. **Add the OCTAVE server:**

   ```json
   {
     "mcpServers": {
       "octave": {
         "command": "octave-mcp-server"
       }
     }
   }
   ```

4. **Restart Claude Desktop**

---

## Custom MCP Clients

For custom MCP client integration, use the MCP protocol over stdio.

### Python Client Example

```python
import asyncio
import json
from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    # Start the OCTAVE MCP server
    server_params = StdioServerParameters(
        command="octave-mcp-server",
        args=[]
    )

    async with stdio_client(server_params) as (read, write):
        async with Client(read, write) as client:
            # Initialize the connection
            await client.initialize()

            # List available tools
            tools = await client.list_tools()
            print("Available tools:", [t.name for t in tools.tools])

            # Call octave_validate
            result = await client.call_tool(
                "octave_validate",
                arguments={
                    "content": 'DECISION:\n  ID::"DEC-001"\n  STATUS::"approved"',
                    "schema": "DECISION_LOG"
                }
            )

            print("Result:", result.content[0].text)

asyncio.run(main())
```

### Node.js Client Example

```javascript
const { Client } = require('@modelcontextprotocol/sdk/client/index.js');
const { StdioClientTransport } = require('@modelcontextprotocol/sdk/client/stdio.js');

async function main() {
  const transport = new StdioClientTransport({
    command: 'octave-mcp-server',
    args: []
  });

  const client = new Client({
    name: 'octave-client',
    version: '1.0.0'
  }, {
    capabilities: {}
  });

  await client.connect(transport);

  // List tools
  const tools = await client.listTools();
  console.log('Available tools:', tools.tools.map(t => t.name));

  // Call octave_validate
  const result = await client.callTool({
    name: 'octave_validate',
    arguments: {
      content: 'DECISION:\n  ID::"DEC-001"\n  STATUS::"approved"',
      schema: 'DECISION_LOG'
    }
  });

  console.log('Result:', result.content[0].text);
}

main().catch(console.error);
```

---

## Environment Variables

The OCTAVE MCP server supports the following environment variables:

### `OCTAVE_SCHEMA_PATH`

Custom directory for schema files.

**Default:** Builtin schemas only

**Usage:**

```bash
export OCTAVE_SCHEMA_PATH="/path/to/custom/schemas"
octave-mcp-server
```

### `OCTAVE_LOG_LEVEL`

Logging verbosity level.

**Values:** `DEBUG`, `INFO`, `WARNING`, `ERROR`

**Default:** `INFO`

**Usage:**

```bash
export OCTAVE_LOG_LEVEL=DEBUG
octave-mcp-server
```

### `OCTAVE_LOG_FILE`

Write logs to file instead of stderr.

**Default:** Logs to stderr

**Usage:**

```bash
export OCTAVE_LOG_FILE="/var/log/octave-mcp.log"
octave-mcp-server
```

### Example: Claude Desktop with Environment Variables

```json
{
  "mcpServers": {
    "octave": {
      "command": "octave-mcp-server",
      "env": {
        "OCTAVE_LOG_LEVEL": "DEBUG",
        "OCTAVE_SCHEMA_PATH": "/Users/me/custom-schemas"
      }
    }
  }
}
```

---

## Troubleshooting

### Issue: Server Not Starting

**Symptoms:**
- Claude Desktop shows "octave" server as unavailable
- No OCTAVE tools appear in tools menu

**Diagnosis:**

1. Check if the command is accessible:

   ```bash
   which octave-mcp-server
   ```

   Should output a path. If not, the package isn't installed or not in PATH.

2. Test manual startup:

   ```bash
   octave-mcp-server 2>&1 | tee server-log.txt
   ```

   Check `server-log.txt` for errors.

**Solutions:**

- **Not in PATH:** Add Python bin directory to PATH (see [Prerequisites](#prerequisites))
- **Not installed:** Run `pip install octave-mcp`
- **Wrong Python version:** Ensure Python 3.11+ with `python --version`

### Issue: Tools Not Appearing

**Symptoms:**
- Server starts but tools don't appear in Claude Desktop
- Client can't find `octave_validate`, `octave_write`, or `octave_eject`

**Diagnosis:**

Run server manually and check tool listing:

```bash
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | octave-mcp-server
```

Should return JSON with three tools.

**Solutions:**

- **Server crash on startup:** Check logs with `OCTAVE_LOG_LEVEL=DEBUG`
- **MCP protocol version mismatch:** Update `octave-mcp` package
- **Client cache issue:** Restart MCP client

### Issue: Permission Denied

**Symptoms:**
```
-bash: /path/to/octave-mcp-server: Permission denied
```

**Solution:**

Make the script executable:

```bash
chmod +x $(which octave-mcp-server)
```

### Issue: Module Not Found

**Symptoms:**
```
ModuleNotFoundError: No module named 'octave_mcp'
```

**Diagnosis:**

The Python interpreter can't find the installed package.

**Solutions:**

1. **Virtual environment not activated:**
   ```bash
   source /path/to/venv/bin/activate
   octave-mcp-server
   ```

2. **Install in correct environment:**
   ```bash
   pip install octave-mcp
   # Verify
   python -c "import octave_mcp; print(octave_mcp.__version__)"
   ```

3. **Use absolute path to Python:**
   ```json
   {
     "mcpServers": {
       "octave": {
         "command": "/path/to/venv/bin/octave-mcp-server"
       }
     }
   }
   ```

### Issue: Schema Not Found

**Symptoms:**
```
ValueError: Schema 'MY_SCHEMA' not found
```

**Solution:**

1. Use builtin schemas: `META`, `DECISION_LOG`, `TASK`, `TASK_RESULT`

2. Or add custom schema directory:
   ```bash
   export OCTAVE_SCHEMA_PATH="/path/to/schemas"
   ```

3. Verify schema file exists:
   ```bash
   ls $OCTAVE_SCHEMA_PATH/MY_SCHEMA.oct.md
   ```

### Issue: Validation Errors

**Symptoms:**
- Tool returns validation errors
- Documents rejected despite looking correct

**Diagnosis:**

Run with verbose mode to see details:

```bash
octave validate document.oct.md --schema DECISION_LOG --verbose
```

**Solutions:**

- **Unknown fields:** Use non-strict mode or remove extra fields
- **Type mismatch:** Check field types match schema (e.g., string vs identifier)
- **Missing required:** Add all required fields from schema
- **Enable repairs:** Use `fix: true` parameter for automatic corrections

### Issue: Slow Performance

**Symptoms:**
- Server takes seconds to process documents
- Timeouts in MCP client

**Solutions:**

- **Large documents:** Split into smaller schemas or use projection modes
- **Debug logging:** Disable with `OCTAVE_LOG_LEVEL=ERROR`
- **Upgrade Python:** Use Python 3.11+ (3.12+ recommended for better performance)

---

## Advanced Configuration

### Running Multiple Instances

You can run multiple OCTAVE servers with different configurations:

```json
{
  "mcpServers": {
    "octave-strict": {
      "command": "octave-mcp-server",
      "env": {
        "OCTAVE_STRICT_MODE": "true"
      }
    },
    "octave-lenient": {
      "command": "octave-mcp-server",
      "env": {
        "OCTAVE_STRICT_MODE": "false"
      }
    }
  }
}
```

### Custom Schema Repositories

Organize schemas by project:

```json
{
  "mcpServers": {
    "octave-project-a": {
      "command": "octave-mcp-server",
      "env": {
        "OCTAVE_SCHEMA_PATH": "/projects/project-a/schemas"
      }
    },
    "octave-project-b": {
      "command": "octave-mcp-server",
      "env": {
        "OCTAVE_SCHEMA_PATH": "/projects/project-b/schemas"
      }
    }
  }
}
```

### Logging to Separate Files

```json
{
  "mcpServers": {
    "octave": {
      "command": "octave-mcp-server",
      "env": {
        "OCTAVE_LOG_FILE": "/var/log/octave-mcp.log",
        "OCTAVE_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

### Network Mode (Advanced)

For network-based MCP (requires custom setup):

```python
# server.py
import asyncio
from octave_mcp.mcp.server import create_server

async def run_tcp_server():
    server = create_server()
    # Custom TCP transport implementation
    # ...

asyncio.run(run_tcp_server())
```

---

## Testing Configuration

### Verify Server Responds

```bash
# Test server startup
octave-mcp-server &
PID=$!

# Send tools/list request
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | nc localhost 9000

# Cleanup
kill $PID
```

### Test Tool Execution

```bash
# Create test document
cat > test.oct.md <<EOF
DECISION:
  ID::"DEC-001"
  STATUS::"approved"
EOF

# Test via CLI
octave ingest test.oct.md --schema DECISION_LOG

# Test via MCP (Python)
python -c "
from octave_mcp.mcp.validate import ValidateTool
import asyncio

async def test():
    tool = ValidateTool()
    result = await tool.execute(
        content=open('test.oct.md').read(),
        schema='DECISION_LOG'
    )
    print(result['canonical'])

asyncio.run(test())
"
```

---

## See Also

- [Usage Guide](usage.md) - Detailed usage examples
- [API Reference](api.md) - Complete API documentation
- [MCP Protocol](https://modelcontextprotocol.io/) - Official MCP specification
- [OCTAVE Specification](https://github.com/elevanaltd/octave-mcp/tree/main/specs) - Full protocol specification

---

## Getting Help

If you encounter issues not covered here:

- **Documentation:** Check [docs/](.)
- **Issues:** [GitHub Issues](https://github.com/elevanaltd/octave-mcp/issues)
- **Discussions:** [GitHub Discussions](https://github.com/elevanaltd/octave-mcp/discussions)
