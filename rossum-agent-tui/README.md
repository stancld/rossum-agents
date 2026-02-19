# Rossum Agent TUI

Terminal UI for interacting with the Rossum Agent API. Development test-bed for the [Rossum Agent](../rossum-agent/).

> [!NOTE]
> This is a development tool, not a production application. Tests are not required for this package.

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
| Persona | `--persona` | `ROSSUM_AGENT_PERSONA` | No (default: `default`) |

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

# Cautious persona
fabry --persona cautious
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
| Input | `Meta+1` | Quick reply: Approve |
| Input | `Meta+2` | Quick reply: Reject |
| Input | `Meta+3` | Quick reply: Let's chat about it. |

Expandable items: thinking steps, tool calls, and intermediate content (instructions).

## Task Tracking

When the agent uses task tracking for multi-step operations, a task list appears inline showing progress:

| Badge | Status |
|-------|--------|
| `✓` (green) | Completed |
| Spinner | In progress |
| `○` (dimmed) | Pending |

Tasks update in real-time as the agent works through each step.

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

## License

MIT License - see [LICENSE](../LICENSE) for details.

## Resources

- [Rossum Agent README](../rossum-agent/README.md)
- [Full Documentation](https://stancld.github.io/rossum-agents/)
- [Main Repository](https://github.com/stancld/rossum-agents)
