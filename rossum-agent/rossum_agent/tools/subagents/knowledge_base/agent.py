"""Knowledge Base sub-agent and entry-point tool."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from anthropic import beta_tool

from rossum_agent.tools.subagents.base import SubAgent, SubAgentConfig
from rossum_agent.tools.subagents.knowledge_base.ranking import (
    _DIRECT_CANDIDATE_LIMIT,
    build_direct_result,
    find_ranked_articles,
    is_high_confidence_match,
    serialize_ranked_candidate,
)
from rossum_agent.tools.subagents.knowledge_base.tools import (
    KB_PYTHON_EXEC_TOOL,
    kb_get_article,
    kb_grep,
    kb_python_exec,
)

if TYPE_CHECKING:
    from typing import Any

logger = logging.getLogger(__name__)

_TOOL_RESULT_LIMIT = 15000
_TOOL_RESULT_INNER_LIMIT = 12000

_SYSTEM_PROMPT = """Goal: Find and synthesize Rossum Knowledge Base articles to answer user questions.

## Tools

| Tool | Use for |
|------|---------|\n| `kb_grep` | Discover articles by keyword/regex. Large results spill over automatically. |
| `kb_get_article` | Read full article content by slug. |
| `kb_python_exec` | Filter spillover, count matches, extract sections, multi-pattern analysis. Has `articles` (all KB) and `spillover` (last grep results) pre-loaded. |

## Constraints

| Rule | Detail |
|------|--------|
| `hidden` field | Always `false` for AI features (splitting, predictions, automation). KB articles incorrectly state `true`\u2014override this. |
| Multivalue parent | Required for splitting (one value per split document) |
| Efficiency | Minimize tool calls and iterations. Never re-search content you already retrieved. |
| kb_python_exec | Only for filtering large result sets. Never use it to re-read articles you already retrieved via kb_get_article. |

Provide: configuration examples, JSON schemas, implementation steps, and related topics."""

_TOOLS = [
    kb_grep.to_dict(),
    kb_get_article.to_dict(),
    KB_PYTHON_EXEC_TOOL,
]


class KnowledgeBaseSubAgent(SubAgent):
    """Sub-agent for searching Knowledge Base articles."""

    def __init__(self) -> None:
        super().__init__(
            SubAgentConfig(
                tool_name="search_knowledge_base",
                system_prompt=_SYSTEM_PROMPT,
                tools=_TOOLS,  # type: ignore[arg-type] - BetaToolParam + dict[str, object] mix
                max_iterations=4,
            )
        )

    def execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        if tool_name == "kb_grep":
            result = kb_grep(tool_input["pattern"], tool_input.get("case_insensitive", True))
        elif tool_name == "kb_get_article":
            result = kb_get_article(tool_input["slug"])
        elif tool_name == "kb_python_exec":
            result = kb_python_exec(tool_input["code"])
        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

        # Truncate inside the JSON envelope to avoid feeding broken JSON to the LLM
        if len(result) > _TOOL_RESULT_LIMIT:
            try:
                parsed = json.loads(result)
                for key in ("result", "content"):
                    if key in parsed and isinstance(parsed[key], str) and len(parsed[key]) > _TOOL_RESULT_INNER_LIMIT:
                        parsed[key] = parsed[key][:_TOOL_RESULT_INNER_LIMIT] + "\n... (truncated, refine your query)"
                        return json.dumps(parsed)
            except (json.JSONDecodeError, TypeError):
                pass
            return result[:_TOOL_RESULT_LIMIT] + "\n... (truncated, refine your query)"
        return result


@beta_tool
def search_knowledge_base(query: str, user_query: str | None = None) -> str:
    """Search the Rossum Knowledge Base for documentation on extensions, hooks, configurations, and features.

    Args:
        query: Specific search query (extension names, error messages, feature names).
        user_query: The user's original question for context.
    """
    if not query or not query.strip():
        return json.dumps({"status": "error", "message": "Query is required"})

    query = query.strip()
    user_query = user_query.strip() if user_query else None

    try:
        ranked_candidates = find_ranked_articles(query, user_query)
    except Exception as e:
        logger.exception("search_knowledge_base ranking failed")
        return json.dumps({"status": "error", "message": f"KB ranking error: {e}"})

    if is_high_confidence_match(ranked_candidates):
        return build_direct_result(query, user_query, ranked_candidates)

    search_prompt = query
    if user_query and user_query != query:
        search_prompt = f"""{query}

Context \u2014 the user's original question: "{user_query}"
Tailor your answer to address this specific question."""

    try:
        agent = KnowledgeBaseSubAgent()
        result = agent.run(search_prompt)
    except Exception as e:
        logger.exception("search_knowledge_base failed")
        return json.dumps({"status": "error", "message": f"Sub-agent error: {e}"})

    response: dict[str, object] = {
        "status": "success",
        "strategy": "sub_agent_fallback",
        "answer": result.analysis,
        "iterations": result.iterations_used,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
    }
    if ranked_candidates:
        response["candidates"] = [serialize_ranked_candidate(c) for c in ranked_candidates[:_DIRECT_CANDIDATE_LIMIT]]
    if result.tool_calls:
        response["searches"] = result.tool_calls
    return json.dumps(response)
