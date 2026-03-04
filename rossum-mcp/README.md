# Rossum MCP Server

<div align="center">

**MCP server for AI-powered Rossum document processing. 25 tools for queues, schemas, hooks, engines, and more.**

[![Documentation](https://img.shields.io/badge/docs-latest-blue.svg)](https://stancld.github.io/rossum-agents/)
[![Python](https://img.shields.io/pypi/pyversions/rossum-mcp.svg)](https://pypi.org/project/rossum-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI - rossum-mcp](https://img.shields.io/pypi/v/rossum-mcp?label=rossum-mcp)](https://pypi.org/project/rossum-mcp/)
[![Coverage](https://codecov.io/gh/stancld/rossum-agents/branch/master/graph/badge.svg?flag=rossum-mcp)](https://codecov.io/gh/stancld/rossum-agents)
[![MCP Tools](https://img.shields.io/badge/MCP_Tools-26-blue.svg)](#available-tools)

[![Rossum API](https://img.shields.io/badge/Rossum-API-orange.svg)](https://github.com/rossumai/rossum-api)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

</div>

> [!NOTE]
> This is not an official Rossum project. It is a community-developed integration built on top of the Rossum API, not a product (yet).

## Quick Start

```bash
# Set environment variables
export ROSSUM_API_TOKEN="your-api-token"
export ROSSUM_API_BASE_URL="https://api.elis.rossum.ai/v1"

# Run the MCP server
uv pip install rossum-mcp
rossum-mcp
```

Or run from source:

```bash
git clone https://github.com/stancld/rossum-agents.git
cd rossum-agents/rossum-mcp
uv sync
python rossum_mcp/server.py
```

## Claude Desktop Configuration

Configure Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json` on Mac):

```json
{
  "mcpServers": {
    "rossum": {
      "command": "python",
      "args": ["/path/to/rossum-mcp/rossum-mcp/rossum_mcp/server.py"],
      "env": {
        "ROSSUM_API_TOKEN": "your-api-token",
        "ROSSUM_API_BASE_URL": "https://api.elis.rossum.ai/v1",
        "ROSSUM_MCP_MODE": "read-write"
      }
    }
  }
}
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ROSSUM_API_TOKEN` | Yes | Your Rossum API authentication token |
| `ROSSUM_API_BASE_URL` | Yes | Base URL for the Rossum API |
| `ROSSUM_MCP_MODE` | No | `read-write` (default) or `read-only` |

### Read-Only Mode

Set `ROSSUM_MCP_MODE=read-only` to disable all CREATE, UPDATE, and UPLOAD operations. Only GET and LIST operations will be available.

### Runtime Mode Switching

Two tools allow dynamic mode control:

| Tool | Description |
|------|-------------|
| `get_mcp_mode` | Returns current operation mode (`read-only` or `read-write`) |
| `set_mcp_mode` | Switches between modes at runtime |

**Use case:** Start in read-only mode for safe exploration, then switch to read-write when ready to make changes.

```
User: What mode are we in?
Assistant: [calls get_mcp_mode] → "read-only"

User: I'm ready to update the schema now.
Assistant: [calls set_mcp_mode("read-write")] → Mode switched to read-write
           [calls update_schema(...)]
```

## Available Tools

The server provides **25 tools** organized into categories:

| Category | Tools | Description |
|----------|-------|-------------|
| **Read Layer** | 2 | Get any entity by ID or search/list with typed filters |
| **Create Layer** | 1 | Unified create for any supported entity |
| **Delete Layer** | 1 | Unified delete for any supported entity by ID |
| **Document Processing** | 6 | Upload documents, retrieve content, update/confirm/copy annotations |
| **Queue Management** | 1 | Update queue settings |
| **Schema Management** | 4 | Update, patch, tree view, and prune field structures |
| **Engine Management** | 2 | Update engines, get engine fields |
| **Extensions (Hooks)** | 2 | Update and test hooks |
| **Rules & Actions** | 2 | Update and patch business rules |
| **User Management** | 1 | Update users |
| **MCP Mode** | 2 | Get/set read-only or read-write mode |
| **Tool Discovery** | 1 | Dynamic tool loading |

<details>
<summary><strong>Tool List by Category</strong></summary>

**Read Layer** (unified get + search replacing ~25 individual get_X/list_X tools):
`get`, `search`

Supported entities for `get` (by ID): `queue`, `schema`, `hook`, `engine`, `rule`, `user`, `workspace`, `email_template`, `organization_group`, `organization_limit`, `annotation`, `relation`, `document_relation`

Supported entities for `search` (with typed filters): all `get` entities plus `hook_log`, `hook_template`, `user_role`, `queue_template_name`

**Create Layer** (unified create replacing 11 individual create_X tools):
`create`, `get_create_schema`

Supported entities: `workspace`, `queue_from_template`, `schema`, `user`, `hook`, `hook_from_template`, `engine`, `engine_field`, `rule`, `email_template`

**Delete Layer** (unified delete replacing individual delete_X tools):
`delete`

Supported entities: `queue`, `schema`, `hook`, `rule`, `workspace`, `annotation`

**Document Processing:**
`upload_document`, `get_annotation_content`, `start_annotation`, `bulk_update_annotation_fields`, `confirm_annotation`, `copy_annotations`

**Queue Management:**
`update_queue`

**Schema Management:**
`update_schema`, `patch_schema`, `get_schema_tree_structure`, `prune_schema_fields`

**Engine Management:**
`update_engine`, `get_engine_fields`

**Extensions (Hooks):**
`update_hook`, `test_hook`

**Rules & Actions:**
`update_rule`, `patch_rule`

**User Management:**
`update_user`

**MCP Mode:**
`get_mcp_mode`, `set_mcp_mode`

**Tool Discovery:**
`list_tool_categories`

</details>

For detailed API documentation with parameters and examples, see [TOOLS.md](TOOLS.md).

## Example Workflows

### Upload and Monitor

```python
# 1. Upload document
upload_document(file_path="/path/to/invoice.pdf", queue_id=12345)

# 2. Get annotation ID
annotations = search(query={"entity": "annotation", "queue_id": 12345, "ordering": ["-created_at"], "first_n": 1})

# 3. Check status
annotation = get(entity="annotation", entity_id=annotations[0]["id"])
```

### Update Fields

```python
# 1. Start annotation (moves to 'reviewing')
start_annotation(annotation_id=12345)

# 2. Get content with field IDs
annotation_content = get_annotation_content(annotation_id=12345)
# Returns {"path": "/tmp/rossum_annotation_12345_content.json"} — use jq/grep on that file

# 3. Update fields using datapoint IDs
bulk_update_annotation_fields(
    annotation_id=12345,
    operations=[{"op": "replace", "id": 67890, "value": {"content": {"value": "INV-001"}}}]
)

# 4. Confirm
confirm_annotation(annotation_id=12345)
```

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Resources

- [Full Documentation](https://stancld.github.io/rossum-agents/)
- [Tools Reference](TOOLS.md)
- [Rossum API Documentation](https://rossum.app/api/docs)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Main Repository](https://github.com/stancld/rossum-agents)
