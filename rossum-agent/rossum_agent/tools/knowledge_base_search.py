"""Knowledge Base article search tools (regex grep + article lookup)."""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

from anthropic import beta_tool

if TYPE_CHECKING:
    from typing import Any

logger = logging.getLogger(__name__)

_KB_DATA_PATH_ENV = "ROSSUM_KB_DATA_PATH"
_BUNDLED_KB_PATH = Path(__file__).resolve().parent.parent / "data" / "rossum-kb.json"

# Output limits
_GREP_MATCH_LIMIT = 200
_GREP_OUTPUT_LIMIT = 50000
_ARTICLE_OUTPUT_LIMIT = 50000
_SNIPPET_CONTEXT = 150  # chars before/after match to include in snippet


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


def _make_snippet(text: str, match: re.Match[str]) -> str:
    """Build a snippet around a regex match with surrounding context."""
    start = max(0, match.start() - _SNIPPET_CONTEXT)
    end = min(len(text), match.end() + _SNIPPET_CONTEXT)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    snippet = prefix + text[start:end] + suffix
    return " ".join(snippet.split())


@beta_tool
def kb_grep(pattern: str, case_insensitive: bool = True) -> str:
    """Search Knowledge Base article titles and content by keyword or regex.

    Use to discover relevant articles when you don't know the exact slug.
    Returns matching articles with short snippets around each match.

    Examples: "document splitting", "webhook", "email_template", "formula"

    Args:
        pattern: Text pattern to search for (supports regex).
        case_insensitive: Whether to ignore case (default: True).

    Returns:
        Matching articles with snippets showing context around matches.
    """
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
    matches: list[dict[str, str]] = []

    for article in articles:
        title = article.get("title", "")
        content = article.get("content", "")
        slug = article.get("slug", "")
        url = article.get("url", "")

        # Search title first, then content
        title_match = compiled.search(title)
        content_match = compiled.search(content)

        if title_match or content_match:
            parts = []
            if title_match:
                parts.append(f"[title] {title}")
            if content_match:
                parts.append(f"[content] {_make_snippet(content, content_match)}")
            matches.append({"slug": slug, "title": title, "url": url, "snippet": "\n".join(parts)})

    if not matches:
        return json.dumps({"status": "success", "result": "No matches found"})

    total_matches = len(matches)
    if total_matches > _GREP_MATCH_LIMIT:
        matches = matches[:_GREP_MATCH_LIMIT]

    result = json.dumps({"status": "success", "matches": total_matches, "result": matches})

    if len(result) > _GREP_OUTPUT_LIMIT:
        # Trim matches until under limit
        while matches and len(result) > _GREP_OUTPUT_LIMIT:
            matches.pop()
            result = json.dumps(
                {"status": "success", "matches": total_matches, "showing": len(matches), "result": matches}
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
                "title": article.get("title", ""),
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
