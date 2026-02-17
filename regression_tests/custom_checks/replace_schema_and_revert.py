"""Check that schema was replaced with a formula field and then reverted to its original state."""

from __future__ import annotations

from typing import TYPE_CHECKING

from regression_tests.custom_checks._utils import agent_called_tool, create_api_client, extract_datapoints
from regression_tests.custom_checks.replace_schema_with_formula import (
    _extract_schema_id_from_steps,
)

if TYPE_CHECKING:
    from rossum_agent.agent.models import AgentStep


def check_schema_replaced_and_reverted(steps: list[AgentStep], api_base_url: str, api_token: str) -> tuple[bool, str]:
    """Verify the agent reverted the schema back to its original (multi-field) state."""
    if not agent_called_tool(steps, "revert_commit"):
        return False, "Agent never called revert_commit"

    if not (schema_id := _extract_schema_id_from_steps(steps)):
        return False, "Could not find schema_id in agent steps"

    client = create_api_client(api_base_url, api_token)
    schema = client.retrieve_schema(schema_id)
    datapoints = extract_datapoints(schema.content)

    if len(datapoints) <= 1:
        return (
            False,
            f"Schema {schema_id} still has only {len(datapoints)} datapoint(s) — revert did not restore original fields",
        )

    return (
        True,
        f"Schema {schema_id} reverted successfully — has {len(datapoints)} datapoints",
    )
