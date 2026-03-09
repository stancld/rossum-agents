"""Check that the cautious persona asks a clarifying question before creating a formula field."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rossum_agent.agent.models import ToolResultStep

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
