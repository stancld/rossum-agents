from __future__ import annotations

from typing import TYPE_CHECKING

from regression_tests.framework.models import RegressionRun

if TYPE_CHECKING:
    from rossum_agent.agent.core import RossumAgent
    from rossum_agent.agent.models import AgentStep


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
        if not step.is_streaming and step.tool_calls:
            all_tools.extend(tc.name for tc in step.tool_calls)

    total_input_tokens = agent.tokens.total_input
    total_output_tokens = agent.tokens.total_output

    final_steps = [s for s in all_steps if s.is_final]
    is_successful = bool(final_steps) and not any(s.error for s in all_steps)
    final_answer = final_steps[-1].final_answer if final_steps else None
    error = next((s.error for s in all_steps if s.error), None)

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
        if not step.is_streaming and step.tool_calls:
            all_tools.extend(tc.name for tc in step.tool_calls)

    total_input_tokens = agent.tokens.total_input
    total_output_tokens = agent.tokens.total_output

    final_steps = [s for s in steps if s.is_final]
    is_successful = bool(final_steps) and not any(s.error for s in steps)
    final_answer = final_steps[-1].final_answer if final_steps else None
    error = next((s.error for s in steps if s.error), None)

    return RegressionRun(
        steps=steps,
        all_tools=all_tools,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        is_successful=is_successful,
        final_answer=final_answer,
        error=error,
    )
