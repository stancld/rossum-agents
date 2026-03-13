# Rossum Agents API Skill

**Goal**: Delegate Rossum document-processing tasks to the Rossum Agent via CLI — querying, configuring, and automating a Rossum instance without knowing its internal API.

## When to Use

| Trigger | Example |
|---------|---------|
| Anything involving Rossum platform | "List queues", "Update schema", "Check annotations" |
| Document processing orchestration | "Extract invoice data and create a Jira ticket" |
| Rossum configuration changes | "Add a tax_id field to queue 12345" |

## Prerequisites

Three environment variables must be set. If missing, ask the user.

| Variable | Purpose | Example |
|----------|---------|---------|
| `ROSSUM_AGENT_API_URL` | Agent API endpoint | `https://agent.rossum.app` |
| `ROSSUM_API_BASE_URL` | Rossum API URL | `https://elis.rossum.ai/api/v1` |
| `ROSSUM_API_TOKEN` | Authentication token | (from user) |

Install the CLI if not available:

```bash
uv pip install rossum-agent-client
```

## How to Use

Run `rossum-agent-client` via Bash. It sends a natural language prompt to the Rossum Agent, which has full access to the Rossum platform. The final answer goes to **stdout**, progress to stderr.

```bash
# Read-only query (default)
rossum-agent-client -x "List all queues with their IDs and names"

# Write operation — requires --mcp-mode read-write
rossum-agent-client --mcp-mode read-write -x "Add a required string field 'tax_id' to the schema on queue 12345"

# Long or complex prompt — write to a file, pass with -r
rossum-agent-client -r prompt.md

# Cautious mode — agent confirms before making changes
rossum-agent-client --mcp-mode read-write --persona cautious -x "Delete the 'obsolete_field' from queue 12345 schema"
```

### CLI Flags

| Flag | Purpose | Default |
|------|---------|---------|
| `-x PROMPT` | Execute prompt directly | — |
| `-r FILE` | Read prompt from file | — |
| `--mcp-mode` | `read-only` or `read-write` | `read-only` |
| `--persona` | `default` or `cautious` | `default` |
| `--show-thinking` | Show reasoning + tool calls on stderr | off |

### Output Behavior

- **stdout**: Final answer text only — pipe-friendly, machine-readable
- **stderr**: Progress, tool calls, token usage
- **Files**: Agent-created files (CSVs, PDFs) are saved to the current directory

## What the Rossum Agent Can Do

| Category | Capabilities |
|----------|-------------|
| Queues | List, inspect, configure, create queues |
| Schemas | Read/modify fields, formula fields, AI reasoning fields, lookup fields |
| Hooks | Create, configure, test serverless extensions |
| Rules | Validation rules with TxScript expressions |
| Annotations | Query, inspect, process document annotations |
| UI Settings | Configure queue UI layout and behavior |
| Documents | Generate mock PDFs, upload documents, verify extraction |
| Knowledge Base | Search Rossum platform documentation |

## Writing Effective Prompts

The Rossum Agent is an Opus 4.6-powered expert. Be specific about what you want.

| Pattern | Example |
|---------|---------|
| Be specific about the target | "On queue **12345**, list all schema fields with their types" |
| State the goal, not steps | "Add a required vendor_name field" not "First get the schema, then find the right section, then..." |
| Include IDs when known | "Queue 12345", "Hook 67890" — avoids ambiguity |
| Request structured output | "Return the result as JSON" or "Format as a markdown table" |
| Combine read + write | "Check if queue 12345 has a tax_id field; if not, add it as a required string" |

## Choosing MCP Mode

| Mode | Use When |
|------|---------|
| `read-only` | Querying, listing, inspecting, explaining — no side effects |
| `read-write` | Creating, modifying, or deleting any Rossum resource |

Default to `read-only`. Only escalate to `read-write` when the task explicitly requires mutations.

## Choosing Persona

| Persona | Use When |
|---------|---------|
| `default` | Standard tasks — agent acts autonomously |
| `cautious` | Destructive operations, production changes — agent plans first and confirms |

## Orchestrating with Other Systems

The CLI's stdout-only final answer makes it composable. Capture Rossum output and feed it into other tools.

```bash
# Get data from Rossum, use it downstream
QUEUES=$(rossum-agent-client -x "List all queue IDs and names as JSON")
# Now use $QUEUES in a Jira/Freshdesk/Slack API call

# Extract invoice data, create a ticket
INVOICE_DATA=$(rossum-agent-client -x "Get the latest annotation data from queue 12345 as JSON")
# Pass $INVOICE_DATA to Jira CLI, Freshdesk API, etc.

# Complex prompt from file for multi-step Rossum tasks
cat > /tmp/rossum-task.md << 'PROMPT'
On queue 12345:
1. List all fields that have no validation rules
2. For each, suggest an appropriate validation rule
3. Return as a JSON array of {field_name, suggested_rule}
PROMPT
rossum-agent-client -r /tmp/rossum-task.md
```

## Constraints

| Constraint | Value |
|-----------|-------|
| Chat creates | 30/min |
| Messages | 10/min |
| Message length | 50,000 chars max |
| Images per message | 5 (max 5 MB each, jpeg/png/gif/webp) |
| PDFs per message | 5 (max 20 MB each) |
| Timeout | 300s default |

## Errors

| Symptom | Cause | Fix |
|---------|-------|-----|
| "Missing required configuration" | Env var not set | Set `ROSSUM_AGENT_API_URL`, `ROSSUM_API_BASE_URL`, `ROSSUM_API_TOKEN` |
| 401 | Bad or expired token | Get a fresh `ROSSUM_API_TOKEN` |
| 429 | Rate limit | Wait and retry (error includes retry-after) |
| Timeout | Complex task exceeded 300s | Break into smaller prompts |
| "read-only mode" error | Write attempted in read-only | Add `--mcp-mode read-write` |
