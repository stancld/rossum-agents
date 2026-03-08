"""Deterministic article ranking for Knowledge Base search."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TypedDict

from rossum_agent.tools.file_tools import write_file
from rossum_agent.tools.subagents.knowledge_base.cache import cache

_SNIPPET_CONTEXT = 300
_DIRECT_CANDIDATE_LIMIT = 5

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


class RankedArticle(TypedDict):
    slug: str
    title: str
    url: str
    score: int
    match_level: str
    match_reasons: list[str]
    excerpt: str
    rank_key: tuple[int, int, int, int, int, int, int, int, int, int, int]
    article: dict[str, str]


def make_snippet(text: str, match: re.Match[str]) -> str:
    """Build a snippet around a regex match with surrounding context."""
    start = max(0, match.start() - _SNIPPET_CONTEXT)
    end = min(len(text), match.end() + _SNIPPET_CONTEXT)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    snippet = prefix + text[start:end] + suffix
    return " ".join(snippet.split())


def normalize_text(text: str) -> str:
    """Lowercase and collapse non-word characters for ranking."""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def query_terms(*parts: str) -> list[str]:
    """Extract meaningful deduplicated terms from the query and context."""
    terms: list[str] = []
    seen: set[str] = set()
    for part in parts:
        for term in normalize_text(part).split():
            if len(term) < 3 or term in _QUERY_STOPWORDS or term in seen:
                continue
            seen.add(term)
            terms.append(term)
    return terms


def extract_title_from_content(content: str) -> str:
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


def article_display_title(article: dict[str, str]) -> str:
    """Prefer a title recovered from content over broken scraper metadata."""
    content_title = extract_title_from_content(article.get("content", ""))
    if content_title:
        return content_title
    title = article.get("title", "").strip()
    if title:
        return title
    return article.get("slug", "").replace("-", " ").strip().title()


def _article_excerpt(article: dict[str, str], query: str, terms: list[str]) -> str:
    """Build a short excerpt around the best phrase or term match."""
    content = article.get("content", "")
    if not content:
        return ""

    for pattern in [query.strip(), *terms]:
        if not pattern:
            continue
        match = re.search(re.escape(pattern), content, re.IGNORECASE)
        if match:
            return make_snippet(content, match)

    content_start = content.split("Markdown Content:", 1)[-1]
    excerpt = " ".join(content_start.split())
    if len(excerpt) > 600:
        return excerpt[:600] + "..."
    return excerpt


def _first_match_position(content: str, patterns: list[str]) -> int | None:
    """Return the earliest position of any phrase or term match in the content."""
    positions: list[int] = []
    for pattern in patterns:
        if not pattern:
            continue
        match = re.search(re.escape(pattern), content, re.IGNORECASE)
        if match:
            positions.append(match.start())
    return min(positions) if positions else None


def _match_level(
    exact_slug: bool,
    exact_title: bool,
    phrase_in_slug: bool,
    phrase_in_title: bool,
    phrase_in_content: bool,
    slug_term_hits: int,
    title_term_hits: int,
    content_term_hits: int,
) -> str:
    """Map matches to a small set of relevance buckets."""
    if exact_slug or exact_title:
        return "exact"
    if phrase_in_slug or phrase_in_title:
        return "strong"
    if slug_term_hits >= 2 or title_term_hits >= 2 or phrase_in_content:
        return "medium"
    if slug_term_hits > 0 or title_term_hits > 0 or content_term_hits > 0:
        return "weak"
    return "none"


def _match_level_score(level: str) -> int:
    """Convert relevance bucket to a stable small integer."""
    return {"exact": 4, "strong": 3, "medium": 2, "weak": 1}.get(level, 0)


def rank_article(article: dict[str, str], query: str, user_query: str | None = None) -> RankedArticle:
    """Rank an article using simple buckets and deterministic tie-breaks."""
    title = article_display_title(article)
    slug = article.get("slug", "")
    url = article.get("url", "")
    content = article.get("content", "")

    normalized_query = normalize_text(query)
    normalized_slug = normalize_text(slug.replace("-", " "))
    normalized_title = normalize_text(title)
    terms = query_terms(query, user_query or "")
    patterns = [query.strip(), *terms]

    exact_slug = bool(normalized_query and normalized_slug == normalized_query)
    exact_title = bool(normalized_query and normalized_title == normalized_query)
    phrase_in_slug = bool(normalized_query and normalized_query in normalized_slug)
    phrase_in_title = bool(normalized_query and normalized_query in normalized_title)
    phrase_in_content = bool(query.strip() and re.search(re.escape(query.strip()), content, re.IGNORECASE))
    slug_term_hits = sum(term in normalized_slug for term in terms)
    title_term_hits = sum(term in normalized_title for term in terms)
    content_term_hits = sum(bool(re.search(re.escape(term), content, re.IGNORECASE)) for term in terms)
    match_pos = _first_match_position(content, patterns)
    match_level = _match_level(
        exact_slug,
        exact_title,
        phrase_in_slug,
        phrase_in_title,
        phrase_in_content,
        slug_term_hits,
        title_term_hits,
        content_term_hits,
    )

    reasons: list[str] = []
    if exact_slug:
        reasons.append("slug_exact")
    if exact_title:
        reasons.append("title_exact")
    if phrase_in_slug and not exact_slug:
        reasons.append("slug_phrase")
    if phrase_in_title and not exact_title:
        reasons.append("title_phrase")
    if phrase_in_content:
        reasons.append("content_phrase")
    if slug_term_hits:
        reasons.append("slug_terms")
    if title_term_hits:
        reasons.append("title_terms")
    if content_term_hits:
        reasons.append("content_terms")

    return {
        "slug": slug,
        "title": title,
        "url": url,
        "score": _match_level_score(match_level),
        "match_level": match_level,
        "match_reasons": reasons,
        "excerpt": _article_excerpt(article, query, terms),
        "rank_key": (
            _match_level_score(match_level),
            int(exact_slug),
            int(exact_title),
            int(phrase_in_slug),
            int(phrase_in_title),
            slug_term_hits,
            title_term_hits,
            int(phrase_in_content),
            content_term_hits,
            -(match_pos if match_pos is not None else 1_000_000),
            -len(slug),
        ),
        "article": article,
    }


def find_ranked_articles(query: str, user_query: str | None = None) -> list[RankedArticle]:
    """Rank the full KB locally before involving the sub-agent."""
    data = cache.load()
    articles = data.get("articles", [])
    ranked = [rank_article(article, query, user_query) for article in articles]
    ranked = [candidate for candidate in ranked if candidate["match_level"] != "none"]
    ranked.sort(key=lambda candidate: candidate["rank_key"], reverse=True)
    return ranked


def is_high_confidence_match(candidates: list[RankedArticle]) -> bool:
    """Return True when the best candidate is clearly better than the rest."""
    if not candidates:
        return False

    best_level = candidates[0]["match_level"]
    if best_level == "exact":
        return True

    if len(candidates) == 1:
        return best_level in {"strong", "medium"}

    second_level = candidates[1]["match_level"]
    if best_level == "strong":
        return second_level not in {"exact", "strong"}
    if best_level == "medium":
        return second_level == "weak"
    return False


def serialize_ranked_candidate(candidate: RankedArticle) -> dict[str, str | int | list[str]]:
    """Strip internal ranking fields before returning metadata."""
    return {
        "slug": candidate["slug"],
        "title": candidate["title"],
        "url": candidate["url"],
        "score": candidate["score"],
        "match_level": candidate["match_level"],
        "match_reasons": candidate["match_reasons"],
        "excerpt": candidate["excerpt"],
    }


def build_direct_result(query: str, user_query: str | None, candidates: list[RankedArticle]) -> str:
    """Return structured KB JSON and persist the full article for follow-up jq queries."""
    best = candidates[0]
    article = best["article"]
    top_candidates = [serialize_ranked_candidate(candidate) for candidate in candidates[:_DIRECT_CANDIDATE_LIMIT]]

    article_payload = {
        **serialize_ranked_candidate(best),
        "content": article.get("content", ""),
    }
    file_result = json.loads(write_file(filename=f"knowledge-base-{best['slug']}.json", content=article_payload))

    response: dict[str, object] = {
        "status": "success",
        "strategy": "direct_lookup",
        "query": query,
        "user_query": user_query,
        "iterations": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "candidates": top_candidates,
        "selected_article": top_candidates[0],
    }

    if file_result.get("status") == "success":
        selected_article_path = str(Path(str(file_result["path"])).resolve())
        response["answer"] = (
            f"Found best matching article '{best['title']}' ({best['url']}). "
            "Use `run_jq('.content', selected_article_path)` to read the full article."
        )
        response["selected_article_path"] = selected_article_path
        response["selected_article_jq_hint"] = ".content"
    else:
        response["answer"] = (
            f"Found best matching article '{best['title']}' ({best['url']}). "
            "The full article could not be persisted, so only the excerpt is included inline."
        )
        response["selected_article_error"] = file_result

    return json.dumps(response)
