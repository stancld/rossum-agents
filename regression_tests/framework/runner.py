from __future__ import annotations

from typing import TYPE_CHECKING

from rossum_agent.agent.models import ErrorStep, FinalAnswerStep, ToolCall, ToolResultStep

from regression_tests.framework.models import RegressionRun

if TYPE_CHECKING:
    from rossum_agent.agent.core import RossumAgent
    from rossum_agent.agent.models import AgentStep


def _synthesize_tool_name(tc: ToolCall) -> str:
    """Enrich generic read-layer tool names with their entity argument.

    The MCP read layer replaced individual get_X/list_X tools with generic
    `get(entity, id)` and `search(query)` tools. This helper produces
    descriptive names like `get:queue` or `search:hook` so regression test
    expectations remain meaningful.
    """
    if tc.name == "get":
        entity = tc.arguments.get("entity", "")
        return f"get:{entity}" if entity else "get"
    if tc.name == "search":
        query = tc.arguments.get("query", {})
        entity = query.get("entity", "") if isinstance(query, dict) else ""
        return f"search:{entity}" if entity else "search"
    return tc.name


async def run_multiturn_regression_test(agent: RossumAgent, prompts: list[str]) -> RegressionRun:
    """Run the agent through multiple conversation turns, accumulating all steps.

    The agent's memory persists between turns so each prompt sees the full prior context.

    Args:
        agent: The RossumAgent instance to run.
        prompts: Ordered list of user prompts for each conversation turn.

    Returns:
        RegressionRun with all steps from all turns aggregated, final answer from last turn.
    """
    all_steps: list[AgentStep] = []

    for prompt in prompts:
        async for step in agent.run(prompt):
            all_steps.append(step)

    agent.log_token_usage_summary()

    all_tools: list[str] = []
    for step in all_steps:
        if isinstance(step, ToolResultStep):
            all_tools.extend(_synthesize_tool_name(tc) for tc in step.tool_calls)

    total_input_tokens = agent.tokens.total_input
    total_output_tokens = agent.tokens.total_output

    final_steps = [s for s in all_steps if isinstance(s, FinalAnswerStep)]
    error_steps = [s for s in all_steps if isinstance(s, ErrorStep)]
    is_successful = bool(final_steps) and not error_steps
    final_answer = final_steps[-1].final_answer if final_steps else None
    error = error_steps[0].error if error_steps else None

    return RegressionRun(
        steps=all_steps,
        all_tools=all_tools,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        is_successful=is_successful,
        final_answer=final_answer,
        error=error,
    )


async def run_regression_test(agent: RossumAgent, prompt: str) -> RegressionRun:
    """Run the agent and collect all steps + aggregated metrics.

    Args:
        agent: The RossumAgent instance to run.
        prompt: The prompt to send to the agent.

    Returns:
        RegressionRun with all steps and aggregated metrics.
    """
    steps: list[AgentStep] = []

    async for step in agent.run(prompt):
        steps.append(step)

    agent.log_token_usage_summary()

    all_tools: list[str] = []
    for step in steps:
        if isinstance(step, ToolResultStep):
            all_tools.extend(_synthesize_tool_name(tc) for tc in step.tool_calls)

    total_input_tokens = agent.tokens.total_input
    total_output_tokens = agent.tokens.total_output

    final_steps = [s for s in steps if isinstance(s, FinalAnswerStep)]
    error_steps = [s for s in steps if isinstance(s, ErrorStep)]
    is_successful = bool(final_steps) and not error_steps
    final_answer = final_steps[-1].final_answer if final_steps else None
    error = error_steps[0].error if error_steps else None

    return RegressionRun(
        steps=steps,
        all_tools=all_tools,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        is_successful=is_successful,
        final_answer=final_answer,
        error=error,
    )
