"""Task sub-agent for executing individual tasks from the TaskTracker.

Spawns a fresh sub-agent per task with clean context, scoped tools,
and a focused system prompt. The main agent acts as orchestrator,
delegating task execution here.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from anthropic import beta_tool

from rossum_agent.agent.skills import get_skill
from rossum_agent.prompts.base_prompt import (
    CHANGE_HISTORY,
    CONFIGURATION_WORKFLOWS,
    CRITICAL_REQUIREMENTS,
    TASK_SUBAGENT_EXPERT_INTRO,
)
from rossum_agent.tools.core import get_context
from rossum_agent.tools.dynamic_tools import is_skill_loaded
from rossum_agent.tools.subagents.base import SubAgent, SubAgentConfig
from rossum_agent.tools.subagents.mcp_helpers import call_mcp_tool
from rossum_agent.tools.task_tracker import TaskStatus

if TYPE_CHECKING:
    from typing import Any

logger = logging.getLogger(__name__)

# Tools that are orchestrator-only and should not be given to task sub-agents
_EXCLUDED_TOOLS = {
    "create_task",
    "update_task",
    "list_tasks",
    "load_skill",
    "load_tool_category",
    "load_tool",
    "ask_user_question",
    "list_tool_categories",
    "execute_task",
}


@dataclass
class TaskSubAgentConfig(SubAgentConfig):
    """Extended config for task sub-agents with mixed tool routing."""

    internal_tool_names: set[str] = field(default_factory=set)


class TaskSubAgent(SubAgent):
    """Sub-agent scoped to a single task from the TaskTracker.

    Unlike domain-specific sub-agents (schema creation, KB search) which have
    hardcoded tool sets, TaskSubAgent accepts arbitrary tools passed by the
    orchestrator at spawn time and routes execution to either internal tools
    or MCP tools based on the tool name.
    """

    def __init__(self, config: TaskSubAgentConfig) -> None:
        super().__init__(config)
        self._internal_tool_names = config.internal_tool_names

    def execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        if tool_name in self._internal_tool_names:
            from rossum_agent.tools import (  # noqa: PLC0415 - circular: tools/__init__ imports execute_task from here
                execute_internal_tool,
            )

            result = execute_internal_tool(tool_name, tool_input)
            return str(result)
        result = call_mcp_tool(tool_name, tool_input)
        if result is None:
            return "No data returned"
        return json.dumps(result, indent=2, default=str)

    def process_response_block(self, block: Any, iteration: int, max_iterations: int) -> dict[str, Any] | None:
        return None


def _build_task_system_prompt(skill_contents: list[str] | None = None) -> str:
    """Build a focused system prompt for task sub-agents.

    Includes core domain knowledge but excludes orchestration-specific
    sections (skill loading, task tracking, discovery workflow).
    """
    sections = [
        TASK_SUBAGENT_EXPERT_INTRO,
        CRITICAL_REQUIREMENTS,
        CONFIGURATION_WORKFLOWS,
        CHANGE_HISTORY,
        _TASK_SUBAGENT_INSTRUCTIONS,
    ]
    if skill_contents:
        sections.extend(skill_contents)
    return "\n\n---\n".join(sections)


_TASK_SUBAGENT_INSTRUCTIONS = """# Execution

You are executing a single task delegated by the orchestrator agent. Focus exclusively on this task.

| Rule | Detail |
|------|--------|
| Scope | Complete only the described task — nothing more |
| Tools | Use the provided tools as needed; do not request additional tools |
| Output | End with a clear summary of what was done and any important results (IDs, URLs, status) |
| Errors | If a tool fails, try an alternative approach or report the failure clearly |"""


def _build_task_prompt(subject: str, description: str, context: str) -> str:
    """Build the user message for a task sub-agent."""
    parts = []
    if context:
        parts.append(f"## Context from prior tasks\n{context}")
    parts.append(f"## Task: {subject}\n\n{description}")
    parts.append(
        "Complete this task using the available tools. "
        "Provide a clear summary of what was done and any important results."
    )
    return "\n\n".join(parts)


def _snapshot_tools_for_task(extra_mcp_tools: list[Any] | None = None) -> tuple[list[Any], set[str]]:
    """Snapshot currently loaded tools for a task sub-agent.

    Returns (tool_definitions, internal_tool_names) where tool_definitions
    are in Anthropic dict format and internal_tool_names identifies which
    tools should be routed to execute_internal_tool vs call_mcp_tool.

    extra_mcp_tools are transiently fetched MCP tools (e.g. from tool_categories)
    that should be included without being added to the main agent's context.
    """
    from rossum_agent.tools import (  # noqa: PLC0415 - circular: tools/__init__ imports execute_task from here
        get_internal_tool_names,
        get_internal_tools,
    )
    from rossum_agent.tools.dynamic_tools import get_dynamic_tools  # noqa: PLC0415 - same circular dependency chain

    all_internal_names = get_internal_tool_names()

    internal_tools = [t for t in get_internal_tools() if t.get("name") not in _EXCLUDED_TOOLS]
    internal_names = {t["name"] for t in internal_tools if t.get("name") in all_internal_names}

    dynamic_tools = [t for t in get_dynamic_tools() if t.get("name") not in _EXCLUDED_TOOLS]

    if extra_mcp_tools:
        existing_names = {t.get("name") for t in internal_tools + dynamic_tools}
        extra = [
            t for t in extra_mcp_tools if t.get("name") not in existing_names and t.get("name") not in _EXCLUDED_TOOLS
        ]
        dynamic_tools.extend(extra)

    return internal_tools + dynamic_tools, internal_names


@beta_tool
def execute_task(
    task_id: str,
    context: str = "",
    skills: list[str] | None = None,
    tool_categories: list[str] | None = None,
) -> str:
    """Execute a task from the task tracker using a dedicated sub-agent.

    Spawns a fresh sub-agent with clean context, scoped to this task only.
    The sub-agent gets the currently loaded MCP tools and relevant internal tools.

    Args:
        task_id: ID of the task to execute (from create_task).
        context: Optional context from prior tasks or the orchestrator.
            Include relevant IDs, URLs, or summaries the sub-agent needs.
        skills: Optional skill slugs (e.g. ["formula-fields"]) to load into the
            sub-agent. Skills are injected into the system prompt and their gated
            tools become available. Loaded transiently — does not affect main agent.
        tool_categories: Optional MCP tool categories (e.g. ["schemas", "queues"])
            to load for the sub-agent. Loaded transiently — does not affect main
            agent's tool list.

    Returns:
        JSON with task_id, subject, analysis, elapsed_ms, iterations_used,
        and token counts.
    """
    start_time = time.perf_counter()

    ctx = get_context()
    tracker = ctx.task_tracker
    if tracker is None:
        return json.dumps({"error": "Task tracking not available"})

    task = tracker.tasks.get(task_id)
    if task is None:
        return json.dumps({"error": f"Task {task_id} not found"})

    tracker.update_task(task_id, status=TaskStatus.in_progress)
    ctx.report_task_snapshot(tracker.snapshot())

    # Load skills transiently — mark loaded so gated internal tools are included
    # in the snapshot, then unmark after so they don't leak to the main agent
    skill_contents: list[str] = []
    newly_loaded_skills: list[str] = []
    if skills:
        from rossum_agent.tools.dynamic_tools import mark_skill_loaded  # noqa: PLC0415 - circular dependency chain

        for slug in skills:
            skill = get_skill(slug)
            if skill is None:
                logger.warning(f"Unknown skill '{slug}' — skipping")
                continue
            if not is_skill_loaded(slug):
                mark_skill_loaded(slug)
                newly_loaded_skills.append(slug)
            skill_contents.append(skill.content)

    # Fetch extra MCP tools transiently (not added to main agent's context)
    extra_mcp_tools: list[Any] | None = None
    if tool_categories:
        from rossum_agent.tools.dynamic_tools import fetch_category_tools  # noqa: PLC0415 - circular dependency chain

        extra_mcp_tools = fetch_category_tools(tool_categories) or None

    tools, internal_names = _snapshot_tools_for_task(extra_mcp_tools=extra_mcp_tools)

    # Clean up transiently loaded skills so they don't leak to main agent
    if newly_loaded_skills:
        from rossum_agent.tools.dynamic_tools import unmark_skill_loaded  # noqa: PLC0415 - circular dependency chain

        for slug in newly_loaded_skills:
            unmark_skill_loaded(slug)

    if not tools:
        return json.dumps({"error": "No tools available for task execution"})

    system_prompt = _build_task_system_prompt(skill_contents=skill_contents or None)
    user_message = _build_task_prompt(task.subject, task.description, context)

    config = TaskSubAgentConfig(
        tool_name=f"task_{task_id}",
        system_prompt=system_prompt,
        tools=tools,
        internal_tool_names=internal_names,
        max_iterations=15,
        max_tokens=16384,
    )

    logger.info(f"Spawning task sub-agent for task {task_id}: {task.subject} ({len(tools)} tools)")

    sub_agent = TaskSubAgent(config)
    result = sub_agent.run(user_message)

    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 3)

    is_error = result.analysis.startswith("Error calling Opus sub-agent")
    if is_error:
        tracker.update_task(task_id, status=TaskStatus.pending)
        logger.warning(f"Task {task_id} failed after {elapsed_ms:.1f}ms: {result.analysis[:200]}")
    else:
        tracker.update_task(task_id, status=TaskStatus.completed)
        logger.info(
            f"Task {task_id} completed in {elapsed_ms:.1f}ms "
            f"({result.iterations_used} iterations, "
            f"in={result.input_tokens}, out={result.output_tokens})"
        )
    ctx.report_task_snapshot(tracker.snapshot())

    return json.dumps(
        {
            "task_id": task_id,
            "subject": task.subject,
            "analysis": result.analysis,
            "is_error": is_error,
            "iterations_used": result.iterations_used,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "elapsed_ms": elapsed_ms,
        }
    )
