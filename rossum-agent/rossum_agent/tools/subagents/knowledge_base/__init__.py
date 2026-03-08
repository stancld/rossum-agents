"""Knowledge base search sub-agent.

Provides a sub-agent that searches pre-scraped Rossum Knowledge Base articles
using kb_grep, kb_get_article, and kb_python_exec tools.
"""

from __future__ import annotations

from rossum_agent.tools.subagents.knowledge_base.agent import (
    _SYSTEM_PROMPT,
    _TOOL_RESULT_INNER_LIMIT,
    _TOOL_RESULT_LIMIT,
    _TOOLS,
    KnowledgeBaseSubAgent,
    search_knowledge_base,
)
from rossum_agent.tools.subagents.knowledge_base.cache import KBCache
from rossum_agent.tools.subagents.knowledge_base.ranking import (
    make_snippet as _make_snippet,
)
from rossum_agent.tools.subagents.knowledge_base.tools import (
    _ARTICLE_OUTPUT_LIMIT,
    _GREP_MATCH_LIMIT,
    _MAX_CODE_LENGTH,
    kb_get_article,
    kb_grep,
    kb_python_exec,
)
from rossum_agent.tools.subagents.knowledge_base.tools import (
    KB_PYTHON_EXEC_TOOL as _KB_PYTHON_EXEC_TOOL,
)

__all__ = [
    "_ARTICLE_OUTPUT_LIMIT",
    "_GREP_MATCH_LIMIT",
    "_KB_PYTHON_EXEC_TOOL",
    "_MAX_CODE_LENGTH",
    "_SYSTEM_PROMPT",
    "_TOOLS",
    "_TOOL_RESULT_INNER_LIMIT",
    "_TOOL_RESULT_LIMIT",
    "KBCache",
    "KnowledgeBaseSubAgent",
    "_make_snippet",
    "kb_get_article",
    "kb_grep",
    "kb_python_exec",
    "search_knowledge_base",
]
