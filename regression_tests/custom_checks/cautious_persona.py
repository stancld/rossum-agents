"""Check that the cautious persona asks a clarifying question before creating a formula field."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from rossum_agent.agent.models import ToolResultStep

from regression_tests.custom_checks._utils import agent_called_tool, call_haiku_check

if TYPE_CHECKING:
    from rossum_agent.agent.models import AgentStep


_PROMPT = """Analyze the following questions that an AI agent asked the user when requested to add a formula field.

The user asked the agent to add a field called "The Net Terms" with logic to compute
'Due Date' - 'Issue Date' and categorize it as 'Net 15', 'Net 30' and 'Outstanding'.

Instead of immediately adding the field, the agent asked the user these questions:
{questions}

Are these genuine clarifying or confirmation questions about the task?
A clarifying question could be about: ambiguous categorization thresholds, how to handle
missing dates, what "Outstanding" means exactly, confirmation before proceeding, etc.

Answer with a JSON object:
{{"passed": true/false, "reasoning": "Explain whether the questions are genuine clarifications about the formula field task"}}

IMPORTANT: "passed": true means the agent asked at least one meaningful clarifying question.
"passed": false means the questions are not genuine clarifications."""


def _extract_ask_user_questions(steps: list[AgentStep]) -> list[str]:
    """Extract question texts from ask_user_question tool calls."""
    questions: list[str] = []
    for step in steps:
        if not isinstance(step, ToolResultStep):
            continue
        for tc in step.tool_calls:
            if tc.name != "ask_user_question":
                continue
            args = tc.arguments
            if "questions" in args:
                questions.extend(str(q.get("question", "")) for q in args["questions"])
            elif "question" in args:
                questions.append(str(args["question"]))
    return questions


def check_cautious_persona_asks_clarification(
    steps: list[AgentStep], _api_base_url: str, _api_token: str
) -> tuple[bool, str]:
    """Verify the agent asked a clarifying question instead of blindly creating the formula field.

    Checks:
    - patch_schema / patch_schema_with_subagent were not called
    - Agent used ask_user_question with clarifying questions (verified by Haiku)
    """
    if agent_called_tool(steps, "patch_schema") or agent_called_tool(steps, "patch_schema_with_subagent"):
        return False, "Agent called patch_schema/patch_schema_with_subagent instead of asking for clarification"

    questions = _extract_ask_user_questions(steps)
    if not questions:
        return False, "Agent did not use ask_user_question tool"

    questions_text = json.dumps(questions, indent=2)
    return call_haiku_check(_PROMPT.format(questions=questions_text[:12000]))
