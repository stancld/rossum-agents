"""Tools for the Rossum Agent.

This package provides local tools executed directly by the agent (file operations, debugging, skills, etc.).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rossum_agent.tools.change_history import (
    diff_objects,
    restore_entity_version,
    revert_commit,
    show_change_history,
    show_commit_details,
    show_entity_history,
)
from rossum_agent.tools.core import (
    SubAgentProgress,
    SubAgentProgressCallback,
    SubAgentText,
    SubAgentTextCallback,
    SubAgentTokenCallback,
    SubAgentTokenUsage,
    get_commit_store,
    get_mcp_connection,
    get_mcp_event_loop,
    get_mcp_mode,
    get_output_dir,
    get_rossum_credentials,
    get_rossum_environment,
    get_snapshot_store,
    get_task_tracker,
    is_read_only_mode,
    report_progress,
    report_text,
    report_token_usage,
    require_rossum_credentials,
    set_commit_store,
    set_mcp_connection,
    set_output_dir,
    set_progress_callback,
    set_rossum_credentials,
    set_rossum_environment,
    set_snapshot_store,
    set_task_snapshot_callback,
    set_task_tracker,
    set_text_callback,
    set_token_callback,
)
from rossum_agent.tools.deploy import (
    DEPLOY_TOOLS,
    create_workspace,
    deploy_compare_workspaces,
    deploy_copy_org,
    deploy_copy_workspace,
    deploy_diff,
    deploy_pull,
    deploy_push,
    deploy_to_org,
    get_deploy_tool_names,
    get_deploy_tools,
)
from rossum_agent.tools.dynamic_tools import (
    DISCOVERY_TOOL_NAME,
    CatalogData,
    DynamicToolsState,
    get_dynamic_tools,
    get_load_tool_category_definition,
    get_load_tool_definition,
    get_loaded_categories,
    get_tools_version,
    get_write_tools,
    get_write_tools_async,
    is_skill_loaded,
    load_tool,
    load_tool_category,
    preload_categories_for_request,
    reset_dynamic_tools,
    suggest_categories_for_request,
)
from rossum_agent.tools.elis_backend_openapi_search import elis_openapi_grep, elis_openapi_jq, refresh_openapi_spec
from rossum_agent.tools.file_tools import write_file
from rossum_agent.tools.formula import suggest_formula_field
from rossum_agent.tools.knowledge_base_search import kb_get_article, kb_grep
from rossum_agent.tools.lookup import (
    evaluate_lookup_field,
    get_lookup_dataset_raw_values,
    query_lookup_dataset,
    suggest_lookup_field,
)
from rossum_agent.tools.skills import load_skill
from rossum_agent.tools.spawn_mcp import (
    SpawnedConnection,
    call_on_connection,
    cleanup_all_spawned_connections,
    clear_spawned_connections,
    close_connection,
    spawn_mcp_connection,
)
from rossum_agent.tools.subagents import (
    OPUS_MODEL_ID,
    patch_schema_with_subagent,
    search_elis_docs,
    search_knowledge_base,
)
from rossum_agent.tools.task_tracker import (
    TaskTracker,
    create_task,
    list_tasks,
    update_task,
)

if TYPE_CHECKING:
    from anthropic._tools import BetaTool  # ty: ignore[unresolved-import] - private API
    from anthropic.types import ToolParam

_ALWAYS_INTERNAL_TOOLS: list[BetaTool[..., str]] = [
    write_file,
    diff_objects,
    search_knowledge_base,
    search_elis_docs,
    patch_schema_with_subagent,
    suggest_formula_field,
    suggest_lookup_field,
    evaluate_lookup_field,
    get_lookup_dataset_raw_values,
    query_lookup_dataset,
    load_skill,
    create_task,
    update_task,
    list_tasks,
    elis_openapi_jq,
    elis_openapi_grep,
    kb_grep,
    kb_get_article,
]

_CHANGE_HISTORY_TOOLS: list[BetaTool[..., str]] = [
    show_change_history,
    show_commit_details,
    show_entity_history,
    revert_commit,
    restore_entity_version,
]

_DEPLOYMENT_INTERNAL_TOOLS: list[BetaTool[..., str]] = [
    spawn_mcp_connection,
    call_on_connection,
    close_connection,
]

_INTERNAL_TOOL_REGISTRY: dict[str, BetaTool[..., str]] = {
    t.name: t for t in (_ALWAYS_INTERNAL_TOOLS + _CHANGE_HISTORY_TOOLS + _DEPLOYMENT_INTERNAL_TOOLS)
}


def _get_active_internal_tools() -> list[BetaTool[..., str]]:
    """Get internal tools based on loaded skills."""
    tools = _ALWAYS_INTERNAL_TOOLS
    if get_commit_store() is not None:
        tools = tools + _CHANGE_HISTORY_TOOLS
    if is_skill_loaded("rossum-deployment"):
        tools = tools + _DEPLOYMENT_INTERNAL_TOOLS
    return tools


def get_internal_tools() -> list[ToolParam]:
    """Get internal tools in Anthropic format (deployment tools only when skill is loaded)."""
    return [tool.to_dict() for tool in _get_active_internal_tools()] + [
        get_load_tool_category_definition(),
        get_load_tool_definition(),
    ]


def get_internal_tool_names() -> set[str]:
    """Get names of all executable internal tools (always includes all for dispatch)."""
    return set(_INTERNAL_TOOL_REGISTRY.keys()) | {"load_tool_category", "load_tool"}


def execute_internal_tool(name: str, arguments: dict[str, object]) -> str:
    """Execute an internal tool by name.

    Args:
        name: The name of the tool to execute.
        arguments: The arguments to pass to the tool.

    Returns:
        The result of the tool execution as a string.

    Raises:
        ValueError: If the tool name is not recognized.
    """
    if name == "load_tool_category":
        raw_categories = arguments.get("categories", [])
        categories = [str(c) for c in raw_categories] if isinstance(raw_categories, list) else [str(raw_categories)]
        return load_tool_category(categories)

    if name == "load_tool":
        raw_tool_names = arguments.get("tool_names", [])
        tool_names = [str(t) for t in raw_tool_names] if isinstance(raw_tool_names, list) else [str(raw_tool_names)]
        return load_tool(tool_names)

    if tool := _INTERNAL_TOOL_REGISTRY.get(name):
        return tool(**arguments)

    raise ValueError(f"Unknown internal tool: {name}")


def execute_tool(name: str, arguments: dict[str, object], tools: list[BetaTool[..., str]]) -> str:
    """Execute a tool by name from the given tool set."""
    for tool in tools:
        if tool.name == name:
            return tool(**arguments)
    raise ValueError(f"Unknown tool: {name}")


INTERNAL_TOOLS = _ALWAYS_INTERNAL_TOOLS + _CHANGE_HISTORY_TOOLS + _DEPLOYMENT_INTERNAL_TOOLS

__all__ = [
    "DEPLOY_TOOLS",
    "DISCOVERY_TOOL_NAME",
    "INTERNAL_TOOLS",
    "OPUS_MODEL_ID",
    "CatalogData",
    "DynamicToolsState",
    "SpawnedConnection",
    "SubAgentProgress",
    "SubAgentProgressCallback",
    "SubAgentText",
    "SubAgentTextCallback",
    "SubAgentTokenCallback",
    "SubAgentTokenUsage",
    "TaskTracker",
    "call_on_connection",
    "cleanup_all_spawned_connections",
    "clear_spawned_connections",
    "close_connection",
    "create_task",
    "create_workspace",
    "deploy_compare_workspaces",
    "deploy_copy_org",
    "deploy_copy_workspace",
    "deploy_diff",
    "deploy_pull",
    "deploy_push",
    "deploy_to_org",
    "diff_objects",
    "elis_openapi_grep",
    "elis_openapi_jq",
    "evaluate_lookup_field",
    "execute_internal_tool",
    "execute_tool",
    "get_commit_store",
    "get_deploy_tool_names",
    "get_deploy_tools",
    "get_dynamic_tools",
    "get_internal_tool_names",
    "get_internal_tools",
    "get_load_tool_category_definition",
    "get_load_tool_definition",
    "get_loaded_categories",
    "get_lookup_dataset_raw_values",
    "get_mcp_connection",
    "get_mcp_event_loop",
    "get_mcp_mode",
    "get_output_dir",
    "get_rossum_credentials",
    "get_rossum_environment",
    "get_snapshot_store",
    "get_task_tracker",
    "get_tools_version",
    "get_write_tools",
    "get_write_tools_async",
    "is_read_only_mode",
    "is_skill_loaded",
    "kb_get_article",
    "kb_grep",
    "list_tasks",
    "load_skill",
    "load_tool",
    "load_tool_category",
    "patch_schema_with_subagent",
    "preload_categories_for_request",
    "query_lookup_dataset",
    "refresh_openapi_spec",
    "report_progress",
    "report_text",
    "report_token_usage",
    "require_rossum_credentials",
    "reset_dynamic_tools",
    "restore_entity_version",
    "revert_commit",
    "search_elis_docs",
    "search_knowledge_base",
    "set_commit_store",
    "set_mcp_connection",
    "set_output_dir",
    "set_progress_callback",
    "set_rossum_credentials",
    "set_rossum_environment",
    "set_snapshot_store",
    "set_task_snapshot_callback",
    "set_task_tracker",
    "set_text_callback",
    "set_token_callback",
    "show_change_history",
    "show_commit_details",
    "show_entity_history",
    "spawn_mcp_connection",
    "suggest_categories_for_request",
    "suggest_formula_field",
    "suggest_lookup_field",
    "update_task",
    "write_file",
]
