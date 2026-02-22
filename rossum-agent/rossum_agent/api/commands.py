"""Slash command registry and handlers for the agent API."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC
from typing import TYPE_CHECKING

from rossum_agent.agent.skills import get_all_skills
from rossum_agent.tools import INTERNAL_TOOLS
from rossum_agent.tools.dynamic_tools import (
    get_cached_category_tool_names,
    get_load_tool_category_definition,
    get_load_tool_definition,
)

if TYPE_CHECKING:
    from rossum_agent.api.services.chat_service import ChatService
    from rossum_agent.change_tracking.store import CommitStore

logger = logging.getLogger(__name__)


@dataclass
class CommandDefinition:
    name: str
    description: str


@dataclass
class CommandContext:
    chat_id: str
    user_id: str | None
    credentials_api_url: str
    chat_service: ChatService
    commit_store: CommitStore | None


COMMANDS: dict[str, CommandDefinition] = {}


def _register(name: str, description: str) -> None:
    COMMANDS[name] = CommandDefinition(name=name, description=description)


# -- /list-commands ----------------------------------------------------------

_register("/list-commands", "List all available slash commands")


async def _handle_list_commands(ctx: CommandContext) -> str:
    lines = ["**Available commands:**", ""]
    for cmd in COMMANDS.values():
        lines.append(f"- `{cmd.name}` - {cmd.description}")
    return "\n".join(lines)


# -- /list-commits ----------------------------------------------------------

_register("/list-commits", "List configuration commits made in this chat")


async def _handle_list_commits(ctx: CommandContext) -> str:
    if ctx.commit_store is None:
        return "Commit tracking is not available (Redis not connected)."

    chat_data = ctx.chat_service.get_chat_data(user_id=ctx.user_id, chat_id=ctx.chat_id)
    if chat_data is None:
        return "Chat not found."

    commit_hashes = chat_data.metadata.config_commits
    if not commit_hashes:
        return "No configuration commits have been made in this chat yet."

    environment = ctx.credentials_api_url
    lines = ["**Configuration commits in this chat:**", ""]
    for h in commit_hashes:
        commit = ctx.commit_store.get_commit(environment, h)
        if commit is None:
            lines.append(f"- `{h}` - (expired or unavailable)")
            continue
        ts = commit.timestamp.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
        lines.append(f"- `{commit.hash}` ({ts}) - {commit.message} ({len(commit.changes)} changes)")
    return "\n".join(lines)


# -- /list-skills ------------------------------------------------------------

_register("/list-skills", "List available agent skills")


def _extract_skill_goal(content: str) -> str:
    """Extract the Goal line from a skill's markdown content."""
    for line in content.splitlines():
        if line.startswith("**Goal**:"):
            return line.removeprefix("**Goal**:").strip()
    return ""


async def _handle_list_skills(ctx: CommandContext) -> str:
    skills = get_all_skills()
    if not skills:
        return "No skills found."

    lines = [f"**Available skills ({len(skills)}):**", ""]
    for skill in sorted(skills, key=lambda s: s.slug):
        goal = _extract_skill_goal(skill.content)
        suffix = f" - {goal}" if goal else ""
        lines.append(f"- `{skill.slug}`{suffix}")
    return "\n".join(lines)


# -- /list-mcp-tools --------------------------------------------------------

_register("/list-mcp-tools", "List MCP tools by category")


async def _handle_list_mcp_tools(ctx: CommandContext) -> str:
    catalog = get_cached_category_tool_names()
    if catalog is None:
        return "MCP tool catalog not loaded yet. Send a message to the agent first to initialize the connection."

    total = sum(len(tools) for tools in catalog.values())
    lines = [f"**MCP tools ({total} tools in {len(catalog)} categories):**", ""]
    for category in sorted(catalog):
        tool_names = sorted(catalog[category])
        lines.append(f"**{category}** ({len(tool_names)})")
        for name in tool_names:
            lines.append(f"  - `{name}`")
        lines.append("")
    return "\n".join(lines)


# -- /list-agent-tools -------------------------------------------------------

_register("/list-agent-tools", "List built-in agent tools")


async def _handle_list_agent_tools(ctx: CommandContext) -> str:
    tools: list[tuple[str, str]] = []
    for tool in INTERNAL_TOOLS:
        d = tool.to_dict()
        tools.append((d["name"], d.get("description", "")))
    for defn in [get_load_tool_category_definition(), get_load_tool_definition()]:
        tools.append((defn["name"], defn.get("description", "")))

    tools.sort(key=lambda t: t[0])

    lines = [f"**Agent tools ({len(tools)}):**", ""]
    for name, desc in tools:
        first_line = desc.split("\n")[0] if desc else ""
        lines.append(f"- `{name}` - {first_line}")
    return "\n".join(lines)


# -- Handler dispatch --------------------------------------------------------

_HANDLERS: dict[str, object] = {
    "/list-commands": _handle_list_commands,
    "/list-commits": _handle_list_commits,
    "/list-skills": _handle_list_skills,
    "/list-mcp-tools": _handle_list_mcp_tools,
    "/list-agent-tools": _handle_list_agent_tools,
}


def parse_command(text: str) -> str | None:
    """Extract the command name from user input, or None if not a command."""
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None
    return stripped.split()[0].lower()


async def execute_command(name: str, ctx: CommandContext) -> str:
    """Execute a slash command by name. Returns the formatted result text."""
    handler = _HANDLERS.get(name)
    if handler is None:
        return f"Unknown command `{name}`. Use `/list-commands` to see available commands."
    return await handler(ctx)
