"""Knowledge base search sub-agent.

Provides a sub-agent that searches pre-scraped Rossum Knowledge Base articles
using kb_grep, kb_get_article, and kb_python_exec tools.
"""

from __future__ import annotations

import ast
import io
import json
import logging
import os
import re
from contextlib import redirect_stdout
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

from anthropic import beta_tool

from rossum_agent.tools.subagents.base import SubAgent, SubAgentConfig

if TYPE_CHECKING:
    from typing import Any


class _RankedArticle(TypedDict):
    slug: str
    title: str
    url: str
    score: int
    match_reasons: list[str]
    excerpt: str
    article: dict[str, str]


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# KB data paths & output limits
# ---------------------------------------------------------------------------
_KB_DATA_PATH_ENV = "ROSSUM_KB_DATA_PATH"
_BUNDLED_KB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "rossum-kb.json"

_GREP_MATCH_LIMIT = 200
_GREP_OUTPUT_LIMIT = 50000
_ARTICLE_OUTPUT_LIMIT = 50000
_SNIPPET_CONTEXT = 300  # chars before/after match to include in snippet

# Sub-agent context window budget
_TOOL_RESULT_LIMIT = 15000
_TOOL_RESULT_INNER_LIMIT = 12000
_DIRECT_CONTENT_LIMIT = 12000
_DIRECT_CANDIDATE_LIMIT = 5
_DIRECT_SCORE_MIN = 120
_DIRECT_SCORE_GAP_MIN = 35

# Python exec limits
_MAX_CODE_LENGTH = 8000
_MAX_EXEC_OUTPUT = 30000

_QUERY_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "configure",
        "for",
        "how",
        "i",
        "in",
        "is",
        "of",
        "on",
        "or",
        "please",
        "rossum",
        "set",
        "setup",
        "the",
        "to",
        "up",
        "use",
        "with",
    }
)

_ALLOWED_MODULES = frozenset({"collections", "itertools", "json", "math", "re", "statistics", "textwrap"})

_SAFE_BUILTINS: dict[str, object] = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "int": int,
    "isinstance": isinstance,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "print": print,
    "range": range,
    "reversed": reversed,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "type": type,
    "zip": zip,
    "next": next,
    "iter": iter,
    "getattr": getattr,
    "hasattr": hasattr,
}

_DISALLOWED_AST_NODES = (
    ast.AsyncFor,
    ast.AsyncFunctionDef,
    ast.AsyncWith,
    ast.Await,
    ast.ClassDef,
    ast.Delete,
    ast.Global,
    ast.Nonlocal,
    ast.Raise,
    ast.Try,
    ast.TryStar,
    ast.With,
    ast.Yield,
    ast.YieldFrom,
)


# ---------------------------------------------------------------------------
# KB cache
# ---------------------------------------------------------------------------
class KBCache:
    """In-memory cache for pre-scraped Knowledge Base articles."""

    def __init__(self, cache_path: Path = _BUNDLED_KB_PATH) -> None:
        self._cache_path = cache_path
        self._data: dict[str, Any] | None = None
        self._mtime: float = 0

    def load(self) -> dict[str, Any]:
        """Load KB data with in-memory caching keyed on file mtime."""
        path = self._resolve_path()
        current_mtime = path.stat().st_mtime

        if self._data is not None and current_mtime == self._mtime:
            return self._data

        data = json.loads(path.read_text())
        self._data = data
        self._mtime = current_mtime
        return data

    def _resolve_path(self) -> Path:
        """Return the KB data file path (env override or bundled)."""
        local_path = os.environ.get(_KB_DATA_PATH_ENV)
        if local_path:
            p = Path(local_path)
            if p.exists():
                return p
            raise FileNotFoundError(f"{_KB_DATA_PATH_ENV} points to non-existent file: {local_path}")
        return self._cache_path


# Module-level singleton
_cache = KBCache()

# Spillover buffer for large grep results (per sub-agent instance, set via _spillover)
_spillover: list[dict[str, str]] = []


# ---------------------------------------------------------------------------
# Low-level KB tools (used by the sub-agent)
# ---------------------------------------------------------------------------
def _make_snippet(text: str, match: re.Match[str]) -> str:
    """Build a snippet around a regex match with surrounding context."""
    start = max(0, match.start() - _SNIPPET_CONTEXT)
    end = min(len(text), match.end() + _SNIPPET_CONTEXT)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    snippet = prefix + text[start:end] + suffix
    return " ".join(snippet.split())


def _normalize_text(text: str) -> str:
    """Lowercase and collapse non-word characters for ranking."""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _query_terms(*parts: str) -> list[str]:
    """Extract meaningful deduplicated terms from the query and context."""
    terms: list[str] = []
    seen: set[str] = set()
    for part in parts:
        for term in _normalize_text(part).split():
            if len(term) < 3 or term in _QUERY_STOPWORDS or term in seen:
                continue
            seen.add(term)
            terms.append(term)
    return terms


def _extract_title_from_content(content: str) -> str:
    """Recover article titles from scraped markdown when metadata is noisy."""
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    for line in lines[:20]:
        if line.startswith("Title: "):
            return line.removeprefix("Title: ").strip()
    for line in lines[:40]:
        if line.startswith("# "):
            return line[2:].strip()
    for i in range(min(len(lines) - 1, 40)):
        if re.fullmatch(r"[=-]{3,}", lines[i + 1]) and 3 <= len(lines[i]) <= 160:
            return lines[i].strip()
    return ""


def _article_display_title(article: dict[str, str]) -> str:
    """Prefer a title recovered from content over broken scraper metadata."""
    content_title = _extract_title_from_content(article.get("content", ""))
    if content_title:
        return content_title

    title = article.get("title", "").strip()
    if title:
        return title

    return article.get("slug", "").replace("-", " ").strip().title()


def _truncate_text(text: str, limit: int) -> tuple[str, bool]:
    """Bound large article content before returning it to the main agent."""
    if len(text) <= limit:
        return text, False
    return text[:limit] + "\n... (truncated)", True


def _article_excerpt(article: dict[str, str], query: str, terms: list[str]) -> str:
    """Build a short excerpt around the best phrase/term match."""
    content = article.get("content", "")
    if not content:
        return ""

    patterns = [query.strip(), *terms]
    for pattern in patterns:
        if not pattern:
            continue
        match = re.search(re.escape(pattern), content, re.IGNORECASE)
        if match:
            return _make_snippet(content, match)

    content_start = content.split("Markdown Content:", 1)[-1]
    excerpt = " ".join(content_start.split())
    if len(excerpt) > 600:
        return excerpt[:600] + "..."
    return excerpt


def _score_terms(
    terms: list[str], normalized_slug: str, normalized_title: str, content_lower: str
) -> tuple[int, list[str]]:
    """Score individual term hits and all-terms bonuses across slug/title/content."""
    score = 0
    reasons: list[str] = []

    for hits, weight, reason in [
        (sum(t in normalized_slug for t in terms), 18, "slug_terms"),
        (sum(t in normalized_title for t in terms), 14, "title_terms"),
        (sum(t in content_lower for t in terms), 3, "content_terms"),
    ]:
        if hits:
            score += hits * weight
            reasons.append(reason)

    if terms:
        for text, bonus, reason in [
            (normalized_slug, 40, "all_terms_in_slug"),
            (normalized_title, 30, "all_terms_in_title"),
            (content_lower, 10, "all_terms_in_content"),
        ]:
            if all(t in text for t in terms):
                score += bonus
                reasons.append(reason)

    return score, reasons


def _rank_article(article: dict[str, str], query: str, user_query: str | None = None) -> _RankedArticle:
    """Score an article using slug/title matches before falling back to content."""
    title = _article_display_title(article)
    slug = article.get("slug", "")
    url = article.get("url", "")
    content = article.get("content", "")
    content_lower = content.lower()

    normalized_query = _normalize_text(query)
    normalized_slug = _normalize_text(slug.replace("-", " "))
    normalized_title = _normalize_text(title)
    terms = _query_terms(query, user_query or "")

    score = 0
    reasons: list[str] = []

    if normalized_query:
        if normalized_slug == normalized_query:
            score += 120
            reasons.append("slug_exact")
        elif normalized_query in normalized_slug:
            score += 70
            reasons.append("slug_contains")

        if normalized_title == normalized_query:
            score += 90
            reasons.append("title_exact")
        elif normalized_query in normalized_title:
            score += 60
            reasons.append("title_contains")

        phrase_pos = content_lower.find(query.lower())
        if phrase_pos >= 0:
            score += 40 if phrase_pos < 800 else 10
            reasons.append("content_phrase")

    term_score, term_reasons = _score_terms(terms, normalized_slug, normalized_title, content_lower)
    score += term_score
    reasons.extend(term_reasons)

    return {
        "slug": slug,
        "title": title,
        "url": url,
        "score": score,
        "match_reasons": reasons,
        "excerpt": _article_excerpt(article, query, terms),
        "article": article,
    }


def _find_ranked_articles(query: str, user_query: str | None = None) -> list[_RankedArticle]:
    """Rank the full KB locally before involving the sub-agent."""
    data = _cache.load()
    articles = data.get("articles", [])
    ranked = [_rank_article(article, query, user_query) for article in articles]
    ranked = [candidate for candidate in ranked if candidate["score"] > 0]
    ranked.sort(key=lambda candidate: (int(candidate["score"]), len(str(candidate["slug"]))), reverse=True)
    return ranked


def _is_high_confidence_match(candidates: list[_RankedArticle]) -> bool:
    """Return True when the best candidate is clearly better than the rest."""
    if not candidates:
        return False

    best = candidates[0]
    reasons = set(best["match_reasons"])
    if "slug_exact" in reasons or "title_exact" in reasons:
        return True

    best_score = int(best["score"])
    second_score = int(candidates[1]["score"]) if len(candidates) > 1 else 0
    return best_score >= _DIRECT_SCORE_MIN and best_score - second_score >= _DIRECT_SCORE_GAP_MIN


def _serialize_ranked_candidate(candidate: _RankedArticle) -> dict[str, str | int | list[str]]:
    """Strip internal fields before returning ranking metadata."""
    return {
        "slug": candidate["slug"],
        "title": candidate["title"],
        "url": candidate["url"],
        "score": candidate["score"],
        "match_reasons": candidate["match_reasons"],
        "excerpt": candidate["excerpt"],
    }


def _build_direct_result(query: str, user_query: str | None, candidates: list[_RankedArticle]) -> str:
    """Return structured KB JSON so the main agent can use the article directly."""
    best = candidates[0]
    article = best["article"]

    content, content_truncated = _truncate_text(article.get("content", ""), _DIRECT_CONTENT_LIMIT)
    top_candidates = [_serialize_ranked_candidate(candidate) for candidate in candidates[:_DIRECT_CANDIDATE_LIMIT]]

    response = {
        "status": "success",
        "strategy": "direct_lookup",
        "query": query,
        "user_query": user_query,
        "answer": (
            f"Found best matching article '{best['title']}' "
            f"({best['url']}). Use selected_article.content for the full article."
        ),
        "iterations": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "candidates": top_candidates,
        "selected_article": {
            **top_candidates[0],
            "content": content,
            "content_truncated": content_truncated,
        },
    }
    return json.dumps(response)


def _grep_match_articles(
    articles: list[dict[str, str]], compiled: re.Pattern[str], pattern: str
) -> list[tuple[int, dict[str, str]]]:
    """Score and collect articles matching the compiled regex."""
    matches: list[tuple[int, dict[str, str]]] = []
    for article in articles:
        title = _article_display_title(article)
        content = article.get("content", "")
        slug = article.get("slug", "")
        url = article.get("url", "")

        title_match = compiled.search(title)
        content_match = compiled.search(content)

        if title_match or content_match:
            parts = []
            if title_match:
                parts.append(f"[title] {title}")
            if content_match:
                parts.append(f"[content] {_make_snippet(content, content_match)}")
            rank_score = _rank_article(article, pattern)["score"]
            if title_match:
                rank_score += 50
            matches.append((rank_score, {"slug": slug, "title": title, "url": url, "snippet": "\n".join(parts)}))
    return matches


@beta_tool
def kb_grep(pattern: str, case_insensitive: bool = True) -> str:
    """Search Knowledge Base article titles and content by keyword or regex.

    Use to discover relevant articles when you don't know the exact slug.
    Returns matching articles with short snippets around each match.
    When results are truncated, the full list is saved to spillover — use
    kb_python_exec to filter with: `[m for m in spillover if 'keyword' in m['snippet']]`

    Examples: "document splitting", "webhook", "email_template", "formula"

    Args:
        pattern: Text pattern to search for (supports regex).
        case_insensitive: Whether to ignore case (default: True).

    Returns:
        Matching articles with snippets showing context around matches.
    """
    global _spillover
    logger.debug(f"kb_grep called with pattern: {pattern!r}")

    if not pattern or not pattern.strip():
        return json.dumps({"status": "error", "message": "Empty pattern not allowed"})

    try:
        data = _cache.load()
    except (ValueError, OSError) as e:
        logger.exception("Error loading KB data")
        return json.dumps({"status": "error", "message": f"Error loading KB data: {e}"})

    try:
        compiled = re.compile(pattern, re.IGNORECASE if case_insensitive else 0)
    except re.error as e:
        return json.dumps({"status": "error", "message": f"Invalid regex pattern: {e}"})

    articles = data.get("articles", [])
    matches = _grep_match_articles(articles, compiled, pattern)

    if not matches:
        _spillover = []
        return json.dumps({"status": "success", "result": "No matches found"})

    matches.sort(key=lambda item: item[0], reverse=True)
    ordered_matches = [match for _, match in matches]
    total_matches = len(matches)

    # Store full results in spillover before any truncation
    _spillover = ordered_matches

    if total_matches > _GREP_MATCH_LIMIT:
        ordered_matches = ordered_matches[:_GREP_MATCH_LIMIT]

    result = json.dumps({"status": "success", "matches": total_matches, "result": ordered_matches})

    if len(result) > _GREP_OUTPUT_LIMIT:
        while ordered_matches and len(result) > _GREP_OUTPUT_LIMIT:
            ordered_matches.pop()
            result = json.dumps(
                {
                    "status": "success",
                    "matches": total_matches,
                    "showing": len(ordered_matches),
                    "spillover": total_matches,
                    "result": ordered_matches,
                }
            )

    return result


@beta_tool
def kb_get_article(slug: str) -> str:
    """Retrieve a full Knowledge Base article by its slug.

    Use after kb_grep to read the complete content of a specific article.

    Args:
        slug: Article slug (e.g. "document-splitting-extension"). Partial match supported.

    Returns:
        Full article content in markdown, or error if not found.
    """
    logger.debug(f"kb_get_article called with slug: {slug!r}")
    try:
        data = _cache.load()
    except (ValueError, OSError) as e:
        logger.exception("Error loading KB data")
        return json.dumps({"status": "error", "message": f"Error loading KB data: {e}"})

    articles = data.get("articles", [])

    def _serialize_article(article: dict[str, str]) -> str:
        content = article.get("content", "")
        if len(content) > _ARTICLE_OUTPUT_LIMIT:
            content = content[:_ARTICLE_OUTPUT_LIMIT] + "\n... (truncated)"
        return json.dumps(
            {
                "status": "success",
                "slug": article["slug"],
                "title": _article_display_title(article),
                "url": article.get("url", ""),
                "content": content,
            }
        )

    # Exact match first
    for article in articles:
        if article.get("slug", "") == slug:
            return _serialize_article(article)

    # Partial match fallback
    slug_lower = slug.lower()
    partial_matches = [a for a in articles if slug_lower in a.get("slug", "").lower()]

    if len(partial_matches) == 1:
        return _serialize_article(partial_matches[0])
    if len(partial_matches) > 1:
        candidates = [a.get("slug", "") for a in partial_matches[:10]]
        return json.dumps({"status": "error", "message": f"Ambiguous slug '{slug}', candidates: {candidates}"})

    return json.dumps({"status": "error", "message": f"No article found matching slug: {slug}"})


# ---------------------------------------------------------------------------
# Python exec for KB (lightweight, sandboxed)
# ---------------------------------------------------------------------------
def _validate_kb_ast(tree: ast.AST) -> None:
    """Validate AST for KB python exec — stricter than main execute_python."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.Import):
                if not all(alias.name in _ALLOWED_MODULES for alias in node.names):
                    raise ValueError(f"Import not allowed: {ast.dump(node)}")
            elif node.level != 0 or node.module not in _ALLOWED_MODULES:
                raise ValueError(f"Import not allowed: {node.module}")
            continue
        if isinstance(node, _DISALLOWED_AST_NODES):
            raise ValueError(f"{type(node).__name__} is not allowed")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise ValueError("Names starting with '__' are not allowed")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError("Attributes starting with '__' are not allowed")


def kb_python_exec(code: str) -> str:
    """Execute Python code with access to KB articles and grep spillover.

    Pre-loaded variables:
    - `articles`: list of all KB articles (each has slug, title, url, content)
    - `spillover`: list of last kb_grep matches (each has slug, title, url, snippet)
    - `re`, `json`, `collections`, `itertools` modules

    Assign result to `result` or leave as last expression.
    """
    if len(code) > _MAX_CODE_LENGTH:
        return json.dumps({"status": "error", "error": f"Code exceeds {_MAX_CODE_LENGTH} characters"})

    try:
        tree = ast.parse(code, mode="exec")
        _validate_kb_ast(tree)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)})

    # Build execution environment with KB data pre-loaded
    try:
        kb_data = _cache.load()
        kb_articles = kb_data.get("articles", [])
    except (ValueError, OSError):
        kb_articles = []

    allowed_modules: dict[str, object] = {name: __import__(name) for name in _ALLOWED_MODULES}

    def _safe_import(name: str, *_args: object, **_kwargs: object) -> object:
        if name in allowed_modules:
            return allowed_modules[name]
        raise ImportError(f"Import not allowed: {name}")

    builtins = {**_SAFE_BUILTINS, "__import__": _safe_import}
    globals_dict: dict[str, object] = {"__builtins__": builtins}
    locals_dict: dict[str, object] = {
        "articles": kb_articles,
        "spillover": list(_spillover),
        **allowed_modules,
    }

    stdout = io.StringIO()
    result_value: object = None

    try:
        with redirect_stdout(stdout):
            if tree.body and isinstance(tree.body[-1], ast.Expr):
                prefix = ast.fix_missing_locations(ast.Module(body=tree.body[:-1], type_ignores=[]))
                suffix = ast.fix_missing_locations(ast.Expression(tree.body[-1].value))
                exec(compile(prefix, "<kb_python_exec>", "exec"), globals_dict, locals_dict)
                result_value = eval(compile(suffix, "<kb_python_exec>", "eval"), globals_dict, locals_dict)
            else:
                exec(compile(tree, "<kb_python_exec>", "exec"), globals_dict, locals_dict)
                result_value = locals_dict.get("result")
    except Exception as e:
        return json.dumps(
            {"status": "error", "error": f"{type(e).__name__}: {e}", "stdout": stdout.getvalue() or None}
        )

    output = json.dumps(
        {"status": "success", "result": result_value, "stdout": stdout.getvalue() or None},
        default=str,
    )
    if len(output) > _MAX_EXEC_OUTPUT:
        output = output[:_MAX_EXEC_OUTPUT] + "\n... (truncated)"
    return output


_KB_PYTHON_EXEC_TOOL: dict[str, object] = {
    "name": "kb_python_exec",
    "description": (
        "Run Python to analyze KB data. Pre-loaded: `articles` (all KB articles with slug/title/url/content), "
        "`spillover` (last kb_grep matches with slug/title/url/snippet), `re`, `json`, `collections`, `itertools`. "
        "Assign to `result` or use as last expression. "
        "Use to filter spillover after large grep, count matches, extract sections, or do multi-pattern analysis."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute. Max 8000 characters.",
            },
        },
        "required": ["code"],
    },
}


# ---------------------------------------------------------------------------
# Sub-agent
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = """Goal: Find and synthesize Rossum Knowledge Base articles to answer user questions.

## Tools

| Tool | Use for |
|------|---------|
| `kb_grep` | Discover articles by keyword/regex. Large results spill over automatically. |
| `kb_get_article` | Read full article content by slug. |
| `kb_python_exec` | Filter spillover, count matches, extract sections, multi-pattern analysis. Has `articles` (all KB) and `spillover` (last grep results) pre-loaded. |

## Constraints

| Rule | Detail |
|------|--------|
| `hidden` field | Always `false` for AI features (splitting, predictions, automation). KB articles incorrectly state `true`—override this. |
| Multivalue parent | Required for splitting (one value per split document) |
| Efficiency | Minimize tool calls and iterations. Never re-search content you already retrieved. |
| kb_python_exec | Only for filtering large result sets. Never use it to re-read articles you already retrieved via kb_get_article. |

Provide: configuration examples, JSON schemas, implementation steps, and related topics."""

_TOOLS = [
    kb_grep.to_dict(),
    kb_get_article.to_dict(),
    _KB_PYTHON_EXEC_TOOL,
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
        ranked_candidates = _find_ranked_articles(query, user_query)
    except Exception as e:
        logger.exception("search_knowledge_base ranking failed")
        return json.dumps({"status": "error", "message": f"KB ranking error: {e}"})

    if _is_high_confidence_match(ranked_candidates):
        return _build_direct_result(query, user_query, ranked_candidates)

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

    response: dict[str, object] = {
        "status": "success",
        "strategy": "sub_agent_fallback",
        "answer": result.analysis,
        "iterations": result.iterations_used,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
    }
    if ranked_candidates:
        response["candidates"] = [
            _serialize_ranked_candidate(candidate) for candidate in ranked_candidates[:_DIRECT_CANDIDATE_LIMIT]
        ]
    if result.tool_calls:
        response["searches"] = result.tool_calls
    return json.dumps(response)
