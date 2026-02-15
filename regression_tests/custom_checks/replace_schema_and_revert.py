"""Check that schema was replaced with a formula field and then reverted to its original state."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rossum_api import SyncRossumAPIClient
from rossum_api.dtos import Token
from rossum_api.models.schema import Datapoint

from regression_tests.custom_checks.replace_schema_with_formula import (
    _extract_schema_id_from_steps,
)

if TYPE_CHECKING:
    from rossum_agent.agent.models import AgentStep


def _agent_called_revert(steps: list[AgentStep]) -> bool:
    """Check that the agent called revert_commit at some point."""
    return any(tc.name == "revert_commit" for step in steps for tc in step.tool_calls)


def check_schema_replaced_and_reverted(
    steps: list[AgentStep],
    api_base_url: str,
    api_token: str,
) -> tuple[bool, str]:
    """Verify the agent reverted the schema back to its original (multi-field) state."""
    if not _agent_called_revert(steps):
        return False, "Agent never called revert_commit"

    schema_id = _extract_schema_id_from_steps(steps)
    if not schema_id:
        return False, "Could not find schema_id in agent steps"

    client = SyncRossumAPIClient(base_url=api_base_url, credentials=Token(api_token))
    schema = client.retrieve_schema(schema_id)

    datapoints = [node for section in schema.content for node in section.traverse() if isinstance(node, Datapoint)]

    if len(datapoints) <= 1:
        return (
            False,
            f"Schema {schema_id} still has only {len(datapoints)} datapoint(s) — revert did not restore original fields",
        )

    return (
        True,
        f"Schema {schema_id} reverted successfully — has {len(datapoints)} datapoints",
    )
