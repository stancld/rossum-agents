"""Check that a multi-turn schema editing session was fully reverted."""

from __future__ import annotations

from typing import TYPE_CHECKING

from regression_tests.custom_checks._utils import agent_called_tool, create_api_client, extract_datapoints
from regression_tests.custom_checks.replace_schema_with_formula import _extract_schema_id_from_steps

if TYPE_CHECKING:
    from rossum_agent.agent.models import AgentStep


def check_multi_turn_schema_reverted(steps: list[AgentStep], api_base_url: str, api_token: str) -> tuple[bool, str]:
    """Verify the schema was reverted after a multi-turn session adding formula and reasoning fields.

    Checks:
    - revert_commit was called
    - are_reasoning_fields_enabled was called (agent verified feature availability)
    - Session-added fields (the_net_terms, recipient_country) are gone from the schema
    - Schema still has the original EU template fields (>= 5 datapoints)
    """
    if not agent_called_tool(steps, "restore_entity_version"):
        return False, "Agent never called restore_entity_version"

    if not agent_called_tool(steps, "are_reasoning_fields_enabled"):
        return False, "Agent never checked reasoning field availability (are_reasoning_fields_enabled not called)"

    schema_id = _extract_schema_id_from_steps(steps)
    if not schema_id:
        return False, "Could not find schema_id in agent steps"

    client = create_api_client(api_base_url, api_token)
    schema = client.retrieve_schema(schema_id)
    datapoints = extract_datapoints(schema.content)

    field_ids = {dp.id for dp in datapoints}
    leftover_fields = {"the_net_terms", "recipient_country"} & field_ids
    if leftover_fields:
        return False, f"Schema still contains session fields after revert: {leftover_fields}"

    if len(datapoints) < 5:
        return (
            False,
            f"Schema {schema_id} has too few fields ({len(datapoints)}) — revert may not have restored originals",
        )

    return True, f"Schema {schema_id} reverted: {len(datapoints)} original fields, no session fields remaining"
