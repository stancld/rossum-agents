# Development Guidelines

**Goal**: Maintain code quality, consistency, and documentation across rossum-agents packages (rossum-mcp, rossum-agent, rossum-deploy, rossum-agent-client).

## Critical Constraints

- **No auto-commits** - Only `git commit`/`git push` when explicitly instructed
- **Simplicity first** - Design the simplest solution that works. Fewer abstractions, fewer indirections, fewer layers. If a reader needs to jump through hoops to understand the code, it's too complex.
- **YAGNI** - Don't add functionality until needed. Remove unused code proactively.
- **Tests required** - New features and bug fixes must include tests
- **Docs in sync** - Tool changes require documentation updates

## Commands

| Task | Command |
|------|---------|
| Setup | `uv sync` or `uv pip install -e .` |
| Server | `rossum-mcp` (installed) or `python -m rossum_mcp.server` (dev) |
| Tests | `pytest` or `pytest path/to/test.py` |
| rossum-deploy tests | `cd rossum-deploy && pytest tests/` (required when modifying `workspace.py`) |
| Lint | `pre-commit run --all-files` |

## Architecture

- **rossum-mcp**: FastMCP server in `rossum_mcp/server.py`; tools registered from `rossum_mcp/tools/` modules, 67 tools
- **rossum-agent**: AI agent with prompts in `rossum_agent/prompts/`, skills in `rossum_agent/skills/`
- **rossum-agent-tui**: Development test-bed TUI for rossum-agent. Not production code — no tests required.
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
| No lazy imports | All imports at module level. No `import` inside functions/methods. |
| Comments | Explain why, not what |
| No trailing commas | Follow ruff-format output |
| Logging | f-strings in `logger.*()` calls are fine — prefer `logger.info(f"...")` over `%s` style |
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

### Adding New MCP Tools

| Step | Action |
|------|--------|
| Install latest SDK | Run `uv add rossum-api@latest` to get the newest `rossum-api` package |
| Leverage SDK | Check if `rossum-api` already provides models, dataclasses, type literals, or helper methods for the feature before writing custom code |
| Private SDK access | Usage of private/internal APIs in `rossum-api` is allowed — we control both packages |
| Use typed constructs | Prefer dataclasses, `Literal` types, enums, and typed models from `rossum-api` over plain strings or untyped dicts |
| API docs fallback | If the SDK doesn't cover the needed functionality, consult https://rossum.app/api/docs for the raw API spec |

### Adding New Rossum Capabilities (formula fields, reasoning fields, etc.)

When implementing support for Rossum-specific features, research them first:

| Source | URL | Purpose |
|--------|-----|---------|
| Knowledge Base | https://knowledge-base.rossum.ai/ | Feature concepts, configuration, and usage guides |
| API Docs | https://rossum.app/api/docs | API endpoints, request/response schemas |

## Documentation Updates

When adding/modifying tools, update:

| Tool Type | Files to Update |
|-----------|-----------------|
| MCP tools | `rossum-mcp/README.md`, `docs/source/index.rst`, `docs/source/usage.rst`, `docs/source/mcp_reference.rst` |
| Agent tools | `rossum-agent/README.md`, `docs/source/index.rst`, `docs/source/usage.rst`, `docs/source/skills_and_subagents.rst` |

Include: tool name, description, parameters with types, return format with JSON examples.

## Testing

| Scenario | Action |
|----------|--------|
| New functions | Unit tests |
| New MCP tools | Integration tests in `rossum-mcp/tests/tools/` and catalog tests in `rossum-mcp/tests/test_catalog.py` |
| New agent tools | Tests in `rossum-agent/tests/` |
| Bug fixes | Regression tests |
| Modified logic | Update + add tests |

Structure: `tests/` mirrors source, pytest fixtures in `conftest.py`, imports at file top.

**Exception**: `rossum-agent-tui` — dev-only test-bed, tests not required.

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

**During streaming**: While a tool is executing, the TUI shows a `StreamingIndicator` with a spinner and tool name/progress. Sub-agent progress (for compound tools like `create_schema_with_subagent`) is shown inline.

### Field Serialization

- Backend uses Pydantic `model_dump_json()` → snake_case keys (`step_number`, `tool_name`, `is_streaming`)
- TUI `StepEvent` interface mirrors snake_case field names directly
- TUI converts to camelCase `CompletedStep` via `stepToCompleted()` in `useChat.ts` for internal state
- `tool_progress`: Python `tuple[int, int]` serializes as JSON `[int, int]`; TS declares `number[] | null` (works but could be tightened to `[number, number] | null`)

### Known Issues & Contract Mismatches

#### 1. `StreamDoneEvent` missing `type` field (minor mismatch)
Python `StreamDoneEvent` has no `type` field; TUI type declares `type: "done"`. Not a runtime bug (TUI dispatches on the SSE event name, not `data.type`), but makes TS types inaccurate.
**Fix**: Add `type: Literal["done"] = "done"` to Python `StreamDoneEvent`, or remove `type` from TS `StreamDoneEvent`.

#### 2. `sub_agent_text` events not rendered (minor)
Backend emits `sub_agent_text` events; TUI handles them in dispatch but currently ignores them (`return prev`). Not a crash, but sub-agent text is not surfaced to the user.

#### 3. TUI `SSEEvent` union includes legacy `event: "error"` variant
TUI types still declare `{ event: "error"; data: { message: string } }` in `SSEEvent`, but the backend no longer emits `event: error` — errors are emitted as `event: step` with `StepEvent(type="error")`. The TUI type is dead code.

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `ROSSUM_API_TOKEN` | Required - API authentication |
| `ROSSUM_API_BASE_URL` | Required - API endpoint |
| `REDIS_HOST`, `REDIS_PORT` | Optional - Redis connection (default port: 6379) |
| `ROSSUM_MCP_MODE` | Optional - read-only or read-write |

## Planning Files

Place planning documents, task breakdowns, and scratch files in `.agents/` (gitignored).

## Code Review Checklist

- Type hints complete and accurate
- Error handling comprehensive
- Logging appropriate
- No security vulnerabilities
- Follows project conventions
- Tests exist for new functionality
