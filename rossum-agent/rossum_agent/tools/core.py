"""Core module with shared types, callbacks, and MCP state management.

This module provides the foundational types and state management used by
all internal tools. Uses contextvars for thread-safe state management.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncio

    from rossum_agent.change_tracking.store import CommitStore, SnapshotStore
    from rossum_agent.rossum_mcp_integration import MCPConnection
    from rossum_agent.tools.task_tracker import TaskTracker


@dataclass
class SubAgentProgress:
    """Progress information from a sub-agent (e.g., schema creation Opus sub-agent)."""

    tool_name: str
    iteration: int
    max_iterations: int
    current_tool: str | None = None
    tool_calls: list[str] = field(default_factory=list)
    status: str = "running"


@dataclass
class SubAgentTokenUsage:
    """Token usage from a sub-agent call."""

    tool_name: str
    input_tokens: int
    output_tokens: int
    iteration: int | None = None
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass
class SubAgentText:
    """Text output from a sub-agent (e.g., schema creation Opus sub-agent)."""

    tool_name: str
    text: str
    is_final: bool = False


SubAgentProgressCallback = Callable[[SubAgentProgress], None]
SubAgentTextCallback = Callable[[SubAgentText], None]
SubAgentTokenCallback = Callable[[SubAgentTokenUsage], None]
TaskSnapshotCallback = Callable[[list[dict[str, object]]], None]

# Context variables for thread-safe state management
_progress_callback: ContextVar[SubAgentProgressCallback | None] = ContextVar("progress_callback", default=None)
_text_callback: ContextVar[SubAgentTextCallback | None] = ContextVar("text_callback", default=None)
_token_callback: ContextVar[SubAgentTokenCallback | None] = ContextVar("token_callback", default=None)
_task_snapshot_callback: ContextVar[TaskSnapshotCallback | None] = ContextVar("task_snapshot_callback", default=None)
_task_tracker: ContextVar[TaskTracker | None] = ContextVar("task_tracker", default=None)
_mcp_connection: ContextVar[MCPConnection | None] = ContextVar("mcp_connection", default=None)
_mcp_event_loop: ContextVar[asyncio.AbstractEventLoop | None] = ContextVar("mcp_event_loop", default=None)
_mcp_mode: ContextVar[str] = ContextVar("mcp_mode", default="read-only")
_output_dir: ContextVar[Path | None] = ContextVar("output_dir", default=None)
_rossum_credentials: ContextVar[tuple[str, str] | None] = ContextVar("rossum_credentials", default=None)
_commit_store: ContextVar[CommitStore | None] = ContextVar("commit_store", default=None)
_snapshot_store: ContextVar[SnapshotStore | None] = ContextVar("snapshot_store", default=None)
_rossum_environment: ContextVar[str | None] = ContextVar("rossum_environment", default=None)


def set_progress_callback(callback: SubAgentProgressCallback | None) -> None:
    _progress_callback.set(callback)


def set_text_callback(callback: SubAgentTextCallback | None) -> None:
    _text_callback.set(callback)


def set_token_callback(callback: SubAgentTokenCallback | None) -> None:
    _token_callback.set(callback)


def report_progress(progress: SubAgentProgress) -> None:
    if (callback := _progress_callback.get()) is not None:
        callback(progress)


def report_text(text: SubAgentText) -> None:
    if (callback := _text_callback.get()) is not None:
        callback(text)


def report_token_usage(usage: SubAgentTokenUsage) -> None:
    if (callback := _token_callback.get()) is not None:
        callback(usage)


def set_output_dir(output_dir: Path | None) -> None:
    _output_dir.set(output_dir)


def get_output_dir() -> Path:
    """Get the output directory for internal tools."""
    if (output_dir := _output_dir.get()) is not None:
        return output_dir
    fallback = Path("./outputs")
    fallback.mkdir(exist_ok=True)
    return fallback


def set_mcp_connection(
    connection: MCPConnection | None,
    loop: asyncio.AbstractEventLoop | None,
    mcp_mode: str = "read-only",
) -> None:
    _mcp_connection.set(connection)
    _mcp_event_loop.set(loop)
    _mcp_mode.set(mcp_mode)


def get_mcp_connection() -> MCPConnection | None:
    return _mcp_connection.get()


def get_mcp_event_loop() -> asyncio.AbstractEventLoop | None:
    return _mcp_event_loop.get()


def get_mcp_mode() -> str:
    return _mcp_mode.get()


def is_read_only_mode() -> bool:
    return _mcp_mode.get() != "read-write"


def set_rossum_credentials(api_base_url: str | None, token: str | None) -> None:
    if api_base_url and token:
        _rossum_credentials.set((api_base_url, token))
    else:
        _rossum_credentials.set(None)


def get_rossum_credentials() -> tuple[str, str] | None:
    """Get Rossum API credentials from context or environment.

    Checks context first (set by API service), then falls back to environment variables.

    Returns:
        Tuple of (api_base_url, token) or None if neither context nor env vars are set.
    """
    if (creds := _rossum_credentials.get()) is not None:
        return creds

    api_base = os.getenv("ROSSUM_API_BASE_URL")
    token = os.getenv("ROSSUM_API_TOKEN")
    if api_base and token:
        return api_base, token

    return None


def require_rossum_credentials() -> tuple[str, str]:
    """Get Rossum API credentials, raising if unavailable.

    Returns:
        Tuple of (api_base_url, token).

    Raises:
        ValueError: If credentials are not available.
    """
    if (creds := get_rossum_credentials()) is not None:
        return creds
    raise ValueError("Rossum API credentials not available (neither in context nor environment variables)")


def set_task_tracker(tracker: TaskTracker | None) -> None:
    _task_tracker.set(tracker)


def get_task_tracker() -> TaskTracker | None:
    return _task_tracker.get()


def set_task_snapshot_callback(callback: TaskSnapshotCallback | None) -> None:
    _task_snapshot_callback.set(callback)


def report_task_snapshot(snapshot: list[dict[str, object]]) -> None:
    if (callback := _task_snapshot_callback.get()) is not None:
        callback(snapshot)


def set_commit_store(store: CommitStore | None) -> None:
    _commit_store.set(store)


def get_commit_store() -> CommitStore | None:
    return _commit_store.get()


def set_snapshot_store(store: SnapshotStore | None) -> None:
    _snapshot_store.set(store)


def get_snapshot_store() -> SnapshotStore | None:
    return _snapshot_store.get()


def set_rossum_environment(environment: str | None) -> None:
    _rossum_environment.set(environment)


def get_rossum_environment() -> str | None:
    return _rossum_environment.get()
