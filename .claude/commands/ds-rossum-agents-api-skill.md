# Rossum Agents API Skill

**Goal**: Use the Rossum Agent API to perform document processing tasks — querying queues, managing schemas, configuring hooks, and processing annotations on a Rossum instance.

## When to Use

| Scenario | Use This Skill |
|----------|---------------|
| User asks to query or modify Rossum configuration | Yes |
| User asks to process documents or invoices | Yes |
| User asks to manage queues, schemas, hooks, rules | Yes |
| User asks about Rossum platform capabilities | Yes |
| Task has nothing to do with Rossum | No |

## Prerequisites

| Requirement | How to Get |
|-------------|-----------|
| `ROSSUM_AGENT_API_URL` | Agent API endpoint (ask user or check environment) |
| `ROSSUM_API_BASE_URL` | Rossum API URL, e.g. `https://elis.rossum.ai/api/v1` |
| `ROSSUM_API_TOKEN` | Rossum authentication token |

Verify credentials are available before making any API calls. If missing, ask the user.

## Option A: CLI (Preferred for Single-Turn Tasks)

The `rossum-agent-client` CLI sends a prompt to the Rossum Agent and streams the response.

```bash
# Install if not available
uv pip install rossum-agent-client

# Execute a prompt (env vars must be set)
rossum-agent-client -x "List all queues"

# Read-write mode (required for mutations)
rossum-agent-client --mcp-mode read-write -x "Add a field 'tax_id' to schema on queue 12345"

# Read prompt from file
rossum-agent-client -r prompt.md

# Show agent reasoning and tool calls
rossum-agent-client --show-thinking -x "Explain the schema on queue 12345"
```

| Flag | Purpose |
|------|---------|
| `-x PROMPT` | Execute prompt directly |
| `-r FILE` | Read prompt from markdown file |
| `--mcp-mode read-write` | Allow write operations (default: `read-only`) |
| `--persona cautious` | Agent plans first, asks before writes (default: `default`) |
| `--show-thinking` | Display reasoning and tool arguments |

**Output**: Final answer goes to stdout, progress/tools/tokens go to stderr. Created files are saved to the current directory.

## Option B: Python Client (For Multi-Turn or Programmatic Use)

```python
from rossum_agent_client import RossumAgentClient
from rossum_agent_client.models import StepEvent, StreamDoneEvent, FileCreatedEvent

client = RossumAgentClient(
    agent_api_url="...",          # or os.environ["ROSSUM_AGENT_API_URL"]
    rossum_api_base_url="...",    # or os.environ["ROSSUM_API_BASE_URL"]
    token="...",                  # or os.environ["ROSSUM_API_TOKEN"]
)

# Create chat (one per conversation)
chat = client.create_chat(mcp_mode="read-only")

# Send message and collect final answer
final_answer = ""
for event in client.send_message_stream(chat.chat_id, "List all queues"):
    if isinstance(event, StepEvent) and event.type == "final_answer" and not event.is_streaming:
        final_answer = event.content or ""
    elif isinstance(event, StreamDoneEvent):
        pass  # Stream complete

print(final_answer)
```

### Multi-Turn Conversation

```python
# Same chat_id preserves context across turns
chat = client.create_chat(mcp_mode="read-write")

# Turn 1: query
collect_answer(client, chat.chat_id, "Show me queue 12345 schema")

# Turn 2: modify (agent remembers context from turn 1)
collect_answer(client, chat.chat_id, "Add a required field 'vendor_name' of type string")
```

### Sending Images and PDFs

```python
import base64
from rossum_agent_client.models import ImageContent, DocumentContent

# Image
with open("screenshot.png", "rb") as f:
    img = ImageContent(media_type="image/png", data=base64.b64encode(f.read()).decode())

for event in client.send_message_stream(chat_id, "What's in this image?", images=[img]):
    ...

# PDF
with open("invoice.pdf", "rb") as f:
    doc = DocumentContent(
        media_type="application/pdf",
        data=base64.b64encode(f.read()).decode(),
        filename="invoice.pdf",
    )

for event in client.send_message_stream(chat_id, "Process this invoice", documents=[doc]):
    ...
```

### Downloading Created Files

```python
# After streaming, check for FileCreatedEvent
created_files = []
for event in client.send_message_stream(chat_id, "Generate a test PDF"):
    if isinstance(event, FileCreatedEvent):
        created_files.append(event.filename)

# Download
for filename in created_files:
    content = client.download_file(chat_id, filename)
    Path(filename).write_bytes(content)
```

### Error Handling

```python
from rossum_agent_client.exceptions import (
    AuthenticationError,   # 401
    NotFoundError,         # 404
    RateLimitError,        # 429 (has .retry_after)
    ValidationError,       # 422
    ServerError,           # 5xx
    RossumAgentError,      # Base
)
```

## SSE Event Types Reference

| Event Type | Key Fields | When |
|------------|-----------|------|
| `thinking` | `content` | Agent reasoning (cumulative text) |
| `intermediate` | `content` | Partial response before tool calls |
| `tool_start` | `tool_name`, `tool_arguments` | Tool execution begins |
| `tool_result` | `tool_name`, `result`, `is_error` | Tool execution completes |
| `final_answer` | `content` | Agent's final response (cumulative text) |
| `error` | `content` | Execution error |
| `file_created` | `filename`, `url` | Output file generated |
| `sub_agent_progress` | `tool_name`, `iteration`, `status` | Sub-agent progress |
| `done` | `input_tokens`, `output_tokens` | Stream complete |

Text events (`thinking`, `intermediate`, `final_answer`) contain **cumulative content**. To get incremental text: `event.content[len(last_content):]`.

## What the Rossum Agent Can Do

| Category | Examples |
|----------|---------|
| Queues | List, inspect, configure queues |
| Schemas | Read, add/remove/update fields, formula fields, reasoning fields, lookup fields |
| Hooks | Create, configure, test hooks and extensions |
| Rules | Validation rules with TxScript expressions |
| Annotations | Query and process document annotations |
| UI Settings | Configure queue UI layout |
| Documents | Generate mock PDFs, upload, verify extraction |
| Knowledge Base | Search Rossum documentation |

## Choosing MCP Mode

| Mode | Use When |
|------|---------|
| `read-only` | Querying, inspecting, listing, explaining |
| `read-write` | Creating, modifying, deleting any Rossum resource |

Default to `read-only`. Only use `read-write` when the task requires mutations.

## Choosing Persona

| Persona | Behavior |
|---------|---------|
| `default` | Acts autonomously, asks only when ambiguous |
| `cautious` | Plans first, asks before writes, verifies changes |

Use `cautious` for destructive or high-impact operations.

## Constraints

- One chat session per logical task (use multi-turn for follow-ups)
- Rate limits: 30 chat creates/min, 10 messages/min
- Image limit: 5 per message, max 5 MB each (jpeg/png/gif/webp)
- PDF limit: 5 per message, max 20 MB each
- Message content: max 50,000 characters
- Timeout: 300s default (agent tasks can be long-running)
