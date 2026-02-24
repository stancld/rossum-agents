"""Commands endpoint - lists available slash commands."""

from __future__ import annotations

from fastapi import APIRouter

from rossum_agent.api.commands import COMMANDS
from rossum_agent.api.models.schemas import ArgumentSuggestion, CommandInfo, CommandListResponse

router = APIRouter(prefix="/commands", tags=["commands"])


@router.get("", response_model=CommandListResponse)
async def list_commands() -> CommandListResponse:
    return CommandListResponse(
        commands=[
            CommandInfo(
                name=cmd.name,
                description=cmd.description,
                argument_suggestions=[ArgumentSuggestion(value=v, description=d) for v, d in cmd.argument_suggestions],
            )
            for cmd in COMMANDS.values()
        ]
    )
