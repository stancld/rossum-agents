"""Check that the cautious persona asks a clarifying question before creating a formula field."""

from __future__ import annotations

from typing import TYPE_CHECKING

from regression_tests.custom_checks._utils import agent_called_tool, call_haiku_check, get_final_answer

if TYPE_CHECKING:
    from rossum_agent.agent.models import AgentStep


_PROMPT = """Analyze the following agent response to a request for adding a formula field.

The user asked the agent to add a field called "The Net Terms" with logic to compute
'Due Date' - 'Issue Date' and categorize it as 'Net 15', 'Net 30' and 'Outstanding'.

Did the agent ask a clarifying or confirmation question instead of immediately adding the field into the schema?
A clarifying question could be about: ambiguous categorization thresholds, how to handle
missing dates, what "Outstanding" means exactly, confirmation before proceeding, etc.

Agent can use suggest_formula_field, but cannot add the suggestion to the schema.

Agent response:
{final_answer}

Answer with a JSON object:
{{"passed": true/false, "reasoning": "Explain whether the agent asked a clarifying question or just created the field without asking"}}

IMPORTANT: "passed": true means the agent asked at least one clarifying question.
"passed": false means the agent proceeded without asking any clarifying question."""


def check_cautious_persona_asks_clarification(
    steps: list[AgentStep], _api_base_url: str, _api_token: str
) -> tuple[bool, str]:
    """Verify the agent asked a clarifying question instead of blindly creating the formula field.

    Checks:
    - patch_schema / patch_schema_with_subagent were not called
    - Final answer contains a clarifying question (verified by Haiku)
    """
    if agent_called_tool(steps, "patch_schema") or agent_called_tool(steps, "patch_schema_with_subagent"):
        return False, "Agent called patch_schema/patch_schema_with_subagent instead of asking for clarification"

    final_answer = get_final_answer(steps)
    if not final_answer:
        return False, "No final answer found in agent steps"

    return call_haiku_check(_PROMPT.format(final_answer=final_answer[:12000]))
