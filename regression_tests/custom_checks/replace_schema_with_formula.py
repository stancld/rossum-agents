"""Check that schema was replaced with a single formula field returning a constant."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from rossum_agent.agent.models import ToolResultStep

from regression_tests.custom_checks._utils import create_api_client, extract_datapoints, get_final_answer

if TYPE_CHECKING:
    from rossum_agent.agent.models import AgentStep


def _extract_schema_id_from_steps(steps: list[AgentStep]) -> int | None:
    """Extract schema_id from create_queue_from_template result or final answer."""
    for step in steps:
        if not isinstance(step, ToolResultStep):
            continue
        for tc in step.tool_calls:
            if tc.name == "create_queue_from_template":
                for tr in step.tool_results:
                    if tr.tool_call_id == tc.id and isinstance(tr.content, str):
                        match = re.search(r'"schema_id":\s*(\d+)', tr.content)
                        if match:
                            return int(match.group(1))

    # Fallback: extract from final answer
    if final_answer := get_final_answer(steps):
        match = re.search(r"\b(\d{5,})\b", final_answer)
        if match:
            return int(match.group(1))

    return None


def check_schema_replaced_with_formula(steps: list[AgentStep], api_base_url: str, api_token: str) -> tuple[bool, str]:
    """Verify schema contains only a single formula field with the expected constant."""
    schema_id = _extract_schema_id_from_steps(steps)
    if not schema_id:
        return False, "Could not find schema_id in agent steps"

    client = create_api_client(api_base_url, api_token)
    schema = client.retrieve_schema(schema_id)
    datapoints = extract_datapoints(schema.content)

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
