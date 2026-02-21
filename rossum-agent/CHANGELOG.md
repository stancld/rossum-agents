# Changelog - Rossum Agent

All notable changes to this project will be documented in this file.

---

## [Unreleased] - YYYY-MM-DD

### Added
- Added agent persona support (`default`, `cautious`) — settable at chat creation (`POST /api/v1/chats`) and overridable per message; persisted in chat metadata
- Added `SnapshotStore` — Redis-backed store (7-day TTL) that indexes full entity snapshots by `(entity_type, entity_id, commit_hash)` for point-in-time restore [#200](https://github.com/stancld/rossum-agents/pull/200)
- Added `show_entity_history` tool — lists all historical versions of a specific entity [#200](https://github.com/stancld/rossum-agents/pull/200)
- Added `restore_entity_version` tool — restores an entity to a specific historical version by commit hash [#200](https://github.com/stancld/rossum-agents/pull/200)
- Added `diff_objects` tool — computes unified diff between two JSON objects for explicit comparison requests [#200](https://github.com/stancld/rossum-agents/pull/200)

### Changed
- `revert_commit` no longer restricted to the latest commit — any historical commit can now be reverted [#200](https://github.com/stancld/rossum-agents/pull/200)

### Fixed
- Fixed schema revert failing under concurrent modifications — now retries with backoff on HTTP 412 (up to 5 attempts) using fetch-then-patch to register current state before each write [#200](https://github.com/stancld/rossum-agents/pull/200)

## [1.2.1] - 2026-02-18

### Added
- Added `lookup-fields` skill and `suggest_lookup_field`, `evaluate_lookup_field`, `get_lookup_dataset_raw_values`, `query_lookup_dataset` tools for creating and testing lookup fields backed by Master Data Hub datasets [#183](https://github.com/stancld/rossum-agents/pull/183)

### Changed
- Schema patching sub-agent pre-fetches schema tree structure and full schema content before invoking Opus, eliminating 2 redundant tool calls per patching run and reducing `max_iterations` from 5 to 3 [#196](https://github.com/stancld/rossum-agents/pull/196)

## [1.2.0] - 2026-02-17

### Added
- Added tool call and result persistence in conversation history for full replay in multi-turn conversations [#184](https://github.com/stancld/rossum-agents/pull/184)
- Moved `rossum-kb.json` into the `rossum_agent` package so it is included in installed distributions [#185](https://github.com/stancld/rossum-agents/pull/185)
- Added tool call argument logging in `_execute_tool_with_progress` for debugging agent behavior [#192](https://github.com/stancld/rossum-agents/pull/192)
- Added configuration change tracking system that records every mutation as a `ConfigCommit` with before/after snapshots, LLM-generated commit messages, and Redis persistence [#185](https://github.com/stancld/rossum-agents/pull/185)
- Added `show_change_history`, `show_commit_details`, and `revert_commit` agent tools for querying and managing configuration changes [#185](https://github.com/stancld/rossum-agents/pull/185)
- Extended `MCPConnection` with transparent read caching and write interception for change tracking [#185](https://github.com/stancld/rossum-agents/pull/185)
- Added config commit info (`config_commit_hash`, `config_commit_message`, `config_changes_count`) to `StreamDoneEvent` for TUI integration [#185](https://github.com/stancld/rossum-agents/pull/185)

### Changed
- Collapse repeated collapsible tool results (e.g. `patch_schema`) in `AgentMemory.write_to_messages()` — only the last result is sent in full to the LLM, earlier results are replaced with a short summary to reduce context bloat [#192](https://github.com/stancld/rossum-agents/pull/192)
- Changed `prune_schema_fields` `fields_to_keep` behavior — sections are no longer auto-included; list section IDs explicitly to preserve them as empty containers for `patch_schema` [#191](https://github.com/stancld/rossum-agents/pull/191)
- Simplified Knowledge Base cache — use bundled `data/rossum-kb.json` instead of downloading from a remote URL with disk caching [#187](https://github.com/stancld/rossum-agents/pull/187)

### Fixed
- Fixed schema patching sub-agent silently dropping fields when `parent_section` doesn't exist — now auto-creates the missing section [#189](https://github.com/stancld/rossum-agents/pull/189)
- Stagger concurrent `patch_schema` tool calls (0.5s delay between each) to avoid HTTP 412 conflicts from simultaneous schema writes [#192](https://github.com/stancld/rossum-agents/pull/192)

### Removed
- Removed `refresh_knowledge_base` function and `ROSSUM_KB_DATA_URL` env var (no longer needed with bundled data) [#187](https://github.com/stancld/rossum-agents/pull/187)
- Removed `httpx` dependency from `knowledge_base_search` module [#187](https://github.com/stancld/rossum-agents/pull/187)


## [1.1.4] - 2026-02-12

### Added
- Added `txscript` skill — standalone TxScript language reference for formula fields, serverless functions, and rule trigger conditions [#176](https://github.com/stancld/rossum-agents/pull/176)
- Added `fields_to_update` support to schema patching sub-agent for updating existing field properties (formula, label, type, ui_configuration) without removing and re-adding fields [#181](https://github.com/stancld/rossum-agents/pull/181)
- Added `formula` property support to `_build_field_node` so new formula fields retain their formula code [#181](https://github.com/stancld/rossum-agents/pull/181)

### Fixed
- Fixed schema patching sub-agent inability to update existing formula fields — previously only supported add/remove, now supports in-place updates via `action: "update"` [#181](https://github.com/stancld/rossum-agents/pull/181)
- Updated `schema-patching` and `formula-fields` skills with guidance on updating existing fields and explanation of why `update_schema` is intentionally hidden [#181](https://github.com/stancld/rossum-agents/pull/181)

### Changed
- Replaced local hook sandbox (`evaluate_python_hook`, `debug_hook`) with native Rossum API endpoint (`test_hook` MCP tool) [#176](https://github.com/stancld/rossum-agents/pull/176)
- Refactored `formula-fields` and `rules-and-actions` skills — extracted inline TxScript reference to the new `txscript` skill [#176](https://github.com/stancld/rossum-agents/pull/176)

### Removed
- Removed `hook-debugging` skill (hook testing now uses MCP tools directly) [#176](https://github.com/stancld/rossum-agents/pull/176)
- Removed hook debug sub-agent (`HookDebugSubAgent`, `debug_hook`, `evaluate_python_hook`) [#176](https://github.com/stancld/rossum-agents/pull/176)


## [1.1.3] - 2026-02-12

### Fixed
- Upgraded `rossum-api` dependency to fix hook-template deserialization



## [1.1.2] - 2026-02-11

### Added
- Added Slack integration: `POST /chats/{chat_id}/report-to-slack` endpoint to send chat transcripts to a Slack channel via `slack-sdk`, available as an optional `slack` extra [#178](https://github.com/stancld/rossum-agents/pull/178)

### Fixed
- Fixed output files lost after SSE keepalive by moving chat-bound state (`output_dir`, `last_memory`) off context vars to `_ChatRunState` keyed by chat_id — `asyncio.create_task()` in keepalive copied the context, so mutations inside the task never propagated back to the caller


## [1.1.1] - 2026-02-10

### Added
- Added SSE keepalive mechanism to prevent reverse proxies from dropping connections during prolonged agent thinking periods [#174](https://github.com/stancld/rossum-agents/pull/174)


## [1.1.0] - 2026-02-09

### Added
- Added API request cancellation: explicit `POST /chats/{chat_id}/cancel` endpoint, automatic cancellation on client disconnect, and automatic cancellation of superseded requests when a new message is sent to the same chat [#165](https://github.com/stancld/rossum-agents/pull/165)
- Added prompt caching (`cache_control`) for system prompt, tools, and conversation history to reduce input token costs by up to 90% on cached content [#161](https://github.com/stancld/rossum-agents/pull/161)
- Added `kb_grep` and `kb_get_article` tools for direct regex search and article retrieval from pre-scraped Knowledge Base articles [#161](https://github.com/stancld/rossum-agents/pull/161)
- Added `scrape_knowledge_base.py` script to scrape Rossum Knowledge Base via sitemap + Jina Reader and produce S3-hosted JSON [#161](https://github.com/stancld/rossum-agents/pull/161)
- Added task tracking system (`create_task`, `update_task`, `list_tasks` tools) for real-time progress visibility on multi-step operations, streamed via SSE `task_snapshot` events [#157](https://github.com/stancld/rossum-agents/pull/157)
- Added `search_elis_docs` sub-agent tool with `elis_openapi_jq` and `elis_openapi_grep` for querying the Rossum API OpenAPI specification directly [#154](https://github.com/stancld/rossum-agents/pull/154)
- Added Gunicorn server support for production deployments via `--server gunicorn` CLI flag [#152](https://github.com/stancld/rossum-agents/pull/152)
  - Gunicorn is now bundled with the `api` extra
  - Uses UvicornWorker for ASGI compatibility
- Added `prompt` and `context` field support to schema patching sub-agent for reasoning fields [#162](https://github.com/stancld/rossum-agents/pull/162)
- Added `rules-and-actions` skill for creating validation rules with TxScript trigger conditions and actions via `create_rule` [#167](https://github.com/stancld/rossum-agents/pull/167)
- Added `formula-fields` skill for creating/configuring formula fields with TxScript reference, messaging functions, and common patterns [#169](https://github.com/stancld/rossum-agents/pull/169)
- Added `reasoning-fields` skill for creating AI-powered reasoning fields with prompt/context configuration and instruction-writing guidance [#169](https://github.com/stancld/rossum-agents/pull/169)

### Changed
- Token usage breakdown now includes cache creation and cache read input token metrics [#161](https://github.com/stancld/rossum-agents/pull/161)
- Replaced live DuckDuckGo-based `search_knowledge_base` with pre-scraped KB articles using local `kb_grep`/`kb_get_article` tools [#161](https://github.com/stancld/rossum-agents/pull/161)
- Migrated default model from Opus 4.5 to Opus 4.6 [#156](https://github.com/stancld/rossum-agents/pull/156)
- Refactored API to use FastAPI's `app.state` for service instances instead of module-level globals [#153](https://github.com/stancld/rossum-agents/pull/153)
- Replaced `websockets` dependency with `wsproto` to fix deprecation warnings on Python 3.14
- Lazy load deploy tools only when `rossum-deployment` skill is activated [#164](https://github.com/stancld/rossum-agents/pull/164)

### Fixed
- Fixed default column list in `ui-settings` skill — removed non-existent `created_by`/`modified_by` meta names, added correct `modifier` [#172](https://github.com/stancld/rossum-agents/pull/172)
- Added read-only mode warning: agent now immediately stops and warns the user when a write operation is requested in read-only mode, instead of attempting and failing [#172](https://github.com/stancld/rossum-agents/pull/172)
- Task tracker tasks are now created in planned execution order for consistent progress display [#172](https://github.com/stancld/rossum-agents/pull/172)
- Fixed schema patching sub-agent: excluded `update_schema` from available tools to prevent accidental full-schema overwrites [#161](https://github.com/stancld/rossum-agents/pull/161)
- Fixed token counting to include cache creation and cache read tokens in input totals for accurate usage reporting [#161](https://github.com/stancld/rossum-agents/pull/161)
- Fixed incorrect field names (`is_formula`/`is_reasoning`) in base prompt — replaced with correct API field names [#161](https://github.com/stancld/rossum-agents/pull/161)

### Removed
- Removed `ddgs` dependency (replaced by pre-scraped KB article search) [#161](https://github.com/stancld/rossum-agents/pull/161)
- Removed Streamlit UI (`streamlit_app` submodule and all Streamlit dependencies) [#160](https://github.com/stancld/rossum-agents/pull/160)
- Removed Teleport JWT user isolation (`user_detection.py`, `PyJWT`, `cryptography` dependencies) [#155](https://github.com/stancld/rossum-agents/pull/155)


## [1.0.0] - 2026-02-05

### Added
- Added `create_schema_with_subagent` tool for creating new schemas from scratch via Opus sub-agent [#151](https://github.com/stancld/rossum-agents/pull/151)
- Added `schema-creation` skill documenting content array structure (sections, datapoints, multivalues, tuples) [#151](https://github.com/stancld/rossum-agents/pull/151)
- Added message-level `mcp_mode` parameter to override chat's mode per-message and persist for subsequent messages [#147](https://github.com/stancld/rossum-agents/pull/147)
- Added token usage visibility with breakdown by main agent vs sub-agents in API responses and Streamlit UI [#141](https://github.com/stancld/rossum-agents/pull/141)
- Added dynamic tool loading to reduce initial context usage (~8K → ~800 tokens) [#113](https://github.com/stancld/rossum-agents/pull/113)
- Added `load_tool_category(["queues", "schemas"])` internal tool to load MCP tools on-demand [#113](https://github.com/stancld/rossum-agents/pull/113)
- Added automatic pre-loading of tool categories based on keywords in user's first message [#113](https://github.com/stancld/rossum-agents/pull/113)
- Added read-only mode support - write tools (`read_only=false`) are excluded when MCP runs in read-only mode [#141](https://github.com/stancld/rossum-agents/pull/141)
- Added PDF document upload support for both REST API and Streamlit UI. Documents are stored in session output directory for agent use (e.g., upload to Rossum) [#102](https://github.com/stancld/rossum-agents/pull/102)
- Added skills system for dynamic skill loading from markdown files [#73](https://github.com/stancld/rossum-agents/pull/73)
- Added `hook-debugging` skill for systematic hook debugging workflow [#73](https://github.com/stancld/rossum-agents/pull/73)
- Added `rossum-deployment` skill for workspace deployment workflows [#73](https://github.com/stancld/rossum-agents/pull/73)
- Added deployment-related internal tools: `pull_workspace`, `compare_workspaces`, `copy_workspace`, `get_id_mapping` [#73](https://github.com/stancld/rossum-agents/pull/73)
- Added `list_local_files` and `clean_schema_dict` internal tools [#73](https://github.com/stancld/rossum-agents/pull/73)
- Added logging for deploy tools usage [#73](https://github.com/stancld/rossum-agents/pull/73)
- Added extended thinking support with configurable budget (default 10k tokens) for improved reasoning [#92](https://github.com/stancld/rossum-agents/pull/92)
- Added `organization-setup` skill for new customer onboarding with template-based queue creation [#102](https://github.com/stancld/rossum-agents/pull/102)
- Added `schema-pruning` skill for efficient removal of unwanted schema fields [#102](https://github.com/stancld/rossum-agents/pull/102)
- Added `patch_schema_with_subagent` tool for safe schema patching with Opus sub-agent verification [#102](https://github.com/stancld/rossum-agents/pull/102)
- Added MCP helpers module for shared sub-agent utilities [#102](https://github.com/stancld/rossum-agents/pull/102)
- Added Rossum Local Copilot integration for formula field suggestions [#102](https://github.com/stancld/rossum-agents/pull/102)

### Changed
- Execute multiple tool calls in parallel using `asyncio.wait()` instead of sequential execution [#127](https://github.com/stancld/rossum-agents/pull/127)
- Migrated knowledge base search from sync `requests` to async `httpx` with parallel webpage fetching via `asyncio.gather()` [#127](https://github.com/stancld/rossum-agents/pull/127)
- Refactored sub-agents (hook_debug, schema_patching, knowledge_base) to shared `SubAgent` base class with unified iteration loop [#107](https://github.com/stancld/rossum-agents/pull/107)
- Added token tracking to all sub-agents with counts propagated via `SubAgentResult` [#107](https://github.com/stancld/rossum-agents/pull/107)
- Migrated default model from Sonnet 4.5 to Opus 4.5 with significantly simplified prompts [#99](https://github.com/stancld/rossum-agents/pull/99)
- Separated model's chain-of-thought reasoning (thinking blocks) from response text (text blocks) in stream processing [#92](https://github.com/stancld/rossum-agents/pull/92)
- Updated Streamlit UI to display thinking blocks with "🧠 **Thinking:**" label [#92](https://github.com/stancld/rossum-agents/pull/92)
- Refactored `internal_tools.py` into modular `tools/` subpackage with separate modules for file tools, spawn MCP, knowledge base search, hook debugging, and skills [#78](https://github.com/stancld/rossum-agents/pull/78)
- Reorganized sub-agent tools into `tools/subagents/` module (hook_debug, knowledge_base, schema_patching) [#102](https://github.com/stancld/rossum-agents/pull/102)
- Improved multi-turn conversation by passing context properly [#73](https://github.com/stancld/rossum-agents/pull/73)
- Improved sub-agent knowledge base info panel [#73](https://github.com/stancl/rossum-mcp/pull/73)
- Made token owner selection stricter in deployment tools [#73](https://github.com/stancld/rossum-agents/pull/73)
- Display workspace diffs in a concise way [#73](https://github.com/stancld/rossum-agents/pull/73)
- Improved result analyzing UX for sub-agent responses [#85](https://github.com/stancld/rossum-agents/pull/85)

### Removed
- Removed test front-end from rossum-agent API as it doesn't fit the repo scope [#83](https://github.com/stancld/rossum-agents/pull/83)

### Fixed
- Fixed concurrent API request handling by isolating per-request state with contextvars [#148](https://github.com/stancld/rossum-agents/pull/148)
- Fixed `write_file` tool to accept dict/list content by auto-converting to JSON [#139](https://github.com/stancld/rossum-agents/pull/139)
- Fixed displaying generated files in Streamlit UI [#73](https://github.com/stancld/rossum-agents/pull/73)


## [0.2.7] - 2025-12-16

### Added
- Added `search_knowledge_base` internal tool for searching Rossum Knowledge Base documentation with Opus-powered analysis [#72](https://github.com/stancld/rossum-agents/pull/72)
- Added `evaluate_python_hook` internal tool for sandboxed hook execution against test annotation/schema data [#72](https://github.com/stancld/rossum-agents/pull/72)
- Added `debug_hook` internal tool using Opus sub-agent for iterative hook debugging with root cause analysis and fix suggestions [#72](https://github.com/stancld/rossum-agents/pull/72)
- Added `web_search` and `read_web_page` internal tools for web search capabilities [#72](https://github.com/stancld/rossum-agents/pull/72)
- Added multi-turn conversation guidelines to prompts [#72](https://github.com/stancld/rossum-agents/pull/72)

### Changed
- Improved tool result serialization in agent core to handle pydantic models and dataclasses properly [#72](https://github.com/stancld/rossum-agents/pull/72)
- Kept image in the context for the whole conversation [#72](https://github.com/stancld/rossum-agents/pull/72)
- Enabled short, concise answers by default [#72](https://github.com/stancld/rossum-agents/pull/72)
- Improved `list_hook` and `get_hook` MCP tool descriptions [#72](https://github.com/stancld/rossum-agents/pull/72)

### Fixed
- Fixed sending generated files to front-end in API responses [#72](https://github.com/stancld/rossum-agents/pull/72)


## [0.2.6] - 2025-12-15
- Made LLM response to be streamed in API [#70](https://github.com/stancld/rossum-agents/pull/70)


## [0.2.5] - 2025-12-14
- Added SSRF protection via URL validation for Rossum API endpoints [#69](https://github.com/stancld/rossum-agents/pull/69)
- Added path traversal and header injection protection for file downloads [#69](https://github.com/stancld/rossum-agents/pull/69)
- Added XSS protection via DOMPurify in test client [#69](https://github.com/stancld/rossum-agents/pull/69)


## [0.2.4] - 2025-12-14
- Added image input support [#67](https://github.com/stancld/rossum-agents/pull/67)
- Added logging of chat metadata into Redis for auditing [#62](https://github.com/stancld/rossum-agents/pull/62)
- Stopped replaying CoT in the model context [#61](https://github.com/stancld/rossum-agents/pull/61)
- Introduced storing a final answer in memory when no tool is called [#61](https://github.com/stancld/rossum-agents/pull/61)
- Added storing generated files in API and event to inform the client
- Added `preview` field to `/api/v1/chats` response with user request preview [#65](https://github.com/stancld/rossum-agents/pull/65)
- Separated Streamlit components into `streamlit_app` submodule as a standalone test-bed component [#66](https://github.com/stancld/rossum-agents/pull/66)


## [0.2.3] - 2025-12-10
- Handle invalid passed sideload to get_annotation gracefully [#60](https://github.com/stancld/rossum-agents/pull/60)


## [0.2.2] - 2025-12-10
- Pass extra context from URL to the LLM [#59](https://github.com/stancld/rossum-agents/pull/59)


## [0.2.1] - 2025-12-10
- Added FastAPI-based REST API with SSE streaming for real-time agent responses [#58](https://github.com/stancld/rossum-agents/pull/58)
  - Chat session management endpoints (create, list, get, delete)
  - Message endpoint with Server-Sent Events (SSE) for streaming agent responses
  - File management endpoints (list, download) for agent-generated artifacts
  - Rate limiting (30/min for chat creation, 10/min for messages)
  - Rossum API credential validation via headers (`X-Rossum-Token`, `X-Rossum-Api-Url`)


## [0.2.0] - 2025-12-09

### Breaking Changes
- Removed `smolagents` and `LiteLLM` dependencies
- Removed `file_system_tools.py`, `hook_analysis_tools.py`, `plot_tools.py` modules (replaced by Claude's native code execution)
- Removed old `agent.py` implementation

### Changed
- Migrated from smolagents + LiteLLM to Claude Agents SDK with direct Anthropic Bedrock integration
- Started using structured outputs to streamline agent instructions [#52](https://github.com/stancld/rossum-agents/pull/52)
- Streamlined system prompt [#53](https://github.com/stancld/rossum-agents/pull/53), [#54](https://github.com/stancld/rossum-agents/pull/54)
- Consolidated read_file and get_file_info tools into a single one [#54](https://github.com/stancld/rossum-agents/pull/54)

### Added
- New `bedrock_client.py` for direct AWS Bedrock integration
- New `mcp_tools.py` for async MCP server connection
- New `agent/` package with `core.py`, `memory.py`, `models.py`


## [0.1.8] - 2025-12-06
- Updated Rossum MCP to 0.2.0. See more info in the [release notes](https://github.com/stancld/rossum-agents/releases/tag/rossum-mcp-v0.2.0).


## [0.1.7] - 2025-12-04
- Fixed teleport user detection from JWT [#46](https://github.com/stancld/rossum-agents/pull/46)
- Made permalinks shareable across users [#47](https://github.com/stancld/rossum-agents/pull/47), [#48](https://github.com/stancld/rossum-agents/pull/48)


## [0.1.6] - 2025-12-03
- Improved teleport user detection [#45](https://github.com/stancld/rossum-agents/pull/45)


## [0.1.5] - 2025-12-03
- Added User ID to a Streamlit UI for debugging purposes


## [0.1.4] - 2025-12-03
- Added conversation permalinks persisted in Redis [#44](https://github.com/stancld/rossum-agents/pull/44)


## [0.1.3] - 2025-12-02
- Fixed leaking Rossum API credentials across users' session [#41](https://github.com/stancld/rossum-agents/pull/41)
- Fixed leaking generated files across users' session [#42](https://github.com/stancld/rossum-agents/pull/42)


## [0.1.2] - 2025-12-01
- Fixed using AWS Bedrock Model ARN [#39](https://github.com/stancld/rossum-agents/pull/39)


## [0.1.1] - 2025-12-01
- Fixed displaying mermaid diagrams in Streamlit UI [#36](https://github.com/stancld/rossum-agents/pull/36)
- Added beep sound notification upon completing the agent answer [#37](https://github.com/stancld/rossum-agents/pull/37)
- Added missing support for parsing AWS role params [#38](https://github.com/stancld/rossum-agents/pull/38)
