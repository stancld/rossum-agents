# Rossum Agent TUI

Terminal UI for interacting with the Rossum Agent API.

## Setup

```bash
npm install
npm run build
```

## Configuration

| Option | Flag | Environment Variable | Required |
|--------|------|---------------------|----------|
| Agent API URL | `--api-url` | `ROSSUM_AGENT_API_URL` | Yes |
| Rossum API token | `--token` | `ROSSUM_API_TOKEN` | Yes |
| Rossum API base URL | `--rossum-url` | `ROSSUM_API_BASE_URL` | Yes |
| MCP mode | `--mcp-mode` | `ROSSUM_MCP_MODE` | No (default: `read-only`) |

## Usage

```bash
# Using environment variables
export ROSSUM_AGENT_API_URL=http://localhost:8000
export ROSSUM_API_TOKEN=your-token
export ROSSUM_API_BASE_URL=https://api.elis.rossum.ai
fabry

# Using flags
fabry --api-url http://localhost:8000 --token your-token --rossum-url https://api.elis.rossum.ai

# Read-write mode
fabry --mcp-mode read-write
```

## Keyboard Controls

| Mode | Key | Action |
|------|-----|--------|
| Input | `Esc` | Switch to browse mode |
| Browse | `i` / `Tab` | Switch to input mode |
| Browse | `j` / `↓` | Move selection down |
| Browse | `k` / `↑` | Move selection up |
| Browse | `Enter` / `Space` | Expand/collapse selected item |
| Browse | `G` | Jump to bottom (re-enable auto-scroll) |

Expandable items: thinking steps, tool calls, and intermediate content (instructions).

## Session Persistence

Chat state is persisted to `~/.rossum-agent-tui/history.json`. On restart, the TUI restores the previous session (chat history, completed steps, tasks).

### Clear state / start fresh

```bash
rm ~/.rossum-agent-tui/history.json
```

Or remove the entire directory:

```bash
rm -rf ~/.rossum-agent-tui
```

## Development

```bash
npm run dev    # watch mode (recompiles on changes)
npm run build  # one-off build
npm start      # run from dist/
```
