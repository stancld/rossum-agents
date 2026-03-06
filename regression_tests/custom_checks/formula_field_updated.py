"""Check that a formula field was updated on the schema, not merely created."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from rossum_agent.agent.models import ToolResultStep

from regression_tests.custom_checks._utils import create_api_client, extract_datapoints, extract_schema_id_from_steps

if TYPE_CHECKING:
    from rossum_agent.agent.models import AgentStep


def _extract_subagent_formulas(changes_raw: object, field_id: str) -> list[str]:
    """Extract formulas from patch_schema_with_subagent changes JSON."""
    if not isinstance(changes_raw, str):
        return []

    try:
        changes = json.loads(changes_raw)
    except json.JSONDecodeError:
        return []

    if not isinstance(changes, list):
        return []

    formulas: list[str] = []
    for change in changes:
        if not isinstance(change, dict) or change.get("id") != field_id:
            continue

        formula = change.get("formula")
        if isinstance(formula, str) and formula:
            formulas.append(formula)
            continue

        field_definition = change.get("field_definition")
        if isinstance(field_definition, dict):
            nested_formula = field_definition.get("formula")
            if isinstance(nested_formula, str) and nested_formula:
                formulas.append(nested_formula)

    return formulas


def _extract_formula_changes(steps: list[AgentStep], field_id: str) -> list[str]:
    """Collect formulas applied to a field via patch_schema or patch_schema_with_subagent."""
    formulas: list[str] = []

    for step in steps:
        if not isinstance(step, ToolResultStep):
            continue

        for tc in step.tool_calls:
            if tc.name == "patch_schema":
                if tc.arguments.get("node_id") != field_id:
                    continue
                node_data = tc.arguments.get("node_data")
                if isinstance(node_data, dict):
                    formula = node_data.get("formula")
                    if isinstance(formula, str) and formula:
                        formulas.append(formula)

            if tc.name == "patch_schema_with_subagent":
                formulas.extend(_extract_subagent_formulas(tc.arguments.get("changes"), field_id))

    return formulas


def check_formula_field_updated(steps: list[AgentStep], api_base_url: str, api_token: str) -> tuple[bool, str]:
    """Verify the total_quantity formula changed between add/update operations."""
    schema_id = extract_schema_id_from_steps(steps)
    if not schema_id:
        return False, "Could not find schema_id in agent steps"

    formulas = _extract_formula_changes(steps, "total_quantity")
    if len(formulas) < 2:
        return False, f"Expected at least 2 formula changes for total_quantity, found {len(formulas)}"

    first_formula = formulas[0]
    last_formula = formulas[-1]
    if first_formula == last_formula:
        return False, f"Formulas are identical — update did not change the formula: {first_formula}"

    client = create_api_client(api_base_url, api_token)
    schema = client.retrieve_schema(schema_id)
    datapoints = extract_datapoints(schema.content)
    field = next((dp for dp in datapoints if dp.id == "total_quantity"), None)
    if field is None:
        return False, f"total_quantity field not found in schema {schema_id}"

    final_formula = field.formula or ""
    if not final_formula:
        return False, "total_quantity field has empty final formula"

    if final_formula != last_formula:
        return False, "Final schema formula does not match the last schema patch applied to total_quantity"

    if "all_values" not in final_formula:
        return False, f"Updated formula does not use all_values: {final_formula}"

    return True, f"Formula updated from '{first_formula[:80]}...' to '{final_formula[:80]}...'"
