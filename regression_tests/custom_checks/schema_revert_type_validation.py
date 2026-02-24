"""Check that reverted schema has valid field types (not dicts) and expected fields."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from rossum_agent.agent.models import ToolResultStep

from regression_tests.custom_checks._utils import (
    agent_called_tool,
    create_api_client,
    extract_datapoints,
    get_final_answer,
)

if TYPE_CHECKING:
    from rossum_agent.agent.models import AgentStep

VALID_TYPES = {"string", "number", "date", "enum", "button"}


def _extract_schema_id(steps: list[AgentStep]) -> int | None:
    """Extract schema_id from tool call arguments (prune_schema_fields, revert_commit, etc.)."""
    for step in steps:
        if not isinstance(step, ToolResultStep):
            continue
        for tc in step.tool_calls:
            if tc.name in ("prune_schema_fields", "get_schema_tree_structure", "get_schema"):
                args = tc.arguments
                if isinstance(args, dict) and "schema_id" in args:
                    return int(args["schema_id"])

    # Fallback: extract from final answer
    if final_answer := get_final_answer(steps):
        match = re.search(r"\b(\d{5,})\b", final_answer)
        if match:
            return int(match.group(1))

    return None


def check_schema_reverted_with_valid_types(
    steps: list[AgentStep], api_base_url: str, api_token: str
) -> tuple[bool, str]:
    """Verify the reverted schema has multiple fields and all types are valid strings.

    Regression for: revert sending full snapshot with read-only fields, and
    sub-agent fallback producing {"type": {"type": "number"}} dicts.
    """
    if not agent_called_tool(steps, "revert_commit"):
        return False, "Agent never called revert_commit"

    if not (schema_id := _extract_schema_id(steps)):
        return False, "Could not find schema_id in agent steps"

    client = create_api_client(api_base_url, api_token)
    schema = client.retrieve_schema(schema_id)
    datapoints = extract_datapoints(schema.content)

    if len(datapoints) < 5:
        return (
            False,
            f"Schema {schema_id} has only {len(datapoints)} datapoints — revert likely failed",
        )

    # Validate all types are valid strings (not dicts)
    invalid = []
    for dp in datapoints:
        if dp.type not in VALID_TYPES:
            invalid.append(f"{dp.id}: type={dp.type!r}")

    if invalid:
        return False, f"Schema {schema_id} has invalid field types after revert: {invalid}"

    formula_fields = [dp for dp in datapoints if dp.formula]

    return (
        True,
        f"Schema {schema_id} reverted with {len(datapoints)} datapoints, "
        f"all types valid, {len(formula_fields)} formula field(s)",
    )
