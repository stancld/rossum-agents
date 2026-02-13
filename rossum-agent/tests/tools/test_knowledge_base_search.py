"""Tests for rossum_agent.tools.knowledge_base_search module."""

from __future__ import annotations

import json
import os
import re
import time
from unittest.mock import patch

import pytest
from rossum_agent.tools.knowledge_base_search import (
    _ARTICLE_OUTPUT_LIMIT,
    _GREP_MATCH_LIMIT,
    KBCache,
    _make_snippet,
    kb_get_article,
    kb_grep,
)

_SAMPLE_DATA = {
    "scraped_at": "2026-02-07T12:00:00Z",
    "articles": [
        {
            "slug": "document-splitting-extension",
            "url": "https://knowledge-base.rossum.ai/docs/document-splitting-extension",
            "title": "Document Splitting Extension",
            "content": "# Document Splitting Extension\n\nSplit documents into multiple pages based on rules.",
        },
        {
            "slug": "webhook-configuration",
            "url": "https://knowledge-base.rossum.ai/docs/webhook-configuration",
            "title": "Webhook Configuration",
            "content": "# Webhook Configuration\n\nConfigure webhooks for real-time event processing.",
        },
        {
            "slug": "email-import",
            "url": "https://knowledge-base.rossum.ai/docs/email-import",
            "title": "Email Import",
            "content": "# Email Import\n\nImport documents via email with attachment processing.",
        },
    ],
}


@pytest.fixture
def sample_data():
    return _SAMPLE_DATA


@pytest.fixture
def cache_path(tmp_path):
    return tmp_path / "test_kb.json"


@pytest.fixture
def populated_cache(cache_path, sample_data):
    """Create a KBCache with pre-populated data."""
    cache_path.write_text(json.dumps(sample_data))
    return KBCache(cache_path=cache_path)


class TestKBCache:
    """Test KBCache class."""

    def test_load_from_file(self, populated_cache, sample_data):
        """Test that data is loaded from the JSON file."""
        data = populated_cache.load()
        assert data["articles"] == sample_data["articles"]

    def test_memory_cache_used_on_second_load(self, populated_cache):
        """Test that in-memory cache is used on subsequent loads."""
        data1 = populated_cache.load()
        data2 = populated_cache.load()
        assert data1 is data2

    def test_memory_cache_invalidated_on_mtime_change(self, populated_cache, cache_path, sample_data):
        """Test that memory cache is refreshed when file mtime changes."""
        data1 = populated_cache.load()

        modified_data = {**sample_data, "scraped_at": "2026-02-08T00:00:00Z"}
        cache_path.write_text(json.dumps(modified_data))
        future_mtime = time.time() + 10
        os.utime(cache_path, (future_mtime, future_mtime))

        data2 = populated_cache.load()

        assert data1 is not data2
        assert data2["scraped_at"] == "2026-02-08T00:00:00Z"

    def test_local_path_env_override(self, tmp_path, sample_data, monkeypatch):
        """Test that ROSSUM_KB_DATA_PATH env var overrides the default path."""
        local_file = tmp_path / "local_kb.json"
        local_file.write_text(json.dumps(sample_data))
        monkeypatch.setenv("ROSSUM_KB_DATA_PATH", str(local_file))

        cache = KBCache(cache_path=tmp_path / "other.json")
        data = cache.load()
        assert data["articles"] == sample_data["articles"]

    def test_local_path_env_missing_file(self, tmp_path, monkeypatch):
        """Test that missing file via env var raises FileNotFoundError."""
        monkeypatch.setenv("ROSSUM_KB_DATA_PATH", str(tmp_path / "nonexistent.json"))
        cache = KBCache(cache_path=tmp_path / "other.json")

        with pytest.raises(FileNotFoundError):
            cache.load()

    def test_corrupt_file_raises(self, cache_path):
        """Test that corrupt JSON file raises an error."""
        cache_path.write_text("not valid json{{{")
        cache = KBCache(cache_path=cache_path)

        with pytest.raises(json.JSONDecodeError):
            cache.load()


class TestMakeSnippet:
    """Test _make_snippet helper."""

    def test_normalizes_whitespace(self):
        """Test that newlines and multiple spaces are collapsed to single spaces."""
        text = "Before context.\n\n  Multiple   spaces\nand\nnewlines  here.  After context."
        match = re.search("Multiple", text)
        snippet = _make_snippet(text, match)

        assert "\n" not in snippet
        assert "  " not in snippet
        assert "Multiple spaces and newlines here." in snippet


class TestKbGrep:
    """Test kb_grep tool."""

    def test_empty_pattern_returns_error(self, populated_cache):
        """Test that empty or whitespace-only patterns return an error."""
        with patch("rossum_agent.tools.knowledge_base_search._cache", populated_cache):
            for pattern in ["", "   ", "\t"]:
                result = kb_grep(pattern)
                parsed = json.loads(result)

                assert parsed["status"] == "error"
                assert "Empty pattern" in parsed["message"]

    def test_invalid_regex_returns_error(self, populated_cache):
        """Test that invalid regex patterns return an error."""
        with patch("rossum_agent.tools.knowledge_base_search._cache", populated_cache):
            result = kb_grep("[invalid")
            parsed = json.loads(result)

            assert parsed["status"] == "error"
            assert "Invalid regex" in parsed["message"]

    def test_no_matches(self, populated_cache):
        """Test that no matches returns appropriate message."""
        with patch("rossum_agent.tools.knowledge_base_search._cache", populated_cache):
            result = kb_grep("zzz_nonexistent_zzz")
            parsed = json.loads(result)

            assert parsed["status"] == "success"
            assert parsed["result"] == "No matches found"

    def test_basic_keyword_search(self, populated_cache):
        """Test searching for a keyword that matches article content."""
        with patch("rossum_agent.tools.knowledge_base_search._cache", populated_cache):
            result = kb_grep("webhook")
            parsed = json.loads(result)

            assert parsed["status"] == "success"
            assert parsed["matches"] >= 1
            slugs = [m["slug"] for m in parsed["result"]]
            assert "webhook-configuration" in slugs

    def test_case_insensitive_by_default(self, populated_cache):
        """Test that search is case-insensitive by default."""
        with patch("rossum_agent.tools.knowledge_base_search._cache", populated_cache):
            result = kb_grep("WEBHOOK")
            parsed = json.loads(result)

            assert parsed["status"] == "success"
            assert parsed["matches"] >= 1

    def test_title_match_in_snippet(self, populated_cache):
        """Test that title matches are indicated in snippet."""
        with patch("rossum_agent.tools.knowledge_base_search._cache", populated_cache):
            result = kb_grep("Email Import")
            parsed = json.loads(result)

            assert parsed["status"] == "success"
            assert "[title]" in parsed["result"][0]["snippet"]

    def test_match_limit(self, cache_path):
        """Test that results are limited to _GREP_MATCH_LIMIT."""
        articles = [
            {
                "slug": f"article-{i}",
                "url": f"https://kb.example.com/docs/article-{i}",
                "title": f"Article {i} about testing",
                "content": f"Content about testing article {i}",
            }
            for i in range(_GREP_MATCH_LIMIT + 50)
        ]
        data = {"scraped_at": "2026-01-01T00:00:00Z", "articles": articles}
        cache_path.write_text(json.dumps(data))
        cache = KBCache(cache_path=cache_path)

        with patch("rossum_agent.tools.knowledge_base_search._cache", cache):
            result = kb_grep("testing")
            parsed = json.loads(result)

            assert parsed["status"] == "success"
            assert parsed["matches"] == _GREP_MATCH_LIMIT + 50
            assert len(parsed["result"]) <= _GREP_MATCH_LIMIT

    def test_load_error(self, tmp_path):
        """Test error when KB data can't be loaded."""
        cache = KBCache(cache_path=tmp_path / "nonexistent.json")
        with patch("rossum_agent.tools.knowledge_base_search._cache", cache):
            result = kb_grep("test")
            parsed = json.loads(result)

            assert parsed["status"] == "error"
            assert "Error loading KB data" in parsed["message"]


class TestKbGetArticle:
    """Test kb_get_article tool."""

    def test_exact_slug_match(self, populated_cache):
        """Test fetching article by exact slug."""
        with patch("rossum_agent.tools.knowledge_base_search._cache", populated_cache):
            result = kb_get_article("document-splitting-extension")
            parsed = json.loads(result)

            assert parsed["status"] == "success"
            assert parsed["slug"] == "document-splitting-extension"
            assert parsed["title"] == "Document Splitting Extension"
            assert "Split documents" in parsed["content"]

    def test_partial_slug_match(self, populated_cache):
        """Test fetching article by partial slug."""
        with patch("rossum_agent.tools.knowledge_base_search._cache", populated_cache):
            result = kb_get_article("splitting")
            parsed = json.loads(result)

            assert parsed["status"] == "success"
            assert parsed["slug"] == "document-splitting-extension"

    def test_case_insensitive_partial_match(self, populated_cache):
        """Test partial match is case-insensitive."""
        with patch("rossum_agent.tools.knowledge_base_search._cache", populated_cache):
            result = kb_get_article("WEBHOOK")
            parsed = json.loads(result)

            assert parsed["status"] == "success"
            assert parsed["slug"] == "webhook-configuration"

    def test_not_found(self, populated_cache):
        """Test slug not found returns error."""
        with patch("rossum_agent.tools.knowledge_base_search._cache", populated_cache):
            result = kb_get_article("nonexistent-article")
            parsed = json.loads(result)

            assert parsed["status"] == "error"
            assert "No article found" in parsed["message"]

    def test_content_truncation(self, cache_path):
        """Test that very long content is truncated."""
        long_content = "x" * (_ARTICLE_OUTPUT_LIMIT + 1000)
        data = {
            "scraped_at": "2026-01-01T00:00:00Z",
            "articles": [
                {
                    "slug": "long-article",
                    "url": "https://kb.example.com/docs/long-article",
                    "title": "Long Article",
                    "content": long_content,
                }
            ],
        }
        cache_path.write_text(json.dumps(data))
        cache = KBCache(cache_path=cache_path)

        with patch("rossum_agent.tools.knowledge_base_search._cache", cache):
            result = kb_get_article("long-article")
            parsed = json.loads(result)

            assert parsed["status"] == "success"
            assert len(parsed["content"]) <= _ARTICLE_OUTPUT_LIMIT + 50
            assert parsed["content"].endswith("... (truncated)")

    def test_load_error(self, tmp_path):
        """Test error when KB data can't be loaded."""
        cache = KBCache(cache_path=tmp_path / "nonexistent.json")
        with patch("rossum_agent.tools.knowledge_base_search._cache", cache):
            result = kb_get_article("test-slug")
            parsed = json.loads(result)

            assert parsed["status"] == "error"
            assert "Error loading KB data" in parsed["message"]

    def test_ambiguous_partial_slug_returns_candidates(self, cache_path):
        """Test that multiple partial matches return an error with candidate slugs."""
        data = {
            "scraped_at": "2026-01-01T00:00:00Z",
            "articles": [
                {
                    "slug": "webhook-configuration",
                    "url": "https://kb.example.com/docs/webhook-configuration",
                    "title": "Webhook Configuration",
                    "content": "Configure webhooks.",
                },
                {
                    "slug": "webhook-events",
                    "url": "https://kb.example.com/docs/webhook-events",
                    "title": "Webhook Events",
                    "content": "Webhook event types.",
                },
            ],
        }
        cache_path.write_text(json.dumps(data))
        cache = KBCache(cache_path=cache_path)

        with patch("rossum_agent.tools.knowledge_base_search._cache", cache):
            result = kb_get_article("webhook")
            parsed = json.loads(result)

            assert parsed["status"] == "error"
            assert "Ambiguous slug" in parsed["message"]
            assert "webhook-configuration" in parsed["message"]
            assert "webhook-events" in parsed["message"]

    def test_exact_match_preferred_over_partial(self, cache_path):
        """Test that exact slug match is preferred over partial match."""
        data = {
            "scraped_at": "2026-01-01T00:00:00Z",
            "articles": [
                {
                    "slug": "webhook-configuration-advanced",
                    "url": "https://kb.example.com/docs/webhook-configuration-advanced",
                    "title": "Advanced Webhook",
                    "content": "Advanced content",
                },
                {
                    "slug": "webhook",
                    "url": "https://kb.example.com/docs/webhook",
                    "title": "Webhook",
                    "content": "Basic webhook content",
                },
            ],
        }
        cache_path.write_text(json.dumps(data))
        cache = KBCache(cache_path=cache_path)

        with patch("rossum_agent.tools.knowledge_base_search._cache", cache):
            result = kb_get_article("webhook")
            parsed = json.loads(result)

            assert parsed["status"] == "success"
            assert parsed["slug"] == "webhook"


class TestRealKBData:
    """Regression tests using the real scraped KB data file."""

    def test_grep_finds_document_splitting(self, real_kb_cache):
        """Test kb_grep finds document splitting articles in real data."""
        with patch("rossum_agent.tools.knowledge_base_search._cache", real_kb_cache):
            result = kb_grep("document splitting")
            parsed = json.loads(result)

            assert parsed["status"] == "success"
            assert parsed["matches"] >= 1
            slugs = [m["slug"] for m in parsed["result"]]
            assert any("splitting" in s for s in slugs)

    def test_grep_finds_webhook(self, real_kb_cache):
        """Test kb_grep finds webhook articles in real data."""
        with patch("rossum_agent.tools.knowledge_base_search._cache", real_kb_cache):
            result = kb_grep("webhook")
            parsed = json.loads(result)

            assert parsed["status"] == "success"
            assert parsed["matches"] >= 1

    def test_grep_finds_hooks(self, real_kb_cache):
        """Test kb_grep finds hook-related articles in real data."""
        with patch("rossum_agent.tools.knowledge_base_search._cache", real_kb_cache):
            result = kb_grep("serverless function")
            parsed = json.loads(result)

            assert parsed["status"] == "success"
            assert parsed["matches"] >= 1

    def test_get_article_by_exact_slug(self, real_kb_cache):
        """Test kb_get_article retrieves a real article by exact slug."""
        with patch("rossum_agent.tools.knowledge_base_search._cache", real_kb_cache):
            result = kb_get_article("document-splitting-extension")
            parsed = json.loads(result)

            assert parsed["status"] == "success"
            assert parsed["slug"] == "document-splitting-extension"
            assert len(parsed["content"]) > 100

    def test_get_article_by_partial_slug(self, real_kb_cache):
        """Test kb_get_article retrieves article by partial slug."""
        with patch("rossum_agent.tools.knowledge_base_search._cache", real_kb_cache):
            result = kb_get_article("formula-fields")
            parsed = json.loads(result)

            assert parsed["status"] == "success"
            assert "formula" in parsed["slug"]

    def test_get_nonexistent_article(self, real_kb_cache):
        """Test kb_get_article returns error for nonexistent slug."""
        with patch("rossum_agent.tools.knowledge_base_search._cache", real_kb_cache):
            result = kb_get_article("this-article-does-not-exist-xyz")
            parsed = json.loads(result)

            assert parsed["status"] == "error"
