"""Elis API documentation search sub-agent."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from anthropic import beta_tool

if TYPE_CHECKING:
    from typing import Any

logger = logging.getLogger(__name__)

from rossum_agent.tools.elis_backend_openapi_search import elis_openapi_grep, elis_openapi_jq
from rossum_agent.tools.subagents.base import SubAgent, SubAgentConfig

# Sub-agent context window budget: keep tool results small enough for productive iteration
_TOOL_RESULT_LIMIT = 15000
_TOOL_RESULT_INNER_LIMIT = 12000

_SYSTEM_PROMPT = """You search the Rossum API OpenAPI spec to answer user questions about the API.

Use elis_openapi_grep to discover endpoints/schemas by keyword, then elis_openapi_jq for details.

Provide: endpoint paths, HTTP methods, request/response schemas, required fields, code examples."""

_TOOLS = [elis_openapi_jq.to_dict(), elis_openapi_grep.to_dict()]


class ElisDocsSubAgent(SubAgent):
    """Sub-agent for searching Elis API documentation."""

    def __init__(self) -> None:
        super().__init__(
            SubAgentConfig(
                tool_name="search_elis_docs",
                system_prompt=_SYSTEM_PROMPT,
                tools=_TOOLS,  # type: ignore[arg-type] - BetaToolParam is structurally dict[str, Any]
                max_iterations=5,
            )
        )

    def execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        if tool_name == "elis_openapi_jq":
            result = elis_openapi_jq(tool_input["jq_query"])
        elif tool_name == "elis_openapi_grep":
            result = elis_openapi_grep(tool_input["pattern"], tool_input.get("case_insensitive", True))
        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

        # Truncate inside the JSON envelope to avoid feeding broken JSON to the LLM
        if len(result) > _TOOL_RESULT_LIMIT:
            try:
                parsed = json.loads(result)
                if (
                    "result" in parsed
                    and isinstance(parsed["result"], str)
                    and len(parsed["result"]) > _TOOL_RESULT_INNER_LIMIT
                ):
                    parsed["result"] = (
                        parsed["result"][:_TOOL_RESULT_INNER_LIMIT] + "\n... (truncated, refine your query)"
                    )
                    return json.dumps(parsed)
            except (json.JSONDecodeError, TypeError):
                pass
            return result[:_TOOL_RESULT_LIMIT] + "\n... (truncated, refine your query)"
        return result

    def process_response_block(self, block: Any, iteration: int, max_iterations: int) -> dict[str, Any] | None:
        return None


@beta_tool
def search_elis_docs(query: str) -> str:
    """Sub-agent that thoroughly explores the OpenAPI spec for comprehensive API answers.

    Iterates through the spec to find related endpoints, schemas, and connections.
    Good for complex questions requiring multiple lookups or discovering related APIs.

    Args:
        query: API question. Examples: 'webhook payload schema', 'annotation export flow',
        'document splitting endpoint', 'all fields in annotation response'.

    Returns:
        JSON with analysis of relevant API documentation.
    """
    if not query.strip():
        return json.dumps({"status": "error", "message": "Query is required"})

    try:
        agent = ElisDocsSubAgent()
        result = agent.run(query)
    except Exception as e:
        logger.exception("search_elis_docs failed")
        return json.dumps({"status": "error", "message": f"Sub-agent error: {e}"})

    response = {
        "status": "success",
        "answer": result.analysis,
        "iterations": result.iterations_used,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
    }
    if result.tool_calls:
        response["searches"] = result.tool_calls
    return json.dumps(response)
