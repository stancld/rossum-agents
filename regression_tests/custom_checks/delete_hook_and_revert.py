"""Check that hook was deleted and then the deletion was reverted."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rossum_agent.agent.models import AgentStep


def _agent_called_tool(steps: list[AgentStep], tool_name: str) -> bool:
    return any(tc.name == tool_name for step in steps for tc in step.tool_calls)


def _count_tool_calls(steps: list[AgentStep], tool_name: str) -> int:
    return sum(1 for step in steps for tc in step.tool_calls if tc.name == tool_name)


def check_hook_deleted_and_reverted(
    steps: list[AgentStep],
    api_base_url: str,
    api_token: str,
) -> tuple[bool, str]:
    """Verify the agent deleted a hook, reverted, and recreated it."""
    if not _agent_called_tool(steps, "delete_hook"):
        return False, "Agent never called delete_hook"

    if not _agent_called_tool(steps, "revert_commit"):
        return False, "Agent never called revert_commit"

    create_count = _count_tool_calls(steps, "create_hook") + _count_tool_calls(steps, "create_hook_from_template")
    if create_count < 2:
        return False, f"Expected create_hook to be called twice (initial + revert recreation), got {create_count}"

    return True, "Hook was created, deleted, reverted, and recreated"
