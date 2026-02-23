"""Slash command registry and handlers for the agent API."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC
from typing import TYPE_CHECKING, get_args

from rossum_agent.agent.skills import get_all_skills
from rossum_agent.api.models.schemas import Persona
from rossum_agent.prompts.base_prompt import PERSONA_BEHAVIORS
from rossum_agent.tools import INTERNAL_TOOLS
from rossum_agent.tools.dynamic_tools import (
    get_cached_category_tool_names,
    get_load_tool_category_definition,
    get_load_tool_definition,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from rossum_agent.api.services.chat_service import ChatService
    from rossum_agent.change_tracking.store import CommitStore

logger = logging.getLogger(__name__)

VALID_PERSONAS: tuple[str, ...] = get_args(Persona.__value__)

PERSONA_DESCRIPTIONS: dict[str, str] = {
    "default": "Balanced mode — acts autonomously, asks only when truly ambiguous",
    "cautious": "Plans first, asks before writes, verifies before and after changes",
}


@dataclass
class CommandDefinition:
    name: str
    description: str
    argument_suggestions: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class CommandContext:
    chat_id: str
    user_id: str | None
    credentials_api_url: str
    chat_service: ChatService
    commit_store: CommitStore | None
    args: list[str] = field(default_factory=list)


COMMANDS: dict[str, CommandDefinition] = {}


def _register(
    name: str,
    description: str,
    argument_suggestions: list[tuple[str, str]] | None = None,
) -> None:
    COMMANDS[name] = CommandDefinition(
        name=name,
        description=description,
        argument_suggestions=argument_suggestions or [],
    )


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
        badge = " **[REVERTED]**" if commit.reverted else ""
        lines.append(f"- `{commit.hash}` ({ts}) - {commit.message}{badge} ({len(commit.changes)} changes)")
        for change in commit.changes:
            lines.append(f'  - {change.entity_type} "{change.entity_name}" [{change.operation}]')
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

    base_url = "https://github.com/stancld/rossum-agents/blob/master/rossum-agent/rossum_agent/skills"
    lines = [f"**Available skills ({len(skills)}):**", ""]
    for skill in sorted(skills, key=lambda s: s.slug):
        goal = _extract_skill_goal(skill.content)
        suffix = f" - {goal}" if goal else ""
        url = f"{base_url}/{skill.slug}.md"
        lines.append(f"- [{skill.slug}]({url}){suffix}")
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


# -- /persona ----------------------------------------------------------------

_register(
    "/persona",
    "Get or switch the agent persona (e.g. `/persona cautious`)",
    argument_suggestions=[(p, PERSONA_DESCRIPTIONS[p]) for p in VALID_PERSONAS],
)


async def _handle_persona(ctx: CommandContext) -> str:
    chat_data = ctx.chat_service.get_chat_data(user_id=ctx.user_id, chat_id=ctx.chat_id)
    if chat_data is None:
        return "Chat not found."

    if not ctx.args:
        current = chat_data.metadata.persona
        lines = [f"Current persona: **{current}**", "", "Available personas:"]
        for p in VALID_PERSONAS:
            desc = PERSONA_DESCRIPTIONS.get(p, "")
            marker = " (active)" if p == current else ""
            lines.append(f"- `{p}`{marker} — {desc}" if desc else f"- `{p}`{marker}")
        return "\n".join(lines)

    requested = ctx.args[0].lower()
    if requested not in VALID_PERSONAS:
        available = ", ".join(f"`{p}`" for p in VALID_PERSONAS)
        return f"Unknown persona `{requested}`. Available personas: {available}"

    chat_data.metadata.persona = requested
    ctx.chat_service.save_messages(
        user_id=ctx.user_id,
        chat_id=ctx.chat_id,
        messages=chat_data.messages,
        metadata=chat_data.metadata,
    )
    behavior = PERSONA_BEHAVIORS.get(requested, "")
    parts = [f"Persona switched to **{requested}**."]
    if behavior:
        parts.append(f"\n{behavior.strip()}")
    return "\n".join(parts)


# -- /sow-mode ---------------------------------------------------------------

_register("/sow-mode", "Show, enable, or disable SoW mode: /sow-mode [on|off]")


async def _handle_sow_mode(ctx: CommandContext) -> str:
    arg = ctx.args[0].lower() if ctx.args else ""
    if arg not in ("on", "off", ""):
        return "Usage: `/sow-mode on` or `/sow-mode off`"

    chat_data = ctx.chat_service.get_chat_data(ctx.user_id, ctx.chat_id)
    if chat_data is None:
        return "Chat not found."

    if not arg:
        state = "enabled" if chat_data.metadata.sow_mode else "disabled"
        return f"SoW mode is currently {state}."

    enabled = arg == "on"
    if chat_data.metadata.sow_mode == enabled:
        state = "enabled" if enabled else "disabled"
        return f"SoW mode is already {state}."

    chat_data.metadata.sow_mode = enabled
    ctx.chat_service.save_messages(
        ctx.user_id,
        ctx.chat_id,
        chat_data.messages,
        metadata=chat_data.metadata,
    )

    if enabled:
        return (
            "**SoW mode enabled.** Before any significant implementation I will:\n"
            "1. Clarify whether the work targets a specific context (queue, workspace, etc.) or is general\n"
            "2. Create a Statement of Work for your approval\n"
            "3. Create an implementation plan and track each step"
        )
    return "**SoW mode disabled.** I will execute tasks directly without a formal SoW."


# -- Handler dispatch --------------------------------------------------------

_HANDLERS: dict[str, Callable[[CommandContext], Awaitable[str]]] = {
    "/list-commands": _handle_list_commands,
    "/list-commits": _handle_list_commits,
    "/list-skills": _handle_list_skills,
    "/list-mcp-tools": _handle_list_mcp_tools,
    "/list-agent-tools": _handle_list_agent_tools,
    "/persona": _handle_persona,
    "/sow-mode": _handle_sow_mode,
}


@dataclass
class ParsedCommand:
    """Result of parsing a slash command from user input."""

    name: str
    args: list[str]


def parse_command(text: str) -> ParsedCommand | None:
    """Extract the command name and arguments from user input, or None if not a command."""
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None
    parts = stripped.split()
    return ParsedCommand(name=parts[0].lower(), args=[p for p in parts[1:] if p])


async def execute_command(name: str, ctx: CommandContext) -> str:
    """Execute a slash command by name. Returns the formatted result text."""
    handler = _HANDLERS.get(name)
    if handler is None:
        return f"Unknown command `{name}`. Use `/list-commands` to see available commands."
    return await handler(ctx)
