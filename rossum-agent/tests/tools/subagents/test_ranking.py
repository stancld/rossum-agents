"""Tests for rossum_agent.tools.subagents.knowledge_base.ranking module."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from rossum_agent.tools.subagents.knowledge_base.ranking import (
    _article_excerpt,
    _first_match_position,
    _match_level,
    _match_level_score,
    article_display_title,
    build_direct_result,
    extract_title_from_content,
    find_ranked_articles,
    is_high_confidence_match,
    normalize_text,
    query_terms,
    rank_article,
    serialize_ranked_candidate,
)

_RANKING_MOD = "rossum_agent.tools.subagents.knowledge_base.ranking"


def _article(slug: str, title: str = "", content: str = "", url: str = "") -> dict[str, str]:
    return {
        "slug": slug,
        "url": url or f"https://kb.example.com/docs/{slug}",
        "title": title or slug.replace("-", " ").title(),
        "content": content or f"Content about {slug}",
    }


# ---------------------------------------------------------------------------
# normalize_text
# ---------------------------------------------------------------------------
class TestNormalizeText:
    def test_lowercases(self):
        assert normalize_text("Hello World") == "hello world"

    def test_collapses_non_word_chars(self):
        assert normalize_text("foo-bar_baz") == "foo bar baz"

    def test_strips_edges(self):
        assert normalize_text("  hello  ") == "hello"

    def test_empty(self):
        assert normalize_text("") == ""


# ---------------------------------------------------------------------------
# query_terms
# ---------------------------------------------------------------------------
class TestQueryTerms:
    def test_basic_extraction(self):
        terms = query_terms("document splitting")
        assert "document" in terms
        assert "splitting" in terms

    def test_filters_stopwords(self):
        terms = query_terms("how to configure splitting")
        assert "how" not in terms
        assert "configure" not in terms
        assert "splitting" in terms

    def test_filters_short_terms(self):
        terms = query_terms("a is ok")
        # "a" and "is" are stopwords/short, "ok" is only 2 chars
        assert terms == []

    def test_deduplication(self):
        terms = query_terms("webhook webhook config", "webhook setup")
        assert terms.count("webhook") == 1

    def test_multiple_parts(self):
        terms = query_terms("splitting", "document splitting extension")
        assert "splitting" in terms
        assert "document" in terms
        assert "extension" in terms


# ---------------------------------------------------------------------------
# extract_title_from_content
# ---------------------------------------------------------------------------
class TestExtractTitleFromContent:
    def test_title_prefix(self):
        assert extract_title_from_content("Title: My Article\nSome content") == "My Article"

    def test_h1_heading(self):
        assert extract_title_from_content("Some preamble\n# The Heading\nContent") == "The Heading"

    def test_underline_heading(self):
        content = "My Title\n=========\nContent below"
        assert extract_title_from_content(content) == "My Title"

    def test_dash_underline(self):
        content = "My Title\n---------\nContent below"
        assert extract_title_from_content(content) == "My Title"

    def test_no_title_found(self):
        assert extract_title_from_content("Just some content without headings") == ""

    def test_empty_content(self):
        assert extract_title_from_content("") == ""

    def test_title_prefix_preferred_over_h1(self):
        content = "Title: Preferred Title\n# H1 Title\nContent"
        assert extract_title_from_content(content) == "Preferred Title"


# ---------------------------------------------------------------------------
# article_display_title
# ---------------------------------------------------------------------------
class TestArticleDisplayTitle:
    def test_prefers_content_title(self):
        article = {"title": "Metadata Title", "content": "Title: Content Title\nBody", "slug": "my-slug"}
        assert article_display_title(article) == "Content Title"

    def test_falls_back_to_metadata_title(self):
        article = {"title": "Metadata Title", "content": "No title marker here", "slug": "my-slug"}
        assert article_display_title(article) == "Metadata Title"

    def test_falls_back_to_slug(self):
        article = {"title": "", "content": "No title marker here", "slug": "my-cool-article"}
        assert article_display_title(article) == "My Cool Article"

    def test_empty_article(self):
        result = article_display_title({})
        assert result == ""


# ---------------------------------------------------------------------------
# _article_excerpt
# ---------------------------------------------------------------------------
class TestArticleExcerpt:
    def test_finds_query_match(self):
        article = _article("test", content="Long content with webhook configuration details here")
        excerpt = _article_excerpt(article, "webhook", ["webhook"])
        assert "webhook" in excerpt.lower()

    def test_empty_content(self):
        article = {"slug": "test", "url": "", "title": "", "content": ""}
        assert _article_excerpt(article, "query", ["query"]) == ""

    def test_fallback_to_content_start(self):
        article = _article("test", content="Markdown Content: Article body text here")
        excerpt = _article_excerpt(article, "nonexistent", [])
        assert "Article body text" in excerpt

    def test_long_fallback_truncated(self):
        article = _article("test", content="x" * 1000)
        excerpt = _article_excerpt(article, "nonexistent", [])
        assert len(excerpt) <= 604  # 600 + "..."


# ---------------------------------------------------------------------------
# _first_match_position
# ---------------------------------------------------------------------------
class TestFirstMatchPosition:
    def test_finds_earliest(self):
        content = "aaa bbb ccc ddd"
        pos = _first_match_position(content, ["ddd", "bbb"])
        assert pos == content.index("bbb")

    def test_no_match(self):
        assert _first_match_position("content", ["xyz"]) is None

    def test_empty_patterns(self):
        assert _first_match_position("content", [""]) is None

    def test_all_empty(self):
        assert _first_match_position("content", []) is None


# ---------------------------------------------------------------------------
# _match_level
# ---------------------------------------------------------------------------
class TestMatchLevel:
    def test_exact_slug(self):
        assert _match_level(True, False, True, False, False, 1, 0, 0) == "exact"

    def test_exact_title(self):
        assert _match_level(False, True, False, True, False, 0, 1, 0) == "exact"

    def test_strong_phrase_in_slug(self):
        assert _match_level(False, False, True, False, False, 1, 0, 0) == "strong"

    def test_strong_phrase_in_title(self):
        assert _match_level(False, False, False, True, False, 0, 1, 0) == "strong"

    def test_medium_multiple_slug_terms(self):
        assert _match_level(False, False, False, False, False, 2, 0, 0) == "medium"

    def test_medium_multiple_title_terms(self):
        assert _match_level(False, False, False, False, False, 0, 2, 0) == "medium"

    def test_medium_phrase_in_content(self):
        assert _match_level(False, False, False, False, True, 0, 0, 1) == "medium"

    def test_weak_single_slug_term(self):
        assert _match_level(False, False, False, False, False, 1, 0, 0) == "weak"

    def test_weak_single_content_term(self):
        assert _match_level(False, False, False, False, False, 0, 0, 1) == "weak"

    def test_none(self):
        assert _match_level(False, False, False, False, False, 0, 0, 0) == "none"


# ---------------------------------------------------------------------------
# _match_level_score
# ---------------------------------------------------------------------------
class TestMatchLevelScore:
    @pytest.mark.parametrize(
        ("level", "expected"),
        [("exact", 4), ("strong", 3), ("medium", 2), ("weak", 1), ("none", 0), ("unknown", 0)],
    )
    def test_scores(self, level: str, expected: int):
        assert _match_level_score(level) == expected


# ---------------------------------------------------------------------------
# rank_article
# ---------------------------------------------------------------------------
class TestRankArticle:
    def test_exact_slug_match(self):
        article = _article("document-splitting-extension")
        result = rank_article(article, "document splitting extension")
        assert result["match_level"] == "exact"
        assert "slug_exact" in result["match_reasons"]
        assert result["score"] == 4

    def test_phrase_in_title_strong(self):
        article = _article("webhook-config", title="Webhook Configuration Guide", content="Details here")
        result = rank_article(article, "webhook configuration")
        assert result["match_level"] in {"strong", "exact"}
        assert result["score"] >= 3

    def test_content_only_match_medium(self):
        article = _article("generic-article", title="Some Article", content="This mentions formula fields setup")
        result = rank_article(article, "formula fields")
        assert result["match_level"] == "medium"
        assert "content_phrase" in result["match_reasons"]

    def test_no_match(self):
        article = _article("unrelated", title="Unrelated", content="Nothing relevant")
        result = rank_article(article, "zzz nonexistent topic")
        assert result["match_level"] == "none"
        assert result["score"] == 0

    def test_user_query_adds_terms(self):
        article = _article("webhook", content="Configure webhook events and splitting")
        result = rank_article(article, "webhook", user_query="How to configure webhook and splitting?")
        # user_query adds "splitting" as a term
        assert "content_terms" in result["match_reasons"]

    def test_rank_key_is_tuple(self):
        article = _article("test")
        result = rank_article(article, "test")
        assert isinstance(result["rank_key"], tuple)
        assert len(result["rank_key"]) == 11

    def test_article_preserved(self):
        article = _article("test-slug")
        result = rank_article(article, "test")
        assert result["article"] is article


# ---------------------------------------------------------------------------
# find_ranked_articles
# ---------------------------------------------------------------------------
class TestFindRankedArticles:
    def test_filters_none_matches(self):
        data = {
            "articles": [
                _article("webhook-config", content="Webhook configuration guide"),
                _article("unrelated", title="Unrelated", content="Nothing here"),
            ]
        }
        with patch(f"{_RANKING_MOD}.cache") as mock_cache:
            mock_cache.load.return_value = data
            results = find_ranked_articles("webhook")

        slugs = [r["slug"] for r in results]
        assert "webhook-config" in slugs
        assert "unrelated" not in slugs

    def test_sorted_by_relevance(self):
        data = {
            "articles": [
                _article("email-import", content="Import via email with webhooks mentioned"),
                _article("webhook-configuration", content="Configure webhooks for events"),
            ]
        }
        with patch(f"{_RANKING_MOD}.cache") as mock_cache:
            mock_cache.load.return_value = data
            results = find_ranked_articles("webhook configuration")

        assert results[0]["slug"] == "webhook-configuration"

    def test_empty_kb(self):
        with patch(f"{_RANKING_MOD}.cache") as mock_cache:
            mock_cache.load.return_value = {"articles": []}
            assert find_ranked_articles("anything") == []


# ---------------------------------------------------------------------------
# is_high_confidence_match
# ---------------------------------------------------------------------------
class TestIsHighConfidenceMatch:
    def _candidate(self, level: str) -> dict:
        return {
            "match_level": level,
            "slug": "test",
            "title": "Test",
            "url": "",
            "score": 0,
            "match_reasons": [],
            "excerpt": "",
            "rank_key": (),
            "article": {},
        }

    def test_empty_candidates(self):
        assert is_high_confidence_match([]) is False

    def test_exact_always_high_confidence(self):
        assert is_high_confidence_match([self._candidate("exact")]) is True

    def test_exact_with_multiple(self):
        assert is_high_confidence_match([self._candidate("exact"), self._candidate("strong")]) is True

    def test_single_strong(self):
        assert is_high_confidence_match([self._candidate("strong")]) is True

    def test_strong_with_medium_second(self):
        assert is_high_confidence_match([self._candidate("strong"), self._candidate("medium")]) is True

    def test_strong_with_strong_second(self):
        assert is_high_confidence_match([self._candidate("strong"), self._candidate("strong")]) is False

    def test_single_medium(self):
        assert is_high_confidence_match([self._candidate("medium")]) is True

    def test_medium_with_weak_second(self):
        assert is_high_confidence_match([self._candidate("medium"), self._candidate("weak")]) is True

    def test_medium_with_medium_second(self):
        assert is_high_confidence_match([self._candidate("medium"), self._candidate("medium")]) is False

    def test_single_weak(self):
        assert is_high_confidence_match([self._candidate("weak")]) is False


# ---------------------------------------------------------------------------
# serialize_ranked_candidate
# ---------------------------------------------------------------------------
class TestSerializeRankedCandidate:
    def test_strips_internal_fields(self):
        candidate = rank_article(_article("test-slug"), "test")
        serialized = serialize_ranked_candidate(candidate)
        assert "rank_key" not in serialized
        assert "article" not in serialized
        assert serialized["slug"] == "test-slug"
        assert "match_level" in serialized
        assert "match_reasons" in serialized
        assert "excerpt" in serialized


# ---------------------------------------------------------------------------
# build_direct_result
# ---------------------------------------------------------------------------
class TestBuildDirectResult:
    def test_success_with_file_write(self):
        article = _article("doc-splitting", title="Document Splitting", content="Full article content")
        candidate = rank_article(article, "document splitting")
        candidates = [candidate]

        file_result = json.dumps({"status": "success", "path": "/tmp/knowledge-base-doc-splitting.json"})
        with patch(f"{_RANKING_MOD}.write_file", return_value=file_result) as mock_write:
            result = json.loads(build_direct_result("document splitting", None, candidates))

        assert result["status"] == "success"
        assert result["strategy"] == "direct_lookup"
        assert result["iterations"] == 0
        assert "selected_article_path" in result
        assert "selected_article_jq_hint" in result
        assert "candidates" in result
        assert "selected_article" in result
        mock_write.assert_called_once()

    def test_fallback_when_file_write_fails(self):
        article = _article("test", title="Test Article")
        candidate = rank_article(article, "test")

        file_result = json.dumps({"status": "error", "message": "disk full"})
        with patch(f"{_RANKING_MOD}.write_file", return_value=file_result):
            result = json.loads(build_direct_result("test", "user question", [candidate]))

        assert result["status"] == "success"
        assert "could not be persisted" in result["answer"]
        assert "selected_article_error" in result
        assert result["user_query"] == "user question"

    def test_limits_candidates(self):
        articles = [_article(f"article-{i}") for i in range(10)]
        candidates = [rank_article(a, "article") for a in articles]

        file_result = json.dumps({"status": "success", "path": "/tmp/test.json"})
        with patch(f"{_RANKING_MOD}.write_file", return_value=file_result):
            result = json.loads(build_direct_result("article", None, candidates))

        assert len(result["candidates"]) <= 5
