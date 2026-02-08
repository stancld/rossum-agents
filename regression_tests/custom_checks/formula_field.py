"""Check that formula field aggregating table data is correctly configured."""

from __future__ import annotations

from typing import TYPE_CHECKING

from regression_tests.custom_checks._utils import call_haiku_check, extract_field_json_from_final_answer

if TYPE_CHECKING:
    from rossum_agent.agent.models import AgentStep

_FORMULA_EVAL = """Evaluate the following formula configured for a formula field that should aggregate table/line-item data.

Formula:
{formula}

Does this formula:
1. Reference line-item/table column(s) using field.<column_name>.all_values
2. Perform an aggregation (e.g., sum, count, max, min, or similar) over those values

Answer with a JSON object:
{{"passed": true/false, "reasoning": "Brief explanation"}}"""


def check_formula_field_for_table(steps: list[AgentStep], _api_base_url: str, _api_token: str) -> tuple[bool, str]:
    """Verify a formula field that aggregates table data is present and correct."""
    final_answer = next(
        (s.final_answer for s in reversed(steps) if s.final_answer),
        None,
    )
    if not final_answer:
        return False, "No final answer found"

    field = extract_field_json_from_final_answer(final_answer, "total_quantity")
    if not field:
        return False, "No total_quantity field JSON found in final answer"

    ui_config = field.get("ui_configuration", {})
    if not isinstance(ui_config, dict) or ui_config.get("type") != "formula":
        return False, f"Field ui_configuration.type is not 'formula': {ui_config}"

    formula = field.get("formula", "")
    if not formula:
        return False, "Formula field has empty formula"

    if "all_values" not in formula:
        return False, f"Formula does not use all_values: {formula}"

    return call_haiku_check(_FORMULA_EVAL.format(formula=formula))
