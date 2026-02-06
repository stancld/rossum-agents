# Development Guidelines

**Goal**: Maintain code quality, consistency, and documentation across rossum-agents packages (rossum-mcp, rossum-agent, rossum-deploy, rossum-agent-client).

## Critical Constraints

- **No auto-commits** - Only `git commit`/`git push` when explicitly instructed
- **YAGNI** - Don't add functionality until needed. Remove unused code proactively.
- **Tests required** - New features and bug fixes must include tests
- **Docs in sync** - Tool changes require documentation updates

## Commands

| Task | Command |
|------|---------|
| Setup | `uv sync` or `uv pip install -e .` |
| Server | `python server.py` |
| Tests | `pytest` or `pytest path/to/test.py` |
| rossum-deploy tests | `cd rossum-deploy && pytest tests/` (required when modifying `workspace.py`) |
| Lint | `pre-commit run --all-files` |

## Architecture

- **rossum-mcp**: Single-file MCP server (`server.py`), `RossumMCPServer` class, 56 tools
- **rossum-agent**: AI agent with prompts in `rossum_agent/prompts/`, skills in `rossum_agent/skills/`
- Sync API client wrapped in async executors for MCP compatibility
- **New skills**: Add to `rossum_agent/prompts/base_prompt.py` ROSSUM_EXPERT_INTRO section

## Prompt Engineering (rossum-agent)

**rossum-agent uses Opus 4.6** - optimize prompts in `rossum_agent/prompts/` and `rossum_agent/skills/` accordingly:

| Principle | Implementation |
|-----------|----------------|
| Goals over procedures | "Goal: Deploy safely" not step-by-step instructions |
| Constraints over explanations | "Never mix credentials" - Opus infers consequences |
| Tables for structure | More token-efficient than prose lists |
| No redundancy | Don't explain what Opus can infer |
| Facts not warnings | State rules directly, skip "IMPORTANT" preambles |

## Code Style

| Rule | Example |
|------|---------|
| Python 3.12+ | Modern syntax required |
| Type hints | `str \| None` not `Optional[str]`, `list[str]` not `List[str]` |
| No `Any` | Use specific types |
| Imports | Standard library first, `from pathlib import Path` |
| Comments | Explain why, not what |
| No trailing commas | `[1, 2, 3]` not `[1, 2, 3,]` |
| Noqa comments | Always explain: `# noqa: TC003 - reason` |

## FastMCP Tools (rossum-mcp)

**Constraint**: Don't duplicate info between `description` and docstring.

```python
@mcp.tool(description="List users. Filter by username/email. Returns URLs usable as token_owner.")
async def list_users(
    username: str | None = None,
    email: str | None = None,
) -> list[User]:
    # No docstring - description + type hints sufficient
    ...
```

Add docstring only when: non-obvious formats, complex filtering, unclear defaults.

Import return types at module level (not TYPE_CHECKING) for FastMCP serialization.

## Documentation Updates

When adding/modifying tools, update:

| Tool Type | Files to Update |
|-----------|-----------------|
| MCP tools | `rossum-mcp/README.md`, `docs/source/index.rst`, `docs/source/usage.rst` |
| Agent tools | `rossum-agent/README.md`, `docs/source/index.rst`, `docs/source/usage.rst` |

Include: tool name, description, parameters with types, return format with JSON examples.

## Testing

| Scenario | Action |
|----------|--------|
| New functions | Unit tests |
| New MCP tools | Integration tests in `rossum-mcp/tests/test_server.py` |
| New agent tools | Tests in `rossum-agent/tests/` |
| Bug fixes | Regression tests |
| Modified logic | Update + add tests |

Structure: `tests/` mirrors source, pytest fixtures in `conftest.py`, imports at file top.

## SSE Streaming Contract (rossum-agent → rossum-agent-tui)

### SSE Event Types

Backend (`messages.py`) emits these SSE event names with corresponding payloads:

| SSE `event:` | Payload model (Python) | TS type (TUI) | Notes |
|--------------|------------------------|---------------|-------|
| `step` | `StepEvent` | `StepEvent` | Main event for all agent steps |
| `sub_agent_progress` | `SubAgentProgressEvent` | `SubAgentProgressEvent` | Sub-agent iteration updates |
| `sub_agent_text` | `SubAgentTextEvent` | `SubAgentTextEvent` | Sub-agent text streaming |
| `task_snapshot` | `TaskSnapshotEvent` | `TaskSnapshotEvent` | Task tracker state |
| `file_created` | `FileCreatedEvent` | `FileCreatedEvent` | Output file notification |
| `done` | `StreamDoneEvent` | `StreamDoneEvent` | Final event with token usage |
| `error` | `StepEvent` (exception path) | `{ message: string }` | **Mismatch — see Known Issues** |

### StepEvent.type Values

`StepEvent.type` is a `Literal` union shared across both sides:

| Type | When emitted | `is_streaming` | Key fields |
|------|-------------|----------------|------------|
| `thinking` | Model's chain-of-thought reasoning | `true` while streaming, `false` when finalized | `content` |
| `intermediate` | Model's response text before tool calls | `true` while streaming | `content` |
| `tool_start` | Tool execution begins | implicitly streaming (not explicitly marked) | `tool_name`, `tool_arguments`, `tool_progress` |
| `tool_result` | Tool execution completes | always `false` | `tool_name`, `result`, `is_error` |
| `final_answer` | Model's final response | `true` while streaming, `is_final=true` when done | `content` |
| `error` | Agent execution error | N/A, `is_final=true` | `content` |

### Streaming Lifecycle

| Behavior | Detail |
|----------|--------|
| `is_streaming: true` | Step is still in progress; may be replaced by updated events with the same `step_number`/`type` |
| `is_streaming: false` | Step is finalized; safe to commit to history |
| No final event guarantee | Thinking, intermediate, and tool_start steps may **only** arrive as `is_streaming: true` — the server moves to the next step without sending a finalized (`is_streaming: false`) event for the previous one |
| TUI implication | When `currentStreaming` changes to a different `step_number` or `type`, the previous streaming step must be committed to `completedSteps` before being replaced, otherwise it is silently lost |

### Tool Use Event Flow

The agent signals tool usage through two paired `StepEvent` types sharing the same `step_number`:

| Event type | Source | Key fields | When emitted |
|------------|--------|------------|--------------|
| `tool_start` | `agent_service._create_tool_start_event` | `tool_name`, `tool_arguments`, `tool_progress` | When the agent begins executing a tool; `tool_name` is display-formatted via `get_display_tool_name` |
| `tool_result` | `agent_service._create_tool_result_event` | `tool_name`, `result`, `is_error` | After tool execution completes (only emitted when `is_streaming=false`) |

**Pairing logic** (TUI `buildChatItems.ts`): `tool_result` steps are indexed by `stepNumber` into a map; each `tool_start` is paired with its matching `tool_result` to produce a single `ChatItem` of `kind: "tool_call"`.

**Rendering** (`ToolCall.tsx`): Tool calls are expandable. Collapsed shows tool name, args summary, status icon (✓/✗), and result preview. Expanded shows full arguments and full result.

**During streaming**: While a tool is executing, the TUI shows a `StreamingIndicator` with a spinner and tool name/progress. Sub-agent progress (for compound tools like `debug_hook`) is shown inline.

### Field Serialization

- Backend uses Pydantic `model_dump_json()` → snake_case keys (`step_number`, `tool_name`, `is_streaming`)
- TUI `StepEvent` interface mirrors snake_case field names directly
- TUI converts to camelCase `CompletedStep` via `stepToCompleted()` in `useChat.ts` for internal state
- `tool_progress`: Python `tuple[int, int]` serializes as JSON `[int, int]`; TS declares `number[] | null` (works but could be tightened to `[number, number] | null`)

### Known Issues & Contract Mismatches

#### 1. Error event payload mismatch (bug)
Backend exception handler (`messages.py:168`) emits `event: error` with a `StepEvent` JSON payload, but TUI expects `{ message: string }`. Result: `state.error` is set to `undefined`, losing the error message.
**Fix**: Change exception handler to emit `event: step` (not `event: error`) so it's handled by the existing `StepEvent` logic, or change payload to `{ message: str(e) }`.

#### 2. Dead `"text"` type check (bug)
`_process_agent_event` in `messages.py:71` checks `event.type == "text"`, but `StepEvent.type` never includes `"text"`. This branch is dead code.
**Fix**: Remove or change to the intended type (likely `"final_answer"` for streaming final answers).

#### 3. `StreamDoneEvent` missing `type` field (minor mismatch)
Python `StreamDoneEvent` has no `type` field; TUI type declares `type: "done"`. Not a runtime bug (TUI dispatches on the SSE event name, not `data.type`), but makes TS types inaccurate.
**Fix**: Add `type: Literal["done"] = "done"` to Python `StreamDoneEvent`, or remove `type` from TS `StreamDoneEvent`.

#### 4. `sub_agent_text` events silently dropped (missing feature)
Backend emits `sub_agent_text` events, TUI `SSEEvent` union includes them, but `useChat.ts` dispatch has no handler → events hit the default branch and are ignored.
**Fix**: Add `case "sub_agent_text":` handler to `useChat.ts` dispatch.

#### 5. Tool call pairing fragility (design risk)
Pairing by `step_number` alone assumes exactly one tool call per step. The internal `ToolCall` model already has an `id` field and `ToolResult` has `tool_call_id`, but these are **not exposed** in the SSE `StepEvent`. If multiple tools execute within one step or tool_start is emitted multiple times (progress updates), pairing can silently mis-pair or lose results.
**Fix (future)**: Expose `tool_call_id` in `StepEvent` and pair by that instead of `step_number`. Currently safe because `agent/core.py` emits one `tool_start` per tool per step and `tool_result` uses `step.tool_results[-1]` (last result only).

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `ROSSUM_API_TOKEN` | Required - API authentication |
| `ROSSUM_API_BASE_URL` | Required - API endpoint |
| `REDIS_HOST`, `REDIS_PORT` | Optional - Redis connection (default port: 6379) |
| `ROSSUM_MCP_MODE` | Optional - read-only or read-write |
| `PUBLIC_URL` | Optional - shareable links on remote servers |

## Planning Files

Place planning documents, task breakdowns, and scratch files in `.agents/` (gitignored).

## Code Review Checklist

- Type hints complete and accurate
- Error handling comprehensive
- Logging appropriate
- No security vulnerabilities
- Follows project conventions
- Tests exist for new functionality
