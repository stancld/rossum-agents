"""Check that schema was replaced with a single formula field returning a constant."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from rossum_api import SyncRossumAPIClient
from rossum_api.dtos import Token
from rossum_api.models.schema import Datapoint

if TYPE_CHECKING:
    from rossum_agent.agent.models import AgentStep


def _extract_schema_id_from_steps(steps: list[AgentStep]) -> int | None:
    """Extract schema_id from create_queue_from_template result or final answer."""
    for step in steps:
        for tc in step.tool_calls:
            if tc.name == "create_queue_from_template":
                for tr in step.tool_results:
                    if tr.tool_call_id == tc.id and isinstance(tr.content, str):
                        match = re.search(r'"schema_id":\s*(\d+)', tr.content)
                        if match:
                            return int(match.group(1))

    # Fallback: extract from final answer
    final_answer = next((s.final_answer for s in reversed(steps) if s.final_answer), None)
    if final_answer:
        match = re.search(r"\b(\d{5,})\b", final_answer)
        if match:
            return int(match.group(1))

    return None


def check_schema_replaced_with_formula(steps: list[AgentStep], api_base_url: str, api_token: str) -> tuple[bool, str]:
    """Verify schema contains only a single formula field with the expected constant."""
    schema_id = _extract_schema_id_from_steps(steps)
    if not schema_id:
        return False, "Could not find schema_id in agent steps"

    client = SyncRossumAPIClient(base_url=api_base_url, credentials=Token(api_token))
    schema = client.retrieve_schema(schema_id)

    # Collect all leaf datapoints across all sections using traverse()
    datapoints = [node for section in schema.content for node in section.traverse() if isinstance(node, Datapoint)]

    if len(datapoints) != 1:
        ids = [dp.id for dp in datapoints]
        return False, f"Expected exactly 1 datapoint, found {len(datapoints)}: {ids}"

    field = datapoints[0]

    ui_config = field.ui_configuration or {}
    if not isinstance(ui_config, dict) or ui_config.get("type") != "formula":
        return False, f"Field ui_configuration.type is not 'formula': {ui_config}"

    formula = field.formula or ""
    if not formula:
        return False, "Formula field has empty formula"

    if "We love Rossum" not in formula:
        return False, f"Formula does not contain expected constant 'We love Rossum': {formula}"

    return True, f"Schema {schema_id} has exactly 1 formula field returning 'We love Rossum'"
