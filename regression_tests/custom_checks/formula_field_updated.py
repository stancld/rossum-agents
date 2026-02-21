"""Check that a formula field was updated (not just added) on the schema.

The agent writes schema_v1.json (after adding the formula) and schema_v2.json
(after updating it). We parse both, find the total_quantity field, and verify
the formula actually changed.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from rossum_agent.agent.models import ToolResultStep

if TYPE_CHECKING:
    from rossum_agent.agent.models import AgentStep


def _extract_write_file_content(steps: list[AgentStep], filename: str) -> str | None:
    """Extract the content argument from a write_file tool call for a given filename."""
    for step in steps:
        if not isinstance(step, ToolResultStep):
            continue
        for tc in step.tool_calls:
            if tc.name != "write_file":
                continue
            if tc.arguments.get("filename", "") == filename:
                return tc.arguments.get("content")
    return None


def _find_field_formula(schema_content: str | dict | list, field_id: str) -> str | None:
    """Recursively find a field by id in a Rossum schema and return its formula."""
    if isinstance(schema_content, str):
        try:
            schema_content = json.loads(schema_content)
        except json.JSONDecodeError:
            return None

    if isinstance(schema_content, dict):
        if schema_content.get("id") == field_id:
            return schema_content.get("formula", "")
        for value in schema_content.values():
            result = _find_field_formula(value, field_id)
            if result is not None:
                return result

    if isinstance(schema_content, list):
        for item in schema_content:
            result = _find_field_formula(item, field_id)
            if result is not None:
                return result

    return None


def check_formula_field_updated(steps: list[AgentStep], _api_base_url: str, _api_token: str) -> tuple[bool, str]:
    """Compare schema_v1.json and schema_v2.json to verify the formula was updated."""
    v1_content = _extract_write_file_content(steps, "schema_v1.json")
    if v1_content is None:
        return False, "No write_file call found for schema_v1.json"

    v2_content = _extract_write_file_content(steps, "schema_v2.json")
    if v2_content is None:
        return False, "No write_file call found for schema_v2.json"

    v1_formula = _find_field_formula(v1_content, "total_quantity")
    if v1_formula is None:
        return False, "total_quantity field not found in schema_v1.json"

    v2_formula = _find_field_formula(v2_content, "total_quantity")
    if v2_formula is None:
        return False, "total_quantity field not found in schema_v2.json"

    if v1_formula == v2_formula:
        return False, f"Formulas are identical — update did not change the formula: {v1_formula}"

    if "all_values" not in v2_formula:
        return False, f"Updated formula does not use all_values: {v2_formula}"

    return True, f"Formula updated from '{v1_formula[:80]}...' to '{v2_formula[:80]}...'"
