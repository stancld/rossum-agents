"""Check that hook was deleted and then the deletion was reverted."""

from __future__ import annotations

from typing import TYPE_CHECKING

from regression_tests.custom_checks._utils import agent_called_tool, count_tool_calls

if TYPE_CHECKING:
    from rossum_agent.agent.models import AgentStep


def check_hook_deleted_and_reverted(steps: list[AgentStep], api_base_url: str, api_token: str) -> tuple[bool, str]:
    """Verify the agent deleted a hook and reverted (recreation is now auto-executed)."""
    if not agent_called_tool(steps, "delete_hook"):
        return False, "Agent never called delete_hook"

    if not agent_called_tool(steps, "revert_commit"):
        return False, "Agent never called revert_commit"

    # Initial creation is still required; revert recreation is now auto-executed by revert_commit
    create_count = count_tool_calls(steps, "create_hook") + count_tool_calls(steps, "create_hook_from_template")
    if create_count < 1:
        return False, f"Expected at least one create_hook call (initial creation), got {create_count}"

    return True, "Hook was created, deleted, and reverted (recreation auto-executed)"
