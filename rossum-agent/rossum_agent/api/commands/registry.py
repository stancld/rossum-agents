from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from rossum_agent.api.services.chat_service import ChatService
    from rossum_agent.change_tracking.store import CommitStore


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
HANDLERS: dict[str, Callable[[CommandContext], Awaitable[str]]] = {}


def register_command(
    name: str,
    description: str,
    handler: Callable[[CommandContext], Awaitable[str]],
    argument_suggestions: list[tuple[str, str]] | None = None,
) -> None:
    COMMANDS[name] = CommandDefinition(
        name=name,
        description=description,
        argument_suggestions=argument_suggestions or [],
    )
    HANDLERS[name] = handler
