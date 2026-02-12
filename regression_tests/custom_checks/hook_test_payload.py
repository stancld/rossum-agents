"""Check that hook testing produced meaningful diagnostic output."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from regression_tests.custom_checks._utils import call_haiku_check

if TYPE_CHECKING:
    from rossum_agent.agent.models import AgentStep

logger = logging.getLogger(__name__)

_TEST_RESULTS_PROMPT = """Analyze the agent's final answer about creating and testing a serverless hook.

Final answer:
{final_answer}

Does the answer:
1. Report the results of testing the hook (e.g., from test_hook)
2. Indicate whether the hook executed successfully or failed

Answer with a JSON object:
{{"passed": true/false, "reasoning": "Brief explanation"}}"""


def check_hook_test_results_reported(steps: list[AgentStep], _api_base_url: str, _api_token: str) -> tuple[bool, str]:
    """Verify agent used test_hook and reported the results."""
    tool_names = [tc.name for step in steps for tc in step.tool_calls]

    if "test_hook" not in tool_names:
        return False, "test_hook was not called"

    for step in steps:
        for tr in step.tool_results:
            if tr.name == "test_hook":
                logger.info("test_hook result: %s", tr.content)

    final_answer = next(
        (s.final_answer for s in reversed(steps) if s.final_answer),
        None,
    )
    if not final_answer:
        return False, "No final answer found"

    return call_haiku_check(_TEST_RESULTS_PROMPT.format(final_answer=final_answer[:8000]))
