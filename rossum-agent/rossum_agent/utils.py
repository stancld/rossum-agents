from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

# Base directory for all session outputs
BASE_OUTPUT_DIR = Path(tempfile.gettempdir()) / "rossum_agent_outputs"


def create_session_output_dir() -> Path:
    """Create a new session-specific output directory.

    Returns:
        Path to the newly created session directory
    """
    session_id = str(uuid.uuid4())
    session_dir = BASE_OUTPUT_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def add_message_cache_breakpoint(messages: list[dict[str, Any]]) -> None:
    """Add cache_control to the last content block of the last message.

    Mutates messages in-place. Removes any previous message-level
    cache_control breakpoints first to stay within Anthropic's
    4-breakpoint limit.
    """
    if not messages:
        return
    # Remove previous message-level cache_control breakpoints
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    block.pop("cache_control", None)
    # Add breakpoint to last message
    last_msg = messages[-1]
    content = last_msg.get("content")
    if isinstance(content, list) and content:
        last_block = content[-1]
        if isinstance(last_block, dict):
            last_block["cache_control"] = {"type": "ephemeral"}
    elif isinstance(content, str) and content:
        last_msg["content"] = [{"type": "text", "text": content, "cache_control": {"type": "ephemeral"}}]


def get_display_tool_name(tool_call_name: str, tool_arguments: dict[str, Any] | None = None) -> str:
    """Get display name for a tool, expanding call_on_connection to show the actual MCP tool.

    For call_on_connection, returns 'call_on_connection[connection_id.tool_name]' format.
    For other tools, returns the original name.
    """
    if tool_call_name == "call_on_connection" and tool_arguments:
        connection_id = tool_arguments.get("connection_id", "")
        inner_tool = tool_arguments.get("tool_name", "")
        if connection_id and inner_tool:
            return f"call_on_connection[{connection_id}.{inner_tool}]"
    return tool_call_name
