"""Slash command registry and handlers for the agent API."""

from __future__ import annotations

from dataclasses import dataclass

from rossum_agent.api.commands import history, listing
from rossum_agent.api.commands.listing import PERSONA_DESCRIPTIONS
from rossum_agent.api.commands.registry import COMMANDS, HANDLERS, CommandContext, CommandDefinition

__all__ = [
    "COMMANDS",
    "PERSONA_DESCRIPTIONS",
    "CommandContext",
    "CommandDefinition",
    "ParsedCommand",
    "execute_command",
    "history",
    "listing",
    "parse_command",
]


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
    return ParsedCommand(name=parts[0].lower(), args=[part for part in parts[1:] if part])


async def execute_command(name: str, ctx: CommandContext) -> str:
    """Execute a slash command by name. Returns the formatted result text."""
    handler = HANDLERS.get(name)
    if handler is None:
        return f"Unknown command `{name}`. Use `/list-commands` to see available commands."
    return await handler(ctx)
