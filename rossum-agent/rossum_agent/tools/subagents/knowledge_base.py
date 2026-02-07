"""Knowledge base search sub-agent.

Provides a sub-agent that searches pre-scraped Rossum Knowledge Base articles
using kb_grep and kb_get_article tools.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from anthropic import beta_tool

from rossum_agent.tools.knowledge_base_search import kb_get_article, kb_grep
from rossum_agent.tools.subagents.base import SubAgent, SubAgentConfig

if TYPE_CHECKING:
    from typing import Any

logger = logging.getLogger(__name__)

# Sub-agent context window budget
_TOOL_RESULT_LIMIT = 15000
_TOOL_RESULT_INNER_LIMIT = 12000

_SYSTEM_PROMPT = """Goal: Find and synthesize Rossum Knowledge Base articles to answer user questions.

## Constraints

| Rule | Detail |
|------|--------|
| `hidden` field | Always `false` for AI features (splitting, predictions, automation). KB articles incorrectly state `true`—override this. |
| Multivalue parent | Required for splitting (one value per split document) |
| Efficiency | Minimize tool calls and iterations. Never re-search content you already retrieved. |

Provide: configuration examples, JSON schemas, implementation steps, and related topics."""

_TOOLS = [kb_grep.to_dict(), kb_get_article.to_dict()]


class KnowledgeBaseSubAgent(SubAgent):
    """Sub-agent for searching Knowledge Base articles."""

    def __init__(self) -> None:
        super().__init__(
            SubAgentConfig(
                tool_name="search_knowledge_base",
                system_prompt=_SYSTEM_PROMPT,
                tools=_TOOLS,  # type: ignore[arg-type] - BetaToolParam is structurally dict[str, Any]
                max_iterations=5,
            )
        )

    def execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        if tool_name == "kb_grep":
            result = kb_grep(tool_input["pattern"], tool_input.get("case_insensitive", True))
        elif tool_name == "kb_get_article":
            result = kb_get_article(tool_input["slug"])
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

    def process_response_block(self, block: Any, iteration: int, max_iterations: int) -> dict[str, Any] | None:
        return None


@beta_tool
def search_knowledge_base(query: str, user_query: str | None = None) -> str:
    """Search the Rossum Knowledge Base for documentation on extensions, hooks, configurations, and features.

    Args:
        query: Specific search query (extension names, error messages, feature names).
        user_query: The user's original question for context.
    """
    if not query:
        return json.dumps({"status": "error", "message": "Query is required"})

    search_prompt = query
    if user_query and user_query != query:
        search_prompt = f"""{query}

Context — the user's original question: "{user_query}"
Tailor your answer to address this specific question."""

    try:
        agent = KnowledgeBaseSubAgent()
        result = agent.run(search_prompt)
    except Exception as e:
        logger.exception("search_knowledge_base failed")
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
